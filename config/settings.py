"""Django settings for the launch build.

`config/` is the single composition root (ADR-0005, Phase 0 item 3 §7). This module maps
environment configuration to objects and holds no business logic. Runtime packages never
import it; entry points receive their dependencies from the composition root.
"""

from __future__ import annotations

import os
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent


def _env(name: str, default: str | None = None) -> str:
    """Read a required setting from the environment. No secret has a checked-in default."""
    value = os.environ.get(name, default)
    if value is None:
        raise ImproperlyConfigured(f"Missing required environment variable: {name}")
    return value


def _env_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    """Read a non-negative integer operational bound.

    Unlike a secret these carry a checked-in default on purpose: the invariant is that a
    bound is *always* set, and a deployment that forgot to configure one must inherit the
    baseline rather than silently run unbounded (item 5 LK6).
    """
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        value = int(raw)
    except ValueError:
        raise ImproperlyConfigured(f"{name} must be an integer, got {raw!r}") from None
    if value < 0:
        raise ImproperlyConfigured(f"{name} must not be negative, got {value}")
    return value


SECRET_KEY = _env("DJANGO_SECRET_KEY")
DEBUG = _env_bool("DJANGO_DEBUG", False)
ALLOWED_HOSTS = [h for h in _env("DJANGO_ALLOWED_HOSTS", "").split(",") if h]

# Launch modules register themselves as they acquire models. No package presence is probed
# and no `LATER` module is listed (item 14 NF8, NF10).
#
# One app per `core` platform submodule, so that item 3 L13 — `interfaces/*` may import
# `core.inbox` but neither `core.outbox` nor `core.idempotency` — keeps three distinct
# import surfaces to name. `core.outbox` and `core.inbox` join in their own slice.
INSTALLED_APPS: list[str] = [
    "core.idempotency",
    "core.outbox",
    "core.inbox",
]

# The transport boundary binds the chain's `request_id` into ambient observability context,
# which is where every durable Outbox record captures it from (item 10 §12, PC7). It is first
# in the list because a line logged by anything further in — including a middleware that
# rejects the request — belongs to the same chain and must carry the same identifier.
MIDDLEWARE: list[str] = [
    "interfaces.request_context.RequestContextMiddleware",
]

ROOT_URLCONF = "config.urls"

# ---------------------------------------------------------------------------
# Database — primary only (ADR-0016 RR1/RR4)
#
# One application alias. There is no replica alias, no database router, no default read
# alias on a replica and no sticky-primary machinery: shipping routing for a replica that
# is not used is exactly what RR1 and item 14 NF10 forbid. An HA standby, if operations
# runs one, is a backup/failover concern and never an application read target (RR2).
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Bounded waits and the in-process connection pool
#
# Master `# 22.6` gives the baseline and these are its numbers; every one is
# environment-overridable because pool sizing is a deployment-wide calculation across web
# workers, the relay and Celery against the server's `max_connections`, not a per-process
# constant. They are milliseconds for the three session bounds and seconds for the two
# connection ones, matching PostgreSQL's and libpq's own units rather than inventing a
# uniform one that every reader would then have to convert back.
#
# Item 5 LK6 requires that lock and statement timeouts are *configured* and that exceeding
# one is a technical fault. Master `# 22.6` calls that outcome a "retryable business error";
# item 5 §11.6 refines it — a bounded wait exceeded is a technical fault propagating
# untranslated (item 4 §13.5), never a business outcome — and the frozen artifact governs.
#
# This is psycopg's in-process pool. PgBouncer remains a closed infrastructure gate
# (item 14 §22 case 12): the pool is FOUNDATION, the external pooler is not.
# ---------------------------------------------------------------------------

_CONNECT_TIMEOUT_SECONDS = _env_int("POSTGRES_CONNECT_TIMEOUT_SECONDS", 5)
_STATEMENT_TIMEOUT_MS = _env_int("POSTGRES_STATEMENT_TIMEOUT_MS", 15_000)
_LOCK_TIMEOUT_MS = _env_int("POSTGRES_LOCK_TIMEOUT_MS", 3_000)
_IDLE_IN_TRANSACTION_TIMEOUT_MS = _env_int("POSTGRES_IDLE_IN_TRANSACTION_TIMEOUT_MS", 30_000)
_POOL_MIN_SIZE = _env_int("POSTGRES_POOL_MIN_SIZE", 2)
_POOL_MAX_SIZE = _env_int("POSTGRES_POOL_MAX_SIZE", 10)
_POOL_WAIT_TIMEOUT_SECONDS = _env_int("POSTGRES_POOL_WAIT_TIMEOUT_SECONDS", 5)

