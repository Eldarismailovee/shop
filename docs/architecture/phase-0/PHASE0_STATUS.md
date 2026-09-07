# Phase 0 — Architecture Freeze: status tracker

Source of the item list: master `# 25. Roadmap` → `Фаза 0 — Architecture Freeze + ADR`.

**Phase 0 DoD:** the architectural dependency graph contains no domain↔domain imports; every
cross-domain use case has an owner; public contracts and event schemas are approved before any
production migration.

Phase 0 produces **documents and decisions only**. No Django code, packages, models, migrations,
settings or dependencies are created in this phase — that is Phase 1.

## Status legend

| Status | Meaning |
|---|---|
| `TODO` | Not started. |
| `IN PROGRESS` | Being drafted; not binding yet. |
| `DONE / FROZEN` | Decided, binding, and recorded in an artifact and/or ADR. Changing it requires a new ADR. |

## Items

| # | Item | Status | Artifacts |
|---|---|---|---|
| 1 | ERD Product/SKU/typed attributes | **DONE / FROZEN** | [ERD](../erd/catalog_product_sku_attributes.md), [ADR-0001](../../adr/0001-product-vs-sku-sellable-unit.md), [ADR-0002](../../adr/0002-typed-eav-source-of-truth.md), [ADR-0003](../../adr/0003-catalog-boundary-vs-storefront-projection.md) |
| 2 | Four layers `core/domains/application/interfaces` | **DONE / FROZEN** | [02-four-layer-architecture.md](02-four-layer-architecture.md), [ADR-0004](../../adr/0004-four-layer-modular-monolith.md) |
| 3 | Dependency matrix and allowed imports | **DONE / FROZEN** | [03-dependency-matrix.md](03-dependency-matrix.md), [ADR-0005](../../adr/0005-dependency-and-integration-wiring.md) |
| 4 | `public.py` contract template per domain | **DONE / FROZEN** | [04-domain-public-contract.md](04-domain-public-contract.md), [ADR-0006](../../adr/0006-public-contract-primitives.md) |
| 5 | `application/checkout` ownership of `place_order` | **DONE / FROZEN** | [05-place-order-use-case.md](05-place-order-use-case.md), [ADR-0007](../../adr/0007-place-order-atomic-idempotent-boundary.md) |
| 6 | `application/storefront` ownership of the listing projection | **DONE / FROZEN** | [06-storefront-listing-projection.md](06-storefront-listing-projection.md), [ADR-0008](../../adr/0008-storefront-listing-projection.md) |
| 7 | `ProductCard` / Facet DTO contract | **DONE / FROZEN** | [07-storefront-dto-contract.md](07-storefront-dto-contract.md); **no new ADR** — it instantiates ADR-0008 + item 4 (see below) |
| 8 | Event registry + versioning policy | **DONE / FROZEN** | [08-event-registry-versioning.md](08-event-registry-versioning.md), [event registry](../events/event-registry.md), [ADR-0009](../../adr/0009-event-contract-versioning.md) |
| 9 | Queue / failure-domain matrix + DLQ policy | **DONE / FROZEN** | [09-queue-failure-domain-dlq.md](09-queue-failure-domain-dlq.md), [queue / failure-domain matrix](../events/queue-failure-domain-matrix.md), [ADR-0010](../../adr/0010-async-failure-domain-isolation.md) |
| 10 | Trace propagation fields in Outbox/Inbox before partition migrations | **DONE / FROZEN** | [10-async-trace-propagation.md](10-async-trace-propagation.md), [ADR-0011](../../adr/0011-async-trace-causality-envelope.md) |
| 11 | `Money` / `PublicId` types | **DONE / FROZEN** | [11-money-public-id.md](11-money-public-id.md), [ADR-0012](../../adr/0012-money-currency-scoped-partial-order.md), [ADR-0013](../../adr/0013-event-id-distinct-identity-type.md) |
| 12 | `source_version` generation + guarded projection upsert | **DONE / FROZEN** | [12-source-version-guarded-upsert.md](12-source-version-guarded-upsert.md), [ADR-0014](../../adr/0014-storefront-projection-convergence.md) |
| 13 | Analytics MVP decision: sales/favorites only vs full consent-gated domain | **DONE / FROZEN** | [13-analytics-mvp.md](13-analytics-mvp.md); **no new ADR** — it selects a branch master `# 5` principle 37 / `# 10.7` / `# 25` already authorised (see below) |
| 14 | MVP / later marking per module | **DONE / FROZEN** | [14-mvp-later-module-marking.md](14-mvp-later-module-marking.md); **no new ADR** — it selects feature scope master `# 25`'s MVP line / `# 26` MVP governance already authorised (see below) |
| 15 | ADRs: listing projection, idempotency, no replica at launch, module boundaries, event versioning | **DONE / FROZEN** | [15-adr-closure.md](15-adr-closure.md), [ADR-0015](../../adr/0015-postgresql-command-idempotency.md), [ADR-0016](../../adr/0016-no-application-read-replica-at-launch.md); the other three requirements are covered without new ADRs — listing projection by ADR-0003 + ADR-0008 + ADR-0014, module boundaries by ADR-0004 + ADR-0005 + ADR-0006, event versioning by ADR-0009 (see below) |

## Phase 0 status

```text
Items 1–15                       DONE / FROZEN
PHASE 0 ARCHITECTURE FREEZE      COMPLETE
```

**PHASE 0 ARCHITECTURE FREEZE — COMPLETE**, as of 2026-09-06, with sixteen accepted and frozen ADRs
(ADR-0001…ADR-0016) and fifteen frozen items. Master `# 25`'s Phase 0 DoD is met: the architectural
dependency graph permits no domain↔domain import, every frozen cross-domain use case has exactly one
owner, and the public contracts and the event-schema policy are approved before any production
migration. Phase 0 produced **documents and decisions only** — no Django code, package, model,
migration, setting or dependency exists. Every `A*`/`C*`/`V*` check recorded across items 3–15 is an
obligation on Phase 1 and the implementing phases; **none is enforced yet**. The final audit is
[item 15](15-adr-closure.md) §12, and the Phase 1 handoff is [item 15](15-adr-closure.md) §15.

Changing anything frozen here now requires a new ADR that supersedes the one it changes.

## Notes on item 2

Frozen: the meaning and responsibility of the four layers, the skip-allowed dependency direction,
the `core` admission test, domain mutual invisibility, the application/domain invariant split,
storefront projection placement, the interface→domain direct-call rule, the authorization split,
webhook/payment/reconciliation ownership, the conceptual role of `integrations/` and `tasks/`, and
transaction ownership with the local-ACID-is-not-a-saga principle.

Deliberately **not** frozen by item 2, and therefore still open in the items above: the exact
dependency/import matrix (item 3), the integration adapter wiring and port direction (item 3), the
physical placement of the persistent `provider + external_id ↔ internal entity` mapping (item 3 for
architectural placement, Phase 3 for the concrete ERP schema), and `public.py` templates (item 4).

## Notes on item 3

Frozen: the full importer×imported dependency matrix (`ALLOW` / `PUBLIC ONLY` / `PORT ONLY` /
`SELF ONLY` / `FORBID` / `SPECIAL CASE` per cell); per-family `core` submodule allowlists; ports and
adapters with dependency inversion, every outbound port owned by an `application` module at
`application/<a>/ports.py` and no domain-owned ports; the single composition root in `config/`;
`application/erp_sync` as owner of the persistent `provider + external_id ↔ internal entity`
mapping; the composition root owning construction **and** injection, with `interfaces/*` and
`tasks/*` never importing `config/*` (entry points receive dependencies, never locate them, so the
production source graph stays acyclic because no runtime package imports back into `config`, which
is the root of the wiring dependencies); the split of a provider integration package
into an inbound `protocol` surface (importable by `interfaces/webhooks/<provider>`) and an `outbound`
adapter surface (known only to the composition root and provider tests); `tasks/*` never importing
`integrations/*`; `application/<a>/public.py` as the application
entry-point convention with application→application forbidden; application-owned ORM internal to its
module; the domain-local `admin.py` rule with no linter exception; the path-scoped migrations
exception; the test-tier policy; and the classification of every rule as import-linter, AST/static,
or review-only.

Deliberately **not** frozen by item 3: the `.importlinter` file and AST checker code (Phase 1),
physical packages/module names (Phase 1), the concrete injection mechanism at each entry point
(view/entry-point factory, `as_view()` binding, Celery handler registration, or another explicit
startup binding — Phase 1), the physical file names inside a provider package as long as the
`protocol`/`outbound` import surfaces stay distinguishable (Phase 1), port method signatures and
edge-type fields (per implementing phase), the `ErpVariantMapping` schema (Phase 3), and `public.py`
templates (item 4).

## Notes on item 4

Frozen: the uniform shape of `domains/<x>/public.py` as a thin façade (explicit imports, explicit
`__all__`, no `class`/`def`, no wildcard/alias/module re-export, no import-time side effect, no
logic); the eight allowed export categories and the forbidden persistence/internal/transport/vendor/
lazy categories; the DTO baseline `@dataclass(frozen=True, slots=True, kw_only=True)` with an
immutability-by-field-type rule (`tuple`/`frozenset`/nested frozen DTOs only — no `list`/`dict`/`set`/
`Any` and no `Mapping`/`Sequence`, key/value data being a frozen tuple of pairs), pure-and-total
members only, aware UTC instants, `Money`/`PublicId`; identity rules (an internal identifier may
never become a user locator, public API payload identifier, external webhook/integration identifier
or externally consumed event identifier, while strictly internal orchestration and strictly internal
versioned events/jobs may keep using one; no `id`/`pk` field on a public DTO); command semantics
(business verb, frozen result or `None`, no direct external/vendor network I/O — the domain's own
PostgreSQL work and the transactional Outbox row are not that — and Outbox instead of task
scheduling);
selector semantics (materialised immutable results, no QuerySet/lazy object, only disposable
cache/metrics/tracing side effects and no durable business/authorization/audit/compliance write);
authorization by construction — public
reads take no actor, protected operations take an explicit mandatory non-optional actor first, with
`actor=None` banned and privileged access an explicit system context, the actor type owned by `core`;
transaction participation (one semantic command, nesting is a savepoint implementation detail, no
independent commit, no `durable=True`, application owns the outer transaction); the public error
strategy — expected domain failures are domain-owned errors over a closed, business-free `core`
category set (an expected uniqueness race translated only at a nested savepoint and only when the
violated invariant is identified by name), while technical and unexpected faults (database
unavailable, unclassified `DatabaseError`, corruption, programmer bugs) propagate untranslated to the
platform boundary and are never dressed as business errors; public enum rules; immutable collection
returns; the three-class compatibility policy; and the contract checks Phase 1 must implement
(L20–L21, A14–A23, C1–C10, Y1–Y3, V11–V18, extending item 3 §15).

**[ADR-0006](../../adr/0006-public-contract-primitives.md) was required** and is accepted: item 4
introduces two `core` primitives — the actor type and the structural error categories — and thereby
extends `core` submodule allowlists that ADR-0005 §1 froze. ADR-0006 records their placement and
per-family consumers (`domains`, `application`, `interfaces`, `tasks`, plus the composition root,
which passes values but owns no semantics) and the two negative rules: **`integrations/*` depends on
neither primitive**, and neither do migrations. ADR-0005's text is extended by reference, not
rewritten; L10 and L13 are untouched.

Deliberately **not** frozen by item 4: the actor type's fields/roles/capabilities model and the final
`core.actor`/`core.errors` module and class names (Phase 1 / the authentication phase; their
placement and consumers are frozen by ADR-0006), whether a project-approved immutable mapping type is
ever adopted, the mechanism by which state may legitimately change as a consequence of a read, the
physical
file layout inside a domain (Phase 1), the checker and contract-test implementations (Phase 1),
`Money`/`PublicId` implementation (item 11), the public API of any real domain (its own phase),
`place_order` (item 5), storefront/`ProductCard` shapes (items 6, 7), the event registry (item 8),
and whether a given domain answers a non-visible private object with `NotFound` or `NotAllowed`.

## Notes on item 5

