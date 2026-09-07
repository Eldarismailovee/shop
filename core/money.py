"""`Money` and `RoundingPolicy` (item 11 PART A, ADR-0012, master `# 5.3`).

`Money` is an exact, multi-currency value: an integer count of minor units plus an
explicit currency. It knows no business policy — no discount, VAT, promotion, delivery,
loyalty or FX rule, no price list, no sign or range policy, and nothing MDL-specific
(OW4, MS5, SG4). Those live with the module that owns the decision.

The three rules that make it safe rather than merely convenient:

* **Integer discipline.** `minor` is checked by *exact type*, so `bool` — an `int`
  subclass by a language accident, not a monetary fact — is rejected rather than read as
  `1` (IG1, IG2). No `float` enters or leaves the mechanism, anywhere (IG3, FL1).
* **Currency is explicit and never inferred** (CU6). Not from locale, user, store,
  request, session, provider, environment or "MDL because Moldova". `core` validates the
  code *structurally* — three ASCII letters `A`-`Z` — and holds no ISO registry; *which*
  currencies are tradeable is the owning module's policy (CU3, CU4).
* **Operations are currency-scoped.** Arithmetic and ordered comparison are defined only
  within one currency; equality stays total, and zero is currency-bearing (AR1, OD1, ZR1).

Ordering is a **partial** order and is written by hand. Master `# 5.3`'s illustrative
`@dataclass(..., order=True)` is deliberately not adopted: a generated ordering over
`(minor, currency)` makes `Money(100, "EUR") < Money(200, "USD")` legal and true, silently,
at every `sorted()`, `min()`, `max()`, `heapq` and `bisect` call in the platform
(ADR-0012, OD3). `tools/arch_check` reports A75 if that one word ever returns.

Rejections here are **primitive misuse — programmer errors**, not business failures: they
are plain `TypeError`/`ValueError` that propagate untranslated to the platform boundary,
and are never mapped to a `core.errors` category or shown to a user as a validation
message (item 11 §37, item 4 §13.5).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import (
    ROUND_DOWN,
    ROUND_HALF_EVEN,
    ROUND_HALF_UP,
    ROUND_UP,
    Context,
    Decimal,
    localcontext,
)
from enum import Enum

__all__ = ("Money", "RoundingPolicy", "money_from_decimal")

#: CU3. The whole of `core`'s currency knowledge: exactly three ASCII letters `A`-`Z`.
#: CU5 makes a non-canonical spelling (`"mdl"`, `" MDL"`, `"Mdl"`) primitive misuse rather
#: than something to normalise, so one currency never acquires two spellings and therefore
#: two cache keys, two group-by buckets and two equality classes.
_CANONICAL_CURRENCY = re.compile(r"\A[A-Z]{3}\Z")

_INTEGER = Decimal(1)


class RoundingPolicy(Enum):
    """The arithmetic rules a fractional-capable conversion may name (RP1-RP8).

    A policy is **mandatory and has no default anywhere** — no default argument, no module
    default, no settings value, no per-currency default, no "the obvious one" (RP1, CV5).
    Exact operations take none (RP3), because a policy parameter where it cannot matter
    trains callers to pass one without thinking.

    Members are named for the **arithmetic rule** they apply, never for the business step
    that happens to use one (RP5): a `PRICE_ROUNDING` or `VAT_ROUNDING` member would
    smuggle policy into `core` and is reported as A77. *Which* policy a given business step
    uses is decided, stated and tested by the domain or application module that owns the
    step (RP6); `core` supplies the vocabulary and the deterministic arithmetic and never
    chooses.

    The tie direction is spelled out because "up" and "down" are ambiguous for the signed
    amounts SG1 permits: `TOWARD_ZERO` truncates and `AWAY_FROM_ZERO` magnifies on both
    sides of zero, and `HALF_UP` breaks a tie away from zero.
    """

    HALF_EVEN = "HALF_EVEN"
    HALF_UP = "HALF_UP"
    TOWARD_ZERO = "TOWARD_ZERO"
    AWAY_FROM_ZERO = "AWAY_FROM_ZERO"


#: RP4: each policy maps to one well-defined decimal rounding rule, so the same fractional
#: input and the same policy always yield the same minor amount, on every machine.
_DECIMAL_RULE = {
    RoundingPolicy.HALF_EVEN: ROUND_HALF_EVEN,
    RoundingPolicy.HALF_UP: ROUND_HALF_UP,
    RoundingPolicy.TOWARD_ZERO: ROUND_DOWN,
    RoundingPolicy.AWAY_FROM_ZERO: ROUND_UP,
}


@dataclass(frozen=True, slots=True, kw_only=True)
class Money:
    """An exact amount of one explicit currency, in integer minor units (MS1-MS6).

    `minor` counts minor units (bani, cents, or the unit itself for a zero-exponent
    currency) — never a major-unit amount, a scaled decimal or a "units and cents" pair.
    There is no third field: no exponent, locale, formatting hint, tax flag, price list,
    rounding policy or provenance (MS4). A caller needing any of those composes them
    beside `Money`, in its own type.

    The primitive imposes no bound and no sign rule (IG7, SG1): refunds, chargebacks,
    credit notes and accounting deltas need signed amounts. Whether a *specific* field must
    be `>= 0` is an invariant of that field, enforced by its owner and by a PostgreSQL
    `CHECK` where the value is durable (SG2, PS4).
    """

    minor: int
    currency: str

    def __post_init__(self) -> None:
        # IG1: exact type, not `isinstance` — that is precisely what excludes `bool`.
        if type(self.minor) is not int:
            raise TypeError(
                f"minor must be an integer count of minor units, got "
                f"{type(self.minor).__name__}; bool is not a money integer and float is "
                f"not money at all"
            )
        if type(self.currency) is not str:
            raise TypeError(
                f"currency must be a canonical currency code, got "
                f"{type(self.currency).__name__}; an amount without a currency is not money"
            )
        if not _CANONICAL_CURRENCY.fullmatch(self.currency):
            raise ValueError(
                f"{self.currency!r} is not a canonical currency code (three letters A-Z); "
                f"case normalisation and trimming are explicit boundary work"
            )

    # -- arithmetic (§8) ---------------------------------------------------

    def __add__(self, other: Money) -> Money:
        total = self.minor + self._commensurable(other, "+").minor
        return Money(minor=total, currency=self.currency)

    def __sub__(self, other: Money) -> Money:
        difference = self.minor - self._commensurable(other, "-").minor
        return Money(minor=difference, currency=self.currency)

    def __neg__(self) -> Money:
        """Exact and legal (AR3, SG5): the mechanism a domain expresses a reversal with."""
        return Money(minor=-self.minor, currency=self.currency)

    def __mul__(self, count: int) -> Money:
        """Multiplication by a dimensionless integer count — a line quantity (AR4).

        Multiplication by a ratio, a percentage or a rate is fractional-capable and is not
        an operator on `Money`: it goes through `money_from_decimal`.
        """
        if type(count) is not int:
            raise TypeError(
                f"money multiplies by a dimensionless integer count, not by "
                f"{type(count).__name__}; a ratio or percentage is a fractional-capable "
                f"conversion that must name a rounding policy"
            )
        return Money(minor=self.minor * count, currency=self.currency)

    __rmul__ = __mul__

    def __radd__(self, other: object) -> Money:
        # ZR2: `sum(values)` starts at bare `0` and lands here, so the naive aggregation
        # of a possibly empty sequence fails loudly instead of yielding a currency-less
        # zero. `sum(values, Money(minor=0, currency=...))` is the correct spelling.
        raise TypeError(
            f"cannot add {type(other).__name__} to money; a bare number is never promoted "
            f"to a Money, and summing money needs an explicit currency-bearing zero as the "
            f"start value"
        )

    def __rsub__(self, other: object) -> Money:
        raise TypeError(
            f"cannot subtract money from {type(other).__name__}; a bare number is never "
            f"promoted to a Money"
        )

    # -- ordering (§9, ADR-0012) -------------------------------------------

    def __lt__(self, other: Money) -> bool:
        return self.minor < self._commensurable(other, "<").minor

    def __le__(self, other: Money) -> bool:
        return self.minor <= self._commensurable(other, "<=").minor

    def __gt__(self, other: Money) -> bool:
        return self.minor > self._commensurable(other, ">").minor

    def __ge__(self, other: Money) -> bool:
        return self.minor >= self._commensurable(other, ">=").minor

    # -- guard -------------------------------------------------------------

    def _commensurable(self, other: object, operation: str) -> Money:
        """The one guard behind every arithmetic and ordered comparison.

        AR2/OD2: a cross-currency operation is rejected at the point of use. It is never
        silently converted, never resolved by taking the left operand's currency, never
        resolved by a configured base currency, and never falls back to comparing `minor`
        alone or the currency code as text. AR7/OD7: a bare number is rejected too, because
        promoting one would have to invent a currency.
        """
        if type(other) is not Money:
            raise TypeError(
                f"{operation} between Money and {type(other).__name__}: a bare number is "
                f"not money and is never promoted; write the comparison against a "
                f"currency-bearing zero"
            )
        if other.currency != self.currency:
            raise ValueError(
                f"{operation} between {self.currency} and {other.currency}: money "
                f"operations are currency-scoped; group by currency, or convert explicitly "
                f"with a rate and a rounding policy"
            )
        return other


def money_from_decimal(
    *, amount: Decimal, currency: str, exponent: int, rounding: RoundingPolicy
) -> Money:
    """The explicit boundary conversion into `Money` (§11, §13, §14).

    There is **no implicit constructor** from a `float`, a `Decimal`, a string, a JSON
    number or a provider amount object (CV2). This is the single named materialisation
    point, and it is given every input it needs rather than discovering any of them
    (CV3): the source value, the currency (never inferred), the currency's minor-unit
    scale, and the policy to apply if the value is not exactly representable.

    The policy is required **even when the value happens to be exact** (CV4): otherwise the
    omission survives until the first value that is not, in production. The conversion is
    deterministic and pure (CV7, RP4) — it reads no clock, locale, request or configuration,
    and runs in an explicit decimal context so the answer cannot depend on ambient process
    state (DE6).

    `exponent` is boundary metadata *passed in*, never a `Money` field and never assumed to
    be 2 (EX1-EX6): a mechanism that bakes in two decimals breaks on the first zero- or
    three-exponent currency. Where the exponent comes from is the owning boundary's
    decision; `core` holds no currency table (CU3, EX5).

    `Decimal` is right for rates, ratios and parsing (DE1) and is never itself commercial
    truth (DE2-DE4): it becomes truth only by passing through here.
    """
    if type(amount) is not Decimal:
        raise TypeError(
            f"amount must be a Decimal, got {type(amount).__name__}; there is no implicit "
            f"conversion from a float, a string or a JSON number into money"
        )
    if not amount.is_finite():
        raise ValueError(f"amount must be a finite Decimal, got {amount}")
    if type(exponent) is not int:
        raise TypeError(
            f"exponent must be the currency's minor-unit scale as an int, got "
            f"{type(exponent).__name__}"
        )
    if exponent < 0:
        raise ValueError(f"exponent must not be negative, got {exponent}")
    if type(rounding) is not RoundingPolicy:
        raise TypeError(
            f"rounding must be an explicit RoundingPolicy, got {type(rounding).__name__}; "
            f"there is no default policy anywhere"
        )

    # A precision derived from the operand, in a context of our own, so neither the
    # scaling nor the quantisation can be altered by the caller's ambient decimal context.
    significant = len(amount.as_tuple().digits)
    with localcontext(Context(prec=significant + exponent + 2)):
        minor = int(amount.scaleb(exponent).quantize(_INTEGER, rounding=_DECIMAL_RULE[rounding]))
    return Money(minor=minor, currency=currency)
