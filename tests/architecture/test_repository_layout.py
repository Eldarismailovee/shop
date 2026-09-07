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


def test_the_only_models_and_migrations_are_the_approved_core_infrastructure_ones() -> None:
    """Persistence exists only where an approved `core` infrastructure mechanism placed it.

    Three mechanisms now have models: `core.idempotency` (Slice 4, item 15 §15 clause 4) and
    `core.outbox` / `core.inbox` (this slice, clause 5). Each is admissible persistence in
    `core` because it is a domain-independent infrastructure mechanism whose placement item 3
    §4 already froze — `core.outbox` and `core.inbox` are named in that matrix by L13, which is
    what makes their asymmetric transport permissions checkable.

    Still no model anywhere else: no domain, no application module, no interface, no adapter.
    Widening this set is a deliberate edit, so a stray `models.py` under a domain cannot appear
    unnoticed — which is the whole point of asserting an exact set rather than a subset.
    """
    families = ("core", "domains", "application", "interfaces", "integrations", "tasks")
    found = {
        path.relative_to(REPO_ROOT).as_posix()
        for family in families
        for path in (REPO_ROOT / family).rglob("*.py")
        if path.name.startswith("models") or "migrations" in path.parts
    }
    assert found == {
        "core/idempotency/models.py",
        "core/idempotency/migrations/__init__.py",
        "core/idempotency/migrations/0001_initial.py",
        "core/outbox/models.py",
        "core/outbox/migrations/__init__.py",
        "core/outbox/migrations/0001_initial.py",
        "core/inbox/models.py",
        "core/inbox/migrations/__init__.py",
        "core/inbox/migrations/0001_initial.py",
    }


#: ADR-0011's storage-before-partition invariant, as a physical fact about the repository: the
#: four TCE fields are on the **initial** migration of every durable message table, so no
#: partitioning migration can precede them.
_INITIAL_MESSAGE_MIGRATIONS = (
    "core/outbox/migrations/0001_initial.py",
    "core/inbox/migrations/0001_initial.py",
)

TCE_FIELDS = ("trace_id", "producer_span_id", "request_id", "causation_event_id")


@pytest.mark.parametrize("migration", _INITIAL_MESSAGE_MIGRATIONS)
@pytest.mark.parametrize("field", TCE_FIELDS)
def test_the_tce_fields_are_on_the_initial_migration(migration: str, field: str) -> None:
    """ADR-0011: the four fields are present before any partitioning migration exists.

    Asserted against the migration file rather than the model, because the model is what the
    tree looks like *now* and the migration is what an existing database was actually built
    from. A column added in `0002` would satisfy the model and violate the invariant.
    """
    assert field in (REPO_ROOT / migration).read_text(encoding="utf-8")


@pytest.mark.parametrize("package", ["core/outbox", "core/inbox"])
def test_no_partitioning_migration_precedes_the_tce_fields(package: str) -> None:
    """The other half of the invariant: `0001` is still the only migration in each package.

    Once a second migration exists this test is expected to be replaced by one that reads the
    dependency graph. Until then, the strongest honest statement is that nothing has been
    added — and stating it keeps the invariant from being forgotten in the slice that adds one.
    """
    migrations = sorted(
        path.name
        for path in (REPO_ROOT / package / "migrations").glob("*.py")
        if path.name != "__init__.py"
    )
    assert migrations == ["0001_initial.py"]


def test_the_app_labels_are_explicit() -> None:
    """A label Django infers from a path segment renames a table when the path moves.

    Each `core` platform submodule is its own Django app — that is what gives L13 three
    distinguishable import surfaces to name — so each needs an explicit label and an explicit
    `db_table`.
    """
    for package, label, table in (
        ("core/idempotency", "core_idempotency", "core_idempotency_key"),
        ("core/outbox", "core_outbox", "core_outbox_message"),
        ("core/inbox", "core_inbox", "core_inbox_delivery"),
    ):
        apps_source = (REPO_ROOT / package / "apps.py").read_text(encoding="utf-8")
        assert f'label = "{label}"' in apps_source
        models_source = (REPO_ROOT / package / "models.py").read_text(encoding="utf-8")
        assert f'db_table = "{table}"' in models_source


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


def test_the_command_idempotency_artifact_records_its_choices_and_its_deferrals() -> None:
    """Slice 4 records the numbers it chose, the checks it made real, and the corpus rows it
    could not discharge — C186/C189/C190 are deferred with an owner, never quietly dropped."""
    artifact = (
        REPO_ROOT / "docs" / "architecture" / "phase-1" / "04-command-idempotency.md"
    ).read_text(encoding="utf-8")
    for recorded in (
        "A129",
        "A132",
        "A136",
        "A138",
        "L13",
        "C186",
        "C189",
        "C190",
        "MIGRATION_CORE_ALLOWLIST",
        "core_idem_scope_key_uniq",
        "core.observability",
    ):
        assert recorded in artifact, f"{recorded} is missing from the Slice-4 artifact"


