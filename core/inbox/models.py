"""Consumer-delivery identity and terminal state (item 8 §21, item 9 §21-§22, ADR-0010).

Two tables, both PostgreSQL-canonical.

### `InboxDelivery` — the unit is the **consumer delivery**, not the message

Item 9 §22.3 is the load-bearing decision: two consumers of one `event_id` are **independent
deliveries**, not duplicates. One may succeed while the other dead-letters; each keeps its own
identity record, its own effect and its own terminal state; and a replay is scoped to the
failed consumer so a sibling that already succeeded is never re-invoked (RA5b, C83). That is
why the unique key is `(consumer, event_id)` and never `event_id` alone — the latter would make
the second consumer of any message look like a duplicate of the first.

Every consumer, **without exception**, durably retains the first-seen `event_type`,
`schema_version` and payload fingerprint (IX2, IX5, IX6). No registry entry may declare that
detection unavailable and no handler may opt out on the grounds that its effect is naturally
idempotent: a naturally idempotent effect says nothing about whether two deliveries claiming one
`event_id` carried the same content (IX11). That is what makes the same `event_id` with
different content detectable as an **integrity violation** rather than absorbed as a duplicate.

### The immutable half and the mutable half are separate column groups

Item 10 A62 requires one writer per trace column and CN3 forbids a consumer writing its span,
trace, attempt number, worker identity or failure domain into the message's four fields. CN8
requires the delivery's *own* operational trace to be kept in storage distinct from the
message's copy. So the row has two groups, and they are never mixed:

* **Immutable, written once at first observation** — `event_id`, `event_type`,
  `schema_version`, `occurred_at`, the four TCE fields, `payload`, `payload_fingerprint`.
  No retry, claim, completion, terminal transition or replay rewrites any of them (FS6, A66).
* **Mutable delivery processing state** — `state`, `attempts`, `first_seen_at`,
  `completed_at`, and the delivery's own `processing_trace_id` / `processing_span_id`, which
  change per attempt and are never confused with, merged into, or allowed to overwrite the
  message's copy.

### `MessageTerminal` — quarantine and dead-letter, which are not the same thing

Item 9 §21 keeps two semantic states apart, and neither is called "failed":

* **Contract quarantine** — an unknown `event_type`, an unsupported `schema_version` or an
  invalid payload (item 8 §20), or an IX5 identity-integrity violation. The message is never
  applied, never coerced, never marked HANDLED.
* **Operational dead-letter** — understood work that exhausted its bounded execution budget.

One physical table is admissible **only** with an explicit terminal-kind discriminator, which
`terminal_kind` is. Every record additionally names its origin `failure_domain` **and** the
`consumer` that failed, because a domain shared by several consumers cannot identify one
(DL16, DL17), and there is no global undifferentiated bucket (TI2, A56). The envelope and the
original payload bytes are preserved so a terminal record stays diagnosable and replayable after
the broker's data is gone, after the source Outbox partition is archived, and after the tracing
backend's retention has expired (TD5-TD8, TM2, C77).
"""

from __future__ import annotations

from django.db import models

from core.events.bounds import (
    FINGERPRINT_HEX_LENGTH,
    MAX_CONSUMER_LENGTH,
    MAX_EVENT_TYPE_LENGTH,
    MAX_REASON_LENGTH,
    MAX_REQUEST_ID_LENGTH,
    SPAN_ID_HEX_LENGTH,
    TRACE_ID_HEX_LENGTH,
)
from core.inbox.domains import FailureDomain

__all__ = ("DeliveryState", "InboxDelivery", "MessageTerminal", "TerminalKind")

_FINGERPRINT_PATTERN = rf"^[0-9a-f]{{{FINGERPRINT_HEX_LENGTH}}}$"
_TRACE_ID_PATTERN = rf"^[0-9a-f]{{{TRACE_ID_HEX_LENGTH}}}$"
_SPAN_ID_PATTERN = rf"^[0-9a-f]{{{SPAN_ID_HEX_LENGTH}}}$"

_FAILURE_DOMAIN_CHOICES = [(member.value, member.value) for member in FailureDomain]


class DeliveryState(models.TextChoices):
    """Where one consumer delivery stands.

    Only two values, and deliberately so. `HANDLED` means the consumer's durable business
    effect committed, in the same local transaction as this transition (item 8's handler
    transaction rule) — never before it. There is no `PROCESSING` value: an in-flight attempt
    is uncommitted transaction-local state, and a committed `PROCESSING` row would be exactly
    the poisoned claim ADR-0015 §6 forbids in the sibling mechanism, reproduced here.

    There is no `FAILED` value either. Item 9 is explicit that quarantine and operational
    dead-letter are two distinct semantic states and that neither is called "failed"; both
    live in `MessageTerminal`, keyed to this same delivery.
    """

    RECEIVED = "RECEIVED", "Received, effect not yet committed"
    HANDLED = "HANDLED", "Effect committed"


