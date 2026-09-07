"""The durable Outbox record (item 15 §15 clause 5, ADR-0011, item 8, item 9).

The row is written **inside the business transaction that produced the fact** (item 8's
handler transaction rule, ADR-0007), so a fact and its message become durable together and a
rollback leaves neither. Nothing is published to a broker from inside that transaction — direct
producer-to-broker publishing stays forbidden (item 9 §25), and the relay is a separate,
later reader of this table.

Three structural properties are rules made physical:

**The four TCE columns are present from the first migration.** ADR-0011's
storage-before-partition invariant is an ordering constraint on Phase 1 itself: no partitioning
migration may precede them, because a partitioned table gains columns far more painfully than
an empty one, and a durable record that cannot carry trace context is not diagnosable after a
broker purge (TM2). They are nullable by construction — every TCE field is optional, and
absence is a complete state (FS5, FS10) — and **no TCE field is a partition, ordering or
uniqueness key** (item 10 §26), which is why none appears in `constraints` or `indexes` below.

**The immutable message and the mutable relay state are separate groups.** Everything from
`event_id` to `payload_fingerprint` is written once, at emission, and never rewritten by any
later path (FS6, A66). Everything under "relay state" is operational metadata that changes as
the row is dispatched. The separation is not decoration: item 10 A62 requires one writer per
trace column, and CN8 requires a delivery's own operational trace to be kept in storage
distinct from the message's copy. Mixing the two groups is how a retry counter ends up in an
envelope slot.

**The payload is canonical text, not `jsonb`.** `jsonb` normalises: it reorders keys, discards
insignificant whitespace and rewrites numbers, so what comes back is a value equal to what went
in but not the bytes that went in. Item 9 C77 requires replay to preserve the payload
**byte-for-byte**, and item 8 IX5's integrity check compares content, so the column stores the
exact canonical rendering `core.events.codec.encode` produced and `payload_fingerprint` digests
those same bytes. The cost is that PostgreSQL cannot index inside the payload; that is correct
for a table nothing queries by payload content.

`core` knows no domain: nothing here carries Order, Payment, Product or Inventory vocabulary,
and the message registry that would name such a fact ships empty (`core/events/registry.py`).
"""

from __future__ import annotations

from django.db import models

from core.events.bounds import (
    FINGERPRINT_HEX_LENGTH,
    MAX_EVENT_TYPE_LENGTH,
    MAX_RELAY_WORKER_LENGTH,
    MAX_REQUEST_ID_LENGTH,
    SPAN_ID_HEX_LENGTH,
    TRACE_ID_HEX_LENGTH,
)

__all__ = ("OutboxMessage", "RelayState")

#: The exact stored form of a SHA-256 digest: lowercase hex, fixed width. `max_length` alone
#: would admit a short or upper-case value, so the alphabet and the length are constrained in
#: SQL rather than trusted from Python.
_FINGERPRINT_PATTERN = rf"^[0-9a-f]{{{FINGERPRINT_HEX_LENGTH}}}$"

#: W3C Trace Context identifiers, lowercase hex, all-zero excluded (item 10 TR2, SP4). A
#: malformed value is normalised to absent at capture, so the column never has to hold one.
_TRACE_ID_PATTERN = rf"^[0-9a-f]{{{TRACE_ID_HEX_LENGTH}}}$"
_SPAN_ID_PATTERN = rf"^[0-9a-f]{{{SPAN_ID_HEX_LENGTH}}}$"


class RelayState(models.TextChoices):
    """Where a row stands with respect to the transport, and nothing more.

    This is **operational** state. It is not the message's business meaning, not a consumer's
    outcome and not a terminal state: item 9 keeps contract quarantine and operational
    dead-letter in their own PostgreSQL-canonical records, per consumer delivery, and neither
    is a value of this enum. A relay that cannot dispatch retries under its failure domain's
    bounded policy; it does not invent a state here.
    """

    PENDING = "PENDING", "Pending relay"
    RELAYED = "RELAYED", "Handed to the transport"


