"""C186's structural stand-in: there is no Redis to make unavailable.

ADR-0015 §2 requires that a Redis miss, flush, eviction, outage or cold start changes none of
the four answers the durable row decides. C186 tests that by running the suite with Redis
down and again with Redis flushed between attempts — but the launch build has no cache client
at all (Slice 3 §2 removed `celery` and `redis`), so there is nothing to take down.

The invariant is therefore discharged the stronger way: no such dependency exists, and A129
prevents one being reached from the claim mechanism. This test is the dependency half; the
import half is `tests/architecture/test_idempotency_rules.py`.

When a cache client is eventually added for some other purpose, this test starts failing and
C186 becomes runnable for real — which is the right moment to write it, rather than leaving a
silently-vacuous test behind now.
"""

from __future__ import annotations

import tomllib

from tests.conftest import REPO_ROOT

_CACHE_PACKAGES = {"redis", "django-redis", "hiredis", "pymemcache", "python-memcached"}


def _declared_dependencies() -> set[str]:
    manifest = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    declared = list(manifest["project"]["dependencies"])
    for group in manifest.get("dependency-groups", {}).values():
        declared.extend(entry for entry in group if isinstance(entry, str))
    return {
        entry.split("[")[0].split("=")[0].split(">")[0].split("<")[0].strip() for entry in declared
    }


def test_no_cache_dependency_exists() -> None:
    assert _CACHE_PACKAGES.isdisjoint(_declared_dependencies())


def test_no_cache_backend_is_configured() -> None:
    """An unconfigured `CACHES` is Django's locmem default; nothing durable depends on it."""
    from django.conf import settings

    assert not getattr(settings, "CACHES", {}).get("default", {}).get("LOCATION")
