"""Writing a message to the Outbox (item 8's handler transaction rule, ADR-0007, ADR-0011).

Usage, and the only sanctioned shape::

    with transaction.atomic():              # the caller's business transaction
        ...the durable business effect...
        emit(
            event_type="<registered type>",
            schema_version=1,
            occurred_at=when_the_fact_became_true,
            payload={...},
        )

The row is inserted **inside the caller's transaction**, so the fact and its message become
durable at the same instant and a rollback leaves neither. Nothing is published to a broker
here: direct producer-to-broker publishing is forbidden (item 9 §25), a business commit never
depends on the broker being reachable, and the relay is a separate later reader of the table.

There is **no network I/O on this path at all** — not to a broker, not to a collector, not to
an exporter, not to a remote sampler (PC2, A65). Capture reads ambient in-process context and
nothing else.

### What this function deliberately does not do

* **It does not check the registry.** Item 8 RI11 requires every emission site to resolve to a
  registered `(event_type, schema_version)`, and A42 makes that a build-time check. The
  registry ships empty and no `event_type` exists yet, so enforcing it at runtime today would
  mean either a check that rejects everything or a check that is switched off — and item 14
  NF10 forbids settings-gated unreachable code. The obligation is recorded, not silently
  dropped: it belongs to the slice that registers the first message.
* **It does not schedule, route or choose a failure domain.** Routing is transport metadata
  assigned **per consumer declaration**, never by the producer (item 9 RT3, RT12).
* **It does not accept trace arguments.** The four TCE values come from ambient context
  (PC7, FS9, A64). A caller cannot pass one, cannot override one, and cannot suppress one.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from django.db import transaction
from django.utils import timezone

from core.events.codec import encode, fingerprint
from core.events.envelope import Envelope
from core.events.identity import EventId
from core.outbox.capture import TraceCausalityState, capture
from core.outbox.errors import EmissionOutsideTransaction
from core.outbox.models import OutboxMessage, RelayState

__all__ = ("Emission", "emit")


class Emission:
    """What was written, for the caller and for the observability defect PR2 requires.

    `envelope` is the message exactly as persisted — the same eight slots, with the same
    absences. It is returned so that a caller can log or assert on the emission without
    re-reading the row, and so that a test can compare captured state against stored state
    without either being reconstructed.

    `pair_defect` reports item 10 PR2: the ambient context offered exactly one half of the
    trace pair. The message was written and is being processed normally — that is what PR2
    requires — and the caller's obligation is to record and alert on the defect, never to
    fail the business transaction over it.
    """

    __slots__ = ("envelope", "pair_defect", "row_id")

    def __init__(self, *, row_id: int, envelope: Envelope, pair_defect: bool) -> None:
        self.row_id = row_id
        self.envelope = envelope
        self.pair_defect = pair_defect


def emit(
    *,
    event_type: str,
    schema_version: int,
    occurred_at: datetime,
    payload: Any,
) -> Emission:
    """Write one message durably, inside the caller's transaction.

    `occurred_at` is required and has no default. It is when the producer's fact became true,
    which only the producer knows; defaulting it to "now" would silently turn business time
    into write time, and item 8 TS1/TS4 keep them apart. It is also not an ordering key, and
    nothing here sorts by it.
    """
    if not transaction.get_connection().in_atomic_block:
        raise EmissionOutsideTransaction(
            "emit() runs inside the transaction that performs the business effect; in "
            "autocommit the message would commit on its own, and a later rollback would "
            "leave a message announcing a fact that never happened"
        )

    event_id = EventId.new()
    trace = capture(event_id=event_id)

    canonical_payload = encode(payload)

    # Constructing the envelope validates every slot before anything is written: the
    # `event_type` grammar, `schema_version >= 1`, an aware-UTC `occurred_at`, the trace
    # identifier shapes and CZ6's self-causation ban. A defect therefore surfaces as a
    # refusal to emit rather than as a durable row nobody can decode.
    envelope = Envelope(
        event_id=event_id,
        event_type=event_type,
        schema_version=schema_version,
        occurred_at=occurred_at,
        trace_id=trace.trace_id,
        producer_span_id=trace.producer_span_id,
        request_id=trace.request_id,
        causation_event_id=trace.causation_event_id,
    )

    row = _row_for(envelope, trace, canonical_payload)
    row.save(force_insert=True)
    return Emission(row_id=row.pk, envelope=envelope, pair_defect=trace.pair_defect)


def _row_for(
    envelope: Envelope,
    trace: TraceCausalityState,
    canonical_payload: str,
) -> OutboxMessage:
    """Build the durable row from validated state.

    Every immutable column is assigned exactly here, at creation, and nowhere else in the
    package — which is what makes item 10 A62's "one writer per trace column" and A66's
    write-once rule checkable rather than aspirational.
    """
    now = timezone.now()
    return OutboxMessage(
        event_id=envelope.event_id.value,
        event_type=envelope.event_type,
        schema_version=envelope.schema_version,
        occurred_at=envelope.occurred_at,
        trace_id=trace.trace_id,
        producer_span_id=trace.producer_span_id,
        request_id=trace.request_id,
        causation_event_id=(
            trace.causation_event_id.value if trace.causation_event_id is not None else None
        ),
        payload=canonical_payload,
        payload_fingerprint=fingerprint(canonical_payload),
        relay_state=RelayState.PENDING,
        # The transport's clock, deliberately not `occurred_at`: a fact that became true an
        # hour ago is still eligible for relay now, and a scheduled emission must never be
        # able to rewrite business time.
        available_at=now,
    )
