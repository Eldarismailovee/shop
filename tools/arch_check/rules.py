"""The architecture rules.

Three groups run here:

* **`L*` import-graph rules** whose subject modules do not exist yet, or which
  `import-linter` cannot express without widening the invariant (the `PUBLIC ONLY`,
  `PORT ONLY` and `SPECIAL CASE` cells of Phase 0 item 3 §4). Rules `import-linter`
  already enforces over existing packages are re-checked here so the harness has
  fixture-level regression tests; the two mechanisms agree by construction because both
  encode the same matrix.
* **`A*` / `NF*` shape rules** that are about the *form* of a module rather than an edge
  (item 3 §15.2, item 4 §19.1, item 14 §19).
* **`M<section>` implementation-level matrix checks.** Two `SPECIAL CASE` cells of item 3
  §4 are narrower than any frozen `L`/`A` number covers: `interfaces → core` and
  `interfaces → tasks`. These carry an implementation-only identifier naming the frozen
  section they enforce (`M4.4-CORE`, `M4.4-TASKS`). They are **not** new architecture
  rules and no new `L` number is invented for them.

Adding a later check is one function plus an `@rule` decorator; nothing else changes.
"""

from __future__ import annotations

import ast
import re
from collections.abc import Callable, Iterable, Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import TypeGuard

from core.observability.masking import is_sensitive
from tools.arch_check.model import SourceModule, Violation, discover, under


@dataclass(frozen=True, slots=True)
class Context:
    """What a rule may know about the tree as a whole."""

    root: Path
    #: Every dotted module name discovered under the source families. Lets a rule tell a
    #: module object from a symbol, which `from X import y` alone cannot.
    inventory: frozenset[str]
    #: `module -> {bound name: (source module, original name)}` for every `from X import y`
    #: in the tree. Lets A11 follow an exported symbol back to where it came from, across
    #: any number of internal forwarding modules.
    symbol_sources: dict[str, dict[str, tuple[str, str]]]


Rule = Callable[[SourceModule, Context], Iterable[Violation]]

RULES: list[Rule] = []


def rule(func: Rule) -> Rule:
    RULES.append(func)
    return func


# ---------------------------------------------------------------------------
# Frozen allowlists
# ---------------------------------------------------------------------------

#: `interfaces/*` reaches only the transport/security primitives item 3 §4.4 enumerates.
#: `core.inbox` is on the list for durable webhook ingest (ADR-0004 §7).
INTERFACES_CORE_ALLOWLIST = (
    "core.security",
    "core.dto",
    "core.money",
    "core.public_id",
    "core.observability",
    "core.cache",
    "core.inbox",
)

#: Named by L13 specifically: writing an event or claiming an idempotency key is a
#: decision that belongs below the transport boundary. Reported under L13 rather than
#: under the generic §4.4 allowlist check, because L13 is the frozen rule for these two.
INTERFACES_CORE_FORBIDDEN = ("core.outbox", "core.idempotency")

#: `integrations/*` keeps a narrow pure-Python `core` subset (item 3 §4.5, L10).
INTEGRATIONS_CORE_ALLOWLIST = (
    "core.money",
    "core.public_id",
    "core.dto",
    "core.security.signing",
    "core.observability",
)

#: `application/<a>/ports.py` imports stdlib plus these value primitives only (L15).
PORTS_CORE_ALLOWLIST = ("core.money", "core.public_id", "core.dto")

#: A6 / item 3 §14.1: the *only* import a migration may carry is a stable technical
#: custom field / expression / constraint class that Django's deconstruction requires to
#: remain importable. No such class exists yet, so the allowlist is empty. A future slice
#: that creates one adds its exact module path here, with a regression test, and records
#: the choice in the phase artifact. It is never a route for `core.money`, a DTO, the
#: actor/error primitives, an Outbox/Inbox/idempotency helper or any service.
MIGRATION_CORE_ALLOWLIST: tuple[str, ...] = ()

#: L20/L21 (item 4 §19.5, ADR-0006) additionally open the actor primitive and the
#: structural public-error categories to `domains`, `application`, `interfaces`, `tasks`
#: and `config` — and forbid them to `integrations/*` and `**/migrations/**`. The
#: core-primitives slice chose the physical names, so each rule now reports under its own
#: frozen id rather than under the generic allowlist that already covered it — the same
#: treatment L13 gives `core.outbox`/`core.idempotency` inside the `interfaces` row.
CORE_PUBLIC_CONTRACT_RULES: dict[str, str] = {
    "core.actor": "L20",
    "core.errors": "L21",
}

CORE_PUBLIC_CONTRACT_PRIMITIVES: tuple[str, ...] = tuple(CORE_PUBLIC_CONTRACT_RULES)

#: TX2-TX4 / ADR-0013 §2: `PublicId` and `EventId` share one UUIDv7 generation, parsing
#: and version-validation implementation, and that mechanism is a surface of `core` for
#: nobody. A generic exported utility would let any call site mint a value that fits both
#: semantic types, dissolving the distinction exactly where it matters. Every module
#: outside `core` imports the semantic type it needs.
CORE_UUID_MECHANISM = "core._uuid7"

#: A70/A77: `core.money` carries mechanism vocabulary only. A member named for a business
#: step would smuggle policy into `core` against ADR-0004 §2 and OW4 — and `RoundingPolicy`
#: is where that pressure lands, because every one of these words is a real rounding site
#: whose *policy choice* belongs to the domain that owns the step (RP5, RP6, HR4, SG4).
MONEY_BUSINESS_VOCABULARY = (
    "discount",
    "vat",
    "tax",
    "promo",
    "promotion",
    "loyalty",
    "delivery",
    "price",
    "pricelist",
    "provider",
)

#: A71: `core` holds no currency constant at all — MDL is a fact about Moldova, not a
#: property of the money mechanism (MS5, V93).
_CURRENCY_LITERAL = re.compile(r"[A-Z]{3}")

#: The enqueue-only surface item 3 §4.4 permits an interface to touch on a task.
TASK_ENQUEUE_METHODS = frozenset({"delay", "apply_async"})


def _head(dotted: str) -> str:
    return dotted.split(".")[0]


def _owner(dotted: str) -> str:
    return ".".join(dotted.split(".")[:2])


def _public_contract_rule(target: str) -> str | None:
    """`L20` / `L21` when `target` is one of the two public-contract primitives."""
    for primitive, rule_id in CORE_PUBLIC_CONTRACT_RULES.items():
        if under(target, primitive):
            return rule_id
    return None


def _v(r: str, m: SourceModule, line: int, msg: str) -> Violation:
    return Violation(rule=r, path=m.rel, line=line, message=msg)


def _chain(node: ast.AST) -> list[str] | None:
    """Dotted parts of a pure `a.b.c` Name/Attribute expression, root first."""
    parts: list[str] = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if isinstance(node, ast.Name):
        parts.append(node.id)
        return list(reversed(parts))
    return None


def _is_model_location(m: SourceModule) -> bool:
    """`domains/<x>/models*`, `application/<a>/models*`, or a `core` infrastructure model."""
    if m.family == "core":
        return True
    if m.family not in {"domains", "application"}:
        return False
    return any(segment.removesuffix(".py").startswith("models") for segment in m.rel.split("/")[2:])


# ---------------------------------------------------------------------------
# The dependency matrix (item 3 §4)
# ---------------------------------------------------------------------------

_FAMILIES = frozenset(
    {"core", "domains", "application", "interfaces", "integrations", "tasks", "config", "tests"}
)


@rule
def import_matrix(m: SourceModule, ctx: Context) -> Iterator[Violation]:
    # §4.8: the matrix constrains production code; tests may inspect every package.
    # §14.1 / L19: migration modules are excluded from the layer contracts by path scope
    # and are checked by A6 instead.
    if m.family == "tests" or m.is_migration:
        return
    checker = _MATRIX.get(m.family)
    if checker is None:
        return
    for imp in m.imports:
        if _head(imp.target) not in _FAMILIES:
            continue
        yield from checker(m, imp.target, imp.line)


def _core_row(m: SourceModule, t: str, line: int) -> Iterator[Violation]:
    head = _head(t)
    if head == "core":
        return
    if head == "tests":
        yield _v("L14", m, line, f"production module imports test code: {t}")
    else:
        yield _v("L1", m, line, f"core imports {t}; core knows nothing above or beside it")


def _domains_row(m: SourceModule, t: str, line: int) -> Iterator[Violation]:
    head = _head(t)
    if head == "core":
        return
    if head == "tests":
        yield _v("L14", m, line, f"production module imports test code: {t}")
    elif head == "domains":
        if _owner(t) != m.owner:
            yield _v(
                "L2",
                m,
                line,
                f"{m.owner} imports {t}; domains are mutually invisible, public.py included",
            )
    else:
        yield _v("L3", m, line, f"a domain imports {t}; a domain knows only itself and core")


def _application_row(m: SourceModule, t: str, line: int) -> Iterator[Violation]:
    head = _head(t)
    if head == "core":
        return
    if head == "tests":
        yield _v("L14", m, line, f"production module imports test code: {t}")
    elif head == "domains":
        owner = _owner(t)
        if not under(t, f"{owner}.public"):
            yield _v(
                "L4", m, line, f"application reaches domain internals: {t}; use {owner}.public"
            )
    elif head == "application":
        if _owner(t) != m.owner:
            yield _v(
                "L5", m, line, f"{m.owner} imports {t}; application to application is forbidden"
            )
    elif head == "integrations":
        yield _v(
            "L6",
            m,
            line,
            f"application names a vendor: {t}; declare the capability in {m.owner}/ports.py",
        )
    else:
        yield _v("L6", m, line, f"application imports {t}")


