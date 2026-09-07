"""LK6's behavioural half on the one path that takes a row lock today.

Item 5 §20.3 LK6 requires that lock and statement timeouts are configured **and** that
exceeding one is a technical fault. Item 5 §11.6 is precise about the second: a bounded wait
exceeded propagates **untranslated** (item 4 §13.5), and "a retry with the same key remains
safe". Master `# 22.6` sketches the same outcome as a "retryable business error"; the frozen
artifact refines it and governs, so what is asserted here is the frozen behaviour.

`claim_or_resolve` takes a row lock in `_lock_existing` when it meets a committed row. That
lock is the subject: held elsewhere, the claim gives up on its bound rather than waiting for
a worker's whole budget, and what reaches the caller is a fault — not a replay, not a
conflict, not a refusal, and not a swallowed contention.
"""

from __future__ import annotations

import threading
from collections.abc import Callable, Iterator

import pytest
from django.db import OperationalError, connection, transaction

from core.actor import Actor
from core.idempotency.claim import Claimed, claim_or_resolve
from core.idempotency.errors import ClaimContention
from core.idempotency.models import IdempotencyKey
from core.idempotency.outcomes import Conflicted, NotOwned, Replay

pytestmark = pytest.mark.django_db(transaction=True)

#: Short enough to keep the suite quick. The *configured* bound is proved in
#: `tests/integration/core/test_bounded_waits.py`; what is under test here is what the code
#: does when a bound — whatever its value — is exceeded, and three seconds of real waiting
#: would add nothing to that. Rule LK6 permits the `SET` because it excludes the test tier;
#: a production module doing this is exactly what it reports.
_CONTENDER_LOCK_TIMEOUT_MS = 250


@pytest.fixture
def committed_key(scope: str, actor: Actor, digest: Callable[..., str]) -> str:
    """One completed claim, committed, so a contender meets a real row. Returns its digest."""
    fingerprint = digest(qty=1)
    with transaction.atomic():
        outcome = claim_or_resolve(scope=scope, key="k", principal=actor, fingerprint=fingerprint)
        assert isinstance(outcome, Claimed)
        with outcome:
            outcome.complete(kind="created")
    return fingerprint


@pytest.fixture
def row_locked_elsewhere(scope: str) -> Iterator[None]:
    """Hold `(scope, 'k')` under a row lock on a second real connection for the test's duration."""
    holding = threading.Event()
    release = threading.Event()
    failure: list[BaseException] = []

    def hold() -> None:
        try:
            with transaction.atomic():
                list(IdempotencyKey.objects.select_for_update().filter(scope=scope, key="k"))
                holding.set()
                release.wait(timeout=30)
        except BaseException as error:  # noqa: BLE001 — reported to the test, never swallowed
            failure.append(error)
            holding.set()
        finally:
            connection.close()

    holder = threading.Thread(target=hold)
    holder.start()
    try:
        assert holding.wait(timeout=10), "the holding thread never took the row lock"
        assert not failure, f"the holding thread failed: {failure[0]!r}"
        yield
    finally:
        release.set()
        holder.join(timeout=30)
        assert not holder.is_alive(), "the holding thread never released the row"


def _claim_against_the_held_row(*, scope: str, actor: Actor, fingerprint: str) -> object:
    with transaction.atomic():
        with connection.cursor() as cursor:
            cursor.execute(f"SET LOCAL lock_timeout = {_CONTENDER_LOCK_TIMEOUT_MS}")
        return claim_or_resolve(scope=scope, key="k", principal=actor, fingerprint=fingerprint)


def test_the_claim_path_raises_an_untranslated_operational_error(
    scope: str, actor: Actor, committed_key: str, row_locked_elsewhere: None
) -> None:
    with pytest.raises(OperationalError) as raised:
        _claim_against_the_held_row(scope=scope, actor=actor, fingerprint=committed_key)

    assert not isinstance(raised.value, ClaimContention), (
        "the timeout was translated into the mechanism's own error, which a caller would "
        "read as contention that settled rather than as a technical fault"
    )


def test_the_timeout_is_not_dressed_as_a_claim_outcome(
    scope: str, actor: Actor, committed_key: str, row_locked_elsewhere: None
) -> None:
    """A timeout laundered into any of the four outcomes is a real commercial defect.

    `Replay` would tell a caller its command already succeeded; `Conflicted` and `NotOwned`
    would refuse a legitimate request on evidence that does not exist; `Claimed` would let the
    protected effect run a second time.
    """
    seen: list[object] = []
    with pytest.raises(OperationalError):
        seen.append(
            _claim_against_the_held_row(scope=scope, actor=actor, fingerprint=committed_key)
        )

    assert seen == []


def test_the_contended_row_is_exactly_what_it_was(
    scope: str, actor: Actor, committed_key: str, row_locked_elsewhere: None
) -> None:
    """§11.6's "a retry with the same key remains safe": the fault durably changed nothing."""
    with pytest.raises(OperationalError):
        _claim_against_the_held_row(scope=scope, actor=actor, fingerprint=committed_key)

    assert IdempotencyKey.objects.count() == 1
    row = IdempotencyKey.objects.get()
    assert row.request_fingerprint == committed_key
    assert row.result_kind == "created"


def test_the_same_key_replays_normally_once_the_lock_is_gone(
    scope: str, actor: Actor, committed_key: str, digest: Callable[..., str]
) -> None:
    """The positive twin: without contention the identical call is an ordinary replay.

    Without this, the three tests above would pass just as well against a claim path that had
    stopped working altogether.
    """
    with transaction.atomic():
        outcome = claim_or_resolve(scope=scope, key="k", principal=actor, fingerprint=committed_key)

    assert isinstance(outcome, Replay)
    assert not isinstance(outcome, Conflicted | NotOwned)
