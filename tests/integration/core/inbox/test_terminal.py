"""Quarantine and dead-letter: two states, one table, never confused.

Item 9 §21 keeps contract quarantine and operational dead-letter apart, and neither is called
"failed". A single physical table is admissible only with an explicit terminal-kind
discriminator, and every record must additionally name its origin domain and the consumer
delivery that failed — because a domain shared by several consumers cannot identify one, and
because a global undifferentiated bucket puts a poison ERP batch beside a payment failure.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from django.db import IntegrityError, connection, transaction

from core.events.codec import encode, fingerprint
from core.events.envelope import Envelope
from core.events.identity import EventId
from core.inbox.domains import Criticality, FailureDomain
from core.inbox.models import MessageTerminal, TerminalKind
from core.inbox.terminal import dead_letter, quarantine, undecodable_quarantine

pytestmark = pytest.mark.django_db

CONSUMER = "fixture.consumer_a"
OTHER_CONSUMER = "fixture.consumer_b"


def envelope(*, event_id: EventId | None = None) -> Envelope:
    return Envelope(
        event_id=event_id or EventId.new(),
        event_type="fixture.thing_happened",
        schema_version=1,
        occurred_at=datetime(2026, 9, 7, 12, 0, tzinfo=UTC),
        trace_id="4bf92f3577b34da6a3ce929d0e0e4736",
        producer_span_id="00f067aa0ba902b7",
        request_id="req-1",
    )


class TestTheTwoStatesAreDistinct:
    def test_a_quarantine_records_its_kind_domain_and_consumer(self) -> None:
        row = quarantine(
            consumer=CONSUMER,
            failure_domain=FailureDomain.EXT_ERP,
            envelope=envelope(),
            payload=encode({"a": 1}),
            reason="unsupported_schema_version",
        )

        assert row.terminal_kind == TerminalKind.QUARANTINE
        assert row.failure_domain == "ext.erp"
        assert row.consumer == CONSUMER
        assert row.attempts == 0

    def test_a_dead_letter_records_the_attempts_actually_spent(self) -> None:
        row = dead_letter(
            consumer=CONSUMER,
            failure_domain=FailureDomain.CORE_PAYMENTS,
            envelope=envelope(),
            payload=encode({"a": 1}),
            reason="budget_exhausted",
            attempts=5,
        )

        assert row.terminal_kind == TerminalKind.DEAD_LETTER
        assert row.attempts == 5

    def test_a_dead_letter_without_an_attempt_is_refused(self) -> None:
        """A terminal state reached without spending an attempt is a quarantine mislabelled."""
        with pytest.raises(ValueError, match="at least one"):
            dead_letter(
                consumer=CONSUMER,
                failure_domain=FailureDomain.CORE_PAYMENTS,
                envelope=envelope(),
                payload="{}",
                reason="budget_exhausted",
                attempts=0,
            )

    def test_the_database_refuses_a_zero_attempt_dead_letter_directly(self) -> None:
        """The Python guard is not the guarantee; a `CHECK` is, against raw SQL too."""
        with pytest.raises(IntegrityError), transaction.atomic(), connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO core_inbox_message_terminal "
                "(terminal_kind, failure_domain, consumer, event_id, payload, reason, "
                " recorded_at, attempts) "
                "VALUES (%s, %s, %s, %s, %s, %s, now(), 0)",
                ["DEAD_LETTER", "ext.erp", CONSUMER, str(uuid.uuid4()), "{}", "x"],
            )


class TestTheRecordIsSufficientForReplay:
    def test_the_original_bytes_are_preserved_exactly(self) -> None:
        """C77: replay preserves the payload byte-for-byte, so the record must hold the bytes."""
        payload = encode({"z": 1, "a": {"nested": [1, 2, 3]}})
        row = quarantine(
            consumer=CONSUMER,
            failure_domain=FailureDomain.EXT_ERP,
            envelope=envelope(),
            payload=payload,
            reason="invalid_payload",
        )

        stored = MessageTerminal.objects.get(pk=row.pk)
        assert stored.payload == payload
        assert stored.payload_fingerprint == fingerprint(payload)

    def test_the_envelope_and_tce_survive_for_diagnosis(self) -> None:
        """TM2: diagnosable after the broker's data is gone and the trace backend has expired."""
        env = envelope()
        row = quarantine(
            consumer=CONSUMER,
            failure_domain=FailureDomain.EXT_ERP,
            envelope=env,
            payload="{}",
            reason="invalid_payload",
        )

        stored = MessageTerminal.objects.get(pk=row.pk)
        assert stored.event_id == env.event_id.value
        assert stored.event_type == env.event_type
        assert stored.schema_version == env.schema_version
        assert stored.trace_id == env.trace_id
        assert stored.request_id == env.request_id


class TestUndecodableMessages:
    def test_a_message_with_no_readable_envelope_can_still_be_quarantined(self) -> None:
        """The case item 8 §20 is actually about: the envelope is what could not be read.

        A record that could not say "I could not read this" is a record nobody can triage,
        which is why `event_type`/`schema_version`/`occurred_at` are nullable here and nowhere
        else.
        """
        row = undecodable_quarantine(
            consumer=CONSUMER,
            failure_domain=FailureDomain.EXT_PAYMENTS,
            event_id=uuid.uuid4(),
            payload="{not json at all",
            reason="unknown_event_type",
        )

        assert row.event_type is None
        assert row.schema_version is None
        assert row.terminal_kind == TerminalKind.QUARANTINE
        assert row.payload == "{not json at all"

    def test_an_undigestible_payload_records_absence_rather_than_losing_the_message(self) -> None:
        row = undecodable_quarantine(
            consumer=CONSUMER,
            failure_domain=FailureDomain.EXT_PAYMENTS,
            event_id=uuid.uuid4(),
            payload='{"a": 1}',  # valid JSON, but not canonical, so it cannot be fingerprinted
            reason="invalid_payload",
        )

        assert row.payload_fingerprint is None
        assert row.payload == '{"a": 1}'


