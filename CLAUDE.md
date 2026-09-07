# E-commerce Platform — Claude Code instructions

## Mission
Build the Moldova RO/RU e-commerce platform described in `docs/architecture/ecommerce_architecture_2026_roadmap.md`.
Architecture baseline: v1.3 Security, Performance & Modular Architecture Hardened.
**Phase 0 Architecture Freeze is COMPLETE / FROZEN** (items 1–15, ADR-0001…ADR-0016). Phase 0 produced
documents and decisions only; no Django code, package, model, migration, setting or dependency exists yet.

## Architecture authority
Read in this order and stop as soon as the question is answered:
1. `docs/architecture/AI_INDEX.md`;
2. the relevant **frozen** artifact (`docs/architecture/phase-0/**`) and/or accepted ADR (`docs/adr/**`);
3. only then the matching master slice, by exact heading.

- Accepted ADRs and `DONE / FROZEN` Phase-0 artifacts are **binding refinements of the master**, not a
  weaker layer under it. `docs/architecture/phase-0/PHASE0_STATUS.md` is the status index.
- Where a frozen artifact explicitly refines, narrows or **rejects** an illustrative master sketch
  (a sample routing table, a sample column, a sample scope name, a sample guard), **follow the frozen
  artifact** and say so; do not re-derive the rejected sketch from the master.
- **Never edit an accepted ADR or a frozen artifact in place.** A genuine architecture change is a
  **new ADR that supersedes** the one it changes. Correcting a rule is not a code-change side effect.
- Do not read the master end-to-end. Use the `architecture-context` skill or search for the exact heading.

## Context budget
- Keep this repository investigation narrow. Start from user-mentioned files, `git diff`, symbols, and direct dependencies.
- For source files over ~400 lines, search for symbols first and read bounded sections.
- Initial exploration target: at most 4–6 relevant files. Expand only when evidence shows another dependency matters.
- Do not recursively inspect generated/vendor/cache directories. Exclusions are enforced in `.claude/settings.json`.
- Do not reread unchanged files unless needed to verify a later edit.
- Prefer targeted tests. Run the broad suite only when the change crosses domains or the targeted suite cannot establish safety.
- Keep progress and final summaries compact. Do not restate large code blocks that already exist in files.
- Use subagents only for genuinely independent parallel investigations; routine tasks stay in one agent to avoid duplicate context/tool reads.

## Current-code rule
- Prefer the versions pinned by this repository and its lockfiles.
- For a new dependency, framework API, security-sensitive API, or version-specific behavior, verify the installed/pinned version first. If current upstream behavior matters, consult official documentation/changelog before coding.
- Do not upgrade unrelated dependencies as part of a feature or bug fix.
- Implement the real general solution; do not hard-code behavior to satisfy a specific test.

## Architecture: four layers
Dependency direction is `interfaces -> application -> domains -> core`; skipping a layer downward is
legal, skipping sideways or upward is not.
- `core/`: knows no domain.
- `domains/*`: knows only itself + `core`; domains do not import other domains.
- `application/*`: owns cross-domain orchestration/read applications and calls domains only through `<domain>.public` + immutable DTO/value objects. Application → application is forbidden.
- `interfaces/*`: I/O only: HTTP/HTMX/DRF/admin/webhooks/CLI; translate DTOs to/from external representations.
- `integrations/*`: pure Python anti-corruption adapters for vendors; no Django models, no business state.
- `tasks/*`: thin Celery transport wrappers; business logic stays in application/domain code.
- `config/` is the **single composition root** — the only package that binds a concrete adapter to a port and injects it. `interfaces/*` and `tasks/*` never import `config/*`, and `tasks/*` never imports `integrations/*`.
- Enforce boundaries with `import-linter`/AST contract tests. Never bypass a boundary because a direct model import is shorter.

## Domain contracts
- `public.py` is the only external entry point of a domain; `application/<a>/public.py` is the application-entry convention.
- Do not expose ORM model instances or QuerySets across domain boundaries. Use frozen DTOs/value objects.
- Cross-domain workflows have one owner in `application/`; e.g. order placement belongs to `application/checkout`.
- Storefront read-model belongs to `application/storefront`, not `domains/catalog`.

