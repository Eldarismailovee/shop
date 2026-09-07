# Phase 0 — Item 11: `Money` and public identity (`PublicId`, `EventId`)

- **Status:** DONE / FROZEN
- **Date:** 2026-09-05
- **Phase:** 0 — Architecture Freeze
- **ADRs:** [ADR-0012](../../adr/0012-money-currency-scoped-partial-order.md) — required, Money ordering (§1.3);
  [ADR-0013](../../adr/0013-event-id-distinct-identity-type.md) — required, `EventId` (§1.3)
- **Related:** [ADR-0001](../../adr/0001-product-vs-sku-sellable-unit.md),
  [ADR-0004](../../adr/0004-four-layer-modular-monolith.md),
  [ADR-0005](../../adr/0005-dependency-and-integration-wiring.md),
  [ADR-0006](../../adr/0006-public-contract-primitives.md),
  [ADR-0007](../../adr/0007-place-order-atomic-idempotent-boundary.md),
  [ADR-0008](../../adr/0008-storefront-listing-projection.md),
  [ADR-0009](../../adr/0009-event-contract-versioning.md),
  [ADR-0010](../../adr/0010-async-failure-domain-isolation.md),
  [ADR-0011](../../adr/0011-async-trace-causality-envelope.md),
  [item 3](03-dependency-matrix.md), [item 4](04-domain-public-contract.md),
  [item 5](05-place-order-use-case.md), [item 6](06-storefront-listing-projection.md),
  [item 7](07-storefront-dto-contract.md), [item 8](08-event-registry-versioning.md),
  [item 9](09-queue-failure-domain-dlq.md), [item 10](10-async-trace-propagation.md),
  master `# 4`, `# 5`, `# 5.1`–`# 5.3`, `# 15.3`, `# 25` (Phase 0 / Phase 1), `# 26`

---

## 1. Purpose

### 1.1 What this item freezes

Every item from 4 onwards has written `Money` and `PublicId` into a frozen contract and then deferred
the types themselves to item 11: item 4 D8/D9 and §7.4, item 5 R10/PR6, item 6 I5/PG4, item 7
DC8/FK6/CD13, item 8 PD9/ID7, item 9 §39, item 10 R16/CZ4. Ten artifacts now depend on two
primitives that have never been given semantics. Item 11 gives them semantics — and **only**
semantics: no package, no module, no dataclass, no field, no migration, no library.

Frozen here:

- **`Money`** as a `core`-owned, domain-independent, exact, multi-currency value type: integer minor
  units plus an explicit currency, with `bool` excluded from "integer", `float` excluded everywhere,
  and no currency ever inferred (§4–§7);
- **currency-scoped arithmetic and a currency-scoped *partial* order**: exact equality across all
  instances, ordered comparison only within one currency, and the explicit rejection of the
  automatic total ordering the master's illustrative `order=True` would produce (§8, §9 — **ADR-0012**);
- **signedness as a field-level, not primitive-level, invariant** (§10);
- **explicit boundary conversion** into `Money` from any non-minor-unit representation, with an
  explicitly named rounding policy wherever a fractional minor unit can arise, and **no default
  policy anywhere** (§11–§14);
- the separation of **Money representation** from **currency exponent/formatting metadata**, so no
  currency is assumed to have two decimals and no live registry is admitted into `core` (§12);
- the **float firewall** and the `Decimal` rule: `Decimal` for rates, ratios and parsing; never as
  persisted or public commercial truth (§15, §16);
- **persistence**: integer minor units, never `float`/`real`/`double precision`, never an arbitrary
  `numeric` as the canonical stored amount (§17);
- **contract usage**: a semantic money position is `Money`, not a naked integer, `Decimal` or float;
  an external representation is exact and never a binary floating number (§18);
- **exact provider amount comparison** with no tolerance, and the negative FX rule — `Money` never
  converts currency implicitly (§19, §20);
- **`PublicId`** as a strongly-distinct, immutable, platform-generated, standards-conforming UUIDv7
  public locator — distinct **both statically and at runtime**, over an underlying UUID
  representation — with its non-authorization, non-timestamp, non-version, non-PK and non-cursor
  rules (§22–§31);
- the preservation of ADR-0001's **three identity spaces** (public locator / external contract
  identifier / internal bigint), which item 11 types rather than rewrites (§21, §31);
- **`EventId`** as a *distinct* semantic type over the same UUIDv7 value space, resolving item 8
  ID7's and item 10 CZ4's deferral without turning a message identity into a resource locator
  (§32–§34 — **ADR-0013**);
- the rule that **one physical representation does not imply one semantic type**, with the generic
  UUIDv7 mechanism kept `core`-internal so it cannot dissolve the distinction (§34);
- equality/hashing, serialization neutrality, the error classification, security rules, the
  failure matrix, and checks **A68–A85**, **C100–C127**, **V84–V101** (§35–§41).

### 1.2 What this item does **not** do

Item 11 produces **documents and decisions only**. It creates no Python package, module, dataclass,
`NewType`, enum member list, Django field, model, migration, serializer, currency table,
exchange-rate service, UUID library choice or dependency. Every "shape" shown below is prose or
pseudo-notation, explicitly labelled as illustrative, and binds meaning rather than code.

It also does not reopen a neighbouring item. In particular it defines **no** `source_version`,
revision or staleness guard (item 12); **no** analytics decision (item 13); **no** MVP/later module
cut (item 14); **no** event type, payload schema, `schema_version` semantics, routing, terminal
state or replay rule (items 8–10); and **no** projection, facet, cursor or pricing algorithm
(items 6, 7).

### 1.3 Why two ADRs are required — evaluated separately

The instruction to evaluate ADR need per decision matters here, because item 11 carries two
unrelated primitives and the honest answer differs for each. The evaluation:

| Decision | ADR? | Reasoning |
|---|---|---|
| `Money` = integer minor units + explicit currency | **No** | Master `# 5.3` states it; item 4 D8 froze it as a contract rule; item 3 §4.2–§4.6 already allowlists `core.money`. Item 11 specifies an existing decision. |
| No implicit constructor from `float`/`Decimal`/string; explicit factory with a `RoundingPolicy` | **No** | Master `# 5.3` states both sentences verbatim; master `# 25` Phase 1 lists `Money/RoundingPolicy`. Item 11 gives the rule its precise scope. |
| `core` validates currency **structurally**, not against an ISO membership registry | **No** | Derived from ADR-0004 §2's admission test (mechanism-shaped, no policy, no changing external data). It adds no dependency and moves no boundary. |
| **Ordered** money comparison is same-currency only; no automatic total order | **Yes → ADR-0012** | Master `# 5.3`'s illustrative dataclass declares `order=True`, which yields a total lexicographic order over `(minor, currency)` and makes `Money(100, "EUR") < Money(200, "USD")` legal. Item 11 forbids that. This is a **money rule change against explicit master content**, visible to every module that sorts, `min`s or thresholds money — exactly the ADR trigger in `docs/adr/README.md`. |
| `PublicId` = distinct UUIDv7 public locator, immutable, never a PK replacement, never a keyset tiebreaker | **No** | ADR-0001 §3 froze the boundary rule and named `core` `PublicId`/UUIDv7; master `# 5.1` froze immutability, the signed-token requirement for sensitive guest access, and the pagination performance rule. Item 11 types what those already decided. |
| `PublicId` is a locator, not a secret and not a permission | **No** | ADR-0001 §3 (locator boundaries) plus master `# 5.1`'s explicit "одного `public_id` недостаточно" and item 4 §11's authorization-by-construction. Item 11 restates the consequence for the type. |
| The UUIDv7 embedded timestamp is never business time, ordering or a version | **No** | It is the direct consequence of item 8 ID2/ID5 and §26 (no ordering key), item 10's nine-way distinctness table, and item 6 §16.1's stale-update requirement. Nothing moves. |
| **`EventId` is a semantic type distinct from `PublicId`**, over the same UUIDv7 value space | **Yes → ADR-0013** | Item 8 ID7 deferred the concrete type to item 11 and its parenthetical reads as a hint toward `PublicId` itself. Choosing a *distinct* type is a new binding identity decision: it introduces a second `core` identity primitive, fixes item 10 CZ4's `causation_event_id` representation, and asserts that a durable message identity is categorically not an externally addressable resource locator. |

**Two ADRs, one decision each.** No combined "item 11 primitives" ADR is written: the money-ordering
decision and the message-identity decision share nothing but a chapter number, and merging them
would make either impossible to supersede alone.

Neither ADR moves a dependency-matrix cell, adds an import edge, or extends a `core` submodule
allowlist. `L1–L21` stand unedited (§43 row 18).

### 1.4 Relationship to the master

| Master content | Item 11 |
|---|---|
| `# 5.3` — `Money` value object, `minor: int` + `currency`, minor units in PostgreSQL | **Preserved** (§4, §17) |
| `# 5.3` — `type(self.minor) is not int` guard | **Preserved and named**: an exact type check, so `bool` is excluded (§5) |
| `# 5.3` — "Неявного конструктора из `float`/`Decimal` нет. Граница ввода использует явную фабрику с `RoundingPolicy`" | **Preserved and scoped**: every fractional-capable operation, not only parsing (§11, §13) |
| `# 5.3` — currency mismatch on `__add__` raises | **Preserved and generalised** to subtraction, comparison and aggregation (§8) |
| `# 5.3` — `@dataclass(..., order=True)` | **Changed** — the only departure. Ordered comparison becomes currency-scoped and partial; the automatic total order is rejected (§9, ADR-0012) |
| `# 5.3` — construction shown positionally | **Specified** by item 4 §7.1's already-frozen `frozen/slots/kw_only` baseline; the master snippet is illustrative code, not a construction contract (§4) |
| `# 5.3` — "`Decimal` допустим для курса/коэффициента и представления, но конверсия в Money происходит в одном месте" | **Preserved** (§16) |
| `# 5.3` — `100.00 MDL == 10000` банов | **Preserved as an example, not as a definition**: the exponent is currency metadata, not a Money field, and is never assumed to be 2 (§12) |
| `# 5.3` — "`PublicId` оформляется отдельным типом/newtype" so a bigint and a UUIDv7 cannot be confused in a signature | **Preserved and strengthened as a requirement.** The concrete construct is Phase 1's, bounded by §23 TY1–TY5: it must be a **runtime-distinct immutable value representation**, so a bare `typing.NewType` over `uuid.UUID` is **not** admissible on its own — the master's "тип/newtype" phrasing names the intent (a separate type, not a convention), and §23 TY4/TY5 fix the strength that intent requires |
| `# 5.1` — internal bigint PK + separate `public_id` UUIDv7, unique, immutable; public links built only from `public_id`; signed limited-lifetime token for sensitive guest access | **Preserved** (§22, §24, §25, §29) |
| `# 5.1` — performance rule: `public_id` is not the keyset tiebreaker; the cursor is a signed opaque token | **Preserved** (§28) |
| `# 5.2` — `IdempotencyKey.key` is `UUID/String`, scoped, with `resource_public_id` | **Preserved and delimited**: an idempotency key is neither a `PublicId` nor an `EventId` (§30 ID9) |
| `# 15.3` — Pricing/Delivery/Order/Payment compare amounts only in minor units; `Decimal` appears only at render | **Preserved** (§17, §18, §19) |
| `# 4` / `# 3` — `core/money.py` (Money + RoundingPolicy), `core/public_id.py` (UUIDv7/PublicId) | **Preserved as placement**; physical file layout stays Phase 1's (§2) |
| `# 25` Phase 0 "Money/PublicId types", Phase 1 "Money/RoundingPolicy + PublicId UUIDv7" | This artifact discharges the Phase 0 entry; the Phase 1 entry is untouched |
| `# 26` — "Money value object используется в domain/application code", "PublicId UUIDv7 отделён от internal bigint" | Both become checkable here (§41) |

---

## 2. Ownership and placement

