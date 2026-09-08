"""A2, A13 and `M20.8-TIMEOUT` — the rules that leave no route around the adapter.

Item 3 §15.2 A2/A13, item 3 §6.5, master `# 20.8` §1, and the Phase 1 DoD clause *"external
client без timeout невозможен через стандартный adapter"*. Each case materialises a
throwaway tree that breaks one rule, and its negative twin proves the rule leaves alone the
legitimate shape it resembles.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from pathlib import Path

Rules = Callable[[Path, Mapping[str, str]], set[str]]


class TestA2NetworkClientsStayInIntegrations:
    def test_a_domain_that_opens_its_own_connection_is_reported(
        self, tmp_path: Path, arch_rules: Rules
    ) -> None:
        """The failure this prevents is not untidiness: it is an outbound call with no
        timeout budget, no breaker, no vendor DTO and no failure domain."""
        violations = arch_rules(
            tmp_path,
            {"domains/payments/services.py": "import httpx\n\n\ndef charge():\n    ...\n"},
        )
        assert "A2" in violations

    def test_an_application_use_case_is_reported(self, tmp_path: Path, arch_rules: Rules) -> None:
        violations = arch_rules(
            tmp_path,
            {"application/checkout/use_case.py": "import requests\n"},
        )
        assert "A2" in violations

    def test_a_view_is_reported(self, tmp_path: Path, arch_rules: Rules) -> None:
        violations = arch_rules(
            tmp_path,
            {"interfaces/web/views/pay.py": "from urllib.request import urlopen\n"},
        )
        assert "A2" in violations

    def test_a_task_is_reported(self, tmp_path: Path, arch_rules: Rules) -> None:
        violations = arch_rules(tmp_path, {"tasks/erp.py": "import socket\n"})
        assert "A2" in violations

    def test_the_composition_root_is_reported_too(self, tmp_path: Path, arch_rules: Rules) -> None:
        """`config/` binds an adapter; it does not make the call itself."""
        violations = arch_rules(tmp_path, {"config/composition/erp.py": "import httpx\n"})
        assert "A2" in violations

    def test_url_parsing_is_not_a_network_client(self, tmp_path: Path, arch_rules: Rules) -> None:
        """Splitting a URL string reaches no host, and a rule that said otherwise would
        push callers towards hand-rolled string surgery."""
        violations = arch_rules(
            tmp_path,
            {"application/storefront/links.py": "from urllib.parse import urlsplit\n"},
        )
        assert "A2" not in violations

    def test_an_integration_may_hold_a_vendor_sdk(self, tmp_path: Path, arch_rules: Rules) -> None:
        violations = arch_rules(
            tmp_path,
            {"integrations/maib/outbound/client.py": "import vendor_sdk\n"},
        )
        assert "A2" not in violations


class TestM208OneDoor:
    def test_a_generic_client_beside_the_adapter_is_reported(
        self, tmp_path: Path, arch_rules: Rules
    ) -> None:
        """A vendor package that reaches for `httpx` itself has re-created the unbounded
        call the standard adapter exists to make impossible."""
        violations = arch_rules(
            tmp_path,
            {"integrations/maib/outbound/client.py": "import httpx\n"},
        )
        assert "M20.8-TIMEOUT" in violations

    def test_the_standard_adapter_itself_is_not_reported(
        self, tmp_path: Path, arch_rules: Rules
    ) -> None:
        violations = arch_rules(
            tmp_path,
            {"integrations/base/transport.py": "import httpx\n"},
        )
        assert "M20.8-TIMEOUT" not in violations
        assert "A2" not in violations

    def test_a_vendor_sdk_is_not_the_generic_http_layer(
        self, tmp_path: Path, arch_rules: Rules
    ) -> None:
        """A2 places a vendor's own SDK with its vendor; this rule does not second-guess it."""
        violations = arch_rules(
            tmp_path,
            {"integrations/maib/outbound/client.py": "import maib_sdk\n"},
        )
        assert "M20.8-TIMEOUT" not in violations


