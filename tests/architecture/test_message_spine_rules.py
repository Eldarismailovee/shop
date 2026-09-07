"""A56 / A60 / A61 / A62 / A66 — fixture-level regression tests for the async spine rules.

Each case materialises a throwaway tree that deliberately breaks one rule, so the harness is
proven to *catch* the violation rather than merely to pass over compliant code. The real source
tree's cleanliness is asserted separately, by
`test_repository_layout.test_the_source_tree_satisfies_every_static_rule`.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from pathlib import Path

import pytest

MODEL_HEADER = "from django.db import models\n\n\n"


def _model(fields: str, name: str = "OutboxMessage") -> str:
    return f"{MODEL_HEADER}class {name}(models.Model):\n{fields}"


class TestA60TheTceIsClosed:
    """Item 8 reserved one extension point and item 10 spent it; there is no second."""

    @pytest.mark.parametrize(
        "column",
        ["meta", "metadata", "extra", "context", "attributes", "headers", "tags", "baggage"],
    )
    def test_a_metadata_bag_beside_the_envelope_is_caught(
        self, tmp_path: Path, arch_rules: Callable[[Path, Mapping[str, str]], set[str]], column: str
    ) -> None:
        assert "A60" in arch_rules(
            tmp_path,
            {
                "core/outbox/models.py": _model(
                    f"    trace_id = models.CharField(max_length=32, null=True)\n"
                    f"    {column} = models.JSONField(null=True)\n"
                )
            },
        )

    @pytest.mark.parametrize("column", ["span_id", "correlation_id", "parent_span_id"])
    def test_a_fifth_trace_field_is_caught(
        self, tmp_path: Path, arch_rules: Callable[[Path, Mapping[str, str]], set[str]], column: str
    ) -> None:
        assert "A60" in arch_rules(
            tmp_path,
            {"core/inbox/models.py": _model(f"    {column} = models.CharField(max_length=32)\n")},
        )

    def test_the_four_slots_themselves_are_not_flagged(
        self, tmp_path: Path, arch_rules: Callable[[Path, Mapping[str, str]], set[str]]
    ) -> None:
        assert "A60" not in arch_rules(
            tmp_path,
            {
                "core/outbox/models.py": _model(
                    "    trace_id = models.CharField(max_length=32, null=True)\n"
                    "    producer_span_id = models.CharField(max_length=16, null=True)\n"
                    "    request_id = models.CharField(max_length=128, null=True)\n"
                    "    causation_event_id = models.UUIDField(null=True)\n"
                )
            },
        )

    def test_the_deliverys_own_processing_pair_is_not_a_fifth_field(
        self, tmp_path: Path, arch_rules: Callable[[Path, Mapping[str, str]], set[str]]
    ) -> None:
        """CN8 requires exactly that separate pair; A60 must not mistake it for a bag."""
        assert "A60" not in arch_rules(
            tmp_path,
            {
                "core/inbox/models.py": _model(
                    "    processing_trace_id = models.CharField(max_length=32, null=True)\n"
                    "    processing_span_id = models.CharField(max_length=16, null=True)\n",
                    name="InboxDelivery",
                )
            },
        )


class TestA62OneWriterPerTraceColumn:
    @pytest.mark.parametrize(
        "column", ["trace_id", "producer_span_id", "request_id", "causation_event_id"]
    )
    def test_an_update_assigning_a_tce_column_is_caught(
        self, tmp_path: Path, arch_rules: Callable[[Path, Mapping[str, str]], set[str]], column: str
    ) -> None:
        assert "A62" in arch_rules(
            tmp_path,
            {
                "core/inbox/delivery.py": (
                    "from core.inbox.models import InboxDelivery\n\n\n"
                    "def backfill(row_id, value):\n"
                    f"    InboxDelivery.objects.filter(pk=row_id).update({column}=value)\n"
                )
            },
        )

    def test_an_attribute_assignment_on_a_loaded_row_is_caught(
        self, tmp_path: Path, arch_rules: Callable[[Path, Mapping[str, str]], set[str]]
    ) -> None:
        assert "A62" in arch_rules(
            tmp_path,
            {
                "core/outbox/relay.py": (
                    "def repair(row, value):\n    row.producer_span_id = value\n    row.save()\n"
                )
            },
        )

    def test_writing_the_deliverys_own_processing_trace_is_permitted(
        self, tmp_path: Path, arch_rules: Callable[[Path, Mapping[str, str]], set[str]]
    ) -> None:
        assert "A62" not in arch_rules(
            tmp_path,
            {
                "core/inbox/delivery.py": (
                    "from core.inbox.models import InboxDelivery\n\n\n"
                    "def attempt(row_id, trace, span):\n"
                    "    InboxDelivery.objects.filter(pk=row_id).update(\n"
                    "        processing_trace_id=trace, processing_span_id=span\n"
                    "    )\n"
                )
            },
        )

    def test_a_migration_is_not_the_subject(
        self, tmp_path: Path, arch_rules: Callable[[Path, Mapping[str, str]], set[str]]
    ) -> None:
        """A schema migration adding the columns is not a runtime writer."""
        assert "A62" not in arch_rules(
            tmp_path,
            {
                "core/outbox/migrations/0002_x.py": (
                    "from django.db import migrations\n\n\n"
                    "def forwards(apps, schema_editor):\n"
                    "    apps.get_model('core_outbox', 'OutboxMessage').objects.update("
                    "trace_id=None)\n"
                )
            },
        )


class TestA66MessageFieldsAreWriteOnce:
    @pytest.mark.parametrize(
        "column", ["event_id", "event_type", "schema_version", "occurred_at", "payload"]
    )
    def test_an_update_rewriting_durable_identity_is_caught(
        self, tmp_path: Path, arch_rules: Callable[[Path, Mapping[str, str]], set[str]], column: str
    ) -> None:
        assert "A66" in arch_rules(
            tmp_path,
            {
                "core/outbox/relay.py": (
                    "from core.outbox.models import OutboxMessage\n\n\n"
                    "def amend(row_id, value):\n"
                    f"    OutboxMessage.objects.filter(pk=row_id).update({column}=value)\n"
                )
            },
        )

    def test_updating_mutable_relay_state_is_permitted(
        self, tmp_path: Path, arch_rules: Callable[[Path, Mapping[str, str]], set[str]]
    ) -> None:
        assert "A66" not in arch_rules(
            tmp_path,
            {
                "core/outbox/relay.py": (
                    "from core.outbox.models import OutboxMessage\n\n\n"
                    "def dispatch(row_id, when):\n"
                    "    OutboxMessage.objects.filter(pk=row_id).update(\n"
                    "        relay_state='RELAYED', relayed_at=when, relay_attempts=1\n"
                    "    )\n"
                )
            },
        )


class TestA56TerminalRecordsAreDomainScoped:
    @pytest.mark.parametrize("missing", ["terminal_kind", "failure_domain", "consumer"])
    def test_a_terminal_record_missing_a_discriminator_is_caught(
        self,
        tmp_path: Path,
        arch_rules: Callable[[Path, Mapping[str, str]], set[str]],
        missing: str,
    ) -> None:
        columns = {
            "terminal_kind": "    terminal_kind = models.CharField(max_length=16)\n",
            "failure_domain": "    failure_domain = models.CharField(max_length=64)\n",
            "consumer": "    consumer = models.CharField(max_length=128)\n",
        }
        body = "".join(source for name, source in columns.items() if name != missing)
        assert "A56" in arch_rules(
            tmp_path, {"core/inbox/models.py": _model(body, name="MessageTerminal")}
        )

    def test_a_complete_terminal_record_passes(
        self, tmp_path: Path, arch_rules: Callable[[Path, Mapping[str, str]], set[str]]
    ) -> None:
        assert "A56" not in arch_rules(
            tmp_path,
            {
                "core/inbox/models.py": _model(
                    "    terminal_kind = models.CharField(max_length=16)\n"
                    "    failure_domain = models.CharField(max_length=64)\n"
                    "    consumer = models.CharField(max_length=128)\n",
                    name="MessageTerminal",
                )
            },
        )

    def test_a_choices_enum_named_for_the_discriminator_is_not_the_subject(
        self, tmp_path: Path, arch_rules: Callable[[Path, Mapping[str, str]], set[str]]
    ) -> None:
        """`TerminalKind` is the discriminator's vocabulary, not the record that carries it."""
        assert "A56" not in arch_rules(
            tmp_path,
            {
                "core/inbox/models.py": (
                    f"{MODEL_HEADER}class TerminalKind(models.TextChoices):\n"
                    "    QUARANTINE = 'QUARANTINE', 'q'\n"
                )
            },
        )


