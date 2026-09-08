"""`BaseClient` — the standard adapter every outbound vendor call goes through.

> Master `# 20.8`: *"Каждый outbound integration client наследует общие гарантии"* —
> explicit timeout, circuit breaker, bounded retries, and a vendor payload that never
> reaches a domain directly.
>
> Item 9 PV7: *"`integrations/*`'s `BaseClient` is their home."*

This module composes the four mechanisms and owns exactly one decision that none of them
can make alone: **what a given outcome means for the safety of repeating it**. Everything
else it delegates.

### The classification, which is the whole substance

```text
NotSent                          nothing arrived      → repeat, always safe
Interrupted                      unknown              → §27: repeat only if declared safe
429 / 503                        refused at the edge  → repeat, always safe
408 / 500 / 502 / 504            unknown              → §27: repeat only if declared safe
Malformed                        broken exchange      → never repeat; a human
anything else (2xx, 3xx, 4xx)    delivered, answered  → return it; the adapter decides
```

The second and fourth rows are the ones worth reading twice. A `500` is not a polite "try
again": the request reached the provider and blew up *while being processed*, so it may
have applied. Retrying it on a non-idempotent operation is item 9 AX1's forbidden
inference wearing a status code, and for a payment it is a double charge (AX6). A `503` or
a `429`, by contrast, is a refusal at the edge before any processing, and is safe to
repeat for any operation. Collapsing all of `5xx` into one "retryable" bucket — the usual
shape — silently loses that distinction.

A `4xx` other than `408`/`429` is returned, not raised. The provider is healthy and has
answered; whether "declined" is a business outcome, a permanent rejection (TF-B) or a bug
in our request is **vendor knowledge**, and TB6 puts that judgment in the package that owns
the protocol. Anti-corruption lives there too: the raw payload never travels past it.

### What is deliberately not here

* **The retry that survives an outage.** These bounds are seconds, held in-process. A real
  provider outage exhausts them, fails, and becomes the caller's *message* retry with
  delayed scheduling (item 9 §18–§20, BO5). One is a blip; the other is an outage.
* **Resolving ambiguity.** `AmbiguousOutcome` is handed up. The status lookup or
  reconciliation that settles it belongs to the workflow's state machine in
  `application/<a>` (AX3–AX5), and a transport that guessed would be guessing about money.
* **A rate limiter.** PV1/PV7 place one here, and its parameters are a specific provider's
  published contract. There is no provider yet, and a limiter configured to "unlimited" is
  a no-op adapter — forbidden by name (item 14 NF4). It arrives with the first vendor.
"""

from __future__ import annotations

import logging
import random
from enum import Enum

from integrations.base.circuit_breaker import BreakerPolicy, CircuitBreaker, CircuitState
from integrations.base.clock import Clock, SystemClock
from integrations.base.faults import (
    AmbiguousOutcome,
    CircuitOpen,
    VendorFault,
    VendorProtocolError,
    VendorUnavailable,
    VendorUnreachable,
)
from integrations.base.retry import (
    RetryPolicy,
    RetrySafety,
    backoff_seconds,
    clamped_retry_after,
)
from integrations.base.transport import (
    Interrupted,
    Malformed,
    NotSent,
    Transport,
    VendorRequest,
    VendorResponse,
)

__all__ = ("BaseClient",)

_log = logging.getLogger("integrations.client")

#: Refused at the edge: rate limited, or the service is deliberately not serving. The
#: provider states that it did not process the request, so a repeat cannot duplicate it.
_REFUSED_STATUSES = frozenset({429, 503})

#: Delivered and then failed, or timed out somewhere behind the edge. Whether it applied
#: is unknown, so these are treated exactly like a dropped connection (§27).
_AMBIGUOUS_STATUSES = frozenset({408, 500, 502, 504})


class _Outcome(Enum):
    """What one attempt established. Ordered by what the caller may do next."""

    #: Nothing was delivered; repeating is safe for every operation.
    NOT_DELIVERED = "not_delivered"
    #: Delivered and refused before processing; repeating is safe for every operation.
    REFUSED = "refused"
    #: Delivered, and it is unknown whether it applied.
    AMBIGUOUS = "ambiguous"


