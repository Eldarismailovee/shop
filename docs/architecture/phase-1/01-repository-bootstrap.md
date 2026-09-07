# Phase 1 — Slice 1: repository bootstrap, launch skeletons, composition root, enforcement harness

- **Status:** DONE
- **Date:** 2026-09-06
- **Phase:** 1 — first production code
- **ADRs:** **none required.** Every choice below sits inside a decision Phase 0 already froze, or
  fills a deferral Phase 0 explicitly assigned to Phase 1 (item 3 §18, item 15 §15 clause 8). No
  frozen artifact or accepted ADR was edited.
- **Implements:** item 15 §15 clauses 1, 2 (partly), 6, 7; item 3 §15.1 / §15.2; item 4 §19.1 / §19.5
  (partly); item 14 §5, §19; ADR-0016 RR1/RR4.

> **Frozen rule inventory.** The import-graph series is **L1–L21**, not L1–L19: item 3 §15.1 freezes
> L1–L19, and item 4 §19.5 / ADR-0006 extend it with **L20** (the actor primitive) and **L21** (the
> structural public-error categories). The `A` series likewise runs A1–A13 (item 3 §15.2) plus
> A14–A23 (item 4 §19.1). §6 records exactly which of these are enforced today.

---

## 1. Scope

This slice creates the repository baseline, the launch package skeleton, `config/` as the single
composition root, the primary-only database configuration, and the architecture-enforcement harness
with its regression tests.

It deliberately creates **no** `core` primitive (`Money`, `RoundingPolicy`, `PublicId`, `EventId`,
the actor primitive, the structural error categories), no `core.events` runtime, no `IdempotencyKey`,
no Outbox/Inbox/quarantine/dead-letter schema, no business model, no use case, no port, no adapter,
no Celery configuration and no migration. Those are later Phase-1 slices; §11 lists them.

---

## 2. Toolchain and dependencies

The master `# 2` stack table pins the baseline as of 03.09.2026, and the local toolchain matches it.
Nothing was upgraded opportunistically, and no dependency for a `LATER` module or a closed
infrastructure gate was added.

| Choice | Value | Why |
|---|---|---|
| Python | 3.14.7 (`requires-python = "==3.14.*"`) | Master `# 2`. |
| Django | `6.1.1` | Master `# 2`; the planned move to the 6.2 LTS branch stays a maintenance item. |
| PostgreSQL driver | `psycopg[binary]==3.3.5` | Master `# 2` names psycopg3. Pool sizing and timeouts are **not** decided here (§11). |
| Dependency manager | **uv**, `pyproject.toml` + `uv.lock` | No packaging existed. uv is the only manager present on the toolchain; the lockfile is checked in. The project is a virtual root (`[tool.uv] package = false`) because the source roots are the seven top-level families, not one distributable package. |
| Import contracts | `import-linter==2.15` | Item 3 §15.1's named mechanism. |
| Static harness | first-party, `tools/arch_check` | Item 3 §15.2 leaves the implementation to Phase 1. |
| Tests | `pytest==9.1.1` + `pytest-django==4.14.0` | Standard Django test integration. |
| Format / lint | `ruff==0.16.6` | One tool for both; line length 100. |

**Not added:** DRF, Celery, a cache client, a type checker, an email/SMS/CRM/search/pooler package.
Each arrives with the slice that has a use for it. No OpenSearch, PgBouncer, PostGIS or
replica-routing dependency exists — every infrastructure gate stays closed.

---

## 3. Physical source layout

Item 3 §18 deferred "physical package directories, Django app labels, settings modules and the
composition-root module names" to Phase 1. Frozen for this repository:

```text
core/            domain-agnostic primitives (empty in this slice)
domains/<x>/     business truth, mutually invisible
application/<a>/ cross-domain use cases and read applications
interfaces/      web · api/v1 · webhooks · admin
integrations/<v>/{protocol,outbound}   pure-Python vendor adapters, two import surfaces
tasks/           Celery transport wrappers
config/          the single composition root: settings, URLconf, future bindings
tools/arch_check/  the static architecture checker (not a source family)
tests/           the test tiers
```

