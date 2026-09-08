"""Bounded retry: attempts, age, backoff, jitter, and what may be retried at all.

Master `# 20.8` §3 requires "exponential backoff + jitter + max attempts / max age", and
item 9 §19–§20 fixes the properties: no unbounded retry anywhere (RB1), a bounded attempt
count **and/or** a bounded age with both declared (RB2, RB3), increasing bounded backoff
(BO1), mandatory jitter (BO2), a clamped `Retry-After` if the provider sends one (BO3), and
no immediate tight retry loop (BO4).

### The bound this policy is, and the bound it is not

This is the **client's** retry: the short one that rides out a dropped connection or a
momentary `503` inside a single call. It is not the queue's. Item 9 §18–§19 gives a
message its own retry policy with delayed scheduling, and BO5 is explicit that a worker
sleeping through a long backoff is capacity a wedged provider has taken. So the defaults
here stay small — seconds, not minutes — and a real provider outage is meant to exhaust
them quickly, fail, and let the *message* be rescheduled by machinery that does not hold a
worker while it waits.

### `RetrySafety` has no default, and that is the point

Item 9 AX1: *"a non-idempotent provider operation is never blindly retried on ambiguity"*.
"Timeout, therefore send it again" is not an inference the transport is allowed to make —
for a payment it is a double charge (AX6). The transport cannot know which operations are
safe, so it does not guess: every call declares it, there is no default anywhere, and the
three members say *why* a repeat is safe, because that reason is what an operator needs
when the log line is the only thing left.

Note what the declaration does **not** cover. A connect failure is safe to retry for every
operation, `UNSAFE_TO_REPEAT` included, because nothing was sent — the declaration governs
only the ambiguous case, where the request went out and the answer did not come back.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from enum import Enum

__all__ = ("RetryPolicy", "RetrySafety", "backoff_seconds", "clamped_retry_after")


class RetrySafety(Enum):
    """Whether repeating *this* operation after an ambiguous outcome is provably safe."""

    #: The operation changes no provider state, or repeating it is naturally harmless —
    #: a status lookup, a catalogue fetch, a `GET`.
    NATURALLY_IDEMPOTENT = "naturally_idempotent"

    #: The request carries a stable, workflow-owned provider idempotency key, so a repeat
    #: is provably the same operation (AX2). This is the first choice for payment-class
    #: calls, and it is the *only* thing that makes a mutation repeatable.
    PROVIDER_KEYED = "provider_keyed"

    #: A repeat may apply the effect twice. On ambiguity the client stops and hands the
    #: workflow an `AmbiguousOutcome` to resolve by status lookup or reconciliation
    #: (AX3–AX5). It never guesses.
    UNSAFE_TO_REPEAT = "unsafe_to_repeat"

    @property
    def repeatable_after_ambiguity(self) -> bool:
        return self is not RetrySafety.UNSAFE_TO_REPEAT


@dataclass(frozen=True, slots=True, kw_only=True)
class RetryPolicy:
    """Finite by construction: both an attempt bound and an age bound, always (RB2)."""

    #: Total attempts, the first included. `1` disables retrying without disabling the
    #: policy, which is how a call site says "once" without reaching for `None`.
    max_attempts: int
    #: The wall of the whole operation, attempts and backoff together (RB3). Whichever
    #: bound is reached first ends it.
    max_age_seconds: float
    #: The un-jittered first interval; each subsequent one multiplies by `multiplier`.
    initial_backoff_seconds: float
    multiplier: float
    #: The ceiling on any single interval (BO1).
    max_backoff_seconds: float

    def __post_init__(self) -> None:
        if type(self.max_attempts) is not int or self.max_attempts < 1:
            raise ValueError(f"max_attempts must be a positive int, got {self.max_attempts!r}")
        for name in (
            "max_age_seconds",
            "initial_backoff_seconds",
            "max_backoff_seconds",
        ):
            value = getattr(self, name)
            if not value > 0:
                raise ValueError(f"{name} must be positive, got {value}")
        if self.multiplier < 1:
            # A shrinking backoff converges on BO4's forbidden tight loop.
            raise ValueError(f"multiplier must be at least 1, got {self.multiplier}")
        if self.max_backoff_seconds < self.initial_backoff_seconds:
            raise ValueError(
                f"max_backoff_seconds ({self.max_backoff_seconds}) is below "
                f"initial_backoff_seconds ({self.initial_backoff_seconds})"
            )


def backoff_seconds(policy: RetryPolicy, *, completed_attempts: int, rng: random.Random) -> float:
    """The jittered interval to wait after `completed_attempts` have failed.

    Equal jitter — half the interval fixed, half random — rather than full jitter. Full
    jitter can draw a delay of nearly zero, which is BO4's forbidden immediate retry
    arriving by chance; the fixed half guarantees the failing dependency gets a pause, and
    the random half still breaks the thundering herd BO2 exists to prevent.
    """
    if completed_attempts < 1:
        raise ValueError(f"completed_attempts must be at least 1, got {completed_attempts}")
    exponential = policy.initial_backoff_seconds * policy.multiplier ** (completed_attempts - 1)
    interval = min(exponential, policy.max_backoff_seconds)
    return interval / 2 + rng.uniform(0, interval / 2)


def clamped_retry_after(raw: str | None, *, policy: RetryPolicy) -> float | None:
    """A provider's `Retry-After`, clamped to this policy's ceiling — or `None` (BO3).

    Only the delta-seconds form is honoured. The HTTP-date form is deliberately ignored
    rather than parsed: it is rare in practice, and reading it correctly means trusting the
    provider's clock against ours, which turns a scheduling hint into a source of
    unexplainable waits. An unparseable, negative or absent value simply yields `None` and
    the computed backoff is used, because BO3 makes this an input to scheduling and never
    an override of a bound.
    """
    if raw is None:
        return None
    try:
        seconds = float(raw.strip())
    except ValueError:
        return None
    if seconds != seconds or seconds < 0 or seconds == float("inf"):
        return None
    return min(seconds, policy.max_backoff_seconds)
