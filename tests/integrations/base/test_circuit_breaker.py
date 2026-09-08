"""The circuit breaker (master `# 20.8` §2, item 9 §21 PV3-PV7)."""

from __future__ import annotations

import threading

import pytest

from integrations.base.circuit_breaker import BreakerPolicy, CircuitBreaker, CircuitState


def make(clock, *, threshold: int = 3, cooldown: float = 30.0) -> CircuitBreaker:
    return CircuitBreaker(
        name="provider",
        policy=BreakerPolicy(failure_threshold=threshold, cooldown_seconds=cooldown),
        clock=clock,
    )


class TestPolicyValidation:
    def test_a_threshold_must_be_a_positive_int(self):
        with pytest.raises(ValueError):
            BreakerPolicy(failure_threshold=0, cooldown_seconds=1.0)

    def test_a_cooldown_must_be_positive(self):
        """A zero cooldown is an open circuit that is never open: fail fast, forever, once."""
        with pytest.raises(ValueError):
            BreakerPolicy(failure_threshold=1, cooldown_seconds=0)


class TestOpening:
    def test_it_starts_closed(self, clock):
        assert make(clock).state is CircuitState.CLOSED

    def test_consecutive_failures_open_it(self, clock):
        breaker = make(clock, threshold=3)
        for _ in range(3):
            breaker.record_failure()
        assert breaker.state is CircuitState.OPEN

    def test_failures_below_the_threshold_do_not(self, clock):
        breaker = make(clock, threshold=3)
        breaker.record_failure()
        breaker.record_failure()
        assert breaker.state is CircuitState.CLOSED

    def test_a_success_resets_the_run(self, clock):
        """Consecutive means consecutive: a good call is evidence the vendor is alive."""
        breaker = make(clock, threshold=3)
        breaker.record_failure()
        breaker.record_failure()
        breaker.record_success()
        breaker.record_failure()
        breaker.record_failure()
        assert breaker.state is CircuitState.CLOSED

    def test_an_open_circuit_refuses_calls(self, clock):
        breaker = make(clock, threshold=1)
        breaker.record_failure()
        assert breaker.allows_call() is False


class TestTheHalfOpenProbe:
    def test_the_cooldown_must_elapse(self, clock):
        breaker = make(clock, threshold=1, cooldown=30.0)
        breaker.record_failure()
        clock.advance(29.0)
        assert breaker.state is CircuitState.OPEN
        clock.advance(1.0)
        assert breaker.state is CircuitState.HALF_OPEN

    def test_exactly_one_caller_is_admitted(self, clock):
        """Otherwise the cooldown's expiry delivers the herd the open circuit held back."""
        breaker = make(clock, threshold=1, cooldown=30.0)
        breaker.record_failure()
        clock.advance(30.0)
        assert breaker.allows_call() is True
        assert breaker.allows_call() is False
        assert breaker.allows_call() is False

    def test_a_successful_probe_closes_it(self, clock):
        breaker = make(clock, threshold=1, cooldown=30.0)
        breaker.record_failure()
        clock.advance(30.0)
        breaker.allows_call()
        breaker.record_success()
        assert breaker.state is CircuitState.CLOSED
        assert breaker.allows_call() is True

    def test_a_failed_probe_re_opens_for_a_full_cooldown(self, clock):
        breaker = make(clock, threshold=3, cooldown=30.0)
        for _ in range(3):
            breaker.record_failure()
        clock.advance(30.0)
        breaker.allows_call()
        breaker.record_failure()
        assert breaker.state is CircuitState.OPEN
        clock.advance(29.0)
        assert breaker.state is CircuitState.OPEN
        clock.advance(1.0)
        assert breaker.state is CircuitState.HALF_OPEN

    def test_one_failed_probe_re_opens_it_whatever_the_threshold(self, clock):
        """A half-open probe is the test; failing it needs no second opinion."""
        breaker = make(clock, threshold=10, cooldown=5.0)
        for _ in range(10):
            breaker.record_failure()
        clock.advance(5.0)
        breaker.allows_call()
        breaker.record_failure()
        assert breaker.state is CircuitState.OPEN


class TestIsolationAndSafety:
    def test_two_breakers_are_independent(self, clock):
        """PV6: state is per provider and per failure domain, never global."""
        one, other = make(clock, threshold=1), make(clock, threshold=1)
        one.record_failure()
        assert one.state is CircuitState.OPEN
        assert other.state is CircuitState.CLOSED
        assert other.allows_call() is True

    def test_concurrent_probes_admit_one_caller(self, clock):
        """A worker pool shares one client; a miscounting breaker opens on a healthy vendor."""
        breaker = make(clock, threshold=1, cooldown=1.0)
        breaker.record_failure()
        clock.advance(1.0)
        admitted: list[bool] = []
        barrier = threading.Barrier(8)

        def attempt() -> None:
            barrier.wait()
            admitted.append(breaker.allows_call())

        threads = [threading.Thread(target=attempt) for _ in range(8)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        assert admitted.count(True) == 1

    def test_concurrent_failures_are_all_counted(self, clock):
        breaker = make(clock, threshold=8, cooldown=1.0)
        barrier = threading.Barrier(8)

        def fail() -> None:
            barrier.wait()
            breaker.record_failure()

        threads = [threading.Thread(target=fail) for _ in range(8)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        assert breaker.state is CircuitState.OPEN


class TestTransitionLogging:
    """PV5: an alertable edge, not a line per fast-failed call."""

    def test_opening_logs_once(self, clock, caplog):
        breaker = make(clock, threshold=2)
        with caplog.at_level("WARNING", logger="integrations.circuit"):
            breaker.record_failure()
            breaker.record_failure()
        records = [r for r in caplog.records if r.name == "integrations.circuit"]
        assert len(records) == 1
        assert records[0].event == "integration.circuit_transition"
        assert records[0].vendor == "provider"
        assert (records[0].previous_state, records[0].state) == ("closed", "open")

    def test_fast_failed_calls_log_nothing(self, clock, caplog):
        breaker = make(clock, threshold=1)
        breaker.record_failure()
        with caplog.at_level("WARNING", logger="integrations.circuit"):
            caplog.clear()
            for _ in range(20):
                breaker.allows_call()
        assert [r for r in caplog.records if r.name == "integrations.circuit"] == []

    def test_closing_logs_the_recovery(self, clock, caplog):
        breaker = make(clock, threshold=1, cooldown=1.0)
        breaker.record_failure()
        clock.advance(1.0)
        with caplog.at_level("WARNING", logger="integrations.circuit"):
            caplog.clear()
            breaker.allows_call()
            breaker.record_success()
        states = [
            (r.previous_state, r.state) for r in caplog.records if r.name == "integrations.circuit"
        ]
        assert states == [("open", "half_open"), ("half_open", "closed")]