The seven source families are top-level packages, so a family name is the first dotted segment of
every module. Both enforcement mechanisms key off exactly that, and no fifth business layer
(`services/`, `shared/`, `common_business/`) exists.

`interfaces/api/v1` is a package so that a second API version is additive. Provider packages carry
the two frozen surfaces as directories (`protocol/`, `outbound/`) so item 3 §6.5's distinction is
mechanically checkable before either surface has content.

---

## 4. Launch skeletons created

Per item 14 §5, and no further. Every package is a directory with an **empty** `__init__.py` (§10's
freeze, enforced by A8):

- **`domains/`** — `accounts`, `catalog`, `content`, `delivery`, `inventory`, `notifications`,
  `orders`, `payments`, `pricing`, `promotions`, `reviews`, `stores`.
- **`application/`** — `checkout`, `erp_sync`, `payments_gateway`, `storefront`.
- **`interfaces/`** — `web`, `api/v1`, `webhooks`, `admin`.
- **`integrations/`** — `base`, `erp/{protocol,outbound}`, `maib/{protocol,outbound}`.
- **`tasks/`**, **`core/`**, **`config/`**.

**No `LATER` package exists**, and `tests/architecture/test_repository_layout.py` asserts their
absence by name: `domains/analytics`, `domains/tradein`, `domains/support`, `domains/digital`,
`application/backoffice`, `application/crm_sync`, `application/support`, `integrations/crm`,
`integrations/chatwoot`, `integrations/mia`. No null adapter, fake provider, placeholder repository,
`try: import` fallback, `INSTALLED_APPS` probe or settings-gated placeholder was created — and the
harness rejects each of those shapes (A12, NF7, NF8).

Per-family task modules, an outbound email adapter package (item 14 names no vendor) and the
`tasks/notifications` split are **not** created: they arrive with the workloads they carry.

### 4.1 No placeholder `public.py`

**Decision: a launch module gets its `public.py` when it has something to publish.**

An empty façade would say "this module publishes nothing", which is true but buys nothing: the
boundary is enforced by rule, not by the presence of a file, and item 4's contract shape is strict
enough that a fabricated surface is worse than an absent one. Three separate rules bind the first
real façade, and each reports its own id:

```text
A11  no ORM model / manager / instance / QuerySet crosses public.py
A14  façade shape — no class/def, wildcard, alias, module import, conditional/TYPE_CHECKING
     import, module-level __getattr__
A15  exactly one explicit __all__ tuple, matching the imported names
```

All three are proved by fixture tests today.

---

## 5. Composition root

`config/` is the composition root. This slice ships `config/settings.py` and `config/urls.py` only;
there is no port to bind yet, so there is no binding module, **no container and no service locator**.

Recorded for the slice that introduces the first port: bindings live in `config/composition/<capability>.py`,
constructed at startup and injected into entry points. `interfaces/*` and `tasks/*` never import
`config/*` (L16), and the `config → application` SPECIAL cell is narrowed exactly as item 3 §4.7
freezes it — `ports.py` and `public.py` only, every application internal forbidden (L7).

`INSTALLED_APPS` is empty: a module registers when it acquires models. No package presence is probed
and no `LATER` module is listed.

---

## 6. Enforcement harness

Item 3 §15 splits every rule three ways. This slice wires the mechanisms and the rules that the
current tree makes checkable; §11 lists what waits for the packages it is about.

### 6.1 `import-linter` — `pyproject.toml [tool.importlinter]`

Configuration placement was undecided; it lives in `pyproject.toml` beside the other tool
configuration rather than in a separate `.importlinter`, so the whole toolchain is described in one
file. Twelve contracts, all `KEPT`:

