"""The frozen dependency matrix, proved case by case against the static checker.

Each case is one row of Phase 0 item 3 §4 / §16, written as a throwaway source tree.
A legal case must produce no violation at all; an illegal case must produce the rule id
the frozen corpus assigns to it.
"""

from __future__ import annotations

import pytest

# ---------------------------------------------------------------------------
# 1. Legal downward imports
# ---------------------------------------------------------------------------


def test_legal_downward_imports_are_clean(tmp_path, arch_rules):
    found = arch_rules(
        tmp_path,
        {
            "core/money.py": "",
            "domains/orders/public.py": "__all__ = ()\n",
            "domains/orders/services.py": "import core.money\n",
            "application/checkout/use_cases.py": (
                "import core.money\nimport domains.orders.public\n"
            ),
            "application/checkout/public.py": "__all__ = ()\n",
            "interfaces/web/views.py": "import application.checkout.public\nimport core.money\n",
            "tasks/maintenance.py": "import application.checkout.public\nimport core.money\n",
        },
    )
    assert found == set()


# ---------------------------------------------------------------------------
# 2-5. Sideways edges inside domains and application
# ---------------------------------------------------------------------------


def test_domain_to_domain_is_rejected_even_via_public(tmp_path, arch_rules):
    found = arch_rules(
        tmp_path,
        {
            "domains/inventory/public.py": "__all__ = ()\n",
            "domains/orders/services.py": "import domains.inventory.public\n",
        },
    )
    assert "L2" in found


def test_domain_internals_are_not_importable_from_outside(tmp_path, arch_rules):
    found = arch_rules(
        tmp_path,
        {
            "application/storefront/selectors.py": "from domains.catalog import models\n",
        },
    )
    assert "L4" in found


def test_application_to_application_is_rejected(tmp_path, arch_rules):
    found = arch_rules(
        tmp_path,
        {
            "application/storefront/selectors.py": "",
            "application/checkout/use_cases.py": "import application.storefront.selectors\n",
        },
    )
    assert "L5" in found


def test_application_importing_an_integration_is_rejected(tmp_path, arch_rules):
    found = arch_rules(
        tmp_path,
        {
            "application/checkout/use_cases.py": "import integrations.maib.outbound.client\n",
        },
    )
    assert "L6" in found


# ---------------------------------------------------------------------------
# 6-8. Transport peers never name a vendor or the composition root
# ---------------------------------------------------------------------------


def test_task_importing_an_integration_is_rejected(tmp_path, arch_rules):
    found = arch_rules(tmp_path, {"tasks/erp.py": "import integrations.erp.outbound.client\n"})
    assert "L11" in found


def test_task_importing_config_is_rejected(tmp_path, arch_rules):
    found = arch_rules(tmp_path, {"tasks/payments.py": "import config.composition\n"})
    assert "L16" in found


def test_interface_importing_config_is_rejected(tmp_path, arch_rules):
    found = arch_rules(tmp_path, {"interfaces/web/views.py": "import config.composition\n"})
    assert "L16" in found


# ---------------------------------------------------------------------------
# 9-10. The two provider surfaces
# ---------------------------------------------------------------------------


def test_webhook_may_use_the_provider_protocol_surface(tmp_path, arch_rules):
    found = arch_rules(
        tmp_path,
        {
            "integrations/maib/protocol/signature.py": "",
            "interfaces/webhooks/maib.py": "from integrations.maib.protocol import signature\n",
        },
    )
    assert found == set()


def test_webhook_may_not_reach_the_outbound_adapter(tmp_path, arch_rules):
    found = arch_rules(
        tmp_path,
        {
            "integrations/maib/outbound/client.py": "",
            "interfaces/webhooks/maib.py": "from integrations.maib.outbound import client\n",
        },
    )
    assert "L17" in found


def test_a_non_webhook_interface_may_not_reach_a_provider_at_all(tmp_path, arch_rules):
    found = arch_rules(
        tmp_path,
        {
            "integrations/maib/protocol/signature.py": "",
            "interfaces/web/views.py": "from integrations.maib.protocol import signature\n",
        },
    )
    assert "L12" in found


def test_protocol_surface_carries_no_client_code(tmp_path, arch_rules):
    found = arch_rules(
        tmp_path,
        {
            "integrations/maib/outbound/client.py": "",
            "integrations/maib/protocol/codec.py": (
                "from integrations.maib.outbound import client\n"
            ),
        },
    )
    assert "L18" in found


# ---------------------------------------------------------------------------
# 11-12. The composition root's SPECIAL cell
# ---------------------------------------------------------------------------


def test_config_may_import_application_ports_and_public(tmp_path, arch_rules):
    found = arch_rules(
        tmp_path,
        {
            "application/payments_gateway/ports.py": "",
            "application/payments_gateway/public.py": "__all__ = ()\n",
            "integrations/maib/outbound/client.py": ("import application.payments_gateway.ports\n"),
            "config/composition/payments.py": (
                "import application.payments_gateway.ports\n"
                "import application.payments_gateway.public\n"
                "import integrations.maib.outbound.client\n"
            ),
        },
    )
    assert found == set()


