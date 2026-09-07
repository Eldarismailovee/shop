"""LK6's first half against real PostgreSQL: the configured bounds reach the server.

`tests/config/test_database_baseline.py` asserts that a bound is *configured*. Configuration
that never arrives — a typo in the options string, an option the driver silently drops — is
the failure that assertion cannot see, so this file asks PostgreSQL what it actually received.

The behavioural half of LK6 (item 5 §11.6: a bounded wait exceeded is a technical fault, never
a business outcome) is proved on its one existing subject in
`tests/integration/core/idempotency/test_bounded_lock_wait.py`.
"""

from __future__ import annotations

import pytest
from django.conf import settings
from django.db import connection

pytestmark = pytest.mark.django_db

SESSION_BOUNDS = ("statement_timeout", "lock_timeout", "idle_in_transaction_session_timeout")


def _configured() -> dict[str, int]:
    """The session bounds as the composition root spells them on the wire."""
    options = settings.DATABASES["default"]["OPTIONS"]
    assert isinstance(options, dict)
    delivered = options["options"]
    assert isinstance(delivered, str)
    bounds: dict[str, int] = {}
    for fragment in delivered.split("-c "):
        name, _, value = fragment.strip().partition("=")
        if value:
            bounds[name] = int(value)
    return bounds


def _effective(name: str) -> int:
    """The bound in force on this session, in milliseconds.

    Read from `pg_settings` rather than `SHOW`, which renders a unit that varies with the
    magnitude configured (`15s`, `250ms`) and would make the comparison depend on the value.
    """
    with connection.cursor() as cursor:
        cursor.execute("SELECT setting::bigint FROM pg_settings WHERE name = %s", [name])
        row = cursor.fetchone()
    assert row is not None, f"{name} is not a recognised server setting"
    return int(row[0])


@pytest.mark.parametrize("name", SESSION_BOUNDS)
def test_the_session_carries_the_configured_bound(name: str) -> None:
    assert _effective(name) == _configured()[name]


@pytest.mark.parametrize("name", SESSION_BOUNDS)
def test_no_bound_arrives_disabled(name: str) -> None:
    """`0` disables a timeout in PostgreSQL, so an arriving `0` is not an arriving bound."""
    assert _effective(name) > 0


def test_the_alias_is_pooled_at_runtime() -> None:
    """The settings assertion says a pool is declared; this says one is actually in use.

    Reached with `getattr` because `pool` is the PostgreSQL wrapper's attribute, not the base
    wrapper's — the sentinel keeps a backend that has no pool at all a failure rather than an
    `AttributeError` that reads like a broken test.
    """
    assert getattr(connection, "pool", None) is not None