## Correctness invariants
- PostgreSQL is the source of truth for orders, payments, inventory, reservations, idempotency, consent, and legal data. Redis is disposable acceleration.
- `Product` and sellable `ProductVariant/SKU` are separate. Cart/Order/Inventory/Price point to SKU.
- `CheckoutSession` and `Order` are separate.
- Money in domain/application code is `Money(minor: int, currency)` with an explicit currency; storage uses minor units. No float money, no inferred currency, no implicit FX.
- External locators use `PublicId` (UUIDv7) or purpose-bound signed tokens; internal bigint PKs do not appear in URLs/APIs. Message identity is the **distinct** type `EventId` over the same value space.
- Private objects are fetched through actor-scoped selectors/policies; no direct unscoped `.get()` from request identifiers.
- Inventory uses atomic reservation state transitions + DB constraints; no read-then-decrement stock logic.
- Orders store immutable commercial snapshots.
- External HTTP is outside critical DB transactions.
- Webhook path is durable ingest -> worker/state machine -> reconciliation.

## Idempotency — five separated mechanisms (ADR-0015)
None is derivable from another; do not collapse them or reuse one name for another.
1. **local command `IdempotencyKey`** — `UNIQUE (scope, key)` + principal binding + a canonical *semantic* request fingerprint. Platform-owned bounded `scope`; opaque `key`; a key is never an authorization or an object-access token.
2. **Inbox + `EventId`** — message-delivery identity; one effect per `event_id` per consumer.
3. **provider `external_event_id`** — inbound webhook dedupe.
4. **outbound provider idempotency key** — retry safety for a provider call.
5. **domain `UNIQUE` + state machine** — the permanent business effect. A permanent business rule lives here, never in a retention-limited idempotency row.

ADR-0015's *claim + effect + replayable completion commit together, rollback leaves no durable claim*
lifecycle applies **only** to a command scope whose protected effect is **one local ACID transaction**.
**Provider I/O is never that effect**: a provider call is strictly post-commit under its own provider
idempotency key and reconciliation. A scope *name* like `payment.initialize` proves nothing about shape —
master `# 20.4`'s scope names are illustrative. No durable `processing`/`failed` state in the generic
mechanism; expiry ends the replay promise.

## Async message contracts
- Envelope is exactly `event_id`, `event_type`, `schema_version`, `occurred_at`; the trace extension is the closed four-field TCE `trace_id`, `producer_span_id`, `request_id`, `causation_event_id`. No `correlation_id`, no metadata bag, no ancestry path. A generic message field is **never** named `idempotency_key`.
- Only a **registered** `(event_type, schema_version)` may be emitted; a published version is immutable (an additive field is a new version); consumers support exact versions with registered upcasters.
- Unknown type / unsupported version / invalid contract → **durable QUARANTINE + alert**, never silently handled, coerced or marked HANDLED. Understood work that exhausts its execution budget → **operational dead-letter for that consumer delivery**. The two are different states and neither is called "failed".
- PostgreSQL holds the canonical terminal state; the **broker DLQ is transport only**.
- The unit of failure, terminal identity and replay is a **consumer delivery**: two consumers of one `event_id` are independent, one may succeed while another dead-letters, and replay is scoped to the failed consumer delivery and never rebroadcasts to a sibling that already succeeded.
- Transport routing is assigned **per consumer**, never by the producer and never per message version; a routing change never bumps `schema_version`. `schema_version` is not a source or ordering version.

## Storefront/performance invariants
- Catalog grid/API reads `ProductListingProjection`, not OLTP JOIN chains; a miss never falls back to cross-domain joins in the request.
- Storefront selector returns DTOs used by both Web and DRF.
- EAV is truth/admin/comparison data, not the hot filtering path. Facets use projection arrays/promoted typed columns with same-variant existential matching.
- **Projection convergence is compare-and-set, not source ordering (ADR-0014).** A trigger is a *dirty-identity signal* only. The writer observes the row's `projection_revision` **before** every source read's visibility point, rebuilds the **whole candidate** from **authoritative** current state through `<domain>.public` batch selectors, and commits only if the observed token is still **equal** (equality only — never `>`). A guard miss discards the candidate whole, re-observes and rebuilds as ordinary contention. An unchanged candidate **writes nothing** — no `UPDATE`, no token advance, no `updated_at`. `source_version`, monotonic source-version guards and producer-supplied freshness tokens are **not adopted**; no producer supplies a version and no domain learns it is projected. Rebuild, reconciliation and replay use the identical protocol; there is no force-write path.
- The projection is fully rebuildable from OLTP without event history, and is never checkout truth or a security/authorization basis.
- Preserve fixed query budgets and N+1 tests.
- Avoid `SELECT *` on heavy JSON/text/payload models; use shaped selectors / `.only()` / `.defer()` where appropriate.
- Batch ERP/catalog changes with set-based SQL and coalesced events; suppress no-op updates.
- Cache misses use single-flight + stale fallback for shared navigation/read fragments.

