# Architecture Decision Records

Decisions that constrain the implementation of the platform described in
`docs/architecture/ecommerce_architecture_2026_roadmap.md` (baseline v1.3, frozen 2026-09-03).

An ADR records **one** decision, its context and its cost. It is short, immutable once accepted,
and superseded by a new ADR rather than edited. The master architecture document stays the
canonical reference for *what* the system is; ADRs record *why* a specific modelling or boundary
choice was made when the master leaves room for more than one.

## Index

| # | Title | Status | Phase | Area |
|---|---|---|---|---|
| [0001](0001-product-vs-sku-sellable-unit.md) | Product vs ProductVariant: the SKU is the only sellable unit | Accepted — Frozen | 0 | catalog, identity |
| [0002](0002-typed-eav-source-of-truth.md) | Typed EAV is the source of truth, and its type contract is enforced by PostgreSQL | Accepted — Frozen | 0 | catalog, attributes |
| [0003](0003-catalog-boundary-vs-storefront-projection.md) | Catalog domain boundary: no price, no stock, no ERP identity, no storefront projection | Accepted — Frozen | 0 | boundaries, storefront, i18n |
| [0004](0004-four-layer-modular-monolith.md) | Four-layer modular monolith: core / domains / application / interfaces | Accepted — Frozen | 0 | layering, boundaries, transactions, authorization |
| [0005](0005-dependency-and-integration-wiring.md) | Dependency matrix, integration ports and the single composition root | Accepted — Frozen | 0 | boundaries, imports, integrations, wiring |
| [0006](0006-public-contract-primitives.md) | `core` primitives of the public contract: the actor and the structural error categories | Accepted — Frozen | 0 | public contracts, authorization, errors, `core` allowlists |
| [0007](0007-place-order-atomic-idempotent-boundary.md) | `place_order`: one local ACID placement transaction, in-transaction idempotency claim, provider payment strictly post-commit | Accepted — Frozen | 0 | checkout, transactions, idempotency, payments |
| [0008](0008-storefront-listing-projection.md) | `ProductListingProjection`: an `application/storefront`-owned derived serving read model with same-variant facet correctness | Accepted — Frozen | 0 | storefront, read models, facets, consistency |
| [0009](0009-event-contract-versioning.md) | Event contracts: producer-owned, immutably versioned, consumed by exact version | Accepted — Frozen | 0 | async messaging, Outbox/Inbox, contracts, versioning, idempotency |
| [0010](0010-async-failure-domain-isolation.md) | Asynchronous failure-domain isolation, PostgreSQL-canonical terminal state, and the payment split | Accepted — Frozen | 0 | async transport, queues, retries, DLQ/quarantine, replay, capacity |
| [0011](0011-async-trace-causality-envelope.md) | The asynchronous trace/causality envelope: four closed fields, durable in the Outbox, immutable through replay | Accepted — Frozen | 0 | observability, Outbox/Inbox, envelope, causality, replay |
| [0012](0012-money-currency-scoped-partial-order.md) | `Money` is currency-scoped and partially ordered: no automatic cross-currency ordering | Accepted — Frozen | 0 | money, `core` primitives, comparison |
| [0013](0013-event-id-distinct-identity-type.md) | `EventId` is a semantic type distinct from `PublicId`, over the same UUIDv7 value space | Accepted — Frozen | 0 | identity, `core` primitives, async messaging |
| [0014](0014-storefront-projection-convergence.md) | Storefront projection convergence: an application-owned per-row CAS over a current-state rebuild, not a producer-supplied source version | Accepted — Frozen | 0 | storefront, read models, concurrency, convergence |
| [0015](0015-postgresql-command-idempotency.md) | Command idempotency: a PostgreSQL-canonical `(scope, key)` claim committed with the effect it protects | Accepted — Frozen | 0 | idempotency, commands, transactions, retention, security |
| [0016](0016-no-application-read-replica-at-launch.md) | No application read replica at launch: primary is the default read source, and a future replica is a per-path, evidence-gated opt-in | Accepted — Frozen | 0 | database topology, consistency, read paths, infrastructure gates |

Related frozen artifacts:

