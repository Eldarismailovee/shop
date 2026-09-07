"""Emission: the transaction rule, the TCE columns, and the byte guarantee.

Two properties here are the reason this table exists at all. The message becomes durable in the
same transaction as the fact, so a rollback leaves neither. And the four TCE columns are present
and populated from the first migration, which is ADR-0011's storage-before-partition invariant
made observable rather than asserted.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from django.db import IntegrityError, connection, transaction

from core.events.codec import encode, fingerprint
from core.events.context import handling_message
from core.events.errors import InvalidPayload
from core.events.identity import EventId
from core.observability.context import observability_context
from core.outbox.emit import emit
from core.outbox.errors import EmissionOutsideTransaction
from core.outbox.models import OutboxMessage, RelayState

pytestmark = pytest.mark.django_db

TRACE = "4bf92f3577b34da6a3ce929d0e0e4736"
SPAN = "00f067aa0ba902b7"
OCCURRED = datetime(2026, 9, 7, 12, 0, tzinfo=UTC)


def emit_one(**overrides: object) -> object:
    kwargs: dict[str, object] = {
        "event_type": "fixture.thing_happened",
        "schema_version": 1,
        "occurred_at": OCCURRED,
        "payload": {"a": 1},
    }
    kwargs.update(overrides)
    return emit(**kwargs)  # type: ignore[arg-type]


class TestTheTransactionRule:
    def test_a_message_is_written_inside_the_callers_transaction(self) -> None:
        with transaction.atomic():
            emission = emit_one()
        assert OutboxMessage.objects.filter(event_id=emission.envelope.event_id.value).exists()  # type: ignore[attr-defined]

    def test_a_rolled_back_fact_leaves_no_message(self) -> None:
        """The one failure an Outbox exists to make impossible."""

        class Boom(Exception):
            pass

        with pytest.raises(Boom):
            with transaction.atomic():
                emit_one()
                raise Boom

        assert OutboxMessage.objects.count() == 0

    @pytest.mark.django_db(transaction=True)
    def test_emission_outside_a_transaction_is_refused(self) -> None:
        """`transaction=True` matters: the ordinary fixture wraps each test in an atomic block,
        which would hide exactly the condition this test is about."""
        with pytest.raises(EmissionOutsideTransaction, match="never happened"):
            emit_one()


class TestTheEnvelopeIsStored:
    def test_the_four_semantic_fields_round_trip(self) -> None:
        with transaction.atomic():
            emission = emit_one()

        row = OutboxMessage.objects.get()
        assert row.event_id == emission.envelope.event_id.value  # type: ignore[attr-defined]
        assert row.event_type == "fixture.thing_happened"
        assert row.schema_version == 1
        assert row.occurred_at == OCCURRED

    def test_business_time_is_not_write_time(self) -> None:
        """TS1/TS4: `occurred_at` is when the fact became true, and nothing defaults it."""
        past = datetime(2020, 1, 1, tzinfo=UTC)
        with transaction.atomic():
            emit_one(occurred_at=past)

        row = OutboxMessage.objects.get()
        assert row.occurred_at == past
        assert row.available_at > past + timedelta(days=365)

    def test_each_emission_mints_a_new_identity(self) -> None:
        with transaction.atomic():
            first = emit_one()
            second = emit_one()
        assert first.envelope.event_id != second.envelope.event_id  # type: ignore[attr-defined]

    def test_a_malformed_event_type_is_refused_before_anything_is_written(self) -> None:
        with pytest.raises(ValueError, match="owner-qualified"):
            with transaction.atomic():
                emit_one(event_type="NotDotted")
        assert OutboxMessage.objects.count() == 0

    def test_a_naive_occurred_at_is_refused(self) -> None:
        with pytest.raises(ValueError, match="timezone-aware"):
            with transaction.atomic():
                emit_one(occurred_at=datetime(2026, 9, 7, 12, 0))

    def test_an_invalid_payload_is_refused(self) -> None:
        with pytest.raises(InvalidPayload):
            with transaction.atomic():
                emit_one(payload={"amount": 10.5})


class TestTheTceColumns:
    def test_all_four_are_populated_from_ambient_context(self) -> None:
        parent = EventId.new()
        with observability_context(trace_id=TRACE, span_id=SPAN, request_id="req-1"):
            with handling_message(parent):
                with transaction.atomic():
                    emit_one()

        row = OutboxMessage.objects.get()
        assert row.trace_id == TRACE
        assert row.producer_span_id == SPAN
        assert row.request_id == "req-1"
        assert row.causation_event_id == parent.value

    def test_absence_is_stored_as_absence(self) -> None:
        """FS5/FS10: a system-origin first hop legitimately has three of the four empty."""
        with transaction.atomic():
            emit_one()

        row = OutboxMessage.objects.get()
        assert row.trace_id is None
        assert row.producer_span_id is None
        assert row.request_id is None
        assert row.causation_event_id is None

    def test_a_broken_pair_is_stored_as_untraced_and_reported(self) -> None:
        """PR2: the message is written and processed normally; the defect is reported."""
        with observability_context(trace_id=TRACE):
            with transaction.atomic():
                emission = emit_one()

        assert emission.pair_defect  # type: ignore[attr-defined]
        row = OutboxMessage.objects.get()
        assert row.trace_id is None
        assert row.producer_span_id is None

    def test_an_observability_outage_changes_nothing_commercially(self) -> None:
        """SM3a/FW8: no ambient trace at all still writes the message and its business fields."""
        with transaction.atomic():
            emit_one()

        row = OutboxMessage.objects.get()
        assert row.event_type == "fixture.thing_happened"
        assert row.payload == encode({"a": 1})

    def test_no_tce_column_is_a_uniqueness_key(self) -> None:
        """Item 10 §26: no TCE field is a partition, ordering or uniqueness key.

        Two messages sharing one trace is the normal case — that is what a trace *is* — so a
        uniqueness constraint over one would break ordinary fan-out.
        """
        with observability_context(trace_id=TRACE, span_id=SPAN, request_id="req-1"):
            with transaction.atomic():
                emit_one()
                emit_one()

        assert OutboxMessage.objects.filter(trace_id=TRACE).count() == 2


class TestTheByteGuarantee:
    def test_the_stored_payload_is_the_canonical_rendering(self) -> None:
        with transaction.atomic():
            emit_one(payload={"z": 1, "a": {"nested": [1, 2]}})

        row = OutboxMessage.objects.get()
        assert row.payload == encode({"z": 1, "a": {"nested": [1, 2]}})
        assert row.payload_fingerprint == fingerprint(row.payload)

    def test_postgresql_does_not_reorder_the_stored_text(self) -> None:
        """The reason the column is `text` and not `jsonb`.

        `jsonb` would return an equal *value* with different bytes, and C77 requires replay to
        preserve the bytes. Asserted against what the database actually returns, because that
        is the claim.
        """
        with transaction.atomic():
            emit_one(payload={"z": 1, "y": 2, "a": 3})

        with connection.cursor() as cursor:
            cursor.execute("SELECT payload FROM core_outbox_message")
            stored = cursor.fetchone()[0]

        assert stored == '{"a":3,"y":2,"z":1}'


class TestTheRelayColumnsAreDormant:
    def test_a_new_message_is_pending_and_unclaimed(self) -> None:
        """Declared, defaulted, and written by nothing but emission: no relay exists yet."""
        with transaction.atomic():
            emit_one()

        row = OutboxMessage.objects.get()
        assert row.relay_state == RelayState.PENDING
        assert row.relayed_at is None
        assert row.claimed_at is None
        assert row.claimed_by is None
        assert row.claim_expires_at is None
        assert row.relay_attempts == 0

    def test_the_database_refuses_a_half_written_lease(self) -> None:
        """A claim without an expiry never releases; an expiry without a claimant is orphaned."""
        with transaction.atomic():
            emit_one()

        with pytest.raises(IntegrityError), transaction.atomic():
            OutboxMessage.objects.update(claimed_at=OCCURRED)

    def test_the_database_refuses_a_relayed_row_with_no_dispatch_time(self) -> None:
        with transaction.atomic():
            emit_one()

        with pytest.raises(IntegrityError), transaction.atomic():
            OutboxMessage.objects.update(relay_state=RelayState.RELAYED)


class TestDatabaseLevelInvariants:
    def test_two_rows_may_not_claim_one_event_id(self) -> None:
        with transaction.atomic():
            emission = emit_one()

        row = OutboxMessage.objects.get()
        with pytest.raises(IntegrityError), transaction.atomic(), connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO core_outbox_message "
                "(event_id, event_type, schema_version, occurred_at, payload, "
                " payload_fingerprint, relay_state, available_at, relay_attempts) "
                "VALUES (%s, %s, 1, now(), %s, %s, 'PENDING', now(), 0)",
                [
                    str(emission.envelope.event_id.value),  # type: ignore[attr-defined]
                    "fixture.other",
                    row.payload,
                    row.payload_fingerprint,
                ],
            )

    def test_the_database_refuses_a_half_present_trace_pair(self) -> None:
        """Capture normalises it away; the `CHECK` is what stops any *other* writer creating it."""
        with transaction.atomic():
            emit_one()

        with pytest.raises(IntegrityError), transaction.atomic():
            OutboxMessage.objects.update(trace_id=TRACE)

    def test_the_database_refuses_an_uppercase_trace_id(self) -> None:
        with pytest.raises(IntegrityError), transaction.atomic():
            with transaction.atomic():
                emit_one()
            OutboxMessage.objects.update(trace_id=TRACE.upper(), producer_span_id=SPAN)

    def test_the_database_refuses_self_causation(self) -> None:
        with transaction.atomic():
            emission = emit_one()

        with pytest.raises(IntegrityError), transaction.atomic():
            OutboxMessage.objects.update(
                causation_event_id=emission.envelope.event_id.value  # type: ignore[attr-defined]
            )

    def test_the_database_refuses_schema_version_zero(self) -> None:
        with transaction.atomic():
            emit_one()

        with pytest.raises(IntegrityError), transaction.atomic():
            OutboxMessage.objects.update(schema_version=0)
