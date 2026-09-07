"""ADR-0016 at launch: primary only, and no machinery for a replica that is not used.

These assertions are the launch-time half of RR1/RR4/A139/A140/A141/A145 and C191. The
per-read-path admission contract (RR6-RR8) has nothing to test while the gate is closed.
"""

from __future__ import annotations

from pathlib import Path

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