class TestA61ThePayloadGateStaysClosed:
    def test_narrowing_the_reserved_set_is_caught(
        self, tmp_path: Path, arch_rules: Callable[[Path, Mapping[str, str]], set[str]]
    ) -> None:
        """Deleting a name would remove the protection with nothing else failing."""
        assert "A61" in arch_rules(
            tmp_path,
            {"core/events/codec.py": "RESERVED_PAYLOAD_FIELDS = frozenset({'event_id'})\n"},
        )

    def test_a_missing_gate_is_caught(
        self, tmp_path: Path, arch_rules: Callable[[Path, Mapping[str, str]], set[str]]
    ) -> None:
        assert "A61" in arch_rules(
            tmp_path, {"core/events/codec.py": "def encode(x):\n    return x\n"}
        )

    def test_the_real_closed_set_passes(
        self, tmp_path: Path, arch_rules: Callable[[Path, Mapping[str, str]], set[str]]
    ) -> None:
        assert "A61" not in arch_rules(
            tmp_path,
            {
                "core/events/codec.py": (
                    "RESERVED_PAYLOAD_FIELDS = frozenset({\n"
                    "    'event_id', 'event_type', 'schema_version', 'occurred_at',\n"
                    "    'trace_id', 'producer_span_id', 'request_id', 'causation_event_id',\n"
                    "})\n"
                )
            },
        )


