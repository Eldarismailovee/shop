"""The circuit breaker (master `# 20.8` §2, item 9 §21 PV3–PV7).

> PV7: *"The circuit-breaker and rate-limiter implementations and thresholds are Phase 1's;
> `integrations/*`'s `BaseClient` is their home. Item 9 designs neither."*

Consecutive vendor failures open the circuit; calls then fail fast until a half-open probe
succeeds (PV3). The purpose is not to protect the caller — a fast failure and a slow one
are both failures — it is to stop the platform's own retry behaviour from amplifying a
provider's degradation into a provider outage (PV1), and to stop a wedged dependency from
holding worker capacity that other work in the same pool needs.

### What the breaker deliberately does not decide

**It never disposes of work.** PV4: a fast-failed call is an ordinary transient failure —
the caller's message is retried within its own bounds and, on exhaustion, becomes a durable
operational dead-letter. Nothing is dropped, lost or marked handled because a circuit was
open. Opening changes how long a worker is held, never what happens to the work.

**It does not classify.** Whether a given outcome reflects provider *health* is the
client's judgment, and the two differ in a way that matters: a `503` is the provider
failing, a `422` is the provider working perfectly and rejecting our request. Counting
rejections would let one malformed integration open a circuit against a healthy vendor and
take down every other workload that shares it. So the client calls `record_failure()` for
health failures only, and `record_success()` for everything that proves the vendor answered.

### One breaker per vendor, per failure domain (PV6)

State is instance state, held by the client that owns it. There is no module-level registry
and no shared store: a global breaker would let one provider's outage suppress calls to an
unrelated one, which is the opposite of what §5's isolation exists for. It follows that
state is also **per process** — two workers open independently, and neither learns from the
other. That is a deliberate Phase 1 choice, not an oversight: a shared breaker needs a
shared store on the outbound path, and a coordination round trip in front of every provider
call buys less than it costs while a single deployment's worker count is small.
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass
from enum import Enum

from integrations.base.clock import Clock

__all__ = ("BreakerPolicy", "CircuitBreaker", "CircuitState")

_log = logging.getLogger("integrations.circuit")


class CircuitState(Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


@dataclass(frozen=True, slots=True, kw_only=True)
class BreakerPolicy:
    """Thresholds. Phase 1 owns the numbers; a vendor slice may tighten them."""

    #: Consecutive health failures that open the circuit. Consecutive, not a rate: a
    #: rate needs a window, a window needs a memory, and the failure this exists to catch
    #: — a provider that is simply down — trips a consecutive counter immediately.
    failure_threshold: int
    #: How long the circuit stays open before admitting one probe.
    cooldown_seconds: float

    def __post_init__(self) -> None:
        if type(self.failure_threshold) is not int or self.failure_threshold < 1:
            raise ValueError(
                f"failure_threshold must be a positive int, got {self.failure_threshold!r}"
            )
        if not self.cooldown_seconds > 0:
            raise ValueError(f"cooldown_seconds must be positive, got {self.cooldown_seconds}")


class CircuitBreaker:
    """Closed → open on consecutive failures → one half-open probe → closed or open again.

    Every method is safe to call from several threads: a worker pool shares one client, and
    a breaker that miscounts under concurrency is a breaker that opens on a healthy vendor.
    """

    __slots__ = ("_clock", "_failures", "_lock", "_name", "_opened_at", "_policy", "_probing")

    def __init__(self, *, name: str, policy: BreakerPolicy, clock: Clock) -> None:
        self._name = name
        self._policy = policy
        self._clock = clock
        self._lock = threading.Lock()
        self._failures = 0
        self._opened_at: float | None = None
        self._probing = False

    @property
    def name(self) -> str:
        return self._name

    @property
    def state(self) -> CircuitState:
        with self._lock:
            return self._state_locked()

    def allows_call(self) -> bool:
        """Claim the right to make one call.

        In `HALF_OPEN` this admits **exactly one** caller and refuses the rest until that
        probe reports back. A half-open state that let every waiting caller through would
        deliver, on the cooldown's expiry, precisely the burst that the open circuit was
        holding back — the thundering herd, rebuilt by the mechanism meant to prevent it.
        """
        with self._lock:
            state = self._state_locked()
            if state is CircuitState.CLOSED:
                return True
            if state is CircuitState.OPEN:
                return False
            if self._probing:
                return False
            self._probing = True
            self._log_transition(CircuitState.OPEN, CircuitState.HALF_OPEN)
            return True

    def record_success(self) -> None:
        """The vendor answered. Reset, closing the circuit if it was not closed."""
        with self._lock:
            previous = self._state_locked()
            self._failures = 0
            self._opened_at = None
            self._probing = False
            if previous is not CircuitState.CLOSED:
                self._log_transition(previous, CircuitState.CLOSED)

    def record_failure(self) -> None:
        """A vendor *health* failure. A probe failure re-opens for a full cooldown."""
        with self._lock:
            previous = self._state_locked()
            self._failures += 1
            if self._probing or previous is CircuitState.OPEN:
                # The probe failed, or a call that started before the circuit opened
                # finished afterwards. Either way the cooldown starts again from now.
                self._probing = False
                self._opened_at = self._clock.monotonic()
                if previous is not CircuitState.OPEN:
                    self._log_transition(previous, CircuitState.OPEN)
                return
            if self._failures >= self._policy.failure_threshold:
                self._opened_at = self._clock.monotonic()
                self._log_transition(previous, CircuitState.OPEN)

    def _state_locked(self) -> CircuitState:
        if self._opened_at is None:
            return CircuitState.CLOSED
        if self._clock.monotonic() - self._opened_at >= self._policy.cooldown_seconds:
            return CircuitState.HALF_OPEN
        return CircuitState.OPEN

    def _log_transition(self, previous: CircuitState, current: CircuitState) -> None:
        """One line per transition, never one per failure (PV5).

        An open circuit is an alerted operational state with a *duration* threshold, so
        what operations needs is the edge; a line per fast-failed call would bury it and
        would itself become the load during an outage. The alert thresholds are theirs.
        """
        _log.warning(
            "circuit %s -> %s",
            previous.value,
            current.value,
            extra={
                "event": "integration.circuit_transition",
                "vendor": self._name,
                "previous_state": previous.value,
                "state": current.value,
                "consecutive_failures": self._failures,
            },
        )
