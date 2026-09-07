# ADR-0008 — `ProductListingProjection`: an `application/storefront`-owned derived serving read model with same-variant facet correctness

- **Status:** Accepted — Frozen
- **Date:** 2026-09-04
- **Phase:** 0 — Architecture Freeze
- **Supersedes:** —
- **Related:** [ADR-0001](0001-product-vs-sku-sellable-unit.md), [ADR-0002](0002-typed-eav-source-of-truth.md),
  [ADR-0003](0003-catalog-boundary-vs-storefront-projection.md),
  [ADR-0004](0004-four-layer-modular-monolith.md), [ADR-0005](0005-dependency-and-integration-wiring.md),
  [ADR-0007](0007-place-order-atomic-idempotent-boundary.md),
  [Phase 0 item 6 artifact](../architecture/phase-0/06-storefront-listing-projection.md),
  master `# 7.2`, `# 7.6`, `# 10`, `# 20.2`, `# 22.1`, `# 22.2`, `# 22.5`

## Context

ADR-0003 §3 decided where `ProductListingProjection` does **not** live: not in `domains/catalog`,
which also gains no `source_version`, no facet index and no denormalized price, stock or rating.
ADR-0004 §4 repeats the placement in one sentence; ADR-0005 §7 mentions the projection only as an
example of application-owned ORM. Master `# 7.6` sketches the row and its builder, `# 10` the filter
and pagination path, `# 22` the query contract.

What no accepted decision covers is what the projection **is** as a contract — and four questions
have to be answered before Phase 4 writes a model, because each of them is expensive to reverse:

1. **Same-variant filter correctness.** Master `# 7.2` stores discrete facets as one product-level
   union array, `facet_choice_ids`, queried with `@>`. For product-scope attributes the union is
   exact. For variant-scope attributes — every variant axis, by ADR-0002 §2 — it is silently wrong: a
   product with `(red, M)` and `(blue, L)` variants has `{red, blue, M, L}` in its union and would
   match `color=red AND size=L`, which no sellable SKU satisfies. This is a correctness defect that
   presents as "the grid shows products that vanish when you open them", and it cannot be fixed later
   without a schema change to the hottest table in the system.
2. **Whether the projection is truth.** Once several domains' facts sit in one row, the row starts
   looking authoritative — for a badge, for a price, eventually for a checkout decision.
3. **Whether the projection must be rebuildable from OLTP**, or may become event-sourced state whose
   history lives in Outbox partitions that master `# 20.5` archives and drops.
4. **What happens on a miss.** The natural incident-time fix — "if the row is missing, just join
   catalog + pricing + inventory for this request" — reintroduces exactly the bottleneck the
   projection exists to remove (master `# 22.1`), under exactly the load that caused the incident.

Alternatives considered and rejected: a **variant-grained serving row** (exact facets for free, but
`LIMIT` no longer returns a known number of products, cursors become ambiguous at a page edge where
two variants of one product straddle it, facet counts double-count, and every card field is
duplicated per variant on the highest-write-amplification table); **post-pagination grouping** of
variant rows (unstable page sizes and ordering — the same defect one step later); **keeping the union
array and accepting false positives** (a visible correctness bug, and one that grows with catalog
depth); and **leaving the whole question to Phase 4** (the schema would be written first and the
semantics argued afterwards).

## Decision

### 1. `application/storefront` owns the projection, positively and exclusively

`ProductListingProjection` is owned by `application/storefront`, which owns projection persistence,
the build/update/rebuild/reconcile use cases, the storefront selectors, filter/sort/pagination
compilation, consistency behaviour, and the projection's own indexes. It is **internal** to the
module (ADR-0005 §7); `public.py` is the only importable surface.

No domain owns, writes or knows about it — a domain does not know it is projected. Neither
`core`, `interfaces/*`, `integrations/*`, `tasks/*` nor a shared "read models" package may own or
write it. Every input is read through `<domain>.public` DTOs; `application/storefront` imports no
other `application` module and declares no outbound port.

### 2. Three truths, and the projection is only the middle one

- **OLTP/domain truth** stays with catalog, pricing, inventory, promotions and reviews.
- **Storefront serving source**: the projection is the primary PostgreSQL serving source for
  listing/search/filter/sort requests. Web and API do not rebuild cards from OLTP per request.
- **Commercial transaction truth**: checkout never treats the projection as authoritative for price,
  discounts, coupon validity, stock, reservation, payment or final sellability. `place_order`
  revalidates through owning domains (ADR-0007, item 5 PR2/INV3/C21).

The projection is a **derived serving read model**: every field is a copy or computation over another
module's authoritative state, no field is written back into a domain as truth, and no authorization,
consent or entitlement decision reads it. A stale projection may display stale information; it must
never make a commercially incorrect `Order` possible.

### 3. Grain: one row per `Product × Language`, with a per-variant satisfier structure

