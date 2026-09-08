"""The time source the outbound mechanisms measure and wait on.

Every bound in this package — a timeout budget, a backoff interval, a breaker's cooldown —
is a statement about elapsed time, and a test that proves one by really waiting is a test
that makes the suite slow and flaky in exchange for nothing. The clock is therefore an
injected dependency with a real implementation and no other production one.

It is **monotonic** on purpose. A duration measured with wall-clock time is wrong whenever
NTP steps the clock or a leap second lands, which is precisely when an operator is least
able to tell a broken breaker from a broken provider.
"""

from __future__ import annotations

import time
from typing import Protocol

__all__ = ("Clock", "SystemClock")


class Clock(Protocol):
    """Elapsed time, and waiting for some of it to pass."""

    def monotonic(self) -> float:
        """Seconds from an arbitrary fixed point; never decreases, never jumps."""

    def sleep(self, seconds: float) -> None:
        """Block for `seconds`. A non-positive value returns immediately."""


class SystemClock:
    """The production clock: `time.monotonic` and `time.sleep`."""

    __slots__ = ()

    def monotonic(self) -> float:
        return time.monotonic()

    def sleep(self, seconds: float) -> None:
        if seconds > 0:
            time.sleep(seconds)
