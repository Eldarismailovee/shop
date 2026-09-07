"""C177-C188 — the ADR-0015 behavioural corpus, against real PostgreSQL.

Each test names the check it discharges. Three of the corpus's rows have no subject in this
slice and are **not** claimed as passing; they are recorded in
`docs/architecture/phase-1/04-command-idempotency.md` with their owner:

* **C186** (Redis unavailable / flushed between attempts) — the launch build has no Redis at
  all (Slice 3 §2), so there is nothing to make unavailable. The invariant it protects is
  discharged structurally instead by A129 and by `test_no_cache_dependency_exists`.
* **C189** (a duplicate *event* delivery creates no `IdempotencyKey` row) — the Inbox and
  `EventId` arrive with `core.inbox`.
* **C190** (a provider-side retry under the provider's own key) — the payments phase.
"""

from __future__ import annotations

import uuid
from datetime import timedelta

import pytest
from django.db import transaction
from django.utils import timezone

from core.actor import Actor, SystemActor
from core.errors import DomainError
from core.idempotency import claim as claim_module
from core.idempotency.claim import Claimed, claim_or_resolve
from core.idempotency.errors import (
    ClaimOutsideTransaction,
    IncompleteClaim,
    InvalidClaimInput,
)
from core.idempotency.models import IdempotencyKey
from core.idempotency.outcomes import Conflicted, NotOwned, Replay
from core.idempotency.scopes import CommandScope, ScopeRegistry
from core.public_id import PublicId

pytestmark = pytest.mark.django_db


class Effects:
    """A stand-in for the protected durable effect, so "executed twice" is observable."""

    def __init__(self) -> None:
        self.runs: list[str] = []

    def perform(self, label: str = "run") -> None:
        self.runs.append(label)


def _claim_and_complete(
    *,
    scope: str,
    key: str,
    principal: Actor | SystemActor,
    fingerprint: str,
    effects: Effects,
    locator: PublicId | None = None,
    detail: object = None,
):
    """The sanctioned shape, run inside one transaction."""
    with transaction.atomic():
        outcome = claim_or_resolve(
            scope=scope, key=key, principal=principal, fingerprint=fingerprint
        )
        if isinstance(outcome, Claimed):
            with outcome:
                effects.perform()
                outcome.complete(kind="created", public_id=locator, detail=detail)
        return outcome


# ---------------------------------------------------------------------------
# C177 / C178 — first use, and an exact retry
# ---------------------------------------------------------------------------


def test_c177_first_use_executes_once_and_leaves_one_row(scope, actor, digest) -> None:
    effects = Effects()
    outcome = _claim_and_complete(
        scope=scope, key="k", principal=actor, fingerprint=digest(qty=1), effects=effects
    )

    assert isinstance(outcome, Claimed)
    assert effects.runs == ["run"]
    assert IdempotencyKey.objects.count() == 1


def test_c178_an_exact_retry_replays_and_performs_no_second_effect(scope, actor, digest) -> None:
    effects = Effects()
    fingerprint = digest(qty=1)
    locator = PublicId.new()

    _claim_and_complete(
        scope=scope,
        key="k",
        principal=actor,
        fingerprint=fingerprint,
        effects=effects,
        locator=locator,
    )
    replayed = _claim_and_complete(
        scope=scope, key="k", principal=actor, fingerprint=fingerprint, effects=effects
    )

    assert isinstance(replayed, Replay)
    assert effects.runs == ["run"]  # exactly one effect
    assert replayed.result.kind == "created"
    assert replayed.result.public_id == locator
    assert IdempotencyKey.objects.count() == 1


# ---------------------------------------------------------------------------
# C180 / C181 — conflict and ownership, sequentially
# ---------------------------------------------------------------------------


def test_c180_a_different_fingerprint_on_a_committed_key_conflicts(scope, actor, digest) -> None:
    effects = Effects()
    _claim_and_complete(
        scope=scope, key="k", principal=actor, fingerprint=digest(qty=1), effects=effects
    )

    outcome = _claim_and_complete(
        scope=scope, key="k", principal=actor, fingerprint=digest(qty=2), effects=effects
    )

    assert isinstance(outcome, Conflicted)
    assert effects.runs == ["run"]


