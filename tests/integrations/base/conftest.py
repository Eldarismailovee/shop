"""Test doubles for the outbound mechanisms.

Both are here for the same reason: the properties under test are statements about elapsed
time and about how many times something was attempted, and a test that proves either by
really waiting on a real socket proves it slowly and then fails on a loaded CI machine for
reasons that have nothing to do with the invariant.
"""

from __future__ import annotations

import random
from collections.abc import Sequence

import pytest

from integrations.base.circuit_breaker import BreakerPolicy
from integrations.base.retry import RetryPolicy
from integrations.base.transport import VendorRequest, VendorResponse


class FakeClock:
    """Monotonic time that only moves when a test says so — or when the code sleeps."""

    def __init__(self) -> None:
        self.now = 1000.0
        self.slept: list[float] = []

    def monotonic(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        if seconds > 0:
            self.slept.append(seconds)
            self.now += seconds

    def advance(self, seconds: float) -> None:
        self.now += seconds


class ScriptedTransport:
    """Replays a fixed list of outcomes, one per `send`, and records what it was given.

    A step is either a `VendorResponse` to return or an exception instance to raise. Running
    off the end is an assertion failure rather than a silent repeat: "the client stopped
    after two attempts" is exactly the kind of claim a forgiving double would hide.
    """

    def __init__(self, steps: Sequence[object]) -> None:
        self.steps = list(steps)
        self.budgets: list[float] = []

    @property
    def calls(self) -> int:
        return len(self.budgets)

    def send(self, request: VendorRequest, *, budget_seconds: float) -> VendorResponse:
        self.budgets.append(budget_seconds)
        if not self.steps:
            raise AssertionError(f"unscripted call #{self.calls} to the transport")
        step = self.steps.pop(0)
        if isinstance(step, BaseException):
            raise step
        assert isinstance(step, VendorResponse)
        return step


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock()


@pytest.fixture
def rng() -> random.Random:
    """Seeded, so a jittered interval is a fixed number for the duration of a test."""
    return random.Random(20260908)


@pytest.fixture
def retry() -> RetryPolicy:
    return RetryPolicy(
        max_attempts=3,
        max_age_seconds=30.0,
        initial_backoff_seconds=0.2,
        multiplier=2.0,
        max_backoff_seconds=2.0,
    )


@pytest.fixture
def breaker() -> BreakerPolicy:
    return BreakerPolicy(failure_threshold=5, cooldown_seconds=30.0)


@pytest.fixture
def request_() -> VendorRequest:
    return VendorRequest(method="POST", url="https://provider.example/v1/charge", body=b"{}")