class TestTheMutationAllowlistIsExhaustive:
    """The positive complement to A62/A66, which are denylists.

    A62 and A66 name the columns that may **not** be written after creation. This asserts the
    other direction over the real source: every column the Inbox's mutation paths actually
    write is one of the five `_MUTABLE_FIELDS` declares. A denylist protects the columns
    somebody thought of; an allowlist protects the ones nobody has added yet.
    """

    def test_every_update_in_the_inbox_writes_only_declared_mutable_columns(self) -> None:
        import ast

        from core.inbox.delivery import _MUTABLE_FIELDS
        from tests.conftest import REPO_ROOT

        source = (REPO_ROOT / "core" / "inbox" / "delivery.py").read_text(encoding="utf-8")
        written: set[str] = set()
        for node in ast.walk(ast.parse(source)):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "update"
            ):
                written |= {kw.arg for kw in node.keywords if kw.arg is not None}

        assert written, "no update() call was found; the parse is not proving anything"
        assert written <= set(_MUTABLE_FIELDS), (
            f"these columns are written after first observation but are not declared mutable: "
            f"{sorted(written - set(_MUTABLE_FIELDS))}"
        )

    def test_no_immutable_column_is_declared_mutable(self) -> None:
        from core.inbox.delivery import _MUTABLE_FIELDS
        from tools.arch_check.rules import TCE_FIELDS, WRITE_ONCE_MESSAGE_FIELDS

        immutable = set(TCE_FIELDS) | set(WRITE_ONCE_MESSAGE_FIELDS)
        assert not (set(_MUTABLE_FIELDS) & immutable)