class TerminalKind(models.TextChoices):
    """The discriminator that makes one physical terminal table admissible (item 9 §21)."""

    QUARANTINE = "QUARANTINE", "Contract or identity integrity failure"
    DEAD_LETTER = "DEAD_LETTER", "Understood work that exhausted its budget"


class InboxDelivery(models.Model):
    """One `(consumer, event_id)` delivery: what arrived first, and how it is going."""

    # -- Delivery identity ------------------------------------------------------------------

    #: The registered consumer, dotted. Never a failure-domain name: a domain shared by
    #: several consumers cannot say which one this delivery belongs to (DL16).
    consumer = models.CharField(max_length=MAX_CONSUMER_LENGTH)

    # -- The message, as first seen. Immutable. ---------------------------------------------
    #
    # IX2/IX5/IX6: retained by every consumer without exception, so that the same `event_id`
    # arriving with different content is always detectable as an integrity violation. These
    # columns are never overwritten — not by a redelivery, not by a retry, not by a replay.

    event_id = models.UUIDField()
    event_type = models.CharField(max_length=MAX_EVENT_TYPE_LENGTH)
    schema_version = models.PositiveIntegerField()
    occurred_at = models.DateTimeField()

    #: The message's own TCE, copied verbatim (CN6). The consumer never writes here (CN3,
    #: A62); its own trace context is the separate pair below.
    trace_id = models.CharField(max_length=TRACE_ID_HEX_LENGTH, null=True)
    producer_span_id = models.CharField(max_length=SPAN_ID_HEX_LENGTH, null=True)
    request_id = models.CharField(max_length=MAX_REQUEST_ID_LENGTH, null=True)
    causation_event_id = models.UUIDField(null=True)

    #: The exact canonical bytes that arrived, retained so replay preserves them (C77) and so
    #: the fingerprint below can be re-derived from what was actually seen rather than from a
    #: value rebuilt through today's DTOs.
    payload = models.TextField()
    payload_fingerprint = models.CharField(max_length=FINGERPRINT_HEX_LENGTH)

    first_seen_at = models.DateTimeField()

    # -- Mutable delivery processing state --------------------------------------------------

    state = models.CharField(
        max_length=16,
        choices=DeliveryState.choices,
        default=DeliveryState.RECEIVED,
    )

    #: Item 10 CN8 / item 9 RO2: attempt metadata lives on the transport row, never in a
    #: payload and never in an envelope slot.
    attempts = models.PositiveIntegerField(default=0)

    #: CN8: this delivery's **own** operational trace, per attempt. Mutable, and never merged
    #: into or allowed to overwrite the message's copy above.
    processing_trace_id = models.CharField(max_length=TRACE_ID_HEX_LENGTH, null=True)
    processing_span_id = models.CharField(max_length=SPAN_ID_HEX_LENGTH, null=True)

    completed_at = models.DateTimeField(null=True)

    class Meta:
        db_table = "core_inbox_delivery"
        constraints = [
            # The whole mechanism. Two consumers of one `event_id` are independent rows; one
            # consumer seeing one `event_id` twice conflicts here and is resolved by comparing
            # the committed identity, never by assuming a duplicate (IX4, IX5).
            models.UniqueConstraint(
                fields=("consumer", "event_id"),
                name="core_inbox_consumer_event_uniq",
            ),
            models.CheckConstraint(
                condition=~models.Q(consumer="") & ~models.Q(event_type=""),
                name="core_inbox_identity_not_empty",
            ),
            models.CheckConstraint(
                condition=models.Q(schema_version__gte=1),
                name="core_inbox_schema_version_from_one",
            ),
            models.CheckConstraint(
                condition=models.Q(payload_fingerprint__regex=_FINGERPRINT_PATTERN),
                name="core_inbox_fingerprint_is_sha256",
            ),
            # PR2's pair rule, on the message's copy. The processing pair below is the
            # delivery's own and is governed by the same rule for the same reason.
            models.CheckConstraint(
                condition=(
                    models.Q(trace_id__isnull=True, producer_span_id__isnull=True)
                    | models.Q(trace_id__isnull=False, producer_span_id__isnull=False)
                ),
                name="core_inbox_trace_pair_complete",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(trace_id__isnull=True) | models.Q(trace_id__regex=_TRACE_ID_PATTERN)
                ),
                name="core_inbox_trace_id_well_formed",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(producer_span_id__isnull=True)
                    | models.Q(producer_span_id__regex=_SPAN_ID_PATTERN)
                ),
                name="core_inbox_span_id_well_formed",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(processing_trace_id__isnull=True, processing_span_id__isnull=True)
                    | models.Q(processing_trace_id__isnull=False, processing_span_id__isnull=False)
                ),
                name="core_inbox_processing_pair_complete",
            ),
            models.CheckConstraint(
                condition=~models.Q(causation_event_id=models.F("event_id")),
                name="core_inbox_no_self_causation",
            ),
            # A handled delivery names when its effect committed; an unhandled one does not
            # claim to have one. Item 8's rule that completion never precedes the effect is a
            # transaction property, and this is its observable trace.
            models.CheckConstraint(
                condition=(
                    models.Q(state=DeliveryState.RECEIVED, completed_at__isnull=True)
                    | models.Q(state=DeliveryState.HANDLED, completed_at__isnull=False)
                ),
                name="core_inbox_state_shape_valid",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.consumer}<-{self.event_type}@{self.schema_version}"


