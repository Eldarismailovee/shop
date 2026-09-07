# Claude Code setup for E-commerce Platform v1.3

This bundle is tuned for Claude Code + Claude Opus 5 at `high` effort, with strong code quality and reduced context/token waste.

## Install
Copy the bundle contents to the repository root. Keep:
- `CLAUDE.md`
- `.claude/settings.json`
- `.claude/rules/`
- `.claude/skills/`
- **`docs/architecture/` in full** — `AI_INDEX.md`, the frozen Phase-0 artifacts and
  `phase-0/PHASE0_STATUS.md`, the event registry and queue/failure-domain matrices under
  `events/`, the ERD under `erd/`, and the master `ecommerce_architecture_2026_roadmap.md`
- **`docs/adr/` in full** — ADR-0001…ADR-0016 and the ADR index

The instruction layer is not self-contained: `architecture-context`, `roadmap-next`,
`phase1-foundation` and `event-contract-change` all resolve authority through
`AI_INDEX.md` → a frozen Phase-0 artifact or accepted ADR → a master slice. `AI_INDEX.md` plus the
master alone is **not** sufficient — the frozen artifacts and ADRs are the binding refinements, and
several of them explicitly reject an illustrative master sketch.

If the repository already has any of these files, merge rather than blindly overwrite.

## Verify in Claude Code
Run:
- `/status` — confirm project settings are loaded.
- `/model` — confirm `claude-opus-5`.
- `/effort` — confirm `high`.
- `/memory` or `/context` — confirm project `CLAUDE.md`/rules.
- `/skills` — confirm the project skills.
- `/doctor` — catch invalid configuration/schema issues.

## Token-saving design
- `CLAUDE.md` is intentionally concise and does NOT import the 3500+ line master architecture.
- Path-scoped rules load only when matching code is touched.
- Skill bodies load only when relevant/invoked.
- Architecture reads are routed through `AI_INDEX.md` → the relevant frozen Phase-0 artifact/ADR → a targeted master heading. Accepted ADRs and `DONE / FROZEN` artifacts are binding refinements of the master.
- Generated/vendor/cache/secret paths are hard-excluded through `.claude/settings.json`.
- Workflow asks Claude to inspect a small call path first, read slices of large files, and run targeted tests.
- Auto memory is disabled in project settings to prevent an ever-growing startup context. Promote durable lessons into `CLAUDE.md`, a path rule, or a skill instead.

## About `.claudeignore`
Claude Code exclusions are enforced by `permissions.deny` in `.claude/settings.json`. This repository ships no `.claudeignore`.

If you additionally maintain a `.claudeignore` for a third-party or compatibility workflow, keep it aligned with the deny list.

## Useful skills
- `/architecture-context` — load only relevant architecture context (AI_INDEX → frozen artifact/ADR → master slice).
- `/implement-feature` — scoped implementation workflow.
- `/phase1-foundation` — Phase 1 scaffolding under the frozen launch cut.
- `/event-contract-change` — add/version/retire a registered async message contract.
- `/security-critical` — auth/checkout/payments/webhooks/PII hardening.
- `/storefront-performance` — catalog/projection/query performance.
- `/database-change` — models/migrations/transactions/indexes.
- `/integration-change` — ERP/maib/MIA/CRM/queues/outbox.
- `/review-change` — architecture/security/performance diff review.
- `/dependency-update` — current/version-sensitive package work.
- `/roadmap-next` — choose next roadmap slice.

## Recommended prompt style
For routine work, ask for the behavior directly. Example:
`Implement phase 2 Category and ProductVariant models with migrations and tests.`

For a critical path, explicitly name the concern:
`Implement maib webhook ingest and reconciliation. Use the security-critical and integration-change rules.`

For a review:
`Review my current diff for architecture, security, performance and missing tests.`

Avoid pasting the full architecture into prompts; it is already available on demand.

## Session hygiene
For a long implementation phase, keep one focused session. After a phase is complete, use `/compact` or start a fresh session before switching to an unrelated subsystem. This avoids carrying old diffs, tool output, and debugging history into the next task.
