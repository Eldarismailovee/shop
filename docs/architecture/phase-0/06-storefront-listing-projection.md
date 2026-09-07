# Phase 0 — Item 6: `application/storefront` ownership and contract of `ProductListingProjection`

- **Status:** DONE / FROZEN
- **Date:** 2026-09-04
- **Phase:** 0 — Architecture Freeze
- **ADR:** [ADR-0008](../../adr/0008-storefront-listing-projection.md) — required, accepted
- **Related:** [ADR-0001](../../adr/0001-product-vs-sku-sellable-unit.md),
  [ADR-0002](../../adr/0002-typed-eav-source-of-truth.md),
  [ADR-0003](../../adr/0003-catalog-boundary-vs-storefront-projection.md),
  [ADR-0004](../../adr/0004-four-layer-modular-monolith.md),
  [ADR-0005](../../adr/0005-dependency-and-integration-wiring.md),
  [ADR-0006](../../adr/0006-public-contract-primitives.md),
  [ADR-0007](../../adr/0007-place-order-atomic-idempotent-boundary.md),
  [item 2](02-four-layer-architecture.md), [item 3](03-dependency-matrix.md),
  [item 4](04-domain-public-contract.md), [item 5](05-place-order-use-case.md),
  master `# 7.2`, `# 7.6`, `# 8.2`, `# 9.1`, `# 10`, `# 20.1`, `# 20.2`, `# 22.1`, `# 22.2`,
  `# 22.4`, `# 22.5`, `# 22.7`

---

## 1. Purpose

### 1.1 What this item freezes

`ProductListingProjection` is the **primary PostgreSQL serving read model** of the storefront
listing, search, filter and sort pages, owned by `application/storefront`. This item freezes:

- the single owner and the enumerated forbidden homes (§4);
- the three-way split of "truth" — OLTP/domain truth, storefront serving source, commercial
  transaction truth — and the rule that the projection is **never** checkout truth (§5);
- the projection **grain**: one row per `Product × Language`, and the existential matching rule plus
  the per-variant satisfier structure that makes same-SKU attribute predicates correct and
  cross-variant false positives structurally impossible (§6);
- projection **identity**: copied scalar source identifiers, no cross-boundary ORM relation, no
  internal bigint as a public locator (§7);
- the **categories** of denormalized serving data the row may carry, and the rule that copied data
  never becomes owned business truth (§8);
- the **facet** strategy: typed EAV stays the source of truth, listing facets are derived serving
  structures with a per-scope representation rule (§9);
- **PostgreSQL** as the MVP search engine, with search fields as derived serving mechanics (§10);
- **deterministic sorting** with a mandatory final tie-break key, the product-wide price-sort
  baseline, the deferral of filtered-price semantics with a frozen display/sort/cursor coherence
  rule, and the rule that no sort input (manual merchandising boost included) may exist only as
  serving state (§11);
- **keyset pagination** at the visible-result grain, with grouping performed at build time and never
  after pagination (§12);
- the single shared **read path** `projection → application selector → immutable DTO → HTML/JSON`,
  and the no-ORM public boundary of `application/storefront` (§13, §20);
- the two **update modes** — incremental (Outbox → async → projection-update use case, owned by
  `application/storefront`) and full/targeted **rebuild + reconciliation** (§14, §15);
- the **stale-update correctness requirement** — an older update may never overwrite newer projected
  state — while leaving the `source_version` mechanism entirely to item 12 (§16);
- **lifecycle convergence**: a source object that is no longer storefront-eligible must disappear
  from serving results (§17);
- the **eventual-consistency** model and its correctness boundaries (§18);
- **no synchronous OLTP fallback** on a projection/cache miss (§19);
- **cache disposability**: a full cache flush leaves PostgreSQL able to serve the storefront (§20.1);
- the **query-budget** and **batch-rebuild** architecture contracts (§21, §22);
- the **failure matrix** (§23), the **public-data-only** rule (§24), and the checks later phases must
  implement (§25).

### 1.2 What this item does **not** do

No Python package, Django model, migration, index, management command, cache key, event schema or
production code is created here. Specifically **not** designed:

- final `ProductCard` / `Facet` / `Badge` DTO fields — **item 7**;
- `source_version` generation and the guarded upsert SQL — **item 12**;
- event names, payload schemas, versions and the registry — **item 8**;
- queue/failure-domain matrix and DLQ policy — **item 9**;
- trace fields in Outbox/Inbox — **item 10**;
- `Money` / `PublicId` implementation — **item 11**;
- the popularity source model beyond what master `# 10.7` already permits for MVP — **item 13**;
- the physical projection schema, column list, index list and Django model — **Phase 4**;
- OpenSearch, read replicas, a personalized/private price read model, an analytics view pipeline —
  deferred by master `# 10.8`, `# 22.8` and the MVP scope rule.

### 1.3 Why ADR-0008 is required

ADR-0003 §3 states the projection's home **negatively**, from `catalog`'s side: catalog does not own
it, does not carry `source_version`, and carries no facet index. ADR-0004 §4 repeats the placement in
one sentence. ADR-0005 §7 lists `ProductListingProjection` only as an example of application-owned
ORM. None of them decides what the projection **is** as a contract.

Item 6 makes four decisions that are new and binding, not restatements:

1. **Existential variant matching and the per-variant satisfier structure** (§6.4). Master `# 7.2`
   freezes a product-level `facet_choice_ids` union array. A union is *correct* for product-scope
   attributes and *silently wrong* for a conjunction of two variant-scope predicates. This item
   refines the master's representation, which the ADR index's own trigger list — "a read model or
   projection strategy changes" — puts under an ADR.
2. **Derived-serving classification with eventual consistency as a frozen property** (§5, §18),
   including the rule that no security or private-authorization decision may read this projection.
3. **Full rebuildability from OLTP truth**, with events as an acceleration mechanism and never the
   historical source of record (§15).
4. **No synchronous OLTP fallback** on a projection or cache miss (§19), which forbids the single
   most natural "temporary" fix a developer will reach for during an incident.

ADR-0008 records these. It moves **no** dependency-matrix cell and **no** `core` submodule allowlist:
`application/storefront` → `<domain>.public` is already `PUBLIC ONLY`, `application/*` → `core` is
already `ALLOW`, and application-owned ORM internal to its module is already ADR-0005 §7. L1–L21
stand unedited.

---

## 2. Frozen principles inherited from ADR-0003 / ADR-0004 / ADR-0005 / items 2–5

These are not re-decided here; every rule below is written to be consistent with them.

| # | Inherited rule | Source |
|---|---|---|
| R1 | Dependencies point down only; `interfaces → application → domains → core`, skipping downward is legal. | ADR-0004 §1 |
| R2 | Domains are mutually invisible; a domain never imports another domain, not even its `public.py`. | ADR-0004 §3, R4 of item 5 |
| R3 | Any operation touching two or more domains has exactly one owner in `application/`. | ADR-0004 §4 |
| R4 | `ProductListingProjection` and the storefront read model belong to `application/storefront`. | ADR-0003 §3, ADR-0004 §4 |
| R5 | `application/<a>` reaches domains **only** through `<domain>.public` with frozen DTOs; no ORM instance or QuerySet crosses. | item 3 §4.3, item 4 §6 |
| R6 | Application-owned ORM is internal to its module, exactly as domain ORM is internal to its domain; `public.py` is the only importable surface. | ADR-0005 §7 |
| R7 | Application→application imports are forbidden with no MVP exception. | ADR-0005 §7 |
| R8 | `catalog` carries no price, stock, ERP identity, popularity, rating, facet index or `source_version`. | ADR-0003 §1, §3 |
| R9 | Typed EAV is the source of truth; `AttributeDefinition.scope ∈ {product, variant, both}` and `is_variant_axis` are catalog-owned facts. | ADR-0002 §2 |
| R10 | The SKU (`ProductVariant`) is the only sellable unit; price, stock, reservation, cart and order lines point at the SKU. | ADR-0001, master `# 7.1` |
| R11 | Internal bigint PKs never become user locators, public API payload identifiers, external integration identifiers or externally consumed event identifiers; `PublicId` is the external locator. | ADR-0001, item 4 §8 |
| R12 | PostgreSQL is the source of truth; Redis is disposable acceleration and no cache is a correctness source. | master `# 22.7`, `# 5` |
| R13 | The storefront/price projection is **never** authoritative for checkout pricing, availability or sellability; `place_order` revalidates through owning domains. | item 5 PR2/INV3, C21, ADR-0003, master `# 8.4` |
| R14 | A public selector returns fully materialised immutable results; no QuerySet, paginator or `Page` crosses a public boundary. | item 4 §10, K1–K5 |
| R15 | A domain emits an Outbox event inside its own transaction; it never schedules transport. | item 4 §9.1, item 3 §4.2 |
| R16 | `tasks/*` is thin transport: one use case or one domain command per task function. | ADR-0004 §9, ADR-0005 §5 |
| R17 | Query budgets and N+1 guards are CI invariants for listing paths. | master `# 22.5`, `# 24.7` |

---

## 3. Vocabulary

| Term | Meaning in this artifact |
|---|---|
| **Projection** | `ProductListingProjection`: the PostgreSQL serving table owned by `application/storefront`. |
| **Serving row** | One projection row: one `Product × Language`. |
| **Derived serving read model** | State whose every field is a copy or a computation over another module's authoritative state, kept for read performance, reconstructible at any time. Deliberately **not** called a source of truth. |
| **Product-scope predicate** | A filter over an attribute whose value belongs to the Product as a whole (`scope='product'`, or the inherited product default of `scope='both'`). |
| **Variant-scope predicate** | A filter over a fact that belongs to an individual sellable variant: a variant axis, a `scope='variant'` attribute, the effective `scope='both'` value where a variant overrides, price, and availability. |
| **Satisfier structure** | The per-variant grouping carried by a serving row that allows a conjunction of variant-scope predicates to be evaluated against **one** variant (§6.4). |
| **Visible-result grain** | The unit that the storefront orders, paginates and returns: one Product per language. |
| **Convergence** | The state after all pending projection updates for a source object have been applied. |

---

## 4. Ownership

### 4.1 The frozen rule

```text
application/storefront
    owns ProductListingProjection
```

`application/storefront` owns, as one indivisible responsibility:

| Owned | Meaning |
|---|---|
| Projection persistence | The projection model(s), their constraints and their indexes are internal to the module. |
| Projection build / update / rebuild use cases | The only code that writes a serving row. |
| Storefront selectors | The only read path from the projection to a DTO. |
| Filter/sort/pagination compilation | `FilterSpec` whitelisting and compilation to projection predicates (master `# 10.2`). |
| Consistency and reconciliation behaviour | Freshness monitoring, targeted and full rebuild, checksum/count reconciliation. |
| Projection-specific query and index requirements | Serving indexes live with the projection, never in an OLTP domain (R8). |