def _interfaces_row(m: SourceModule, t: str, line: int) -> Iterator[Violation]:
    head = _head(t)
    if head == "core":
        if any(under(t, forbidden) for forbidden in INTERFACES_CORE_FORBIDDEN):
            yield _v("L13", m, line, f"interfaces import {t}; that decision lives below transport")
        elif not any(
            under(t, allowed)
            for allowed in INTERFACES_CORE_ALLOWLIST + CORE_PUBLIC_CONTRACT_PRIMITIVES
        ):
            yield _v(
                "M4.4-CORE",
                m,
                line,
                f"interfaces import {t}; item 3 §4.4 opens only "
                f"{', '.join(INTERFACES_CORE_ALLOWLIST)} to a transport boundary",
            )
    elif head == "tests":
        yield _v("L14", m, line, f"production module imports test code: {t}")
    elif head == "domains":
        owner = _owner(t)
        if not under(t, f"{owner}.public"):
            yield _v("L4", m, line, f"interface reaches domain internals: {t}; use {owner}.public")
    elif head == "application":
        owner = _owner(t)
        if not under(t, f"{owner}.public"):
            yield _v(
                "L7", m, line, f"interface reaches application internals: {t}; use {owner}.public"
            )
    elif head == "integrations":
        vendor = _owner(t)
        if not m.dotted.startswith("interfaces.webhooks."):
            yield _v(
                "L12",
                m,
                line,
                f"only interfaces.webhooks.* may reach a provider package; {m.dotted} imports {t}",
            )
        elif under(t, f"{vendor}.outbound"):
            yield _v(
                "L17",
                m,
                line,
                f"inbound boundary reaches the outbound surface: {t}; "
                "only the composition root may",
            )
        elif not under(t, f"{vendor}.protocol"):
            yield _v("L12", m, line, f"webhook imports {t}; the protocol surface only")
    elif head == "config":
        yield _v(
            "L16", m, line, f"entry point imports {t}; it receives dependencies, never locates them"
        )


def _integrations_row(m: SourceModule, t: str, line: int) -> Iterator[Violation]:
    head = _head(t)
    if head == "core":
        primitive = _public_contract_rule(t)
        if primitive is not None:
            yield _v(
                primitive,
                m,
                line,
                f"integrations import {t}; an adapter answers no authorization question and "
                "never raises or interprets a domain public error",
            )
        elif not any(under(t, allowed) for allowed in INTEGRATIONS_CORE_ALLOWLIST):
            yield _v(
                "L10",
                m,
                line,
                f"integrations import {t}; only the pure-Python core subset is open to an adapter",
            )
    elif head == "tests":
        yield _v("L14", m, line, f"production module imports test code: {t}")
    elif head == "application":
        owner = _owner(t)
        if not under(t, f"{owner}.ports"):
            yield _v("L8", m, line, f"adapter imports {t}; the one upward edge is {owner}.ports")
        elif m.owner and under(m.dotted, f"{m.owner}.protocol"):
            yield _v(
                "A13",
                m,
                line,
                f"protocol surface imports a port ({t}); only the outbound surface implements one",
            )
    elif head == "integrations":
        vendor = _owner(t)
        if vendor == "integrations.base":
            return
        if vendor != m.owner:
            yield _v("L9", m, line, f"{m.owner} imports {t}; vendor packages are isolated")
        elif m.owner and under(m.dotted, f"{m.owner}.protocol") and under(t, f"{m.owner}.outbound"):
            yield _v("L18", m, line, f"protocol support imports client code: {t}")
    else:
        yield _v("L8", m, line, f"adapter imports {t}")


def _tasks_row(m: SourceModule, t: str, line: int) -> Iterator[Violation]:
    head = _head(t)
    if head in {"core", "tasks"}:
        return
    if head == "tests":
        yield _v("L14", m, line, f"production module imports test code: {t}")
    elif head == "domains":
        owner = _owner(t)
        if not under(t, f"{owner}.public"):
            yield _v("L4", m, line, f"task reaches domain internals: {t}; use {owner}.public")
    elif head == "application":
        owner = _owner(t)
        if not under(t, f"{owner}.public"):
            yield _v("L7", m, line, f"task reaches application internals: {t}; use {owner}.public")
    elif head == "integrations":
        yield _v(
            "L11",
            m,
            line,
            f"task names a vendor: {t}; the bound port arrives with the handler at bootstrap",
        )
    elif head == "interfaces":
        yield _v("L11", m, line, f"task imports {t}; interfaces and tasks are peer transports")
    elif head == "config":
        yield _v("L16", m, line, f"task imports {t}; a task body is never a composition root")


def _config_row(m: SourceModule, t: str, line: int) -> Iterator[Violation]:
    head = _head(t)
    if head == "tests":
        yield _v("L14", m, line, f"production module imports test code: {t}")
    elif head == "domains":
        owner = _owner(t)
        if not under(t, f"{owner}.public"):
            yield _v("L4", m, line, f"composition root reaches domain internals: {t}")
    elif head == "application":
        owner = _owner(t)
        if not (under(t, f"{owner}.ports") or under(t, f"{owner}.public")):
            yield _v(
                "L7",
                m,
                line,
                f"composition root reaches application internals: {t}; only {owner}.ports "
                f"and {owner}.public are open to it",
            )


_MATRIX: dict[str, Callable[[SourceModule, str, int], Iterator[Violation]]] = {
    "core": _core_row,
    "domains": _domains_row,
    "application": _application_row,
    "interfaces": _interfaces_row,
    "integrations": _integrations_row,
    "tasks": _tasks_row,
    "config": _config_row,
}


# ---------------------------------------------------------------------------
# `interfaces → tasks` — the enqueue-only SPECIAL CASE (item 3 §4.4)
# ---------------------------------------------------------------------------


def _bindings_for_family(tree: ast.Module, family: str) -> dict[str, str]:
    """Local names bound to modules of `family`, mapped to the dotted module behind them.

    Permitted import forms, and what each binds:

        import tasks.notifications                  -> "tasks"       (the family root)
        import tasks.notifications as t             -> "t"
        from tasks import notifications             -> "notifications"
        from tasks.notifications import send_email  -> "send_email"
    """
    bound: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if _head(alias.name) != family:
                    continue
                bound[alias.asname or _head(alias.name)] = alias.name
        elif isinstance(node, ast.ImportFrom):
            base = node.module or ""
            if _head(base) != family:
                continue
            for alias in node.names:
                bound[alias.asname or alias.name] = f"{base}.{alias.name}"
    return bound


@rule
def m44_tasks_are_enqueue_only(m: SourceModule, ctx: Context) -> Iterator[Violation]:
    """`interfaces → tasks` is `task.delay()` / `task.apply_async()` and nothing else.

    Item 3 §4.4 SPECIAL CASE: "Enqueue only. Calling a task function body inline, or
    importing anything else from `tasks/`, is FORBID." No frozen `L`/`A` number covers
    this cell, so the identifier names the section it enforces.
    """
    if m.family != "interfaces":
        return
    bound = _bindings_for_family(m.tree, "tasks")
    if not bound:
        return

    handled: set[int] = set()
    for node in ast.walk(m.tree):
        if not isinstance(node, ast.Call):
            continue
        chain = _chain(node.func)
        if not chain or chain[0] not in bound:
            continue
        for sub in ast.walk(node.func):
            handled.add(id(sub))
        if chain[-1] not in TASK_ENQUEUE_METHODS:
            yield _v(
                "M4.4-TASKS",
                m,
                node.lineno,
                f"{'.'.join(chain)}(...) runs a task body inline; an interface may only "
                f"enqueue ({', '.join(sorted(TASK_ENQUEUE_METHODS))})",
            )

    for node in ast.walk(m.tree):
        if isinstance(node, ast.Name) and node.id in bound and id(node) not in handled:
            yield _v(
                "M4.4-TASKS",
                m,
                node.lineno,
                f"'{node.id}' is used outside an enqueue call; a task is transport, "
                "not an application API",
            )


# ---------------------------------------------------------------------------
# Shape rules
# ---------------------------------------------------------------------------


