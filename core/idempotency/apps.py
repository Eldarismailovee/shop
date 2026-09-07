"""The Django application for the command-idempotency mechanism.

**One app per `core` platform submodule**, rather than a single `core` app holding every
infrastructure table. Item 3 L13 distinguishes these submodules by name — `interfaces/*` may
import `core.inbox` for durable webhook ingest but **not** `core.outbox` and **not**
`core.idempotency`, because writing an event or claiming an idempotency key is a decision
that belongs below the transport boundary. A single `core/models.py` would collapse those
three import surfaces into one module and leave L13 with nothing to name; separate apps keep
the rule mechanically checkable and keep each mechanism's migration history independent.
`core.outbox` and `core.inbox` follow the same shape in their own slice.

`label` is explicit so the app is `core_idempotency` rather than the bare `idempotency`
Django would infer from the last path segment, and `db_table` is explicit on the model so a
future label change can never rename a table.
"""

from __future__ import annotations

from django.apps import AppConfig

__all__ = ("CoreIdempotencyConfig",)


class CoreIdempotencyConfig(AppConfig):
    name = "core.idempotency"
    label = "core_idempotency"
    default_auto_field = "django.db.models.BigAutoField"
    verbose_name = "Command idempotency"