The serving row is `Product × Language` (confirming master `# 7.6` and ADR-0003 §3), and that is also
the visible, ordered and paginated grain. Grouping to that grain happens at **build** time, never
after pagination.

Matching semantics are frozen as **existential over one sellable variant**:

> A row matches a filter set iff the Product satisfies every product-scope predicate **and there
> exists at least one sellable variant satisfying all variant-scope predicates simultaneously.**

To make that exact, a serving row carries — in addition to any product-level union — a **per-variant
satisfier structure**: one entry per sellable variant holding that variant's own variant-scope values,
with grouping preserved rather than flattened. Every variant-scope predicate (choice, boolean, range,
price, availability) compiles against that structure; the union array serves product-scope predicates,
and for a variant-scope facet it may act **only as an over-inclusive candidate prefilter that the
same-variant satisfier predicate must then confirm exactly** — `union prefilter → exact satisfier
predicate → count/match`, never a count or a match taken directly off the union. Row-level aggregates
(`min/max` price, `in_stock`) remain for sorting
and display and may never answer a same-variant conjunction. Only sellable variants produce entries.
A variant-scope range attribute is either carried per variant or declared display/comparison-only; a
product-level column alone is not admissible for it.

The predicate must be answerable by a single indexable containment/semi-join within the listing query
budget. The physical encoding is Phase 4's choice between an in-row nested structure (`jsonb` +
`jsonb_path_ops` GIN, `@>`) and a companion variant-grain relation inside `application/storefront`
used **only** as an `EXISTS` semi-join — never as the ordered or paginated row source.

This refines master `# 7.2`'s union-array representation; it does not replace the union array for the
cases where a union is exact.

### 4. Eventual consistency, full rebuildability, and no OLTP fallback

The projection is eventually consistent with OLTP truth and is never written inside a domain's
transaction. Updates flow `domain transaction + Outbox → relay → projection queue → thin task →
application/storefront update use case → guarded set-based upsert`; the **update owner is
`application/storefront`**, batch/coalesced events are preferred over one event per row, and event
names and schemas remain item 8's.

The projection **must be completely rebuildable from authoritative OLTP state** through
`<domain>.public`. It is not event-sourced: no event history is required to reconstruct it, so an
archived Outbox partition can never make it unreconstructible. Full rebuild, targeted rebuild by
source identity, and periodic count/checksum reconciliation all exist; a rebuild must reproduce the
same serving state as the incremental path, and divergence is a defect in the update path.

The updater must be safe under duplicate delivery, retry and reordering, and **a stale update must
never overwrite newer projected state**. The mechanism — `source_version` type, generation, per-source
mapping and the guarded upsert SQL — is **Phase 0 item 12's**, not this ADR's, and it is a different
mechanism from ADR-0007's owner-defined checkout freshness guard: one protects a derived serving row
against out-of-order asynchronous writes, the other protects a durable commercial write against stale
prepared reads. No `source_version` or other read-model state appears on a domain table (ADR-0003 §3).

A source object that stops being storefront-eligible must disappear from every serving surface —
listings, facet counts, search, cursors — after convergence. Whether that is a physical delete or a
non-visible state is an implementation choice; serving selectors filter on an explicit **positive**
visibility predicate, and source-domain audit and history are untouched.

**A projection or cache miss must never cause a synchronous OLTP reconstruction inside the request.**
The admissible hierarchy is cache → PostgreSQL projection → a controlled stale cached result where the
master already permits one. A missing row means "not currently listable"; repair happens outside the
request path. Exceeding the operational freshness threshold is an alertable fault, never a licence to
fall back to cross-domain joins.

Redis, fragment caches and the CDN are disposable accelerators: a full flush must leave PostgreSQL
able to serve the storefront.

### 5. One read path, public data only

`projection → application/storefront selector → immutable DTO → HTML or JSON`. Web and API consume
the same semantic result; no transport-specific query path may bypass the selector. No ORM object,
QuerySet, manager, `Paginator`/`Page`, cache client or search-vector type crosses `public.py`. The
projection declares no ORM relation to any domain model — source identities are copied scalars, so
deletion propagates through the update path rather than a cascade, and internal bigints stay internal
(travelling outward only inside a signed opaque cursor).

Every public listing sort compiles to row-level scalars ending in a deterministic tie-break key; deep
listing paths use keyset pagination. PostgreSQL (projection + FTS + `pg_trgm` + GIN) is the MVP search
engine; OpenSearch stays behind master `# 10.8`'s measurement gate and a future ADR.

**Filtered-price semantics are deferred, not decided by the sort.** The product-wide projected price
sort key remains the legal baseline, including under an active variant-scope filter. Whether such a
filter changes the *effective* price — for card display, for the price sort key and for cursor
construction — is a deliberate storefront contract decision, taken jointly for all three before Phase
4. Coherence is frozen even though the policy is not: if the card ever shows the price of a variant
satisfying the filter, the sort key and the cursor may not silently keep ordering by a non-matching
variant's price. Item 7 may define the card's price representation but may not redefine listing sort
semantics on its own. No mechanism is mandated now — no dynamic aggregation, no matched-variant
sorting, no new column, no new satisfier encoding.

