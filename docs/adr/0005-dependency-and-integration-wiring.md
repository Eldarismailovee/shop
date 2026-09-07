# ADR-0005 — Dependency matrix, integration ports and the single composition root

- **Status:** Accepted — Frozen
- **Date:** 2026-09-04
- **Phase:** 0 — Architecture Freeze
- **Supersedes:** —
- **Related:** [ADR-0004](0004-four-layer-modular-monolith.md),
  [ADR-0003](0003-catalog-boundary-vs-storefront-projection.md),
  [ADR-0001](0001-product-vs-sku-sellable-unit.md),
  [Phase 0 item 3 artifact](../architecture/phase-0/03-dependency-matrix.md),
  [Phase 0 item 2 artifact](../architecture/phase-0/02-four-layer-architecture.md),
  master `# 4`

## Context

ADR-0004 froze four layers, a skip-allowed downward dependency direction, and the conceptual roles of
`integrations/` and `tasks/`. It deliberately left open (its §8, and item 2 §9.3/§17) the questions
that decide whether those rules can be enforced by a machine rather than by memory:

- whether an integration adapter imports a port defined elsewhere, and in which direction dependency
  inversion runs;
- where the stable contract types exchanged at the adapter edge live;
- who wires a concrete vendor implementation;
- which package owns the persistent `provider + external_id ↔ internal entity` mapping, given that
  `integrations/*` is pure Python without Django models while the mapping needs PostgreSQL;
- the exact import rules for `tasks/*`, for application-owned ORM, for domain-local `admin.py`, and
  for migrations, which Django allows to reference other apps' historical models.

Phase 1 must turn all of this into `import-linter` contracts, AST checks and a package layout. Left
unfrozen, each of these becomes an argument at the moment code is written, and the usual outcome is
an "exception" that quietly becomes the rule — a task that imports a vendor client, an `admin.py`
that reaches a sibling domain, a blanket `ignore_imports` for migrations that swallows runtime code
with it.

## Decision

### 1. The dependency matrix is frozen

The full importer×imported matrix — `core`, `domains/self`, `domains/other`, `application/self`,
`application/other`, `interfaces`, `integrations`, `tasks`, composition/bootstrap, `tests`,
`migrations` — is frozen in the [item 3 artifact](../architecture/phase-0/03-dependency-matrix.md)
§4, one intentional status (`ALLOW` / `PUBLIC ONLY` / `PORT ONLY` / `SELF ONLY` / `FORBID` /
`SPECIAL CASE`) and one reason per cell. It refines ADR-0004 without weakening any of its rules.

Two additions worth naming here: `core` submodule access is an **allowlist** per package family —
`integrations/*` sees only the pure-Python subset, `interfaces/*` may use `core.inbox` for durable
webhook ingest but not `core.outbox`/`core.idempotency`; and `__init__.py` files under `domains/`,
`application/` and `integrations/` stay **empty**, so a package import cannot drag internals into the
graph.

### 2. Ports and adapters, with every port owned by an `application` module

Dependency inversion, in the canonical direction: the business side declares the required
capability, the vendor adapter implements it, and the runtime dependency (application → adapter) is
the inverse of the source dependency (adapter → port).

> **Every outbound vendor port lives at `application/<a>/ports.py`. No domain declares, imports,
> invokes or is injected with a port. There is no shared `contracts/` package.**

A port module holds only `Protocol` definitions and frozen vendor-neutral edge types, may import
only stdlib and `core` value primitives, and must import no domain, no Django and no
`integrations` module — which keeps `adapter → port` acyclic and keeps `integrations/*` pure Python.
`integrations/*` → `application/<a>/ports` is the **single legal upward import in the graph**;
everything else in `application` remains invisible to an adapter.

Frozen owners: payments provider → `application/payments_gateway`; ERP/1C → `application/erp_sync`;
email and SMS → `application/notifications`; CRM export → `application/crm_sync`; Chatwoot →
`application/support`.

Domain-owned ports were rejected because they would make a domain perform outbound vendor I/O,
against ADR-0004 §10 and the domain unit-test tier; a shared `contracts/` package was rejected
because a package with no owner cannot refuse an addition.

**This extends item 2 §7.3:** an `application` module is justified by coordinating two or more
domains, **or** by owning application state, **or** by owning an outbound vendor port and the
workflow around it. The third clause is added here.

### 3. Exactly one composition root, which owns construction **and** injection