def test_c181_a_different_principal_is_refused_and_learns_nothing(
    scope, actor, other_actor, digest
) -> None:
    effects = Effects()
    fingerprint = digest(qty=1)
    _claim_and_complete(
        scope=scope, key="k", principal=actor, fingerprint=fingerprint, effects=effects
    )

    outcome = _claim_and_complete(
        scope=scope, key="k", principal=other_actor, fingerprint=fingerprint, effects=effects
    )

    assert isinstance(outcome, NotOwned)
    # The refusal carries no fields at all, so nothing about the row can leak through it —
    # not the result, not the owner, not even that the key exists.
    assert outcome.__slots__ == ()
    assert effects.runs == ["run"]


def test_ownership_is_decided_before_the_fingerprint(scope, actor, other_actor, digest) -> None:
    """A stranger must not learn whether its own input would have matched (§4)."""
    effects = Effects()
    _claim_and_complete(
        scope=scope, key="k", principal=actor, fingerprint=digest(qty=1), effects=effects
    )

    outcome = _claim_and_complete(
        scope=scope, key="k", principal=other_actor, fingerprint=digest(qty=999), effects=effects
    )

    assert isinstance(outcome, NotOwned)  # not Conflicted


def test_a_system_context_is_a_principal_in_its_own_right(
    scope, actor, system_actor, digest
) -> None:
    effects = Effects()
    fingerprint = digest(qty=1)
    _claim_and_complete(
        scope=scope, key="k", principal=system_actor, fingerprint=fingerprint, effects=effects
    )

    outcome = _claim_and_complete(
        scope=scope, key="k", principal=actor, fingerprint=fingerprint, effects=effects
    )

    assert isinstance(outcome, NotOwned)


# ---------------------------------------------------------------------------
# C182 / C183 / C184 — nothing durable survives a rollback
# ---------------------------------------------------------------------------


def test_c182_a_validation_failure_before_the_transaction_leaves_no_row(
    scope, actor, digest
) -> None:
    with pytest.raises(InvalidClaimInput), transaction.atomic():
        claim_or_resolve(scope=scope, key="", principal=actor, fingerprint=digest(qty=1))

    assert IdempotencyKey.objects.count() == 0

    # ...and the key is claimable normally afterwards.
    effects = Effects()
    outcome = _claim_and_complete(
        scope=scope, key="k", principal=actor, fingerprint=digest(qty=1), effects=effects
    )
    assert isinstance(outcome, Claimed)


def test_c183_a_business_rollback_after_the_claim_leaves_no_row(scope, actor, digest) -> None:
    effects = Effects()
    fingerprint = digest(qty=1)

    class BusinessRejection(Exception):
        pass

    with pytest.raises(BusinessRejection):
        with transaction.atomic():
            outcome = claim_or_resolve(
                scope=scope, key="k", principal=actor, fingerprint=fingerprint
            )
            assert isinstance(outcome, Claimed)
            with outcome:
                effects.perform("first")
                outcome.complete(kind="created")
                raise BusinessRejection

    assert IdempotencyKey.objects.count() == 0

    # A retry re-executes rather than replaying a stale failure: the key reserved nothing.
    retried = _claim_and_complete(
        scope=scope, key="k", principal=actor, fingerprint=fingerprint, effects=effects
    )
    assert isinstance(retried, Claimed)
    assert effects.runs == ["first", "run"]


def test_c184_a_technical_fault_before_commit_leaves_no_row_and_is_untranslated(
    scope, actor, digest
) -> None:
    class DatabaseWentAway(Exception):
        """A technical fault is never dressed as a business error (item 4 §13.5)."""

    with pytest.raises(DatabaseWentAway) as caught:
        with transaction.atomic():
            outcome = claim_or_resolve(
                scope=scope, key="k", principal=actor, fingerprint=digest(qty=1)
            )
            assert isinstance(outcome, Claimed)
            with outcome:
                raise DatabaseWentAway

    assert not isinstance(caught.value, DomainError)
    assert IdempotencyKey.objects.count() == 0