| # | Rule |
|---|---|
| O1 | The projection has exactly one owner. There is no second writer, no "fast path" writer and no admin shortcut that writes a serving row. |
| O2 | No domain owns, writes, reads or knows about the projection. A domain does not know it is projected. |
| O3 | The projection is **internal** to `application/storefront` (R6). Its model, manager and QuerySet are not exported (§20). |
| O4 | Every input to a serving row is obtained through `<domain>.public` selectors returning frozen DTOs (R5). The builder issues no query against another module's tables and imports no other module's models. |
| O5 | `application/storefront` imports no other `application` module (R7). A fact it needs that only another application module holds is resolved by moving the fact to a domain contract, by merging owners, or by a new ADR — never by an application→application import. |
| O6 | `application/storefront` performs no outbound vendor I/O and declares no port; it has no vendor dependency to invert (ADR-0005 §2). |

### 4.2 The negative form

`ProductListingProjection` must **not** live in, and must not be written by:

| Rejected home | Why it is rejected |
|---|---|
| `domains/catalog` | It would require catalog to know pricing, inventory, promotions and reviews — the exact domain→domain edge R2 forbids — and would put money, stock, rating and facet indexes on catalog tables, which ADR-0003 §1/§3 forbids by name. |
| `domains/pricing` | Price is one of several inputs; a listing row is not a price. Pricing would need catalog text, images, category ancestry and stock. |
| `domains/inventory` | Same objection, from the stock side. Inventory owns a write-hot table whose physical tuning (master `# 9.1`) is the opposite of a read-optimised serving table's. |
| Any other domain | Cross-domain read composition in a domain is R2/R3 in reverse. |
| `core` | `core` knows no domain (ADR-0004 §2). A storefront serving model is the densest possible concentration of domain vocabulary. |
| `interfaces/web` or `interfaces/api` | Interfaces own no state and no business rule (ADR-0004 §5); a per-transport projection is exactly the duplicated read path master `# 10.9` forbids. |
| `integrations/*` | Adapters hold no Django models and own no domain truth (ADR-0004 §8, ADR-0005). An ERP import is a *source of updates*, never the owner of the read model. |
| `tasks/*` | Transport, not a layer (ADR-0004 §9). A task calls the projection-update use case; it does not contain it. |
| A shared "read models" package | A package with no owner cannot refuse an addition (ADR-0005 §2's rejection of `contracts/`, applied here). |

### 4.3 Consumers

```text
interfaces/web        → application/storefront.public   (HTML / HTMX fragments)
interfaces/api/v1     → application/storefront.public   (DRF JSON)
tasks/projections/*   → application/storefront.public   (update / rebuild / reconcile use cases)
```

No file is created in Phase 0. `interfaces/*` never imports the projection model, never composes a
listing from two `<domain>.public` calls, and never issues its own listing SQL (master `# 10.9`).

---

## 5. Truth semantics — three distinct meanings

| # | Layer of truth | Owner | Rule |
|---|---|---|---|
| T1 | **OLTP / domain truth** | `domains/catalog`, `domains/pricing`, `domains/inventory`, `domains/promotions`, `domains/reviews` | Each domain remains authoritative for its own business state. The projection changes nothing about that. |
| T2 | **Storefront serving source** | `application/storefront` | `ProductListingProjection` is the **primary** PostgreSQL serving source for listing/search/filter/sort requests. Web and API do not rebuild cards by joining OLTP domains per request. |
| T3 | **Commercial transaction truth** | `application/checkout` + owning domains | Checkout never treats the projection as authoritative. |

| # | Rule |
|---|---|
| T4 | The projection is a **derived serving read model**. It is never described, documented, tested or reasoned about as the platform's source of truth. |
| T5 | Every projection field is a copy or a computation over another module's authoritative state. Writing a projection field back into a domain as truth is forbidden; a projection value is never an input to a domain command. |
| T6 | The projection is never authoritative for: final price, discounts, coupon validity, stock, reservation success, payment, or final sellability at placement. `place_order` revalidates through owning domain contracts (R13, item 5 §4, PR2/INV3). |
| T7 | A stale projection may temporarily display stale information. It must never make a commercially incorrect `Order` possible. This is a **hard** invariant: every failure row in §23 is measured against it. |
| T8 | Losing the entire projection loses no commercial history and no business fact. Truth is recomputable; the projection is not backed up as truth (master `# 7.6`: "Projection не содержит уникальной коммерческой истины"). |
| T9 | No authorization, consent, entitlement or other security decision reads the projection (§24). |

---

## 6. The projection grain

### 6.1 The decision

> **One serving row per `Product × Language`, with `UNIQUE(product_id, language)`. The visible,
> ordered, paginated result grain is the Product. Variant-level facts are carried *inside* the row as
> a per-variant satisfier structure; they are never a separate paginated row source.**

This confirms the grain already frozen by master `# 7.6` and ADR-0003 §3, and adds the satisfier
structure (§6.4) that the master's product-level union array does not by itself provide.

### 6.2 The alternatives, evaluated

| Option | Grain | Verdict |
|---|---|---|
| **A** | One row per `Product × Language` | **Chosen.** The serving row is the visible result, so ordering, keyset pagination and `LIMIT` operate directly on the unit the user sees; page size is exact, no grouping happens after pagination, and one row is one card. Its single weakness — variant-scope facts collapse into a union — is closed by §6.4 rather than by changing the grain. |
| **B** | One row per sellable `ProductVariant × Language` | **Rejected.** Variant-scope predicates would be exact for free, but every visible page would require `DISTINCT`/`GROUP BY product` *after* filtering and ordering: `LIMIT 24` returns an unknown number of products, the "next" cursor is ambiguous when two variants of one product straddle the page edge, facet counts double-count products, and each product's card fields (name, image, category ancestry, rating, badges) are duplicated across every variant row — multiplying rebuild cost and write amplification on the hottest table in the system. Master `# 7.6`, `# 10.2` and `# 22.2` are all written against a product-grained row. |
| **C** | Two coordinated relations: a `Product × Language` serving row plus a variant-grain satisfier relation | **Admitted as an implementation option of A, not as a separate grain.** If Phase 4 measurement shows a companion variant-grain relation is the better physical encoding of §6.4, it is legal — provided it is used **only** as a semi-join (`EXISTS`) inside the predicate, never as the row source that is ordered or paginated, and it lives inside `application/storefront` (§6.5). The visible grain is unchanged. |
| **D** | One row per `Product × Category × Language` or per `Product × PriceList × Language` | **Rejected.** Category ancestry is already an array (`category_path_ids` + GIN, master `# 7.6`), and multi-price-list serving is not an MVP requirement; either would multiply rows for a case the array representation already answers. |

### 6.3 The matching semantics

> **A serving row matches a filter set iff the Product satisfies every product-scope predicate, and
> there exists at least one *sellable* variant of that Product that satisfies **all** variant-scope
> predicates simultaneously.**

This existential-over-one-variant rule is the frozen semantics of the listing. It is what the
example demands:

```text
Product P:  variant V1 = (color=red,  size=M)
            variant V2 = (color=blue, size=L)

filter: color=red AND size=L
        → V1 fails (size), V2 fails (color), no variant satisfies both
        → P does NOT match
```

A product-level union (`facet_choice_ids = {red, blue, M, L}`) contains both tokens and would match.
That is the false positive this item forbids.

### 6.4 The satisfier structure — the frozen correctness rule

| # | Rule |
|---|---|
| G1 | Every facet-eligible attribute value copied into the projection carries its catalog-owned **scope** classification (`product` / `variant`, with `both` resolved per ADR-0002 §2 to the level that actually holds the effective value). Classification is copied from `catalog.public`, never guessed by the storefront. |
| G2 | The serving row carries, in addition to any product-level union, a **per-variant satisfier structure**: one entry per *sellable* variant of the product, each entry holding that variant's own variant-scope values. Grouping by variant is preserved in storage; it is not flattened. |
| G3 | A conjunction of variant-scope predicates is compiled to a predicate that is satisfied only if **one single entry** of the satisfier structure contains all of them. It is never compiled to a conjunction of membership tests over a flattened union. |
| G4 | For uniformity and to remove the "is one predicate safe on the union?" judgement call, **all** variant-scope predicates — including a single one — compile against the satisfier structure. The union array is used for product-scope predicates, and for variant-scope facets **only as an over-inclusive candidate prefilter that must still be confirmed exactly** (§9.4 F6a). |
| G5 | Product-scope predicates compile against product-level fields (the union array for choice facets, promoted typed columns for ranges). A product-scope conjunction on the union is exact by construction, because all its values belong to one object. |
| G6 | Only **sellable** variants (ADR-0001's sellable unit; active, storefront-eligible) produce satisfier entries. A withdrawn or non-sellable variant must not keep a filter combination alive (§17). |
| G7 | The structure is chosen so it can be answered by a **single indexable containment/semi-join predicate** on the projection-serving path — not by post-filtering rows in Python and not by an unbounded per-row subquery. It participates in the §21 query budget. |
| G8 | Price and availability are variant-scope facts (R10). A price-range or availability predicate that is combined with another variant-scope predicate is subject to G3: the result must not claim a product matches unless one sellable variant satisfies the whole conjunction. |
| G9 | Row-level aggregate columns (`min_price_minor`, `max_price_minor`, `in_stock`, …, master `# 7.6`) remain frozen and are used for **sorting, display and single product-level bounds**. They are never used to answer a same-variant conjunction, because an aggregate has lost the grouping G2 preserves. |

### 6.5 Admissible physical encodings — decided in Phase 4, constrained here

The exact columns are **not** designed here (§1.2). Phase 4 chooses among encodings that satisfy
G1–G9; two are known to be viable in PostgreSQL:

- **E-a — nested inside the row:** a `jsonb` array of per-variant token arrays (plus per-variant
  promoted typed values where a variant-scope range facet exists), answered with the `@>` containment
  operator under a `jsonb_path_ops` GIN index. One table, one predicate, no join.
- **E-b — companion variant-grain relation inside `application/storefront`:** a satisfier table keyed
  by the same product row, used **only** as `EXISTS (…)` in the `WHERE` clause. It never appears in
  the `FROM` list as a row multiplier, is never ordered or paginated, and never leaves the module.

| # | Rule |
|---|---|
| G10 | Whichever encoding is chosen, it is **internal** to `application/storefront` (O3) and is rebuilt by the same use cases as the row (§15). E-b is not a second projection with its own lifecycle; it converges atomically with the row it belongs to. |
| G11 | A variant-scope range attribute may **not** be represented solely by a product-level promoted column. Either it is carried per variant, or the attribute is documented as display/comparison-only and is not offered as a storefront filter (master `# 7.2` already permits that outcome for rarely used ranges). |
| G12 | An over-inclusive product-level bound (for example a `min/max` price window) may be used as a **cheap pre-filter** ahead of the exact satisfier predicate, never as the final answer, and never on its own when G3 applies. |

### 6.6 Where grouping happens

> **Grouping and deduplication to the visible grain happen at projection *build* time, not at query
> time and never after pagination.**

The builder reads a product and all its sellable variants through `<domain>.public`, computes the
aggregates and the satisfier structure, and writes exactly one row per language. By the time any
request runs, the visible grain already **is** the row grain. §12 depends on this.

---

## 7. Projection identity

| # | Rule |
|---|---|
| I1 | A serving row retains enough stable identity to (a) map back to its source entities for targeted rebuild, and (b) construct public DTOs later (item 7). At minimum: the internal source identifier, the source `PublicId`, and the language. |
| I2 | Source identities are **copied scalar values**. The projection declares **no** Django `ForeignKey`, `OneToOneField` or `ManyToManyField` to any model outside `application/storefront`, and no cross-boundary ORM relation of any kind. |
| I3 | Consequences of I2, all intentional: no cross-module `select_related`/`prefetch_related` is possible; no `on_delete` cascade couples a domain table to a serving table; a domain migration cannot break the projection; the projection can be truncated and rebuilt without touching OLTP (ADR-0003's "drop and rebuild at any time"). |
| I4 | Removal of a source object is propagated by the **update path** (§17), never by database cascade. The absence of an FK is what forces the deletion semantics to be explicit and testable. |
| I5 | The internal bigint source identifier stays internal (R11). It may be used for joins inside the module, for the keyset tie-break key, and inside a **signed opaque cursor** (master `# 10.3`); it never appears in a URL, an API payload, an HTML attribute, an event consumed externally or a public DTO field. |
| I6 | The external locator carried by a serving row is the source `PublicId` (`product_public_id`, master `# 7.6`). Item 7's DTOs expose that, never `id`/`pk` (item 4 A16, I1–I3). |
| I7 | Language is part of the row identity, not a render-time parameter: one row per language, resolved by column, with no runtime translation join (ADR-0003 §4). |
| I8 | The projection carries **no** ERP/provider identifier. Vendor identity stays at the integration boundary (ADR-0003 §2, ADR-0005 §4). |

Exact columns, types, key layout and indexes: **Phase 4**.

---

## 8. What the projection may contain

Frozen as **categories of denormalized serving data**, not as a schema. A serving row may carry
copied or derived values in these categories:

| Category | Examples (illustrative, not a schema) |
|---|---|
| Source identity | product internal id, product `PublicId`, language |
| Taxonomy | category id, category ancestry tokens, brand id |
| Display facts | listing name, slug, brand/category display facts |
| RO/RU listing text | the localized text the card needs, in physical columns for that language |
| Media references | primary image path/reference for the card (never the gallery, master `# 7.3`) |
| Display pricing | current display price, previous/regular price, discount magnitude |
| Availability | display availability state, per-store availability tokens |
| Filter tokens | product-scope facet tokens, promoted typed range values |
| Variant satisfier structure | per-variant variant-scope values (§6.4) |
| Search fields | normalized text, search document/vector, rank inputs (§10) |
| Sort keys | price sort key, recency sort key, popularity/boost sort key (§11) |
| Badge inputs | structural badge codes — never localized UI text (master `# 7.6`) |
| Rating summary | rating aggregate and count, when reviews are enabled |
| Merchandising | manual boost — **copied from its authoritative owner, never owned here; disabled until that owner exists** (SO6, SO6a, SO6b) |
| Popularity | first-party popularity input, within master `# 10.7`'s MVP source rules and item 13's decision |
| Serving state | visibility state, freshness/version bookkeeping (mechanism = item 12) |

| # | Rule |
|---|---|
| CT1 | Copied data is derived. The projection does not become the owner of a business fact by storing it. |
| CT2 | A projection field is never written back into a domain as truth, and never becomes an input to a domain command (T5). |
| CT3 | Badge, price and availability values in the row are **display** facts. They carry no commercial promise; the commercial answer comes from the owning domain at cart/checkout time (T6). |
| CT4 | The row carries no long description, no spec JSON, no gallery and no other heavy payload the card does not render (master `# 22.4`: the listing does not read `Product` long description or spec JSON). |
| CT5 | No private, customer-scoped or personalized value ever enters this projection (§24). |
| CT6 | Nothing here defines `ProductCard`, `Facet` or `Badge` DTO fields; item 7 owns those and is free to expose a subset, a superset-by-computation or a different shape over these categories. |

---

## 9. Typed facets

### 9.1 The relationship between truth and serving structure

```text
domains/catalog                          application/storefront
─────────────────                        ──────────────────────
typed EAV  = SOURCE OF TRUTH             listing facet representation
AttributeDefinition (scope,        ──▶   = DERIVED SERVING STRUCTURE
  data_type, is_variant_axis,             (tokens, promoted typed values,
  filterable, sortable)                    per-variant satisfier entries)
ProductAttributeValue (typed)            rebuilt from EAV at any time
```

| # | Rule |
|---|---|
| F1 | Typed EAV remains the source of truth, and the admin/validation/comparison/import path (ADR-0002, master `# 7.2`). The projection never replaces it and never corrects it. |
| F2 | The listing facet representation is derived. A full rebuild from EAV must reproduce **the same serving state** — this is a testable property (C26), and it is why no facet value may originate in the projection. |
| F3 | **No EAV traversal occurs in a listing request.** No self-join, no `EXISTS` chain over `ProductAttributeValue`, no attribute-definition lookup per selected facet (master `# 7.2`, `# 10.2`: "`EAV` не участвует в hot list request"). The number of selected facets does not change the number of joins. |
| F4 | Which attributes are facet-eligible is catalog-owned metadata (`filterable`, `sortable`, `scope`, `is_variant_axis`), read through `catalog.public`. The storefront does not invent facet eligibility. |

### 9.2 Representation per facet kind

| Facet kind | Scope | Representation family | Correctness note |
|---|---|---|---|
| Choice / discrete | product | Product-level token array under a GIN index (master `# 7.2`) | Conjunction on the array is exact (G5). |
| Choice / discrete | variant (including every variant axis) | Per-variant satisfier entries (§6.4) | Conjunction must be same-variant (G3). |
| Integer / decimal range | product | Promoted typed column, btree/partial index added after measured usage (master `# 7.2`) | Exact. |
| Integer / decimal range | variant | Per-variant promoted values inside the satisfier structure, **or** the attribute is display/comparison-only (G11) | A product-level column alone is not admissible (G11). |
| Boolean | product | Promoted typed column or a token in the array | Exact. |
| Boolean | variant | Per-variant satisfier entry | G3 applies. |
| Price range | variant by definition | Aggregate bounds for sort/display (G9) + satisfier participation where combined with another variant-scope predicate (G8, G12) | Never claim a same-variant match an aggregate cannot prove. |
| Availability | variant by definition | Row-level display state + per-store tokens; participates in filtering under the same rules | G8 applies. |
| Category | product | Ancestry token array under a GIN index (master `# 7.6`) | Exact. |

### 9.3 Promoted attributes

Master `# 7.2` promotes 5–10 genuinely used range attributes per category into typed columns. That
stands. Item 6 adds only: promotion is a **serving decision** owned by `application/storefront`,
driven by measured usage, and it never causes a column to appear on a catalog table (R8). A promoted
column is rebuildable from EAV like any other projected value (F2).

### 9.4 Facet counts

| # | Rule |
|---|---|
| F5 | Facet counts are computed over the projection only (master `# 10.4`), never over OLTP/EAV. |
| F6 | A count query applies the **same** candidate-set predicate as the listing query that produced the candidate set, compiled by the same code path. A count may never use a looser predicate than the listing — a count that promises results the grid cannot deliver is a defect, not a rounding difference. |
| F6a | **What "candidacy" means, precisely.** For a variant-scope facet the product-level union array may be used **only** as an over-inclusive indexed prefilter / candidate reducer; it is never the final counting predicate. Before a Product contributes to an exact variant-scope facet count, the same-variant satisfier predicate must confirm the candidate exactly: <br>`union candidate prefilter → exact satisfier predicate → count Product` <br>and never `union candidate prefilter → COUNT directly`. This is the counting form of G3/G12: an over-inclusive structure narrows the work, it never answers the question. For a product-scope facet the union is exact (G5) and no confirmation step is needed. |
| F7 | The documented degradations remain available: cached counts, omitted counts, or an approximate/limited set above a candidate-set threshold (master `# 10.4`). Degradation is a **UX** decision under this explicitly frozen policy, and a degraded count is labelled/treated as such; it never becomes permission to use a wrong predicate or to skip F6a's confirmation while presenting the result as exact. |
| F8 | Count caching is disposable Redis acceleration (§20.1); losing it changes no result, only cost. |

---

## 10. Search

| # | Rule |
|---|---|
| S1 | **PostgreSQL is the MVP listing and search serving engine**: the projection for structured filtering, PostgreSQL FTS for text relevance, `pg_trgm` for typo-tolerant autocomplete, GIN for vectors and token arrays (master `# 10.1`). |
| S2 | **OpenSearch is not introduced by item 6.** It remains master `# 10.8`'s measurement-gated Stage 2, requiring a new ADR and evidence of a real relevance/scale gap. The migration contract already exists: the same projection updates would index an external document. |
| S3 | The projection may own search-oriented derived fields — normalized text, search document/vector, rank inputs. They are serving mechanics, not domain truth (T4): a search vector is never a catalog fact and is always recomputable. |
| S4 | Search-side input discipline from master `# 10.2` is inherited unchanged: whitelisted parameters, bounded `q` length, `websearch`/plain syntax rather than raw `tsquery`, bind parameters only, a query-cost guard **before** SQL, and no dynamic `.filter(**request.GET)` / `.order_by(user_input)`. |
| S5 | Language stemming configuration, ranking weights and autocomplete tuning stay implementation details of Phase 4, bounded by S1–S4. |
| S6 | Whether the search document lives in the same physical row or in a sibling serving structure inside `application/storefront` is a Phase 4 decision; either way it is owned, updated and rebuilt by the same module and the same use cases (G10). |

---

## 11. Sorting

| # | Rule |
|---|---|
| SO1 | Every public listing sort compiles to a **whitelisted** `(sort key…, tie-break key)` tuple over projection columns (master `# 10.2` `SORTS` map). An unknown sort parameter is rejected or normalized to the canonical default. |
| SO2 | **Every** sort ends with a deterministic final tie-break key that is unique per serving row, so equal sort values can never reshuffle between requests or between pages. Rows with equal primary sort values have exactly one possible order. |
| SO3 | The sort keys frozen as required by master `# 10.2`: price (asc/desc), newest, popularity, plus relevance for text queries. Each compiles to a **row-level scalar of the serving row**, which is what makes SO2 and product-grained keyset pagination (§12) possible. |
| SO3a | **Baseline filtered-price semantics.** With no variant-sensitive price policy in force, price sorting uses the product-wide projected price sort key (master `# 7.6`, `# 10.2`), including when a variant-scope filter is active. That is the master's already-described behaviour and it remains legal. Its known consequence is recorded rather than hidden: under `color=red`, a product whose cheapest variant is blue is still ordered by that blue price, so the visible order can differ from the order of the prices that actually satisfy the filter. |
| SO3b | **Whether an active variant-scope filter changes the *effective* price is deferred** — equally for card display, for the price sort key and for cursor construction (§27). Item 6 does not decide it; SO3a is the baseline, not a ruling that the semantics must stay product-wide. |
| SO3c | **Coherence is frozen even though the policy is not.** Display price, price sort key and cursor value must use **one** price semantics. If the storefront contract later says the card shows the price of a variant satisfying the active filter, price sorting and the cursor may **not** silently continue to order by a non-matching variant's price. Whatever that choice then requires — an additional projected representation, a different satisfier encoding, a filtered sort key — follows the decision; item 6 requires none of them now and mandates no dynamic SQL aggregation, no matched-variant sorting, no new column and no new encoding. |
| SO3d | The filtered-price policy is a **joint storefront contract decision** — listing sort, card display and cursor recorded together — taken before Phase 4 implementation. Item 7 may define the `ProductCard` price representation, but it may **not** independently redefine listing sort semantics; a card decision that implies a sort change requires the joint decision (RP6). |
| SO4 | Relevance sorting is a computed rank over the search fields (§10), also terminated by the tie-break key (SO2), so that two equally relevant products still have a stable order. |
| SO5 | **Popularity may not be invented here.** For MVP it uses only master `# 10.7`'s already-approved first-party signals — paid/delivered sales in a window, favorites, rating/review signal — plus a manual merchandising boost **where SO6 is satisfied**. Page-view tracking is **not** a required source and does not block launch. Anything beyond this waits for item 13's analytics decision; a consent-gated `domains/analytics` would deliver aggregates into the projection in batches, never join raw metrics into a request (master `# 10.7`). |
| SO6 | **A manual merchandising boost is never owned by `ProductListingProjection` and is never stored only as serving state.** Like every other projected value it is derived (T4, T5, CT1): before it may participate in sorting it must have a **durable authoritative source with an explicit owner**, and the projection only copies or derives it from that source through the owner's legal public contract — so that a full rebuild reproduces it exactly (F2, RB1, RB4). |
| SO6a | **Item 6 does not assign that owner.** It is not `catalog` (R8); no owner is chosen among promotions, content or any other module here; no new domain is invented; and no application state is created for it. The assignment is an explicitly deferred decision (§27) that must respect the frozen dependency graph — whatever owner is chosen has to be legally reachable from `application/storefront` under O4/O5/R7, which in practice means a domain public contract. |
| SO6b | **Until an authoritative owner is assigned, manual boost is unavailable/disabled**: the popularity sort key is computed from the other approved signals only. "Store it directly in the projection" and "let an operator edit the serving row" are both forbidden — either would make a sort key unreproducible by rebuild, and would turn a disposable read model into truth (T4, T8, RB1, V37). |
| SO7 | A sort key is a projected value, so a stale row can order slightly stale data. That is display staleness (§18), never a correctness failure (T7). |

---

## 12. Pagination

| # | Rule |
|---|---|
| PG1 | The visible-result grain is the Product (§6.1), and it is established at **build** time (§6.6). Pagination therefore operates on the same rows the user sees. |
| PG2 | Deep listing paths use **keyset/cursor pagination** on `(sort key…, tie-break key)` (master `# 10.3`). Deep `OFFSET` is forbidden. |
| PG3 | Shallow SEO-relevant pages may use bounded page-number pagination (master `# 10.3`), bounded so it cannot degrade into deep offset. |
| PG4 | Cursor values are serialized into a **signed opaque cursor**; the internal bigint tie-break key never becomes a public locator (I5, R11, master `# 10.3`). |
| PG5 | **Forbidden: `LIMIT`/`OFFSET` over variant-grained rows followed by grouping products afterwards.** With the chosen grain this is structurally impossible in the primary encoding; with encoding E-b it is prevented by the semi-join rule (G10/E-b: the satisfier relation is never the paginated row source). |
| PG6 | A page contains exactly the requested number of visible results when enough rows match, and the concatenation of consecutive pages under an unchanged snapshot contains every matching product exactly once, in the sort order — no duplicates, no gaps (asserted by C31). |
| PG7 | Projection updates during a walk may cause a row to move; that is ordinary eventual-consistency drift (§18), not a pagination defect. The invariant PG6 constrains a stable snapshot. |
| PG8 | API cursor serialization fields, the exact cursor codec and page-size limits are **not** designed here — Phase 4 / item 7, bounded by PG2–PG4. |

---

## 13. The read path

```text
ProductListingProjection            (internal to application/storefront)
        ↓  storefront selector      (filter compilation, sort, keyset, shaped read)
   immutable storefront DTO         (item 7: ProductCard / Facet / Badge)
        ├─ interfaces/web  → HTML / HTMX fragment (+ fragment cache)
        └─ interfaces/api  → DRF JSON
```

| # | Rule |
|---|---|
| RP1 | There is exactly **one** application read path. Web and API consume the same semantic application result from the same selector (master `# 10.5`, `# 10.9`). |
| RP2 | The projection ORM object, its QuerySet, its manager and any Django `Paginator`/`Page` never cross the `application/storefront` boundary (R14, item 4 K1–K3). The selector returns fully materialised immutable data. |
| RP3 | No web-specific or API-specific query implementation may bypass the shared selector. A second DRF queryset that reassembles a card from `Product`/`Variant`/`Price`/`Inventory` is forbidden by name (master `# 10.9`). |
| RP4 | Localization is resolved by the projection's per-language row (I7) and rendered at the transport boundary; badge codes are localized at the Web/API edge, never stored as UI text (master `# 7.6`). |
| RP5 | Selector reads are **shaped**: `.only()`/`.defer()`-style column selection, no unrestricted `SELECT *` over heavy fields (master `# 22.4`). |
| RP6 | Item 7 owns the exact `ProductCard`, `Facet` and `Badge` contracts. Item 6 freezes only their **source and path**: they are built from projection rows by this selector and by nothing else. Item 7 may not, on its own, change listing **sort** semantics — a card price representation that implies a different sort key or cursor requires the joint decision of SO3d. |
| RP7 | Web/API parity is a contract test, not a convention: same order for the same filter/cursor, same public identifiers, same price/availability/rating/badge semantics, same selector-level query budget (master `# 10.9`, C32). |

---

## 14. Incremental update path

```text
domain transaction (catalog / pricing / inventory / promotions / reviews)
        │  business write + Outbox row, one ACID transaction        (master # 20.2, R15)
        ▼
transactional Outbox  →  relay  →  queue (core.low, master # 20.1)
        ▼
tasks/projections/*  — thin transport (R16)
        ▼
application/storefront  projection-update use case                 ← the update owner
        ▼
ProductListingProjection  (guarded, set-based upsert)
```

| # | Rule |
|---|---|
| UP1 | The **update owner is `application/storefront`**, not the emitting domain. A domain records that something changed; it does not know a projection exists (O2). |
| UP2 | A domain never writes a serving row, directly or through a signal, `save()` override or admin action. Neither does an ERP import, a management command, a task body or an interface (O1). |
| UP3 | The task layer is transport only: deserialize, restore actor/trace, call **one** `application/storefront.public` use case, map the result to success/retry/DLQ (R16). |
| UP4 | Event names, payload schemas, versions and the registry are **item 8**'s. This artifact names no event and fixes no payload. |
| UP5 | **One event per changed row is not required and is not wanted.** Batch/coalesced events with bounded payloads, or a dirty-set/staging table, are the intended shape for bulk change (master `# 20.2`); the worker deduplicates identifiers and applies a set-based upsert. |
| UP6 | The update path is idempotent under duplicate delivery and safe under reordering (§16). |
| UP7 | A projection update never participates in a domain's business transaction and never blocks it. A slow or failing updater degrades storefront freshness; it does not fail a checkout, a price change or an ERP import (T7, §23). |
| UP8 | The update use case reads whatever it still needs through `<domain>.public` batch selectors (O4); it never trusts an event payload as a complete substitute for authoritative state when a full row must be recomputed. |
| UP9 | The projection queue is a `core` failure domain, not an external-vendor one (master `# 20.1`: `tasks.projections.* → core.low`). Item 9 owns the final queue/DLQ matrix. |

---

## 15. Rebuild and reconciliation

| # | Rule |
|---|---|
| RB1 | **The projection is completely rebuildable from authoritative OLTP state**, using only the owning modules' legal public contracts (`<domain>.public`, per O4/O5). This is a hard architectural property, not an operational convenience: **every enabled facet, sort key and search field must be reproducible from an authoritative source**, which is why a value with no assigned owner cannot be enabled (SO6b, F2, V37). |
| RB2 | Events are an **acceleration/update** mechanism. The projection is **not** event-sourced: no event history is required to reconstruct it, and a discarded, expired or archived Outbox partition (master `# 20.5`) can never make the projection unreconstructible. |
| RB3 | Three operations are frozen as existing: **full rebuild** (the whole table), **targeted rebuild by source identity** (one product, a set of products, a category, a brand, a price list), and **periodic reconciliation** (counts/checksums against OLTP, repairing drift — master `# 7.6`). |
| RB4 | A rebuild produces the same serving state as the incremental path (F2, C26). Divergence between "rebuilt" and "event-updated" state is a defect in the update path, and reconciliation is what makes it observable. |
| RB5 | Rebuild is **set-based and batched** (§22) and runs outside the request path (§19). |
| RB6 | A rebuild in progress must keep the storefront servable: it does not truncate the serving table under live traffic as its normal mode. The concrete mechanism (in-place guarded upsert per batch, or a build-then-swap) is a Phase 4 decision bounded by this rule and by §16. |
| RB7 | Reconciliation reports drift as an operational signal (metric/alert), not as a silent repair. "The reconciler fixes it every night" is not an acceptable substitute for a correct update path. |
| RB8 | Exact commands, task names, batch sizes, schedules and the swap mechanism: **Phase 4** and the operations phase. |

---

## 16. Event ordering and stale updates

### 16.1 What item 6 freezes

| # | Rule |
|---|---|
| PU1 | The projection updater is **safe under duplicate delivery**: applying the same update twice leaves the same serving state. |
| PU2 | The updater is **safe under retry**, including a retry after a partial batch. |
| PU3 | The updater is **safe under reordering**: updates for one product may arrive out of order and must converge to the state of the newest one. |
| PU4 | **A stale update must never overwrite newer projected state.** An older writer that arrives after a newer one is a no-op, not a regression. This is monotonic convergence, and it is the correctness requirement of this section. |
| PU5 | Convergence is per serving row. Two independent sources changing different aspects of the same product (a price change and a stock change, master `# 7.6`) must not lose each other's effect through last-writer-wins on the whole row; the guarded upsert must make the row converge to the newest state of each contributing fact. |
| PU6 | Ordering safety is a property of the **write path**, never of the read path. A selector never compensates for a possibly-stale row, never re-reads OLTP to check, and never repairs (§19). |
| PU7 | No serving-state rollback: a correction is a forward update, never an undo of a newer state. |

### 16.2 What stays with item 12

Item 12 — `source_version` generation + guarded projection upsert — owns, and item 6 does **not**
define:

- the version column's type, name and cardinality;
- the generation algorithm and its monotonicity argument;
- the per-domain/per-source version source, and how several sources map into one row's guard;
- the SQL guard itself (the `ON CONFLICT … WHERE EXCLUDED.source_version > …` shape sketched in
  master `# 7.6` is master text, not a decision made here);
- how PU5's per-fact convergence is expressed in that guard.

| # | Rule |
|---|---|
| PU8 | Item 6 states the requirement; item 12 chooses the mechanism. An implementation may not claim item 6 as authority for a specific version scheme. |
| PU9 | **This is not checkout's freshness guard.** Item 5 §7.4's owner-defined freshness/revalidation guard protects a *durable commercial write* inside the placement transaction against stale prepared reads, per owning domain, with no shared counter (FG1–FG4). Item 12's `source_version` protects a *derived serving row* against out-of-order asynchronous updates. Different problem, different owner, different failure mode: conflating them would either put a read-model version column on OLTP tables (ADR-0003 §3 forbids it) or let a projection version decide a commercial write (T6 forbids it). |
| PU10 | No `source_version`, and no other storefront read-model state, is added to `Product`, `ProductVariant` or any other domain table (ADR-0003 §3, R8). |

---

## 17. Lifecycle: withdrawal and deletion

Trigger examples: a product archived or unpublished; the last sellable variant withdrawn; a variant
made non-sellable; a category hidden; a brand or product removed under its domain's rules; a
price list or listing eligibility withdrawn.

### 17.1 The frozen semantic invariant

> **A source object that is no longer eligible for storefront visibility must disappear from serving
> results after projection convergence — from listings, facet counts, search results and cursors
> alike.**

| # | Rule |
|---|---|
| LC1 | Convergence removes the object from **every** serving surface, not only from the grid: facet counts (F6), search, sitemap-facing reads and any other projection-sourced answer. |
| LC2 | The architecture freezes the invariant, **not** the storage implementation. Physical deletion of the row and a non-visible/tombstone state are both admissible, provided every serving selector excludes the object. |
| LC3 | Serving selectors filter on an explicit **positive** visibility predicate (master `# 7.6`'s `is_active` shape, with the partial indexes of `# 22.3` written against it). "Not yet marked invisible" must never mean "visible": a row is served only when it positively asserts eligibility. |
| LC4 | Partial visibility is expressed at the satisfier level too: a withdrawn variant loses its satisfier entry (G6), so a filter combination that only that variant satisfied stops matching, and the aggregates (G9) are recomputed. |
| LC5 | If the last sellable variant disappears, the product's storefront eligibility is re-evaluated by the same rule; a product with nothing sellable is not silently kept listed because its row still exists. |
| LC6 | Deletion propagates through the update path, not through a database cascade (I4). A source domain's delete/archive emits its ordinary change signal; the storefront removes or hides. |
| LC7 | **Source-domain audit and history are untouched.** Hiding or deleting a serving row weakens no domain's retention, audit or legal history, and orders keep their immutable snapshots regardless (master `# 8.3`, item 5 PR5). |
| LC8 | A tombstone that is retained indefinitely is a serving-storage decision for Phase 4; retention must not be unbounded without a stated reason, and a retained tombstone never becomes servable again except through a normal update that re-asserts eligibility. |
| LC9 | Convergence is bounded operationally (§18): "eventually" means within the alerting threshold, not "whenever the queue drains". |

---

## 18. Consistency model

| # | Rule |
|---|---|
| CM1 | `ProductListingProjection` is **eventually consistent** with OLTP truth. |
| CM2 | It is **not** updated synchronously by importing from, or writing across, several domains inside their transactions. No domain transaction is extended to include a projection write. |
| CM3 | Normal storefront rendering tolerates bounded projection lag. A slightly stale card is an accepted product property, not an incident. |
| CM4 | Stale display is possible during lag: price, availability, badges, rating and popularity may briefly lag their domains. |
| CM5 | Checkout revalidation protects commercial correctness (R13, T6): the user may be shown a stale price and still cannot buy at it. |
| CM6 | **Security and private-state decisions must not rely on this projection** (§24, T9). |
| CM7 | Hidden/withdrawn products require **operationally bounded** propagation: convergence lag has a monitored threshold and an alert, so a product that must vanish does not stay listed indefinitely (LC9). |
| CM8 | **No seconds-based SLO is invented here.** The master states no numeric projection-freshness SLO; the number is set with the alert in the operations/performance phase. What is frozen is that a threshold, a freshness metric and an alert must exist. |
| CM9 | Exceeding the freshness threshold is an **observable operational fault** — a metric, an alert and a runbook — and never a licence for storefront code to fall back to expensive cross-domain joins (§19). The response is to repair the pipeline or run a targeted rebuild. |
| CM10 | Lag is measured, not assumed: projection freshness is a first-class metric alongside the query budgets of master `# 22.9`/`# 23.2`. |

---

## 19. No OLTP fallback on the hot path

| # | Rule |
|---|---|
| NF1 | A cache miss or a projection miss must **not** cause the web request to dynamically join catalog + pricing + inventory + EAV as a fallback. |
| NF2 | The admissible serving hierarchy is: **cache → PostgreSQL `ProductListingProjection` → a controlled stale cached result** where the master already permits one (single-flight + stale fallback for shared read fragments, master `# 22.7`, `# 19.2`). There is no fourth tier. |
| NF3 | `projection miss → rebuild from OLTP synchronously inside the request` is forbidden on every path, including "just this one card", "only for admins" and "only when the row is missing". |
| NF4 | A missing serving row means the object is **not currently listable**: the request returns the ordinary empty/not-listed answer. It does not become a repair trigger inside the request. |
| NF5 | Repair happens outside the request hot path: targeted rebuild, reconciliation, or the normal update path (§15). A request may at most record a signal (metric/log) that a row was missing; it may not schedule per-request rebuild work in a way that lets a crawler or a bot drive rebuild load. |
| NF6 | The product **detail** page is outside this item's scope, but the same principle applies to it as a review rule: a bounded, owned read path, not an unbounded OLTP composition per request (master `# 22.5` gives it its own budget). |
| NF7 | A "temporary" fallback added during an incident is a review failure (V29), not a pragmatic exception: it converts a bounded storefront degradation into an unbounded OLTP load exactly when the system is least able to absorb it. |

---

## 20. Cache, and the application public boundary

### 20.1 Redis / CDN relationship

| # | Rule |
|---|---|
| CA1 | Redis, HTML fragment caches and the CDN **accelerate** the projection-serving path (master `# 10.5`, `# 22.7`). |
| CA2 | They are **disposable**. No cache is a correctness source (R12). |
| CA3 | **A full cache flush must leave PostgreSQL `ProductListingProjection` capable of serving the storefront** — colder, not broken (C29). No listing state exists only in Redis. |
| CA4 | The already-frozen master principles are preserved and not redesigned here: single-flight + stale fallback for shared navigation/read fragments, fragment cache TTL with catalog versioning, facet-count caching, and the rule that the selector/DTO path — not the HTML cache — is the primary contract (master `# 10.5`). |
| CA5 | Personalized values never enter a shared anonymous cache without an explicit `vary`/partition policy (master `# 10.5`); given §24, the shared listing path has nothing personalized to leak. |
| CA6 | Cache keys, TTL values and invalidation topology are **not** designed here beyond what the master already fixes; they are Phase 4 work. |

### 20.2 `application/storefront/public.py`

```text
application/storefront/public.py
    exports the stable storefront selectors / use cases,
    and (later) item 7's ProductCard / Facet / Badge DTOs
```

| # | Rule |
|---|---|
| SP1 | `public.py` is the module's only importable surface (ADR-0005 §7, item 5 AP1). The projection model and every other internal object stay internal (O3). |
| SP2 | It does **not** export: the `ProductListingProjection` ORM model or instance, a manager or QuerySet, a Django `Paginator`/`Page`, any domain ORM object, a cache client, or a search-vector/implementation type. |
| SP3 | The same **no-ORM / no-vendor / no-transport / no-lazy** contract rules as a domain contract apply (item 4 §6, §7; item 5 AP2): frozen DTOs, `Money`, `PublicId`, aware UTC instants, immutable collections, no `Mapping`/`Sequence` field shapes, no field named `id`/`pk`. |
| SP4 | Public storefront listing reads are **public state**: they take no actor (item 4 §11.1's first shape). If a future storefront capability reads private state, it takes an explicit mandatory non-optional actor and is a different contract (§24). |
| SP5 | Application→application imports remain forbidden (R7/O5). |
| SP6 | Collections are bounded and materialised; pagination metadata, when it becomes part of the contract, is a frozen DTO owned by item 7 (item 4 K1–K4). |
| SP7 | Update/rebuild/reconcile use cases are also exported here — they are the only entry points `tasks/*` may call (UP3) — and they return frozen results, not ORM objects. |
| SP8 | The file is **not** created in Phase 0. |

---

## 21. Query-budget invariant

| # | Rule |
|---|---|
| QB1 | A listing page/request uses a **small bounded number** of SQL statements on the projection-serving path, independent of page size and of the number of selected facets. |
| QB2 | **No per-card SQL. No N+1.** A card is rendered from data already in the row (or already fetched in the same bounded set). |
| QB3 | **No request-time EAV traversal** (F3) and **no request-time catalog→pricing→inventory join chain** (master `# 22.1`, `# 22.2`). |
| QB4 | The satisfier predicate (§6.4) participates in this budget: it is a single indexable containment/semi-join predicate, not a per-row subquery (G7). |
| QB5 | The exact numbers follow master `# 22.5`, which makes category/listing a mandatory budget and shows `assertNumQueries(<=6)` as an example; the approved per-endpoint number is set with the endpoint in Phase 4. What is frozen here is boundedness and `O(1)`-in-page-size. |
| QB6 | Storefront selectors must be **compatible with the CI query-budget and N+1 guards** (`django-zen-queries` or equivalent, master `# 22.5`, `# 24.7`): no lazy attribute that triggers SQL during rendering or serialization, in either transport. |
| QB7 | The budget is asserted at the selector level **and** at the endpoint level, so a regression cannot hide behind a template or a serializer. |
| QB8 | Facet counting is a separate, separately budgeted and separately degradable query (F5–F7); it does not enter the card budget through the back door. |

---

## 22. Rebuild performance

| # | Rule |
|---|---|
| BP1 | Projection rebuild and update code is **set-based and batched**. Per-entity loops that query per SKU are an architectural failure at catalog/ERP scale, not a performance nit. |
| BP2 | The forbidden shape, named explicitly: <br>`for each SKU: query catalog; query price; query inventory; save projection`. |
| BP3 | Owning domains expose **batch** public selectors (a set of identifiers → a materialised tuple of DTOs) as needed; a missing batch capability becomes a new public symbol in that domain, never a models import (item 4 §16). |
| BP4 | Bulk changes coalesce: deduplicated identifier sets, bounded batches (master `# 20.2`'s 500–1000 shape), set-based upsert per batch, and **no-op suppression** so an unchanged row is not rewritten (master `# 22.1`'s ERP row: set-based update + no-op guard + event coalescing). |
| BP5 | Write amplification is a design constraint: a batch that rewrites every row of the serving table because one attribute changed is a defect. Targeted rebuild (RB3) exists to avoid it. |
| BP6 | Rebuild runs on the projection queue (UP9) and must not starve the queues that carry correctness-critical work (master `# 20.1`). |
| BP7 | Exact batch sizes, chunking strategy, SQL mechanics and throttling are Phase 4 implementation details bounded by BP1–BP6. |

---

## 23. Failure matrix

"Commercial correctness impact" is measured against T7: no row may compromise `Order` correctness.

| # | Failure | Storefront display impact | Commercial correctness impact | Recovery owner |
|---|---|---|---|---|
| 1 | **Duplicate projection update** delivered twice | None — idempotent apply, same state (PU1) | None | `application/storefront` (no action) |
| 2 | **Old / out-of-order update** arrives after a newer one | None — guarded upsert makes it a no-op (PU3, PU4); mechanism is item 12's | None | `application/storefront` |
| 3 | **Missed event** (relay gap, DLQ, dropped batch) | One or more rows stale until repaired; possibly stale price/stock/visibility | None — checkout revalidates (R13, T6) | Reconciliation + targeted rebuild (RB3); alert on freshness (CM7) |
| 4 | **Projection row missing** for a listable product | The product is not listed; the request returns the ordinary empty/not-listed answer (NF4) | None — the product remains buyable through any path that does not depend on the projection | Targeted rebuild outside the request (NF5) |
| 5 | **Projection updater technical failure** (worker crash, DB error mid-batch) | Freshness degrades from the failure point | None — the domain transaction that emitted the change already committed independently (UP7) | Task retry → DLQ → replay (master `# 20.1`); reconciliation as backstop |
| 6 | **Redis / fragment cache loss** | Colder responses, higher PostgreSQL load; single-flight + stale prevent stampede (CA4) | None | Automatic re-warm; no data recovery needed (CA3) |
| 7 | **Full rebuild running** | Extra background load; rows converge progressively; the storefront stays servable (RB6) | None | `application/storefront` + operations (BP6 throttling) |
| 8 | **Source Product/SKU withdrawn while the projection is stale** | The product may remain listed until convergence (LC9 bounds this) | None — adding to cart / placing an order revalidates sellability through the owning domains; the placement fails or the line is refused (T6, T7) | Update path; alert if convergence exceeds the threshold (CM7) |
| 9 | **Price changed while the projection is stale** | A stale price may be displayed | None — authoritative re-pricing at placement (item 5 §10, §17); a client-supplied total is never trusted (item 5 §6.2) | Update path; the UX policy for a changed price is item 5's deferred decision |
| 10 | **Stock changed while the projection is stale** | "In stock" may be displayed for a depleted SKU | None — `inventory.public`'s atomic reservation is the authoritative gate (item 5 §7.4 FG4, C13) | Update path |
| 11 | **Projection contains a wrong value** (builder bug) | Wrong display until repaired | None, provided T5/T6 hold — the value never reaches a domain command or a commercial decision | Fix + full rebuild (RB1); reconciliation surfaces the class of drift |
| 12 | **Projection lag exceeds the operational threshold** | Broadly stale storefront | None | Operational fault: alert + runbook; **never** an OLTP fallback (CM9, NF7) |
| 13 | **Projection storage lost entirely** | Storefront listing unavailable until rebuilt | None — no unique commercial truth is lost (T8) | Full rebuild from OLTP (RB1) |
| 14 | **Outbox partition archived/expired before an update was applied** | The affected rows stay stale | None | Reconciliation + rebuild — the projection is not event-sourced (RB2) |

**Core invariant of the matrix:** projection failure may degrade or stale storefront **display**; it
must never compromise checkout or order correctness. Every "commercial correctness impact" cell is
`None` by construction, because the commercial answer never comes from this projection (T6, R13).

---

## 24. Security and privacy

| # | Rule |
|---|---|
| SEC1 | The projection contains **public storefront-serving state only** — the same data an anonymous visitor may see. |
| SEC2 | It must **not** contain: cart contents; customer identity or any customer-scoped value; private pricing entitlement; order data; raw consent, session or security records; internal cost, margin or supplier data; PII of any kind. |
| SEC3 | The global listing projection is never used for a personalized or private **authorization** decision. Object-level authorization follows state ownership through actor-scoped selectors and policies (ADR-0004 §6), and reads authoritative state, never a derived read model (CM6, T9). |
| SEC4 | Any future personalized price or private read model is a **separate** artifact with its own ownership, its own actor-scoped contract, its own cache partitioning and its own security review — and a new ADR. It is not a column, a `vary` key or a "personalized" branch added to this projection. |
| SEC5 | Because the shared projection is public by construction, the anonymous HTML fragment cache and the CDN can cache its output without a leak class existing at all (CA5). |
| SEC6 | Input discipline at the boundary is inherited unchanged from master `# 10.2`: whitelist-compiled filters/sorts, bounded facet counts and value counts, bounded `q`, bind parameters only, a query-cost guard before SQL, no dynamic `.filter(**request.GET)` and no `.order_by(user_input)` (S4). |
| SEC7 | Crawl-budget controls (master `# 10.6`) remain the storefront's defence against filter-space explosion; they are a serving concern of this path, not a separate subsystem. |
| SEC8 | No secret, token or internal identifier leaks through the serving path: external locators are `PublicId`, internal bigints stay internal or travel only inside a signed opaque cursor (I5, PG4). |

---

## 25. Checks a later phase must implement

These **extend** the enforcement maps of item 3 §15, item 4 §19 and item 5 §22; those remain
authoritative and unchanged. Nothing here is implemented in Phase 0.

### 25.1 Import graph (`L` series)

**No new `L` rule, and no new `core` allowlist entry.** Every import this item needs —
`application/storefront` → `<domain>.public` (`PUBLIC ONLY`), → `core` (`ALLOW`), → its own internal
ORM (`SELF ONLY`), and `interfaces/*`/`tasks/*` → `application/storefront.public` (`PUBLIC ONLY`) —
is already permitted by item 3 §4.3/§4.4/§4.6. Every import it must not make — another
`application/*`, a domain's internals, `integrations/*`, `config/*` — is already `FORBID`. ADR-0008
moves no cell; L1–L21 stand unedited.

### 25.2 Static / AST (continuing the `A` series)

| # | Rule |
|---|---|
| A29 | No model defined under `application/storefront` declares a `ForeignKey`, `OneToOneField` or `ManyToManyField` whose target resolves outside `application/storefront` (I2). |
| A30 | No module outside `application/storefront` performs an ORM write against a storefront projection model, and no module under `domains/*` references one at all (O1, O2, UP2). |
| A31 | `application/storefront/public.py` exports no ORM model/manager/QuerySet, no `Paginator`/`Page`, no cache client and no search-vector implementation type; its DTO annotations obey item 4 A16/A17/A20 (SP2, SP3). |
| A32 | No module under `interfaces/*` references a storefront projection model, and no `interfaces/*` listing view/serializer reaches two or more `<domain>.public` modules in one callable (RP3; extends A5's one-domain rule to the listing path). |
| A33 | No `.filter(**<request-derived mapping>)` and no `.order_by(<non-literal>)` shape appears on the storefront path; sort and filter compilation goes through the whitelisted map (S4, SEC6, master `# 10.2`). |
| A34 | No projection build/rebuild use case is called from a module under `interfaces/*` (NF3, NF5). |
| A35 | No storefront serving selector issues an unrestricted `SELECT *` over the projection: shaped `.only()`/`.defer()`-style column selection is required for the serving read (RP5, master `# 22.4`). |

### 25.3 Behavioural / contract tests (continuing the `C` series)

| # | Rule |
|---|---|
| C24 | **No cross-variant false positive:** a product with variants `(red, M)` and `(blue, L)` is **absent** from the result of `color=red AND size=L`, and present for `color=red AND size=M`. Asserted for at least: two variant axes, an axis combined with a variant-scope non-axis attribute, and an axis combined with a variant-scope range/price predicate (§6.3, G3, G8). |
| C25 | **No OLTP traversal in a listing request:** a listing/search/facet request touches only `application/storefront`-owned tables — asserted by table-access capture, not by query count alone — so no catalog/pricing/inventory/EAV table appears (F3, QB3). |
| C26 | **Rebuild reproduces serving state:** starting from an event-updated projection, a full rebuild from OLTP produces an identical serving state; running the rebuild twice changes nothing (F2, RB1, RB4). This explicitly covers **every enabled sort input**: a manual merchandising boost must survive a rebuild from its authoritative owner, or it must not be enabled at all (SO6, SO6b). |
| C27 | **Monotonic convergence:** applying an older update after a newer one leaves the serving row unchanged; duplicate and reordered deliveries converge to the newest state, including two sources changing different facts of one row (PU1–PU5). The version *mechanism* under test is item 12's. |
| C28 | **No fallback on a miss:** with a serving row deleted, the request returns the ordinary not-listed answer, issues no OLTP composition query and schedules no in-request rebuild (NF1, NF3, NF4). |
| C29 | **Cache loss is survivable:** with Redis flushed, every listing/search/facet endpoint still serves correct results from PostgreSQL within its query budget (CA3). |
| C30 | **Withdrawal convergence:** after a product is archived (or its last sellable variant withdrawn) and the update path converges, it is absent from listings, search results, facet counts and cursor walks (LC1, LC4, LC5). |
| C31 | **Deterministic pagination:** for every public sort, a full keyset walk over a stable snapshot returns each matching product exactly once, with no gaps and no duplicates, including a dataset engineered so that many rows share the primary sort value (SO2, PG6). |
| C32 | **Web/API parity:** Web and API return the same products in the same order for the same filter/cursor, the same public identifiers, and the same price/availability/rating/badge semantics, at the same selector-level query budget (RP7, master `# 10.9`). |
| C33 | **Listing query budget:** the listing endpoint stays within its approved budget with an N+1 guard active, and the count does not grow with page size or with the number of selected facets (QB1, QB5, QB6). |
| C34 | **Public data only:** the serving row and every storefront DTO contain no customer-scoped field; the same anonymous and authenticated requests receive identical projection-sourced content (SEC1, SEC2). |
| C35 | **Batch update has no N+1:** updating N products issues a number of statements bounded by the batch count, not by N; an unchanged row is not rewritten (BP1, BP4). |
| C36 | **Facet counts agree with the grid:** for a given filter set, every counted facet value, when applied, yields a non-empty result, and the count matches the number of products the grid returns for that refined filter (F6) — including the variant-scope conjunction case of C24, where a union-only count would over-report and the satisfier confirmation step (F6a) is what makes the number exact. Counts presented as exact are asserted exact; only an F7-labelled degraded count may differ. |

Item 5's **C21** (placement outcomes are unchanged with `PriceProjection`/`ProductListingProjection`
stale or emptied) already asserts T6/T7 from the checkout side and is **not** duplicated here.

### 25.4 Review-only (continuing the `V` series)

| # | Rule |
|---|---|
| V27 | Storefront serving state creeping back into `catalog` — a denormalized price/stock/rating/popularity column, a facet or GIN index, a `source_version`, or a "just for the grid" field (R8, ADR-0003 §1/§3). |
| V28 | A second listing read path: a view, DRF queryset, management command, backoffice screen or export that assembles cards itself instead of calling the storefront selector (RP3, master `# 10.9`). |
| V29 | A request-time OLTP fallback introduced for a projection or cache miss — including a "temporary" incident fix (NF1, NF3, NF7). |
| V30 | Redis (or the CDN) becoming the only copy of listing state, or a cache treated as a correctness source (CA2, CA3). |
| V31 | A multi-predicate variant-scope filter compiled against the product-level union array, or an aggregate column used to answer a same-variant conjunction (G3, G4, G9). |
| V32 | Variant-grained rows paginated and then grouped into products, or the satisfier relation used as the ordered/paginated row source (PG5, encoding E-b's rule). |
| V33 | Private, customer-scoped or personalized data added to the shared projection, or a personalization branch grafted onto the shared selector instead of a separately owned model (SEC2, SEC4). |
| V34 | A domain, an ERP import, a signal handler, a `save()` override or an admin action writing a serving row directly, bypassing `application/storefront` (O1, UP2). |
| V35 | Item 12's guard reinvented ad hoc in the updater, or checkout's owner-defined freshness guard and the projection's `source_version` treated as the same mechanism (PU8, PU9). |
| V36 | `application/storefront` reaching a domain's internals — a models import, a raw query against a domain table, or an "efficient" join across the boundary — instead of `<domain>.public` (O4, R5). |
| V37 | A facet, sort or search field whose value originates in the projection and exists nowhere in authoritative state, making a rebuild lossy (F2, RB1) — the manual merchandising boost being the concrete case to watch: a boost typed into a serving row, or an admin screen that edits the projection, is this failure (SO6, SO6b). |
| V38 | A card/display price policy and a price sort/cursor policy drifting apart — a `ProductCard` change that starts showing a matched-variant price while the sort key and the cursor keep using the product-wide aggregate, or the reverse (SO3c, SO3d). |

---

## 26. Acceptance checklist

- [ ] The projection has exactly one owner, `application/storefront`, and every forbidden home is
      enumerated (§4.1, §4.2, O1–O6).
- [ ] `domains/catalog` contains no storefront projection state, no facet index and no
      `source_version` (R8, V27, ADR-0003 §1/§3).
- [ ] The grain is explicitly decided — one row per `Product × Language` — with alternatives A–D
      evaluated and rejected by reason (§6.1, §6.2).
- [ ] Variant-scope filter false positives are structurally impossible: existential same-variant
      matching plus the per-variant satisfier structure (§6.3, §6.4, G1–G9, C24).
- [ ] Web and API use the same application read path and the same selector (RP1, RP3, C32).
- [ ] No ORM object, QuerySet, manager, paginator, cache client or search-vector type crosses
      `application/storefront/public.py` (SP2, SP3, A31).
- [ ] The projection is serving state, never checkout truth; `place_order` revalidates through owning
      domains (T3, T6, T7, R13, item 5 C21).
- [ ] Typed EAV remains the source of truth; listing facets are derived and fully rebuildable from it
      (F1, F2, C26).
- [ ] A listing request performs no EAV traversal and no cross-domain join chain (F3, QB3, C25).
- [ ] The projection is fully rebuildable from OLTP truth; events are acceleration, not the
      historical source (RB1, RB2, RB3).
- [ ] Duplicate, retried and out-of-order updates cannot regress projected state (PU1–PU5, C27).
- [ ] The exact stale-update version mechanism remains item 12's, and is not defined here (PU8,
      §16.2); checkout's freshness guard is a different mechanism (PU9).
- [ ] Cache loss loses no listing state; PostgreSQL alone can serve the storefront (CA3, C29).
- [ ] A projection miss triggers no synchronous OLTP reconstruction and no in-request rebuild (NF1,
      NF3, NF4, C28).
- [ ] Withdrawn or non-visible source state disappears from every serving surface after convergence
      (§17, LC1–LC5, C30).
- [ ] Sorting is deterministic with a mandatory final tie-break key, and keyset pagination operates
      at the visible-result grain established at build time (SO2, PG1, PG5, PG6, C31).
- [ ] No sort input exists only as serving state: the manual merchandising boost has an assigned
      authoritative owner or it is disabled, and every enabled sort key survives a rebuild (SO6,
      SO6a, SO6b, RB1, C26, V37).
- [ ] Filtered-price semantics are left open, not silently decided by the sort: the product-wide
      baseline is legal, and display, sort key and cursor must move together whenever the policy is
      chosen (SO3a–SO3d, V38).
- [ ] A variant-scope facet count ends in the exact satisfier predicate; the union array is only a
      candidate prefilter, and only an F7-labelled count may be approximate (F6, F6a, C36).
- [ ] Batch rebuild/update is set-based, coalesced and no-op-suppressed; the per-SKU loop is
      forbidden by name (BP1, BP2, BP4, C35).
- [ ] The projection contains public storefront data only; no private authorization decision reads it
      (SEC1–SEC4, CM6, C34).
- [ ] Projection staleness cannot compromise `Order` correctness — every failure row's commercial
      impact is `None` (§23, T7).
- [ ] No event name, payload or version from item 8 is designed (UP4).
- [ ] No `ProductCard`, `Facet` or `Badge` field from item 7 is designed (CT6, RP6).
- [ ] No `source_version` type, algorithm or SQL guard from item 12 is designed (§16.2).
- [ ] OpenSearch is not introduced; PostgreSQL is the MVP search engine (S1, S2).
- [ ] No contradiction with ADR-0001…ADR-0007 (§28, row 14).

---

## 27. Explicitly deferred decisions

| Deferred | Owner |
|---|---|
| `ProductCard` / `Facet` / `Badge` DTO fields and their pagination-metadata shape | Phase 0 item 7 |
| Event names, payload schemas, versions, the registry and compatibility policy | Phase 0 item 8 |
| Queue/failure-domain matrix and DLQ policy for `tasks.projections.*` beyond master `# 20.1` | Phase 0 item 9 |
| Trace propagation fields carried through the projection update path | Phase 0 item 10 |
| `Money` / `PublicId` implementation | Phase 0 item 11 |
| `source_version` type, generation algorithm, per-source mapping and the guarded upsert SQL (§16.2) | Phase 0 item 12 |
| Whether popularity gains a consent-gated analytics source beyond master `# 10.7`'s MVP signals | Phase 0 item 13 |
| The physical projection schema: columns, types, keys, constraints, indexes and the Django model | Phase 4 |
| Which encoding realises the satisfier structure — E-a nested-in-row or E-b companion relation (§6.5) | Phase 4, by measurement, within G1–G12 |
| Which variant-scope range attributes are filterable per-variant vs display/comparison-only (G11) | Phase 4 / catalog merchandising policy |
| Whether an active variant-scope filter changes the **effective price** — for card display, for the price sort key and for cursor construction alike (SO3b) | a **joint** storefront contract decision (sort + display + cursor together), recorded before Phase 4; item 7 may define the card's price representation but may not decide the sort semantics alone (SO3c, SO3d) |
| The authoritative owner and durable source of the **manual merchandising boost** (SO6a) | a later decision respecting the frozen dependency graph; until it is made the boost stays disabled (SO6b) — it is never stored in the projection |
| Search language configuration, stemming, ranking weights, autocomplete tuning; whether the search document is in-row or a sibling structure (S5, S6) | Phase 4 |
| Cursor codec, cursor field list and page-size limits (PG8) | Phase 4 / item 7 |
| Cache keys, TTLs and invalidation topology beyond master `# 10.5`/`# 22.7` (CA6) | Phase 4 |
| The approved numeric query budget per storefront endpoint (QB5) | Phase 4 performance tests, per master `# 22.5` |
| The numeric projection-freshness threshold, its metric and its alert (CM8) | the operations/performance phase |
| Rebuild mechanics: batch sizes, chunking, throttling, in-place vs build-and-swap (RB6, RB8, BP7) | Phase 4 |
| Tombstone retention policy for non-visible rows (LC8) | Phase 4 |
| A personalized/private price or entitlement read model | a separate artifact + a new ADR (SEC4) |
| OpenSearch adoption | master `# 10.8` measurement gate + a new ADR |
| The AST/contract-test implementations for A29–A35 and C24–C36 | Phase 1+ |
| Any weakening of §4–§24 — a second listing path, an OLTP fallback, a domain writing the projection, personalized data in the shared row, a union-array variant conjunction | requires a new ADR |

---

## 28. Self-review record

| # | Check | Result |
|---|---|---|
| 1 | The projection cannot drift back into `catalog` | Pass — §4.2 rejects `domains/catalog` by name with the mechanism (it would need four sibling domains, violating R2, and money/stock/rating/facet columns forbidden by ADR-0003 §1). O2 keeps a domain unaware it is projected, A30 forbids a domain referencing the model, and V27/V34 cover the review-only drift. |
| 2 | Projection price/stock cannot become checkout truth | Pass — T3/T6/T7 state it, R13 inherits item 5's PR2/INV3, CT3 marks price/availability as display facts, §23 rows 8–10 walk the stale cases and land on `None` commercial impact via the owning domains' authoritative gates, and item 5's C21 already asserts it from the checkout side (not duplicated, §25.3). |
| 3 | Product-level union facets cannot cause cross-variant false positives | Pass — §6.3 states existential same-variant matching with the worked `red/M`, `blue/L` example; G1 classifies scope from catalog metadata; G2 preserves per-variant grouping; G3 requires one entry to satisfy the whole conjunction; G4 removes the "is one predicate safe?" judgement by routing **all** variant-scope predicates through the structure; G8/G9 extend it to price and availability so an aggregate can never answer a same-variant question; C24 and C36 test it; V31 is the review check. This is recorded as the main reason ADR-0008 exists (§1.3). |
| 4 | SKU-grained rows are not paginated and then grouped | Pass — grain A is chosen (§6.1), grouping happens at **build** time (§6.6), PG1 states the visible grain is the row grain, PG5 forbids the naïve shape by name, and encoding E-b is admitted only as an `EXISTS` semi-join that is never the ordered/paginated row source (§6.5, G10). C31 asserts the resulting pagination property, V32 is the review check. |
| 5 | No request-time OLTP fallback survives anywhere | Pass — NF1–NF7 give the rule, the admissible three-tier hierarchy, the "not listable" answer for a missing row, and the explicit rejection of the incident-time exception; A34 forbids a rebuild call from `interfaces/*`; C25 asserts no OLTP table is touched; C28 asserts a missing row triggers neither composition nor rebuild; CM9 removes staleness as a justification; V29 is the review check. |
| 6 | Redis cannot become truth | Pass — R12, CA1–CA3, C29 (flush and still serve within budget), §23 row 6, V30. Facet-count caching (F8) and fragment caching (CA4) are both explicitly disposable. |
| 7 | No domain writes the application projection | Pass — O1/O2/UP1/UP2 state it; the update path (§14) routes every change through Outbox → task → the storefront use case; A30 is the static check; V34 names the indirect routes (signal, `save()` override, admin action, ERP import). |
| 8 | `application/storefront` reads only `<domain>.public` | Pass — O4 and R5, master `# 7.6`'s builder-dependency rule restated; BP3 routes a missing batch capability to a new public symbol rather than a models import; V36 is the review check; §25.1 confirms the matrix already encodes it. |
| 9 | A stale/out-of-order event cannot overwrite newer state | Pass — PU1–PU7 freeze idempotence, reorder safety, monotonic non-regression, per-fact convergence, read-path neutrality and no serving rollback; C27 tests it; §23 rows 1–2 record the outcome. |
| 10 | Item 12 is not consumed | Pass — §16.2 lists the five things item 12 owns (column, algorithm, per-source mapping, SQL guard, per-fact expression), PU8 forbids citing item 6 as authority for a version scheme, and the master's `ON CONFLICT` sketch is explicitly labelled master text rather than a decision made here. PU10 keeps `source_version` off domain tables. |
| 11 | Item 12's guard is not confused with checkout's freshness guard | Pass — PU9 contrasts them on all four axes (protected object, failure mode, owner, timing) and names both failure modes of conflating them: a read-model version column on OLTP (ADR-0003 §3) or a projection version deciding a commercial write (T6). V35 is the review check. |
| 12 | Item 7's DTOs are not designed | Pass — §8 freezes **categories**, not fields; CT6 and RP6 state that item 7 owns `ProductCard`/`Facet`/`Badge` and may expose a different shape; §12's PG8 leaves cursor/pagination DTO shape to item 7; §27 lists it as deferred. No field list appears anywhere. |
| 13 | OpenSearch is not introduced | Pass — S1 freezes PostgreSQL (projection + FTS + `pg_trgm` + GIN) as the MVP engine, S2 keeps master `# 10.8`'s measurement gate and requires a new ADR, and §27 lists adoption as deferred. The projection's own search fields are classified as serving mechanics (S3), which is what keeps the future migration contract cheap. |
| 14 | No contradiction with ADR-0001…ADR-0007 | Pass — **0001:** R10 keeps the SKU as the only sellable unit (G6 counts only sellable variants); I5/I6 keep internal bigints internal and `PublicId` external. **0002:** F1/F2 keep typed EAV authoritative and the facet representation derived; G1 consumes `scope`/`is_variant_axis` as catalog-owned metadata rather than redefining them. **0003:** §4 is its positive form; R8/V27/PU10 keep price, stock, ERP identity, facet indexes and `source_version` out of catalog; I7 keeps the per-language physical-column model. **0004:** §4 applies §4 (one application owner) and §5 (interfaces delegate); SEC3 applies §6 (authorization follows state ownership, and a derived read model is not the owner). **0005:** O3/SP1 apply §7 (one importable surface, application-owned ORM internal); O5 applies §7's no application→application; O6 confirms no port is introduced; §25.1 confirms no matrix cell moves. **0006:** SP4 uses the actor primitive only where private state would exist and adds no business vocabulary to `core`; `integrations/*` gains nothing. **0007:** untouched — no rule here enters the placement transaction, and T6/§23 preserve its guarantees. |
| 15 | The master is followed where it already decided, and refined only where it left a hole | Pass — grain (`# 7.6`), union array and promoted range columns (`# 7.2`), `SORTS` map and keyset (`# 10.2`, `# 10.3`), facet counts (`# 10.4`), shared DTO path and fragment cache (`# 10.5`), popularity MVP sources (`# 10.7`), Web/API parity (`# 10.9`), queue routing and coalescing (`# 20.1`, `# 20.2`), query contract and budgets (`# 22.2`, `# 22.4`, `# 22.5`), cache rules (`# 22.7`) are all inherited and cited. Three refinements are made, each stated openly rather than smuggled in: the satisfier structure for variant-scope predicates (§6.4), which the master's product-level union does not provide and which §1.3 records as ADR-0008's principal reason; F6a's confirmation step, which is the same refinement applied to counting; and SO6's precondition on master `# 10.7`'s "optional manual merchandising boost" — the boost stays in the popularity model exactly as the master allows, but only once it has an authoritative owner, because RB1 otherwise makes it unreproducible. None of the three contradicts the master; each closes a place where the master's shape is silent or exact only for the product-scope case. |
| 16 | The failure matrix has no ambiguous or unsafe cell | Pass — §23 gives all fourteen rows a display impact, a commercial impact and a recovery owner; every commercial cell is `None`, and each one names the mechanism that makes it `None` (revalidation, atomic reservation, authoritative re-pricing, independent domain commit, rebuildability) rather than asserting it. Rows 3, 12 and 14 route to reconciliation/rebuild and alerting, never to a fallback. |
| 17 | No private data can enter the public projection | Pass — SEC1/SEC2 enumerate the forbidden categories, CT5 repeats it at the content level, SEC3 forbids authorization decisions on it, SEC4 sends any personalized model to its own artifact and ADR, CA5 records why the anonymous cache is safe as a consequence, C34 tests it, V33 is the review check. |
| 18 | Nothing here creates code, schema or infrastructure | Pass — §1.2 states it, SP8 and §4.3 state that no file is created, every encoding in §6.5 is labelled a Phase 4 decision, and §27 routes every physical artifact — model, columns, indexes, cursors, cache keys, batch sizes, budgets, thresholds — to a later owner. |
| 19 | Rebuildability is a real property, not an aspiration | Pass — RB1 makes it architectural, RB2 forbids event-sourcing dependence (including the archived-partition case, §23 row 14), F2 requires facets to reproduce, RB4 makes divergence a defect rather than a tolerated difference, C26 asserts it twice over (identity with the event-updated state, and idempotence of a second rebuild), and V37 flags a projection-originated value that would make a rebuild lossy. |
| 20 | The query-budget contract is enforceable, not decorative | Pass — QB1–QB8 fix boundedness, `O(1)`-in-page-size, no per-card SQL, no EAV traversal, satisfier-predicate inclusion (G7) and CI compatibility; A35 keeps the read shaped; C25, C33 and C36 assert table access, budget and facet-count agreement; QB5 defers only the number, citing master `# 22.5`'s mandatory listing budget. |
| 21 | No projected value can be truth-by-accident, boost included | Pass — SO6 forbids the projection owning the manual boost or holding it only as serving state; SO6a refuses to invent an owner here (not `catalog` per R8, no new domain, no application state) while requiring any future owner to be legally reachable under O4/O5/R7; SO6b makes "disabled" the default rather than "stored in the row"; RB1 now states that every **enabled** facet/sort/search value must be reproducible from an authoritative source; C26 tests it; V37 names the concrete drift (a boost typed into a serving row, an admin screen editing the projection). Disposability (T8, RB1) is strengthened by this, not weakened: nothing gains a backup obligation. |
| 22 | Sorting does not pre-empt the filtered-price UX question | Pass — the earlier unconditional "sorting never depends on which variant matched" is replaced: SO3 keeps the row-level-scalar requirement that SO2/PG2 actually need, SO3a records the product-wide baseline as legal **and** records its visible consequence with the `red`/`blue` example's shape, SO3b defers display/sort/cursor semantics together, SO3c freezes coherence without mandating any mechanism (no dynamic aggregation, no matched-variant sort, no new column, no new encoding), and SO3d makes it a joint contract decision that item 7 cannot take alone. V38 is the review check, and §27 carries the deferral. |
| 23 | "Facet-count candidacy" cannot be read as permission to count on the union | Pass — F6a states the pipeline explicitly (`union prefilter → exact satisfier predicate → count`) and forbids the direct form; G4 now points at F6a instead of saying "candidacy only"; G5 records that a product-scope union needs no confirmation because it is already exact; F7 keeps degradation available but requires it to be labelled and forbids presenting an unconfirmed count as exact; C36 asserts count/grid agreement including the C24 conjunction case. F6 remains authoritative and is unchanged. |

Verdict: **PASS**.