class TestOneTerminalStatePerConsumerDelivery:
    def test_two_consumers_of_one_event_id_get_independent_records(self) -> None:
        """DL16/DL17: each record names which consumer failed."""
        env = envelope()
        quarantine(
            consumer=CONSUMER,
            failure_domain=FailureDomain.EXT_ERP,
            envelope=env,
            payload="{}",
            reason="invalid_payload",
        )
        dead_letter(
            consumer=OTHER_CONSUMER,
            failure_domain=FailureDomain.EXT_EMAIL,
            envelope=env,
            payload="{}",
            reason="budget_exhausted",
            attempts=3,
        )

        records = MessageTerminal.objects.filter(event_id=env.event_id.value)
        assert records.count() == 2
        assert {r.consumer for r in records} == {CONSUMER, OTHER_CONSUMER}
        assert {r.failure_domain for r in records} == {"ext.erp", "ext.email"}

    def test_a_re_quarantine_updates_rather_than_duplicating(self) -> None:
        """RD2: a still-invalid replay returns to quarantine — as the same terminal delivery."""
        env = envelope()
        first = quarantine(
            consumer=CONSUMER,
            failure_domain=FailureDomain.EXT_ERP,
            envelope=env,
            payload="{}",
            reason="unknown_event_type",
        )
        second = quarantine(
            consumer=CONSUMER,
            failure_domain=FailureDomain.EXT_ERP,
            envelope=env,
            payload="{}",
            reason="still_unknown_event_type",
        )

        assert second.pk == first.pk
        assert MessageTerminal.objects.filter(event_id=env.event_id.value).count() == 1
        assert MessageTerminal.objects.get(pk=first.pk).reason == "still_unknown_event_type"


class TestRecordsAreNeverAnonymous:
    def test_a_record_without_a_consumer_is_refused(self) -> None:
        with pytest.raises(TypeError, match="which consumer failed"):
            quarantine(
                consumer="",
                failure_domain=FailureDomain.EXT_ERP,
                envelope=envelope(),
                payload="{}",
                reason="invalid_payload",
            )

    def test_a_record_without_a_reason_is_refused(self) -> None:
        with pytest.raises(TypeError, match="reason token"):
            quarantine(
                consumer=CONSUMER,
                failure_domain=FailureDomain.EXT_ERP,
                envelope=envelope(),
                payload="{}",
                reason="",
            )

    def test_a_domain_outside_the_frozen_matrix_is_refused(self) -> None:
        """A56: a terminal record names a domain that exists in the matrix, not a free string."""
        with pytest.raises(TypeError, match="FailureDomain"):
            quarantine(
                consumer=CONSUMER,
                failure_domain="ext.whatever",  # type: ignore[arg-type]
                envelope=envelope(),
                payload="{}",
                reason="invalid_payload",
            )

    def test_a_reconstructed_payload_is_refused(self) -> None:
        """The stored bytes are the replay material, never a re-serialized object."""
        with pytest.raises(TypeError, match="original canonical text"):
            quarantine(
                consumer=CONSUMER,
                failure_domain=FailureDomain.EXT_ERP,
                envelope=envelope(),
                payload={"a": 1},  # type: ignore[arg-type]
                reason="invalid_payload",
            )


class TestTheFailureDomainSet:
    def test_all_ten_frozen_definitions_exist(self) -> None:
        """Item 9 §5 froze ten. Item 14 provisions eight; a definition is not a commitment."""
        assert {member.value for member in FailureDomain} == {
            "core.payments",
            "core.inventory",
            "core.projection.incremental",
            "core.projection.rebuild",
            "core.maintenance",
            "ext.payments",
            "ext.erp",
            "ext.email",
            "ext.sms",
            "ext.crm",
        }

    def test_the_core_prefix_asserts_a_checkable_property(self) -> None:
        """QN3: no work in a `core.*` domain performs provider I/O."""
        for member in FailureDomain:
            assert member.performs_provider_io == member.value.startswith("ext.")

    def test_payments_is_split_by_io_nature(self) -> None:
        """Both CRITICAL, but only one may touch a provider — the whole reason for the split."""
        assert FailureDomain.CORE_PAYMENTS.criticality is Criticality.CRITICAL
        assert FailureDomain.EXT_PAYMENTS.criticality is Criticality.CRITICAL
        assert not FailureDomain.CORE_PAYMENTS.performs_provider_io
        assert FailureDomain.EXT_PAYMENTS.performs_provider_io

    def test_every_domain_has_its_own_terminal_namespace(self) -> None:
        """TI2/A56: no global bucket. Ten domains, ten namespaces, all distinct."""
        namespaces = {member.terminal_namespace for member in FailureDomain}
        assert len(namespaces) == len(FailureDomain)
        assert FailureDomain.EXT_ERP.terminal_namespace == "ext.erp.dlq"

    def test_every_domain_declares_a_criticality(self) -> None:
        for member in FailureDomain:
            assert isinstance(member.criticality, Criticality)
