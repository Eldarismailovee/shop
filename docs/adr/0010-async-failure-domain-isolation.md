# ADR-0010 — Asynchronous failure-domain isolation, PostgreSQL-canonical terminal state, and the payment split

- **Status:** Accepted — Frozen
- **Date:** 2026-09-05
- **Phase:** 0 — Architecture Freeze (item 9)
- **Supersedes:** —
- **Related:** [ADR-0004](0004-four-layer-modular-monolith.md), [ADR-0005](0005-dependency-and-integration-wiring.md),
  [ADR-0007](0007-place-order-atomic-idempotent-boundary.md), [ADR-0008](0008-storefront-listing-projection.md),
  [ADR-0009](0009-event-contract-versioning.md),
  [Phase 0 item 9](../architecture/phase-0/09-queue-failure-domain-dlq.md),
  [queue / failure-domain matrix](../architecture/events/queue-failure-domain-matrix.md),
  master `# 12.2`, `# 20.1`–`# 20.8`, `# 23.2`, `# 23.3`, `# 24.8`

## Context

ADR-0009 froze what an asynchronous message *means* and what happens semantically when it cannot be
understood. It deliberately left transport open: which queue carries the work, what shares worker
capacity with what, how failures are retried, and where a message goes when it can never succeed.

Master `# 20.1` states the goal in prose — *"разделение очередей только по high/default/low
недостаточно; главная изоляция строится по внешней зависимости"* — and gives an illustrative
`CELERY_TASK_ROUTES` block. The prose and the example disagree. The example routes by two rules at
once: `ext.erp` / `ext.crm` / `ext.email` / `ext.sms` are failure domains, while `core.high` /
`core.low` are the criticality buckets the same paragraph has just called insufficient. `core.high`
holds payment reconciliation *and* inventory expiry, and there is no queue at all for outbound
payment provider calls, even though master `# 12` makes payment initiation a post-commit provider
operation.

Four questions therefore had no binding answer, and each of them can be got wrong in a way that no
unit test catches and that only surfaces during an incident:

1. **Is isolation an architectural requirement or an operations tuning knob?** If it is only the
   latter, a deployment where one wedged integration starves a critical domain is merely unlucky
   rather than non-conformant, and nothing fails when it happens.
2. **What is the authoritative record of a terminally failed message?** Master says the event "does
   not disappear" and lands in *dead-letter storage/queue* without choosing between the two.
3. **Where does outbound payment work run?** Routing it beside payment reconciliation would let
   provider rate limiting delay the convergence of money that is already authorised.
4. **Is a message that cannot be understood the same operational state as one that was understood and
   failed?** Master, and most systems, call both "failed".

## Decision

### 1. Failure-domain isolation is an architectural requirement with reserved capacity

The platform's asynchronous work is partitioned into **logical failure domains**. Two workloads share
a normal-processing queue only when it is acceptable for one's latency, provider outage,
poison-message rate and retry storm to consume the other's worker capacity. Same broker, same
framework, same source (Outbox), low volume, code proximity and equal criticality are **never**
sufficient reasons to share.

Every `CRITICAL` domain has **reserved worker capacity** that no other domain can consume, whatever
that other domain's backlog. Autoscaling from one shared pool does **not** satisfy this: it reacts
after the contention it is meant to prevent, and it cannot help when the shared constraint is a
connection pool or a broker prefetch budget. Message **priority inside one worker pool is not
isolation** and may not be used to realise any isolation guarantee — priority orders which message a
free worker takes next; it does not bound what a running workload consumes.

The enforceable form: **a deployment configuration must exist in which, with `ext.erp` fully wedged
and saturated with retries, `core.payments` still converges, `ext.payments` still progresses for
unaffected providers, and `core.projection.incremental` still meets its freshness SLO.** This is a
contract test and a runbook exercise, not an aspiration.

Criticality (`CRITICAL` / `IMPORTANT` / `BEST_EFFORT`) governs **capacity, isolation and alerting
only**. It never governs durability, contract strength, validation or whether data may be lost, and no
business rule may be inferred from it.

Ten failure-domain **definitions** are frozen; no two share a worker pool. A frozen definition is not
a launch commitment: it fixes a domain's name, class, isolation rule, retry class, terminal namespace
and capacity relationship, while **which definitions are provisioned follows from which workloads are
actually enabled**, and the MVP/later cut per module remains item 14's decision. `ext.crm` is
explicitly conditional on that decision — its isolation rule binds if and when CRM is enabled, and it
carries no worker pool, terminal queue or on-call burden until then. **Merging or removing a frozen
domain definition requires a new ADR**, because each is an isolation guarantee the others were sized
against; that is a separate question from whether a feature is enabled at launch. Splitting
one logical domain into several physical queues for throughput is a Phase 1 decision that needs no
ADR, provided the isolation guarantee, the single terminal namespace and the single replay authority
survive.

