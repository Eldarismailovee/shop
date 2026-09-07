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


SECRET_KEY = _env("DJANGO_SECRET_KEY")
DEBUG = _env_bool("DJANGO_DEBUG", False)
ALLOWED_HOSTS = [h for h in _env("DJANGO_ALLOWED_HOSTS", "").split(",") if h]

# Launch modules register themselves as they acquire models. No package presence is probed
# and no `LATER` module is listed (item 14 NF8, NF10).
INSTALLED_APPS: list[str] = []

MIDDLEWARE: list[str] = []

ROOT_URLCONF = "config.urls"

# ---------------------------------------------------------------------------
# Database — primary only (ADR-0016 RR1/RR4)
#
# One application alias. There is no replica alias, no database router, no default read
# alias on a replica and no sticky-primary machinery: shipping routing for a replica that
# is not used is exactly what RR1 and item 14 NF10 forbid. An HA standby, if operations
# runs one, is a backup/failover concern and never an application read target (RR2).
# ---------------------------------------------------------------------------

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": _env("POSTGRES_DB"),
        "USER": _env("POSTGRES_USER"),
        "PASSWORD": _env("POSTGRES_PASSWORD"),
        "HOST": _env("POSTGRES_HOST", "localhost"),
        "PORT": _env("POSTGRES_PORT", "5432"),
    }
}

# Instants are aware UTC (Phase 0 item 11).
USE_TZ = True
TIME_ZONE = "UTC"