class TestM208TheDoorIsNotProppedOpen:
    def test_timeout_none_is_reported(self, tmp_path: Path, arch_rules: Rules) -> None:
        violations = arch_rules(
            tmp_path,
            {
                "integrations/base/transport.py": (
                    "import httpx\n\n\ndef send(client, url):\n"
                    "    return client.request('GET', url, timeout=None)\n"
                ),
            },
        )
        assert "M20.8-TIMEOUT" in violations

    def test_it_is_reported_wherever_it_appears(self, tmp_path: Path, arch_rules: Rules) -> None:
        violations = arch_rules(
            tmp_path,
            {"application/erp_sync/pull.py": "def go(p):\n    return p.fetch(timeout=None)\n"},
        )
        assert "M20.8-TIMEOUT" in violations

    def test_a_real_budget_is_not_reported(self, tmp_path: Path, arch_rules: Rules) -> None:
        violations = arch_rules(
            tmp_path,
            {
                "integrations/base/transport.py": (
                    "import httpx\n\n\ndef send(client, url, budget):\n"
                    "    return client.request('GET', url, timeout=budget)\n"
                ),
            },
        )
        assert "M20.8-TIMEOUT" not in violations

    def test_a_zero_timeout_is_left_to_review(self, tmp_path: Path, arch_rules: Rules) -> None:
        """`timeout=0` is a value, and a rule that read numbers would drift from the
        settings tests that already own them. The rule catches the *absence* of a bound."""
        violations = arch_rules(
            tmp_path,
            {"integrations/base/transport.py": "def send(c):\n    return c.get(timeout=0)\n"},
        )
        assert "M20.8-TIMEOUT" not in violations


class TestA13ProviderSurfacesStaySeparate:
    def test_a_protocol_surface_may_not_reach_the_adapter(
        self, tmp_path: Path, arch_rules: Rules
    ) -> None:
        """§6.5: protocol support is codecs, signatures and constants — never a call.

        This is what lets `interfaces/webhooks/<provider>` verify a signature (L12/L17)
        without thereby gaining the ability to make an outbound business call."""
        violations = arch_rules(
            tmp_path,
            {
                "integrations/maib/protocol/signature.py": (
                    "from integrations.base.client import BaseClient\n"
                ),
            },
        )
        assert "A13" in violations

    def test_a_protocol_surface_may_not_hold_a_network_client(
        self, tmp_path: Path, arch_rules: Rules
    ) -> None:
        violations = arch_rules(
            tmp_path,
            {"integrations/erp/protocol/codec.py": "import httpx\n"},
        )
        assert "A13" in violations

    def test_a_protocol_surface_may_hold_codecs_and_constants(
        self, tmp_path: Path, arch_rules: Rules
    ) -> None:
        violations = arch_rules(
            tmp_path,
            {
                "integrations/maib/protocol/signature.py": (
                    "import hashlib\nimport hmac\n\nHEADER = 'X-Signature'\n"
                ),
            },
        )
        assert "A13" not in violations

    def test_only_the_outbound_surface_implements_a_port(
        self, tmp_path: Path, arch_rules: Rules
    ) -> None:
        violations = arch_rules(
            tmp_path,
            {
                "integrations/maib/adapter.py": (
                    "from application.payments_gateway.ports import PaymentGatewayPort\n"
                ),
            },
        )
        assert "A13" in violations

    def test_the_outbound_surface_may_implement_one(
        self, tmp_path: Path, arch_rules: Rules
    ) -> None:
        violations = arch_rules(
            tmp_path,
            {
                "integrations/maib/outbound/client.py": (
                    "from application.payments_gateway.ports import PaymentGatewayPort\n"
                    "from integrations.base.client import BaseClient\n"
                ),
            },
        )
        assert "A13" not in violations

    def test_the_shared_mechanism_is_not_a_provider_package(
        self, tmp_path: Path, arch_rules: Rules
    ) -> None:
        """`integrations/base` has no protocol to keep separate and no port to implement."""
        violations = arch_rules(
            tmp_path,
            {"integrations/base/client.py": "import httpx\n"},
        )
        assert "A13" not in violations
