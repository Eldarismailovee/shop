"""`Money` and `RoundingPolicy` against the frozen contract (item 11 PART A, ADR-0012).

The `C` ids are item 11 §40.2's behavioural checks; a test's docstring names the one it
discharges so a later reader can find the rule rather than guess the intent.
"""

from __future__ import annotations

import dataclasses
import inspect
from decimal import Decimal

import pytest

from core.money import Money, RoundingPolicy, money_from_decimal

MDL = "MDL"
EUR = "EUR"

# ---------------------------------------------------------------------------
# Construction, integer discipline and the float firewall
# ---------------------------------------------------------------------------


def test_money_is_minor_units_plus_an_explicit_currency() -> None:
    amount = Money(minor=10_000, currency=MDL)
    assert amount.minor == 10_000
    assert amount.currency == MDL


def test_money_is_immutable_and_slotted() -> None:
    amount = Money(minor=1, currency=MDL)
    with pytest.raises(dataclasses.FrozenInstanceError):
        amount.minor = 2  # type: ignore[misc]
    with pytest.raises(AttributeError):
        amount.note = "x"  # type: ignore[attr-defined]


def test_currency_has_no_default_so_there_is_no_currency_less_money() -> None:
    """MS3: no currency-less Money, no sentinel currency, no inferred currency (CU6)."""
    fields = {f.name: f for f in dataclasses.fields(Money)}
    assert fields["currency"].default is dataclasses.MISSING
    assert fields["currency"].default_factory is dataclasses.MISSING
    with pytest.raises(TypeError):
        Money(minor=100)  # type: ignore[call-arg]


def test_bool_is_not_a_money_integer() -> None:
    """C107: `bool` subclasses `int` by a language accident; it is not read as 1 or 0."""
    with pytest.raises(TypeError):
        Money(minor=True, currency=MDL)  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        Money(minor=False, currency=MDL)  # type: ignore[arg-type]


@pytest.mark.parametrize("value", [1.5, 100.0, 0.0, Decimal("1.5"), "100", None])
def test_float_and_every_other_source_is_rejected_as_minor(value: object) -> None:
    """C106: no float — and no Decimal or string — is a money amount (IG3, FL1, CV2)."""
    with pytest.raises(TypeError):
        Money(minor=value, currency=MDL)  # type: ignore[arg-type]


@pytest.mark.parametrize("currency", ["mdl", " MDL", "Mdl", "MDL ", "MD", "MDLX", "978", ""])
def test_a_non_canonical_currency_is_rejected_rather_than_normalised(currency: str) -> None:
    """CU5: one currency never acquires two spellings, and therefore two equality classes."""
    with pytest.raises(ValueError):
        Money(minor=100, currency=currency)


def test_a_non_string_currency_is_rejected() -> None:
    with pytest.raises(TypeError):
        Money(minor=100, currency=978)  # type: ignore[arg-type]


def test_the_primitive_imposes_no_sign_or_range_rule() -> None:
    """C115 (primitive half): a negative Money constructs; SG2 puts the rule on the field."""
    assert Money(minor=-2_500, currency=MDL).minor == -2_500
    assert Money(minor=0, currency=MDL).minor == 0
    assert Money(minor=10**30, currency=MDL).minor == 10**30


# ---------------------------------------------------------------------------
# Equality and hashing (§35)
# ---------------------------------------------------------------------------


def test_equality_is_exact_and_currency_bearing() -> None:
    """C105 / EQ1, EQ2: zero is not universal — there is no currency-less monetary zero."""
    assert Money(minor=100, currency=MDL) == Money(minor=100, currency=MDL)
    assert Money(minor=100, currency=MDL) != Money(minor=101, currency=MDL)
    assert Money(minor=100, currency=MDL) != Money(minor=100, currency=EUR)
    assert Money(minor=0, currency=MDL) != Money(minor=0, currency=EUR)


def test_equality_is_total_across_currencies_and_against_other_types() -> None:
    """OD5: equality answers "same amount of the same currency" and never raises."""
    assert (Money(minor=100, currency=MDL) == Money(minor=100, currency=EUR)) is False
    assert (Money(minor=100, currency=MDL) == 100) is False
    assert (Money(minor=0, currency=MDL) == 0) is False


def test_hashing_is_consistent_with_equality() -> None:
    """EQ5: usable as a dict key and a set member."""
    assert hash(Money(minor=100, currency=MDL)) == hash(Money(minor=100, currency=MDL))
    assert len({Money(minor=0, currency=MDL), Money(minor=0, currency=EUR)}) == 2
    assert {Money(minor=1, currency=MDL): "one"}[Money(minor=1, currency=MDL)] == "one"


