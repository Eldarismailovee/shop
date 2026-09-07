"""The security-event log (ADR-0015 §4, item 5 AU6)."""

from __future__ import annotations

import logging
from typing import Any

import pytest

from core.observability.security_events import (
    SECURITY_LOGGER_NAME,
    SecurityEvent,
    SecurityEventCode,
    record_security_event,
)


def context_of(record: logging.LogRecord) -> dict[str, Any]:
    """The structured fields the record carries, as the formatter sees them."""
    return record.__dict__


class TestVocabulary:
    def test_the_code_set_is_closed_and_holds_exactly_what_has_a_subject(self) -> None:
        """One member per refusal that exists. A code with no emitter is a promise, not a log."""
        assert {code.value for code in SecurityEventCode} == {"idempotency_key_ownership_refused"}

    def test_a_free_text_code_is_refused(self) -> None:
        with pytest.raises(TypeError, match="closed"):
            SecurityEvent(code="somebody did something suspicious")  # type: ignore[arg-type]

    @pytest.mark.parametrize(
        "subject",
        ["a key value", "Scope.Name", "", "x" * 65, "полезная нагрузка"],
    )
    def test_an_unbounded_or_unshaped_subject_is_refused(self, subject: str) -> None:
        with pytest.raises(ValueError, match="bounded"):
            SecurityEvent(code=SecurityEventCode.IDEMPOTENCY_KEY_OWNERSHIP_REFUSED, subject=subject)

    def test_a_platform_scope_name_is_an_acceptable_subject(self) -> None:
        event = SecurityEvent(
            code=SecurityEventCode.IDEMPOTENCY_KEY_OWNERSHIP_REFUSED,
            subject="fixture.do_thing",
        )
        assert event.subject == "fixture.do_thing"

    def test_a_principal_locator_is_an_acceptable_reference(self) -> None:
        event = SecurityEvent(
            code=SecurityEventCode.IDEMPOTENCY_KEY_OWNERSHIP_REFUSED,
            principal_kind="actor",
            principal_id="6f1b1f4e-9c33-7b0a-8e2d-1a2b3c4d5e6f",
        )
        assert event.principal_kind == "actor"

    def test_an_over_long_principal_reference_is_refused(self) -> None:
        with pytest.raises(ValueError, match="bounded"):
            SecurityEvent(
                code=SecurityEventCode.IDEMPOTENCY_KEY_OWNERSHIP_REFUSED,
                principal_id="a" * 65,
            )

    def test_the_event_is_immutable(self) -> None:
        event = SecurityEvent(code=SecurityEventCode.IDEMPOTENCY_KEY_OWNERSHIP_REFUSED)
        with pytest.raises(AttributeError):
            event.subject = "elsewhere"  # type: ignore[misc]


class TestRecording:
    def test_the_line_goes_to_the_dedicated_logger_at_warning(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        with caplog.at_level(logging.INFO, logger=SECURITY_LOGGER_NAME):
            record_security_event(
                SecurityEvent(
                    code=SecurityEventCode.IDEMPOTENCY_KEY_OWNERSHIP_REFUSED,
                    subject="fixture.do_thing",
                )
            )
        (record,) = caplog.records
        assert record.name == SECURITY_LOGGER_NAME
        assert record.levelno == logging.WARNING

    def test_the_message_is_the_code_and_carries_no_interpolated_detail(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        with caplog.at_level(logging.INFO, logger=SECURITY_LOGGER_NAME):
            record_security_event(
                SecurityEvent(
                    code=SecurityEventCode.IDEMPOTENCY_KEY_OWNERSHIP_REFUSED,
                    subject="fixture.do_thing",
                )
            )
        (record,) = caplog.records
        assert record.getMessage() == "idempotency_key_ownership_refused"

    def test_the_structured_fields_are_present(self, caplog: pytest.LogCaptureFixture) -> None:
        with caplog.at_level(logging.INFO, logger=SECURITY_LOGGER_NAME):
            record_security_event(
                SecurityEvent(
                    code=SecurityEventCode.IDEMPOTENCY_KEY_OWNERSHIP_REFUSED,
                    subject="fixture.do_thing",
                    principal_kind="actor",
                    principal_id="6f1b1f4e-9c33-7b0a-8e2d-1a2b3c4d5e6f",
                )
            )
        (record,) = caplog.records
        assert context_of(record)["security_event"] == "idempotency_key_ownership_refused"
        assert context_of(record)["security_subject"] == "fixture.do_thing"
        assert context_of(record)["principal_kind"] == "actor"
        assert context_of(record)["principal_id"] == "6f1b1f4e-9c33-7b0a-8e2d-1a2b3c4d5e6f"

    def test_an_absent_field_is_omitted_rather_than_recorded_as_none(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        with caplog.at_level(logging.INFO, logger=SECURITY_LOGGER_NAME):
            record_security_event(
                SecurityEvent(
                    code=SecurityEventCode.IDEMPOTENCY_KEY_OWNERSHIP_REFUSED,
                    principal_kind="system",
                    principal_purpose="reconciliation",
                )
            )
        (record,) = caplog.records
        assert "principal_id" not in context_of(record)
        assert context_of(record)["principal_purpose"] == "reconciliation"

    def test_only_a_security_event_may_be_recorded(self) -> None:
        with pytest.raises(TypeError, match="SecurityEvent"):
            record_security_event("ownership refused")  # type: ignore[arg-type]