class BaseClient:
    """One vendor, one breaker, one retry policy (PV6).

    The transport is injected rather than constructed here, which is what lets the retry
    and breaker behaviour be proved against a scripted transport with no network and a
    clock that does not really wait.
    """

    __slots__ = ("_breaker", "_clock", "_retry", "_rng", "_transport", "_vendor")

    def __init__(
        self,
        *,
        vendor: str,
        transport: Transport,
        retry: RetryPolicy,
        breaker: BreakerPolicy,
        clock: Clock | None = None,
        rng: random.Random | None = None,
    ) -> None:
        self._vendor = vendor
        self._transport = transport
        self._retry = retry
        self._clock = clock if clock is not None else SystemClock()
        self._rng = rng if rng is not None else random.Random()
        # Built here, from the same clock, so a client can never hold a breaker that
        # measures its cooldown against a different notion of time.
        self._breaker = CircuitBreaker(name=vendor, policy=breaker, clock=self._clock)

    @property
    def vendor(self) -> str:
        return self._vendor

    @property
    def circuit_state(self) -> CircuitState:
        return self._breaker.state

    def send(
        self,
        request: VendorRequest,
        *,
        operation: str,
        retry_safety: RetrySafety,
    ) -> VendorResponse:
        """Perform `request`, retrying within bounds, or raise a `VendorFault`.

        `retry_safety` has no default anywhere: the transport cannot know whether repeating
        this particular operation is safe, and the one thing it must never do is assume so
        (AX1). `operation` is a stable label — `"authorize"`, `"fetch_stock"` — that names
        the call in logs and in faults without carrying a URL, a query string or a payload.
        """
        started = self._clock.monotonic()
        attempts = 0
        last: _Outcome = _Outcome.NOT_DELIVERED
        last_detail = ""

        while True:
            remaining = self._retry.max_age_seconds - (self._clock.monotonic() - started)
            if remaining <= 0:
                break

            if not self._breaker.allows_call():
                # PV4: fast-failing changes how long the worker is held, never what
                # happens to the work. The caller's message keeps its own retry bounds.
                raise self._fault(
                    CircuitOpen,
                    operation=operation,
                    attempts=attempts,
                    started=started,
                    detail="circuit open",
                )

            attempts += 1
            retry_after_raw: str | None = None
            last_status: int | None = None
            try:
                response = self._transport.send(request, budget_seconds=remaining)
            except NotSent as error:
                self._breaker.record_failure()
                last, last_detail = _Outcome.NOT_DELIVERED, error.detail
            except Interrupted as error:
                self._breaker.record_failure()
                last, last_detail = _Outcome.AMBIGUOUS, error.detail
            except Malformed as error:
                # Neither a success nor a health failure: an unusable URL is our defect and
                # an undecodable body is a contract change. Charging either to the vendor's
                # breaker would open a circuit against a provider that is working fine, and
                # item 9 TD3 forbids dressing a defect as a provider failure.
                self._log_attempt(operation, attempts, "malformed", error.detail, None)
                raise self._fault(
                    VendorProtocolError,
                    operation=operation,
                    attempts=attempts,
                    started=started,
                    detail=error.detail,
                ) from error
            else:
                status = last_status = response.status_code
                retry_after_raw = response.header("Retry-After")
                if status in _REFUSED_STATUSES:
                    self._breaker.record_failure()
                    last, last_detail = _Outcome.REFUSED, f"HTTP {status}"
                elif status in _AMBIGUOUS_STATUSES:
                    self._breaker.record_failure()
                    last, last_detail = _Outcome.AMBIGUOUS, f"HTTP {status}"
                else:
                    self._breaker.record_success()
                    self._log_attempt(operation, attempts, "answered", "", status)
                    return response

            self._log_attempt(operation, attempts, last.value, last_detail, last_status)

            if last is _Outcome.AMBIGUOUS and not retry_safety.repeatable_after_ambiguity:
                # AX5: the transport's role is bounded — it stops and hands the workflow a
                # durable ambiguous outcome to resolve. It never guesses.
                break
            if attempts >= self._retry.max_attempts:
                break

            delay = backoff_seconds(self._retry, completed_attempts=attempts, rng=self._rng)
            # BO3: a provider's own `Retry-After` informs scheduling and never overrides a
            # bound. It is clamped to the policy's ceiling, and it can only make the client
            # wait *longer* than it had planned to — never shorter, which would let a
            # provider talk us into the tight loop BO4 forbids.
            hinted = clamped_retry_after(retry_after_raw, policy=self._retry)
            if hinted is not None:
                delay = max(delay, hinted)
            left = self._retry.max_age_seconds - (self._clock.monotonic() - started)
            if delay >= left:
                # Sleeping past the age bound would spend the remaining budget on waiting
                # and leave no room for the attempt the wait was for.
                break
            self._clock.sleep(delay)

        raise self._fault(
            _TERMINAL_FAULTS[last],
            operation=operation,
            attempts=attempts,
            started=started,
            detail=last_detail,
        )

    def _fault(
        self,
        kind: type[VendorFault],
        *,
        operation: str,
        attempts: int,
        started: float,
        detail: str,
    ) -> VendorFault:
        return kind(
            vendor=self._vendor,
            operation=operation,
            attempts=attempts,
            elapsed_seconds=self._clock.monotonic() - started,
            detail=detail,
        )

    def _log_attempt(
        self, operation: str, attempt: int, outcome: str, detail: str, status: int | None
    ) -> None:
        """One structured line per attempt.

        It carries the vendor, the operation label and the outcome, and nothing else: no
        URL — a query string is a documented place for a token to hide — no header, no
        body, no credential (master `# 21`, item 10 §11).
        """
        context = {
            "event": "integration.attempt",
            "vendor": self._vendor,
            "operation": operation,
            "attempt": attempt,
            "outcome": outcome,
        }
        if status is not None:
            context["status_code"] = status
        if detail:
            context["detail"] = detail
        _log.info("vendor call %s", outcome, extra=context)


#: What the last attempt established, as the fault the caller finally sees.
_TERMINAL_FAULTS: dict[_Outcome, type[VendorFault]] = {
    _Outcome.NOT_DELIVERED: VendorUnreachable,
    _Outcome.REFUSED: VendorUnavailable,
    _Outcome.AMBIGUOUS: AmbiguousOutcome,
}
