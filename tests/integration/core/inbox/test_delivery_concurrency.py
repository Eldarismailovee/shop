"""The race, on two real connections and one real unique index.

The decision this file exists to prove: **a unique conflict is not automatically a duplicate**.
The losing connection blocks on the index until the winner commits, then reads what actually
committed and compares content. Same content is a duplicate; different content is item 8 IX5's
data-integrity violation. A mechanism that returned "duplicate" on every conflict would pass a
single-threaded test and lose IX5 precisely under the contention it was written for.

`transaction=True`, so each thread gets its own connection and its own real transaction. The
contention is not simulated. Assertions are deterministic in the property proven — exactly one
first delivery, exactly one effect — without depending on which thread wins, because the
scheduler's choice is not part of the contract.
"""

from __future__ import annotations

import threading
from collections.abc import Callable
from datetime import UTC, datetime

import pytest
from django.db import connection, transaction

from core.events.codec import encode
from core.events.envelope import Envelope
from core.events.identity import EventId
from core.inbox.delivery import DuplicateDelivery, FirstDelivery, observe_delivery
from core.inbox.errors import IntegrityViolation
from core.inbox.models import DeliveryState, InboxDelivery

pytestmark = pytest.mark.django_db(transaction=True)

CONSUMER = "fixture.contended_consumer"
OTHER_CONSUMER = "fixture.contended_consumer_b"

#: Long enough that the loser genuinely waits on the index rather than arriving afterwards.
_WINNER_HOLD_SECONDS = 0.25


def envelope(*, event_id: EventId, schema_version: int = 1) -> Envelope:
    return Envelope(
        event_id=event_id,
        event_type="fixture.thing_happened",
        schema_version=schema_version,
        occurred_at=datetime(2026, 9, 7, 12, 0, tzinfo=UTC),
    )


def _race(attempt: Callable[[threading.Barrier], None]) -> None:
    """Run one attempt on each of two real connections, started together."""
    barrier = threading.Barrier(2)
    threads = [threading.Thread(target=attempt, args=(barrier,)) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=30)
        assert not thread.is_alive(), "a contender never settled"


def _contend(
    *,
    consumer: str,
    env: Envelope,
    payload_for: Callable[[int], str],
    effects: list[str],
    outcomes: list[object],
    lock: threading.Lock,
) -> Callable[[threading.Barrier], None]:
    counter = iter(range(2))

    def attempt(barrier: threading.Barrier) -> None:
        index = next(counter)
        try:
            barrier.wait(timeout=10)
            with transaction.atomic():
                outcome = observe_delivery(
                    consumer=consumer, envelope=env, payload=payload_for(index)
                )
                if isinstance(outcome, FirstDelivery):
                    with outcome:
                        with lock:
                            effects.append(f"effect-{index}")
                        # Hold the transaction open so the other contender is genuinely
                        # blocked on the unique index rather than merely arriving later.
                        threading.Event().wait(_WINNER_HOLD_SECONDS)
                        outcome.complete()
                with lock:
                    outcomes.append(outcome)
        except IntegrityViolation as violation:
            with lock:
                outcomes.append(violation)
        finally:
            connection.close()

    return attempt


class TestIdenticalContent:
    def test_two_identical_deliveries_produce_one_effect(self) -> None:
        """IX8: the consumer-visible effect happens once per `event_id`, however many arrive."""
        env = envelope(event_id=EventId.new())
        payload = encode({"a": 1})
        effects: list[str] = []
        outcomes: list[object] = []

        _race(
            _contend(
                consumer=CONSUMER,
                env=env,
                payload_for=lambda _: payload,
                effects=effects,
                outcomes=outcomes,
                lock=threading.Lock(),
            )
        )

        assert len(effects) == 1, f"expected exactly one effect, got {effects}"
        assert sum(isinstance(o, FirstDelivery) for o in outcomes) == 1
        assert sum(isinstance(o, DuplicateDelivery) for o in outcomes) == 1
        assert InboxDelivery.objects.filter(event_id=env.event_id.value).count() == 1
        assert InboxDelivery.objects.get().state == DeliveryState.HANDLED

    def test_the_loser_sees_the_winners_committed_state(self) -> None:
        env = envelope(event_id=EventId.new())
        payload = encode({"a": 1})
        outcomes: list[object] = []

        _race(
            _contend(
                consumer=CONSUMER,
                env=env,
                payload_for=lambda _: payload,
                effects=[],
                outcomes=outcomes,
                lock=threading.Lock(),
            )
        )

        duplicate = next(o for o in outcomes if isinstance(o, DuplicateDelivery))
        assert duplicate.already_handled, (
            "the loser resolved before the winner's completion was visible; the unique index "
            "must make it wait for the committed row it is comparing against"
        )


class TestConflictingContent:
    def test_the_loser_detects_an_integrity_violation_rather_than_a_duplicate(self) -> None:
        """The decision this whole file exists for.

        Two connections race with the *same* `event_id` and *different* payloads. Whichever
        loses must compare the committed content and report IX5 — not silently conclude
        "someone else already handled this" and drop a materially different message.
        """
        env = envelope(event_id=EventId.new())
        effects: list[str] = []
        outcomes: list[object] = []

        _race(
            _contend(
                consumer=CONSUMER,
                env=env,
                payload_for=lambda index: encode({"a": index}),
                effects=effects,
                outcomes=outcomes,
                lock=threading.Lock(),
            )
        )

        assert len(effects) == 1
        assert sum(isinstance(o, FirstDelivery) for o in outcomes) == 1
        assert sum(isinstance(o, IntegrityViolation) for o in outcomes) == 1, (
            f"a conflicting delivery was absorbed as a duplicate: {outcomes}"
        )
        assert not any(isinstance(o, DuplicateDelivery) for o in outcomes)

        # The winner's observation stands; the conflicting content was never applied.
        assert InboxDelivery.objects.filter(event_id=env.event_id.value).count() == 1

    def test_the_violation_names_both_fingerprints(self) -> None:
        env = envelope(event_id=EventId.new())
        outcomes: list[object] = []

        _race(
            _contend(
                consumer=CONSUMER,
                env=env,
                payload_for=lambda index: encode({"a": index}),
                effects=[],
                outcomes=outcomes,
                lock=threading.Lock(),
            )
        )

        violation = next(o for o in outcomes if isinstance(o, IntegrityViolation))
        assert violation.first_seen_fingerprint != violation.arriving_fingerprint
        assert violation.first_seen_fingerprint


class TestSiblingConsumersDoNotContend:
    def test_two_consumers_racing_one_event_id_both_run(self) -> None:
        """DL13-DL16: independent deliveries, so both effects must happen.

        This is the mirror image of the duplicate test, and it is why the unique key carries
        the consumer: with `event_id` alone, one of these two would be starved.
        """
        env = envelope(event_id=EventId.new())
        payload = encode({"a": 1})
        effects: list[str] = []
        lock = threading.Lock()
        consumers = iter((CONSUMER, OTHER_CONSUMER))

        def attempt(barrier: threading.Barrier) -> None:
            consumer = next(consumers)
            try:
                barrier.wait(timeout=10)
                with transaction.atomic():
                    outcome = observe_delivery(consumer=consumer, envelope=env, payload=payload)
                    assert isinstance(outcome, FirstDelivery)
                    with outcome:
                        with lock:
                            effects.append(consumer)
                        outcome.complete()
            finally:
                connection.close()

        _race(attempt)

        assert sorted(effects) == sorted([CONSUMER, OTHER_CONSUMER])
        assert InboxDelivery.objects.filter(event_id=env.event_id.value).count() == 2
