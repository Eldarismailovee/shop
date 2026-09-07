"""The integration tier: everything here needs a live PostgreSQL.

Item 3 A7 splits the suite by tier. The unit tier contacts no database, so `make test` — and
any CI job that calls it — keeps working with no PostgreSQL at all. This tier proves what
only real PostgreSQL can: two connections racing on a unique constraint, a `CHECK` refusing
a direct insert, a row lock serialising a reclaim. Marking is automatic, so a new file here
cannot accidentally join the database-free tier.

Run it with `make test-db`, having exported `POSTGRES_DB`, `POSTGRES_USER`,
`POSTGRES_PASSWORD` and, if they are not the defaults, `POSTGRES_HOST` / `POSTGRES_PORT`.
The role needs `CREATEDB`, because the test database is created and dropped per run.
"""

from __future__ import annotations

from pathlib import Path

import pytest

_TIER_ROOT = Path(__file__).resolve().parent


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    """Mark this tier's items, and only this tier's.

    A non-root `conftest` hook still receives **every** collected item, so the path guard is
    load-bearing: without it this marks the whole suite as needing PostgreSQL, and `make
    test` silently stops being the database-free tier it exists to be.
    """
    for item in items:
        if _TIER_ROOT in Path(str(item.path)).parents:
            item.add_marker(pytest.mark.integration)
