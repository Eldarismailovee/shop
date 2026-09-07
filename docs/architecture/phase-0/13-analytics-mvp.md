# Phase 0 — Item 13: the analytics MVP decision and the popularity source contract

- **Status:** DONE / FROZEN
- **Date:** 2026-09-06
- **Phase:** 0 — Architecture Freeze
- **ADR:** **none required** — see §1.3. This item selects a branch the master already authorises,
  assigns no owner, moves no boundary and changes no frozen artifact.
- **Related:** [ADR-0003](../../adr/0003-catalog-boundary-vs-storefront-projection.md),
  [ADR-0004](../../adr/0004-four-layer-modular-monolith.md),
  [ADR-0005](../../adr/0005-dependency-and-integration-wiring.md),
  [ADR-0008](../../adr/0008-storefront-listing-projection.md),
  [ADR-0009](../../adr/0009-event-contract-versioning.md),
  [ADR-0010](../../adr/0010-async-failure-domain-isolation.md),
  [ADR-0014](../../adr/0014-storefront-projection-convergence.md),
  [item 6](06-storefront-listing-projection.md) §8, §11 SO5–SO7, §15 RB1–RB8, §18, §24 SEC1–SEC8,
  [item 7](07-storefront-dto-contract.md) DC9,
  [item 8](08-event-registry-versioning.md) §4, KD2, OR7,
  [item 9](09-queue-failure-domain-dlq.md) §12 NX3–NX6, FD10,
  [item 12](12-source-version-guarded-upsert.md) R1–R16, CB1–CB14, TR1–TR8, FS1–FS5, §27,
  master `# 5` principle 37, `# 7.5`, `# 7.6`, `# 10.2`, `# 10.7`, `# 25` MVP line,
  `# 25` Phases 4, 7, 8, 9

---

## 1. Purpose

Item 6 SO5 froze that popularity "may not be invented here" and deferred to item 13 everything
beyond master `# 10.7`'s approved first-party signals. Item 9 NX3 froze that **no** analytics failure
domain is reserved because "whether asynchronous analytics exists at all is item 13's decision".
Item 12 FS5 froze that no analytics projection state is pre-created and that item 13 decides whether
the source exists. Three frozen artifacts point here.

This item answers the question they ask, and nothing more.

### 1.1 What this item freezes

- **The MVP decision** between option A (no `domains/analytics`; popularity from existing first-party
  business facts) and option B (a complete consent-gated analytics domain in MVP), with the
  evaluation recorded (§4). **Option A is selected.**
- The complete **negative list** that "not an MVP module" means, and the deliberate preservation of
  the future module seam (§5, §6).
- `popularity_score`'s **classification and ownership** — derived storefront ranking state owned by
  `application/storefront`, never analytics, commercial, authorization or profile truth (§7).
- The **closed MVP source set** and the resolution of the master's `# 10.7` / Phase 4 discrepancy:
  successful sales and favorites are the automated sources; rating/review is **excluded** from the
  formula while remaining an independent storefront signal; the manual merchandising boost stays
  **excluded and ownerless**, exactly as item 6 SO6b left it; page views are excluded (§8).
- The **per-source contracts**: what each source's owner must expose, and the rule that every
  contribution is a **query over current owner state, never an accumulator** (§9).
- **Source enablement across implementation phases** — a source is active only when its authoritative
  owner and public contract exist, a non-enabled source contributes the policy's neutral value, and
  an *enabled-but-failing* source is a technical fault, never a silent neutral (§10).
- The **scoring-policy contract**: deterministic, pure, bounded, integer, saturating, clock-free with
  an explicit quantized reference instant, no PII — with weights, window and schedule deferred (§11).
- **Sort stability** under a neutral or widely-tied score (§12).
- The **interaction with item 12**, reused unchanged: popularity inputs are ordinary builder inputs
  under CB1–CB14 and FS1–FS5; no new version, guard, partial write or exception is created (§13).
- The **rebuildability proof** for popularity specifically (§14).
- The **privacy boundary**: what MVP guarantees architecturally, stated without legal claims (§15).
- **Recently-viewed** as a browser-local UX that implies no server-side analytics (§16).
- The **admission gate** a future `domains/analytics` must pass, and the aggregate-only shape in
  which a future page-view signal may reach the storefront (§17, §18).
- The confirmation that **no analytics failure domain and no analytics event contract** is created
  (§19).
- **Degradation** rules, an 18-row failure matrix (§20, §21), and the checks **A101–A113**,
  **C148–C160**, **V119–V129** (§22).

### 1.2 What this item does **not** do

No Python package, module, Django app, model, migration, event class, Celery task, queue, schema,
consent UI, tracking script or dependency is created. No analytics table, event type, payload,
queue name or retention store is pre-designed. No scoring weight, window length or recomputation
schedule is chosen.

