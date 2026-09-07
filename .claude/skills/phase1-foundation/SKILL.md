---
name: phase1-foundation
description: Scaffold Phase 1 foundation work — package skeletons, core primitives, enforcement harness, Outbox/Inbox and IdempotencyKey schemas — under the frozen Phase 0 launch cut. Use when creating packages, settings, the composition root, or the first migrations.
allowed-tools: Read Grep Glob Edit Write Bash
effort: high
---
# Phase 1 foundation

> **Scope guard.** This skill defines the allowed/required Phase-1 foundation **envelope**. Implement
> only the slice explicitly requested by the user. Do not scaffold the entire Phase-1 list in one
> invocation unless the user explicitly asks for the whole foundation phase. The "What to create"
> section below is the boundary of what is permitted, not a work order.

Phase 0 is **COMPLETE / FROZEN**; Phase 1 is the first phase that writes code. Read
`docs/architecture/phase-0/15-adr-closure.md` §15 (Phase 1 handoff) and
`docs/architecture/phase-0/14-mvp-later-module-marking.md` §5 (launch-cut matrix) before creating
anything.

## What to create
- **Package skeletons only for** `FOUNDATION` mechanisms, `MVP` modules/capabilities, and
  `MVP — REDUCED SCOPE` modules **containing only their enumerated launch scope**.
- `core` primitives: `Money` + `RoundingPolicy`, `PublicId` and `EventId` as runtime-distinct value
  types over UUIDv7 with one non-exported internal mechanism, the actor primitive and the structural
  error categories (ADR-0006), and `core.events` as **mechanism only** with the registry shipping
  **empty**.
- Enforcement harness: `import-linter` contracts for L1–L21, the recorded AST/static checks, and the
  query-budget / N+1 harness, wired into CI.
- `IdempotencyKey` model and migration per ADR-0015: `UNIQUE (scope, key)`, durable principal
  identification, fingerprint column, bounded semantic result storage, retention columns, indexes that
  keep the claim path off any heavy column. **No durable `processing`/`failed` state, no polymorphic
  cross-domain FK.**
- Outbox/Inbox initial schema carrying the four TCE fields (`trace_id`, `producer_span_id`,
  `request_id`, `causation_event_id`) **from the first migration** — no partitioning migration precedes
  them — plus the PostgreSQL-canonical quarantine and dead-letter tables.
- `config/` as the single composition root, with **primary-only** database configuration.

## What must not be created
- **No empty `LATER` package** — not `domains/analytics`, not `domains/tradein`, not
  `integrations/crm`, not `integrations/chatwoot`.
- No null/no-op adapter, fake provider adapter or placeholder repository; no `try: import` fallback;
  no `INSTALLED_APPS` probing; no behaviour that changes on package presence; no settings-gated
  unreachable code; no adapter-less UI option.
- No queue, route or worker provisioned for an unenabled workload — `ext.sms` and `ext.crm` stay
  **defined but not provisioned**.
- No replica alias, database router or sticky-primary machinery; **no infrastructure gate is opened**
  (OpenSearch, read replica, PgBouncer, separate services, ACID-core extraction, PostGIS).
- Absence of a `LATER` capability is expressed by the **absence of a call**, never by a stub.

## Rules
- A mechanism stays `FOUNDATION` even when its consumer is `LATER`: build event versioning without
  analytics events, and failure-domain machinery without `ext.crm`.
- The launch build is a **strict subgraph** of the eventual system — admitting a later module later
  must add nodes and edges and rewrite none.
- Every `A*`/`C*`/`V*` check recorded in items 3–15 is an obligation on Phase 1 onward; none is
  enforced yet. Wire the ones your change makes checkable.
- Where Phase 1 must choose something Phase 0 deliberately deferred (a `RoundingPolicy` member set, a
  column type, an index, the injection mechanism), **record the choice in the phase artifact**. Where
  it would change a frozen rule, **write a superseding ADR** — never edit an accepted ADR in place.