| # | Rule |
|---|---|
| OW1 | **`Money` and the rounding mechanism belong to `core`.** They are domain-independent, carry no business or vendor vocabulary, have many consumers (pricing, promotions, orders, payments, delivery, storefront DTOs, ports, integrations) and are mechanism-shaped. They pass ADR-0004 §2's four-part admission test outright, and item 3 §4 already names `core.money` in every family's allowlist. |
| OW2 | **`PublicId` belongs to `core`** on the same test, and item 3 §4 already names `core.public_id` in every family's allowlist. |
| OW3 | **`EventId` belongs to the envelope mechanism `core.events`** (ADR-0009 §1 / item 8 OW4): `event_id` *is* an envelope field, so its type is envelope mechanism. `core.events` is already allowlisted for `domains` (item 3 §4.2), `application` (§4.3), `tasks` (§4.6) and the composition root (§4.7), and already `FORBID` for `integrations/*` (§4.5) — which is exactly right, because a provider's `external_event_id` is a different identity space (item 8 ID6). **No allowlist entry changes** (§34, ADR-0013). |
| OW4 | **`core.Money` knows no business policy.** It must not encode, reference or branch on: discount rules, VAT or tax policy, promotions, delivery thresholds, payment-provider rules, loyalty rules, exchange-rate sources, price lists, or whether a particular amount is allowed to be negative. Those live with their owning domain or application module. A `core` money member whose name contains a business noun is a defect (A70). |
| OW5 | **`core.PublicId` and `core.EventId` know no entity.** No `OrderId`, `ProductId`, `PaymentId` subtype is created in `core`. A locator is a locator; which entity it addresses is stated by the field name in the owning contract (item 4 I2: `product_public_id`, not `id`). |
| OW6 | Item 11 introduces **no new `core` submodule allowlist entry, no new package family, no new import edge and no new `L` rule.** Every consumer relationship it needs was granted by ADR-0005 §1 / item 3 §4 before it was written. |
| OW7 | If a Phase 1 placement decision (for example, an operator-facing surface that must render an `EventId`) turns out to imply an allowlist extension, it is **recorded then, as ADR-0006 did and as item 10 PC9 anticipated** — not pre-empted here. Item 11 requests none. |

---

## 3. Vocabulary

| Term | Meaning in this artifact |
|---|---|
| **Minor unit** | The smallest indivisible unit in which a currency's amounts are exactly represented (bani for MDL, cents for EUR, the unit itself for a zero-exponent currency). |
| **Major unit** | The human-facing denomination (`100.00 MDL`). Never a storage or contract form. |
| **Currency exponent** | The number of decimal digits separating major from minor units for a given currency. Metadata *about* a currency, never a field *of* `Money` (§12). |
| **Exact operation** | An operation on `Money` that cannot produce a fractional minor unit: addition, subtraction, negation, integer-count multiplication, aggregation of same-currency values. |
| **Fractional-capable operation** | Any operation that can produce a non-integral minor amount: major-unit parsing, ratio/percentage application, FX conversion, proportional allocation, averaging. |
| **Materialisation** | The single, explicitly located step that turns a fractional numeric result into a `Money` under a named rounding policy (§13). |
| **Public locator** | ADR-0001 §3's user/public-addressable object identifier: `PublicId`. |
| **External contract identifier** | ADR-0001 §3's machine-to-machine identifier chosen and documented by an adapter (`sku_code`, `gtin`, provider `external_id`, …). |
| **Internal identifier** | The compact `bigint` PK. A storage detail (master `# 5.1`). |
| **Message identity** | Item 8 §9's `event_id`: the identity of one durable asynchronous message instance. |
| **Value space** | The set of representable values (here: standards-conforming UUIDv7 values). Two semantic types may share one value space and remain distinct types (§34). |

---

# PART A — `Money`

## 4. The semantic shape

The frozen semantic value is exactly two things, and nothing else:

```text
Money
    minor    : integer   — a count of minor currency units
    currency : currency  — an explicit, canonical currency code
```

| # | Rule |
|---|---|
| MS1 | `Money` is an **immutable value object**. Item 4 §7.1's baseline applies: frozen, slotted, constructed by keyword. The master `# 5.3` snippet's positional construction is illustrative code, not a construction contract. |
| MS2 | `minor` means **minor currency units**. A `Money` never holds a major-unit amount, a scaled decimal, a string, or a "units and cents" pair. |
| MS3 | `currency` is a **mandatory field with no default**. There is no currency-less `Money`, no partially constructed `Money`, and no sentinel currency. |
| MS4 | `Money` carries **no third field**: no exponent, no locale, no formatting hint, no price list, no tax flag, no VAT-inclusive marker, no store, no rounding policy, no provenance. A caller needing any of those composes them beside `Money`, in the owning module's own type. |
| MS5 | `Money` is **multi-currency by construction**, even though the initial storefront trades primarily in MDL. `100.00 MDL → Money(minor=10000, currency="MDL")` is an *example*, not a definition, and no MDL-specific behaviour, constant or default exists anywhere in the primitive (A71). |
| MS6 | `Money` is **total and pure** in the item 4 §7.3 sense: no I/O, no database access, no network, no global state, no clock, no locale lookup, no caching. |

---

## 5. Integer discipline

| # | Rule |
|---|---|
| IG1 | `minor` is an **integer count**. Its admissibility is checked by **exact type**, not by `isinstance` — the master `# 5.3` guard `type(self.minor) is not int` is preserved precisely because of what it excludes. |
| IG2 | **`bool` is not a money integer.** That `bool` subclasses `int` in Python is a language accident, not a monetary fact. `Money(minor=True, …)` is rejected as primitive misuse, not silently read as `1`. |
| IG3 | **No `float` may be a money amount, ever** — not in construction, not in arithmetic, not in a comparison, not in a serialized payload, not in a fixture (§15). |
| IG4 | **No binary floating-point value appears anywhere in a money contract**, including a JSON number that a decoder would materialise as a float (§18). |
| IG5 | **There is no approximate monetary comparison.** `19.99 ≈ 20.00` has no legal encoding. No epsilon, tolerance, `math.isclose`, "within one minor unit" or rounding-before-comparing exists in any money path (§19, A73). |
| IG6 | `Money` equality is **exact** (§35). |
| IG7 | `Money` has **no maximum or minimum value in the primitive**. Range is a persistence and field-level concern (§17 PS5), not a `core` invariant. |

---

## 6. Currency semantics

| # | Rule |
|---|---|
| CU1 | The currency value is **explicit, immutable, canonical uppercase, serialization-neutral and vendor-neutral**. |
| CU2 | Where the platform deals in fiat currencies the code is an **ISO-4217 alphabetic code**. No provider-specific currency spelling, numeric ISO code, symbol (`L`, `€`), locale tag or ad-hoc abbreviation is a currency value in a contract. |
| CU3 | **`core` validates the currency structurally, not by registry membership.** The structural rule is: exactly three ASCII letters `A`–`Z`. `core` does **not** hold, embed, download or depend on an ISO currency list, and it does not depend on a currency library. |
| CU4 | **Which currencies the platform may actually trade in is an application/domain policy**, held above `core` by the module that owns the decision (price lists, delivery tariffs, payment methods). A boundary or domain check rejects an unsupported-but-structurally-valid currency as a *business* or *boundary input* failure — never as a `core` failure. This is the direct consequence of ADR-0004 §2: `core` is mechanism-shaped and must not carry periodically changing external data. |
| CU5 | A `Money` **is constructed already canonical**. A non-canonical spelling (`"mdl"`, `" MDL"`, `"Mdl"`) is rejected as primitive misuse; case normalisation and trimming are explicit boundary work, so that one currency never acquires two spellings and therefore two cache keys, two group-by buckets or two equality classes. |
| CU6 | **No currency is ever inferred.** Not from locale, not from the user, not from the store, not from the request, not from the session, not from the provider, not from an environment variable, not from a settings default, and not from "MDL because Moldova". A money amount whose currency had to be guessed is not a `Money` (A72). |
| CU7 | The invariant, stated once: **an amount without a currency is not money.** Any signature, DTO field, payload field, column pair or provider mapping that carries an amount must carry its currency explicitly, or the currency must be structurally fixed and documented by the owning aggregate (§17 PS3). |

---

## 7. Zero and the aggregation trap

| # | Rule |
|---|---|
| ZR1 | **Zero is currency-bearing.** `Money(minor=0, currency="MDL")` and `Money(minor=0, currency="EUR")` are different values and are **not equal** (§35 EQ2). There is no universal monetary zero. |
| ZR2 | **Aggregating an empty collection requires an explicit currency.** Summing zero `Money` values must yield a currency-bearing zero supplied by the caller, never a bare integer `0` and never an arbitrary "first currency seen". A naive `sum()` over a possibly empty sequence of `Money` is a defect (A74, C104). |
| ZR3 | Aggregating a **non-empty** collection follows §8: every element must share one currency, and a mixed-currency collection is rejected rather than partitioned, coerced or summed on the left operand's currency. |

---

## 8. Same-currency arithmetic

| # | Rule |
|---|---|
| AR1 | **Addition and subtraction are legal only when the currencies match exactly.** `Money(100, "MDL") + Money(50, "MDL") → Money(150, "MDL")`. |
| AR2 | **Cross-currency arithmetic without an explicit conversion is invalid.** `Money(…, "MDL") + Money(…, "EUR")` is rejected. It is never silently converted, never resolved by "take the currency from the left operand", never resolved by a configured base currency, and never resolved by dropping one side. |
| AR3 | Addition, subtraction and negation are **exact**: they cannot create a fractional minor unit and therefore take **no** rounding policy (§13 RP3). Requiring one there would be noise that trains callers to pass a policy without thinking. |
| AR4 | **Multiplication by a dimensionless integer count** (a line quantity) is exact and legal. Multiplication by a `Decimal` ratio, a percentage or a rate is **fractional-capable** and is not an operator on `Money`; it goes through §13's named materialisation. |
| AR5 | **Division is not an operator on `Money`.** Splitting an amount is proportional allocation — a fractional-capable operation with a remainder-distribution rule that belongs to the owning domain (§14 HR4), not a `/` on a primitive. |
| AR6 | The result of a legal arithmetic operation on `Money` is a `Money` **of the same currency**. No operation on `Money` may return a bare integer, a `Decimal`, a float or a currency-less amount. |
| AR7 | Mixing a `Money` with a bare number in an arithmetic expression (`Money + 100`, `Money + Decimal("1.5")`) is **rejected as primitive misuse**. There is no implicit promotion of a bare number to a `Money`, because promotion would have to invent a currency (CU6). |

---

## 9. Ordering — currency-scoped and partial

This is the one place item 11 departs from the master's illustrative code, and it is the subject of
**[ADR-0012](../../adr/0012-money-currency-scoped-partial-order.md)**.

| # | Rule |
|---|---|
| OD1 | **Ordered comparison of money is meaningful only within one currency.** `<`, `<=`, `>`, `>=`, `min`, `max` and sorting are defined for two `Money` values **iff** their currencies are equal. |
| OD2 | **A cross-currency ordered comparison without an explicit conversion is invalid** and is rejected loudly at the point of comparison. It never returns `False`, never returns `True`, never falls back to comparing `minor` alone, and never falls back to comparing the currency code as text. |
| OD3 | **`Money` must not acquire an automatic, dataclass-generated total ordering.** A generated ordering over the field tuple `(minor, currency)` would make `Money(100, "EUR") < Money(200, "USD")` legal and true, comparing 1.00 EUR against 2.00 USD as though the codes were commensurable — and would make it legal *silently*, at every `sorted()`, `min()`, `max()`, `heapq` and `bisect` call in the platform. Master `# 5.3`'s illustrative `order=True` is therefore **not** adopted. A dedicated static check exists for exactly this shape (A75), because it is a one-word regression that no ordinary review notices. |
| OD4 | `Money` is therefore **partially ordered**: totally ordered within each currency, incomparable across currencies. Any algorithm that requires a total order over a mixed-currency collection is stating a business requirement (a conversion) that it must satisfy explicitly (§20). |
| OD5 | **Equality is unaffected and remains total**: any two `Money` values may be compared for equality, and the answer is exact (§35 EQ1). Equality answers "is this the same amount of the same currency"; ordering answers "is this more money", and only the second question needs a common unit. |
| OD6 | Sorting a **mixed-currency** collection is not a `core` concern and has no default: the owning module either groups by currency and sorts within each group, or converts explicitly (§20) and sorts the converted values, and says which it did. |
| OD7 | An ordered comparison against a **bare number** (`Money > 0`) is rejected for the same reason as AR7. "Is this positive" is expressed against a currency-bearing zero (`Money > Money(minor=0, currency=…)`), which keeps CU7 intact. |

---

## 10. Sign: a field invariant, never a primitive invariant

| # | Rule |
|---|---|
| SG1 | **A generic `Money` may be positive, zero or negative.** Refunds, chargebacks, credit notes, adjustments, corrections and accounting deltas all need signed amounts, and a primitive that forbade them would be routed around within one phase. |
| SG2 | Whether a **specific** field, parameter, column or payload value must satisfy `>= 0` or `> 0` is an invariant **of that field**, declared and enforced by its owning module — in the domain's own validation, in the DTO's `__post_init__`, and in a PostgreSQL `CHECK` where the value is durable (§17 PS4). |
| SG3 | Examples of the split, none of which is decided here: a catalog/pricing price is expected to be non-negative; a refund request amount is expected to be strictly positive; a manual accounting adjustment is legitimately signed; a discount is expressed with a sign convention its owner states rather than one `core` imposes. |
| SG4 | **No sign policy enters `core`.** `core.Money` has no `assert_non_negative`, no `abs_or_raise`, no "prices must be positive" helper, and no per-field sign registry (OW4, A70). |
| SG5 | Negation is exact and legal (AR3). It is the mechanism by which a domain expresses a reversal; it is not evidence that reversals are a `core` concept. |