It also does not reopen a neighbouring item. It changes no rule of items 6, 7, 8, 9 or 12; it
assigns no manual-boost owner (item 6 §27's deferred decision, left where item 6 put it); it does
**not** decide which modules ship at launch — **item 14** owns the MVP/later cut, including whether
favorites and reviews are in it; and it takes no position on item 15.

### 1.3 ADR evaluation — **no new ADR is required**

An ADR is required when a domain boundary moves, a new cross-domain owner is assigned, a public
contract changes shape, or an identity/money/idempotency/consistency rule changes (`docs/adr/README.md`).
Item 13 does none of those. Point by point:

| Would-be trigger | Item 13's position |
|---|---|
| A new domain, module or owner | **None assigned.** Option A creates nothing; `popularity_score`'s owner is already `application/storefront` (ADR-0008, item 6 §4). The one place item 13 *could* have assigned an owner — the manual merchandising boost — is deliberately not taken (§8 MB1–MB4). |
| A boundary moves | **None.** No dependency-matrix cell, no import edge, no `core` submodule allowlist entry, no port. L1–L21 stand unedited. |
| A public contract changes shape | **None.** No `public.py` export list widens *here*; a source owner's eventual batch aggregate selector is that owner's own phase, delivered under item 12 BP3/CB2's existing rule for a missing batch capability. |
| A consistency/concurrency rule changes | **None.** Item 12's protocol is reused verbatim; popularity is an ordinary builder input under FS1–FS5, and FS3 already states that admitting a source costs no token change, no migration and no re-proof. |
| An event contract, queue or failure domain is added | **None.** Item 8's registry still ships empty; item 9 NX3's non-reservation is confirmed rather than amended. |
| A privacy/consent boundary is created | **None created.** Option A introduces **no** new collection, so there is no new consent surface to decide. The consent gate for a future analytics domain is already master `# 10.7`'s and principle 37's requirement, restated here by reference (§18). |

What item 13 actually does is **select a branch the master already wrote**:

- master `# 5` principle 37: "if `domains/analytics` is not implemented in MVP, `popularity_score` is
  computed only from available first-party signals without view tracking (for example sales +
  favorites). One must not depend on a non-existent event pipeline";
- master `# 10.7` **MVP** subsection, which specifies exactly that branch and states that page-view
  tracking "is not a required source and does not block launch";
- master `# 25` MVP line, which places **views-based analytics/popularity** under "can wait after
  launch";
- master `# 25` Phase 9, which lists "consent-gated analytics/view events" as optional work.

Choosing the branch the master pre-authorised, under the conditions the master attached, is routine
MVP scoping inside an already-decided boundary — the README's explicit "does not need an ADR" case.
Consuming ADR-0015 for it would devalue the numbering.

**What would need one, later:** actually introducing `domains/analytics` adds a domain, a consent
gate, an ingestion boundary, a retention/anonymization obligation, a new public contract feeding the
projection and — under item 9 NX3/NX5 — a new logical failure domain. That is its own architecture
and privacy artifact, and an ADR to the extent it creates or changes a boundary this corpus has not
already specified. Item 13 records the admission gate (§17) but does not pre-approve the decision.

### 1.4 Master mapping

| Master | Statement | Status here |
|---|---|---|
| `# 5` principle 37 | Analytics has an owner and a consent contract; if `domains/analytics` is not in MVP, `popularity_score` uses only available first-party signals and must not depend on a non-existent event pipeline | **Selected and implemented in full.** §4 takes the branch; §5's negative list and §19 make "no hidden dependency" checkable; §14's proof makes "no event pipeline" structural rather than promised. |
| `# 10.7` MVP list — paid/delivered sales in a window, favorites, rating/review signal, optional manual boost | The set of **admissible** MVP sources | **Preserved as a closed upper bound** (item 6 SO5's "only"). Item 13 selects the **required** subset from inside it and admits nothing outside it (§8). |
| `# 10.7` "page-view tracking is not a required source and does not block launch" | — | **Strengthened to a prohibition for MVP**: not merely unrequired but absent, so no half-state can exist (§5). This is narrowing within the master's grant, not a departure. |
| `# 10.7` "after the analytics domain appears": it owns event schema, consent gate, ingestion, retention/aggregation, anonymization rules and aggregate delivery; raw metrics never join the request path; the aggregator updates only the changed products' `popularity_score` in batches | — | **Preserved as the admission gate** (§17). One reading is pinned to prevent misuse: "updates only `popularity_score` of the **changed products**" means the *product set* is narrow, **not** that a writer may issue a single-column write — item 12 CB4 forbids a partial-field merge and item 13 grants no exception (§13 IX5). |
| `# 25` MVP line: "views-based analytics/popularity" can wait after launch | — | **Selected.** Note the wording is precise and is honoured precisely: *views-based* popularity waits; `popularity_score` itself does not (§7). |
| `# 25` Phase 4 checklist: "popularity MVP from sales/favorites/manual boost" | The Phase 4 **delivery** list | **Honoured, with the boost's optionality preserved.** `# 10.7` calls the boost *optional* and item 6 SO6b already disables it until an owner exists; item 13 confirms it is not a launch blocker (§8 MB1–MB4). Phase 4 therefore delivers sales + favorites, each subject to §10's enablement rule. |
| `# 25` Phase 7: favorites/compare; rating projection → storefront update | Favorites and reviews are Phase 7 | **Respected by §10**, which is what lets Phase 4 exist before Phase 7 without fake adapters. |
| `# 25` Phase 8: server-side consent; Phase 9: consent-gated analytics/view events | — | **Preserved as the sequencing of any future analytics** (§18). |
| `# 7.5` Recently viewed: `localStorage` suffices; view events *may later* be sent asynchronously to an event/analytics pipeline; never write each card open synchronously to OLTP | — | **Preserved exactly.** MVP recently-viewed is browser-local and writes nothing server-side; the master's "later" path is the Phase 9 consent-gated one (§16). |
| `# 7.6` sketch: `popularity_score integer` | — | **Preserved**: an integer scalar, no float persisted (§11 SP7). |

---

## 2. Frozen principles inherited

| # | Inherited rule | Source |
|---|---|---|
| R1 | `application/storefront` is the sole owner and sole writer of `ProductListingProjection`; a domain does not know it is projected. | item 6 O1, O2; ADR-0008 |
| R2 | Every input to a serving row is obtained through `<domain>.public` **batch** selectors returning frozen DTOs; the builder issues no query against another module's tables. | item 6 O4, BP3; item 12 CB2 |
| R3 | The projection is fully rebuildable from authoritative OLTP; events are acceleration, never the historical source. | item 6 RB1, RB2; item 12 RB4 |
| R4 | **No sort input may exist only as serving state**; every enabled sort key must be reproducible from an authoritative owner, or it may not be enabled at all. | item 6 SO6, SO6b, RB1, V37 |
| R5 | Popularity for MVP uses **only** master `# 10.7`'s approved first-party signals; page-view tracking is not required and does not block launch. | item 6 SO5 |
| R6 | The manual merchandising boost has no assigned owner and stays disabled until one exists; it is never stored in, or edited on, the serving row. | item 6 SO6a, SO6b |
| R7 | Every sort ends in a deterministic unique tie-break key, so equal sort values have exactly one possible order. | item 6 SO2, SO3 |
| R8 | The projection carries public storefront data only: no customer identity, no customer-scoped value, no PII, and no authorization decision reads it. | item 6 SEC1–SEC3; item 7 DC9 |
| R9 | The projection is never checkout truth; a stale row degrades display only, never commercial correctness. | item 6 T3, T6, T7; ADR-0007 |
| R10 | The builder's candidate is the **whole** serving state, built from authoritative reads whose visibility point follows the observation; no partial per-source field merge. | item 12 CB1, CB4, CB10–CB14 |
| R11 | A trigger is a bounded dirty-identity signal, never a row snapshot and never a freshness token. | item 12 TR1–TR3 |
| R12 | Admitting a future source costs one builder input and one trigger — no token change, no migration, no re-proof. | item 12 FS1–FS5 |
| R13 | The write guard is `projection_revision`, an equality CAS owned by `application/storefront`; no other version or freshness mechanism exists. | item 12 RV1–RV12; ADR-0014 |
| R14 | **No analytics failure domain is reserved**, and work whose domain does not exist does not ship. | item 9 NX3, NX4, FD10 |
| R15 | The event registry ships empty; no `event_type` is frozen outside its owning module's phase. | item 8 §4, KD2 |
| R16 | A storefront cache or projection miss never causes a request-time cross-domain join. | item 6 NF1–NF7 |

---

## 3. Vocabulary

| Term | Meaning in this artifact |
|---|---|
| **Popularity source** | An authoritative owner-held business fact admitted as an input to the scoring policy. |
| **Scoring policy** | The named, versioned-by-configuration combination of the enabled source set, the per-source contribution rules, the weights, the window (if any) and the reference instant. Content configuration — never a schema, never a guard. |
| **Enabled source** | A source whose authoritative owner and public batch contract exist and which the active policy includes. |
| **Neutral contribution** | The value a non-enabled source contributes, defined by the policy, so the score is well-defined over any enabled subset. |
| **First-party business fact** | State the platform already holds because another product capability needs it (an order, a favorite), as distinct from data collected in order to measure behaviour. |
| **Behavioural collection** | New data capture whose purpose is measuring what users do — page views, clickstream, session-level tracking, fingerprinting. Absent from MVP. |
| **Product-scoped aggregate** | A value about a Product, carrying no user, session or order identity. The only shape in which a popularity input crosses into the storefront. |

---

## 4. The decision

> ### **Option A is selected. `domains/analytics` is NOT an MVP module.**
>
> `popularity_score` is computed only from existing first-party business facts, through the ordinary
> item 12 builder. No page-view, clickstream or behavioural analytics exists in MVP.

| # | Rule |
|---|---|
| DC1 | The choice is binary and no intermediate state is admissible. Specifically rejected by name: analytics tables that exist while consent "comes later"; page views collected but ignored; raw events retained "in case we need them"; anonymous tracking that bypasses the consent design; and a storefront that depends on an analytics queue nobody implemented. Each is the exact shape principle 37 forbids — a hidden MVP dependency on a pipeline that does not exist. |
| DC2 | Option B was evaluated and rejected. It is not needed for commercial correctness (nothing in checkout, pricing, inventory, payments or authorization reads popularity — R9, §17 of item 6); it would add a domain, a consent gate, an ingestion boundary, a retention/anonymization obligation and a failure domain, all before launch, for a **ranking refinement**; the master itself places consent-gated analytics/view events in Phase 9 and views-based popularity under "can wait"; and `popularity_score` already has a first-party contract that does not need it. Choosing B would be architecture for its own sake. |
| DC3 | Option A is not a degraded fallback. It is the branch master `# 10.7` specifies for exactly this situation, with an approved source list, and item 13 implements it completely rather than partially. |
| DC4 | **The future module seam is preserved, not deleted.** A consent-gated `domains/analytics` remains a legitimate, deliberately deferred Phase 9 capability with a recorded admission gate (§17). "Not in MVP" is a scope decision, not a prohibition on the capability ever existing. |
| DC5 | Item 13 decides **whether an analytics domain exists in MVP**. It does **not** decide which other modules ship at launch — favorites, reviews and every other module belong to **item 14** — and it may not be cited as authority for that cut (§10 EN6). |

---

## 5. What "not an MVP module" means

Frozen as an enumerated negative list, so that no partial implementation can claim compliance.

| # | For MVP, none of the following exists |
|---|---|
| AN1 | An analytics Django app, package, module or ORM model. |
| AN2 | An analytics ingestion endpoint, collector, beacon or write path of any kind. |
| AN3 | A page-view event, a `ProductViewed`-shaped record, or any per-view server write. |
| AN4 | A clickstream, a behavioural event stream, or a session-activity log kept for measurement. |
| AN5 | An analytics worker, task, aggregator or scheduled behavioural job. |
| AN6 | An analytics queue, failure domain, worker pool, DLQ namespace or terminal namespace (R14; item 9 NX3, FD10). |
| AN7 | An analytics retention store, raw-event table, staging table or data-lake export. |
| AN8 | An analytics entry in the event registry — no `event_type`, no payload, no `schema_version`, no consumer declaration (R15). |
| AN9 | A runtime dependency of the storefront, or of any other module, on an analytics module or on a consent state that gates one. |
| AN10 | A third-party analytics SDK, pixel, tag manager or tracking script implied, required or assumed by the architecture. |
| AN11 | A device fingerprint, a fingerprinting library, or any device-identification mechanism used for measurement. |
| AN12 | A hidden session-level tracking store — in PostgreSQL, in Redis, in a log stream or anywhere else — that exists to be aggregated later. |
| AN13 | Server-side "recently viewed" history kept for analysis (§16). |

| # | Rule |
|---|---|
| AN14 | The list is about **collection for measurement**, not about ordinary operational telemetry. Application logs, OpenTelemetry traces, metrics and error reporting (master `# 23`) are unaffected: they exist for operating the system, are governed by items 10 and 9 and by the platform's own privacy rules, and are never a popularity input (V119, A102). |
| AN15 | Nothing in AN1–AN13 is deleted from the architecture's future. The seam is deferred, and §17 states what must be true before it may be built. |

---

## 6. Scope of the decision

| # | Rule |
|---|---|
| SC1 | Item 13 answers the three questions frozen artifacts asked it: does asynchronous analytics exist (item 9 NX3 — **no, not in MVP**); is a popularity source beyond master `# 10.7`'s admitted (item 6 SO5, §27 — **no**); is an analytics builder input pre-created (item 12 FS5 — **no**). |
| SC2 | It answers no other question. In particular it does not decide the MVP/later cut per module (item 14), the read-replica or infrastructure gates (item 15 and master `# 25` Phase 10), the reviews feature's own scope, or any consent category. |
| SC3 | It creates no artifact in `docs/architecture/events/` and adds no row to the event registry or the queue/failure-domain matrix. |

---

## 7. `popularity_score` — classification and ownership

| # | Rule |
|---|---|
| PS1 | `popularity_score` **remains** a legitimate field of the serving row (master `# 7.6`, item 6 §8). Option A removes the analytics domain, not the ranking signal. |
| PS2 | It is **derived storefront ranking state**: a computation over other modules' authoritative state, kept for serving, reconstructible at any time (item 6 §3's "derived serving read model", CT1). |
| PS3 | It is **not** analytics truth, **not** commercial truth, **not** authorization state, **not** a checkout input, and **not** user-profile data. Nothing in checkout, pricing, promotions, inventory, payments or any policy decision reads it (R9). |
| PS4 | Its owner is `application/storefront`, as serving state, per item 6 §4 and item 12. **No `domains/analytics` is required merely because the field is called "popularity."** The name describes what the number is *about*, not who owns it. |
| PS5 | Storing it does not make the storefront the owner of any business fact (item 6 CT1). Sales stay `domains/orders`'; favorites stay their owner's; the storefront owns only the derived score. |
| PS6 | It is **not** exposed publicly: item 7's `ProductCard` carries no popularity field, and item 7 DC9's forbidden-category rule already covers serving bookkeeping. Item 13 adds no public field. Popularity is a **sort input**, and the sort's *name* is public vocabulary while the *number* is not. |
| PS7 | Any per-source input value the serving row may also store (a copied sales aggregate, a favorite count) is likewise internal serving state, subject to PS2/PS6 and to §15's aggregate-only rule. Whether Phase 4 stores such inputs at all, for diagnostics or for cheaper recomputation, is a Phase 4 schema decision — bounded by §11 and §15, and never a public field. |

---

## 8. The MVP source set — closed

> **Enabled automated sources:** owner-defined **successful sales**, and **favorites**.
> **Excluded from the formula:** rating/review, manual merchandising boost, page views.

### 8.1 The closure rule

| # | Rule |
|---|---|
| SR1 | The MVP source set is **closed**: only master `# 10.7`'s four admissible signals may be considered at all (item 6 SO5's "only"), and item 13 selects a subset of them. Nothing outside that list may be admitted without the future-source procedure (§17, item 12 FS1–FS5). |
| SR2 | Every admitted source must satisfy four conditions: **(a)** the fact already exists because another product capability needs it — no fact is collected in order to feed the score; **(b)** it has an explicit authoritative owner; **(c)** its contribution is reproducible from that owner's current retained state, with no event history; **(d)** it crosses to the storefront only as a **Product-scoped aggregate**. |
| SR3 | The set is deliberately the **smallest sufficient** one. A signal that adds a dimension the storefront already surfaces separately, or that has no owner, is excluded rather than admitted "because the master mentions it". |
| SR4 | Exclusion is not rejection. An excluded-but-admissible signal (rating, manual boost) may be admitted later as a **scoring-policy change** (§11 SP10), with no analytics tracking, no new mechanism and no ADR — provided its condition is met. |