@rule
def a1_model_definitions(m: SourceModule, ctx: Context) -> Iterator[Violation]:
    """A1 — model-definition capability only where the matrix allows it.

    Ordinary query-expression use (`Q`, `F`, `Exists`, `OuterRef`, `Subquery`) and
    `django.db.transaction` stay legal everywhere: A1 is about *defining* a model, not
    about querying one.
    """
    if m.family == "tests" or m.is_migration or _is_model_location(m):
        return

    model_modules: dict[str, int] = {}  # local name -> line
    model_bases: set[str] = set()  # local names bound to django.db.models.Model
    for node in ast.walk(m.tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if under(alias.name, "django.db.models"):
                    model_modules[alias.asname or _head(alias.name)] = node.lineno
        elif isinstance(node, ast.ImportFrom):
            base = node.module or ""
            for alias in node.names:
                target = f"{base}.{alias.name}"
                if target == "django.db.models":
                    model_modules[alias.asname or alias.name] = node.lineno
                elif base == "django.db.models" and alias.name == "Model":
                    model_bases.add(alias.asname or alias.name)

    for name, line in sorted(model_modules.items(), key=lambda item: item[1]):
        yield _v(
            "A1",
            m,
            line,
            f"'{name}' imports the model-definition module; models belong in "
            "domains/<x>/models*, application/<a>/models* or a core infrastructure model",
        )

    for node in ast.walk(m.tree):
        if not isinstance(node, ast.ClassDef):
            continue
        # Not `base`: that name is already bound to the module string of an earlier
        # `ImportFrom` loop in this function, and rebinding it here hid the expression type.
        for base_expr in node.bases:
            chain = _chain(base_expr)
            if chain is None:
                continue
            is_model = (
                (len(chain) == 1 and chain[0] in model_bases)
                or (len(chain) >= 2 and chain[0] in model_modules and chain[-1] == "Model")
                # `import django.db.models` / `import django` reach the base by full path.
                or chain[-4:] == ["django", "db", "models", "Model"]
            )
            if is_model:
                yield _v(
                    "A1",
                    m,
                    node.lineno,
                    f"class {node.name} defines a Django model outside domains/<x>/models*, "
                    "application/<a>/models* or a core infrastructure model",
                )


@rule
def a3_integrations_are_pure_python(m: SourceModule, ctx: Context) -> Iterator[Violation]:
    """A3 — an adapter must stay importable without the Django app registry."""
    if m.family != "integrations":
        return
    for imp in m.imports:
        if imp.target == "django" or imp.target.startswith("django."):
            yield _v(
                "A3", m, imp.line, f"integrations import {imp.target}; adapters are pure Python"
            )


def _a5_units(tree: ast.Module) -> Iterator[tuple[str, int, list[ast.stmt]]]:
    """The A5 units of a module: each top-level view/task callable or class, plus module scope.

    A class is one unit as frozen — its methods are not separate views. Module scope is a
    unit of its own so a reference outside any callable is still counted, while the import
    statements themselves are not references.
    """
    module_scope: list[ast.stmt] = []
    for node in tree.body:
        if isinstance(node, ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef):
            yield node.name, node.lineno, [node]
        elif not isinstance(node, ast.Import | ast.ImportFrom):
            module_scope.append(node)
    if module_scope:
        yield "<module scope>", module_scope[0].lineno, module_scope


@rule
def a5_one_domain_per_callable(m: SourceModule, ctx: Context) -> Iterator[Violation]:
    """A5 — one `domains.<y>.public` per interface view function/class and per task function.

    A module may legally serve two domains through two independent single-domain
    callables. A request path split across helper modules to combine domains stays a
    review concern (V10), which this rule does not claim to catch.
    """
    if m.family not in {"interfaces", "tasks"}:
        return
    bound = _bindings_for_family(m.tree, "domains")
    if not bound:
        return

    for unit_name, unit_line, nodes in _a5_units(m.tree):
        owners: dict[str, int] = {}
        for root in nodes:
            for node in ast.walk(root):
                # `_chain` answers only for these two, and narrowing here is also what
                # makes `node.lineno` readable below.
                if not isinstance(node, ast.Name | ast.Attribute):
                    continue
                chain = _chain(node)
                if chain is None:
                    continue
                if chain[0] == "domains" and "domains" in bound:
                    # A bare `domains` root carries no domain identity on its own; the
                    # owner is the next segment of the attribute chain.
                    if len(chain) >= 2:
                        owners.setdefault(f"domains.{chain[1]}", node.lineno)
                elif chain[0] in bound:
                    owners.setdefault(_owner(bound[chain[0]]), node.lineno)
        if len(owners) > 1:
            names = ", ".join(sorted(owners))
            yield _v(
                "A5",
                m,
                unit_line,
                f"{unit_name} reaches {len(owners)} domains ({names}); "
                "that flow needs an application use case",
            )


@rule
def a6_migrations_import_no_runtime_code(m: SourceModule, ctx: Context) -> Iterator[Violation]:
    """A6 — a migration imports no runtime module, `core` included (item 3 §14.1, §4.9).

    Django's own migration machinery and stdlib remain available; historical models come
    from `apps.get_model()` inside `RunPython`.
    """
    if not m.is_migration:
        return
    for imp in m.imports:
        head = _head(imp.target)
        if head not in _FAMILIES:
            continue
        primitive = _public_contract_rule(imp.target)
        if primitive is not None:
            yield _v(
                primitive,
                m,
                imp.line,
                f"migration imports {imp.target}; a migration consumes no runtime "
                "authorization subject and carries no business error contract",
            )
            continue
        if head == "core" and any(
            under(imp.target, allowed) for allowed in MIGRATION_CORE_ALLOWLIST
        ):
            continue
        yield _v(
            "A6",
            m,
            imp.line,
            f"migration imports runtime code: {imp.target}; a migration may import only a "
            "deconstruction-stable technical class from the (currently empty) core "
            "allowlist, and reaches historical models through apps.get_model()",
        )


@rule
def a8_empty_package_inits(m: SourceModule, ctx: Context) -> Iterator[Violation]:
    """A8 — `__init__.py` under domains/, application/, integrations/ stays empty (§10)."""
    if not m.is_package_init or m.family not in {"domains", "application", "integrations"}:
        return
    body = list(m.tree.body)
    if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant):
        body = body[1:]
    if body:
        yield _v(
            "A8",
            m,
            body[0].lineno,
            "package __init__.py must stay empty; a re-export shortcut blurs the contract above it",
        )


@rule
def a9_ports_location(m: SourceModule, ctx: Context) -> Iterator[Violation]:
    """A9 — `ports.py` exists only at `application/<a>/ports.py`."""
    parts = m.dotted.split(".")
    if parts[-1] != "ports":
        return
    if not (parts[0] == "application" and len(parts) == 3):
        yield _v("A9", m, 1, "a ports module belongs at application/<a>/ports.py and nowhere else")


@rule
def l15_ports_dependencies(m: SourceModule, ctx: Context) -> Iterator[Violation]:
    """L15 — a port module imports stdlib plus core value primitives only (§6.3)."""
    parts = m.dotted.split(".")
    if not (parts[0] == "application" and len(parts) == 3 and parts[-1] == "ports"):
        return
    for imp in m.imports:
        head = _head(imp.target)
        if head == "core":
            if not any(under(imp.target, allowed) for allowed in PORTS_CORE_ALLOWLIST):
                yield _v(
                    "L15", m, imp.line, f"port imports {imp.target}; core value primitives only"
                )
        elif head in _FAMILIES or head == "django":
            yield _v(
                "L15",
                m,
                imp.line,
                f"port imports {imp.target}; a port is a leaf importable without Django",
            )


def _is_public_facade(m: SourceModule) -> bool:
    return m.dotted.split(".")[-1] == "public" and m.family in {"domains", "application"}


def _imported_names(tree: ast.Module) -> dict[str, int]:
    """Names an import statement binds in the module namespace, with their line."""
    bound: dict[str, int] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                bound.setdefault(alias.asname or _head(alias.name), node.lineno)
        elif isinstance(node, ast.ImportFrom):
            for alias in node.names:
                if alias.name != "*":
                    bound.setdefault(alias.asname or alias.name, node.lineno)
    return bound


def _import_from_base(node: ast.ImportFrom, dotted: str, is_package_init: bool) -> str:
    """The absolute module a `from ... import ...` statement reads from."""
    base = node.module or ""
    if not node.level:
        return base
    parts = dotted.split(".")
    package = parts if is_package_init else parts[:-1]
    if node.level > 1:
        package = package[: -(node.level - 1)]
    return ".".join([*package, base] if base else package)


def symbol_bindings(m: SourceModule) -> dict[str, tuple[str, str]]:
    """Names this module imports, mapped to the `(module, name)` they came from."""
    bound: dict[str, tuple[str, str]] = {}
    for node in ast.walk(m.tree):
        if not isinstance(node, ast.ImportFrom):
            continue
        base = _import_from_base(node, m.dotted, m.is_package_init)
        if not base:
            continue
        for alias in node.names:
            if alias.name != "*":
                bound[alias.asname or alias.name] = (base, alias.name)
    return bound


#: A module whose name marks it as ORM-owning material (item 3 §12, master `# 4.1`).
ORM_MODULE_PREFIXES = ("models", "managers", "querysets")
ORM_SYMBOL_SUFFIXES = ("QuerySet", "Manager")


def _is_orm_module(dotted: str) -> bool:
    return any(segment.startswith(ORM_MODULE_PREFIXES) for segment in dotted.split("."))


def _orm_provenance(base: str, symbol: str, ctx: Context) -> str | None:
    """Follow `base.symbol` back through repository modules; name the ORM module reached.

    Only the **exported symbol** is followed, never its containing module's other
    dependencies: a selector that internally imports a model still exports a callable.
    The walk stops at the first module outside the repository (Django, stdlib) and at a
    name the source module defines rather than imports — neither can be resolved further
    statically, and neither is guessed to be ORM.
    """
    seen: set[tuple[str, str]] = set()
    module, name = base, symbol
    while (module, name) not in seen:
        if _is_orm_module(module) or name.endswith(ORM_SYMBOL_SUFFIXES):
            return module
        seen.add((module, name))
        following = ctx.symbol_sources.get(module, {}).get(name)
        if following is None or following[0] not in ctx.inventory:
            return None
        module, name = following
    return None  # a cycle resolves to nothing rather than to a guess