Popularity uses only master `# 10.7`'s approved first-party signals until item 13 decides otherwise.
**A manual merchandising boost is never owned by the projection and is never stored only as serving
state**: it must have a durable authoritative source with an explicit owner, reachable from
`application/storefront` under the frozen dependency graph, and the projection only copies or derives
it so that a rebuild reproduces it. This ADR assigns no such owner and invents no domain or
application state for it; **until an owner is assigned, manual boost is disabled** rather than stored
in the serving row. The general form of the rule: every *enabled* facet, sort key and search field
must be reproducible from authoritative state.

The projection contains **public storefront-serving state only** — no cart, customer identity, private
entitlement, order data or consent/security records — and a future personalized read model is a
separate artifact with its own ownership, security design and ADR.

**Out of scope of this ADR:** the physical schema, columns, indexes and Django model (Phase 4); which
satisfier encoding is chosen; `ProductCard`/`Facet`/`Badge` DTO fields (item 7); event names and
schemas (item 8); `source_version` and its guard (item 12); `Money`/`PublicId` (item 11); cursor
codecs, cache keys, batch sizes, numeric query budgets and the freshness threshold; the filtered-price
policy; and the authoritative owner of the manual merchandising boost.

## Consequences

**Positive**

- A grid filter can no longer promise a product that no sellable SKU satisfies; the defect is closed
  in the representation rather than in each query author's memory.
- The storefront has one owner, one read path and one serving source, so a mobile client or a new
  surface cannot create a second unoptimised catalog query path.
- The projection stays disposable: it can be dropped, rebuilt or re-shaped without an OLTP migration,
  without a backup obligation and without commercial risk.
- Checkout correctness is independent of storefront freshness, so a projection incident degrades
  display only — every row of the item 6 failure matrix has `None` commercial impact.
- Forbidding the request-time OLTP fallback removes the failure mode where a storefront incident
  becomes a database incident.
- Domains stay ignorant of the read model, so a projection redesign touches one module.

**Negative / accepted cost**

- The satisfier structure is more storage and more build work than a single union array, and one more
  concept for every future facet. Accepted: it is the price of a correct multi-facet filter over
  variant-scope attributes, and it is paid at build time, not per request.
- Product-grained rows mean the card's aggregate price and availability are not statements about the
  variant that matched a filter. The filtered-price policy is therefore a deferred decision that must
  be taken for display, sort key and cursor together — the grain does not resolve it, and the baseline
  can order a product by a price that the active filter excludes.
- Requiring an authoritative owner before a manual boost may sort means merchandising cannot be
  switched on by typing a number into the read model. Accepted: the alternative is a sort key that a
  rebuild silently erases.
- Full rebuildability constrains what may be stored: nothing whose value originates in the projection.
  A derived-only rule occasionally forces a fact into a domain contract that "could" have been
  computed in the builder.
- Eventual consistency makes stale display a normal state, which needs a freshness metric, a threshold
  and a runbook rather than an intuition.
- Refusing the request-time fallback means a missing row is a visible absence rather than a slow page.
  Accepted: the alternative is unbounded load at the worst moment (master `# 22.1`).

**Enforcement**

- **Phase 1** extends the CI checks with A29–A35 (no cross-boundary ORM relation from a storefront
  model, no projection write outside the owner, no ORM/paginator/cache type across `public.py`, no
  projection reference or two-domain listing composition in `interfaces/*`, no dynamic
  filter/order-by, no rebuild call from an interface, no unshaped serving `SELECT *`).
- **Phase 4** implements C24–C36 as behavioural/contract tests — in particular C24 (no cross-variant
  false positive), C25 (no OLTP table touched by a listing request), C26 (rebuild reproduces serving
  state), C27 (monotonic convergence, mechanism from item 12), C28 (no fallback on a miss), C29 (cache
  loss survivable), C30 (withdrawal convergence), C31 (deterministic pagination), C32 (Web/API
  parity), C33 (query budget), C34 (public data only), C35 (no N+1 in batch updates) and C36 (facet
  counts agree with the grid, the union prefilter having been confirmed exactly). C26 additionally
  covers every enabled sort input, so a manual boost either survives a rebuild or is not enabled.
- Item 5's C21 already asserts from the checkout side that placement outcomes are unchanged with the
  projections stale or emptied.
- V27–V38 are review-checklist items carried in §25.4 of the
  [item 6 artifact](../architecture/phase-0/06-storefront-listing-projection.md); anything proposed
  against them needs a new ADR.
- This ADR moves **no** dependency-matrix cell and **no** `core` submodule allowlist: L1–L21 stand
  unedited.
