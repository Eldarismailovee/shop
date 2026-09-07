"""Ambient trace and request context, in-process (item 10 §12, PC2, PC7).

Item 10 requires the TCE to be captured from **ambient in-process context** at the instant of
the durable Outbox `INSERT` — never from an argument, so that no `public.py` signature,
command input DTO, selector parameter or payload gains a trace parameter (FS9, A64, PC7). This
module is that context.

`contextvars` is the whole mechanism, and deliberately so:

* **No network I/O** (PC2, A65). Reading a context variable is not a collector call, an
  exporter flush or a remote-sampler lookup, and nothing here can be slow, fail, or sit
  between a `BEGIN` and a `COMMIT`.
* **Correct under concurrency.** A `ContextVar` is per-task and per-thread, so two requests
  served concurrently never see each other's trace, which a module-level global would not
  guarantee.
* **Absence is normal** (FS5, PR3). Every getter answers `None` outside a bound scope. A
  system-origin job legitimately has no `request_id`, and an untraced process legitimately
  has no trace pair; neither is an error and neither is repaired by invention.

### Why this lives in `core.observability`

Item 3 §4.4 opens `core.observability` to `interfaces/*`, and L13 closes `core.outbox` to it.
The trace triple must be settable at the HTTP boundary — that is where a `traceparent` is
adopted and a `request_id` is minted — so it cannot live in the package that boundary may not
import. `core.observability` was already on the frozen allowlist, so no allowlist moves.

### What this is not

It is **not** a place to put anything a decision reads. Item 10's correctness firewall (FW1,
FW4, A63) forbids any conditional, authorization check, policy, selector filter, idempotency
key, dedupe key, ordering expression or routing decision from reading a value here. It holds
no PII, no actor identity and no authorization state (item 10 §22): `request_id` identifies a
request, never the person who made it.

A bridge that populates this from an OpenTelemetry SDK is not part of this slice — item 10
defers the SDK, propagator and instrumentation choice, and the absence of that bridge is the
absence of a call, not a stub. Everything here works, and is exercised, without one.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar

__all__ = (
    "current_request_id",
    "current_span_id",
    "current_trace_id",
    "observability_context",
)

_TRACE_ID: ContextVar[str | None] = ContextVar("core_observability_trace_id", default=None)
_SPAN_ID: ContextVar[str | None] = ContextVar("core_observability_span_id", default=None)
_REQUEST_ID: ContextVar[str | None] = ContextVar("core_observability_request_id", default=None)


def current_trace_id() -> str | None:
    """The trace this process is currently working in, if any."""
    return _TRACE_ID.get()


def current_span_id() -> str | None:
    """The span active right now.

    Read by Outbox capture into `producer_span_id` — the span active when the durable record
    was written. Item 10 SP3/CN3 name that field absolutely so that no consumer, retry or
    replay path can ever put *its* span in a message's slot: this getter answers "what is
    active", and only the emission path is allowed to persist the answer.
    """
    return _SPAN_ID.get()


def current_request_id() -> str | None:
    """The originating synchronous request of this chain, if there was one.

    Absent means system origin (a scheduled job, a reconciliation sweep), which is a complete
    state rather than a missing value (RQ3, PR6).
    """
    return _REQUEST_ID.get()


@contextmanager
def observability_context(
    *,
    trace_id: str | None = None,
    span_id: str | None = None,
    request_id: str | None = None,
) -> Iterator[None]:
    """Bind ambient context for the duration of a block, then restore exactly what was there.

    Every value is optional, and passing none of them is legal: that binds an explicitly
    untraced scope. Restoration uses the tokens `ContextVar.set` returns rather than reading
    and re-setting the previous values, so nested scopes unwind correctly even when a block
    raises.

    Values are stored exactly as given. Normalising a malformed identifier to absent is the
    *capture* boundary's job (`core.events.envelope.normalised_trace_id` and its siblings),
    applied where a value is persisted — so a defect in an inbound header is visible to the
    boundary that adopted it rather than silently smoothed away here.
    """
    tokens = (
        _TRACE_ID.set(trace_id),
        _SPAN_ID.set(span_id),
        _REQUEST_ID.set(request_id),
    )
    try:
        yield
    finally:
        trace_token, span_token, request_token = tokens
        _TRACE_ID.reset(trace_token)
        _SPAN_ID.reset(span_token)
        _REQUEST_ID.reset(request_token)
