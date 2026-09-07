# Phase 0 — Item 7: `ProductCard` / Facet DTO contract of `application/storefront`

- **Status:** DONE / FROZEN
- **Date:** 2026-09-04
- **Phase:** 0 — Architecture Freeze
- **ADR:** none required — see §1.3
- **Related:** [ADR-0001](../../adr/0001-product-vs-sku-sellable-unit.md),
  [ADR-0002](../../adr/0002-typed-eav-source-of-truth.md),
  [ADR-0003](../../adr/0003-catalog-boundary-vs-storefront-projection.md),
  [ADR-0005](../../adr/0005-dependency-and-integration-wiring.md),
  [ADR-0006](../../adr/0006-public-contract-primitives.md),
  [ADR-0008](../../adr/0008-storefront-listing-projection.md),
  [item 4](04-domain-public-contract.md), [item 6](06-storefront-listing-projection.md),
  [ERD — catalog](../erd/catalog_product_sku_attributes.md),
  master `# 4.4`, `# 7.2`, `# 7.3`, `# 7.6`, `# 10.2`–`# 10.7`, `# 10.9`, `# 14.1`, `# 22.2`, `# 22.4`

---

## 1. Purpose

### 1.1 What this item freezes

Item 6 froze the **source and the path** of the storefront read contract
(`ProductListingProjection → storefront selector → immutable DTO → Web/API`, RP1–RP7) and explicitly
left the DTO shapes open (CT6, RP6, §27). This item freezes the **semantic output contract** carried
on that path, and the minimum **input** shape needed for a returned facet to be applied back to the
same selector.

Frozen here:

- the DTO baseline for `application/storefront` and its forbidden field categories (§4);
- `ProductCard` and its nested display DTOs, including the price representation, its **explicit
  basis** and the **coherent comparison-pair** rule for `amount`/`regular_amount`/discount (§5);
- `Badge` (§6);
- the **public facet identifier strategy** — attribute facets by immutable catalog `code`, entity
  facets by `PublicId`, no internal bigint anywhere (§7);
- the **facet type system**: six explicit frozen variants with genuinely different value semantics,
  no generic value bag, and the two sources of a facet's `scope` (§8);
- the **count-quality model**: exact / approximate / unavailable, kept distinct from `0` and from a
  truncated option set (§9);
- **selection state and canonical ordering ownership** (§10);
- the **materialised listing result** and the two pagination-metadata variants, with the cursor as an
  opaque public token (§11);
- the **round-trip query contract**: the six `FilterTerm` shapes and their invariants; **`AND` between
  facet keys, `OR` between values of one discrete key, with every variant-scope disjunction evaluated
  inside the single-variant existential**; one canonical term per key and one shared canonicalization;
  and what an exact facet count means under that `OR` (§12);
- **localization**: which strings are already-localized content and which stay structural codes (§13);
- **availability and rating** as display state only (§14);
- the **compatibility classification** of the likely future changes (§16);
- the checks later phases must implement (§18) — A36–A41, C37–C54, V39–V51.

### 1.2 What this item does **not** do

No Python package, module, `public.py`, model, migration, serializer, view, setting or dependency is
created. Phase 0 produces documents and decisions only. Every code fragment in §17 is illustrative
pseudo-code, not a file to be copied.

Specifically **not** decided here: `Money`/`PublicId` implementation (item 11); the filtered-price
display/sort/cursor policy (a joint storefront decision before Phase 4, ADR-0008 §5, SO3b–SO3d); the
physical projection schema and the facet-vocabulary serving structure (Phase 4); the cursor codec,
its internal fields and page-size limits (Phase 4); `source_version` (item 12); event schemas (item
8); queue/DLQ (item 9); trace fields (item 10); analytics popularity (item 13); the manual
merchandising boost owner (still unassigned, boost still disabled); and the exact Web HTML and DRF
serializer representations. §20 is the complete list.

### 1.3 Why **no** new ADR is required

An ADR is required when a boundary moves, a `core` allowlist changes, an identity/money/consistency
rule changes, a read-model strategy changes, or a frozen public contract **changes shape**
(`docs/adr/README.md`). Item 7 does none of these. It gives the first concrete shape to a contract
whose existence, owner, source, path, style and constraints were already frozen:

| Item 7 decides | Already frozen by | Item 7's role |
|---|---|---|
| DTO style (`frozen/slots/kw_only`, immutable field types, no `id`/`pk`) | item 4 §7, SP3 | applies |
| One shared Web/API DTO on one read path | ADR-0008 §5, RP1–RP3 | applies |
| Card/Facet/Badge field lists | ADR-0008 "out of scope … item 7"; item 6 CT6, RP6, §27 | **explicitly delegated** |
| Pagination metadata as a frozen DTO | item 4 K3; item 6 PG8, SP6 | **explicitly delegated** |
| Card price representation, not sort semantics | item 6 SO3d, ADR-0008 §5 | **explicitly delegated**, with the ban respected |
| Facet counts exact vs degraded | item 6 F6, F6a, F7 | applies, adds a type |
| No internal bigint as a public identifier | ADR-0001 §3.3/§3.4, item 4 I1–I3, item 6 I5 | applies |
| Attribute/choice addressed by immutable `code` | ADR-0002 §118, ERD §3.4 D-11, I-7 | applies |

The delegation is explicit in both directions: ADR-0008 lists `ProductCard`/`Facet`/`Badge` fields
under "Out of scope of this ADR", and item 6 §27 assigns them to item 7 as an artifact-level
deferral. Freezing them here is the intended completion of that deferral, not a new decision.

**Five changes that would have required an ADR, and are deliberately not made:**

| # | Would-be decision | Why it would need an ADR | Item 7's position |
|---|---|---|---|
| 1 | Put a facet key/value or language primitive in `core` | Extends a `core` submodule allowlist frozen by ADR-0005 §1 — exactly ADR-0006's precedent | Facet vocabulary and `StorefrontLanguage` stay **application-owned** (FK1, LO5) |
| 2 | Let an active variant filter change the card's effective price | Moves ADR-0008 §5's joint display/sort/cursor deferral | `PriceBasis` has exactly one legal member today (CD8–CD10) |
| 3 | Use an internal bigint (`choice_id`, `category_id`) as the facet identifier | Changes the identity rule of ADR-0001 §3.3 and item 4 I3 | Forbidden by FK2, checked by A36/C38 |
| 4 | Count a variant-scope facet off the product-level union | Changes ADR-0008 §3's matching/counting decision | `EXACT` means satisfier-confirmed (FQ4) |
| 5 | Give Web or API its own DTO/serializer-shaped contract | Changes ADR-0004 §5 / ADR-0008 §5's one-read-path rule | One DTO graph, transport-neutral (DC2, C37) |

If any of the five is later wanted, it is an ADR, not a field addition.

---

## 2. Frozen principles inherited

| # | Inherited rule | Source |
|---|---|---|
| R1 | `application/storefront/public.py` is the module's only importable surface; no ORM model, QuerySet, manager, `Paginator`/`Page`, cache client or search-vector type crosses it. | item 6 SP1, SP2; ADR-0005 §7 |
| R2 | Public DTOs are `@dataclass(frozen=True, slots=True, kw_only=True)`, fully annotated, immutable **by field type** (`tuple`/`frozenset`/nested frozen DTOs), with no `Any`, `Mapping`, `Sequence`, mutable collection, money `float`, or field named `id`/`pk`. | item 4 §7.1, §7.4, D1–D10; item 6 SP3 |
| R3 | A selector returns fully materialised immutable results; no lazy object, generator or deferred attribute crosses. | item 4 §10.1, §10.3, K1 |
| R4 | Public locators are `PublicId`; an internal bigint never becomes a user locator, an API payload identifier, an external contract identifier or an externally consumed event identifier. It may travel outward **only** inside a signed opaque cursor. | ADR-0001 §3.3, item 4 I1–I3, item 6 I5, PG4 |
| R5 | Storefront listing reads are **public state**: no actor parameter (and therefore no private or customer-scoped data). | item 6 SP4, SEC1–SEC3 |
| R6 | Web and API consume the same semantic application result from the same selector; localization and transport representation happen at the edge. | item 6 RP1, RP4, RP7; master `# 10.9` |
| R7 | Existential same-variant matching is the frozen listing semantics; the product-level union is a prefilter, never the answer, for variant-scope predicates. | item 6 §6.3, G3, G4, F6a; ADR-0008 §3 |
| R8 | Facet counts use the same predicate as the listing; a degraded count is labelled and never presented as exact. | item 6 F6, F6a, F7 |
| R9 | Sorting is deterministic with a mandatory unique final tie-break key; deep paths use keyset pagination on a signed opaque cursor; bounded page-number pagination is allowed for shallow SEO pages. | item 6 SO2, PG2–PG4 |
| R10 | The product-wide price sort baseline stands; card display, price sort key and cursor must use **one** price semantics, decided jointly before Phase 4. Item 7 may define the card price representation and may **not** change sort semantics. | item 6 SO3a–SO3d, RP6; ADR-0008 §5 |
| R11 | Badge codes are structural and localized at the Web/API edge; the projection stores no UI text. | item 6 §8, RP4; master `# 7.6` |
| R12 | `AttributeDefinition.code` and `AttributeChoice.code` are immutable; those entities have **no** `public_id` and are addressed by `code`. `Category`/`Brand` **do** carry `public_id`. | ADR-0002, ERD §3.4 (D-11), I-7 |
| R13 | The listing request performs no EAV traversal and no per-facet attribute-definition lookup. | item 6 F3, QB3 |
| R14 | The projection is display state, never checkout truth. | item 6 T6, T7, CT3 |

Nothing below weakens any of these.

---

## 3. Vocabulary

| Term | Meaning here |
|---|---|
| **Storefront DTO graph** | The transitive closure of frozen objects returned by a storefront selector: result → cards/facets/page info → nested DTOs and value objects. |
| **Facet** | One filterable dimension offered to the user, with its public key, its label and its value semantics. |
| **Facet option** | One selectable discrete value of a facet (choice, boolean, entity). Range facets have bounds, not options. |
| **Facet key** | The public, application-owned token that names a facet in a request and in a DTO. |
| **Facet value identity** | The public identifier of one option: an immutable catalog `code`, a `PublicId`, or a `bool`. Never an internal bigint. |
| **Count quality** | Whether a returned number is satisfier-confirmed exact, deliberately approximate, or not computed. |
| **Canonical query** | The normalized, whitelist-filtered, deterministically ordered form of the query the selector actually executed. |

---

## 4. The storefront DTO baseline