# Delivered as libpq connection options, so every connection carries them from the moment it
# opens — including a pooled connection handed to a worker that never runs a `SET` of its own.
# A session bound applied by application code after connecting would be one `SET` away from
# being absent, which is the state this line exists to make impossible.
_SESSION_BOUNDS = (
    f"-c statement_timeout={_STATEMENT_TIMEOUT_MS}"
    f" -c lock_timeout={_LOCK_TIMEOUT_MS}"
    f" -c idle_in_transaction_session_timeout={_IDLE_IN_TRANSACTION_TIMEOUT_MS}"
)

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": _env("POSTGRES_DB"),
        "USER": _env("POSTGRES_USER"),
        "PASSWORD": _env("POSTGRES_PASSWORD"),
        "HOST": _env("POSTGRES_HOST", "localhost"),
        "PORT": _env("POSTGRES_PORT", "5432"),
        # The pool owns connection lifetime, and the psycopg backend refuses to combine it
        # with persistent connections. Stated explicitly rather than left to the default, so
        # that raising it later fails loudly instead of quietly disabling pooling.
        "CONN_MAX_AGE": 0,
        # Makes the pool hand out a checked connection: a socket the server closed underneath
        # an idle pooled connection would otherwise surface as a spurious technical fault on
        # whichever request happened to receive it.
        "CONN_HEALTH_CHECKS": True,
        "OPTIONS": {
            "connect_timeout": _CONNECT_TIMEOUT_SECONDS,
            "options": _SESSION_BOUNDS,
            "pool": {
                "min_size": _POOL_MIN_SIZE,
                "max_size": _POOL_MAX_SIZE,
                # How long a caller waits for a free pooled connection before failing. It is
                # a bounded wait like the others: a saturated pool must surface, not queue.
                "timeout": _POOL_WAIT_TIMEOUT_SECONDS,
            },
        },
    }
}

# Instants are aware UTC (Phase 0 item 11).
USE_TZ = True
TIME_ZONE = "UTC"

# ---------------------------------------------------------------------------
# Observability (master `# 23.1`, Phase 0 item 10)
# ---------------------------------------------------------------------------

# Item 10 RQ8/PV6: a client-supplied request identifier is untrusted input, adoptable only
# where the deployment's trust policy permits — behind the platform's own reverse proxy, which
# is where master `# 23.1` mints it. It defaults to off, so a deployment that has not decided
# does not silently let a public endpoint colour internal correlation. Both settings are
# reachable and both do something; neither gates unreachable code (item 14 NF10).
OBSERVABILITY_TRUST_EDGE_REQUEST_ID = _env_bool("OBSERVABILITY_TRUST_EDGE_REQUEST_ID", False)

# Structured JSON on stdout, for a collector to ship. The context filter is installed on the
# handler rather than on a logger, so records from Django, the database backend and every
# third-party library carry the chain's identifiers too — not only records from this codebase.
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "filters": {
        "observability_context": {"()": "core.observability.logging.ContextFilter"},
    },
    "formatters": {
        "json": {"()": "core.observability.logging.JsonFormatter"},
    },
    "handlers": {
        "stdout": {
            "class": "logging.StreamHandler",
            "filters": ["observability_context"],
            "formatter": "json",
        },
    },
    "root": {
        "handlers": ["stdout"],
        "level": _env("DJANGO_LOG_LEVEL", "INFO"),
    },
    "loggers": {
        # The security-event stream is named separately so a deployment can route it to its
        # own sink and alerting policy without matching on line content. It shares the handler
        # today because no second sink exists; `propagate` is off so that naming one later
        # changes where these lines go and nothing else.
        "security": {
            "handlers": ["stdout"],
            "level": "INFO",
            "propagate": False,
        },
    },
}