The project bootstrap package `config/` is the only place that may import a concrete outbound
adapter together with the port it satisfies, and the only place that decides which vendor is used.
Binding happens at startup from settings.

> **Entry points receive dependencies; they do not locate them.**

`config/composition` may import application ports, concrete outbound adapter implementations,
interface entry-point factories/classes, task registration/factory functions, and settings.
**`interfaces/*` and `tasks/*` must not import `config/*`** — there is no provider API, registry
lookup or service locator at a transport boundary, and therefore no `config ↔ interfaces` or
`config ↔ tasks` source cycle. A use case still receives its port explicitly as a parameter; no
global service locator is introduced.

```text
application port  ←  integration adapter (outbound)  ←  config/composition
                                                            ├── injects into the interface entry point
                                                            └── injects into the task handler
```

`core` may own the *mechanism* of a typed registry but never a binding, and it is not a lookup seam
for entry points; `application/*` never imports the composition root; `domains/*` never see it.
Tests compose fakes through the same seam.

The **injection mechanism** is deliberately not frozen — a view/entry-point factory, class
construction or `as_view()` binding for web/API; handler registration or a bound callable/task class
for Celery; or another explicit startup binding. What is frozen is the direction. If a
framework-specific late lookup ever proves unavoidable, it requires an explicit architecture review
and a new ADR, not a silent reintroduction of `interfaces/tasks → config`.

### 4. Persistent integration state belongs to the owning application sync module

The durable `provider + external_id ↔ internal entity` mapping — future `ErpVariantMapping` — is
owned by the `application` synchronization module that owns the corresponding external workflow, as
an **internal** model: `application/erp_sync`. No new business domain is invented for vendor
mapping, no generic cross-provider `integration_state` table is created (a polymorphic
`entity_type + entity_id` table cannot carry real constraints), `integrations/*` neither defines nor
imports it, and no domain table acquires a provider identity column. ADR-0003 §2 stands unchanged;
its "conceptually in `integrations/erp`" phrasing is boundary ownership, as item 2 §9.4 already
recorded. The concrete schema remains Phase 3.

### 5. `tasks/*` may not import `integrations/*` at all

A task imports one `application/<a>/public.py` use case or one `<domain>.public` command, `core`
primitives and its own package — nothing else, and in particular no `config/*`. The open question of
whether a task that owns a post-commit external operation may import an adapter is answered **no**:
the bound port is injected into the handler at bootstrap and passed into the use case. A task
function reaching two domains is a static failure.

### 6. A provider integration package has two surfaces: inbound `protocol`, outbound adapter

`integrations/<provider>` is split into two distinguishable import surfaces (exact Phase-1 file
names may differ):

- **`protocol/`** — pure provider protocol support: signature/HMAC canonicalisation, header parsing,
  timestamp validation helpers, event-id parsing, wire DTO codecs, protocol constants. No Django, no
  business rule, no domain state transition, and no outbound business operation merely because it
  knows the protocol. `interfaces/webhooks/<provider>` may import it.
- **`outbound/`** — the concrete implementation of `application/<a>/ports.py`: provider HTTP client,
  SDK usage, timeout/retry/circuit-breaker behaviour, request/response translation. **Only the
  composition root and provider-integration tests may know it.** `interfaces/*`, `tasks/*`,
  `application/*` and `domains/*` are forbidden sources; `protocol/` may not import it either.

This does **not** move webhook ownership into `integrations/`. `interfaces/webhooks/<provider>`
remains the inbound adapter and owner of authentication of the provider call, the replay/timestamp
policy, durable Inbox ingest and the HTTP acknowledgement (ADR-0004 §7). ADR-0004 §8's
characterisation of `integrations/*` as an **outbound** anti-corruption boundary remains true of the
adapter implementation; this ADR adds only the narrow pure-protocol support surface consumed by the
inbound boundary, and grants `integrations/*` no business role in either direction.

### 7. One provided entry point per module, plus `ports.py` as the required one

`domains/<x>/public.py` and `application/<a>/public.py` are the only importable surfaces of their
packages; `application/<a>/ports.py` is importable only by `integrations/*` and the composition
root. Application-owned ORM (`CheckoutSession`, `ProductListingProjection`, `ErpVariantMapping`) is
internal to its module exactly as domain ORM is internal to its domain. Application→application
imports are forbidden with no MVP exception; a genuine need is resolved by merging owners, pushing
the rule into a domain or `core`, or a new ADR.

