# Phase 0 — Item 12: storefront projection convergence — the guard token and the guarded write

- **Status:** DONE / FROZEN
- **Date:** 2026-09-06
- **Phase:** 0 — Architecture Freeze
- **ADR:** [ADR-0014](../../adr/0014-storefront-projection-convergence.md) — required, accepted
- **Related:** [ADR-0003](../../adr/0003-catalog-boundary-vs-storefront-projection.md),
  [ADR-0004](../../adr/0004-four-layer-modular-monolith.md),
  [ADR-0005](../../adr/0005-dependency-and-integration-wiring.md),
  [ADR-0007](../../adr/0007-place-order-atomic-idempotent-boundary.md),
  [ADR-0008](../../adr/0008-storefront-listing-projection.md),
  [ADR-0009](../../adr/0009-event-contract-versioning.md),
  [ADR-0010](../../adr/0010-async-failure-domain-isolation.md),
  [ADR-0011](../../adr/0011-async-trace-causality-envelope.md),
  [ADR-0013](../../adr/0013-event-id-distinct-identity-type.md),
  [item 6](06-storefront-listing-projection.md) §14–§18 (UP1–UP9, RB1–RB8, PU1–PU10, LC1–LC9),
  [item 7](07-storefront-dto-contract.md) DC9, LR8,
  [item 8](08-event-registry-versioning.md) §24 OR1–OR8, SR5, SR6, SV9,
  [item 9](09-queue-failure-domain-dlq.md) §9 PJ1–PJ7, §28 RA1–RA6,
  [item 10](10-async-trace-propagation.md) §9 (the nine-way distinctness table),
  [item 11](11-money-public-id.md) TS4, MI7,
  master `# 5` principle 36, `# 7.6`, `# 20.2`, `# 20.6`, `# 22.1`, `# 22.2`, `# 24`, `# 25` Phase 4,
  `# 26`

---

## 1. Purpose

Item 6 froze the **requirement** — a stale writer never regresses a serving row (PU4), and two
independent sources changing one product never erase each other (PU5) — and deferred the
**mechanism** to item 12 in five named pieces (§16.2): the version column's type, name and
cardinality; the generation algorithm and its monotonicity argument; the per-source mapping; the SQL
guard; and how PU5's per-fact convergence is expressed in that guard.

This artifact decides all five.

### 1.1 What this item freezes

- The **convergence model**: an asynchronous trigger is a *dirty-identity signal*, never an
  authoritative row snapshot; the writer rebuilds a whole candidate from current authoritative state
  and commits it under an optimistic **compare-and-set** on an application-owned per-row token.
- The **token**: name `projection_revision`, type, cardinality, ownership, generation, comparison
  rule, and the **generation-scoped** non-reuse rule with its fenced-reset counterpart — the two
  halves that let ordinary writers be ABA-safe while the projection stays fully disposable (§8).