# ---------------------------------------------------------------------------
# Same-currency arithmetic (§8)
# ---------------------------------------------------------------------------


def test_same_currency_addition_and_subtraction_are_exact() -> None:
    """C101, including a signed result and a currency-bearing zero result."""
    assert Money(minor=100, currency=MDL) + Money(minor=50, currency=MDL) == Money(
        minor=150, currency=MDL
    )
    assert Money(minor=100, currency=MDL) - Money(minor=250, currency=MDL) == Money(
        minor=-150, currency=MDL
    )
    assert Money(minor=100, currency=MDL) - Money(minor=100, currency=MDL) == Money(
        minor=0, currency=MDL
    )


def test_negation_is_exact() -> None:
    assert -Money(minor=150, currency=MDL) == Money(minor=-150, currency=MDL)
    assert -Money(minor=0, currency=MDL) == Money(minor=0, currency=MDL)


def test_multiplication_by_an_integer_count_is_exact_and_commutative() -> None:
    """AR4: a line quantity is dimensionless and cannot create a fractional minor unit."""
    assert Money(minor=1_999, currency=MDL) * 3 == Money(minor=5_997, currency=MDL)
    assert 3 * Money(minor=1_999, currency=MDL) == Money(minor=5_997, currency=MDL)


@pytest.mark.parametrize("factor", [1.5, Decimal("1.5"), True, "3"])
def test_multiplication_by_anything_but_an_integer_count_is_rejected(factor: object) -> None:
    """AR4: a ratio or percentage is a conversion that must name a rounding policy."""
    with pytest.raises(TypeError):
        Money(minor=100, currency=MDL) * factor  # type: ignore[operator]


def test_division_is_not_an_operator_on_money() -> None:
    """AR5: splitting an amount is proportional allocation, owned by the domain."""
    with pytest.raises(TypeError):
        Money(minor=100, currency=MDL) / 2  # type: ignore[operator]


@pytest.mark.parametrize("other", [100, 0, 1.5, Decimal("1.5"), "100", None])
def test_money_never_mixes_with_a_bare_number(other: object) -> None:
    """AR7: promotion would have to invent a currency, so there is none."""
    with pytest.raises(TypeError):
        Money(minor=100, currency=MDL) + other  # type: ignore[operator]
    with pytest.raises(TypeError):
        Money(minor=100, currency=MDL) - other  # type: ignore[operator]


def test_cross_currency_addition_and_subtraction_are_rejected_in_both_orders() -> None:
    """C102: never silently converted, never resolved by the left operand's currency."""
    mdl, eur = Money(minor=100, currency=MDL), Money(minor=100, currency=EUR)
    for left, right in ((mdl, eur), (eur, mdl)):
        with pytest.raises(ValueError):
            left + right
        with pytest.raises(ValueError):
            left - right


# ---------------------------------------------------------------------------
# Aggregation (§7)
# ---------------------------------------------------------------------------


def test_aggregation_requires_an_explicit_currency_bearing_zero() -> None:
    """C104 / ZR2: a naive `sum()` cannot yield a currency-less bare zero."""
    values = [Money(minor=100, currency=MDL), Money(minor=250, currency=MDL)]
    with pytest.raises(TypeError):
        sum(values)  # type: ignore[call-overload]

    zero = Money(minor=0, currency=MDL)
    assert sum(values, zero) == Money(minor=350, currency=MDL)
    assert sum([], zero) == zero


def test_aggregating_a_mixed_currency_collection_is_rejected() -> None:
    """ZR3: rejected rather than partitioned, coerced or summed on one currency."""
    with pytest.raises(ValueError):
        sum(
            [Money(minor=100, currency=MDL), Money(minor=100, currency=EUR)],
            Money(minor=0, currency=MDL),
        )


# ---------------------------------------------------------------------------
# Ordering — currency-scoped and partial (§9, ADR-0012)
# ---------------------------------------------------------------------------


def test_same_currency_ordering_is_total() -> None:
    low, high = Money(minor=100, currency=MDL), Money(minor=200, currency=MDL)
    assert low < high and low <= high and high > low and high >= low
    assert low <= Money(minor=100, currency=MDL)
    assert min(low, high) == low
    assert max(low, high) == high
    assert sorted([high, low]) == [low, high]


def test_negative_amounts_order_below_zero_in_the_same_currency() -> None:
    assert Money(minor=-1, currency=MDL) < Money(minor=0, currency=MDL)


