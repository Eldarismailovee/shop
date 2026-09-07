"""Recording the terminal state of a consumer delivery (item 9 §21-§22, ADR-0010).

Two functions, because there are two semantic states and item 9 forbids collapsing them:

* `quarantine()` — a **contract or identity integrity** failure: an unknown `event_type`, an
  unsupported `schema_version`, an invalid payload (item 8 §20), or an IX5 violation where one
  `event_id` claims two contents. The message is never applied, never coerced to a known
  version, never partially applied and **never marked HANDLED**.
* `dead_letter()` — **understood** work that exhausted its bounded execution budget. The
  message was valid and the handler knew what to do; it could not finish within the budget its
  failure domain allows.

Neither is called "failed", and neither is the other. They have different causes, different
runbooks, different urgency and different replay authority — a re-run fixes a dead-letter, and
a re-run of a quarantined message returns it straight to quarantine (RD2).

### Ordering: persist, commit, only then dispose

Item 9 DL8-DL11 and item 8 C69 fix the sequence as **validate → persist → COMMIT → only then
dispose of the transport delivery**. A terminal write that fails means the delivery is *not*
disposed of, so a message is never lost between the decision and its durability, and never
left hot-looping on the normal path either. These functions therefore write and return; the
transport disposition is the caller's next step, after its commit.

### Why the broker's own DLQ is not this

PostgreSQL is the canonical durable truth for both terminal states; the broker DLQ is demoted
to transport (ADR-0010). A broker's dead-letter queue can be purged, is not queryable by
domain, cannot name which consumer failed, and does not survive a broker rebuild. This row is
sufficient for replay on its own: envelope, original payload bytes, TCE, consumer, domain,
kind and reason.

### Replay is not implemented here

Item 9 makes replay an explicit, authorised, audited, identity-preserving operation, scoped to
the failed consumer delivery, re-entering normal validation with **no force-apply path**, and
never rebroadcasting to a sibling consumer that already succeeded. It needs an authorisation
model, an audit store and a running consumer — none of which exists in this slice. What exists
here is the record replay will read, shaped so that replay never needs to reconstruct anything:
`payload` holds the original bytes, so a replay re-presents the message rather than re-authoring
it, and `event_id` is preserved so no replay ever mints a new identity (RA8).
"""

from __future__ import annotations

import uuid

from django.db import transaction
from django.utils import timezone

from core.events.codec import fingerprint
from core.events.envelope import Envelope
from core.inbox.domains import FailureDomain
from core.inbox.models import MessageTerminal, TerminalKind

__all__ = ("dead_letter", "quarantine", "undecodable_quarantine")


def quarantine(
    *,
    consumer: str,
    failure_domain: FailureDomain,
    envelope: Envelope,
    payload: str,
    reason: str,
) -> MessageTerminal:
    """Record a contract or identity integrity failure, durably.

    `attempts` stays at zero: a quarantine is reached on the **first** look, because the
    message could not be understood, not after a budget was spent trying. The `CHECK` on the
    table enforces the converse for a dead-letter, so the two states differ by more than their
    label.
    """
    return _record(
        terminal_kind=TerminalKind.QUARANTINE,
        consumer=consumer,
        failure_domain=failure_domain,
        envelope=envelope,
        payload=payload,
        reason=reason,
        attempts=0,
    )


def dead_letter(
    *,
    consumer: str,
    failure_domain: FailureDomain,
    envelope: Envelope,
    payload: str,
    reason: str,
    attempts: int,
) -> MessageTerminal:
    """Record understood work that exhausted its execution budget, durably.

    `attempts` is required and must be at least one. A dead-letter with no attempts would be a
    quarantine wearing the wrong label, and the table refuses it.
    """
    if type(attempts) is not int or attempts < 1:
        raise ValueError(
            f"a dead-letter records the attempts that were actually spent, at least one; got "
            f"{attempts!r}. A terminal state reached without an attempt is a quarantine"
        )
    return _record(
        terminal_kind=TerminalKind.DEAD_LETTER,
        consumer=consumer,
        failure_domain=failure_domain,
        envelope=envelope,
        payload=payload,
        reason=reason,
        attempts=attempts,
    )