**Out of scope:** worker counts, concurrency, prefetch, autoscaling policy, physical queue topology
and `CELERY_TASK_ROUTES` — Phase 1 and operations.

### 2. PostgreSQL is the canonical durable truth for terminal state; the broker DLQ is transport

Both terminal states — contract quarantine and operational dead-letter — are canonically durable in
**PostgreSQL**. A broker dead-letter queue is a parking place and an operational reference; it is
**never** the sole record and is never consulted as the authority.

A broker DLQ can be lost to a restart with non-durable configuration, a topology reconfiguration, a
queue redeclaration with different arguments, a purge, a TTL, a max-length policy or a broker
migration. None of those may lose a payment reconciliation that needs manual completion. This is
R1 — PostgreSQL is the source of truth, Redis and the broker are disposable — applied to failure
state.

The payload need not be stored twice: where the original Outbox or Inbox row still retains the message
within its retention window, the terminal record may reference it. The requirement is **sufficiency
for replay and diagnosis**, not duplication.

The transport ordering is fixed: *validate → persist the durable terminal record → COMMIT → only then
remove the delivery from the normal processing path.* Never dispose before the commit; never leave a
permanently failing message hot-looping after it. If terminal storage is unavailable, the delivery is
**not** disposed of — work backs up visibly rather than disappearing quietly.

Each domain has its own terminal namespace, `<failure-domain>.dlq`, generalising master `# 20.1`'s
`ext.<vendor>.dlq` to internal domains too. **One global undifferentiated dead-letter bucket is
forbidden.** A global operational view may aggregate for triage; storage and routing identity always
preserve the originating domain.

**Out of scope:** table schemas, columns, indexes, partitions, retention periods — Phase 1 and
operations.

### 3. Provider-facing payment work and local payment-state convergence are separate failure domains

```text
ext.payments    provider-facing payment I/O — initiation, capture, refund,
                status query / reconciliation polling
                inherits provider availability, rate limits and circuit state

core.payments   local durable payment-state convergence — applying durably ingested
                provider events and reconciliation findings under row locks,
                inventory commit/release, resulting Outbox rows
                NO provider I/O of any kind
```

The split is by **I/O nature, not by workflow step**. Naming the two "initiation" and "reconciliation"
would be wrong, because reconciliation has both halves: it queries the provider *and* applies what it
learned to local state. Splitting by I/O nature makes the queue boundary coincide exactly with
ADR-0007's and ADR-0009's transaction boundary — the durable local transaction contains no provider
call, and the post-commit provider step runs through `application/payments_gateway`'s port.

**`core.payments` must keep converging while every payment provider is down.** Applying an already
ingested authorisation to `PaymentAttempt`/`Order` requires no provider, so a provider outage may not
stall it; a realisation in which it can is non-conformant. A general-purpose `external` queue is not
acceptable for payment-critical work, and neither is one `core.high` bucket shared with inventory
expiry.

Inside `ext.payments`, **each provider has its own concurrency, rate-limit and circuit budget**, so a
maib outage cannot exhaust the capacity MIA work needs.

**Out of scope:** provider idempotency-key formats, reconciliation queries, maib/MIA protocol fields —
the payments phase and `integrations/<provider>`.

### 4. Contract quarantine and operational dead-letter are two semantic states

```text
QUARANTINE                              OPERATIONAL DEAD-LETTER
"we cannot understand this message"     "we understood it; execution failed"
unknown type / unsupported version /    retry bounds exhausted, permanent provider
invalid payload / conflicting event_id  rejection, handler defect after bounded retries
never any business effect               an effect may partially or fully exist upstream
fix: producer, deploy order, schema     fix: provider, data, code, manual completion
```

**Neither is ever called simply "failed"** — not in a table, a metric, a log line, an alert, an admin
screen or a runbook. Phase 1 may map both onto one physical mechanism, but never onto one semantic
state: a shared structure carries an explicit terminal-kind discriminator, and every query, metric,
alert and replay path distinguishes them.

A permanent **provider business rejection** is therefore not a schema quarantine. Classifying a
declined transaction as an unknown schema destroys the operator's ability to tell a bank API change
from a declined payment. Likewise a **programmer defect** is never reported as a provider or transient
failure, or the alert that exists to find defects never fires.

**The unit of routing, failure, terminal state and replay is a consumer delivery — never a message.**
A failure domain describes a *handler's* work and dependencies, so it is assigned **per consumer
declaration**, beside that consumer's supported versions and effect-idempotency mechanism (ADR-0009
IX13), and never once per `(event_type, schema_version)`. A `COMMAND` has exactly one handler and
therefore one assignment; an `EVENT`'s independent consumers may be assigned to different domains — a
notification handler in `ext.email`, a CRM handler in `ext.crm` and a local state handler in a `core.*`
domain, all from one `event_id`. An `EVENT` with no declared consumers needs no assignment, and
ADR-0009's zero-consumer allowance is unchanged. A producer never selects a failure domain for
anyone.