@pytest.mark.parametrize("operator", ["__lt__", "__le__", "__gt__", "__ge__"])
def test_cross_currency_ordered_comparison_is_rejected_in_both_orders(operator: str) -> None:
    """C103: never `True`, never `False`, never a fallback to `minor` or to the code as text."""
    mdl, eur = Money(minor=100, currency=MDL), Money(minor=200, currency=EUR)
    for left, right in ((mdl, eur), (eur, mdl)):
        with pytest.raises(ValueError):
            getattr(left, operator)(right)


def test_min_max_and_sorted_reject_a_mixed_currency_collection() -> None:
    """C103: asserted through the algorithms, not only through the operators."""
    mixed = [Money(minor=100, currency=EUR), Money(minor=200, currency=MDL)]
    for call in (lambda: min(mixed), lambda: max(mixed), lambda: sorted(mixed)):
        with pytest.raises(ValueError):
            call()


@pytest.mark.parametrize("other", [0, 100, 1.5, Decimal("1")])
def test_ordering_against_a_bare_number_is_rejected(other: object) -> None:
    """OD7: "is this positive" is written against a currency-bearing zero."""
    with pytest.raises(TypeError):
        assert Money(minor=100, currency=MDL) > other  # type: ignore[operator]


def test_positivity_is_expressed_against_a_currency_bearing_zero() -> None:
    assert Money(minor=1, currency=MDL) > Money(minor=0, currency=MDL)


# ---------------------------------------------------------------------------
# RoundingPolicy and the explicit conversion (§11-§14)
# ---------------------------------------------------------------------------


def test_the_conversion_has_no_default_anywhere() -> None:
    """RP1, CV5: every parameter is keyword-only and required — no policy default exists."""
    parameters = inspect.signature(money_from_decimal).parameters
    assert set(parameters) == {"amount", "currency", "exponent", "rounding"}
    for parameter in parameters.values():
        assert parameter.kind is inspect.Parameter.KEYWORD_ONLY
        assert parameter.default is inspect.Parameter.empty


def test_omitting_the_rounding_policy_is_a_hard_failure() -> None:
    with pytest.raises(TypeError):
        money_from_decimal(  # type: ignore[call-arg]
            amount=Decimal("100.00"), currency=MDL, exponent=2
        )


def test_an_exactly_representable_conversion_still_names_its_policy() -> None:
    """C100, CV4: the call site does not get to omit the policy because *this* value is exact."""
    assert money_from_decimal(
        amount=Decimal("100.00"), currency=MDL, exponent=2, rounding=RoundingPolicy.HALF_EVEN
    ) == Money(minor=10_000, currency=MDL)


@pytest.mark.parametrize(
    ("amount", "exponent", "expected"),
    [
        (Decimal("1500"), 0, 1_500),  # a zero-exponent currency
        (Decimal("100.00"), 2, 10_000),  # a two-exponent currency
        (Decimal("1.234"), 3, 1_234),  # a three-exponent currency
    ],
)
def test_the_conversion_does_not_assume_two_decimals(
    amount: Decimal, exponent: int, expected: int
) -> None:
    """C100 / EX3: "two decimals" is a fact about MDL, not a law of currencies."""
    converted = money_from_decimal(
        amount=amount, currency=MDL, exponent=exponent, rounding=RoundingPolicy.HALF_EVEN
    )
    assert converted.minor == expected


@pytest.mark.parametrize(
    ("policy", "expected"),
    [
        (RoundingPolicy.HALF_EVEN, 10_000),
        (RoundingPolicy.HALF_UP, 10_001),
        (RoundingPolicy.TOWARD_ZERO, 10_000),
        (RoundingPolicy.AWAY_FROM_ZERO, 10_001),
    ],
)
def test_each_policy_applies_its_own_arithmetic_rule(policy: RoundingPolicy, expected: int) -> None:
    """RP4: the policy is what decides, and the four members genuinely differ."""
    converted = money_from_decimal(
        amount=Decimal("100.005"), currency=MDL, exponent=2, rounding=policy
    )
    assert converted.minor == expected


@pytest.mark.parametrize(
    ("policy", "expected"),
    [
        (RoundingPolicy.HALF_UP, -10_001),
        (RoundingPolicy.TOWARD_ZERO, -10_000),
        (RoundingPolicy.AWAY_FROM_ZERO, -10_001),
    ],
)
def test_the_tie_direction_is_defined_for_signed_amounts(
    policy: RoundingPolicy, expected: int
) -> None:
    """The member names say "toward"/"away from zero" precisely because SG1 allows a sign."""
    converted = money_from_decimal(
        amount=Decimal("-100.005"), currency=MDL, exponent=2, rounding=policy
    )
    assert converted.minor == expected


