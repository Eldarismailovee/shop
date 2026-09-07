---
paths:
  - "core/**/*.py"
  - "core/**/tests.py"
  - "core/**/tests/**/*.py"
---
# `core` layer rules
- `core` **knows no domain**. No business rule, no product/order/payment concept, no business vocabulary or semantics, no vendor type, no transport type. Admission test: it must be needed by more than one family and carry no domain semantics.
- **`core` contains no business/domain persistence model.** Django persistence is admissible in `core` only for an already-approved, **domain-independent infrastructure mechanism** whose placement satisfies the `core` admission test and the frozen allowlists — e.g. idempotency / Outbox / Inbox / terminal-state (quarantine, dead-letter) infrastructure, where the implementing Phase-1 decision places it. Item 3 A1 permits model definitions in `domains/<x>/models*`, `application/<a>/models*` and **`core` infrastructure models**; this rule does not narrow that.
- A `core` infrastructure model carries **no** Product/Order/Payment/Inventory/Promotion (or any other domain's) business ownership or domain rule. Cross-cutting persistence does **not** make `core` a shared-business-model layer, and it never becomes a back door for a domain table.
- Adding a `core` submodule extends an allowlist frozen by ADR-0005 §1 / ADR-0006. Do not add one silently — record the placement and its per-family consumers, and write an ADR where an allowlist actually moves. `integrations/*` keeps only its narrow permitted pure-Python `core` subset; `interfaces/*` may not import `core.outbox` or `core.idempotency`.
- `Money` = integer minor units + an **explicit** currency. `float` is banned end to end; `bool` is not a money integer. Same-currency arithmetic is exact; cross-currency arithmetic and cross-currency **ordered** comparison are rejected, while equality stays total and zero is currency-bearing. Currency is never inferred from locale, user, store, request, provider or environment. `core` knows no discount/VAT/promotion/delivery/loyalty/FX policy.
- Every non-minor-unit input goes through an explicit conversion naming currency, exponent and a `RoundingPolicy` that has **no default anywhere**. The currency exponent is boundary metadata, never a `Money` field and never assumed to be 2. `Decimal` is for rates/ratios/parsing only — never persisted, never public commercial truth.
- `PublicId` is a platform-generated, immutable, never-recycled, never-derived, standards-conforming UUIDv7 **locator**: not a secret, not a permission, not a PK replacement, not the keyset tiebreaker, and its embedded timestamp is never business time, ordering or a version. Provider/ERP/legacy UUIDs never become `PublicId`s.
- `EventId` is a **runtime-distinct** type over the same UUIDv7 value space (ADR-0013); the shared mechanism is `core`-internal and exported to nobody.
- `core.events` owns **mechanism only** — envelope, registry lookup, codec, validation, contract-failure signalling. **No business message type lives in `core`**, and the registry ships empty.
- The actor primitive and the structural public-error categories live in `core` (ADR-0006) and are business-free. `integrations/*` and migrations depend on neither.
- **DTO/value-object derived properties and methods are pure and total.** Parsing, validation, UUIDv7 generation, registry validation and similar `core` mechanisms follow their own explicit primitive contracts — they may reject invalid input, and may use the approved time/entropy mechanism — and are **not** reclassified as DTO-derived members. This bounds the rule; it does not weaken the public-DTO requirement.
- Instants are aware UTC.