### 8.2 Resolving the `# 10.7` / Phase 4 discrepancy

The master lists four signals in `# 10.7` and three in the Phase 4 checklist. They are **not**
contradictory once each is read for what it is, and item 13 pins that reading:

| Master text | What it is |
|---|---|
| `# 10.7` — sales, favorites, rating/review, optional manual boost | The **admissible set**: the closed upper bound on what MVP popularity may use. Item 6 SO5 already read it this way ("uses **only** …"). |
| Phase 4 checklist — "popularity MVP from sales/favorites/manual boost" | The **delivery list** for Phase 4, and it carries `# 10.7`'s own "*optional*" on the boost. |

| # | Rule |
|---|---|
| SR5 | The two lists are reconciled as *permission set* vs *delivery list*, not as a conflict to be split. Rating appears in the permission set and not in the delivery list; the boost appears in both and is marked optional in `# 10.7`. Item 13's selection is consistent with both readings and contradicts neither. |
| SR6 | The result is recorded once, here, so that neither list is later cited alone: **required automated MVP sources = successful sales + favorites; rating/review = excluded from the formula; manual boost = excluded and ownerless; page views = excluded.** |

### 8.3 Sales — **included**

| # | Rule |
|---|---|
| SL1 | **Owner: `domains/orders`.** The storefront reads it through `orders.public`'s batch contract (R2). |
| SL2 | The admitted fact is **owner-defined successful commercial sales for a Product**, aggregated to a Product-scoped count or equivalent measure. |
| SL3 | **Only successful sales contribute.** Created-but-unpaid orders, abandoned checkouts, payment attempts, failed or cancelled operations must not silently count. A "popularity" that rises on abandoned carts measures traffic, not popularity, and would also make the score a weak signal of commercial failure. |
| SL4 | Item 13 does **not** freeze the order-status predicate. The order lifecycle taxonomy belongs to `domains/orders` and item 5's phase. What is frozen is the **semantic requirement** in SL3: whatever predicate the owner defines as a successful commercial sale is the one that contributes, and the storefront neither redefines nor second-guesses it. |
| SL5 | The aggregate is a **query over current retained order truth**, not an accumulator (§9 AG1). A sale that is later cancelled or refunded therefore stops contributing as soon as the owner's predicate stops matching it, with no compensating event and no negative counter. |
| SL6 | Orders retain their own truth for their own reasons (item 5, master `# 8.3`); popularity adds **no** retention obligation to `domains/orders` and does not extend any retention period. If the owner's retention policy eventually shortens what is queryable, the scoring window is bounded by what the owner still holds — a policy consequence, not a reason to keep order data longer. |

### 8.4 Favorites — **included, when its owner exists**

| # | Rule |
|---|---|
| FV1 | **Owner: the module that owns the favorites feature** (master `# 25` Phase 7 — accounts/trust). Item 13 does not name its package, define its model or decide whether it ships at launch (item 14). |
| FV2 | The admitted fact is the **current active favorite count per Product** — durable owner-held state, queried as it stands. |
| FV3 | A counter of historical "favorite added" occurrences is **forbidden** as the source. It cannot reflect removal, it drifts with every duplicate delivery, and its history lives only in consumed events — all three of which violate §9 AG1 and §14. |
| FV4 | **Removal must be reflected.** Because FV2 is a query over current state, un-favouriting reduces the count on the next recomputation with no compensating event and no negative adjustment. |
| FV5 | The count is Product-scoped. **No user identity, no favorite-row identity and no timestamp of any individual action crosses to the storefront** (§15). |
| FV6 | If the owning module does not exist yet, or item 14 places it after launch, favorites is simply **not enabled** and contributes the policy's neutral value (§10). It is not a launch blocker. |

### 8.5 Rating / review — **excluded from the formula**

| # | Rule |
|---|---|
| RA1 | Rating/review is **excluded from the MVP `popularity_score` formula.** |
| RA2 | The reason is not that it is unavailable — reviews are MVP per master `# 25`'s line — but that it **already has its own independent representation** in the serving row and its own place in the contract: `rating_avg_x10` and `rating_count` (master `# 7.6`, item 6 §8) and item 7's optional rating summary on the card. Folding it into popularity would blend two distinct relevance dimensions — *how much this sells* and *how well it is rated* — into one opaque number, double-count a signal the storefront already surfaces, and make both harder to tune. |
| RA3 | It is the smaller sufficient set (SR3): sales and favorites already give a demand signal, and the Phase 4 delivery list does not ask for rating. |
| RA4 | **Rating remains an independent storefront signal and may be admitted into the popularity formula later without any analytics tracking** — it is a scoring-policy change (SP10) over an owner (`domains/reviews`) that already exists, whose aggregate is already rebuildable, and it needs no new mechanism, no ADR and no new collection. |
| RA5 | Excluded means excluded: rating may not enter the score informally — through a "quality" term, a secondary sort blended into the popularity key, or a boost keyed on `rating_avg_x10` — without a recorded policy change (V124). |

### 8.6 Manual merchandising boost — **excluded, and no owner assigned**

| # | Rule |
|---|---|
| MB1 | The manual merchandising boost is **not part of the MVP popularity formula**, and item 13 **does not assign it an owner**. |
| MB2 | This changes nothing: item 6 SO6a explicitly declined to assign the owner and routed it to a later decision; SO6b made "disabled" the default until one exists. Item 13 confirms that state rather than resolving it, because assigning a new authoritative owner for a merchandising value *would* be a boundary decision requiring its own analysis and probably an ADR — and item 13's mandate is the analytics/popularity source question, not merchandising ownership. |
| MB3 | Master `# 10.7` calls the boost **optional**, and the Phase 4 checklist inherits that optionality. It is therefore **not a launch blocker**, and Phase 4 delivers the popularity MVP without it. |
| MB4 | The prohibitions stand unweakened: the boost is never stored only as serving state, never typed into the projection, never editable through an admin screen on the serving row, and never enabled without a durable authoritative source reachable through a legal public contract (R4, R6, item 6 SO6/SO6b, V37, V123). Admitting it later is a scoring-policy change **plus** the owner assignment item 6 §27 still owes. |

### 8.7 Page views — **excluded**

| # | Rule |
|---|---|
| PW1 | Page views, product-detail views, impressions, dwell time, scroll depth, click-through and every other behavioural measure are **excluded from MVP** — not merely unused, but not collected (§5). |
| PW2 | Master `# 10.7` says page-view tracking "is not a required source and does not block launch". Item 13 narrows that grant to an outright MVP absence, so that no partial state can exist and no future reader can find collection code and assume it was sanctioned. Narrowing inside a grant is not a departure. |
| PW3 | A future page-view-derived signal may reach the storefront **only** as a Product-scoped aggregate from a consent-gated `domains/analytics` that has passed §17's admission gate. Raw metrics never join the storefront request path (master `# 10.7`, R16). |

---

## 9. How a source contributes

