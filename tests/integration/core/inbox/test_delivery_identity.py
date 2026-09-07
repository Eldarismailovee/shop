"""First-seen identity, duplicates, and IX5 — on a real unique index.

Item 8 IX5's distinction is the point of this file: a unique conflict is **not** automatically
a duplicate. The losing insert must read the committed row and compare content, because the
same `event_id` with different content is a data-integrity violation that must be loud, and
collapsing the two cases would make IX5 undetectable in exactly the circumstance it exists for.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from django.db import transaction

from core.events.codec import encode
from core.events.envelope import Envelope
from core.events.identity import EventId
from core.inbox.delivery import (
    DuplicateDelivery,
    FirstDelivery,
    observe_delivery,
    record_attempt,
)
from core.inbox.errors import IngestOutsideTransaction, IntegrityViolation, UnknownDelivery
from core.inbox.models import DeliveryState, InboxDelivery

pytestmark = pytest.mark.django_db

CONSUMER = "fixture.consumer_a"
OTHER_CONSUMER = "fixture.consumer_b"
TRACE = "4bf92f3577b34da6a3ce929d0e0e4736"
SPAN = "00f067aa0ba902b7"


def envelope(
    *,
    event_id: EventId | None = None,
    event_type: str = "fixture.thing_happened",
    schema_version: int = 1,
    traced: bool = False,
) -> Envelope:
    """A structurally valid envelope under a name that belongs to no real module.

    The message registry ships empty and stays empty (item 8 RG8): no `event_type` is invented
    in production code to make a test convenient.
    """
    return Envelope(
        event_id=event_id or EventId.new(),
        event_type=event_type,
        schema_version=schema_version,
        occurred_at=datetime(2026, 9, 7, 12, 0, tzinfo=UTC),
        trace_id=TRACE if traced else None,
        producer_span_id=SPAN if traced else None,
        request_id="req-1" if traced else None,
    )


def first_delivery(*, consumer: str, envelope: Envelope, payload: str) -> FirstDelivery:
    """`observe_delivery` narrowed to its first-delivery outcome, for the cases that expect one.

    The union is the real contract — a caller must handle a duplicate — so it is not weakened
    in production code. Tests that are *about* the first delivery narrow it here once, with an
    assertion, rather than repeating the check at every call site.
    """
    outcome = observe_delivery(consumer=consumer, envelope=envelope, payload=payload)
    assert isinstance(outcome, FirstDelivery), f"expected a first delivery, got {outcome!r}"
    return outcome


class TestFirstDelivery:
    def test_a_first_delivery_is_the_callers_to_run(self) -> None:
        env = envelope()
        with transaction.atomic():
            outcome = observe_delivery(consumer=CONSUMER, envelope=env, payload=encode({"a": 1}))
            assert isinstance(outcome, FirstDelivery)
            with outcome:
                outcome.complete()

        row = InboxDelivery.objects.get(consumer=CONSUMER, event_id=env.event_id.value)
        assert row.state == DeliveryState.HANDLED
        assert row.completed_at is not None

    def test_the_stored_bytes_are_the_bytes_that_arrived(self) -> None:
        """C77's premise: what is stored is what will be replayed, not a re-rendering."""
        env = envelope()
        payload = encode({"z": 1, "a": {"nested": [1, 2]}})
        with transaction.atomic():
            with first_delivery(consumer=CONSUMER, envelope=env, payload=payload) as first:
                first.complete()

        assert InboxDelivery.objects.get(event_id=env.event_id.value).payload == payload

    def test_the_message_tce_is_copied_verbatim(self) -> None:
        env = envelope(traced=True)
        with transaction.atomic():
            with first_delivery(consumer=CONSUMER, envelope=env, payload=encode({})) as first:
                first.complete()

        row = InboxDelivery.objects.get(event_id=env.event_id.value)
        assert (row.trace_id, row.producer_span_id, row.request_id) == (TRACE, SPAN, "req-1")
        # CN8: the delivery's own operational trace is a separate, still-empty pair.
        assert row.processing_trace_id is None

    def test_an_uncompleted_block_is_refused(self) -> None:
        """A delivery committing as RECEIVED beside a committed effect re-runs that effect."""
        with pytest.raises(UnknownDelivery, match="without complete"):
            with transaction.atomic():
                with first_delivery(consumer=CONSUMER, envelope=envelope(), payload="{}"):
                    pass

    def test_completion_outside_the_block_is_refused(self) -> None:
        with transaction.atomic():
            outcome = observe_delivery(consumer=CONSUMER, envelope=envelope(), payload="{}")
            assert isinstance(outcome, FirstDelivery)
            with pytest.raises(UnknownDelivery, match="inside"):
                outcome.complete()

    @pytest.mark.django_db(transaction=True)
    def test_ingest_outside_a_transaction_is_refused(self) -> None:
        """A claim that commits on its own survives a rolled-back effect and suppresses retry.

        `transaction=True` matters here: the ordinary `django_db` fixture wraps each test in an
        atomic block, which would hide exactly the condition this test is about.
        """
        with pytest.raises(IngestOutsideTransaction):
            observe_delivery(consumer=CONSUMER, envelope=envelope(), payload="{}")