def undecodable_quarantine(
    *,
    consumer: str,
    failure_domain: FailureDomain,
    event_id: uuid.UUID,
    payload: str,
    reason: str,
) -> MessageTerminal:
    """Quarantine a message whose envelope could not be constructed at all.

    The case item 8 §20 is actually about: an unknown `event_type`, a `schema_version` no
    consumer supports, or a structurally invalid envelope. There is no `Envelope` to pass,
    because building one is what failed — which is exactly why `event_type`, `schema_version`
    and `occurred_at` are nullable on `MessageTerminal` and on nothing else. A record that
    could not say "I could not read this" would be a record nobody can triage.

    `event_id` is taken as a raw UUID rather than an `EventId`, because a delivery whose
    envelope is undecodable may carry an identity that is not a valid UUIDv7 either; the
    transport's best knowledge of what arrived is recorded rather than discarded. Nothing here
    parses, repairs or invents it.
    """
    row = MessageTerminal(
        terminal_kind=TerminalKind.QUARANTINE,
        failure_domain=failure_domain.value,
        consumer=_checked_consumer(consumer),
        event_id=event_id,
        event_type=None,
        schema_version=None,
        occurred_at=None,
        payload=payload,
        payload_fingerprint=_optional_fingerprint(payload),
        reason=_checked_reason(reason),
        recorded_at=timezone.now(),
        attempts=0,
    )
    row.save(force_insert=True)
    return row


def _record(
    *,
    terminal_kind: TerminalKind,
    consumer: str,
    failure_domain: FailureDomain,
    envelope: Envelope,
    payload: str,
    reason: str,
    attempts: int,
) -> MessageTerminal:
    """Write the terminal record, preserving the message exactly as it arrived.

    The envelope's eight slots and the original payload bytes are copied verbatim. Nothing is
    re-serialized, re-derived or normalised on the way in: item 9 C77 requires replay to
    preserve `event_id`, `event_type`, `schema_version`, `occurred_at` and payload byte-for-byte,
    and a record that re-encoded its payload would already have broken that before replay was
    ever attempted.
    """
    if type(failure_domain) is not FailureDomain:
        raise TypeError(
            f"failure_domain must be a FailureDomain, got {type(failure_domain).__name__}; a "
            f"terminal record names a domain that exists in the frozen matrix (A56)"
        )
    if type(payload) is not str:
        raise TypeError(
            f"payload must be the original canonical text, got {type(payload).__name__}; the "
            f"stored bytes are the replay material, never a re-serialized reconstruction"
        )

    row = MessageTerminal(
        terminal_kind=terminal_kind,
        failure_domain=failure_domain.value,
        consumer=_checked_consumer(consumer),
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
        payload_fingerprint=fingerprint(payload),
        reason=_checked_reason(reason),
        recorded_at=timezone.now(),
        attempts=attempts,
    )
    # A re-quarantine of an already-terminal delivery (RD2) updates the operational half
    # rather than adding a second row, so the count of terminal records stays the count of
    # terminal deliveries. The immutable half is identical by construction — same message —
    # so nothing about the message is rewritten by the update.
    with transaction.atomic():
        existing = (
            MessageTerminal.objects.select_for_update()
            .filter(consumer=row.consumer, event_id=row.event_id)
            .first()
        )
        if existing is None:
            row.save(force_insert=True)
            return row
        MessageTerminal.objects.filter(pk=existing.pk).update(
            terminal_kind=row.terminal_kind,
            failure_domain=row.failure_domain,
            reason=row.reason,
            recorded_at=row.recorded_at,
            attempts=row.attempts,
        )
        existing.refresh_from_db()
        return existing


def _checked_consumer(consumer: str) -> str:
    if type(consumer) is not str or not consumer:
        raise TypeError(
            "a terminal record names which consumer failed; a failure domain shared by "
            "several consumers cannot identify one (DL16, DL17)"
        )
    return consumer


def _checked_reason(reason: str) -> str:
    if type(reason) is not str or not reason:
        raise TypeError(
            "a terminal record carries a machine-readable reason token; it is the triage "
            "handle, and a record nobody can classify is a record nobody can action"
        )
    return reason


def _optional_fingerprint(payload: str) -> str | None:
    """The digest of an undecodable delivery's bytes, when they can be digested at all.

    An undecodable message may carry non-canonical or oversized text — that can be exactly
    why it is here — so a failure to fingerprint is recorded as absence rather than allowed to
    stop the quarantine write. Losing the message would be far worse than losing its digest.
    """
    try:
        return fingerprint(payload)
    except Exception:
        return None