def test_config_may_not_import_application_internals(tmp_path, arch_rules):
    found = arch_rules(
        tmp_path,
        {
            "application/checkout/use_cases.py": "",
            "config/composition/checkout.py": "import application.checkout.use_cases\n",
        },
    )
    assert "L7" in found


# ---------------------------------------------------------------------------
# 13-14. The one legal upward edge
# ---------------------------------------------------------------------------


def test_integration_may_implement_an_application_port(tmp_path, arch_rules):
    found = arch_rules(
        tmp_path,
        {
            "application/payments_gateway/ports.py": "",
            "integrations/maib/protocol/codec.py": "",
            "integrations/maib/outbound/client.py": (
                "from application.payments_gateway.ports import PaymentGatewayPort\n"
                "from integrations.maib.protocol import codec\n"
            ),
        },
    )
    assert found == set()


def test_integration_may_not_reach_application_public_or_internals(tmp_path, arch_rules):
    found = arch_rules(
        tmp_path,
        {
            "application/erp_sync/public.py": "__all__ = ()\n",
            "application/erp_sync/models.py": "",
            "integrations/erp/outbound/client.py": (
                "import application.erp_sync.public\nimport application.erp_sync.models\n"
            ),
        },
    )
    assert "L8" in found


# ---------------------------------------------------------------------------
# 15. Tests are never a source package
# ---------------------------------------------------------------------------


def test_production_importing_tests_is_rejected(tmp_path, arch_rules):
    found = arch_rules(
        tmp_path,
        {
            "tests/fakes.py": "",
            "application/checkout/use_cases.py": "from tests import fakes\n",
        },
    )
    assert "L14" in found


# ---------------------------------------------------------------------------
# Remaining matrix rows
# ---------------------------------------------------------------------------


def test_core_knows_nothing_above_it(tmp_path, arch_rules):
    found = arch_rules(
        tmp_path,
        {
            "application/storefront/selectors.py": "",
            "core/cache/single_flight.py": "import application.storefront.selectors\n",
        },
    )
    assert "L1" in found


def test_domain_imports_nothing_above_or_sideways(tmp_path, arch_rules):
    found = arch_rules(
        tmp_path,
        {"domains/notifications/services.py": "import application.notifications.ports\n"},
    )
    assert "L3" in found


def test_vendor_packages_are_isolated(tmp_path, arch_rules):
    found = arch_rules(
        tmp_path,
        {
            "integrations/mia/outbound/client.py": "",
            "integrations/maib/outbound/client.py": "import integrations.mia.outbound.client\n",
        },
    )
    assert "L9" in found


def test_shared_integrations_base_is_not_a_sibling_vendor(tmp_path, arch_rules):
    found = arch_rules(
        tmp_path,
        {
            "integrations/base/client.py": "",
            "integrations/maib/outbound/client.py": "from integrations.base import client\n",
        },
    )
    assert found == set()


def test_integrations_keep_the_pure_python_core_subset(tmp_path, arch_rules):
    found = arch_rules(
        tmp_path,
        {
            "integrations/maib/outbound/client.py": ("import core.money\nimport core.outbox\n"),
        },
    )
    assert "L10" in found


# ---------------------------------------------------------------------------
# `interfaces -> core` — the item 3 §4.4 SPECIAL CASE allowlist
# ---------------------------------------------------------------------------


def test_an_interface_may_use_the_transport_and_security_primitives(tmp_path, arch_rules):
    found = arch_rules(
        tmp_path,
        {
            "interfaces/web/views.py": (
                "import core.security\n"
                "import core.dto\n"
                "import core.money\n"
                "import core.public_id\n"
                "import core.observability\n"
                "import core.cache\n"
            )
        },
    )
    assert found == set()


def test_a_webhook_may_use_core_inbox_for_durable_ingest(tmp_path, arch_rules):
    found = arch_rules(tmp_path, {"interfaces/webhooks/maib.py": "import core.inbox\n"})
    assert found == set()


def test_an_interface_may_not_write_an_outbox_row(tmp_path, arch_rules):
    found = arch_rules(tmp_path, {"interfaces/webhooks/maib.py": "import core.outbox\n"})
    assert "L13" in found


def test_an_interface_may_not_claim_an_idempotency_key(tmp_path, arch_rules):
    found = arch_rules(
        tmp_path, {"interfaces/web/views.py": "from core.idempotency import claim\n"}
    )
    assert "L13" in found


def test_an_interface_may_not_reach_core_events(tmp_path, arch_rules):
    found = arch_rules(tmp_path, {"interfaces/web/views.py": "import core.events\n"})
    assert "M4.4-CORE" in found
    assert "L13" not in found


def test_an_interface_may_not_reach_an_unlisted_core_module(tmp_path, arch_rules):
    found = arch_rules(tmp_path, {"interfaces/api/v1/orders.py": "from core.foo import bar\n"})
    assert "M4.4-CORE" in found