| Contract | Frozen rule |
|---|---|
| L1 | `core` imports nothing above or beside it |
| L2 | the twelve domains are mutually independent |
| L3 | domains import no application/interfaces/tasks/integrations/config |
| L5 | application → application |
| L6 | application imports no interfaces/tasks/integrations/config |
| L8 | integrations reach application only through `application.*.ports` |
| L9 | vendor packages are isolated (`integrations.base` shared) |
| L11 | tasks import no integrations, no interfaces |
| L12 / L17 | only `interfaces.webhooks.*` reaches a provider, and only its `protocol` surface |
| L14 | no production package imports `tests` |
| L16 | `interfaces` and `tasks` never import `config` |
| L18 | a `protocol` surface carries no client/SDK code |

L8 and L12/L17 carry their exception as `ignore_imports` with
`unmatched_ignore_imports_alerting = "none"`, because the exception is written before the module it
excepts exists. The `.ports` exception was verified to behave correctly in both directions: an
adapter importing `application.<a>.ports` is `KEPT`; the same adapter importing
`application.<a>.public` breaks L8.

### 6.2 `tools/arch_check` — the static harness

The rules `import-linter` cannot state without weakening the invariant, plus the shape rules. Every
rule is one function with an `@rule` decorator over a parsed module; adding a later `A`/`C`/`V` check
adds a function and changes nothing else. `from M import n` is recorded as the dotted path `M.n`, so
a `PUBLIC ONLY` cell is answered correctly whether `n` is a submodule or a symbol.

| Rule | What it enforces | Status |
|---|---|---|
| L1, L2, L3, L5, L6, L8, L9, L11, L12, L14, L16, L17, L18 | the §4 matrix edge by edge, mirroring the contracts above so a fixture can prove each one | full |
| **L4** | outside `domains.<x>`, only `domains.<x>.public` is importable | full |
| **L7** | outside `application.<a>`, only `.public` — plus `.ports` for `integrations` and `config` | full |
| **L10** | an adapter keeps the pure-Python `core` subset (`money`, `public_id`, `dto`, `security.signing`, `observability`) | full |
| **L13** | `interfaces` reach neither `core.outbox` nor `core.idempotency` | full |
| **L15** | `application/<a>/ports.py` imports stdlib + `core` value primitives only | full |
| **M4.4-CORE** | the `interfaces → core` allowlist (§6.4) | full |
| **M4.4-TASKS** | `interfaces → tasks` is enqueue-only (§6.5) | full |
| A1 | model-definition capability only in `domains/<x>/models*`, `application/<a>/models*`, `core` (§6.6) | full |
| A3 | `integrations/*` imports no `django.*` | full |
| A5 | one `domains.<y>.public` per view function/class and per task function (§6.7) | full |
| A6 | a migration imports no runtime code, `core` included (§6.8) | full |
| A8 | `__init__.py` under `domains/`, `application/`, `integrations/` stays empty | full |
| A9 | a `ports` module exists only at `application/<a>/ports.py` | full |
| A10 | only `config/` knows both an adapter and the port it implements | full |
| A11 | no ORM model/manager/QuerySet crosses `public.py`, by **symbol provenance** (§6.10) | full |
| A13 | the two provider surfaces stay distinguishable | **partial** — see §6.9 |
| A14 | façade shape S1–S6: no `class`/`def`, wildcard, alias, **plain `import`**, module re-export, `TYPE_CHECKING`, module `__getattr__` | full |
| A15 | **exactly one** explicit `__all__` tuple of distinct string literals, matching the imported names (S5) | full |
| A12 | no dynamic-import / service-locator resolution in production code | full |
| NF7 | no `try: import … except ImportError` capability fallback | full |
| NF8 | no `INSTALLED_APPS` / app-registry probing outside `config` | full |

**A11 vs A14 vs A15 are three separate rules and report three separate ids.** A11 (item 3) is the ORM
re-export ban; A14 (item 4) is the façade *shape*; A15 (item 4) is the `__all__` contract. An earlier
draft of this harness folded all three under A11; it no longer does, and each has its own fixtures.

