"""The message currently being handled, as ambient context (item 10 §12, CZ1-CZ3, PC13).

`causation_event_id` is the **immediate parent message's `event_id`** — one hop, no ancestry
path (FS3). A message emitted while handling another is that other message's child; a message
emitted from a request or a scheduled job has no parent and legitimately carries nothing here.

Like the trace triple, causation is captured from ambient context rather than passed as an
argument, so no contract signature acquires a causation parameter (FS9, A64, PC7). It lives in
`core.events` rather than in `core.observability` because `causation_event_id` *is* an envelope
field and `EventId` is envelope mechanism (OW3) — while the trace triple is observability
context that an HTTP boundary must be able to set, and `interfaces/*` may not import
`core.events` at all (item 3 §4.4).

What is bound here is set by the **consumer runtime** when it begins handling a delivery. That
runtime arrives with the workload slice; until then this context is bound explicitly, and
nothing anywhere depends on it being populated.

`causation_event_id` carries no ordering, no authorization and no idempotency meaning, is
never a foreign key, and is expected to dangle once the parent's partition is archived
(CZ4-CZ10). It is diagnostic lineage and nothing else.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar

from core.events.identity import EventId

__all__ = ("current_causation_event_id", "handling_message")

_CAUSATION: ContextVar[EventId | None] = ContextVar("core_events_causation", default=None)


def current_causation_event_id() -> EventId | None:
    """The `event_id` of the message being handled right now, if any."""
    return _CAUSATION.get()


@contextmanager
def handling_message(event_id: EventId | None) -> Iterator[None]:
    """Bind the message being handled for the duration of a block.

    Accepts `None` explicitly, which binds "no parent": that is how a scheduled job or a
    request-origin path states its origin, and it is a complete state rather than an omission
    (CZ2, PR9). Passing something that is not an `EventId` is refused rather than coerced — a
    `PublicId` or a bare `uuid.UUID` here would put a foreign identity space into an envelope
    slot, which is precisely the confusion ADR-0013 created a distinct type to prevent.
    """
    if event_id is not None and type(event_id) is not EventId:
        raise TypeError(
            f"handling_message() takes an EventId or None, got {type(event_id).__name__}; "
            f"causation is the parent message's identity, of exactly that type"
        )
    token = _CAUSATION.set(event_id)
    try:
        yield
    finally:
        _CAUSATION.reset(token)
