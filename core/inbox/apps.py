"""The Django application for durable message ingest and terminal state.

One app per `core` platform submodule, following `core/idempotency/apps.py`. `core.inbox` is
the one of the three that item 3 L13 **opens** to `interfaces/*`, for durable webhook ingest
(ADR-0004 §7): an inbound boundary performs durable ingest and returns, and the internal
registered message is authored later by the owning application module in the worker. Writing
an Outbox row or claiming an idempotency key stays below the transport boundary.

`label` is explicit so the app is `core_inbox` rather than the bare `inbox` Django would infer
from the last path segment, and `db_table` is explicit on each model so a future label change
can never rename a table.
"""

from __future__ import annotations

from django.apps import AppConfig

__all__ = ("CoreInboxConfig",)


class CoreInboxConfig(AppConfig):
    name = "core.inbox"
    label = "core_inbox"
    default_auto_field = "django.db.models.BigAutoField"
    verbose_name = "Inbox and terminal state"
