"""Observing a consumer delivery, and resolving one already committed (item 8 §21, IX2-IX8).

Usage, and the only sanctioned shape::

    with transaction.atomic():                  # the consumer's handler transaction
        outcome = observe_delivery(
            consumer="<registered consumer>",
            envelope=envelope,
            payload=canonical_payload_text,
        )
        match outcome:
            case FirstDelivery() as delivery:
                with delivery:
                    ...the durable business effect...
                    ...any Outbox rows the effect emits...
                    delivery.complete()
            case DuplicateDelivery():
                ...do nothing; the effect already happened...

An `IntegrityViolation` is raised rather than returned, because it is not an outcome a handler
chooses between: the conflicting delivery is never applied, and the caller's only correct
response is to quarantine and alert.

### The race, and why a unique conflict is not a duplicate

Two connections may insert `(consumer, event_id)` concurrently. One wins; the other's insert
conflicts. **The loser must then read the committed row and compare content** — it may not
assume it lost to a copy of itself:

* Same `event_type`, `schema_version` **and** payload fingerprint → a genuine duplicate
  delivery. At-least-once transport makes this normal (IX4, IX8): the effect already happened
  or is happening, and this delivery does nothing.
* Anything materially different → item 8 IX5's **data-integrity violation**. One `event_id`
  now claims two contents, which is a producer bug, a mis-copied identity or corruption. The
  conflicting delivery is never applied, the recorded first observation is never overwritten,
  and it is quarantined loudly rather than absorbed quietly.

Treating every unique conflict as a duplicate would collapse those two cases into the benign
one, and IX5 would be undetectable in exactly the circumstance it was written for — which is
why the comparison is here and not optional.

The comparison reads the **committed** row. That is deliberate: the losing connection cannot
see the winner's uncommitted insert, so the conflict is only resolvable after the winner
commits, and PostgreSQL's unique index is what makes the loser wait for that.

### Completion never precedes the effect

`complete()` runs inside the caller's transaction, after the effect and after any Outbox rows
(item 8's handler transaction rule). It is never a separate commit, never an `on_commit` hook
and never precedes the effect it records — a completion that outlived a rolled-back effect
would permanently suppress the redelivery that would have retried it. No provider I/O happens
inside this transaction (IX-handler rule): external work is a post-commit port call.

### What is never rewritten here

The immutable half of the row — identity, envelope, the four TCE fields and the payload — is
written once, at first observation. `complete()` and `record_attempt()` name explicit mutable
column lists, and every column they name is from the mutable group. That is what makes item 10
A62 ("one writer per trace column") and A66 (write-once, no back-fill) checkable statically
rather than asserted in prose.
"""

from __future__ import annotations

from types import TracebackType

from django.db import IntegrityError, transaction
from django.db.models import F
from django.utils import timezone

from core.events.codec import fingerprint
from core.events.envelope import Envelope, normalised_span_id, normalised_trace_id
from core.events.identity import EventId
from core.inbox.errors import (
    IngestOutsideTransaction,
    IntegrityViolation,
    UnknownDelivery,
)
from core.inbox.models import DeliveryState, InboxDelivery

__all__ = (
    "DeliveryOutcome",
    "DuplicateDelivery",
    "FirstDelivery",
    "observe_delivery",
    "record_attempt",
)

#: The identity columns IX5 compares, and the only ones the resolution path reads. Named
#: explicitly so the heavy `payload` column is not pulled on every duplicate delivery: the
#: fingerprint is over exactly those bytes, so comparing digests decides the question without
#: loading them.
_RESOLUTION_FIELDS = (
    "id",
    "consumer",
    "event_id",
    "event_type",
    "schema_version",
    "payload_fingerprint",
    "state",
)

#: The mutable delivery-processing columns, and the complete list of what any path in this
#: module may write after first observation. Every immutable column — identity, envelope, the
#: four TCE fields, payload, fingerprint — is absent by construction (FS6, A66, CN3, A62).
_MUTABLE_FIELDS = (
    "state",
    "attempts",
    "processing_trace_id",
    "processing_span_id",
    "completed_at",
)


