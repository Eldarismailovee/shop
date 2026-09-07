"""Django settings for the test run.

`config.settings` deliberately has no checked-in default for any secret, so the suite
supplies throwaway local values and then re-exports the real settings unchanged. Nothing
is overridden here: a divergence between test and launch configuration would make the
ADR-0016 assertions meaningless.
"""

from __future__ import annotations

import os

os.environ.setdefault("DJANGO_SECRET_KEY", "test-only-not-a-secret")
os.environ.setdefault("POSTGRES_DB", "store_test")
os.environ.setdefault("POSTGRES_USER", "store_test")
os.environ.setdefault("POSTGRES_PASSWORD", "test-only-not-a-secret")

from config.settings import *  # noqa: E402, F403