@rule
def a11_public_exports_no_orm(m: SourceModule, ctx: Context) -> Iterator[Violation]:
    """A11 — no ORM model, manager or QuerySet crosses `public.py` (item 3 §15.2, §12).

    Provenance, not spelling: an ORM symbol forwarded through one or more internal
    modules is still an ORM export.
    """
    if not _is_public_facade(m):
        return
    for node in ast.walk(m.tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if _is_orm_module(alias.name):
                    yield _v("A11", m, node.lineno, f"public.py imports ORM material: {alias.name}")
        elif isinstance(node, ast.ImportFrom):
            base = _import_from_base(node, m.dotted, m.is_package_init)
            if not base:
                continue
            for alias in node.names:
                if alias.name == "*":
                    if _is_orm_module(base):
                        yield _v(
                            "A11", m, node.lineno, f"public.py re-exports ORM material: {base}"
                        )
                    continue
                origin = _orm_provenance(base, alias.name, ctx)
                if origin is None:
                    continue
                route = "" if origin == base else f" (reached through {base})"
                yield _v(
                    "A11",
                    m,
                    node.lineno,
                    f"public.py exports ORM material: '{alias.name}' originates in {origin}{route}",
                )


@rule
def a14_public_facade_shape(m: SourceModule, ctx: Context) -> Iterator[Violation]:
    """A14 — the `public.py` façade shape (item 4 §4.1 S1-S6, §19.1).

    No `class`/`def`, no wildcard import, no aliasing, no module re-export, no
    conditional/`TYPE_CHECKING` import, no module-level `__getattr__`.
    """
    if not _is_public_facade(m):
        return

    for node in ast.walk(m.tree):
        if isinstance(node, ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef):
            kind = "class" if isinstance(node, ast.ClassDef) else "function"
            detail = (
                "module-level __getattr__ makes the contract unreadable statically (S6)"
                if node.name == "__getattr__"
                else f"public.py defines a {kind}; implementations live in internal modules (S1)"
            )
            yield _v("A14", m, node.lineno, detail)

    for node in ast.walk(m.tree):
        if isinstance(node, ast.Import):
            # `import x` binds a module object whatever `x` is — internal, `core`, stdlib
            # or third-party. A façade imports names (S3).
            names = ", ".join(alias.asname or alias.name for alias in node.names)
            yield _v(
                "A14",
                m,
                node.lineno,
                f"public.py imports the module object(s) {names}; only names cross (S3)",
            )
            continue
        if not isinstance(node, ast.ImportFrom):
            continue
        if any(alias.name == "*" for alias in node.names):
            yield _v("A14", m, node.lineno, "wildcard import in public.py (S2)")
        if any(alias.asname for alias in node.names):
            yield _v(
                "A14",
                m,
                node.lineno,
                "aliased import in public.py; the public name is the internal name (S4)",
            )
        base = _import_from_base(node, m.dotted, m.is_package_init)
        for alias in node.names:
            if alias.name != "*" and f"{base}.{alias.name}" in ctx.inventory:
                yield _v(
                    "A14",
                    m,
                    node.lineno,
                    f"public.py re-exports the module object {base}.{alias.name}; "
                    "only names cross (S3)",
                )

    for node in ast.walk(m.tree):
        if isinstance(node, ast.If | ast.Try) and any(
            isinstance(inner, ast.Import | ast.ImportFrom) for inner in ast.walk(node)
        ):
            yield _v("A14", m, node.lineno, "conditional or TYPE_CHECKING import in public.py (S6)")


def _assigns_all(node: ast.AST) -> TypeGuard[ast.Assign | ast.AnnAssign | ast.AugAssign]:
    """True for any statement that binds or rebinds `__all__`.

    Narrowing to the three assignment statements is what lets callers read `.lineno`:
    the bare `ast.AST` that `ast.walk` yields does not declare position attributes.
    """
    if isinstance(node, ast.Assign):
        return any(isinstance(t, ast.Name) and t.id == "__all__" for t in node.targets)
    if isinstance(node, ast.AnnAssign | ast.AugAssign):
        return isinstance(node.target, ast.Name) and node.target.id == "__all__"
    return False


@rule
def a15_public_all_matches_exports(m: SourceModule, ctx: Context) -> Iterator[Violation]:
    """A15 — exactly one explicit `__all__` tuple, matching the imported names (S5).

    One authoritative assignment: a second `Assign`, an `AnnAssign` redefinition or an
    `AugAssign` extension would make the runtime contract differ from the one a reader
    (or this checker) sees first.
    """
    if not _is_public_facade(m):
        return

    assignments = [node for node in ast.walk(m.tree) if _assigns_all(node)]
    if not assignments:
        yield _v("A15", m, 1, "public.py declares no __all__")
        return
    if len(assignments) > 1:
        lines = ", ".join(str(node.lineno) for node in assignments)
        yield _v(
            "A15",
            m,
            assignments[1].lineno,
            f"__all__ is assigned {len(assignments)} times (lines {lines}); "
            "exactly one authoritative declaration is the contract",
        )
        return

    assignment = assignments[0]
    if isinstance(assignment, ast.AugAssign):
        yield _v(
            "A15", m, assignment.lineno, "__all__ is extended in place; declare it once, explicitly"
        )
        return

    value = assignment.value
    if not isinstance(value, ast.Tuple):
        yield _v("A15", m, assignment.lineno, "__all__ must be a tuple of string literals")
        return

    declared: list[str] = []
    for element in value.elts:
        if isinstance(element, ast.Constant) and isinstance(element.value, str):
            declared.append(element.value)
        else:
            yield _v("A15", m, assignment.lineno, "__all__ must contain string literals only")
            return

    duplicates = sorted({name for name in declared if declared.count(name) > 1})
    if duplicates:
        yield _v("A15", m, assignment.lineno, f"__all__ repeats: {', '.join(duplicates)}")
        return

    imported = set(_imported_names(m.tree))
    missing = sorted(imported - set(declared))
    extra = sorted(set(declared) - imported)
    if missing:
        yield _v(
            "A15",
            m,
            assignment.lineno,
            f"imported but not exported: {', '.join(missing)}; __all__ matches the imports exactly",
        )
    if extra:
        yield _v(
            "A15",
            m,
            assignment.lineno,
            f"exported but not imported: {', '.join(extra)}",
        )


@rule
def a12_no_dynamic_resolution(m: SourceModule, ctx: Context) -> Iterator[Violation]:
    """A12 — no service-locator / dynamic-import shape in production code."""
    if m.family == "tests":
        return
    for node in ast.walk(m.tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        name = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", "")
        if name in {"import_module", "__import__"}:
            yield _v(
                "A12",
                m,
                node.lineno,
                f"dynamic import ({name}) resolves a dependency by name; dependencies are injected",
            )


@rule
def nf7_no_optional_import_fallback(m: SourceModule, ctx: Context) -> Iterator[Violation]:
    """NF7 — no `try: import ... except ImportError` capability fallback (item 14 §19)."""
    if m.family == "tests":
        return
    for node in ast.walk(m.tree):
        if not isinstance(node, ast.Try):
            continue
        if not any(isinstance(stmt, ast.Import | ast.ImportFrom) for stmt in ast.walk(node)):
            continue
        for handler in node.handlers:
            names = _exception_names(handler.type)
            if names & {"ImportError", "ModuleNotFoundError"}:
                yield _v(
                    "NF7",
                    m,
                    node.lineno,
                    "optional-import fallback; absence of a LATER module is the absence of a call",
                )


def _exception_names(node: ast.expr | None) -> set[str]:
    if node is None:
        return {"ImportError", "ModuleNotFoundError"}  # bare `except:` swallows them too
    collected: set[str] = set()
    for child in ast.walk(node):
        if isinstance(child, ast.Name):
            collected.add(child.id)
        elif isinstance(child, ast.Attribute):
            collected.add(child.attr)
    return collected


@rule
def nf8_no_installed_apps_probing(m: SourceModule, ctx: Context) -> Iterator[Violation]:
    """NF8 — no runtime probing for whether a module is installed (item 14 §19)."""
    if m.family in {"tests", "config"}:
        return
    for node in ast.walk(m.tree):
        if isinstance(node, ast.Attribute) and node.attr == "INSTALLED_APPS":
            yield _v(
                "NF8", m, node.lineno, "runtime probing of INSTALLED_APPS; absent means absent"
            )
        elif isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Attribute) and func.attr in {"is_installed", "get_app_config"}:
                yield _v(
                    "NF8",
                    m,
                    node.lineno,
                    "runtime probing of the app registry; "
                    "behaviour must not change on package presence",
                )


@rule
def a10_single_composition_root(m: SourceModule, ctx: Context) -> Iterator[Violation]:
    """A10 — only `config/` may know both an adapter and the port it implements."""
    if m.family in {"config", "tests"}:
        return
    # An adapter importing its own vendor package (or the shared `integrations.base`
    # mechanism) alongside the port it implements is the frozen design, not a binding.
    own = (m.owner, "integrations.base") if m.family == "integrations" else ()
    adapter = next(
        (
            i
            for i in m.imports
            if _head(i.target) == "integrations" and not any(under(i.target, o) for o in own if o)
        ),
        None,
    )
    port = next(
        (
            i
            for i in m.imports
            if _head(i.target) == "application" and under(i.target, f"{_owner(i.target)}.ports")
        ),
        None,
    )
    if adapter and port:
        yield _v(
            "A10",
            m,
            min(adapter.line, port.line),
            f"binds {adapter.target} to {port.target} outside config/; "
            "there is one composition root",
        )


# ---------------------------------------------------------------------------
# The `core` primitives (item 11, ADR-0012, ADR-0013)
#
# These rules exist because their subjects now physically exist. Each guards a
# regression that ordinary review is unreliable against: a one-word ordering flag,
# a business noun that drags policy into `core`, a hard-coded currency, and a
# generic UUID utility that would dissolve the PublicId/EventId distinction.
# ---------------------------------------------------------------------------

MONEY_MODULE = "core.money"

_CAMEL_BOUNDARY = re.compile(r"(?<=[a-z0-9])(?=[A-Z])")
_BUSINESS_WORD = re.compile(
    r"(?:\A|_)(" + "|".join(MONEY_BUSINESS_VOCABULARY) + r")(?:_|\Z)",
)


def _business_word(name: str) -> str | None:
    """The business noun a defined name carries, if any — segment-wise, not substring-wise.

    `private` does not contain the currency word `vat`, and `VatRate` does contain it, so
    the name is split on underscores and on camel-case boundaries before matching.
    """
    found = _BUSINESS_WORD.search(_CAMEL_BOUNDARY.sub("_", name).lower())
    return found.group(1) if found else None


def _defined_names(roots: Iterable[ast.AST]) -> Iterator[tuple[str, int]]:
    """Every name these subtrees *define*: classes, functions, parameters, assignments."""
    for root in roots:
        for node in ast.walk(root):
            if isinstance(node, ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef):
                yield node.name, node.lineno
                if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                    args = node.args
                    for arg in (*args.posonlyargs, *args.args, *args.kwonlyargs):
                        yield arg.arg, arg.lineno
                    for optional in (args.vararg, args.kwarg):
                        if optional is not None:
                            yield optional.arg, optional.lineno
            elif isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        yield target.id, node.lineno
            elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
                yield node.target.id, node.lineno


def _rounding_policy(tree: ast.Module) -> ast.ClassDef | None:
    return next(
        (n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "RoundingPolicy"),
        None,
    )


@rule
def a70_no_business_vocabulary_in_money(m: SourceModule, ctx: Context) -> Iterator[Violation]:
    """A70 — `core.money` declares no business vocabulary (OW4, SG4, HR4).

    `core.Money` knows no discount, VAT, promotion, delivery, loyalty or price-list rule
    and no sign or range policy; those live with the module that owns the decision. A
    member here named after one of them is how policy gets into `core` (ADR-0004 §2).
    The sign/range half of the rule stays a review shape (V91) — a helper named
    `assert_non_negative` is caught by reading, not by a word list.
    """
    if m.dotted != MONEY_MODULE:
        return
    policy = _rounding_policy(m.tree)  # A77's subject, reported under its own id
    for name, line in _defined_names(n for n in m.tree.body if n is not policy):
        word = _business_word(name)
        if word is not None:
            yield _v(
                "A70",
                m,
                line,
                f"'{name}' names the business step '{word}'; core.money owns the arithmetic, "
                "never which business rule applies it",
            )


@rule
def a77_rounding_policy_members_are_arithmetic(
    m: SourceModule, ctx: Context
) -> Iterator[Violation]:
    """A77 — a `RoundingPolicy` member names an arithmetic rule, never a business step (RP5).

    `PRICE_ROUNDING`, `VAT_ROUNDING`, `PROMO_ROUNDING` and their kin are forbidden members:
    which policy a business step uses is that step's owner's decision (RP6), and a member
    named for the step would make `core` the place that decides.
    """
    if m.dotted != MONEY_MODULE:
        return
    policy = _rounding_policy(m.tree)
    if policy is None:
        return
    for name, line in _defined_names([policy]):
        word = _business_word(name)
        if word is not None:
            yield _v(
                "A77",
                m,
                line,
                f"RoundingPolicy member '{name}' names the business step '{word}'; a policy "
                "member is an arithmetic rule",
            )


@rule
def a71_no_currency_literal_in_core(m: SourceModule, ctx: Context) -> Iterator[Violation]:
    """A71 — `core` holds no currency constant (MS5, V93).

    `100.00 MDL` is an example, not a definition. A currency literal in the primitive is
    how a multi-currency type acquires a single-currency default.
    """
    if m.family != "core":
        return
    for node in ast.walk(m.tree):
        if (
            isinstance(node, ast.Constant)
            and isinstance(node.value, str)
            and _CURRENCY_LITERAL.fullmatch(node.value)
        ):
            yield _v(
                "A71",
                m,
                node.lineno,
                f"currency literal {node.value!r} in core; which currencies the platform "
                "trades in is an owning module's policy, never a core constant",
            )


@rule
def a75_no_generated_money_ordering(m: SourceModule, ctx: Context) -> Iterator[Violation]:
    """A75 — the money value type declares no automatic ordering (OD3, ADR-0012).

    A dataclass-generated ordering over `(minor, currency)` makes
    `Money(100, "EUR") < Money(200, "USD")` legal and true, comparing one euro against two
    dollars as though the codes were commensurable — and makes it true *silently*, at every
    `sorted()`, `min()`, `max()`, `heapq` and `bisect` call in the platform. This is a
    dedicated check because it is a one-word regression no ordinary review notices. That
    the four comparisons the type does define are currency-guarded is asserted
    behaviourally instead (C103), in both operand orders and through `min`/`max`/`sorted`.
    """
    if m.dotted != MONEY_MODULE:
        return
    for node in ast.walk(m.tree):
        if not isinstance(node, ast.ClassDef):
            continue
        for decorator in node.decorator_list:
            if not isinstance(decorator, ast.Call):
                continue
            chain = _chain(decorator.func)
            if not chain or chain[-1] != "dataclass":
                continue
            for keyword in decorator.keywords:
                if keyword.arg != "order":
                    continue
                disabled = isinstance(keyword.value, ast.Constant) and keyword.value.value is False
                if not disabled:
                    yield _v(
                        "A75",
                        m,
                        decorator.lineno,
                        f"class {node.name} generates ordering from its field tuple; money "
                        "ordering is currency-scoped and written explicitly",
                    )


@rule
def a82_uuid_mechanism_is_core_internal(m: SourceModule, ctx: Context) -> Iterator[Violation]:
    """A82 (import half) — the shared UUIDv7 mechanism is exported to no package family.

    TX3/TX4: a generic `new_uuid7()`/`parse_uuid7()` pair reachable from outside `core`
    would let every call site produce a value that fits *both* `PublicId` and `EventId`,
    and the distinction would evaporate at exactly the boundaries where it matters. Each
    module imports the semantic type it needs.

    A82's other half — no bare `uuid.UUID` annotation in a locator position — waits for the
    first public signature or DTO to annotate, and is recorded as deferred.
    """
    if m.family in {"core", "tests"}:
        return
    for imp in m.imports:
        if under(imp.target, CORE_UUID_MECHANISM):
            yield _v(
                "A82",
                m,
                imp.line,
                f"{imp.target} is the core-internal UUIDv7 mechanism; import the semantic "
                "type (core.public_id.PublicId or core.events.identity.EventId) instead",
            )


# ---------------------------------------------------------------------------
# Command idempotency (ADR-0015, item 15 §13.1 A129-A138)
# ---------------------------------------------------------------------------

#: A129: the claim is a PostgreSQL write. No Redis command, in-process lock, file lock or
#: advisory-lock-only path may stand in for it, and no command may be correct only while
#: Redis is warm. Redis may damp bursts *somewhere else*; it may not appear in the claim
#: mechanism, so the rule is stated as an import ban over the whole submodule.
_IDEMPOTENCY_FORBIDDEN_IMPORTS = (
    "redis",
    "django_redis",
    "memcache",
    "pymemcache",
    "threading",
    "multiprocessing",
    "filelock",
    "core.cache",
    "django.core.cache",
)

#: A129: nor by another spelling of the same idea.
_IDEMPOTENCY_FORBIDDEN_CALLS = (
    "pg_advisory_lock",
    "pg_advisory_xact_lock",
    "pg_try_advisory_lock",
)

#: A131: the claim commits with the effect it protects. An independent commit, an
#: autocommit toggle or a post-commit hook would each recreate the separately committed
#: `processing` row ADR-0015 §6 forbids by name.
_IDEMPOTENCY_FORBIDDEN_TRANSACTION_CALLS = (
    "commit",
    "rollback",
    "set_autocommit",
    "on_commit",
    "get_autocommit",
)

#: A132: no durable `processing`/`failed` state. The surest way to guarantee a column has
#: exactly one legal committed value is for the column not to exist.
_IDEMPOTENCY_FORBIDDEN_FIELDS = ("state", "status", "stage", "phase", "attempts", "retries")

#: A134/A135: neither the fingerprint material nor the stored result may carry credential,
#: session or transport material. Matched segment-wise so that an ordinary word containing
#: one of these as a substring does not read as a violation.
_IDEMPOTENCY_FORBIDDEN_VOCABULARY = frozenset(
    {
        "cookie",
        "cookies",
        "csrf",
        "credential",
        "credentials",
        "password",
        "secret",
        "token",
        "bearer",
        "authorization",
        "session",
        "header",
        "headers",
    }
)

#: A136: the one heavy column, which the claim path never selects.
_IDEMPOTENCY_HEAVY_COLUMN = "result_detail"

_WORD = re.compile(r"[a-z0-9]+")


def _is_idempotency(m: SourceModule) -> bool:
    return under(m.dotted, "core.idempotency") and not m.is_migration


def _assigned_field_names(tree: ast.Module) -> Iterator[tuple[str, int]]:
    """Class-body `name = models.X(...)` assignments, i.e. declared columns."""
    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue
        for statement in node.body:
            if not isinstance(statement, ast.Assign) or not isinstance(statement.value, ast.Call):
                continue
            chain = _chain(statement.value.func)
            if chain is None or "models" not in chain:
                continue
            for target in statement.targets:
                if isinstance(target, ast.Name):
                    yield target.id, statement.lineno


@rule
def a129_claim_is_a_postgresql_write(m: SourceModule, ctx: Context) -> Iterator[Violation]:
    """A129 — no Redis, cache, in-process lock or advisory-lock path is the claim mechanism.

    ADR-0015 §2: the durable PostgreSQL row is the only thing that decides whether a command
    executes twice, whether a retry replays, whether a request is a conflict and who owns a
    key. A Redis miss, flush, eviction, outage or cold start changes none of those four
    answers, which is only true if no such call exists here at all.
    """
    if not _is_idempotency(m):
        return
    for imp in m.imports:
        if any(under(imp.target, banned) for banned in _IDEMPOTENCY_FORBIDDEN_IMPORTS):
            yield _v(
                "A129",
                m,
                imp.line,
                f"the idempotency claim imports {imp.target}; the claim is a PostgreSQL "
                "write and nothing else stands in for it",
            )
    for node in ast.walk(m.tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            for banned in _IDEMPOTENCY_FORBIDDEN_CALLS:
                if banned in node.value:
                    yield _v(
                        "A129",
                        m,
                        node.lineno,
                        f"{banned} appears in the claim mechanism; contenders serialize on "
                        "the durable uniqueness constraint, not on an advisory lock",
                    )


@rule
def a130_unique_scope_key_constraint(m: SourceModule, ctx: Context) -> Iterator[Violation]:
    """A130 — a `UNIQUE (scope, key)` database constraint exists on the idempotency model.

    ADR-0015 §3 / master `# 5.4`. Declared in `Meta.constraints`, not as a `unique_together`
    afterthought and not as a Python-side check: `Model.clean()` does not run on
    `bulk_create`, on raw SQL, or on a concurrent writer.
    """
    if not _is_idempotency(m) or m.basename != "models.py":
        return
    for node in ast.walk(m.tree):
        if not isinstance(node, ast.Call):
            continue
        chain = _chain(node.func)
        if chain is None or chain[-1] != "UniqueConstraint":
            continue
        for keyword in node.keywords:
            if keyword.arg != "fields":
                continue
            names = {
                element.value
                for element in getattr(keyword.value, "elts", [])
                if isinstance(element, ast.Constant)
            }
            if names == {"scope", "key"}:
                return
    yield _v(
        "A130",
        m,
        1,
        "the idempotency model declares no UniqueConstraint over ('scope', 'key'); that "
        "constraint is the mechanism, not an optimisation",
    )


@rule
def a131_claim_commits_with_its_effect(m: SourceModule, ctx: Context) -> Iterator[Violation]:
    """A131 — no idempotency write is committed outside the transaction performing the effect.

    ADR-0015 §6 forbids the two-transaction pattern by name: no separate
    `atomic(durable=True)`, no autocommit write, no `on_commit` claim. Nesting *is* allowed —
    a savepoint is an implementation detail of one semantic command (item 4 §12) — so this
    rule bans the durable/independent spellings, not `atomic()` itself.
    """
    if not _is_idempotency(m):
        return
    for node in ast.walk(m.tree):
        if not isinstance(node, ast.Call):
            continue
        chain = _chain(node.func)
        if chain is None:
            continue
        if chain[-1] == "atomic":
            for keyword in node.keywords:
                if keyword.arg == "durable" and not (
                    isinstance(keyword.value, ast.Constant) and keyword.value.value is False
                ):
                    yield _v(
                        "A131",
                        m,
                        node.lineno,
                        "atomic(durable=True) makes the claim its own outermost "
                        "transaction; the claim commits with the effect it protects",
                    )
        if chain[-1] in _IDEMPOTENCY_FORBIDDEN_TRANSACTION_CALLS and "transaction" in chain:
            yield _v(
                "A131",
                m,
                node.lineno,
                f"transaction.{chain[-1]}() in the claim mechanism; the outer transaction "
                "owns every durable write and its commit boundary",
            )


@rule
def a132_no_durable_lifecycle_state(m: SourceModule, ctx: Context) -> Iterator[Violation]:
    """A132 — the generic mechanism writes no durable `processing` or `failed` value.

    ADR-0015 §6 refines master `# 5.2`'s `state` sketch: `processing` may exist only as
    uncommitted, transaction-local state, and no durable `failed` state is required — so a
    transient fault can never reserve a key forever. A column with exactly one legal
    committed value is best expressed as no column.
    """
    if not _is_idempotency(m) or m.basename != "models.py":
        return
    for name, line in _assigned_field_names(m.tree):
        if name in _IDEMPOTENCY_FORBIDDEN_FIELDS:
            yield _v(
                "A132",
                m,
                line,
                f"the idempotency model declares a '{name}' column; the existence of a "
                "committed row is the completed state, and no other is durable",
            )


@rule
def a133_scope_comes_from_the_platform_set(m: SourceModule, ctx: Context) -> Iterator[Violation]:
    """A133 — `scope` values come from a platform-owned constant set, never from request data.

    Enforced structurally rather than by inspecting call sites: the only way to obtain a
    `CommandScope` is `ScopeRegistry.resolve`, which refuses an unregistered name, and the
    claim path must go through it. A caller that invents a scope therefore cannot claim.
    """
    if not _is_idempotency(m) or m.basename != "claim.py":
        return
    resolves = any(
        isinstance(node, ast.Call)
        and (chain := _chain(node.func)) is not None
        and chain[-2:] == ["COMMAND_SCOPES", "resolve"]
        for node in ast.walk(m.tree)
    )
    if not resolves:
        yield _v(
            "A133",
            m,
            1,
            "the claim path does not resolve its scope through COMMAND_SCOPES.resolve(); a "
            "scope is platform-owned and an unregistered one must not be claimable",
        )


@rule
def a134_a135_no_credential_material(m: SourceModule, ctx: Context) -> Iterator[Violation]:
    """A134 / A135 (vocabulary half) — no credential, session or transport material here.

    A134: fingerprint material is a canonicalized semantic structure and carries no
    credential, token, cookie or CSRF value. A135: stored result material is bounded and
    carries none of those either, nor arbitrary request headers.

    This is the *vocabulary* half, matched segment-wise so `is_fingerprint` does not read as
    a violation. The behavioural half — that a given scope's material genuinely excludes such
    values — belongs to each scope's own contract and to review: no static rule can look at a
    string and know it is a bearer token.
    """
    if not _is_idempotency(m):
        return
    reported: set[int] = set()
    for node in ast.walk(m.tree):
        name: str | None = None
        if isinstance(node, ast.Name):
            name = node.id
        elif isinstance(node, ast.Attribute):
            name = node.attr
        elif isinstance(node, ast.arg):
            name = node.arg
        elif isinstance(node, ast.FunctionDef | ast.ClassDef):
            name = node.name
        else:
            continue
        line = node.lineno
        words = set(_WORD.findall(name.lower()))
        offending = sorted(words & _IDEMPOTENCY_FORBIDDEN_VOCABULARY)
        if offending and line not in reported:
            reported.add(line)
            rule_id = "A135" if m.basename in {"models.py", "outcomes.py"} else "A134"
            yield _v(
                rule_id,
                m,
                line,
                f"'{name}' carries {offending[0]} vocabulary; neither the fingerprint nor "
                "the stored result holds credential, session or transport material",
            )


@rule
def a136_heavy_column_is_off_the_claim_path(m: SourceModule, ctx: Context) -> Iterator[Violation]:
    """A136 — no heavy result column is selected while claiming (ADR-0015 §9, master `# 20.5`).

    The claim path names its columns explicitly and the heavy one is absent from that list,
    so it is loaded only when a replay actually needs it.
    """
    if not _is_idempotency(m) or m.basename != "claim.py":
        return
    for node in ast.walk(m.tree):
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if not isinstance(target, ast.Name) or target.id != "_CLAIM_PATH_FIELDS":
                continue
            selected = {
                element.value
                for element in getattr(node.value, "elts", [])
                if isinstance(element, ast.Constant)
            }
            if not selected:
                yield _v(
                    "A136",
                    m,
                    node.lineno,
                    "the claim path selects no explicit column list; an unshaped read pulls "
                    "the heavy result column on every claim",
                )
            elif _IDEMPOTENCY_HEAVY_COLUMN in selected:
                yield _v(
                    "A136",
                    m,
                    node.lineno,
                    f"the claim path selects {_IDEMPOTENCY_HEAVY_COLUMN}; the heavy column "
                    "is read only when a replay needs it",
                )
            return
    yield _v(
        "A136",
        m,
        1,
        "the claim path declares no _CLAIM_PATH_FIELDS column list, so nothing keeps the "
        "heavy result column off it",
    )


@rule
def a137_event_identity_is_not_a_command_key(m: SourceModule, ctx: Context) -> Iterator[Violation]:
    """A137 — no `EventId` is used as a command idempotency key.

    ADR-0015 §1: these are two of the five separated duplicate-protection mechanisms. A
    message delivery is deduplicated by the Inbox against `EventId`; a command invocation is
    protected by `(scope, key)`. Neither is derivable from the other, and no `IdempotencyKey`
    row is created to deduplicate a delivery.
    """
    if not _is_idempotency(m):
        return
    for imp in m.imports:
        if under(imp.target, "core.events"):
            yield _v(
                "A137",
                m,
                imp.line,
                f"the command-idempotency mechanism imports {imp.target}; message-delivery "
                "identity and command identity are separate mechanisms (ADR-0015 §1)",
            )


@rule
def a138_ownership_is_resolved_before_result(m: SourceModule, ctx: Context) -> Iterator[Violation]:
    """A138 (structural half) — no replay path can bypass the owning-principal check.

    ADR-0015 §4: a different principal presenting an existing key receives neither the
    outcome nor confirmation that the key exists. Structurally: the refusal outcome carries
    no fields at all, so nothing about the row can leak through it, and the replay outcome is
    built in exactly one place. The behavioural half — that ownership is compared *before*
    the fingerprint, and that the refusal returns no data — is asserted by test.
    """
    if not _is_idempotency(m) or m.basename != "claim.py":
        return
    builders = [
        node.lineno
        for node in ast.walk(m.tree)
        if isinstance(node, ast.Call)
        and (chain := _chain(node.func)) is not None
        and chain[-1] == "SemanticResult"
    ]
    if len(builders) > 1:
        for line in builders:
            yield _v(
                "A138",
                m,
                line,
                "the replayed result is built in more than one place; a single construction "
                "site is what keeps every replay behind the ownership check",
            )


# ---------------------------------------------------------------------------
# The durable async spine (item 8, item 9, item 10, ADR-0010, ADR-0011)
#
# These rules exist because their subjects now physically exist. Each guards a
# regression that ordinary review is unreliable against: a fifth trace field or a
# metadata bag creeping in beside the closed four; a consumer writing its own span
# into a message's slot; a back-fill rewriting durable history; and a terminal record
# that cannot say which domain and which consumer it belongs to.
#
# Their *behavioural* halves — that a real producer captures the right state, that a
# real relay never rewrites a row, that a real consumer's replay preserves identity —
# need a producer, a consumer and a relay, none of which exists in this slice. Those
# obligations are recorded as deferred in the phase artifact rather than claimed here.
# ---------------------------------------------------------------------------

#: The four TCE slots (item 10 FS1, FS2). Exactly these, on every durable message record.
TCE_FIELDS: tuple[str, ...] = (
    "trace_id",
    "producer_span_id",
    "request_id",
    "causation_event_id",
)

#: Item 10 CN8: a *delivery's own* operational trace, per attempt, kept in storage distinct
#: from the message's copy. Permitted precisely because it is not the message's TCE, and
#: named here so A60 does not mistake it for a fifth envelope field.
DELIVERY_TRACE_FIELDS: tuple[str, ...] = ("processing_trace_id", "processing_span_id")

#: A60 / FS3: the extension point item 8 reserved was spent on a closed set, so none of these
#: may appear beside it — in any spelling, including the "one JSON column for future use" that
#: every metadata bag is eventually justified as.
FORBIDDEN_ENVELOPE_FIELDS: frozenset[str] = frozenset(
    {
        "meta",
        "metadata",
        "extra",
        "context",
        "attributes",
        "headers",
        "tags",
        "annotations",
        "baggage",
        "tracestate",
        "traceparent",
        "correlation_id",
        "causation_id",
        "span_id",
        "parent_span_id",
    }
)

#: A66: written once at message creation and never rewritten — not by a relay, a retry, a
#: redelivery, a replay, a reconciliation, an admin action or a management command. The TCE
#: fields are write-once too, but a violation there is reported under A62, which is the
#: narrower and more specific rule.
WRITE_ONCE_MESSAGE_FIELDS: tuple[str, ...] = (
    "event_id",
    "event_type",
    "schema_version",
    "occurred_at",
    "payload",
    "payload_fingerprint",
    "first_seen_at",
)

#: A56: a terminal record is domain-scoped and names the consumer delivery that failed. A
#: shared bucket without these discriminators is the global `dead_letters` table item 9 TI2
#: forbids: a poison ERP batch must not sit undiscriminated beside a payment failure.
TERMINAL_DISCRIMINATORS: tuple[str, ...] = ("terminal_kind", "failure_domain", "consumer")

MESSAGE_PACKAGES = ("core.outbox", "core.inbox")

CODEC_MODULE = "core.events.codec"


def _is_message_machinery(m: SourceModule) -> bool:
    return any(under(m.dotted, package) for package in MESSAGE_PACKAGES) and not m.is_migration


def _update_calls(tree: ast.Module) -> Iterator[tuple[ast.Call, set[str]]]:
    """Every `<...>.update(**kwargs)` call, with the column names it assigns."""
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if not isinstance(func, ast.Attribute) or func.attr != "update":
            continue
        yield node, {kw.arg for kw in node.keywords if kw.arg is not None}


@rule
def a60_the_tce_is_closed(m: SourceModule, ctx: Context) -> Iterator[Violation]:
    """A60 — exactly four TCE fields exist on a durable message record, and no bag beside them.

    Item 8 EN6 reserved **one** extension point and item 10 spent it on a closed named set
    (FS1, FS2). There is no second extension point, so a fifth trace field does not exist and
    a metadata bag cannot arrive disguised as a convenience: every precise meaning one could
    carry is already carried by one of the eight envelope slots, and a bag is where routing,
    attempt counters and — eventually — a value some handler branches on end up.
    """
    if not _is_message_machinery(m) or m.basename != "models.py":
        return
    for name, line in _assigned_field_names(m.tree):
        if name in FORBIDDEN_ENVELOPE_FIELDS:
            yield _v(
                "A60",
                m,
                line,
                f"a '{name}' column beside the envelope; the TCE is closed at "
                f"{', '.join(TCE_FIELDS)}, and item 8 reserved no second extension point",
            )


@rule
def a61_no_tce_name_in_a_payload(m: SourceModule, ctx: Context) -> Iterator[Violation]:
    """A61 (codec half) — the payload gate rejects every envelope and trace slot name.

    The envelope is not payload (EV3, item 8 EN11). A payload field named `trace_id` is how a
    handler ends up branching on trace metadata (FW4, A63), and a payload field named
    `event_id` is how a second, unversioned envelope grows beside the frozen one.

    No registered payload contract module exists yet, so the *static* half of A61 — reading
    declared contract fields — has no subject. What does exist is the single gate every
    payload passes, and this rule keeps that gate's closed list from being quietly narrowed:
    deleting a name from `RESERVED_PAYLOAD_FIELDS` would remove the protection with nothing
    else failing. The obligation to check declared contracts is recorded as deferred.
    """
    if m.dotted != CODEC_MODULE:
        return
    for node in ast.walk(m.tree):
        if not isinstance(node, ast.Assign):
            continue
        if not any(
            isinstance(t, ast.Name) and t.id == "RESERVED_PAYLOAD_FIELDS" for t in node.targets
        ):
            continue
        declared = {
            element.value
            for element in ast.walk(node.value)
            if isinstance(element, ast.Constant) and isinstance(element.value, str)
        }
        missing = sorted(set(TCE_FIELDS) - declared)
        if missing:
            yield _v(
                "A61",
                m,
                node.lineno,
                f"the payload gate no longer rejects {', '.join(missing)}; the envelope is "
                f"not payload, and no payload field carries a trace value under any name",
            )
        return
    yield _v(
        "A61",
        m,
        1,
        "the codec declares no RESERVED_PAYLOAD_FIELDS, so nothing stops a payload declaring "
        "an envelope or trace slot as one of its own fields",
    )


@rule
def a62_one_writer_per_trace_column(m: SourceModule, ctx: Context) -> Iterator[Violation]:
    """A62 — no path outside message creation assigns a message's TCE column.

    Item 10 SP3/CN3/PR2: no consumer, handler, relay, retry or replay path writes a span
    identifier into a message row, and the delivery's own operational trace is a **separate**
    target. The check is structural: a TCE value may reach the database only as a constructor
    keyword at creation, never through a queryset `update()` and never through an attribute
    assignment on a loaded row. `processing_trace_id` / `processing_span_id` are exempt by
    name — CN8 requires exactly that separate pair, and it is mutable per attempt.
    """
    if not _is_message_machinery(m):
        return
    banned = set(TCE_FIELDS)

    for node, assigned in _update_calls(m.tree):
        for column in sorted(assigned & banned):
            yield _v(
                "A62",
                m,
                node.lineno,
                f"update() assigns the message's '{column}'; the TCE is captured once at "
                f"creation, and a delivery's own trace context is a separate column pair",
            )

    # Not `node`: that name is bound to the `ast.Call` of the loop above, and rebinding it
    # here hid the expression type from the checker.
    for statement in ast.walk(m.tree):
        if not isinstance(statement, ast.Assign):
            continue
        for target in statement.targets:
            if isinstance(target, ast.Attribute) and target.attr in banned:
                yield _v(
                    "A62",
                    m,
                    statement.lineno,
                    f"'{target.attr}' is assigned on a loaded row; a message's trace context "
                    f"has exactly one writer, at the durable INSERT",
                )


@rule
def a66_message_fields_are_write_once(m: SourceModule, ctx: Context) -> Iterator[Violation]:
    """A66 — no retry, replay, relay or admin path rewrites a message's durable identity.

    Item 10 FS6/PR8/RP1: TCE state is immutable through every retry, redelivery, replay,
    terminal transition and archival, and no later process back-fills a field the emission
    left empty — a gap is a diagnostic fact, and rewriting history to hide it is worse than
    the gap. The same holds for the message's own identity and payload: item 9 C77 requires
    replay to preserve `event_id`, `event_type`, `schema_version`, `occurred_at` and payload
    byte-for-byte, which a mechanism that can rewrite them cannot promise.
    """
    if not _is_message_machinery(m):
        return
    banned = set(WRITE_ONCE_MESSAGE_FIELDS)

    for node, assigned in _update_calls(m.tree):
        for column in sorted(assigned & banned):
            yield _v(
                "A66",
                m,
                node.lineno,
                f"update() rewrites '{column}'; a durable message's identity and payload are "
                f"written once and replayed byte-for-byte, never amended",
            )


@rule
def a56_terminal_records_are_domain_scoped(m: SourceModule, ctx: Context) -> Iterator[Violation]:
    """A56 — every terminal record names its kind, its origin domain and its consumer.

    Item 9 TI2 forbids one global undifferentiated `dead_letters` bucket, and DL16/DL17 require
    the record to name **which** consumer failed, because a failure domain shared by several
    consumers cannot. One physical table is admissible only with an explicit terminal-kind
    discriminator, so the three columns are checked together: any one of them missing turns the
    table back into the shared bucket the rule exists to prevent.
    """
    if not _is_message_machinery(m) or m.basename != "models.py":
        return
    for node in ast.walk(m.tree):
        # A `TextChoices` enum named for the discriminator is not the record that carries it,
        # so the subject is narrowed to classes that actually define persistence.
        if not isinstance(node, ast.ClassDef) or not node.name.endswith("Terminal"):
            continue
        if not any(
            (chain := _chain(base)) is not None and chain[-1] == "Model" for base in node.bases
        ):
            continue
        declared = {
            name for name, _ in _assigned_field_names(ast.Module(body=[node], type_ignores=[]))
        }
        missing = [column for column in TERMINAL_DISCRIMINATORS if column not in declared]
        if missing:
            yield _v(
                "A56",
                m,
                node.lineno,
                f"class {node.name} declares no {', '.join(missing)}; a terminal record that "
                f"cannot name its kind, its domain and its consumer is a global bucket",
            )


# ---------------------------------------------------------------------------
# Observability and the log surface (item 3 §4.5, item 10 §21, master `# 23.1`)
# ---------------------------------------------------------------------------

#: Item 3 §4.5: the `core` subset `integrations/*` may import must stay **pure Python** —
#: importable without the Django app registry, because an adapter is a plain library that a
#: provider test constructs directly. A Django import anywhere under one of these modules
#: makes the whole allowlist entry unusable from an adapter.
_DJANGO_FREE_CORE = INTEGRATIONS_CORE_ALLOWLIST

#: A65 / PC2: no collector call, exporter flush, remote-sampler lookup or broker call on the
#: observability path or the emission path — both of which run between `BEGIN` and `COMMIT` of
#: a business transaction, where a network round trip cannot be allowed to sit.
_NETWORK_FREE_PACKAGES = ("core.observability", "core.outbox")
_NETWORK_MODULES = (
    "socket",
    "ssl",
    "http",
    "urllib",
    "urllib3",
    "requests",
    "httpx",
    "smtplib",
    "ftplib",
    "xmlrpc",
    "redis",
    "kombu",
    "celery",
    "amqp",
)

#: A63: the ambient readers of trace metadata, and the durable column names.
_TCE_READERS = frozenset(
    {
        "current_trace_id",
        "current_span_id",
        "current_request_id",
        "current_causation_event_id",
    }
)
_TCE_FIELDS = frozenset(
    {"trace_id", "span_id", "producer_span_id", "request_id", "causation_event_id"}
)

#: Families where reading a TCE value into a decision would be a business branch. `core` is
#: excluded on purpose: PR2's pair-integrity check and the log formatter legitimately read
#: these values, and both live in `core` precisely because that is the mechanism layer.
_TCE_BRANCH_FAMILIES = frozenset({"domains", "application", "interfaces", "tasks"})

#: The logging call surface, for `M23.1-MASK`.
_LOG_METHODS = frozenset(
    {"debug", "info", "warning", "warn", "error", "exception", "critical", "log"}
)


@rule
def l10_core_open_to_integrations_is_pure_python(
    m: SourceModule, ctx: Context
) -> Iterator[Violation]:
    """L10 — the `core` subset open to `integrations/*` imports no Django (item 3 §4.5)."""
    if m.family != "core" or not any(under(m.dotted, allowed) for allowed in _DJANGO_FREE_CORE):
        return
    for ref in m.imports:
        if _head(ref.target) == "django":
            yield _v(
                "L10",
                m,
                ref.line,
                f"{m.dotted} imports {ref.target}; this module is on the subset "
                f"integrations/* may import, which must stay importable without Django",
            )


@rule
def a65_no_network_io_on_the_emission_path(m: SourceModule, ctx: Context) -> Iterator[Violation]:
    """A65 — observability and emission perform no network I/O (item 10 PC2, §12)."""
    if not any(under(m.dotted, package) for package in _NETWORK_FREE_PACKAGES):
        return
    for ref in m.imports:
        if _head(ref.target) in _NETWORK_MODULES:
            yield _v(
                "A65",
                m,
                ref.line,
                f"{m.dotted} imports {ref.target}; nothing on this path may call a "
                f"collector, exporter, sampler or broker between BEGIN and COMMIT",
            )


def _tce_readers_bound_in(tree: ast.Module) -> set[str]:
    """Names assigned directly from a TCE getter, so a branch on one is still caught."""
    bound: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign) or not isinstance(node.value, ast.Call):
            continue
        chain = _chain(node.value.func)
        if chain is None or chain[-1] not in _TCE_READERS:
            continue
        for target in node.targets:
            if isinstance(target, ast.Name):
                bound.add(target.id)
    return bound


def _reads_trace_metadata(node: ast.AST, bound: set[str]) -> int | None:
    """The line where `node`'s subtree reads a TCE value, if it does."""
    for inner in ast.walk(node):
        if isinstance(inner, ast.Call):
            chain = _chain(inner.func)
            if chain is not None and chain[-1] in _TCE_READERS:
                return inner.lineno
        elif isinstance(inner, ast.Attribute) and inner.attr in _TCE_FIELDS:
            return inner.lineno
        elif isinstance(inner, ast.Name) and inner.id in bound:
            return inner.lineno
    return None


@rule
def a63_no_business_branch_on_trace_metadata(m: SourceModule, ctx: Context) -> Iterator[Violation]:
    """A63 — no conditional, policy or filter reads trace metadata (item 10 FW1, FW4).

    Trace metadata is observability only. The moment a branch reads it, a sampling decision, a
    stripped header or a collector outage acquires a business consequence — which is exactly
    what item 10's correctness firewall exists to make impossible.
    """
    if m.family not in _TCE_BRANCH_FAMILIES:
        return
    bound = _tce_readers_bound_in(m.tree)
    for node in ast.walk(m.tree):
        if isinstance(node, ast.If | ast.While | ast.IfExp):
            test: ast.AST = node.test
        elif isinstance(node, ast.Compare | ast.BoolOp):
            test = node
        else:
            continue
        line = _reads_trace_metadata(test, bound)
        if line is not None:
            yield _v(
                "A63",
                m,
                line,
                "a decision reads trace metadata; observability context never selects a "
                "branch, a policy, a filter, an ordering or a route",
            )


def _log_call_target(node: ast.Call) -> str | None:
    """`logger.warning` / `logging.info` / `self._log.error` -> the method name."""
    chain = _chain(node.func)
    if chain is None or len(chain) < 2 or chain[-1] not in _LOG_METHODS:
        return None
    return chain[-1] if any("log" in part.lower() for part in chain[:-1]) else None


def _sensitive_name_in(node: ast.AST) -> tuple[str, int] | None:
    for inner in ast.walk(node):
        if isinstance(inner, ast.Attribute) and is_sensitive(inner.attr):
            return inner.attr, inner.lineno
        if isinstance(inner, ast.Name) and is_sensitive(inner.id):
            return inner.id, inner.lineno
    return None


@rule
def m23_1_no_sensitive_binding_reaches_a_log_call(
    m: SourceModule, ctx: Context
) -> Iterator[Violation]:
    """`M23.1-MASK` — a sensitively-named binding is never handed to a logger.

    `core.observability.masking` masks by **field name**, which cannot see a value interpolated
    into a message or passed positionally. This is that rule's other half, and it shares the
    runtime vocabulary rather than restating it, so the two can never disagree. It is an
    implementation-level check on master `# 23.1`'s masking protocol, not a new architecture
    rule, and carries no new `A` number.
    """
    if m.family not in _FAMILIES or m.family == "tests":
        return
    for node in ast.walk(m.tree):
        if not isinstance(node, ast.Call) or _log_call_target(node) is None:
            continue
        for argument in node.args:
            found = _sensitive_name_in(argument)
            if found is not None:
                yield _v(
                    "M23.1-MASK",
                    m,
                    found[1],
                    f"{found[0]!r} is passed into a log call, where name-based masking "
                    f"cannot reach it; log a bounded, non-sensitive reference instead",
                )
        for keyword in node.keywords:
            if keyword.arg == "extra" and isinstance(keyword.value, ast.Dict):
                for key in keyword.value.keys:
                    if isinstance(key, ast.Constant) and is_sensitive(key.value):
                        yield _v(
                            "M23.1-MASK",
                            m,
                            key.lineno,
                            f"log context key {key.value!r} is masked at render time; a "
                            f"value that must be withheld is not context worth passing",
                        )
            elif keyword.arg != "extra":
                found = _sensitive_name_in(keyword.value)
                if found is not None:
                    yield _v(
                        "M23.1-MASK",
                        m,
                        found[1],
                        f"{found[0]!r} is passed into a log call, where name-based masking "
                        f"cannot reach it; log a bounded, non-sensitive reference instead",
                    )


# ---------------------------------------------------------------------------
# LK6 — bounded waits (item 5 §11.6, §20.3 LK6)
# ---------------------------------------------------------------------------

#: The session bounds the composition root delivers as libpq connection options, so that a
#: connection carries them from the moment it opens. Re-setting one in SQL anywhere else
#: silently widens or removes a bound the deployment believes it configured.
_SESSION_BOUND_GUCS = ("statement_timeout", "lock_timeout", "idle_in_transaction_session_timeout")

_SESSION_BOUND_SQL = re.compile(
    r"\bset\s+(?:local\s+|session\s+)?(" + "|".join(_SESSION_BOUND_GUCS) + r")\b",
    re.IGNORECASE,
)

#: Technical faults that a bounded wait raises. Item 4 §13.5 keeps them untranslated all the
#: way to the platform boundary; catching one in business code is precisely how a timeout
#: becomes a fabricated business outcome. `IntegrityError` is deliberately **absent**: item 4
#: §13.4 admits it at a nested savepoint when the violated invariant is identified by name,
#: which is what the idempotency claim path does.
_UNTRANSLATABLE_DB_FAULTS = frozenset({"DatabaseError", "OperationalError", "InterfaceError"})

#: Scoped like A63, and for the same reason: `core` is the mechanism layer, where a relay or
#: a retry loop legitimately handles a technical fault. `integrations` speaks to vendors, not
#: to PostgreSQL. What must never launder a database fault is business code.
_BOUNDED_WAIT_FAMILIES = frozenset({"domains", "application", "interfaces", "tasks"})


@rule
def lk6_bounded_waits(m: SourceModule, ctx: Context) -> Iterator[Violation]:
    """LK6 — the bound is the composition root's, and exceeding one is a technical fault.

    Item 5 §20.3 LK6 has two halves and this rule enforces both structurally:

    * **the bound stands.** No production module re-sets a session timeout in SQL. The
      composition root sets all three as libpq connection options, which no `SET` of its own
      can be missing; a `SET statement_timeout = 0` further in is an escape hatch that
      disables a deployment's configured bound with nothing at the call site to say so. A
      maintenance run that genuinely needs a longer bound raises it through the environment
      for that invocation, where it is visible in the command rather than buried in a module.
    * **the fault is not laundered.** Business code does not catch `OperationalError` (or the
      broader `DatabaseError`/`InterfaceError`). Item 5 §11.6: a bounded wait exceeded is a
      technical fault propagating untranslated, never a business outcome — master `# 22.6`'s
      "retryable business error" sketch is refined by the frozen artifact, which governs.

    Like A63 this sees syntax, not semantics: a fault caught through an aliased name or
    re-raised from a helper is beyond it, and stays item 5 V-tier review.
    """
    if m.family not in _FAMILIES or m.family == "tests":
        return

    for node in ast.walk(m.tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            found = _SESSION_BOUND_SQL.search(node.value)
            if found is not None:
                yield _v(
                    "LK6",
                    m,
                    node.lineno,
                    f"{found.group(1)} is re-set in SQL here; the bound belongs to the "
                    "composition root's connection options, and a module that moves it "
                    "disables a bound the deployment believes it configured",
                )

    if m.family not in _BOUNDED_WAIT_FAMILIES:
        return

    for node in ast.walk(m.tree):
        if not isinstance(node, ast.ExceptHandler):
            continue
        if node.type is None:
            yield _v(
                "LK6",
                m,
                node.lineno,
                "a bare `except:` swallows the technical fault a bounded wait raises; item 4 "
                "§13.5 propagates it untranslated to the platform boundary",
            )
            continue
        for caught in sorted(_exception_names(node.type) & _UNTRANSLATABLE_DB_FAULTS):
            yield _v(
                "LK6",
                m,
                node.lineno,
                f"{caught} is caught here; a statement or lock timeout is a technical fault "
                "(item 5 §11.6), never a business outcome, and never a retry decision this "
                "layer makes",
            )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def check_tree(root: Path) -> list[Violation]:
    """Run every rule over the source families found under `root`."""
    modules = discover(root)
    ctx = Context(
        root=root,
        inventory=frozenset(m.dotted for m in modules),
        symbol_sources={m.dotted: symbol_bindings(m) for m in modules},
    )
    violations: list[Violation] = []
    for module in modules:
        for check in RULES:
            violations.extend(check(module, ctx))
    return sorted(violations, key=lambda v: (v.path, v.line, v.rule))
