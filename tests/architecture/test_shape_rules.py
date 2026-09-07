"""Module-shape rules: item 3 §15.2's `A` series, item 4 §19.1's extension, item 14 §19."""

from __future__ import annotations

import pytest

# ---------------------------------------------------------------------------
# A1 — model-definition capability, not ordinary ORM query use
# ---------------------------------------------------------------------------


def test_a1_query_expressions_stay_legal_in_a_selector(tmp_path, arch_rules):
    found = arch_rules(
        tmp_path,
        {
            "domains/catalog/selectors.py": (
                "from django.db.models import Exists, F, OuterRef, Q, Subquery\n"
            )
        },
    )
    assert found == set()


def test_a1_allows_transactions_in_a_domain_service(tmp_path, arch_rules):
    found = arch_rules(
        tmp_path, {"domains/orders/services.py": "from django.db import transaction\n"}
    )
    assert found == set()


def test_a1_allows_a_model_in_a_domain_models_module(tmp_path, arch_rules):
    found = arch_rules(
        tmp_path,
        {
            "domains/catalog/models.py": (
                "from django.db import models\n\n\nclass Product(models.Model):\n    pass\n"
            )
        },
    )
    assert found == set()


def test_a1_allows_a_model_in_an_application_models_module(tmp_path, arch_rules):
    found = arch_rules(
        tmp_path,
        {
            "application/storefront/models.py": (
                "from django.db import models\n\n\n"
                "class ProductListingProjection(models.Model):\n    pass\n"
            )
        },
    )
    assert found == set()


def test_a1_allows_a_core_infrastructure_model(tmp_path, arch_rules):
    """A1 permits the model; A130 separately requires it to declare its unique constraint.

    This fixture is a bare model, so A130 fires and is expected here — the assertion is
    about A1 alone, and the full-constraint case lives in `test_idempotency_rules.py`.
    """
    found = arch_rules(
        tmp_path,
        {
            "core/idempotency/models.py": (
                "from django.db import models\n\n\nclass IdempotencyKey(models.Model):\n    pass\n"
            )
        },
    )
    assert "A1" not in found
    assert found == {"A130"}


def test_a1_rejects_the_model_module_outside_a_model_location(tmp_path, arch_rules):
    found = arch_rules(tmp_path, {"interfaces/web/views.py": "from django.db import models\n"})
    assert "A1" in found


def test_a1_rejects_a_model_subclass_outside_a_model_location(tmp_path, arch_rules):
    found = arch_rules(
        tmp_path,
        {
            "interfaces/web/views.py": (
                "from django.db import models\n\n\nclass Sneaky(models.Model):\n    pass\n"
            )
        },
    )
    assert "A1" in found


def test_a1_catches_a_directly_imported_model_base(tmp_path, arch_rules):
    """`from django.db.models import Model` binds no module, so a name check would miss it."""
    found = arch_rules(
        tmp_path,
        {
            "application/storefront/selectors.py": (
                "from django.db.models import Model\n\n\nclass X(Model):\n    pass\n"
            )
        },
    )
    assert "A1" in found


# ---------------------------------------------------------------------------
# A3
# ---------------------------------------------------------------------------


def test_a3_adapters_stay_importable_without_django(tmp_path, arch_rules):
    found = arch_rules(
        tmp_path, {"integrations/erp/outbound/client.py": "from django.conf import settings\n"}
    )
    assert "A3" in found


# ---------------------------------------------------------------------------
# A5 — the unit is the view function/class and the task function, not the module
# ---------------------------------------------------------------------------


def test_a5_two_single_domain_views_may_share_a_module(tmp_path, arch_rules):
    found = arch_rules(
        tmp_path,
        {
            "interfaces/web/views.py": (
                "import domains.catalog.public\n"
                "import domains.reviews.public\n\n\n"
                "def category_view(request):\n"
                "    return domains.catalog.public.get_category(request)\n\n\n"
                "def review_view(request):\n"
                "    return domains.reviews.public.list_reviews(request)\n"
            )
        },
    )
    assert found == set()