- The **write protocol**: observe → build → guarded write, with the ordering constraint
  (`observe` strictly precedes every source read's **visibility point**) that makes the whole thing
  correct (§9).
- The **authoritative-read contract** for the builder's source reads: no cache entry, no lagging
  replica and no snapshot opened before the observation may finalize a candidate field (§11.1).
- The **guard predicate** and the exact meaning of a guard miss (§10).
- **Whole-candidate rebuild** as the only admissible candidate shape, and the conditions under which
  a per-source partial merge could ever be introduced (§11).
- The **role of the event payload** and the requirements every future projection-driving contract
  must satisfy — without naming an `event_type` or fixing a payload (§12).
- **No-op suppression** and what "unchanged serving state" means (§13).
- **Multi-language coherence**: the guard unit is the product's full language row set (§14).
- **Batch, locking and contention shape**: the logical guard unit is the product while the physical
  write transaction is the bounded batch; deterministic key order, no global projection mutex, no
  source read inside the write transaction, and a technical batch abort as a retry coupling that
  establishes no cross-product freshness relationship (§15).
- **Lifecycle**: withdrawal is a forward content change, not a delete; reactivation works; the
  ordinary update path never destroys guard state, which closes the ABA hole (§16).
- **Rebuild interaction**: in-place rebuild uses the identical protocol; build-then-swap is admitted
  only behind an explicit catch-up/fence requirement (§17).
- **Reconciliation and operator repair**: no force-write path; a destructive repair is a fenced
  operation (§18).
- **Replay, retry, crash and bounded contention** behaviour (§19, §20).
- **Source identity → affected product set** resolution without cross-domain ORM access (§21).
- **Admission of a future source** (§22).
- The **separations** restated by reference: `schema_version`, `EventId`/UUIDv7, `occurred_at`,
  `updated_at`, Outbox row id, cache counters, checkout truth, public DTOs (§23).
- **Overflow, corruption and observability** requirements (§24, §25).
- The **pseudo-SQL** shape of the guarded write (§26), the **correctness proof** (§27), the
  **failure matrix** (§28) and the checks **A86–A100**, **C128–C147**, **V102–V118** that later
  phases must implement (§29).

### 1.2 What this item does **not** do

No Python package, module, Django model, migration, SQL migration file, Celery task, event class,
database trigger, dependency or production code is created. The pseudo-SQL in §26 is an architecture
artifact that fixes the *semantics* of the guard; it is not a migration and not a query to be
copied.

It also does not reopen a neighbouring item. It defines no `event_type`, payload schema or
`schema_version` rule (item 8); no queue, routing, retry number or terminal state (item 9); no trace
field (item 10); no `Money`, `PublicId` or `EventId` semantics (item 11); no analytics source
(item 13); and no MVP/later cut (item 14). It designs no projection schema, index, batch size, retry
count or Django model — those remain Phase 4 (§30).

### 1.3 Why ADR-0014 is required

Master `# 7.6` contains a concrete sketch — a `source_version bigint` column, a producer-supplied
value, and a guarded upsert whose predicate is
`WHERE EXCLUDED.source_version > product_listing_projection.source_version` — and master `# 20.6`
shows that value as a **payload field** of the producer's message
(`CatalogProjectBatch { product_ids, source_version }`). Item 6 §16.2 recorded that sketch as master
text rather than a decision, precisely because it was not obviously compatible with PU5 and RB1/RB2.

It is not compatible. §6 and §7 show, with the failing cases named, that:

1. **No legitimate total order exists** across catalog, pricing, inventory, promotions and reviews
   without a shared cross-domain counter, which R2/R8/PU10 and ADR-0003 §3 all forbid.
2. **A producer-side sequence does not order commits.** A value allocated before `COMMIT` (a
   sequence, a transaction id, a WAL position) can be issued in one order and committed in the
   other, so `10 < 11` may reject a fact that is now authoritative — the transaction-commit
   inversion.
3. **Whole-row last-writer-wins on a scalar loses PU5.** A candidate built from `(P2, I1)` bearing
   the higher version permanently erases a committed inventory change whose own trigger has already
   been consumed.
4. **A rebuild has no source version to write.** RB1/RB2 require full reconstruction from OLTP with
   no event history; a producer-supplied token exists only in past payloads, so a rebuild would have
   to either write a value the guard then rejects (rebuild cannot repair) or write an inflated value
   that swallows every subsequent legitimate update.

The mechanism therefore changes: the producer supplies no version, the token becomes application-
owned CAS state, the field is renamed to stop the semantic drift the old name invites, and the guard
predicate changes from `>` to `=`. Item 6 delegated the choice; ADR-0008 lists it as out of scope;
item 8 OR7 states item 12 owns it and neither designs nor constrains it. But the change refines a
concrete master sketch, retires a master field name, removes a field from master's illustrative
payload and introduces a cross-cutting invariant (observe-before-read), so it is recorded in
**[ADR-0014](../../adr/0014-storefront-projection-convergence.md)** rather than buried in an
artifact.

ADR-0014 changes **no** dependency-matrix cell, adds **no** import edge, extends **no** `core`
submodule allowlist, adds **no** registry column or consumer-declaration attribute, and edits **no**
accepted ADR. L1–L21 stand unedited.

### 1.4 Master mapping — what is preserved, refined, departed from

| Master | Statement | Status here |
|---|---|---|
| `# 5` principle 36 | "Projection updates are monotonic… an older event cannot overwrite newer state. Full rebuild remains a reconciliation mechanism, not the primary race protection." | **Preserved in full.** §27's safety proof is strictly stronger than the master's sentence, and RC1 keeps rebuild as reconciliation rather than as the race defence. |
| `# 7.6` | Guarded upsert on `(product_id, language)` protecting against out-of-order workers | **Preserved.** The unique key on the row identity is load-bearing (§10 GM6) and the write is still a single set-based guarded upsert per batch. |
| `# 7.6` | Column `source_version bigint`, producer-supplied, "built from a monotone revision/event sequence defined by the projection contract" | **Refined / renamed.** The column becomes `projection_revision bigint`, generated by `application/storefront` per serving row, never supplied by a producer (§8). ADR-0014. |
| `# 7.6` | `WHERE EXCLUDED.source_version > product_listing_projection.source_version` | **Departed from.** The predicate becomes an equality CAS against an earlier-observed value of the same row (§10). Ordered comparison of the token is forbidden outright (RV6). ADR-0014. |
| `# 7.6` | "Price and stock may change simultaneously and arrive in different batch events; an older worker may not overwrite a fresher projection" | **Preserved as the motivating case, and actually solved.** §27's independence proof is exactly this scenario; the master's own predicate does not solve it (§7 case B). |
| `# 20.2` | Batch/coalesced events with bounded payloads or a dirty-set/staging table; worker deduplicates ids, 500–1000 per iteration, set-based upsert | **Preserved in full.** This is the trigger model item 12 adopts (§12). |
| `# 20.6` | `CatalogProjectBatch { product_ids: tuple[int, ...]; source_version: int }` | **Partially departed from.** `product_ids` is exactly the frozen payload role. `source_version` as a producer-supplied freshness token is **not adopted** and is forbidden as a guard input (TR5). No published contract needs migration: the registry ships empty (item 8) and master's example is explicitly an illustration item 8 did not adopt. ADR-0014. |
| `# 22.1` | ERP row: "set-based update + no-op guard + event coalescing" | **Preserved.** No-op suppression is mandatory and is strengthened: a no-op writes nothing at all, not even the token (§13). |
| `# 24` "Projection race" | "Two rebuilds of one product with `source_version=N` and `N+1`; the final state is always `N+1` regardless of commit order" | **Preserved in intent, restated in the new vocabulary.** Two concurrent builds of one product converge to the state of the later authoritative *read*, never to a mix; the loser discards and rebuilds. C128/C143. |
| `# 25` Phase 4 | "`product_public_id + created_sort_key + source_version`", "guarded monotonic batch upsert" | **Preserved with the renamed field.** The Phase 4 checklist item is satisfied by `projection_revision`; the batch upsert stays guarded, set-based and monotonic. |
| `# 26` release gate | "Projection upsert is protected by `source_version` against out-of-order workers" | **Preserved with the renamed field.** The gate is read as: the projection write is guarded against out-of-order workers, and the token is `projection_revision`. |

---

## 2. Frozen principles inherited

Not re-decided here; every rule below is written to be consistent with them.

| # | Inherited rule | Source |
|---|---|---|
| R1 | `application/storefront` is the sole owner **and sole writer** of `ProductListingProjection`; no domain, interface, task, integration or admin action writes a serving row. | item 6 O1, O2, UP1, UP2, ADR-0008 |
| R2 | The projection is a **derived serving read model**: never checkout truth, never the basis of a security decision, and its every field is a copy or computation over another module's authoritative state. | item 6 §5, T3, T6, T9, SEC3 |
| R3 | The builder reads authoritative state only through `<domain>.public` **batch** selectors returning frozen DTOs; it issues no query against another module's tables and imports no other module's models. | item 6 O4, BP3, R5 |
| R4 | The projection is **fully rebuildable from OLTP**; events are acceleration, not the historical source; an archived Outbox partition can never make it unreconstructible. | item 6 RB1, RB2 |
| R5 | The updater is safe under duplicate delivery, retry and reordering, and a stale update never regresses newer projected state; convergence is per serving row and per contributing fact. | item 6 PU1–PU5 |
| R6 | Ordering safety is a property of the **write** path. A selector never compensates for staleness, never re-reads OLTP and never repairs. | item 6 PU6, NF1–NF7 |
| R7 | No storefront read-model state — a version column included — is added to any domain table. | item 6 PU10, R8, ADR-0003 §3 |
| R8 | Item 5's checkout freshness/revalidation guard and this mechanism are different mechanisms for different problems and are never conflated. | item 6 PU9 |
| R9 | Bulk work is set-based, batched, coalesced and no-op-suppressed; the per-entity loop is forbidden by name; write amplification is a design constraint. | item 6 BP1–BP7 |
| R10 | Global message ordering is never assumed; broker order, `occurred_at` and Outbox row ids are not ordering keys; `schema_version` is not a revision. | item 8 OR1–OR6, SV9 |
| R11 | Where ordering matters for one fact stream, the contract or the **owning state** must let the consumer recognise and reject stale state. | item 8 OR5, SR6 |
| R12 | `core.projection.incremental` and `core.projection.rebuild` are two failure domains but **one writer path**, one code path and one consistency model. | item 9 PJ5 |
| R13 | Replay is explicit, authorised, audited, identity-preserving, scoped to one consumer delivery, and re-enters normal validation and idempotency with **no force-apply path**. | item 9 RA1–RA6 |
| R14 | A `PublicId`/`EventId` is never a version, never an ordering key, never a sequence number. | item 11 TS4, MI7 |
| R15 | No projection bookkeeping (`source_version`, `updated_at`-as-version, freshness state) appears in any public storefront DTO. | item 7 DC9, LR8 |
| R16 | A domain writes its business change and its Outbox row in **one** ACID transaction and never schedules transport itself. | item 4 §9.1, item 6 §14, master `# 20.2` |

---

## 3. Vocabulary

| Term | Meaning in this artifact |
|---|---|
| **Serving row** | One `ProductListingProjection` row: one `Product × Language` (item 6 §6.1). |
| **Serving state** | The stored fields of a serving row that participate in filtering, sorting, pagination, counting, search or rendering — everything except the guard token, `updated_at` and diagnostic metadata (§13). |
| **Trigger** | A durable asynchronous message, or a dirty-set entry, that says *this product may be dirty*. Never a row snapshot. |
| **Candidate** | The full serving state for one product's rows, computed by the canonical builder from current authoritative state. |
| **Guard token** | `projection_revision`: the per-serving-row value observed before building and re-verified at write time (§8). |
| **Observation** | The read of the guard tokens for a product's rows, taken **before** any source read of that unit of work (§9). |
| **Guarded write** | The single local transaction that re-verifies observations and applies surviving candidates (§10). |
| **Guard miss** | The observation no longer holds at write time: another projection writer committed first. Not a business failure, not a quarantine (§10). |
| **Unit of work** | One bounded batch of products processed by one worker through one observe/build/write cycle. |
| **Convergence** | The state after all pending triggers for a source object have been applied (item 6 §3). |
| **Fence** | An operational barrier that makes concurrent incremental writers either drain into, or be excluded from, a structural operation, and that invalidates observations taken before it (§17, §18). |
| **Projection generation** | The lifetime of the serving structure between fences. Ordinary incremental, targeted-rebuild and reconciliation work all happen *within* one generation; a fenced destructive rebuild, table replacement, build-then-swap or fenced tombstone collection ends one generation and begins the next. The token's non-reuse rule is scoped to a generation (RV8, RV8a); it is a property of the protocol, not a stored column. |
| **Authoritative read** | A source read whose visibility point is established **after** this unit of work's observation and which reflects committed owner state — not a cache entry, not a lagging replica copy, not a snapshot opened earlier (CB10–CB13). |

---

## 4. The problem, stated exactly

A serving row is `Product × Language`. Its content derives from **independent** authoritative
sources — catalog, pricing, inventory, promotions, reviews (master `# 7.6`, item 6 §8) — which share
no business transaction and no natural total order.

| # | Rule |
|---|---|
| PR1 | `pricing` revision `P2` and `inventory` revision `I7` are facts of two different owners. Neither `P2 > I7` nor `P2 < I7` means anything. Two independent counters do not become comparable by both being integers. |
| PR2 | The dangerous outcome is not staleness — item 6 CM1–CM5 already accept bounded lag. It is **permanent divergence**: a committed source change whose effect is erased by a writer that started earlier, after that change's trigger has already been consumed. Nothing then re-drives it except reconciliation. |
| PR3 | Two failure shapes must both be excluded: **regression** (a newer serving state replaced by an older one, PU4) and **partial erasure** (`P2 + I1` or `P1 + I2` surviving as the converged state, PU5). |
| PR4 | The mechanism must hold with the sources' commit order unknown, the delivery order unknown, deliveries duplicated, workers crashing at any instant, and the entire event history deleted. |
| PR5 | It must hold **without** a domain learning that it is projected (item 6 O2), without a cross-domain counter (R2 of item 6), and without a projection-motivated column on a domain table (R7). |

---

## 5. Ordering sources rejected by name

None of the following is a valid freshness order for a serving row. Most are already forbidden by a
frozen artifact; the rest are rejected here with the reason.

| Candidate ordering source | Verdict | Reason |
|---|---|---|
| `schema_version` / `event_version` | **Forbidden** | Item 8 OR6, SV9, A47. It versions a payload shape, not a fact. |
| `EventId` / `causation_event_id` | **Forbidden** | Item 11 MI7, ADR-0013. Identity, not order. |
| UUIDv7 timestamp bits | **Forbidden** | Item 11 TS4 and §26: the embedded timestamp is never business time, ordering, replay chronology or any version. Index locality may be benefited from, never depended on. |
| `occurred_at` | **Forbidden** | Item 8 TS4, OR3. Business fact time; clocks skew, values tie, and commit order is unrelated. |
| Wall-clock `updated_at` (LWW) | **Forbidden** | §23 UD1–UD4. It is an effect of a write, not a claim about the state written; two writers can produce equal or inverted values. |
| Broker delivery order / queue order | **Forbidden** | Item 8 OR2; item 9's whole design assumes reordering. |
| Worker start or finish order | **Forbidden** | Unobservable, unrecorded, and unrelated to what the worker read. |
| Retry attempt number | **Forbidden** | Item 9: attempt metadata is transport state confined to the delivery row. |
| Outbox row id / Inbox row id | **Forbidden** | Item 8 OR3: it orders insertion into one table, not the facts of one entity across producers, and is not preserved across replay. |
| `max()` over independent per-domain counters | **Rejected** | PR1. A maximum over incomparable values is arithmetic, not semantics. |
| Random UUID / content hash as an order | **Rejected** | No order exists. A hash is admitted only as a no-op *detection* accelerator with an exact fallback (§13 NO6). |
| `trace_id` / `request_id` / causation identifiers | **Forbidden** | Item 10's correctness firewall: trace metadata decides nothing. |
| Redis `INCR` or any cache counter | **Rejected** | Item 6 R12, CA2: no cache is a correctness source; a flush would reset the ordering universe. |
| PostgreSQL sequence value allocated before `COMMIT` | **Rejected** | §7 case A: allocation order is not commit order. `nextval` is monotone in *allocation*, and the transaction that took the smaller value may commit last. |
| Transaction id (`xid`) | **Rejected** | Same inversion, plus wraparound semantics and no cross-database meaning. Ordering `xid`s orders transaction *starts*. |
| WAL position (LSN) / commit timestamp (`pg_xact_commit_timestamp`) | **Rejected** | These genuinely order *commits*, but they order **database activity**, not the state being projected: a candidate is built from many reads across many sources at many instants, so no single LSN describes it. Adopting one would also bind the architecture to a PostgreSQL-internal, per-cluster, non-restorable value and would still not solve PR3's partial-erasure shape. Master `# 7.6` asks for a projection-contract mechanism, not a storage-engine one. |
| Row system column `xmin` as a CAS token | **Rejected** | Technically a valid CAS token, but it changes under `VACUUM FREEZE` without any logical write (spurious guard misses), is invisible to the ORM contract, is undiagnosable in a runbook, and hides the invariant it enforces. §8's explicit token costs one `bigint` and makes the rule reviewable. |

| # | Rule |
|---|---|
| OS1 | Every entry above is forbidden **as a guard input**. Some of them (`occurred_at`, `updated_at`, `EventId`, trace fields) remain perfectly legitimate as diagnostics, metrics and log fields. |
| OS2 | The prohibition is on the *use*, not on the *name*: renaming `occurred_at` to `source_time` and comparing it is the same defect (A89, V111). |
| OS3 | A future proposal to use any of them must carry a transactional-semantics proof and a new ADR. "It looks monotonic" is not one. |

---

## 6. Candidate models, evaluated

### 6.1 Candidate A — one scalar producer-supplied source/event sequence

The master sketch: every projection-driving message carries `source_version`, and the upsert applies
only when the incoming value exceeds the stored one.

| Question | Answer |
|---|---|
| Does a legally-owned total sequence exist across catalog, pricing, inventory, promotions and reviews? | **No.** It would need either a shared counter (a cross-domain business object with no owner — item 6 R2/R3, ADR-0005 §2's rejection of an ownerless shared package), or a projection-motivated column in each domain (R7, ADR-0003 §3), or a producer transaction writing `application/storefront` state (item 6 O1, UP2, R7 of item 6). All three are already forbidden. |
| Can the sequence be allocated centrally, e.g. one PostgreSQL sequence all producers call? | **No.** It would be a cross-domain shared counter existing only because the storefront needs it (R7, PU10), *and* it would fail the commit-inversion test below regardless. |
| Does it survive the transaction-commit inversion? | **No.** See §7 case A. |
| Does it satisfy PU5? | **No.** See §7 case B. |
| Can a rebuild produce a comparable value? | **No.** See §7 case C. This alone is fatal against R4. |

**Rejected.** Not for complexity and not for taste: it has no admissible generator, and even given
one it loses committed facts.

### 6.2 Candidate B — a per-source revision vector on the serving row

Conceptually `catalog_revision`, `pricing_revision`, `inventory_revision`, `promotions_revision`,
`reviews_revision`, applied component-wise.

| Question | Answer |
|---|---|
| Who generates each component? | Only the owning domain legitimately could. Catalog might plausibly own a per-product aggregate revision for its own reasons; **pricing, inventory, promotions and reviews do not have a per-Product revision at all** — their truth is per SKU, per price list, per store, per campaign, per review. Manufacturing one per Product for each of them is exactly the projection-motivated domain column R7 forbids. |
| How does a full rebuild discover the current components? | Every owner would have to expose its current revision through `<domain>.public`, i.e. four or five public contracts would gain a symbol whose only consumer and only reason to exist is the read model. That is projection leakage through the contract rather than through the schema, and it makes item 6 O2 ("a domain does not know it is projected") false in substance. |
| How are incomparable candidates resolved? | Component-wise maximum, which forces a **field-to-source decomposition** of the row so that each field takes its value from the candidate whose corresponding component is newer. |
| What about cross-source derived fields? | This is where it breaks. `discount_percent_bps` derives from pricing **and** promotions; display availability from inventory **and** catalog sellability; the visibility predicate from catalog, inventory and pricing eligibility together (item 6 LC3–LC5); badge inputs and sort keys from several. A component-wise merge has no defined answer for a field whose sources disagree about which is newer, and every future field re-opens the question. |
| Adding a future source? | A new component, a schema migration, a new public symbol in the new owner, and a re-proof of every derived field's merge rule (§22). |
| Cost? | Five extra columns per row, plus write amplification: any component advance rewrites the row even when serving state is unchanged, fighting R9/BP4/BP5. |

**Rejected.** A vector clock is the right tool when independent replicas hold independent partial
state. Here one writer holds the whole row and can simply re-read the truth. The vector would buy a
merge rule the architecture does not own, at the cost of making five domains aware of the read model.

### 6.3 Candidate C — current-state rebuild under an application-owned CAS token — **selected**

The trigger is a dirty-identity signal. The writer observes the row's token, rebuilds the whole
candidate from current authoritative state through batch `<domain>.public` selectors, and commits
only if the token is unchanged. A lost race discards the candidate and rebuilds.

| Question | Answer |
|---|---|
| Where does the token come from? | `application/storefront`, per serving row. No producer supplies it; no domain knows it exists (R1, R7, item 6 O2). |
| Does it order the sources? | **No, and it does not claim to.** It orders *writes to one row*, which is the only ordering anyone actually needs (§27). |
| Commit inversion? | Not applicable: nothing is allocated before a commit and compared afterwards. A late-committing source transaction is simply a source change like any other, discovered by the next read. |
| PU5? | Satisfied structurally: every committed candidate is a total rebuild from **all** sources, and §27's Lemma 2 makes each writer's view of every source strictly newer than its predecessor's. `P2 + I1` cannot be the converged state. |
| Rebuildability (R4)? | Native: the token is application-owned, so a rebuild from an empty table simply inserts at the initial value. No event history, no retained payload, no producer version is consulted. |
| Adding a future source? | One more input to the canonical builder and one more trigger. No token change, no migration, no re-proof (§22). |
| Does an old event replayed later carry old prices back into the row? | No. It causes a rebuild from current truth (§19). |
| Cost? | One extra observation query per batch; wasted work when a race is lost; a whole-candidate build even when one field changed. All bounded, all batched, all off the request path (§15, §20). |

**Selected.** The name follows the semantics: the field is `projection_revision`, not
`source_version`, because it is not a version of any source (§8, ADR-0014).

### 6.4 Candidate D — variants considered and not selected

| Variant | Verdict |
|---|---|
| **Pessimistic**: lock the product's rows, then read sources, then write, releasing at commit | Correct but unacceptable in shape: row locks would be held across many cross-module `<domain>.public` calls for a 500–1000-product batch, turning a read-model refresh into a long lock-holding transaction. The selected model uses the same lock only for the short verify-and-write window with **no** source read inside it (§15 BL5). |
| **Advisory lock per product for the whole build** | Same objection, plus a lock namespace that must be coordinated with nothing else in the system, plus an orphan-lock failure mode on worker death. |
| **`SERIALIZABLE` isolation over build + write** | Does not remove the need for a token (a serialization failure is a differently-spelled guard miss), and a batch of 500–1000 products under `SERIALIZABLE` will abort under exactly the load it is meant to survive. Admissible as a Phase 4 hardening choice, never as the correctness argument (§15 BL7). |
| **A single repeatable-read snapshot for all source reads** | Legitimate and, in this modular monolith, would make a candidate a true point-in-time snapshot. It is **not required** and correctness must not depend on it (§11 CB6): it must never be held across a long batch or any external I/O, and it does not by itself prevent regression — the token still does. |
| **Per-source partial merge under the same CAS** | Not unsafe *in principle* — the CAS still prevents regression — but it requires an exact, owned field-to-source decomposition including every derived field, which the architecture does not have, and it would end item 6 F2/RB4/C26's "one canonical builder, rebuild ≡ incremental" property. Forbidden unless a future ADR supplies the decomposition (§11 CB4). |

---

## 7. The three tests the master's sketch fails

Recorded explicitly, because rejecting master text requires showing the failure rather than
asserting it.

### 7.1 Case A — transaction-commit inversion

```text
TX-A (pricing)      obtains source_version = 10        … pauses before COMMIT
TX-B (pricing)      obtains source_version = 11        … COMMITs
                    projection applies candidate v11
TX-A                COMMITs later                      … its fact is now authoritative
                    projection receives candidate v10  → rejected: 10 < 11
```

TX-A's committed price change is now permanently absent from the serving row, its trigger consumed,
with no remaining driver except reconciliation. The guard rejected a **fact**, not a stale write.

Under the selected model the question does not arise: no value is allocated before a commit, and the
build triggered by TX-A's Outbox row (written in TX-A, therefore visible only after TX-A commits,
R16) reads the state TX-A committed.

### 7.2 Case B — independent-source lost update

```text
serving state:  price = P1,  stock = I1

pricing    commits P2  → trigger T_p
inventory  commits I2  → trigger T_i

W_p  reads sources → (P2, I1)   [I2 not yet committed when W_p read inventory]   version 11
W_i  reads sources → (P1, I2)   [read before P2 committed]                       version 10

W_i commits  → row = (P1, I2), stored version 10
W_p commits  → 11 > 10 → row = (P2, I1)
```

Converged state is `P2 + I1`. `I2` is lost; `T_i` is HANDLED; nothing re-drives it. This is exactly
the case master `# 7.6` names as the motivation ("price and stock may change simultaneously and
arrive in different batch events") and exactly the case its predicate does not solve — because the
version travels with the *message*, while the staleness lives in the *read*.

Under the selected model, `W_p` and `W_i` observed the same token; one of them wins, the other
misses, discards and rebuilds — and its rebuild reads both `P2` and `I2` (§27, Independence).

### 7.3 Case C — the rebuild has no version

RB1/RB2 require a full rebuild from OLTP with no event history. A rebuild builder has no message and
therefore no `source_version`. Its only options under the master predicate are:

- write a low value → the guard rejects the rebuild, so **the repair mechanism cannot repair**; or
- write `stored + 1` → the rebuild's own writes are then unguarded against concurrent incremental
  updates (§17's race), so the repair mechanism becomes the regression mechanism; or
- write a very large value → every subsequent legitimate incremental update is silently swallowed
  until the sources catch up to a number that has no meaning.

There is no fourth option. A producer-supplied token and a rebuildable projection are incompatible.

---

## 8. The token: `projection_revision`

| # | Rule |
|---|---|
| RV1 | **Name (frozen): `projection_revision`.** The name `source_version` is retired for this purpose. It is not a version of any source, and keeping the master's name would keep inviting the master's `>` predicate. Phase 4 uses this name for the physical column; a deviation requires a new ADR. |
| RV2 | **Type (frozen): a 64-bit signed integer (`bigint`), `NOT NULL`.** Not a UUID, not a timestamp, not a hash, not a `numeric`, not nullable, and never a `Money`, `PublicId` or `EventId` (item 11 TS4, MI7). Phase 4 owns the column definition, not the type choice. |
| RV3 | **Cardinality (frozen): exactly one value per serving row** (`Product × Language`). Not one global counter, not one per product, not one per source, not one per language, not one per batch. |
| RV4 | **Generation (frozen): `application/storefront`, inside the guarded write transaction, as a function of the row's own current value** — initial value `1` on insert, and strictly increasing by at least one on each committed change of serving state. No producer, domain, task, interface, integration, admin action or cache supplies or advances it (R1, R7). |
| RV5 | **A no-op does not advance it.** The token advances **iff** the row's serving state actually changes (§13). It is a write counter, not a trigger counter. |
| RV6 | **Comparison rule (frozen): equality only, within one row identity.** The only legal use in a predicate is `stored.projection_revision = <value observed earlier from that same row>`. `<`, `>`, `<=`, `>=`, `MAX`, `GREATEST`, `ORDER BY` and arithmetic comparison of the token are forbidden in every predicate and every assignment other than the `+ 1` advance (A91, V102). |
| RV7 | Values of **different rows** are not comparable and carry no relative meaning. Row X at `7` and row Y at `912` says nothing about their relative freshness. |
| RV8 | **Non-reuse within a projection generation:** for a given row identity, a value once committed is never reused and the sequence never decreases, for as long as any observation taken against the current generation may still execute. This covers every ordinary operation — withdrawal, tombstoning, targeted rebuild, in-place full rebuild, reconciliation — and it is what makes ordinary concurrent writers ABA-safe (§16 LF6). |
| RV8a | **A fenced destructive structural operation ends the generation, and the next generation may start its tokens over.** A destructive full rebuild, a physical tombstone collection, a table replacement or a build-then-swap **may reinitialize per-row tokens** — rows may begin again at `1` — **only if** the fence guarantees that every observation taken against the old structure is drained or invalidated, so that no pre-fence observation is capable of executing a compare-and-set against a post-fence row. The ABA protection is therefore: <br>• **either** preserve non-reuse (RV8, the ordinary path), <br>• **or** invalidate every prior observation before reuse becomes possible (RV8a, the fenced path). <br>It is explicitly **not** "retain historical per-row token maxima". |
| RV8b | Consequently **no durable global epoch column, no token-history table, no retained maxima and no backup, replication or retention obligation** is introduced for the token, and no source domain gains any version state (R7). A generation boundary is an operational fact established by the fence (§17 RB6, §18 RC5, §16 LF6), not a value stored in a row. |
| RV9 | The token is **internal serving metadata**. It never appears in a public DTO, an API payload, HTML, a URL, a cursor, a cache key used as correctness, a checkout input, an authorization decision or an event payload (item 7 DC9, LR8; §23). It may appear in internal logs, metrics and diagnostics. |
| RV10 | The token is **not** a `source_version`, a schema version, a business revision, an aggregate version, an optimistic lock on any domain object, a freshness timestamp, an ordering key across rows, or an idempotency key. It is a per-row compare-and-set token and nothing else. |
| RV11 | **Overflow** (§24): `bigint` with a `+1`-per-content-change generator has no reachable wrap under any plausible catalog and update rate. Wraparound semantics are forbidden; approaching the type's bound is a technical fault requiring intervention, never a silent reset. |
| RV12 | The token is **disposable with the projection**. Losing it costs nothing that a rebuild does not restore (item 6 T8, RB1); it therefore gains no backup, replication or retention obligation of its own. This is consistent with RV8 precisely because non-reuse is scoped to a generation: total loss of the projection is the limiting case of a generation ending, and RV8a — not retained token history — is what keeps the next generation safe (§27.4). |

---

## 9. The write protocol

```text
unit of work = one bounded batch of products (master # 20.2: 500–1000)

  1. OBSERVE      read the guard token of every serving row of every product in the batch,
                  and record which (product, language) keys are absent
                        ── strictly before step 2 ──
  2. BUILD        read current authoritative state through batch <domain>.public selectors;
                  compute the full candidate serving state for every product × language
  3. GUARDED      one local transaction:
     WRITE          re-verify every observation under a row lock in deterministic key order;
                    apply the candidates of the products whose observations still hold;
                    advance the token only for rows whose serving state actually changed
  4. MISS         products whose observation no longer holds are discarded and re-driven
                  (bounded local retry, then re-coalesced through the projection workflow)
```

| # | Rule |
|---|---|
| OB1 | **The observation strictly precedes every source read of that unit of work** — and "precedes" means the source read's **visibility point** is established after the observation, not merely that the call is issued later (CB10, CB12). This single ordering constraint is what makes the mechanism correct; §27's Lemma 2 depends on it and nothing else does the work. A token read *after* the source reads, or a source view whose visibility point predates the observation (a cache entry, a lagging replica, a snapshot opened too early), would let a writer commit a candidate older than the state that produced the token it observed. |
| OB2 | The observation records, per `(product_id, language)` key: the current `projection_revision`, or **absent**. Absence is a first-class observed value, not a missing entry (§10 GM5). |
| OB3 | The observation is set-based: one statement per batch, not one per product. It is not a lock, holds nothing, and is taken outside any write transaction. |
| OB4 | A unit of work may not carry an observation forward across a retry. **A retry re-observes and rebuilds** (§20 RT3). |
| OB5 | A unit of work may not reuse another unit's observation, and two units may not share a build. |
| OB6 | The candidate for a product is built from the **current** authoritative state at build time, never from a stored previous candidate, never from the serving row itself, and never from the trigger payload (§11, §12). |
| OB7 | Nothing durable is written before step 3. An in-memory candidate is disposable at every instant; a crash between steps 1 and 3 changes no projection state (§19 CR1). |
| OB8 | The guarded write is a **local** transaction owned by `application/storefront`. It contains no `<domain>.public` call, no external I/O and no provider interaction (§15 BL5), and it is never nested inside, or extended into, a domain's business transaction (item 6 CM2, UP7). |

---

## 10. Guard semantics

| # | Rule |
|---|---|
| GM1 | The guard predicate is an **equality compare-and-set**: a row is written only if its stored `projection_revision` still equals the value observed for that row in step 1 (or the row is still absent, if that is what was observed). |
| GM2 | Verification is **per product, all-or-nothing across that product's language rows** (§14). If any row of a product fails verification, none of that product's rows is written in this unit of work. |
| GM3 | **Guard verification of one product never invalidates another product in the same batch**: within the same bounded write transaction, the products whose observations still hold are written and the guard-missed ones are excluded and re-driven (§15 BL3, ML3). The shared transaction is a physical container, not a shared guard: a miss on product `3` is not a miss on products `1`, `2`, `4` or `5`. (A *technical* abort of that transaction is a different event and is covered by BL9.) |
| GM4 | A **guard miss means exactly one thing**: another projection writer committed to that row after this unit observed it, so this candidate may be based on older reads. It is **not** a business failure, not a contract violation, not an item 8 quarantine (which is reserved for unknown type / unsupported version / invalid payload), not a checkout conflict and not a provider failure. |
| GM5 | The **insert race** is the same rule with `absent` as the observed value: the write attempts an insert guarded by the serving row's unique key on `(product identity, language)`; a concurrent insert that got there first is observed as a conflict, which **is** a guard miss. The loser discards and rebuilds. No integrity error surfaces as a business error, and neither writer is special (§26). |
| GM6 | The uniqueness of the serving row identity is **load-bearing** for GM5, not decorative. Phase 4 must provide it as a database constraint; without it two rows for one `Product × Language` would each carry an independent token and the guard would protect nothing. |
| GM7 | On a guard miss the candidate is **discarded whole**. It is never partially applied, never merged field-by-field into the winner's row, and never retried without rebuilding (§11 CB5, §20 RT3). |
| GM8 | There is **no force-write path**. No parameter, flag, environment variable, management command, admin action, reconciler or replay tool may write a serving row without a satisfied guard (A94, V105). A destructive repair is a fenced operational procedure (§18), not a hidden argument. |
| GM9 | A guard miss is **not** an error to a caller: it is normal contention, it is counted as a metric, and it resolves through retry or re-coalescing (§20). A sustained spike is an operational signal, not automatically a defect. |
| GM10 | The guarded write never blocks, delays or fails a domain's business transaction; a failure of the whole mechanism degrades storefront freshness only (item 6 UP7, T7). |

---

## 11. Candidate construction

| # | Rule |
|---|---|
| CB1 | The candidate is produced by the **one canonical builder** (item 6 §14, master `# 7.6`) and is the **complete** serving state for the product's rows — every field, in every language, exactly as a rebuild would compute it. |
| CB2 | Every input is read through `<domain>.public` **batch** selectors returning frozen DTOs (R3, BP3). No projection-motivated public symbol is required by this mechanism: the builder asks for facts, never for revisions (§6.2). |
| CB3 | Because the candidate is a total function of the read views, **rebuild ≡ incremental** by construction (item 6 F2, RB4, C26). The incremental path is not a second, cheaper builder with different behaviour. |
| CB4 | **A per-source partial merge is forbidden.** A writer may not update "only the price fields" or "only the stock fields" of an existing row. Introducing one requires a new ADR that supplies an exact, owned field-to-source decomposition covering every derived field (discount, availability, badges, visibility, sort keys, search fields) and re-proves §27 under it (V115). |
| CB5 | On a guard miss the candidate is discarded, not merged (GM7). Merging two whole-row candidates built from different source states is the failure mode CB4 exists to prevent. |
| CB6 | The builder is **not** guaranteed a cross-domain point-in-time snapshot, and correctness does not assume one: a candidate may reflect catalog at `t1`, pricing at `t2` and inventory at `t3`. §27 shows this is safe — each source's view advances across successive committed writers — and item 6 CM3/CM4 already accept the transient display incoherence it can produce. A Phase 4 decision to wrap a batch's source reads in one database snapshot is admissible as a **quality** improvement, must be bounded per batch, must never be held across external I/O, must satisfy CB12's ordering constraint, and may never be cited as the safety argument. |
| CB7 | A product with no storefront eligibility yields a **not-visible candidate**, never a delete instruction (§16 LF2). |
| CB8 | The builder performs no write to any domain, no domain command call, and no write-back of a projected value as truth (item 6 CT2, T5). |
| CB9 | Candidate construction is deterministic: the same authoritative state yields the same candidate, so two builders reading the same state produce byte-equal serving content and the second write is suppressed as a no-op (§13). |

### 11.1 The authoritative-read contract

Item 12's safety proof does not merely need "the later call happens later". It needs the later
call's **visibility point** to be later. A `<domain>.public` selector is an architectural boundary
that says nothing, by itself, about where the bytes came from; without the rule below, a future
implementation could satisfy a builder read from a warm cache entry or an asynchronously lagging
replica, and §27's Lemma 2 would prove nothing.

| # | Rule |
|---|---|
| CB10 | **Every source read used to build a candidate is a correctness read of authoritative committed owner state**, whose visibility point is established **after** this unit of work's observation: `visibility_point(read(W, S)) > obs(W)` for every source `S`. This is the projection builder's read contract, and it is the premise Lemma 2 uses. |
| CB11 | Consequently, **no candidate field is finalized from a bounded-stale copy**: not a Redis or fragment-cache entry, not an asynchronously lagging read replica, not a materialised copy whose freshness is merely "good enough". A cache may be used as a **hint or accelerator** — to skip work, to prefilter, to short-circuit a build that is provably unnecessary — only where the authoritative state is verified before the candidate is materialised. "Fresh enough for display" is not "authoritative"; the projection *serves* bounded-stale data, it may not *be built from* it. |
| CB12 | If Phase 4 wraps the source reads of a unit of work in one database transaction or snapshot (CB6), that snapshot's **visibility point is established after the observation, never before it**. A snapshot opened before the observation would silently invalidate Lemma 2 while looking, in code, exactly like one opened after it — which is why the ordering is frozen here rather than left to implementation taste. A snapshot established after the observation is admissible and improves candidate coherence. |
| CB13 | This is narrowly a constraint on **the projection builder's source-read path**. It is *not* the platform-wide read-replica decision, which remains item 15's; the platform default (reads consistent on Primary, replica by explicit opt-in) already satisfies it, and item 12 neither introduces a replica nor forbids one elsewhere. It requires no domain to know it is projected (item 6 O2): the builder calls ordinary legal `<domain>.public` batch contracts, and **how** an owning module exposes an authoritative-read capability — a routing hint, a selector variant, a module-level policy, or simply the platform default — is each domain's own phase and Phase 4, bounded by CB10. No Django database alias and no selector signature is chosen in Phase 0. |
| CB14 | The contract concerns **state chronology, not value trajectory**. A source may legitimately move `100 → 120 → 100`; the final `100` is newer authoritative state, and writing it is convergence, not regression. Nothing in this mechanism compares business values to decide freshness — only the token, and only for equality (RV6). |

---

## 12. The role of a trigger

Item 12 names no `event_type` and fixes no payload — those are item 8's and each owning module's
phase. It freezes the **role** and the **requirements** any such contract must satisfy.

| # | Rule |
|---|---|
| TR1 | **A trigger is a bounded dirty-identity signal.** Its role is to say *which products may need rebuilding*, nothing more. Master `# 20.2`'s `{ product_ids: [...] }` batch shape and the dirty-set/staging-table alternative are both exactly this. |
| TR2 | **A trigger is never treated as a complete row snapshot.** No serving field is taken from a payload; the builder re-reads authoritative state (item 6 UP8, CB1). A payload may not become the source of a copied value "to save a query" (A96, V109). |
| TR3 | **A trigger carries no freshness token, and none would be honoured.** Producer-supplied `source_version` is not required and is forbidden as a guard input; if an owner's payload happens to carry a revision meaningful to that owner for its own reasons, the projection writer must not compare it (TR5). |
| TR4 | A trigger **may** carry a bounded change-kind hint. Its only admissible uses are routing, coalescing and metrics. It may not select which sources are read (CB1), may not narrow the candidate (CB4) and may not decide staleness. |
| TR5 | The requirements every future projection-driving contract must satisfy: (a) its payload is sufficient to resolve the affected product set through `<domain>.public` batch selectors or `application/storefront`-owned state (§21); (b) the **content** of the resulting serving row does not depend on the payload; (c) no payload field is compared for freshness; (d) identifiers may be deduplicated and coalesced across triggers without loss; (e) it is emitted in the owning domain's business transaction (R16) so that its visibility implies the fact's commit — the property §27's liveness argument uses. |
| TR6 | Duplicate triggers, reordered triggers, coalesced triggers and a single trigger standing for thousands of changed rows are all normal (item 8 OR4, master `# 20.2`). |
| TR7 | The projection consumer's **business-effect idempotency** (item 8's per-consumer declaration) is satisfied *by construction*: the guarded write is idempotent, since a redelivery rebuilds and finds the row already equal (§13, §19). Item 12 declares the property; the registry entry recording it belongs to the owning module's phase. |
| TR8 | A trigger is never emitted by `application/storefront` to itself as an ordering device, and the projection writer emits no Outbox row for the purpose of sequencing its own work. |

---

## 13. No-op suppression and candidate equality

| # | Rule |
|---|---|
| NO1 | **If the serving state is unchanged, the serving row is not written.** No `UPDATE`, no token advance, no `updated_at` change (item 6 BP4, C35, master `# 22.1`). |
| NO2 | "Unchanged" is defined over the **serving state**: every stored field that participates in filtering, sorting, pagination, counting, search or rendering. It **excludes** `projection_revision`, `updated_at` and any diagnostic/processing metadata. Comparing those would make every comparison unequal and defeat the rule. |
| NO3 | A duplicate or irrelevant trigger therefore produces **zero row writes** and leaves the token untouched (RV5). The hot projection row is not rewritten to advance a counter. |
| NO4 | This is safe: a no-op writes nothing, so it cannot regress anything, and it cannot be mistaken for a guard miss because the two are distinguished under the write transaction's row lock (§26). |
| NO5 | Freshness is therefore **not** measured from `updated_at` — a converged row that stops changing is not stale. Lag is measured on the trigger pipeline (item 9's oldest-message age, item 6 CM10, master `# 23.2` *Listing Projection Lag*) and by reconciliation (§18, §25). |
| NO6 | A content hash or checksum is admissible **only** as a no-op *detection accelerator*, and only where a hash match is confirmed by an exact comparison before suppression, so a collision can never cause a stale row to be treated as converged. A hash is never an ordering mechanism and never a guard token (§5). |
| NO7 | The exact physical comparison technique — column-wise `IS DISTINCT FROM`, a generated comparison tuple, a hash-plus-exact-fallback — is **Phase 4**, bounded by NO1–NO6. |
| NO8 | Suppression is per **row**, not per product: in one product's write, a language row whose localized text changed is written while the other language rows, whose serving state is identical, are not — and the unwritten rows keep their own tokens (§14 ML4). |

---

## 14. Multi-language coherence

A product has one serving row per language. Some contributing facts are language-independent (price,
availability, rating, structural facet tokens, sort keys); others are localized (listing name, slug,
brand/category display facts, search text).

| # | Rule |
|---|---|
| ML1 | **The guard unit is the product's full language row set.** A unit of work observes, verifies and writes all of a product's rows together, in one transaction, all-or-nothing (GM2). |
| ML2 | Consequently a language-independent fact can never be committed into one language row and lost for another: either every one of the product's rows reflects the new candidate, or none does and the product is re-driven. |
| ML3 | The **logical guard unit** is the product; the **physical write transaction** is the bounded batch. These are different things and the artifact does not pretend otherwise: several products are verified and written in one local transaction for set-based efficiency (§15 BL1), while guard evaluation stays per product — one product's guard miss makes only *that* product ineligible and leaves the others in the batch eligible for the same write (GM3). What is frozen is that **no correctness order, freshness relationship or shared guard state exists between two different products**, not the stronger and untrue claim that they never share a transaction. A technical abort of the bounded transaction is a *technical* coupling — the whole batch is retried through the ordinary workflow (§15 BL9) — and it establishes no relationship between the products in it. |
| ML4 | Within the product's write, **no-op suppression still applies per row** (NO8). Unwritten rows keep their tokens; written rows advance theirs independently. Tokens of a product's rows are not required to be equal to each other and carry no cross-row meaning (RV7). |
| ML5 | A language row that is observed **absent** is created in the same guarded write as its siblings (GM5). Adding a language to the platform is an ordinary forward change: the next build creates the missing rows. |
| ML6 | A permanent split — one language at a newer source state and another permanently stale because the guard was applied differently — is structurally impossible under ML1 and is asserted by C139. |

---

## 15. Batch, locking and contention shape

| # | Rule |
|---|---|
| BL1 | Work is **set-based and batched** (R9, BP1, BP2): one observation statement, batch `<domain>.public` selectors, one guarded write per batch. Per-product loops that issue per-product queries are the failure BP2 names. |
| BL2 | Within the guarded write, rows are locked in a **deterministic key order** (product identity, then language). Two workers with overlapping batches therefore cannot suffer lock-order inversion, and cannot deadlock. |
| BL3 | **Guard contention is resolved per product.** Worker A on `{1,2,3}` and worker B on `{3,4,5}` contend *semantically* only on product `3`: only there can one worker's commit make the other's observation stale. Products `1,2,4,5` are never made stale by the other worker and are never guard-missed because of it (C138). |
| BL3a | This is a statement about **guard semantics, not about lock waits.** A transaction that holds serving-row locks for several products while it completes may briefly delay the *other batch's own completion* — that is ordinary row-lock contention, bounded by the short verify-and-write window (BL5) and by the batch size. It creates no correctness order between products, no shared guard state and no cross-product staleness. The artifact does not claim that unrelated products never share a lock, a transaction or a technical failure; it claims that they never share a **freshness relationship**. |
| BL4 | **There is no global projection mutex**, no table-level lock, no single-writer worker, no per-language global lock, no advisory lock covering the whole projection and no correctness-serialized writer fleet. Locks are serving-row locks scoped to the bounded batch. Serializing the projection fleet to solve a per-product race is forbidden by name (V107). |
| BL5 | **The guarded write transaction contains no source read, no `<domain>.public` call, no cache call and no external I/O** (OB8). The lock window is verify-and-write only, so a slow domain selector can never extend a lock hold. |
| BL6 | Batch size, chunking, throttling and the concrete locking statement are **Phase 4** (BP7), bounded by BL1–BL5. Batch size is the knob that bounds BL3a's lock-hold window; it is not a correctness parameter. |
| BL7 | A Phase 4 choice of a stricter isolation level is admissible as hardening; a serialization failure is then handled exactly as a guard miss (§20). Correctness may not be argued from isolation level (CB6). |
| BL8 | Both projection failure domains — `core.projection.incremental` and `core.projection.rebuild` (item 9 PJ1) — use **this** protocol and this code path. Two blast radii, one writer (R12, PJ5). |
| BL9 | **A technical failure of the bounded write transaction** — a deadlock, a lock timeout, a serialization failure, a connection loss, a crash — rolls back the whole batch, including the products whose guards had held. Nothing durable was written, so nothing regressed (OB7); the batch is retried through the ordinary projection workflow (§20 RT2) and each product is re-observed and rebuilt (OB4). This is a **technical retry coupling within one unit of work**, and it must not be described, tested or reasoned about as a freshness or ordering relationship between the products (ML3, BL3a). |

---

## 16. Lifecycle: withdrawal, tombstones, reactivation

| # | Rule |
|---|---|
| LF1 | Visibility is **part of the candidate**, computed from current authoritative state exactly like every other field (item 6 LC3's positive predicate). It is not a side channel and not a separate write path. |
| LF2 | **The ordinary update path never physically deletes a serving row.** Withdrawal — a product archived or unpublished, the last sellable variant withdrawn, category/brand eligibility lost, price or availability state ending sellability, a source object deleted — is a **forward content change** to a not-visible state that advances the token like any other change (item 6 LC1–LC6). |
| LF3 | This is a deliberate narrowing of item 6 LC2's latitude, made on concurrency grounds and within the mandate item 6 §16.2 gave item 12. LC2 admits both physical deletion and a non-visible state; item 12 chooses the non-visible state **for the update path**, because deleting the row destroys the guard token, and a destroyed token cannot fail a stale writer's compare-and-set. LC1's serving invariant, LC3's positive predicate and LC8's retention rule are unchanged. |
| LF4 | **A late stale visible candidate cannot resurrect a withdrawn product.** Either the withdrawal advanced the token and the stale writer's guard fails, or the stale writer's reads post-date the withdrawal and its own candidate is not-visible. There is no third case (§27, C132). |
| LF5 | **A genuine later reactivation works normally.** Re-publication is a forward current-state change: the next build reads visible truth and writes a visible row, advancing the token. Lifecycle is not modelled as an irreversible tombstone (item 6 LC8, C133). |
| LF6 | **Physical removal of a tombstoned row is a fenced maintenance operation** (§18), never part of the incremental path. Under RV8 it is not enough to delete the row and let the next write re-create it: a writer that observed token `1`, then saw the row deleted and re-inserted at `1`, would pass its guard against state it never observed — the classic ABA hole (V113). The rule is RV8/RV8a's disjunction: **either** the collector preserves non-reuse for the re-created identity, **or** it runs behind a fence that drains or invalidates every observation of the affected keys, after which reinitialization at `1` is safe because no pre-fence observation can execute. What is **not** admissible is deletion by the ordinary path, and what is **not** required is a retained history of used token values. |
| LF7 | Tombstone retention policy remains **Phase 4** (item 6 LC8), bounded by LF6. |
| LF8 | Source-domain audit, history and order snapshots are untouched by any of this (item 6 LC7). |

---

## 17. Rebuild interaction

| # | Rule |
|---|---|
| RB1 | **Targeted and full in-place rebuild use the identical protocol**: observe → build → guarded write, same builder, same token, same guard, same miss handling. A rebuild is not a privileged writer (GM8, PJ5). |
| RB2 | **A rebuild candidate can never overwrite a fresher incremental commit.** Its guard fails, exactly as an incremental writer's would; it discards and rebuilds (C136). This is the direct answer to master `# 5` principle 36's "full rebuild remains a reconciliation mechanism, not the primary race protection". |
| RB3 | Conversely, an incremental update during a rebuild is not lost: the rebuild's miss is re-driven, and the incremental write it lost to was itself built from current truth. |
| RB4 | **A rebuild requires no event history.** It reads current authoritative state and writes tokens it owns; deleting every Outbox partition, every retained payload and the whole projection leaves the projection reconstructible (R4, C137). |
| RB5 | Rebuild is bounded, batched and resumable (item 9 PJ3): each batch is an independent unit of work, so a rebuild can be paused, resumed and interleaved with incremental work. |
| RB6 | **Build-then-swap** remains a Phase 4 option (item 6 RB6) and is admitted **only** with an explicit **catch-up/handoff barrier**. Frozen now, so Phase 4 cannot choose the naive form: <br>• a fence point is recorded before the build begins; <br>• every change committed while the new structure was being built is applied to it before the swap; <br>• the swap is atomic with respect to writers, and **invalidates every observation taken before it**, so an in-flight writer's guard fails rather than silently succeeding against a token that no longer means what it meant; <br>• the swap is therefore a **generation boundary** in the sense of RV8a: because every prior observation is invalidated, the swapped-in structure's rows **may** start their tokens over at `1`, and the swap is under no obligation to carry, look up or exceed any previously used value. If a Phase 4 implementation instead chooses to preserve tokens across the swap, that is permitted and makes the fence's invalidation the belt to that suspenders — but it is never the substitute for the fence. |
| RB7 | **"Build a table for an hour and rename it over live state" without catch-up is forbidden by name** (V106). It loses every change committed during the build, and it does so silently. |
| RB8 | Neither the in-place nor the swap variant may bypass the guard (GM8) or truncate the serving table under live traffic as a normal mode (item 6 RB6). |
| RB9 | The swap mechanism, batch sizes, chunking and throttling remain **Phase 4** (item 6 RB8, BP7), bounded by RB1–RB8. |

---

## 18. Reconciliation and operator repair

| # | Rule |
|---|---|
| RC1 | **Reconciliation uses the same convergence semantics as an ordinary update.** It identifies drift (counts, checksums, sampled comparison against OLTP — item 6 RB3, master `# 7.6`) and then requests a targeted rebuild through the normal protocol. |
| RC2 | A reconciler **never** force-overwrites, never bypasses the guard, never writes a serving row directly and never carries a `force` argument (GM8). |
| RC3 | Drift is reported as an operational signal — metric, alert, runbook — not silently repaired (item 6 RB7). "The reconciler fixes it nightly" is not a substitute for a correct write path. |
| RC4 | **Token corruption** — a token that cannot be trusted because of an operator error, a partial restore, a botched migration or a bug — is a technical fault, not a business condition. The recovery is the projection's disposability (item 6 T8, RV12): rebuild the affected key range from OLTP. |
| RC5 | Such a repair must be **fenced**, because a rebuild racing live incremental writers over a key range whose tokens are untrustworthy has no guard to rely on. The frozen requirement: the affected key range is either quiesced (its incremental work paused or drained) or the repair runs behind the swap fence of RB6. Because the fence invalidates every observation of the affected keys, the repair is an **RV8a generation boundary** and may reinitialize those rows' tokens at `1`; it need not — and cannot be required to — recover or exceed the corrupted values, which is the whole point of not retaining token history. The mechanism, the CLI, the permission model and the runbook are **Phase 4 / operations**. |
| RC6 | A fenced repair is an **explicit, authorised, audited operational action** with a recorded reason — the same posture item 9 RA1–RA4 fixes for replay. It is never an ambient code path, never a hidden default and never available to a worker. |
| RC7 | **The projection is never a repair source for a domain.** No reconciliation, repair or rebuild writes projected data back into catalog, pricing, inventory, promotions or reviews (item 6 CT2, T5). Drift is always resolved in the projection's favour of OLTP, never the reverse. |
| RC8 | Reconciliation runs in `core.projection.rebuild`, under that domain's bounded capacity (item 9 PJ3, PJ4), and never starves incremental freshness (PJ2). |

---

## 19. Replay, redelivery and crash

| # | Rule |
|---|---|
| RY1 | **Replay does not bypass the guard** (item 9 RA5, GM8). A replayed trigger re-enters the normal protocol: observe, rebuild from current truth, guarded write. |
| RY2 | **Replaying an old trigger cannot regress the row.** The trigger only names products; the rebuild reads *current* state. The result is the current state — usually a no-op, because the row is already converged (C142). This is the property Candidate C buys that a source-version model has to argue for. |
| RY3 | Replay semantics are item 9's and are used unchanged: explicit, authorised, audited, identity-preserving, scoped to the failed consumer delivery, never rebroadcast to a sibling consumer that already succeeded, and never automatic. Item 12 adds no replay rule and no force path. |
| RY4 | **Crash before the guarded write** (steps 1–2, or mid-transaction): no projection state changed; the transaction rolls back; the candidate was never durable (OB7). Redelivery re-observes and rebuilds. |
| RY5 | **Crash after the guarded write commits but before the transport acknowledgement**: the delivery is redelivered. The redelivered unit rebuilds, finds the row already equal to its candidate, and performs **zero** row writes (NO1). No second effect, no token advance, no regression (C135). |
| RY6 | **Crash after reading sources but before the write**: the candidate is disposable. It is never persisted anywhere as truth, never staged into a durable table for later application, and never resumed — a retry rebuilds (OB4, OB7). |
| RY7 | Item 8's message-identity retention and item 9's terminal-state semantics apply unchanged. Item 12 requires no additional dedupe table: the guard plus no-op suppression make the *effect* idempotent by construction (TR7). |
| RY8 | A guard miss is never a reason to quarantine. Quarantine is item 8's contract/identity state (unknown type, unsupported version, invalid payload); a guard miss is ordinary contention (GM4). |

---

## 20. Bounded retry and hot contention

| # | Rule |
|---|---|
| RT1 | Compare-and-set retries are **bounded**. An unbounded retry loop is forbidden by name (V108): a continuously updated product must not spin a worker. |
| RT2 | The escalation is frozen; the numbers are not: **bounded local retries with increasing, jittered backoff → re-coalescing/rescheduling through the projection workflow → item 9's ordinary transient-failure (TF-A) handling with its own bounded retries, backoff and terminal disposition with an alert.** Item 12 invents no new retry machinery. |
| RT3 | Every retry **re-observes and rebuilds** (OB4). Retrying a stale candidate against a new token would apply older state under a fresh guard, which is the exact regression the mechanism exists to prevent. |
| RT4 | Retry is **never** surfaced as a business error, never returned to a request path, and never triggers a request-time OLTP fallback (item 6 NF1–NF7, item 9 PJ7). |
| RT5 | Coalescing is the pressure valve: many pending triggers for one hot product converge into one build, and one successful write satisfies all of them (master `# 20.2`, item 6 BP4). |
| RT6 | A hot product may not monopolise a worker or a batch: after the local budget is spent, the work returns to the queue so unrelated products progress (BL3). |
| RT7 | Attempt counts, backoff seconds, jitter widths and batch-level partial-failure policy are **Phase 4 / operations**, bounded by RT1–RT6. |

---

## 21. Resolving a source identity to the affected product set

Item 6 RB3 freezes targeted rebuild by product, product set, category, brand, price list or other
source identity. Resolving those to serving rows must not create a cross-domain shortcut.

| # | Rule |
|---|---|
| SI1 | Resolution uses **`<domain>.public` batch selectors** or `application/storefront`-owned state. No task, worker, reconciler or projection writer queries another module's tables, imports another module's models or joins across the boundary (R3, item 6 O4, V36). |
| SI2 | A category- or brand-scoped rebuild seeds its product set from the **union** of: (a) the products the authoritative owner currently reports for that identity, and (b) the products the **projection currently records** under that identity. Without (b), a product that has just *left* the category would never be refreshed by a category-targeted rebuild and would stay listed under it until full reconciliation. |
| SI3 | The projection's own copied taxonomy columns are legitimate for (b) — they are application-owned state — but they are **only** a seed. They are never the authoritative answer to "what is in this category" (item 6 CT1, R2). |
| SI4 | Resolution is bounded and batched: a seed set larger than a batch is chunked into units of work (BL1, RB5), never materialised as one unbounded write. |
| SI5 | Resolution never changes the protocol: whatever the seed, each product is written through observe → build → guarded write. |
| SI6 | Where a mapping between an external identity and internal entities is needed, the owner is `application/erp_sync` (ADR-0005, item 3); `application/storefront` neither owns nor duplicates it, and application→application imports remain forbidden (R7 of item 6). |
| SI7 | Concrete event payloads, selector signatures and seed queries are **not** designed here (TR5, item 8, each owning module's phase, Phase 4). |

---

## 22. Admitting a future source

| # | Rule |
|---|---|
| FS1 | The set of contributing sources is **not** assumed permanent. Item 13 may or may not introduce an analytics source for popularity; other sources may follow. |
| FS2 | Under the selected model, admitting a source is: one more input to the canonical builder, read through that owner's `<domain>.public` batch selector; one more trigger contract (item 8); and one more failure-domain routing decision per consumer (item 9). |
| FS3 | It requires **no** change to the token, no new component, no schema migration of guard state, no re-proof of §27 and no version-space coordination. This is a decisive advantage over Candidate B, where each new source is a new vector component plus a re-proof of every derived field's merge rule. |
| FS4 | Admission is still deliberate: the new value must have an authoritative owner and must be reproducible by a rebuild, or it may not be enabled at all (item 6 RB1, SO6b, V37). |
| FS5 | **No analytics projection state, column, signal or trigger is pre-created here.** Item 13 decides whether analytics exists; item 12 only states what happens if it does. |

---

## 23. Separations restated by reference

Restated, not re-decided. Each rule's authority is the artifact named.

| # | Rule | Authority |
|---|---|---|
| SE1 | `schema_version` ≠ `projection_revision`. `schema_version` is never read, compared, ordered or `max`-ed to decide which of two messages or states is newer. | item 8 OR6, SV9, A47 |
| SE2 | `EventId`, `causation_event_id`, `PublicId` and UUIDv7 timestamp bits are identity, never freshness. No guard, no comparison, no ordering, no tiebreak. | item 11 TS4, MI7; ADR-0013 |
| SE3 | `occurred_at` is business fact time. Clocks skew and values tie; it orders nothing. | item 8 TS4, OR3 |
| SE4 | An Outbox or Inbox row id orders insertion into one table, not the facts of one entity, and is not preserved across replay. | item 8 OR3 |
| SE5 | Trace fields decide nothing: not ordering, not identity, not idempotency, not routing. | item 10's correctness firewall |
| SE6 | Redis and every other cache are disposable acceleration. A cache counter is never the correctness version, and cache invalidation is not this mechanism. A full flush leaves PostgreSQL serving. | item 6 R12, CA1–CA3, C29 |
| SE7 | Checkout's freshness/revalidation guard and this mechanism are different mechanisms for different problems, with different owners and different failure modes. | item 6 PU9, item 5 §7.4 |
| SE8 | `projection_revision` never decides a final price, an inventory reservation, coupon validity, a payment, an order placement or an authorization outcome. The projection can be stale; checkout revalidates through the owning domains. This is display convergence, not transaction concurrency control. | item 6 T6, T9, R13; ADR-0007 |
| SE9 | No public storefront DTO, API payload, HTML attribute, URL, cursor or externally consumed event carries `projection_revision` or any freshness state. | item 7 DC9, LR8; RV9 |
| UD1 | `updated_at` is **operational/display metadata**: it records when a serving row's content actually changed. | here |
| UD2 | `updated_at` is **not** the guard token, not a source revision, not an ordering proof and not a CAS token. Using it as one is forbidden (A89, V111). | here |
| UD3 | Because a no-op writes nothing, `updated_at` **does not change** on a duplicate or no-change trigger — the preferred behaviour, and the one that keeps it meaningful. | NO1, NO5 |
| UD4 | Freshness/lag is therefore measured on the trigger pipeline and by reconciliation, never by reading `updated_at` and assuming staleness. | NO5, §25 |

---

## 24. Corruption, overflow and physical-type position

| # | Rule |
|---|---|
| OV1 | **The physical type is decided here, not deferred**: a 64-bit signed integer, `NOT NULL`, initial `1`, `+1` per committed serving-state change (RV2, RV4). Item 6 §16.2 assigned the type to item 12 and item 12 takes the position rather than passing it to Phase 4. Phase 4 owns the column *definition*, index decisions and the model — not the choice of type. |
| OV2 | **Wraparound semantics are forbidden.** No modular arithmetic, no reset-to-zero, no "it will never happen so we ignore it" comparison that would silently succeed after a wrap. |
| OV3 | Approaching the type's bound is a **technical fault** requiring intervention (a fenced rebuild re-establishing tokens, RC5), not a correctness feature. At `+1` per content change, the bound is not reachable by any catalog size and update rate this platform will see; the rule exists so that a future generator change cannot quietly introduce a wrap. |
| OV4 | A `NULL`, negative or non-increasing token is **corruption**, not a state: the guard cannot be evaluated against it, so the row is repaired through RC4/RC5, and the condition is alerted, never silently coerced to a default. |
| OV5 | Token corruption never justifies a force write (GM8). It justifies a fenced rebuild, which is a different thing with a different authorisation model. |

---

## 25. Observability

Conceptual requirements only. Metric names, thresholds, dashboards and alert routing are **Phase 4 /
operations**, per item 6 CM8 and item 9's alerting model.

| # | Rule |
|---|---|
| OM1 | **Projection update lag** must be measurable and alerted (item 6 CM7, CM10; item 9's oldest-message age; master `# 23.2` *Listing Projection Lag*), measured on the trigger pipeline, not from `updated_at` (UD4). |
| OM2 | **Guard-miss rate** (compare-and-set conflicts) per unit of work and per product. |
| OM3 | **Stale-candidate rejections** — candidates discarded after a miss, distinguished from misses that resolved on the first local retry. |
| OM4 | **Retry and re-coalesce rate**, including local budget exhaustion (RT2). |
| OM5 | **Rows changed vs candidates processed**, and the derived **no-op suppression ratio** — the direct health signal for trigger coalescing and write amplification (BP5). |
| OM6 | **Reconciliation drift**: rows compared, rows found divergent, rows repaired (RC3). |
| OM7 | **Full/targeted rebuild progress**: units of work completed, remaining, and rebuild-vs-incremental conflict rate (RB2). |
| OM8 | A **spike in guard conflicts is an operational signal**, not automatically an error: it means contention, which the protocol is designed to survive. A sustained spike alongside a rising no-op ratio means triggers are not being coalesced (RT5). |
| OM9 | No metric, log or trace attribute derived from this mechanism may carry PII or secrets, and none of them feeds a correctness decision (item 10's firewall). |

---

## 26. The guard, in pseudo-SQL

Architecture notation. It fixes the semantics of the guard so the mechanism is mechanically
reviewable; it is not a migration, not a query to copy, and it names no final column set (Phase 4).

```text
─── step 1: OBSERVE ─── strictly before any source read, no lock, one statement per batch

    SELECT product_id, language, projection_revision
      FROM product_listing_projection
     WHERE product_id = ANY(:product_ids);

    observed[(product_id, language)] := projection_revision
    every (product_id, language) key not returned  := ABSENT

─── step 2: BUILD ─── no lock held; each source read is an AUTHORITATIVE read whose
                      visibility point is established AFTER step 1   (CB10, CB12, OB1)
                      — never a cache entry, never a lagging replica,
                      never a snapshot opened before step 1

    candidate[(product_id, language)] :=
        canonical_builder(
            catalog.public.<batch selector>(:product_ids),
            pricing.public.<batch selector>(...),
            inventory.public.<batch selector>(...),
            promotions.public.<batch selector>(...),
            reviews.public.<batch selector>(...)
        )
    -- whole serving state, every language, every field         (CB1)
    -- a product with no storefront eligibility yields a NOT-VISIBLE candidate,
    --   never a delete                                          (CB7, LF2)

─── step 3: GUARDED WRITE ─── one local transaction per bounded batch — several products,
                              guard evaluated per product (GM3, ML3); no source read
                              inside                                        (OB8, BL5)

    BEGIN;

    SELECT product_id, language, projection_revision
      FROM product_listing_projection
     WHERE product_id = ANY(:product_ids)
     ORDER BY product_id, language
       FOR UPDATE;                       -- deterministic order (BL2); product-scoped (BL4)

    -- verify, per product, ALL of its rows at once                (GM1, GM2, ML1):
    --   every observed revision is still equal, and
    --   every observed-ABSENT key is still absent
    -- any mismatch ⇒ that product is a GUARD MISS: excluded from this write entirely,
    --   its candidate discarded whole                             (GM3, GM7)

    -- for each surviving product, for each language row whose candidate differs from the
    -- stored serving state (comparison excludes projection_revision and updated_at, NO2):

    INSERT INTO product_listing_projection AS p
           (product_id, language, <serving columns>, projection_revision, updated_at)
    VALUES (...,                                     1,                   now())
        ON CONFLICT (product_id, language) DO UPDATE
       SET <serving columns>   = EXCLUDED.<serving columns>,
           projection_revision = p.projection_revision + 1,
           updated_at          = now()
     WHERE p.projection_revision = :observed_revision_for_that_row       -- equality only (RV6)
       AND (p.<serving tuple>) IS DISTINCT FROM (EXCLUDED.<serving tuple>);  -- no-op (NO1)

    COMMIT;

─── outcomes ───

    row written        ⇒ serving state changed; projection_revision advanced; updated_at set
    row not written,
      content equal    ⇒ NO-OP: no UPDATE, no token advance, no updated_at change  (NO1, NO3)
    row not written,
      revision moved   ⇒ GUARD MISS — already detected by the FOR UPDATE verification,
                         so a no-op is never mistaken for a miss                    (NO4)
    insert conflicted  ⇒ the key was observed ABSENT and now exists: GUARD MISS     (GM5)

─── guard miss handling ─── never a business error, never a quarantine   (GM4, GM9, RY8)

    discard the candidate whole                                              (GM7)
    bounded local retry:  re-OBSERVE → re-BUILD → re-attempt, jittered       (RT1, RT3)
    budget exhausted:     return to the projection workflow as a transient
                          failure; item 9's bounded retry / backoff /
                          terminal disposition applies unchanged             (RT2)
    never:                force write, partial apply, field merge, request-path effect

─── technical abort of the bounded transaction ───                          (BL9)

    deadlock / lock timeout / serialization failure / crash
        ⇒ the whole batch rolls back, including products whose guards held
        ⇒ nothing durable was written, so nothing regressed              (OB7)
        ⇒ the batch is retried; every product is re-OBSERVEd and re-BUILT (OB4)
    this is a technical retry coupling inside one unit of work,
    never a freshness or ordering relationship between products      (ML3, BL3a)
```

---

## 27. Correctness proof

**Setup.** All of §27 is stated **within one projection generation** (§3): ordinary incremental,
targeted-rebuild and reconciliation work. A generation boundary — a fenced destructive rebuild,
tombstone collection, table replacement or swap — is not a concurrent write and is not covered by
these lemmas; it is covered by RV8a's fence, which drains or invalidates every observation of the
old generation so that no pre-fence observation can execute against a post-fence row (§27.4).

For a committed write `W` to serving row `r`:

- `obs(W)` — the instant `W` observed `r`'s token (step 1);
- `view(W, S)` — the **authoritative committed view** of source `S` from which `W` built its
  candidate, and `vp(W, S)` its **visibility point**: the instant such that `view(W, S)` contains
  exactly the transactions of `S` committed before it;
- `commit(W)` — its commit instant.

The protocol guarantees:

1. `obs(W) < vp(W, S)` for **every** source `S` — this is OB1 read together with CB10 and CB12. It
   is a statement about *visibility points*, not about call order: a cache entry, a lagging replica
   read or a snapshot opened before `obs(W)` would satisfy "the call happened later" while
   violating this premise, which is exactly why CB10–CB12 forbid them for a candidate field.
2. `W` commits only if `r`'s token is unchanged throughout `[obs(W), commit(W))` — the atomicity of
   the compare-and-set.
3. `vp(W, S) < commit(W)` — the candidate is built before it is written.

**Visibility monotonicity.** If `vp(W_k, S) > vp(W_j, S)` then `view(W_k, S)` contains every
transaction of `S` that `view(W_j, S)` contains: a transaction committed before the earlier
visibility point is also committed before the later one. This is a statement about *which commits are
visible*, not about the values they carry — see §27.3's note on `100 → 120 → 100`.

### 27.1 Safety — a stale candidate cannot overwrite newer serving state

**Lemma 1.** Let `W_j` and `W_k` be consecutive committed writes to `r`, `W_j` first. Then
`commit(W_j) < obs(W_k)`.

*Proof.* `W_k` committed, so at `commit(W_k)` the token of `r` still equalled the value `W_k`
observed at `obs(W_k)`. `W_j` committed a change to `r`, which advanced the token (RV4), and within
this generation an advanced token never returns to a previously committed value (RV8) — so had
`commit(W_j)` fallen inside `[obs(W_k), commit(W_k))` the equality would have failed. With
`commit(W_j) < commit(W_k)` it follows that `commit(W_j) < obs(W_k)`. ∎

RV8 is load-bearing here, and it is exactly why RV8a's reuse allowance must be fenced: without
within-generation non-reuse, "the value is still what I observed" would no longer imply "nobody wrote
in between", which is the ABA hole (LF6, V113).

**Lemma 2 (visibility-point domination).** For every source `S`:
`vp(W_j, S) < commit(W_j) < obs(W_k) < vp(W_k, S)`.

*Proof.* The left inequality is setup premise 3, the right one is setup premise 1, and the middle
one is Lemma 1. ∎

**Safety.** By Lemma 2, `W_k`'s visibility point on **every** source is strictly later than `W_j`'s,
so by visibility monotonicity `view(W_k, S) ⊇ view(W_j, S)` for every `S`: `W_k` saw every source
commit that `W_j` saw, and possibly more. The row's content is a deterministic total function of
those views (CB1, CB9), so no source's contribution is dropped from the committed row. A candidate
whose visibility points predate a competing newer write can therefore never be committed after it:
its guard fails. ∎

Note what the proof does **not** use: no ordering of the sources against each other, no message
order, no clock, no producer sequence, and no assumption about how business values move. It uses
exactly three things — OB1 read as CB10's visibility-point ordering, the atomicity of the
compare-and-set, and RV8's within-generation non-reuse (which is what makes Lemma 1's "the token
changed" detectable). Those three are therefore the invariants to enforce and check (A98, A99, A100,
V102's neighbours, V116).

### 27.2 Convergence — the row equals a fresh rebuild once work stops

Let the last source change relevant to product `P` commit at `T*`. By R16 its durable trigger is
written in the same transaction, so the trigger becomes visible to the relay only after `T*`. Any
unit of work driven by that trigger therefore has `obs > T*` and, by OB1/CB10, has
`vp(·, S) > obs > T*` for every source `S`; its candidate reflects `T*`. (This is where CB11 earns
its keep: a builder allowed to answer from a cache warmed before `T*` could satisfy the call ordering
and still miss the change entirely, and convergence would fail even though safety held.)

That unit either (a) commits — the row now equals a fresh rebuild; or (b) finds its candidate equal
to the stored state and no-ops — the row already equalled a fresh rebuild; or (c) guard-misses,
retries with strictly later visibility points (RT3), and re-enters the same three cases. Delivery is at-least-
once and case (c) is bounded (RT2): on exhaustion the delivery becomes an item 9 terminal state with
an alert, and convergence then depends on an operator replay (RY1) or on reconciliation (RC1) —
both of which run this same protocol. Under no path is the change silently dropped. ∎

### 27.3 Independence — two sources cannot erase each other

Apply §7.2's canonical race. `W_p` and `W_i` observed the same token; by the atomicity of the
compare-and-set at most one commits. Suppose `W_i` commits `(P1, I2)`. Then `W_p` guard-misses,
discards, re-observes and rebuilds, and by Lemma 2 its new visibility points post-date `W_i`'s, so it
sees both `P2` and `I2` and commits `(P2, I2)`. Symmetrically if `W_p` wins. The converged state is
`(P2, I2)`.

`(P2, I1)` cannot be the converged state, because a committed candidate is always a **total** rebuild
from all sources (CB1) and Lemma 2 makes each successive committed candidate's per-source view a
superset of its predecessor's. The lost-update mode of whole-row last-writer-wins — a newer *token*
carrying an older *view* — is impossible here, because the token is not a claim about the sources at
all; it is a per-row write counter, and Lemma 2 ties its order to visibility-point order. ∎

**What "regression" means here.** The proof is about **state visibility chronology, not value
trajectory** (CB14). A source may legitimately move `price 100 → 120 → 100`; committing the final
`100` is convergence on the newest authoritative fact, not a regression, and nothing in this
mechanism inspects business values to decide freshness. "Regression" means exactly one thing: a
committed row reflecting a *strictly earlier set of visible source commits* than the row it replaced.

A candidate may still be a **mixed-time** snapshot across sources (CB6). By Lemma 2 that is safe:
mixing produces transient display incoherence bounded by convergence (item 6 CM3, CM4), never a
regression and never a permanent loss.

### 27.4 Rebuildability — delete everything and reconstruct

The token is application-owned and per row (RV3, RV4). A rebuild **over a populated projection**
(targeted or full, in place) runs the ordinary protocol inside the current generation, so §27.1
applies to it unchanged. A **destructive** rebuild — the projection deleted, lost, or replaced —
is a **generation boundary**: rows are re-created starting at `1`.

That reset does not weaken §27.1, and it is the one place where the two properties could have
collided:

- §27.1 needs RV8 (within a generation, an observed value still standing means nobody wrote in
  between). A reset would break that **only** if some observation from the old generation could
  still execute a compare-and-set against a new-generation row.
- RV8a forbids exactly that: a destructive rebuild, tombstone collection, replacement or swap is
  admissible **only** behind a fence that drains or invalidates every old observation (RB6, RC5,
  LF6). After the fence, the value `1` appearing again is harmless, because nothing that once read
  `1` is still capable of acting on it.

So the two statements hold together: **ordinary concurrent writers cannot suffer ABA** (RV8), and
**the entire disposable projection can be deleted and rebuilt from OLTP with no retained token
history and no retained event history** (RV8a, RV12, RB4). No step consults an event payload, a
retained partition, a producer version, a historical order or a previous token value; item 6
RB1/RB2 hold exactly. ∎

### 27.5 No-op property — duplicates do not rewrite rows

Comparison excludes the token and `updated_at` (NO2), and the builder is deterministic (CB9). A
duplicate trigger therefore produces a candidate byte-equal to the stored serving state, the write
predicate's `IS DISTINCT FROM` clause matches nothing, and **zero** statements affect the row. The
token does not advance (RV5), so a duplicate cannot even cause another writer's guard to fail. ∎

### 27.6 What the proof does not assume

| Assumption **not** made | Where it would have hidden |
|---|---|
| Messages normally arrive in order | Anywhere the argument said "the newer event wins" |
| One delivery per fact | Anywhere the argument counted effects |
| A producer sequence orders commits | §7.1 |
| A single message describes the whole row | §7.2 |
| Event history is retained | §7.3 |
| A cross-domain atomic snapshot exists | CB6 |
| A specific isolation level | BL7 |
| A clock is comparable across processes | §5 |
| Business values move monotonically | §27.3's `100 → 120 → 100` note, CB14 |
| Token values are globally unique forever | §27.4, RV8a |
| Two products in one batch share any freshness relationship | ML3, BL3a, BL9 |

If any of these were required, the design would fail. None is.

What the proof **does** require, and what §29 therefore checks, is exactly three things: OB1 read as
CB10's visibility-point ordering (A98, A99, A100); the atomicity of the per-row compare-and-set
(GM1, GM6); and RV8's within-generation non-reuse, with every reset fenced (RV8a, V116).

---

## 28. Failure matrix

Commercial-correctness impact is measured against item 6 T7: no row may compromise `Order`
correctness. Every cell is `None` because the commercial answer never comes from this projection
(item 6 T6, R13, ADR-0007).

| # | Situation | Can stale serving state commit? | Does the row change? | Retry / rebuild action | Token / guard action | Commercial impact |
|---|---|---|---|---|---|---|
| 1 | Duplicate trigger | No | No | None — converged | Unchanged (NO1, NO3) | None |
| 2 | Old trigger delivered after a newer one | No | Only if current truth differs from the row | Rebuild from current truth | Advances only on a real change | None |
| 3 | Price and inventory change concurrently | No | Yes, to `(P2, I2)` | Loser rebuilds and commits both | One writer advances; the other misses | None |
| 4 | Two workers build from the same observed token | No | Yes, once | One commits; the other discards and rebuilds | Exactly one advance | None |
| 5 | Worker A old candidate, worker B newer candidate, B commits first | No | Yes, to B's state, then to A's rebuilt state if truth moved | A discards and rebuilds with later reads | A's guard fails | None |
| 6 | A source changes after the candidate was read, before the write | No — the write is per-source monotone | Yes, to the candidate | The later source change's own trigger drives convergence | Advances normally | None |
| 7 | Guard miss | No | No, for that product in that unit | Discard whole, bounded retry, then re-coalesce (RT2) | No advance; not an error, not a quarantine | None |
| 8 | Insert race on a missing row | No | Yes, once | Loser observes the conflict as a miss and rebuilds | Winner inserts at `1`; loser retries | None |
| 9 | Withdrawal, then a late stale visible candidate | No | No resurrection | Stale writer's guard fails, or its own reads already say not-visible | Withdrawal advanced the token (LF2, LF4) | None |
| 10 | Legitimate reactivation after withdrawal | n/a — forward change | Yes, back to visible | Normal build from current truth | Advances (LF5) | None |
| 11 | Incremental update during a targeted rebuild | No | Yes, to whichever commits; the loser rebuilds | Same protocol both sides (RB1) | One advance per commit | None |
| 12 | Incremental update during a full in-place rebuild | No | Same as row 11 | Rebuild batches are independent units (RB5) | Rebuild is not privileged (RB2) | None |
| 13 | Build-then-swap attempted without catch-up | **Would lose committed changes**, and would also let a pre-swap observation act on a post-swap row | — | **Forbidden** (RB7, V106); a swap requires a fence and catch-up (RB6) | The swap is an RV8a generation boundary: it must invalidate every prior observation, after which the new generation's tokens **may** start at `1` | None (the shape is not permitted) |
| 14 | Rebuild after the event history was archived | No | Yes, to current truth | Full/targeted rebuild reads OLTP only (RB4) | Tokens are application-owned; no history, no producer version and no previous token value is consulted (RV8a, §27.4) | None |
| 15 | Replay of an old projection trigger | No | Only if truth differs | Rebuild from current truth (RY2) | Normal guard; usually a no-op | None |
| 16 | Worker crash before the guarded write | No | No | Redelivery re-observes and rebuilds (RY4) | Nothing durable was written | None |
| 17 | Worker crash after commit, before acknowledgement | No | No, on redelivery | Redelivery rebuilds and finds equality (RY5) | No second advance | None |
| 18 | Reconciliation finds content drift | No | Yes, repaired through the normal protocol | Targeted rebuild (RC1) | Guard honoured; no force (RC2) | None |
| 19 | Token metadata corrupted | No — the guard is untrustworthy, so the path is fenced | Yes, after repair | Fenced rebuild of the affected range (RC4, RC5) | The fence ends the generation, so the repair may reinitialize the affected rows' tokens; it is not required to recover or exceed the corrupted values (RV8a, RV8b) | None |
| 20 | Unchanged candidate from a duplicate event | No | No | None | Unchanged; `updated_at` unchanged (UD3) | None |
| 21 | Overlapping batches `{1,2,3}` and `{3,4,5}` | No | Yes, per product | Product `3` resolved by the guard; the other products stay semantically eligible in their own batch and are not guard-missed because of it (GM3, BL3) | Per-product guard scope, deterministic lock order; lock waits between the batches are ordinary contention and imply no freshness relationship (BL2, BL3a) | None |
| 22 | Two language rows of one product | No | Yes, all-or-nothing per product | Whole product re-driven on a miss (ML1) | Per-row tokens, per-product verification | None |
| 23 | A newly admitted future source | No | Yes, when its facts change | One more builder input, one more trigger (FS2) | No token or guard change (FS3) | None |
| 24 | Projection queue delay / backlog | No — only staleness | No, until work drains | Capacity and alerting; **never** a request-time OLTP fallback (item 6 NF1, item 9 PJ7) | No guard involvement | None |
| 25 | **Technical abort of a bounded write transaction** (deadlock, lock timeout, serialization failure, crash) | No — nothing durable was written | No; the whole batch rolls back, including products whose guards held | The batch is retried; every product is re-observed and rebuilt (BL9, OB4) | No token advances; a technical retry coupling within one unit of work, never a cross-product freshness relationship (ML3, BL3a) | None |
| 26 | **A stale cache entry or lagging replica is offered to the builder** | No — such a view may not finalize a candidate field (CB10, CB11) | Only from authoritative state | The builder reads authoritatively, or the field is verified before materialisation; a cache remains a hint | No guard involvement; the failure this prevents is a *convergence* failure, not a regression (§27.2) | None |
| 27 | **A read snapshot is opened before the observation** | **Would break Lemma 2 silently** | — | **Forbidden** (CB12, A100, V117); a snapshot opened after the observation is admissible | The token guard alone cannot detect it, which is why the ordering is frozen rather than left to implementation taste | None (the shape is not permitted) |

**Core invariant:** every row above answers "can stale serving state commit?" with **No**. Rows 13,
19 and 27 are the three where an unsafe *shape* exists; each is forbidden in the ordinary path and
admitted, where admitted at all, only behind an explicit fence or ordering rule.

---

## 29. Checks a later phase must implement

These **extend** the enforcement maps of item 3 §15, item 4 §19, item 5 §22, item 6 §25, item 7
§23, item 8 §30, item 9 §33, item 10 §22 and item 11 §40; those remain authoritative and unchanged.
Nothing here is implemented in Phase 0.

### 29.1 Import graph (`L` series)

**No new `L` rule and no new `core` allowlist entry.** Every import this mechanism needs —
`application/storefront` → `<domain>.public`, → `core`, → its own internal ORM; `tasks/*` →
`application/storefront.public` — is already permitted by item 3 §4.3/§4.4/§4.6, and every import it
must not make is already `FORBID`. L1–L21 stand unedited.

### 29.2 Static / AST (continuing the `A` series)

| # | Rule |
|---|---|
| A86 | **No projection-motivated version on a domain table:** no model under `domains/*` declares a field named `source_version`, `projection_revision`, `listing_version`, `storefront_version` or an equivalent whose only consumer is the read model (R7, PU10, ADR-0003 §3). |
| A87 | **No `schema_version` freshness comparison** anywhere on the projection write path: no comparison, ordering, `max`/`min`, staleness guard or upsert predicate reads `schema_version`/`event_version` (extends A47 to this writer; SE1). |
| A88 | **No identity-as-order:** no `EventId`, `PublicId`, `causation_event_id`, raw `UUID` or UUID timestamp component appears in a projection write predicate, sort key or freshness comparison (SE2; extends V97). |
| A89 | **No timestamp last-writer-wins:** no projection write predicate compares `occurred_at`, `updated_at`, `NOW()`, a clock reading or any renamed equivalent, and `updated_at` is never read as a guard (SE3, UD2, OS2). |
| A90 | **No transport ordering:** no Outbox/Inbox row id, broker delivery id, queue position, attempt counter, worker id or trace field appears in a projection write predicate (SE4, SE5). |
| A91 | **Equality-only token comparison:** `projection_revision` appears in a predicate only under `=`, and in an assignment only as the `+ 1` advance. No `<`, `>`, `<=`, `>=`, `BETWEEN`, `MAX`, `GREATEST`, `LEAST` or `ORDER BY` over it in any write path (RV6). |
| A92 | **Single owner of the guard state:** no module outside `application/storefront` reads or writes `projection_revision`, and no module under `domains/*`, `interfaces/*`, `integrations/*` or `tasks/*` references it at all (extends A30; R1). |
| A93 | **No unguarded projection write:** every `INSERT`/`UPDATE`/`UPSERT`/`DELETE` against a serving table originates in the single guarded-write component; no other module, manager method, signal handler, `save()` override, admin action or management command issues one (extends A30; GM8). |
| A94 | **No force path:** no projection write use case, task or tool exposes a `force`, `overwrite`, `ignore_guard`, `skip_version_check` or equivalent parameter, and no code path writes a serving row without an observed token (GM8, RC2). |
| A95 | **No leakage into public shape:** no storefront DTO, serializer, template, URL builder, cursor codec or cache-key builder references `projection_revision` or any freshness field (RV9, SE9; extends item 7 A39). |
| A96 | **Payload is not content:** the projection updater assigns no serving field from a trigger payload attribute; payload use is confined to identifier resolution, coalescing and metrics (TR2, TR4). |
| A97 | **No cache counter as a version:** no Redis/cache `INCR`, counter or TTL value is read into a projection write predicate or used as a guard token (SE6). |
| A98 | **Observe before read:** within the guarded-write component, no `<domain>.public` selector call for a unit of work appears before that unit's token observation, and the observation is not re-taken between the source reads and the write. AST-checkable at the call-ordering level and reinforced by review V102's neighbours (OB1). |
| A99 | **Authoritative source reads:** no candidate field is finalized from a cache/Redis client, a fragment-cache read, a `cache.get`-shaped call or a connection routed to an asynchronously lagging replica. The builder's correctness reads target authoritative committed owner state (CB10, CB11). Checkable as: the builder module opens no cache client for candidate content, and any read-routing hint on its path resolves to an authoritative source. |
| A100 | **Snapshot ordering:** if the builder wraps its source reads in a database transaction or explicit snapshot, that transaction/snapshot is opened **after** the token observation of the same unit of work — never before, and never reused across units of work (CB12, OB4). |

### 29.3 Behavioural / contract tests (continuing the `C` series)

| # | Rule |
|---|---|
| C128 | **Classic stale writer:** W1 builds an old candidate; W2 builds a current one; W2 commits; W1 attempts. Final serving state is W2's / current truth, W1's write is rejected, and W1's rebuilt retry converges (§27.1). |
| C129 | **Independent sources:** from `(P1, I1)`, pricing commits `P2` and inventory commits `I2` with overlapping workers in every interleaving. Final state is `(P2, I2)`; `(P2, I1)` and `(P1, I2)` never survive convergence (PU5, §27.3). |
| C130 | **Reverse delivery:** a newer trigger is handled, then an older one. The serving state does not regress, and the second pass rewrites nothing unless truth moved (PU3, PU4). |
| C131 | **Duplicate trigger:** a second identical pass performs **zero** row writes, leaves `projection_revision` unchanged and leaves `updated_at` unchanged (NO1, NO3, UD3). |
| C132 | **Withdrawal is not resurrected:** a product is withdrawn; a worker holding an older visible candidate then attempts a write. The product remains absent from listings, facet counts, search and cursor walks (LF4; extends C30). |
| C133 | **Reactivation works:** after withdrawal, authoritative state becomes visible again; the projection returns the product through the ordinary path with no operator action (LF5). |
| C134 | **Insert race:** two workers build for an absent row and both attempt the initial insert. Exactly one row exists, its content equals current truth, and no integrity error surfaces as a business error or escapes the write component (GM5). |
| C135 | **Crash after commit, before acknowledgement:** the redelivered unit performs no row write, no token advance and no regression (RY5). |
| C136 | **Incremental vs rebuild:** a rebuild candidate built before an incremental commit cannot overwrite it; the rebuild's guard fails and its retry converges to current truth (RB2). |
| C137 | **Event history removed:** with every Outbox partition and retained payload deleted, a full rebuild from OLTP establishes valid guard state and reproduces the event-updated serving state; the rebuilt rows may start at token `1` and no retained token history is consulted (RB4, RV8a, §27.4; extends C26). |
| C138 | **Batch overlap:** worker A on `{1,2,3}` and worker B on `{3,4,5}` converge; product `3` resolves through the guard while a guard miss on `3` leaves `1,2` (or `4,5`) semantically eligible in the same write, and no deadlock occurs under repeated interleaving (BL2, BL3, GM3). The assertion is about **guard outcomes**, not about lock waits: the test does not assert that the two batches never block each other. |
| C138a | **Technical abort of a bounded batch:** a forced deadlock/serialization failure in the guarded write rolls the whole batch back, leaves no partially applied product, regresses nothing, and is retried with every product re-observed and rebuilt (BL9, OB4, OB7). |
| C139 | **Two language rows of one product** are never left permanently split at different source states under any interleaving; a partial write of one language without its siblings never commits (ML1, ML6). |
| C140 | **Source change during build:** a source commits between the builder's reads. The write does not regress any already-committed newer state, and the change's own trigger converges the row (CB6, §27.2). |
| C141 | **Hot contention:** a continuously updated product produces bounded local retries, then re-coalescing; no unbounded loop, no worker starvation, and unrelated products keep progressing (RT1, RT6). |
| C142 | **Replay of an old trigger:** replaying an archived projection trigger produces current state — normally a no-op — and never regresses the row; the guard is not bypassed (RY1, RY2). |
| C143 | **Rebuild idempotence and no-op:** a full rebuild over an already-converged projection changes no row and advances no token; running it twice changes nothing (extends C26 with the token property). |
| C144 | **Reconciliation honours the guard:** a reconciler that detects drift repairs it through the normal protocol; with a concurrent newer incremental write, the reconciler's stale candidate is rejected rather than forced (RC1, RC2). |
| C145 | **Stale reads cannot become a candidate:** with a fixture in which the cache (and, where applicable, a lagging replica connection) holds source data older than a committed change, the builder's committed candidate reflects the committed change. A candidate field sourced from the stale copy without authoritative verification never reaches the serving row (CB10, CB11, §27.2). |
| C146 | **Snapshot ordering:** with the builder configured to use a read transaction/snapshot, a unit of work whose snapshot would be established before its observation is rejected (or the ordering is asserted directly), and a snapshot established after the observation converges normally (CB12, A100). |
| C147 | **Fenced generation reset:** after a fenced destructive rebuild or swap, a writer holding a pre-fence observation of token `1` cannot commit against a post-fence row that also carries token `1`; its unit of work is invalidated or fails and is re-driven (RV8a, RB6, RC5, LF6). The mirrored negative case is asserted too: **without** a fence, a delete-and-recreate at `1` lets the stale writer through — which is why the ordinary path never deletes (LF2, V113). |

### 29.4 Review-only (continuing the `V` series)

| # | Rule |
|---|---|
| V102 | An ordered comparison of `projection_revision` — `>`, `>=`, `MAX`, `GREATEST`, an `ORDER BY`, or a cross-row comparison — appearing in any predicate or reasoning (RV6, RV7). |
| V103 | A producer-supplied `source_version` (under any name) reappearing in a payload and being honoured as a freshness token, or a domain being asked to emit one "so the projection can order" (TR3, TR5, R7). |
| V104 | A projection-motivated version, dirty flag or freshness column added to `Product`, `ProductVariant`, `Price`, `InventoryBalance` or any other domain table (R7, PU10, A86). |
| V105 | A force/bypass write path arriving as a "temporary" repair tool, an admin action, a management command flag or a reconciler argument (GM8, RC2). |
| V106 | A build-then-swap rebuild without a catch-up barrier and without observation invalidation at the swap (RB6, RB7). |
| V107 | A global projection mutex, table lock, single-writer worker or advisory lock covering the whole projection, introduced to "simplify" the race (BL4). |
| V108 | An unbounded compare-and-set retry loop, or a retry that reuses a stale candidate instead of rebuilding (RT1, RT3). |
| V109 | A candidate assembled from trigger payload fields, or a "fast path" that skips a source read because the payload "already has the price" (TR2, A96). |
| V110 | No-op suppression removed or weakened so that every delivery rewrites the row to advance a counter, or a comparison that includes `projection_revision`/`updated_at` and therefore never finds equality (NO1, NO2). |
| V111 | `updated_at` promoted to a guard, an ordering proof or a freshness comparison, including under a renamed column (UD2, OS2). |
| V112 | `projection_revision` surfacing in a `ProductCard`, a facet DTO, an API response, HTML, a URL, a cursor, a checkout input, an authorization decision, or a cache key treated as correctness (RV9, SE8, SE9). |
| V113 | The ordinary update path physically deleting a serving row, or a tombstone collector re-creating a key with a reused token value **outside a fence** — the ABA hole (LF2, LF6, RV8, RV8a). |
| V116 | Either half of RV8/RV8a's disjunction quietly dropped: a destructive rebuild, tombstone collection, table replacement or swap that **resets tokens without a fence** that drains or invalidates prior observations; or, in the opposite direction, a **durable epoch column, token-history table, retained per-row maxima, or a backup/replication obligation for the token** introduced to "solve" ABA — which would make the projection non-disposable (RV8b, RV12, §27.4). |
| V117 | A builder candidate field finalized from bounded-stale data — a warm cache entry, a fragment cache, a lagging replica, a "fresh enough" copy — or a read snapshot established before the observation; equivalently, any argument of the form "the selector was called later, so it saw newer state" (CB10–CB12, A99, A100). |
| V118 | The false strong claim reappearing in text or tests — that different products never share a transaction, a lock or a technical failure — instead of the true one, that they share no freshness or ordering relationship (ML3, BL3a, BL9). |
| V114 | Reconciliation or operator repair performed without a fence over a key range whose tokens are untrusted, or a repair that writes projected data back into a domain (RC5, RC7). |
| V115 | A per-source partial merge or version vector introduced ad hoc — "only update the price columns" — without an owned field-to-source decomposition and a new ADR (CB4, §6.2). |

---

## 30. Explicitly deferred decisions

| Deferred | Owner |
|---|---|
| The physical projection schema: columns, keys, constraints, indexes and the Django model (including the `projection_revision` column definition and whether it is indexed) | Phase 4 |
| The unique constraint realising the serving row identity that GM6 depends on | Phase 4 |
| The concrete no-op comparison technique (column-wise `IS DISTINCT FROM`, a comparison tuple, hash-plus-exact-fallback) | Phase 4, bounded by NO1–NO7 |
| Batch sizes, chunking, throttling and the concrete locking statement | Phase 4, bounded by BL1–BL8 |
| Local retry attempt counts, backoff seconds and jitter widths | Phase 4 / operations, bounded by RT1–RT7 |
| In-place vs build-then-swap for full rebuild, and the swap's fence/catch-up implementation | Phase 4, bounded by RB6–RB9 |
| Tombstone retention and the fenced tombstone-collection procedure | Phase 4, bounded by LF6, LF7 |
| The fenced-repair mechanism, CLI, permission model, audit storage and runbook | Phase 4 / operations, bounded by RC5, RC6 |
| Reconciliation cadence, sampling strategy, checksum shape and drift thresholds | Phase 4 / operations |
| Whether a Phase 4 implementation wraps a batch's source reads in one database snapshot, and the isolation level of the guarded write | Phase 4, bounded by CB6, BL7 — never the safety argument |
| Metric names, thresholds, dashboards, alert severities and runbook contents | operations, bounded by OM1–OM9 |
| The numeric projection-freshness threshold and its alert | operations (item 6 CM8) |
| Every `event_type`, payload schema and `schema_version` for projection triggers, and each consumer's registry declarations | item 8 + each owning module's phase, bounded by TR5 |
| Failure-domain routing per projection consumer | item 9 (already frozen: `core.projection.incremental` / `core.projection.rebuild`) |
| Batch selector signatures in `<domain>.public` needed by the builder | each owning domain's phase, bounded by R3, BP3 |
| Whether an analytics source is ever admitted | **item 13** (untouched here; FS5) |
| The MVP/later cut per module | **item 14** (untouched here) |
| A per-source partial merge / field-to-source decomposition | a new ADR (CB4, V115) |
| The concrete fence mechanism for a generation boundary — how observations of the old structure are drained or invalidated (a quiesced domain, a drained worker set, an atomic structural swap, or another Phase 4 device satisfying RV8a) | Phase 4 / operations, bounded by RV8a, RB6, RC5, LF6 |
| How an owning module exposes an authoritative-read capability to the builder — a routing hint, a selector variant, a module policy, or simply the platform default | each owning domain's phase / Phase 4, bounded by CB10–CB13; no Django database alias or selector signature is chosen in Phase 0 |
| The platform-wide read-replica decision | **item 15** (untouched; CB13 constrains only the projection builder's source-read path) |
| Any change to RV1–RV12 (RV8/RV8a/RV8b included), OB1, CB10–CB14, GM1–GM10, CB4, NO1, LF2, RB6/RB7 or GM8 | a new ADR superseding ADR-0014 |

---

## 31. Acceptance checklist

- [x] 1. A stale writer can never regress a newer serving row (§27.1, C128).
- [x] 2. Independent price and inventory changes converge to both effects (§27.3, C129).
- [x] 3. The design does not rely on broker ordering (§27.6, R10).
- [x] 4. The design does not rely on `schema_version` (SE1, A87).
- [x] 5. The design does not rely on `EventId`/UUIDv7 ordering (SE2, A88).
- [x] 6. The design does not rely on timestamps as last-writer-wins (SE3, UD2, A89).
- [x] 7. The design does not rely on an Outbox row id (SE4, A90).
- [x] 8. No source domain learns about the projection (R1, item 6 O2; the builder asks for facts, never revisions).
- [x] 9. No projection-specific version is added to a domain table (R7, A86, V104).
- [x] 10. Only `application/storefront` owns the guard state (RV4, A92, A93).
- [x] 11. Guard failure has explicit discard/rebuild semantics (GM4, GM7, RT3).
- [x] 12. Retry is bounded and escalates into item 9's existing machinery (RT1, RT2).
- [x] 13. Duplicate delivery is safe (NO1, TR7, C131).
- [x] 14. A duplicate/no-change trigger keeps no-op suppression, writing nothing at all (NO1–NO3, UD3).
- [x] 15. An old replay cannot regress state (RY1, RY2, C142).
- [x] 16. A withdrawal cannot be resurrected by a late worker (LF2, LF4, C132).
- [x] 17. A genuine later reactivation works (LF5, C133).
- [x] 18. The insert race converges with no business error (GM5, C134).
- [x] 19. Incremental vs incremental converges (§27, C128, C138).
- [x] 20. Incremental vs rebuild converges (RB1, RB2, C136).
- [x] 21. Build-then-swap without catch-up is forbidden (RB6, RB7, V106).
- [x] 22. A full rebuild requires no event history **and no retained token history** (RB4, RV8a, §27.4, C137).
- [x] 23. Reconciliation does not bypass the guard (RC1, RC2, C144).
- [x] 24. Token corruption has a fenced rebuild recovery (RC4, RC5, OV4).
- [x] 25. Multi-language rows converge together (ML1, ML6, C139).
- [x] 26. Batch overlap does not require a global lock (BL3, BL4, C138).
- [x] 27. A future source can be admitted deliberately with no token change (FS1–FS4).
- [x] 28. The token is never public DTO or API data (RV9, SE9, A95, V112).
- [x] 29. The token never affects checkout, pricing, reservation or authorization (SE7, SE8).
- [x] 30. `updated_at` is not the freshness token (UD1–UD4, A89, V111).
- [x] 31. Item 13 remains TODO; no analytics state is created (FS5).
- [x] 32. Item 14 remains TODO; no MVP/later cut is made.
- [x] 33. No code, package, model, migration, task, event class or dependency is created (§1.2).
- [x] 34. The ADR need was evaluated explicitly and ADR-0014 was written for the four decisions that depart from master text (§1.3, §1.4).
- [x] 35. No contradiction with ADR-0001…ADR-0013 (§32 row 14).
- [x] 36. Token non-reuse and projection disposability are simultaneously true: non-reuse is scoped to a generation (RV8), a reset is legal only behind a fence that invalidates every prior observation (RV8a), and no token history, epoch column or backup obligation is introduced (RV8b, RV12, §27.4).
- [x] 37. The proof's authoritative-read premise is explicit, not hand-waved: `view`/`vp` are defined, `obs(W) < vp(W, S)` is stated as a premise, and CB10–CB13 forbid a cache, a lagging replica or an early snapshot from satisfying it (§27 Setup, §11.1).
- [x] 38. The proof concerns state-visibility chronology, not value trajectory: `100 → 120 → 100` is convergence, not regression (CB14, §27.3).
- [x] 39. CB13 does not pre-empt item 15's read-replica decision and requires no domain to know it is projected.
- [x] 40. The per-product guard unit and the bounded-batch write transaction are reconciled without weakening the all-or-nothing rule for one product's language rows (ML1, ML3, GM3, BL3a, BL9).
- [x] 41. No claim survives that different products never share a transaction, a lock or a technical failure (ML3, BL3a, BL9, V118).

---

## 32. Self-review record

| # | Check | Result |
|---|---|---|
| 1 | Is one scalar version compared across unrelated source counters anywhere? | Pass — no. PR1 states the incomparability, §6.1 rejects the model with its four failing questions, and RV6/RV7 make ordered and cross-row comparison of the token illegal outright. `max()` over per-domain counters is rejected by name in §5. |
| 2 | Does anything assume messages normally arrive in order? | Pass — §27.6 tabulates the assumptions deliberately not made; the safety proof uses exactly three things — OB1 read as CB10's visibility-point ordering, per-row CAS atomicity, and RV8's within-generation non-reuse. R10 and item 8 OR1–OR4 are inherited unedited. |
| 3 | Is timestamp LWW present under any spelling? | Pass — `occurred_at`, `updated_at`, `NOW()`, clock readings and renamed equivalents are forbidden as guard inputs (SE3, UD2, OS2, A89, V111). UD3 removes the temptation by making a no-op leave `updated_at` alone, and NO5/UD4 move lag measurement to the trigger pipeline. |
| 4 | Is UUID/`EventId` ordering used? | Pass — SE2, A88, V112's neighbours; item 11 TS4/MI7 and ADR-0013 are restated by reference, not reopened. |
| 5 | Is an Outbox/Inbox PK or sequence assumed to equal commit ordering? | Pass — SE4 and A90 forbid the row id; §5 rejects pre-commit sequence values, `xid`, LSN, commit timestamps and `xmin` **each with its own reason**, and §7.1 shows the inversion concretely rather than asserting it. |
| 6 | Is an event payload used as a complete projection snapshot? | Pass — TR1/TR2 fix the payload's role as a dirty-identity set, CB1 makes the candidate a full rebuild, A96 is the static check and V109 the review check. Item 6 UP8 is applied, not weakened. |
| 7 | Is a version column added to a domain table for the storefront? | Pass — R7, A86, V104. §6.2 rejects Candidate B partly *because* it would require exactly that, and §6.3 records that the selected model asks domains for facts, never revisions — so item 6 O2 stays true in substance, not only in letter. |
| 8 | Is there a global lock around projection updates? | Pass — BL4 forbids it by name; BL2/BL3 give per-product scope with deterministic key order; C138 asserts that unrelated products do not serialize; V107 is the review check. |
| 9 | Is the CAS loop unbounded? | Pass — RT1–RT7 freeze bounded local retries with jitter, then re-coalescing, then item 9's existing TF-A machinery. C141 asserts it; V108 is the review check. Item 12 invents no new retry subsystem. |
| 10 | Does a rebuild bypass the guard? | Pass — RB1 makes rebuild use the identical protocol, RB2 makes its candidate losable, GM8 removes every force path, RC2 binds the reconciler, and C136/C144 assert both. §7.3 records that a producer-token design *cannot* have this property, which is one of the reasons it was rejected. |
| 11 | Is a rebuild swap allowed without catch-up? | Pass — RB6 freezes the three requirements (fence point, catch-up, observation invalidation) plus RV8 preservation; RB7 forbids the naive shape by name; failure-matrix row 13 records it; V106 is the review check. The final swap mechanism stays Phase 4, as item 6 RB6/RB8 require. |
| 12 | Can a stale visible candidate resurrect a withdrawn product? | Pass — LF2 makes withdrawal a forward content change that advances the token, LF4 gives the two-case argument, C132 asserts it. LF3 records honestly that this narrows item 6 LC2's latitude for the update path, states the concurrency reason, and confirms LC1/LC3/LC8 are unchanged. |
| 13 | Does a duplicate event rewrite an unchanged row? | Pass — NO1–NO3 and the pseudo-SQL's `IS DISTINCT FROM` clause; RV5 keeps the token still; NO4 explains why a no-op is never confused with a guard miss; C131 asserts zero writes, unchanged token and unchanged `updated_at`. Item 6 BP4/C35 and master `# 22.1`'s no-op guard are preserved, not weakened. |
| 14 | Contradiction with ADR-0001…ADR-0013? | Pass — **0001/0002:** untouched; no identity, SKU or EAV rule changes. **0003:** R7/A86/V104 keep every storefront version off catalog, which is ADR-0003 §3's positive form. **0004:** the mechanism lives entirely in one application module and enters no domain transaction (OB8, item 6 CM2). **0005:** no port, no new import edge, no matrix cell, no `core` allowlist entry (§29.1); `application/storefront` still imports no other application module (SI6). **0006:** no `core` primitive is added or extended; a guard miss is not a business error and requests no error category (GM4). **0007:** SE7/SE8 keep this out of the placement transaction entirely; item 5 C21 stands. **0008:** this is the mechanism ADR-0008 deferred; the projection stays derived, rebuildable, non-authoritative and single-writer. **0009:** SE1 and A87 restate OR6; item 8 is neither edited nor cited as authority — OR7 explicitly handed this decision here. **0010:** RT2, RY3, RY8 and BL8 use item 9's failure taxonomy, replay authority and both projection domains exactly as written; no queue, routing value or terminal state is defined. **0011:** SE5; no trace field is read, written or added. **0012:** untouched. **0013:** SE2, A88. |
| 15 | Is the departure from master text stated openly rather than smuggled? | Pass — §1.3 names the four failures, §1.4 tabulates every master statement as preserved / refined / departed, and §7 works all three failing cases in full. ADR-0014 records the decision. Master `# 5` principle 36's *requirement* is preserved verbatim in effect; only its illustrative mechanism changes. |
| 16 | Are all five things item 6 §16.2 deferred actually decided? | Pass — **name/type/cardinality:** RV1–RV3. **generation + monotonicity argument:** RV4, RV5, RV8/RV8a's generation scoping, and §27.1's Lemma 1/Lemma 2 over `vp`. **per-source mapping:** §6.2's rejection plus TR1–TR5 — the answer is that no per-source mapping is needed, stated as a decision rather than an omission. **the SQL guard:** §26. **PU5 in the guard:** §27.3. |
| 17 | Does the proof depend on anything the architecture cannot deliver? | Pass — it needs OB1/CB10 (a visibility-point ordering the writer controls, satisfied by the platform's default consistent reads on Primary), an atomic compare-and-set on one row (a PostgreSQL guarantee), a unique key on the row identity (GM6, Phase 4), RV8's within-generation non-reuse with fenced resets (RV8a, an operational obligation Phase 4 must meet), and R16's write-fact-and-trigger-in-one-transaction (already frozen). It needs no isolation level (BL7), no cross-domain snapshot (CB6), no clock, no ordering guarantee from the transport and no retained token history (§27.4). |
| 18 | Is the liveness claim honest about its limits? | Pass — §27.2 states that case (c) is bounded and that on exhaustion convergence depends on an operator replay or reconciliation, both of which run the same protocol. It does not claim unconditional convergence in the presence of a permanently failing consumer; item 9's terminal state and alert are the honest answer there, and failure-matrix rows 7 and 24 record it. |
| 19 | Did item 12 quietly consume item 13 or item 14? | Pass — FS5 states that no analytics state, column, signal or trigger is created and that item 13 owns the decision; §30 lists both as untouched; no MVP/later judgement appears anywhere. |
| 20 | Does anything here create code, schema or infrastructure? | Pass — §1.2 states it; §26 is labelled architecture notation with no final column set; §30 routes the model, columns, indexes, constraint, batch sizes, retry numbers, swap mechanism, fence tooling, metrics and thresholds to Phase 4 or operations. |
| 21 | Can RV8, RV12 and §27.4 all be true at once? | Pass — they could not in the first draft, and the contradiction was real: RV8 asserted non-reuse "including across physical deletion, full rebuild and swap" while §27.4 rebuilt from empty at `1` and RV12 called the token disposable. The fix scopes non-reuse to a **projection generation** (RV8) and admits reset **only** behind a fence that drains or invalidates every prior observation (RV8a), explicitly rejecting the alternative fix of retained token maxima, a durable epoch column or a backup obligation (RV8b). §27.4 now states both halves and shows why they compose; LF6, RB6 and RC5 are aligned; failure-matrix rows 13, 14 and 19 carry the generation vocabulary; C137 and the new C147 assert both directions, including the negative case that an unfenced delete-and-recreate *does* let a stale writer through. |
| 22 | Does the proof still hand-wave the source-read premise? | Pass — it did: "sources are append-only because committed facts stay committed" proves nothing about where a `<domain>.public` selector's bytes came from. §27's Setup now defines `view(W, S)` and its visibility point `vp(W, S)`, states `obs(W) < vp(W, S)` as an explicit premise, and Lemma 2 is restated as visibility-point domination with a superset conclusion. §11.1 freezes the premise as a contract (CB10–CB14): no candidate field from a cache, a lagging replica or a snapshot opened before the observation; a cache may accelerate but not finalize; a post-observation snapshot is admissible and improves coherence. A99, A100, C145, C146, V117 and failure-matrix rows 26 and 27 enforce it. §27.2 records that this premise protects **convergence** specifically — a cache warmed before the change would satisfy call ordering and still miss the fact. |
| 23 | Does CB10 quietly decide item 15's read-replica question, or make a domain projection-aware? | Pass — CB13 states both negatives explicitly: the constraint is scoped to the projection builder's source-read path, the platform default (consistent reads on Primary, replica by explicit opt-in) already satisfies it, and item 15's platform-wide decision is untouched. The builder still calls ordinary legal `<domain>.public` batch contracts; how an owning module exposes an authoritative-read capability is deferred to that domain's phase and Phase 4, with no Django alias and no selector signature chosen here (§30). |
| 24 | Is the per-product/batch contradiction resolved without weakening ML1? | Pass — the first draft asserted both "different products never share a transaction, a lock or a failure" (ML3) and a single `WHERE product_id = ANY(...)` batch transaction. ML3 now separates the **logical guard unit** (the product) from the **physical write transaction** (the bounded batch), keeps the true claim (no freshness or ordering relationship between products) and drops the false one; GM3 says the shared transaction is a container and not a shared guard; BL3 is restated as semantic contention with BL3a covering lock waits honestly; BL9 names the technical abort as a retry coupling inside one unit of work; the pseudo-SQL, C138, the new C138a and failure-matrix rows 21 and 25 follow. **ML1's all-or-nothing rule for one product's language rows is unchanged**, as is ML6's no-permanent-split property. |
| 25 | Did the correction change any selected decision? | Pass — no. Candidate C, the dirty-identity trigger, whole-candidate rebuild, the rejection of producer `source_version`, the name `projection_revision`, the 64-bit type, per-serving-row cardinality, equality-only CAS, observe-before-read, no source read inside the guarded write, no-op suppression, the ban on partial merges, bounded retry, replay semantics, withdrawal-as-not-visible, reactivation, reconciliation through the normal guard, the absence of a force path, domain blindness, the DTO/checkout exclusions and items 13/14's TODO status are all unchanged. The corrections made three statements consistent and one proof premise explicit; they selected nothing new. |

Verdict: **PASS**.
