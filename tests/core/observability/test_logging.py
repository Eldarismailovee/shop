"""Structured JSON logging (master `# 23.1`).

Records are built directly rather than through a configured handler, so each case asserts on
exactly one rendering decision. `tests/interfaces/test_request_context.py` covers the other
half — that the ambient values the filter reads are actually bound at the HTTP boundary.
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
from typing import Any

import pytest

from core.observability.context import observability_context
from core.observability.logging import MAX_LINE_BYTES, ContextFilter, JsonFormatter
from core.observability.masking import MASKED
from tests.conftest import REPO_ROOT


def make_record(**extra: Any) -> logging.LogRecord:
    record = logging.LogRecord(
        name="store.example",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="something happened",
        args=(),
        exc_info=None,
    )
    for key, value in extra.items():
        setattr(record, key, value)
    return record


def render(record: logging.LogRecord) -> dict[str, Any]:
    line: dict[str, Any] = json.loads(JsonFormatter().format(record))
    return line


class TestMandatoryShape:
    def test_every_line_is_one_json_object(self) -> None:
        text = JsonFormatter().format(make_record())
        assert "\n" not in text
        assert json.loads(text)["message"] == "something happened"

    def test_the_mandatory_keys_are_present(self) -> None:
        line = render(make_record())
        assert set(line) == {"timestamp", "level", "logger", "message"}
        assert line["level"] == "INFO"
        assert line["logger"] == "store.example"

    def test_the_timestamp_is_aware_utc(self) -> None:
        assert render(make_record())["timestamp"].endswith("+00:00")

    def test_an_exception_is_rendered_as_a_formatted_traceback(self) -> None:
        try:
            raise ValueError("boom")
        except ValueError:
            record = logging.LogRecord(
                name="store.example",
                level=logging.ERROR,
                pathname=__file__,
                lineno=1,
                msg="failed",
                args=(),
                exc_info=sys.exc_info(),
            )
        assert "ValueError: boom" in render(record)["exception"]


class TestAmbientContext:
    def test_the_filter_attaches_the_bound_identifiers(self) -> None:
        record = make_record()
        with observability_context(trace_id="a" * 32, span_id="b" * 16, request_id="req-1"):
            ContextFilter().filter(record)
        line = render(record)
        assert line["request_id"] == "req-1"
        assert line["trace_id"] == "a" * 32
        assert line["span_id"] == "b" * 16

    def test_an_absent_identifier_is_omitted_rather_than_rendered_as_a_placeholder(self) -> None:
        """PR6 — absence is a complete state; `null`/`"-"`/`"unknown"` are not values."""
        record = make_record()
        with observability_context(request_id="req-1"):
            ContextFilter().filter(record)
        line = render(record)
        assert line["request_id"] == "req-1"
        assert "trace_id" not in line
        assert "span_id" not in line

    def test_nothing_is_attached_outside_a_bound_scope(self) -> None:
        record = make_record()
        ContextFilter().filter(record)
        assert set(render(record)) == {"timestamp", "level", "logger", "message"}

    def test_a_value_set_by_the_call_site_wins_over_ambient_context(self) -> None:
        """A relay reconstructing a durable message's chain knows better than the process."""
        record = make_record(request_id="from-the-durable-row")
        with observability_context(request_id="from-this-process"):
            ContextFilter().filter(record)
        assert render(record)["request_id"] == "from-the-durable-row"

    def test_the_filter_always_admits_the_record(self) -> None:
        assert ContextFilter().filter(make_record()) is True


class TestStructuredContext:
    def test_extra_fields_are_rendered_as_structured_context(self) -> None:
        line = render(make_record(order_id=7, latency_ms=12))
        assert line["order_id"] == 7
        assert line["latency_ms"] == 12

    def test_a_sensitive_field_name_is_masked(self) -> None:
        line = render(make_record(password="hunter2", card_number="4111111111111111"))
        assert line["password"] == MASKED
        assert line["card_number"] == MASKED

    def test_masking_reaches_nested_context(self) -> None:
        line = render(make_record(provider_response={"status": "ok", "token": "abc"}))
        assert line["provider_response"] == {"status": "ok", "token": MASKED}

    def test_context_cannot_overwrite_a_mandatory_key(self) -> None:
        """An alert rule matches on `level`; a call site must not be able to rewrite it."""
        line = render(make_record(level="DEBUG", message="spoofed"))
        assert line["level"] == "INFO"
        assert line["message"] == "something happened"

    def test_an_unserializable_value_is_rendered_rather_than_losing_the_line(self) -> None:
        line = render(make_record(thing=object()))
        assert line["thing"].startswith("<object object at")

    def test_an_oversized_line_keeps_its_mandatory_fields_and_says_what_it_dropped(self) -> None:
        record = make_record(blob="x" * (MAX_LINE_BYTES * 2))
        with observability_context(request_id="req-1"):
            ContextFilter().filter(record)
        line = render(record)
        assert line["context_dropped"] is True
        assert line["request_id"] == "req-1"
        assert line["message"] == "something happened"
        assert "blob" not in line


class TestPurity:
    def test_the_package_imports_without_django_configured(self) -> None:
        """Item 3 §4.5 — `integrations/*` must be able to import this without Django.

        Run in a fresh interpreter with no `DJANGO_SETTINGS_MODULE`: importing Django's
        settings machinery inside this package would surface as `ImproperlyConfigured` the
        first time an adapter's own test constructed it, long after the import was written.
        """
        source = (
            "import core.observability.context, core.observability.logging, "
            "core.observability.masking, core.observability.request_id, "
            "core.observability.security_events; "
            "import sys; "
            "assert not [m for m in sys.modules if m.split('.')[0] == 'django'], sorted("
            "m for m in sys.modules if m.split('.')[0] == 'django')"
        )
        environment = {k: v for k, v in os.environ.items() if k != "DJANGO_SETTINGS_MODULE"}
        result = subprocess.run(
            [sys.executable, "-c", source],
            capture_output=True,
            cwd=REPO_ROOT,
            env=environment,
            text=True,
        )
        assert result.returncode == 0, result.stderr

    @pytest.mark.parametrize("value", [None, "", 0])
    def test_a_falsy_extra_is_still_rendered(self, value: object) -> None:
        """Only the ambient identifiers are omitted when absent; context is data."""
        assert render(make_record(quantity=value))["quantity"] == value
