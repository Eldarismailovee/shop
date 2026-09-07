"""Fixtures for the command-idempotency tier.

The platform scope set ships empty and stays empty (`core/idempotency/scopes.py`), so every
case here builds its own registry under a fixture name that exists nowhere else. No sample
scope is added to the production set to make the tests convenient — that is exactly the
"registered for the sake of the mechanism" entry item 8's empty registry refuses, and
ADR-0015 §3 leaves scope registration to the phase that owns the command.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import timedelta

import pytest

from core.actor import Actor, SystemActor
from core.idempotency import claim as claim_module
from core.idempotency.fingerprint import canonicalize, fingerprint
from core.idempotency.scopes import CommandScope, ScopeRegistry
from core.public_id import PublicId

#: A name that belongs to no real module, so it can never be mistaken for a launch scope.
TEST_SCOPE = "fixture.do_thing"

#: ADR-0015 §10's HTTP floor. Expiry cases backdate `expires_at` rather than shorten this:
#: a scope may not declare retention below the window it promises.
TEST_RETENTION = timedelta(hours=24)


@pytest.fixture
def scope(monkeypatch: pytest.MonkeyPatch) -> str:
    """Register one throwaway scope for the duration of a test."""
    registry = ScopeRegistry([CommandScope(name=TEST_SCOPE, retention=TEST_RETENTION)])
    monkeypatch.setattr(claim_module, "COMMAND_SCOPES", registry)
    return TEST_SCOPE


@pytest.fixture
def actor() -> Actor:
    return Actor(principal_id=PublicId.new())


@pytest.fixture
def other_actor() -> Actor:
    return Actor(principal_id=PublicId.new())


@pytest.fixture
def system_actor() -> SystemActor:
    return SystemActor(purpose="reconciliation")


@pytest.fixture
def digest() -> Callable[..., str]:
    """Build a fingerprint from keyword material, the way a scope owner would."""

    def build(**material: object) -> str:
        return fingerprint(canonicalize(material))

    return build
