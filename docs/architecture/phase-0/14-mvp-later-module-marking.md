# Phase 0 — Item 14: the MVP / later launch cut per module and per mixed-scope capability

- **Status:** DONE / FROZEN
- **Date:** 2026-09-06
- **Phase:** 0 — Architecture Freeze
- **ADR:** **none required** — see §1.3. This item selects feature scope the master already
  authorises, assigns no owner, moves no boundary and changes no frozen artifact.
- **Related:** [ADR-0003](../../adr/0003-catalog-boundary-vs-storefront-projection.md),
  [ADR-0004](../../adr/0004-four-layer-modular-monolith.md),
  [ADR-0005](../../adr/0005-dependency-and-integration-wiring.md),
  [ADR-0006](../../adr/0006-public-contract-primitives.md),
  [ADR-0007](../../adr/0007-place-order-atomic-idempotent-boundary.md),
  [ADR-0008](../../adr/0008-storefront-listing-projection.md),
  [ADR-0009](../../adr/0009-event-contract-versioning.md),
  [ADR-0010](../../adr/0010-async-failure-domain-isolation.md),
  [ADR-0014](../../adr/0014-storefront-projection-convergence.md),
  [item 2](02-four-layer-architecture.md) §8.3, §8.4,
  [item 3](03-dependency-matrix.md) §8, §12, §13,
  [item 4](04-domain-public-contract.md),
  [item 5](05-place-order-use-case.md) §4, §5,
  [item 6](06-storefront-listing-projection.md) §8, §11,
  [item 8](08-event-registry-versioning.md) KD2,
  [item 9](09-queue-failure-domain-dlq.md) §12 FD9, FD9a, NX1–NX3,
  [queue / failure-domain matrix](../events/queue-failure-domain-matrix.md) §5,
  [item 12](12-source-version-guarded-upsert.md) FS1–FS5,
  [item 13](13-analytics-mvp.md) §8, §10 EN1–EN7,
  master `# 4`, `# 5` principle 39, `# 9.3`, `# 10.7`, `# 11.3`, `# 11.4`, `# 12.4`, `# 13.2`,
  `# 13.3`, `# 14.1`, `# 14.2`, `# 15.1`–`# 15.3`, `# 16`, `# 17`, `# 19.3`, `# 20.1`, `# 25` MVP
  line + Phases 0–13, `# 26` MVP governance

---

## 1. Purpose

The master states the launch cut in three separate places — the `# 25` MVP line, the "can wait"
list beside it, and per-chapter remarks such as `# 17`'s optional editorial types, `# 12.4`'s
provider list and `# 15.2`'s map credentials — and the roadmap phases interleave launch and
post-launch capabilities inside the same phase. Item 9 FD9a left `ext.crm`'s provisioning to this
item. Item 13 left the launch source set of `popularity_score` to this item. Item 5 left the MVP
participation of trade-in to "the implementing phase".

This item turns that scattered language into **one authoritative launch-cut matrix** and answers
exactly four questions per module or separately cuttable capability:

```text
What exists at launch?
What exists at launch only in reduced scope?
What is explicitly later?
What is an infrastructure gate rather than a business module?
```

It is **classification, not redesign**.

> **The governing constraint, restated unchanged (master `# 5` principle 39, `# 25`, `# 26` MVP
> governance): MVP cuts features, never correctness, security, performance or module-boundary
> invariants.** Every invariant frozen by items 1–13 applies to every module that ships, in its
> reduced scope as much as in its full scope, and applies to a LATER module from its first line of
> code.

### 1.1 What this item freezes

- The **classification vocabulary** — `FOUNDATION`, `MVP`, `MVP — REDUCED SCOPE`, `LATER`,
  `INFRASTRUCTURE GATE` — and the rule that roadmap phase number never determines launch
  membership (§2, §3).
- The **complete launch matrix** over `core/*`, `domains/*`, `application/*`, `interfaces/*`,
  `integrations/*`, `tasks/*` and the named optional commercial capabilities that have no physical
  package (§5).
- The **per-module reduced-scope tables**: exactly what is in and what is out for every
  `MVP — REDUCED SCOPE` module (§6).
- The **payment-provider cut**: maib + cash + IBAN at launch; MIA, credit, POS-on-delivery and any
  further adapter later — with the payment domain, state machine, webhook contract, reconciliation
  and provider seam themselves **MVP foundation, not a provider** (§7).
- The **accounts / reviews / favorites / compare cut**: accounts and order history MVP, basic
  reviews MVP in their full `# 14.1` shape, **favorites LATER, compare LATER** (§8).
- The **content cut**: static/legal/operational content, consent support and static sitemaps at
  launch; Blog, Promo pages, Events, eSIM guides and video CMS later — **one physical module,
  feature-cut, not package-split** (§9).
- The **delivery / stores / maps cut**: courier + pickup at launch, store-scoped pickup reservation
  at launch, digital fulfilment later, interactive map later (§10).
- The **notification channel cut**: transactional email MVP, **SMS LATER**, with the master's guest
  claim flow shown to have a compliant non-SMS launch path (§11).
- The **CRM / Chatwoot cut**: both LATER, resolving item 9 FD9a's conditional — **`ext.crm` is
  defined and not provisioned** (§12).
- The **item 13 consequence**: `domains/analytics` LATER unchanged, and the launch-enabled
  popularity source set is **successful sales only**, because favorites is LATER (§13).
- The **optional commercial capability cut**: Trade-In, eUpgrade, Digital Products/KMS, Chatwoot,
  full analytics, complex Blog, Events, eSIM, video CMS, personalized recommendations and the
  **newsletter** capability — all LATER, classified only (§14).
- The **failure-domain launch-provisioning view** derived from item 9's frozen definitions, with a
  `YES`/`NO` per domain and the enabled workload as the reason (§15).
- The **dependency-closure matrix** proving no MVP module requires a LATER module, plus the
  degradation each MVP module exhibits with each LATER feature absent (§16, §17).
- The **later-feature admission rule** and the **no-fake-compatibility-layer rule**, which reject by
  name the shapes that would quietly reintroduce a LATER dependency (§18, §19).
- A **20-row failure/degradation matrix** distinguishing *not shipped* from *runtime outage* (§20).
- The checks **A114–A128**, **C161–C176**, **V130–V145** (§21).

### 1.2 What this item does **not** do

No Python package, module, Django app, model, migration, event class, Celery task, queue, schema,
dependency, infrastructure component or public API schema is created. No `event_type` is invented.
No queue topology, routing syntax, worker count or capacity number is chosen.

It designs **no** deferred feature contract: not Trade-In, not eUpgrade, not digital/KMS, not a
Chatwoot identity contract, not an analytics event schema, not MIA's protocol details, not a
recommendation schema, not a complex CMS model. Those are classified and nothing more.

It does not reopen items 1–13, does not edit item 9's failure-domain definitions (it derives a
provisioning view that references them), does not reopen item 13's analytics decision (it states
only the launch consequence item 13 explicitly left here), and does not consume **item 15**:
infrastructure gates stay measurement-driven under item 15 and master `# 25` Phase 10, with no
threshold, topology or vendor decided here.

It does not decide **which Phase 1 packages physically exist** (§4), and it assigns **no new owner**
to any capability.

### 1.3 ADR evaluation — **no new ADR is required**

`docs/adr/README.md` requires an ADR when a domain boundary moves, a new cross-domain owner is
assigned, a public contract changes shape, an identity/money/idempotency/consistency rule changes, a
read model or projection strategy changes, a frozen ERD invariant changes, or a deferred item is
un-deferred. Item 14 does none of those:

| Would-be trigger | Item 14's position |
|---|---|
| A boundary moves, or a new owner is assigned | **None.** Every capability classified here already has the owner an earlier item gave it. Where the corpus has **no** owner for something (the manual merchandising boost, item 6 §27; the newsletter subscriber entity, §9.3 — a `LATER` capability, so no owner is needed now), item 14 classifies launch membership and **leaves the owner where it found it** — it does not assign one. |
| A public contract changes shape | **None.** No `public.py` export list, DTO, event schema or version changes. A module shipping in reduced scope exposes a smaller contract than its eventual full one; that is a contract not yet grown, not a contract changed. |
| An identity/money/idempotency/consistency rule changes | **None.** Cutting a feature never relaxes a rule about the features that remain (§2 CV7). |
| A read model or projection strategy changes | **None.** `ProductListingProjection` and `ProductRatingProjection` ship exactly as items 6, 7, 12 and master `# 14.1` froze them. |
| A deferred item is un-deferred | **None.** Item 14 defers; it un-defers nothing. Multi-valued attributes, category↔attribute applicability, read replica and OpenSearch all stay deferred. |
| A new module, queue or failure domain is added | **None.** §15 provisions a subset of item 9's existing definitions and adds no definition. |