---

## 11. Boundary conversion into `Money`

| # | Rule |
|---|---|
| CV1 | **Conversion from any non-minor-unit representation into `Money` is explicit boundary conversion**, performed by an explicitly named conversion path — never by a constructor overload, never by an implicit coercion, never by a codec that "knows what to do". |
| CV2 | There is **no implicit constructor** from `float`, `Decimal`, `str`, a JSON number, a provider amount object, or a major-unit numeric pair. Master `# 5.3` states this; item 11 scopes it to every representation, not only the two the master names. |
| CV3 | An explicit conversion must know, as inputs it is given rather than values it discovers: **the source value**, **the currency** (CU6 — never inferred), **the currency's minor-unit scale** (§12), and **the rounding policy** to apply if the source cannot be represented exactly in minor units (§13). |
| CV4 | **A conversion that is exactly representable still names its policy.** `Decimal("100.00") → 10000` for a two-exponent currency needs no rounding, but the call site does not get to omit the policy on the grounds that *this* value happens to be exact — otherwise the omission survives until the first value that is not, in production (C107). |
| CV5 | **There is no global "just round it" helper**, no module-level default policy, no settings-driven default, and no per-currency implicit default. A conversion site that has not named a policy does not compile past review and does not pass A79. |
| CV6 | Conversion **out** of `Money` for display or for a provider is equally explicit and equally located: `Money` never renders itself, never formats itself, never localises itself and never chooses a separator. Rendering is transport work (§18, §36). |
| CV7 | A conversion path is **deterministic and pure**: the same source value, currency, scale and policy always produce the same `Money` (C108). It reads no clock, no locale, no request and no configuration. |

---

## 12. Currency exponent is metadata, not a Money field

| # | Rule |
|---|---|
| EX1 | **Money representation and currency exponent/formatting metadata are two different things.** Once a `Money` exists it already holds minor units, and every exact operation on it (§8) is exponent-independent. |
| EX2 | The exponent is needed **only at boundaries**: parsing a major-unit decimal, formatting for display, mapping a provider amount encoding, FX conversion, and materialising a fractional result back into minor units. |
| EX3 | **"Two decimals" is not hard-coded into the primitive.** MDL uses a two-digit minor unit; that is a fact about MDL, not a law of currencies, and a platform that bakes it in breaks the first time it touches a zero- or three-exponent currency. No `/ 100`, `* 100`, `Decimal("0.01")` or `round(x, 2)` is admissible as a general money mechanism (A76). |
| EX4 | **No live external dependency is admitted for exponent lookup**, in Phase 0 or after it: no network call, no runtime registry fetch, no vendor service. Item 11 freezes the *requirement* that an exponent source exists and is explicit. |
| EX5 | The concrete Phase-1 source — a small checked-in static table owned by the money boundary, or an approved library pinned by the repository's lockfiles — is **deferred to Phase 1**, bounded by EX4, by CU3 (`core` holds no currency registry as policy) and by the current-code rule in `CLAUDE.md`. |
| EX6 | Whatever the source, the exponent is **passed into** a conversion (CV3), not discovered inside `Money`. `Money` gains no lookup, no import and no dependency because of it. |

---

## 13. `RoundingPolicy`

Master `# 5.3` requires that the input boundary use "an explicit factory with a `RoundingPolicy`",
and master `# 25` Phase 1 lists `Money/RoundingPolicy` as one deliverable. Item 11 freezes the
mechanism's architectural role and deliberately stops there.

| # | Rule |
|---|---|
| RP1 | **There is no implicit rounding policy anywhere.** No default argument, no module default, no settings value, no per-currency default, no "the obvious one". |
| RP2 | **Every fractional-capable operation names its policy explicitly** at the call site: major-unit parsing, percentage/ratio application, FX conversion, proportional allocation, averaging, and any other operation that can produce a non-integral minor amount. |
| RP3 | **Exact operations take no policy** (AR3). Adding a policy parameter to `Money + Money` would be ceremony that devalues the parameter where it matters. |
| RP4 | A policy value **maps deterministically to one well-defined decimal rounding rule**. The reference semantics are the standard decimal rounding modes; given the same fractional input and the same policy, the materialised minor amount is always identical, on every machine, in every process (C108). |
| RP5 | `RoundingPolicy` is a **mechanism vocabulary, not a business vocabulary**. A member is named for the arithmetic rule it applies, never for the business step that happens to use it: `PRICE_ROUNDING`, `VAT_ROUNDING`, `PROMO_ROUNDING`, `DELIVERY_ROUNDING` and their kin are forbidden members, because they would smuggle policy into `core` against ADR-0004 §2 and OW4 (A70, A77). |
| RP6 | **Which policy applies at a given business step is decided by the owning domain or application module**, stated in that module's contract and covered by that module's tests. `core` supplies the vocabulary and the deterministic arithmetic; it never chooses. |
| RP7 | **The concrete initial member set is deliberately not frozen here.** Freezing an enumeration in Phase 0 would either over-commit (a member no domain ever selects, kept forever by the compatibility policy) or under-commit (a missing member added under pressure during a pricing phase). What is frozen is stronger and smaller: a policy is mandatory, has no default, is a pure decimal rounding rule (RP5), and is deterministic (RP4). The member list is Phase 1's, and each domain's phase justifies the members it actually needs. Half-even, half-up, down and up are the expected shape of that list, named here as an expectation and not as a decision. |
| RP8 | A policy is **never inferred from the value**, never chosen by the currency, never chosen by the sign, and never varied to make a total reconcile. A total that only balances under a value-dependent policy is a bug in the allocation rule (§14). |

---

## 14. No hidden rounding, no double rounding

| # | Rule |
|---|---|
| HR1 | **A business calculation states where materialisation happens.** The step that turns a fractional numeric result into minor units is a named, single, visible point in the flow — not an emergent property of which helper returned what. |
| HR2 | **Round → calculate further → round again is forbidden as an accident.** A chain of helpers that each return `Money` silently rounds at every hop; that is the classic source of a total that disagrees with the sum of its lines by a few minor units, and it is a defect regardless of how small the discrepancy is. |
| HR3 | **Intermediate values may stay exact.** Rates, ratios, coefficients, percentages and multi-step derivations may be carried as exact decimal arithmetic for as long as the owning domain requires; only the **materialisation** into minor units is explicit and deterministic (§16). |
| HR4 | **Line-level versus total-level rounding is a domain decision.** A domain may legitimately require per-line materialisation then summation, or total-level materialisation, or a proportional allocation with a stated remainder rule. Whichever it requires, it **names** the choice in its own contract and **tests** it there. `core` does not choose between them and offers no helper that implies a choice (A70, V88). |
| HR5 | **A materialised `Money` is not re-materialised.** Once an amount is minor units, further exact arithmetic on it (§8) introduces no rounding, and no code path may "re-round to be safe". |
| HR6 | Item 5's frozen commercial snapshot is unaffected and reinforced: the amounts written into an `Order` at placement are materialised once, inside the placement transaction, and are never recomputed afterwards (ADR-0007, item 5 §13). |

---

## 15. The float firewall

| # | Rule |
|---|---|
| FL1 | **No `float` enters or leaves the money mechanism.** This covers construction, arithmetic, comparison, aggregation, conversion, serialization, deserialization, provider mapping, discount and tax calculation, database columns, test fixtures and snapshots. |
| FL2 | A test fixture or factory that expresses an amount as `19.99` is a defect even though it never reaches production: it teaches the shape, and it eventually gets copied into code that does. Money in fixtures is minor units or an explicitly converted decimal string (A78). |
| FL3 | **A JSON monetary amount is never a JSON float.** §18 fixes the external representation; a decoder that would materialise a monetary number as a binary float is not an admissible codec for money. |
| FL4 | **A provider that supplies a floating amount is normalised at the integration boundary**, from a lossless representation — the provider's integer minor-unit field where one exists, otherwise its textual decimal field parsed exactly. A `Money` is never constructed from the binary float itself, and never from a float that has been "cleaned up" by rounding it first. |
| FL5 | Where a provider offers **only** a binary float and no lossless alternative, that is an integration-contract problem recorded and handled in that provider's own phase (an exact-comparison failure per §19, reconciled rather than tolerated). It is never solved by relaxing FL1 or by introducing an epsilon (IG5). |
| FL6 | `float` remains perfectly legal for values that are **not money** and where exactness is not the contract — physical dimensions rendered for display, geographic coordinates (master `# 15.2` fixes those as `Decimal(9,6)` anyway), performance metrics. The firewall is around money, not around the codebase. |

---

## 16. `Decimal`

| # | Rule |
|---|---|
| DE1 | `Decimal` is **permitted and expected** for: exchange rates, ratios, coefficients, percentages, major-unit parsing and rendering, and intermediate exact decimal calculation where a domain requires it (master `# 5.3`, item 4 D8, item 7 FT7/DC8). |
| DE2 | `Decimal` is **not** the representation of a persisted or public commercial money value. An arbitrary-precision decimal amount is not commercial truth. |
| DE3 | At a durable or public money boundary the shape is exactly: `Decimal → explicit conversion + currency + RoundingPolicy → Money(minor, currency)` (§11, §13). |
| DE4 | **No raw `Decimal` monetary value may bypass that conversion and become commercial truth** — not into a database column, not into an `Order` snapshot, not into a public DTO field, not into an event payload, not into a provider request body (A79, C110). |
| DE5 | A `Decimal` that is a **rate or ratio** may itself be persisted or carried in a contract where that is what the field means (item 7's `DecimalRangeFacet` bounds, a promotion percentage). Such a field is not money and is not typed `Money`; the distinction is in the field's meaning, not in its numeric shape. |
| DE6 | Decimal context — precision, traps, the global context object — is never relied upon implicitly for a money conversion. A conversion's determinism (CV7, RP4) must not depend on ambient process state. |

---

## 17. Persistence

| # | Rule |
|---|---|
| PS1 | **Critical monetary database state is stored as integer minor units**, in an integer column, together with an explicit currency where the currency is not structurally fixed by the owning aggregate or price list. Master `# 5.3` already names the column shape family (`price_minor`, `regular_price_minor`, `discount_minor`, `delivery_minor`, `total_minor`, `payment_amount_minor`, `tradein_value_minor`, `refund_minor`); item 11 designs none of those schemas. |
| PS2 | **Forbidden as the canonical stored money amount**: `float`, `real`, `double precision`; a `numeric`/`decimal` column standing in for the amount; a text amount; a JSON number inside a payload column used as commercial truth. |
| PS3 | Where the currency is **structurally fixed** — a price list, tariff table or aggregate that is single-currency by definition — the currency may live once on the owning row rather than on every amount, and the owning schema **documents** that fixing. Silence is not fixing: a bare `*_minor` column with no reachable currency is a defect (V85). |
| PS4 | **Sign and range constraints are the owning schema's**, expressed as PostgreSQL `CHECK` constraints beside the column (`>= 0`, `> 0`, or genuinely signed), per §10 and master `# 5.4`'s "DB-инварианты как последний рубеж". |
| PS5 | Whether a specific column is `integer` or `bigint` is the **owning schema's decision**, taken on a proven range with the aggregate's realistic maximum in mind. Item 11 fixes neither, and the primitive imposes no bound (IG7). |
| PS6 | A stored amount is read back into a `Money` by pairing it with its currency at the module boundary. A repository, selector or serializer that returns a bare `*_minor` integer into application or domain code, where the semantic value is money, is a defect (A81). |
| PS7 | Item 11 authors **no migration, no model, no field class and no constraint**. PS1–PS6 are the rules that later phases' schemas are checked against. |

---

## 18. `Money` in contracts and on the wire

| # | Rule |
|---|---|
| DT1 | Where a domain or application public contract exposes money **semantically**, the type is `Money` — not `price: int`, not `price_minor: int`, not `price: Decimal`, not `price: float`. This is item 4 D8 and item 7 DC8, now enforceable (A81). |
| DT2 | The exception is narrow and one-directional: an `interfaces/*` module producing a **transport representation** may convert a `Money` into the JSON, HTML or form shape that transport requires. That conversion changes the representation, never the semantic value, and never travels back inward — an interface never hands a bare amount to an application or a domain (item 3 §4.4, item 4 §6). |
| DT3 | An `integrations/*` adapter maps `Money` to and from a **vendor** amount encoding inside its own boundary, in both directions, and the vendor encoding never leaks inward under a neutral field name (item 3 V3, item 8 PD6). |
| DT4 | **No single HTTP JSON money shape is frozen here.** Item 7 deliberately left transport representations to the Web and DRF layers, and item 11 does not pre-empt them. |
| DT5 | What **is** frozen for every external representation: it is **exact**, it **never uses a binary floating number**, and it **carries its currency** (or the enclosing contract fixes the currency explicitly and says so). A minor-unit integer plus a currency code, or an exact decimal **string** plus a currency code, both satisfy this; a JSON float does not, under any field name. |
| DT6 | An event payload's money follows item 8 PD9 unchanged: integer minor units plus an explicit currency, never a float, never a bare number. Item 11 adds no envelope field and changes no `schema_version` semantics. |
| DT7 | A `Money` in a public DTO is an allowed field type by item 4 §7.4's table (frozen `core` value type) and needs no exception. |

---

## 19. Provider and payment amount comparison

| # | Rule |
|---|---|
| PV1 | When validating a provider-reported payment, capture, refund or reconciliation amount against internal state, the comparison is **internal `Money` versus the provider amount explicitly converted into `Money`**, and it must match on **both** the exact minor amount **and** the exact currency. |
| PV2 | **No tolerance comparison exists for money.** No epsilon, no `abs(a - b) < ε`, no "within one bani", no percentage tolerance, no rounding both sides before comparing (IG5, A73). |
| PV3 | A currency match is part of the comparison, not an assumption. An amount that matches numerically in a different currency is a **mismatch**, and it is exactly the shape a real integration incident takes. |
| PV4 | The conversion of the provider's encoding into `Money` is **integration-boundary work** owned by that provider's adapter (§18 DT3): which field carries the amount, whether it is minor units or a decimal string, and how the currency is expressed are that provider's protocol facts, decided in the payments/integration phases. |
| PV5 | A mismatch is **never** resolved by adjusting internal state to agree with the provider, and never by widening the comparison. It is a security-relevant integration failure handled by the owning workflow's state machine and reconciliation (item 9's ambiguous-outcome rules, master `# 12`). |
| PV6 | This rule is the enforcement point for the invariant that a client-, session- or provider-supplied total is never authoritative (item 5 IN-trust rules): "never trust client totals" is implemented as an exact `Money` comparison against internally computed truth. |