L4, L7, L10, L13 and L15 are stated here rather than in `import-linter` because their subject modules
(domain and application internals, `core` submodules, `ports.py`) do not exist yet. Stating them over
source text keeps the invariant at full strength while the packages fill in; they may move to
`import-linter` later without changing what is enforced.

### 6.3 `M<section>` — implementation-level matrix identifiers

Two `SPECIAL CASE` cells of item 3 §4.4 are narrower than any frozen `L`/`A` number covers. They are
checked under an identifier that names the frozen section it enforces — `M4.4-CORE`, `M4.4-TASKS` —
rather than under an invented `L22`. **These are implementation identifiers, not new architecture
rules**; the rule they enforce is item 3 §4.4 exactly as frozen.

### 6.4 `interfaces → core` (M4.4-CORE)

Item 3 §4.4 opens an enumerated set to a transport boundary and closes the rest:

```text
ALLOWED   core.security  core.dto  core.money  core.public_id
          core.observability  core.cache  core.inbox
FORBIDDEN core.outbox, core.idempotency          -> reported as L13, the frozen rule for these two
          every other core module                -> reported as M4.4-CORE
```

Item 4 / ADR-0006 additionally authorise the **actor primitive** and the **structural public-error
categories** for `interfaces` (L20/L21). Their physical module names belong to the core-primitives
slice, so `CORE_PUBLIC_CONTRACT_PRIMITIVES` in `tools/arch_check/rules.py` is an explicitly empty
tuple that the slice extends. **No name is guessed**, and until then those imports simply do not
exist. The negative half of L20/L21 — forbidden to `integrations/*` and `**/migrations/**` — already
holds independently of the eventual names, because both of those allowlists are explicit and closed.

### 6.5 `interfaces → tasks` (M4.4-TASKS)

Item 3 §4.4: "Enqueue only — `task.delay()` / `apply_async()`. Calling a task function body inline,
or importing anything else from `tasks/`, is `FORBID`." The check binds the local names an import
introduces and then requires every use of them to be an enqueue call. Permitted import forms, and
what each binds:

```text
import tasks.notifications                  -> tasks        tasks.notifications.send_email.delay(…)
import tasks.notifications as t             -> t            t.send_email.apply_async(…)
from tasks import notifications             -> notifications  notifications.send_email.delay(…)
from tasks.notifications import send_email  -> send_email   send_email.delay(…)

rejected: send_email(…)            running the task body inline
          send_email.some_helper   any other attribute of a task
          send_email.backend.…     inspecting task implementation state
```

### 6.6 A1 — model definition, not ORM query use

A1 forbids `from django.db import models` and Django `Model` class definitions outside the allowed
locations. It does **not** forbid a selector or service from using ORM query expressions. The check
therefore looks for the model-definition *capability*: a binding of the `django.db.models` module
object, or a `ClassDef` whose base resolves to `django.db.models.Model` — including the
`from django.db.models import Model` form a name-only shortcut would miss. `Q`, `F`, `Exists`,
`OuterRef`, `Subquery` and `django.db.transaction` stay legal everywhere.

### 6.7 A5 — the unit is the callable

Frozen A5 is "an `interfaces/*` view function/class and a `tasks/*` task function reference at most
**one** `domains.*.public` module" — not one domain per file. The check units are each top-level
function or class (a class-based view is one unit, as frozen) plus module scope. Two independent
single-domain views may therefore share a module; one view reaching two domains fails. **V10 is not
weakened**: a request path that combines domains across helper modules remains a review concern, and
this rule makes no claim to catch it.

### 6.8 A6 — the migration `core` SPECIAL CASE

Item 3 §4.9 admits from `core` only "stable technical primitives Django's deconstruction requires to
be importable: custom field classes and expression/constraint helpers". An earlier draft allowed
every `core.*` import from a migration, which contradicted that. The allowlist is now explicit and
**empty** (`MIGRATION_CORE_ALLOWLIST = ()`), because no such class exists yet:

