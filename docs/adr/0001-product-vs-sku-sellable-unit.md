# ADR-0001 — Product vs ProductVariant: the SKU is the only sellable unit

- **Status:** Accepted — Frozen
- **Date:** 2026-09-03
- **Phase:** 0 — Architecture Freeze
- **Supersedes:** —
- **Related:** [ADR-0002](0002-typed-eav-source-of-truth.md), [ADR-0003](0003-catalog-boundary-vs-storefront-projection.md),
  [ERD](../architecture/erd/catalog_product_sku_attributes.md), master `# 7.1`

## Context

A catalog entity such as "iPhone 17 Pro" is one marketing object but several sellable objects
(256 GB Black, 512 GB Black, 1 TB Black …). Collapsing them into one row forces price, stock and
order lines onto an entity that has no single price and no single stock, and makes every later
correction — reservations, ERP import, order snapshots — a special case. The split has to be
frozen before any commercial domain is designed, because every one of them takes a foreign key to
whichever side we choose.

A second, related question is which identifier is allowed to leave the system: internal `bigint`
primary keys are compact and fast, but enumerable and unstable across environments.

## Decision

### 1. Two entities, one sellable

- `Product` — marketing entity: taxonomy, brand, localized copy, SEO, gallery, related products.
  It has **no price, no stock, no availability flag** and is **never** sellable.
- `ProductVariant` — the SKU: the single sellable unit. It carries `sku_code`, `gtin`,
  option values, physical dimensions, `max_credit_months`, lifecycle state and `is_sellable`.

**Reference rule.** A relationship whose semantics require a concrete sellable unit MUST reference
`ProductVariant`/SKU: `Price`, `InventoryBalance`, `Reservation`, `CartItem`, `OrderItem`, and any
fulfilment/shipment line where the concrete SKU matters.

A variant-independent relationship MAY intentionally reference `Product`: `Review`, `Favorite`,
`RelatedProduct`, CMS merchandising, product-wide promotion targeting.

The invariant is therefore precise: **`Product` must never substitute for `ProductVariant` where
concrete price, stock, reservation, cart, order or fulfilment semantics require a SKU.** A
`Product` foreign key is a defect only when the relationship carries one of those semantics.

### 2. Variant options

Option values are ordinary typed attribute values on the variant (ADR-0002). A separate
`ProductOptionAxis(product_id, attribute_id, position)` declares *which* attributes vary for a
given product. There is **no parallel option-value storage**.

`ProductVariant.option_signature` is a derived canonical string built from the variant's option
values, ordered by axis position, in the form `color=black;storage=256gb`. The database enforces
`UNIQUE (product_id, option_signature)`, so two variants of one product cannot share an option
combination. A product with no declared axes uses the sentinel `-` and therefore may hold exactly
one variant (D-10).

The signature is a denormalized cache: the database guarantees its uniqueness, the catalog domain
service guarantees it matches the stored values. That gap is recorded as an explicit non-DB
invariant rather than assumed away.

### 3. Identity

- Internal PK: `bigint` identity.
- Public identifier: `public_id uuid NOT NULL UNIQUE`, generated as UUIDv7 by `core` `PublicId`,
  on `Product`, `ProductVariant`, `Category` and `Brand`.
- Business keys on the variant: `sku_code` unique (canonical uppercase, DB-checked) and `gtin`
  unique-where-present with a format CHECK.

**Boundary rule.** Two different boundaries, two different rules.

*User/public locator boundaries* — URLs, public API resource locators, email links, QR links,
Track & Trace and similar user-facing object locators — use `PublicId` (UUIDv7) or a purpose-bound
signed public token.

*External machine-to-machine boundaries* — ERP/CRM/payment/vendor integrations — MUST use an
explicitly defined stable contract identifier chosen and documented by that adapter. `public_id`,
`sku_code`, `gtin`, a provider `external_id`, a provider order/payment identifier, or another
provider-specific stable identifier are all allowed. There is no requirement that vendor contracts
speak `public_id`.

*Internal boundaries* — internal Outbox event payloads, projection rebuild jobs, internal Celery
task arguments — may use the internal `bigint` PK, where the narrower key is a real performance
benefit and both sides deploy together.

The hard rule across all three: the internal `bigint` PK must **never** be exposed merely as the
external contract identifier. `integrations/*` is the anti-corruption boundary that translates
between external identifiers and internal `bigint` ids, and `interfaces/*` does the same for public
HTTP. This is compatible with `ErpVariantMapping(provider, external_id, variant_id)`, which is not
required to expose `ProductVariant.public_id` unless that provider's contract needs it.

ERP/1C identity is **not** part of this domain — see ADR-0003.

### 4. Deletion

`Product` and `ProductVariant` are not hard-deleted in normal business flow. Withdrawal is
`Product.status='archived'`, `ProductVariant.lifecycle_status='discontinued'`, `is_sellable=false`.
Every foreign key in the catalog schema is `ON DELETE RESTRICT ON UPDATE RESTRICT`; there is no
`CASCADE` and no `SET NULL`. Historical commercial references must never break.

Two sellability rules follow:

- `is_sellable = true` requires `lifecycle_status = 'active'` — a DB CHECK;
- `is_sellable = true` requires the parent `Product.status = 'active'` — a cross-table rule the
  catalog domain service enforces, with a Phase 2 consistency test. MVP adds no trigger for it.

## Consequences

**Positive**

- Price, stock, reservations and order lines have exactly one correct anchor from day one, while
  variant-independent features (reviews, favorites, merchandising) keep the product-level reference
  that actually fits them.
- Duplicate SKUs from ERP import are blocked by the database, not by import code.
- Internal PKs stay out of public locators and out of contract identifiers, while remaining usable
  internally where they are cheap.
- Archiving is safe: no historical order can lose its product reference.

**Negative / accepted cost**

- `option_signature` is denormalized and needs a writer path plus a rebuild procedure when a
  product's axis set changes.
- `RESTRICT` everywhere makes genuine admin cleanup of unused draft data a deliberate multi-step
  operation. This friction is intended.
- Every externally addressable table pays for an extra `uuid` column and its unique index.

**Enforcement**

Phase 2 implements the ERD constraints. Phase 1 provides `core.PublicId`. Boundary compliance is
split by what each mechanism can actually see:

| Mechanism | What it enforces |
|---|---|
| `import-linter` | Python module/dependency boundaries. It inspects imports, **not** payload contents, and cannot detect a serialized identifier leak. |
| Serializer / route / API tests | Identifiers exposed on public HTTP responses and URLs. |
| Webhook / integration contract tests | Identifiers on external machine-to-machine contracts, per adapter. |
| Typed `PublicId` DTOs | Reduce accidental id confusion at the type level, so a `bigint` cannot silently occupy a public-locator field. |
| Targeted AST / static checks | May additionally flag dangerous identifier exposure where practical; best-effort, not the primary control. |
