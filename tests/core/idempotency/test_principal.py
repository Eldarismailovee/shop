"""Principal binding: two shapes, and `NULL` never means "anybody" (ADR-0015 §4)."""

from __future__ import annotations

import pytest

from core.actor import Actor, SystemActor
from core.idempotency.principal import PrincipalKind, PrincipalRef
from core.public_id import PublicId


def test_an_actor_is_encoded_by_its_locator() -> None:
    locator = PublicId.new()
    reference = PrincipalRef.of(Actor(principal_id=locator))
    assert reference.kind is PrincipalKind.ACTOR
    assert reference.actor_id == locator.value
    assert reference.purpose is None


def test_a_system_context_is_encoded_by_its_purpose() -> None:
    reference = PrincipalRef.of(SystemActor(purpose="reconciliation"))
    assert reference.kind is PrincipalKind.SYSTEM
    assert reference.actor_id is None
    assert reference.purpose == "reconciliation"


def test_the_same_actor_encodes_equal() -> None:
    locator = PublicId.new()
    assert PrincipalRef.of(Actor(principal_id=locator)) == PrincipalRef.of(
        Actor(principal_id=locator)
    )


def test_two_actors_never_encode_equal() -> None:
    assert PrincipalRef.of(Actor(principal_id=PublicId.new())) != PrincipalRef.of(
        Actor(principal_id=PublicId.new())
    )


def test_an_actor_and_a_system_context_never_collide() -> None:
    """Two columns rather than one string: no locator can render as a purpose token."""
    assert PrincipalRef.of(Actor(principal_id=PublicId.new())) != PrincipalRef.of(
        SystemActor(purpose="reconciliation")
    )


def test_two_system_purposes_are_distinct_principals() -> None:
    assert PrincipalRef.of(SystemActor(purpose="reconciliation")) != PrincipalRef.of(
        SystemActor(purpose="erp_import")
    )


def test_there_is_no_third_form() -> None:
    with pytest.raises(TypeError, match="no third form"):
        PrincipalRef.of(None)  # type: ignore[arg-type]


def test_a_bare_locator_is_not_a_principal() -> None:
    with pytest.raises(TypeError):
        PrincipalRef.of(PublicId.new())  # type: ignore[arg-type]


def test_a_half_filled_reference_cannot_be_constructed() -> None:
    """`NULL` never means "anybody": there is no constructible "no principal" value."""
    with pytest.raises(ValueError):
        PrincipalRef(kind=PrincipalKind.ACTOR, actor_id=None, purpose=None)
    with pytest.raises(ValueError):
        PrincipalRef(kind=PrincipalKind.SYSTEM, actor_id=None, purpose=None)


def test_a_reference_cannot_carry_both_forms() -> None:
    with pytest.raises(ValueError):
        PrincipalRef(
            kind=PrincipalKind.ACTOR,
            actor_id=PublicId.new().value,
            purpose="reconciliation",
        )