class OutboxMessage(models.Model):
    """One emitted message: an immutable fact, plus the relay's operational view of it."""

    # -- Envelope: item 8 EN1's four semantic fields. Immutable after emission. ------------

    #: Item 8 MI1-MI3: one identity per emission, unchanged across every relay retry, broker
    #: redelivery, worker retry and terminal replay. `UNIQUE`, because two rows claiming one
    #: `event_id` would make every consumer's duplicate detection meaningless at the source.
    #: Stored as a native `uuid`, never as text: `EventId` is a UUIDv7 value type, and the
    #: version check belongs to the type rather than to a `CHECK` that would duplicate it.
    event_id = models.UUIDField()

    event_type = models.CharField(max_length=MAX_EVENT_TYPE_LENGTH)

    #: Item 8: a positive integer from 1, versioning the **payload contract only**. Never a
    #: source version, never a revision, never an ordering signal (SV2, OR6, A47).
    schema_version = models.PositiveIntegerField()

    #: When the producer's fact became true — not a publication, enqueue, delivery or handling
    #: time, and not an ordering key (TS1, TS4). `available_at` below is the transport's
    #: clock; these two are deliberately different columns because they answer different
    #: questions and a scheduled emission must not be able to rewrite business time.
    occurred_at = models.DateTimeField()

    # -- The trace/causality extension: item 10's closed four-field TCE. Write-once. --------
    #
    # A60: exactly these four exist. There is no fifth envelope trace field and no
    # `meta`/`extra`/`context`/`attributes`/`headers`/`tags`/JSON-blob/`baggage`/`tracestate`
    # column beside them, in any spelling.

    trace_id = models.CharField(max_length=TRACE_ID_HEX_LENGTH, null=True)
    producer_span_id = models.CharField(max_length=SPAN_ID_HEX_LENGTH, null=True)
    request_id = models.CharField(max_length=MAX_REQUEST_ID_LENGTH, null=True)
    causation_event_id = models.UUIDField(null=True)

    # -- Payload: the replay material itself. Write-once. -----------------------------------

    #: The exact canonical bytes `core.events.codec.encode` produced, as text. Item 9 C77
    #: replays these, never a value re-serialized from a reconstructed object.
    payload = models.TextField()

    #: SHA-256 over exactly the bytes in `payload`. Item 8 IX5's integrity comparison reads
    #: this; a consumer that sees a known `event_id` with a different fingerprint has found a
    #: data-integrity violation, not a duplicate.
    payload_fingerprint = models.CharField(max_length=FINGERPRINT_HEX_LENGTH)

    # -- Relay state: operational, mutable, and never message data. -------------------------
    #
    # These columns are dormant persistence structure in this slice: the relay process is not
    # implemented here, and nothing writes anything but `available_at` and the `PENDING`
    # default. They are declared now because the lease is part of the durable record's
    # definition rather than the broker's — ADR-0016 lists "Outbox relay claiming" among the
    # correctness reads that may never touch a replica, which is a statement about *this row*
    # — and because adding them later means a migration on a table that already carries
    # production traffic. The constraint on that choice is that no code may branch on them
    # until a relay exists: a dormant column is not a feature flag.

    relay_state = models.CharField(
        max_length=16,
        choices=RelayState.choices,
        default=RelayState.PENDING,
    )

    #: When the row becomes eligible for relay. Set to the emission instant today; a future
    #: bounded, jittered retry schedule (item 9 RB1-RB2) advances it rather than sleeping in a
    #: worker slot.
    available_at = models.DateTimeField()

    #: The lease. A relay claims a batch by setting all three together and releases them on
    #: dispatch; a crashed relay's lease simply expires and the rows become eligible again.
    #: The lease is an *availability* mechanism, never a correctness one — duplicate dispatch
    #: is absorbed by the consumer's Inbox identity, which is why at-least-once is the
    #: contract (item 8 IX8).
    claimed_at = models.DateTimeField(null=True)
    claimed_by = models.CharField(max_length=MAX_RELAY_WORKER_LENGTH, null=True)
    claim_expires_at = models.DateTimeField(null=True)

    relayed_at = models.DateTimeField(null=True)

    #: Item 10 CN8: attempt metadata is confined to the transport row. It is never a payload
    #: field (item 9 RO2) and never an envelope slot.
    relay_attempts = models.PositiveIntegerField(default=0)

    class Meta:
        # Explicit, so that renaming the app label can never rename the table.
        db_table = "core_outbox_message"
        constraints = [
            # Item 8 MI1: one row per emission. This also creates the index a relay's
            # by-identity lookup and every diagnostic join need, so no second one is declared.
            models.UniqueConstraint(fields=("event_id",), name="core_outbox_event_id_uniq"),
            models.CheckConstraint(
                condition=~models.Q(event_type=""),
                name="core_outbox_event_type_not_empty",
            ),
            models.CheckConstraint(
                condition=models.Q(schema_version__gte=1),
                name="core_outbox_schema_version_from_one",
            ),
            models.CheckConstraint(
                condition=models.Q(payload_fingerprint__regex=_FINGERPRINT_PATTERN),
                name="core_outbox_fingerprint_is_sha256",
            ),
            # PR2 made physical: both halves of the trace pair, or neither. Capture already
            # normalises a broken pair to absent; the constraint is what guarantees no other
            # writer — a data fix, a management command, a future relay — can create the half
            # state that PR2 classifies as a defect.
            models.CheckConstraint(
                condition=(
                    models.Q(trace_id__isnull=True, producer_span_id__isnull=True)
                    | models.Q(trace_id__isnull=False, producer_span_id__isnull=False)
                ),
                name="core_outbox_trace_pair_complete",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(trace_id__isnull=True) | models.Q(trace_id__regex=_TRACE_ID_PATTERN)
                ),
                name="core_outbox_trace_id_well_formed",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(producer_span_id__isnull=True)
                    | models.Q(producer_span_id__regex=_SPAN_ID_PATTERN)
                ),
                name="core_outbox_span_id_well_formed",
            ),
            # CZ6: self-causation is a defect, not a loop to be tolerated.
            models.CheckConstraint(
                condition=~models.Q(causation_event_id=models.F("event_id")),
                name="core_outbox_no_self_causation",
            ),
            # A dispatched row names when it was dispatched; an undispatched one does not
            # claim to have been. Without this the relay's own progress is unauditable.
            models.CheckConstraint(
                condition=(
                    models.Q(relay_state=RelayState.PENDING, relayed_at__isnull=True)
                    | models.Q(relay_state=RelayState.RELAYED, relayed_at__isnull=False)
                ),
                name="core_outbox_relay_state_shape_valid",
            ),
            # A lease is whole or absent: a claim without an expiry never releases, and an
            # expiry without a claimant cannot be attributed.
            models.CheckConstraint(
                condition=(
                    models.Q(
                        claimed_at__isnull=True,
                        claimed_by__isnull=True,
                        claim_expires_at__isnull=True,
                    )
                    | models.Q(
                        claimed_at__isnull=False,
                        claimed_by__isnull=False,
                        claim_expires_at__isnull=False,
                    )
                ),
                name="core_outbox_lease_shape_valid",
            ),
        ]
        indexes = [
            # The relay's claim path, and the only query this table is shaped for: the oldest
            # eligible undispatched rows. Partial, so the index holds a working set rather than
            # the whole history, and stops holding a row the moment it is relayed. No TCE
            # column appears here — item 10 §26 forbids one being an ordering key.
            models.Index(
                fields=("available_at",),
                name="core_outbox_relay_claim_idx",
                condition=models.Q(relay_state=RelayState.PENDING),
            ),
        ]

    def __str__(self) -> str:
        # The payload is not this row's business to advertise, and may carry personal data.
        return f"{self.event_type}@{self.schema_version}"