| # | Rule |
|---|---|
| DC1 | Every symbol in this contract is owned by `application/storefront`, defined in its internal modules, and exported later **only** through `application/storefront/public.py` under item 4 §4.1's façade rules (S1–S9). No file is created in Phase 0. |
| DC2 | The DTO graph is **transport-neutral**. It carries no HTML, no URL, no CSS class, no colour, no icon name, no HTTP status, no template name, no serializer metadata, no `Content-Type`, no DRF/Django type. Web and API each map the same graph into their own representation (R6). |
| DC3 | The graph is **fully materialised and immutable to the depth its annotations promise** (R2, R3). Every collection field is a `tuple` (or `frozenset` where order is genuinely meaningless); no nested field is an ORM object, QuerySet, model instance, lazy object, generator, paginator, cache handle or search-vector type. |
| DC4 | Every DTO member is **pure and total** (item 4 §7.3): computed from the instance's own fields, with no I/O, no query, no cache and no global state. `slots=True` removes `cached_property` by construction. |
| DC5 | **No `Any`.** Where several semantic shapes are possible, the contract uses an explicit **union of frozen variants** (`Facet`, `FilterTerm`, `PageInfo`, `PageRequest`), never one type with a polymorphic field. |
| DC6 | **No generic bag-of-fields DTO.** A DTO whose meaning depends on which of its optional fields happen to be set is forbidden; that shape becomes explicit variants instead. |
| DC7 | Optionality (`X \| None`) means **absent**, never "unknown, ask again", never "zero", and never "degraded" (item 4 D10). Degradation and omission of a *number* are carried by the quality enum of §9, not by `None` alone, and not by `0`. |
| DC8 | Instants are timezone-aware UTC `datetime`; money is `Money`; non-money decimals are `Decimal`; ratings keep the frozen `×10` integer representation (master `# 14.1`). No `float` anywhere. |
| DC9 | **Forbidden field categories** in the whole graph: internal bigint / ORM identity (`id`, `pk`, `product_id`, `choice_id`, …); ERP/provider identifiers (ADR-0003 §2, item 6 I8); cost, margin, supplier or purchase data; any customer-scoped, personalized, consent, session, cart or order value (R5, item 6 SEC1/SEC2); projection bookkeeping (`source_version`, `updated_at`-as-version, freshness state); heavy payloads the card does not render — gallery, specification JSON, long description (item 6 CT4, master `# 22.4`); cache keys, TTLs, search vectors, index names or any other serving-implementation type. |
| DC10 | Storefront listing selectors take **no actor** and the graph is identical for anonymous and authenticated callers (R5, C46). A future private storefront capability is a different contract with a mandatory actor (item 6 SP4). |
| DC11 | A value object in this contract (`FacetKey`, `FacetValueId`, `Cursor`) validates only its **own shape** in `__post_init__` (charset, length, non-empty). Constructing one is **not** authorization to use it: whether a key is filterable, whether a value exists and whether a cursor is authentic is decided by the storefront's whitelist compiler (QI3, master `# 10.2`). |

---

## 5. `ProductCard`

### 5.1 The decision

> **The card is Product-grained, matches the visible result grain of item 6 §6.1, is addressed by
> `Product.public_id`, and carries exactly the data a listing card renders — nothing that belongs to
> the product detail page, to checkout, or to the projection's own bookkeeping.**

Final shape (illustrative annotation style; the contract is the field list, its types and its rules):

```python
@dataclass(frozen=True, slots=True, kw_only=True)
class ProductCard:
    product_public_id: PublicId          # R4 — the only product locator on the card
    slug: str                            # localized navigation slug of this language row
    name: str                            # already-localized listing name (LO1)
    brand: CardBrand | None              # display facts of the owning brand, if any
    image: CardImage | None              # vendor-neutral reference + localized alt
    price: CardPrice                     # §5.3 — basis-explicit
    availability: AvailabilityState      # §14 — display state, two members
    rating: CardRating | None            # None means "no approved reviews", never 0.0
    badges: tuple[Badge, ...]            # §6 — structural codes, application-ordered
```

```python
@dataclass(frozen=True, slots=True, kw_only=True)
class CardBrand:
    public_id: PublicId                  # Brand.public_id (ERD §3.4)
    name: str
    slug: str

@dataclass(frozen=True, slots=True, kw_only=True)
class CardImage:
    reference: str                       # storage-relative reference, NOT a URL (CD/CD5 below)
    alt: str | None                      # localized alt; None = not authored

@dataclass(frozen=True, slots=True, kw_only=True)
class CardRating:
    average_x10: int                     # 47 == 4.7 (master # 14.1, frozen representation)
    count: int                           # approved reviews only
```

### 5.2 Rules