Frozen: `application/checkout` as the single owner of `place_order`, with every alternative home
rejected by name; the per-domain responsibility split (pricing, inventory, orders, catalog,
promotions, delivery, payments) reached only through `<domain>.public`; the architectural role of
`CheckoutSession` — workflow state, never Order/price/inventory truth, actor-scoped, revalidated at
placement; the semantic input contract and the trust rule that a client- or session-supplied price,
discount, total, availability, reservation success or payment success is never authoritative;
**one** outer local `transaction.atomic()` owning every durable write, with the master's pre-lock
preparation phase frozen as read-only, lock-free, non-durable and revalidated in-transaction; the
requirement — not the mechanism — that prepared data may never back a durable write after becoming
stale, revalidated through each owning module's **freshness/revalidation guard** (with inventory's
and promotions' atomic commands being their own authoritative gates), while checkout reads no
internal version column, assumes no uniform version field and introduces no global counter; the
canonical placement sequence with its deterministic lock rank order and a concurrency analysis
(last-unit depletion, duplicate HTTP retry, double-click, failure before/after reservation and order
creation, commit ambiguity); reservation semantics — created and transitioned only by
`inventory.public`, in the same transaction as the Order, so an orphan committed reservation is
structurally impossible; authoritative pricing and the immutable commercial snapshot, never rewritten
after commit and never sourced from a projection; the durable idempotency behavioural contract —
claim and completion inside the placement transaction; **against a committed record** same
fingerprint replays, a different fingerprint is a `Conflict` and a different principal is
`NotAllowed`, while a rolled-back attempt leaves no record and no retained fingerprint, so the key is
simply unused again (a *committed* key can never be reused for materially different input, and a
failed attempt reserves nothing); contenders serialized on the durable uniqueness mechanism with no
separately committed "processing" claim; bounded lock waits surfacing as technical faults;
principal-scoped replay, so an idempotency key is never an object-access token; the split of
technical failure at `COMMIT` — before it, everything rolls back and no Order exists; after it, the
committed placement stands, the invocation may still fail technically, a same-key retry replays, and
**no compensation is attempted**; the result contract and its forbidden leakage; the payment
boundary — no provider I/O on any branch, provider interaction strictly post-commit and owned by
`application/payments_gateway` per ADR-0005 §2/§7; the Outbox-in-transaction responsibility; a
failure matrix covering all of the above; the error split between domain-owned errors and checkout
application errors with technical faults left untranslated; and the checks A24–A28, C11–C23 and
V19–V26 that later phases must implement.

**[ADR-0007](../../adr/0007-place-order-atomic-idempotent-boundary.md) was required** and is
accepted, for the three decisions that are not mere specification of ADR-0004/ADR-0005: the single
durable placement transaction (resolving the apparent tension between "one local `atomic()`" and the
master's `PREPARE`/`SHORT TX` structure), the canonical idempotent placement semantics (completion
never precedes the Order commit, the claim dies with a rollback, replay is principal-scoped), and
the assignment of the post-commit provider step to `application/payments_gateway`. ADR-0007 changes
**no** dependency-matrix cell and **no** `core` submodule allowlist; L1–L21 stand unedited.

Deliberately **not** frozen by item 5: every schema (`CheckoutSession`, `Order`/`OrderItem`,
reservation, `PaymentAttempt`, `IdempotencyKey`); the final `place_order` signature, its input DTO
and its result DTO fields; the request-fingerprint field list; how a principal/context is
fingerprinted from the actor; the **mechanism** of each owner's freshness/revalidation guard (each
owning domain's own phase — item 12's storefront `source_version` decision is separate and
untouched, and catalog `Product`/`ProductVariant` gain no storefront `source_version` state); which
post-commit payment trigger (an Outbox-driven task or a second
transport entry point) applies per payment method; whether a given payment method commits the
reservation at placement or later; the UX policy on a price that changed at placement (authoritative
re-pricing itself **is** frozen); event names/schemas/versions (item 8); delivery and promotion
internals; `Money`/`PublicId` (item 11); and the concrete locking SQL.

## Notes on item 6

Frozen: `application/storefront` as the single owner **and single writer** of
`ProductListingProjection`, with every alternative home rejected by name and no domain aware that it
is projected; the three-way truth split — domain/OLTP truth, storefront serving source, commercial
transaction truth — and the rule that the projection is a *derived serving read model* that is never
checkout truth and never the basis of a security/authorization decision; the grain, one row per
`Product × Language`, with grain alternatives A–D evaluated and rejected by reason; **existential
same-variant matching** plus the per-variant satisfier structure that makes a conjunction of
variant-scope predicates (axes, variant-scope attributes, price, availability) exact and cross-variant
false positives structurally impossible, with row-level aggregates confined to sorting/display and
the union array confined to product-scope predicates and count candidacy; copied-scalar projection
identity with **no** cross-boundary ORM relation, deletion propagated by the update path rather than a
cascade, and internal bigints leaving only inside a signed opaque cursor; the categories (not the
schema) of denormalized serving data, and the rule that copied data never becomes owned truth; typed
EAV as source of truth with derived facet representation per facet kind and scope, and no EAV
traversal in a request; PostgreSQL as the MVP search engine with search fields as serving mechanics;
deterministic sorting with a mandatory final tie-break key, the product-wide price-sort baseline with
filtered-price semantics deliberately left open under a frozen display/sort/cursor coherence rule, MVP
popularity restricted to master `# 10.7`'s approved first-party signals, and the rule that no sort
input — manual merchandising boost included — may exist only as serving state, so the boost stays
disabled until an authoritative owner is assigned; keyset pagination at a visible grain established at **build**
time, with post-pagination product grouping forbidden; the single shared Web/API read path
`projection → selector → immutable DTO → HTML/JSON` and the no-ORM/no-QuerySet/no-paginator
`application/storefront/public.py` boundary; the Outbox-driven incremental update path with
`application/storefront` as update owner and coalesced batch updates preferred; **full
rebuildability** from OLTP with events as acceleration rather than the historical source, plus
targeted rebuild and reconciliation; the stale-update non-regression requirement; lifecycle
convergence with a positive visibility predicate; the eventual-consistency model with a required (but
un-numbered) freshness threshold and alert; **no request-time OLTP fallback** on a projection or cache
miss; cache disposability; the query-budget and batch-rebuild contracts; a fourteen-row failure matrix
whose every commercial-impact cell is `None`; the public-data-only rule; and the checks A29–A35,
C24–C36 and V27–V38 that later phases must implement.

