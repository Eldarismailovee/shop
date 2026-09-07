"""The observability enforcement rules (item 3 §4.5, item 10 A63/A65, master `# 23.1`).

Each case materialises a throwaway tree that breaks exactly one rule, and its negative twin
proves the rule does not fire on the legitimate shape it resembles — a rule that only ever
says "no" is indistinguishable from a rule that is broken.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from pathlib import Path

Rules = Callable[[Path, Mapping[str, str]], set[str]]


class TestL10CoreOpenToIntegrationsIsPurePython:
    def test_a_django_import_in_the_integrations_visible_subset_is_reported(
        self, tmp_path: Path, arch_rules: Rules
    ) -> None:
        violations = arch_rules(
            tmp_path,
            {
                "core/observability/logging.py": "from django.conf import settings\n",
            },
        )
        assert "L10" in violations

    def test_the_rest_of_core_may_use_django_freely(
        self, tmp_path: Path, arch_rules: Rules
    ) -> None:
        """`core.outbox` is Django-backed platform state and is closed to adapters anyway."""
        violations = arch_rules(
            tmp_path,
            {"core/outbox/models.py": "from django.db import models\n"},
        )
        assert "L10" not in violations

    def test_a_stdlib_import_in_the_subset_is_fine(self, tmp_path: Path, arch_rules: Rules) -> None:
        violations = arch_rules(tmp_path, {"core/observability/masking.py": "import re\n"})
        assert "L10" not in violations


class TestA65NoNetworkIoOnTheEmissionPath:
    def test_a_collector_client_in_the_observability_package_is_reported(
        self, tmp_path: Path, arch_rules: Rules
    ) -> None:
        violations = arch_rules(
            tmp_path,
            {"core/observability/exporter.py": "import httpx\n"},
        )
        assert "A65" in violations

    def test_a_broker_client_on_the_emission_path_is_reported(
        self, tmp_path: Path, arch_rules: Rules
    ) -> None:
        """Direct producer-to-broker publishing, caught as the network import it needs."""
        violations = arch_rules(tmp_path, {"core/outbox/emit.py": "import kombu\n"})
        assert "A65" in violations

    def test_the_same_import_elsewhere_is_not_this_rule(
        self, tmp_path: Path, arch_rules: Rules
    ) -> None:
        violations = arch_rules(
            tmp_path, {"integrations/maib/outbound/client.py": "import httpx\n"}
        )
        assert "A65" not in violations


class TestA63NoBusinessBranchOnTraceMetadata:
    def test_a_conditional_on_an_ambient_trace_reader_is_reported(
        self, tmp_path: Path, arch_rules: Rules
    ) -> None:
        violations = arch_rules(
            tmp_path,
            {
                "application/checkout/use_case.py": (
                    "from core.observability.context import current_request_id\n"
                    "def run():\n"
                    "    if current_request_id():\n"
                    "        return 1\n"
                    "    return 2\n"
                )
            },
        )
        assert "A63" in violations

    def test_a_branch_on_a_value_bound_from_a_reader_is_reported(
        self, tmp_path: Path, arch_rules: Rules
    ) -> None:
        """Assigning it to a local first is the obvious way around a shallower rule."""
        violations = arch_rules(
            tmp_path,
            {
                "domains/orders/service.py": (
                    "from core.observability.context import current_trace_id\n"
                    "def run():\n"
                    "    trace = current_trace_id()\n"
                    "    return 1 if trace is not None else 2\n"
                )
            },
        )
        assert "A63" in violations

    def test_a_policy_comparing_a_durable_trace_column_is_reported(
        self, tmp_path: Path, arch_rules: Rules
    ) -> None:
        violations = arch_rules(
            tmp_path,
            {
                "tasks/handlers.py": (
                    "def allowed(message, actor):\n    return message.request_id == actor.session\n"
                )
            },
        )
        assert "A63" in violations

    def test_passing_a_trace_value_to_a_logger_is_not_a_branch(
        self, tmp_path: Path, arch_rules: Rules
    ) -> None:
        violations = arch_rules(
            tmp_path,
            {
                "interfaces/web/views.py": (
                    "import logging\n"
                    "from core.observability.context import current_request_id\n"
                    "def view(request):\n"
                    "    logging.getLogger(__name__).info('served')\n"
                    "    return current_request_id()\n"
                )
            },
        )
        assert "A63" not in violations

    def test_the_pair_integrity_check_in_core_is_not_this_rule(
        self, tmp_path: Path, arch_rules: Rules
    ) -> None:
        """PR2's defect signal legitimately compares the two halves — in `core`, at capture."""
        violations = arch_rules(
            tmp_path,
            {
                "core/outbox/capture.py": (
                    "def capture(trace_id, span_id):\n"
                    "    return (trace_id is None) != (span_id is None)\n"
                )
            },
        )
        assert "A63" not in violations


class TestMaskingReachesTheLogCall:
    def test_a_sensitive_binding_passed_positionally_is_reported(
        self, tmp_path: Path, arch_rules: Rules
    ) -> None:
        violations = arch_rules(
            tmp_path,
            {
                "domains/payments/service.py": (
                    "import logging\n"
                    "logger = logging.getLogger(__name__)\n"
                    "def charge(card_number):\n"
                    "    logger.info('charging %s', card_number)\n"
                )
            },
        )
        assert "M23.1-MASK" in violations

    def test_a_sensitive_attribute_in_an_f_string_is_reported(
        self, tmp_path: Path, arch_rules: Rules
    ) -> None:
        violations = arch_rules(
            tmp_path,
            {
                "application/checkout/use_case.py": (
                    "import logging\n"
                    "logger = logging.getLogger(__name__)\n"
                    "def run(request):\n"
                    "    logger.warning(f'token was {request.access_token}')\n"
                )
            },
        )
        assert "M23.1-MASK" in violations

    def test_a_sensitive_context_key_is_reported(self, tmp_path: Path, arch_rules: Rules) -> None:
        """It would render as `[MASKED]`; passing it is a leak that only looks harmless."""
        violations = arch_rules(
            tmp_path,
            {
                "interfaces/api/v1/views.py": (
                    "import logging\n"
                    "logger = logging.getLogger(__name__)\n"
                    "def view(request, password):\n"
                    "    logger.info('login', extra={'password': password})\n"
                )
            },
        )
        assert "M23.1-MASK" in violations

    def test_an_ordinary_diagnostic_is_left_alone(self, tmp_path: Path, arch_rules: Rules) -> None:
        violations = arch_rules(
            tmp_path,
            {
                "application/checkout/use_case.py": (
                    "import logging\n"
                    "logger = logging.getLogger(__name__)\n"
                    "def run(order_id, latency_ms):\n"
                    "    logger.info('placed', extra={'order_id': order_id, "
                    "'latency_ms': latency_ms})\n"
                )
            },
        )
        assert "M23.1-MASK" not in violations

    def test_a_sensitive_name_outside_a_log_call_is_not_this_rule(
        self, tmp_path: Path, arch_rules: Rules
    ) -> None:
        violations = arch_rules(
            tmp_path,
            {"domains/accounts/service.py": "def check(password):\n    return bool(password)\n"},
        )
        assert "M23.1-MASK" not in violations