def test_a5_one_view_may_not_reach_two_domains(tmp_path, arch_rules):
    found = arch_rules(
        tmp_path,
        {
            "interfaces/web/views.py": (
                "import domains.catalog.public\n"
                "import domains.reviews.public\n\n\n"
                "def bad_view(request):\n"
                "    product = domains.catalog.public.get_product(request)\n"
                "    return domains.reviews.public.list_reviews(product)\n"
            )
        },
    )
    assert "A5" in found


def test_a5_counts_a_class_based_view_as_one_unit(tmp_path, arch_rules):
    found = arch_rules(
        tmp_path,
        {
            "interfaces/web/views.py": (
                "from domains.catalog.public import get_product\n"
                "from domains.reviews.public import list_reviews\n\n\n"
                "class ProductView:\n"
                "    def get(self, request):\n"
                "        return get_product(request)\n\n"
                "    def post(self, request):\n"
                "        return list_reviews(request)\n"
            )
        },
    )
    assert "A5" in found


def test_a5_one_task_function_may_not_reach_two_domains(tmp_path, arch_rules):
    found = arch_rules(
        tmp_path,
        {
            "tasks/order.py": (
                "from domains.pricing.public import quote\n"
                "from domains.inventory.public import reserve\n\n\n"
                "def place(order_id):\n"
                "    return reserve(quote(order_id))\n"
            )
        },
    )
    assert "A5" in found


# ---------------------------------------------------------------------------
# A6 — migrations import no runtime code, `core` included
# ---------------------------------------------------------------------------


def test_a6_migration_may_not_import_its_own_domain_model(tmp_path, arch_rules):
    found = arch_rules(
        tmp_path,
        {"domains/catalog/migrations/0007_x.py": "from domains.catalog.models import Product\n"},
    )
    assert "A6" in found


def test_a6_migration_may_not_import_core_money(tmp_path, arch_rules):
    found = arch_rules(
        tmp_path,
        {"domains/pricing/migrations/0002_price.py": "from core.money import Money\n"},
    )
    assert "A6" in found


def test_a6_migration_may_not_import_core_dto(tmp_path, arch_rules):
    found = arch_rules(
        tmp_path,
        {"domains/orders/migrations/0003_snapshot.py": "from core.dto import frozen\n"},
    )
    assert "A6" in found


def test_a6_migration_may_not_import_an_arbitrary_core_module(tmp_path, arch_rules):
    found = arch_rules(
        tmp_path,
        {"domains/orders/migrations/0004_outbox.py": "import core.outbox\n"},
    )
    assert "A6" in found


def test_a6_migration_may_use_django_migration_machinery(tmp_path, arch_rules):
    """L19 — the layer-contract exclusion is path-scoped, and A6 inspects migrations instead."""
    found = arch_rules(
        tmp_path,
        {
            "domains/catalog/migrations/0001_initial.py": (
                "from django.db import migrations, models\n\n\n"
                "def forwards(apps, schema_editor):\n"
                "    Product = apps.get_model('catalog', 'Product')\n"
                "    Product.objects.all()\n\n\n"
                "class Migration(migrations.Migration):\n"
                "    operations = [migrations.RunPython(forwards)]\n"
            )
        },
    )
    assert found == set()


# ---------------------------------------------------------------------------
# A8, A9, A10
# ---------------------------------------------------------------------------


def test_a8_package_inits_stay_empty(tmp_path, arch_rules):
    found = arch_rules(
        tmp_path,
        {
            "domains/catalog/public.py": "__all__ = ()\n",
            "domains/catalog/__init__.py": "from domains.catalog.public import *  # noqa\n",
        },
    )
    assert "A8" in found


def test_a9_a_ports_module_belongs_to_an_application(tmp_path, arch_rules):
    found = arch_rules(tmp_path, {"domains/notifications/ports.py": ""})
    assert "A9" in found


