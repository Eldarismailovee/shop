"""Structured JSON logging (master `# 23.1`).

The platform emits **no unstructured text logs**. Every component — the Django process, a
Celery worker, the Outbox relay — writes one JSON object per line, so that aggregation,
correlation and alerting are queries rather than regular expressions.

Two pieces, deliberately separate:

* `ContextFilter` attaches the ambient correlation identifiers to every record, wherever the
  record came from. It is a filter rather than formatter code because Django, the database
  backend and every third-party library log through loggers this module never sees; a filter
  installed on the handler reaches all of them, while a formatter that read context would only
  serve records the formatter happens to render.
* `JsonFormatter` renders the record, masking sensitive field names on the way out.

### The mandatory context

Master `# 23.1` requires `request_id` on every line, plus the transactional markers and
metrics a call site supplies through `extra=`. `trace_id` and `span_id` join it when the
process is traced. All three are **omitted when absent** rather than rendered as `null`,
`"-"` or `"unknown"`: absence is a complete state (PR6), and a placeholder is a value someone
will eventually group by.

### The correctness firewall

Nothing here decides anything. Reading a correlation identifier to *render* it is not
branching on it: no authorization check, policy, selector, idempotency key, ordering
expression or routing decision may read one (FW1, FW4, A63), and a logging failure, a
sampling decision or an unreachable collector never changes a business outcome (FW8, SM2).

This module holds **no Django import and performs no network I/O** (PC2, A65). It is on
`integrations/*`'s narrow `core` allowlist, which requires it to be importable without the
Django app registry, and it runs between `BEGIN` and `COMMIT` of business transactions, where
a collector call or an exporter flush has no business being.
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from typing import Any

from core.observability.context import current_request_id, current_span_id, current_trace_id
from core.observability.masking import masked

__all__ = ("ContextFilter", "JsonFormatter")

#: The ambient identifiers every line carries when the chain has them (master `# 23.1`).
_CONTEXT_ATTRS = ("request_id", "trace_id", "span_id")

#: The keys this formatter owns. An `extra=` entry may not overwrite one — a call site that
#: passed `level=` would otherwise silently rewrite the severity an alert rule matches on.
_RESERVED_OUTPUT = frozenset(
    {"timestamp", "level", "logger", "message", "exception", *_CONTEXT_ATTRS}
)

#: Attributes the stdlib puts on every `LogRecord`. Everything else in `record.__dict__` was
#: put there by a call site through `extra=`, and is rendered as structured context.
_STANDARD_RECORD_ATTRS = frozenset(
    {
        "args",
        "asctime",
        "created",
        "exc_info",
        "exc_text",
        "filename",
        "funcName",
        "levelname",
        "levelno",
        "lineno",
        "message",
        "module",
        "msecs",
        "msg",
        "name",
        "pathname",
        "process",
        "processName",
        "relativeCreated",
        "stack_info",
        "stacklevel",
        "taskName",
        "thread",
        "threadName",
    }
)

#: A single log line is bounded. Past this, structured context is dropped and the line says
#: so: an unbounded line is how one oversized payload takes out a log pipeline.
MAX_LINE_BYTES = 16384

#: How much of an unserializable object's `repr` is kept.
_MAX_REPR = 200


class ContextFilter(logging.Filter):
    """Attach the ambient `request_id` / `trace_id` / `span_id` to a record.

    A value already set by the call site wins: a relay or a worker that is reconstructing the
    context of a *durable message* knows more about which chain the line belongs to than the
    ambient process context does, and this filter must not overwrite it.

    Reading a `ContextVar` is the whole mechanism — no I/O, nothing that can be slow or fail,
    and correct under concurrency because the variables are per-task.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        for attribute, source in (
            ("request_id", current_request_id),
            ("trace_id", current_trace_id),
            ("span_id", current_span_id),
        ):
            if getattr(record, attribute, None) is None:
                value = source()
                if value is not None:
                    setattr(record, attribute, value)
        return True


class JsonFormatter(logging.Formatter):
    """Render one record as a single-line JSON object, with sensitive names masked."""

    def format(self, record: logging.LogRecord) -> str:
        line: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for attribute in _CONTEXT_ATTRS:
            value = getattr(record, attribute, None)
            if value is not None:
                line[attribute] = value
        if record.exc_info is not None:
            line["exception"] = self.formatException(record.exc_info)

        context = {
            key: value
            for key, value in record.__dict__.items()
            if key not in _STANDARD_RECORD_ATTRS and key not in _RESERVED_OUTPUT
        }
        if context:
            line.update(masked(context))
        return _dump(line)


def _dump(line: dict[str, Any]) -> str:
    text = json.dumps(line, default=_unserializable, ensure_ascii=False, separators=(",", ":"))
    if len(text.encode("utf-8")) <= MAX_LINE_BYTES:
        return text
    # The line is too large for the structured context it was given. The mandatory fields —
    # the ones alerting and correlation depend on — are kept and the rest is dropped, so an
    # oversized diagnostic degrades to a usable line instead of to a lost one.
    bounded = {key: value for key, value in line.items() if key in _RESERVED_OUTPUT}
    bounded["context_dropped"] = True
    return json.dumps(bounded, default=_unserializable, ensure_ascii=False, separators=(",", ":"))


def _unserializable(value: object) -> str:
    """Render whatever JSON cannot, bounded, instead of failing the record.

    A formatter that raises loses the log line — most often exactly when something has already
    gone wrong. Masking has already run over the field *names*; this is the last resort for a
    value whose type `json` does not know.
    """
    return repr(value)[:_MAX_REPR]