**[ADR-0008](../../adr/0008-storefront-listing-projection.md) was required** and is accepted. ADR-0003
stated the projection's home only negatively, from `catalog`'s side, and ADR-0004/ADR-0005 mention it
in one line each; item 6 makes four decisions that are new and binding: existential same-variant
matching with the satisfier structure (which **refines** master `# 7.2`'s product-level union array,
the one place where the master's representation is silently wrong for variant-scope conjunctions), the
derived-serving/eventual-consistency classification including the ban on security decisions over the
projection, full rebuildability from OLTP, and the prohibition of a request-time OLTP fallback.
ADR-0008 changes **no** dependency-matrix cell and **no** `core` submodule allowlist; L1–L21 stand
unedited.

Deliberately **not** frozen by item 6: the physical projection schema — columns, types, keys,
constraints, indexes and the Django model (Phase 4); which encoding realises the satisfier structure
(in-row `jsonb` + GIN, or a companion variant-grain relation used only as an `EXISTS` semi-join);
which variant-scope range attributes are filterable per variant versus display/comparison-only;
whether an active variant-scope filter changes the effective price for display, price sorting and
cursor construction (a **joint** storefront contract decision taken for all three together before
Phase 4; item 7 may define the card's price representation but not the sort semantics); the
authoritative owner and durable source of the manual merchandising boost (no owner is chosen here, no
new domain or application state is invented, and the boost stays disabled meanwhile); search language
configuration, stemming, ranking weights and whether
the search document is in-row or a sibling structure; cursor codec/fields and page-size limits; cache
keys, TTLs and invalidation topology; the approved numeric query budget per endpoint; the numeric
freshness threshold and its alert; rebuild mechanics (batch sizes, chunking, throttling, in-place vs
build-and-swap) and tombstone retention;
`ProductCard`/`Facet`/`Badge` DTO fields (item 7); event names/schemas/versions (item 8); the
`source_version` column, generation algorithm, per-source mapping and guarded upsert SQL (item 12);
the popularity source beyond MVP (item 13); `Money`/`PublicId` (item 11); a personalized/private price
read model and OpenSearch (both requiring a new ADR).

## Notes on item 7

Frozen: the storefront DTO baseline for `application/storefront` (item 4's `frozen/slots/kw_only`
semantics, immutability by field type, tuples/frozensets, no `Any`/`Mapping`/`Sequence`/ORM/QuerySet/
paginator/cache/transport/vendor type, no `id`/`pk`) plus transport-neutrality, the no-`Any`-union rule
and the ban on a bag-of-fields DTO; **`ProductCard`** — Product-grained, addressed by
`Product.public_id`, with brand display facts, a vendor-neutral storage-relative media reference, a
**basis-explicit** price, a two-member display availability state, an optional rating summary and
structural badges — together with its enumerated forbidden field categories (ORM identity,
ERP/provider ids, cost/margin, customer/private state, gallery/spec/long description, `source_version`,
cache/search types); **`Badge`** as a structural code with an intentionally non-enum, additively
growing vocabulary that a transport localizes and safely skips when unknown; the **facet public
identifier strategy** — application-owned facet keys built from the immutable
`AttributeDefinition.code` or a closed structural list, the two vocabularies disjoint by construction,
and per-kind value identity (`AttributeChoice.code`, `Category`/`Brand` `PublicId`, `bool`, or bounds)
deliberately **not** flattened into one wire form, with no internal bigint anywhere; the **six frozen
facet variants** (choice, boolean, integer range, decimal range, money range, entity choice) in a
closed union with a shared key/label/scope header, scope-level range bounds, and the rule that a DTO
describes a facet without exposing or encouraging the product-level union; **the two sources of a
facet's `scope`** — copied from catalog `AttributeDefinition` metadata for attribute-derived facets,
and fixed by the storefront contract from already-frozen business semantics for structural facets
(category/brand → `PRODUCT`, price/availability → `VARIANT`), with neither guessed, transport-inferred
nor request-overridable, and no scope primitive in `core`; the
**count-quality model** (`EXACT` meaning satisfier-confirmed per item 6 F6a, `APPROXIMATE`,
`UNAVAILABLE`) with its `iff` invariant, its four mutually distinct states — never conflating unknown,
omitted, `0` and "approximately 0" — and a **separate** option-set truncation field; selection as
result state with a selected option always surviving, and **application-owned canonical, deterministic,
total ordering** where tuple order is render order; the materialised **`ProductListingResult`** (no
`Paginator`/`Page`) composing cards, optionally-present facets, pagination metadata and the canonical
query echo, with keyset and bounded numbered pagination as two metadata variants of **one** listing
implementation, an **opaque** single-field cursor exposing no payload, and no mandatory exact total;
the typed, whitelist-driven **round-trip query** that both transports map into, with the six
`FilterTerm` field shapes and their invariants (non-empty canonical value tuples, at least one range
bound, `minimum <= maximum`, one currency on money bounds) and with no caller-controlled `scope`,
`EntityMatch`, operator or internal token; the **combination semantics** — `AND` between different
facet keys, `OR` between values of one discrete key, with every variant-scope disjunction evaluated
**inside** ADR-0008's single-variant existential, so `(red OR blue) AND (M OR L)` still requires one
satisfying sellable variant; **canonicalization** — at most one term per `FacetKey`, repeated terms
merged, duplicates removed, deterministic value and term ordering, and empty/both-values/boundless
terms dropped — as one shared function producing identical canonical queries, URLs and cache keys for
Web and API; the meaning of an **exact discrete facet count** as the card set of the current canonical
query with that option added to the selection of its own key (idempotent for an already-selected
option), with no separate disjunctive or self-excluding counting model; the **coherent `CardPrice`
comparison pair** — `amount`, `regular_amount` and `discount_percent_bps` from one pricing
observation, matching currencies, `regular_amount > amount`, both comparison fields absent when no
coherent pair exists, the percentage computed once from that exact pair, and no representative SKU
identity exposed; the **localization split** (domain content already localized in the DTO,
one language per result, no RO/RU pair on a card; interface vocabulary and every public enum stay
structural codes); availability and rating as display state with no new inventory or review state
machine; the additive-vs-breaking classification of the likely future changes; and the checks
A36–A41, C37–C54 and V39–V51 that later phases must implement.

**No new ADR was required.** Item 7 gives the first concrete shape to a contract whose existence,
owner, source, path, style and constraints were already frozen, and the delegation is explicit in both
directions: ADR-0008 lists `ProductCard`/`Facet`/`Badge` fields and the pagination-metadata shape under
"Out of scope of this ADR", and item 6 §27 assigns them to item 7 as an artifact-level deferral. No
boundary moves, no dependency-matrix cell moves, no `core` submodule allowlist changes, and no frozen
public contract changes shape; L1–L21 stand unedited and the artifact adds no import edge. Artifact
§1.3 names the five changes that **would** have required an ADR and are deliberately not made: a facet
vocabulary or language primitive in `core`; letting an active variant filter change the card's
effective price; an internal bigint as a facet identifier; an `EXACT` count taken off the union without
same-variant confirmation; and a transport-specific DTO or a second read path. The frozen `OR`-within-
key semantics contradicts no accepted ADR: none states multi-select-within-one-facet semantics, and
master `# 7.2`'s `facet_choice_ids @> ARRAY[:choice_ids]` illustrates the array-containment mechanism
for a set of distinct-attribute selections rather than a UX rule for two values of one facet.

Deliberately **not** frozen by item 7: `Money`/`PublicId` implementation (item 11); the filtered-price
display/sort/cursor policy — `PriceBasis` has exactly one legal member until item 6 SO3d's joint
decision; the physical projection schema and the facet-vocabulary/label serving structure (Phase 4);
the cursor codec, its internal fields, the signing scheme and page-size/numbered-depth limits (Phase
4); which **physical predicate** realises the frozen within-key `OR` (`&&`, per-key containment groups
or a satisfier-side disjunction), bounded by item 6 G3/G4/G7; the physical projection support that
yields `CardPrice`'s coherent comparison pair; the concrete `FacetKey` spelling and
namespace separator (Phase 4, externally immutable once shipped); slug → `PublicId` route resolution
for category/brand pages; per-store availability faceting, blocked on a public locator for `Store`;
parametrized badges; the facet/option ordering *policy* within the frozen determinism; a `core`
language primitive replacing `StorefrontLanguage` (an ADR if adopted); candidate-refined range bounds
(a breaking change if adopted); `source_version` (item 12); event schemas (item 8); queue/DLQ (item 9);
trace fields (item 10); analytics popularity (item 13); the manual merchandising boost owner, which
stays unassigned with the boost disabled; and the exact Web HTML/HTMX and DRF serializer
representations.

## Notes on item 8

Frozen: the **scope** of the registry (durable internal async messages through Outbox/Inbox) and the
eight message classes it deliberately does not govern, with the rule that a provider wire schema and
the internal registered message derived from it are two separate contracts and provider vocabulary
never becomes internal event vocabulary; **one semantic owner per message type**, ownership following
the fact, with no central `events` domain, no shared business-message package, no business message
type in `core` (`core.events` owns *mechanism* — envelope, registry lookup, codec, validation,
contract-failure signalling — and nothing else), a registry that indexes contracts without owning any,
and transport packages (`interfaces/*`, `tasks/*`, `integrations/*`) that are never owners or
producers; **the asynchronous boundary as a data boundary** — no consumer imports a producer's
contract, and the canonical owner-internal source reaches the validator only as a **generated,
checked-in, versioned data artifact** (canonical source → deterministic generation → checked-in
artifact → `core.events` validator → consumer validation), with the composition root explicitly
**forbidden** from importing an owner-internal contract because `config/ → domains/<x>` is
`PUBLIC ONLY` and a message schema is not a `public.py` export, and every realisation bound by "no
consumer → producer import edge, no matrix cell moves, no widened `public.py` export list, no shared
business-message package"; a single registry of async messages with a mandatory
`kind = EVENT | COMMAND` discriminator, fixed for the life of a type, introducing no `core` enum and
carrying one identical rule set for both kinds; the **naming model** (lowercase, dot-separated,
owner-qualified first segment, no version suffix, no module/class/queue/transport word, no vendor name
as first segment, meaning immutable once published, retired names never reused); **instance identity**
`event_id` — assigned in the emitting transaction, unchanged across every retry/replay, new for a
genuinely new fact, never a broker delivery identifier, and a separate identity space from a provider
`external_event_id`, conceptually the item 11 UUID primitive; the **four-field semantic envelope**
(`event_id`, `event_type`, `schema_version`, `occurred_at`) with owner derivable from the type, no
transport concern, no metadata bag and one reserved item 10 extension point; `occurred_at` as business
truth time in aware UTC, unchanged by retries and never an ordering key; **payload discipline**
(explicitly typed, immutable, serialization-neutral, bounded, deterministic; no ORM/QuerySet/lazy
object, no Django/DRF/Celery type, no provider SDK or wire DTO, no row dumps or `__dict__`, no
`dict[str, Any]`, explicit units with money in minor units) plus the careful identity split that keeps
item 4 I3 **and** I4 intact — internal-only messages may carry internal identifiers, externally
consumed ones may not, with the classification recorded per entry and a change of it breaking; the
**snapshot-vs-reference rule** rejecting both the full-aggregate snapshot and the bare identifier, and
allowing a consumer needing current truth to re-read through the owning module's public selector;
`schema_version` semantics (positive integer from `1`, strictly increasing, never reused, versioning
the **payload only**, no semantic-version strings, never bumped for implementation/broker/trace
changes); **immutability of a published version** — the strict policy adopted deliberately with its
costs stated, so an additive optional field is a new version and no `(type, version)` is ever mutated
in place; the eleven breaking-change triggers and the `same fact → new version` /
`different fact → new event_type` split with retire-and-introduce for a rename; **exact-version
consumer support** (no "latest", no best-effort decode, no nearest-version coercion, no unknown-field
tolerance) and **upcasters** bounded to explicit, total, pure transformations between two registered
versions of one type; **producer emission** rules and the frozen five-step **consumer-first migration
sequence** with dual-publish discouraged and old-version removal requiring evidence; the semantic
result for an unknown type, unsupported version or invalid payload — **durable quarantine + alert**,
never ignored, coerced, treated as latest, marked as successfully HANDLED, partially applied or
retried forever, with quarantine state identity-bearing so no hot loop is possible, and the explicit
separation of **semantic completion from transport disposition** — quarantine commits first, after
which the transport may terminally remove the delivery (ack-after-quarantine, reject/nack without
requeue or the broker equivalent, the exact operation being item 9's), never losing the message before
quarantine durability and never leaving an invalid message hot-looping; the split of **message-identity
integrity from business-effect idempotency** — every consumer, without exception, durably retains
first-seen `event_id`/type/version/payload-fingerprint identity so the same `event_id` with different
content is always detectable as an **integrity violation** rather than a duplicate (no registry entry
may declare that detection unavailable), while the durable business **effect** may use any of the three
mechanisms, chosen and recorded **per consumer** with its justification rather than once per message
version — so an `EVENT`'s independent consumers may legally differ while a `COMMAND` has exactly one
such declaration — and the latter two of which never discharge the identity obligation; the **handler transaction rule** (claim → effect → Outbox rows →
completion in one local transaction, never completed before the effect commits, never with provider
I/O inside, with the post-commit port shape for external work); the causality **extension point**
reserved without naming a field; **ordering** (no global order, broker order never relied on,
`occurred_at` and Outbox row ids not ordering keys, and `schema_version` prominently **not** a source
or ordering version); the **registry artifact** — its columns, its four statuses with one-way
transitions and precise meanings, and the rule that `DEPRECATED` is a live consumer obligation rather
than a soft delete; the split of a registry entry into an **immutable contract half** (type, version,
kind, semantic owner, canonical schema, payload field semantics, exposure, introduction) and a
**mutable audited operational half** (status, consumer declarations, upcasters, notes and retirement
proof, `emitted in production`, recorded producer delegations, effect-mechanism declarations), with
lineage declared **forward once** on the new row and the reverse view derived so no published row is
edited to add a back-pointer, and with an owner-qualified type's **semantic owner immutable in place**
— re-homing is a retire-and-introduce at `schema_version = 1`, an ADR authorising the move but never
an in-place edit; fifteen **registry invariants**; **one canonical schema source** per version with
everything else generated and two hand-written schemas forbidden; **validation** at both edges against
the registered schema rather than the producer's current classes, classified as an integrity failure
and never a business error; **JSON-compatible deterministic serialization** with no pickle, no
Python-object serialization and no binary schema system; **replay and retention** obligations
(support retained for anything that can still arrive, decoder deletion requiring proof, schemas
outliving handlers, no numeric periods frozen, and no event-sourcing dependency for any read model);
**security and privacy** (minimum data, no secrets/tokens/credentials/PII beyond need, no
authorization decision from a payload, a per-entry privacy classification, no actor added to the
envelope); a seventeen-row failure matrix whose every commercial-impact cell is `None`; and the checks
A42–A50, C55–C69 and V52–V61 that later phases must implement.

**[ADR-0009](../../adr/0009-event-contract-versioning.md) was required** and is accepted, for the
three decisions that are not mere specification of the earlier ADRs: producer-owned message contracts
with `core.events` reduced to mechanism (which **departs from master `# 20.6`**'s literal
`core/events` declaration while preserving every requirement that section states — item 8 §1.4
tabulates the mapping), immutable published schema versions including additive change, and exact-
version consumer support with unknown/invalid → durable quarantine + alert. ADR-0009 changes **no**
dependency-matrix cell, adds **no** import edge and extends **no** `core` submodule allowlist
(`core.events` was already allowlisted by item 3 §4.2/§4.3 and `FORBID` for `integrations/*` in
§4.5); L1–L21 stand unedited and no new `L` rule is required. Item 4 §5's eight `public.py` export
categories are untouched — the data boundary of §6 exists precisely so that an event contract never
needs to become a ninth.

One master detail is recorded as **already superseded** rather than newly decided: master `# 12.2`
step 8 has the webhook boundary create an Outbox marker, which item 3 L13 already forbids. The frozen
shape stands — the inbound boundary performs durable Inbox ingest only, and the internal registered
message is authored later by the owning application module in the worker.

Deliberately **not** frozen by item 8: queue names, routing, priorities, failure-domain isolation,
DLQ/quarantine topology, replay tooling and alert routing (item 9); trace/correlation/causation field
names and propagation mechanics (item 10); `Money`/`PublicId` implementation including the concrete
`event_id` type (item 11); `source_version` generation, per-source mapping and the guarded upsert
(item 12); Outbox/Inbox/dedupe/quarantine table schemas, columns, indexes and partitions, the physical
column names for `event_type`/`schema_version`, the canonical-schema form and generator, which of the
generated artifact's file format, the validation and serialization libraries, the physical module layout
of owner-internal contract modules, and whether a runtime `kind` discriminator exists (Phase 1); every
real `event_type` with its payload and each of its consumers' supported versions and effect-idempotency
mechanism (each owning module's phase —
the registry ships **empty**, and master's `catalog.project.batch`, `review.approved` and
`payment.webhook.received` are explicitly identified as master illustrations that item 8 does not
adopt); provider webhook wire schemas (the integration phases); numeric retention periods, replay
windows, freshness thresholds and retry schedules (operations phases); privacy retention, erasure and
anonymization rules for payload personal data (security/privacy phases); and any binary schema system,
event store, saga/orchestration framework or third message `kind`, each of which would require a new
ADR.

## Notes on item 9

Frozen: the **three separated layers** — registered message contract (item 8) / logical failure domain
(item 9) / physical broker queue (Phase 1) — with the rules that queue identity is never event
semantics, that a routing change never bumps `schema_version` or creates a new `event_type`, that a
logical domain may be split into several physical queues for throughput but two logical domains may
never be merged onto one; the **failure-domain principle** (share a normal-processing queue only when
one workload's latency, provider outage, poison rate and retry storm may acceptably consume the
other's capacity), the six reasons that are explicitly never sufficient, and the ban on a
general-purpose `external`/`integrations`/`default`/`misc` queue; the **criticality vocabulary**
`CRITICAL`/`IMPORTANT`/`BEST_EFFORT` governing capacity, isolation and alerting **only** — never
durability, contract strength or whether data may be lost, and never a source of business inference;
the **ten frozen logical failure-domain definitions** (`core.payments`, `core.inventory`,
`core.projection.incremental`, `core.projection.rebuild`, `core.maintenance`, `ext.payments`,
`ext.erp`, `ext.email`, `ext.sms`, `ext.crm`), of which none shares a worker pool with another, with
the separation of a frozen **definition** from a launch **provisioning** decision — provisioning
follows the workloads actually enabled, `ext.crm` is a **conditional** definition whose isolation rule
binds if and when CRM is enabled while **whether CRM ships at launch stays item 14's** open decision,
and **no support/Chatwoot and no analytics domain is reserved at all** — plus a recorded procedure for
adding one;
the **payment split by I/O nature rather than by workflow step** — `core.payments` performs local
durable state convergence with **no** provider I/O and must keep converging through any provider
outage, while `ext.payments` performs all provider-facing payment calls with per-provider concurrency,
rate-limit and circuit budgets — so the queue boundary coincides with ADR-0007's transaction boundary;
the **projection split** into incremental and rebuild domains, with the decidable rule that a rebuild
backlog may never delay incremental updates beyond their freshness SLO and no lag ever authorises a
request-time OLTP fallback; **ERP batch isolation** (bounded, set-based, resumable, idempotent, and
unable to stop payment/inventory/projection work) and the **separate email and SMS** domains with SMS
deliberately not made critical pre-emptively; **routing ownership** — routing is transport metadata determined by a
transport routing policy and assigned **per consumer declaration**, beside that consumer's supported
versions and effect-idempotency mechanism, never once per `(event_type, schema_version)` and never by
the producer, so a `COMMAND` has exactly one route, an `EVENT`'s independent consumers may legitimately
sit in different domains, and an `EVENT` with no declared consumers needs none (item 8 KD2's
zero-consumer allowance is used, not amended), with the registry never becoming queue configuration and
the matrix never becoming a contract authority; **logical queue naming** reconciled with master `# 20.1`'s `core.*` / `ext.*` /
`<domain>.dlq` family, where the `core.` prefix asserts the checkable property that no work there
performs provider I/O; **priority is not isolation** (it orders the next pick, it does not bound what a
running workload consumes) and **autoscaling from one shared pool is not reserved capacity**, with the
wedged-ERP deployment configuration frozen as a testable requirement; the **TF-A/TF-B/TF-C/TF-D failure
taxonomy** — transient, permanent workload rejection (explicitly *not* a schema quarantine), contract/
identity integrity (item 8's quarantine unchanged), and programmer defect (never disguised as a
provider failure) — with **retry policy owned by the failure domain**, never encoded in a payload;
**finite bounds everywhere** (attempts and/or age, plus backoff, plus an explicit terminal
disposition), increasing bounded backoff with mandatory jitter, clamped `Retry-After`, no tight loops,
no worker slot held while sleeping, and provider rate limits plus circuits that fail fast without ever
dropping a message; the precise separation of **contract quarantine** from **operational dead-letter**
as two semantic states never called simply "failed" (one physical mechanism permitted only with an
explicit terminal-kind discriminator); **PostgreSQL as the canonical durable truth for both terminal
states** with the broker DLQ demoted to transport, sufficiency-for-replay rather than duplicate
storage, the fixed *validate → persist → COMMIT → only then dispose* order, and the rule that a failed
terminal write means the delivery is **not** disposed of; **per-domain terminal namespaces** with no
global undifferentiated bucket and origin preserved in storage as well as routing; the **consumer
delivery** as the unit of failure, terminal identity and replay — two consumers of one `event_id` are
independent deliveries rather than duplicates, each keeps its own identity/effect/terminal state, one
may succeed while another quarantines or dead-letters, and every terminal record names **which**
registered consumer failed because a domain shared by several consumers cannot identify it; **poison-message**
behaviour that survives worker restarts without restarting retry budgets or alert storms; **delivery
ambiguity** (crash before/after the effect, lost acknowledgement — never dead-lettered) resting
entirely on item 8's identity and idempotency rules with no exactly-once broker semantics anywhere;
**ambiguous external outcomes** resolved by provider idempotency keys or application-owned status
lookup/reconciliation inside the owning workflow's state machine, never by a blind transport retry;
**replay** as an explicit, authorised, audited, idempotent, identity-preserving operation that
re-enters normal validation and idempotency with **no force-apply path**, **scoped to the failed
consumer delivery** so replaying one consumer never rebroadcasts to a sibling that already succeeded,
where a still-invalid replay returns to quarantine, a completed replay duplicates nothing, and a
genuinely new business attempt is a **new message with a new `event_id`** rather than a replay; the interaction with **schema retirement**
(a retired version is not routinely replayable, forensic decoding stays possible, a deprecated version
stays fully replayable); **broker outage** (business commits never depend on the broker, direct
producer→broker publishing stays forbidden, relay lag is the signal, recovery drains automatically);
**single-domain outage** with fair relay scheduling; **backpressure** (per-domain metrics, critical
progress preferred, and durable messages never dropped to reduce depth — TTL and max-length policies
included); **alert severity classes** with runbook owners and no alerting on individual retries; a
22-row failure matrix; and the checks A51–A59, C70–C84 and V62–V73 that later phases must implement.

**[ADR-0010](../../adr/0010-async-failure-domain-isolation.md) was required** and is accepted, for
four decisions that are not mere specification of the earlier ADRs: failure-domain isolation with
reserved capacity as an architectural, testable requirement rather than an operations tuning knob;
PostgreSQL as the canonical durable truth for both terminal states with the broker DLQ demoted to
transport; the separation of provider-facing payment work from local payment-state convergence, which
adds a `CRITICAL` external domain master `# 20.1`'s illustrative routing table does not contain; and
contract quarantine versus operational dead-letter as two semantic states. ADR-0010 changes **no**
dependency-matrix cell, adds **no** import edge, extends **no** `core` submodule allowlist and changes
**no** ADR-0009 message-contract rule; it adds exactly **one** mutable operational field
(the failure-domain assignment) to **each consumer declaration** in the event registry's operational
half — no entry-global column — and it uses item 8 KD2/KD3/IX13's consumer cardinality exactly as
written rather than amending it. L1–L21 stand unedited.

Item 9 follows master `# 20.1`'s **prose** ("isolation is built primarily by external dependency") and
refines its **illustrative** `CELERY_TASK_ROUTES` example, which routes by two rules at once:
`core.high`/`core.low` are the criticality buckets the same paragraph calls insufficient, `core.high`
holds payment reconciliation *and* inventory expiry, and no queue exists for outbound payment provider
calls at all. Criticality becomes an *attribute* of a failure domain rather than a queue; the internal
work those buckets held is split into named `core.*` domains; and `ext.payments` is added. Every other
master `# 20.1` requirement — per-external-queue independent concurrency/prefetch/rate limits, a
separate DLQ per queue, explicit timeouts, circuit breakers, bounded retries, DLQ/replay, and the
six-hour-ERP-outage isolation goal — is preserved and, in the DLQ case, generalised to internal
domains too.

Deliberately **not** frozen by item 9: `CELERY_TASK_ROUTES`, broker/transport settings, exchanges,
routing keys, prefetch, acks-late semantics and the physical queue topology (Phase 1); whether a
logical domain is split per provider or per lane (Phase 1); worker process counts, concurrency,
autoscaling policy and the joint database connection-pool budget (Phase 1 / operations); retry attempt
counts, retry ages, backoff seconds, jitter widths, circuit thresholds and probe policy (Phase 1 /
operations); quarantine / dead-letter / Outbox / Inbox table schemas, columns, indexes, partitions and
retention (Phase 1); the circuit-breaker and rate-limiter libraries and the `integrations/*`
`BaseClient` implementation (Phase 1); replay tooling, its UI, permission model and audit storage
(Phase 1 / operations); alert thresholds, SLO values, severity routing and on-call rotation, and the
`docs/runbooks/<alert-name>.md` contents (operations); provider idempotency-key formats, reconciliation
queries and maib/MIA protocol fields (the payments phase and `integrations/<provider>`); ERP payload
fields, mappings and the `provider + external_id` schema (`application/erp_sync`, Phase 3); trace/
correlation/causation fields and their propagation (item 10); `Money`/`PublicId` and the concrete
`event_id` type (item 11); `source_version` generation, per-source mapping and the guarded upsert
(item 12); whether asynchronous analytics exists at all and therefore whether an analytics domain is
ever added (item 13); **the MVP/later cut per module, including whether CRM ships at launch and
therefore whether `ext.crm` is ever provisioned — its operational shape is frozen either way**
(item 14); every real `event_type` with its payload/version and each declared consumer's routing
assignment (item 8
plus each owning module's phase); and a support/Chatwoot domain, any other new domain, or the merging
or removal of a frozen one (the matrix's own procedure, with an ADR where an isolation guarantee
moves).

## Notes on item 10

Frozen: item 8 EN6's **single** reserved envelope extension point, now spent on a **closed set of
exactly four fields** — `trace_id` (the trace containing *this message's production*),
`producer_span_id` (the span active when the durable record was written, named absolutely so no
future writer can put a consumer's span in it), `request_id` (the originating synchronous request of
the chain, inherited transitively and unchanged, absent for system origin, never actor identity or
authorization) and `causation_event_id` (the immediate parent message's `event_id`, one hop only, of
the same semantic type as `event_id` with the representation left to item 11) — with a generic
`correlation_id`, every metadata-bag disguise, persisted OpenTelemetry baggage, persisted W3C
`tracestate`, a free-form ancestry path and any queue/attempt/worker field **rejected by name**;
every field optional by construction, **write-once at message creation** and immutable thereafter;
the distinction between the four **defined slots** and the values actually present, with **TCE
state** (value *or* legitimate absence, per field) as the unit that is captured, copied, retained and
compared — so "four fields" never means "four non-empty values" — and the **canonical TCE state per
origin** (request first hop: trace pair, `request_id`, no causation; system first hop: trace pair
only; child: causation present and `request_id` inherited);
the trace/span **pair rule**, untraced production as a legal state, malformed and all-zero
identifiers normalised to absent at capture rather than stored or invented, and no back-fill ever;
`causation_event_id` never equal to the message's own `event_id`, never ordering, never
authorization, never idempotency, never a foreign key, and expected to dangle once the parent
partition is archived; **producer capture at the instant of the durable INSERT**, inside the same
business transaction, into the same record, from ambient in-process context with **no network I/O**,
populated by the `core.events` envelope mechanism so that **no `public.py` signature, command input
DTO, selector parameter or DTO field gains a trace argument**, and a capture failure never failing
the business transaction; the **durable Outbox record as the propagation source** — sufficient after
a restart, a delayed relay, a broker outage, a retry, a deployment and a relay in another process,
so the relay never requires the originating HTTP process to still exist; transport headers demoted
to a **copy/carrier** that loses every conflict with the durable row, with the disagreement recorded
as an observability defect and the message processed normally; a **new processing span per consumer
delivery**, child of the message's production context, with the message's four fields immutable at
the consumer and the delivery's own operational trace context kept in separate storage; the Inbox
and both terminal states retaining or durably referencing the four values so diagnosis survives
broker purge, partition archival and trace-retention expiry; **fan-out** as N independent spans over
one immutable envelope; **retry** as the same delivery with unchanged fields, a new span per attempt
and attempt metadata confined to the transport row and span attributes; **replay** as immutable
historical lineage plus a **new operational trace that links to** the original production context
rather than being parented into it — minting no `event_id`, changing no causation, still scoped to
one consumer delivery, with a child message emitted during a replay taking the replay's trace/span,
the inherited `request_id` and the unchanged causation; the **nine-way distinctness table**
(trace / producer span / request / causation / `event_id` / `occurred_at` / `schema_version` /
`source_version` / failure domain), none interchangeable and none an ordering counter; the
**correctness firewall** — sixteen classes of decision that may never read trace metadata, with a
valid business message always processable and lost trace continuity an observability defect only;
**security and privacy** (no PII in any of the four, no identity encoded in `request_id`, no baggage
or vendor blob made durable, inbound trace context untrusted and adopted only at a trusted boundary,
diagnosis never requiring raw payload logging); **sampling neutrality**, including the deliberate
decision *not* to persist a sampled flag and the incompleteness accepted with it; the
**storage-before-partition invariant** — the four fields present on the initial Phase 1 Outbox/Inbox
schema, no partitioning migration before that decision, and no TCE field as a partition, ordering or
uniqueness key; a 16-row failure matrix whose every business-correctness cell is unaffected; and the
checks A60–A67, C85–C99 and V74–V83 that later phases must implement.

**[ADR-0011](../../adr/0011-async-trace-causality-envelope.md) was required** and is accepted, for
four decisions that are not mere specification of the earlier ADRs: filling ADR-0009's reserved
extension point with a closed named set (a change to the shape of the cross-cutting envelope every
producer and consumer sees); the rename of master `# 20.2`/`# 20.6`'s ambiguous `span_id` to
`producer_span_id` together with the addition of `causation_event_id`, which the master names
nowhere; the durable Outbox/Inbox record as the source of truth for asynchronous trace context plus
the schema-ordering constraint that binds Phase 1 before any partitioning migration; and the
replay rule separating immutable historical lineage from the new operational trace. ADR-0011 changes
**no** dependency-matrix cell, adds **no** import edge, extends **no** `core` submodule allowlist,
changes **no** ADR-0009 message-contract rule and **no** ADR-0010 transport rule; L1–L21 stand
unedited. **ADR-0009 and ADR-0010 are neither edited nor superseded** — item 8 EN6/CA3 reserved this
decision in writing, so filling the extension point exercises a reserved right rather than amending
anything, and item 9's routing, terminal-state and replay models are used exactly as written (item 10
adds no registry column and no consumer-declaration attribute).

Master `# 20.7`'s mechanism — capture at INSERT, W3C trace context plus `request_id` in message
headers, the worker restoring parent context and creating a child span, the webhook trace starting at
`interfaces/webhooks/*` with the provider event id as a span **attribute** — is preserved in full,
as is master `# 23.3`'s rule that losing trace on the async boundary is an observability defect. The
only departures are the `span_id` rename and the added causation field, both recorded in item 10
§1.4's mapping table.

Deliberately **not** frozen by item 10: the concrete `event_id`/`PublicId` type and therefore
`causation_event_id`'s representation, and `Money` (item 11); `source_version` and the guarded upsert
(item 12); whether async analytics exists (item 13); the MVP/later module cut (item 14); the physical
Outbox/Inbox/quarantine/dead-letter schemas — column names, SQL types, nullability encoding, indexes,
partition keys, retention — and whether any TCE field is indexed at all (Phase 1); Celery headers,
message serializer, broker configuration and routing (Phase 1); the OpenTelemetry SDK, propagator,
exporter, instrumentation and the API used to express a span link (Phase 1); the physical module
owning ambient capture/restoration and any `core` allowlist extension its placement may imply, which
is recorded then rather than pre-empted here (Phase 1, on ADR-0006's precedent); span names and
attribute keys (Phase 1 / operations); which peers and entry points may adopt an inbound
`traceparent` (Phase 1 / operations); numeric sampling rates, trace retention windows and alert
thresholds (operations); privacy retention and erasure for durable trace metadata (the
security/privacy phases); provider-specific tracing headers (the integration phases); and any change
to the closed four-field set, any persistence of `tracestate`/baggage, or an envelope version field —
each requiring a new ADR superseding ADR-0011.

## Notes on item 11

Frozen: `core` ownership of `Money`, the rounding mechanism, `PublicId` and `EventId`, with the
explicit negative that the money primitive knows no discount, VAT, promotion, delivery-threshold,
payment-provider, loyalty, exchange-rate or sign policy, and that no entity-tagged locator subtype
exists; the semantic `Money` shape — integer minor units plus a mandatory explicit currency and **no
third field** — as an immutable, multi-currency value object with the MDL figure recorded as an
example rather than a definition; integer discipline by **exact type**, so `bool` is not a money
integer, with `float` banned end to end (construction, arithmetic, comparison, JSON, provider
mapping, DB columns, fixtures and snapshots) and **no approximate monetary comparison anywhere**;
currency semantics — explicit, immutable, canonical uppercase, ISO-4217 alphabetic for fiat,
**structurally** validated in `core` (three ASCII letters) while *which* currencies are tradeable
stays an owning module's policy so `core` depends on no changing external currency data, with a
currency never inferred from locale, user, store, request, provider, environment or "MDL because
Moldova"; zero as **currency-bearing** and the empty-aggregation trap (a `sum()` over a possibly
empty money sequence needs an explicit currency-bearing zero, never a bare `0`); exact same-currency
addition/subtraction/negation and integer-count multiplication with **no** rounding policy, against
rejected cross-currency arithmetic, rejected mixing with bare numbers, no left-operand currency
inheritance and no silent FX; **currency-scoped partial ordering** — equality total and exact
(`Money(0,"MDL") != Money(0,"EUR")`), ordered comparison legal only within one currency, no
dataclass-generated total order, and no default for sorting a mixed-currency collection; signedness
as a **field and database** invariant rather than a primitive one, with the price/refund/adjustment
examples left to their owners; explicit boundary conversion into `Money` with no implicit constructor
from `float`/`Decimal`/`str`/JSON number, taking the value, the currency, the exponent and the
rounding policy as given inputs, deterministic and pure, and with the policy named even when the
source happens to be exactly representable; the separation of Money representation from **currency
exponent metadata**, so "two decimals" is never hard-coded, no live exponent lookup is admitted and
the Phase-1 data source is deferred; the `RoundingPolicy` contract — mandatory, **defaultless**,
deterministic against a well-defined decimal rounding rule, arithmetic-named rather than
business-named, chosen by the owning domain — with the **member set deliberately left to Phase 1** as
the smallest decision that still satisfies the master; the no-hidden-rounding and no-double-rounding
rules with a single named materialisation point and the line-vs-total choice assigned to the owning
domain; `Decimal` for rates, ratios and parsing but never as persisted or public commercial truth;
persistence as **integer minor units** with no `float`/`real`/`double precision` and no arbitrary
`numeric` canonical amount, currency reachable and documented, sign/range as owning-schema `CHECK`s
and `integer` vs `bigint` as the owning schema's proven-range decision; `Money` (not a naked integer,
`Decimal` or float) in every semantic money contract position, with transport and vendor conversion
one-directional at the edges, no single JSON shape frozen, and the minimum requirement that an
external representation be **exact, currency-carrying and never a binary float**; **exact** provider
amount **and** currency comparison with no tolerance and no state adjusted to agree with a provider;
and the negative FX rule — `Money` never converts, a conversion is an explicit owner-held operation
with rate, provenance and policy, and no rate source enters `core`.

On identity: ADR-0001's three spaces preserved and **typed** rather than rewritten; `PublicId` as a
strongly-distinct immutable UUIDv7 locator that a bare `UUID`, an `int`, a provider id, a business
key, an idempotency key or an `EventId` cannot occupy, with the Phase-1 construct left open behind
five type-safety requirements that demand distinctness **statically and at runtime** — so a bare
`typing.NewType` over `uuid.UUID` is excluded and a frozen validating wrapper value object is the
admissible shape, while the underlying representation may still be a `uuid.UUID` and no class,
module or signature is frozen; standards-conforming, server-side, in-transaction generation with **no
custom bit layout**, DB-enforced uniqueness, and clients never choosing the locator of a new
platform-owned entity; immutability across rename/slug/status/re-import/merge, a new locator on
delete-and-recreate, never recycled and never derived from a PK, email, SKU, slug, customer datum or
provider id; **locator ≠ permission** — actor-scoped authorization or master `# 5.1`'s purpose-bound
signed token, with UUID entropy explicitly rejected as access control; the embedded timestamp as
**never** business time, ordering, causation, replay chronology or any version, so clock rollback and
same-millisecond generation cannot affect correctness (index locality may be benefited from, never
depended on); the PK split preserved — no wholesale UUID PK migration, `PublicId` only where an
entity is externally addressable, **not** the keyset tiebreaker, and cursor opacity untouched;
version-checked parsing with a single canonical lowercase hyphenated rendering and non-canonical
spellings **rejected rather than normalised**, so one resource never acquires two external
identities; logging rules that keep a locator usable for correlation without making it a secret or a
substitute for redaction policy; and integration rules that force no provider/ERP contract onto
`PublicId`, never serialize an internal bigint as `external_id`, and never let a provider, legacy,
v4 or foreign-v7 UUID become a platform locator.

On message identity, item 8 ID7's and item 10 CZ4's deferral is **resolved**: `EventId` is a
**distinct** semantic type over the same UUIDv7 value space, `causation_event_id` has exactly that
type, and every item 8/9/10 rule (assignment at emission, survival through retry/redelivery/replay, a
new identity for a genuinely new fact, not a broker delivery id, not a `source_version`, not
ordering, not authorization, not an HTTP idempotency key, and a provider `external_event_id` as a
separate space) is restated unchanged rather than reopened. One `core`-internal UUIDv7 mechanism
serves both types and is **exported to no package family**, because a generic `new_uuid7()` would let
every call site produce a value fitting both types and dissolve the distinction. Equality, hashing,
serialization neutrality, the three-way error classification (boundary input failure / primitive
misuse as an untranslated programmer error / business rejection — with **no** new `core.errors`
category requested), the security rules, a 28-row failure matrix whose every commercial-impact cell
is `None`, and the checks A68–A85, C100–C127 and V84–V101 are frozen with it.

**Two ADRs were required, evaluated per decision and kept to one decision each.**
[ADR-0012](../../adr/0012-money-currency-scoped-partial-order.md) records the money-ordering
decision: master `# 5.3`'s illustrative `@dataclass(..., order=True)` would generate a total
lexicographic order over `(minor, currency)`, making `Money(100, "EUR") < Money(200, "USD")` legal,
true and **silent** at every `sorted()`/`min()`/`max()` in the platform, while the same snippet's
`__add__` already raises on a currency mismatch. Ordering becomes currency-scoped and partial;
equality stays total. [ADR-0013](../../adr/0013-event-id-distinct-identity-type.md) records the
`EventId` decision, verified against ID7's actual text first — ID7 defers the type to item 11 and
requires only a stable, globally unique, non-sequential, opaque, once-assigned UUID, so no frozen
artifact requires `PublicId` itself. Both rejected alternatives are named: reusing `PublicId` would
make `order_public_id` and `event_id` mutually assignable and would make item 8 PD14 ambiguous about
the envelope; a bare `UUID` would abandon ID7's "typed distinctly enough" spirit.

**No mixed catch-all ADR was written**, and six of the eight decisions item 11 §1.3 evaluates needed
no ADR at all, each traced to the artifact that already authorizes it: minor units + explicit
currency (master `# 5.3`, item 4 D8), no implicit `float`/`Decimal` constructor and an explicit
`RoundingPolicy` factory (master `# 5.3` verbatim, master `# 25` Phase 1), structural-only currency
validation in `core` (ADR-0004 §2's admission test), `PublicId` as a distinct immutable UUIDv7
locator that is not a PK replacement and not the keyset tiebreaker (ADR-0001 §3, master `# 5.1`),
locator ≠ permission (ADR-0001 §3, master `# 5.1`'s signed-token requirement, item 4 §11), and the
UUID timestamp as neither business time nor a version (item 8 ID2/ID5/§26, item 10's distinctness
table, item 6 §16.1). Neither ADR moves a dependency-matrix cell, adds an import edge or extends a
`core` submodule allowlist — `core.money` and `core.public_id` were already allowlisted per family by
item 3 §4.2–§4.7, `core.events` (which hosts `EventId`) was already allowlisted for `domains`,
`application`, `tasks` and the composition root and already `FORBID` for `integrations/*`, and
`core → core` is already `SELF ONLY`. L1–L21 stand unedited, item 11 adds no `L` rule, and
ADR-0001…ADR-0011 are neither edited nor superseded.

Deliberately **not** frozen by item 11: the physical `core` modules, file layout, member names and
signatures for `Money`, `RoundingPolicy`, `PublicId`, `EventId` and the UUIDv7 mechanism (Phase 1);
the identity construct itself — deferred but **bounded**, not open, since it must be a
runtime-distinct immutable value representation satisfying TY1–TY5, which admits a frozen validating
wrapper value object and excludes a bare `typing.NewType` over `uuid.UUID` (Phase 1, within that
bound); the concrete
`RoundingPolicy` member set, justified per domain in its own phase (Phase 1); the standards-conforming
UUIDv7 implementation or library, chosen against the pinned Python version (Phase 1); the
currency-exponent data source — a checked-in static table or an approved library, never a live lookup
(Phase 1); every Django field, model, column, `CHECK` and index for money and `public_id`, and
`integer` vs `bigint` per column (each owning schema's phase); which currencies the platform supports
and where that policy lives, plus the exact error member for rejecting an unsupported one (pricing /
payments / delivery phases); the line-vs-total rounding choice per business calculation (pricing /
promotions / delivery / orders); any FX mechanism, rate source or provenance model (a future phase);
the HTTP/HTML/JSON representation of money and locators (the Web and DRF phases); provider amount and
currency encodings (each provider's integration phase); the signed guest/access token's scheme,
purpose binding, nonce and lifetime (security/checkout phases); the keyset cursor codec, fields,
signing and page-size limits (Phase 4); retention, erasure and anonymization for durable identifiers
and money records (privacy/security phases); client-supplied creation identity, if ever wanted (a new
ADR); a currency registry, currency library or exponent service inside `core` (a new ADR); and
`source_version` with its guarded upsert (**item 12**, untouched — the term appears in item 11 only as
a negative rule), analytics (**item 13**) and the MVP/later module cut (**item 14**).

## Notes on item 12

Frozen: the **convergence model** — an asynchronous trigger is a bounded *dirty-identity signal*,
never an authoritative row snapshot and never a carrier of a freshness token, while the writer
rebuilds the **whole** candidate (every field, every language) from current authoritative state
through `<domain>.public` batch selectors and commits it under an optimistic compare-and-set;
master `# 7.6`'s producer-supplied scalar and its `EXCLUDED.source_version > stored` predicate
**evaluated and rejected**, with all three failures worked in full (no admissible cross-domain
generator that does not violate ADR-0003 §3 / item 6 R2/PU10; a pre-commit sequence, `xid`, LSN,
commit timestamp or `xmin` ordering database activity rather than the projected state, with the
transaction-commit inversion shown concretely; and a rebuild that has no version to write, which is
fatal against RB1/RB2) plus the independent-source lost-update case (`P2 + I1` surviving as the
converged state) that the master's own motivating sentence describes and its predicate does not
solve; the per-source **version vector** evaluated and rejected by name, because four of the five
sources have no per-Product revision of their own, each component would have to be invented and
exposed for the read model's benefit (making item 6 O2 false in substance), and a component-wise
merge has no answer for the row's cross-source derived fields; the **token** — name
`projection_revision` with `source_version` retired for this purpose, type 64-bit signed integer
`NOT NULL`, cardinality **one per serving row**, generated only by `application/storefront` inside
the guarded write, initial `1`, advancing by at least one **iff** serving state changes, compared
**only for equality and only against a value observed earlier from that same row** (ordered
comparison, `MAX`/`GREATEST`, `ORDER BY` and cross-row comparison forbidden outright), and never a
`source_version`, schema version, aggregate version, ordering key, idempotency key, freshness
timestamp or public value; **non-reuse scoped to a projection generation** — within a generation
(ordinary incremental work, targeted rebuild, in-place full rebuild, reconciliation, withdrawal,
tombstoning) a row identity's token never decreases and never repeats a committed value, which is
what makes ordinary concurrent writers ABA-safe, while a **fenced** destructive operation
(destructive rebuild, physical tombstone collection, table replacement, build-then-swap, recovery
from total loss) ends the generation and **may reinitialize tokens at `1`** provided the fence
drains or invalidates every observation taken against the old structure, so the rule is *either*
preserve non-reuse *or* invalidate every prior observation, and explicitly **not** retained per-row
maxima, a durable epoch column, a token-history table or any backup/replication/retention obligation
— leaving the projection and its tokens fully disposable; the **protocol**
observe → build → guarded write with the ordering constraint that the observation strictly precedes
every source read's **visibility point** (not merely the call), plus
the rules that nothing durable exists before the write, that a retry re-observes and rebuilds rather
than reusing a candidate, and that the guarded write is a local transaction containing no
`<domain>.public` call, no cache call and no external I/O; the **authoritative-read contract** for
the builder — every source read used to build a candidate is a correctness read of authoritative
committed owner state whose visibility point is established after the observation, so no candidate
field may be finalized from a Redis/fragment-cache entry, an asynchronously lagging read replica or
any bounded-stale copy (a cache may accelerate or short-circuit, never finalize), and a Phase 4 read
transaction/snapshot must be opened **after** the observation and never before, all of it narrowly
scoped to the projection builder's source-read path so that item 15's platform-wide read-replica
decision, item 6 O2's domain blindness, the Django database aliases and the selector signatures are
all left untouched; the **guard semantics** — equality CAS,
verification all-or-nothing across one product's language rows and per-product independent, with the
shared batch transaction a container rather than a shared guard,
absence as a first-class observed value, the serving-row unique key as load-bearing for the insert
race, a guard miss meaning **only** "another projection writer committed first" and never a business
failure, an item 8 quarantine, a checkout conflict or a provider failure, the candidate discarded
**whole** rather than merged or partially applied, and **no force-write path anywhere**; **whole-
candidate rebuild** as the only admissible shape, making rebuild ≡ incremental by construction, with
a per-source partial merge forbidden until a future ADR supplies an owned field-to-source
decomposition covering every derived field, and with a cross-domain point-in-time snapshot explicitly
**not** assumed (a mixed-time candidate is safe because each successive committed writer's view of
every source is a superset of its predecessor's, and a Phase 4 single-snapshot choice — established
after the observation — may never be cited as the safety argument); the rule that the whole
mechanism concerns **state-visibility chronology, not value trajectory**, so a source moving
`100 → 120 → 100` is converging rather than regressing and no business value is ever compared for
freshness; the **trigger role** and the five requirements every future projection-driving contract
must satisfy, without naming an `event_type` or fixing a payload, including that producer-supplied
`source_version` is neither required nor honoured and that a change-kind hint may only route,
coalesce and measure; **total no-op suppression** (equal candidate ⇒ no `UPDATE`, no token advance,
no `updated_at` change), the definition of "unchanged serving state" excluding the token and
`updated_at`, per-row suppression inside a per-product write, and a hash admitted only as a
detection accelerator with an exact fallback and never as an order; **multi-language coherence**
through the product-scoped guard unit, all of one product's language rows verified and written
together or not at all; the explicit separation of the **logical guard unit (the product)** from the
**physical write transaction (the bounded batch)** — several products share one local transaction
for set-based efficiency, a guard miss on one leaves the others eligible in the same write, and what
is asserted between two products is the absence of any freshness or ordering relationship rather
than the untrue claim that they never share a transaction, a lock or a technical failure, since a
technical abort (deadlock, lock timeout, serialization failure, crash) rolls the whole batch back
without writing anything durable and is retried with every product re-observed and rebuilt, a retry
coupling inside one unit of work; **batch,
locking and contention shape** — deterministic product → language lock order preventing lock-order
inversion, serving-row locks scoped to the bounded batch with no global or table-wide correctness
mutex and no correctness-serialized writer fleet, semantic contention confined to genuinely
overlapping products while ordinary lock waits between batches imply nothing about freshness, and
both item 9 projection failure domains using one writer path; **lifecycle** — withdrawal as a
forward not-visible change rather than a delete (a deleted row destroys the guard token and reopens
the ABA hole), a deliberate and recorded narrowing of item 6 LC2 for the update path only, genuine
reactivation as an ordinary forward change, and physical tombstone removal as a fenced maintenance
operation satisfying the non-reuse-or-fence disjunction; **rebuild interaction** — in-place rebuild
using the identical
protocol with no privileges, a rebuild candidate losable to a fresher incremental commit, no event
history and no token history required, and build-then-swap admitted **only** with a fence point,
catch-up of every change committed during the build and a swap that invalidates every prior
observation — after which the swapped-in generation may legitimately start its tokens over — with
"build for an hour and rename over live state" forbidden by name; **reconciliation
and operator repair** — the same convergence semantics, no force overwrite, drift as an operational
signal, token corruption answered by a **fenced** rebuild that is explicit, authorised and audited
and that may reinitialize the affected rows' tokens rather than attempting to recover corrupted
values,
and never a write-back from the projection into a domain; **replay, redelivery and crash** semantics
resting entirely on item 9's replay authority and the guard's own idempotence, with all three crash
positions resolved and no additional dedupe table required; **bounded retry** escalating into item
9's existing transient-failure machinery with no new subsystem, no unbounded loop, no stale-candidate
retry and no request-path effect; **source-identity resolution** through `<domain>.public` batch
selectors or application-owned state, with a category/brand rebuild seeded from the union of the
owner's current membership and the projection's recorded membership so a product that just left the
identity is still refreshed; **future-source admission** costing one builder input and one trigger
with no token change and no re-proof; the **separations** restated by reference (`schema_version`,
`EventId`/`PublicId`/UUIDv7 timestamp, `occurred_at`, Outbox/Inbox row id, trace fields, cache
counters, checkout's freshness guard, public DTOs) together with the four `updated_at` rules that
keep it display metadata and move lag measurement to the trigger pipeline; the **physical type
position taken rather than deferred**, with wraparound forbidden and corruption classified as a
technical fault; observability requirements; a 27-row failure matrix whose every "can stale serving
state commit?" cell is **No** and every commercial-impact cell is `None`; a five-part correctness
proof (safety by visibility-point domination, convergence, independence, rebuildability, the no-op
property) stated within one projection generation, with `view`/`vp` defined explicitly so the
authoritative-read premise is visible rather than assumed, and with a table of the eleven
assumptions deliberately **not** made and the three premises the proof actually needs; and the
checks A86–A100, C128–C147 and V102–V118 that later phases must implement.

**[ADR-0014](../../adr/0014-storefront-projection-convergence.md) was required** and is accepted,
for the decisions that are not mere specification of ADR-0008: rejecting master `# 7.6`'s
producer-supplied `source_version` and its `>` guard in favour of an application-owned per-row
compare-and-set; renaming the field to `projection_revision` and retiring `source_version`; removing
the version from master `# 20.6`'s illustrative producer payload (no published contract needs
migration — the registry ships empty and item 8 had already identified that example as
non-adopted); the cross-cutting observe-before-read invariant with its authoritative-read contract
(narrowly scoped to the projection builder's source-read path, leaving item 15's platform-wide
read-replica decision untouched); the generation-scoped non-reuse rule with its fenced-reset
counterpart; and the narrowing of build-then-swap
and of withdrawal-by-deletion. ADR-0014 changes **no** dependency-matrix cell, adds **no** import
edge, extends **no** `core` submodule allowlist, adds **no** event-registry column or
consumer-declaration attribute, and edits **no** accepted ADR; L1–L21 stand unedited and item 12
adds no `L` rule. Master `# 5` principle 36's *requirement* ("projection updates are monotonic; an
older event cannot overwrite newer state; full rebuild remains a reconciliation mechanism, not the
primary race protection") is preserved in full — only its illustrative mechanism changes — and item
12 §1.4 maps every master statement in `# 7.6`, `# 20.2`, `# 20.6`, `# 22.1`, `# 24`, `# 25` and
`# 26` to preserved / refined / departed.

Deliberately **not** frozen by item 12: the physical projection schema, the `projection_revision`
column definition and whether it is indexed, and the serving-row unique constraint the insert guard
depends on (Phase 4); the concrete no-op comparison technique (Phase 4); batch sizes, chunking,
throttling and the concrete locking statement (Phase 4); local retry attempt counts, backoff seconds
and jitter widths (Phase 4 / operations); in-place vs build-then-swap and the swap's fence/catch-up
implementation (Phase 4); tombstone retention and the fenced collection procedure (Phase 4); the
fenced-repair mechanism, CLI, permission model, audit storage and runbook (Phase 4 / operations);
reconciliation cadence, sampling, checksum shape and drift thresholds (Phase 4 / operations);
whether a Phase 4 implementation wraps a batch's source reads in one database snapshot (which must
then be established **after** the observation), and the
isolation level of the guarded write — admissible as hardening, never as the safety argument (Phase
4); the concrete fence mechanism by which a generation boundary drains or invalidates prior
observations (Phase 4 / operations); how an owning module exposes an authoritative-read capability to
the builder, with no Django database alias and no selector signature chosen in Phase 0 (each owning
domain's phase / Phase 4); **the platform-wide read-replica decision (item 15, untouched)**;
metric names, thresholds, dashboards, alert severities and runbooks (operations); the numeric
projection-freshness threshold (operations, item 6 CM8); every `event_type`, payload schema and
`schema_version` for projection triggers with each consumer's registry declarations (item 8 plus
each owning module's phase); the builder's batch selector signatures in `<domain>.public` (each
owning domain's phase); whether an analytics source is ever admitted (**item 13**, untouched — no
analytics state, column, signal or trigger is pre-created); the MVP/later module cut (**item 14**,
untouched); a per-source partial merge or field-to-source decomposition (a new ADR); and any change
to the token rules (generation-scoped non-reuse and the fenced reset included), the
observe-before-read invariant, the authoritative-read contract, the guard semantics, no-op
suppression, the
withdrawal rule, the swap requirements or the no-force-path rule (a new ADR superseding ADR-0014).

## Notes on item 13

Frozen: **option A** — `domains/analytics` is **not** an MVP module, and `popularity_score` is
computed only from existing first-party business facts through the ordinary item 12 builder — with
option B evaluated and rejected by reason (nothing commercial reads popularity; B would add a
domain, a consent gate, an ingestion boundary, a retention/anonymization obligation and a failure
domain before launch for a ranking refinement; the master itself places consent-gated analytics in
Phase 9 and views-based popularity under "can wait") and with the five half-states rejected **by
name** (analytics tables with consent "later", page views collected but ignored, raw events kept
"in case", anonymous tracking bypassing the consent design, a storefront depending on an
unimplemented analytics queue); the enumerated **negative list** of what "not an MVP module" means —
no analytics app/model, ingestion endpoint, page-view event, clickstream, behavioural stream,
worker, queue/failure-domain/DLQ namespace, retention store, registry entry, runtime consent
dependency, third-party SDK/pixel/tag manager, device fingerprint, hidden session-tracking store or
server-side viewed history — with ordinary operational telemetry explicitly untouched and never a
popularity input; the deliberate **preservation of the future module seam** as a Phase 9 capability;
`popularity_score`'s classification as **derived storefront ranking state** owned by
`application/storefront` (never analytics, commercial, authorization or profile truth, never a
`ProductCard` field, and needing no analytics domain merely because of its name); the **closed MVP
source set** and the explicit resolution of master's `# 10.7`-vs-Phase-4 discrepancy as *permission
set* versus *delivery list* rather than as a conflict — **successful sales** (owner
`domains/orders`, owner-defined success predicate, item 13 freezing the semantic requirement and not
the taxonomy, with abandoned/unpaid/failed operations excluded and no retention obligation added to
orders) and **favorites** (owner the Phase 7 favorites module, current active count, an
`added`-event counter forbidden, removal reflected) as the automated sources, **rating/review
excluded from the formula** because it already has an independent serving representation and would
double-count a separate relevance dimension (remaining an independent storefront signal readmissible
later as a policy change with no analytics tracking and no ADR), the **manual merchandising boost
excluded and left ownerless** exactly as item 6 SO6a/SO6b did — optional in `# 10.7`, therefore not
a launch blocker, and its owner assignment still item 6 §27's deferred decision — and **page views
excluded** outright rather than merely unrequired; the rule that **every source contribution is a
query over the owner's current authoritative state, never an accumulator**, batched, Product-scoped,
in a frozen DTO, with the owner never told why the aggregate is wanted; **source enablement across
phases** — a source is active only when its authoritative owner and public contract exist, a
non-enabled source contributes the policy's neutral value, "neutral" is a policy term and never a
stub/mock/fake adapter, Phase 4 therefore ships complete with zero enabled sources and a
tie-break-determined popularity order, and enabling one later is a scoring-policy change rather than
a migration; the sharp distinction between **not enabled** and **enabled but failing** — a failing
authoritative read is a transient technical fault that preserves the row's previous value and is
**never** silently degraded to neutral or zero; the **scoring-policy contract** (pure, deterministic,
total, clock-free, no ambient state, no I/O, integer with no persisted float, deliberate
saturation, no identity or PII anywhere, weights/window/schedule deferred to Phase 4 merchandising),
with a time window admitted only behind an **explicit quantized reference instant** supplied as a
parameter so a rebuild inside one bucket reproduces the incremental state exactly (preserving item
12 C26) and a bucket crossing is a forward policy-input change, and with window advancement realised
by bounded scheduled recomputation that writes nothing when scores are unchanged rather than by
wall-clock dirtying the catalog; **sort stability** including the degenerate all-neutral case, where
the deterministic unique tie-break fully determines a stable total order, with no random/session/
request-time/personalized input in the global anonymous popularity sort; **item 12 reused verbatim**
— popularity inputs are ordinary builder reads under CB10–CB14, no source supplies a freshness
token or knows it is projected, triggers stay dirty-identity signals, there is no partial
`popularity_score` write (with master `# 10.7`'s "updates only `popularity_score` of the changed
products" pinned as *only the changed products*, not a single-column write), no `popularity_version`,
and no analytics exception; a **rebuildability proof** showing that deleting all Outbox and broker
history and the projection still reconstructs the score from current business state plus the
recorded policy, with the residual policy-parameter boundary stated honestly; the **privacy
boundary** — the architectural distinction between existing first-party business facts and new
behavioural collection, guaranteeing no new collection, no raw behavioural stream, no user/session/
device identifier or raw Order/User/Favorite/Review row in the projection, no PII in the score, and
guest browsing that never becomes server-side analytics — while making **no legal claim** that
first-party data never requires consent or a lawful basis, and showing that a later purpose/legal
restriction degrades gracefully into a policy change; **recently-viewed** as browser-local
`localStorage` state implying no server write, no view event and no popularity input; the
**admission gate** for a future `domains/analytics` (it must own event semantics, the consent gate,
ingestion, retention, aggregation, anonymization and aggregate publication; no other module may hold
any of those; a signal enters only as a Product-scoped aggregate in coalesced batches with raw
metrics never in the request path; admission uses item 12 FS1–FS5 unchanged; item 9 NX5's
domain-addition procedure applies; and it never owns Orders, Favorites, Reviews or the projection,
never becomes commercial truth and never rewrites historical business records); the **consent
invariant** that no consent-gated event is collected before the applicable consent state permits it,
with categories, banners, retention and revocation left to Phases 8/9 and MVP carrying **no runtime
analytics consent dependency at all**; the confirmation that **item 9 NX3/NX4/FD10 stand unedited**
and that popularity is a field of a candidate rather than a workload, so it runs in the existing
`core.projection.*` domains; the refusal to create or even name any `event_type`, with the only
requirement on future owners being that a business-fact change affecting the active policy must
eventually cause the affected Products to be rebuilt or reconciled (reconciliation alone being a
legal driver for a low-rate source); **degradation** rules keeping checkout, pricing, reservation,
payment and authorization untouched with no silent substitution; an 18-row failure matrix whose
every commercial cell is `None`, every PII cell is `None` and every request-path cell is
non-failing; and the checks **A101–A113**, **C148–C160** and **V119–V129** that later phases must
implement.

**No new ADR was required**, and the evaluation is recorded rather than assumed: item 13 assigns no
owner, moves no boundary, adds no import edge or `core` allowlist entry, changes no public contract,
changes no consistency rule, and adds no event type, queue or failure domain — it selects the branch
master `# 5` principle 37 and `# 10.7`'s **MVP** subsection already specify, under the conditions
they already attach, with master `# 25`'s MVP line placing *views-based* analytics/popularity after
launch and Phase 9 listing consent-gated analytics/view events as optional. That is routine MVP
scoping inside an already-decided boundary — `docs/adr/README.md`'s explicit no-ADR case. The one
decision item 13 could have taken that **would** have required one — assigning an authoritative
owner to the manual merchandising boost — is deliberately declined and left with item 6 §27.
Actually introducing `domains/analytics` later is a different matter: it adds a domain, a consent
gate, an ingestion boundary, a retention/anonymization obligation, a new public contract feeding the
projection and (per item 9 NX3/NX5) a new logical failure domain, so it needs its own architecture
and privacy artifact and an ADR to the extent it moves a boundary this corpus has not specified.
L1–L21 stand unedited and item 13 adds no `L` rule.

Deliberately **not** frozen by item 13: scoring weights, the window length or the decision to have
none, quantization granularity and the recomputation schedule (Phase 4 / merchandising
configuration); whether the serving row stores per-source inputs beside the score, and the physical
column definition (Phase 4); the batch aggregate selector signatures in `orders.public` and the
favorites owner's `public.py` (each owning domain's phase); the order-status predicate defining a
successful commercial sale (`domains/orders` / item 5's phase); whether the popularity sort option is
exposed when no source is enabled, and the default listing sort (Phase 4 / merchandising); whether
rating is later admitted into the formula (a recorded policy change, no ADR); **the manual
merchandising boost's owner (item 6 §27, untouched)**; **which modules ship at launch and therefore
which source set is active at launch (item 14, untouched)**; **infrastructure gates and the
remaining open ADRs (item 15, untouched)**; whether a consent-gated `domains/analytics` is ever
built together with its events, schema, ingestion, retention, anonymization, aggregates, queue and
consent categories (Phase 9, behind the admission gate); consent categories, banner state machines,
retention periods and revocation mechanics (Phase 8 and the privacy phases); a personalized
recommendation or ranking read model (a separate artifact and a new ADR); and any change to the
absence list, the closed source set, the accumulator ban, the enablement rules, the scoring-policy
contract, the item 12 interaction rules, the admission gate or the consent invariant (a new ADR, or
the artifact that introduces analytics).

## Notes on item 14

Frozen: the **single authoritative launch-cut matrix** over `core/*`, `domains/*`, `application/*`,
`interfaces/*`, `integrations/*`, `tasks/*` and the named optional commercial capabilities that have
no physical package, using five classes — `FOUNDATION` (cross-cutting mechanism required regardless
of which optional features ship), `MVP`, `MVP — REDUCED SCOPE` (both lists enumerated; "basic
version" inadmissible), `LATER` (not a launch dependency, seam may exist in documentation, package
need not exist) and `INFRASTRUCTURE GATE` (measurement-driven, still governed by item 15 / master
`# 25` Phase 10) — under the governing constraint restated unchanged: **MVP cuts features, never
correctness, security, performance or module-boundary invariants**; the rule that **roadmap phase
number is never launch membership** (launch membership derives from the `# 25` MVP line, explicit
optional/later statements including a phase checklist's own internal asymmetry, and dependency
closure — with the MVP line winning over a broader chapter enumeration), and the separation of three
distinct questions where item 14 answers only the third (does the seam exist in docs / must the
Phase 1 package exist / **is the production feature enabled at launch**), so no empty package is
required for any LATER domain and an empty `domains/analytics` is explicitly forbidden; **FOUNDATION**
= the fifteen mechanisms (`core.money`, `core.public_id`, `core.dto`, actor + structural errors,
idempotency, Outbox/Inbox with the item 10 envelope, the `core.events` registry mechanism shipping
with an empty registry, cache single-flight/versioning, signing/trusted-IP, observability,
`integrations/base` resilience primitives, failure-domain/DLQ/quarantine machinery, query-budget/N+1
+ `import-linter`/AST harness, the `config/` composition root, backup/PITR/runbook foundations);
**MVP** = `catalog`, `pricing`, `promotions`, `inventory`, `orders`, `reviews` (master's "basic
reviews" being `# 14.1` **in full**, including moderation, verified-purchase badge, anti-spam and
`ProductRatingProjection`), `stores`, `application/storefront`, `application/erp_sync`,
`interfaces/web`, `interfaces/api/v1`, the maib and ERP ingest paths, single-domain
`interfaces/admin`, `integrations/erp`, `integrations/maib`, the outbound transactional-email
transport and the media object-storage/CDN path (classified MVP rather than a gate because a launch
promise requires it, not measurement); **MVP — REDUCED SCOPE** = `payments` (domain, state machine,
webhook contract, reconciliation and provider seam MVP; enabled providers reduced), `delivery`
(courier + pickup; digital fulfilment out), `content` (static/legal/operational pages, publication
identity, block-JSON sanitisation + CSP, consent surface, static sitemaps, cached
footer/navigation; Blog/Promo/Events/eSIM/video out), `accounts` (identity, profile, order history,
guest claim; favorites/compare/viewed-history out), `notifications` (transactional email; SMS out),
`application/checkout` (cart, `CheckoutSession`, `place_order`, `apply_coupon`;
`apply_tradein_quote` out) and `application/payments_gateway` (launch provider bindings only);
**LATER** = `analytics`, `tradein`
(Trade-In *and* eUpgrade), digital distribution/KMS, support/Chatwoot, own WebSocket chat,
`application/backoffice`, MIA (adapter + webhook route), credit, POS-on-delivery, SMS,
`integrations/crm`, `integrations/chatwoot`, the map/tile provider, favorites, compare, complex
Blog/news/guide article types, promo landing pages, Events, eSIM guides, video CMS, **the newsletter
capability in its entirety** (no subscription endpoint, subscriber persistence, double opt-in
workflow, campaign sending or CRM/mailing hand-off at launch — the `# 25` MVP line does not name it,
it appears only as an unqualified entry inside a roadmap phase, which item 14's own MP1/MP5 forbid
treating as launch membership, and dropping it changes no module, dependency, queue, invariant or
commercial flow; **transactional email stays MVP independently**, because launch commerce and
account flows require it, and newsletter is never admitted merely because an email channel exists),
personalized recommendations and cross-device viewed history; **INFRASTRUCTURE GATE** = OpenSearch, read replica,
PgBouncer, separate analytics/search/image services, ACID-core microservice extraction (which the
master already requires a separate saga/compensation ADR for), PostGIS and a separate frontend
stack.

The **payment cut** separates the domain from the provider list: the state machine, `PaymentAttempt`,
exact amount/currency matching, the webhook durable-ingest contract, reconciliation, the signed
return-URL flow and the single provider-adapter interface of `# 12.4` are MVP foundation and are
never cut with a provider; launch providers are **maib + cash + IBAN** exactly per the MVP line,
later providers are **MIA, credit, POS-on-delivery and any further adapter**, with `# 12.4`'s
five-class list and `# 11.4` step 3's six-method enumeration read as the interface's eventual
population rather than a launch requirement, MIA explicitly **not** promoted because no master
passage places a stronger launch requirement on it, no stub/"coming soon" adapter and no
adapter-less method option anywhere, and cash/IBAN held to the same `PaymentAttempt`, state-machine,
actor-scoping and idempotency invariants as a card payment. The **accounts/reviews/favorites/compare
cut** freezes accounts and order history as MVP, `# 14.1` reviews as MVP in full, and **favorites
and compare as LATER** — with `# 13.2`/`# 13.3`'s merge, size-limit and `comparable=True` rules kept
frozen for whenever they ship, guest-`localStorage` favorites classified as part of the same LATER
feature rather than a partial launch, and the promotion of favorites to enrich `popularity_score`
explicitly declined because a one-source or zero-source policy is already valid. The **content cut**
keeps one physical module (feature cut, no package split), with publication identity, block-JSON
sanitisation and CSP in MVP because static pages use them and because they are the module's security
contract, an enum member explicitly not an implemented feature, and the server-side consent
lifecycle untouched. The **delivery/stores/map cut** gives checkout a real physical fulfilment path
(courier + store-scoped pickup reservation), classifies the interactive map LATER with pickup
selection served by a store list — so the launch build carries no tile-provider credential at all,
the strongest form of `# 15.2`'s rule — and keeps `# 15.2`/`# 21.11`'s credential rules binding from
the map module's first release. The **notification cut** ships transactional email only and defers
SMS, resolving master `# 11.3`'s "signed link/**OTP**" to the signed-link branch over the MVP email
channel, with guest Track & Trace on a signed access token, no SMS OTP login, no phone-verification
requirement and admin 2FA on TOTP/WebAuthn.

**CRM and Chatwoot are both LATER**, which **resolves item 9 FD9a's conditional**: `ext.crm`'s
definition stays frozen and undeleted while the domain is **not provisioned**, CRM work may not be
re-routed into another queue to dodge the decision, and no CRM/Chatwoot client, port, adapter, task,
event or column exists in an MVP flow — `place_order` and every order state transition commit with
no CRM interaction of any kind. The **item 13 consequence** is stated without reopening it:
`domains/analytics` and view tracking stay LATER, no analytics failure domain exists to provision
(the absence is at the *definition* level, one step stronger than `ext.crm`'s), and the
**launch-enabled popularity source set is `{successful sales}`** because favorites is LATER and a
non-enabled source is not a term rather than a zero — with rating, the manual boost and page views
still excluded, so reviews shipping at launch does not admit rating into the formula. A derived
**failure-domain launch-provisioning view** references item 9's frozen definitions without editing
them: `core.payments`, `ext.payments`, `core.inventory`, `core.projection.incremental`,
`core.projection.rebuild`, `core.maintenance`, `ext.erp` and `ext.email` are provisioned **YES** by
enabled workload; `ext.sms` and `ext.crm` are **NO**; analytics, support and search domains are
not applicable because no definition exists — with no worker count, concurrency, route syntax or
broker topology chosen. The **dependency-closure matrix** resolves every MVP row to A (dependency
is FOUNDATION/MVP), B (capability narrowed) or C (apparent dependency false, with the contract that
proves it — notably that `# 9.3`'s `search.index.batch` is conditional in the master itself, so at
launch it is not produced at all rather than produced and ignored), giving the launch build the
property that it is a **strict subgraph** of the eventual system: admitting a later module adds
nodes and edges and rewrites none. Twelve fake-compatibility shapes are rejected **by name** (empty
LATER packages, `NullAnalyticsService`, fake CRM/Chatwoot adapters, fake Trade-In providers,
placeholder favorites repositories, null SMS gateways, `try: import` fallbacks, `INSTALLED_APPS`
probing, a service that changes behaviour on package presence, settings-gated present-but-unreachable
code, adapter-less UI options, and queues provisioned for unenabled workloads), and a 20-row
failure/degradation matrix separates **not shipped** (cases 1–15: no alert, no retry, no runbook)
from **enabled-workload failure** (cases 16–20: served by the mechanisms items 9, 10 and 12 already
froze), with the read replica the one case where absence is *required* rather than merely
acceptable, because item 12 CB10–CB14 forbid a lagging replica for builder reads. The checks
**A114–A128**, **C161–C176** and **V130–V145** are recorded for later phases; **no new `L` rule and
no `core` allowlist entry** is added, because item 14 adds no module and no import edge.

**No new ADR was required**, and the evaluation is recorded rather than assumed: item 14 moves no
boundary, assigns no owner, changes no public contract, changes no identity/money/idempotency/
consistency rule, changes no read model or projection strategy, un-defers nothing and adds no event
type, queue or failure domain — it selects feature scope master `# 25`'s MVP line, its "can wait"
list, Phases 9 and 10 and `# 26` MVP governance already authorise, which is the README's explicit
"routine implementation choice inside an already-decided boundary" case. The two decisions that
**would** have needed one were deliberately declined rather than taken: inventing a cross-domain
administrative use case to justify `application/backoffice` (classified LATER instead, with the
admission path already frozen by item 3 §13 and the most likely first candidate — a combined
order+payment view that item 2 §8.3 forbids an interface from composing — named), and assigning an
owner to the newsletter subscriber entity (unnecessary once newsletter is LATER; the artifact or
phase that admits it assigns a legitimate owner before implementation, bounded by items 2, 3 and 4,
with an ADR evaluated **then** if that assignment moves or creates a boundary). ADR-0001…ADR-0014 and
items 1–13 stand unedited.

Deliberately **not** frozen by item 14: infrastructure-gate thresholds, evidence, topology, vendors
and sizing (**item 15**, untouched); the remaining open Phase 0 ADRs — the generic idempotency
mechanism/schema and no-replica-at-launch (**item 15**, still `IN PROGRESS`); the newsletter
subscriber entity's owner (the artifact/phase that admits newsletter, which assigns it before
implementation); **the manual merchandising boost's owner (item 6 §27, untouched)**; whether and for what action `application/backoffice` is admitted (an implementing
phase, under item 3 §13); whether the launch ERP protocol is push, scheduled pull or both (Phase 3 —
both shapes sit inside the MVP boundary); popularity scoring weights, window, quantization and
schedule (Phase 4 / merchandising); the `orders.public` batch aggregate selector that enables the
sales source (`domains/orders`' phase — until it exists the enabled set may legally be empty, with
the sort determined by the deterministic tie-break and nothing stubbed); every deferred feature's
contract — Trade-In, eUpgrade, digital/KMS, Chatwoot identity, analytics event schemas, MIA protocol
details, recommendation schemas and complex CMS models, all **classified only**; the newsletter
capability itself — endpoint, subscriber entity, double opt-in workflow, sending and CRM/mailing
hand-off — which is **LATER** and, when admitted, is bound by master `# 19.3`'s security and privacy
requirements in full; consent categories, banner state machines, retention periods and revocation mechanics (Phase 8 and
the privacy phases); and any post-launch admission of a LATER capability, which follows item 14's
admission rule and needs **no supersession of this artifact**.

## Notes on item 15

Frozen: the **five-way coverage audit** of master `# 25`'s Phase 0 ADR line, recorded as evidence
rather than asserted — **listing projection** covered by ADR-0003 §3 (negatively, from catalog's
side), ADR-0008 (ownership, grain, same-variant correctness, derived-serving classification, full
rebuildability, no request-time OLTP fallback) and ADR-0014 (the convergence/concurrency mechanism
item 6 PU4/PU5 deferred), so a fourth would only restate or contradict them; **module boundaries**
covered by ADR-0004 (layers, `core` admission test, single cross-domain owner, transaction
ownership), ADR-0005 (the cell-by-cell import matrix L1–L21, ports, the single composition root) and
ADR-0006 (the two `core` primitives item 4's template required), with item 3 §15 already classifying
every rule as import-linter / AST / review — the form the DoD actually needs; **event versioning**
covered by ADR-0009 in full (stable `event_type`, integer `schema_version`, immutable published
versions, exact-version consumers with registered upcasters, consumer-first migration,
unknown/invalid → durable quarantine + alert), with ADR-0010/ADR-0011/ADR-0013 as neighbours that
reopen none of it; and the two **real gaps** — the generic command-idempotency mechanism (ADR-0007 §2
froze placement *behaviour* and deferred the mechanism here by name; ADR-0009 §7 covers the
*message-delivery* side, a different subject) and the no-replica-at-launch decision (master prose,
item 14 §22's `INFRASTRUCTURE GATE` classification and ADR-0014 §3's "remains item 15's" all pointed
here, and none of them decided it). **Exactly two ADRs were created**; no redundant ADR was written
to make the count symmetrical.

**[ADR-0015](../../adr/0015-postgresql-command-idempotency.md) was required** and is accepted:
command idempotency is durable PostgreSQL state identified by `(scope, key)` under a database unique
constraint, bound to the claiming principal and to a semantic request fingerprint, with the claim,
the commercial effect and the replayable completion committing **together** for a command scope whose
protected durable effect is **one local ACID transaction**, and a rollback leaving **no** durable
claim. Frozen with it: the **local / provider split** — a provider network operation is never that
effect, no transaction spans a network call, no local `IdempotencyKey` makes an external provider
operation atomic, a provider-facing workflow keeps its local layer and its provider layer
(provider idempotency key + state machine + reconciliation, ADR-0007 §3 / ADR-0010) separate, master
`# 20.4`'s scope names are **illustrative** rather than proof of shape (so `payment.initialize`'s
local durable command, if any, is the payments phase's to identify while its provider call stays
post-commit), and a command needing one idempotency contract across multiple commits or an external
effect requires **its own ADR** rather than an assumed extension of this one; the **five separated
mechanisms**
(`IdempotencyKey` = command invocation, Inbox + `EventId` = message delivery, provider
`external_event_id` = inbound webhook dedupe, provider idempotency key = outbound call retry, domain
`UNIQUE`/state machine = the permanent business effect), none derivable from another and an `EventId`
never a command key; PostgreSQL as the only thing deciding execution, replay, `Conflict` and
ownership, with Redis disposable anti-storm whose loss, flush, eviction or outage changes none of the
four; a platform-owned bounded `scope` never taken from client input and an opaque `key` carrying no
authorization, timestamp or ordering and **not** globally unique across scopes; principal binding
(same principal + same fingerprint → replay, different fingerprint → `Conflict`, different principal
→ ownership refusal with no data and no existence disclosure, `NULL` never meaning "anybody", the
durable encoding left to Phase 1); a canonical **semantic** fingerprint — deterministic,
discriminating, canonicalization-stable, computable without retaining the raw body, never containing
a secret — whose field list is **per scope** (`place_order`'s stays item 5 ID3's); the **refinement of
master `# 5.2`'s `processing / completed / failed` sketch**, with `processing` legal only as
uncommitted transaction-local state, no durable `failed` in the generic mechanism (so no accidental
validation error can reserve a key forever) and a durable rejected outcome admitted only where a
scope's own contract states the behaviour and its reason; contenders serialized on the durable
uniqueness constraint rather than an application mutex or a Redis lock, with a bounded lock wait a
technical fault; commit ambiguity leaving the operation committed, replaying on retry and attempting
**no** compensation; **bounded semantic result replay** — result kind, resource `PublicId`, a bounded
status snapshot — with `response_body_json` demoted to an optional per-scope strategy, no cookies,
headers, credentials or unbounded JSON stored, heavy material never read on the claim path, and no
polymorphic cross-domain FK; explicit per-scope retention covering at least the promised retry window
and at least 24 h for HTTP commands, with the honesty rule that **expiry ends the replay promise** and
that advertised guarantees must agree with retention; idempotency ≠ business uniqueness, so deleting
an expired row never makes a permanently single-use operation repeatable; local and outbound provider
idempotency as separate layers, with a provider response never deciding whether the local `Order`
exists; and the security rules (key ≠ authorization, fingerprint ≠ authentication, no credential in
either, redacted/hashed keys in logs where a scope treats them as sensitive).

**[ADR-0016](../../adr/0016-no-application-read-replica-at-launch.md) was required** and is accepted:
the launch application sends **no** read traffic to a PostgreSQL replica, primary is the default and
current source, a future replica is a measured per-read-path explicit opt-in, and an HA standby is a
separate concept. Frozen with it: the launch baseline (no request path selecting a replica, no global
ORM router, no default read alias on a replica, no replica-aware selector required of any MVP module,
and **no sticky-primary machinery shipped for a replica that is not used** — item 14 NF10/A128's ban
on settings-gated unreachable code applied); **read replica ≠ HA standby**, so a provider-managed or
physical streaming standby for backups, PITR, DR and failover stays legitimate, is simply never an
application read target, and on promotion *is* the primary, with failover topology, replication mode
and RPO/RTO left to operations; the master's own reasons recorded rather than invented (target scale,
the storefront's own serving projection, Redis/CDN absorbing disposable reads, query budgets that must
be fixed rather than hidden, unnecessary sticky-primary complexity) and the explicit note that this is
a simplicity/correctness decision at this scale rather than a claim that replicas are bad; the global
verb/model/app-label/method-based router forbidden **permanently**, so no read path changes
consistency class as a deployment side effect; the enumerated set of reads that is **never** a replica
candidate — placement preparation and revalidation, inventory reservation and stock, pricing/promotion
/coupon validation feeding a write, payment state and reconciliation, the idempotency claim,
fingerprint comparison and ownership check, actor/permission/ownership state, Outbox relay claiming,
Inbox dedupe/identity/state, webhook durable ingest, every write and lock, any read that immediately
participates in a correctness write, and **`application/storefront`'s projection-builder source reads
under item 12 CB10–CB14 / ADR-0014 §3, which opening the gate later does not weaken by one clause**;
the future admission gate as a **recorded evidence review** over frozen criteria *categories* —
primary CPU/I-O pressure, connection/pool pressure, query budgets already satisfied, indexes and plans
reviewed, cache/projection already applied, material load contribution, explicitly stated tolerated
staleness — with **no numeric threshold frozen in Phase 0**; **per-read-path admission** recording
path, owner, staleness semantics, post-write behaviour, fallback rule, lag-safety rule, metrics and
tests, so no module gains access wholesale and one module may legitimately hold both primary-only and
replica-eligible selectors without any change to the dependency architecture; read-your-own-writes /
sticky-primary as a frozen **requirement** with the cookie format, TTL, middleware and routing code
deliberately unfrozen and the causal window owned per path; lag safety on master `# 22.8`'s four
metrics, with a path exceeding its stated tolerance becoming ineligible and reading primary rather
than serving known-too-stale data; a replica outage as never a correctness outage (no write blocked,
no primary-required read degraded, and at launch the case does not exist); no transaction split across
sources and no distributed-consistency assumption introduced; and security freshness never traded for
throughput.

Recorded with the two ADRs in the [item 15 artifact](15-adr-closure.md): the frozen `IdempotencyKey`
lifecycle diagram and the master-sketch treatment table; the two failure matrices — 20 idempotency
rows whose every commercial-impact cell is `None`, and 18 replica rows — the interaction audit against
items 5, 8, 9, 10, 11, 12 and 14 with **nothing reopened**; the final Phase 0 dependency/decision
audit and DoD verification; the checks **A129–A145**, **C177–C198** and **V146–V163**; a 42-point
acceptance checklist; and the Phase 1 handoff. **No `L` rule and no `core` allowlist entry is added**,
no dependency-matrix cell moves, no import edge appears, no event-registry column or
consumer-declaration attribute is created, and **ADR-0001…ADR-0014 are untouched**.

Deliberately **not** frozen by item 15: the physical `IdempotencyKey` model, columns, types, indexes,
partitioning and migration, the durable principal/actor-fingerprint encoding, the canonicalization
function and digest library, and the purge job's mechanics (Phase 1 / the authentication phase); the
exact fingerprint field list and numeric retention period of any scope beyond the 24-hour HTTP floor,
and the full scope registry beyond master `# 20.4`'s illustrative names (each owning command's phase —
`place_order`'s field list stays item 5 ID3's); the concrete claim/contention SQL, savepoints and
timeouts (Phase 1); HTTP status mapping and header names such as `X-Idempotency-Key` (the Web and DRF
phases); any command whose durable effect is not a single local ACID transaction, and any durable
rejected-outcome state added to the generic mechanism (a new ADR); failover topology, replication
mode, promotion procedure, RPO/RTO and backup/PITR design (operations, master `# 23.5`); every numeric
threshold for lag, load, pool pressure or staleness (the replica gate's own review); the routing
mechanism, database aliases, selector signatures, middleware and cookie/session scheme should that
gate open, and which display paths would be admitted first (that phase and that review); the other
infrastructure gates — OpenSearch, PgBouncer, separate analytics/search/image services, ACID-core
extraction and PostGIS — each of which stays item 14 §22's classification pending its own evidence
review and, for the ACID core, the master's required saga/compensation ADR; and any change to the
idempotency rules (PostgreSQL truth, `(scope, key)`, principal binding, the one-transaction lifecycle,
the absent durable `failed` state, bounded result replay, the retention honesty rule, the five-way
separation) or to the replica rules (the launch baseline, the permanent router ban, the correctness-read
set, the evidence gate, per-path admission, read-your-own-writes, lag safety, the outage rule), each
requiring a new ADR superseding ADR-0015 or ADR-0016.
