# ADR-0002 — Typed EAV is the source of truth, and its type contract is enforced by PostgreSQL

- **Status:** Accepted — Frozen
- **Date:** 2026-09-03
- **Phase:** 0 — Architecture Freeze
- **Related:** [ADR-0001](0001-product-vs-sku-sellable-unit.md), [ADR-0003](0003-catalog-boundary-vs-storefront-projection.md),
  [ERD](../architecture/erd/catalog_product_sku_attributes.md), master `# 7.2`

## Context

Product characteristics must serve admin editing, validation, comparison, import/export and
projection building. A JSON blob cannot be validated or compared reliably; a wide typed table
cannot absorb heterogeneous categories. A typed EAV model fits — but naive EAV has three classic
failure modes we must close in the schema rather than in prose:

1. the value row and the attribute definition disagree about the type;
2. a value row is attached to a variant of a different product;
3. `NULL` semantics silently permit duplicate values for the same owner.

There is also a modelling question the ERD cannot dodge: some characteristics belong to the
marketing product (warranty, series), some to the SKU (colour, storage), and some to both with the
product acting as a default.

## Decision

### 1. Typed EAV is truth; it is not the filtering path

`AttributeDefinition` + `AttributeChoice` + `ProductAttributeValue` are the source of truth for
attributes. The storefront **never** self-joins or `EXISTS`-es over `ProductAttributeValue` per
selected facet; it filters the storefront projection (ADR-0003). EAV serves admin, validation,
comparison, import/export and projection building only.

### 2. Attribute scope and variant axes

`AttributeDefinition.scope ∈ {product, variant, both}`:

| `scope` | Value lives at | Inheritance |
|---|---|---|
| `product` | Product level only | applies to all variants |
| `variant` | Variant level only | none |
| `both` | either level | product row is the default, variant row overrides |

Effective value for `scope='both'` is `variant explicit value ?? product default value`, resolved
in the catalog domain at read time and never materialized in the OLTP schema.

`AttributeDefinition.is_variant_axis = true` marks an attribute that forms variants. A variant axis
must be `data_type='choice'` and `scope='variant'` (D-9), enforced by a CHECK. Two consequences
follow for free: the option token in `option_signature` is always a stable choice code, and a
variant-axis value can never be stored at product level, so it can never be inherited.

### 3. The type contract, enforced relationally

A plain CHECK cannot read `AttributeDefinition.data_type` from another table. Instead, the
governing columns are **mirrored** into the dependent row and locked with composite foreign keys,
after which the CHECK is purely local and fully enforceable.

`ProductAttributeValue` carries `value_type` and `attribute_scope` mirrors, with

```
FOREIGN KEY (attribute_id, value_type, attribute_scope)
    REFERENCES attribute_definition (id, data_type, scope)
    ON DELETE RESTRICT ON UPDATE RESTRICT
```

plus a local CHECK that exactly one value column is populated for the given `value_type`, and a
local CHECK that the owner level matches the scope.

`AttributeChoice` carries an `attribute_data_type` mirror with `CHECK (attribute_data_type = 'choice')`
and

```
FOREIGN KEY (attribute_id, attribute_data_type)
    REFERENCES attribute_definition (id, data_type)
    ON DELETE RESTRICT ON UPDATE RESTRICT
```

so a choice list cannot be attached to an `integer`/`decimal`/`bool`/`text` attribute at all.

`ProductOptionAxis` carries an `is_variant_axis` mirror with `CHECK (is_variant_axis)` and a
composite FK to `attribute_definition (id, is_variant_axis)`, so a non-axis attribute cannot be
declared as an axis.

Each of these requires a `UNIQUE` constraint on exactly the referenced column list in
`AttributeDefinition`; all three are declared explicitly in the ERD.

`ON UPDATE RESTRICT` gives a further property for free (D-12): while values, choices or axes exist,
an attribute's `data_type`, `scope` and `is_variant_axis` cannot be changed at all.

### 4. Ownership integrity

`ProductAttributeValue.product_id` is always required. `variant_id` is nullable — `NULL` means
product level. When it is set, the composite FK
`(variant_id, product_id) → product_variant (id, product_id)` guarantees the variant belongs to
that same product. PostgreSQL's default `MATCH SIMPLE` skips the constraint entirely when
`variant_id IS NULL`, which is exactly the desired behaviour. The same technique binds
`ProductImage` and `AttributeChoice` references.

### 5. Uniqueness under NULL semantics

`UNIQUE (product_id, variant_id, attribute_id)` would not work: two rows with `variant_id IS NULL`
never conflict in PostgreSQL. Two partial unique indexes are used instead — one
`WHERE variant_id IS NULL` on `(product_id, attribute_id)`, one `WHERE variant_id IS NOT NULL` on
`(variant_id, attribute_id)`.

### 6. Decimal precision

Decimal values use `numeric(16,4)`: four fractional digits absorb unit conversions and real spec
values, twelve integral digits exceed any physical specification, and fixed-point keeps comparison
and bucketing exact. `float`/`double precision` is prohibited. This type is never used for money —
money is integer minor units in `domains/pricing`.

### 7. Immutable identifiers and units

`option_signature` is composed of attribute and choice codes, and stored numeric values are
meaningful only relative to `AttributeDefinition.unit`. Therefore, once an `AttributeDefinition` is
referenced by any value or axis row:

- `AttributeDefinition.code` and `AttributeChoice.code` are immutable — a rename is a new
  definition plus a controlled data migration, never an admin `UPDATE`;
- `AttributeDefinition.unit` is immutable unless a controlled migration rewrites every dependent
  `value_integer`, `value_decimal` and `numeric_value` in the same transaction.

These are domain-service and admin enforced, not DB enforced, because expressing "immutable once
referenced" in PostgreSQL requires a trigger and MVP adds none here. Human-readable labels stay
freely editable — they carry no structural meaning.

### 8. Single-valued in MVP

One `AttributeDefinition` has at most one value per owner. **Multi-valued attributes are deferred.**
Adding them requires a new ADR and replacement of both partial unique indexes.

Also deferred (D-13): category↔attribute applicability — nothing in the schema currently prevents
attaching a phone attribute to a fridge. It is validated in the domain and listed as a known gap.

## Consequences

**Positive**

- A type-mismatched, wrongly-owned, wrongly-scoped, duplicated or orphan-choice value row is
  rejected by PostgreSQL, so importers, admin actions and future refactors cannot corrupt the data.
- Retyping an in-use attribute is impossible by accident.
- `option_signature` rests on identifiers that cannot silently drift.

**Negative / accepted cost**

- Three mirrored columns denormalize definition metadata into dependent rows and must be kept
  correct on write — the composite FKs make an incorrect value unwritable, so the cost is verbosity,
  not risk.
- Three overlapping `UNIQUE` constraints on `AttributeDefinition` exist purely as FK targets.
- Changing an attribute's type or unit becomes an explicit migration procedure. Intended.
- Code and unit immutability is service-enforced, so an out-of-band SQL update could still break it.
  Accepted for MVP and recorded as invariants I-7 and I-8.

**Enforcement**

Phase 2 implements the constraints; the catalog domain service owns invariants I-1, I-2, I-7, I-8;
a `catalog_consistency` integrity test covers them in CI.