| # | Rule |
|---|---|
| CD1 | The card is **Product-grained**. It exposes no SKU/variant identity, no variant list, no variant count and no per-variant breakdown. A variant-scope fact reaches the card only as an already-aggregated display value under §5.3/§14. |
| CD2 | `product_public_id` is the card's only product identity. No `id`, no `pk`, no `product_id`, no projection row identity (R4, item 4 I2, A36). |
| CD3 | Every field is supported by an item 6 §8 projection category: source identity, taxonomy, display facts, RO/RU listing text, media reference, display pricing, availability, rating summary, badge inputs. The card invents no new projection input. |
| CD4 | `brand` is present because item 6 §8 admits brand display facts and master `# 7.6` projects `brand_id`; it is `None` for a product with no brand. **Category is deliberately absent** from the card: a grid card renders no category, and category ancestry is a filter token, not card content (master `# 22.2`'s select list). Adding it later is an additive change (§16). |
| CD5 | **Media is vendor-neutral.** `CardImage.reference` is a storage-relative reference exactly as master `# 7.6`'s `primary_image_path` is; it is **not** an absolute URL, not a signed provider URL, not a bucket/key pair, not a storage-backend object, and not a `srcset`. Deriving responsive URLs, formats and CDN versioning from the reference is transport/media work (master `# 7.3`). Changing storage provider must not change this contract. |
| CD6 | Image dimensions, gallery, video and any other detail-page media are **not** on the card (item 6 CT4). |
| CD7 | `badges` is an ordered tuple whose order is the render order (SL3). Unknown badge codes are the transport's problem, not the card's (BD4). |

### 5.3 Price on the card — the basis is part of the contract

| # | Rule |
|---|---|
| CD8 | `CardPrice` carries an explicit **`basis`**: which price semantics produced the numbers. Today exactly one member is legal — `PriceBasis.PRODUCT_WIDE` — matching item 6 SO3a's frozen baseline: the product-wide projected price, including under an active variant-scope filter. |
| CD9 | Making the basis an explicit, exhaustively matched enum is what keeps the deferred policy deferred **and** unambiguous: the card states which semantics it used instead of leaving a reader to assume. Adding `FILTER_MATCHED_VARIANT` later is a **breaking** change (item 4 N5) that may be made only together with the joint display/sort/cursor decision of item 6 SO3d — and never by item 7 or by a card-only change (V45). |
| CD10 | Item 7 therefore **does not** decide that a variant filter changes the effective price, **does not** invent matched-variant aggregation, **does not** request a projection column, **does not** define a satisfier encoding and **does not** touch price sorting or cursor semantics (R10). |
| CD11 | `amount` is the price the card displays. `amount_is_lower_bound` is `True` when sellable variants of this product have differing prices, so the transport renders "from <amount>"; it is derived from the frozen row-level `min`/`max` aggregates (item 6 G9) and states a display fact, not a match. The maximum itself is not exposed — a card does not render it. |
| CD12 | **`amount`, `regular_amount` and `discount_percent_bps` describe ONE coherent price comparison.** Under `PriceBasis.PRODUCT_WIDE`, `amount` remains the frozen product-wide display baseline; `regular_amount`, when present, **must be the comparison/reference price of the same pricing observation — the same representative variant — that supplied `amount`**. It must **not** be independently aggregated from a different variant because it happens to be the largest or the most convenient regular price. |
| CD12a | Worked case: variant A `current=100, regular=120`; variant B `current=110, regular=200`. With `amount = 100` the card may show `regular_amount = 120`. It may **never** show `regular_amount = 200` to claim a discount from 200 to 100 — that pair describes no purchasable offer and is a false commercial statement on a page whose price is not even checkout truth (R14). |
| CD12b | **If no coherent pair can be established for the displayed amount, both fields are absent:** `regular_amount = None` **and** `discount_percent_bps = None`. Showing an incoherent comparison is never the fallback; showing no comparison is. |
| CD12c | Invariants validated in `__post_init__` (DC4): `regular_amount` present ⟹ `regular_amount.currency == amount.currency`; `regular_amount > amount`; `discount_percent_bps` present **iff** `regular_amount` present. |
| CD12d | The card exposes **no representative-SKU identity** — no variant `public_id`, no `sku_code`, no index (CD1). Coherence is a property the application guarantees, not a fact the card discloses. Which physical projection support produces the pair is Phase 4's; the **semantic** requirement is item 7's. |
| CD13 | `discount_percent_bps` is computed **once, in the application, from exactly that pair**, using the project's later `Money` rounding rule (item 11). It is never independently aggregated from other variants and never re-derived by a transport — otherwise Web and API round differently and break parity (R6, C37). |
| CD14 | `CardPrice` is **display state only** (R14, item 6 CT3): no tax breakdown, no cost, no margin, no coupon eligibility, no personalized or entitlement price, no promotion identity. The commercial answer comes from the owning domains at cart/checkout time. |

```python
class PriceBasis(StrEnum):
    PRODUCT_WIDE = "product_wide"        # the only legal member until the SO3d joint decision

@dataclass(frozen=True, slots=True, kw_only=True)
class CardPrice:
    basis: PriceBasis
    amount: Money
    amount_is_lower_bound: bool
    regular_amount: Money | None         # same observation as `amount`, or None (CD12–CD12c)
    discount_percent_bps: int | None     # computed from exactly that pair, or None
```

---

## 6. `Badge`

| # | Rule |
|---|---|
| BD1 | A `Badge` carries a **structural semantic code** and nothing else. No localized text, no CSS class, no colour, no icon, no priority-for-CSS, no inline style, no URL (DC2, R11). |
| BD2 | `code` is a `str` from a documented, storefront-owned vocabulary, copied from the projection's `badge_codes` (master `# 7.6`). It is deliberately **not** a public enum: badge vocabulary grows with merchandising, and an exhaustively matched enum would make every new badge a breaking contract change (item 4 N5). |
| BD3 | The vocabulary is stable and additive: a code's **meaning** never changes once used; retiring a code means it stops being emitted, never that it is reused for something else. |
| BD4 | A transport **must render an unknown code safely** — skip it — and must never echo the raw code as user-visible text. Localization of a known code is an interface translation-catalog lookup (R11). |
| BD5 | Badge **order is the application's** (SL3) and is deterministic; a transport must not re-sort badges. |
| BD6 | **Parametrized badges are not modelled here.** A badge that must render a number (master `# 18.2`'s eUpgrade example) needs an owner for its parameter vocabulary and its value source; Trade-In/eUpgrade is out of MVP scope. The `-N%` case needs no badge parameter — it is `CardPrice.discount_percent_bps`. A parametrized badge is a deferred, additive extension (§20). |

```python
@dataclass(frozen=True, slots=True, kw_only=True)
class Badge:
    code: str
```

---

## 7. Facet identity — the public key/value strategy

### 7.1 The problem this solves

A facet is only useful if the value the server returned can travel out to Web/API, into a URL or a
JSON body, back in a request, and into the whitelist compiler, meaning exactly the same thing.
Master `# 7.2` stores discrete facets as `facet_choice_ids bigint[]`, so the convenient identifier is
an internal bigint — which R4 forbids on every public boundary. The catalog offers two different
stable public identities depending on the entity (R12), and they must not be forced to look alike.

### 7.2 Rules

| # | Rule |
|---|---|
| FK1 | Facet vocabulary is **owned by `application/storefront`**. It is not moved into `core` (that would extend a `core` allowlist and require an ADR — §1.3) and it is not owned by `catalog` (a domain does not know it is projected — item 6 O2). |
| FK2 | **No internal bigint is ever a facet key or a facet value identity** — not in a DTO, not in a URL, not in an API payload, not "just for convenience". The projection's `choice_id`/`category_id`/`brand_id` stay internal, and the compiler maps public identity → internal token inside the module (R4, A36, C38). |
| FK3 | A **facet key** is a single application-owned public token, typed `FacetKey`. Two vocabularies feed it: an **attribute-derived** key built from the immutable `AttributeDefinition.code` (R12), and a **structural** key from a closed storefront list (category, brand, price, availability). |
| FK4 | The two vocabularies must be **disjoint by construction**, not by convention: a key carries its source kind, so a future catalog attribute with `code = "price"` can never silently reinterpret an existing URL. This is a real correctness hazard, not cosmetic uniformity, and is the only reason a shared token shape is frozen at all. |
| FK5 | The **concrete spelling** of that disjointness (prefix, separator, casing) is a Phase 4 decision bounded by FK3/FK4 and by URL-safety. It becomes externally visible and effectively immutable the moment it ships, because it appears in crawlable URLs (master `# 10.6`); changing it afterwards is a breaking change (§16). |
| FK6 | **Facet value identity is typed per kind and is not flattened into one wire form:** a discrete attribute value is the immutable `AttributeChoice.code` (`FacetValueId`); an entity value is the owning entity's `PublicId` (`Category.public_id` / `Brand.public_id`, ERD §3.4); a boolean value is a `bool`; a range has no value identity, only bounds. Forcing a `PublicId` into a string token so all facets "look the same" is explicitly rejected — it would hide an identity distinction that ADR-0001 §3 deliberately makes. |
| FK7 | `FacetKey` and `FacetValueId` are frozen application value objects, not bare `str`, so that a raw request string cannot reach a selector untyped and so A38 is checkable. They validate their own shape only (DC11). |
| FK8 | Resolving a public facet key/value to a projection predicate, and resolving facet **labels**, must not add a per-facet query, an attribute-definition lookup or any EAV traversal to a listing request (R13). The vocabulary/label source is a storefront-owned, rebuildable serving structure; its physical form (in-row, sibling relation, or a warm single-flight cache per item 6 CA4) is Phase 4's, bounded by this rule. |
| FK9 | Per-store availability faceting is **not** modelled here: no public locator for `Store` is frozen anywhere in the architecture (master `# 15.1` gives it an ERP-aligned `code`). The projection may carry `in_stock_store_ids` (item 6 §8), but exposing it as a facet waits for the phase that owns `Store`'s public contract (§20). |

---

## 8. The facet type system

### 8.1 The decision

> **Six explicit frozen facet variants, distinguished by their value semantics, combined in one
> typed union. No generic facet type, no `value: Any`, no polymorphic option.**

| Variant | Value semantics | Value identity | Typical scope |
|---|---|---|---|
| `ChoiceFacet` | discrete catalog choices | `FacetValueId` = `AttributeChoice.code` | product or variant |
| `BooleanFacet` | closed two-valued domain | `bool` | product or variant |
| `IntegerRangeFacet` | integer bounds + unit | — (bounds) | product or variant |
| `DecimalRangeFacet` | `Decimal` bounds + unit | — (bounds) | product or variant |
| `MoneyRangeFacet` | `Money` bounds | — (bounds) | variant, by definition |
| `EntityChoiceFacet` | category/brand entities | `PublicId` | product |

```python
type Facet = (
    ChoiceFacet | BooleanFacet | IntegerRangeFacet
    | DecimalRangeFacet | MoneyRangeFacet | EntityChoiceFacet
)
```

### 8.2 Shared facet header

Every variant carries the same three header fields. Whether Phase 1 expresses them by a non-exported
frozen base class or by repeating them per variant is a style choice; the **contract** is that all
six carry them:

```python
key: FacetKey            # FK3
label: str               # already localized (LO2)
scope: FacetScope        # PRODUCT | VARIANT — catalog-copied or contract-fixed per FT2, never guessed
```

### 8.3 Rules

| # | Rule |
|---|---|
| FT1 | The variants are a closed union. Adding a variant is **breaking** for exhaustive matchers (item 4 N5) and is reviewed as such (§16). |
| FT2 | **`scope` has two sources, by facet family, and is never guessed and never request-supplied.** For an **attribute-derived** facet — `ChoiceFacet`, `IntegerRangeFacet`, `DecimalRangeFacet`, and a `BooleanFacet` backed by an `AttributeDefinition` — it is **copied from the catalog-owned** `AttributeDefinition` scope / effective-scope metadata (item 6 G1, ADR-0002 §2); `application/storefront` never infers it. For a **structural** facet it is **fixed by this contract** from already-frozen business semantics: category → `PRODUCT`, brand → `PRODUCT`, price/`MoneyRangeFacet` → `VARIANT` (item 6 G8), availability → `VARIANT` (item 6 §9.2). A structural `BooleanFacet` representing availability takes its `VARIANT` scope from those frozen availability semantics, not from catalog metadata — there is no `AttributeDefinition` behind it. No transport infers scope and no request may override it (QI11, A41, C53). No scope primitive is created in `core`. |
| FT3 | **`scope` is not a licence to compute matching client-side.** A transport must never combine facet values, unions or counts to decide what matches; matching is R7's satisfier semantics, evaluated only by the storefront compiler. A DTO **describes** a facet; it never exposes the product-level union, per-variant token sets or any structure that would invite reconstruction of the predicate (V39). |
| FT4 | `MoneyRangeFacet` is `scope = VARIANT` (item 6 G8): a price predicate is satisfied by a **sellable variant**. The card's displayed price is product-wide (CD8). These two facts can visibly disagree, and that disagreement **is** the deferred SO3b policy — the contract states it openly rather than hiding it behind a shared field name. |
| FT5 | Range facets carry **scope-level domain bounds** (`range_min`, `range_max`) for the current listing scope, not bounds refined by the active filter set. This is stated in the contract so a transport cannot claim otherwise; a slider therefore may offer a sub-range that yields no results, which is honest and cheap. Switching to candidate-refined bounds later is a **breaking** semantic change (§16). |
| FT6 | Range facets carry **no counts**: counting is defined over discrete values (item 6 F5, master `# 10.4`). |
| FT7 | `IntegerRangeFacet` and `DecimalRangeFacet` are separate variants because their value domains differ; `DecimalRangeFacet` uses `Decimal`, never `float` (DC8), regardless of any scaled-integer physical storage (master `# 7.2`'s `attr_screen_inch_x10` is a column shape, not a contract shape). |
| FT8 | `unit_code` is a **structural code** rendered by the transport (LO4), sourced from `AttributeDefinition.unit`; it is never localized unit text. |
| FT9 | `EntityChoiceFacet` carries an explicit closed `match: EntityMatch` — `SUBTREE_INCLUSIVE` for category (matching the frozen `category_path_ids @> ARRAY[:id]` ancestry semantics of master `# 22.2`) and `EXACT` for brand. The rejected alternative was two variants that would have differed in no field; the accepted cost is one more enum. |
| FT10 | `AvailabilityFacet` is **not** a seventh variant: availability filtering is a `BooleanFacet` under a reserved structural key with `scope = VARIANT`. No new inventory state machine is introduced (§14). |

```python
class FacetScope(StrEnum):
    PRODUCT = "product"
    VARIANT = "variant"

class EntityMatch(StrEnum):
    EXACT = "exact"
    SUBTREE_INCLUSIVE = "subtree_inclusive"

@dataclass(frozen=True, slots=True, kw_only=True)
class ChoiceFacetOption:
    value_id: FacetValueId       # AttributeChoice.code (immutable, R12)
    label: str                   # already localized
    count: int | None            # §9 — meaning fixed by the facet's count_quality
    is_selected: bool

@dataclass(frozen=True, slots=True, kw_only=True)
class BooleanFacetOption:
    value: bool
    label: str
    count: int | None
    is_selected: bool

@dataclass(frozen=True, slots=True, kw_only=True)
class EntityFacetOption:
    entity_public_id: PublicId   # Category.public_id / Brand.public_id
    label: str
    slug: str                    # crawlable single-facet URLs (master # 10.6)
    count: int | None
    is_selected: bool
```

```python
@dataclass(frozen=True, slots=True, kw_only=True)
class ChoiceFacet:
    key: FacetKey; label: str; scope: FacetScope
    options: tuple[ChoiceFacetOption, ...]
    option_set: FacetOptionSet
    count_quality: CountQuality

@dataclass(frozen=True, slots=True, kw_only=True)
class MoneyRangeFacet:
    key: FacetKey; label: str; scope: FacetScope     # scope is VARIANT (FT4)
    range_min: Money
    range_max: Money
    selected_min: Money | None
    selected_max: Money | None
```

`BooleanFacet` and `EntityChoiceFacet` follow `ChoiceFacet`'s option-bearing shape (plus
`EntityChoiceFacet.match`); `IntegerRangeFacet` and `DecimalRangeFacet` follow `MoneyRangeFacet`'s
bounds shape with `int` / `Decimal` bounds plus `unit_code: str | None`.

---

## 9. Facet counts and count quality

Item 6 F5–F8 is authoritative for **how** a count is produced. This section freezes only how its
**quality** is represented, so that no reader has to infer it from a convention.

```python
class CountQuality(StrEnum):
    EXACT = "exact"                # satisfier-confirmed count of matching products (F6, F6a)
    APPROXIMATE = "approximate"    # deliberately degraded under F7; indicative only
    UNAVAILABLE = "unavailable"    # deliberately not computed under F7

class FacetOptionSet(StrEnum):
    COMPLETE = "complete"          # every eligible option of this facet is present
    TRUNCATED = "truncated"        # the option set was limited (master # 10.2)
```

| # | Rule |
|---|---|
| FQ1 | `count_quality` is carried **per facet**, because degradation is a per-facet/per-filter-set policy decision (master `# 10.4`), and it applies uniformly to every option of that facet. A facet may not silently mix qualities across its options. |
| FQ2 | The cross-field invariant is frozen and validated in `__post_init__`: `count_quality == UNAVAILABLE` **iff** every option's `count is None`. For `EXACT` and `APPROXIMATE`, every option's `count` is a non-negative `int`. |
| FQ3 | **Four states stay distinct, and none of them is `0`:** `UNAVAILABLE` (not computed) ≠ `EXACT, 0` (genuinely zero, which per F6 should normally not be offered at all) ≠ `APPROXIMATE, 0` ("about zero") ≠ absence of the option from the tuple (not applicable in this candidate set). Encoding any two of these the same way is a contract defect (C42, V43). |
| FQ4 | **`EXACT` has a precise meaning:** the same-variant satisfier predicate confirmed the candidate set (item 6 F6a). A count derived from the product-level union without that confirmation may **never** be labelled `EXACT`. For a product-scope facet the union is already exact (item 6 G5) and no confirmation step exists to skip. C43 asserts this on C24's dataset. |
| FQ5 | **Option-set truncation is a different fact from count quality** and has its own field: a facet may be `option_set = TRUNCATED` while its counts are `EXACT`, and it may be `COMPLETE` while its counts are `APPROXIMATE`. Collapsing the two into one flag is forbidden. |
| FQ6 | **A transport never infers quality.** It reads the enum. No convention — "0 means unknown", "missing means degraded", "we only degrade above N" — may be relied on, encoded in a template, or documented as an alternative (V43). |
| FQ7 | The same three-valued model applies to the result total (§11), so the platform has one quality concept rather than two. |
| FQ8 | Which threshold triggers degradation, and which degradation is chosen, remains item 6 F7's UX/serving policy and Phase 4's numbers. Item 7 freezes only that the choice is **reported** in the contract. |
| FQ9 | **What a count counts** is frozen in §12.4: the card set of the current canonical query with that option added to the selection of **its own key**, under §12.2's `OR`. There is no separate disjunctive or self-excluding counting model, and changing this meaning is a breaking semantic change (§16). |

---

## 10. Selection state and ordering

| # | Rule |
|---|---|
| SL1 | Selection is **result state, never projection state**: no request-specific selection is stored in `ProductListingProjection` (item 6 §8, CT5). It lives in the facet/result DTOs and in the canonical query. |
| SL2 | Selection is explicit and complete enough for Web and API to render the same semantic state: `is_selected: bool` on every discrete option, `selected_min`/`selected_max` on every range facet, and the canonical query echo (§11). Neither transport reconstructs selection by re-parsing its own request. |
| SL3 | **`application/storefront` owns canonical ordering**, and tuple order **is** render order for cards, facets, options and badges. A transport must not re-sort (V40). Ordering is deterministic and total — every ordering ends in a stable unique tie-break (facet key, value id, public id) so that two processes and two transports produce identical sequences (C44), exactly as item 6 SO2 requires for rows. |
| SL4 | Card order is the order the compiled sort produced (item 6 SO1–SO4). Item 7 adds no ordering semantics to cards and changes no sort key. |
| SL5 | The **ordering policy** for facets and options — catalog-defined choice order, alphabetical, count-descending, or a configured merchandising order — is a Phase 4 storefront decision bounded by SL3's determinism. Whatever is chosen is one policy shared by Web and API. |
| SL6 | **A selected option is always present** in its facet's option tuple, even when its count is `0`, its quality is `UNAVAILABLE`, or the option set is `TRUNCATED`. Otherwise the UI cannot offer "remove this filter" and the two transports diverge on how to recover (C48). |
| SL7 | A facet whose key is not offered in the current scope is absent from `facets`; a selected term over an absent facet still appears in the canonical query, so the state is recoverable rather than silently dropped. |

---

## 11. Listing result and pagination

### 11.1 The decision

> **The selector returns one materialised `ProductListingResult`. No Django `Paginator`, `Page` or
> `object_list` exists anywhere in the contract (item 4 K1–K3, item 6 RP2, SP2).**

```python
@dataclass(frozen=True, slots=True, kw_only=True)
class ProductListingResult:
    cards: tuple[ProductCard, ...]
    facets: tuple[Facet, ...] | None     # None == facets were not requested (LR3)
    page: PageInfo                       # union of two variants (LR4)
    applied_query: ListingQuery          # the canonical form actually executed (LR7)
```

```python
type PageInfo = KeysetPageInfo | NumberedPageInfo

@dataclass(frozen=True, slots=True, kw_only=True)
class KeysetPageInfo:                    # deep listing paths (PG2)
    page_size: int                       # the effective size after clamping
    has_next: bool
    next_cursor: Cursor | None
    has_previous: bool
    previous_cursor: Cursor | None
    total: ResultTotal | None            # None == a total was not requested

@dataclass(frozen=True, slots=True, kw_only=True)
class NumberedPageInfo:                  # bounded shallow SEO pages (PG3)
    page_size: int
    page_number: int
    has_next: bool
    has_previous: bool
    total: ResultTotal | None
    total_pages: int | None              # present only when an exact total is present

@dataclass(frozen=True, slots=True, kw_only=True)
class ResultTotal:
    quality: CountQuality                # FQ7 — one quality model
    value: int | None                    # None iff quality is UNAVAILABLE

@dataclass(frozen=True, slots=True, kw_only=True)
class Cursor:
    token: str                           # signed, opaque; no payload field is exposed
```

### 11.2 Rules

| # | Rule |
|---|---|
| LR1 | The result is fully materialised: `cards` is a `tuple`, every nested object is frozen, and no SQL runs after the selector returns (R3, C39). |
| LR2 | The result composes cards, facets **where requested**, pagination metadata and the canonical query. It carries no ORM object, no cache handle, no query plan, no timing, no freshness/version field (DC9). |
| LR3 | `facets is None` means **not requested**; `facets == ()` means requested and none applicable. Conflating them is a defect (DC7, C49). |
| LR4 | Pagination metadata is a **union of two variants**, matching item 6's frozen distinction between deep keyset paths (PG2) and bounded shallow page-number pages (PG3) — **without** a second listing query implementation: one selector, one compiler, one result type, two metadata shapes chosen by the request variant (QI5). A single DTO with mutually exclusive optional fields is rejected by DC6. |
| LR5 | **The cursor is an opaque public token.** No DTO exposes a sort value, a tie-break value, an internal bigint, a page offset or any other cursor payload field; `Cursor` has exactly one field, and the codec, its internal field list and its signature scheme remain Phase 4's (PG4, PG8). Item 7 owns only the public metadata shape. A transport passes the token back unmodified and never parses it (A39, C45). |
| LR6 | **An exact total is not mandatory.** The already-frozen master requires no exact count for the listing, and keyset paths do not need one; `has_next` answers the only question the grid must answer. A total is computed only when the caller asks, and its quality is reported like a facet count (FQ7). `total_pages` exists only where an exact total exists — a numbered page set cannot be sized from an approximate number. |
| LR7 | `applied_query` is the **canonical** form of the executed query: unknown parameters dropped or normalized (master `# 10.2`), page size clamped, terms deduplicated and deterministically ordered. It is what makes Web and API produce identical canonical URLs and identical cache keys (master `# 10.5`'s `filters_hash`, `# 10.6`'s canonical policy) and what makes round-trip testable (C41). |
| LR8 | Item 7 decides nothing about item 12: no `source_version`, freshness, generation or projection-version field appears in the result, and pagination introduces no ordering guard of its own (item 6 PU6 — the read path never compensates for staleness). |

---

## 12. Input side — the round-trip contract

Item 7 defines the **semantic input shapes** needed for a returned facet to be applied back to the
same selector. It does **not** redesign the filter compiler's implementation (item 6 §4.1 owns it) —
but the **meaning** of a public multi-value filter term is part of *this* contract, because a
round-trip contract in which the same DTO may mean two different things is not frozen at all. §12.2
therefore closes that question.

### 12.1 The query and its term variants

```python
@dataclass(frozen=True, slots=True, kw_only=True)
class ListingQuery:
    language: StorefrontLanguage
    terms: tuple[FilterTerm, ...]        # at most one term per FacetKey; canonically ordered
    text: str | None                     # bounded free-text query (master # 10.2)
    sort: ListingSort
    page: PageRequest                    # KeysetPageRequest | NumberedPageRequest
    include_facets: bool
    include_total: bool

type FilterTerm = (
    ChoiceFilterTerm | BooleanFilterTerm | IntegerRangeFilterTerm
    | DecimalRangeFilterTerm | MoneyRangeFilterTerm | EntityFilterTerm
)

class ListingSort(StrEnum):              # mirrors the frozen SORTS map (master # 10.2, SO3)
    PRICE_ASC = "price_asc"
    PRICE_DESC = "price_desc"
    NEW = "new"
    POPULAR = "popular"
    RELEVANCE = "relevance"
```

```python
@dataclass(frozen=True, slots=True, kw_only=True)
class ChoiceFilterTerm:
    key: FacetKey
    values: tuple[FacetValueId, ...]     # AttributeChoice.code; OR within the key (QI7)

@dataclass(frozen=True, slots=True, kw_only=True)
class EntityFilterTerm:
    key: FacetKey
    values: tuple[PublicId, ...]         # Category/Brand public_id; OR within the key (QI7)

@dataclass(frozen=True, slots=True, kw_only=True)
class BooleanFilterTerm:
    key: FacetKey
    value: bool                          # closed two-valued domain — no tuple (QI10)

@dataclass(frozen=True, slots=True, kw_only=True)
class IntegerRangeFilterTerm:
    key: FacetKey
    minimum: int | None
    maximum: int | None

@dataclass(frozen=True, slots=True, kw_only=True)
class DecimalRangeFilterTerm:
    key: FacetKey
    minimum: Decimal | None
    maximum: Decimal | None

@dataclass(frozen=True, slots=True, kw_only=True)
class MoneyRangeFilterTerm:
    key: FacetKey
    minimum: Money | None
    maximum: Money | None                # one currency across both bounds (QI10)
```

Note what a term does **not** carry: no `scope`, no `EntityMatch`, no internal token, no operator, no
compiler directive, no raw attribute name (QI11).

### 12.2 Combination semantics — frozen

> **Different facet keys combine with `AND`. Multiple selected values inside one discrete facet key
> combine with `OR`.**

```text
color IN {red, blue}
AND size  IN {M, L}
AND brand IN {A, B}
```

**The `OR` never weakens the same-variant existential of ADR-0008 §3.** For variant-scope keys the
disjunctions are evaluated *inside* the existential, against one sellable variant:

```text
EXISTS one sellable variant V such that
        V.color IN {red, blue}
    AND V.size  IN {M, L}
    AND every other variant-scope predicate holds on that same V
```

So `(red OR blue) AND (M OR L)` is satisfied by a single variant. It is **never**:

```text
some variant is red  AND  another variant is L        ← forbidden (item 6 G3, ADR-0008 §3)
```

Product-scope keys use the identical `OR`-within-key / `AND`-between-keys rule, evaluated at Product
scope, where the union array is already exact (item 6 G5).

Range and boolean terms have no within-key disjunction to define: a range term is one interval, a
boolean term is one value. They join other terms with `AND` like any other key, and a variant-scope
range or boolean term participates in the same existential.

### 12.3 Canonicalization — frozen

The compiler produces exactly one canonical form, shared by Web and API (QI4):

| # | Canonicalization rule |
|---|---|
| 1 | **At most one term per `FacetKey`.** Repeated input terms for the same discrete key are merged into one term by set union. |
| 2 | Duplicate values inside a term are removed. |
| 3 | Value tuples are ordered deterministically (by their public identity), so two spellings of one selection produce one canonical query, one canonical URL and one cache key (LR7). |
| 4 | An empty discrete selection canonicalizes to **no term**, not to a term with an empty tuple. |
| 5 | A boolean term selecting both values canonicalizes to **no term** — it constrains nothing. |
| 6 | Repeated range terms for one key are merged into the **tightest interval they jointly express** (their intersection). |
| 7 | A range term with **neither bound** canonicalizes to no term — it constrains nothing. |
| 8 | Unknown, non-filterable or ill-formed keys and values are dropped or normalized away (QI3) and their absence is visible in `applied_query`. |
| 9 | Terms are ordered deterministically by key. |

#### The safety invariant that governs removal

> **Canonicalization may remove a term only when that term is semantically *non-constraining*. It must
> never remove a recognized contradiction, because removing it broadens the result set.**

Rules 4, 5 and 7 are the complete list of removals, and each is a genuine tautology: an empty discrete
selection, a boolean term selecting both values, and a range with neither bound all constrain nothing,
so dropping them changes no result.

A **contradiction is the opposite case** and is handled the opposite way:

| Input on one recognized key | Canonical outcome |
|---|---|
| `minimum > maximum` on a single range term | **Rejected as invalid query input** |
| repeated range terms whose intersection is empty — e.g. `price = 0..100` **and** `price = 200..300` | **Rejected as invalid query input** |

Because item 7 deliberately has **no** `MatchNoneFilterTerm` and adds none (DC5's union is closed,
FT1/§16), a contradictory recognized range has no representable canonical form. The frozen MVP rule is
therefore that it is **rejected before selector execution**. Explicitly forbidden: silently swapping
the bounds, silently dropping the constraint, dropping the key, widening either bound, or returning an
unconstrained result. `price = 0..100 AND price = 200..300` must never become "no price filter" — that
answer is not a degraded version of the question, it is a different and much larger one.

The transport representation of that validation failure (status code, error body, form message) is
transport work, as every transport mapping in this contract is (DC2).

### 12.4 What an exact facet count means under `OR`

> **A discrete option's count is the size of the card set produced by taking the current canonical
> query and adding that option to the selection of its own key, under the `OR` semantics of §12.2,
> with every other term unchanged.**

```text
current:  color = {red}
count shown for blue  =  result count for  color = {red, blue}   (all other terms unchanged)
```

For an option that is already selected, adding it is idempotent, so its `EXACT` count equals the
current result count.

This keeps item 6 F6/C36 intact: the count predicate **is** the grid predicate, a variant-scope
`EXACT` count still requires the satisfier confirmation of F6a, and `APPROXIMATE`/`UNAVAILABLE`
behaviour is unchanged. **No separate "disjunctive" or "self-excluding" facet-count model is
introduced.** If the product later wants a different counting UX, that is a deliberate breaking
semantic change (§16), not an implementation detail.

### 12.5 Rules

| # | Rule |
|---|---|
| QI1 | The query is a **typed frozen DTO**. No raw request dictionary, no `**kwargs`, no dynamic field name, no attribute name taken from user input ever reaches the selector (master `# 10.2`, item 6 S4/SEC6/A33, A38). |
| QI2 | Filter terms mirror the facet variants one-to-one, so a returned option maps to exactly one term type with exactly one identity type (FK6). There is no untyped `value` field and no term that could carry two kinds of identity. |
| QI3 | The contract stays **whitelist-driven**: a well-formed `FacetKey` is not a filterable facet until the compiler's whitelist says so; unknown or non-filterable keys are rejected or normalized away, and the outcome is visible in `applied_query` (DC11, LR7). |
| QI4 | **Web and API map their transports into the same `ListingQuery`.** Neither has its own query type, its own defaults or its own clamping (R6, C37). Query-string spelling, JSON body shape and DRF/form parsing stay at the edge. |
| QI5 | `PageRequest` is the union `KeysetPageRequest(page_size, cursor: Cursor \| None)` / `NumberedPageRequest(page_size, page_number)`; the request variant selects the `PageInfo` variant of the result (LR4). Page-size limits and the numbered-mode depth bound remain Phase 4's (PG3, PG8). |
| QI6 | **Round-trip invariant:** for every option a facet returns, constructing the corresponding term from that option's identity and re-running the selector yields a query whose canonical form contains that selection, with the option then `is_selected = True` — and, when the facet's quality is `EXACT`, a card set whose size equals that option's count under §12.4 (C41, tying to item 6 C36). |
| QI7 | **Combination semantics are frozen (§12.2):** `AND` between different facet keys, `OR` between values of one discrete key, with every variant-scope disjunction evaluated **inside** the single-variant existential. Master `# 7.2`'s `facet_choice_ids @> ARRAY[:choice_ids]` is an illustration of the array containment *mechanism* for a set of distinct-attribute selections; it states no multi-select-within-one-facet UX semantics and is not contradicted by this rule. Which physical predicate realises `OR` within a key (`&&`, a per-key containment group, or a satisfier-side disjunction) is Phase 4's, bounded by item 6 G3/G4/G7. |
| QI8 | The category-page context enters as an ordinary `EntityFilterTerm` over the reserved category key with `SUBTREE_INCLUSIVE` semantics (FT9); no separate "scope" concept is introduced. **Slug → `PublicId` route resolution is out of scope** of this contract and belongs to whoever owns category-page routing (§20). |
| QI9 | `ListingQuery` is also the echo type (LR7), so the canonical form a caller receives is constructible input — there is exactly one query vocabulary, not an input one and an output one. |
| QI10 | **Term field invariants**, validated in `__post_init__` (DC4): a `ChoiceFilterTerm`/`EntityFilterTerm` `values` tuple is non-empty, unique and canonically ordered after canonicalization; a range term carries **at least one** bound; when both bounds are present `minimum <= maximum`; a `MoneyRangeFilterTerm`'s bounds share one currency; a `BooleanFilterTerm` carries exactly one `bool`. |
| QI10a | **How a violation is resolved depends on whether it is a tautology or a contradiction**, and the two are never treated alike (§12.3's safety invariant). A **non-constraining** input — an empty discrete selection, a both-values boolean, a range with neither bound — canonicalizes to **no term**. A **contradictory recognized range** — `minimum > maximum`, or repeated range terms for one key whose intersection is empty — is **rejected as invalid query input before the selector runs**. It is never bound-swapped, never dropped, never allowed to widen the result set, and it does not motivate a `MatchNoneFilterTerm` (C54, V51). |
| QI11 | **Facet semantics are never caller-controlled.** No term carries `scope`, `EntityMatch`, an operator, a compiler directive or an internal token. Scope (FT2) and match semantics (FT9) come from the whitelist definition behind the `FacetKey`. A caller can therefore not turn the category facet from `SUBTREE_INCLUSIVE` into `EXACT`, nor turn a product-scope facet into a variant-scope one, by any input value (A41, C53). |
| QI12 | **Canonicalization is one shared function**, not two transport conventions: Web and API produce byte-identical canonical queries for equivalent input, which is what makes canonical URLs, `filters_hash` cache keys and parity tests meaningful (§12.3, C51). |
| QI13 | Bounds on the number of terms, the number of values per term and the length of `text` remain master `# 10.2`'s serving limits with Phase 4's numbers; canonicalization applies them before SQL (item 6 SEC6). |

---

## 13. Localization

| # | Rule |
|---|---|
| LO1 | **One projection row is one language** (item 6 I7), so a result carries **one** language. `ProductCard` never contains both an RO and an RU copy of anything, however the OLTP row stores them (ADR-0003 §4). |
| LO2 | **Domain content is already localized in the DTO**: product name, slug, brand name and slug, image alt, facet labels, facet option labels. These originate in catalog/brand data and are resolved by the storefront for the requested language. They are not codes and the transport does not translate them. |
| LO3 | The alternative — sending codes and letting the transport localize catalog content — is rejected because it would force `interfaces/*` to read catalog per request, which is a second read path (item 6 RP3, A32) and a per-facet lookup (R13). |
| LO4 | **Interface-owned vocabulary stays a structural code**, localized at the Web/API edge from a translation catalog: badge codes (R11), `unit_code`, and every public enum value (`AvailabilityState`, `ListingSort`, `CountQuality`, `FacetOptionSet`, `FacetScope`, `EntityMatch`, `PriceBasis`). Enum values are contract tokens, never UI text (item 4 N4). |
| LO5 | The requested language enters as `StorefrontLanguage` — a closed enum **owned by `application/storefront`**. This is not a claim of platform-wide ownership: a shared language primitive in `core` would extend a `core` allowlist and is an ADR-requiring decision (§1.3). If one is later adopted, replacing `StorefrontLanguage` is a breaking contract change migrated in one commit (item 4 §17.3). |
| LO6 | Number, date, currency and rating formatting is transport work: `average_x10` stays an integer, `Money` stays minor units + currency, `discount_percent_bps` stays basis points (DC8, master `# 14.1`). |

---

## 14. Availability and rating

| # | Rule |
|---|---|
| AV1 | `AvailabilityState` has exactly two members, `IN_STOCK` and `OUT_OF_STOCK`, mirroring the projection's frozen display boolean (master `# 7.6`'s `in_stock`). It is an enum rather than a `bool` so a transport cannot invent semantics from truthiness, and so the type is nameable in tests. |
| AV2 | It is **not** an inventory state machine, **not** a reservation state, and it exposes **no quantity**, no per-store list, no threshold, no "low stock" band and no lead time. Item 7 invents no inventory semantics (item 6 §9.2, R14). |
| AV3 | Availability on the card is **display state**. It is never a promise of sellability: `inventory.public`'s atomic reservation is the authoritative gate at placement (item 6 §23 row 10, item 5 FG4). |
| AV4 | `rating` is `CardRating \| None`. `None` means **no approved reviews**; it is never represented as `average_x10 = 0`, which would render as a zero-star product. This is the same distinction FQ3 makes for counts. |
| AV5 | `average_x10: int` is the frozen platform representation (master `# 14.1`); `4.7` is produced by the presentation layer only. `count` counts approved reviews only. |
| AV6 | No review state machine, moderation state, histogram, author or review text appears on the card. The rating histogram of `ProductRatingProjection` is detail-page data, not listing data. |

---

## 15. Security and privacy of the DTO graph

| # | Rule |
|---|---|
| SE1 | The graph is **public data only** and identical for anonymous and authenticated callers (R5, item 6 SEC1, C34 → C46). Because there is nothing personalized in it, the anonymous fragment cache and the CDN have no leak class (item 6 CA5). |
| SE2 | No secret, token, internal identifier, ERP/provider identifier, cost, margin, supplier, consent, session, cart or order value appears anywhere in the graph (DC9, item 6 SEC2, SEC8). |
| SE3 | The only outward path for an internal bigint remains the **signed opaque cursor** (R4, LR5), and it is not readable from the DTO. |
| SE4 | No storefront DTO is an authorization input. Object-level authorization reads authoritative state through actor-scoped selectors, never a derived read model (item 6 SEC3, T9). |
| SE5 | Query input discipline is inherited unchanged: bounded `text`, bounded facet and value counts, whitelist compilation, bind parameters, query-cost guard before SQL (item 6 SEC6, master `# 10.2`). Item 7 adds the type-level half of it (QI1). |

---

## 16. Contract evolution

Item 4 §17's three classes apply unchanged. Their concrete reading for this contract:

| Change | Class | Note |
|---|---|---|
| New selector; new facet **option**; new badge **code**; new field on `ProductCard` or a nested display DTO that a caller may ignore | **Additive** | Contract review + tests; no ADR. BD3/BD4 make new badge codes safe by construction. |
| New **required** field on any DTO | **Breaking** | item 4 §17.2's named exception. |
| New member of `ListingSort`, `CountQuality`, `FacetOptionSet`, `AvailabilityState`, `FacetScope`, `EntityMatch`, `PriceBasis` | **Breaking** | Public enums are matched exhaustively (item 4 N5). |
| New **facet variant** or new `FilterTerm` variant | **Breaking** | The unions are matched exhaustively (FT1, DC5). |
| Changing an existing facet's **kind** (e.g. choice → range) for the same key | **Breaking** | Existing URLs and stored filters change meaning. |
| Changing a facet **identifier semantics** (choice `code` → `PublicId`, or the `FacetKey` spelling of FK5) | **Breaking** | Indexed URLs, canonical URLs and cache keys all change. |
| Changing what `EXACT` / `APPROXIMATE` / `UNAVAILABLE` mean, or which one a situation produces | **Breaking** | Consumers branch on it; FQ4 ties `EXACT` to a specific predicate. |
| Range bounds moving from scope-level to candidate-refined (FT5) | **Breaking** | Silent semantic change of an existing field. |
| Changing the `AND`/`OR` combination semantics of §12.2, or the canonicalization of §12.3 | **Breaking** | Every indexed URL, cache key and stored filter changes meaning, and facet counts change with them. |
| Changing what a discrete facet count counts (§12.4) — e.g. adopting a self-excluding/disjunctive model | **Breaking** | Consumers and F6/C36 are written against the add-option definition (FQ9). |
| Weakening the `CardPrice` comparison-pair coherence of CD12 | **Forbidden here** | It would let the card state a discount no purchasable offer supports. |
| Adding `PriceBasis.FILTER_MATCHED_VARIANT` | **Breaking + gated** | Requires item 6 SO3d's joint display/sort/cursor decision first (CD9, V45). |
| Adding a personalized/private field | **Forbidden here** | A separate artifact with its own ownership, security review and ADR (item 6 SEC4). |

| # | Rule |
|---|---|
| EV1 | **Optional fields are not a staging area.** A field is added when a rendered surface needs it, not because it might be useful (V44). Every `\| None` in this contract has a stated meaning (DC7). |
| EV2 | A breaking change migrates all callers in the same commit — the monolith makes them enumerable (item 4 §17.3). There is no deprecation window and no versioned duplicate DTO. |
| EV3 | An ADR is required only when a breaking change also moves a frozen architectural decision; §1.3's five cases are the ones to expect. |

---

## 17. Illustrative assembly (non-production)

Deliberately partial; it shows *shape*, not content to be copied in Phase 1.

```python
# application/storefront/public.py   (NOT created in Phase 0; item 4 §4.1 façade rules apply)
__all__ = (
    # value objects
    "FacetKey", "FacetValueId", "Cursor",
    # enums
    "PriceBasis", "AvailabilityState", "FacetScope", "EntityMatch",
    "CountQuality", "FacetOptionSet", "ListingSort", "StorefrontLanguage",
    # card
    "ProductCard", "CardBrand", "CardImage", "CardPrice", "CardRating", "Badge",
    # facets
    "Facet", "ChoiceFacet", "BooleanFacet", "IntegerRangeFacet", "DecimalRangeFacet",
    "MoneyRangeFacet", "EntityChoiceFacet",
    "ChoiceFacetOption", "BooleanFacetOption", "EntityFacetOption",
    # query + result
    "ListingQuery", "FilterTerm", "ChoiceFilterTerm", "BooleanFilterTerm",
    "IntegerRangeFilterTerm", "DecimalRangeFilterTerm", "MoneyRangeFilterTerm",
    "EntityFilterTerm", "PageRequest", "KeysetPageRequest", "NumberedPageRequest",
    "ProductListingResult", "PageInfo", "KeysetPageInfo", "NumberedPageInfo", "ResultTotal",
    # selector
    "list_products",
)
```

```python
# application/storefront/selectors/listing.py
def list_products(*, query: ListingQuery) -> ProductListingResult: ...
    # public state → no actor (R5, item 6 SP4)
    # materialised, bounded, shaped read over the projection (item 6 RP5, A35)
```

Note what is absent: no `Paginator`, no `QuerySet`, no `Product`/`ProductVariant` model, no
serializer, no request, no cache client, no `Any`, no `id`.

---

## 18. Checks a later phase must implement

These **extend** item 3 §15, item 4 §19, item 5 §22 and item 6 §25; all remain authoritative and
unchanged. No new `L` rule and no `core` allowlist entry: this contract adds no import edge — it uses
`core` value types (`Money`, `PublicId`) that `application/*` may already import, and every other
symbol is `application/storefront`-internal. Nothing here is implemented in Phase 0.

### 18.1 Static / AST (continuing the `A` series)

| # | Rule |
|---|---|
| A36 | No storefront public DTO declares an `int`-typed identifier field, a field named `id`/`pk`/`*_pk`, or a field whose name matches a known internal-identifier shape (`product_id`, `choice_id`, `category_id`, `brand_id`, `variant_id`). Identity fields are `PublicId`, `FacetKey`, `FacetValueId` or `bool` (FK2, FK6; extends A16). |
| A37 | Every class exported from `application/storefront/public.py` that is not an enum or a value object is `@dataclass(frozen=True, slots=True, kw_only=True)`; no field is annotated `Any`, `list`, `dict`, `set`, `Mapping`, `MutableMapping`, `Sequence`, `Iterable`, `Collection`, or `float`-as-money (extends A17/A31 to this module). |
| A38 | No public storefront signature accepts a bare `str`/`dict`/`int` where a facet key, facet value identity or cursor is meant, and none declares `**kwargs` or an unannotated parameter (QI1, FK7; extends A18). |
| A39 | No public storefront DTO declares a cursor payload field (sort value, tie-break value, offset, internal id); `Cursor` declares exactly one opaque token field (LR5). |
| A40 | No public storefront DTO declares a presentation field: CSS class, colour, icon, style, URL, HTML fragment, template name, HTTP status, or a localized-text field for something declared a structural code (DC2, BD1, LO4). |
| A41 | No `FilterTerm` variant declares a `scope`, `EntityMatch`, operator, compiler-directive or internal-token field, and no public storefront input type lets a caller supply facet semantics (QI11, FT2, FT9). |

### 18.2 Behavioural / contract tests (continuing the `C` series)

| # | Rule |
|---|---|
| C37 | **Web/API semantic parity over the DTO graph:** for the same `ListingQuery`, both transports render from the identical result object — same cards in the same order, same public identifiers, same price basis/amount/discount, same availability, same rating, same badges in the same order, same facets/options/selection/count qualities, same canonical query (extends C32 from endpoint to DTO). |
| C38 | **No internal bigint leakage:** a recursive walk of the result graph finds no `int` field used as an identifier, and no rendered Web or API payload contains a projection row id, product id, choice id, category id or brand id (R4, FK2). |
| C39 | **Immutable, materialised graph:** mutating any node raises; every collection is a `tuple`/`frozenset`; a query-count assertion shows no SQL issued after the selector returns, including during template rendering and serialization (R3, item 6 QB6). |
| C40 | **No ORM or lazy object in any nested DTO:** a recursive type/instance walk finds no model instance, QuerySet, manager, deferred instance, `SimpleLazyObject`, generator or paginator anywhere in the graph (R1, DC3). |
| C41 | **Facet option round-trip and exact-count agreement:** for every returned option of every facet kind, adding it to the selection of **its own key** under §12.2's `OR` and re-running the selector produces a canonical query containing that selection, the option comes back `is_selected = True`, and when the facet's quality is `EXACT` the returned card count equals that option's count. For an already-selected option, adding it changes neither the canonical query nor the card count (QI6, §12.4). |
| C42 | **Count-quality distinction:** with degradation forced on, counts are `APPROXIMATE`/`UNAVAILABLE` and never presented as exact; an `UNAVAILABLE` count is `None`, never `0`; an `APPROXIMATE, 0` is distinguishable from `UNAVAILABLE` and from an absent option; a `TRUNCATED` option set is distinguishable from degraded counts (FQ2, FQ3, FQ5). |
| C43 | **Same-variant count semantics:** on item 6 C24's dataset, every `EXACT` count on a `VARIANT`-scope facet equals the number of products the grid returns for that refined filter; a union-derived count that skipped the satisfier confirmation is never labelled `EXACT` (FQ4, item 6 F6a, C36). |
| C44 | **Deterministic ordering:** identical queries executed twice, in two processes, and through both transports return identical card, facet, option and badge sequences, including datasets engineered so many entries share a primary ordering value (SL3). |
| C45 | **Cursor opacity:** the token exposes no sort value and no internal id under inspection; a tampered or foreign token is rejected rather than silently reinterpreted; no consumer outside `application/storefront` parses it (LR5). |
| C46 | **No customer or private data:** the result graph is identical for an anonymous caller and for an authenticated one, and contains no customer-scoped field (SE1; extends item 6 C34 to the DTO). |
| C47 | **Price DTO does not decide the deferred policy:** `PriceBasis` has exactly one member; under an active variant-scope filter the card reports `PRODUCT_WIDE` and the amount equals the product-wide baseline that price sorting and the cursor use. The test fails if a second member appears without the item 6 SO3d joint decision being recorded (CD8–CD10, V45). |
| C48 | **Selected options survive:** a selected option whose count is `0`, whose quality is `UNAVAILABLE`, or which falls outside a `TRUNCATED` option set is still present with `is_selected = True` (SL6). |
| C49 | **Omission is not emptiness:** `facets is None` exactly when facets were not requested and `()` when requested with none applicable; `total is None` exactly when no total was requested, `UNAVAILABLE` when requested but not computed (LR3, LR6, DC7). |
| C50 | **Combination semantics (§12.2):** (a) two values of one `ChoiceFacet` return the union of what each returns alone — `OR` within the key; (b) two different facet keys return the intersection — `AND` between keys; (c) on item 6 C24's dataset, `color IN {red, blue} AND size IN {M, L}` returns only products having **one sellable variant** satisfying both disjunctions, and a product whose only red variant is `M` and whose only `L` variant is blue is **absent**; (d) `EntityFilterTerm` multi-select behaves as `OR` for brand and as `OR` over subtrees for category. |
| C51 | **Canonicalization is one shared function (§12.3):** repeated same-key terms, duplicate values and differing value orders collapse to one identical canonical query; an empty discrete selection, a both-values boolean and a boundless range term produce **no** term; repeated range terms for one key are merged into their intersection when it is non-empty; and Web and API produce byte-identical canonical queries — hence identical canonical URLs and `filters_hash` cache keys — for equivalent input (QI12). |
| C52 | **Coherent price comparison pair:** with at least two sellable variants whose current and regular prices differ (A `100/120`, B `110/200`), the card never pairs `amount` from one observation with `regular_amount` from another — `amount = 100` admits `regular_amount = 120` and never `200`; currencies agree; `regular_amount > amount`; and where no coherent pair exists **both** `regular_amount` and `discount_percent_bps` are `None` (CD12–CD12c). |
| C53 | **Facet semantics are not caller-controlled:** no `ListingQuery` input changes a facet's `scope`, changes the category facet's `SUBTREE_INCLUSIVE` match to `EXACT`, or makes a product-scope facet evaluate at variant scope; attribute-facet scope tracks the catalog metadata and structural-facet scope is fixed by FT2 (QI11, A41). |
| C54 | **A contradiction is never canonicalized into "no filter":** `price = 0..100` together with `price = 200..300` on one key is **rejected as invalid query input**, and the resulting query is never one in which that key is simply absent, nor one with widened or swapped bounds; a direct `minimum > maximum` term is rejected the same way. Asserted for integer, decimal and money range terms, and paired with the positive case — a non-empty intersection is merged and applied (§12.3, QI10a). |

### 18.3 Review-only (continuing the `V` series)

| # | Rule |
|---|---|
| V39 | A generic facet DTO, an untyped `value` field, or a facet DTO that exposes the product-level union / per-variant token structure and thereby invites a transport to compute matching itself (DC5, DC6, FT3). |
| V40 | A transport re-sorting cards, facets, options or badges, or re-deriving a value the application already computed (discount, rating formatting, selection state) so the two transports drift (SL3, CD13). |
| V41 | A presentation concept arriving as a "data" field — badge colour, CSS class, icon name, image URL, sort label text (DC2, BD1, CD5). |
| V42 | An internal bigint appearing as a facet identifier, a card identifier or a URL parameter "because the projection already has it" (FK2). |
| V43 | Count quality inferred from a convention — `0`, `None`, a threshold constant, or a template `if` — instead of read from the enum (FQ6). |
| V44 | An optional field added for a speculative future feature, or a `\| None` whose meaning is not stated (EV1, DC7). |
| V45 | A card price change that implies a different sort key or cursor without item 6 SO3d's joint decision (extends V38 to the DTO). |
| V46 | A heavy payload migrating onto the card — gallery, specification JSON, long description, per-store availability lists, variant matrices (DC9, item 6 CT4). |
| V47 | A second DTO shape appearing for one transport — a "mobile card", an "API-only facet", a serializer-shaped variant (DC2, item 6 RP3). |
| V48 | A within-key `OR` compiled so that different variants satisfy different disjuncts — the same-variant existential silently weakened by multi-select (§12.2, item 6 G3, V31). |
| V49 | A second canonicalization appearing at a transport ("the API sorts values differently", "the Web layer merges duplicates itself"), splitting canonical URLs or cache keys (QI12). |
| V50 | A `regular_amount` or discount assembled from a different variant than the displayed `amount`, or a "best-looking" regular price aggregated independently (CD12, CD12a). |
| V51 | A contradictory filter "helpfully" repaired — bounds swapped, the constraint dropped, the key removed or a bound widened — so an impossible query silently returns a broader result set instead of being rejected (§12.3, QI10a). |

---

## 19. Acceptance checklist

- [ ] Every symbol is `application/storefront`-owned and reaches the outside only through
      `application/storefront/public.py`; nothing is created in Phase 0 (DC1, §17).
- [ ] Item 4's DTO rules hold everywhere: `frozen/slots/kw_only`, immutable field types, tuples not
      mutable collections, no `Any`/`Mapping`/`Sequence`, no ORM/QuerySet/paginator/cache/transport/
      vendor type, no field named `id`/`pk` (R2, DC3, A37).
- [ ] The card is Product-grained, addressed by `Product.public_id`, and leaks no ORM identity, ERP
      identifier, cost/margin, customer state, gallery/spec/long description, `source_version`, or
      cache/search type (CD1, CD2, DC9).
- [ ] Media representation is vendor-neutral: a storage-relative reference, never a bucket, backend
      object or signed provider URL (CD5).
- [ ] Badges carry structural codes only; localization happens at the transport edge; unknown codes
      are skipped (BD1–BD4).
- [ ] The card price states its **basis**, the only legal basis is the product-wide baseline, and the
      deferred filtered-price policy is neither taken nor foreclosed; no matched-variant aggregation,
      projection column or satisfier encoding is invented; sort and cursor semantics are untouched
      (CD8–CD10, C47).
- [ ] `amount`, `regular_amount` and `discount_percent_bps` form **one coherent comparison pair** from
      one pricing observation, currencies agree, `regular_amount > amount`, both comparison fields are
      absent when no coherent pair exists, and no representative SKU identity is exposed
      (CD12–CD12d, C52).
- [ ] Facet keys and values are publicly safe by construction — immutable catalog `code` for
      attributes/choices, `PublicId` for category/brand, `bool` for boolean, bounds for ranges — and no
      internal bigint is an identifier anywhere (FK2, FK6, A36, C38).
- [ ] The two facet-key vocabularies are disjoint by construction, and only that requirement — not a
      cosmetic wire encoding — is frozen (FK4, FK5).
- [ ] Facet kinds with genuinely different value semantics are separate frozen variants; there is no
      `value: Any` and no bag-of-fields facet (§8, DC5, DC6).
- [ ] Attribute-facet `scope` is copied from catalog metadata and structural-facet `scope` is fixed by
      this contract from frozen business semantics; neither is guessed, inferred by a transport or
      overridable by a request, and no scope primitive enters `core` (FT2).
- [ ] The contract describes facets without exposing or encouraging the product-level union as the
      truth for a variant-scope filter (FT3, R7).
- [ ] Exact, approximate and unavailable counts are distinct from each other, from `0`, from
      "approximately 0" and from an absent option; option-set truncation is a separate field; `EXACT`
      means satisfier-confirmed (FQ2–FQ5, C42, C43).
- [ ] Selection state is result state, is explicit for both transports, and a selected option always
      survives in its facet (SL1, SL2, SL6, C48).
- [ ] Canonical ordering is application-owned, deterministic and total; tuple order is render order
      (SL3, C44).
- [ ] The listing result is a materialised DTO — no `Paginator`, no `Page` — composing cards, optional
      facets, pagination metadata and the canonical query (LR1–LR3).
- [ ] Keyset and bounded numbered pagination are two metadata variants of **one** listing
      implementation; the cursor is opaque and exposes no payload field; no exact total is mandatory
      (LR4–LR6, C45).
- [ ] Every `FilterTerm` variant has a frozen field shape and validated invariants: non-empty
      canonical value tuples, at least one range bound, `minimum <= maximum`, one currency on money
      bounds (§12.1, QI10).
- [ ] Combination semantics are explicit — `AND` between facet keys, `OR` between values of one
      discrete key — and the `OR` is evaluated **inside** the single-variant existential, so
      `(red OR blue) AND (M OR L)` still requires one satisfying sellable variant (§12.2, QI7, C50).
- [ ] Exactly one canonical term exists per `FacetKey`, canonicalization is one shared function, and
      Web and API produce identical canonical queries, URLs and cache keys (§12.3, QI12, C51).
- [ ] Canonicalization removes a term only when it is semantically non-constraining; a contradictory
      recognized range (`minimum > maximum`, or repeated ranges with an empty intersection) is
      **rejected as invalid input**, never swapped, dropped, widened or turned into "no filter", and
      no `MatchNoneFilterTerm` is invented (§12.3, QI10a, C54, V51).
- [ ] An exact facet count is defined as the result of adding that option to the selection of its own
      key under the same semantics the grid uses; no separate disjunctive counting model exists
      (§12.4, FQ9, C41).
- [ ] Facet semantics are never caller-controlled: no term carries `scope`, `EntityMatch`, an operator
      or an internal token (QI11, A41, C53).
- [ ] The input contract is typed and whitelist-driven; no raw request mapping or dynamic field name
      reaches the selector; Web and API map into the same query (QI1–QI4).
- [ ] One language per result; domain content is already localized, interface vocabulary stays a
      structural code; no RO/RU pair on a card (LO1–LO4).
- [ ] Availability and rating are display state with no new inventory or review state machine, and
      "no rating" is `None`, never `0` (AV1–AV5).
- [ ] The graph is public-data-only and identical for anonymous and authenticated callers (SE1, C46).
- [ ] Additive vs breaking changes are classified, enum/union additions are treated as breaking, and
      optional fields are not a dumping ground (§16, EV1).
- [ ] No item 8, 9, 10, 11, 12 or 13 decision is consumed; the manual merchandising boost remains
      ownerless and disabled (§20).
- [ ] No ADR is required, and the five would-be ADR triggers are named and avoided (§1.3).

---

## 20. Explicitly deferred decisions

| Deferred | Owner |
|---|---|
| `Money` / `PublicId` implementation — referenced here as already-frozen semantic types only | Phase 0 item 11 |
| Whether an active variant-scope filter changes the effective price, for card display, price sort key and cursor **together** | the joint storefront contract decision before Phase 4 (item 6 SO3b–SO3d); `PriceBasis` gains a member only then |
| The physical projection schema, columns, indexes and Django model | Phase 4 |
| The facet-vocabulary/label serving structure that satisfies FK8 without per-facet request queries | Phase 4, bounded by item 6 F3/QB3 |
| Which **physical predicate** realises `OR` within one key (`&&`, per-key containment groups, satisfier-side disjunction) — the *semantics* are frozen by §12.2 | Phase 4, bounded by item 6 G3/G4/G7 and the query budget |
| The **physical projection support** that yields `CardPrice`'s coherent comparison pair (a paired regular price on the representative observation, or an equivalent) — the *semantics* are frozen by CD12 | Phase 4 |
| Cursor codec, its internal field list, signing scheme and page-size / numbered-depth limits — item 7 owns only the public opacity and metadata shape | Phase 4 (item 6 PG8) |
| **The concrete `FacetKey` spelling and namespace separator** — externally immutable once shipped (FK5) | Phase 4 |
| **Slug → `PublicId` route resolution** for category/brand pages (QI8) | the phase owning category-page routing |
| **Per-store availability faceting** — blocked on a public locator for `Store` (FK9) | the phase owning `Store`'s public contract |
| **Parametrized badges** (e.g. master `# 18.2`'s eUpgrade amount) — additive, needs a vocabulary owner and a value source | the phase owning that programme; out of MVP |
| Facet/option ordering **policy** (catalog order, alphabetical, count-desc, merchandised) within SL3's determinism | Phase 4 |
| A platform-wide language primitive in `core` replacing `StorefrontLanguage` (LO5) | a deliberate decision **requiring an ADR** |
| Candidate-refined range bounds instead of scope-level bounds (FT5) | a later breaking change, reviewed as such |
| `source_version` and the guarded upsert | Phase 0 item 12 |
| Event names, payload schemas, versions, registry | Phase 0 item 8 |
| Queue / failure-domain matrix and DLQ policy | Phase 0 item 9 |
| Trace propagation fields | Phase 0 item 10 |
| Popularity beyond master `# 10.7`'s MVP signals | Phase 0 item 13 |
| The authoritative owner of the **manual merchandising boost**; it stays **disabled** meanwhile and is never stored in the projection | a later decision respecting the frozen dependency graph (item 6 SO6a, SO6b) |
| The exact Web HTML/HTMX markup and the DRF serializer/JSON representation of this graph | Phase 4 / the transport phases |
| A personalized or private storefront read model and its DTOs | a separate artifact + a new ADR (item 6 SEC4) |
| The AST/contract-test implementations for A36–A41, C37–C54 and the review checks V39–V51 | Phase 1+ |
| Any weakening of §4–§16 — an untyped facet value, an internal bigint identifier, a transport-specific DTO, a personalized field, a card price that decides the deferred policy | requires a new ADR |

---

## 21. Self-review record

| # | Check | Result |
|---|---|---|
| 1 | Item 7 instantiates frozen architecture rather than deciding new architecture | Pass — §1.3 maps every decision to the artifact that already froze it, shows the delegation is explicit in both ADR-0008 ("out of scope … item 7") and item 6 §27, and names the five would-be ADR triggers that are deliberately not pulled. |
| 2 | Item 4's DTO rules are preserved, not restated loosely | Pass — R2/DC3 carry `frozen/slots/kw_only`, immutability-by-field-type, tuple/frozenset, no `Any`/`Mapping`/`Sequence`, no ORM/QuerySet/paginator/cache/transport/vendor type, no `id`/`pk`; A37 checks the annotations, C39/C40 check the behaviour and the nested graph. |
| 3 | The card is Product-grained and exposes only the public locator | Pass — CD1 forbids SKU identity and per-variant breakdown; CD2 makes `product_public_id` the only product identity; A36 checks the shape, C38 checks the rendered payloads. |
| 4 | Nothing forbidden leaks onto the card | Pass — DC9 enumerates ORM identity, ERP/provider ids, cost/margin, customer/private state, gallery/spec/long description, `source_version` and cache/search types; CD5/CD6 cover media; V46 is the review check. |
| 5 | Media stays vendor-neutral | Pass — CD5 freezes a storage-relative reference and names the four things it is not (absolute URL, signed provider URL, bucket/key, backend object); the transport derives `srcset`/CDN URLs per master `# 7.3`. |
| 6 | Badges carry structure, not presentation | Pass — BD1 lists the excluded presentation concepts, BD2 justifies `str` over an enum with item 4 N5's exhaustive-match cost, BD3/BD4 make the vocabulary safely additive, BD6 defers parametrization instead of inventing a template system. |
| 7 | ADR-0008's price rule is obeyed exactly | Pass — CD8 makes the basis explicit with one legal member; CD9 makes any second member breaking **and** gated on the SO3d joint decision; CD10 refuses matched-variant aggregation, a projection column, a satisfier encoding and any sort/cursor change; C47 tests it; V45 extends V38 to the DTO. FT4 states the display/filter tension openly instead of hiding it. |
| 7a | The card cannot state a discount no offer supports | Pass — CD12 requires `amount` and `regular_amount` to come from **one** pricing observation; CD12a works the `100/120` vs `110/200` case and names `regular_amount = 200` as forbidden; CD12b makes "both fields absent" the only fallback, so an incoherent pair has no legal encoding; CD12c fixes the currency, ordering and presence invariants; CD12d keeps the representative SKU identity off the card; CD13 keeps the percentage derived from that exact pair and computed once; C52 tests it and V50 is the review check. The product-wide baseline, the filtered-price deferral, sort/cursor semantics and the projection schema are all untouched — only the physical support is Phase 4's (§20). |
| 8 | Facet identifiers are publicly safe and round-trip | Pass — FK2 bans internal bigints outright; FK6 keeps `AttributeChoice.code` and `PublicId` as distinct typed identities per ERD §3.4/D-11 and R12; QI2 mirrors them one-to-one in the terms; QI6/C41 assert the round trip for every kind. |
| 9 | No wire encoding is frozen for cosmetic uniformity | Pass — FK4 gives the one real architectural reason (two vocabularies sharing one URL namespace, where a future catalog `code` could silently reinterpret an indexed URL) and FK5 leaves the spelling to Phase 4; FK6 explicitly refuses to flatten `PublicId` into a string token. |
| 10 | Facet kinds are genuinely differentiated, with no `Any` | Pass — six variants in a closed union (§8.1), DC5/DC6 forbid the polymorphic field and the optional-field bag, FT7 separates integer from decimal, FT9 records the rejected two-variant alternative for entity facets and takes the closed-enum route instead, FT10 avoids a redundant availability variant. |
| 10a | Facet `scope` ownership is stated correctly, not over-claimed | Pass — the earlier blanket "always copied from catalog" was wrong for structural facets, which have no `AttributeDefinition` behind them. FT2 now splits the two families: attribute-derived facets copy the catalog-owned scope (item 6 G1, ADR-0002 §2), while category/brand (`PRODUCT`) and price/availability (`VARIANT`) are fixed by this contract from already-frozen business semantics (item 6 G8, §9.2). Neither source is guessed, transport-inferred or request-overridable (QI11, A41, C53), and no scope primitive enters `core`. |
| 11 | Same-variant correctness is not undermined | Pass — FT3 forbids a transport computing matches and forbids exposing the union/satisfier structures; FQ4 ties `EXACT` to item 6 F6a's confirmation step; C43 asserts it on C24's dataset; the DTO describes facets and never carries the predicate. |
| 12 | Count quality cannot collapse into a convention | Pass — FQ2's iff invariant, FQ3's four distinct states (including "approximately 0" vs "unavailable" vs "absent option"), FQ5's separate truncation field, FQ6's ban on inference, C42's test and V43's review check. FQ7 reuses one quality model for totals. |
| 13 | Selection state and ordering are unambiguous and owned | Pass — SL1 keeps selection out of the projection; SL2 makes it explicit for both transports; SL3 puts canonical, deterministic, totally-ordered sequencing in `application/storefront` with tuple order as render order; SL6/C48 keep a selected option recoverable; SL5 defers only the policy, not the determinism. |
| 14 | The listing result replaces the paginator without a second implementation | Pass — LR1/LR2 materialise it, LR4 gives two metadata variants over one selector and one compiler (answering master `# 10.3`'s deep-vs-shallow distinction), DC6 rejects the mutually-exclusive-optional-fields alternative, and item 4 K1–K3 stay intact. |
| 15 | The cursor stays opaque and item 12 stays untouched | Pass — LR5 gives `Cursor` one field, forbids any payload field, and leaves the codec to Phase 4; A39 and C45 enforce it; LR8 keeps `source_version`/freshness out of the result and keeps the read path from compensating for staleness (item 6 PU6). |
| 16 | No mandatory exact total is introduced | Pass — LR6 states that the frozen master requires none, makes totals opt-in, applies the quality model, and ties `total_pages` to an exact total only; `has_next` covers the grid's actual need. |
| 17 | The input contract is complete without redesigning the compiler | Pass — §12.1 freezes all six `FilterTerm` field shapes and QI10 their invariants; QI3 keeps the whitelist authoritative and QI1/A38 forbid raw mappings and dynamic names; §12.2 freezes the *meaning* (`AND` between keys, `OR` within a key) while QI7 leaves the *physical predicate* to Phase 4 within item 6 G3/G4/G7 — semantics are the contract's, mechanism is the compiler's; QI8 still refuses to invent a scope concept or a routing rule. The earlier draft's deferral of AND/OR is withdrawn: a round-trip contract whose multi-value term has no defined meaning is not frozen. |
| 17a | Multi-select cannot weaken same-variant matching | Pass — §12.2 states the existential form explicitly, shows the forbidden "some variant is red AND another is L" reading by name, and confines every variant-scope disjunction inside one `EXISTS`; C50(c) asserts it on item 6 C24's dataset; V48 is the review check; item 6 G3/G4 and ADR-0008 §3 are applied, not amended. |
| 17b | The canonical form is single-valued | Pass — §12.3's nine rules give one term per key, merged and deduplicated values, range terms merged into their intersection, and deterministic value and term ordering; QI12 makes canonicalization one shared function; LR7 already ties it to canonical URLs and `filters_hash`; C51 asserts Web/API identity. |
| 17e | Canonicalization can never broaden a query | Pass — the earlier draft's QI10 implied that any invariant violation is simply removed, which is right for a tautology and **wrong for a contradiction**: dropping `price = 0..100 AND price = 200..300` would answer a strictly larger question than the one asked. §12.3's safety invariant now permits removal **only** for a semantically non-constraining term and enumerates the three (empty discrete selection, both-values boolean, boundless range); QI10a routes a contradictory recognized range — `minimum > maximum`, or an empty intersection — to **rejection before selector execution**, and forbids bound-swapping, dropping, key removal and widening by name. No `MatchNoneFilterTerm` is invented, so the closed unions of DC5/FT1 are untouched; the transport representation of the failure stays transport work (DC2). C54 tests both the negative case and the positive merge; V51 is the review check. |
| 17c | Counting is defined, and defined as the grid's own predicate | Pass — §12.4 fixes the add-option-to-its-own-key meaning with a worked example and the idempotence of an already-selected option; FQ9 records it in the count section; C41 asserts count/grid agreement under it; F6/F6a/C36 are preserved unchanged, and §16 classifies any other counting UX as a breaking semantic change rather than an implementation choice. |
| 17d | Facet semantics stay server-side | Pass — no `FilterTerm` carries `scope`, `EntityMatch`, an operator or an internal token (§12.1's closing note, QI11); the whitelist definition behind the `FacetKey` supplies them; A41 is the static check and C53 the behavioural one, so a caller cannot demote category from `SUBTREE_INCLUSIVE` or re-scope a facet. |
| 18 | Localization is decided rather than assumed | Pass — LO1 keeps one language per result and forbids RO/RU pairs; LO2 classifies domain content as already localized with LO3's concrete reason (a transport lookup would be a second read path and a per-facet query, item 6 RP3/F3); LO4 keeps interface vocabulary as codes; LO5 refuses to put a language type in `core` and flags that as ADR-requiring. |
| 19 | Availability and rating invent no state machine | Pass — AV1/AV2 mirror the frozen display boolean with no quantity, store list, band or lead time; AV3 keeps sellability with `inventory.public`; AV4/AV5 keep `None` distinct from `0` and keep the `×10` representation; AV6 keeps review internals off the card. |
| 20 | The DTO graph stays public and non-authorizing | Pass — SE1–SE5 with R5/DC10; C46 asserts anonymous/authenticated identity of the graph; SE3 keeps the signed cursor as the only outward path for an internal bigint; SE4 restates that no derived read model decides authorization. |
| 21 | Evolution is classified, not left to instinct | Pass — §16's table classifies each likely change, treats every enum/union addition as breaking per item 4 N5, gates the price-basis addition on SO3d, marks identifier and count-quality changes breaking, and EV1 forbids speculative optional fields (V44). |
| 22 | Nothing from items 8–13 is consumed and nothing is created | Pass — §1.2 and §20 route every deferred artifact to its owner; the boost stays ownerless and disabled; §17 is labelled non-production and creates no file; no event name, queue, trace field, version column or analytics source appears anywhere. |
| 23 | No contradiction with ADR-0001…ADR-0008 | Pass — **0001:** FK6/CD2/R4 keep `PublicId` as the public locator and internal bigints internal; CD1 keeps the card Product-grained without denying the SKU's sellable-unit role. **0002:** FK6 uses the immutable `AttributeChoice.code` and adds no attribute truth; FT2 copies attribute `scope` from catalog metadata rather than inferring it, and fixes structural-facet scope from frozen business semantics without inventing attribute truth. **0003:** no field asks catalog to hold price/stock/ERP identity/projection state. **0004/0005:** DC1 keeps one importable surface and adds no import edge; §18's preamble confirms no `L` rule and no `core` allowlist entry moves. **0006:** LO5 and FK1 keep facet and language vocabulary out of `core`. **0007:** untouched — nothing here enters the placement transaction, and R14/AV3/CD14 keep display state away from commercial truth. **0008:** §1.3 row 2, CD8–CD10, FT3, FQ4 and LR5 preserve its deferrals, its matching/counting decision and its one-read-path rule; §12.2's `OR` is confined inside its existential, so §3's same-variant rule is applied rather than relaxed. **No accepted ADR states multi-select-within-one-facet semantics**, so §12.2 contradicts none of them: master `# 7.2`'s `facet_choice_ids @> ARRAY[:choice_ids]` illustrates the array-containment *mechanism* for a set of distinct-attribute selections and makes no UX claim about two values of one facet (QI7). |

Verdict: **PASS**.