class TestDuplicateDelivery:
    def test_the_same_message_twice_is_a_duplicate_and_runs_no_effect(self) -> None:
        """IX4/IX8: at-least-once transport makes this ordinary, not exceptional."""
        env = envelope()
        payload = encode({"a": 1})

        with transaction.atomic():
            with first_delivery(consumer=CONSUMER, envelope=env, payload=payload) as first:
                first.complete()

        with transaction.atomic():
            second = observe_delivery(consumer=CONSUMER, envelope=env, payload=payload)

        assert isinstance(second, DuplicateDelivery)
        assert second.already_handled
        assert InboxDelivery.objects.filter(event_id=env.event_id.value).count() == 1

    def test_a_duplicate_never_overwrites_the_first_observation(self) -> None:
        """IX5: the recorded first observation is never rewritten, by any path."""
        env = envelope()
        payload = encode({"a": 1})
        with transaction.atomic():
            with first_delivery(consumer=CONSUMER, envelope=env, payload=payload) as first:
                first.complete()
        original = InboxDelivery.objects.get(event_id=env.event_id.value)

        with transaction.atomic():
            observe_delivery(consumer=CONSUMER, envelope=env, payload=payload)

        again = InboxDelivery.objects.get(event_id=env.event_id.value)
        assert again.first_seen_at == original.first_seen_at
        assert again.payload_fingerprint == original.payload_fingerprint

    def test_key_order_in_the_payload_does_not_make_a_duplicate_look_different(self) -> None:
        """Determinism is what makes the fingerprint a content comparison rather than a hash
        of an arbitrary rendering (IX3)."""
        env = envelope()
        with transaction.atomic():
            with first_delivery(
                consumer=CONSUMER, envelope=env, payload=encode({"a": 1, "b": 2})
            ) as first:
                first.complete()

        with transaction.atomic():
            outcome = observe_delivery(
                consumer=CONSUMER, envelope=env, payload=encode({"b": 2, "a": 1})
            )
        assert isinstance(outcome, DuplicateDelivery)


class TestTheConsumerDeliveryIsTheUnit:
    def test_two_consumers_of_one_event_id_are_independent(self) -> None:
        """DL13-DL16: not duplicates. The second consumer must get to run its own effect."""
        env = envelope()
        payload = encode({"a": 1})

        with transaction.atomic():
            with first_delivery(consumer=CONSUMER, envelope=env, payload=payload) as first:
                first.complete()

        with transaction.atomic():
            second = observe_delivery(consumer=OTHER_CONSUMER, envelope=env, payload=payload)
            assert isinstance(second, FirstDelivery), (
                "a sibling consumer's first delivery was mistaken for a duplicate; the unique "
                "key is (consumer, event_id), never event_id alone"
            )
            with second:
                second.complete()

        assert InboxDelivery.objects.filter(event_id=env.event_id.value).count() == 2

    def test_one_consumer_may_be_handled_while_the_other_is_not(self) -> None:
        """DL16: independent state. One consumer finishing says nothing about the other."""
        env = envelope()
        with transaction.atomic():
            with first_delivery(consumer=CONSUMER, envelope=env, payload="{}") as first:
                first.complete()

        # The sibling's effect fails, so its whole transaction — delivery row included — rolls
        # back. The handled consumer is untouched, and the sibling is simply unobserved again.
        class EffectFailed(Exception):
            pass

        with pytest.raises(EffectFailed):
            with transaction.atomic():
                with first_delivery(consumer=OTHER_CONSUMER, envelope=env, payload="{}"):
                    raise EffectFailed

        assert InboxDelivery.objects.get(consumer=CONSUMER).state == DeliveryState.HANDLED
        assert not InboxDelivery.objects.filter(consumer=OTHER_CONSUMER).exists()

    def test_an_abandoned_delivery_leaves_no_row(self) -> None:
        env = envelope()
        with pytest.raises(UnknownDelivery):
            with transaction.atomic():
                with first_delivery(consumer=CONSUMER, envelope=env, payload="{}"):
                    pass
        assert not InboxDelivery.objects.filter(event_id=env.event_id.value).exists()


