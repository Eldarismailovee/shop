---
name: architecture-context
description: Load the smallest relevant slice of the e-commerce architecture before design, refactor, cross-domain, checkout/payment/inventory, storefront, event, or roadmap decisions. Use when architectural constraints can change the correct implementation.
allowed-tools: Read Grep Glob
effort: high
---
# Architecture context

Phase 0 is **COMPLETE / FROZEN** (items 1–15, ADR-0001…ADR-0016). Read in authority order and stop as
soon as the question is answered.

1. Read `docs/architecture/AI_INDEX.md`. Its "Always-on invariants" and "Frozen decision artifacts"
   sections usually answer the question outright — many entries are already narrower than the master.
2. Open the **frozen artifact and/or accepted ADR** the index names: `docs/architecture/phase-0/**`,
   `docs/adr/**`. Use `docs/architecture/phase-0/PHASE0_STATUS.md` for status and for what each item
   deliberately left open.
3. Only then grep `docs/architecture/ecommerce_architecture_2026_roadmap.md` for the exact heading and
   read a bounded slice. Never read the master end-to-end.

## Authority rules
- Accepted ADRs and `DONE / FROZEN` artifacts are **binding refinements of the master**, not a weaker
  layer beneath it.
- Where a frozen artifact explicitly refines, narrows or **rejects** an illustrative master sketch,
  **follow the frozen artifact** and name it. Known cases: master `# 7.6`'s `source_version` guard
  (rejected by ADR-0014), `# 20.1`'s `CELERY_TASK_ROUTES` buckets (refined by ADR-0010), `# 20.6`'s
  `core/events` as contract home (refined by ADR-0009), `# 20.2`/`# 20.6`'s `span_id` (renamed
  `producer_span_id` by ADR-0011), `# 5.2`'s `processing`/`failed` idempotency sketch and `# 20.4`'s
  illustrative scope names (refined by ADR-0015), `# 12.2` step 8's webhook Outbox marker (already
  superseded by L13), `# 7.2`'s product-level union array (refined by ADR-0008), and master illustrative
  event types (`catalog.project.batch`, `review.approved`, `payment.webhook.received` — not adopted).
- Extract at most 8 task-specific invariants before editing.
- If the task conflicts with a frozen decision, preserve safety/correctness and **flag the conflict**;
  do not silently invent a new architecture.
- If an architectural decision truly must change: **never edit an accepted ADR or a frozen artifact in
  place.** Write a **new ADR that supersedes** the one it changes, and say so explicitly rather than
  folding it into a code change. Phase-1-and-later choices that Phase 0 deliberately deferred are
  recorded in that phase's artifact instead.
