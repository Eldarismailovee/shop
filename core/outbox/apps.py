"""The Django application for the durable Outbox.

**One app per `core` platform submodule**, following the precedent
`core/idempotency/apps.py` set and for the same reason: item 3 L13 distinguishes these
submodules by name — `interfaces/*` may import `core.inbox` for durable webhook ingest but
**not** `core.outbox` and **not** `core.idempotency`. A single `core/models.py` would collapse
those import surfaces into one module and leave L13 with nothing to name; separate apps keep
the rule mechanically checkable and keep each mechanism's migration history independent.

`label` is explicit so the app is `core_outbox` rather than the bare `outbox` Django would
infer from the last path segment, and `db_table` is explicit on the model so a future label
change can never rename a table.
"""

from __future__ import annotations

from django.apps import AppConfig

__all__ = ("CoreOutboxConfig",)


class CoreOutboxConfig(AppConfig):
    name = "core.outbox"
    label = "core_outbox"
    default_auto_field = "django.db.models.BigAutoField"
    verbose_name = "Outbox"
