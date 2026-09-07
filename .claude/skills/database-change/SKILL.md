---
name: database-change
description: Design or review Django models, migrations, constraints, indexes, transaction boundaries, SQL/ORM queries, or high-volume PostgreSQL changes. Use whenever schema or transactional data behavior changes.
effort: high
---
# Database change
- Load relevant architecture context first for commercial/core tables.
- Express correctness invariants with DB constraints/unique constraints where possible.
- Keep money in integer minor units with an explicit currency (never `float`/`numeric`), and keep `PublicId`/`EventId` separate from the internal bigint PK.
- All application reads target primary; add no replica alias, router or sticky-primary machinery (ADR-0016).
- Keep the five idempotency mechanisms in separate tables/columns (local `IdempotencyKey (scope, key)`, Inbox/`EventId`, provider `external_event_id`, outbound provider key, domain `UNIQUE`/state machine); no durable `processing`/`failed` on the generic key and no polymorphic cross-domain FK.
- Outbox/Inbox carry the four TCE fields from the **initial** migration, before any partitioning migration; no TCE field is a partition, ordering or uniqueness key.
- Prefer set-based updates and no-op suppression for batches.
- Keep hot mutable tables lightly indexed; justify each new index by query shape.
- Avoid long transactions; perform computation before hot row locks.
- Consider migration locking/table rewrite/index-build impact on production volume.
- Use expand/contract for risky live schema changes.
- Add migration/schema tests plus concurrency/query tests where applicable.
- Performance claims need plan/measurement evidence, not intuition.