def test_the_conversion_is_deterministic_under_a_hostile_ambient_decimal_context() -> None:
    """C108 / DE6: determinism must not depend on ambient process state."""
    import decimal

    call = lambda: money_from_decimal(  # noqa: E731
        amount=Decimal("123456789.005"),
        currency=MDL,
        exponent=2,
        rounding=RoundingPolicy.HALF_EVEN,
    )
    baseline = call()
    with decimal.localcontext() as context:
        context.prec = 3
        context.rounding = decimal.ROUND_UP
        assert call() == baseline


@pytest.mark.parametrize("amount", [100.0, "100.00", 100, None])
def test_no_raw_source_bypasses_the_conversion(amount: object) -> None:
    """C110, CV2: no implicit constructor from a float, a string or a JSON number."""
    with pytest.raises(TypeError):
        money_from_decimal(
            amount=amount,  # type: ignore[arg-type]
            currency=MDL,
            exponent=2,
            rounding=RoundingPolicy.HALF_EVEN,
        )


@pytest.mark.parametrize("amount", [Decimal("NaN"), Decimal("Infinity"), Decimal("-Infinity")])
def test_a_non_finite_decimal_is_not_an_amount(amount: Decimal) -> None:
    with pytest.raises(ValueError):
        money_from_decimal(
            amount=amount, currency=MDL, exponent=2, rounding=RoundingPolicy.HALF_EVEN
        )


def test_the_exponent_is_a_required_non_negative_integer() -> None:
    """EX6: the scale is passed in, never discovered inside `Money`."""
    with pytest.raises(ValueError):
        money_from_decimal(
            amount=Decimal("1"), currency=MDL, exponent=-1, rounding=RoundingPolicy.HALF_EVEN
        )
    with pytest.raises(TypeError):
        money_from_decimal(
            amount=Decimal("1"),
            currency=MDL,
            exponent=True,  # type: ignore[arg-type]
            rounding=RoundingPolicy.HALF_EVEN,
        )


def test_the_policy_argument_must_be_a_policy() -> None:
    with pytest.raises(TypeError):
        money_from_decimal(
            amount=Decimal("1"),
            currency=MDL,
            exponent=2,
            rounding="HALF_EVEN",  # type: ignore[arg-type]
        )


def test_the_conversion_validates_the_currency_it_is_given() -> None:
    with pytest.raises(ValueError):
        money_from_decimal(
            amount=Decimal("1"), currency="mdl", exponent=2, rounding=RoundingPolicy.HALF_EVEN
        )


def test_rounding_is_not_doubled() -> None:
    """C109: the difference is pinned rather than assumed away (HR2, HR3)."""
    lines = [Decimal("0.335"), Decimal("0.335"), Decimal("0.335")]
    once = money_from_decimal(
        amount=sum(lines, Decimal(0)),
        currency=MDL,
        exponent=2,
        rounding=RoundingPolicy.HALF_UP,
    )
    twice = sum(
        (
            money_from_decimal(
                amount=line, currency=MDL, exponent=2, rounding=RoundingPolicy.HALF_UP
            )
            for line in lines
        ),
        Money(minor=0, currency=MDL),
    )
    assert once == Money(minor=101, currency=MDL)
    assert twice == Money(minor=102, currency=MDL)
    assert once != twice


# ---------------------------------------------------------------------------
# The policy vocabulary itself
# ---------------------------------------------------------------------------


def test_the_policy_member_set_is_explicit_and_arithmetic_only() -> None:
    """RP5: a member is named for the arithmetic rule, never for a business step."""
    assert {member.name for member in RoundingPolicy} == {
        "HALF_EVEN",
        "HALF_UP",
        "TOWARD_ZERO",
        "AWAY_FROM_ZERO",
    }


def test_core_money_renders_nothing_and_serialises_nothing() -> None:
    """C114 / CV6, SN4: rendering and transport mapping happen above `core`."""
    for forbidden in ("to_json", "from_json", "__json__", "format", "render", "localise"):
        assert not hasattr(Money, forbidden)


def test_core_money_offers_no_fx_and_no_currency_registry() -> None:
    """C113 / FX1, FX3, CU3: no operation converts currency, and no rate source is reachable."""
    import core.money as module

    forbidden = ("convert", "exchange", "fx_", "rate")
    assert not any(name.lower().startswith(forbidden) for name in dir(module))
    assert module.__all__ == ("Money", "RoundingPolicy", "money_from_decimal")