class TestIntegrityViolation:
    """IX5: one `event_id`, two materially different contents. Never absorbed as a duplicate."""

    def _first_delivery(self, env: Envelope, payload: str) -> None:
        with transaction.atomic():
            with first_delivery(consumer=CONSUMER, envelope=env, payload=payload) as first:
                first.complete()

    def test_a_different_payload_under_one_event_id_is_a_violation(self) -> None:
        env = envelope()
        self._first_delivery(env, encode({"a": 1}))

        with pytest.raises(IntegrityViolation, match="not a duplicate") as caught:
            with transaction.atomic():
                observe_delivery(consumer=CONSUMER, envelope=env, payload=encode({"a": 2}))

        assert caught.value.first_seen_fingerprint != caught.value.arriving_fingerprint
        assert caught.value.consumer == CONSUMER

    def test_a_different_event_type_under_one_event_id_is_a_violation(self) -> None:
        identity = EventId.new()
        payload = encode({"a": 1})
        self._first_delivery(envelope(event_id=identity), payload)

        with pytest.raises(IntegrityViolation):
            with transaction.atomic():
                observe_delivery(
                    consumer=CONSUMER,
                    envelope=envelope(event_id=identity, event_type="fixture.other_thing"),
                    payload=payload,
                )

    def test_a_different_schema_version_under_one_event_id_is_a_violation(self) -> None:
        identity = EventId.new()
        payload = encode({"a": 1})
        self._first_delivery(envelope(event_id=identity), payload)

        with pytest.raises(IntegrityViolation):
            with transaction.atomic():
                observe_delivery(
                    consumer=CONSUMER,
                    envelope=envelope(event_id=identity, schema_version=2),
                    payload=payload,
                )

    def test_the_conflicting_delivery_is_never_applied(self) -> None:
        """The first observation stands, unchanged, and no second row appears."""
        env = envelope()
        self._first_delivery(env, encode({"a": 1}))
        before = InboxDelivery.objects.get(event_id=env.event_id.value)

        with pytest.raises(IntegrityViolation):
            with transaction.atomic():
                observe_delivery(consumer=CONSUMER, envelope=env, payload=encode({"a": 999}))

        after = InboxDelivery.objects.get(event_id=env.event_id.value)
        assert after.payload == before.payload
        assert after.payload_fingerprint == before.payload_fingerprint
        assert InboxDelivery.objects.filter(event_id=env.event_id.value).count() == 1

    def test_a_sibling_consumer_is_unaffected_by_another_consumers_violation(self) -> None:
        env = envelope()
        self._first_delivery(env, encode({"a": 1}))

        with pytest.raises(IntegrityViolation):
            with transaction.atomic():
                observe_delivery(consumer=CONSUMER, envelope=env, payload=encode({"a": 2}))

        with transaction.atomic():
            sibling = observe_delivery(consumer=OTHER_CONSUMER, envelope=env, payload=encode({}))
            assert isinstance(sibling, FirstDelivery)
            with sibling:
                sibling.complete()


class TestAttemptRecording:
    def test_an_attempt_increments_and_records_the_deliverys_own_trace(self) -> None:
        """CN8: the delivery's operational trace, never the message's."""
        env = envelope(traced=True)
        with transaction.atomic():
            with first_delivery(consumer=CONSUMER, envelope=env, payload="{}") as first:
                first.complete()

        record_attempt(
            consumer=CONSUMER,
            envelope=env,
            processing_trace_id="a" * 32,
            processing_span_id="b" * 16,
        )

        row = InboxDelivery.objects.get(event_id=env.event_id.value)
        assert row.attempts == 1
        assert row.processing_trace_id == "a" * 32
        # A62/CN3: the message's own copy is untouched by the consumer's attempt.
        assert row.trace_id == TRACE
        assert row.producer_span_id == SPAN

    def test_a_half_present_processing_pair_is_normalised_to_absent(self) -> None:
        env = envelope()
        with transaction.atomic():
            with first_delivery(consumer=CONSUMER, envelope=env, payload="{}") as first:
                first.complete()

        record_attempt(consumer=CONSUMER, envelope=env, processing_trace_id="a" * 32)

        row = InboxDelivery.objects.get(event_id=env.event_id.value)
        assert row.processing_trace_id is None
        assert row.processing_span_id is None

    def test_an_attempt_against_an_unobserved_delivery_is_refused(self) -> None:
        with pytest.raises(UnknownDelivery):
            record_attempt(consumer=CONSUMER, envelope=envelope())
