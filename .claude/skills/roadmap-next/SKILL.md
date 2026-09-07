---
name: roadmap-next
description: Choose or plan the next implementation step from the frozen architecture without loading the whole master document. Use when asked what to build next, how to sequence work, or to create a sprint/task plan.
allowed-tools: Read Grep
effort: high
---
# Roadmap planning

Consult these before proposing any implementation work:

1. `docs/architecture/AI_INDEX.md` — always-on invariants and the frozen-artifact map.
2. `docs/architecture/phase-0/PHASE0_STATUS.md` — Phase 0 is **COMPLETE / FROZEN**; each item's notes
   also list what it deliberately left open, which is where legitimate next work lives.
3. `docs/architecture/phase-0/14-mvp-later-module-marking.md` — the **authoritative launch cut**.
4. `docs/architecture/phase-0/15-adr-closure.md` §15 — the **Phase 1 handoff** obligations.
5. Only then, if still needed, grep the master for `# 25. Roadmap` and read the target phase slice.

## Rules
- **A roadmap phase number is never launch membership.** Launch membership comes from item 14's matrix:
  `FOUNDATION` / `MVP` / `MVP — REDUCED SCOPE` / `LATER` / `INFRASTRUCTURE GATE`. When a phase list and
  the MVP line disagree, the MVP line wins.
- MVP cuts **features**, never correctness, security, performance or module-boundary invariants.
- Do not propose work for a `LATER` module, and do not propose an empty package, null adapter, stub or
  probe to "prepare" for one. Absence is the absence of a call.
- Do not propose opening an `INFRASTRUCTURE GATE` (OpenSearch, read replica, PgBouncer, separate
  services, ACID-core extraction, PostGIS) without a recorded evidence review; ADR-0016 already froze
  the read-replica gate's admission contract.
- A mechanism can be `FOUNDATION` while its consumer is `LATER` — sequence the mechanism, not the
  consumer.
- Identify prerequisites already present in the repo before proposing work; the repository currently
  holds documents only.
- If the next step is Phase 1 scaffolding, use the `phase1-foundation` skill.
- Produce a short ordered plan with acceptance criteria and tests — not a restatement of the roadmap.