- [ERD — Catalog: Product / SKU / typed attributes](../architecture/erd/catalog_product_sku_attributes.md)
- [Phase 0 item 2 — The four architectural layers](../architecture/phase-0/02-four-layer-architecture.md)
- [Phase 0 item 3 — Dependency matrix and allowed imports](../architecture/phase-0/03-dependency-matrix.md)
- [Phase 0 item 4 — `public.py` contract template per domain](../architecture/phase-0/04-domain-public-contract.md)
- [Phase 0 item 5 — `application/checkout` ownership and contract of `place_order`](../architecture/phase-0/05-place-order-use-case.md)
- [Phase 0 item 6 — `application/storefront` ownership and contract of `ProductListingProjection`](../architecture/phase-0/06-storefront-listing-projection.md)
- [Phase 0 item 7 — storefront DTO contract (`ProductCard` / Facet / listing result)](../architecture/phase-0/07-storefront-dto-contract.md) — no ADR of its own; it instantiates ADR-0008 and the item 4 template
- [Phase 0 item 8 — event registry and versioning policy](../architecture/phase-0/08-event-registry-versioning.md)
- [Asynchronous message registry](../architecture/events/event-registry.md) — the index itself; ships with no entries
- [Phase 0 item 9 — queue / failure-domain matrix and DLQ policy](../architecture/phase-0/09-queue-failure-domain-dlq.md)
- [Queue / failure-domain matrix](../architecture/events/queue-failure-domain-matrix.md) — the operational routing policy; names no `event_type`
- [Phase 0 item 10 — trace and causality propagation through Outbox/Inbox](../architecture/phase-0/10-async-trace-propagation.md)
- [Phase 0 item 11 — `Money` and public identity (`PublicId`, `EventId`)](../architecture/phase-0/11-money-public-id.md)
- [Phase 0 item 12 — storefront projection convergence: the guard token and the guarded write](../architecture/phase-0/12-source-version-guarded-upsert.md)
- [Phase 0 item 13 — the analytics MVP decision and the popularity source contract](../architecture/phase-0/13-analytics-mvp.md) — no ADR of its own; it selects a branch the master already authorises
- [Phase 0 item 14 — the MVP / later launch cut per module](../architecture/phase-0/14-mvp-later-module-marking.md) — no ADR of its own; it selects feature scope master `# 25` / `# 26` already authorise
- [Phase 0 item 15 — ADR closure and the Phase 0 Architecture Freeze](../architecture/phase-0/15-adr-closure.md) — the five-way coverage audit, the two ADRs it created, and the Phase 1 handoff
- [Phase 0 status tracker](../architecture/phase-0/PHASE0_STATUS.md) — **Phase 0 is COMPLETE / FROZEN**

## When an ADR is required

- a domain boundary moves, or a new cross-domain owner is assigned;
- a public contract (`public.py` DTO, event schema, event version) changes shape;
- an identity, money, idempotency or consistency rule changes;
- a read model or projection strategy changes;
- a frozen ERD invariant changes — including the supplementary decisions D-9…D-13;
- a deferred item is un-deferred (multi-valued attributes, category↔attribute applicability,
  read replica, OpenSearch, …).

Routine implementation choices inside an already-decided boundary do not need an ADR.

## Statuses

| Status | Meaning |
|---|---|
| `Proposed` | Under discussion; do not build against it. |
| `Accepted` | Decided and binding. |
| `Accepted — Frozen` | Decided, binding, and part of a frozen artifact. Changing it requires a new ADR that supersedes this one. |
| `Superseded by ADR-NNNN` | Historical. Kept for the reasoning, not for the rule. |
| `Deprecated` | No longer applies and has no successor. |

## Numbering and file name

Four digits, monotonically increasing, never reused:
`NNNN-short-kebab-case-title.md`.

## Template

```markdown
# ADR-NNNN — <decision in one line>

- **Status:** Proposed | Accepted | Accepted — Frozen | Superseded by ADR-NNNN | Deprecated
- **Date:** YYYY-MM-DD
- **Phase:** <roadmap phase>
- **Supersedes:** ADR-NNNN | —
- **Related:** <ADRs, ERDs, master headings>

## Context

The forces in play: what problem, what constraints, what makes this non-obvious.
Reference the master by heading, never by pasting it.

## Decision

What we decided, in the imperative. Include the enforceable form — constraint, contract,
lint rule — not only the intent. State explicitly what is *out* of scope of the decision.

## Consequences

**Positive** — what this buys.

**Negative / accepted cost** — what it costs, and why the cost is acceptable.

**Enforcement** — which phase implements it, and which check (constraint, `import-linter`
contract, test) fails if it is violated.
```
