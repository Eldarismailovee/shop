"""TCE capture at the durable `INSERT` (item 10 §12, PC1-PC7, PR2-PR5).

One function, and every rule item 10 states about capture is visible in it:

* **Ambient, not argument** (PC7, FS9, A64). The four values are read from
  `core.observability.context` and `core.events.context`. No caller passes them, so no
  `public.py` signature, command input DTO, selector parameter or payload ever grows a trace
  parameter.
* **No network I/O** (PC2, A65). Reading a `ContextVar` is the whole mechanism. Nothing here
  contacts a collector, flushes an exporter or asks a remote sampler, so nothing here can sit
  between a `BEGIN` and a `COMMIT`.
* **Never fails the business transaction** (PC3). Absence is a legal, complete TCE state
  (FS5, FS10), so the failure mode is an absent field, not a raised exception. This function
  has no error path.
* **Not conditional on sampling** (PC4, SM3a). The identifiers are captured whenever they
  exist, whatever the sampler decided. No sampled flag is persisted (§23), and no
  observability outage can change what is durably written.
* **Normalised, never invented** (PR3, PR5). A malformed, all-zero or placeholder value
  becomes *absent*. Nothing is padded, re-cased, defaulted or back-filled.
* **The pair rule is permitted, not enforced** (PR2). Exactly one of
  `trace_id`/`producer_span_id` present is a TCE **integrity defect**: it is reported and
  alerted as an observability defect while the message is read as untraced and processing
  continues normally. Raising here would stop precisely the processing PR2 requires to
  continue, so this function returns the defect alongside the state rather than rejecting it.

Capture happens **once**, at message creation. Item 10 FS6/A66 make all four fields write-once
thereafter: no relay, retry, redelivery, replay, reconciliation, admin action or management
command may rewrite them or complete one that emission left empty. That is enforced physically
by `core/outbox/emit.py` and `core/inbox/delivery.py` naming explicit mutable column lists that
exclude every TCE column, and statically by the `A62`/`A66` rules in `tools/arch_check`.
"""

from __future__ import annotations

from dataclasses import dataclass

from core.events.context import current_causation_event_id
from core.events.envelope import (
    normalised_request_id,
    normalised_span_id,
    normalised_trace_id,
)
from core.events.identity import EventId
from core.observability.context import (
    current_request_id,
    current_span_id,
    current_trace_id,
)

__all__ = ("TraceCausalityState", "capture")


@dataclass(frozen=True, slots=True, kw_only=True)
class TraceCausalityState:
    """The four TCE slots as captured, plus whether the trace pair was broken.

    Item 10 FS10 makes **state** — a value *or* a legitimate absence, per field — the unit that
    is captured, copied, retained and compared. "Four fields" never means "four non-empty
    values": a first hop from a request has no causation, and a system-origin hop has no
    `request_id` either. Both are complete states.

    `pair_defect` is not a fifth TCE field and is never persisted in one. It is the PR2 signal
    that exactly one half of the trace pair arrived, which the caller reports and alerts on as
    an observability defect. The message itself is simply untraced.
    """

    trace_id: str | None = None
    producer_span_id: str | None = None
    request_id: str | None = None
    causation_event_id: EventId | None = None
    pair_defect: bool = False


def capture(*, event_id: EventId) -> TraceCausalityState:
    """Read the ambient TCE state for a message being written durably right now.

    `event_id` is taken only to enforce CZ6: a message may never cause itself. If the ambient
    handling context somehow names this very message — a producer emitting a child with its
    parent's identity, or a runtime that failed to rebind context — the causation slot is left
    absent rather than made self-referential, because a self-causing record is a defect that a
    later reader cannot distinguish from a genuine loop.
    """
    trace_id = normalised_trace_id(current_trace_id())
    span_id = normalised_span_id(current_span_id())

    # PR2: both, or neither. Exactly one is a defect that is reported, not repaired: the
    # missing half cannot be invented, and keeping the present half would record a trace
    # context that no backend can resolve.
    pair_defect = (trace_id is None) != (span_id is None)
    if pair_defect:
        trace_id = None
        span_id = None

    causation = current_causation_event_id()
    if causation is not None and causation == event_id:
        causation = None

    return TraceCausalityState(
        trace_id=trace_id,
        producer_span_id=span_id,
        request_id=normalised_request_id(current_request_id()),
        causation_event_id=causation,
        pair_defect=pair_defect,
    )
