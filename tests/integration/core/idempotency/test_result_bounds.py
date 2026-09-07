"""The stored result: bounded, semantic, and off the claim path (ADR-0015 §9, A135/A136)."""

from __future__ import annotations

import pytest
from django.db import connection, transaction
from django.test.utils import CaptureQueriesContext

from core.idempotency.bounds import MAX_RESULT_DETAIL_BYTES
from core.idempotency.claim import Claimed, claim_or_resolve
from core.idempotency.errors import InvalidClaimInput
from core.idempotency.models import IdempotencyKey
from core.idempotency.outcomes import Replay

pytestmark = pytest.mark.django_db


def _claim(scope, actor, fingerprint, *, key="k"):
    return claim_or_resolve(scope=scope, key=key, principal=actor, fingerprint=fingerprint)


# ---------------------------------------------------------------------------
# The cap is applied before the write, and the result is refused, never truncated
# ---------------------------------------------------------------------------


def test_an_oversized_result_is_refused_before_any_write(scope, actor, digest) -> None:
    with pytest.raises(InvalidClaimInput, match="over the"), transaction.atomic():
        outcome = _claim(scope, actor, digest(qty=1))
        assert isinstance(outcome, Claimed)
        with outcome:
            outcome.complete(kind="created", detail={"blob": "x" * (MAX_RESULT_DETAIL_BYTES + 1)})

    assert IdempotencyKey.objects.count() == 0


def test_a_result_at_the_bound_is_accepted(scope, actor, digest) -> None:
    payload = {"blob": "x" * (MAX_RESULT_DETAIL_BYTES - len('{"blob":""}'))}
    with transaction.atomic():
        outcome = _claim(scope, actor, digest(qty=1))
        assert isinstance(outcome, Claimed)
        with outcome:
            outcome.complete(kind="created", detail=payload)

    assert IdempotencyKey.objects.count() == 1


def test_a_float_cannot_enter_the_stored_result(scope, actor, digest) -> None:
    """Money is integer minor units with an explicit currency, here as everywhere."""
    with pytest.raises(InvalidClaimInput, match="float"), transaction.atomic():
        outcome = _claim(scope, actor, digest(qty=1))
        assert isinstance(outcome, Claimed)
        with outcome:
            outcome.complete(kind="created", detail={"total": 19.99})


def test_the_result_round_trips_through_jsonb_canonically(scope, actor, digest) -> None:
    fingerprint = digest(qty=1)
    payload = {"z": 1, "a": [1, 2], "n": None, "t": True}
    with transaction.atomic():
        outcome = _claim(scope, actor, fingerprint)
        assert isinstance(outcome, Claimed)
        with outcome:
            outcome.complete(kind="created", detail=payload)

    with transaction.atomic():
        replayed = _claim(scope, actor, fingerprint)
    assert isinstance(replayed, Replay)
    assert replayed.result.detail_json == '{"a":[1,2],"n":null,"t":true,"z":1}'


def test_completion_happens_once(scope, actor, digest) -> None:
    from core.idempotency.errors import IncompleteClaim

    with pytest.raises(IncompleteClaim, match="already been completed"), transaction.atomic():
        outcome = _claim(scope, actor, digest(qty=1))
        assert isinstance(outcome, Claimed)
        with outcome:
            outcome.complete(kind="created")
            outcome.complete(kind="created")


def test_completion_outside_the_block_is_refused(scope, actor, digest) -> None:
    """The `with` block is what guarantees a claim cannot commit without its result."""
    from core.idempotency.errors import IncompleteClaim

    with pytest.raises(IncompleteClaim, match="inside"), transaction.atomic():
        outcome = _claim(scope, actor, digest(qty=1))
        assert isinstance(outcome, Claimed)
        outcome.complete(kind="created")


# ---------------------------------------------------------------------------
# A136 (behavioural half) — the heavy column is not read while claiming
# ---------------------------------------------------------------------------


def test_the_claim_path_does_not_read_the_heavy_column(scope, actor, digest) -> None:
    """Master `# 20.5`: the heavy result column is selected only when a replay needs it."""
    fingerprint = digest(qty=1)
    with transaction.atomic():
        outcome = _claim(scope, actor, fingerprint)
        assert isinstance(outcome, Claimed)
        with outcome:
            outcome.complete(kind="created", detail={"state": "accepted"})

    # A conflicting attempt takes the claim path — insert, then the guarded lookup — and
    # resolves without ever needing the result body.
    with CaptureQueriesContext(connection) as captured, transaction.atomic():
        conflicting = _claim(scope, actor, digest(qty=2))

    selects = [
        q["sql"]
        for q in captured.captured_queries
        if q["sql"].lstrip().upper().startswith("SELECT")
    ]
    assert selects, "the claim path issued no lookup at all"
    assert not any("result_detail" in sql for sql in selects), selects
    assert type(conflicting).__name__ == "Conflicted"


def test_a_replay_does_read_the_heavy_column(scope, actor, digest) -> None:
    """The other half of the same rule: deferred, not absent."""
    fingerprint = digest(qty=1)
    with transaction.atomic():
        outcome = _claim(scope, actor, fingerprint)
        assert isinstance(outcome, Claimed)
        with outcome:
            outcome.complete(kind="created", detail={"state": "accepted"})

    with CaptureQueriesContext(connection) as captured, transaction.atomic():
        replayed = _claim(scope, actor, fingerprint)

    assert isinstance(replayed, Replay)
    assert replayed.result.detail_json == '{"state":"accepted"}'
    assert any("result_detail" in q["sql"] for q in captured.captured_queries)