def test_a10_only_the_composition_root_binds_an_adapter_to_a_port(tmp_path, arch_rules):
    found = arch_rules(
        tmp_path,
        {
            "interfaces/web/bootstrap.py": (
                "import integrations.maib.outbound.client\n"
                "import application.payments_gateway.ports\n"
            ),
        },
    )
    assert "A10" in found


# ---------------------------------------------------------------------------
# A11 / A14 / A15 — three separate rules over `public.py`
# ---------------------------------------------------------------------------


def test_a_well_formed_facade_passes_all_three(tmp_path, arch_rules):
    found = arch_rules(
        tmp_path,
        {
            "domains/orders/dto.py": "",
            "domains/orders/services.py": "",
            "domains/orders/public.py": (
                "from domains.orders.dto import OrderDTO\n"
                "from domains.orders.services import place_order\n\n"
                '__all__ = ("OrderDTO", "place_order")\n'
            ),
        },
    )
    assert found == set()


def test_a11_reports_an_orm_re_export_under_its_own_id(tmp_path, arch_rules):
    found = arch_rules(
        tmp_path,
        {
            "domains/orders/public.py": (
                'from domains.orders.models import Order\n\n__all__ = ("Order",)\n'
            )
        },
    )
    assert "A11" in found


def test_a11_catches_a_queryset_or_manager_symbol(tmp_path, arch_rules):
    found = arch_rules(
        tmp_path,
        {
            "domains/orders/public.py": (
                "from domains.orders.selectors import OrderQuerySet\n\n"
                '__all__ = ("OrderQuerySet",)\n'
            )
        },
    )
    assert "A11" in found


def test_a11_follows_a_symbol_through_one_forwarding_module(tmp_path, arch_rules):
    """The immediate import names no `models` module and the symbol is just `Order`."""
    found = arch_rules(
        tmp_path,
        {
            "domains/orders/models.py": (
                "from django.db import models\n\n\nclass Order(models.Model):\n    pass\n"
            ),
            "domains/orders/export_helpers.py": "from domains.orders.models import Order\n",
            "domains/orders/public.py": (
                'from domains.orders.export_helpers import Order\n\n__all__ = ("Order",)\n'
            ),
        },
    )
    assert "A11" in found


def test_a11_follows_a_symbol_through_two_forwarding_modules(tmp_path, arch_rules):
    found = arch_rules(
        tmp_path,
        {
            "domains/orders/models.py": (
                "from django.db import models\n\n\nclass Order(models.Model):\n    pass\n"
            ),
            "domains/orders/helper1.py": "from domains.orders.models import Order\n",
            "domains/orders/helper2.py": "from domains.orders.helper1 import Order\n",
            "domains/orders/public.py": (
                'from domains.orders.helper2 import Order\n\n__all__ = ("Order",)\n'
            ),
        },
    )
    assert "A11" in found


def test_a11_allows_a_callable_whose_module_uses_the_orm_internally(tmp_path, arch_rules):
    """Provenance of the exported symbol, not the dependency graph of its module."""
    found = arch_rules(
        tmp_path,
        {
            "domains/orders/models.py": (
                "from django.db import models\n\n\nclass Order(models.Model):\n    pass\n"
            ),
            "domains/orders/dto.py": "",
            "domains/orders/services.py": (
                "from domains.orders.models import Order\n\n\n"
                "def place_order():\n    return Order\n"
            ),
            "domains/orders/public.py": (
                "from domains.orders.dto import OrderDTO\n"
                "from domains.orders.services import place_order\n\n"
                '__all__ = ("OrderDTO", "place_order")\n'
            ),
        },
    )
    assert found == set()


def test_a11_provenance_terminates_on_a_cycle(tmp_path, arch_rules):
    """A forwarding cycle resolves to nothing rather than hanging or guessing."""
    found = arch_rules(
        tmp_path,
        {
            "domains/orders/a.py": "from domains.orders.b import Thing\n",
            "domains/orders/b.py": "from domains.orders.a import Thing\n",
            "domains/orders/public.py": (
                'from domains.orders.a import Thing\n\n__all__ = ("Thing",)\n'
            ),
        },
    )
    assert "A11" not in found