def test_a_claim_that_is_never_completed_cannot_commit(scope, actor, digest) -> None:
    """§6: a committed claim carries the result it promises to replay, or does not commit."""
    with pytest.raises(IncompleteClaim):
        with transaction.atomic():
            outcome = claim_or_resolve(
                scope=scope, key="k", principal=actor, fingerprint=digest(qty=1)
            )
            assert isinstance(outcome, Claimed)
            with outcome:
                pass  # the effect ran, but nothing was recorded

    assert IdempotencyKey.objects.count() == 0


# ---------------------------------------------------------------------------
# C185 — after COMMIT the operation stands, and nothing is compensated
# ---------------------------------------------------------------------------


def test_c185_a_failure_after_commit_leaves_the_effect_standing(scope, actor, digest) -> None:
    effects = Effects()
    fingerprint = digest(qty=1)
    locator = PublicId.new()

    class ResponseLost(Exception):
        pass

    _claim_and_complete(
        scope=scope,
        key="k",
        principal=actor,
        fingerprint=fingerprint,
        effects=effects,
        locator=locator,
    )
    # The transaction committed; the response is then lost on the way back to the caller.
    with pytest.raises(ResponseLost):
        raise ResponseLost

    assert IdempotencyKey.objects.count() == 1  # no compensation, no cleanup

    replayed = _claim_and_complete(
        scope=scope, key="k", principal=actor, fingerprint=fingerprint, effects=effects
    )
    assert isinstance(replayed, Replay)
    assert replayed.result.public_id == locator
    assert effects.runs == ["run"]


# ---------------------------------------------------------------------------
# C187 — replay reconstructs a bounded semantic result, never a raw response
# ---------------------------------------------------------------------------


def test_c187_replay_reconstructs_the_stored_semantic_material(scope, actor, digest) -> None:
    effects = Effects()
    fingerprint = digest(qty=1)
    locator = PublicId.new()

    _claim_and_complete(
        scope=scope,
        key="k",
        principal=actor,
        fingerprint=fingerprint,
        effects=effects,
        locator=locator,
        detail={"state": "accepted", "items": 2},
    )
    replayed = _claim_and_complete(
        scope=scope, key="k", principal=actor, fingerprint=fingerprint, effects=effects
    )

    assert isinstance(replayed, Replay)
    assert replayed.result.kind == "created"
    assert replayed.result.public_id == locator
    # Canonical text, so one stored value has exactly one rendering.
    assert replayed.result.detail_json == '{"items":2,"state":"accepted"}'


def test_the_stored_locator_is_a_public_id_not_an_internal_identifier(scope, actor, digest) -> None:
    effects = Effects()
    fingerprint = digest(qty=1)
    locator = PublicId.new()
    _claim_and_complete(
        scope=scope,
        key="k",
        principal=actor,
        fingerprint=fingerprint,
        effects=effects,
        locator=locator,
    )

    replayed = _claim_and_complete(
        scope=scope, key="k", principal=actor, fingerprint=fingerprint, effects=effects
    )
    assert isinstance(replayed, Replay)
    assert type(replayed.result.public_id) is PublicId


def test_an_internal_identifier_cannot_be_recorded_as_the_result_locator(
    scope, actor, digest
) -> None:
    with pytest.raises(InvalidClaimInput, match="PublicId"):
        with transaction.atomic():
            outcome = claim_or_resolve(
                scope=scope, key="k", principal=actor, fingerprint=digest(qty=1)
            )
            assert isinstance(outcome, Claimed)
            with outcome:
                outcome.complete(kind="created", public_id=uuid.uuid4())  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# C188 — expiry ends the replay promise, and the key re-executes
# ---------------------------------------------------------------------------


def _expire(key: str) -> None:
    """Simulate the retention window passing, without waiting 24 hours for it."""
    past = timezone.now() - timedelta(seconds=1)
    IdempotencyKey.objects.filter(key=key).update(
        created_at=past - timedelta(days=2), expires_at=past
    )


