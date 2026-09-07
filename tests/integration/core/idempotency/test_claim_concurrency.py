"""C179 / C180 / C188 under genuine contention — two connections, one unique index.

These use `transaction=True` so each thread gets its own real connection and its own real
transaction. The contention is not simulated: both threads reach `INSERT` together, one
blocks on the unique index until the other settles, and the loser resolves against whatever
actually committed. That is ADR-0015 §7's mechanism, exercised rather than described.

The assertions are deterministic in the property they prove — *exactly one effect*, and a
resolution consistent with the winner — without depending on which thread wins, because the
scheduler's choice is not part of the contract.
"""

from __future__ import annotations

import threading
import time
from collections.abc import Callable, Iterator
from datetime import timedelta

import pytest
from django.db import connection, transaction
from django.utils import timezone

from core.actor import Actor
from core.idempotency import claim as claim_module
from core.idempotency.claim import Claimed, claim_or_resolve
from core.idempotency.models import IdempotencyKey
from core.idempotency.outcomes import Conflicted, Replay
from core.idempotency.scopes import CommandScope, ScopeRegistry
from core.public_id import PublicId

pytestmark = pytest.mark.django_db(transaction=True)

SCOPE = "fixture.contended"

#: Long enough that the loser genuinely waits on the index rather than arriving afterwards.
_WINNER_HOLD_SECONDS = 0.25


@pytest.fixture
def contended_scope(monkeypatch: pytest.MonkeyPatch) -> str:
    monkeypatch.setattr(
        claim_module,
        "COMMAND_SCOPES",
        ScopeRegistry([CommandScope(name=SCOPE, retention=timedelta(hours=24))]),
    )
    return SCOPE


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
    scope: str,
    key: str,
    principal: Actor,
    fingerprint: Callable[[], str],
    effects: list[str],
    outcomes: list[object],
    lock: threading.Lock,
) -> Callable[[threading.Barrier], None]:
    def attempt(barrier: threading.Barrier) -> None:
        try:
            barrier.wait(timeout=10)
            with transaction.atomic():
                outcome = claim_or_resolve(
                    scope=scope, key=key, principal=principal, fingerprint=fingerprint()
                )
                if isinstance(outcome, Claimed):
                    with outcome:
                        with lock:
                            effects.append("run")
                        # Hold the claim so the contender really blocks on the index.
                        time.sleep(_WINNER_HOLD_SECONDS)
                        outcome.complete(kind="created")
                with lock:
                    outcomes.append(outcome)
        finally:
            connection.close()

    return attempt


def test_c179_two_identical_requests_produce_one_effect(contended_scope, digest) -> None:
    actor = Actor(principal_id=PublicId.new())
    fingerprint = digest(qty=1)
    effects: list[str] = []
    outcomes: list[object] = []

    _race(
        _contend(
            scope=contended_scope,
            key="k",
            principal=actor,
            fingerprint=lambda: fingerprint,
            effects=effects,
            outcomes=outcomes,
            lock=threading.Lock(),
        )
    )

    assert effects == ["run"], "the protected effect ran more than once"
    assert IdempotencyKey.objects.count() == 1
    kinds = sorted(type(outcome).__name__ for outcome in outcomes)
    assert kinds == ["Claimed", "Replay"]


def test_c180_two_requests_with_different_input_produce_one_effect_and_one_conflict(
    contended_scope, digest
) -> None:
    actor = Actor(principal_id=PublicId.new())
    effects: list[str] = []
    outcomes: list[object] = []
    fingerprints: Iterator[str] = iter([digest(qty=1), digest(qty=2)])
    handout = threading.Lock()

    def next_fingerprint() -> str:
        with handout:
            return next(fingerprints)

    _race(
        _contend(
            scope=contended_scope,
            key="k",
            principal=actor,
            fingerprint=next_fingerprint,
            effects=effects,
            outcomes=outcomes,
            lock=threading.Lock(),
        )
    )

    assert effects == ["run"]
    assert IdempotencyKey.objects.count() == 1
    kinds = sorted(type(outcome).__name__ for outcome in outcomes)
    assert kinds == ["Claimed", "Conflicted"]


def test_two_principals_racing_one_key_leave_exactly_one_owner(contended_scope, digest) -> None:
    """§4: the loser is refused, and learns nothing — it does not execute the effect."""
    fingerprint = digest(qty=1)
    effects: list[str] = []
    outcomes: list[object] = []
    principals = iter([Actor(principal_id=PublicId.new()) for _ in range(2)])
    handout = threading.Lock()

    def attempt(barrier: threading.Barrier) -> None:
        with handout:
            principal = next(principals)
        try:
            barrier.wait(timeout=10)
            with transaction.atomic():
                outcome = claim_or_resolve(
                    scope=contended_scope, key="k", principal=principal, fingerprint=fingerprint
                )
                if isinstance(outcome, Claimed):
                    with outcome:
                        with handout:
                            effects.append("run")
                        time.sleep(_WINNER_HOLD_SECONDS)
                        outcome.complete(kind="created")
                with handout:
                    outcomes.append(outcome)
        finally:
            connection.close()

    _race(attempt)

    assert effects == ["run"]
    assert IdempotencyKey.objects.count() == 1
    kinds = sorted(type(outcome).__name__ for outcome in outcomes)
    assert kinds == ["Claimed", "NotOwned"]
    assert not any(isinstance(outcome, Replay | Conflicted) for outcome in outcomes)


def test_c188_two_contenders_reclaiming_one_expired_row(contended_scope, digest) -> None:
    """Two contenders meeting one expired row produce exactly one reclaim and one effect.

    What this proves is the *outcome*, not which primitive delivers it: the reclaim path
    reaches the same one-effect guarantee as every other path in §7, because a losing
    re-insert conflicts on the unique constraint and is resolved rather than executed.
    Removing the explicit `SELECT ... FOR UPDATE` does **not** fail this test — the `DELETE`
    takes the row lock anyway — so the lock is stated as readability, not as the guarantee
    (see `core/idempotency/claim.py`). What *does* fail it is dropping the bounded re-attempt,
    which is the property under test here.
    """
    owner = Actor(principal_id=PublicId.new())
    fingerprint = digest(qty=1)
    past = timezone.now() - timedelta(seconds=1)
    IdempotencyKey.objects.create(
        scope=SCOPE,
        key="k",
        principal_kind="ACTOR",
        principal_id=owner.principal_id.value,
        principal_purpose=None,
        request_fingerprint=fingerprint,
        created_at=past - timedelta(days=2),
        expires_at=past,
        result_kind="created",
    )

    effects: list[str] = []
    outcomes: list[object] = []

    _race(
        _contend(
            scope=contended_scope,
            key="k",
            principal=owner,
            fingerprint=lambda: fingerprint,
            effects=effects,
            outcomes=outcomes,
            lock=threading.Lock(),
        )
    )

    assert effects == ["run"], "the expired row was reclaimed twice"
    assert IdempotencyKey.objects.count() == 1
    kinds = sorted(type(outcome).__name__ for outcome in outcomes)
    assert kinds == ["Claimed", "Replay"]