def test_a14_rejects_a_plain_module_import_of_stdlib(tmp_path, arch_rules):
    found = arch_rules(
        tmp_path,
        {"domains/orders/public.py": 'import typing\n\n__all__ = ("typing",)\n'},
    )
    assert "A14" in found


def test_a14_rejects_a_plain_module_import_of_an_internal_module(tmp_path, arch_rules):
    found = arch_rules(
        tmp_path,
        {
            "domains/orders/dto.py": "",
            "domains/orders/public.py": ('import domains.orders.dto\n\n__all__ = ("domains",)\n'),
        },
    )
    assert "A14" in found


def test_a14_rejects_a_plain_module_import_of_core(tmp_path, arch_rules):
    found = arch_rules(
        tmp_path,
        {
            "core/money.py": "",
            "domains/orders/public.py": 'import core.money\n\n__all__ = ("core",)\n',
        },
    )
    assert "A14" in found


def test_a14_allows_an_explicit_symbol_import_from_core(tmp_path, arch_rules):
    found = arch_rules(
        tmp_path,
        {
            "core/money.py": "",
            "domains/orders/dto.py": "",
            "domains/orders/public.py": (
                "from core.money import Money\n"
                "from domains.orders.dto import OrderDTO\n\n"
                '__all__ = ("Money", "OrderDTO")\n'
            ),
        },
    )
    assert found == set()


def test_a14_rejects_a_def_in_a_facade(tmp_path, arch_rules):
    found = arch_rules(
        tmp_path,
        {
            "domains/orders/public.py": (
                'def place_order():\n    return None\n\n\n__all__ = ("place_order",)\n'
            )
        },
    )
    assert "A14" in found
    assert "A11" not in found


def test_a14_rejects_a_wildcard_import(tmp_path, arch_rules):
    found = arch_rules(
        tmp_path,
        {"domains/orders/public.py": "from domains.orders.dto import *\n\n__all__ = ()\n"},
    )
    assert "A14" in found


def test_a14_rejects_an_aliased_import(tmp_path, arch_rules):
    found = arch_rules(
        tmp_path,
        {
            "domains/orders/dto.py": "",
            "domains/orders/public.py": (
                'from domains.orders.dto import OrderDTO as Order\n\n__all__ = ("Order",)\n'
            ),
        },
    )
    assert "A14" in found


def test_a14_rejects_a_module_re_export(tmp_path, arch_rules):
    found = arch_rules(
        tmp_path,
        {
            "domains/orders/dto.py": "",
            "domains/orders/public.py": 'from domains.orders import dto\n\n__all__ = ("dto",)\n',
        },
    )
    assert "A14" in found


def test_a14_rejects_a_type_checking_import(tmp_path, arch_rules):
    found = arch_rules(
        tmp_path,
        {
            "domains/orders/public.py": (
                "from typing import TYPE_CHECKING\n\n"
                "if TYPE_CHECKING:\n"
                "    from domains.orders.dto import OrderDTO\n\n"
                '__all__ = ("TYPE_CHECKING", "OrderDTO")\n'
            )
        },
    )
    assert "A14" in found


def test_a14_rejects_a_module_level_getattr(tmp_path, arch_rules):
    found = arch_rules(
        tmp_path,
        {
            "domains/orders/public.py": (
                "def __getattr__(name):\n    raise AttributeError(name)\n\n\n__all__ = ()\n"
            )
        },
    )
    assert "A14" in found


def test_a15_requires_an_explicit_all(tmp_path, arch_rules):
    found = arch_rules(
        tmp_path,
        {
            "domains/orders/dto.py": "",
            "domains/orders/public.py": "from domains.orders.dto import OrderDTO\n",
        },
    )
    assert "A15" in found


def test_a15_requires_a_tuple_of_string_literals(tmp_path, arch_rules):
    found = arch_rules(
        tmp_path,
        {
            "domains/orders/dto.py": "",
            "domains/orders/public.py": (
                'from domains.orders.dto import OrderDTO\n\n__all__ = ["OrderDTO"]\n'
            ),
        },
    )
    assert "A15" in found