def test_c188_after_retention_expiry_the_key_re_executes(scope, actor, digest) -> None:
    effects = Effects()
    fingerprint = digest(qty=1)
    _claim_and_complete(
        scope=scope, key="k", principal=actor, fingerprint=fingerprint, effects=effects
    )
    _expire("k")

    outcome = _claim_and_complete(
        scope=scope, key="k", principal=actor, fingerprint=fingerprint, effects=effects
    )

    assert isinstance(outcome, Claimed)  # re-executed, not replayed
    assert effects.runs == ["run", "run"]
    assert IdempotencyKey.objects.count() == 1  # the expired row was reclaimed, not doubled


def test_an_expired_row_belonging_to_someone_else_is_reclaimable(
    scope, actor, other_actor, digest
) -> None:
    """Expiry ends the promise for everyone; the row is no longer anybody's claim."""
    effects = Effects()
    _claim_and_complete(
        scope=scope, key="k", principal=actor, fingerprint=digest(qty=1), effects=effects
    )
    _expire("k")

    outcome = _claim_and_complete(
        scope=scope, key="k", principal=other_actor, fingerprint=digest(qty=2), effects=effects
    )

    assert isinstance(outcome, Claimed)
    assert IdempotencyKey.objects.count() == 1


def test_a_live_row_is_never_treated_as_expired(scope, actor, digest) -> None:
    effects = Effects()
    fingerprint = digest(qty=1)
    _claim_and_complete(
        scope=scope, key="k", principal=actor, fingerprint=fingerprint, effects=effects
    )

    outcome = _claim_and_complete(
        scope=scope, key="k", principal=actor, fingerprint=fingerprint, effects=effects
    )
    assert isinstance(outcome, Replay)


# ---------------------------------------------------------------------------
# The key is opaque, and stored exactly as given
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("first", "second"),
    [
        (" a ", "a"),
        ("A", "a"),
        ("a b", "a b"),
        ("é", "é"),  # combining vs precomposed: two keys, not one
    ],
)
def test_keys_that_differ_only_in_spelling_are_different_keys(
    scope, actor, digest, first: str, second: str
) -> None:
    effects = Effects()
    fingerprint = digest(qty=1)

    assert isinstance(
        _claim_and_complete(
            scope=scope, key=first, principal=actor, fingerprint=fingerprint, effects=effects
        ),
        Claimed,
    )
    assert isinstance(
        _claim_and_complete(
            scope=scope, key=second, principal=actor, fingerprint=fingerprint, effects=effects
        ),
        Claimed,
    )
    assert IdempotencyKey.objects.count() == 2
    assert set(IdempotencyKey.objects.values_list("key", flat=True)) == {first, second}


def test_the_same_key_in_two_scopes_is_two_claims(monkeypatch, actor, digest) -> None:
    """ADR-0015 §3: a key is not globally unique, and nothing may assume it is."""
    monkeypatch.setattr(
        claim_module,
        "COMMAND_SCOPES",
        ScopeRegistry(
            [
                CommandScope(name="fixture.one", retention=timedelta(hours=24)),
                CommandScope(name="fixture.two", retention=timedelta(hours=24)),
            ]
        ),
    )
    effects = Effects()
    fingerprint = digest(qty=1)

    for scope_name in ("fixture.one", "fixture.two"):
        outcome = _claim_and_complete(
            scope=scope_name,
            key="shared",
            principal=actor,
            fingerprint=fingerprint,
            effects=effects,
        )
        assert isinstance(outcome, Claimed)

    assert IdempotencyKey.objects.count() == 2


# ---------------------------------------------------------------------------
# The mechanism refuses to be used outside a transaction
# ---------------------------------------------------------------------------


@pytest.mark.django_db(transaction=True)
def test_a_claim_outside_a_transaction_is_refused(scope, actor, digest) -> None:
    """§6/A131: in autocommit the claim would commit on its own.

    `transaction=True` matters here: the ordinary `django_db` fixture wraps each test in an
    atomic block, which would hide exactly the condition this test is about.
    """
    with pytest.raises(ClaimOutsideTransaction):
        claim_or_resolve(scope=scope, key="k", principal=actor, fingerprint=digest(qty=1))