What item 14 does is **select feature scope the master already authorised**: the `# 25` MVP line
lists the launch set, the "can wait" list beside it names the deferrals, `# 25` Phases 9 and 10
separate optional commercial features from optional infrastructure, and `# 26` MVP governance
states the rule ("production scope is marked `MVP`/`later`; deferred feature modules must not force
core to contain their dependencies or stub logic"). That is the README's explicit *routine
implementation choice inside an already-decided boundary* case.

**What would have needed one, and was therefore avoided:** the one place item 14 could have created
a boundary is `application/backoffice` — inventing a cross-domain administrative use case to justify
the directory would have assigned a new owner. §5.4 declines it instead (BO1–BO4), taking the
narrowing rather than the invention. Symmetrically, promoting a LATER capability into MVP to make
another module richer — favorites to enrich `popularity_score` — is declined in §8.4.

### 1.4 Master mapping

| Master | Statement | Status here |
|---|---|---|
| `# 25` MVP line, "Обязательный фундамент / MVP" | Ten launch bullets: catalog + listing projection + basic facets; cart/checkout/order + idempotency; pricing + promotions/coupon core; inventory/reservations + ERP batch import; maib + cash/IBAN; static CMS/legal pages + consent; account/order history + basic reviews; module boundaries/public contracts; Outbox/Inbox/event versioning; query budgets/observability/runbooks | **Adopted verbatim as the launch floor.** §3 MP1: every bullet is MVP or FOUNDATION, and no bullet is narrowed. §5's matrix maps each to modules. |
| `# 25` MVP line, "Можно отложить после запуска" | Trade-In; eUpgrade; digital goods/KMS; Chatwoot with identity context; complex Blog/Events/eSIM/video CMS; OpenSearch; read replica/PgBouncer; views-based analytics/popularity; separate microservices | **Adopted.** §14 classifies the first five as `LATER`; §22 classifies OpenSearch, read replica, PgBouncer and microservices as `INFRASTRUCTURE GATE`; views-based analytics is item 13's, restated in §13. |
| `# 25` MVP line, closing sentence | "Инварианты **не режутся ради MVP**; режутся только features" | **The governing constraint** (§1, CV7, A114, V130). |
| `# 5` principle 39 | MVP cuts features but not invariants; `public_id`, Money, `IdempotencyKey`, actor policies, DB constraints, module boundaries, event versioning, listing projection and query budgets are foundation | **This is the `FOUNDATION` class** (§2). The named list is §5.1's first eleven rows. |
| `# 26` MVP governance | Production scope is marked `MVP`/`later`; deferred feature modules must not force core to contain their dependencies or stub logic; invariants/boundaries/observability are not deferred | **The mandate for this artifact.** "No stub logic" is §19's no-fake-compatibility rule; "not deferred" is the `FOUNDATION` class. |
| `# 12.4` | `MaibProvider`, `MiaProvider`, `CashProvider`, `IbanProvider`, `CreditProvider` implement one interface | **Read as an interface contract, not a launch list** (§7 PM1). The single interface is MVP; the enabled adapter set is `maib`/`cash`/`IBAN` per the MVP line. |
| `# 11.4` step 3 | Payment step offers online card / MIA / credit / IBAN / cash / POS on delivery | **A capability enumeration, not a launch requirement** (§7 PM3). The MVP line is the narrower and more explicit statement about launch. |
| `# 13.2`, `# 13.3` | Favorites and Compare with their merge/validation rules | **LATER** (§8). The rules stay frozen and bind the feature whenever it ships. |
| `# 14.1` | Review model, moderation, verified-purchase badge, anti-spam, `ProductRatingProjection`, `rating_avg_x10` | **MVP in full** — this *is* the master's "basic reviews" (§8.3). |
| `# 15.1`–`# 15.3` | `Store` with pickup/delivery capability flags; map tiles and provider credentials; `DeliveryTariff` | Store + tariff **MVP**; the interactive map **LATER** (§10). |
| `# 16` | Digital fulfilment types, `DigitalCode`, KMS, key rotation | **LATER** (§14). §10 DL6 stops a fulfilment-type enum value from forcing it into MVP. |
| `# 17.1` | Static legal/reference pages editable by content and legal staff without developers | **MVP** (§9). |
| `# 17.2`–`# 17.7` | `Article` polymorphic model; block JSON + CSP; Promo pages with SEO lifecycle; Events; eSIM guides; video embedding | Publication **identity, block-JSON sanitisation and CSP** are MVP because static pages use them; the **types** `news`/`review`/`guide`/`promo` and the Event/eSIM/video extensions are LATER (§9). |
| `# 19.3` | Newsletter subscription endpoint with consent, honeypot, rate limit, optional double opt-in, low-priority CRM/mailing hand-off | **LATER in its entirety** — capture, subscriber persistence, double opt-in, sending and the CRM/mailing hand-off alike (§9.3). Its security/privacy requirements bind it whenever it ships. |
| `# 14.2`, `# 21.10` | Chatwoot as an external processor with identity validation and data minimisation | **LATER** (§12). |
| `# 9.3` | ERP batch import: authenticated ingest, set-based SQL, no-op suppression, coalesced events, reconciliation | **MVP in full** (§5.3, §5.5). |
| `# 10.7` MVP subsection | Popularity from available first-party signals, no view tracking | Item 13's decision; item 14 supplies only the **launch-enabled source set** (§13). |
| `# 25` Phase 9 | Trade-In, eUpgrade, Digital Products + KMS, Chatwoot, consent-gated analytics/view events — by business priority, independently | **The `LATER` set** (§14). |
| `# 25` Phase 10 | OpenSearch, read replica, PgBouncer, separate analytics/search/image service; the ACID core is not split without an ADR | **The `INFRASTRUCTURE GATE` set** (§22), left to item 15. |

---

## 2. Classification vocabulary

Five classes. A module or separately cuttable capability has **exactly one**.

| Class | Meaning |
|---|---|
| `FOUNDATION` | Cross-cutting architecture or runtime mechanism required regardless of which optional business features ship. Not a business feature; never "later because its consumer is later". |
| `MVP` | The module or capability must be **production-ready at launch**, in the scope the master and the frozen items already describe. |
| `MVP — REDUCED SCOPE` | The module exists at launch, but **named** capabilities inside it are deliberately later. Both lists are enumerated; "basic version" is not an admissible description. |
| `LATER` | Not a launch dependency. No MVP module may depend on it, secretly or otherwise. Its architectural seam may already exist in documentation; its package need not exist at all. |
| `INFRASTRUCTURE GATE` | A measurement-driven infrastructure choice (OpenSearch, read replica, PgBouncer, service extraction, PostGIS). Not an ordinary later feature: activation stays governed by **item 15** / master `# 25` Phase 10, behind evidence and, where the master says so, an ADR. |

| # | Rule |
|---|---|
| CV1 | Every named module and every separately cuttable capability carries exactly one class. An unclassified module is a defect, not a default. |
| CV2 | `FOUNDATION` is a statement about **mechanism**, `MVP` a statement about **business feature readiness**. A mechanism is never downgraded because one eventual consumer is LATER (§19 FD-rules). |
| CV3 | `MVP — REDUCED SCOPE` requires **two enumerated lists** — launch scope and later scope — in §6. A row without both is invalid. |
| CV4 | `LATER` means *not a launch dependency*. It does **not** mean the seam is undesigned, and it does **not** license a stub, a null adapter or an empty package (§19). |
| CV5 | `INFRASTRUCTURE GATE` is deliberately not `LATER`: a LATER feature ships when the business wants it, a gate opens when **measurement** justifies it. Item 14 states the class and nothing about the threshold. |
| CV6 | The grain of the matrix is an **architectural module or a separately cuttable capability**, never an individual file. A capability is separately cuttable when removing it changes no other module's contract. |
| CV7 | A class never changes an invariant. A reduced-scope module obeys every rule of items 1–13 for the scope it ships; a LATER module obeys them from its first line. Nothing in this vocabulary weakens actor scoping, idempotency, money typing, boundary rules, query budgets, consent or security. |
| CV8 | A classification is about **production enablement at launch**, not about implementation order between phases. Two capabilities in the same phase may hold different classes; one capability may be built in Phase 3 and enabled at launch, or built in Phase 8 and never enabled. |

---

## 3. Phase number is not launch membership

| # | Rule |
|---|---|
| MP1 | Launch membership is derived from **(a)** master `# 25`'s MVP line, **(b)** explicit optional / "can wait" / "later" statements anywhere in the master or a frozen item, and **(c)** dependency closure over (a) and (b). It is **never** derived from the phase number a capability appears in. |
| MP2 | A roadmap phase is an **implementation-order container** and routinely holds both launch and post-launch capabilities. Phase 8 is the clearest case: "basic static/legal CMS first" and "optional Blog/Promo/Event/Guide/Video **according to the MVP line**" sit in the same checklist. Phase 7 is the second: account, order history and reviews sit beside favorites and compare. |
| MP3 | Where a phase checklist marks some entries optional and others not, that **asymmetry inside the phase's own list** is admissible evidence under MP1(b). Where a phase marks nothing, the phase says nothing about launch. |
| MP4 | Where the MVP line and a chapter enumeration disagree in breadth, the **MVP line wins for launch membership**, and the chapter is read as the capability's eventual full shape (applied in §7 to `# 12.4`/`# 11.4`, and in §9 to `# 17`). |
| MP5 | The converse also holds: a capability's presence in an early phase does **not** make it MVP. Phase 1 builds the whole `ext.*` failure-domain skeleton; §15 still provisions only the domains with an enabled launch workload. |

---

## 4. Three distinct questions

Item 14 answers only the third.

```text
Q1  Does the architectural seam exist in documentation?     — items 1–13 answer this
Q2  Must the source package exist in Phase 1?                — Phase 1 answers this
Q3  Is the production feature enabled at launch?             — ITEM 14 ANSWERS THIS
```

| # | Rule |
|---|---|
| PX1 | A `LATER` classification does **not** require Phase 1 to create an empty package, an app label, a migration, a settings entry or an `__init__.py` for that module. No earlier frozen artifact requires skeletons for deferred domains. |
| PX2 | Specifically, an empty `domains/analytics` package would contradict item 13 AN1 by appearing to be a real module, and is forbidden (A116, V131). |
| PX3 | A documented seam (item 9's `ext.crm` definition, item 13 §17's admission gate, item 5 §4's participant table) is **documentation**, and its existence is never evidence that the feature is enabled. Item 9 FD9 already states this for failure domains; §15 applies it. |
| PX4 | Conversely, a package that exists for an MVP module ships its **real** implementation. Item 14 authorises no placeholder module of any kind (§19). |

---

## 5. The launch module matrix

Grain per CV6. "Owner" names the frozen owner; item 14 assigns none.

### 5.1 `core/*` and cross-cutting mechanism — all `FOUNDATION`

| Module / mechanism | Class | Note |
|---|---|---|
| `core.money` — `Money`, `RoundingPolicy` | FOUNDATION | ADR-0012, item 11. Required by pricing, promotions, delivery, orders, payments at launch; would be required by any subset. |
| `core.public_id` — `PublicId`, `EventId` | FOUNDATION | ADR-0013, item 11. Every external locator at launch. |
| `core.dto` | FOUNDATION | Item 4's DTO style is the boundary primitive. |
| `core.security.actor` + structural public-error categories | FOUNDATION | ADR-0006. Every `public.py` signature. |
| `core.idempotency` | FOUNDATION | Master MVP line names idempotency explicitly; ADR-0007. |
| `core.outbox` / `core.inbox` (incl. the item 10 four-field TCE on the initial schema) | FOUNDATION | Master MVP line; items 8, 10. |
| `core.events` — registry + version validator **mechanism** | FOUNDATION | Item 8. The registry ships **empty** (item 8 KD2); the mechanism is still MVP foundation (§19 FD1). |
| `core.cache` — single-flight, versioning | FOUNDATION | Master `# 10.5`, `# 19.2`; navigation/footer/fragment caching at launch. |
| `core.security` — signing, trusted client IP | FOUNDATION | Guest access tokens, payment return state, rate limiting, webhook crypto. |
| `core.observability` — logging, tracing, metrics | FOUNDATION | Master MVP line: observability/runbooks. Never a popularity input (item 13 AN14). |
| `integrations/base` — mandatory timeout / retry / circuit breaker | FOUNDATION | Master `# 20.8`; binds every vendor client at launch and later. |
| Failure-domain / DLQ / quarantine machinery, PostgreSQL-canonical terminal records, replay procedure | FOUNDATION | Items 9, 10. The **machinery** is foundation; **which domains are provisioned** is §15. |
| Query-budget / N+1 harness, `pg_stat_statements`, `import-linter` + AST contract tests | FOUNDATION | Master MVP line and `# 24.7`, `# 24.8`. |
| `config/` composition root and adapter binding | FOUNDATION | ADR-0005, item 3 §12. |
| Backup / PITR / restore-verification / runbook foundations | FOUNDATION | Master `# 23.4`, Phase 12. |

### 5.2 `domains/*`

| Domain | Class | Launch statement |
|---|---|---|
| `catalog` | **MVP** | Category/Brand/Product/ProductVariant/typed EAV/images, RO/RU, admin + bulk import, static sitemap source data. ADR-0001–0003 unchanged. |
| `pricing` | **MVP** | Price/PriceList in minor units, `PriceProjection`, pricing pipeline, `pricing.public`. |
| `promotions` | **MVP** | Promotion/Coupon/Redemption with atomic redemption under its own constraints (item 5 C5). Promo **landing pages** are content (§9); eUpgrade **campaigns** are `# 18.2` and LATER — neither is inside this domain. |
| `inventory` | **MVP** | `InventoryBalance` constraints, reservation state machine, `reserve`/`commit`/`release`, store-scoped pickup reservation, concurrency tests. |
| `orders` | **MVP** | `Order`/`OrderItem`, state machine, immutable commercial snapshots, order identity, actor-scoped selectors, Track & Trace source. |
| `payments` | **MVP — REDUCED SCOPE** | Domain, state machine, `PaymentAttempt`, amount/currency matching, reconciliation and the provider seam are MVP; the **enabled provider set** is reduced (§7). |
| `reviews` | **MVP** | The full `# 14.1` shape: `Review` with `author_display_name` snapshot, verified-purchase badge, moderation, anti-spam, `ProductRatingProjection`, `rating_avg_x10`. This *is* the master's "basic reviews" (§8.3). |
| `delivery` | **MVP — REDUCED SCOPE** | Courier + pickup tariffs/zones; digital fulfilment later (§10). |
| `stores` | **MVP** | `Store` with ERP-consistent `code`, explicit pickup/delivery capability flags, coordinates as `Decimal`. The interactive **map** is a separate capability and LATER (§10). |
| `content` | **MVP — REDUCED SCOPE** | Static/legal/operational pages, consent support, static sitemaps; editorial types later (§9). |
| `accounts` | **MVP — REDUCED SCOPE** | User/Profile/address, order history, guest claim; favorites and compare later (§8). |
| `notifications` | **MVP — REDUCED SCOPE** | Transactional email only; SMS later (§11). |
| `analytics` | **LATER** | Item 13 option A, unchanged and not reopened. No package, model, endpoint, event, worker or queue (§13, PX2). |
| `tradein` | **LATER** | Trade-In and eUpgrade both (§14). |
| Digital distribution / KMS (`# 16`; no domain in the master tree) | **LATER** | `DigitalCode`, key rotation, digital fulfilment lifecycle (§14). |
| Support / Chatwoot (`# 14.2`; no domain in the master tree) | **LATER** | Including its identity-validation contract, which item 14 does not design (§12). |

### 5.3 `application/*`

| Module | Class | Launch statement |
|---|---|---|
| `application/storefront` | **MVP** | `ProductListingProjection`, `ProductCard`/Facet/Badge DTOs, shared Web/API selector, basic facets, PostgreSQL search baseline, deterministic sort + keyset pagination, incremental update + full/targeted rebuild + reconciliation, crawl controls, anonymous fragment cache, `popularity_score` per §13. §6.6 lists what is **not** pulled in. |
| `application/checkout` | **MVP — REDUCED SCOPE** | Cart, `CheckoutSession`, `place_order`, `apply_coupon`; `apply_tradein_quote` later (§6.4). |
| `application/payments_gateway` | **MVP — REDUCED SCOPE** | Port ownership, post-commit charge, reconciliation scheduling — bound to the launch provider set only (§7). |
| `application/erp_sync` | **MVP** | Batch import/synchronisation contract, `ErpVariantMapping` ownership (item 3 §8), coalesced catalog events, reconciliation. Scope is the roadmap's batch import/sync — not every conceivable ERP feature (§5.5). |
| `application/backoffice` | **LATER** | §5.4. |

### 5.4 `application/backoffice` — LATER, seam preserved

| # | Rule |
|---|---|
| BO1 | **No cross-domain administrative use case is described** for launch by the master or by any frozen item. Item 14 declines to invent one to populate the directory from the illustrative `# 4` tree. |
| BO2 | Launch administration is therefore **domain-local and single-domain**: `domains/<x>/admin.py` under item 3 §13's import rules (catalog management and bulk import, content editing, moderation queues, price and tariff maintenance), plus `interfaces/admin` entry points that call **one** domain's `public.py`. Both are covered by their own modules' MVP rows and neither is reduced by BO1. |
| BO3 | DLQ inspection and replay (master `# 20.5`, Phase 6) is a **`core` mechanism** operated through `interfaces/admin`, scoped to one consumer delivery under item 9's replay authority. It is not a cross-domain business workflow and does not require `application/backoffice`. |
| BO4 | If an implementation phase finds a genuine cross-domain administrative action — the most likely candidate being a single view combining `orders` and `payments` state, which item 2 §8.3 forbids an interface from composing — it is admitted into `application/backoffice` under item 3 §13's **already frozen** rule. That admission needs no ADR, no new boundary and no reopening of item 14; the alternative (a domain-local admin action reaching into a second domain) stays forbidden either way. |
| BO5 | BO1 is a statement about a **cross-domain application module**, never a licence to run the shop without administration. Every MVP module's own administrative surface is part of that module's MVP scope. |

### 5.5 `interfaces/*`

| Interface | Class | Launch statement |
|---|---|---|
| `interfaces/web` | **MVP** | HTMX storefront, catalog/listing/product/cart/checkout/account/order-history/content pages, SEO, anonymous fragment cache. |
| `interfaces/api/v1` | **MVP** | DRF serialisers built from the **same** storefront DTOs; Web/API parity contract tests (master `# 10.9`, Phase 4). **A native mobile client product is not implied by this classification** (§21 AP1–AP3). |
| `interfaces/webhooks` — maib | **MVP** | Raw-body signature, timestamp/replay window, durable ingest only (master `# 12.2`). |
| `interfaces/webhooks` — MIA | **LATER** | Follows the MIA provider (§7). |
| ERP inbound ingest (`interfaces/webhooks/erp` and/or scheduled pull through `application/erp_sync`) | **MVP** | The **capability** — authenticated, bounded, deduplicated, durable ERP batch ingest with unknown-master-data quarantine (master `# 9.3`) — is MVP. Whether the launch protocol is provider-push, scheduled pull, or both is Phase 3's integration decision, not a launch-membership question; both shapes are inside the MVP boundary and neither adds a module. |
| `interfaces/admin` | **MVP** | Single-domain administrative entry points per BO2; DLQ/replay operation per BO3. |
| Chatwoot webhook ingest | **LATER** | Follows Chatwoot (§12). |

### 5.6 `integrations/*`

| Adapter | Class | Launch statement |
|---|---|---|
| `integrations/base` | **FOUNDATION** | §5.1. |
| `integrations/erp` | **MVP** | Anti-corruption DTO + client for the ERP batch import the MVP line requires. |
| `integrations/maib` | **MVP** | Client, signature verification, vendor DTO. |
| `integrations/mia` | **LATER** | §7. |
| Outbound transactional **email** transport adapter | **MVP** | The vendor-facing half of `domains/notifications`' launch scope (§11). Item 14 names no package and no vendor. |
| Outbound **SMS** transport adapter | **LATER** | §11. |
| `integrations/crm` | **LATER** | §12. |
| `integrations/chatwoot` | **LATER** | §12. |
| Map / tile provider | **LATER** | §10 DL7–DL9. |
| Media object storage / CDN delivery path | **MVP** | Catalog media is MVP (master `# 7.3`, Phase 2 "safe media/CDN"), so its storage and delivery path is too. This is **not** an `INFRASTRUCTURE GATE`: it is required by a launch promise rather than justified by measurement (CV5). |

> **An external adapter is not the domain it serves, and the reverse.** `integrations/erp` is MVP
> because ERP batch import is; `domains/inventory` would still be MVP if the ERP protocol changed
> vendor. `domains/notifications` is MVP in reduced scope while its SMS adapter is LATER.

### 5.7 `tasks/*`

Thin Celery transport wrappers (ADR-0004, item 3). The **wrapper mechanism** is FOUNDATION; each
task family follows the workload it carries.

| Task family | Class | Note |
|---|---|---|
| `tasks/projections` | **MVP** | Incremental projection updates and rebuild/reconciliation runs. |
| `tasks/payments` | **MVP** | Post-webhook state convergence and reconciliation for the launch providers. |
| `tasks/erp` | **MVP** | Batch import entry point; a single bounded batch task, never 20 000 tasks (master `# 9.3`). |
| `tasks/notifications` — email | **MVP** | Transactional email dispatch. |
| `tasks/notifications` — SMS | **LATER, not provisioned** | No SMS workload at launch (§11, §15). |
| `tasks/maintenance` | **MVP** | Reservation expiry sweeps, Outbox/Inbox retention, cache re-warm, scheduled recomputation. |
| A CRM task family | **LATER, not provisioned** | §12. |

### 5.8 Named optional commercial capabilities without a physical package

| Capability | Class |
|---|---|
| Trade-In (`# 18.1`) | **LATER** |
| eUpgrade (`# 18.2`) | **LATER** |
| Digital Products / KMS (`# 16`) | **LATER** |
| Chatwoot / operator support platform (`# 14.2`, `# 21.10`) | **LATER** |
| Own WebSocket chat via Django Channels (`# 14.2`) | **LATER** |
| Full analytics / view events (`# 25` Phase 9) | **LATER** (item 13) |
| Complex Blog / news / review / guide article types (`# 17.2`) | **LATER** |
| Marketing promo landing pages with SEO lifecycle (`# 17.4`) | **LATER** |
| Events calendar (`# 17.5`) | **LATER** |
| eSIM interactive guides (`# 17.6`) | **LATER** |
| Video CMS / embedded video (`# 17.7`) | **LATER** |
| Favorites (`# 13.2`) | **LATER** |
| Compare (`# 13.3`) | **LATER** |
| Personalized recommendations / personalized ranking | **LATER** (item 6 SEC4, item 13 SS4) |
| Newsletter subscription (`# 19.3`) | **LATER** (§9.3) |
| Cross-device viewed history (`# 7.5`) | **LATER** (item 13 §16: recently-viewed stays browser-local at launch) |

---

## 6. Per-module reduced-scope tables

Each table is the CV3-mandated pair of enumerated lists.

### 6.1 `domains/payments`

| Launch scope | Later scope |
|---|---|
| `PaymentAttempt` with minor-unit amount + ISO-4217 currency | MIA adapter, its deep-link/QR UX and its webhook route |
| The payment state machine and its row-locked transitions | `CreditProvider`, eligibility computation and provider fee handling |
| Exact amount/currency matching against `Order.total_minor` | POS-on-delivery as a payment method |
| Webhook durable-ingest contract, raw-body signature, replay window | Any further provider adapter |
| Reconciliation as the convergence mechanism | Refund/partial-refund workflows beyond the frozen state machine |
| The provider-adapter interface itself, with `maib`, `cash`, `IBAN` bound | — |
| Signed stateless return-URL handling | — |

### 6.2 `domains/delivery`

| Launch scope | Later scope |
|---|---|
| `DeliveryTariff` (zone, method, `price_minor`, `free_from_minor`, currency, validity) | Digital fulfilment methods (`digital_email`, `digital_sms`, `external_activation`) |
| Courier delivery method | Carrier-integration/tracking automation beyond the frozen Track & Trace |
| Pickup method bound to a specific `Store` | Zone modelling that requires PostGIS (an infrastructure gate, §22) |
| Server-side tariff computation, free-shipping threshold compared against the final discounted total in the same currency and minor units | Map-based delivery-address UX (§10) |

### 6.3 `domains/accounts`

| Launch scope | Later scope |
|---|---|
| Custom `User` created before the first migration; email as `USERNAME_FIELD` with DB-level case-insensitive uniqueness; phone in canonical E.164 | Favorites (`# 13.2`) |
| Profile and addresses | Compare (`# 13.3`) |
| Actor-scoped selectors; order history via `Order.objects.for_actor(user)` | Server-side cross-device viewed history |
| Guest Track & Trace by `Order.public_id` + time-limited signed token | Personalized recommendation state |
| Guest order claim via signed link (§11 NT5) | Loyalty or reputation state |
| Account-enumeration protection, anonymization, password-reset token rules, logout/CSRF rules | — |

### 6.4 `application/checkout`

| Launch scope | Later scope |
|---|---|
| Cart | `use_cases/apply_tradein_quote.py` |
| `CheckoutSession` (contact, delivery selection, payment-method selection, displayed pricing snapshot, expiry) | Trade-In and eUpgrade participation in `place_order` |
| `use_cases/place_order.py` in its full ADR-0007 shape: read-only preparation, one durable placement transaction, in-transaction idempotency claim, post-commit provider payment | Digital fulfilment branches |
| `use_cases/apply_coupon.py` | Loyalty participation |
| Guest checkout and signed guest access | — |
| Courier / pickup fulfilment selection; cash / IBAN / maib payment selection | — |

> **Contract consequence (CK1):** the launch `place_order` contract must be **complete with trade-in
> and loyalty absent**. Item 5 §4 already left participation to the implementing phase; item 14
> settles it as *absent at launch*. No parameter, DTO field, branch or adapter may be required for a
> participant that does not exist (§19 NF4, A121, C165).

### 6.5 `application/payments_gateway`

| Launch scope | Later scope |
|---|---|
| `ports.py` ownership of the payment-gateway port and its result DTOs | The MIA port binding and its per-provider budgets |
| Post-commit charge initiation for the launch providers | Credit-provider port binding |
| Reconciliation scheduling and the ambiguous-outcome resolution path | Provider-specific capability negotiation |
| Per-provider timeout, retry, circuit and failure isolation for the bound adapters | — |

### 6.6 `application/storefront` — MVP, with the boundary of its launch scope

`application/storefront` is **MVP** (not reduced): everything master `# 25` requires of it ships.
This table records what is explicitly **not** pulled in, so the row cannot be read as "storefront
plus whatever helps ranking".

| Launch scope | Explicitly not in MVP |
|---|---|
| `ProductListingProjection` at `Product × Language` grain | OpenSearch or any external search service — **infrastructure gate** (§22) |
| Basic facets over the six frozen facet variants | Personalized recommendations or personalized ranking |
| PostgreSQL search baseline | View analytics, impressions, clickstream — item 13 |
| Deterministic sorting + keyset pagination + opaque cursor | Favorites as a popularity source at launch (§13) |
| Shared Web/API selector and DTOs; parity contract tests | A read replica for builder or serving reads — **infrastructure gate** (§22) |
| Incremental update, full/targeted rebuild, reconciliation, item 12's observe→build→guarded-write protocol | Manual merchandising boost (item 6 §27 / item 13 MB1–MB4: still ownerless) |
| `popularity_score` from the §13 launch source set | |
| Crawl-budget controls, autocomplete/debounce | |
| Anonymous HTML fragment cache with single-flight + stale fallback | |
| Fixed query budgets and N+1 tests | |

### 6.7 `domains/content` — see §9. `domains/notifications` — see §11.

---

## 7. The payment-provider cut

| # | Rule |
|---|---|
| PM1 | **The payment domain is not a provider.** The state machine, `PaymentAttempt`, amount/currency matching, webhook ingest contract, reconciliation, the signed return-URL flow and the **single provider-adapter interface** of master `# 12.4` are MVP foundation of payments. Cutting providers never cuts them (V133). |
| PM2 | **Launch providers: `maib`, `cash`, `IBAN`** — exactly master `# 25`'s MVP line. |
| PM3 | **Later providers: MIA, credit, POS-on-delivery, and any further adapter.** `# 12.4`'s five-class list and `# 11.4` step 3's six-method enumeration describe the *interface's* eventual population and the *checkout step's* eventual choices; the MVP line is the explicit and narrower statement about launch, and MP4 resolves the breadth difference in its favour. Neither passage states that MIA, credit or POS-on-delivery must be accepted at launch. |
| PM4 | **MIA is not promoted.** No master passage places a stronger launch requirement on MIA than the MVP line places on the trio; `# 12.4`'s MIA UX paragraph specifies *how* MIA behaves if enabled, not *that* it launches. Promotion would require citing such a passage, and there is none. |
| PM5 | A later provider is added by **binding one more adapter to the existing interface** in the composition root, plus its webhook route, its own `ext.payments` provider budget and its reconciliation coverage. No domain change, no state-machine change, no schema-version change (item 9 LY3). |
| PM6 | No stub, no-op or "coming soon" adapter for a later provider exists at launch, and no payment-method enum value is offered in a UI or API without a bound adapter behind it (A118, C168, V134). |
| PM7 | Cash and IBAN are **not** exempt from payment invariants: both are `PaymentAttempt`-backed with the same state machine, actor scoping, amount matching and idempotency as a card payment; "offline method" never means "informal state". |

---

## 8. Accounts, reviews, favorites and compare

### 8.1 Accounts — MVP (reduced, §6.3)

Master's MVP line requires **account + order history**. AC1: the launch scope is the minimum that
makes that promise true and safe — identity with case-insensitive email uniqueness at the DB level,
canonical E.164 phone, profile/addresses, actor-scoped order history, guest Track & Trace by signed
token, guest claim, and the enumeration/anonymization/session rules of `# 21.6` and `# 13.4`.

### 8.2 The invariants that do not move (AC2)

Reduced scope never weakens: actor-scoped access and the ban on unscoped `.get()` from a request
identifier; anonymization and account-enumeration protection; `Review.author_display_name` snapshot
semantics; the single `rating_avg_x10` representation across both projections; guest access by
signed token rather than sequential ID. **These bind whenever the feature exists**, in MVP scope and
in every later addition.

### 8.3 Reviews — MVP, and "basic" means `# 14.1` in full (AC3)

Master's "basic reviews" is not a reduced version of `# 14.1`; `# 14.1` **is** the basic module. Its
duplicate-review DB constraint, moderation status, verified-purchase badge, rate limiting/captcha,
`ProductRatingProjection` with the histogram, the `review.approved` Outbox-driven recomputation and
the storefront dirty-marking all ship. Nothing in `# 14.1` is deferred, so `reviews` is plain `MVP`,
not reduced. Trust or reputation features beyond `# 14.1` are not described anywhere in the master
and are therefore **out of scope**, not "later".

### 8.4 Favorites — LATER; Compare — LATER

| # | Rule |
|---|---|
| AC4 | **Favorites is LATER.** It is absent from the master's MVP line; it sits in Phase 7 beside launch capabilities, which under MP2 says nothing; and no launch promise depends on it. Master `# 13.2`'s merge/validation rules stay frozen and bind it whenever it ships. |
| AC5 | **Compare is LATER**, on the same evidence. Master `# 13.3`'s `CompareGroup` and `AttributeDefinition.comparable=True` constraints stay frozen. Note that `comparable` is catalog attribute **metadata** that exists regardless, so compare's absence costs the catalog nothing. |
| AC6 | **Favorites is not promoted to enrich `popularity_score`.** A one-source or even zero-source popularity policy is already valid and complete (item 13 EN3, EN5, SS2): a non-enabled source is not a term in the policy, and the deterministic tie-break yields a stable total order regardless. Promoting a launch feature to improve a ranking refinement inverts the MVP rule (V136). |
| AC7 | Because favorites is LATER, the storefront's **launch-enabled popularity source set is `{successful sales}`** (§13). This is a consequence of item 14's cut, **not a change to item 13** — item 13 §8 froze the closed *permitted* source set and explicitly left the *enabled at launch* subset here. |
| AC8 | Guest favorites in `localStorage` (master `# 13.2`) is part of the favorites feature and is equally LATER. A browser-local list with no server contract is not a partial launch of favorites, and must not be introduced as one (V137). |

---

## 9. The content cut

### 9.1 The split

`domains/content` — **MVP — REDUCED SCOPE**.

| Launch scope | Later scope |
|---|---|
| Static legal/reference pages: delivery, payment, returns, FAQ, privacy policy, terms, useful-information pages (`# 17.1`) | Blog / news / review / guide article **types** and their listing, taxonomy and archive UX (`# 17.2`) |
| Real-time editing of those pages by content and legal staff through the admin, with no developer, no template edit and no container restart (`# 17.1`) | Marketing promo landing pages with the campaign-end SEO lifecycle, 301 policy and manual `410 Gone` (`# 17.4`) |
| Publication **identity**: bigint PK + immutable public UUIDv7, RO/RU titles and strict-unique slugs (`# 17.2`, `# 6.2`) | Events calendar with `start_date`/`end_date`/`location`/coordinates and Schema.org `Event` JSON-LD (`# 17.5`) |
| Structured block-JSON rendering with sanitisation and CSP (`# 17.3`, `# 21.9`) | eSIM interactive guides: step blocks, QR generation from the digital-distribution domain, operator-column comparison (`# 17.6`) |
| Server-side consent support surface for the launch consent lifecycle (`# 21.1`) | Video content: provider video IDs, click-to-load/lazy-iframe player integration (`# 17.7`) |
| Static sitemaps where the roadmap assigns them to content | Schema.org `TechArticle`/`HowTo` markup for guides |
| Footer/navigation content keys served through the `core.cache` versioned + single-flight path (`# 19.2`) | Rich editorial workflows beyond page editing |

### 9.2 Rules

| # | Rule |
|---|---|
| CT1 | **Feature cut first; no package split.** `domains/content` stays **one** module. Splitting it because some article types are later would create a boundary no frozen artifact requires, and master `# 17.1`'s "isolated CMS domain" plus Phase 8's "content remains a candidate for future independent deployment" already describe the seam that exists. |
| CT2 | The **publication identity, block-JSON sanitisation and CSP** rules are MVP because static pages use them — Phase 8 lists them without the "according to the MVP line" qualifier it attaches to the editorial types (MP3). They are also the module's security contract, and CV7 forbids cutting them. |
| CT3 | A static/legal page must render without any Event, video, promo-campaign or guide-specific class, field or template existing. If a static page's code path requires a complex-CMS model, the cut has been violated (A122, C171, V139). |
| CT4 | The `Article.type` enum may name values whose features are later, exactly as `FulfillmentType` may (§10 DL6): an enum member is not an implemented feature. No later type is selectable in the admin or reachable by URL at launch. |
| CT5 | **Consent is not reduced.** The server-side consent lifecycle (`# 21.1`) is a launch requirement of the MVP line, is FOUNDATION-adjacent security behaviour, and is untouched by the editorial cut. MVP carries **no runtime analytics consent dependency** (item 13 CS1) because there is no analytics collection to gate. |

### 9.3 Newsletter (`# 19.3`) — **LATER**

| # | Rule |
|---|---|
| NL1 | **The newsletter capability is `LATER` in its entirety.** At launch there is **no** subscription endpoint, **no** subscriber persistence, **no** double opt-in workflow, **no** campaign or marketing sending, and **no** CRM/mailing hand-off. |
| NL2 | **The evidence does not support a launch classification.** The master's `# 25` MVP line does not name newsletter; it appears only as an unqualified entry inside a roadmap phase, and MP1/MP5 forbid deriving launch membership from a phase. No MVP capability depends on it, its CRM/mailing half is already LATER (§12), and dropping it changes no module, dependency, queue, invariant or commercial flow. Under CV1 the smallest sufficient launch cut therefore classifies it LATER, with **exactly one** answer and no residual "to be reviewed" state. |
| NL3 | **Transactional email is MVP independently of this row** (§11 NT2), because launch commerce and account flows require it. Newsletter is **not** admitted merely because an email channel exists — the FD2 direction of the mechanism/workload rule. |
| NL4 | **No owner is assigned, and none is needed now.** The master's tree contains no newsletter module. The artifact or phase that **admits** newsletter assigns a legitimate owner *before* implementation, bounded by items 2, 3 and 4; if that assignment moves or creates an architectural boundary, an ADR is evaluated **then**, under `docs/adr/README.md`. Item 14 invents no `domains/newsletter`, no `domains/marketing`, no `domains/content` ownership and no application use case (§1.3). |
| NL5 | When admitted, the capability is bound in full by master `# 19.3`'s existing requirements — server-side validation, the mandatory privacy-policy consent flag, honeypot silent rejection, rate limiting on trusted client IP + session/account + destination, double opt-in where enabled, and the low-priority isolated queue for any outbound marketing hand-off. Deferral relaxes none of them (CV7). |
| NL6 | Nothing else in the content cut moves: **static/legal pages, required operational content, privacy/terms content, server-side consent support and static sitemaps stay MVP** exactly as §9.1 and CT5 freeze them. |

---

## 10. Delivery, stores and maps

| # | Rule |
|---|---|
| DL1 | **Checkout's MVP has a real physical fulfilment path.** Launch offers **courier delivery** and **store pickup**, both server-priced through `DeliveryTariff` and both reaching a durable inventory reservation. |
| DL2 | **`domains/stores` is MVP**: `Store` with an ERP-consistent strict-unique `code`, explicit pickup/delivery capability flags, address and `Decimal` coordinates. Pickup requires it. |
| DL3 | **Store-scoped pickup reservation is MVP**: a pickup reservation is always bound to a specific `Store` (master `# 9.4`), and inter-store transfer is a separate logistics entity that is **not** launch scope and is never faked by adjusting a destination store's `on_hand`. |
| DL4 | Free-shipping evaluation compares the tariff threshold against the **final discounted total in the same currency and minor units** — an invariant, not a feature, and therefore not reduced. |
| DL5 | **Digital fulfilment is LATER**, because Digital Products / KMS is LATER. |
| DL6 | **An enum value is not a feature.** `SKU` supporting `courier`, `pickup`, `digital_email`, `digital_sms`, `external_activation` (master `# 16.1`), and checkout step 3 naming digital delivery, do **not** force Digital Products into MVP. At launch no SKU carries a digital fulfilment type, no digital branch is reachable, and no digital code, KMS key or delivery adapter exists (A119, C169, V135). |
| DL7 | **The interactive map is LATER.** No launch promise requires it: pickup-store selection is served by a store list with addresses, working hours and capability flags, which satisfies DL1 without a tile provider. |
| DL8 | DL7 is a **cut of a UX capability, never of a security rule**. If a later phase ships the map, `# 15.2`'s public-scoped token, origin/referrer restriction, separate production/staging tokens, quota alerting, rotation and the optional own-CDN proxy — and `# 21.11`'s credential rules — apply from that module's first release. Item 14 pre-approves nothing. |
| DL9 | Public OSM tiles are never used as a production CDN. Since DL7 ships no map, the launch build contains **no tile provider credential at all**, which is the strongest available form of that rule. |
| DL10 | Coordinates stay `Decimal`; **PostGIS is an infrastructure gate** (§22), exactly as master `# 15.1` frames it ("until a real need appears"). |

---

## 11. Notifications: the channel cut

`domains/notifications` — **MVP — REDUCED SCOPE**.

| Launch scope | Later scope |
|---|---|
| Transactional **email** for the launch flows: order confirmation, payment status outcome, guest channel-ownership confirmation, guest order-claim signed link, password reset | **SMS** on any channel |
| Post-commit dispatch through the Outbox with `ext.email` isolation | Push notifications |
| Bounded retry, circuit breaker, provider timeouts, DLQ/replay (FOUNDATION) | Newsletter and marketing/campaign sending (§9.3) |

| # | Rule |
|---|---|
| NT1 | **`domains/notifications` being MVP does not make every channel MVP.** The launch channel set is determined by what launch flows actually require. |
| NT2 | **Transactional email is MVP.** Order confirmation and payment-outcome notification are required by the launch commercial flow, and master `# 20.1` names email as an isolated launch workload. |
| NT3 | **SMS is LATER.** No launch flow lacks a compliant non-SMS alternative. |
| NT4 | The one flow that could have forced it — master `# 11.3`'s guest "add this order to my account", which reads "signed link/**OTP**" — is satisfied by the **signed link** branch over the MVP email channel, with server-side re-verification. The master offers the two as alternatives; item 14 selects the one whose channel is already MVP. |
| NT5 | Guest **Track & Trace** likewise needs no SMS: it opens on `Order.public_id` + a time-limited signed access token (`# 13.5`), delivered by email or by the post-checkout page. |
| NT6 | Launch authentication uses email identity with short-lived single-purpose password-reset tokens (`# 21.6`); there is **no SMS OTP login and no phone-verification requirement** at launch. Admin 2FA is TOTP/WebAuthn (`# 21.6`), not SMS. |
| NT7 | **Item 9 froze an `ext.sms` failure-domain *definition*, not a launch provisioning** (item 9 FD9, §15 here). A frozen definition is never evidence that a channel ships; §15 provisions `ext.sms` `NO`. |
| NT8 | If a later phase introduces a flow with no compliant non-SMS alternative, SMS is admitted through §18's admission rule: adapter, provider contract, consent/PII handling, `ext.sms` provisioning and an on-call owner arrive **together**. Item 9's note stands — a latency-critical security flow gets *its own* domain and class with an ADR, never a re-labelling of all SMS. |

---

## 12. CRM and Chatwoot

| # | Rule |
|---|---|
| CR1 | **CRM integration is LATER.** No master passage places CRM in the launch set; `# 20.1` names it as an isolated workload *if enabled*, and `# 19.3` point 6 routes newsletter sync to it as marketing traffic explicitly forbidden from competing with transactional work — a hand-off that has no launch producer either, since newsletter is itself LATER (§9.3). |
| CR2 | **Chatwoot is LATER**, named directly in master `# 25`'s "can wait" list ("Chatwoot with identity context") and in Phase 9. |
| CR3 | **This resolves item 9 FD9a's conditional.** `ext.crm`'s definition — name, class, isolation rule, retry class, terminal namespace, capacity relationship — **stays frozen and is not edited or deleted**; it is simply **not provisioned** at launch (§15). Item 9 §9's procedure still governs any change to the definition itself; that is a separate question from enablement. |
| CR4 | **CRM work is never routed into another queue to dodge the decision.** No CRM message may be handled in `ext.email`, `core.maintenance` or any other domain, and the forbidden general-purpose `external`/`default` queue stays forbidden (item 9 FD7). With no CRM workload, there are simply no CRM messages. |
| CR5 | **No CRM or Chatwoot call, port binding, adapter, event or column exists in an MVP flow.** In particular, `place_order` and every order state transition commit with no CRM interaction of any kind — synchronous or asynchronous (A123, C172, V140). |
| CR6 | If Chatwoot ships later it gets its **own** `BEST_EFFORT` domain (`ext.support`) rather than sharing `ext.crm`, unless item 9 §2's sharing rule is satisfied with independently enforced per-provider limits. Item 14 records this pointer and decides nothing about it. |
| CR7 | Item 14 **does not design** the Chatwoot identity-validation contract, the HMAC identifier, the guest pseudonymous conversation identity or the data-minimisation payload. `# 14.2` and `# 21.10` bind that module whenever it ships. |

---

## 13. The analytics consequence (item 13, not reopened)

| # | Rule |
|---|---|
| AY1 | **`domains/analytics` is LATER.** Item 13 option A stands, entirely unchanged and not reopened. |
| AY2 | **View tracking is LATER**, and item 13's negative list (AN1–AN13) is the operative definition of its absence: no analytics app, model, ingestion endpoint, page-view event, clickstream, behavioural stream, worker, retention store, registry entry, runtime consent dependency, third-party SDK/pixel/tag manager, fingerprint, hidden session store or server-side viewed history. |
| AY3 | **No analytics failure domain is provisioned, because none is defined** (item 9 NX3). §15's table contains no analytics row for exactly that reason — the absence is at the definition level, one step stronger than `ext.crm`'s. |
| AY4 | **The launch-enabled popularity source set is: `{successful sales}`.** Favorites is LATER (AC4), so its owner does not exist at launch and, by item 13 EN1–EN3, it is **not enabled** — it is not a term in the policy, never a stub, mock or fake adapter. |
| AY5 | Rating/review, the manual merchandising boost and page views remain **excluded** exactly as item 13 §8 left them. Reviews shipping at launch does **not** admit rating into the popularity formula; that would be a recorded scoring-policy change, and item 14 does not make one. |
| AY6 | AY4 is a statement about which item-13-permitted sources are *enabled*, not a change to item 13's closed permitted set. Enabling favorites later is a scoring-policy change under item 13 EN6 — no migration, no ADR, no new mechanism. |
| AY7 | Between Phase 4 and Phase 5 the enabled set may be **empty**, which item 13 EN5 already covers: the storefront ships complete, every score neutral, order fully determined by the deterministic tie-break. If `orders.public`'s batch aggregate selector is not yet delivered at launch, that state simply persists — it is not a defect and is never patched with a stub. |
| AY8 | Ordinary operational telemetry (logs, traces, metrics, error reporting) is unaffected and is **never** a popularity input (item 13 AN14). |

---

## 14. The optional commercial capability cut

All **LATER**. Classified only — item 14 designs no contract for any of them (§1.2).

| Capability | Class | Consequence recorded here |
|---|---|---|
| Trade-In (`# 18.1`) | LATER | `domains/tradein` absent; `apply_tradein_quote` absent; `place_order` complete without a trade-in participant (CK1); item 5 §4's "scope question for the implementing phase" is hereby answered *absent at launch*. |
| eUpgrade (`# 18.2`) | LATER | Its campaign targeting is not part of `domains/promotions`' MVP row. |
| Digital Products / KMS (`# 16`) | LATER | No `DigitalCode`, no envelope encryption, no key rotation runbook, no digital fulfilment branch (DL5, DL6). |
| Chatwoot / support platform (`# 14.2`) | LATER | §12. |
| Own WebSocket chat (Django Channels) | LATER | `# 14.2`'s hard requirements bind it from its first release if it ever ships. |
| Full analytics / view events | LATER | §13. |
| Complex Blog / news / guide types, promo landing pages, Events, eSIM guides, video CMS (`# 17.2`–`# 17.7`) | LATER | §9. |
| Favorites, Compare (`# 13.2`, `# 13.3`) | LATER | §8.4. |
| Newsletter subscription (`# 19.3`) | LATER | No endpoint, subscriber persistence, double opt-in workflow, sending or CRM hand-off at launch; its owner is assigned by the phase that admits it, and master `# 19.3` binds it in full then (§9.3 NL1–NL5). |
| Personalized recommendations / ranking | LATER | Needs its own artifact and a new ADR (item 6 SEC4, item 13 SS4). |
| Cross-device viewed history (`# 7.5`) | LATER | Recently-viewed stays browser-local at launch (item 13 §16). |

| # | Rule |
|---|---|
| OC1 | Each is independently admissible in any order (master Phase 9) and none is a prerequisite of another, with the single documented exception that eSIM guides consume digital-distribution QR data (`# 17.6` → `# 16.3`) and therefore cannot precede it. |
| OC2 | Every one of them, when it ships, obeys `public.py`, the DTO rules, event versioning and the failure-domain rules in full, and creates **no** reverse dependency in a core domain (master Phase 9). |
| OC3 | The **top header** (`# 19.1`) links to Trade-In and eUpgrade as dynamic campaign triggers. At launch those links simply do not exist. Global navigation must render correctly with zero commercial-programme links, and must not import, probe for or conditionally branch on a LATER module to decide (A124, C173, V141). |

---

## 15. Failure-domain launch provisioning (a derived view of item 9)

> **This section edits nothing.** Item 9 and the [queue / failure-domain matrix](../events/queue-failure-domain-matrix.md)
> remain the authority on every domain's name, class, isolation rule, retry class, terminal namespace
> and capacity relationship. Item 14 supplies only the column item 9 FD9/FD9a deferred here:
> **is it provisioned at launch?** "Provisioned" means given a physical queue, workers, a terminal
> namespace and an on-call owner.

| Failure domain | Class (item 9) | Provision at launch | Reason — the enabled workload |
|---|---|---|---|
| `core.payments` | CRITICAL | **YES** | Local payment-state convergence for maib/cash/IBAN; must run through any provider outage. Payments are MVP. |
| `ext.payments` | CRITICAL | **YES** | Provider-facing calls for the launch provider set (maib), post-commit charge and reconciliation. |
| `core.inventory` | CRITICAL | **YES** | Reservation expiry and local inventory convergence. Inventory/reservations are MVP. |
| `core.projection.incremental` | IMPORTANT | **YES** | Incremental `ProductListingProjection` updates from catalog/pricing/inventory/reviews changes. Storefront is MVP. |
| `core.projection.rebuild` | IMPORTANT | **YES** | Full/targeted rebuild and reconciliation, including ERP-import-coalesced batches. Its separation from incremental is the reason the domain exists and is not deferred. |
| `core.maintenance` | BEST_EFFORT | **YES** | Reservation sweeps, Outbox/Inbox retention, cache re-warm, scheduled recomputation. |
| `ext.erp` | IMPORTANT | **YES** | ERP batch import/synchronisation and balance reconciliation. Explicitly in the MVP line. |
| `ext.email` | BEST_EFFORT | **YES** | Transactional email for the launch flows (§11). |
| `ext.sms` | BEST_EFFORT | **NO** | **No enabled SMS workload** — SMS is LATER (NT3). Definition frozen and retained (NT7). |
| `ext.crm` | BEST_EFFORT, conditional | **NO** | **No enabled CRM workload** — CRM is LATER (CR1). This resolves item 9 FD9a's conditional; the definition is frozen and retained, not deleted (CR3). |
| *(an analytics domain)* | — | **not applicable** | **No definition exists** (item 9 NX3), because `domains/analytics` is LATER (AY3). Stronger than "not provisioned". |
| *(a support / `ext.support` domain)* | — | **not applicable** | No definition exists (item 9 NX2); Chatwoot is LATER (CR6). |
| *(a search / OpenSearch domain)* | — | **not applicable** | Not reserved; OpenSearch is an infrastructure gate (§22). |

| # | Rule |
|---|---|
| FP1 | **No workload ⇒ no provisioning.** A frozen definition never justifies a queue, a worker pool, a terminal namespace or an on-call rotation on its own (item 9 FD9). |
| FP2 | **Every domain a launch workload needs is provisioned**, with its isolation rule intact — reserved capacity for `CRITICAL`, no sharing across the pairs item 9 forbids, and no general-purpose fallback queue (item 9 FD7). |
| FP3 | Provisioning a domain later is an **operational** change: it adds a queue, workers, a terminal namespace and an owner. It bumps no `schema_version`, creates no `event_type` and requires no consumer redeclaration (item 9 LY3, RT6, RT11). |
| FP4 | Item 14 chooses **no** worker count, concurrency, prefetch, queue name syntax, Celery route or broker topology. Those are Phase 1's and the operational owner's. |
| FP5 | The Outbox relay is not a consumer failure domain and is sized independently, fair across routes, at launch as always (item 9 FD11, QO3, QO4). |
| FP6 | A LATER workload's absence is **never** simulated by routing it into a provisioned domain (CR4), and never by a task that succeeds without doing anything (§19 NF2). |

---

## 16. Dependency-closure matrix

For every MVP capability: does it require another module? If yes, exactly one of **A** (the
dependency is FOUNDATION/MVP), **B** (the capability is narrowed so the dependency is not required)
or **C** (the apparent dependency is false, and a contract proves why) must hold. There is no fourth
state.

> **The "required dependencies" column names *capability* dependencies — which other module must
> exist for this launch capability to be true — not import mechanics.** How each dependency is
> reached (a `public.py` call, an application-layer composition, or an identity reference that is no
> dependency at all) is fixed unchanged by items 2, 3 and 4, and item 14 neither restates nor
> relaxes it.

| Module | Launch capability | Required module dependencies | All FOUNDATION/MVP? | Later dependency explicitly absent | Resolution | Degradation with the later feature missing |
|---|---|---|---|---|---|---|
| `domains/catalog` | Product/SKU/typed EAV/media/i18n | `core` | Yes | analytics, reviews-as-source, storefront | **A** | None. ADR-0003 keeps price, stock, ERP identity and projection outside catalog. |
| `domains/pricing` | Sell price, `PriceProjection` | `core.money`, `core` | Yes | tradein, eUpgrade campaigns | **A** | None. Trade-In is a checkout-time deduction, not a pricing input at launch. |
| `domains/promotions` | Coupon/promotion core, atomic redemption | `core`, DB constraints | Yes | eUpgrade campaigns, promo landing pages | **A** | None. A promotion needs no landing page to be valid. |
| `domains/inventory` | Balances, reservations, store-scoped pickup | `core`; `stores` must **exist** for pickup to mean anything | Yes | analytics, tradein | **A** | None. |
| `domains/orders` | Order aggregate, snapshots, actor-scoped history | `core` | Yes | CRM, Chatwoot, analytics, tradein | **A** + **C** | None. **C**: no master passage makes any of them a participant in an order state transition; CR5 makes it checkable. |
| `domains/payments` | State machine, attempts, reconciliation | `core`; `orders` must exist to have an amount to match | Yes | MIA, credit, POS-on-delivery | **B** | None: the provider set is narrowed, the mechanism is complete. A later adapter binds without domain change (PM5). |
| `domains/reviews` | `# 14.1` in full, rating projection | `core`; `accounts` (author identity) and `orders` (verified-purchase fact) must exist | Yes | analytics | **A** | None. Rating is an independent storefront signal, never a popularity term (AY5). |
| `domains/delivery` | Courier + pickup tariffs | `core.money`; `stores` must exist for the pickup method | Yes | digital fulfilment, map provider | **B** | None. Pickup selection is a store list (DL7). |
| `domains/stores` | Store, pickup flags | `core` | Yes | map provider, PostGIS | **A** + **B** | Store list renders without a map; coordinates stay `Decimal`. |
| `domains/content` | Static/legal pages, consent surface, sitemaps | `core`, CSP/sanitisation | Yes | Blog, Promo, Events, eSIM, video | **B** | None. CT3 makes the independence checkable. |
| `domains/accounts` | Identity, profile, order history, guest claim | `core.security`; `orders` must exist for history; the MVP email channel for the claim link | Yes | favorites, compare, viewed history, Chatwoot | **B** | Account pages render with no favorites/compare entry points; no placeholder page and no empty-state for an absent feature. |
| `domains/notifications` | Transactional email | `core.outbox`, `ext.email`, email adapter | Yes | SMS, CRM, push | **B** | None: every launch flow has an email path (NT4–NT6). |
| `application/storefront` | Projection, facets, search, sort, cache, popularity | `core`, `catalog`/`pricing`/`inventory`/`reviews` `.public` | Yes | analytics, favorites, OpenSearch, read replica, personalization | **A** + **B** + **C** | **C**: item 13 proves popularity needs no analytics; §22 proves listing needs no OpenSearch; item 12 CB10–CB14 require **authoritative** reads, so a replica is not merely unnecessary but forbidden for the builder. Popularity runs on `{sales}` (AY4). |
| `application/checkout` | Cart, session, `place_order`, coupon | `core.idempotency`, `pricing`/`inventory`/`orders`/`promotions`/`delivery`/`payments` `.public`, `payments_gateway` | Yes | tradein, eUpgrade, digital, analytics, CRM, Chatwoot | **B** + **C** | **B**: no trade-in participant, no digital branch (CK1, DL6). **C**: CRM/Chatwoot/analytics are named in no placement step by item 5 §4. |
| `application/payments_gateway` | Port, post-commit charge, reconciliation | `core`, `payments.public`, `integrations/maib` | Yes | MIA, credit adapters | **B** | None; per-provider isolation already generalises. |
| `application/erp_sync` | Batch import/sync, mapping, coalesced events, reconciliation | `core`, `catalog`/`inventory`/`pricing` `.public`, `integrations/erp` | Yes | OpenSearch index batch, CRM | **B** + **C** | **C**: master `# 9.3`'s `search.index.batch` is explicitly conditional ("only if OpenSearch is enabled"); at launch that event is not produced at all — not produced-and-ignored. |
| `interfaces/web` | Storefront, checkout, account, content pages | application + single-domain `public` | Yes | favorites/compare UI, Chatwoot widget, map, Trade-In links | **B** | Navigation and pages render with those entry points absent (OC3). |
| `interfaces/api/v1` | DRF parity over the same DTOs | `application/storefront` DTOs | Yes | a native mobile client | **C** | An API is not a client (§21). |
| `interfaces/webhooks` | maib ingest, ERP ingest | `core.inbox`, `core.security` | Yes | MIA route, Chatwoot route | **B** | Absent routes are absent URLs, not disabled handlers. |
| `interfaces/admin` | Single-domain admin surfaces, DLQ replay | domain `public`, `core` | Yes | `application/backoffice` | **B** + **C** | **C**: BO3 — replay is a `core` mechanism, not cross-domain business. |

**Closure result: every MVP row resolves to A, B or C. No MVP module requires a LATER module.**

---

## 17. Launch dependency graph — narrative

The launch graph is a tree with three roots and no edge into the LATER set.

```text
FOUNDATION  (core, integrations/base, contracts, budgets, ops)
    ↑ used by everything below, and by nothing later

domains      catalog · pricing · promotions · inventory · orders
             payments(maib/cash/IBAN) · reviews · delivery(courier/pickup)
             stores · content(static) · accounts(no favorites/compare)
             notifications(email)
    ↑ each knows only itself + core

application  storefront ← catalog/pricing/inventory/reviews .public
             checkout   ← pricing/inventory/orders/promotions/delivery/payments .public
             payments_gateway ← payments .public + maib adapter
             erp_sync   ← catalog/inventory/pricing .public + erp adapter

interfaces   web · api/v1 · webhooks(maib, erp) · admin(single-domain)
```

Read top-down, three properties hold at launch.

**First, the foundation carries no feature scope.** Every mechanism in §5.1 exists because the
launch set as a whole needs it, not because a particular optional module does. The event-registry
validator ships with an empty registry; the failure-domain machinery ships with two of its ten
definitions unprovisioned; the idempotency mechanism serves placement and message consumers alike.
None of that is contingent on the feature cut, which is why cutting features never destabilises it.

**Second, every cross-domain workflow at launch has exactly one owner that already existed.**
Checkout owns placement, storefront owns the read model, payments_gateway owns the provider
boundary, erp_sync owns the import. The cut removes participants from those workflows (trade-in) and
adapters from those boundaries (MIA), never an owner and never a workflow.

**Third, the LATER set is reachable from nothing.** The edges that *would* have pointed into it are
each individually accounted for: checkout→tradein is removed by CK1; storefront→analytics is removed
by item 13 and storefront→favorites by AY4; orders→CRM never existed (CR5); content→editorial types
is removed by CT3; delivery→digital is removed by DL5/DL6; notifications→SMS is removed by NT3;
web→Chatwoot/map/commercial-programme links is removed by OC3 and DL7; erp_sync→OpenSearch index is
conditional in the master itself. Because those edges are absent rather than stubbed, the launch
build is a **strict subgraph** of the eventual system: adding a LATER module later adds nodes and
edges, and rewrites none.

---

## 18. The later-feature admission rule

| # | Rule |
|---|---|
| AD1 | A LATER capability enters through **its own workflow and its own contracts**, owned by the module that implements it — never by relaxing an MVP module's contract in advance to leave room. |
| AD2 | Admission is **atomic across its surfaces**: the module, its `public.py`, its DTOs, its registered event versions (if any), its failure-domain provisioning, its adapter and its on-call owner arrive together. A half-admitted capability is the state item 13 DC1 rejected in the analytics case, generalised. |
| AD3 | Admission never changes a frozen invariant. If it appears to require one, that is an ADR-scale discovery and stops the admission (`docs/adr/README.md`). |
| AD4 | Admission requires no reopening of item 14. This artifact freezes the **launch** cut; a post-launch module shipping is the roadmap operating normally, not a supersession. |
| AD5 | An MVP module consuming a newly admitted capability changes **its own** contract at that point, under item 4's compatibility policy — a widening, forward, with tests. It does not pre-widen at launch. |
| AD6 | Admitting a capability whose absence is currently load-bearing for a proof here (favorites for AY4, digital fulfilment for DL6) requires re-reading that section's rule, not re-deciding it: each already states what changes (AY6, DL6). |

---

## 19. No fake compatibility layers

> **MVP code depends only on real MVP/FOUNDATION contracts.** The absence of a LATER module is
> expressed by the absence of a call, never by the presence of a substitute.

Rejected **by name**:

| # | Rejected shape |
|---|---|
| NF1 | An empty package for a LATER domain created so an import resolves (`domains/analytics`, `domains/tradein`, a support package) — PX1, PX2. |
| NF2 | A `NullAnalyticsService`, no-op event emitter or silently-succeeding task standing in for a LATER consumer. |
| NF3 | A fake CRM adapter, a fake Chatwoot client or a "logging-only" outbound stub. |
| NF4 | A fake Trade-In provider, a zero-valued trade-in quote, or a `trade_in=None` parameter that exists only to keep a future signature. |
| NF5 | A placeholder favorites repository, an always-empty favorites selector, or a zero-count favorites aggregate presented to the popularity policy (item 13 EN3: a non-enabled source is **not a term**, not a zero). |
| NF6 | A `NullSmsGateway` or an SMS send that is silently dropped. |
| NF7 | A "temporary" `if FEATURE_EXISTS` / `try: import ... except ImportError` cross-domain import. |
| NF8 | Runtime probing of `INSTALLED_APPS`, the module registry or the filesystem to detect whether a domain is installed. |
| NF9 | A general-purpose application service that silently changes behaviour depending on package presence — the most dangerous shape, because it makes the dependency real while hiding it from the import graph. |
| NF10 | A settings flag that toggles a LATER module's code path in the launch build, with the code present but unreachable. Absent means absent. |
| NF11 | A payment-method, fulfilment-type or article-type option offered in a UI/API without a bound implementation behind it (PM6, DL6, CT4). |
| NF12 | A queue, terminal namespace or on-call rotation provisioned for an unenabled workload "so it is ready" (FP1). |

| # | Rule |
|---|---|
| FD1 | **A mechanism is never LATER because one eventual consumer is.** The event-versioning mechanism is FOUNDATION even though analytics events are LATER; the failure-domain machinery is FOUNDATION even though `ext.crm` is unprovisioned; the public-contract rules are FOUNDATION even though `domains/tradein` is LATER; the integration-client resilience primitives are FOUNDATION even though the CRM and SMS adapters are LATER. |
| FD2 | The converse also holds: a mechanism existing is never an argument for enabling a workload. `ext.sms` being defined does not ship SMS (NT7); `# 16.1`'s enum does not ship digital products (DL6); `application/backoffice` appearing in the illustrative tree does not create a use case (BO1). |
| FD3 | Distinguish **mechanism** from **workload** in every review: mechanism is FOUNDATION and complete at launch; workload is classified per module and provisioned per §15. |

---

## 20. Failure / degradation matrix

Twenty cases. "Not shipped" and "runtime outage" are different columns of thought and are never
conflated: the first has no incident, no alert and no retry; the second is an existing frozen
mechanism doing its job.

| # | Case | Kind | Launch request path | Commercial correctness | Degraded UX acceptable | Existing mechanism |
|---|---|---|---|---|---|---|
| 1 | Analytics absent | not shipped | Intact | Unaffected | No degradation — nothing reads it | Item 13; popularity on `{sales}` |
| 2 | Favorites absent | not shipped | Intact | Unaffected | Yes — no favorites entry point exists | AY4; item 13 EN3 (not a term) |
| 3 | CRM absent | not shipped | Intact | Unaffected — no order/commit interaction (CR5) | Yes — no launch flow produces CRM work, newsletter included (NL1) | `ext.crm` unprovisioned (FP1) |
| 4 | Chatwoot absent | not shipped | Intact | Unaffected | Yes — support is contact details from `# 19.1` settings | None needed |
| 5 | SMS absent | not shipped | Intact | Unaffected | Yes — every flow has an email path (NT4–NT6) | `ext.sms` unprovisioned |
| 6 | MIA absent | not shipped | Intact | Unaffected — maib/cash/IBAN complete the flow | Yes — method not offered (PM6) | — |
| 7 | Trade-In absent | not shipped | Intact | Unaffected — `place_order` complete without it (CK1) | Yes — no top-header link (OC3) | — |
| 8 | Digital Products absent | not shipped | Intact | Unaffected — no SKU carries a digital type (DL6) | Yes | — |
| 9 | Complex CMS absent | not shipped | Intact | Unaffected | Yes — static/legal pages fully served (CT3) | — |
| 10 | OpenSearch absent | infrastructure gate closed | Intact | Unaffected | No degradation — PostgreSQL **is** the launch search engine (`# 10.1`) | Item 15 / Phase 10 |
| 11 | Read replica absent | infrastructure gate closed | Intact | Unaffected — and even if a replica existed, item 12 CB10–CB14 forbid the projection builder from finalizing any candidate field from a lagging copy | None | Default reads on primary; replica is explicit opt-in only (`# 22.8`) |
| 12 | PgBouncer absent | infrastructure gate closed | Intact | Unaffected | None — psycopg pool + timeouts are FOUNDATION | Item 15 / Phase 10 |
| 13 | Manual boost absent | not shipped, ownerless | Intact | Unaffected | Yes — ranking uses `{sales}` + tie-break | Item 6 §27; item 13 MB1–MB4 |
| 14 | A LATER module's directory does not exist at all | not shipped | Intact | Unaffected | Yes — no import, no probe, no branch (NF1, NF7, NF8) | PX1 |
| 15 | An optional provider is enabled later | admission | Intact throughout | Unaffected | Additive only | PM5, AD1–AD5, FP3 |
| 16 | MVP ERP unavailable | **runtime outage** | Intact — storefront and checkout serve from local truth | Preserved: site `reserved` is never overwritten by ERP; balances go stale, they do not become wrong | Yes — bounded staleness | `ext.erp` isolation, circuit breaker, bounded retry, DLQ/replay, reconciliation |
| 17 | MVP email provider unavailable | **runtime outage** | Intact — order placement never depends on it | Unaffected: dispatch is post-commit through the Outbox | Yes — delayed confirmations | `ext.email` isolation, retry, DLQ/replay |
| 18 | MVP payment provider unavailable | **runtime outage** | Intact — cash/IBAN remain selectable | Preserved: `core.payments` runs through provider outage by design; no order is silently paid or silently failed | Yes — one method temporarily unusable | `core.payments`/`ext.payments` split, circuit breaker, reconciliation |
| 19 | Projection rebuild worker unavailable | **runtime outage** | Intact — serving reads the existing projection | Unaffected — the projection is never checkout truth (ADR-0008) | Yes — bounded staleness; incremental updates continue in their **own** domain | `core.projection.rebuild` isolated from `.incremental` (item 9 PJ2) |
| 20 | Basic reviews stale or unavailable | **runtime outage** | Intact — listing and product pages render | Unaffected — rating is never a price, availability or popularity input (AY5) | Yes — stale or hidden rating block | `ProductRatingProjection` + item 12 protocol; a failing authoritative read preserves the previous value (item 13 EN4) |

| # | Rule |
|---|---|
| DG1 | Cases 1–15 are **feature-not-offered**: no alert, no retry, no incident, no runbook, no DLQ entry. Cases 16–20 are **enabled-workload failures**: they are alertable, retried and reconciled by mechanisms items 9, 10 and 12 already froze. |
| DG2 | No case degrades a commercial guarantee. Order placement, money computation, reservation atomicity, idempotency and authorization behave identically in every row. |
| DG3 | No case is handled by silent substitution. An enabled-but-failing source preserves its previous value and fails its unit of work; it is never degraded to a neutral or zero (item 13 EN4). |

---

## 21. API capability vs native mobile client

| # | Rule |
|---|---|
| AP1 | **`interfaces/api/v1` is MVP.** Master `# 10.9` and Phase 4 require Web/API parity over the same storefront DTOs, and the parity contract test is part of the launch quality gate. |
| AP2 | **A native mobile application is not implied by AP1 and is not classified as MVP.** A public API capability and a native client product are different questions; DRF existing is not a commitment to ship an app. |
| AP3 | Nothing in the launch cut may be justified by "the mobile app needs it". If a native client is ever built, it consumes the same DTO contract, and its own product scope is decided outside this artifact. |

---

## 22. Infrastructure gates — classified, not decided

| Gate | Class | Left to |
|---|---|---|
| OpenSearch | INFRASTRUCTURE GATE | item 15 / master `# 25` Phase 10, `# 10.8` |
| Read replica | INFRASTRUCTURE GATE | item 15 / `# 22.8`; item 12 CB10–CB14 constrain the projection builder's reads regardless |
| PgBouncer | INFRASTRUCTURE GATE | item 15 / `# 22.6` |
| Separate analytics / search / image service | INFRASTRUCTURE GATE | item 15 / Phase 10 |
| Microservice extraction of the ACID core (`catalog`/`pricing`/`inventory`/`orders`/`payments`/`checkout`) | INFRASTRUCTURE GATE | Phase 10 — the master requires a **separate ADR with saga/compensation design**; item 14 pre-approves nothing |
| PostGIS for geo queries | INFRASTRUCTURE GATE | `# 15.1` ("until a real need appears"); coordinates stay `Decimal` (DL10) |
| Next.js / separate frontend stack | INFRASTRUCTURE GATE | `# 2` — conditional on an independent frontend team or SPA need |

| # | Rule |
|---|---|
| IG1 | A gate is opened by **measured evidence** and, where the master says so, an ADR — never by a feature request and never by this artifact. |
| IG2 | Item 14 decides **no** threshold, topology, vendor, sizing or sequencing for any gate. |
| IG3 | No MVP module's correctness may depend on a gate being open. Storefront listing works without OpenSearch (case 10); correctness never reads a replica (case 11); the connection pool is FOUNDATION, not PgBouncer (case 12). |
| IG4 | Marking a gate here is **not** the item 15 decision. Item 15 stays **IN PROGRESS**, and its no-replica-at-launch ADR and the generic idempotency-mechanism ADR remain open (§25). |

---

## 23. Checks a later phase must implement

These **extend** the enforcement maps of items 3, 4, 5, 6, 7, 8, 9, 10, 11, 12 and 13; those remain
authoritative and unchanged. Nothing here is implemented in Phase 0.

### 23.1 Import graph (`L` series)

**No new `L` rule and no new `core` allowlist entry.** Item 14 adds no module and no import edge;
the launch build is a strict subgraph of the already-permitted graph (§17). L1–L21 stand unedited.

### 23.2 Static / AST (continuing the `A` series)

| # | Rule |
|---|---|
| A114 | **No MVP module imports, references or names a LATER module** — no import, no string module path, no app label, no settings entry, no URL include, no template include (§16, §19). |
| A115 | **No `try: import` / `ImportError` fallback, no `INSTALLED_APPS` membership probe and no filesystem check** is used to detect whether a domain is installed (NF7, NF8). |
| A116 | **No analytics module, app, model, admin, migration or package exists** under any analytics name — item 13 A101 restated as a launch-cut check, extended to forbid an *empty* package (PX2, NF1). |
| A117 | **No page-view, impression, clickstream, session-activity or view-counter collection** exists anywhere in the source tree, including in an interface, a task or an integration adapter (item 13 AN3, AN4). |
| A118 | **No payment adapter, port binding, webhook route, settings key or enum-backed UI option exists for a LATER provider** (MIA, credit, POS-on-delivery) (PM6, NF11). |
| A119 | **No digital-fulfilment branch, `DigitalCode`, KMS key handling or digital delivery adapter exists**, and no SKU fixture or migration assigns a digital fulfilment type (DL5, DL6). |
| A120 | **No SMS adapter, SMS task, SMS template or SMS provider setting exists**, and no `ext.sms` route is registered (NT3, FP1). |
| A121 | **`place_order`'s signature, DTOs and step list name no trade-in, eUpgrade, loyalty, CRM, Chatwoot or analytics participant** (CK1, CR5). |
| A122 | **A static/legal content page's code path references no Event, video, promo-campaign or guide-specific model, field, template or serializer** (CT3). |
| A123 | **No CRM or Chatwoot client, port, adapter, task, event, settings key or column exists** in the launch build (CR5). |
| A124 | **Global navigation, the top header and the footer contain no import of, and no conditional branch on, a LATER module** (OC3). |
| A125 | **No null/no-op/stub/fake adapter, repository, service or gateway exists for a LATER capability**, by class name or by behaviour (NF2–NF6, NF9). |
| A126 | **No queue, terminal namespace, route or worker configuration is declared for `ext.sms`, `ext.crm` or any unenabled workload** (FP1, NF12). |
| A127 | **No OpenSearch, replica-routing, PgBouncer or PostGIS client, setting, index definition or query hint exists** in the launch build (IG3). |
| A128 | **No settings flag gates a LATER module's present-but-unreachable code path** (NF10). |

### 23.3 Behavioural / contract tests (continuing the `C` series)

| # | Rule |
|---|---|
| C161 | **The MVP boots and serves with every LATER module absent from the source tree** — not disabled, absent: no import error, no startup probe, no degraded-mode banner. |
| C162 | **Storefront listing, search, facets, sorting and pagination work with analytics absent**, within their frozen query budgets (item 13 C148 restated at the module-cut level). |
| C163 | **Storefront works with favorites absent**, and `popularity_score` is computed from `{sales}` alone with a deterministic, repeatable order — with no favorites stub participating (AY4, NF5). |
| C164 | **Catalog and listing work with OpenSearch absent**: the PostgreSQL search baseline satisfies the launch search contract and no code path expects an external index (IG3). |
| C165 | **`place_order` succeeds with Trade-In and eUpgrade absent**, including retry/double-click idempotency, for every launch payment method and both fulfilment methods (CK1). |
| C166 | **Order commit succeeds with CRM and Chatwoot absent**, and no order state transition attempts any CRM/support interaction, synchronous or asynchronous (CR5). |
| C167 | **The payment flow completes end to end with only the launch providers** — maib online, cash, IBAN — including webhook ingest, worker convergence and reconciliation. |
| C168 | **No later payment method is selectable**: the checkout payment step and the API expose exactly the bound adapters (PM6). |
| C169 | **Checkout offers no digital fulfilment path**, and a fulfilment-type enum value with no implementation is unreachable from every interface (DL6). |
| C170 | **Checkout completes over a real physical fulfilment path** — courier and pickup — with pickup producing a store-scoped reservation and with no map provider configured (DL1, DL3, DL7). |
| C171 | **The legal/static content flow works without Blog, Events, eSIM or video machinery**: pages render, are admin-editable without a deploy, and carry the frozen CSP/sanitisation behaviour (CT1–CT3). |
| C172 | **Account and order-history flows work with compare and favorites absent**, preserving actor scoping, guest signed-token access and anonymization behaviour (AC2). |
| C173 | **Global navigation renders with zero commercial-programme links** and with the support entry point reduced to contact details (OC3). |
| C174 | **Transactional email covers every launch flow with SMS absent**, including the guest order-claim signed link and password reset (NT4–NT6). |
| C175 | **The provisioned failure domains are sufficient**: every launch async workload has a domain with reserved capacity where its class requires it, and the unprovisioned definitions (`ext.sms`, `ext.crm`) receive no message at all (§15). |
| C176 | **Reviews being MVP does not change popularity**: enabling reviews leaves `popularity_score` computed from `{sales}` only (AY5). |

### 23.4 Review-only (continuing the `V` series)

| # | Rule |
|---|---|
| V130 | An invariant cut "for MVP" — a dropped constraint, a skipped actor scope, a float money field, a relaxed idempotency claim, a waived query budget — justified by the launch cut (CV7, master `# 5` principle 39). |
| V131 | An empty package, app label or migration created for a LATER domain so that an import, a settings entry or a test fixture resolves (PX1, PX2, NF1). |
| V132 | A LATER module reached through a settings flag, a feature toggle or an environment variable while its code sits in the launch build (NF10, A128). |
| V133 | The payment **domain**, state machine, webhook contract or reconciliation cut because a provider was cut (PM1). |
| V134 | A later payment provider assumed available — a method rendered, a fee computed, a branch taken, a test fixture created — without a bound adapter (PM6). |
| V135 | Digital Products pulled into MVP by a fulfilment-type enum value, a checkout step label or a delivery-method constant (DL6). |
| V136 | Favorites promoted to enrich `popularity_score`, or any LATER feature promoted to improve another module's output rather than to meet a launch promise (AC6). |
| V137 | A partial launch of a LATER feature presented as "not really the feature" — guest favorites in `localStorage`, a compare list held only client-side, a hidden viewed-history store (AC8, item 13 AN13, §16). |
| V138 | SMS assumed by a launch flow — an OTP-only branch, a phone-verification requirement, an SMS template, an `ext.sms` route (NT3, A120). |
| V139 | A static/legal page depending on a complex-CMS model, block type, Event field or video embed pipeline (CT3). |
| V140 | CRM or Chatwoot reached from an order, payment or account flow, or CRM work routed into another provisioned queue to avoid the provisioning decision (CR4, CR5). |
| V141 | Navigation, header or footer branching on a LATER module's presence instead of simply not rendering the entry point (OC3). |
| V142 | OpenSearch required by a storefront path, a replica read treated as correctness truth, or a gate assumed open (IG3, item 12 CB10–CB14). |
| V143 | An item 15 infrastructure gate treated as decided here — a threshold, a vendor, a topology or a sizing number attributed to item 14 (IG2, IG4). |
| V144 | A queue, worker pool, terminal namespace or on-call rotation provisioned for an unenabled workload because its definition is frozen (FP1, NF12). |
| V145 | Item 14 cited as authority for something it did not decide — an owner assignment, an infrastructure threshold, a deferred feature's contract, a change to item 13's source set, or the reopening of a frozen item (§1.2, §1.3). |

---

## 24. Acceptance checklist

- [x] 1. Every named business module has a launch classification (§5).
- [x] 2. Every mixed-scope MVP module lists exactly what is in and out (§6, §9, §11; CV3).
- [x] 3. `FOUNDATION` is distinct from MVP feature scope (CV2, §5.1, FD1–FD3).
- [x] 4. Phase number is not used as launch membership (MP1–MP5).
- [x] 5. Catalog is MVP (§5.2).
- [x] 6. Pricing is MVP (§5.2).
- [x] 7. Promotions / coupon core is MVP (§5.2).
- [x] 8. Inventory / reservations is MVP (§5.2).
- [x] 9. ERP batch sync is MVP — domain seam, application module, adapter, ingest, workload and task (§5.3, §5.5, §5.6, §5.7, §15).
- [x] 10. Storefront projection + basic facets is MVP, with its launch scope bounded (§5.3, §6.6).
- [x] 11. Checkout / Order / durable idempotency is MVP (§5.3, §6.4).
- [x] 12. Launch payment providers are explicit: maib, cash, IBAN (PM2).
- [x] 13. Later payment providers are explicit: MIA, credit, POS-on-delivery, further adapters (PM3, PM4).
- [x] 14. Delivery / store launch scope is explicit (§6.2, §10).
- [x] 15. Accounts launch scope is explicit (§6.3, §8.1).
- [x] 16. Basic reviews are explicit — `# 14.1` in full (AC3).
- [x] 17. The favorites decision is explicit: **LATER** (AC4).
- [x] 18. The compare decision is explicit: **LATER** (AC5).
- [x] 19. Static / legal content is MVP (§9.1).
- [x] 20. Complex CMS scope is later (§9.1, CT3).
- [x] 21. The consent foundation for launch is preserved (CT5).
- [x] 22. Notification launch channels are explicit: email MVP, SMS LATER (NT1–NT8).
- [x] 23. The CRM decision is explicit: **LATER** (CR1).
- [x] 24. Chatwoot is explicit: **LATER** (CR2).
- [x] 25. Analytics remains later exactly per item 13, unreopened (AY1–AY3).
- [x] 26. Trade-In is later (§14).
- [x] 27. eUpgrade is later (§14).
- [x] 28. Digital / KMS is later (§14, DL5).
- [x] 29. OpenSearch = infrastructure gate (§22).
- [x] 30. Read replica = infrastructure gate (§22).
- [x] 31. PgBouncer = infrastructure gate (§22).
- [x] 32. Separate services / microservice extraction = infrastructure gate (§22).
- [x] 33. No MVP module depends on a LATER module — closure resolved A/B/C for every row (§16).
- [x] 34. No fake or null later-module adapter exists (§19 NF1–NF12, A125).
- [x] 35. Failure-domain provisioning follows actual launch workloads (§15, FP1).
- [x] 36. Item 9's `ext.crm` conditional is resolved: **defined, not provisioned** (CR3, §15).
- [x] 37. Item 13's launch popularity enabled-source consequence is stated: **`{successful sales}`** (AY4, AY7).
- [x] 38. No event contract is invented — no `event_type`, payload or version appears here.
- [x] 39. No queue topology, route syntax or worker number is invented (FP4).
- [x] 40. No existing frozen invariant is weakened (CV7, V130; items 1–13 unedited).
- [x] 41. Item 15 remains open and is not pre-empted (IG4, §25).
- [x] 42. The ADR need is evaluated honestly and answered **no**, with what *would* have required one named (§1.3).
- [x] 43. No production code, schema, package, migration, dependency or infrastructure is created (§1.2).

---

## 25. Explicitly deferred — to item 15 and to later phases

| Deferred | Owner |
|---|---|
| OpenSearch, read replica, PgBouncer, separate analytics/search/image services, ACID-core extraction, PostGIS, a separate frontend stack — their thresholds, evidence, topology and vendors | **item 15** / master `# 25` Phase 10 (IG1–IG4) |
| The remaining open Phase 0 ADRs — the generic idempotency mechanism/schema, and no-replica-at-launch | **item 15**, still `IN PROGRESS` |
| The owner of the newsletter subscriber entity | **the artifact/phase that admits newsletter**, which assigns it before implementation, bounded by items 2, 3, 4 — with an ADR evaluated then if the assignment moves or creates a boundary (NL4) |
| The owner of the manual merchandising boost | **item 6 §27, untouched** (item 13 MB2) |
| Whether `application/backoffice` is admitted, and for which cross-domain administrative action | the implementing phase, under item 3 §13's frozen rule (BO4) |
| Whether the launch ERP protocol is push, scheduled pull, or both | Phase 3 integration design (§5.5) — both shapes are inside the MVP boundary |
| Scoring weights, window, quantization and schedule for `popularity_score` | Phase 4 / merchandising (item 13 SP1–SP13) |
| The `orders.public` batch aggregate selector delivering the sales source | `domains/orders`' phase (item 13 AG3, AG4); until then the enabled set may be empty (AY7) |
| Trade-In, eUpgrade, digital/KMS, Chatwoot identity, analytics event schemas, MIA protocol details, recommendation schemas, complex CMS models | each capability's own artifact when it is admitted — **classified only here** (§1.2, §14) |
| The newsletter capability itself — its endpoint, subscriber entity, double opt-in workflow, sending and CRM/mailing hand-off | **LATER** (NL1); admitted under §18's rule, bound by master `# 19.3` in full (NL5) |
| Consent categories, banner state machines, retention periods, revocation mechanics | Phase 8 and the privacy phases (item 13 CS2, CS3) |
| Any change to this launch cut before launch | a recorded decision in this artifact; after launch, ordinary roadmap admission under §18, which needs no supersession (AD4) |

---

## 26. Self-review record

| # | Check | Result |
|---|---|---|
| 1 | Is analytics marked both MVP and later anywhere? | Pass — LATER only (§5.2, §13). §15 records the stronger fact that no analytics failure domain is even *defined*, so there is nothing to provision by accident. |
| 2 | Is favorites marked later but required by the storefront? | Pass — AY4 removes the only edge (popularity), and item 13 EN3 makes a non-enabled source *not a term* rather than a zero, so no stub is needed to fill it. C163 asserts the storefront runs on `{sales}` alone; NF5 forbids the placeholder. |
| 3 | Is MIA later but required for payment acceptance? | Pass — PM2 gives three launch methods, C167 exercises them end to end, and PM6/A118 keep MIA out of every surface. PM4 records that promotion would have needed a stronger master passage, and that none exists. |
| 4 | Is CRM later but called synchronously at order commit? | Pass — CR5 forbids any CRM interaction in an order flow, C166 asserts commit without it, A123 makes it statically checkable, and CR4 blocks the "route it elsewhere" escape. |
| 5 | Is Chatwoot later but imported by an account flow? | Pass — CR2, CR5, A123, C166; OC3/A124 additionally cover the header/footer entry point, which is the realistic leak path. |
| 6 | Is Trade-In later but required by `place_order`? | Pass — CK1 makes contract completeness without it a rule, A121 checks the signature and step list, C165 exercises placement. Item 5 §4 left this open on purpose; §14 answers it rather than leaving the ambiguity to code. |
| 7 | Are Digital Products later while checkout requires digital fulfilment? | Pass — DL5, DL6. The enum-value-is-not-a-feature rule (DL6) is the load-bearing one, because master `# 16.1`'s `SKU` types and `# 11.4`'s step-3 wording are exactly where this contradiction would otherwise enter. A119/C169 check both directions. |
| 8 | Is complex CMS later while static pages depend on its model? | Pass — CT2 keeps identity/block-JSON/CSP in MVP precisely so static pages need nothing editorial; CT3 states the independence, A122/C171 check it, CT4 handles the enum case. CT1 also prevents the tempting wrong fix of splitting the package. |
| 9 | Is OpenSearch absent while a search path assumes it? | Pass — IG3, A127, C164. Master `# 9.3`'s `search.index.batch` was the one real risk; §16's erp_sync row resolves it as **C**, citing the master's own "only if OpenSearch is enabled" qualifier — the event is not produced at all, rather than produced and ignored. |
| 10 | Is the read replica absent while builder correctness reads it? | Pass — and the guarantee does not rest on the gate staying closed: item 12 CB10–CB14 forbid the builder from finalizing a candidate field from a lagging copy whatever item 15 later decides platform-wide, so opening the gate cannot silently make case 11 wrong (V142). |
| 11 | Is SMS later while a required OTP has no alternate MVP channel? | Pass — NT4 is the deliberate resolution of master `# 11.3`'s "signed link/OTP": the two are alternatives and the signed-link branch runs on the MVP email channel. NT5, NT6 close Track & Trace and authentication; V138/A120/C174 check it. |
| 12 | Is `ext.crm` provisioned despite CRM being later? | Pass — §15 provisions it `NO`, CR3 keeps the definition frozen and undeleted, FP1 states the general rule, CR4 blocks re-routing, A126/V144 check it. This is the specific question item 9 FD9a asked item 14, answered explicitly. |
| 13 | Is any later module represented by a fake or no-op adapter? | Pass — §19 rejects twelve shapes by name, A125 checks for them, and NF9 names the subtlest (a service that changes behaviour on package presence, which hides the dependency from the import graph). |
| 14 | Is a mechanism wrongly deferred because its consumer is later? | Pass — FD1 with four worked examples, and §5.1 classifies all fifteen mechanisms FOUNDATION. FD2 guards the reverse error, which §15 and DL6 each depend on. |
| 15 | Is any invariant weakened to make the cut work? | Pass — CV7 states the rule, V130 checks it, and each cut section restates the invariants that survive it: AC2 for accounts/reviews, CT5 for consent, DL8 for map credentials, PM7 for cash/IBAN, DL4 for free-shipping comparison. |
| 16 | Does the cut invent a boundary or an owner? | Pass — BO1–BO4 decline the one real temptation (`application/backoffice`), and NL4 declines the second (newsletter ownership), which classifying newsletter LATER removes the need for entirely. §1.3 records both as the reason no ADR is needed. |
| 17 | Is item 13 reopened or contradicted? | Pass — AY1–AY8 state only the consequence item 13 EN6 explicitly routed here. AY5 is the one that needed care: reviews shipping at launch does **not** admit rating into the formula, and C176 asserts it. |
| 18 | Is item 15's territory consumed? | Pass — §22 classifies gates and decides nothing about them; IG2, IG4, V143 and §25 all state the limit, and item 15 stays `IN PROGRESS`. |
| 19 | Are "not shipped" and "runtime outage" conflated anywhere? | Pass — §20 separates them into cases 1–15 and 16–20, and DG1 states the operational difference: the first group has no alert, no retry and no runbook; the second is served by mechanisms items 9, 10 and 12 already froze. |
| 20 | Does anything here require Phase 1 to create empty packages? | Pass — PX1 says no, PX2 makes the analytics case explicit, and NF1/V131 check it. §17's "strict subgraph" property is what makes that safe: adding a module later adds nodes, and rewrites nothing. |
| 21 | Does any capability carry two launch answers? | Pass — CV1 requires exactly one class per row. Newsletter was the one row that briefly held both a launch classification and an open "whether it ships at all" deferral, which an artifact whose purpose is to *freeze* the cut cannot carry; it is resolved to a single answer, **LATER** (NL1, NL2), and the deferrals table now defers the capability rather than the decision about it. |