### 8. Domain-local `admin.py` gets no exception; migrations get a path-scoped one

`domains/<x>/admin.py` follows the **domain's import rules** (own domain + `core` only — no sibling
domain, not even its `public.py`, no `application`, no `integrations`) and the **interface's content
rules**. A cross-domain admin action moves to `interfaces/admin/`, which calls
`application/backoffice`. No `import-linter` exception is required, because the domain row already
describes exactly what `admin.py` may do.

Migration packages are excluded from the runtime layer contracts by **path scope only**
(`**/migrations/**`), never by a blanket ignore list. Migrations reach historical models through
`dependencies` and `apps.get_model()`, import no runtime business module including their own
domain's, and are separately inspected by an AST check so the exclusion cannot become a hole.
Runtime code never imports a migration module.

### 9. Every rule is classified by the mechanism that can actually enforce it

The artifact's §15 assigns each rule to `import-linter` (L1–L19, the import graph, including
`interfaces`/`tasks` importing no `config`, and `outbound` reachable only from the composition
root), AST/static checks (A1–A13, shapes such as ORM definitions outside owners, vendor SDKs outside
`integrations`, `objects.get` in interfaces, two domains in one task, non-empty `__init__.py`,
`ports.py` in the wrong family, a model re-exported from `public.py`, a service-locator call shape,
the two provider surfaces staying separate), or review/behavioural tests (V1–V10, meaning: business
logic in a view, an application reimplementing a domain invariant, a neutrally typed DTO carrying
vendor semantics). No claim is made that `import-linter` can see V-rules.

**Out of scope of this ADR:** the `.importlinter` file itself, AST checker code, package
directories, `ports.py`/`public.py` contents, port method signatures, the composition-root module
names, the concrete injection mechanism at each entry point, the physical file names inside a
provider package, and the `ErpVariantMapping` schema.

## Consequences

**Positive**

- Phase 1 can write CI configuration directly from a table instead of re-deriving intent.
- Vendor choice exists in exactly one file; no other module can name a vendor, so swapping or adding
  a provider is a binding change plus one adapter.
- Domains stay pure and synchronously testable: no ports, no vendor I/O, no Django-registry coupling
  in adapters.
- The two historic loopholes — admin and migrations — are closed with a rule and a path scope rather
  than with exceptions that grow.
- `config` is the single composition root and the root of the wiring dependencies; the production
  source graph stays acyclic because no runtime package imports back into it. An entry point cannot
  reach the composition root, so wiring cannot decay into service location.
- A webhook can reuse provider signature/codec mechanism without any package gaining the ability to
  call the provider.
- `ErpVariantMapping` has a home with real constraints, without a fifth layer or a fake domain.

**Negative / accepted cost**

- Small outbound capabilities acquire an `application` module that would have been a two-line call
  inside a domain (`application/notifications` for an email send). Accepted: the alternative is a
  domain performing HTTP.
- `integrations/*` importing `application/<a>/ports` is an upward-looking edge that must be
  whitelisted in the linter and explained to every newcomer. Accepted: it is the standard
  ports-and-adapters shape, and the port module's own import restrictions keep it acyclic.
- Injecting dependencies into entry points is more setup code at bootstrap than a one-line lookup in
  a view or task, and Django/Celery make the lookup tempting. Accepted: the lookup is exactly what
  turns the composition root into a service locator and creates the `config ↔ interfaces` cycle.
- Splitting a provider package into two surfaces is more structure than one `client.py`. Accepted:
  it is what lets the inbound boundary reuse signature code without opening the outbound client to
  every caller.
- Forbidding application→application will occasionally force a merge or an ADR where a shortcut
  would have "worked". Accepted: an application mesh hides workflows exactly like a domain mesh.
- The `core` allowlist per package family is more bookkeeping than "everyone may import `core`".
  Accepted: it is what keeps adapters pure Python and keeps Outbox/idempotency decisions below the
  transport boundary.

**Enforcement**

- **Phase 1** implements L1–L19 as `import-linter` contracts and A1–A13 as AST checks in CI; a
  violation fails the build (Phase 1 DoD).
- V1–V10 are review-checklist and behavioural-test items, carried in §15.3 of the
  [item 3 artifact](../architecture/phase-0/03-dependency-matrix.md); anything proposed against them
  needs a new ADR.
- Contract tests verify adapter↔port conformance and that `application/<a>/ports.py` imports without
  the Django app registry.