```text
migration -> core.money / core.dto / core.outbox / any core.*   REJECT
migration -> its own domain's models                            REJECT
migration -> django.db.migrations, django.db.models, stdlib     ALLOW
historical models                                               apps.get_model() inside RunPython
```

A future slice that creates a genuine deconstruction-stable technical class adds its exact module
path to the allowlist with a regression test and records the choice here. It is never a route for
`core.money`, a DTO, the actor/error primitives, an Outbox/Inbox/idempotency helper or a service.

### 6.9 A13 — partial

A13 has two halves. The half enforced today is the import half: a provider's `protocol` surface may
not import a port, and only the `outbound` surface implements one (with L18 keeping `protocol` free
of `outbound`). The other half — "the `protocol` surface defines no HTTP client/SDK call" — needs
A2's vendor-SDK inventory, which has no vendor dependency to inventory yet. **A13 is therefore
recorded as partial, not full**, and completes with A2 in the slice that adds the first vendor client.

### 6.10 A11 — provenance, not spelling

A name check alone passes an ORM model forwarded through an internal module: the immediate
target `domains.orders.export_helpers.Order` contains no `models` segment and the symbol is
just `Order`. A11 therefore follows the **exported symbol** back through repository modules
(`Context.symbol_sources`), with cycle protection, and rejects any provenance reaching a
`models*` / `managers*` / `querysets*` module however many forwarding hops away.

It follows the symbol only, never its containing module's other dependencies: a selector or
service that internally imports a model still exports a callable, and that stays legal. A walk
that leaves the repository (Django, stdlib), reaches a name its source module *defines* rather
than imports, or closes a cycle resolves to "not ORM" rather than to a guess. No new rule such
as "internal modules may never re-export" is introduced.

### 6.11 A15 — one authoritative `__all__`

Taking the first assignment let a second one silently replace the runtime contract. A15 now
requires exactly one module-level binding of `__all__` — a second `Assign`, an `AnnAssign`
redefinition and an `AugAssign` extension are all rejected — whose value is an explicit tuple
of distinct string literals matching the imported names. Computed or dynamic `__all__` stays
forbidden by the frozen contract and is not supported.

### 6.12 Review-only

V1–V10 (item 3 §15.3), item 4 §19.4's `V11`–`V18`, and the semantic `V` rules of items 9–15 stay on
the review checklist. No regex approximation of a meaning-level rule was added.

---

## 7. Primary-only database (ADR-0016)

`config/settings.py` defines exactly one alias, `default`, on `django.db.backends.postgresql`, from
the environment. There is **no** replica alias, **no** `DATABASE_ROUTERS` entry, **no** sticky-primary
or read-your-own-writes machinery and **no** replica-aware repository abstraction — RR1 plus item 14
NF10 forbid shipping routing for a replica that is not used, so the setting is simply absent rather
than present-and-empty. HA topology is not designed here; a standby is an operational concern and
never an application read target (RR2).

`tests/config/test_database_baseline.py` asserts the alias set, the engine, that
`settings.DATABASE_ROUTERS` is empty, that no launch source line names a replica/follower/standby,
and that no secret has a checked-in default.

---

## 8. Tests and configuration for the test run

**Fixture approach.** The matrix cases need modules that deliberately break the graph. Writing them
into the real tree would create production packages whose only purpose is to be illegal, so each case
is materialised as a throwaway tree under `tmp_path` (`tests/architecture/conftest.py::arch_rules`)
and the checker is run against it. A legal case must produce **no** violation; an illegal case must
produce the frozen rule id. The real tree is separately asserted clean by both mechanisms.

**Settings for the test run.** `config.settings` deliberately has no checked-in default for any
secret, so `DJANGO_SETTINGS_MODULE` is `tests.settings`: it sets throwaway local values and then
re-exports `config.settings` unchanged. Nothing is overridden, so the ADR-0016 assertions are made
against the real launch configuration. No database is contacted by this slice's tests.

`make django-check` runs through the same module, so the whole verification entry point works from a
clean shell with every production variable unset. `manage.py` uses `setdefault`, so the explicitly
supplied test settings win. No production `SECRET_KEY` fallback and no `.env` file was added.

