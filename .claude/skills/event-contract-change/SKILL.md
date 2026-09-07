---
name: event-contract-change
description: Introduce, version, deprecate or retire a registered async message contract, or change a consumer declaration, payload, routing assignment or registry entry. Use whenever an event_type or schema_version is added or changed.
allowed-tools: Read Grep Glob Edit Write
effort: high
---
# Event contract change

Governed by ADR-0009 (contracts/versioning), ADR-0010 (transport/failure domains), ADR-0011 (TCE),
ADR-0013 (`EventId`). The registry index is `docs/architecture/events/event-registry.md` — it ships
**empty**; every real `event_type` is authored by its owning module's phase.

## Ownership and boundary
- **One semantic owner per `event_type`**, following the fact. No central `events` domain, no shared
  business-message package, no business message type in `core` (`core.events` is mechanism only).
  Transport packages (`interfaces/*`, `tasks/*`, `integrations/*`) are never owners or producers.
- The async boundary is a **data** boundary: no consumer imports a producer's contract. The path is
  canonical owner-internal source → deterministic generation → checked-in versioned artifact →
  `core.events` validator. The **composition root may not import an owner-internal contract either**.
- Naming: lowercase, dot-separated, owner-qualified first segment; no version suffix, no
  module/class/queue/transport word, no vendor name as first segment. Meaning is immutable once
  published; a retired name is never reused. Re-homing an owner is retire-and-introduce at
  `schema_version = 1` under an ADR, never an in-place edit.

## Envelope and payload
- Envelope: exactly `event_id`, `event_type`, `schema_version`, `occurred_at`. `occurred_at` is
  business truth time in aware UTC, unchanged by retries, and **not** an ordering key.
- The one reserved extension point is spent: the closed four-field TCE `trace_id`, `producer_span_id`,
  `request_id`, `causation_event_id`. Nothing else may be added to the envelope.
- **Never call a message field `idempotency_key`.** Delivery identity is `event_id`; a command's local
  key is `IdempotencyKey (scope, key)`; a provider retry uses the provider's key.
- Payload: explicitly typed, immutable, serialization-neutral, bounded, deterministic. No ORM/QuerySet/
  lazy object, no Django/DRF/Celery type, no provider SDK or wire DTO, no row dumps or `__dict__`, no
  `dict[str, Any]`. Money in minor units with explicit currency; explicit units everywhere.
- Neither a full-aggregate snapshot nor a bare identifier: carry what the fact means. A consumer
  needing current authoritative state may re-read through the owning module's public contract **only
  where the frozen dependency graph permits that call** (item 8 SR3). This does **not** permit a
  domain → domain import: if the current-state coordination crosses domains, the owning **application**
  use case performs it. Never widen a dependency-matrix cell merely because an event consumer wants a
  synchronous re-read.
- Internal-only messages may carry internal identifiers; **externally consumed ones may not** — record
  the exposure classification per entry, and treat changing it as breaking.
- No secrets/tokens/credentials, no PII beyond need, no authorization decision from a payload, no actor
  in the envelope.

## Versioning
- `schema_version` is a positive integer from `1`, strictly increasing, never reused, versioning the
  **payload only**. It is not a source version, not an ordering key, and is never bumped for an
  implementation, broker, routing or trace change.
- **A published version is immutable.** An additive optional field is a **new version**. Same fact →
  new version; different fact → new `event_type`; a rename is retire-and-introduce.
- Consumers support **exact** versions — no "latest", no best-effort decode, no nearest-version
  coercion, no unknown-field tolerance. Cross-version movement is an explicit, total, pure **upcaster**
  registered between two registered versions of one type.
- Migration is **consumer-first**: consumers support the new version before any producer emits it.
  Dual-publish is discouraged; removing an old version requires evidence that nothing can still arrive.

## Consumer declarations
Each consumer declares, in the registry's mutable operational half: supported versions, its
**effect-idempotency mechanism with justification**, and its **failure-domain assignment**. An
`EVENT`'s independent consumers may legitimately differ; a `COMMAND` has exactly one declaration; a
zero-consumer `EVENT` needs no route. A producer never chooses routing.

Separately and without exception, **every** consumer durably retains first-seen `event_id` / type /
version / payload-fingerprint identity, so the same `event_id` with different content is always an
**integrity violation** rather than a duplicate. No entry may declare that detection unavailable, and
the business-effect mechanism never discharges this obligation.

## Failure semantics
- Unknown type / unsupported version / invalid payload / identity violation → **durable quarantine +
  alert**, committed **before** transport disposal, never marked HANDLED and never coerced.
- Understood work that exhausts its execution budget → **operational dead-letter for that consumer
  delivery**. Distinct from quarantine; neither is called "failed".
- PostgreSQL is canonical for both terminal states; the broker DLQ is transport only. Replay is
  consumer-delivery scoped, identity-preserving, and has no force-apply path.

## Checklist before finishing
- Registry entry added/updated with the immutable contract half and the mutable operational half;
  lineage declared **forward once** on the new row (no published row edited to add a back-pointer).
- One canonical schema source per version; everything else generated. No hand-written second schema.
- Validation at both edges against the **registered** schema, not the producer's current classes.
- Compatibility, upcaster, quarantine and replay tests. Confirm no dependency-matrix cell moved and no
  `public.py` export list widened — an event contract must never become a ninth export category.
