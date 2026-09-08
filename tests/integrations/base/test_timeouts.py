"""The connect/read/total budget (master `# 20.8` §1, Phase 1 DoD).

The point of these is not that a wrong number is rejected. It is that there is **no way to
express the absence of a bound**: no default, no `None`, no partial budget.
"""

from __future__ import annotations

import dataclasses

import pytest

from integrations.base.timeouts import TimeoutBudget


class TestTheBudgetCannotBeOmitted:
    def test_every_field_is_required(self):
        with pytest.raises(TypeError):
            TimeoutBudget()  # type: ignore[call-arg]

    @pytest.mark.parametrize("missing", ["connect", "read", "total"])
    def test_no_single_field_has_a_default(self, missing):
        fields = {"connect": 3.0, "read": 10.0, "total": 15.0}
        del fields[missing]
        with pytest.raises(TypeError):
            TimeoutBudget(**fields)  # type: ignore[arg-type]

    def test_none_is_not_a_timeout(self):
        with pytest.raises(TypeError):
            TimeoutBudget(connect=3.0, read=None, total=15.0)  # type: ignore[arg-type]

    def test_the_budget_is_immutable(self):
        budget = TimeoutBudget(connect=3.0, read=10.0, total=15.0)
        with pytest.raises(dataclasses.FrozenInstanceError):
            budget.read = 600.0  # type: ignore[misc]


class TestRejectedValues:
    @pytest.mark.parametrize("field", ["connect", "read", "total"])
    @pytest.mark.parametrize("value", [0, -1.0, float("inf"), float("nan")])
    def test_a_bound_must_be_finite_and_positive(self, field, value):
        fields = {"connect": 3.0, "read": 10.0, "total": 15.0}
        fields[field] = value
        with pytest.raises(ValueError):
            TimeoutBudget(**fields)

    def test_true_is_not_one_second(self):
        """`bool` is an `int` by a language accident, the way `Money` reads it (IG1)."""
        with pytest.raises(TypeError):
            TimeoutBudget(connect=True, read=10.0, total=15.0)  # type: ignore[arg-type]

    def test_a_string_is_not_a_number_of_seconds(self):
        with pytest.raises(TypeError):
            TimeoutBudget(connect="3", read=10.0, total=15.0)  # type: ignore[arg-type]

    def test_total_below_connect_is_a_contradiction(self):
        with pytest.raises(ValueError, match="below connect"):
            TimeoutBudget(connect=10.0, read=1.0, total=5.0)

    def test_total_below_read_is_a_contradiction(self):
        with pytest.raises(ValueError, match="below read"):
            TimeoutBudget(connect=1.0, read=10.0, total=5.0)


class TestTheBaseline:
    def test_masters_own_numbers_are_admissible(self):
        """Master `# 20.8`: connect ~3 s, read ~10 s. The total is Phase 1's."""
        budget = TimeoutBudget(connect=3.0, read=10.0, total=15.0)
        assert (budget.connect, budget.read, budget.total) == (3.0, 10.0, 15.0)

    def test_a_total_equal_to_a_part_is_legal(self):
        """`total` binds the exchange; equalling `read` is a tight budget, not an error."""
        assert TimeoutBudget(connect=1.0, read=10.0, total=10.0).total == 10.0