# ---------------------------------------------------------------------------
# L20 / L21 — the actor primitive and the structural public-error categories
# (item 4 §19.5, ADR-0006 §1 and §2). Both halves, for every family.
# ---------------------------------------------------------------------------

CONSUMER_MODULES = {
    "domains": "domains/orders/policies.py",
    "application": "application/checkout/use_cases.py",
    "interfaces": "interfaces/web/views.py",
    "tasks": "tasks/maintenance.py",
    "config": "config/composition/checkout.py",
}


@pytest.mark.parametrize("module", sorted(CONSUMER_MODULES.values()))
@pytest.mark.parametrize("primitive", ["core.actor", "core.errors"])
def test_the_five_permitted_families_may_name_the_public_contract_primitives(
    tmp_path, arch_rules, module, primitive
):
    """The positive half. `interfaces` is the allowlist extension ADR-0006 records: before
    the physical names existed, this import was reported as M4.4-CORE."""
    found = arch_rules(tmp_path, {module: f"import {primitive}\n"})
    assert found == set()


@pytest.mark.parametrize(("primitive", "rule"), [("core.actor", "L20"), ("core.errors", "L21")])
def test_an_adapter_may_not_name_either_primitive(tmp_path, arch_rules, primitive, rule):
    """The negative half: an adapter answers no authorization question and never raises or
    interprets a domain public error. Reported under the frozen rule id rather than under
    the generic L10 allowlist that also covers it."""
    found = arch_rules(tmp_path, {"integrations/maib/outbound/client.py": f"import {primitive}\n"})
    assert rule in found
    assert "L10" not in found


@pytest.mark.parametrize(("primitive", "rule"), [("core.actor", "L20"), ("core.errors", "L21")])
def test_a_migration_may_not_name_either_primitive(tmp_path, arch_rules, primitive, rule):
    found = arch_rules(
        tmp_path,
        {"domains/orders/migrations/0001_initial.py": f"from {primitive} import Actor\n"},
    )
    assert rule in found
    assert "A6" not in found


def test_the_generic_integrations_allowlist_is_not_widened(tmp_path, arch_rules):
    """ADR-0006 does not weaken L10: the adapter's `core` subset gains nothing."""
    found = arch_rules(
        tmp_path,
        {"integrations/erp/outbound/client.py": "import core.events\nimport core.inbox\n"},
    )
    assert found == {"L10"}


# ---------------------------------------------------------------------------
# `interfaces -> tasks` — enqueue only (item 3 §4.4 SPECIAL CASE)
# ---------------------------------------------------------------------------


def test_an_interface_may_enqueue_a_task(tmp_path, arch_rules):
    found = arch_rules(
        tmp_path,
        {
            "tasks/notifications.py": "",
            "interfaces/web/views.py": (
                "from tasks.notifications import send_email\n\n\n"
                "def confirm(request):\n"
                "    send_email.delay(request.order_id)\n"
                "    send_email.apply_async((request.order_id,), countdown=5)\n"
            ),
        },
    )
    assert found == set()


def test_an_interface_may_enqueue_through_a_module_import(tmp_path, arch_rules):
    found = arch_rules(
        tmp_path,
        {
            "tasks/notifications.py": "",
            "interfaces/web/views.py": (
                "import tasks.notifications\n\n\n"
                "def confirm(request):\n"
                "    tasks.notifications.send_email.delay(request.order_id)\n"
            ),
        },
    )
    assert found == set()


def test_an_interface_may_not_run_a_task_body_inline(tmp_path, arch_rules):
    found = arch_rules(
        tmp_path,
        {
            "tasks/notifications.py": "",
            "interfaces/web/views.py": (
                "from tasks.notifications import send_email\n\n\n"
                "def confirm(request):\n"
                "    send_email(request.order_id)\n"
            ),
        },
    )
    assert "M4.4-TASKS" in found


def test_an_interface_may_not_reach_a_task_helper(tmp_path, arch_rules):
    found = arch_rules(
        tmp_path,
        {
            "tasks/notifications.py": "",
            "interfaces/web/views.py": (
                "from tasks.notifications import send_email\n\n\n"
                "def confirm(request):\n"
                "    return send_email.some_helper\n"
            ),
        },
    )
    assert "M4.4-TASKS" in found


def test_an_interface_may_not_inspect_task_state(tmp_path, arch_rules):
    found = arch_rules(
        tmp_path,
        {
            "tasks/notifications.py": "",
            "interfaces/web/views.py": (
                "from tasks.notifications import send_email\n\n\n"
                "def status(request):\n"
                "    return send_email.backend.get_result(request.id)\n"
            ),
        },
    )
    assert "M4.4-TASKS" in found


def test_a_port_is_a_leaf_importable_without_django(tmp_path, arch_rules):
    found = arch_rules(
        tmp_path,
        {
            "application/payments_gateway/ports.py": (
                "import core.money\n"
                "from django.db import models\n"
                "import integrations.maib.protocol\n"
            ),
        },
    )
    assert "L15" in found
