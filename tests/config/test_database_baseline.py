"""The application's one database alias: primary only, pooled, and bounded.

Two frozen obligations meet on the same settings dict:

* **ADR-0016 at launch** — primary only, and no machinery for a replica that is not used.
  These are the launch-time half of RR1/RR4/A139/A140/A141/A145 and C191; the per-read-path
  admission contract (RR6-RR8) has nothing to test while the gate is closed.
* **Item 5 §20.3 LK6** — lock and statement timeouts *are configured*. That half is a
  property of the composition root, so it is asserted here. That the bounds actually reach
  PostgreSQL is `tests/integration/core/test_bounded_waits.py`; that exceeding one is a
  technical fault rather than a business outcome is
  `tests/integration/core/idempotency/test_bounded_lock_wait.py`; and rule LK6 enforces both
  statically.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from django.conf import settings

from tests.conftest import REPO_ROOT

SOURCE_FAMILIES = (
    "core",
    "domains",
    "application",
    "interfaces",
    "integrations",
    "tasks",
    "config",
)


def _production_sources() -> list[Path]:
    return [
        path
        for family in SOURCE_FAMILIES
        for path in (REPO_ROOT / family).rglob("*.py")
        if (REPO_ROOT / family).is_dir()
    ]


def test_exactly_one_application_database_alias() -> None:
    assert list(settings.DATABASES) == ["default"]


def test_the_application_alias_is_postgresql() -> None:
    assert settings.DATABASES["default"]["ENGINE"] == "django.db.backends.postgresql"


def test_no_database_router_is_installed() -> None:
    """RR4 — a global verb-based router is forbidden permanently, not only at launch."""
    assert settings.DATABASE_ROUTERS == []


def test_no_replica_alias_appears_in_the_launch_source() -> None:
    """RR1/A141 — no `using(...)`/`db_manager(...)` can name a replica that does not exist."""
    needles = ("replica", "follower", "standby", "database_routers")
    offenders = []
    for path in _production_sources():
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            code = line.split("#", 1)[0].lower()  # the rule is about code, not about prose
            for needle in needles:
                if needle in code:
                    offenders.append(f"{path.relative_to(REPO_ROOT).as_posix()}:{number}: {needle}")
    assert offenders == []


def test_no_secret_has_a_checked_in_default() -> None:
    source = (REPO_ROOT / "config" / "settings.py").read_text(encoding="utf-8")
    for required in ("DJANGO_SECRET_KEY", "POSTGRES_PASSWORD"):
        assert f'_env("{required}")' in source, f"{required} must have no default"


def _options() -> dict[str, Any]:
    options = settings.DATABASES["default"]["OPTIONS"]
    assert isinstance(options, dict)
    return options


class TestBoundedWaits:
    """LK6's first half: every wait the application can make is bounded by configuration."""

    def test_the_three_session_bounds_are_delivered_as_connection_options(self) -> None:
        """As libpq options, so a connection carries them before it runs any statement.

        Asserted as the wire-level string rather than as a Python constant: a bound named in
        a settings variable that never reaches `OPTIONS` is the failure this pins.
        """
        delivered = _options()["options"]
        assert isinstance(delivered, str)
        for bound in ("statement_timeout", "lock_timeout", "idle_in_transaction_session_timeout"):
            assert f"-c {bound}=" in delivered, f"{bound} is not delivered to the connection"

    def test_every_session_bound_is_a_positive_number_of_milliseconds(self) -> None:
        """`0` disables a bound in PostgreSQL, so a configured `0` is not a configured bound."""
        delivered = _options()["options"]
        assert isinstance(delivered, str)
        for fragment in delivered.split("-c "):
            if "=" not in fragment:
                continue
            name, _, value = fragment.strip().partition("=")
            assert int(value) > 0, f"{name} is set to {value}, which disables it"

    def test_the_connection_attempt_itself_is_bounded(self) -> None:
        connect_timeout = _options()["connect_timeout"]
        assert isinstance(connect_timeout, int) and connect_timeout > 0


class TestTheConnectionPool:
    """Master `# 22.6`'s in-process pool — FOUNDATION, and not an external pooler."""

    def test_the_alias_is_pooled(self) -> None:
        pool = _options()["pool"]
        assert isinstance(pool, dict)
        assert 0 < pool["min_size"] <= pool["max_size"]

    def test_waiting_for_a_free_connection_is_bounded_too(self) -> None:
        """A saturated pool must surface as a fault, not queue callers indefinitely."""
        pool = _options()["pool"]
        assert isinstance(pool, dict)
        assert pool["timeout"] > 0

    def test_persistent_connections_are_off_because_the_pool_owns_lifetime(self) -> None:
        """The psycopg backend refuses to combine the two; stating it keeps the refusal loud."""
        assert settings.DATABASES["default"]["CONN_MAX_AGE"] == 0

    def test_a_pooled_connection_is_checked_before_it_is_handed_out(self) -> None:
        assert settings.DATABASES["default"]["CONN_HEALTH_CHECKS"] is True

    def test_no_external_pooler_is_assumed(self) -> None:
        """Item 14 §22 case 12: the in-process pool is FOUNDATION, PgBouncer is a closed gate."""
        source = (REPO_ROOT / "config" / "settings.py").read_text(encoding="utf-8")
        for number, line in enumerate(source.splitlines(), start=1):
            code = line.split("#", 1)[0].lower()  # the rule is about code, not about prose
            assert "pgbouncer" not in code, (
                f"config/settings.py:{number} assumes an external pooler"
            )