def test_a15_requires_all_to_match_the_imports(tmp_path, arch_rules):
    found = arch_rules(
        tmp_path,
        {
            "domains/orders/dto.py": "",
            "domains/orders/public.py": (
                "from domains.orders.dto import OrderDTO, OrderLineDTO\n\n"
                '__all__ = ("OrderDTO", "Missing")\n'
            ),
        },
    )
    assert "A15" in found


def test_a15_rejects_a_second_all_assignment(tmp_path, arch_rules):
    """The first assignment matches the imports; the runtime contract is the last one."""
    found = arch_rules(
        tmp_path,
        {
            "domains/orders/dto.py": "",
            "domains/orders/public.py": (
                'from domains.orders.dto import OrderDTO\n\n__all__ = ("OrderDTO",)\n__all__ = ()\n'
            ),
        },
    )
    assert "A15" in found


def test_a15_rejects_an_in_place_extension(tmp_path, arch_rules):
    found = arch_rules(
        tmp_path,
        {
            "domains/orders/dto.py": "",
            "domains/orders/public.py": (
                "from domains.orders.dto import OrderDTO\n\n"
                '__all__ = ("OrderDTO",)\n'
                '__all__ += ("Extra",)\n'
            ),
        },
    )
    assert "A15" in found


def test_a15_rejects_a_repeated_member(tmp_path, arch_rules):
    found = arch_rules(
        tmp_path,
        {
            "domains/orders/dto.py": "",
            "domains/orders/public.py": (
                'from domains.orders.dto import OrderDTO\n\n__all__ = ("OrderDTO", "OrderDTO")\n'
            ),
        },
    )
    assert "A15" in found


# ---------------------------------------------------------------------------
# A12, NF7, NF8
# ---------------------------------------------------------------------------


def test_a12_dependencies_are_injected_not_located(tmp_path, arch_rules):
    found = arch_rules(
        tmp_path,
        {
            "interfaces/web/views.py": (
                "import importlib\n\n\ndef gateway():\n"
                "    return importlib.import_module('integrations.maib.outbound.client')\n"
            )
        },
    )
    assert "A12" in found


def test_nf7_optional_import_fallbacks_are_rejected(tmp_path, arch_rules):
    found = arch_rules(
        tmp_path,
        {
            "application/storefront/selectors.py": (
                "try:\n"
                "    import domains.analytics.public as analytics\n"
                "except ImportError:\n"
                "    analytics = None\n"
            )
        },
    )
    assert "NF7" in found


def test_nf8_package_presence_is_never_probed(tmp_path, arch_rules):
    found = arch_rules(
        tmp_path,
        {
            "application/storefront/selectors.py": (
                "from django.apps import apps\n\n\ndef has_favorites():\n"
                "    return apps.is_installed('domains.accounts')\n"
            )
        },
    )
    assert "NF8" in found


# ---------------------------------------------------------------------------
# A70, A71, A75, A77, A82 — the `core` primitive guards (item 11 §40.1)
#
# These became checkable when the core-primitives slice created their subjects.
# ---------------------------------------------------------------------------


LEGAL_MONEY = (
    "from dataclasses import dataclass\n"
    "from enum import Enum\n\n\n"
    "class RoundingPolicy(Enum):\n"
    "    HALF_EVEN = 'HALF_EVEN'\n"
    "    TOWARD_ZERO = 'TOWARD_ZERO'\n\n\n"
    "@dataclass(frozen=True, slots=True, kw_only=True)\n"
    "class Money:\n"
    "    minor: int\n"
    "    currency: str\n"
)


def test_the_money_primitive_as_shipped_is_clean(tmp_path, arch_rules):
    assert arch_rules(tmp_path, {"core/money.py": LEGAL_MONEY}) == set()


def test_a75_rejects_a_dataclass_generated_money_ordering(tmp_path, arch_rules):
    """ADR-0012's one-word regression: `order=True` makes `Money(100, 'EUR') < Money(200,
    'USD')` legal and true at every sorted()/min()/max() call in the platform."""
    found = arch_rules(
        tmp_path,
        {
            "core/money.py": LEGAL_MONEY.replace(
                "frozen=True, slots=True", "frozen=True, order=True"
            )
        },
    )
    assert "A75" in found