## Database reads at launch (ADR-0016)
- **No application read goes to a PostgreSQL replica at launch.** Ship no replica alias, no router, and no sticky-primary machinery for a replica that is not used.
- A global "all SELECT → replica" router is forbidden **permanently**.
- **Read replica ≠ HA standby.** Backups/PITR/DR/failover standbys are legitimate and simply never an application read target; a promoted standby *is* the primary.
- A future replica is admitted only through a recorded evidence review and then **per read path**, with owner, staleness semantics, read-your-own-writes, lag safety, fallback-to-primary, metrics and tests. Correctness reads — placement, inventory, pricing-for-write, payments/reconciliation, idempotency claim and ownership, actor/security state, Outbox relay claiming, Inbox dedupe, webhook ingest, and the projection builder's source reads — are never replica candidates whatever the gate does.

## Security and integrations
- Validate all external input at boundaries; never trust client totals, IDs, ownership, callback status, or vendor payload shape.
- Payments/webhooks: verify raw-body signature, timestamp/replay window, **exact** amount/currency (no tolerance), event uniqueness, state transition, and reconciliation.
- Every outbound vendor client has explicit connect/read/total timeout, bounded jittered retry, circuit breaker, vendor DTO, an isolated logical failure domain, and a durable terminal state with an authorised replay procedure.
- Keep secrets/PII out of logs, traces, fixtures, snapshots, prompts, and generated docs. Trace metadata never decides authorization, identity, money, idempotency, ordering or routing.
- Consent/privacy lifecycle and account anonymization are server-side concerns.

## Working method
1. Inspect the smallest relevant context.
2. State a short implementation plan only for multi-file/cross-domain work.
3. Make the smallest coherent change that preserves architecture.
4. Add/update tests at the same abstraction level as the change.
5. Run targeted formatting/lint/type/tests; add architecture/query/security checks when relevant.
6. Review the diff for boundary leaks, N+1, race conditions, unsafe retries, and accidental feature creep.

## Change gates
Before finishing changes to critical paths, verify as applicable:
- `import-linter` / architecture contracts;
- unit + integration tests;
- concurrency/idempotency tests for checkout/inventory/payments;
- query-budget tests for storefront/read paths;
- migration safety and constraints/indexes;
- event registry / schema compatibility and consumer version support;
- no new secrets or generated artifacts.

## Phase 1 launch discipline
- Create package skeletons only for, per item 14's launch-cut matrix (`docs/architecture/phase-0/14-mvp-later-module-marking.md`):
  - **`FOUNDATION`** mechanisms;
  - **`MVP`** modules/capabilities;
  - **`MVP — REDUCED SCOPE`** modules, containing only their enumerated launch scope.

  Do not create `LATER` modules/capabilities or open `INFRASTRUCTURE GATE`s. Use the `phase1-foundation` skill.
- **MVP cuts features, never invariants.** Absence of a `LATER` capability is expressed by the **absence of a call**. Forbidden by name: empty `LATER` packages (including `domains/analytics`), null/no-op adapters, fake provider adapters, `try: import` fallbacks, `INSTALLED_APPS` probing, behaviour that changes on package presence, settings-gated unreachable code, adapter-less UI options, and queues provisioned for unenabled workloads.
- A mechanism stays `FOUNDATION` even when its consumer is `LATER` (event versioning without analytics events; failure-domain machinery without `ext.crm`). A frozen *definition* is never a launch *commitment*.
- All **infrastructure gates stay closed**: OpenSearch, read replica, PgBouncer, separate analytics/search/image services, ACID-core extraction, PostGIS.
- Where Phase 1 must choose something Phase 0 deliberately deferred, record the choice in that phase's artifact; where it would change a frozen rule, write a superseding ADR.