class MessageTerminal(models.Model):
    """The PostgreSQL-canonical terminal state of one consumer delivery.

    The broker's own dead-letter queue is **transport only** (item 9 §21): it is not the
    record, it is not sufficient for replay, and it may be purged without loss. This row is
    the record. It is written and committed **before** the transport disposes of the delivery
    (DL8-DL11, C76), so a message is never lost between validation and durability and never
    left hot-looping on the normal path.
    """

    terminal_kind = models.CharField(max_length=16, choices=TerminalKind.choices)

    #: A56: every terminal record carries its origin domain **and** its terminal kind. The
    #: per-domain namespace is derived from this (`FailureDomain.terminal_namespace`) rather
    #: than stored twice, so the two can never disagree.
    failure_domain = models.CharField(max_length=64, choices=_FAILURE_DOMAIN_CHOICES)

    #: DL16/DL17: which consumer failed. Not optional, and not derivable from the domain.
    consumer = models.CharField(max_length=MAX_CONSUMER_LENGTH)

    # -- The message, preserved for diagnosis and replay. Immutable. ------------------------

    event_id = models.UUIDField()

    #: Nullable **only** here, and only because a message can reach quarantine precisely
    #: because its `event_type` or `schema_version` could not be understood. A record that
    #: could not state that is a record that cannot be triaged. The delivery table above has
    #: no such case: nothing is admitted there without a structurally valid envelope.
    event_type = models.CharField(max_length=MAX_EVENT_TYPE_LENGTH, null=True)
    schema_version = models.PositiveIntegerField(null=True)
    occurred_at = models.DateTimeField(null=True)

    trace_id = models.CharField(max_length=TRACE_ID_HEX_LENGTH, null=True)
    producer_span_id = models.CharField(max_length=SPAN_ID_HEX_LENGTH, null=True)
    request_id = models.CharField(max_length=MAX_REQUEST_ID_LENGTH, null=True)
    causation_event_id = models.UUIDField(null=True)

    #: The original bytes exactly as they arrived. C77 replays these; nothing re-serializes a
    #: reconstructed object, and no fingerprint substitutes for them.
    payload = models.TextField()
    payload_fingerprint = models.CharField(max_length=FINGERPRINT_HEX_LENGTH, null=True)

    # -- Operational half -------------------------------------------------------------------

    #: A bounded machine-readable token — the triage handle, not the diagnosis. The diagnosis
    #: lives in the alert and the runbook; a terminal record is not a log line.
    reason = models.CharField(max_length=MAX_REASON_LENGTH)

    recorded_at = models.DateTimeField()

    #: Attempts made before the delivery became terminal. Zero for a quarantine, which is
    #: reached on the first look rather than after a budget.
    attempts = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = "core_inbox_message_terminal"
        constraints = [
            # One terminal state per consumer delivery. A still-invalid replay re-quarantines
            # the same delivery (RD2) — it updates this record's operational half rather than
            # creating a second row, so the count of terminal records stays the count of
            # terminal deliveries and a triage queue cannot double-count one failure.
            models.UniqueConstraint(
                fields=("consumer", "event_id"),
                name="core_inbox_terminal_consumer_event_uniq",
            ),
            models.CheckConstraint(
                condition=~models.Q(consumer="") & ~models.Q(reason=""),
                name="core_inbox_terminal_identity_not_empty",
            ),
            models.CheckConstraint(
                condition=(models.Q(schema_version__isnull=True) | models.Q(schema_version__gte=1)),
                name="core_inbox_terminal_schema_version_from_one",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(payload_fingerprint__isnull=True)
                    | models.Q(payload_fingerprint__regex=_FINGERPRINT_PATTERN)
                ),
                name="core_inbox_terminal_fingerprint_is_sha256",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(trace_id__isnull=True, producer_span_id__isnull=True)
                    | models.Q(trace_id__isnull=False, producer_span_id__isnull=False)
                ),
                name="core_inbox_terminal_trace_pair_complete",
            ),
            # An operational dead-letter is reached by exhausting a budget, so it has made at
            # least one attempt. A quarantine is reached on the first look and has made none.
            # The two are different states, and the record says which by more than its label.
            models.CheckConstraint(
                condition=(
                    models.Q(terminal_kind=TerminalKind.QUARANTINE)
                    | models.Q(terminal_kind=TerminalKind.DEAD_LETTER, attempts__gte=1)
                ),
                name="core_inbox_terminal_kind_shape_valid",
            ),
        ]
        indexes = [
            # Per-domain triage: "what is terminal in `ext.erp` right now", newest first.
            # This is the query a runbook runs, and the reason item 9 forbids a global bucket.
            models.Index(
                fields=("failure_domain", "terminal_kind", "-recorded_at"),
                name="core_inbox_terminal_triage_idx",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.terminal_kind}/{self.failure_domain}/{self.consumer}"
