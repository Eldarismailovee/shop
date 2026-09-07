"""The real source tree: the launch cut, the closed gates, and a clean harness run."""

from __future__ import annotations

import subprocess
import sys

import pytest

from tests.conftest import REPO_ROOT
from tools.arch_check import check_tree

#: Item 14 §5 / §19 NF1: a LATER module has no package at all, and absence is absence.
LATER_PACKAGES = (
    "domains/analytics",
    "domains/tradein",
    "domains/support",
    "domains/digital",
    "application/backoffice",
    "application/crm_sync",
    "application/support",
    "integrations/crm",
    "integrations/chatwoot",
    "integrations/mia",
)

#: Item 14 §5.2-§5.7: the launch cut, as physically created by this slice.
LAUNCH_PACKAGES = (
    "core",
    "config",
    "domains/accounts",
    "domains/catalog",
    "domains/content",
    "domains/delivery",
    "domains/inventory",
    "domains/notifications",
    "domains/orders",
    "domains/payments",
    "domains/pricing",
    "domains/promotions",
    "domains/reviews",
    "domains/stores",
    "application/checkout",
    "application/erp_sync",
    "application/payments_gateway",
    "application/storefront",
    "interfaces/web",
    "interfaces/api/v1",
    "interfaces/webhooks",
    "interfaces/admin",
    "integrations/base",
    "integrations/erp/protocol",
    "integrations/erp/outbound",
    "integrations/maib/protocol",
    "integrations/maib/outbound",
    "tasks",
)


#: The `core` primitives slice's physical layout, frozen by
#: docs/architecture/phase-1/02-core-primitives.md §2 (item 11 §42 deferred it to Phase 1).
CORE_MODULES = (
    "core/_uuid7.py",
    "core/money.py",
    "core/public_id.py",
    "core/actor.py",
    "core/errors.py",
    "core/events/identity.py",
    "core/events/envelope.py",
    "core/events/registry.py",
    "core/events/errors.py",
)


@pytest.mark.parametrize("package", LAUNCH_PACKAGES)
def test_launch_package_exists(package: str) -> None:
    assert (REPO_ROOT / package / "__init__.py").is_file()


@pytest.mark.parametrize("module", CORE_MODULES)
def test_core_primitive_module_exists(module: str) -> None:
    assert (REPO_ROOT / module).is_file()


def test_core_declares_no_umbrella_re_export() -> None:
    """Slice 1 §10 / task §8: `core` follows its own frozen per-family allowlists, so no
    `public.py` façade and no convenience re-export exists — a family imports the exact
    submodule its allowlist names."""
    for init in ("core/__init__.py", "core/events/__init__.py"):
        assert (REPO_ROOT / init).read_text(encoding="utf-8").strip() == ""
    assert not (REPO_ROOT / "core" / "public.py").exists()


@pytest.mark.parametrize("package", LATER_PACKAGES)
def test_later_package_is_absent(package: str) -> None:
    assert not (REPO_ROOT / package).exists()


def test_no_production_model_or_migration_exists_yet() -> None:
    """This slice ships package structure and enforcement only."""
    families = ("core", "domains", "application", "interfaces", "integrations", "tasks")
    offenders = [
        path.relative_to(REPO_ROOT).as_posix()
        for family in families
        for path in (REPO_ROOT / family).rglob("*.py")
        if path.name.startswith("models") or "migrations" in path.parts
    ]
    assert offenders == []


def test_the_phase_1_artifact_records_the_outstanding_enforcement_obligations() -> None:
    """L20/L21 and the item-4 `A16`-`A23` series are recorded, not silently omitted."""
    artifact = (
        REPO_ROOT / "docs" / "architecture" / "phase-1" / "01-repository-bootstrap.md"
    ).read_text(encoding="utf-8")
    for obligation in ("L20", "L21", "A16", "A23", "MIGRATION_CORE_ALLOWLIST"):
        assert obligation in artifact, f"{obligation} is missing from the Phase-1 artifact"


def test_the_core_primitives_artifact_records_its_choices_and_its_deferrals() -> None:
    """The slice records the Phase-0 deferrals it filled, and does not silently drop the
    A16-A23 obligations it could not yet make checkable."""
    artifact = (
        REPO_ROOT / "docs" / "architecture" / "phase-1" / "02-core-primitives.md"
    ).read_text(encoding="utf-8")
    for recorded in (
        "L20",
        "L21",
        "A16",
        "A19",
        "A23",
        "A75",
        "A82",
        "RoundingPolicy",
        "uuid.uuid7()",
        "CORE_PUBLIC_CONTRACT_PRIMITIVES",
    ):
        assert recorded in artifact, f"{recorded} is missing from the Slice-2 artifact"


def test_no_phase_0_artifact_or_adr_was_edited_by_this_slice() -> None:
    """Phase 0 is FROZEN: a genuine architecture change is a new superseding ADR, never an
    in-place edit. This slice needed none, so the highest ADR number stays 0016."""
    adrs = sorted(p.name for p in (REPO_ROOT / "docs" / "adr").glob("0*.md"))
    assert len(adrs) == 16
    assert adrs[-1].startswith("0016-")
    status = (REPO_ROOT / "docs" / "architecture" / "phase-0" / "PHASE0_STATUS.md").read_text(
        encoding="utf-8"
    )
    assert "PHASE 0 ARCHITECTURE FREEZE — COMPLETE" in status


def test_the_source_tree_satisfies_every_static_rule() -> None:
    violations = check_tree(REPO_ROOT)
    assert violations == [], "\n".join(str(v) for v in violations)


def test_import_linter_contracts_hold() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "importlinter.cli", "lint-imports"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_no_runtime_package_imports_the_composition_root() -> None:
    """L16, as a property of the tree rather than of one fixture."""
    offenders = []
    for module in (
        REPO_ROOT / p for p in ("interfaces", "tasks", "domains", "application", "core")
    ):
        for path in module.rglob("*.py"):
            source = path.read_text(encoding="utf-8")
            if "import config" in source or "from config" in source:
                offenders.append(path.relative_to(REPO_ROOT).as_posix())
    assert offenders == []