def test_a75_accepts_an_explicitly_disabled_ordering(tmp_path, arch_rules):
    found = arch_rules(
        tmp_path,
        {"core/money.py": LEGAL_MONEY.replace("frozen=True,", "frozen=True, order=False,")},
    )
    assert found == set()


@pytest.mark.parametrize(
    "declaration",
    [
        "def apply_vat(amount): ...",
        "def round_delivery_fee(amount): ...",
        "DISCOUNT_SCALE = 1",
        "class TaxRate: ...",
        "class VatPolicy: ...",
        "def convert(amount, provider): ...",
    ],
)
def test_a70_rejects_business_vocabulary_in_the_money_primitive(tmp_path, arch_rules, declaration):
    """OW4: `core.money` owns the arithmetic, never which business rule applies it."""
    found = arch_rules(tmp_path, {"core/money.py": f"{LEGAL_MONEY}\n\n{declaration}\n"})
    assert "A70" in found


def test_a70_matches_segments_not_substrings(tmp_path, arch_rules):
    """`private` does not contain the currency word `vat`."""
    found = arch_rules(
        tmp_path, {"core/money.py": f"{LEGAL_MONEY}\n\ndef _private_helper(): ...\n"}
    )
    assert found == set()


@pytest.mark.parametrize("member", ["VAT_ROUNDING", "PRICE_ROUNDING", "PROMO_ROUNDING"])
def test_a77_rejects_a_rounding_policy_member_named_for_a_business_step(
    tmp_path, arch_rules, member
):
    """RP5: which policy a business step uses is that step's owner's decision, not core's.
    These three are the frozen rule's own examples."""
    found = arch_rules(
        tmp_path,
        {
            "core/money.py": LEGAL_MONEY.replace(
                "    HALF_EVEN = 'HALF_EVEN'", f"    {member} = '{member}'"
            )
        },
    )
    assert "A77" in found
    assert "A70" not in found  # the policy member reports under its own id


def test_a71_rejects_a_currency_literal_anywhere_in_core(tmp_path, arch_rules):
    """MS5: `100.00 MDL` is an example, not a definition."""
    found = arch_rules(tmp_path, {"core/money.py": f"{LEGAL_MONEY}\n\nDEFAULT = 'MDL'\n"})
    assert "A71" in found


def test_a71_covers_every_core_module_not_only_money(tmp_path, arch_rules):
    found = arch_rules(tmp_path, {"core/pricing_support.py": "FALLBACK = 'EUR'\n"})
    assert "A71" in found


@pytest.mark.parametrize(
    "module",
    [
        "domains/orders/services.py",
        "application/checkout/use_cases.py",
        "interfaces/web/views.py",
        "tasks/maintenance.py",
        "config/composition/checkout.py",
        "integrations/maib/outbound/client.py",
    ],
)
def test_a82_no_package_outside_core_reaches_the_uuid7_mechanism(tmp_path, arch_rules, module):
    """TX3/TX4: a generic exported utility would let any call site mint a value that fits
    both PublicId and EventId, dissolving the distinction exactly where it matters."""
    found = arch_rules(tmp_path, {module: "from core._uuid7 import generate\n"})
    assert "A82" in found


def test_a82_leaves_the_semantic_types_importable(tmp_path, arch_rules):
    found = arch_rules(
        tmp_path,
        {
            "domains/orders/services.py": "from core.public_id import PublicId\n",
            "application/checkout/use_cases.py": "from core.events.identity import EventId\n",
        },
    )
    assert found == set()


def test_a82_permits_core_to_use_its_own_mechanism(tmp_path, arch_rules):
    found = arch_rules(
        tmp_path,
        {
            "core/_uuid7.py": "import uuid\n",
            "core/public_id.py": "from core import _uuid7\n",
        },
    )
    assert found == set()