class FirstDelivery:
    """This consumer has not seen this `event_id` before; the effect is this caller's to run.

    Used as a context manager, so the effect cannot be forgotten and a completion cannot be
    silently skipped::

        with delivery:
            ...effect...
            delivery.complete()

    Leaving the block without completing raises. That is not ceremony: a delivery row that
    committed as `RECEIVED` while its effect also committed would look, on redelivery, like
    work that never happened, and the effect would run twice.
    """

    __slots__ = ("_completed", "_entered", "_row_id", "event_id")

    def __init__(self, *, row_id: int, event_id: EventId) -> None:
        self._row_id = row_id
        self._entered = False
        self._completed = False
        self.event_id = event_id

    def __enter__(self) -> FirstDelivery:
        self._entered = True
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        # An exception on the way out is the caller's failure, and the whole transaction —
        # this claim included — rolls back. Only a *successful* block that forgot to complete
        # is a defect worth naming.
        if exc_type is None and not self._completed:
            raise UnknownDelivery(
                "the delivery block ended without complete(); a delivery that commits as "
                "RECEIVED beside a committed effect will re-run that effect on redelivery"
            )

    def complete(self) -> None:
        """Record that the effect committed, in the same transaction as the effect."""
        if not self._entered:
            raise UnknownDelivery(
                "complete() is called inside `with delivery:`; the block is what guarantees a "
                "delivery cannot be committed without its completion"
            )
        if self._completed:
            raise UnknownDelivery("this delivery has already been completed")

        updated = InboxDelivery.objects.filter(pk=self._row_id).update(
            state=DeliveryState.HANDLED,
            completed_at=timezone.now(),
        )
        if not updated:
            raise UnknownDelivery(
                "the delivery row disappeared before completion; it was never observed, or "
                "something outside this mechanism deleted it"
            )
        self._completed = True


class DuplicateDelivery:
    """This consumer has already seen this exact `event_id` with this exact content.

    At-least-once delivery makes this ordinary, not exceptional: a crash between the effect's
    commit and the acknowledgement, a lost ack, a broker redelivery after a restart. The
    correct response is to do nothing and let the transport dispose of the delivery. It is
    **not** dead-lettered (item 9 AM5, AM6, C74).

    `already_handled` distinguishes "the effect committed" from "a concurrent attempt claimed
    this delivery and has not committed yet". Both mean *this* caller runs no effect; only the
    first means the work is finished, which is what an operator triaging a stuck delivery
    needs to know.
    """

    __slots__ = ("already_handled",)

    def __init__(self, *, already_handled: bool) -> None:
        self.already_handled = already_handled


DeliveryOutcome = FirstDelivery | DuplicateDelivery


def observe_delivery(
    *,
    consumer: str,
    envelope: Envelope,
    payload: str,
) -> DeliveryOutcome:
    """Record first-seen identity for `(consumer, event_id)`, or resolve against the committed row.

    `payload` is the **canonical text that arrived**, not a re-serialized object: the stored
    bytes are the replay material (item 9 C77) and the fingerprint is taken over exactly them,
    so a value rebuilt through today's DTOs would fingerprint a different message.
    """
    _require_consumer(consumer)
    if type(payload) is not str:
        raise TypeError(f"payload must be canonical text, got {type(payload).__name__}")

    if not transaction.get_connection().in_atomic_block:
        raise IngestOutsideTransaction(
            "observe_delivery() runs inside the handler transaction; a claim that commits on "
            "its own would survive a rolled-back effect and suppress the retry"
        )

    digest = fingerprint(payload)
    row_id = _try_insert(consumer=consumer, envelope=envelope, payload=payload, digest=digest)
    if row_id is not None:
        return FirstDelivery(row_id=row_id, event_id=envelope.event_id)

    return _resolve(consumer=consumer, envelope=envelope, digest=digest)