It follows that two consumers of one `event_id` are two independent deliveries rather than duplicates,
that each keeps its own identity/effect/terminal state, that one may succeed while another
dead-letters, that **a terminal record must name which registered consumer failed** (the domain alone
cannot, since consumers may share one), and that **replay is scoped to the failed consumer delivery
and never rebroadcasts to a sibling that already succeeded**.

Consequently: **no message retries forever on its normal queue** (every domain declares finite bounds,
backoff with jitter, and a terminal disposition); a **retry preserves the message exactly**, minting
no new `event_id`; and **replay is explicit, authorised, audited and identity-preserving**, re-entering
at the normal validation and idempotency boundary with **no force-apply path**. A still-invalid replay
returns to quarantine rather than being coerced. A genuinely *new* business attempt is a different
operation: its owner emits a new message with a new `event_id`.

**Out of scope:** attempt counts, retry ages, backoff seconds, jitter widths, circuit thresholds,
replay tooling and alert thresholds — Phase 1 and operations.

## Consequences

**Positive**

- A six-hour ERP outage, a notification retry storm, a full projection rebuild and one provider's rate
  limiting each stop exactly one domain, and the blast radius is written down per domain rather than
  discovered during an incident.
- Money-state convergence keeps running while payment providers are down, because the domain that
  performs it makes no provider calls at all — the same boundary ADR-0007 already draws.
- A terminally failed message survives any broker event, and an operator can always tell *"we cannot
  understand this"* from *"we understood it, execution failed"*, which are the two situations with
  entirely different responses.
- Isolation becomes falsifiable: the wedged-ERP configuration is a test, not a hope.
- Routing stays operational metadata, so moving work between domains never touches a message contract,
  never bumps `schema_version` and never forces a consumer migration.

**Negative / accepted cost**

- **More worker pools than a single queue would need**, with reserved capacity that is idle when its
  domain is quiet. This is the cost of a reservation and is accepted: capacity that can be borrowed is
  capacity that will be taken at the worst moment.
- **Ten domain definitions, and for each one that is actually enabled a terminal namespace and a
  runbook owner**, several of which will carry low volume. Accepted, because merging them later
  requires an ADR while splitting them under load requires an incident. Definitions that are not
  enabled — `ext.crm` today — cost nothing operationally.
- **Routing is per consumer, so a single message's operational picture is spread across its consumer
  declarations**, and tooling must address consumer deliveries rather than messages. Accepted: the
  alternative is a single route for an `EVENT` whose handlers have nothing in common, which is not a
  simplification but a wrong answer.
- **Two durable terminal states rather than one bucket**, with a discriminator that every query,
  metric and alert must respect. Accepted for the operator's sake.
- **Terminal records in PostgreSQL** add write volume and a retention obligation beyond what a broker
  DLQ alone would cost. Accepted; TD8's reference-rather-than-copy rule keeps it bounded.
- **Payment work is split across two domains**, so a payment workflow's diagnosis spans two queues and
  two runbooks. Accepted: the alternative lets a provider outage delay committed money.

**Enforcement**

Phase 1 and later phases implement the checks item 9 §37 defines:

- static — A51 (every declared production consumer/handler that can receive a delivery has a valid
  failure-domain assignment — **not** one domain per event version), A52 (no transport metadata
  in a business contract), A53 (no direct producer → broker publish), A54 (no provider I/O from a
  `core.*` domain), A55 (no unbounded retry policy), A56 (no global undifferentiated dead-letter),
  A57 (no replay mints a new identity), A58 (no force-apply path), A59 (no item 10/12 vocabulary
  here);
- behavioural — C70–C73 (ERP outage, ERP retry storm, rebuild backlog and notification storm each
  isolated), C74 (lost acknowledgement produces no second effect and is not dead-lettered), C75
  (ambiguous provider timeout not blindly duplicated), C76 (quarantine commits before disposition),
  C77–C79 (replay preserves identity, still-invalid returns to quarantine, completed replay
  duplicates nothing), C80–C81 (broker outage does not roll back business state; the relay resumes
  and stays fair), C82 (a terminal poison message does not restart retries), C83 (replaying one
  failed consumer does not re-invoke a successful sibling, asserted by handler-invocation count),
  C84 (one `EVENT`, two consumers, two failure domains, independent retry budgets and terminal
  states);
- review — V62–V73.

This ADR changes **no** dependency-matrix cell, adds **no** import edge, extends **no** `core`
submodule allowlist, and changes **no** ADR-0009 message-contract rule — ADR-0009's consumer
cardinality (zero, one or many for an `EVENT`; exactly one for a `COMMAND`) and its per-consumer
effect-idempotency declaration are used exactly as written. It adds exactly **one** mutable
operational field to **each consumer declaration** in the event registry's operational half, and no
entry-global column. L1–L21 stand unedited.
