"""The message envelope (item 8 §10.1) and its trace/causality extension (item 10 §5).

The **semantic envelope** is kind-independent, message-independent metadata, frozen as
exactly four fields: `event_id`, `event_type`, `schema_version`, `occurred_at` (EN1). Item 8
reserved one extension point for the causality/trace fields (EN6); item 10 spent it on the
closed four-field TCE — `trace_id`, `producer_span_id`, `request_id`, `causation_event_id`
(FS1, FS2). There is no second extension point, and a field that is not one of those eight
does not exist.

Rejected by name, so that none of them arrives later disguised as a convenience: a generic
`correlation_id` (every precise meaning it could carry is already carried by one of the
eight); a metadata bag in any spelling — `meta`, `extra`, `context`, `attributes`,
`headers`, `tags`, `annotations`, `dict[str, Any]`, "one JSON column for future use";
OpenTelemetry `baggage`; W3C `tracestate`; an ancestry list or causal path; and any
transport concern — queue, exchange, routing key, retry counter, attempt number, delivery
id, broker timestamp, worker identity, priority (EN3, EN7, FS3, §10).

The envelope carries **no business data** (EN4): a value a handler would branch on is, by
definition, payload. And no envelope field decides authorization, identity, money,
idempotency, ordering or routing — trace metadata in particular is observability only, so
no sampling decision or observability outage can change a business outcome (RQ4, CZ8, FS8).

Every TCE field is optional **by construction** (FS5), and absence is a complete state
rather than a partial one (FS10): a message emitted from a system-origin job legitimately
has no `request_id`, and one emitted directly from a request legitimately has no
`causation_event_id`. A reader tolerates any of the four being absent and still processes
the message.

What this module deliberately does not do: capture. Populating the TCE happens at the
Outbox INSERT, inside the business transaction, from the ambient context (§12) — no
`public.py` signature ever gains a trace parameter (FS9). PR2's pair-integrity handling
(exactly one of `trace_id`/`producer_span_id` present is an observability defect that is
recorded and alerted while processing continues normally) is capture-and-consume behaviour,
so this type **permits** that state rather than rejecting it: raising here would stop the
processing PR2 requires to continue. Both belong to the Outbox/Inbox slice.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timedelta

from core.events.identity import EventId

__all__ = ("Envelope",)

#: NM1/NM2/NM3: lowercase dot-separated segments, the first being the semantic owner's
#: stable module name and the rest naming the fact or the work item. Owner-qualification is
#: what makes a type globally unique without a central authority. The prohibitions NM4-NM6
#: state on *meaning* — no table or queue name, no version suffix, no vendor as the first
#: segment — are registry-review matters, not grammar.
_EVENT_TYPE = re.compile(r"\A[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*)+\Z")

#: TR2: a W3C Trace Context trace-id — 16 bytes as 32 lowercase hex characters, all-zero
#: being invalid.
_TRACE_ID = re.compile(r"\A(?!0{32}\Z)[0-9a-f]{32}\Z")

#: SP4: a W3C Trace Context span-id — 8 bytes as 16 lowercase hex characters, all-zero
#: being invalid.
_SPAN_ID = re.compile(r"\A(?!0{16}\Z)[0-9a-f]{16}\Z")

#: RQ6: a bounded-length opaque token. The platform parses no structure out of it, derives
#: nothing from it and sorts nothing by it. The bound is a Phase-1 choice.
_REQUEST_ID_MAX_LENGTH = 128
_REQUEST_ID = re.compile(r"\A[\x21-\x7e]+\Z")

#: PR6: `request_id` is present or absent, with no third state. These are the stand-ins
#: that would smuggle one in.
_REQUEST_ID_PLACEHOLDERS = frozenset({"-", "none", "null", "unknown"})


@dataclass(frozen=True, slots=True, kw_only=True)
class Envelope:
    """The eight frozen envelope slots, validated structurally.

    `event_id` identifies one emission; `event_type` and `schema_version` together select
    the registered contract; `occurred_at` is when the producer's fact became true — not a
    publication, enqueue, delivery or handling time, and not an ordering key (TS1, TS4).

    `schema_version` versions the **payload contract and only the payload contract**. It is
    not a source version, not a revision and not an ordering signal: no staleness guard or
    upsert predicate may ever read it (SV2, OR6, A47).
    """

    event_id: EventId
    event_type: str
    schema_version: int
    occurred_at: datetime
    trace_id: str | None = None
    producer_span_id: str | None = None
    request_id: str | None = None
    causation_event_id: EventId | None = None

    def __post_init__(self) -> None:
        if type(self.event_id) is not EventId:
            raise TypeError(
                f"event_id must be an EventId, got {type(self.event_id).__name__}; a bare "
                f"UUID and a PublicId are different identity spaces"
            )
        _require_event_type(self.event_type)
        _require_schema_version(self.schema_version)
        _require_occurred_at(self.occurred_at)

        if self.trace_id is not None:
            _require_pattern(_TRACE_ID, self.trace_id, "trace_id", "32 lowercase hex characters")
        if self.producer_span_id is not None:
            _require_pattern(
                _SPAN_ID, self.producer_span_id, "producer_span_id", "16 lowercase hex characters"
            )
        if self.request_id is not None:
            _require_request_id(self.request_id)
        if self.causation_event_id is not None:
            _require_causation(self.causation_event_id, self.event_id)


def _require_event_type(value: str) -> None:
    if type(value) is not str:
        raise TypeError(f"event_type must be a string, got {type(value).__name__}")
    if not _EVENT_TYPE.fullmatch(value):
        raise ValueError(
            f"{value!r} is not an owner-qualified event_type: lowercase dot-separated "
            f"segments matching [a-z][a-z0-9_]*, the first being the semantic owner"
        )


def _require_schema_version(value: int) -> None:
    # Exact type, so `True` cannot become version 1.
    if type(value) is not int:
        raise TypeError(f"schema_version must be an int, got {type(value).__name__}")
    if value < 1:
        raise ValueError(f"schema_version starts at 1 and strictly increases, got {value}")


def _require_occurred_at(value: datetime) -> None:
    if type(value) is not datetime:
        raise TypeError(f"occurred_at must be a datetime, got {type(value).__name__}")
    offset = value.utcoffset()
    if offset is None:
        raise ValueError("occurred_at must be timezone-aware; a naive datetime is a violation")
    if offset != timedelta(0):
        raise ValueError(
            f"occurred_at must be UTC, got an offset of {offset}; one instant has one "
            f"spelling, which is what makes serialization deterministic"
        )


def _require_pattern(pattern: re.Pattern[str], value: str, field: str, shape: str) -> None:
    if type(value) is not str:
        raise TypeError(f"{field} must be a string, got {type(value).__name__}")
    if not pattern.fullmatch(value):
        raise ValueError(
            f"{field} must be {shape}, and the all-zero identifier is invalid; a malformed "
            f"value is normalised to absent at capture, never repaired by invention"
        )


def _require_request_id(value: str) -> None:
    if type(value) is not str:
        raise TypeError(f"request_id must be a string, got {type(value).__name__}")
    if len(value) > _REQUEST_ID_MAX_LENGTH:
        raise ValueError(
            f"request_id must be at most {_REQUEST_ID_MAX_LENGTH} characters, got {len(value)}"
        )
    if not _REQUEST_ID.fullmatch(value) or value.lower() in _REQUEST_ID_PLACEHOLDERS:
        raise ValueError(
            f"{value!r} is not an opaque request_id token; absence means system origin and "
            f"is spelled by leaving the field out, never by a placeholder"
        )


def _require_causation(value: EventId, event_id: EventId) -> None:
    if type(value) is not EventId:
        raise TypeError(
            f"causation_event_id must be an EventId, got {type(value).__name__}; it is the "
            f"immediate parent message's identity, of exactly that type"
        )
    if value == event_id:
        # CZ6: self-causation is a defect. A dangling parent, by contrast, is expected once
        # the parent's partition is archived and is never a validation failure (CZ10).
        raise ValueError("causation_event_id must not equal event_id; self-causation is a defect")