def test_the_async_spine_artifact_records_its_choices_and_its_deferrals() -> None:
    """Slice 5 records the choices it made and, more importantly, what it did **not** discharge.

    The deferred behavioural checks are the point of this assertion: A62/A66 are enforced over
    the code that exists, and C76-C87 need a broker, a producer and a consumer that do not.
    Claiming them would be the easiest thing in the slice to get wrong, so the artifact naming
    them is asserted rather than trusted.
    """
    artifact = (
        REPO_ROOT / "docs" / "architecture" / "phase-1" / "05-outbox-inbox-terminal.md"
    ).read_text(encoding="utf-8")
    for recorded in (
        # The choices Phase 0 deferred to Phase 1.
        "A56",
        "A60",
        "A61",
        "A62",
        "A66",
        "L13",
        "core_outbox_message",
        "core_inbox_delivery",
        "core_inbox_message_terminal",
        "relay-claim columns",
        "core.observability",
        # The obligations that stay open, with an owner.
        "C76",
        "C77",
        "C83",
        "C85",
        "A42",
        "A51",
        "security-event log",
        "MIGRATION_CORE_ALLOWLIST",
    ):
        assert recorded in artifact, f"{recorded} is missing from the Slice-5 artifact"


def test_the_message_bounds_are_recorded_in_the_artifact() -> None:
    """Item 8 says "bounded" and fixes no numbers; the numbers this slice chose are a recorded
    decision, not an implementation detail only `bounds.py` knows."""
    from core.events import bounds

    artifact = (
        REPO_ROOT / "docs" / "architecture" / "phase-1" / "05-outbox-inbox-terminal.md"
    ).read_text(encoding="utf-8")
    for name in bounds.__all__:
        value = getattr(bounds, name)
        assert name in artifact, f"{name} is missing from the Slice-5 artifact"
        rendered = f"{value:,}".replace(",", " ")
        assert rendered in artifact or str(value) in artifact, (
            f"{name}'s value {value} is not recorded in the Slice-5 artifact"
        )


def test_the_observability_artifact_records_its_choices_and_its_deferrals() -> None:
    """Slice 6 records what it chose, and — more importantly — what it refused to fake.

    The trace pair is the assertion that matters. A slice that binds `request_id` at the edge is
    one line away from also adopting an inbound `traceparent`, which would write an upstream
    peer's span into a column whose meaning is "ours" (SP3, V74). The artifact has to say that it
    was considered and declined, and that C85's trace half is therefore **not** claimed.
    """
    artifact = (
        REPO_ROOT / "docs" / "architecture" / "phase-1" / "06-observability-request-boundary.md"
    ).read_text(encoding="utf-8")
    for recorded in (
        # The choices this slice made.
        "L10",
        "A63",
        "A65",
        "M23.1-MASK",
        "security-event log",
        "SecurityEventCode",
        "OBSERVABILITY_TRUST_EDGE_REQUEST_ID",
        "RQ8",
        "PV6",
        # What it refused to fake, and what stays open with an owner.
        "traceparent",
        "SP3",
        "C85",
        "OpenTelemetry",
        "MIGRATION_CORE_ALLOWLIST",
    ):
        assert recorded in artifact, f"{recorded} is missing from the Slice-6 artifact"


def test_every_security_event_code_is_recorded_in_the_artifact() -> None:
    """The vocabulary is closed by rule, so a member added later is a documented decision.

    A code that exists in the enum and nowhere else is a line an operator will one day see with
    no alert rule and no runbook behind it.
    """
    from core.observability.security_events import SecurityEventCode

    artifact = (
        REPO_ROOT / "docs" / "architecture" / "phase-1" / "06-observability-request-boundary.md"
    ).read_text(encoding="utf-8")
    for code in SecurityEventCode:
        assert code.value in artifact, f"{code.value} is missing from the Slice-6 artifact"


def test_the_repository_status_in_claude_md_is_current() -> None:
    """The instruction file is what every new session reads first.

    Slices 1-5 shipped code, so the sentence claiming none exists was corrected. `CLAUDE.md` is
    a working instruction file, not a frozen artifact, so this is an ordinary edit — unlike the
    identical correction to `PHASE0_STATUS.md`, which stays unedited and is recorded in the
    slice artifact instead.
    """
    claude_md = (REPO_ROOT / "CLAUDE.md").read_text(encoding="utf-8")
    assert "no Django code, package, model, migration, setting or dependency exists yet" not in (
        claude_md
    )
    assert "Phase 1 is in progress" in claude_md


def test_the_chosen_bounds_are_recorded_in_the_artifact() -> None:
    """ADR-0015 says "bounded" and fixes no numbers; the numbers this slice chose are a
    recorded decision, not an implementation detail only `bounds.py` knows."""
    from core.idempotency import bounds

    artifact = (
        REPO_ROOT / "docs" / "architecture" / "phase-1" / "04-command-idempotency.md"
    ).read_text(encoding="utf-8")
    for name in bounds.__all__:
        value = getattr(bounds, name)
        assert name in artifact, f"{name} is missing from the Slice-4 artifact"
        rendered = f"{value:,}".replace(",", " ")
        assert rendered in artifact or str(value) in artifact, (
            f"{name}'s value {value} is not recorded in the Slice-4 artifact"
        )


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
