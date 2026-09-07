# ADR-0012 — `Money` is currency-scoped and partially ordered: no automatic cross-currency ordering

- **Status:** Accepted — Frozen
- **Date:** 2026-09-05
- **Phase:** 0 — Architecture Freeze
- **Supersedes:** —
- **Related:** [ADR-0004](0004-four-layer-modular-monolith.md) §2 (the `core` admission test),
  [ADR-0007](0007-place-order-atomic-idempotent-boundary.md) (the immutable commercial snapshot),
  [item 4](../architecture/phase-0/04-domain-public-contract.md) §7.1/D8,
  [item 11](../architecture/phase-0/11-money-public-id.md) §9,
  master `# 5.3`, `# 15.3`

## Context

Master `# 5.3` freezes `Money` as an immutable value object of integer minor units plus a currency,
and illustrates it with a dataclass declaration that includes `order=True`:

```python
@dataclass(frozen=True, slots=True, order=True)
class Money:
    minor: int
    currency: str
```

`order=True` generates `__lt__`, `__le__`, `__gt__` and `__ge__` from the field tuple. For this
class that means every pair of `Money` values becomes comparable, in every currency, by comparing
`minor` first and then comparing the currency **as text**. The consequences are concrete:

- `Money(100, "EUR") < Money(200, "USD")` is legal and returns `True`. One euro is reported as less
  than two dollars because `100 < 200`, with the currencies never consulted.
- `Money(100, "MDL") < Money(100, "USD")` is legal and returns `True`, because `"MDL" < "USD"`
  lexicographically. Two amounts that are not commensurable are ordered by alphabet.
- `sorted()`, `min()`, `max()`, `heapq` and `bisect` all silently accept mixed-currency
  collections and produce an answer.

None of these raises. There is no log line, no warning and no failing test unless somebody wrote one
specifically. The platform has many places where money is ordered — a cheapest-offer selection, a
free-delivery threshold, a promotion floor or cap, a price-range facet's bounds, a
"best price across variants" reduction, a payment-amount validation, a refund cap. Every one of
them is a place where a mixed-currency collection would be ordered confidently and wrongly.

The platform is multi-currency by type even though it launches trading primarily in MDL, so the
failure mode is not hypothetical for long: it becomes reachable the moment a second currency exists
in a price list, a provider response, an ERP import, a test fixture, or a delivery tariff — and it
manifests as a plausible-looking number, not as an exception.

This is the same class of decision as the arithmetic rule the master already took. Master `# 5.3`
makes `Money.__add__` raise on a currency mismatch: adding across currencies is treated as a
programmer error, precisely because the result would be meaningless. Ordering across currencies is
meaningless for the same reason, and `order=True` grants it anyway. The illustration is internally
inconsistent, and the inconsistency is a single word that no ordinary code review notices.

The counter-argument for keeping the total order is real and was weighed: a total order makes
`Money` usable as a sort key and a dictionary-ordering value without ceremony, and a partial order
means some collection operations need the caller to group or convert first. That cost is accepted
below.

## Decision

**`Money` is totally ordered within a currency and incomparable across currencies. It must not
acquire an automatic, field-derived total ordering.**

Concretely:

1. **Ordered comparison is currency-scoped.** `<`, `<=`, `>`, `>=` — and therefore `min`, `max`,
   `sorted`, and every algorithm built on them — are defined for two `Money` values **iff** their
   currencies are equal.

2. **A cross-currency ordered comparison is rejected at the point of comparison.** It never returns
   `False`, never returns `True`, never falls back to comparing `minor` alone, and never falls back
   to comparing the currency code as text. The rejection is a **primitive misuse / programmer
   error**: it propagates untranslated to the platform boundary and is never dressed as a business
   error (item 4 §13.5, item 11 §37).

3. **Master `# 5.3`'s illustrative `order=True` is not adopted.** No implementation may obtain its
   ordering by generation over the field tuple. Whatever comparison the type defines is explicitly
   currency-guarded.

4. **Equality is unaffected and stays total.** Any two `Money` values may be compared for equality;
   the answer is exact and is `True` **iff** `minor` and `currency` are both equal. Zero is
   currency-bearing: `Money(0, "MDL") != Money(0, "EUR")`. Equality answers "the same amount of the
   same currency"; only ordering needs a common unit.

5. **An ordered comparison against a bare number is rejected** for the same reason. "Is this
   positive" is written against a currency-bearing zero, so an amount never loses its currency in
   order to be compared.

6. **Sorting a mixed-currency collection has no default.** The owning module either groups by
   currency and sorts within each group, or converts explicitly through the FX operation
   (item 11 §20) and sorts the converted values — and states which it did. `core` does not choose,
   and offers no helper that implies a choice.

**Out of scope of this ADR:** the arithmetic rules (already master `# 5.3`'s, restated in item 11
§8); the rounding contract (master `# 5.3` and item 11 §13); currency validation (item 11 §6); any
FX mechanism, which item 11 §20 deliberately leaves as a negative rule only; the physical Python
construct, module and member names, which are Phase 1's.

## Consequences

**Positive**

- The most dangerous silent money bug the master's illustration permits — a confident, wrong
  ordering across currencies — becomes impossible rather than merely discouraged.
- `Money` becomes internally consistent: arithmetic and ordering now fail on the same condition, so
  there is one rule to remember ("money operations are currency-scoped") instead of two that
  disagree.
- A module that genuinely needs to order across currencies is forced to say so, which surfaces the
  rate, its provenance and its rounding policy as explicit inputs rather than as an accident of
  field order.
- Equality stays total, so `Money` remains usable as a dictionary key, a set member and an assertion
  target without ceremony.

**Negative / accepted cost**

- `sorted()`, `min()` and `max()` over a mixed-currency collection now raise instead of returning a
  number. That is the point, but it means a caller that was relying on the permissive behaviour must
  be rewritten to group or convert.
- The comparison operators cannot be generated; someone has to write four guarded methods once, and
  a future refactor could reintroduce `order=True` in a single word. Item 11 A75 exists as a
  dedicated static check for exactly that regression, because reviewing for it is unreliable.
- `Money` is a partially ordered type, which is slightly unusual and will occasionally surprise a
  developer expecting Python's usual value-type behaviour. The surprise is loud and immediate, which
  is the preferable direction for a money type.

**Enforcement**

| Mechanism | What it enforces |
|---|---|
| Phase 1 implementation | The currency guard on every ordered comparison; no generated ordering on the money value type. |
| Item 11 **A75** (static/AST) | The money value type is not declared with automatic ordering generation, and any ordered comparison it defines is currency-guarded. A dedicated check, separate from the general money checks, because the regression is one word. |
| Item 11 **C103** (behavioural) | Cross-currency `<`, `<=`, `>`, `>=` are rejected in both operand orders, **and** the rejection is asserted through `min`, `max` and `sorted` over a mixed-currency collection — not only through the operators. |
| Item 11 **C105** | Equality stays exact and total, including the currency-bearing zero case, with hashing consistent. |
| Item 11 **V89 / V91** (review) | No tolerance comparison; no ordering helper in `core` that reintroduces a cross-currency default. |
| Item 11 §39 rows 11, 12 | The failure matrix records both the rejected comparison and the regression that would make it silent. |

Phase 1 implements the type and the checks. No dependency-matrix cell moves, no import edge is
added, and no `core` submodule allowlist changes: `core.money` was already allowlisted for every
package family by ADR-0005 §1 and item 3 §4.2–§4.7. `L1–L21` stand unedited.
</content>
