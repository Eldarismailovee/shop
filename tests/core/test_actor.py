"""The actor primitive (ADR-0006 §1, item 4 §11).

The rule these tests exist for is item 4 Z2: `actor=None` never means "system", "admin",
"trusted caller" or "skip the check". There is no third form between "public read, no actor"
and "private read, mandatory actor", and no value of either type here is constructible as
"unauthenticated but privileged".
"""

from __future__ import annotations

import ast
import dataclasses

import pytest

from core.actor import Actor, SystemActor
from core.public_id import PublicId
from tests.conftest import REPO_ROOT

ACTOR_TYPES = (Actor, SystemActor)

# Neither subject type derives from the other (Z1), so the parametrised cases name both.
ActorType = type[Actor] | type[SystemActor]


def test_an_actor_carries_an_authenticated_principal() -> None:
    principal = PublicId.new()
    assert Actor(principal_id=principal).principal_id == principal


def test_a_system_actor_is_an_explicit_privileged_context() -> None:
    """Z3: privileged use is visible at every call site and greppable in review."""
    assert SystemActor(purpose="erp_sync").purpose == "erp_sync"


@pytest.mark.parametrize("subject", ACTOR_TYPES)
def test_an_authorization_subject_is_immutable_and_slotted(subject: ActorType) -> None:
    instance = Actor(principal_id=PublicId.new()) if subject is Actor else SystemActor(purpose="p")
    field = "principal_id" if subject is Actor else "purpose"
    with pytest.raises(dataclasses.FrozenInstanceError):
        setattr(instance, field, None)
    with pytest.raises(AttributeError):
        instance.role = "admin"  # type: ignore[union-attr]


@pytest.mark.parametrize("subject", ACTOR_TYPES)
def test_no_field_has_a_default_so_no_shortcut_shape_exists(subject: ActorType) -> None:
    """Z1, Z2: no default and no `Optional`, so there is no partially built subject."""
    for field in dataclasses.fields(subject):
        assert field.default is dataclasses.MISSING
        assert field.default_factory is dataclasses.MISSING
    with pytest.raises(TypeError):
        subject()  # type: ignore[call-arg]


@pytest.mark.parametrize("subject", ACTOR_TYPES)
def test_none_is_never_an_authorization_subject(subject: ActorType) -> None:
    """Z2: an optional actor is an authorization switch disguised as a default."""
    field = "principal_id" if subject is Actor else "purpose"
    with pytest.raises(TypeError):
        subject(**{field: None})  # type: ignore[arg-type]  # Z2: None is the thing rejected


def test_a_principal_is_a_public_id_not_a_bare_uuid_or_an_internal_identifier() -> None:
    """PI3, TY1, TY2: the annotation must state which identity space the value belongs to."""
    import uuid

    from core.events.identity import EventId

    for wrong in (uuid.uuid7(), 12345, "018f6c1e-4a2b-7c3d-8e4f-5a6b7c8d9e0f"):
        with pytest.raises(TypeError):
            Actor(principal_id=wrong)  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        Actor(principal_id=EventId.new())  # type: ignore[arg-type]


@pytest.mark.parametrize("purpose", ["", " ", "ERP", "erp sync", "erp-sync", "1erp", "erp.sync"])
def test_a_privileged_context_must_name_a_well_formed_purpose(purpose: str) -> None:
    """A bounded mechanism token, never a free-text message that could carry a secret."""
    with pytest.raises(ValueError):
        SystemActor(purpose=purpose)


def test_the_two_subjects_are_siblings_not_a_hierarchy() -> None:
    """Z4: a system-only operation can be typed so that only a system context satisfies it."""
    assert not issubclass(SystemActor, Actor)
    assert not issubclass(Actor, SystemActor)
    assert not isinstance(SystemActor(purpose="p"), Actor)
    assert not isinstance(Actor(principal_id=PublicId.new()), SystemActor)


def test_the_module_exports_no_convenience_union() -> None:
    """A callable that accepts either subject writes `Actor | SystemActor` itself, so every
    privileged admission stays visible; an alias would become the default annotation."""
    import core.actor as module

    assert module.__all__ == ("Actor", "SystemActor")


def test_the_actor_module_is_domain_independent_and_framework_free() -> None:
    """ADR-0006 §1, D2-D5: no domain, no Django, no HTTP, no session, no vendor."""
    source = (REPO_ROOT / "core" / "actor.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported = {
        alias.name.split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    } | {
        (node.module or "").split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
    }
    assert imported <= {"__future__", "re", "dataclasses", "core"}


def test_the_actor_carries_no_permission_model_yet() -> None:
    """ADR-0006 §3: roles, capabilities, sessions and tenants belong to the authentication
    phase. A domain never accepts a pre-computed decision instead of the subject (Z7)."""
    declared = {field.name for subject in ACTOR_TYPES for field in dataclasses.fields(subject)}
    assert declared == {"principal_id", "purpose"}
    for subject in ACTOR_TYPES:
        exposed = {name for name in dir(subject) if not name.startswith("_")}
        assert not exposed & {"roles", "capabilities", "session", "tenant", "is_owner", "allowed"}