def record_attempt(
    *,
    consumer: str,
    envelope: Envelope,
    processing_trace_id: str | None = None,
    processing_span_id: str | None = None,
) -> None:
    """Count an attempt and record **this delivery's own** trace context (item 10 CN8).

    Separate from the message's `trace_id`/`producer_span_id`, which this function cannot
    reach: those columns are not in `_MUTABLE_FIELDS`, and CN3/A62 forbid a consumer writing
    its span into a message's slot. A retry is the same delivery with a new span and unchanged
    message fields (item 10 §18).

    The pair is normalised together, so a half-present processing pair never reaches the
    column pair the `CHECK` constrains — the same PR2 discipline the message's own pair gets.
    """
    trace_id = normalised_trace_id(processing_trace_id)
    span_id = normalised_span_id(processing_span_id)
    if (trace_id is None) != (span_id is None):
        trace_id = None
        span_id = None

    updated = InboxDelivery.objects.filter(
        consumer=consumer, event_id=envelope.event_id.value
    ).update(
        # Incremented in SQL. A read-modify-write in Python would lose a concurrent attempt's
        # increment, and a count that undercounts is exactly the count a bounded retry budget
        # must not have.
        attempts=F("attempts") + 1,
        processing_trace_id=trace_id,
        processing_span_id=span_id,
    )
    if not updated:
        raise UnknownDelivery(
            f"no delivery of {envelope.event_id} exists for consumer {consumer!r}; an attempt "
            f"is recorded against an observed delivery, never against a guess"
        )


def _try_insert(
    *,
    consumer: str,
    envelope: Envelope,
    payload: str,
    digest: str,
) -> int | None:
    """Insert first-seen identity inside a savepoint, so a uniqueness race is recoverable.

    Nesting is a savepoint implementation detail of one handler transaction (item 4 §12), not
    an independent transaction: nothing here commits, and the outer transaction still owns
    every durable write.
    """
    row = InboxDelivery(
        consumer=consumer,
        event_id=envelope.event_id.value,
        event_type=envelope.event_type,
        schema_version=envelope.schema_version,
        occurred_at=envelope.occurred_at,
        trace_id=envelope.trace_id,
        producer_span_id=envelope.producer_span_id,
        request_id=envelope.request_id,
        causation_event_id=(
            envelope.causation_event_id.value if envelope.causation_event_id is not None else None
        ),
        payload=payload,
        payload_fingerprint=digest,
        first_seen_at=timezone.now(),
        state=DeliveryState.RECEIVED,
    )
    try:
        with transaction.atomic():
            row.save(force_insert=True)
    except IntegrityError:
        return None
    return row.pk


def _resolve(*, consumer: str, envelope: Envelope, digest: str) -> DeliveryOutcome:
    """Compare the arriving message against the committed first observation (IX4, IX5).

    Reads bounded identity columns only. The payload itself is never loaded: the fingerprint
    is over exactly the stored bytes, so comparing digests answers the question without pulling
    a quarter-megabyte of text on every duplicate.
    """
    committed = (
        InboxDelivery.objects.only(*_RESOLUTION_FIELDS)
        .filter(consumer=consumer, event_id=envelope.event_id.value)
        .first()
    )
    if committed is None:
        # The winning contender's transaction rolled back after all, so no row exists durably.
        # The delivery is unobserved again and the transport will redeliver it; reporting it as
        # a duplicate here would suppress an effect that never ran.
        raise IntegrityViolation(
            "the conflicting delivery vanished before it could be compared; the message is "
            "unobserved and must be redelivered rather than treated as handled",
            consumer=consumer,
            first_seen_fingerprint="",
            arriving_fingerprint=digest,
        )

    same_identity = (
        committed.event_type == envelope.event_type
        and committed.schema_version == envelope.schema_version
        and committed.payload_fingerprint == digest
    )
    if not same_identity:
        raise IntegrityViolation(
            f"event_id {envelope.event_id} was first seen by {consumer!r} as "
            f"{committed.event_type}@{committed.schema_version} with fingerprint "
            f"{committed.payload_fingerprint}, and has now arrived as "
            f"{envelope.event_type}@{envelope.schema_version} with fingerprint {digest}; "
            f"one identity claiming two contents is an integrity violation, not a duplicate",
            consumer=consumer,
            first_seen_fingerprint=committed.payload_fingerprint,
            arriving_fingerprint=digest,
        )

    return DuplicateDelivery(already_handled=committed.state == DeliveryState.HANDLED)


def _require_consumer(consumer: str) -> None:
    if type(consumer) is not str or not consumer:
        raise TypeError(
            "consumer must be the registered consumer's non-empty dotted name; the unit of "
            "failure and replay is the consumer delivery, so it is never optional"
        )