---

## 9. Commands

`Makefile` is the verification entry point; it drives the existing tools rather than wrapping them in
a second command system.

```text
make install       uv sync
make fmt / lint    ruff format . / ruff check .
make arch-imports  lint-imports
make arch-static   python -m tools.arch_check .
make arch          both
make test          pytest
make django-check  DJANGO_SETTINGS_MODULE=tests.settings python manage.py check
make check         lint + arch + test + django-check
```

`make check` is reproducible from a clean developer or CI shell: it needs no exported
`DJANGO_SECRET_KEY`, `POSTGRES_*` or any other production variable.

---

## 10. Results

`make check`, run from a shell with `DJANGO_SECRET_KEY` and every `POSTGRES_*` variable unset:

```text
ruff check .                    All checks passed
lint-imports                    12 contracts kept, 0 broken
python -m tools.arch_check .    OK
pytest                          118 passed
manage.py check                 System check identified no issues
```

---

## 11. Deliberately deferred to later slices

| Deferred | Owner |
|---|---|
| `Money` + `RoundingPolicy` member set, `PublicId`, `EventId`, the actor primitive, the structural error categories, `core.events` mechanism (registry empty) | the `core` primitives slice (item 15 §15 clause 3) |
| `IdempotencyKey` model and migration | ADR-0015 slice (clause 4) |
| Outbox/Inbox initial schema with the four TCE fields, quarantine and dead-letter tables | clause 5 |
| Query-budget / N+1 harness | the slice that creates the first read path (clause 2) |
| **L20 / L21** — the actor primitive and the structural public-error categories are importable by `domains`, `application`, `interfaces`, `tasks`, `config` and **forbidden to `integrations/*` and `**/migrations/**`** (item 4 §19.5, ADR-0006). The negative half already holds (§6.4); the positive half becomes concrete when the physical module names exist, by extending `CORE_PUBLIC_CONTRACT_PRIMITIVES` | the `core` primitives slice |
| **A16** no `id`/`pk` field on a public DTO, locators `PublicId`-typed · **A17** exported classes are frozen dataclasses with no mutable/abstract field types · **A18** no `**kwargs`, unannotated parameter or `Any` in a public signature · **A19** no `actor` parameter with a default or `Optional` · **A20** no transport/vendor/ORM type in a public annotation · **A21** no `transaction.commit/rollback/set_autocommit` and no `atomic(durable=True)` in a domain · **A22** no `transaction.on_commit` scheduling transport work in a domain · **A23** every public error inherits a domain root plus exactly one `core.errors` category | the slices that introduce the DTO, actor, error and transactional contract shapes each rule inspects (item 4 §21) |
| **A2** (vendor SDK confinement) and the second half of **A13** (no HTTP client/SDK call on a `protocol` surface, §6.9) | the slice that adds the first vendor client |
| A4 (object-level authz shape), A7 (test-tier scoping) | the slices that create interface views and the test tiers those rules are about |
| C1–C8 (item 4 §19.2 contract tests) | the slice that publishes the first `public.py` |
| A6's `MIGRATION_CORE_ALLOWLIST` entry, if a deconstruction-stable technical class is ever created | that slice; the allowlist stays empty until then (§6.8) |
| L19's path-scoped migration exclusion in `import-linter` | the first migration; A6 already covers migrations statically |
| `config/composition/` bindings and the concrete injection mechanism per entry point | the first port (item 3 §18) |
| Django app labels and `INSTALLED_APPS` registration | the first slice with models |
| `wsgi.py` / `asgi.py`, DRF, Celery app and routing, psycopg pool sizing and timeouts | the slices that need them; queues follow item 14 §15's provisioning view |
| CI job wiring | the repository is not under version control and no CI system exists; `make check` is the provider-agnostic entry point a CI job will call |
| A type checker | not required by this slice |

Nothing in this slice required changing a frozen boundary, so no superseding ADR is needed.