---

## 20. Exchange rates

| # | Rule |
|---|---|
| FX1 | **`Money` performs no implicit currency conversion**, ever. This is the whole of item 11's FX decision. |
| FX2 | A conversion is a **separate, explicit operation owned by the appropriate business or application policy**, and it takes, as explicit inputs: the source `Money`, the target currency, the rate, the rate's provenance and effective time where business-relevant, and an explicit `RoundingPolicy` (§13). |
| FX3 | **No exchange-rate service, rate table, rate cache or rate provider enters `core`** (OW4). `core` would fail ADR-0004 §2's admission test on the first rate source. |
| FX4 | **No FX mechanism is designed here.** FX is not an MVP requirement, and item 11 deliberately freezes only the negative rule (FX1) plus the shape any future conversion must take (FX2), so that a later FX requirement cannot be satisfied by quietly relaxing AR2 or OD2. |
| FX5 | A cross-currency comparison or arithmetic operation that a caller "solves" by converting **must** do so through FX2's explicit operation, and the converted value's provenance is then that caller's to record. It is never solved inside the primitive. |

---

# PART B — public identity

## 21. The three identity spaces stand

ADR-0001 §3 froze three roles. Item 11 **types** them; it does not renumber, merge or reinterpret
them.

| Space | What it is | Item 11's contribution |
|---|---|---|
| **A — public locator** | The identifier of a platform object that must be externally or user-addressable: URLs, public API payloads, email links, QR links, Track & Trace. | Freezes it as the distinct semantic type `PublicId` over the UUIDv7 value space (§22–§29). |
| **B — external contract identifier** | The stable identifier an integration contract chooses and documents: `sku_code`, `gtin`, a provider `external_id`, a provider order/payment id, an ERP key. It **may or may not** be a `PublicId`. | Freezes that it is **not forced** to become a `PublicId`, and that a foreign UUID never becomes one (§30, §31). |
| **C — internal persistence identifier** | The compact `bigint` PK. Legitimate for internal orchestration, internal joins, internal versioned events and jobs where the already-frozen rules permit (item 4 I4, item 8 PD12). | Freezes that it stays statically distinguishable from `PublicId` and is never serialized outward merely because it was convenient (§27, §30). |

The hard rule across all three is ADR-0001's and stands verbatim: **the internal `bigint` PK must
never be exposed merely as the external contract identifier or as a public locator.**

---

## 22. `PublicId` — semantic shape

| # | Rule |
|---|---|
| PI1 | **`PublicId` is a strongly-distinct, immutable semantic type whose value space is UUIDv7.** It is a type, not a naming convention and not a comment. |
| PI2 | A `PublicId` is **not interchangeable** with, and must not be silently substitutable for: an internal `bigint`, an arbitrary `int`, a provider identifier, a `sku_code` or other business key, an idempotency key, an `EventId`, or a raw unrelated `UUID`. |
| PI3 | **A bare, untyped `UUID` must not appear in a domain or application public signature, parameter or DTO field where the semantic value is a public locator.** `uuid.UUID` as an annotation states "some 128-bit value"; it does not state which identity space the value belongs to, and it is precisely the annotation that lets an `EventId` or a provider UUID reach a locator position (A82). |
| PI4 | The **mechanism** by which distinctness is achieved is Phase 1's, bounded by §23's requirements: it must be a **runtime-distinct immutable value representation** — a frozen validating wrapper value object is the obvious admissible shape, and any other construct is admissible only if it genuinely preserves every frozen immutability, validation, equality, hashing and type-safety property. A bare `typing.NewType` over `uuid.UUID` is **not** admissible on its own, because its runtime constructor returns the underlying value unchanged and therefore cannot satisfy TY5, EQ4 or C127. Item 11 freezes the requirements and this exclusion; it selects no construct. |
| PI5 | `PublicId` is **transport-neutral, framework-neutral and vendor-neutral** (§36). It knows nothing of Django, DRF, HTTP, Celery or any provider SDK. |
| PI6 | `PublicId` carries **no entity type tag** (OW5). There is no `OrderPublicId`/`ProductPublicId` family in `core`; the addressed entity is stated by the field name in the owning contract (item 4 I2). |
| PI7 | **The underlying representation stays UUID.** A `PublicId` — like an `EventId` — may hold a `uuid.UUID` internally, and PI3 does not say otherwise. What is forbidden is a **bare** UUID value serving as the semantic locator or message identity in a contract, a signature or at a runtime boundary. Wrapping a UUID is the mechanism; the bare UUID *as the identity* is the defect. |

---

## 23. Type-safety requirements

The distinction is required **at both levels**: statically, so the type checker reports a
substitution before it ships; and at runtime, so two values over one value space are genuinely
different values rather than the same object under two annotations. Whatever Phase 1 builds must
satisfy all five:

