---
name: implement-feature
description: Implement a scoped feature or bug fix with minimal repository exploration, architecture-safe changes, targeted tests, and concise verification. Use for normal coding tasks that change behavior.
effort: high
---
# Feature implementation workflow
1. Start from the requested behavior and directly named files/symbols.
2. Inspect only the immediate call path and tests; initial target is 4–6 files.
3. If the work crosses domains or touches a critical invariant, use `architecture-context` before editing — accepted ADRs and frozen Phase-0 artifacts outrank an illustrative master sketch.
4. Prefer existing project abstractions and pinned dependencies. Avoid unrelated refactors and speculative extensibility.
5. Preserve layer boundaries and use `public.py` contracts across domains. `interfaces`/`tasks` never import `config`/`integrations`; only `config` binds an adapter.
6. Build only what is `FOUNDATION`/`MVP` at launch (item 14). Never add an empty `LATER` package, null adapter, `try: import` fallback, `INSTALLED_APPS` probe or settings-gated unreachable path — absence is the absence of a call. For scaffolding work use `phase1-foundation`; for a message contract use `event-contract-change`.
7. Add the smallest sufficient tests: regression test first for a bug; unit/integration/contract/concurrency/query-budget according to risk.
8. Run targeted checks while iterating; run broader checks only at final gate if scope warrants them.
9. Review the diff for boundary leaks, race conditions, N+1, unsafe retries, client-trusted state, and accidental feature creep.
10. Final response: changed files, behavior, tests/checks run, remaining risk. Keep it short.
