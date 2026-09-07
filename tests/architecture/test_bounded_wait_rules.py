"""LK6 — the bounded-wait rule (item 5 §11.6, §20.3 LK6).

Each case materialises a throwaway tree that breaks exactly one half of the rule, and its
negative twin proves the rule leaves alone the legitimate shape it resembles.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from pathlib import Path

Rules = Callable[[Path, Mapping[str, str]], set[str]]


class TestTheBoundBelongsToTheCompositionRoot:
    def test_disabling_the_statement_timeout_in_sql_is_reported(
        self, tmp_path: Path, arch_rules: Rules
    ) -> None:
        violations = arch_rules(
            tmp_path,
            {
                "application/checkout/use_case.py": (
                    "def widen(cursor):\n    cursor.execute('SET statement_timeout = 0')\n"
                ),
            },
        )
        assert "LK6" in violations

    def test_a_transaction_scoped_lock_timeout_is_reported_too(
        self, tmp_path: Path, arch_rules: Rules
    ) -> None:
        """`SET LOCAL` is the subtler form: bounded to the transaction, still not this layer's."""
        violations = arch_rules(
            tmp_path,
            {
                "domains/inventory/services.py": (
                    "def reserve(cursor):\n    cursor.execute('SET LOCAL lock_timeout = 60000')\n"
                ),
            },
        )
        assert "LK6" in violations

    def test_the_rule_reaches_core_and_migrations_as_well(
        self, tmp_path: Path, arch_rules: Rules
    ) -> None:
        """A mechanism module and a migration are exactly where such a line would hide."""
        violations = arch_rules(
            tmp_path,
            {
                "core/idempotency/migrations/0002_backfill.py": (
                    "def forwards(apps, schema_editor):\n"
                    "    schema_editor.execute('SET statement_timeout = 0')\n"
                ),
            },
        )
        assert "LK6" in violations

    def test_naming_a_bound_in_connection_options_is_not_a_set(
        self, tmp_path: Path, arch_rules: Rules
    ) -> None:
        """The composition root's own libpq options are the sanctioned shape."""
        violations = arch_rules(
            tmp_path,
            {"config/settings.py": "OPTIONS = {'options': '-c statement_timeout=15000'}\n"},
        )
        assert "LK6" not in violations

    def test_an_unrelated_setting_is_left_alone(self, tmp_path: Path, arch_rules: Rules) -> None:
        violations = arch_rules(
            tmp_path,
            {"domains/orders/services.py": "SQL = 'SET LOCAL search_path = public'\n"},
        )
        assert "LK6" not in violations


class TestTheTechnicalFaultIsNotLaundered:
    def test_catching_an_operational_error_in_an_application_use_case_is_reported(
        self, tmp_path: Path, arch_rules: Rules
    ) -> None:
        violations = arch_rules(
            tmp_path,
            {
                "application/checkout/use_case.py": (
                    "from django.db import OperationalError\n"
                    "def place():\n"
                    "    try:\n"
                    "        pass\n"
                    "    except OperationalError:\n"
                    "        return 'out of stock'\n"
                ),
            },
        )
        assert "LK6" in violations

    def test_a_qualified_database_error_is_seen_too(
        self, tmp_path: Path, arch_rules: Rules
    ) -> None:
        violations = arch_rules(
            tmp_path,
            {
                "interfaces/web/views.py": (
                    "from django import db\n"
                    "def view(request):\n"
                    "    try:\n"
                    "        pass\n"
                    "    except db.DatabaseError:\n"
                    "        return None\n"
                ),
            },
        )
        assert "LK6" in violations

    def test_a_bare_except_is_reported(self, tmp_path: Path, arch_rules: Rules) -> None:
        violations = arch_rules(
            tmp_path,
            {
                "tasks/orders.py": (
                    "def run():\n    try:\n        pass\n    except:\n        return None\n"
                ),
            },
        )
        assert "LK6" in violations

    def test_an_integrity_error_at_a_savepoint_is_permitted(
        self, tmp_path: Path, arch_rules: Rules
    ) -> None:
        """Item 4 §13.4 admits it for a uniqueness invariant identified by name."""
        violations = arch_rules(
            tmp_path,
            {
                "domains/orders/services.py": (
                    "from django.db import IntegrityError\n"
                    "def create():\n"
                    "    try:\n"
                    "        pass\n"
                    "    except IntegrityError:\n"
                    "        raise\n"
                ),
            },
        )
        assert "LK6" not in violations

    def test_core_is_outside_this_half_of_the_rule(self, tmp_path: Path, arch_rules: Rules) -> None:
        """Scoped like A63: the mechanism layer is where a retry loop legitimately lives."""
        violations = arch_rules(
            tmp_path,
            {
                "core/outbox/relay.py": (
                    "from django.db import OperationalError\n"
                    "def claim():\n"
                    "    try:\n"
                    "        pass\n"
                    "    except OperationalError:\n"
                    "        return None\n"
                ),
            },
        )
        assert "LK6" not in violations

    def test_a_domain_error_is_not_a_database_fault(
        self, tmp_path: Path, arch_rules: Rules
    ) -> None:
        violations = arch_rules(
            tmp_path,
            {
                "application/checkout/use_case.py": (
                    "def place():\n"
                    "    try:\n"
                    "        pass\n"
                    "    except ValueError:\n"
                    "        return None\n"
                ),
            },
        )
        assert "LK6" not in violations
