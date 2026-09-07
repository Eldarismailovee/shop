---
name: review-change
description: Review current changes or a diff for correctness, architecture boundaries, security, performance, migrations, and missing tests. Use when asked to review, audit, or sanity-check code.
effort: high
---
# Review workflow
- Review the diff first; do not scan the whole repository.
- Open only changed files plus direct contracts/tests needed to validate behavior.
- Classify findings by severity and provide file:line evidence.
- Check: cross-domain imports; `config`/`integrations` imported from `interfaces`/`tasks`; leaked ORM objects or QuerySets across a `public.py`; ownership/IDOR; Money/PublicId/`EventId` misuse; transaction/race issues; raw vendor payload leakage; unsafe retry/webhook behavior; N+1/query budget; migration/index hazards; missing tests.
- Idempotency: are the five mechanisms kept separate (local command `IdempotencyKey`, Inbox/`EventId`, provider `external_event_id`, outbound provider key, domain `UNIQUE`/state machine)? Is any provider call inside the claim transaction? Is a durable `processing`/`failed` state being introduced? Is a permanent business rule resting on a retention-limited row?
- Events: envelope `event_id`/`event_type`/`schema_version`/`occurred_at`; TCE exactly the four fields; no field called `idempotency_key`; unknown/unsupported/invalid → durable quarantine + alert; execution exhaustion → operational dead-letter for that consumer delivery; PostgreSQL terminal state canonical, broker DLQ transport only; replay consumer-delivery scoped.
- Projection: convergence by `projection_revision` observe → whole-candidate rebuild from authoritative state → equality CAS; guard miss discards and rebuilds; unchanged candidate writes nothing. Flag any reappearance of `source_version`, a monotonic source-version guard, a producer freshness token or a force-write path.
- Launch discipline: any replica alias/router/sticky-primary machinery, empty `LATER` package, null/no-op adapter, `try: import` fallback, `INSTALLED_APPS` probe, or settings-gated unreachable code is a finding.
- A change that contradicts a frozen artifact or accepted ADR is a finding; an in-place edit of an accepted ADR is always a finding.
- Distinguish confirmed bug from design suggestion.
- Do not propose broad rewrites when a local fix preserves the architecture.
- If no significant findings, say so and mention residual untested risks briefly.
