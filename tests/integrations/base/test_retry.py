"""Bounded retry (master `# 20.8` §3, item 9 §19 RB1-RB3, §20 BO1-BO4, §27 AX1)."""

from __future__ import annotations

import random

import pytest

from integrations.base.retry import RetryPolicy, RetrySafety, backoff_seconds, clamped_retry_after


def policy(**overrides) -> RetryPolicy:
    fields = {
        "max_attempts": 3,
        "max_age_seconds": 30.0,
        "initial_backoff_seconds": 0.2,
        "multiplier": 2.0,
        "max_backoff_seconds": 2.0,
    }
    return RetryPolicy(**(fields | overrides))


class TestThePolicyIsFiniteByConstruction:
    """RB1: there is no unbounded retry policy anywhere in the platform."""

    def test_both_bounds_are_required(self):
        with pytest.raises(TypeError):
            RetryPolicy(max_attempts=3)  # type: ignore[call-arg]

    def test_an_attempt_bound_of_none_is_not_expressible(self):
        with pytest.raises(ValueError):
            policy(max_attempts=None)

    def test_zero_attempts_is_not_a_policy(self):
        with pytest.raises(ValueError):
            policy(max_attempts=0)

    def test_one_attempt_disables_retrying_without_disabling_the_policy(self):
        assert policy(max_attempts=1).max_attempts == 1

    @pytest.mark.parametrize(
        "field", ["max_age_seconds", "initial_backoff_seconds", "max_backoff_seconds"]
    )
    def test_no_duration_may_be_zero_or_negative(self, field):
        with pytest.raises(ValueError):
            policy(**{field: 0})

    def test_a_shrinking_backoff_is_refused(self):
        """BO4: a multiplier below 1 converges on the forbidden tight loop."""
        with pytest.raises(ValueError, match="multiplier"):
            policy(multiplier=0.5)

    def test_a_ceiling_below_the_first_interval_is_a_contradiction(self):
        with pytest.raises(ValueError, match="max_backoff_seconds"):
            policy(initial_backoff_seconds=5.0, max_backoff_seconds=1.0)


class TestBackoff:
    def test_intervals_increase(self):
        """BO1: increasing, bounded backoff."""
        rng = random.Random(1)
        first = backoff_seconds(policy(), completed_attempts=1, rng=rng)
        second = backoff_seconds(policy(), completed_attempts=2, rng=rng)
        assert first < second

    def test_the_ceiling_holds_however_many_attempts_have_failed(self):
        rng = random.Random(1)
        for attempt in range(1, 20):
            assert backoff_seconds(policy(), completed_attempts=attempt, rng=rng) <= 2.0

    def test_no_interval_is_ever_zero(self):
        """BO4: an immediate retry is a denial of service against a failing dependency.

        Equal jitter, not full jitter — full jitter can draw ~0 and produce exactly the
        tight loop the rule forbids, by chance rather than by design.
        """
        rng = random.Random(7)
        for attempt in range(1, 50):
            assert backoff_seconds(policy(), completed_attempts=attempt, rng=rng) > 0

    def test_intervals_are_jittered(self):
        """BO2: without jitter one outage synchronises every retry into a herd."""
        rng = random.Random(3)
        drawn = {backoff_seconds(policy(), completed_attempts=1, rng=rng) for _ in range(20)}
        assert len(drawn) > 1

    def test_jitter_stays_inside_the_interval(self):
        rng = random.Random(11)
        for _ in range(50):
            value = backoff_seconds(policy(), completed_attempts=1, rng=rng)
            assert 0.1 <= value <= 0.2

    def test_a_backoff_before_the_first_attempt_is_a_programming_error(self):
        with pytest.raises(ValueError):
            backoff_seconds(policy(), completed_attempts=0, rng=random.Random())


class TestRetryAfter:
    """BO3: a provider hint informs scheduling, clamped, and overrides no bound."""

    def test_absent_header_yields_nothing(self):
        assert clamped_retry_after(None, policy=policy()) is None

    def test_delta_seconds_is_honoured(self):
        assert clamped_retry_after("1", policy=policy()) == 1.0

    def test_a_large_hint_is_clamped_to_the_ceiling(self):
        assert clamped_retry_after("3600", policy=policy()) == 2.0

    @pytest.mark.parametrize("raw", ["", "soon", "Wed, 21 Oct 2026 07:28:00 GMT", "-5", "nan"])
    def test_an_unusable_hint_falls_back_to_the_computed_backoff(self, raw):
        """Including the HTTP-date form, which is ignored rather than parsed on purpose."""
        assert clamped_retry_after(raw, policy=policy()) is None

    def test_an_infinite_hint_is_not_a_wait_forever(self):
        assert clamped_retry_after("inf", policy=policy()) is None


class TestRetrySafety:
    """AX1: 'timeout, therefore send it again' is not the transport's inference to make."""

    def test_a_naturally_idempotent_operation_may_repeat(self):
        assert RetrySafety.NATURALLY_IDEMPOTENT.repeatable_after_ambiguity is True

    def test_a_provider_keyed_operation_may_repeat(self):
        """AX2: a stable provider key makes the retry provably the same operation."""
        assert RetrySafety.PROVIDER_KEYED.repeatable_after_ambiguity is True

    def test_an_unsafe_operation_may_not(self):
        assert RetrySafety.UNSAFE_TO_REPEAT.repeatable_after_ambiguity is False

    def test_the_member_set_is_closed(self):
        assert {member.name for member in RetrySafety} == {
            "NATURALLY_IDEMPOTENT",
            "PROVIDER_KEYED",
            "UNSAFE_TO_REPEAT",
        }