| # | Requirement |
|---|---|
| TY1 | **Statically distinct from `int`.** Passing an internal `bigint` where a `PublicId` is required is a type error the type checker reports, not a runtime surprise (master `# 5.3`'s stated purpose: a bigint and a UUIDv7 must not be confusable in a signature or a URL builder). |
| TY2 | **Statically distinct from a bare `UUID`.** An arbitrary UUID value — a provider's, a legacy system's, a UUIDv4 — cannot occupy a `PublicId` position without an explicit, visible conversion step that performs §29's validation. |
| TY3 | **Statically distinct from `EventId`** (§34). Two identity types over one value space must not be mutually assignable. |
| TY4 | **Validated at construction from untrusted input.** Every path that builds a `PublicId` from external text, an external payload or an external parameter performs §29's parse-and-validate; there is no unchecked cast from external data into the type. Construction from the platform's own storage of its own `public_id` needs no re-validation, because that value was validated when it was created. |
| TY5 | **Runtime-distinct, not merely annotation-distinct.** The semantic type must survive into the runtime value, so that `PublicId(U)` and `EventId(U)` built from the *same* UUID value are different values: they do not compare equal, they hash consistently with that inequality, and neither passes silently through the other's constructor, parser or lookup path (EQ4, C127). **A construct that erases the distinction at runtime therefore does not satisfy this contract**, which excludes a bare `typing.NewType` over `uuid.UUID`: its runtime constructor returns the underlying value unchanged, so two such types produce indistinguishable values with identical equality and hashing. A frozen validating wrapper value object satisfies TY1–TY5; any other construct is admissible only if it genuinely preserves all five together with the immutability and validation rules. Phase 0 selects no construct (PI4). |

---

## 24. Generation

| # | Rule |
|---|---|
| GN1 | Every platform-generated `PublicId` is a **standards-conforming UUIDv7**. |
| GN2 | **No custom UUIDv7 bit layout, timestamp source or entropy scheme is implemented.** The architecture must not depend on a hand-rolled identifier algorithm; Phase 1 selects a standards-conforming implementation compatible with the repository's pinned Python version, following `CLAUDE.md`'s current-code rule (verify the pinned version and consult the official documentation before choosing). |
| GN3 | **Generation is server-side and platform-owned.** A `PublicId` for a platform-owned entity is minted by the platform at creation, inside the transaction that creates the entity, so no entity is ever committed without its locator. |
| GN4 | **A client never chooses the `PublicId` of a newly created platform-owned entity.** A client may *supply* a `PublicId` only to refer to an object that already exists. A future contract that deliberately admits client-supplied creation identity (an upsert-by-client-key shape) would be a new decision requiring its own ADR; none exists. |
| GN5 | **Uniqueness is enforced by the database**, not by generation luck: the `public_id` column is `UNIQUE` on every externally addressable table (ADR-0001 §3, master `# 5.1`). A collision is a constraint violation, not a silently accepted duplicate. |
| GN6 | Generation is **not** an ordering, sequencing or versioning event, no matter how time-ordered the resulting values happen to be (§27). |

---

## 25. Immutability and non-reuse

| # | Rule |
|---|---|
| IM1 | **A `public_id` is immutable for the lifetime of the resource it addresses.** It is assigned once, at creation, and never rewritten. |
| IM2 | A rename, a slug change, a status or lifecycle transition, a category move, a re-import from ERP, a merge of duplicate records, a price change and a translation update all leave the `public_id` untouched. |
| IM3 | **Deleting and recreating a resource produces a new `PublicId`.** The new object is a new object; inheriting the old locator would make two distinct histories share one external identity. |
| IM4 | **A `PublicId` is never recycled** for another object, in any table, at any time. |
| IM5 | **A `PublicId` is never derived deterministically** from an internal PK, an email address, a `sku_code`, a slug, a customer attribute, a provider identifier or any other content. A derived locator leaks its input, becomes enumerable through it, and silently changes identity when the input changes. |
| IM6 | Immutability is a **database-enforceable** property on the owning schema (master `# 5.1` states `public_id` as immutable); which mechanism enforces it is that schema's phase decision, not item 11's. |

---

## 26. `PublicId` is a locator, not a permission

| # | Rule |
|---|---|
| AZ1 | **A `PublicId` is not a secret and not a permission.** Knowing `/order/<public_id>` does not authorize reading that order. |
| AZ2 | Every protected resource is reached through **actor-scoped authorization** — item 4 §11's mandatory explicit actor, and the actor-scoped selectors/policies that `CLAUDE.md` and item 5 already require — or through the **purpose-bound, time-limited signed token** master `# 5.1` already requires for sensitive guest access, with nonce, purpose and `max_age`, consumed or rotated after use. |
| AZ3 | **UUID unpredictability is never access control.** "It is a random 128-bit value, nobody will guess it" is not an authorization argument, and a code path whose only protection is the locator's entropy is a security defect (V96). |
| AZ4 | A `PublicId` never carries a claim, a scope, a role, an expiry or a signature. It addresses; it does not assert. |
| AZ5 | Item 5 AU2 is reinforced: an idempotency-key replay is served only to the same authorized principal, and an order's `PublicId` is never disclosed to another actor on the strength of a key or a locator. |
| AZ6 | Item 6's rule that the storefront projection is never the basis of a security decision is untouched, and item 11 adds no identity-based shortcut around a policy check. |

---

## 27. The embedded timestamp, and non-use as a version

UUIDv7 values embed a time component. That is a property of the encoding and of index locality; it
is **not** information the platform is permitted to read.

| # | Rule |
|---|---|
| TS1 | **The time embedded in a `PublicId` is never authoritative** for `created_at`, `occurred_at`, payment time, order time, event time, or any other business instant. Business timestamps remain explicit, aware-UTC fields (item 4 D7, item 8 §11). |
| TS2 | **No business decision decodes a `PublicId`.** No filter, branch, policy, expiry rule, report boundary, retention rule, reconciliation window or audit conclusion extracts the timestamp bits (A83). |
| TS3 | **A `PublicId` is never an ordering key**: not for event ordering, not for causation, not for replay chronology, not for a business sequence, not for "which happened first". Item 8 §26 already states that no global order exists and that identity is not an ordering key; item 11 does not create one by the back door. |
| TS4 | **A `PublicId` is never a version**: not `source_version`, not an optimistic-lock version, not a storefront projection freshness version, not a schema version, not a business sequence number. Item 10's nine-way distinctness table stands, and **item 12 remains entirely untouched** (A85). |
| TS5 | **Clock behaviour must not affect correctness.** A clock rollback, an NTP step, two identifiers generated within the same millisecond, or generation on two hosts must be incapable of changing any business outcome — which is exactly what TS1–TS4 guarantee by never reading the bits. |
| TS6 | Index locality — the operational reason UUIDv7 is preferred over UUIDv4 — is a **storage property** the platform may benefit from without ever reading the timestamp semantically. Benefiting is allowed; depending is not. |

---

## 28. `PublicId`, the primary key, and pagination

| # | Rule |
|---|---|
| PK1 | The split stands: **`id` is the compact internal PK and FK; `public_id` is the external locator.** Both exist on an externally addressable entity (master `# 5.1`, ADR-0001 §3). |
| PK2 | **Internal `bigint` primary keys and foreign keys are not replaced by UUIDv7.** Item 11 mandates no such migration and no such default. |
| PK3 | **`PublicId` is added where an entity is externally addressable**, not everywhere. A purely internal table needs none, and giving one to every table would be cost without a boundary to justify it (ADR-0001's accepted cost is per externally addressable table). |
| PK4 | A `public_id` column is normally **unique and indexed** for locator lookup (GN5). Which additional indexes an entity needs is its own schema's decision. |
| PK5 | **`PublicId` is not the keyset-pagination tiebreaker**, per master `# 5.1`'s performance rule and item 6/item 7's frozen pagination contract. The stable order uses `(sort_field, id)` with the compact `bigint`. |
| PK6 | A compact internal `bigint` **may travel inside a signed opaque cursor** and nowhere else (item 6 I5, item 7 R4). **Cursor opacity is not weakened**: the cursor exposes no payload, and item 11 defines no cursor codec, field list, signing scheme or page-size limit — all of which remain Phase 4's. |
| PK7 | **UUIDv7's approximate chronological ordering is not an argument for using it as a pagination key** (TS3, TS6). Any claim that it "sorts well enough" is rejected: it would make pagination correctness depend on generation-time clock behaviour, which TS5 forbids. |
| PK8 | Item 11 designs **no table's schema**. PK1–PK7 are the rules those schemas are checked against. |

---

## 29. Parsing and canonical representation

| # | Rule |
|---|---|
| PA1 | Textual input intended to become a `PublicId` must **parse as a valid UUID value**, and must be **UUID version 7**. A structurally valid UUID of another version is rejected (§31). |
| PA2 | The **canonical rendered form** is the standard lowercase hyphenated 8-4-4-4-12 representation. Every outward rendering — URL, API payload, email link, log line, cache key — uses exactly that form. |
| PA3 | At a **public input boundary**, only the canonical form is accepted. Uppercase hex, brace-wrapped, `urn:uuid:`-prefixed and unhyphenated 32-character spellings are **rejected**, not normalised. Accepting several spellings would give one resource several external identities, and therefore several canonical URLs, several cache keys and several crawl targets — which item 7's canonicalization rule exists to prevent. |
| PA4 | **Malformed input is rejected at the interface boundary**, as boundary input validation, before any selector, policy or domain call runs (§37). A malformed locator never becomes a database query. |
| PA5 | **The semantic type stays transport-neutral.** Parsing an HTTP path segment, a query parameter, a form field or a JSON string is `interfaces/*` work; parsing a vendor payload field is `integrations/*` work. `PublicId` itself has no transport awareness (PI5). |
| PA6 | Round-tripping is exact and idempotent: rendering a `PublicId` and parsing the result yields the same value, and the rendered form of a parsed canonical value is byte-identical to the input (C119). |

---

## 30. Logging and diagnostics

| # | Rule |
|---|---|
| LG1 | A `PublicId` is **intentionally usable as a locator and correlation reference in ordinary logs, traces and operator tooling** where the addressed resource is not itself sensitive. That is much of the point of having a non-enumerable external identifier. |
| LG2 | It is **not a secret** (AZ1), so logging one is not a credential leak — and equally, **logging one is not protected by anything**, so it must not be treated as though redaction had been applied. |
| LG3 | **Logging a `PublicId` does not discharge PII or redaction policy.** The resource's sensitivity, not the identifier's shape, determines whether a given log context is appropriate, what may accompany the identifier, and how long the record is retained (master `# 21`, `# 23`, and the privacy phases). |
| LG4 | **Not every UUID is automatically harmless public data.** A UUID that is in fact a signed-token component, a session artefact, a provider secret or a value from which a subject can be re-identified is classified by what it *is*, never by the fact that it is 128 bits of hex. |
| LG5 | Item 10's rules stand unchanged: trace metadata carries no PII, `request_id` encodes no identity, and diagnosis never justifies raw payload logging. |

---

## 31. External integrations

| # | Rule |
|---|---|
| EI1 | ADR-0001 §3 stands: **an external integration contract explicitly chooses and documents its stable identifier.** |
| EI2 | **No provider, ERP or CRM contract is forced to speak `PublicId`.** Requiring it would be an anti-corruption violation in the wrong direction, imposing our identity model on a vendor's. |
| EI3 | Adapters **translate** between the external contract identifier and internal identity according to the already-frozen ownership rules: `application/erp_sync` owns the persistent `provider + external_id ↔ internal entity` mapping (ADR-0005 §4), and `integrations/*` is the anti-corruption boundary (ADR-0001, item 3 §6). |
| EI4 | **An internal `bigint` is never simply serialized and renamed `external_id`.** Item 4 I3 and ADR-0001's hard rule are the same rule seen from two sides. |
| EI5 | **A foreign UUID does not become a `PublicId` merely because it parses.** A provider UUID, a legacy system UUID, a UUIDv4, an ERP UUID and an ERP-supplied UUIDv7 all remain the contract identifier type owned by their boundary. PA1's version check catches most of them mechanically; EI5 covers the rest, including a foreign UUIDv7 that would pass every structural test (V99, C123). |
| EI6 | Deliberately migrating an external identifier into a platform resource locator is a **schema and contract decision** taken by the owning module, with its own migration and its own review. It is never an implicit consequence of a value having the right shape. |
| EI7 | Item 8 ID6 stands: a provider's `external_event_id` and the internal message identity are **two identity spaces**, and neither substitutes for the other. `integrations/*` cannot reach `core.events` at all (item 3 §4.5, item 8 R7), so this separation is structural rather than merely stated. |

---

# PART C — message identity

## 32. Resolving item 8 ID7 and item 10 CZ4

**What the frozen documents actually require — verified before deciding.**

- Item 8 **ID7**: "`event_id` is conceptually the project's UUID-based identity primitive
  (`PublicId`/UUIDv7, master `# 5`). **Item 11 owns the implementation**; item 8 requires only that
  the value be a stable, globally unique, non-sequential, opaque UUID assigned once. No sequential
  bigint is acceptable here."
- Item 10 **CZ4**: `causation_event_id`'s "semantic type is **the same as `event_id`'s**. The
  concrete representation is **item 11's**."
- Item 10 **R16**, **A67**, **DX4**, and ADR-0011 §"not frozen": the concrete `event_id` type is
  item 11's and item 10 invents none.

So the binding requirements are: a UUID value space, stable, globally unique, non-sequential,
opaque, assigned once, never a sequential bigint. **No frozen artifact requires the `PublicId`
semantic type itself.** ID7's parenthetical names the project's UUID *primitive* as the conceptual
reference and then explicitly delegates. Item 11 is therefore free to choose, and chooses:

| # | Decision |
|---|---|
| EV1 | **`EventId` is a semantic type distinct from `PublicId`**, over the **same UUIDv7 value space**, resolving ID7 and CZ4. |
| EV2 | The reason is semantic, not stylistic: **a durable message identity is not an externally addressable domain resource.** A `PublicId` addresses a thing a user or a partner can ask for; an `EventId` identifies an emission of a fact inside the platform's own asynchronous machinery. They have different lifecycles (one is created with an entity and outlives it; the other is created with a message and is retained per retention policy), different exposure rules (item 8 PD14 governs one; ADR-0001 §3 governs the other), and different consumers. |
| EV3 | The practical reason is confusion cost: with one type, `order_public_id` and `event_id` become mutually assignable, and nothing but a field name prevents an event identity reaching a URL builder or an order locator reaching a dedupe key. That is exactly the confusion master `# 5.3` created `PublicId` as a distinct type to prevent, applied to a second identity space. |
| EV4 | **Both share one low-level UUIDv7 generation and parsing mechanism** inside `core` (§34), so there is one algorithm, one library decision and one validation implementation — and two types. |
| EV5 | This is recorded in **[ADR-0013](../../adr/0013-event-id-distinct-identity-type.md)**. It **clarifies** ID7's deferral rather than amending it: every ID7 requirement is satisfied, and **ADR-0009, ADR-0010 and ADR-0011 are neither edited nor superseded**. |

**No alternative model was adopted.** For the record, the two rejected alternatives and why: reusing
`PublicId` for `event_id` fails EV2/EV3 and would make item 8 PD14's "externally consumed messages
carry `PublicId` locators only" ambiguous, since the envelope identity would then be indistinguishable
from a payload locator; and using a bare `UUID` for `event_id` fails ID7's own "typed distinctly
enough" spirit, PI3, and TY2.

---

## 33. `EventId` semantics

Every rule below restates an already-frozen item 8/9/10 rule in terms of the now-named type, under
the `MI` (message identity) prefix. **None of items 8–10 is reopened.**

| # | Rule |
|---|---|
| MI1 | An `EventId` is a **globally unique, immutable UUIDv7 message identity**, assigned once by the producer at emission, in the same transaction that writes the message (item 8 ID1). |
| MI2 | It **survives retry, redelivery and replay unchanged** — relay retries, broker redelivery, worker retries and terminal-state replay all carry the original identity forward (item 8 ID3, item 9's replay model, item 10 TY2/RP1). |
| MI3 | A **genuinely new** business fact gets a **new** `EventId`, even when the payload is byte-identical to an earlier one (item 8 ID4). |
| MI4 | A dual-published version during a consumer-first migration follows **item 8 §19's identity rule as written**; item 11 adds nothing to it. |
| MI5 | It is **not a broker or transport delivery identifier**: not a Celery task id, not an AMQP delivery tag, not a Redis stream id, not an Outbox row primary key, not a retry counter (item 8 ID5). |
| MI6 | It is **not a `PublicId`** (EV1) and never occupies a public-locator position. |
| MI7 | It is **not a `source_version`**, not an ordering key, not a sequence number, not a version of anything (item 8 §26, item 10's distinctness table, TS3/TS4). Item 12 stays untouched. |
| MI8 | It is **not an authorization token**. Holding an `EventId` grants nothing, exactly as AZ1 states for `PublicId`. |
| MI9 | It is **not an idempotency key for an arbitrary HTTP command.** Master `# 5.2`'s `IdempotencyKey` is a separate, scoped mechanism with its own uniqueness and its own fingerprint rules (item 5 §16). An `EventId` is used for consumer-side message identity and effect idempotency inside the asynchronous machinery (item 8 §21); a client's HTTP idempotency key is neither an `EventId` nor a `PublicId`, and item 11 does not type it. |
| MI10 | **`causation_event_id` is exactly this type** (item 10 CZ4). Item 10's rules for it are unchanged: one hop, never self-referential, never ordering, never authorization, never idempotency, never a foreign key, and expected to dangle once the parent partition is archived. |
| MI11 | It is **never reused, never regenerated for the same logical fact, and never derived from mutable payload content** (item 8 ID8) — the direct analogue of IM4/IM5. |
| MI12 | A **provider `external_event_id` is a different identity space** and never becomes an `EventId` (item 8 ID6, EI7). |

---

## 34. One value space, two semantic types

| # | Rule |
|---|---|
| TX1 | The architectural principle, stated once: **the same physical representation does not imply the same semantic identifier type.** UUIDv7 is a value space; `PublicId` and `EventId` are two disjoint semantic uses of it. |
| TX2 | The **UUIDv7 generation, parsing and version-validation mechanism is `core`-internal**. It is shared by both identity types (EV4), so there is one algorithm and one standards-conforming library decision (GN2). |
| TX3 | **That mechanism is not an exported surface of `core` for any package family.** No `domains/*`, `application/*`, `interfaces/*`, `integrations/*`, `tasks/*` or `config/*` module imports a generic UUID utility to mint or accept an identity; each imports the **semantic type** it actually needs. `core → core` is `SELF ONLY` and already legal (item 3 §4.1), so nothing in the matrix changes. |
| TX4 | The reason TX3 is a rule and not a preference: a generic exported `new_uuid7()` / `parse_uuid7()` pair would let every call site produce a value that fits *both* types, and the distinction would evaporate at exactly the boundaries where it matters. A shared mechanism is fine; a shared **public** mechanism is not. |
| TX5 | **`PublicId` and `EventId` are not mutually assignable** (TY3), and two values whose underlying UUID bytes are identical are **not** semantically interchangeable — **statically or at runtime** (TY5, §35 EQ4). A shared low-level mechanism (TX2) produces the UUID *value*; each semantic type is what carries that value onward, so the sharing never collapses the two into one runtime representation. |
| TX6 | **Placement, restated for the record:** `PublicId` with the identity primitives already allowlisted as `core.public_id` (item 3 §4.2–§4.7); `EventId` with the envelope mechanism already allowlisted as `core.events` (OW3). `core.events` being `FORBID` for `integrations/*` is a feature, not a gap: an adapter has no business minting internal message identity, and item 8 ID6/EI7 already says so. **No allowlist entry is added, removed or widened** (OW6). |

---

# PART D — cross-cutting

## 35. Equality and hashing

| # | Rule |
|---|---|
| EQ1 | **`Money` equality:** two values are equal **iff** `minor` is equal **and** `currency` is equal. Exact, total, and defined for every pair (OD5). |
| EQ2 | Zero is not universal: `Money(0, "MDL") != Money(0, "EUR")` (ZR1). |
| EQ3 | **Identity equality:** two `PublicId` values are equal iff they hold the same UUID value; two `EventId` values likewise. |
| EQ4 | **Cross-type equality is not equality.** A `PublicId` and an `EventId` whose underlying UUID bytes coincide are **not** equal and are **not** interchangeable (TX5). The three cases together: `PublicId(U) == PublicId(U)` → true; `EventId(U) == EventId(U)` → true; `PublicId(U) == EventId(U)` → **never** true. Whether the cross-type comparison is a type error or simply `False` is Phase 1's implementation detail; what is frozen is that it is never `True`, that the distinction is a **runtime** property of the values and not only of their annotations (TY5), and that no code path may rely on such a comparison at all (C127). |
| EQ5 | All three types are **hashable**, consistently with their equality, so they may be dictionary keys and set members. The requirement is the ordinary equality/hash contract — equal values hash equally — and nothing more: hash **collision** between unequal values, including across the two identity types, is legal and expected, and correctness never rests on its absence. |
| EQ6 | **No ordering is defined for `PublicId` or `EventId` as a business contract.** They may be sorted for a deterministic test fixture or a stable rendering, and that is a presentation convenience with no business meaning; no business rule, sequence, precedence, tie-break or "which came first" may rest on it (TS3, MI7). |
| EQ7 | `Money` ordering is §9's partial order and nothing else. |

---

## 36. Serialization neutrality

| # | Rule |
|---|---|
| SN1 | `Money`, `PublicId` and `EventId` depend on **no** Django model field, DRF serializer field, HTTP request/response object, Celery construct, provider SDK, template engine or cache client. Item 4 D2/D3 applies to all three. |
| SN2 | They are usable by every package family the existing `core` allowlists permit — and by no other, exactly as those allowlists already state (§2). |
| SN3 | **Transport conversion belongs at `interfaces/*`**; **vendor conversion belongs at `integrations/*`**. Neither conversion travels inward, and neither changes the semantic value (DT2, DT3, PA5). |
| SN4 | A `Money`, `PublicId` or `EventId` **never serializes itself**: no `to_json`, `from_json`, `__json__`, DRF field, schema decorator or framework metadata lives on the type (item 4 D3). |
| SN5 | An event payload's representation of these values follows item 8 §29's canonical deterministic serialization; item 11 chooses no serializer, no format and no library. |
| SN6 | Because the types are Django-free and pure Python, `integrations/*` keeps satisfying master `# 4`'s requirement that it be importable without the Django app registry (item 3 §4.5), with `core.money` and `core.public_id` in its allowed subset exactly as already frozen. |

---

## 37. Errors and their classification

Item 11 introduces **no new platform-wide public error category** and requests **no** `core.errors`
extension. ADR-0006's closed category set stands unchanged. The classification is instead a mapping
onto the categories that already exist:

| Situation | Classification | Where it is raised / handled |
|---|---|---|
| Malformed UUID text, wrong-version UUID, non-canonical spelling, missing currency in an external payload, unparseable amount | **Boundary input validation** | `interfaces/*` (HTTP/HTMX/DRF) or `integrations/*` (vendor payload). Rejected before any domain or application call. |
| `Money(minor=True, …)`, `Money(minor=1.5, …)`, `Money(…, currency="mdl")`, cross-currency `+`, cross-currency `<`, a bare number in a money expression, `sum()` over an empty `Money` sequence, an unchecked cast of an `int` into a `PublicId` | **Primitive misuse — a programmer error** | Raised by the primitive as a structural/technical fault. It propagates untranslated to the platform boundary (item 4 §13.5) and is **never** dressed as a business error, never mapped to a `core.errors` category, and never presented to a user as a validation message. |
| An unsupported-but-structurally-valid currency; a negative amount in a field whose invariant is non-negative; a provider amount that does not match internal state; a locator that addresses nothing the actor may see | **Business rejection** | The **owning domain or application module's** public error contract (item 4 §13), with the not-found/not-allowed choice left where item 4 already leaves it. |
| A database or infrastructure failure encountered while resolving a locator | **Technical fault** | Propagates untranslated (item 4 §13.5). |

| # | Rule |
|---|---|
| ER1 | The three classes above are kept distinct. Collapsing primitive misuse into business rejection would let a programmer error be rendered as "invalid input" to a user and silently retried; collapsing boundary validation into primitive misuse would turn ordinary bad input into a 500. |
| ER2 | **If a new `core` public error primitive ever appeared necessary for item 11, it would require an explicit ADR and an allowlist decision** on ADR-0006's precedent. Item 11 deliberately introduces none, and none of §39's failure rows needs one. |

---

## 38. Security

| # | Rule |
|---|---|
| SE1 | **Money:** no float anywhere (FL1); no approximate or tolerance comparison (IG5, PV2); no implicit currency (CU6); no implicit FX (FX1); no hidden or double rounding (RP1, HR2). Each of these is a real attack or loss surface, not a style preference: a tolerance turns into free money, an inferred currency turns into a hundredfold price error, a hidden rounding turns into an unreconcilable ledger. |
| SE2 | **Provider amounts are validated exactly** — amount **and** currency — against internally computed truth, never trusted as reported (PV1–PV6, item 5's trust rules). |
| SE3 | **Identity:** a `PublicId` is not a secret and not a permission (AZ1–AZ4); an internal `bigint` is never an external locator or contract identifier (§21, EI4); provider identifiers stay a distinct space (EI5, MI12); a UUID's embedded timestamp is never trusted as business state (TS1–TS5). |
| SE4 | **Enumeration** is addressed by not exposing sequential identifiers (§21, master `# 5.1`), and **access** is addressed by authorization — never by the identifier's entropy (AZ3). The two must not be confused, because a locator that leaks (a shared link, a referrer header, a support ticket, a log) then costs nothing. |
| SE5 | **Sensitive guest access** keeps requiring master `# 5.1`'s purpose-bound, time-limited, nonce-carrying signed token, consumed or rotated after use. Item 11 designs no token, no signing scheme and no lifetime. |
| SE6 | **No secret, credential or personal datum is encoded into, or derivable from, any of the three types** (IM5, LG3–LG4, item 10 PV1). |

---

## 39. Failure matrix

"Commercial state" means order, payment, inventory, reservation, idempotency or ledger state.

| # | Situation | Which layer rejects / handles it | Classification | Commercial state may change |
|---|---|---|---|---|
| 1 | Major-unit `Decimal` input that **is** exactly representable in minor units | The explicit conversion at the owning boundary, which still names a policy (CV4) | Normal operation | Only as the caller's own flow intends |
| 2 | Major-unit `Decimal` input that **requires** rounding | The same conversion, applying the **explicitly named** policy (RP2) | Normal operation | Only as the caller's own flow intends |
| 3 | A conversion site that names **no** rounding policy | Review + static check (A79); it never reaches runtime as a silent default (RP1, CV5) | Defect — caught before merge | **None** |
| 4 | `float` offered as a money amount (constructor, arithmetic, payload, fixture) | The primitive (IG3) and the codec (DT5), backed by A78 | Primitive misuse / boundary rejection | **None** |
| 5 | `bool` offered as `minor` | The primitive's exact type check (IG1, IG2) | Primitive misuse | **None** |
| 6 | Currency omitted from an external amount | Boundary validation at `interfaces/*` or `integrations/*` (CU7) | Boundary input failure | **None** |
| 7 | Currency inferred from locale, store, user, request or environment | Review + static check (A72, CU6) | Defect — caught before merge | **None** |
| 8 | Non-canonical currency spelling (`"mdl"`, `" MDL"`) | The primitive (CU5); normalisation, if wanted, is explicit boundary work | Primitive misuse | **None** |
| 9 | Structurally valid but unsupported currency (`"XYZ"`) | The **owning module's** supported-currency policy (CU4) — not `core` | Business rejection | **None** |
| 10 | Cross-currency addition or subtraction | The primitive (AR2) | Primitive misuse | **None** |
| 11 | Cross-currency ordered comparison, `min`, `max` or sort | The primitive (OD1, OD2) | Primitive misuse | **None** |
| 12 | An automatic dataclass total ordering silently making case 11 legal | Static check A75 + ADR-0012 | Defect — caught before merge | **None** (if it reached production, mispriced comparisons **could** change commercial state — which is why it has its own check) |
| 13 | `sum()` over a possibly empty sequence of `Money` returning bare `0` | Review + static check (ZR2, A74) | Defect — caught before merge | **None** |
| 14 | A negative `Money` in the generic primitive | **Nothing rejects it** — it is legal (SG1) | Not a failure | n/a |
| 15 | A negative value in a field whose invariant is non-negative | The owning module's validation **and** its PostgreSQL `CHECK` (SG2, PS4) | Business rejection, with a DB constraint as the last line | **None** — the write fails |
| 16 | Provider amount or currency mismatch on a payment/refund callback | The owning payment workflow's exact comparison (PV1–PV3) | Business/integration failure → reconciliation (PV5) | **None** from the mismatch itself; the workflow's state machine decides what happens next |
| 17 | Provider supplies only a binary float amount | The integration boundary (FL4, FL5) — normalised losslessly or handled as a provider-contract problem in that provider's phase | Integration-contract failure | **None** |
| 18 | Malformed `PublicId` text in a URL or payload | `interfaces/*` boundary validation (PA1, PA4) | Boundary input failure | **None** — no query is issued |
| 19 | Non-canonical `PublicId` spelling (braces, `urn:uuid:`, unhyphenated, uppercase) | `interfaces/*` boundary validation — **rejected, not normalised** (PA3) | Boundary input failure | **None** |
| 20 | A UUIDv4 (or any non-v7 UUID) supplied where a `PublicId` is required | The version check at construction (PA1, TY4) | Boundary input failure | **None** |
| 21 | An internal `bigint` supplied as an API locator | The type boundary (TY1) plus route/serializer tests (ADR-0001's enforcement table) | Boundary input failure; a **serialized** internal id going out is a defect (A84) | **None** |
| 22 | A valid `PublicId` presented for a protected resource without authorization | The actor-scoped selector/policy, or the signed-token check (AZ2) | Business rejection — not-found or not-allowed per item 4's rule | **None** |
| 23 | A provider or legacy UUID mistaken for a `PublicId` (including a foreign **v7**) | PA1 catches every non-v7 case; a foreign v7 is caught by the boundary that owns the mapping (EI5, EI6) and by review (V99) | Boundary input failure / defect | **None** — the lookup finds nothing |
| 24 | A UUIDv7 timestamp read to order, version or date something | Review + static check (A83, A85), and TS5 makes clock behaviour irrelevant by construction | Defect — caught before merge | **None** |
| 25 | Retry or replay of a message | **Nothing rejects it** — the `EventId` is unchanged and item 8's identity/idempotency rules apply as written (MI2) | Not a failure | Not from identity; item 8 §21's one-effect rule governs |
| 26 | A new business fact emitted with a **reused** `EventId` | The consumer's mandatory first-seen identity retention: same `EventId` with different content is an **integrity violation** (item 8 §21.1), not a duplicate | Contract/identity integrity failure → durable quarantine + alert (item 8 §20, item 9's TF-C) | **None** — the effect is not applied |
| 27 | An `EventId` and a `PublicId` accidentally substituted for one another | The type boundary (TY3, TX5); at runtime the lookup or dedupe simply finds nothing | Defect — caught by the type checker before merge | **None** |
| 28 | A generic exported UUID utility that erases the type distinction | Review + static check (A82, TX3, TX4) | Defect — caught before merge | **None** |

Every commercial-impact cell is **None**. That is the intended property: item 11's failures are
either caught statically, rejected at a boundary before any durable write, or handled by an
already-frozen mechanism that item 11 does not modify.

---

## 40. Checks later phases must implement

Numbering continues item 10: `A68+`, `C100+`, `V84+`. Item 11 adds **no** `L` rule — no import edge
changes (OW6).

### 40.1 Static / AST (`A` series)

| # | Check |
|---|---|
| A68 | **No `float` in a money position.** No public DTO field, payload field, port edge-type field, model field, constructor parameter or annotation that is semantically money is typed `float`, and no money expression contains a float literal or a `float()` call (FL1, IG3). |
| A69 | **No money constructed from a disallowed source.** No call site builds a money value directly from a `float`, `Decimal`, `str` or JSON number without going through a named conversion (CV1, CV2). |
| A70 | **No business vocabulary in the money primitive.** `core.money` declares no member, constant, parameter or policy name containing discount/VAT/tax/promo/loyalty/delivery/price-list/provider vocabulary, and no sign or range policy (OW4, SG4, RP5, HR4). |
| A71 | **No currency hard-coding in `core`.** `core` contains no MDL-specific constant, default or branch, and no currency literal outside a test (MS5). |
| A72 | **No inferred currency.** No money construction takes its currency from a locale, request, session, store, settings default, environment variable or provider field standing in for one (CU6). |
| A73 | **No approximate money comparison.** No epsilon, tolerance, `isclose`, `abs(a-b) < …` or round-before-compare appears in any money path (IG5, PV2). |
| A74 | **No bare-`0` money aggregation.** No `sum()`/`reduce()` over a possibly empty sequence of money values without an explicit currency-bearing zero (ZR2). |
| A75 | **No dataclass-generated total ordering on `Money`.** The money value type is not declared with automatic ordering generation, and any ordered comparison it defines is currency-guarded (OD3 — a dedicated check because it is a one-word regression). |
| A76 | **No hard-coded exponent arithmetic.** No general money mechanism divides or multiplies by `100`, uses a `0.01` constant, or rounds to two decimals as a currency-independent rule (EX3). |
| A77 | **`RoundingPolicy` members are arithmetic, not business.** No policy member name references a business step (RP5). |
| A78 | **No float money in fixtures.** Test factories, fixtures, snapshots and parametrisations express money as minor units or as an explicitly converted decimal string (FL2). |
| A79 | **Explicit rounding boundary.** Every fractional-capable conversion call site passes a rounding policy explicitly; no default parameter, module-level default or settings default exists (RP1, RP2, CV5, DE4). |
| A80 | **No money helper outside its owner.** No ad-hoc money conversion, formatting or rounding helper exists outside `core.money` and the interface/integration boundaries entitled to render or map (CV6, SN3). |
| A81 | **Money in contracts is `Money`.** No domain or application public signature or DTO field that is semantically money is typed as a naked `int`, `*_minor` integer, `Decimal` or `float` (DT1, PS6). |
| A82 | **No bare `UUID` in a locator position, and no generic UUID utility outside `core`.** No public signature or DTO field that identifies an addressable object is annotated `uuid.UUID`; no package outside `core` imports a generic UUID generation/parsing utility instead of a semantic type (PI3, TX3). |
| A83 | **No UUID timestamp decoding.** No code path extracts, decodes or branches on the time component of a `PublicId` or `EventId` (TS2). |
| A84 | **No internal identifier in a public locator position.** No route parameter, URL builder argument, public serializer field or public DTO field carries an internal `bigint`; the signed-opaque-cursor path remains the one exception (§21, PK6, extending item 4 A16 and item 7 A36). |
| A85 | **No neighbouring item's vocabulary here.** This artifact and ADRs 0012/0013 define no `source_version`, revision or staleness guard (item 12); no analytics signal (item 13); no MVP/later cut (item 14); no `event_type`, payload schema, `schema_version`, routing, terminal state or replay rule (items 8–10); and no projection, facet, cursor codec or pricing algorithm (items 6, 7). A reviewer-runnable grep-level check on the artifacts themselves (§1.2). |

### 40.2 Behavioural / property tests (`C` series)

| # | Test |
|---|---|
| C100 | **Explicit major-unit conversion.** `100.00 MDL` converts to `minor = 10000` through the named conversion path with an explicit policy — and the same assertion holds for a zero-exponent and a three-exponent currency, so the test does not encode "two decimals" (EX3, CV3). |
| C101 | **Exact same-currency addition and subtraction**, including a signed result and a currency-bearing zero result (AR1, AR3, SG1). |
| C102 | **Cross-currency addition and subtraction are rejected**, in both operand orders, with no silent conversion and no left-operand currency inheritance (AR2). |
| C103 | **Cross-currency ordered comparison is rejected** for `<`, `<=`, `>`, `>=`, and through `min`, `max` and `sorted` over a mixed-currency collection — asserting that the failure is raised, not that some order was produced (OD1, OD2, OD6). |
| C104 | **Aggregation.** Summing a same-currency collection is exact; summing an **empty** collection requires an explicit currency-bearing zero and never yields a bare `0`; a mixed-currency collection is rejected (ZR2, ZR3). |
| C105 | **Money equality is exact and currency-bearing.** Equal minor + equal currency ⇒ equal; equal minor + different currency ⇒ **not** equal, zero included; hashing is consistent with equality (EQ1, EQ2, EQ5). |
| C106 | **Float input is rejected** at construction, in arithmetic and in comparison (IG3, FL1). |
| C107 | **`bool` is rejected** as `minor`, and is not silently read as `1`/`0` (IG2). |
| C108 | **Fractional conversion requires an explicit policy, and is deterministic.** The same source value, currency, scale and policy always yield the same minor amount, across processes and platforms; the conversion reads no clock, locale or configuration (RP2, RP4, CV4, CV7). |
| C109 | **Rounding is not doubled.** A calculation carried exactly to a single materialisation point yields the documented result; a deliberately double-rounded variant is asserted to differ, so the test pins the difference rather than assuming it away (HR2, HR3). |
| C110 | **No raw `Decimal` becomes commercial truth.** A `Decimal` amount cannot reach a durable or public money position without the explicit conversion (DE4). |
| C111 | **No epsilon comparison anywhere in a money path** — a value one minor unit apart is never equal and never "close enough", in the primitive and in the provider-comparison path (IG5, PV2). |
| C112 | **Provider amount comparison is exact on amount and currency.** A one-minor-unit difference mismatches; the same number in a different currency mismatches (PV1, PV3). |
| C113 | **No implicit FX.** No operation on money converts currency; a conversion requires the explicit operation with its rate, provenance and policy (FX1, FX2). |
| C114 | **Money is not renderable or serializable by itself**, and an external representation of money is exact, carries its currency, and is never a binary float (CV6, SN4, DT5). |
| C115 | **Sign is a field invariant, not a primitive invariant.** A negative `Money` constructs; a field declared non-negative rejects it in validation **and** at the database constraint (SG1, SG2, PS4). |
| C116 | **Persisted money round-trips exactly** through an integer minor-unit column paired with its currency, with no float or `numeric` in the path (PS1, PS2, PS6). |
| C117 | **UUIDv7 generation yields distinct, valid, version-7 identifiers** across a large batch and across concurrent generation, with database uniqueness as the backstop (GN1, GN5). |
| C118 | **A non-v7 UUID is rejected as a `PublicId`** — v4 and every other version, including a well-formed foreign v7 rejected by the owning boundary's mapping rather than by shape (PA1, EI5). |
| C119 | **`PublicId` canonical round-trip.** Rendering yields the lowercase hyphenated form; parsing that form yields the same value; non-canonical spellings (uppercase, braces, `urn:uuid:`, unhyphenated) are **rejected**, not normalised (PA2, PA3, PA6). |
| C120 | **An internal `bigint` cannot occupy a `PublicId` position** — a type-checker assertion plus a runtime rejection where the boundary constructs from external input (TY1, TY4). |
| C121 | **A `PublicId` does not authorize.** A valid locator for a protected resource, presented without the required actor scope or signed token, is refused; the refusal leaks no existence detail beyond what item 4 already permits (AZ1, AZ2, AZ5). |
| C122 | **A UUID timestamp is ignored by business logic.** Two entities created with deliberately skewed clocks (including a rollback) produce identical business outcomes, ordering and versions (TS1–TS5). |
| C123 | **A provider/ERP contract is not forced onto `PublicId`.** An adapter's contract identifier remains its own, translated through the frozen mapping ownership; a foreign UUID never becomes a platform locator (EI1–EI6). |
| C124 | **Retry and replay preserve the `EventId`.** Across relay retries, broker redelivery, worker retries and a terminal-state replay, the identity is byte-identical (MI2). |
| C125 | **A genuinely new message gets a new `EventId`**, even with a byte-identical payload (MI3). |
| C126 | **`causation_event_id` is the same semantic type as `event_id`** — asserted structurally, and asserted by the type checker rejecting a `PublicId` in that position (MI10, TY3). |
| C127 | **`PublicId` and `EventId` with identical underlying UUID bytes are not interchangeable** — a **runtime** assertion, not only a type-checker one: constructed from the same UUID value they are not equal, they hash consistently with that inequality, neither is mutually assignable, and neither resolves in the other's lookup, parser or constructor path. Same-type equality is asserted alongside it (`PublicId(U) == PublicId(U)`, `EventId(U) == EventId(U)`), so the test pins the distinction rather than merely a failure. Hash collision between unequal values is not asserted against (TY5, EQ3, EQ4, EQ5, TX5). |

### 40.3 Review-only (`V` series)

Each is a shape a reviewer rejects on sight:

| # | Reject |
|---|---|
| V84 | A float, a `numeric` column, or an arbitrary `Decimal` standing in as a persisted or public money amount (FL1, DE2, PS2). |
| V85 | A `*_minor` column, payload field or DTO field with no reachable, documented currency (CU7, PS3). |
| V86 | A currency default, a currency fallback, or a comment explaining which currency is "obviously" meant (CU6). |
| V87 | A default rounding policy, an optional policy parameter, a settings-driven policy, or a general-purpose "round it" helper (RP1, CV5). |
| V88 | A calculation whose rounding point is implicit, a chain of money-returning helpers that rounds at every hop, or a line-versus-total rounding choice left unstated in the owning contract (HR1, HR2, HR4). |
| V89 | Any tolerance, epsilon or "close enough" in a money comparison, especially in a payment or reconciliation path (IG5, PV2). |
| V90 | An implicit currency conversion, an FX helper on the primitive, or a rate source reachable from `core` (FX1, FX3). |
| V91 | A money helper in `core` named after a business step, or a sign/range policy in `core` (OW4, SG4, RP5). |
| V92 | A money mechanism that assumes two decimal places, or an exponent obtained from a live external lookup (EX3, EX4). |
| V93 | Anything MDL-specific in the primitive (MS5). |
| V94 | An internal `bigint` in a URL, an API payload, an email link, a webhook body or an external contract field — under any field name (§21, EI4, A84). |
| V95 | A `PublicId` replacing internal `bigint` PKs/FKs wholesale, or proposed as a keyset tiebreaker, or a cursor whose opacity is weakened to expose one (PK2, PK5, PK6). |
| V96 | A code path whose only access protection is the unpredictability of a locator; or a `PublicId` used as, or in place of, an authorization decision, a token, a claim or a capability (AZ1, AZ3). |
| V97 | A `PublicId` or `EventId` used as `source_version`, an optimistic-lock version, an ordering key, a sequence number or a causation chain position (TS3, TS4, MI7). |
| V98 | A UUID timestamp decoded for a business decision, a report boundary, a retention rule or a "which came first" conclusion (TS2). |
| V99 | A provider, ERP or legacy UUID renamed `public_id`, or an external identifier promoted into a platform locator without a deliberate schema and contract decision (EI5, EI6). |
| V100 | A generic exported UUID utility, a bare `UUID` annotation in a locator position, or any construct that lets `PublicId` and `EventId` become mutually assignable (PI3, TX3, TX5). |
| V101 | An `EventId` minted afresh on a retry or replay; a `causation_event_id` typed differently from `event_id`; an `EventId` used as an HTTP idempotency key; or a provider `external_event_id` adopted as internal message identity (MI2, MI9, MI10, MI12). |

---

## 41. Acceptance checklist

- [x] 1. Money is integer minor units (MS2, IG1).
- [x] 2. `bool` is not a money integer (IG2).
- [x] 3. `float` is forbidden throughout the money mechanism (IG3, FL1–FL5).
- [x] 4. Currency is explicit, canonical and never inferred (CU1, CU5–CU7).
- [x] 5. Same-currency addition and subtraction are exact (AR1, AR3).
- [x] 6. Cross-currency arithmetic is rejected (AR2).
- [x] 7. Cross-currency ordered comparison is rejected (OD1, OD2).
- [x] 8. No accidental dataclass-generated total ordering (OD3, A75, ADR-0012).
- [x] 9. Generic Money may be signed; sign constraints are field-level (SG1–SG5, PS4).
- [x] 10. Major-unit conversion is explicit (CV1–CV3).
- [x] 11. Fractional conversion has no implicit rounding (RP1, RP2, CV4, CV5).
- [x] 12. `RoundingPolicy`'s responsibility is clear: mandatory, defaultless, deterministic, arithmetic-only; owner-chosen (RP1–RP8).
- [x] 13. `Decimal` is never canonical persisted or public money (DE2–DE4, PS2).
- [x] 14. Provider comparison is exact on amount and currency (PV1–PV3).
- [x] 15. No implicit FX (FX1, FX2).
- [x] 16. `PublicId` is a strongly-distinct UUIDv7 locator type, distinct **statically and at runtime** (PI1–PI7, TY1–TY5).
- [x] 17. `PublicId` is immutable and never recycled or derived (IM1–IM6).
- [x] 18. `PublicId` is not authorization (AZ1–AZ6).
- [x] 19. Internal `bigint` remains internal (§21, PK1–PK3, EI4, A84).
- [x] 20. External contract identifiers remain distinct and explicitly chosen (EI1–EI7).
- [x] 21. The UUID timestamp is not business time, ordering or a version (TS1–TS6).
- [x] 22. `PublicId` is not forced into internal PK/FK usage (PK2, PK3).
- [x] 23. `PublicId` is not the keyset tiebreaker; cursor opacity is intact (PK5–PK7).
- [x] 24. Malformed or non-v7 input cannot become a `PublicId` (PA1, PA3, PA4).
- [x] 25. Items 8/10's event identity has a concrete semantic value space (EV1, MI1).
- [x] 26. Event identity is not confused with `PublicId` (EV1–EV3, MI6, TX5).
- [x] 27. `causation_event_id` is exactly `event_id`'s type (MI10).
- [x] 28. Items 8–10's retry/replay identity rules are unchanged (MI2 – MI5, MI11, MI12).
- [x] 29. No `source_version` mechanism appears anywhere (TS4, MI7, A85).
- [x] 30. No new dependency edge and no business vocabulary in `core` (OW4–OW7, TX6, A70).
- [x] 31. ADRs created only where genuinely required, one decision each (§1.3).
- [x] 32. No contradiction with ADR-0001…ADR-0011 (§43 row 19).

---

## 42. Deferred — what item 11 deliberately does not decide

| Deferred | Owner |
|---|---|
| The physical `core` modules, file layout, member names and signatures for `Money`, `RoundingPolicy`, `PublicId`, `EventId` and the UUIDv7 mechanism | **Phase 1** |
| The concrete identity construct — **bounded**, not open: it must be a runtime-distinct immutable value representation satisfying TY1–TY5, which admits a frozen validating wrapper value object and excludes a bare `typing.NewType` over `uuid.UUID` (PI4, TY5) | **Phase 1**, within that bound |
| The concrete `RoundingPolicy` member set (RP7) | **Phase 1**, justified per domain in that domain's phase |
| The standards-conforming UUIDv7 implementation or library, chosen against the pinned Python version (GN2) | **Phase 1** |
| The currency-exponent data source — a checked-in static table or an approved library (EX5) | **Phase 1** |
| The Django field classes, model fields, columns, `CHECK` constraints and indexes for money and `public_id` (PS7, PK8) | each owning schema's phase (catalog Phase 2, pricing/orders/payments/delivery in theirs) |
| `integer` vs `bigint` per money column (PS5) | the owning schema |
| Which currencies the platform supports, and where that policy lives (CU4) | pricing / payments / delivery phases |
| The supported-currency rejection's exact error member within item 4 §13's contract | the owning domain's phase |
| Line-level vs total-level rounding per business calculation (HR4) | pricing / promotions / delivery / orders phases |
| Any FX mechanism, rate source, rate provenance model or conversion API (FX4) | a future phase, on a new decision |
| The HTTP/HTML/JSON representation of money and of locators (DT4) | the Web and DRF interface phases |
| Provider amount and currency encodings, and their exact-comparison mapping (PV4) | each provider's integration phase |
| The signed guest/access token: scheme, purpose binding, nonce, lifetime, consumption (AZ2, SE5) | the security/checkout phases |
| The keyset cursor codec, its fields, signing and page-size limits (PK6) | **Phase 4** |
| `source_version`, its generation, per-source mapping and the guarded projection upsert | **item 12** |
| Whether analytics exists, and any popularity signal | **item 13** |
| The MVP/later module cut | **item 14** |
| Retention, erasure and anonymization policy for durable identifiers and money records | the privacy/security phases |
| Client-supplied creation identity, if ever wanted (GN4) | a new ADR |
| A currency registry, currency library or exponent service inside `core` (CU3, EX4) | would require a new ADR superseding this artifact's `core` scoping |

---

## 43. Self-review record

| # | Question | Verdict |
|---|---|---|
| 1 | Any `float` near money? | Pass — FL1–FL6 forbid it in construction, arithmetic, comparison, persistence, payloads and fixtures; IG3/IG4 in the primitive; PS2 in the schema; DT5 on the wire; A68/A78 check it; FL6 states plainly where `float` remains fine, so the rule is a firewall and not a blanket ban that reviewers would learn to ignore. |
| 2 | `Decimal` as persistent or public money truth? | Pass — DE2–DE4 forbid it; PS2 bans a `numeric` canonical amount; DE5 keeps a genuine rate/ratio field legal without calling it money; C110 and A79 check it. |
| 3 | Any implicit currency default? | Pass — MS3 (no default), CU5 (no normalisation inside the primitive), CU6 (an explicit list of the seven sources it may not come from, "MDL because Moldova" included), CU7, A72, V86. |
| 4 | Could a dataclass `order=True` accidentally order currencies? | Pass — OD3 rejects it by name against the master's own snippet, A75 is a dedicated check for the one-word regression, C103 asserts the failure through `min`/`max`/`sorted` rather than merely through the operators, and ADR-0012 records the decision so it cannot be re-litigated as a style preference. |
| 5 | Any tolerance or epsilon money comparison? | Pass — IG5 states it in the primitive, PV2 in the provider path, A73 and C111 check it, V89 is the review shape, SE1 states why it is a loss surface. |
| 6 | Any global default rounding? | Pass — RP1 (no default of any kind, enumerated), CV5 (no global helper), A79 and V87. RP3 keeps exact operations policy-free so the requirement stays meaningful where it matters. |
| 7 | Any hidden or double rounding? | Pass — HR1–HR6; C109 pins the difference rather than assuming it away; HR4 puts the line-vs-total choice with its owner and requires it to be named and tested there; HR6 ties it to the already-frozen immutable order snapshot. |
| 8 | Does Money assume all currencies have two decimals? | Pass — EX1–EX6; MS5 makes the MDL figure an example; A76 bans `/100`, `*100`, `0.01` and two-decimal rounding as general mechanisms; C100 requires the conversion test to cover a zero- and a three-exponent currency so the test itself cannot encode the assumption. |
| 9 | Is Money hard-coded to MDL? | Pass — MS5, A71, V93. `core` holds no currency constant at all. |
| 10 | Is `PublicId` ever used as authorization? | Pass — AZ1–AZ6, SE4, C121, V96; AZ3 rejects the entropy argument explicitly, and SE4 separates enumeration-resistance from access control so the two are not conflated. |
| 11 | Is `PublicId` ever a source/order version? | Pass — TS1–TS6, EQ6, MI7, A83, A85, C122, V97, V98. TS5 makes clock behaviour irrelevant by construction rather than by discipline. |
| 12 | Does `PublicId` replace internal bigint PKs? | Pass — PK1–PK3 keep the split; PK2 states the negative; PK8 refuses to design any schema; V95 is the review shape. |
| 13 | Is an internal bigint exposed in a URL or API? | Pass — §21's hard rule, EI4, PK6's single signed-cursor exception, A84 extending item 4 A16 and item 7 A36, V94. |
| 14 | Could a provider UUID become a `PublicId`? | Pass — PA1's version check catches non-v7; EI5 covers the residual foreign-v7 case explicitly and puts it with the boundary that owns the mapping; EI6 requires a deliberate decision to migrate one; C118, C123, V99. |
| 15 | Could a generic raw UUID destroy semantic type safety? | Pass — PI3, TY2, TX3, TX4 (with the reason stated, not just the rule), A82, V100. The shared mechanism is `core`-internal and exported to nobody. PI7 keeps the rule correctly scoped: the *underlying representation* may be a `uuid.UUID`; what is banned is a **bare** UUID serving as the identity. |
| 15a | Is every admissible construct actually able to satisfy the frozen behavioural contract? | Pass — this was a real contradiction and is fixed. EQ4 and C127 require `PublicId(U) != EventId(U)` **at runtime**, which a bare `typing.NewType` cannot deliver: its constructor returns the underlying value unchanged, so two such types produce indistinguishable values with identical equality and hashing. TY5 now states the runtime requirement, PI4 and §42 name the exclusion, and the construct itself stays Phase 1's within that bound. No class name, module name or signature is frozen. |
| 16 | Is `EventId` conflated with `PublicId`? | Pass — EV1–EV5 decide the distinction and state both rejected alternatives; TY3 and TY5 keep them non-interchangeable statically **and** at runtime; TX1, TX5, EQ4 state it; C127 tests the identical-bytes case; ADR-0013 records it. §32 verifies against ID7's actual text before deciding, as required. |
| 17 | Does a retry mint a new `EventId`, or does causation use another type? | Pass — MI2 (retry/replay preserve identity), MI3 (a new fact gets a new identity), MI10 (`causation_event_id` is exactly this type), C124–C126, V101. Items 8–10 are restated, never amended. |
| 18 | Does anything move a matrix cell, add an import edge or extend a `core` allowlist? | Pass — OW1/OW2 use `core.money` and `core.public_id`, already allowlisted per family by item 3 §4.2–§4.7; OW3 places `EventId` in `core.events`, already allowlisted for `domains`/`application`/`tasks`/`config` and already `FORBID` for `integrations/*`; TX3 keeps the shared mechanism `core`-internal, and `core → core` is `SELF ONLY` and already legal (§4.1). OW6 states the negative; OW7 leaves a Phase 1 placement consequence to be recorded then, on ADR-0006's precedent. `L1–L21` stand unedited, and item 11 adds no `L` rule. |
| 19 | Contradiction with ADR-0001…ADR-0011? | Pass — **0001:** §21 preserves the three identity spaces verbatim and types them; §22–§31 specify the locator side; EI1–EI7 preserve the adapter's freedom to choose its own contract identifier. **0002/0003:** untouched; no attribute, catalog or projection rule changes. **0004:** OW1–OW3 apply §2's admission test rather than bending it; OW4/OW5 keep policy out of `core`. **0005:** OW6/TX6 confirm no allowlist or matrix change; SN6 keeps `integrations/*` Django-free. **0006:** ER1/ER2 use the existing error categories and request no `core.errors` extension. **0007:** HR6, PV6 and AZ5 reinforce the placement transaction, the trust rules and principal-scoped replay without touching them. **0008:** PK5–PK7 preserve the pagination and cursor contract; AZ6 preserves "the projection is never a security basis". **0009:** §32 uses ID7's deferral as written and satisfies every requirement it states; MI1 – MI12 restate items 8's identity rules unchanged; DT6 leaves PD9 and `schema_version` untouched; ADR-0013 clarifies rather than amends. **0010:** untouched — no routing, terminal state, quarantine or replay rule changes; failure-matrix rows 25/26 defer to item 9's taxonomy. **0011:** MI10 fixes `causation_event_id`'s representation exactly as CZ4 requested, and adds no envelope field, no TCE semantics and no `schema_version` change. |
| 20 | Does anything pull item 12 forward? | Pass — TS4, MI7, A85 and §42 keep `source_version`, the guarded upsert and every staleness mechanism entirely with item 12. The word appears only as a negative rule. |
| 21 | Was any implementation code created? | Pass — no Python module, package, dataclass, `NewType`, enum, field, model, migration, serializer, library choice or dependency. §4's block is pseudo-notation; every concrete construct is listed in §42 as Phase 1's or later. |
| 22 | Was ADR need evaluated per decision, without a catch-all? | Pass — §1.3 tabulates eight decisions individually, finds six already authorized by existing frozen artifacts (naming which), and writes exactly two ADRs, one decision each, on unrelated subjects. No accepted ADR is edited. |
</content>
</invoke>
