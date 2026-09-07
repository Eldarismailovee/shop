"""The scope registry ships empty, and refuses everything (ADR-0015 §3, §10, A133)."""

from __future__ import annotations

from datetime import timedelta

import pytest

from core.idempotency.errors import UnregisteredScope
from core.idempotency.scopes import COMMAND_SCOPES, CommandScope, ScopeRegistry

#: Master `# 20.4`'s list, quoted here **only** to assert that none of it is registered.
#: ADR-0015 §6: these are names, not proofs of shape — a scope name does not establish that
#: the workflow it labels is one local ACID command, and `payment.initialize` in particular
#: is left to the payments phase to identify.
MASTER_ILLUSTRATIONS = (
    "checkout.place_order",
    "payment.initialize",
    "refund.create",
    "coupon.redeem",
    "tradein.redeem",
    "digital.fulfillment.allocate",
)


def test_the_registry_ships_empty() -> None:
    assert len(COMMAND_SCOPES) == 0
    assert COMMAND_SCOPES.names == frozenset()


@pytest.mark.parametrize("name", MASTER_ILLUSTRATIONS)
def test_no_master_illustration_is_registered(name: str) -> None:
    with pytest.raises(UnregisteredScope):
        COMMAND_SCOPES.resolve(name)


def test_an_unregistered_scope_cannot_be_resolved() -> None:
    """A133: a caller that invents a scope cannot claim under it."""
    with pytest.raises(UnregisteredScope):
        COMMAND_SCOPES.resolve("anything.at_all")


def test_resolution_has_no_fallback_and_no_register_on_first_use() -> None:
    with pytest.raises(UnregisteredScope):
        COMMAND_SCOPES.resolve("x.y")
    assert len(COMMAND_SCOPES) == 0


# ---------------------------------------------------------------------------
# The scope value itself
# ---------------------------------------------------------------------------


def test_a_scope_is_owner_qualified() -> None:
    scope = CommandScope(name="example.do_thing", retention=timedelta(hours=24))
    assert scope.name == "example.do_thing"


def test_a_deeper_owner_qualified_name_is_legal() -> None:
    """Master's own `digital.fulfillment.allocate` shape: more than two segments is fine."""
    assert CommandScope(name="a.b.c", retention=timedelta(hours=24)).name == "a.b.c"


@pytest.mark.parametrize(
    "name",
    [
        "place_order",  # not owner-qualified
        "Checkout.place_order",  # not lowercase
        "checkout..place_order",
        "checkout.place-order",
        "",
    ],
)
def test_a_malformed_scope_name_is_refused(name: str) -> None:
    with pytest.raises(ValueError):
        CommandScope(name=name, retention=timedelta(hours=24))


def test_a_versioned_scope_name_is_refused() -> None:
    """A scope is not versioned: two spellings would protect one command with two keys."""
    with pytest.raises(ValueError, match="version suffix"):
        CommandScope(name="checkout.place_order.v2", retention=timedelta(hours=24))


def test_retention_below_the_http_floor_is_refused() -> None:
    """ADR-0015 §10: retention covers at least the retry window the API promises."""
    with pytest.raises(ValueError, match="at least 24h"):
        CommandScope(name="example.do_thing", retention=timedelta(hours=23))


def test_a_financial_scope_may_declare_longer_retention() -> None:
    scope = CommandScope(name="example.settle", retention=timedelta(days=90))
    assert scope.retention == timedelta(days=90)


def test_a_registry_refuses_a_duplicate_name() -> None:
    scope = CommandScope(name="example.do_thing", retention=timedelta(hours=24))
    with pytest.raises(ValueError, match="appears twice"):
        ScopeRegistry([scope, scope])


def test_a_locally_built_registry_resolves_its_own_scope() -> None:
    """The mechanism works; the platform set is empty because nothing owns a command yet."""
    scope = CommandScope(name="example.do_thing", retention=timedelta(hours=24))
    assert ScopeRegistry([scope]).resolve("example.do_thing") is scope
