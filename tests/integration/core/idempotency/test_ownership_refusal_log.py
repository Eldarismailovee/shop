"""The ownership refusal is recorded (ADR-0015 §4, item 5 AU3/AU6).

Slice 4 returned the outcome and left the log to "the slice that introduces
`core.observability`". This is that half, asserted against a real committed row rather than a
stubbed resolver, because the refusal only happens once a *committed* claim exists.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

import pytest
from django.db import transaction

from core.actor import Actor, SystemActor
from core.idempotency.claim import Claimed, claim_or_resolve
from core.idempotency.outcomes import NotOwned, Replay
from core.observability.security_events import SECURITY_LOGGER_NAME

pytestmark = pytest.mark.django_db(transaction=True)


def context_of(record: logging.LogRecord) -> dict[str, Any]:
    """The structured fields the record carries, as the formatter sees them."""
    return record.__dict__


def commit_a_claim(*, scope: str, key: str, principal: Actor | SystemActor, digest: str) -> None:
    with transaction.atomic():
        outcome = claim_or_resolve(scope=scope, key=key, principal=principal, fingerprint=digest)
        assert isinstance(outcome, Claimed)
        with outcome:
            outcome.complete(kind="created")


def resolve_as(*, scope: str, key: str, principal: Actor | SystemActor, digest: str) -> object:
    with transaction.atomic():
        return claim_or_resolve(scope=scope, key=key, principal=principal, fingerprint=digest)


class TestOwnershipRefusalIsRecorded:
    def test_a_foreign_principal_is_refused_and_the_attempt_is_logged(
        self,
        scope: str,
        actor: Actor,
        other_actor: Actor,
        digest: Callable[..., str],
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        material = digest(quantity=1)
        commit_a_claim(scope=scope, key="k-1", principal=actor, digest=material)

        with caplog.at_level(logging.INFO, logger=SECURITY_LOGGER_NAME):
            outcome = resolve_as(scope=scope, key="k-1", principal=other_actor, digest=material)

        assert isinstance(outcome, NotOwned)
        (record,) = [r for r in caplog.records if r.name == SECURITY_LOGGER_NAME]
        assert context_of(record)["security_event"] == "idempotency_key_ownership_refused"
        assert context_of(record)["security_subject"] == scope
        assert context_of(record)["principal_kind"] == "actor"

    def test_the_line_names_the_attempting_principal_not_the_owner(
        self,
        scope: str,
        actor: Actor,
        other_actor: Actor,
        digest: Callable[..., str],
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """The owner is a second party whose identity has no place in this line."""
        material = digest(quantity=1)
        commit_a_claim(scope=scope, key="k-2", principal=actor, digest=material)

        with caplog.at_level(logging.INFO, logger=SECURITY_LOGGER_NAME):
            resolve_as(scope=scope, key="k-2", principal=other_actor, digest=material)

        (record,) = [r for r in caplog.records if r.name == SECURITY_LOGGER_NAME]
        assert context_of(record)["principal_id"] == str(other_actor.principal_id.value)
        assert str(actor.principal_id.value) not in record.getMessage()
        assert str(actor.principal_id.value) not in str(record.__dict__)

    def test_the_line_carries_neither_the_key_nor_the_fingerprint(
        self,
        scope: str,
        actor: Actor,
        other_actor: Actor,
        digest: Callable[..., str],
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """AU6 — without the key, without PII, without secrets."""
        material = digest(quantity=1)
        commit_a_claim(scope=scope, key="a-very-recognisable-key", principal=actor, digest=material)

        with caplog.at_level(logging.INFO, logger=SECURITY_LOGGER_NAME):
            resolve_as(
                scope=scope,
                key="a-very-recognisable-key",
                principal=other_actor,
                digest=material,
            )

        (record,) = [r for r in caplog.records if r.name == SECURITY_LOGGER_NAME]
        rendered = f"{record.getMessage()} {record.__dict__}"
        assert "a-very-recognisable-key" not in rendered
        assert material not in rendered

    def test_a_system_principal_is_recorded_by_its_purpose(
        self,
        scope: str,
        actor: Actor,
        system_actor: SystemActor,
        digest: Callable[..., str],
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        material = digest(quantity=1)
        commit_a_claim(scope=scope, key="k-3", principal=actor, digest=material)

        with caplog.at_level(logging.INFO, logger=SECURITY_LOGGER_NAME):
            resolve_as(scope=scope, key="k-3", principal=system_actor, digest=material)

        (record,) = [r for r in caplog.records if r.name == SECURITY_LOGGER_NAME]
        assert context_of(record)["principal_kind"] == "system"
        assert context_of(record)["principal_purpose"] == system_actor.purpose
        assert "principal_id" not in context_of(record)

    def test_the_signal_survives_the_rollback_of_the_refused_transaction(
        self,
        scope: str,
        actor: Actor,
        other_actor: Actor,
        digest: Callable[..., str],
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """A security signal an attacker can erase by rolling back is not a signal."""
        material = digest(quantity=1)
        commit_a_claim(scope=scope, key="k-4", principal=actor, digest=material)

        with caplog.at_level(logging.INFO, logger=SECURITY_LOGGER_NAME):
            with pytest.raises(RuntimeError):
                with transaction.atomic():
                    claim_or_resolve(
                        scope=scope,
                        key="k-4",
                        principal=other_actor,
                        fingerprint=material,
                    )
                    raise RuntimeError("the caller aborts after being refused")

        assert [r for r in caplog.records if r.name == SECURITY_LOGGER_NAME]


class TestNothingElseIsRecorded:
    def test_an_ordinary_replay_by_the_owner_logs_no_security_event(
        self,
        scope: str,
        actor: Actor,
        digest: Callable[..., str],
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        material = digest(quantity=1)
        commit_a_claim(scope=scope, key="k-5", principal=actor, digest=material)

        with caplog.at_level(logging.INFO, logger=SECURITY_LOGGER_NAME):
            outcome = resolve_as(scope=scope, key="k-5", principal=actor, digest=material)

        assert isinstance(outcome, Replay)
        assert [r for r in caplog.records if r.name == SECURITY_LOGGER_NAME] == []

    def test_a_fingerprint_conflict_by_the_owner_logs_no_security_event(
        self,
        scope: str,
        actor: Actor,
        digest: Callable[..., str],
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """A conflict is the owner sending different material — a bug, not an intrusion."""
        commit_a_claim(scope=scope, key="k-6", principal=actor, digest=digest(quantity=1))

        with caplog.at_level(logging.INFO, logger=SECURITY_LOGGER_NAME):
            resolve_as(scope=scope, key="k-6", principal=actor, digest=digest(quantity=2))

        assert [r for r in caplog.records if r.name == SECURITY_LOGGER_NAME] == []