| # | Rule |
|---|---|
| AG1 | **Every source contribution is a query over the owner's current authoritative state, never an accumulator.** No stored counter is incremented by a consumed event, and no contribution depends on how many messages were delivered. This single rule is what gives removal, cancellation, refund, duplicate delivery and event-history deletion correct behaviour for free (§14, §21 rows 5–8). |
| AG2 | The value crossing the boundary is a **Product-scoped aggregate** in a frozen DTO (R2). No order row, favorite row, user row, review row, identifier, timestamp of an individual action or free-text field crosses. |
| AG3 | Reads are **batched**: a set of Product identities in, a materialised tuple of aggregates out (item 6 BP3, item 12 CB2, BL1). A per-Product query loop is the failure item 6 BP2 names. |
| AG4 | A missing batch capability in an owner becomes a **new public symbol in that owner**, in that owner's own phase — never a models import, a raw query or a cross-boundary join (item 6 BP3, V36). Item 13 defines no signature. |
| AG5 | The owner is **not told why** the aggregate is wanted. A batch aggregate selector is an ordinary public read; it carries no projection vocabulary, no freshness token, no `projection_revision` and no storefront concept (R1, item 12 TR3, RV4). A domain still does not know it is projected. |
| AG6 | No source read is a write. Reading a popularity input mutates nothing in the owning domain and creates no durable record anywhere (item 4's selector semantics). |
| AG7 | The aggregate must be **deterministic given the owner's state and the policy's parameters** — including the window bounds and reference instant when the policy has them (§11 SP4). |

---

## 10. Source enablement across implementation phases

`application/storefront` is Phase 4; orders are Phase 5; favorites are Phase 7. Phase 4 must not
secretly require modules that do not exist.

| # | Rule |
|---|---|
| EN1 | **A popularity source is activated only when its authoritative owner and its public contract actually exist.** Until then it is *not enabled*. |
| EN2 | A non-enabled source contributes the policy's **neutral contribution** — the identity element of the policy's combination rule for that source. The score is therefore well-defined over **any** enabled subset, including the empty one. |
| EN3 | **Neutral is not fabricated data.** No stub adapter, no fake selector, no placeholder aggregate, no "assume zero sales for now" record and no mock module exists. The scoring policy is *defined over the enabled source set*, and a non-enabled source is simply not in it. The distinction is the difference between "the policy has two terms today" and "the policy has five terms, three of which lie". |
| EN4 | **Not enabled ≠ enabled but failing.** A source that is enabled and whose authoritative read fails technically does **not** degrade to neutral: the candidate is not materialised, the unit of work fails as an ordinary transient technical fault under item 12 RT2 / item 9's TF-A handling, and the serving row keeps its previous value. Silently substituting neutral would zero the ranking of the entire catalog on one bad query (§21 row 18, V125, C153). |
| EN5 | Phase 4 can therefore ship a complete, correct storefront with **zero** enabled popularity sources: every product carries the policy's neutral score, the popularity sort is fully determined by its tie-break key (§12), and nothing is stubbed. Sources switch on as their owners land. |
| EN6 | **Which modules actually ship at launch — and therefore which source set is active at launch — is item 14's decision.** Item 13 freezes only the enablement *rule* and must not be cited as authority for whether favorites, reviews or any other module is in MVP (DC5). |
| EN7 | Enabling or disabling a source is a **scoring-policy change** (SP10), converged through item 12's ordinary rebuild path. It is not a data migration, not an analytics-event migration, and not a version bump of anything. |

---

## 11. The scoring policy

| # | Rule |
|---|---|
| SP1 | The score is produced by a **pure, deterministic, total** function of: the enabled source set, that set's Product-scoped aggregates, and the policy's explicit parameters. Same inputs → same result, in every process, in every phase, on every rebuild. |
| SP2 | The function reads **no ambient state**: no clock, no random source, no environment lookup, no cache, no request context, no actor, no session, no feature flag consulted from inside it. Everything it depends on is an argument. |
| SP3 | It performs **no I/O**. Source reads happen in the builder, before the function is applied, under item 12 CB10–CB14. |
| SP4 | **If the policy has a time window or decay, its reference instant is an explicit input, never a clock read** — and it is **quantized** by the policy (to a bucket the policy defines) so that: every builder running within one bucket computes the same score; a rebuild within the same bucket reproduces the incrementally computed state exactly, preserving item 12 C26/RB4; and crossing a bucket boundary is a **policy input change** that converges through the ordinary rebuild path, not an unexplained drift. |
| SP5 | Consequently **wall-clock time never makes the whole catalog continuously dirty.** Window advancement is realised by **bounded, scheduled recomputation** over bounded product sets, never by request-time recalculation and never by a sweep that must touch every row every second. Because a recomputation that yields an unchanged score writes nothing (item 12 NO1), a sweep over a stable catalog costs reads and produces zero row writes. |
| SP6 | Whether the MVP policy uses a rolling window at all, or an unbounded aggregate over retained owner truth, is a **Phase 4 / merchandising-configuration** decision bounded by SP1–SP5. Master `# 10.7` describes a window; item 13 requires only that if one exists it obeys SP4. |
| SP7 | The stored score is an **integer** (master `# 7.6`'s `popularity_score integer`). **No floating-point value is persisted.** Intermediate arithmetic may use exact decimal where a ratio or weight requires it, converted to the integer representation by an explicit, deterministic rule — never by an implicit float cast (the discipline item 11 froze for money, applied here for the same reason: reproducibility). |
| SP8 | **Overflow and saturation are deliberate.** The function's range is bounded and its behaviour at the bound is defined and documented; it never wraps, never overflows silently and never becomes negative by accident. The concrete bound follows the chosen representation in Phase 4. |
| SP9 | **No user identity, no session identity, no PII and no personalization input appears anywhere in the score, in its inputs or in its intermediate values.** |
| SP10 | **Weights, window length, quantization granularity, the enabled source set and the recomputation schedule are policy configuration, decided in Phase 4 / merchandising — not here.** Item 13 invents no weight: the master states none, and a number invented in Phase 0 would be a merchandising decision disguised as an architectural one. |
| SP11 | A policy change is a **content** change: it makes the affected products dirty and converges through item 12's protocol. It is **not** a schema change, not an event version, not a guard change and not a migration. |
| SP12 | The active policy must be **recorded and reproducible** — its parameters are inputs to a rebuild, so a rebuild states which policy it applied. How the policy is stored and versioned in configuration is Phase 4; that it must be explicit is frozen here. |
| SP13 | **No `popularity_version` and no popularity-specific freshness token exists.** `popularity_score` is *content*; `projection_revision` protects the *write* (item 12 RV10). Two scores computed under different policies are two contents, never two versions to be compared for freshness (V120's neighbours, A112). |

---

## 12. Sort stability

| # | Rule |
|---|---|
| SS1 | The popularity sort compiles, like every other, to a whitelisted `(popularity_score, …, unique tie-break key)` tuple over projection columns (R7, item 6 SO1–SO3). |
| SS2 | **A neutral or widely shared score is not a defect.** With no enabled source, every product carries the same neutral value and the order is fully determined by the deterministic tie-break — stable across requests, across pages and across a keyset walk (item 6 SO2, PG6, C31). The same holds for any large group of products that legitimately tie. |
| SS3 | The global popularity sort uses **no** random tie-break, **no** request time, **no** session or cookie value, **no** actor identity and **no** personalized behaviour. It is one global anonymous ordering, identical for every viewer (item 6 SEC1, C34). |
| SS4 | Future personalized recommendations, if they ever exist, are a **different feature** with a different model, a different contract and their own security review (item 6 SEC4). They are never this field and never a branch inside this sort. |
| SS5 | Whether the popularity sort is *offered* in the UI when the enabled source set is empty, and what the default listing sort is, are Phase 4 / merchandising decisions (master `# 10.2`). The architecture guarantees determinism either way. |
| SS6 | A stale score orders slightly stale data. That is display staleness under the existing eventual-consistency model, never a correctness failure (item 6 SO7, T7). |

---

## 13. Interaction with item 12 — unchanged

| # | Rule |
|---|---|
| IX1 | **Item 12's mechanism is reused verbatim.** A sales, favorite or policy change that can affect popularity is simply another reason a Product may be dirty. The writer still does: observe `projection_revision` → authoritative reads → whole-candidate rebuild → equality CAS → discard-and-rebuild on a guard miss. |
| IX2 | Popularity source reads are ordinary builder reads and obey **CB10–CB14** in full: the visibility point of every read is established after the observation; **no cached or Redis-held aggregate may finalize the value without authoritative verification**; no asynchronously lagging replica is correctness truth; a snapshot, if used, is opened after the observation; and the reasoning is about state-visibility chronology, not value trajectory — a popularity aggregate legitimately moving `40 → 55 → 40` is convergence, not regression. |
| IX3 | **No popularity source supplies a freshness token**, no source knows it is projected, and no source reads or writes `projection_revision` (R1, item 12 TR3, RV4, A92). |
| IX4 | Popularity triggers are **dirty-identity signals** under TR1–TR8: they name affected Products, carry no score, and are never trusted as a row snapshot. A trigger's payload may not carry a computed score for the writer to store (TR2, A96). |
| IX5 | **No partial write.** `popularity_score` is never updated alone; it is part of the whole candidate (item 12 CB4). Master `# 10.7`'s future-aggregator sentence — "updates only `popularity_score` of the changed products in batches" — is read as *only the changed products*, which is the coalesced batch model item 12 already freezes; it is **not** a licence for a single-column write, and item 13 grants no exception (§1.4). |
| IX6 | Adding sales, favorites or any future source uses **FS1–FS5 exactly as written**: one more builder input, one more trigger, one more per-consumer routing decision. No token change, no migration of guard state, no re-proof of item 12 §27. |
| IX7 | **There is no analytics exception to item 12** — no force write, no bypass, no privileged aggregator, no second writer, no separate popularity update path (item 12 GM8, O1). |
| IX8 | No request-time popularity computation exists: the listing path reads the projection, and never an order, favorite or review table (R16, item 6 QB3, C25, A109). |

---

## 14. Rebuildability

> **Delete all Outbox history, delete all broker history, delete the projection, and rebuild from
> current authoritative business state under the recorded policy → the same logically correct
> popularity result.**

| # | Rule |
|---|---|
| RD1 | Popularity participates in the **canonical item 12 builder**. There is no separate popularity build path, no incremental-only shortcut and no second implementation. |
| RD2 | A full rebuild reconstructs the score from **current authoritative business state + the explicit scoring policy** — never from analytics history, event history or a retained counter. |
| RD3 | Reconciliation detects and repairs popularity drift through the **same** item 12 protocol, with no `force=True` and no bypass (item 12 RC1, RC2). |
| RD4 | The proof, in one line each: <br>• every contribution is a query over **current** owner state, not an accumulator (AG1); <br>• the combining function is pure and total over those aggregates plus explicit policy parameters (SP1–SP3); <br>• the only time-dependence is an explicit **quantized reference instant** supplied as a parameter (SP4); <br>• therefore a rebuild that reads the same owner state and applies the same policy computes the same integer, and one that reads newer owner state computes the newer correct integer. **No consumed message, retained partition or historical counter is consulted at any step.** ∎ |
| RD5 | The one honest boundary: the score is reproducible **within the recorded policy's parameters**. A rebuild run under a different policy — different weights, a different enabled source set, a later quantization bucket — produces that policy's correct value, which is a *content* difference and a converged forward state, not a regression and not a rebuild failure (SP11, item 12 §27.3's chronology-not-trajectory rule). Item 12 C26's "rebuild reproduces serving state" is asserted, as it always was, **given the same inputs** — and SP12 makes the policy one of them. |
| RD6 | A source's own retention policy bounds what any rebuild can reconstruct (SL6). That is a property of the owner's truth, not a defect of the projection, and it is never a reason to retain event history as a shadow source. |

---

## 15. Privacy boundary

Stated as architectural guarantees. This artifact makes **no legal claim** and no assertion about
what any jurisdiction requires.

| # | Rule |
|---|---|
| PV1 | The relevant architectural distinction is between **existing first-party business facts** — an order that exists because someone bought something, a favorite that exists because someone saved it — and **new behavioural collection** created to measure what users do. MVP uses only the former and creates none of the latter. |
| PV2 | The architecture therefore guarantees, checkably: **no new collection is introduced**; **no raw behavioural stream exists**; **no individual user, session or device identifier is copied into `ProductListingProjection`**; **no raw Order, User, Favorite or Review row is denormalized into it**; **no PII forms any part of `popularity_score` or its inputs**; and **guest browsing does not become server-side analytics in order to improve ranking**. |
| PV3 | Only **Product-scoped aggregates** cross into the storefront (AG2). The storefront receives "this Product has N successful sales in the window" — never who bought, when, at what price, from where, or on what device. |
| PV4 | Using existing sales and favorites data for ranking remains subject to the platform's privacy policy, purpose-limitation review and applicable legal review — which are owned by the privacy/security phases and by the business, not by this artifact. Item 13 **does not** claim that first-party business data never requires consent or a lawful basis in any jurisdiction; that would be legal advice an architecture document cannot freeze. What it freezes is the **architectural** fact that MVP adds no behavioural collection and no new personal-data category. |
| PV5 | If purpose or legal review later restricts a source, the response is a **scoring-policy change** — disable the source, the score falls back to the remaining enabled set through the ordinary rebuild path (EN7, SP10). Nothing breaks, nothing needs migrating, and no data must be extracted from the projection, because none of it is there (PV2). This gracefulness is a designed consequence of the aggregate-only boundary, not luck. |
| PV6 | The projection's existing rules apply unchanged: public storefront data only, no customer-scoped value, no authorization decision over it, anonymous and authenticated requests receive identical projection-sourced content (item 6 SEC1–SEC3, C34). |

---

## 16. Recently viewed is not analytics

| # | Rule |
|---|---|
| LV1 | Master `# 7.5`'s recently-viewed UX is **browser-local**: a bounded list of Product/SKU identifiers in `localStorage`, working for guests, costing PostgreSQL nothing. |
| LV2 | **It implies no server-side view event, no `ProductViewed` record, no per-view write and no analytics of any kind.** Rendering a product page writes nothing for measurement. |
| LV3 | Master `# 7.5`'s own "if later needed" clause — cross-device history, email/push scenarios, viewed-product analytics — is precisely the deferred Phase 9 path, consent-gated, and is **not** MVP. |
| LV4 | Master `# 7.5`'s standing prohibition is preserved: a card open is never written synchronously to a hot OLTP table. |
| LV5 | The local list is never a popularity input. It is per-browser state the server never sees, and admitting it would be behavioural collection through the back door (PW1). |

---

## 17. The admission gate for a future `domains/analytics`

Not designed here. Only the gate is frozen, so that a future implementation cannot arrive piecemeal.

| # | Rule |
|---|---|
| FA1 | Before a page-view or other behavioural signal may exist, a `domains/analytics` must own **all** of: the analytics event semantics and schema; the **consent gate**; ingestion; retention; aggregation; anonymization and privacy handling; and the aggregate publication contract (master `# 10.7`). |
| FA2 | **No other module may pretend to own those responsibilities.** An "interim" collector in `interfaces/*`, a tracking table in another domain, a task that writes raw views, or an integration adapter that ships events to a vendor are each the piecemeal arrival FA1 exists to prevent (V122). |
| FA3 | A future signal reaches the storefront **only as a Product-scoped aggregate through an explicit public contract**, delivered in coalesced batches. **Raw page-view or clickstream data never joins the storefront request path** (master `# 10.7`, R16). |
| FA4 | Admission uses item 12 **FS1–FS5 exactly as written**: one more builder input, one more trigger, one more routing decision. It changes no token, no guard, no `projection_revision` semantics and no proof (C158). |
| FA5 | Its aggregate must satisfy §9 in full — a query over the analytics owner's current retained state, batched, Product-scoped, carrying no identity — and §14: **the storefront's rebuild must not require analytics event history.** If the analytics owner cannot answer "what is this Product's current aggregate" from its own retained state, the source is not admissible. |
| FA6 | It must satisfy item 6 RB1's rule that an enabled sort input is reproducible from an authoritative owner, and item 6 SO5's placement of aggregates-in-batches rather than raw metrics in requests. |
| FA7 | Under item 9 NX3/NX5, it needs a **new logical failure domain** with every matrix cell filled, a named operational owner and runbook, a criticality with justification, a retry class, a terminal namespace and a declared capacity relationship to every existing domain — and, per NX4, it may never be routed into a `CRITICAL` or `IMPORTANT` domain to avoid provisioning a `BEST_EFFORT` one. |
| FA8 | Its event contracts are registered under item 8 by their owner, in that owner's phase. **Item 13 pre-creates no table, model, `event_type`, payload, `schema_version`, queue, consumer declaration or retention period.** |
| FA9 | **Scope limit, frozen now:** a future analytics domain owns behavioural metrics and nothing else. It does **not** become the owner of Orders, Favorites, Reviews or `ProductListingProjection`, and it never becomes the source of price, inventory, payment or any other commercial truth. It may contribute one aggregate popularity input. Nothing more (V128). |
| FA10 | It also never **rewrites historical business truth**: it derives metrics from facts other modules own, and no analytics process corrects, backfills or adjusts an order, a favorite, a review or an order snapshot (item 6 CT2, item 12 RC7). |
| FA11 | Its introduction requires its own architecture and privacy artifact, and an ADR to the extent it creates or changes a boundary this corpus has not already specified (§1.3). |

---

## 18. Consent lifecycle — the invariant only

| # | Rule |
|---|---|
| CS1 | **No consent-gated event is collected before the applicable consent state permits collection.** Collection is gated at the boundary, not filtered afterwards: "collect now, honour consent at query time" is not compliance with this rule. |
| CS2 | Withdrawal and revocation handling, retention periods, deletion and anonymization, and any lawful exceptions belong to the **future analytics and privacy design** — not to this artifact. |
| CS3 | No consent category, cookie-banner state machine, storage format or retention number is designed here. Server-side consent infrastructure is master `# 25` **Phase 8**; consent-gated analytics/view events are **Phase 9**. |
| CS4 | Because MVP collects nothing behavioural, **MVP has no analytics consent dependency at runtime**: no code path branches on an analytics consent state, and no storefront behaviour changes with it (AN9). This is the cleanest possible starting position for Phase 8's consent work. |
| CS5 | CS1 binds whoever eventually builds analytics; it is stated here so that the gate exists in writing before the temptation does. |

---

## 19. No failure domain, no event contract

| # | Rule |
|---|---|
| NQ1 | **No analytics failure domain is created or reserved** — no `core.analytics`, no `ext.analytics`, no queue, no worker pool, no DLQ or quarantine namespace. Item 9 NX3 and FD10 stand exactly as written and are **not** edited by item 13; item 13 supplies the answer NX3 was waiting for, and the answer is that the non-reservation is correct. |
| NQ2 | Item 9 NX4 applies with full force: analytics work may never be routed into an existing `CRITICAL` or `IMPORTANT` domain to avoid provisioning a `BEST_EFFORT` one. **Where the domain does not exist, the work does not ship.** |
| NQ3 | Popularity recomputation itself is ordinary projection work and runs in the **existing** `core.projection.*` domains (item 9 PJ1). Scheduled window recomputation (SP5) is rebuild-shaped work for `core.projection.rebuild`; a source-change-driven refresh is incremental work. **No new domain is needed for popularity, because popularity is not a workload — it is a field of a candidate the projection builder already builds.** |
| NE1 | **No `event_type` is created.** Item 8's registry ships empty and item 13 adds nothing to it. |
| NE2 | The only requirement item 13 places on future source owners is semantic: **a business fact change that affects the active scoring policy must eventually cause the affected Products to be rebuilt or reconciled.** How — a coalesced batch trigger, a dirty-set entry, or reconciliation alone for a low-rate signal — is the owning module's implementation-phase decision, registered under item 8 by that owner. |
| NE3 | **No event name is frozen, illustrated or implied** for orders, favorites, reviews or analytics. Speculative names are avoided entirely rather than labelled non-binding, because a name written in a frozen artifact acquires gravity it was not granted (V122's neighbours). |
| NE4 | A low-rate or low-value source may legitimately rely on **scheduled reconciliation alone** rather than on a dedicated trigger, provided convergence stays within the projection's freshness threshold (item 6 CM7, CM8). Popularity does not have to be event-driven to be correct. |

---

## 20. Degradation

| # | Rule |
|---|---|
| DG1 | Popularity is a **ranking and display** concern. A failure of any popularity input, aggregate query or recomputation must never fail or degrade checkout, price calculation, reservation, payment or authorization, and must never cause a request-time cross-domain fallback (R9, R16, item 6 T7, NF1–NF7). |
| DG2 | A temporarily stale `popularity_score` is **acceptable** under the existing storefront eventual-consistency model (item 6 CM1–CM5, SO7). |
| DG3 | **Degradation is never silent substitution.** A failing enabled source does not become neutral (EN4), does not become zero, does not become a random value and does not become last week's cached number promoted to truth. The row keeps the last correctly computed value until convergence. |
| DG4 | Persistent failure to recompute is an **operational** fault: it surfaces through the existing projection freshness metric and alert (item 6 CM7–CM10, item 12 OM1), with the runbook response being repair or a targeted rebuild — never a read-path change. |
| DG5 | If a source must be turned off for an extended period, that is a deliberate **policy change** (SP10, PV5), converged through the ordinary rebuild path and recorded — not an incident workaround left in place. |

---

## 21. Failure matrix

Columns: does the **request path** fail; does **commercial correctness** change; may **stale
popularity** persist; what **drives convergence**; is **consent** involved; is any **PII** persisted
in the storefront.

| # | Situation | Request path | Commercial | Stale popularity? | Convergence driver | Consent | PII in storefront |
|---|---|---|---|---|---|---|---|
| 1 | No analytics domain exists (the MVP state) | No — nothing depends on it (AN9) | None | No — this is the normal state, not a degradation | n/a | Not involved — nothing is collected | None |
| 2 | No page-view consent exists / none is asked for | No | None | No | n/a | **Not involved in MVP**: no consent-gated collection exists (CS4) | None |
| 3 | Sales source exists, favorites not implemented yet | No | None | No — the policy is defined over the enabled set (EN2) | n/a; favorites simply is not a term | Not involved | None |
| 4 | Favorites later becomes available | No | None | Briefly, until the rebuild lands | Policy change → bounded rebuild through item 12 (EN7, SP11) | Not involved | None |
| 5 | Duplicate favorite trigger | No | None | No | The rebuild recomputes from current state; an unchanged score writes nothing (AG1, item 12 NO1) | Not involved | None |
| 6 | Favorite removed | No | None | Until the next recomputation | Count is a query over current state, so removal is reflected with no compensating event (FV4) | Not involved | None |
| 7 | A sale is later cancelled or refunded per owner semantics | No | None — order truth is the owner's and is unaffected by ranking | Until the next recomputation | The owner's predicate stops matching it; the aggregate drops (SL5) | Not involved | None |
| 8 | Old Outbox / broker history removed | No | None | No | Nothing consulted it (AG1, RD2, RD4) | Not involved | None |
| 9 | Storefront projection fully rebuilt | No — the storefront stays servable (item 6 RB6) | None | Converges progressively | Current owner state + recorded policy (RD2, RD5) | Not involved | None |
| 10 | Analytics service/domain absent | No | None | No | n/a — it is not an input | Not involved | None |
| 11 | A future analytics domain exists but is unavailable | No | None | Yes, for its term only | Its own retry/reconciliation; the remaining terms are unaffected; EN4 applies — no neutral substitution | Its own gate, unchanged | None (aggregate only, FA3) |
| 12 | A future analytics aggregate is stale | No | None | Yes, bounded by the freshness threshold | Ordinary projection convergence (item 6 CM7) | Its own gate | None |
| 13 | User browses anonymously with no tracking consent | No | None | No | n/a — **no server-side analytics write occurs**, and the anonymous and authenticated views are identical (item 6 C34) | Not involved: nothing is collected either way | None |
| 14 | Many products share the same score (including the all-neutral case) | No | None | n/a | n/a — the deterministic tie-break fully determines the order (SS2) | Not involved | None |
| 15 | Scoring-policy weights change | No | None | Until the rebuild lands | Policy change → bounded rebuild; content change, not a version bump (SP11, SP13) | Not involved | None |
| 16 | Manual boost absent (the MVP state) | No | None | No | n/a — it is not a term; the boost stays disabled and ownerless (MB1–MB4) | Not involved | None |
| 17 | Rating excluded (the MVP decision) / later admitted | No | None | Briefly on admission | Rating remains an independent serving field either way; admission is a policy change (RA1–RA4) | Not involved — reviews are first-party content, not tracking | None |
| 18 | A source aggregate query fails technically | **No** — the read path serves the existing row | None | Yes, until repair | The unit of work fails as a transient technical fault (item 12 RT2, item 9 TF-A); the row keeps its previous value; **no neutral substitution** (EN4, DG3) | Not involved | None |

**Core invariant:** every commercial cell is `None`, because nothing commercial reads popularity
(R9, PS3). Every PII cell is `None`, because only Product-scoped aggregates cross the boundary
(PV2, PV3). No row makes the request path fail, because popularity is display state and the read
path never recomputes it (IX8, DG1).

---

## 22. Checks a later phase must implement

These **extend** the enforcement maps of items 3, 4, 5, 6, 7, 8, 9, 10, 11 and 12; those remain
authoritative and unchanged. Nothing here is implemented in Phase 0.

### 22.1 Import graph (`L` series)

**No new `L` rule and no new `core` allowlist entry.** Option A adds no module, so there is no new
edge to permit or forbid; the popularity source reads use `application/storefront` →
`<domain>.public`, already `PUBLIC ONLY` per item 3 §4.3. L1–L21 stand unedited.

### 22.2 Static / AST (continuing the `A` series)

| # | Rule |
|---|---|
| A101 | **No analytics module exists** while option A stands: no package, app, model, admin or migration under an analytics name anywhere in the source tree (AN1). |
| A102 | **No behavioural collection:** no page-view/impression/clickstream/dwell model, table, ingestion endpoint, beacon route, collector task or client-side tracking script; and no ordinary telemetry (logs, traces, metrics) is wired into a popularity input (AN2–AN4, AN14). |
| A103 | **No analytics transport:** no queue name, logical failure domain, worker pool, DLQ or terminal namespace matching an analytics workload; the queue/failure-domain matrix contains no analytics row (AN6, NQ1). |
| A104 | **No storefront dependency on analytics:** no module under `application/storefront` imports, references or feature-flags an analytics module, and the builder's input set contains no analytics source (AN9). |
| A105 | **No identity in the projection:** no `user_id`, `customer_id`, `session_id`, `device_id`, email, order identifier, favorite-row identifier or other per-actor value appears on a storefront projection model or in any popularity input DTO (PV2, PV3; extends item 6 C34). |
| A106 | **No accumulator:** no code path increments, decrements or otherwise mutates a stored popularity input in response to a consumed message; every contribution originates in a query over current owner state (AG1). |
| A107 | **No boundary shortcut:** no popularity input is obtained by importing another module's models, issuing a raw query against its tables, or joining across the boundary; all inputs come from `<domain>.public` batch selectors (R2, AG3, AG4; extends item 6 V36 and item 12 CB2). |
| A108 | **Authoritative reads:** every active popularity source read satisfies item 12 CB10–CB14 — visibility point after the observation, no cache/Redis value and no lagging-replica read finalizing the value, any snapshot opened after the observation (IX2). |
| A109 | **No request-path popularity:** no listing, search, facet or autocomplete request reads an order, favorite or review table, and no storefront selector computes or recomputes a score (IX8; extends item 6 C25, QB3). |
| A110 | **Impersonal sort:** the global popularity sort's compiled tuple contains no session, cookie, actor, request-time or random component (SS3). |
| A111 | **No third-party tracking:** no analytics SDK, pixel, tag manager or fingerprinting library appears in dependencies, templates, base layouts or CSP allowlists (AN10, AN11). |
| A112 | **No parallel version mechanism:** no `popularity_version`, popularity freshness token, popularity-specific guard or per-field write predicate exists; `projection_revision` remains the only write guard (SP13; extends item 12 A91, A93). |
| A113 | **Clock-free scoring:** the scoring function reads no clock, no random source and no ambient configuration; its reference instant, window bounds and weights are explicit parameters (SP2, SP4). |

### 22.3 Behavioural / contract tests (continuing the `C` series)

| # | Rule |
|---|---|
| C148 | **Launch without analytics:** with no analytics module present and zero enabled popularity sources, every listing, search and facet endpoint serves correctly within its query budget, and the popularity sort returns a deterministic, repeatable order (EN5, SS2). |
| C149 | **Rebuild after history deletion:** with every Outbox partition, retained payload and broker message deleted, a full rebuild reproduces the same `popularity_score` for the same owner state and policy (RD2, RD4). |
| C150 | **A source is enabled later:** switching favorites on drives a bounded rebuild through item 12, produces the newer correct scores, requires no migration and no version bump, and leaves `projection_revision` semantics untouched (EN7, SP11, SP13). |
| C151 | **Favorite add and remove converge:** adding a favorite raises the contribution and removing it lowers it, in both cases after ordinary convergence and with no compensating event (FV2, FV4). |
| C152 | **Sales changes converge**, including a sale that later leaves the owner's success predicate (cancellation or refund) reducing the contribution (SL3, SL5). |
| C153 | **Enabled source unavailable:** with the source's authoritative read failing, the serving row keeps its previous score, the request path is unaffected, no commercial operation changes, and the value is **not** replaced by neutral or zero (EN4, DG3). |
| C154 | **Anonymous browsing emits no analytics:** rendering listing and product pages as a guest produces no server-side view record, no behavioural write and no outbound tracking request (LV2, PW1, AN2–AN4). |
| C155 | **Determinism:** the same authoritative inputs and the same policy parameters — reference instant included — yield the same score in every process and on every run (SP1–SP4). |
| C156 | **Policy change is bounded and whole-candidate:** changing weights, the window or the enabled set drives a bounded rebuild, writes whole candidates, and performs no single-column `popularity_score` update (SP11, IX5). |
| C157 | **Tie stability:** with many products sharing a score, a full keyset walk returns each product exactly once in a stable order, with no gaps or duplicates, across repeated requests (SS2; extends item 6 C31). |
| C158 | **Future aggregate admissible:** a Product-scoped aggregate from a hypothetical new source can be added as a builder input without changing `projection_revision` semantics, the guard predicate or the item 12 proof (FA4, IX6). |
| C159 | **No PII reaches the storefront:** the serving row and every popularity input DTO contain no user, session, device or order identity, asserted by field inspection rather than by convention (PV2, A105). |
| C160 | **Neutral determinism:** with a source not enabled, every product's score equals the policy's defined value for the enabled subset, identically across builders and across a full rebuild — and no stub, mock or placeholder module participates (EN2, EN3). |

### 22.4 Review-only (continuing the `V` series)

| # | Rule |
|---|---|
| V119 | Behavioural collection appearing "for later" — a view counter, an impression log, a session-activity table, a "temporary" tracking field, or operational telemetry quietly repurposed as a popularity input (AN2–AN4, AN12, AN14). |
| V120 | An accumulator-shaped popularity input: a counter incremented by consumed events, whose history exists only in messages (AG1, FV3). |
| V121 | A popularity input read from Redis, a fragment cache or a lagging replica and treated as final truth (IX2, item 12 CB11). |
| V122 | An analytics module, table, queue, event type or collector arriving before §17's admission gate is satisfied — including an "interim" collector placed in an interface, a task or an integration adapter (FA1, FA2, NE3). |
| V123 | A manual merchandising boost stored in, typed into, or edited on the serving row, or enabled without the owner item 6 §27 still owes (MB4, item 6 SO6b, V37). |
| V124 | Rating quietly entering the popularity formula — as a "quality" term, a blended secondary key or a boost keyed on `rating_avg_x10` — without a recorded policy change (RA1, RA5). |
| V125 | An enabled-but-failing source silently degraded to neutral, zero or a cached value, instead of failing the unit of work (EN4, DG3). |
| V126 | Personalization creeping into the global popularity sort — a session, actor, cookie, recently-viewed list or recommendation signal influencing the shared ordering (SS3, SS4). |
| V127 | A third-party analytics SDK, pixel, tag manager or fingerprinting library added to the front end or to dependencies (AN10, AN11). |
| V128 | A future analytics domain claiming ownership of Orders, Favorites, Reviews or `ProductListingProjection`, becoming a source of commercial truth, or backfilling/adjusting historical business records (FA9, FA10). |
| V129 | Item 13 cited as authority for something it did not decide — the MVP/later module cut (item 14), whether favorites or reviews ship, an infrastructure gate (item 15), or a manual-boost owner (item 6 §27) (DC5, EN6, SC2). |

---

## 23. Acceptance checklist

- [x] 1. The MVP decision is explicit and binary: **`domains/analytics` is NOT an MVP module** (§4).
- [x] 2. No hidden analytics dependency remains — enumerated negatively and checkably (AN1–AN13, A101–A104).
- [x] 3. Page-view tracking is explicitly not required **and** absent from MVP (PW1, PW2).
- [x] 4. No raw clickstream is collected "for later" (AN4, AN12, V119).
- [x] 5. `popularity_score` still exists as a serving field (PS1).
- [x] 6. Its owner remains `application/storefront` (PS4).
- [x] 7. Each active source's owner is explicit: sales → `domains/orders`; favorites → the favorites owner (SL1, FV1).
- [x] 8. Sales semantics are owner-authoritative; item 13 freezes the requirement, not the predicate (SL3, SL4).
- [x] 9. Favorites are rebuildable from current owner state, and removal is reflected (FV2–FV4).
- [x] 10. Event history is never score truth (AG1, RD2, RD4).
- [x] 11. A full rebuild reconstructs popularity from current business state + the recorded policy (RD1–RD5).
- [x] 12. Item 12's CAS protocol is reused unchanged (IX1–IX8).
- [x] 13. No new freshness or version mechanism exists (SP13, A112).
- [x] 14. No partial `popularity_score` write bypass exists, and `# 10.7`'s aggregator sentence is pinned (IX5).
- [x] 15. No raw user identity reaches the projection (PV2, PV3, A105, C159).
- [x] 16. The formula is deterministic, pure, clock-free and integer-valued (SP1–SP8).
- [x] 17. Exact weights are **not** invented — the master states none (SP10).
- [x] 18. Time-window semantics, if used, are explicit and quantized so rebuild is deterministic (SP4–SP6).
- [x] 19. Source availability across phases is handled: Phase 4 ships before Phase 5/7 (EN1–EN5).
- [x] 20. A missing source means "not enabled", never fake data or a stub adapter (EN2, EN3).
- [x] 21. The rating/review discrepancy is explicitly resolved as permission-set vs delivery-list (SR5, SR6, RA1–RA5).
- [x] 22. The manual boost is excluded and remains ownerless, exactly as item 6 left it (MB1–MB4).
- [x] 23. Recently-viewed is browser-local and implies no server analytics (LV1–LV5).
- [x] 24. A future analytics domain retains a consent gate (FA1, CS1).
- [x] 25. Future raw metrics never join the storefront request path (FA3, PW3).
- [x] 26. No analytics queue or failure domain is invented; item 9 NX3 is confirmed, not edited (NQ1–NQ3).
- [x] 27. No speculative event contract is frozen, and no event name is even written (NE1–NE4).
- [x] 28. Checkout, pricing, inventory, payments and security are unaffected (PS3, DG1, §21).
- [x] 29. Item 14 remains `TODO`; the module cut is untouched (DC5, EN6, V129).
- [x] 30. Item 15 remains open and is not pre-empted (SC2).
- [x] 31. No code, schema, package, migration or dependency is created (§1.2).
- [x] 32. The ADR need is evaluated honestly and answered **no**, with what *would* have required one named (§1.3).

---

## 24. Explicitly deferred decisions

| Deferred | Owner |
|---|---|
| Scoring weights, the window length (or the decision to have none), quantization granularity and the recomputation schedule | Phase 4 / merchandising configuration, bounded by SP1–SP12 |
| Whether the serving row stores per-source input values alongside the score, and the physical column definition for `popularity_score` | Phase 4, bounded by PS7, SP7, SP8 |
| The batch aggregate selector signatures in `orders.public` and the favorites owner's `public.py` | each owning domain's phase, bounded by AG3, AG4 |
| The order-status predicate defining a successful commercial sale | `domains/orders` / item 5's phase (SL4) |
| Whether the popularity sort option is exposed in the UI when no source is enabled, and the default listing sort | Phase 4 / merchandising (SS5, master `# 10.2`) |
| Whether rating/review is later admitted into the formula | a recorded scoring-policy change (RA4, SP10); no ADR, no new mechanism |
| The **owner** of the manual merchandising boost | **item 6 §27's deferred decision, unchanged** — item 13 does not take it (MB2) |
| Which modules ship at launch, and therefore which source set is active at launch | **item 14** (EN6) |
| Infrastructure gates, read replica, and the remaining open ADRs | **item 15** / master `# 25` Phase 10 |
| Whether a consent-gated `domains/analytics` is ever built; its events, schema, ingestion, retention, anonymization, aggregates, queue and consent categories | master `# 25` Phase 9, behind §17's admission gate, with its own architecture + privacy artifact and an ADR to the extent it moves a boundary |
| Consent categories, banner state machines, retention periods and revocation mechanics | master `# 25` Phase 8 (consent) and the privacy phases (CS2, CS3) |
| Personalized recommendations or a personalized ranking read model | a separate artifact + a new ADR (SS4, item 6 SEC4) |
| Any change to AN1–AN15, SR1–SR6, AG1, EN1–EN7, SP1–SP13, IX1–IX8, FA1–FA11 or CS1 | a new ADR, or the artifact that introduces analytics |

---

## 25. Self-review record

| # | Check | Result |
|---|---|---|
| 1 | Is the MVP decision unambiguous, with no half-state? | Pass — §4 states option A in a block quote; DC1 rejects the five named half-states individually, which is important because each is a shape a well-meaning implementation drifts into rather than chooses. AN1–AN13 make "absent" enumerable instead of aspirational, and A101–A104, A111 make it checkable. |
| 2 | Was option B evaluated honestly, or dismissed? | Pass — DC2 gives four reasons and names the cost: a domain, a consent gate, an ingestion boundary, a retention obligation and a failure domain, all before launch, for a ranking refinement that no commercial path reads. DC3 records that A is the master's specified branch rather than a degraded fallback. |
| 3 | Is `ProductViewed`, page-view writing, clickstream or fingerprinting present anywhere? | Pass — only as prohibitions (AN3, AN4, AN11, PW1, LV2, A102, A111, V119, V127). NE3 goes further and declines to write speculative event names at all, so no name in this artifact can later be mistaken for a sanctioned contract. |
| 4 | Is any third-party analytics SDK, pixel or tag manager implied? | Pass — AN10 forbids it, A111 checks dependencies, templates, base layouts and CSP allowlists (the four places one actually appears), V127 is the review check. |
| 5 | Is an analytics queue, DLQ or failure domain created? | Pass — NQ1 confirms item 9 NX3/FD10 **without editing item 9**, NQ2 restates NX4's "where the domain does not exist, the work does not ship", and NQ3 answers the real question by observing that popularity is a **field of a candidate**, not a workload, so it runs in the existing `core.projection.*` domains. A103 is the static check. |
| 6 | Is an event pipeline assumed to exist? | Pass — this is principle 37's central prohibition and §14 makes it structural rather than promised: AG1's query-over-current-state rule means no consumed message is ever consulted, so the "pipeline" has nothing to be depended on. NE2 states the only requirement placed on future owners, and NE4 records that reconciliation alone is a legal convergence driver for a low-rate source. |
| 7 | Can popularity be read from raw Order/Favorite rows in the request path? | Pass — IX8 forbids it, A109 checks it, item 6 C25/QB3 already assert no OLTP table is touched in a listing request, and §21 gives every row a non-failing request path because the read path never computes. |
| 8 | Is there an event-count accumulator that cannot rebuild from OLTP? | Pass — AG1 is the single rule that forbids it, FV3 applies it to the tempting case (a "favorite added" counter), A106 is the static check, V120 the review check, and §21 rows 5–8 show what AG1 buys: duplicate delivery, removal, refund and history deletion all become correct without special handling. |
| 9 | Does any user identity, email or session id reach the projection? | Pass — PV2/PV3 restrict the boundary to Product-scoped aggregates, AG2 states what does **not** cross (rows, identifiers, per-action timestamps, free text), SP9 keeps identity out of the score itself, A105 checks field names on the model **and** on the input DTOs, C159 asserts it by inspection. Every PII cell in §21 is `None`. |
| 10 | Is a `popularity_version` or a popularity freshness token introduced? | Pass — SP13 states the distinction the prompt warned about (score is *content*; `projection_revision` protects the *write*), A112 checks for it, and IX3 keeps every source from supplying a token. Item 12's guard is neither extended nor paralleled. |
| 11 | Are formula weights invented without a source? | Pass — SP10 refuses explicitly and says why: the master states none, and a number chosen in Phase 0 would be a merchandising decision wearing an architectural costume. What **is** frozen are the properties a formula must have (SP1–SP9), which is the part that is genuinely architectural. |
| 12 | Is the time-window/rebuild-determinism tension actually resolved, or hand-waved? | Pass — it was a real hazard: a rolling window makes the score time-dependent, which would either break item 12 C26 ("rebuild reproduces serving state") or make every wall-clock second dirty the catalog. SP4 resolves both by making the reference instant an explicit **quantized** parameter — same bucket ⇒ identical score ⇒ C26 holds; crossing a bucket ⇒ a policy input change ⇒ a forward content change. SP5 turns window advancement into bounded scheduled recomputation and notes that an unchanged score writes nothing (item 12 NO1), so a sweep over a stable catalog costs zero writes. RD5 states the residual boundary honestly rather than claiming more than is true. |
| 13 | Does Phase 4 secretly depend on Phase 5/7? | Pass — EN1–EN5. The key rule is EN3: the policy is *defined over the enabled set*, so a non-enabled source is not a term at all rather than a term filled with a lie. EN5 states the consequence plainly — Phase 4 ships with zero enabled sources, every product neutral, the sort determined by the tie-break, nothing stubbed. C160 asserts it and forbids stub participation. |
| 14 | Is "not enabled" distinguished from "enabled but failing"? | Pass, and this is the correction that matters most operationally — conflating them would let one bad aggregate query silently zero the entire catalog's ranking. EN4 makes a failing enabled source a transient technical fault that preserves the previous value; DG3 forbids substitution of neutral, zero, random or a stale cache promoted to truth; §21 row 18 and C153 pin it; V125 is the review check. |
| 15 | Is rating simultaneously included and excluded anywhere? | Pass — RA1 excludes it from the **formula** once, and every other mention is consistent: RA2 explains that it already has an independent representation (`rating_avg_x10`/`rating_count`, item 7's card summary) so folding it in would double-count and blur two dimensions; RA4 keeps readmission cheap and analytics-free; RA5 closes the informal routes. §21 row 17 covers both states. SR5's permission-set/delivery-list reading shows the master was never actually self-contradictory. |
| 16 | Does the manual boost end up with no owner and no rule? | Pass — MB1–MB4. Item 13 deliberately does **not** assign the owner, because that would be a boundary decision needing its own analysis and probably an ADR, and item 6 §27 already holds that deferral. MB3 records that `# 10.7` calls it optional, so excluding it blocks no launch; MB4 keeps SO6/SO6b's prohibitions intact. V123 is the review check, §24 leaves the deferral exactly where it was. |
| 17 | Is item 14's or item 15's territory consumed? | Pass — DC5, EN6, SC2 and V129 all state the limit, and §24 routes the module cut to item 14 and the infrastructure gates to item 15. Item 13 answers only the three questions items 6, 9 and 12 explicitly asked it (SC1). |
| 18 | Is any legal claim made? | Pass — PV4 states the limit in the negative: item 13 does **not** claim first-party data never needs consent or a lawful basis anywhere. It freezes the architectural fact (no new collection, no new personal-data category) and routes purpose/legal review to the phases and people who own it. PV5 then shows the design degrades gracefully if a review restricts a source — disable it, rebuild, and nothing must be extracted from the projection because nothing personal is there. |
| 19 | Does the sort stay deterministic in the degenerate all-neutral case? | Pass — SS2. This was the case most likely to be missed: at Phase 4 with no sources, every score is identical, so the popularity sort is *entirely* the tie-break. Item 6 SO2's unique final key makes that a stable total order rather than an arbitrary one; C157 asserts a full keyset walk with no gaps or duplicates. SS5 leaves the UI question where it belongs without leaving the invariant unstated. |
| 20 | Is item 12 weakened anywhere, or granted an exception? | Pass — IX1–IX8 reuse it verbatim and IX7 states there is no analytics exception. The one place the master could be misread as authorising a partial-column write — `# 10.7`'s "updates only `popularity_score` of the changed products" — is pinned in §1.4 and IX5 as *only the changed products*, which is item 12's coalesced batch model, not a single-column write. Item 12 CB4 stands. |
| 21 | Is the future seam preserved rather than deleted? | Pass — DC4 and AN15 keep it a legitimate deferred capability, and §17's eleven-rule gate is specific enough to prevent piecemeal arrival (FA2 names the four back doors) while designing nothing: no table, model, event type, payload, schema version, queue, consumer declaration or retention period (FA8). FA9/FA10 bound its scope for the day it exists. |
| 22 | Is the ADR conclusion honest, or convenient? | Pass — §1.3 works through the six ADR triggers individually and shows each is untouched, then names the one decision item 13 *could* have taken that would have needed one (assigning the manual-boost owner) and declines it. It also records that introducing analytics later probably **does** need an artifact and an ADR, so the "no" here is scoped rather than blanket. |
| 23 | Does anything here create code, schema or infrastructure? | Pass — §1.2 states it; no code block in this artifact is a schema, a payload or a signature; §24 routes every physical artifact to Phase 4, to an owning domain's phase, or to the future analytics artifact. |
| 24 | Contradiction with ADR-0001…ADR-0014 or with items 6–12? | Pass — **0003:** nothing enters catalog. **0004/0005:** no module, no boundary, no port, no import edge, no `core` allowlist entry (§22.1). **0007:** popularity reaches no commercial path (PS3, R9). **0008:** the projection stays derived, single-writer, rebuildable; SO5's closed source set is respected and SO6/SO6a/SO6b are confirmed unchanged. **0009:** registry still empty (NE1). **0010:** NX3/NX4/FD10 confirmed, not edited (NQ1, NQ2). **0014/item 12:** protocol reused verbatim, CB4 and CB10–CB14 honoured, FS1–FS5 used as written, no token or guard change (IX1–IX8). **Item 7:** no public DTO field is added (PS6). |

Verdict: **PASS**.
