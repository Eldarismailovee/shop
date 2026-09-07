# ADR-0003 — Catalog domain boundary: no price, no stock, no ERP identity, no storefront projection

- **Status:** Accepted — Frozen
- **Date:** 2026-09-03
- **Phase:** 0 — Architecture Freeze
- **Related:** [ADR-0001](0001-product-vs-sku-sellable-unit.md), [ADR-0002](0002-typed-eav-source-of-truth.md),
  [ERD](../architecture/erd/catalog_product_sku_attributes.md), master `# 7.6`, `# 22`

## Context

The catalog schema is the first thing built, so it is the easiest place to accidentally absorb
everything else. Four temptations are concrete and each would be cheaper *today* and much more
expensive later:

- put `price` on the variant, because a product page shows a price;
- put `in_stock` on the variant, because a grid shows availability;
- put `external_1c_id` on the variant, because the ERP import needs a key;
- put `source_version` on the product, because the storefront projection will need a guard.

Each of them makes `domains/catalog` depend on a domain it must not know about, and the fourth
makes an OLTP table carry a read-model concern.

## Decision

### 1. Catalog owns catalog data only

`domains/catalog` contains `Category`, `Brand`, `Product`, `ProductVariant`, `ProductOptionAxis`,
`AttributeGroup`, `AttributeDefinition`, `AttributeChoice`, `ProductAttributeValue`, `ProductImage`
— and nothing else.

| Concern | Owner | Reference direction |
|---|---|---|
| Price, price lists, discounts | `domains/pricing` | pricing → SKU |
| Stock, reservations | `domains/inventory` | inventory → SKU |
| Cart / order lines + immutable commercial snapshot | `domains/*` orchestrated by `application/checkout` | orders → SKU |
| Reviews, ratings | `domains/reviews` | reviews → product (variant-independent by design, ADR-0001) |
| Favorites, comparison | `domains/accounts` | favorites → product (variant-independent by design, ADR-0001) |
| Listing projection, facets | `application/storefront` | built from catalog `public.py` DTOs |
| ERP/1C identity | `integrations/erp` | mapping → SKU |

The catalog schema therefore has **no** money column of any kind, **no** stock or availability
column, and **no** denormalized rating or popularity column. Catalog does not import from any other
domain, and other domains reach it only through `catalog.public` with immutable DTOs — never ORM
instances or QuerySets.

### 2. ERP/1C identity lives at the integration boundary

No `erp_id`, `1c_id` or `external_1c_id` on `ProductVariant`. Catalog identity is: internal
`bigint` PK, `public_id` UUIDv7, `sku_code` (unique business code), `gtin` (unique where present).

Stable vendor identity belongs to the anti-corruption layer, conceptually
`ErpVariantMapping(provider, external_id, variant_id)` in `integrations/erp`. This keeps a vendor
key rename from touching catalog data, allows more than one provider, and prevents an ERP concept
from becoming a domain concept. The mapping table is designed in Phase 3 with the ERP import; only
its ownership is frozen here.

The identifier rule from ADR-0001 applies at this boundary in its machine-to-machine form: the ERP
contract names its own stable identifier — a provider `external_id` held in the mapping, or
`sku_code`, or `gtin`, or `public_id` — and documents that choice. `ErpVariantMapping` is **not**
required to expose `ProductVariant.public_id` unless that provider's contract actually needs it.
What is forbidden is exposing the internal `bigint` PK as the contract identifier; `integrations/*`
translates between the external identifier and the internal id.

### 3. The storefront projection is not catalog's, and neither is `source_version`

`ProductListingProjection` is a disposable read model owned by `application/storefront`, assembled
from the public contracts of catalog, pricing, inventory, reviews and promotions. One row per
`Product × Language`, containing everything the grid and list API need without joins:
`facet_choice_ids` arrays, promoted typed `attr_*` columns, `min_price_minor`, `in_stock`,
`primary_image_path`, `rating_avg_x10`, and its own `source_version`.

**No `source_version` column exists on `Product` or `ProductVariant`.** The catalog domain must not
know the version scheme of a read model that belongs to another layer. `source_version` generation
and the guarded projection upsert are a separate Phase 0 item and will be designed there.

Consequently the catalog schema carries no facet index, no GIN array index and no promoted
attribute column. Those belong to the projection.

### 4. Localization is physical columns, not a framework dependency

RO/RU is a fixed pair, so localized text is stored in physical `*_ro` / `*_ru` columns on
`Category`, `Brand`, `Product`, `AttributeGroup`, `AttributeDefinition`, `AttributeChoice` and
`ProductImage`. There is no translation side table and no runtime join.

`django-modeltranslation` may manage these columns in Phase 2, but that is an implementation
detail behind the schema contract. The storefront hot read path resolves language by column name
and must not depend on modeltranslation machinery — the projection stores one row per language and
reads a plain column.

`ProductVariant` has no localized text: a variant is identified by its option values, whose labels
are localized on `AttributeChoice`. `ProductAttributeValue.value_text` is deliberately
non-localized; a user-visible translatable characteristic must be modelled as `choice`.

## Consequences

**Positive**

- `domains/catalog` can be developed and tested standalone, which is the Phase 2 DoD.
- Pricing, inventory and ERP can change their models without a catalog migration.
- The read model can be dropped and rebuilt at any time; the OLTP schema is unaffected.
- Storefront performance work stays in one place instead of leaking indexes into OLTP tables.

**Negative / accepted cost**

- The product page and the grid need composition in `application/storefront` from the first sprint;
  there is no "just join it" shortcut.
- ERP import needs its mapping table before it can run, rather than a column on the variant.
- Physical localized columns double the width of text-heavy tables and make adding a third language
  a migration. Accepted: RO/RU is a fixed product decision, and the alternative costs a join on
  every read.

**Enforcement**

`import-linter` contracts in CI (Phase 1) enforce the *module dependency* direction — catalog must
not import pricing, inventory, reviews or storefront. Schema content is a separate control: a
review checklist item, so that any money, stock, ERP-identity or projection column proposed for a
catalog table is rejected by default and needs a new ADR. Identifier exposure on contracts is
covered by the mechanisms listed in ADR-0001 (serializer/route/API tests, webhook and integration
contract tests, typed `PublicId` DTOs), not by `import-linter`, which does not inspect payloads.
