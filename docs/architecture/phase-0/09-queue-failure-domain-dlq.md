# Phase 0 — Item 9: queue / failure-domain matrix and DLQ policy

- **Status:** DONE / FROZEN
- **Date:** 2026-09-05
- **Phase:** 0 — Architecture Freeze
- **ADR:** [ADR-0010](../../adr/0010-async-failure-domain-isolation.md) — required, see §1.3
- **Related:** [ADR-0004](../../adr/0004-four-layer-modular-monolith.md),
  [ADR-0005](../../adr/0005-dependency-and-integration-wiring.md),
  [ADR-0007](../../adr/0007-place-order-atomic-idempotent-boundary.md),
  [ADR-0008](../../adr/0008-storefront-listing-projection.md),
  [ADR-0009](../../adr/0009-event-contract-versioning.md),
  [item 3](03-dependency-matrix.md), [item 5](05-place-order-use-case.md),
  [item 6](06-storefront-listing-projection.md), [item 8](08-event-registry-versioning.md),
  [event registry](../events/event-registry.md),
  [queue / failure-domain matrix](../events/queue-failure-domain-matrix.md),
  master `# 1`, `# 9.3`–`# 9.4`, `# 12.2`–`# 12.3`, `# 20.1`–`# 20.8`, `# 23.2`–`# 23.3`, `# 24.8`

---

## 1. Purpose

### 1.1 What this item freezes

Item 8 froze what an asynchronous message *means*: its owner, its name, its identity, its schema, its
version, its validation, and the semantic outcome when it cannot be understood. It deliberately froze
nothing about **transport**: which queue carries the work, what shares worker capacity with what, how
many times a failure is retried, where a message goes when it can never succeed, and who is allowed
to send it back through.

Item 9 owns exactly that, under one governing objective:

> **Failure isolation before throughput optimisation.**
>
> A broken, slow or hostile integration must not consume the worker capacity that unrelated critical
> work depends on.

Frozen here:

- the **three-layer separation** — registered message contract (item 8) / logical failure domain
  (item 9) / physical broker queue (Phase 1) — and the rule that a routing change never touches a
  message contract (§4);
- the **failure-domain principle**: the single admissible reason for two workloads to share a
  normal-processing queue (§5);
- the **criticality vocabulary** `CRITICAL | IMPORTANT | BEST_EFFORT`, governing capacity, isolation
  and alerting and never durability or correctness (§6);
- the **frozen set of logical failure-domain definitions**, the separation of a frozen *definition*
  from a launch *provisioning* decision, and the rule for adding another (§7, §12);
- the **payment isolation decision**: provider-facing payment work and local payment-state
  convergence are two failure domains, split by I/O nature rather than by workflow step (§8);
- the **projection isolation decision**: incremental projection updates and rebuild batches are two
  failure domains (§9);
- **ERP batch isolation** (§10) and the **notification** split (§11);
- **routing ownership**: routing is transport metadata, assigned **per consumer declaration** in the
  operational half of the registry against the item 9 matrix, never entry-global, never
  producer-selected, and never in the item 8 envelope or payload (§13, §13.1);
- **logical queue naming**, reconciled deliberately with master `# 20.1`'s `core.*` / `ext.*` /
  `ext.*.dlq` family (§14);
- why **priority is not isolation** (§15) and why **critical domains get reserved worker capacity**
  (§16);
- the **failure taxonomy** TF-A…TF-D and what each outcome is (§17);
- **retry ownership** (§18), **finite retry bounds** (§19), **backoff** (§20) and **provider rate
  limit / circuit behaviour** (§21);
- the precise separation of **contract quarantine** from **operational dead-letter**, as two semantic
  states (§22), and the rule that the unit of failure, terminal identity and replay is a **consumer
  delivery** rather than a message (§22.3);
- **PostgreSQL as the canonical durable truth** for both terminal states, with the broker DLQ demoted
  to transport (§23);
- **per-domain terminal namespaces** and the ban on one undifferentiated dead-letter bucket (§24);
- **poison-message** behaviour across worker restarts (§25);
- **delivery ambiguity** — crash before/after the effect, lost acknowledgement (§26) — and
  **ambiguous external outcomes** (§27);
- **replay** as a privileged, audited, identity-preserving operation (§28), its **destination**
  through normal validation (§29), and its interaction with **schema retirement** (§30);
- **broker outage** and relay behaviour (§31), **single-domain outage** and fair relay scheduling
  (§32), **backpressure** (§33) and **alerting** severity classes (§34);
- a 22-row failure matrix (§35), the registry cross-reference (§36), and the checks later phases must
  implement (§37) — A51–A59, C70–C84, V62–V73.

### 1.2 What this item does **not** do

No Celery configuration, worker, queue, exchange, routing key, Redis key, RabbitMQ declaration, task
module, Python package, Outbox/Inbox/DLQ model, migration or production code is created. Phase 0
produces documents and decisions only.

Specifically **not** decided here:

| Not decided | Owner |
|---|---|
| Trace/correlation/causation field names, message-header trace schema, propagation mechanics | **item 10** |
| `Money` / `PublicId` implementation, including the concrete `event_id` type | **item 11** |
| `source_version` generation, per-source mapping, guarded projection upsert SQL, stale-row revision algorithm | **item 12** |
| Whether async analytics exists at all, and therefore whether it ever needs a domain | **item 13** |
| The MVP / later cut per module — including **whether CRM ships at launch**, and therefore whether `ext.crm` is ever provisioned | **item 14** |
| Real `event_type` names, payload schemas, `schema_version` values | **item 8** + each owning module's phase |
| `CELERY_TASK_ROUTES`, broker/transport settings, prefetch, acks-late semantics, physical exchange/routing-key topology | Phase 1 |
| Numeric worker concurrency, process counts, autoscaling policy | Phase 1 / operations |
| Exact retry attempt counts, backoff seconds, jitter width, max age, circuit thresholds | Phase 1 / operations |
| Quarantine / dead-letter / Outbox / Inbox table schemas, columns, indexes, partitions | Phase 1 (master `# 20.2`, `# 20.3`) |
| The circuit-breaker and rate-limiter libraries | Phase 1 |
| Numeric alert thresholds, SLO values, retention and replay windows | operations phases (master `# 20.5`, `# 23.2`, `# 23.3`) |
| Runbook contents at `docs/runbooks/<alert-name>.md` | operations phases (master `# 23.3`) |

### 1.3 Why a new ADR **is** required

Master `# 25`'s Phase 0 list already anticipates a *queue/failure-domain matrix + DLQ policy*, and
item 9 makes four decisions that meet `docs/adr/README.md`'s "when an ADR is required" test:

| Decision | Why it needs an ADR |
|---|---|
| **Failure-domain isolation with reserved capacity is an architectural requirement, not an operations tuning knob.** A deployment in which one wedged integration can starve a critical domain is non-conformant, and this is a testable contract. | It constrains deployment topology and adds a class of contract test; master `# 20.1` states the goal in prose but freezes no requirement anyone can fail a build on. |
| **PostgreSQL is the canonical durable truth for both terminal states** (contract quarantine and operational dead-letter); a broker DLQ is transport and never the sole record. | A consistency/source-of-truth rule of the same class as ADR-0007's and ADR-0009's. Master `# 20.1` names `ext.*.dlq` as *dead-letter storage/queue* without deciding which of the two is authoritative. |
| **Provider-facing payment work and local payment-state convergence are separate failure domains**, split by I/O nature. Master `# 20.1`'s illustrative routing table has no outbound-payment queue at all, and routing every payment task to one `core.high` bucket would let provider rate limiting delay the convergence of already-authorised money. | It assigns a **CRITICAL external** failure domain the master's literal configuration does not contain, and it is a correctness-adjacent isolation guarantee for the financial contour. |
| **Contract quarantine and operational dead-letter are two semantic states**, never one "failed" bucket, even where Phase 1 maps them onto one physical mechanism. | It extends ADR-0009 §20's semantics into transport, and it is the rule that keeps *"cannot understand this"* distinguishable from *"understood it, execution failed"* in every runbook. |

[ADR-0010](../../adr/0010-async-failure-domain-isolation.md) records these. It changes **no**
dependency-matrix cell, adds **no** import edge, extends **no** `core` submodule allowlist and
changes **no** item 8 message contract rule. L1–L21 stand unedited.

### 1.4 The one place item 9 departs from the master

Master `# 20.1`'s prose is binding and is preserved in full:

> Разделение очередей только по `high/default/low` недостаточно. Главная изоляция строится по внешней
> зависимости.

Its **illustrative** `CELERY_TASK_ROUTES` block, however, routes by two different rules at once:
`ext.erp` / `ext.crm` / `ext.email` / `ext.sms` are failure domains, while `core.high` / `core.low`
are the criticality buckets the same section has just called insufficient. `core.high` in that block
holds payment reconciliation *and* inventory expiry, and no queue exists for outbound payment
provider calls at all.

Item 9 follows master `# 20.1`'s **prose** and refines its **example**:

| Master `# 20.1` | Item 9 |
|---|---|
| Isolation is built primarily by external dependency | **Kept** and made the governing principle (§5) |
| Independent concurrency / prefetch / rate limit per external queue | **Kept** (§16, §21) |
| A separate DLQ per external queue, `ext.<vendor>.dlq` | **Kept and generalised** to `<failure-domain>.dlq` for every domain, internal ones included (§24) |
| Explicit timeout, circuit breaker, bounded retry, DLQ, replay, anti-corruption per outbound client | **Kept** (§19, §20, §21, §28) |
| A six-hour ERP outage must not affect `ext.email` latency/throughput | **Kept** and widened to every pair of domains (§5, §16) |
| `core.high` / `core.low` as routing destinations | **Changed:** criticality becomes an *attribute* of a failure domain (§6), not a queue. The internal, no-vendor-dependency work `core.high`/`core.low` held is split into named internal failure domains that keep the `core.*` family prefix (§7, §14). |
| No outbound-payment queue | **Changed:** `ext.payments` is frozen as a CRITICAL provider-backed domain (§8). |

Nothing else in master `# 20` changes. `# 20.2`–`# 20.8` are used exactly as written.

---

## 2. Frozen principles inherited

| # | Inherited rule | Source |
|---|---|---|
| R1 | PostgreSQL is the source of truth for orders, payments, inventory, reservations, idempotency, consent and legal data. Redis is disposable acceleration and never the sole decision. | master `# 1`, `# 5` |
| R2 | A producer writes an Outbox row inside its own business transaction; it never schedules transport and never publishes directly to a broker. | item 4 §9.1, item 8 PI1 |
| R3 | A `tasks/*` handler deserialises, restores actor and trace, calls **one** use case or domain public command, and maps the result to success / retry / dead-letter. It decides *when*, never *what it means*. | ADR-0004 §9, item 3 §4.6 |
| R4 | External provider I/O never happens inside a durable business transaction; external work is post-commit through an `application/<a>/ports.py` port. | ADR-0004 §10, ADR-0007, item 8 HT3/HT4 |
| R5 | Delivery is at-least-once. Duplicate delivery is normal; out-of-order delivery is normal; broker ordering is never relied on for correctness. | item 8 IX1, OR1–OR4 |
| R6 | Every consumer durably retains first-seen `event_id` / `event_type` / `schema_version` / payload fingerprint, and the business effect happens once per `event_id`, durable in PostgreSQL. | item 8 IX2, IX5, IX8, IX9 |
| R7 | An unknown type, unsupported version or invalid payload is **durably quarantined and alerted**, never coerced, never marked HANDLED, never retried forever; quarantine commits **before** the transport disposes of the delivery. | item 8 §20, §20.3 |
| R8 | A retry, redelivery or replay preserves `event_id`, `event_type`, `schema_version`, `occurred_at` and payload unchanged. | item 8 ID3, TS3, C66 |
| R9 | The semantic envelope is exactly `event_id`, `event_type`, `schema_version`, `occurred_at` plus item 10's reserved extension point, and carries **no** transport concern — no queue, exchange, routing key, retry counter, attempt number, delivery id, broker timestamp, worker identity or priority. | item 8 EN1, EN3, EN6, EN7 |
| R10 | `schema_version` versions the payload only. Implementation, broker, queue, routing and trace changes never bump it. | item 8 SV2, SV5, SV7 |
| R11 | The storefront projection is fully rebuildable from OLTP and is never event-sourced; a projection or cache miss **never** falls back to cross-domain OLTP joins in the request. | item 6 RB1/RB2, CM-no-fallback; ADR-0008 |
| R12 | Every outbound vendor client has explicit connect/read/total timeouts, bounded retry, circuit breaker, vendor DTO, isolated failure-domain queue and a DLQ/replay procedure. | master `# 20.1`, `# 20.8` |
| R13 | Webhook is an accelerator; reconciliation is the path to truth. The inbound boundary authenticates and durably ingests only; financial state changes happen in a worker under row locks and a state machine. | master `# 1`, `# 12.2`, item 8 PI12/PI13 |
| R14 | A payload never carries an authorization decision, a secret, a token, or personal data beyond need. | item 8 SEC2–SEC5 |

Nothing below weakens any of these.

---

## 3. Vocabulary

| Term | Meaning here |
|---|---|
| **Logical failure domain** | A named grouping of asynchronous work that may legitimately share worker capacity, retry behaviour and a blast radius. The unit item 9 owns and freezes. |
| **Physical queue** | The broker/Celery realisation of a logical failure domain. Phase 1's. One logical domain may map to one or several physical queues. |
| **Criticality** | `CRITICAL` / `IMPORTANT` / `BEST_EFFORT`. An operational expectation about capacity, isolation and alerting. **Never** a statement about durability, contract or whether data may be lost. |
| **Normal processing path** | The queue and handler chain on which a message is delivered and retried while it may still succeed. |
| **Quarantine** | Item 8's semantic terminal state: the message cannot be *interpreted* — unknown type, unsupported version, invalid payload, conflicting `event_id`. |
| **Operational dead-letter (ODL)** | Item 9's semantic terminal state: the message was understood and valid, but its handler could not complete within its retry policy or hit a permanent technical/provider condition. |
| **Terminal state** | Quarantine or ODL. Durable, identity-bearing, and never re-entered automatically. |
| **Replay** | An explicit, authorised, audited re-injection of an existing message, preserving its identity, through the normal validation and idempotency boundary. |
| **New business attempt** | A *different* thing from a replay: a new fact or work item, with a **new** `event_id`, emitted by its owner. §28. |
| **Reserved capacity** | Worker capacity a domain is guaranteed and that no other domain can consume, whatever its backlog. |

---

## 4. Three layers, kept apart

```text
registered message contract        item 8   what the message MEANS
  event_type / schema_version / kind        immutable once published

logical failure domain             item 9   what it may FAIL TOGETHER WITH
  name / criticality / retry class /        operational, mutable, audited
  terminal destination / capacity

physical broker queue              Phase 1  HOW it is carried
  queue, exchange, routing key,             free to change for throughput
  prefetch, concurrency, worker pool
```

| # | Rule |
|---|---|
| LY1 | The three layers are **separate identifiers with separate lifecycles**. No layer's name is derived from another layer's name, and no layer's change forces a change in another. |
| LY2 | **Queue identity is never event semantics.** No queue, exchange, routing key, worker name, priority, retry count or attempt number appears in an `event_type`, in the item 8 envelope, or in a payload (item 8 NM4, EN3, R9). |
| LY3 | **A routing or queue change never bumps `schema_version`** and never produces a new `event_type` (item 8 SV5, R10). Moving a message from one failure domain to another is an operational rollout with a runbook, not a contract migration. |
| LY4 | One logical failure domain may map **1:1** to one physical queue initially. Phase 1 may split it into several physical queues (per provider, per shard, per lane) purely for throughput, **provided the split does not weaken the isolation the domain guarantees** and the domain keeps one terminal namespace and one replay authority. |
| LY5 | Two logical failure domains may **never** be merged onto one physical queue. A merge is not a Phase 1 tuning decision; it is a change to this artifact and requires the §12 procedure. |
| LY6 | A logical failure domain is **not** a module, a package, a domain in the `domains/` sense, or an ownership boundary. Several consumers may share one failure domain, and one owner's messages may be handled across several. |
| LY7 | A failure domain describes **a handler's work and its dependencies**, so it attaches to a **consumer**, never to a message version and never to a producer (§13.1). One `EVENT` whose consumers run in three domains is the normal case, not an exception. |

---

## 5. The failure-domain principle

> **Messages share a normal-processing queue only when it is acceptable for one workload's latency,
> provider outage, poison-message rate and retry storm to consume the other's worker capacity.**

| # | Rule |
|---|---|
| FD1 | Grouping is justified by **shared acceptable blast radius**, and by nothing else. |
| FD2 | The following are **never** sufficient reasons to share a domain: they use the same broker; they are all Celery tasks; they all come from the Outbox; they are low volume today; their code lives near each other; they belong to the same module; they have the same criticality label. |
| FD3 | The test is asked in the concrete: *if this workload were wedged for six hours with a full retry backlog, which other work would stop?* Every workload named in the answer shares its blast radius, whether or not that was intended. |
| FD4 | Commerce-critical paths are explicitly protected from: an ERP outage; a CRM outage; an email or SMS provider outage; a support/Chatwoot outage; a large projection rebuild; an analytics batch; and any one provider's retry storm. |
| FD5 | A domain that is **provider-backed** inherits that provider's availability. It may therefore never be shared with work that must keep progressing while the provider is down. |
| FD6 | A domain whose work is **unbounded in batch size** (rebuilds, imports, exports) may never be shared with latency-sensitive work, even at equal criticality. |
| FD7 | A general-purpose `external`, `integrations`, `default` or `misc` normal-processing queue is **forbidden**. Every workload names its domain. |

---

## 6. Criticality classes

| # | Rule |
|---|---|
| CR1 | Every logical failure domain carries exactly one criticality: `CRITICAL`, `IMPORTANT` or `BEST_EFFORT`. |
| CR2 | `CRITICAL` — correctness-critical convergence of committed commercial state. Guaranteed reserved worker capacity (§16); the tightest backlog-age alerting; a stall is a P1. |
| CR3 | `IMPORTANT` — normal commerce depends on it converging within an SLO, but a delay degrades experience rather than correctness. Reserved capacity where its SLO requires it; a sustained stall is a P2. |
| CR4 | `BEST_EFFORT` — delivery may lag substantially without commercial harm. No reserved capacity guarantee beyond a non-zero floor; alerting is on sustained backlog and terminal-failure growth, not on latency. |
| CR5 | **Criticality determines capacity, isolation and alerting. It never determines durability, contract strength or whether data may be lost.** A `BEST_EFFORT` message is still registered, still versioned, still validated, still durable, still identity-checked, and still ends in a durable terminal record when it fails. |
| CR6 | **Business correctness is never inferred from criticality.** No handler branches on it, no domain rule reads it, and no commercial decision depends on which queue carried the message. |
| CR7 | Criticality is **mutable operational metadata** of the matrix, changed by the recorded §12 procedure. It is not part of any message contract. |

---

## 7. The frozen failure-domain definitions

The authoritative per-domain matrix is
[`docs/architecture/events/queue-failure-domain-matrix.md`](../events/queue-failure-domain-matrix.md).
This section freezes the **set of definitions** and the reasoning; the matrix freezes each domain's
cells.

> **A frozen definition is not a launch commitment.** This section freezes the failure-domain shapes
> for the architecture as currently known — each domain's name, criticality, isolation rule, retry
> class, terminal namespace and capacity relationship. **Which of them are provisioned at launch
> follows from which workloads are actually enabled**, and the MVP/later cut per module is
> **item 14's** decision, not item 9's (FD9a).

| Logical domain | Class | Provider-backed | Rationale for a separate domain |
|---|---|---|---|
| `core.payments` | CRITICAL | no | Converges already-committed money state from durably ingested provider events and reconciliation findings. Must keep progressing while every provider is down (§8). |
| `core.inventory` | CRITICAL | no | Reservation expiry and inventory state transitions. Master `# 9.2` requires expiry within minutes of expiry time; a backlog silently withholds sellable stock from the storefront. |
| `core.projection.incremental` | IMPORTANT | no | Storefront freshness SLO (item 6, master `# 23.2` *Listing Projection Lag*). Latency-sensitive, small, coalesced units (§9). |
| `core.projection.rebuild` | IMPORTANT | no | Full and targeted rebuilds are large, bounded-batch, throughput-shaped work that would otherwise consume every projection worker (§9). |
| `core.maintenance` | BEST_EFFORT | no | Internal housekeeping with no external dependency and no commercial-correctness role: cache re-warm, sitemap generation, retention/partition lifecycle, aggregate recomputation. Exists so that "everything else" has an explicit home and never lands in a critical domain by default. |
| `ext.payments` | CRITICAL | **yes** | Provider-facing payment calls: initiation, capture, refund, status query. Provider-rate-limited and circuit-controlled, yet commercially critical (§8). |
| `ext.erp` | IMPORTANT | **yes** | 1C imports, exports and sync batches. Large, bursty, and historically the platform's longest outage (§10). Master `# 20.1`. |
| `ext.email` | BEST_EFFORT | **yes** | Master `# 20.1` (§11). |
| `ext.sms` | BEST_EFFORT | **yes** | Master `# 20.1`; a separate provider with separate rate limits and a separate outage profile (§11). |
| `ext.crm` | BEST_EFFORT | **yes** | Master `# 20.1` names CRM as a failure domain and ADR-0005 already homes CRM-sync ownership and its port. **Conditional** — see FD9a (§12). |

| # | Rule |
|---|---|
| FD8 | These ten are the **complete frozen set of failure-domain definitions** for the architecture as currently known. No other normal-processing failure domain exists until it is added by the §12 procedure. |
| FD9 | A domain is **provisioned** — given a physical queue, workers, a terminal namespace and an on-call owner — only when a real workload is routed to it. A definition in the matrix reserves the name, the class and the isolation rule; it is not a running worker pool and creates no operational burden until it is enabled. |
| FD9a | **`ext.crm` is a conditional reserved definition.** Item 9 freezes its operational shape — `BEST_EFFORT`, provider-backed, never sharing a commerce-critical pool — **if and when CRM is enabled**. Item 9 does **not** decide that CRM ships at launch: the MVP/later cut per module is **item 14's**, still open. `ext.crm` is not provisioned until the CRM integration is enabled by the product/MVP roadmap. The definition is not deleted meanwhile, and removing or merging it still follows NX6's procedure — which is a separate question from whether the feature is enabled. |
| FD10 | **No support/Chatwoot domain and no analytics domain is reserved at all** — not even conditionally. Chatwoot identity context has no frozen failure-domain shape, and whether async analytics exists at all is **item 13's** decision. `ext.crm` differs from both because master `# 20.1` already names CRM as a failure domain and ADR-0005 already froze its ownership and port; that gives item 9 a shape to freeze without deciding scope (§12). |
| FD11 | The Outbox **relay** is not a consumer failure domain. It is a producer-side transport component with its own isolation rules (§31, §32) and its own capacity, and it is never sized or scheduled out of a consumer domain's budget. |

---

## 8. Payment isolation — the decision

### 8.1 The question

Master `# 20.1`'s example routes `tasks.payments.reconcile*` to `core.high` and provides no queue for
outbound provider calls. The user-facing test is: *would provider payment-initiation latency or retry
exhaustion be allowed to delay the reconciliation of already-authorised payments?*

**No.** So they are not one failure domain.

### 8.2 The split is by I/O nature, not by workflow step

Naming the two domains "initiation" and "reconciliation" would be wrong, because reconciliation
itself has both halves: it *queries the provider* (external) and then *applies what it learned to
local state* (internal). The frozen split is therefore:

```text
ext.payments     provider-facing payment I/O
                 initiation, capture, refund, status query / reconciliation polling
                 provider availability, provider rate limits, circuit state

core.payments    local durable payment-state convergence
                 applying durably ingested provider events (master # 12.2 Inbox worker)
                 applying reconciliation findings, state-machine transitions,
                 inventory commit/release, resulting Outbox rows
                 NO provider I/O of any kind
```

| # | Rule |
|---|---|
| PY1 | `ext.payments` and `core.payments` are **two logical failure domains** with separate worker capacity, separate retry policy, separate terminal namespaces and separate alerting. |
| PY2 | The split follows item 8 HT3/HT4 and ADR-0007 exactly: the durable local transaction happens in `core.payments` and contains **no** provider call; the post-commit provider step runs in `ext.payments` through `application/payments_gateway`'s port. The queue boundary and the transaction boundary coincide by construction. |
| PY3 | **`core.payments` must keep converging while every payment provider is down.** Applying an already-ingested authorisation to `PaymentAttempt`/`Order` requires no provider, so a provider outage may not stall it. Any realisation in which it can is non-conformant (C70). |
| PY4 | **A general-purpose `external` queue is never acceptable for payment-critical work** (FD7). Neither is `core.high`: sharing one bucket with inventory expiry gives an inventory backlog a path to delay money-state convergence. |
| PY5 | Within `ext.payments`, **each provider gets its own concurrency, rate-limit and circuit budget**, so a maib outage cannot exhaust the capacity MIA work needs. Phase 1 may realise this as per-provider physical queues under LY4; it may not realise it as one shared unbudgeted pool. |
| PY6 | `core.payments` is the domain of record for the payment state machine. It never calls a provider even to "just check"; if a check is needed, it emits the intent and `ext.payments` performs it (R4, item 8 HT4). |
| PY7 | Payment work is never routed to `core.maintenance`, `core.projection.*`, `ext.erp`, `ext.crm`, `ext.email` or `ext.sms`, in either direction. Nothing from those domains may be routed into `core.payments` or `ext.payments`. |

---

## 9. Projection isolation — the decision

A full storefront rebuild can touch the whole catalog. Incremental updates are small, coalesced and
bound by a freshness SLO (master `# 23.2` *Listing Projection Lag*, item 6). One shared domain lets a
multi-hour rebuild push incremental freshness past its SLO for as long as the rebuild runs — and item
6 forbids the only escape hatch a lagging projection would otherwise have, because a projection miss
may **never** fall back to OLTP joins in the request (R11).

| # | Rule |
|---|---|
| PJ1 | `core.projection.incremental` and `core.projection.rebuild` are **two logical failure domains**. |
| PJ2 | **A rebuild backlog may never delay incremental updates beyond their freshness SLO.** This is the decidable form of the rule and the subject of check C72. |
| PJ3 | Rebuild work is **bounded and resumable**: coalesced batches with an explicit maximum size (item 8 PD4, master `# 20.2` 500–1000 per iteration), each batch independently idempotent, so a rebuild can be paused, resumed, and interleaved rather than held as one long-running unit of work. |
| PJ4 | A rebuild may **never** occupy the whole projection capacity indefinitely; `core.projection.rebuild` has its own bounded capacity and cannot borrow the incremental domain's. |
| PJ5 | Both domains write the same projection through the same `application/storefront`-owned update path. Two domains means two blast radii, **not** two writers, not two code paths and not two consistency models (item 6, ADR-0008). |
| PJ6 | Stale-update protection is unchanged and remains **item 12's**: `source_version`, its generation, its per-source mapping and the guarded upsert. Splitting the domains changes no ordering guarantee, and item 9 relies on none — the domains are independent precisely because ordering was never assumed (R5). |
| PJ7 | A projection lag caused by either domain never authorises a request-time OLTP fallback (R11). Backpressure is answered with capacity and alerting, never by changing the read path. |

---

## 10. ERP batch isolation

| # | Rule |
|---|---|
| EP1 | `ext.erp` is a single logical failure domain covering 1C imports, exports and sync batches. Import and export share a blast radius honestly: they share the provider, so an ERP outage stops both regardless of how they are queued. |
| EP2 | ERP batch work is **bounded**: no batch payload grows with the size of the catalog, and mass changes are coalesced into bounded batch messages or a dirty-set/staging table (master `# 9.3`, `# 20.2`; item 8 PD4). An import never fans out into 20 000 tasks. |
| EP3 | ERP batch work is **set-based, resumable and idempotent** per batch, so an interrupted or retried batch converges without duplicating an effect (R6). |
| EP4 | `ext.erp` may **never** occupy every worker indefinitely: its capacity is bounded and reserved *to* it, which also bounds what it can take *from* others (§16). |
| EP5 | **One malformed or poison ERP batch stops ERP work only.** It never stops `core.payments`, `ext.payments`, `core.inventory` or `core.projection.*`. This is check C71 and master `# 24.8`'s failure-domain isolation test. |
| EP6 | ERP payload fields, mappings and the `provider + external_id` schema stay with `application/erp_sync` and Phase 3 (item 3, ADR-0005 §2). Item 9 designs none of them. |

---

## 11. Notifications

| # | Rule |
|---|---|
| NT1 | `ext.email` and `ext.sms` are **separate** logical failure domains, as master `# 20.1` already has them. They are different providers with different rate limits, different failure profiles and different cost per message; a bulk email backlog must not delay an SMS, and an SMS provider outage must not consume email capacity (FD5). |
| NT2 | Both are `BEST_EFFORT` at MVP. That is a statement about capacity and alerting only; a notification message is still registered, versioned, validated, durable and identity-checked (CR5). |
| NT3 | A permanently invalid recipient (dead address, unroutable number) is a **TF-B** permanent workload rejection, not a contract failure and not a schema quarantine (§17, §22). |
| NT4 | **SMS is not made critical pre-emptively.** If a future security flow (2FA, account recovery) depends on SMS delivery latency for correctness, that flow's messages belong in their **own** domain with its own class, decided then, with an ADR — not by re-labelling all SMS as `CRITICAL` (§12). |
| NT5 | Neither notification domain may be given capacity that a `CRITICAL` domain's reservation depends on. A notification retry storm is a `BEST_EFFORT` incident. |

---

## 12. CRM, support, analytics — and how a domain is added

| # | Rule |
|---|---|
| NX1 | `ext.crm` is a **conditional reserved** `BEST_EFFORT` definition, provisioned only when the CRM integration is enabled (FD9a). **Whether CRM is MVP or later is item 14's decision**, and item 9 takes no position on it; it freezes only what must be true of CRM work *if* it runs. |
| NX2 | **No support/Chatwoot domain is reserved**, conditionally or otherwise. If and when it ships, it gets its own `BEST_EFFORT` domain (`ext.support`) rather than sharing `ext.crm`, unless the two are shown to satisfy FD1 with independently enforced per-provider rate limits. |
| NX3 | **No analytics domain is reserved.** Whether asynchronous analytics exists at all is item 13's decision. Naming a queue now for work whose existence is undecided creates an operational surface with no owner and no runbook (master `# 23.3`: an alert without an owner and a runbook is not production-ready). |
| NX4 | CRM, support and analytics work may **never** be routed into a `CRITICAL` or `IMPORTANT` domain to avoid provisioning a `BEST_EFFORT` one. Where the domain does not exist yet, the work does not ship yet. |
| NX5 | **Adding a logical failure domain** requires: a row in the queue/failure-domain matrix with every cell filled; a named operational owner and a runbook path; a criticality with its justification; a retry class; a terminal namespace; a declared capacity relationship to every existing domain; and an update to this artifact's §7 set. It does **not** require an ADR unless it changes an isolation guarantee this artifact freezes (for example, making a provider-backed domain `CRITICAL`, or merging two frozen domains). |
| NX6 | **Removing or merging a frozen domain requires an ADR**, because each frozen domain is an isolation guarantee other domains were sized against (LY5). |

---

## 13. Routing ownership

> **Routing is transport metadata. It is never event semantics.**

| # | Rule |
|---|---|
| RT1 | A semantic owner **never hard-codes a broker queue name** in its payload contract, its envelope, its `public.py` or its business code. Item 8 EN3 and NM4 stand unchanged (R9, LY2). |
| RT2 | Routing is determined by a **transport routing policy** that maps a **consumer's handling of** a registered message to a logical failure domain, and the logical failure domain to a physical queue. The policy is configuration and transport code, owned by `tasks/*` + the composition root (item 3 §4.6, ADR-0005 §3). |

### 13.1 The assignment is **per consumer**, never per message version

Item 8 already freezes that an `EVENT` may have zero, one or many independent consumers (KD2), that a
`COMMAND` has exactly one handling owner (KD3), and that business-effect idempotency is declared **per
consumer** rather than once per version (IX10, IX13). A failure domain describes *the work a handler
does and the dependencies it has*, so it follows the same cardinality:

```text
one EVENT instance E, one event_id

  consumer A  → notification handler  → ext.email
  consumer B  → CRM handler           → ext.crm
  consumer C  → local state handler   → core.<domain>
```

All three receive the same fact with the same `event_id`, and their handler executions belong to three
different failure domains, because a mail provider outage, a CRM outage and a local state transition
have nothing in common (FD1).

| # | Rule |
|---|---|
| RT3 | **The failure-domain assignment belongs to a consumer declaration**, alongside that consumer's supported versions and its effect-idempotency mechanism (item 8 IX13). It is **not** a field of the `(event_type, schema_version)` row, not producer-owned routing, not part of the payload and not part of the semantic envelope. |
| RT4 | For a **`COMMAND`** there is exactly one consumer/handler (item 8 KD3), so there is naturally exactly one failure-domain assignment. For an **`EVENT`**, different consumers may — and often should — be assigned to different failure domains. |
| RT5 | An **`EVENT` with zero declared consumers has no routing assignment**, and needs none. Item 8 KD2's zero-consumer allowance is unchanged: item 9 does not require a consumer to exist. When a consumer is later declared, it must receive a valid assignment **before** it may receive production deliveries (RT8). |
| RT6 | The assignment is **mutable operational metadata on that consumer declaration** (item 8 §26.1's operational half, RI8). Changing only the assignment changes **no** `schema_version`, **no** `event_type`, **no** payload contract and **no** effect-idempotency semantics. |
| RT7 | The separation is: |

```text
event registry             → contract / owner / versions
                             + per consumer: supported versions,
                                             effect-idempotency + justification  [item 8]
                                             failure-domain assignment           [item 9]

queue-failure-domain       → isolation, capacity, criticality, retry class,
matrix                       terminal destination, replay authority, runbook owner
```

| # | Rule |
|---|---|
| RT8 | **A declared consumer may not receive production deliveries without a valid failure-domain assignment** to a domain that exists in the matrix and has a normal-processing path (check A51, registry §6). |
| RT9 | The matrix **must not become a second contract authority**. It names no `event_type`, defines no payload, and confers no ownership. It describes workload categories and the operational rules that apply to whatever is routed into them. |
| RT10 | The registry **must not become queue configuration**. A consumer declaration carries one operational pointer to a domain — not a queue name, not a routing key, not a priority, not a retry schedule and not a concurrency number. |
| RT11 | **Changing a consumer's failure-domain assignment is an operational change**, not a contract change: no `schema_version` bump, no new `event_type`, no re-declaration of supported versions, no change to the effect-idempotency mechanism (LY3, RT6). It may require a rollout order and a runbook — drain the old route or accept dual consumption during the window — and that plan is recorded in the entry's notes. Moving one consumer never affects another consumer of the same message. |
| RT12 | **A producer never selects a failure domain**, for itself or for anyone else. A semantic owner emits a fact; which handler picks it up, and in which domain that handler runs, is a consumer-side operational fact the producer has no knowledge of and no authority over (RT1, OW-neutrality of item 8 KD2). |

---

## 14. Logical queue naming

| # | Rule |
|---|---|
| QN1 | Item 9 owns **logical** failure-domain names. Physical broker names, exchanges and routing keys remain Phase 1's and need not equal the logical name. |
| QN2 | The frozen naming family follows master `# 20.1`: `core.<domain>` for work with **no external vendor dependency**, `ext.<provider-domain>` for **provider-backed** work, and `<failure-domain>.dlq` for a terminal namespace (§24). |
| QN3 | A logical name **describes the failure domain**. It must not contain: a deployment environment; a schema version; a Python module, package, class or function name; a broker/exchange/routing-key word; a criticality word (`high`, `low`, `default`, `urgent`); or a vendor brand where the domain is provider-*class*-shaped rather than provider-specific. |
| QN4 | A logical name must **not require renaming when a handler implementation changes**, when a provider is swapped inside its class, or when the physical topology is re-sharded. |
| QN5 | The `core.` prefix asserts a property that is checkable: **no work routed to a `core.*` domain performs external provider I/O.** If a workload needs a provider call, it belongs in an `ext.*` domain or splits post-commit into one (R4, PY2, check A54). |
| QN6 | A vendor brand (`maib`, `mia`, `1c`, `chatwoot`) may appear only where a domain is genuinely one provider's, and never as a substitute for the provider-class domain. `ext.payments` is the domain; `maib` is a budget inside it (PY5). |
| QN7 | The frozen MVP logical names are exactly those in §7. `core.high`, `core.low`, `default`, `external`, `integrations` and `misc` are **not** logical failure-domain names and must not appear as normal-processing queues (§1.4, FD7). |

---

## 15. Priority is not isolation

| # | Rule |
|---|---|
| PS1 | **Message priority inside one worker pool is not a substitute for failure-domain isolation**, and no isolation guarantee in this artifact may be realised by priority alone. |
| PS2 | The reason is that priority orders *which message a free worker takes next*; it does not bound what a workload consumes once it is running. A low-priority workload can still exhaust worker slots and processes, database and broker **connections**, memory, prefetch buffers, the retry scheduler, and broker visibility/redelivery budget — and a slow provider holds all of those for the whole timeout, at whatever priority. |
| PS3 | **Celery priority behaviour is never relied on for correctness.** Its semantics vary by broker and by prefetch configuration, and a correctness argument that depends on them is invalid by construction (R5's spirit: transport ordering guarantees are never load-bearing). |
| PS4 | Priority is admissible **inside** a single logical failure domain, as an ordering preference between that domain's own work. It never crosses a domain boundary. |
| PS5 | Where an SLO requires that one workload keep progressing regardless of another's backlog, the answer is **separate worker capacity** (§16), never a priority number. |

---

## 16. Worker capacity

| # | Rule |
|---|---|
| WC1 | **Every `CRITICAL` domain has reserved worker capacity** that no other domain can consume, whatever that other domain's backlog, retry rate or provider state. |
| WC2 | `IMPORTANT` domains have reserved capacity where their SLO requires it; `core.projection.incremental` does, because its freshness SLO is alerted on and has no request-time fallback (R11, PJ2). |
| WC3 | `BEST_EFFORT` domains have a non-zero capacity floor and a bounded ceiling. A floor keeps them from being starved to a standstill; a ceiling keeps a retry storm from becoming a platform incident. |
| WC4 | **Reliance on autoscaling from one shared pool is not isolation** and does not satisfy WC1. Autoscaling reacts after the contention it is meant to prevent, and it cannot help at all when the shared constraint is a connection pool or a broker prefetch budget (PS2, master `# 22`'s shared pool sizing). |
| WC5 | The architecture requires that **a deployment configuration exists** in which, with `ext.erp` fully wedged and its retries saturated: `core.payments` still converges, `ext.payments` still progresses for unaffected providers, and `core.projection.incremental` still meets its freshness SLO. This is a contract test and a runbook exercise, not an aspiration (C70, C71, master `# 24.8`). |
| WC6 | Exact process counts, concurrency, prefetch and autoscaling policy are **Phase 1 / operations**. Item 9 freezes the reservation requirement and the relationships, not the numbers. |
| WC7 | Worker capacity is shared with the **database connection pool** budget: pool sizing is computed jointly for web workers, Celery workers and the relay (master `# 22`). A domain's capacity reservation is meaningless if its workers cannot get a connection, so a reservation includes its share of that budget. |

---

## 17. Failure taxonomy

Four transport-level classes. Every asynchronous failure is classified into exactly one, and the
classification determines the outcome.

### TF-A — transient technical failure

Examples: provider timeout; temporary 5xx; connection reset; a rate limit the provider says is
retryable; a transient database or network fault outside a committed local effect; a lock timeout.

| # | Rule |
|---|---|
| TA1 | Outcome: **retry on the normal queue** with bounded backoff (§19, §20). |
| TA2 | The retry preserves `event_id`, `event_type`, `schema_version`, `occurred_at` and payload unchanged (R8). **No new `event_id` is minted.** |
| TA3 | The retry produces no duplicate business effect, because the consumer's identity record and effect idempotency already guarantee one effect per `event_id` (R6). |
| TA4 | On exhausting its bounds, a TF-A failure becomes **operational dead-letter** (§22), never quarantine. |

### TF-B — permanent rejection of this asynchronous work

Examples: a provider permanently rejects a well-formed outbound request; a recipient address or number
is permanently invalid; the external entity the work refers to no longer exists and no retry can fix it.

| # | Rule |
|---|---|
| TB1 | **TF-B is not a contract failure and never a schema quarantine.** The message was understood, valid, and correctly routed; the *external world* said no. Classifying a provider business rejection as an unknown schema destroys the operator's ability to tell a bank API change from a declined transaction (§22). |
| TB2 | The outcome is decided **per workload**, and each workload's registry entry records which: |

```text
(i)  a terminal workflow/domain state, applied through the owning application module
     — the normal answer whenever the platform has somewhere meaningful to record it
       (a payment attempt fails, a notification is marked undeliverable);

(ii) an operational dead-letter for manual action
     — the answer when no owning state machine can represent the outcome, or the
       rejection means the request itself was wrong;

(iii) both — a terminal domain state AND an ODL record,
     when the outcome is business-meaningful and also needs operator triage.
```

| # | Rule |
|---|---|
| TB3 | Where (i) or (iii) applies, the terminal domain state is written through the owning module's public contract inside the handler's normal durable transaction (item 8 HT1, HT8). It is a business outcome and may legitimately produce further Outbox messages. |
| TB4 | Where (ii) or (iii) applies, the ODL record is durable in PostgreSQL and carries the rejection reason and the provider's classification, redacted per item 8 SEC8 (§23). |
| TB5 | TF-B **never retries on the normal queue** once classified. Retrying a permanent rejection is TF-A's mistake made with a wrong classification. |
| TB6 | A workload may not classify **everything** as TF-B to avoid retrying. A rejection is TF-B only when the provider's contract or the platform's own state establishes that no retry can succeed. When it is genuinely ambiguous, it is TF-A until the bounds run out — except where §27 applies. |

### TF-C — contract / identity integrity failure

Unknown `event_type`; unknown or unsupported `schema_version`; a payload invalid for a known version;
the same `event_id` with a conflicting type, version or payload.

| # | Rule |
|---|---|
| TC1 | Outcome: **durable quarantine + alert**, exactly as item 8 §20 freezes it. Item 9 changes none of its semantics and adds only the transport topology (§16 of item 8 is realised by §22–§24 here). |
| TC2 | TF-C is **never** retried on the normal queue, never coerced, never partially applied, never marked HANDLED (R7). |
| TC3 | TF-C is **not** a business error, not a domain state transition and not a compensating action (item 8 QU10, VL4). |

### TF-D — programmer / invariant failure

An impossible branch, an unexpected exception, a violated handler assumption, a `NotImplementedError`,
a broken invariant.

| # | Rule |
|---|---|
| TD1 | TF-D is **retried at most a small bounded number of times** — enough to survive a genuinely transient cause that was misclassified — and then becomes a terminal **operational dead-letter** with a **high-severity** alert. |
| TD2 | TF-D is **never retried indefinitely**. An unhandled defect that loops forever is an outage of the queue it sits on (item 8 QU6). |
| TD3 | **A software defect is never dressed as a provider failure.** A handler must not catch an unexpected exception and report it as a vendor error, a timeout, or a TF-A retryable condition; the classification must reflect what actually happened, or the alert that exists to find defects will never fire (check V64). |
| TD4 | TF-D's ODL record is distinguishable from TF-A exhaustion in the terminal record's reason classification (§22), because the operator response is entirely different: one is "the provider was down", the other is "we shipped a bug". |

### 17.1 Classification summary

| Class | Retry on normal queue | Terminal destination | Alert severity | Effect may already exist |
|---|---|---|---|---|
| TF-A transient | yes, bounded | operational dead-letter on exhaustion | on sustained rate / ODL growth | possibly (§26, §27) |
| TF-B permanent rejection | **no** | terminal domain state and/or ODL | workload-dependent | no, for the rejected step |
| TF-C contract/identity | **no** | **quarantine** | high — schema reject / integrity violation | **no**, never |
| TF-D defect | yes, tightly bounded | operational dead-letter | **high** | possibly (partial handler execution before the exception; the durable effect is all-or-nothing by HT1) |

---

## 18. Retry ownership

| # | Rule |
|---|---|
| RO1 | **Retry policy belongs to the logical failure domain and its handler transport policy**, never to the message. Two messages of the same `event_type` routed to different domains legitimately retry differently. |
| RO2 | A producer **never encodes** a retry count, backoff interval, attempt number, next-retry timestamp, deadline, priority or queue name into a payload in order to steer the transport. Such a field is a contract-discipline violation (item 8 EN3, EN10, PD8; check A52). |
| RO3 | Attempt metadata — attempt number, first-seen time, last error, next scheduled time, terminal reason — is **transport / Inbox / terminal-record metadata**, durable where §23 requires it, and never part of the envelope or payload (R9). |
| RO4 | A retry preserves the message exactly (R8). A retried delivery is the *same* message, not a new one. |
| RO5 | Where a *business* deadline genuinely belongs to the fact — an offer that expires, a reservation window — it is a **payload field with business meaning**, owned by the semantic owner, and is not a retry-control field. The distinction is whether a domain rule reads it (business) or only the transport does (forbidden). |

---

## 19. Retry bounds

| # | Rule |
|---|---|
| RB1 | **No message retries forever on its normal queue.** There is no unbounded retry policy anywhere in the platform (check A55). |
| RB2 | Every retryable failure domain declares, in the matrix: a **bounded attempt count and/or a bounded retry age**, a backoff policy, and an explicit **terminal disposition**. All three are mandatory; a domain with no declared terminal disposition is not a valid domain. |
| RB3 | Bounding by **age** is preferred where a provider outage is the expected failure: attempts alone can exhaust in seconds against a fast-failing circuit and would dead-letter work that a ten-minute outage would have delivered. A domain may declare both, with the terminal disposition triggered by whichever bound is reached first. |
| RB4 | **Numeric attempt counts, ages and seconds are not frozen here.** Master freezes none, and inventing them would fix operations policy in an architecture document. Phase 1 and operations own the values; item 9 owns the requirement that each is explicit, finite and recorded. |
| RB5 | Retry bounds are **per failure domain**, and a workload may declare a tighter bound than its domain's default where the matrix records it. A workload may never declare a *looser* bound than its domain, and never an unbounded one. |
| RB6 | Reaching a bound is a **classification event**, not a silent drop: the message becomes a durable terminal record (§22, §23) and the domain's terminal-failure metric increments (§33). |

---

## 20. Backoff

| # | Rule |
|---|---|
| BO1 | Ordinary transient failures use **increasing, bounded backoff** — exponential by default — with an explicit ceiling on the interval. |
| BO2 | **Jitter is mandatory** wherever many messages can fail at once, which is every provider-backed domain. Without it, one provider outage synchronises every retry into a thundering herd that arrives exactly when the provider recovers. |
| BO3 | A provider's `Retry-After` (or equivalent) **may inform** scheduling where the provider is trusted and the value is clamped to the domain's own bounds. It is never accepted unbounded, and it never overrides RB1's finite bound. |
| BO4 | **Immediate tight retry loops are forbidden.** A retry with no delay is a denial-of-service against the failing dependency and against the queue. |
| BO5 | A waiting retry **must not occupy a worker slot** where the transport supports delayed scheduling. A worker sleeping through a backoff is capacity that a wedged provider has taken from the domain, which is precisely what §5 exists to prevent. |
| BO6 | Backoff policy is expressed in **transport terms**, not tied to any specific Celery primitive. Phase 1 chooses the mechanism (countdown/ETA, a delay queue, a scheduler); the architecture requires only the properties above. |

---

## 21. Provider rate limits and circuit behaviour

| # | Rule |
|---|---|
| PV1 | Every provider-backed domain enforces **provider-specific concurrency and rate limits**, so the platform's own retry behaviour cannot amplify a provider's degradation into a provider outage (master `# 20.1`, `# 20.8`). |
| PV2 | **One provider's outage may never exhaust an unrelated worker pool.** Where two providers share a domain (`ext.payments`, PY5), each has its own budget inside it. |
| PV3 | **Circuit breaking or equivalent load shedding is expected** for provider-backed work: consecutive vendor failures open the circuit, calls fail fast until a half-open probe succeeds (master `# 20.1`). |
| PV4 | **No message is dropped, lost, or marked HANDLED because a circuit is open.** A fast-failed call is a TF-A transient failure: the message is retried within its bounds and, if the bounds are reached, becomes a durable ODL record. Fail-fast changes how long a worker is held, never what happens to the message. |
| PV5 | An open circuit is an **alerted** operational state (master `# 23.2` *DLQ Growth / Circuit Open*), with a duration threshold rather than an alert per failure (§34). |
| PV6 | Circuit state is **per provider and per failure domain**. It is never global, and an open circuit in one domain never suppresses calls in another. |
| PV7 | The circuit-breaker and rate-limiter **implementations and thresholds are Phase 1's**; `integrations/*`'s `BaseClient` is their home (master `# 20.8`, ADR-0005). Item 9 designs neither. |

---

## 22. Quarantine vs operational dead-letter

### 22.1 Two semantic states, never one "failed"

```text
QUARANTINE                                OPERATIONAL DEAD-LETTER (ODL)
"we cannot understand this message"       "we understood it; execution failed"

unknown event_type                        retry bounds exhausted (TF-A)
unsupported / unknown schema_version      permanent workload rejection (TF-B ii/iii)
payload invalid for a known version       handler defect after bounded retries (TF-D)
same event_id, conflicting content

the contract or identity is broken        the contract is fine; the world or the code is not
never any business effect                 an effect may partially or fully exist upstream
fix: producer, deployment order, schema   fix: provider, data, code, or manual completion
```

| # | Rule |
|---|---|
| DL1 | Quarantine and ODL are **two distinct semantic terminal states**. Every terminal record carries which one it is, plus a reason classification within it. |
| DL2 | **Neither is ever called simply "failed"**, in a table, a metric, a log line, an alert, an admin screen or a runbook. An operator must be able to tell the two apart at a glance, because the response is different: quarantine is almost always a producer, deployment-order or schema defect; ODL is almost always a provider, data or code problem (check V65). |
| DL3 | **Phase 1 may map both onto one physical transport mechanism**, but never onto one semantic state. If one durable structure serves both, it carries an explicit terminal-kind discriminator, and every query, metric, alert and replay path distinguishes them. |
| DL4 | Separate storage and separate physical queues for the two are permitted and are the safer default. One physical mechanism with a discriminator is permitted. **One undiscriminated bucket is forbidden.** |
| DL5 | A quarantined message is **never** marked Inbox HANDLED/SUCCEEDED and never recorded as having produced its effect (item 8 QU4, QU15). An ODL record likewise is not a completion — it is a terminal *non*-completion, except where TF-B (i) also wrote a terminal domain state, in which case the *workflow* completed and the *message* still did not deliver its intended effect. That distinction is recorded on the ODL record. |
| DL6 | Both states are **identity-bearing, and the identity is the consumer delivery**: at minimum `event_id`, **the registered consumer/handler identity**, `event_type`, `schema_version`, failure domain, terminal kind, reason classification and the timestamps needed to replay and to diagnose (item 8 QU9, §22.3). |
| DL7 | Both states are **terminal for that delivery**, never for the *fact*. Replay (§28) is the only way out, and it is deliberate. |

### 22.2 Ordering, at the transport boundary

Item 8 §20.3 froze the semantics; item 9 freezes that the transport realises exactly this order and
no other:

```text
validate  (registry lookup → schema → identity integrity)
  → persist the durable terminal record  (quarantine or ODL)
  → COMMIT
  → only then: terminally remove the delivery from the normal processing path
```

| # | Rule |
|---|---|
| DL8 | **The transport never disposes of a delivery before the terminal record's commit.** Acknowledging first and persisting afterwards loses the message on a crash between the two (item 8 QU14). |
| DL9 | **After the commit, the transport must remove the delivery from the normal path** — ack-after-persist, reject/nack without requeue, or the broker equivalent. Leaving it there produces the hot loop RB1 and item 8 QU6 forbid. |
| DL10 | That disposition is a **transport action, never a semantic completion** (DL5). |
| DL11 | The two invariants stated together: **never lose the message before its terminal record is durable, and never leave a permanently failing message hot-looping on a normal queue** (item 8 QU16). |
| DL12 | The exact broker operation is **Phase 1's**. Item 9 names no broker API and requires only the ordering above (item 8 QU17). |

### 22.3 The unit of failure is a **consumer delivery**, not a message

Because an `EVENT` may have several independent consumers in several failure domains (RT4), one
message can be a success in one place and a terminal failure in another **at the same time**. Every
rule about retries, terminal states, alerting and replay is therefore scoped to a *consumer delivery*.

```text
EVENT E, one event_id

  consumer A → handled, effect committed
  consumer B → retries exhausted → operational dead-letter
  consumer C → still retrying
```

| # | Rule |
|---|---|
| DL13 | **Two consumers processing the same `event_id` are two independent consumer deliveries, not two deliveries of one handler's work.** They are never duplicates of each other, and neither one's effect discharges the other's. |
| DL14 | **Each consumer maintains its own Inbox / identity / effect state** for that `event_id` (item 8 IX2 is already per consumer). One consumer's completion record says nothing about another's, and one consumer's terminal state never marks the message terminal for anyone else. |
| DL15 | **One consumer may succeed while another dead-letters or quarantines.** That is a normal, expected outcome for a multi-consumer `EVENT` and is never itself an incident. |
| DL16 | **A terminal record must identify which registered consumer/handler failed** (DL6). "Message X failed" is not actionable when three handlers could have produced it. |
| DL17 | **Failure-domain identity alone is insufficient** to identify the failed consumer, because several consumers may legitimately share one domain (LY6). The consumer identity is recorded in addition to the domain, never instead of it. |
| DL18 | Item 9 designs **no key, column or index** for this. It freezes the identity that must be recoverable; Phase 1 owns the structure (TD9). |

---

## 23. Terminal-state durable truth

> **PostgreSQL is the canonical durable truth for both terminal states. A broker DLQ is transport —
> a parking place and an operational reference — and is never the sole durable record.**

| # | Rule |
|---|---|
| TD5 | This follows R1 directly. A broker's dead-letter queue can be lost to a broker restart with a non-durable configuration, a topology reconfiguration, a queue redeclaration with different arguments, a purge, a TTL, a max-length policy, or a broker migration. None of those may lose a payment reconciliation that needs manual completion. |
| TD6 | **Contract quarantine truth is PostgreSQL state** — the consumer's Inbox/quarantine record — carrying the envelope, the payload, the rejection reason and the identity needed to replay (item 8 QU7, QU9). A broker quarantine/DLQ queue may exist as transport and as an operational view; it is never consulted as the authority. |
| TD7 | **Operational dead-letter truth is durable platform state** sufficient to survive broker loss or reconfiguration: at minimum the identity of DL6 — including **which registered consumer/handler failed** (DL16) — the terminal reason, the attempt history summary, and a durable reference to the full message. |
| TD8 | **The payload need not be stored twice.** Where the original Outbox or Inbox row already retains the message within its retention window, the ODL record may reference it rather than copy it. Where it does not — because the source row has been archived, or the message came from a route with a shorter retention — the terminal record retains enough to replay on its own. The requirement is *sufficiency for replay and diagnosis*, not duplication. |
| TD9 | Item 9 designs **no table, column, index or partition** for either state. Phase 1 owns the schema, informed by master `# 20.2`/`# 20.3` and by this durability requirement. |
| TD10 | Terminal records are subject to redaction in everything **displayed** — logs, alerts, admin screens, exports — while the retained record itself stays complete (item 8 SEC8, master `# 20.8`, `# 21`). Retention is not an exemption from redaction. |
| TD11 | A failure to persist a terminal record is itself a **high-severity** condition: the delivery must **not** be disposed of (DL8), so it stays on the normal path and retries. If terminal storage is unavailable, work backs up visibly rather than disappearing quietly (§35 row 15). |

---

## 24. Terminal-destination isolation

| # | Rule |
|---|---|
| TI1 | **Each logical failure domain has its own terminal namespace.** Master `# 20.1`'s `ext.<vendor>.dlq` convention generalises to `<failure-domain>.dlq` for every domain, internal ones included. |
| TI2 | **One global undifferentiated `dead_letters` bucket is forbidden** (check A56). A poison ERP batch must never sit in the same undiscriminated place as a payment reconciliation failure: the two have different owners, different runbooks, different urgency and different replay authority. |
| TI3 | The originating failure domain **and the failed consumer identity** are both part of the **durable terminal record**, not only of the queue it landed on. Storage and routing identity preserve origin, so re-routing or a topology change cannot erase where a failure came from — and because several consumers may share one domain (LY6), the domain alone never identifies the failure (DL16, DL17). |
| TI4 | A **global operational view may aggregate** every domain's terminal records for triage. Aggregation in a UI is not aggregation in storage, and the aggregated view always shows terminal kind (DL1) and origin domain. |
| TI5 | Terminal namespaces are **never shared between domains**, and a domain's terminal namespace is never used as a normal-processing queue for anything. |
| TI6 | Each domain's terminal namespace has a **named operational owner and a runbook path** (`docs/runbooks/<alert-name>.md`, master `# 23.3`). A terminal destination with no owner is not production-ready. |

---

## 25. Poison messages

| # | Rule |
|---|---|
| PM1 | A deterministically failing message **must not re-consume its whole retry budget after every worker restart, deployment or broker redelivery**. |
| PM2 | Terminal state is **durable** (§23), so it survives restarts. Once a message is classified terminal, its identity record says so. |
| PM3 | On redelivery of a message already in a terminal state: the delivery is **recognised**, no handler runs, no business effect occurs, no automatic retry restarts, and the delivery is disposed of from the normal path (DL9). |
| PM4 | **Alert storms are suppressed while observability is retained**: repeated recognition of an already-terminal message increments a counter and does not raise a new page. The condition is already alerted; re-alerting on redelivery buries the incident it is reporting (§34). |
| PM5 | **Only a deliberate replay reopens processing** (§28). No deployment, restart, migration, configuration change or backlog drain reopens a terminal message. |
| PM6 | PM3's recognition is the same mechanism as item 8 QU9 and R6: the consumer's durable first-seen identity record, extended with terminal state. It is not a second, parallel mechanism. |

---

## 26. Delivery ambiguity: crashes and lost acknowledgements

The classic case:

```text
worker performs the durable effect and COMMITs
worker crashes before the broker acknowledgement
broker redelivers
```

| # | Rule |
|---|---|
| AM1 | **Redelivery is expected, normal and not an incident** (R5). Every normal queue policy assumes at-least-once delivery. |
| AM2 | **The broker acknowledgement is never the exactly-once mechanism.** Correctness comes entirely from item 8's consumer identity retention, per-`event_id` effect idempotency and the one-local-transaction handler rule (R6, item 8 HT1/HT2). |
| AM3 | **No exactly-once broker semantics are designed, configured or relied upon.** Any argument of the form "the broker will not deliver it twice" is invalid. |
| AM4 | **Crash before the effect commits:** nothing committed — no effect, no Inbox completion, no Outbox rows. Redelivery is an ordinary first attempt (item 8 HT2, C64). |
| AM5 | **Crash after the effect commits, before the acknowledgement:** the effect is committed exactly once. Redelivery finds the completed identity/effect record, does **not** repeat the effect, and the handler completes normally. |
| AM6 | **A lost acknowledgement is never a reason to dead-letter.** The redelivery in AM5 succeeds; it is a duplicate, which is an ordinary operating condition, not a failure. Routing it to ODL would manufacture a terminal record for a message that worked (check V67). |
| AM7 | The transport may acknowledge the AM5 duplicate normally. Acknowledging a recognised duplicate is a correct completion of that *delivery*, and it does not re-record the effect. |
| AM8 | Visibility-timeout / prefetch tuning is Phase 1's. No correctness rule may depend on a visibility timeout being long enough — a handler that would be wrong if redelivered mid-flight is wrong. |

---

## 27. Ambiguous external outcomes

```text
outbound HTTP request sent
connection breaks before the response arrives
→ the provider may or may not have applied the action
```

| # | Rule |
|---|---|
| AX1 | **A non-idempotent provider operation is never blindly retried on ambiguity.** "Timeout, therefore it is safe to send again" is not an inference the queue retry policy is allowed to make. |
| AX2 | Where the provider supports **idempotency keys**, an outbound call carries a stable, workflow-owned key so that a retry is provably the same operation. This is the first choice for every payment-class operation. |
| AX3 | Where it does not, the workflow uses an **application-owned status lookup or reconciliation** to establish what actually happened before deciding to re-send (master `# 12.2`/`# 12.3`: webhook is an accelerator, reconciliation is the path to truth, R13). |
| AX4 | **The ambiguous outcome belongs to the workflow's state machine**, owned by the application module (`application/payments_gateway`, `application/erp_sync`, …). It is not a transport decision, and the queue's retry policy never resolves it. |
| AX5 | On ambiguity, the transport's role is bounded: it may **stop retrying** and hand the workflow a durable ambiguous-outcome state to resolve, or retry only where AX2 or AX3 makes the retry provably safe. It never guesses. |
| AX6 | This matters most for **payments**, where a blind retry is a double charge. It applies equally to any non-idempotent provider mutation — ERP document creation, refund, code redemption at a vendor. |
| AX7 | Item 9 designs **no maib/MIA protocol field, no provider idempotency-key format and no reconciliation query.** Those belong to the payments phase and to `integrations/<provider>` (ADR-0005 §6). |

---

## 28. Replay authority

| # | Rule |
|---|---|
| RA1 | Replay is a **privileged operational action**, not a routine part of processing. |
| RA2 | Replay is **explicit** — a human or an explicitly authorised automated procedure initiates it for identified messages. |
| RA3 | Replay is **authorised**: it is a permissioned backoffice/runbook operation, not something any worker, deployment or background job can perform. |
| RA4 | Replay is **audited**: who, when, which messages, from which terminal state, and why. Where the operational process requires it, a reason, ticket or incident reference is recorded with the replay. |
| RA5 | Replay is **idempotent by construction**: it re-enters the normal idempotency boundary (§29), so replaying a message whose effect already exists produces no second effect (R6). |
| RA5a | **Replay is scoped to the failed consumer delivery** (§22.3), never to the message. The operator replays *consumer B's* terminal record, not "event E". |
| RA5b | **A replay never rebroadcasts the message to the other consumers of the same `EVENT`.** A consumer that already succeeded is never re-executed because a sibling consumer is being replayed, and a consumer that is still retrying is not disturbed (DL13–DL15, C83). Re-delivering to a successful consumer would be harmless only by luck — its effect idempotency would absorb it — and relying on that is not a design. |
| RA6 | **Replay is never automatic merely because a deployment happened**, a consumer gained a version, a circuit closed, a provider recovered or a backlog drained. Those are the *reasons* an operator chooses to replay; none of them is the *trigger* (PM5). |
| RA7 | **Replay preserves the original message exactly**: `event_id`, `event_type`, `schema_version`, `occurred_at` and payload, byte-for-byte (R8, item 8 QU11, C66). |
| RA8 | **A replay never mints a new `event_id`.** Doing so converts one fact into two and defeats every consumer's duplicate detection at once (check A57, V68). |
| RA9 | **A new business attempt is a different operation from a replay.** If the platform must genuinely *do something new* — retry a payment as a new attempt, re-export a corrected ERP document, send a *different* notification — its owner emits a **new** message with a **new** `event_id` through the normal Outbox path (item 8 ID4). Replay re-delivers a fact; a new attempt creates one. Confusing the two is how a replay tool becomes a way to duplicate commercial operations. |
| RA10 | Bulk replay is permitted under the same rules and is **rate-limited into the target domain**, so recovering from an incident does not create a second one (§33). |
| RA11 | The replay tooling, its UI, its permission model and its audit storage are **Phase 1 / operations**. Item 9 freezes the properties. |

---

## 29. Replay destination

A replayed consumer delivery re-enters at the **normal validation and handler boundary of that
consumer's failure domain**. It never bypasses validation and never calls a handler function directly,
and it reaches **only the consumer being replayed** (RA5a, RA5b).

```text
contract quarantine replay  (consumer B's quarantined delivery)
  → B's current failure domain
  → registry lookup
  → schema validation for the declared (event_type, schema_version)
  → B's identity-integrity check against B's retained first-seen record
  → B's handler

operational dead-letter replay  (consumer B's terminal record)
  → B's current failure domain
  → normal handler transport boundary
  → B's identity-integrity check
  → B's business-effect idempotency check
  → B's handler

consumers A and C are not invoked.
```

| # | Rule |
|---|---|
| RD1 | **There is no force-apply path.** No tool, admin action, management command or flag may skip validation, skip the identity check, skip idempotency, or apply a payload directly to domain state (check A58). |
| RD2 | **A still-invalid replay returns to quarantine.** If the type is still unknown, the version still unsupported or the payload still invalid, the replay produces the same TF-C outcome, is re-quarantined and is never coerced (item 8 QU2, CS4–CS6). Replay is not a second chance to be lenient. |
| RD3 | **A replay of an already-completed consumer delivery produces no second effect.** That consumer's identity and effect records recognise it and the handler completes as a duplicate (AM5, R6, C79). |
| RD4 | A replay is routed to the **failure domain that consumer is currently assigned to**, which may differ from the one it originally failed in if its assignment has since moved (RT11). Replay follows the current routing policy, not a stale copy of it, and it uses **that consumer's** assignment — not another consumer's, and not an entry-global default, because there is none (RT3). |
| RD5 | A replayed delivery that fails again is classified normally (§17) and returns to a terminal state **for that consumer**. It does not get a larger retry budget for being a replay, and it does not loop. |
| RD6 | Replay never changes a consumer's failure domain, criticality, retry policy or contract as a side effect of being replayed. |
| RD7 | **A replay tool that can only address a whole message is not conformant.** The addressable unit is the consumer delivery; bulk replay is a set of consumer deliveries, selected explicitly, not a re-emission of the underlying facts (RA5a, RA5b, RA9). |

---

## 30. Replay and schema retirement

| # | Rule |
|---|---|
| RS1 | A `RETIRED` `schema_version` has, by item 8's rules, **proved** that no legitimate replay requirement remains (item 8 PE7, RG6, RR3). Item 9 does not undermine that proof. |
| RS2 | **A normal replay of a retired version is not a supported operation.** If one is attempted, the arrival is an unknown version: TF-C, quarantine, alert (item 8 §25.2 `RETIRED`, §32 row 7). The alert is meaningful — it says the retirement proof was wrong. |
| RS3 | **Forensic decoding stays possible** where the schema is retained (item 8 RR4, SC4): an archived message can be read and understood for a legal, financial or investigative reason. Reading it is not executing it. |
| RS4 | Consumer *execution* support for a retired version has been legitimately removed and is not restored by a replay tool. If the platform genuinely must act on such a fact again, its owner introduces a current-version message for it (RA9). |
| RS5 | A `DEPRECATED` version is a different case entirely: it is **still fully replayable and still mandatory for every declared consumer** (item 8 RG4, RG5). Draining a deprecated backlog is exactly what §19's bounds and replay exist to support. |

---

## 31. Broker outage

| # | Rule |
|---|---|
| BR1 | **A broker outage may not lose committed business state.** The business mutation and its Outbox rows commit together in PostgreSQL with no broker involvement whatsoever (R2, master `# 20.2`). |
| BR2 | **A business transaction never depends on broker availability.** A producer that cannot reach the broker still commits, because it never talks to the broker in the first place. A broker outage during a checkout is invisible to the checkout (§35 row 12). |
| BR3 | **Direct producer → broker publishing stays forbidden** (R2, check A53). It is the one shape that would make BR1 and BR2 false. |
| BR4 | The **relay** retries against the broker under its own bounded policy and marks an Outbox row delivered only when the target transport has accepted it. An unaccepted row stays unprocessed and is retried. |
| BR5 | On broker recovery, the relay **drains the backlog** in its normal order without operator intervention. Recovery is not a replay (RA6) — those rows were never delivered. |
| BR6 | **A growing Outbox backlog is observable and alerted**: oldest-unprocessed-event age against an SLO (master `# 23.2` *Outbox Relay Lag*, `# 20.2`). A broker outage is therefore visible as a rising relay lag rather than as silence. |
| BR7 | The relay's own capacity is separate from every consumer domain's (FD11), so a consumer-side backlog cannot slow the relay and a slow relay cannot consume consumer capacity. |
| BR8 | Item 9 designs **no Outbox table, no relay SQL and no batch size.** Master `# 20.2` sketches them and Phase 1 owns them. |

---

## 32. A single queue or domain unavailable

| # | Rule |
|---|---|
| QO1 | If one logical failure domain's queue is unavailable or rejecting, **other domains continue** wherever the broker topology permits. A per-domain physical separation is what makes this possible, and it is one more reason LY5 forbids merging domains. |
| QO2 | Outbox rows destined for the failed route **remain durable and unprocessed**. Nothing is dropped, and nothing is marked delivered (BR4). |
| QO3 | **The relay is fair across domains**: a route that is persistently failing must not cause the relay to stall, abandon or starve routing for unrelated domains. A blocked route is skipped or deferred with its own backoff while other routes continue. |
| QO4 | Fairness is a **requirement on relay behaviour**, not a scheduling algorithm frozen here. Round-robin, per-route cursors, per-route workers or a partitioned relay all satisfy it; a single head-of-line queue that stops at the first failing row does not. |
| QO5 | A persistently unroutable domain raises its own alert (§34) and shows as a per-domain relay backlog (§33), distinguishable from a whole-broker outage. |
| QO6 | Item 9 designs **no relay SQL, cursor structure or scheduling implementation** (BR8). |

---

## 33. Backpressure

| # | Rule |
|---|---|
| BP1 | **Backlog is an operational signal, not an error.** A queue that is long is telling the platform something; the response is capacity, isolation and triage. |
| BP2 | **Per-failure-domain** metrics are required. Conceptually: ready depth; oldest-message age; retry rate; terminal-failure rate split by kind (quarantine vs ODL); quarantine count; and processing latency. Per-domain is the point — a platform-wide aggregate hides exactly the isolation failure these metrics exist to catch. |
| BP3 | Metric names, labels, exporters and dashboards are **observability's** (master `# 23.1`, `# 23.2`). Item 9 freezes what must be measurable and at what granularity, not what it is called. |
| BP4 | **Backpressure policy favours preserving critical-domain progress over draining best-effort backlog.** When capacity is contended, `BEST_EFFORT` work waits. |
| BP5 | **Durable messages are never dropped to reduce queue depth.** Not by TTL, not by a max-length policy, not by a purge, not by an "obviously stale" heuristic. A backlog is reduced by processing it, by adding capacity, by rate-limiting its producer, or — deliberately and with a record — by moving it to a terminal state; never by deletion. |
| BP6 | A broker max-length or TTL policy that silently discards messages is **forbidden on any normal-processing queue**, because it would make PostgreSQL and the broker disagree about what was delivered. |
| BP7 | Where a producer is genuinely overwhelming a domain, the correct responses are coalescing at the producer (item 8 PD4, master `# 20.2`), bounded batching, and rate-limiting the producing job — not discarding its output. |

---

## 34. Alerting

Item 9 freezes the **severity classes** and their triggers. Numeric thresholds, routing and on-call
rotation are operations' (master `# 23.2`, `# 23.3`).

| Class | Trigger | Severity | Notes |
|---|---|---|---|
| Contract/schema quarantine | Any TF-C quarantine event | high | Master `# 23.2` *Event Schema Reject*, widened by item 8 QU8 to unknown types, invalid payloads and identity conflicts. Almost always a producer or deployment-order defect. |
| Identity-integrity violation | Same `event_id`, conflicting content (item 8 IX5) | high | Distinct from an ordinary schema reject: it means a producer bug, a mis-copied identity or corruption. |
| Critical domain stalled | A `CRITICAL` domain's throughput at zero with a non-empty backlog | P1 | Per domain. `core.payments` and `ext.payments` stalls are financial-contour incidents. |
| Oldest-message age exceeded | A domain's oldest ready message older than its SLO | P1 for `CRITICAL`, P2 for `IMPORTANT` | Includes *Listing Projection Lag* (master `# 23.2`) for `core.projection.incremental`. |
| Retry storm | Sustained elevated retry rate in one domain | P2 | Rate-based and sustained; never one alert per retry. |
| Terminal-failure growth | Rising quarantine or ODL rate | P2, or P1 for a `CRITICAL` domain | Master `# 23.2` *DLQ Growth*; reported **per domain, per terminal kind and per failed consumer** — the domain alone does not identify the handler when several consumers share it (DL2, DL16, DL17, TI3). |
| Circuit open | A provider circuit open beyond a duration threshold | P2, P1 for a payment provider | Master `# 23.2` *Circuit Open*. |
| Outbox relay backlog | Oldest unprocessed Outbox row age beyond SLO; or a persistently unroutable domain | P1 | Master `# 23.2` *Outbox Relay Lag*; the primary broker-outage signal (BR6, QO5). |
| Terminal storage failure | Unable to persist a quarantine or ODL record | P1 | TD11; work backs up rather than disappearing, and the backlog is the secondary signal. |
| Replay failure | A replay batch that re-fails, or a replay re-quarantined | P2 | RD2, RD5. |
| Programmer/invariant failure | A TF-D classification | high | TD1; never folded into provider-failure metrics (TD3). |

| # | Rule |
|---|---|
| AL1 | **Alert on sustained or terminal conditions, never on every retry.** A retry is a designed behaviour; alerting on it trains operators to ignore the channel. |
| AL2 | **Repeated recognition of an already-terminal message is deduplicated** and does not re-page (PM4). |
| AL3 | Every alert carries a `runbook_url` and an explicit owner (master `# 23.3`). An alert without both is not production-ready, and a failure domain without a runbook owner is not a valid domain (NX5, TI6). |
| AL4 | Alert thresholds, SLO numbers and routing are **operations'**, and are not frozen here (§1.2). |

---

## 35. Failure matrix

**Every row describes one consumer delivery**, not a message (§22.3). For a multi-consumer `EVENT`,
different consumers may sit in different rows at the same moment — one handled, one dead-lettered, one
still retrying — and each row's outcome, terminal record and replay are scoped to that consumer alone
(DL13–DL17, RA5a, RA5b).

**Commercial impact** is assessed against the frozen invariants: no order, payment, reservation or
price outcome may depend on message delivery (item 8 SR4, R11, ADR-0007).

| # | Situation | Retry on normal queue? | Terminal classification | Effect may already exist? | Durable record | Operator action | Which domains may be affected |
|---|---|---|---|---|---|---|---|
| 1 | Transient provider 5xx | Yes, bounded backoff (TF-A) | ODL only on exhaustion | No, for the failed call | Outbox/Inbox row; ODL if exhausted | None below threshold; check provider on a sustained rate | That provider's domain only |
| 2 | Provider timeout, known to have no side effect | Yes, bounded (TF-A) | ODL on exhaustion | No | As row 1 | None | That provider's domain only |
| 3 | Provider timeout, **ambiguous** side effect | **No blind retry** (§27) | Workflow ambiguous state; ODL if unresolvable | **Yes, possibly** | Workflow state + ODL where applicable | Resolve via idempotency key or status lookup/reconciliation | That provider's domain; the owning workflow |
| 4 | Provider rate limit (retryable) | Yes, backoff honouring `Retry-After` within bounds (TF-A, BO3) | ODL on exhaustion | No | As row 1 | None below threshold | That provider's budget inside its domain (PV2) |
| 5 | Permanent provider rejection of a valid request | **No** (TF-B) | Terminal domain state and/or ODL per the workload's declaration (TB2) | No, for the rejected step | Domain state and/or ODL | Triage per runbook; often a data fix | That provider's domain |
| 6 | Invalid payload for a known version | **No** (TF-C) | **Quarantine** | **No, never** — no partial application | PostgreSQL quarantine record | Fix the producer; replay after the fix | Only the consuming domain; producer investigation |
| 7 | Unsupported / unknown `schema_version` | **No** (TF-C) | **Quarantine** | **No** | PostgreSQL quarantine record | Usually item 8 PE6 violated: deploy consumer support, then replay | Only the consuming domain |
| 8 | Same `event_id`, conflicting type/version/payload | **No** (TF-C) | **Quarantine**, integrity violation | **No** — the conflicting delivery is never applied | Quarantine record; the first observation is never overwritten | High-severity: producer bug, mis-copied identity or corruption | Only the consuming domain |
| 9 | Programmer exception in a handler | Yes, tightly bounded (TF-D) | **ODL**, high-severity | Possibly partially — but the durable effect is all-or-nothing (item 8 HT1) | ODL record with a defect reason | Fix the code, then replay | The handler's domain |
| 10 | Worker crash **before** the effect commits | Yes — ordinary redelivery | None | **No** — nothing committed | Inbox row unchanged; no completion, no Outbox rows | None | None |
| 11 | Worker crash **after** the effect commits, before the ack | Yes — ordinary redelivery | None | **Yes**, committed exactly once | Completed identity/effect record | None; **never dead-letter this** (AM6) | None |
| 12 | Broker unavailable during the producer's transaction | N/A — the producer never touches the broker | None | Business effect commits normally | Outbox row, durable, unprocessed | None; watch relay lag | **None** — the business transaction is unaffected (BR2) |
| 13 | Broker unavailable during relay | Relay retries under its own bounds | None | No | Outbox rows stay unprocessed and undelivered | Restore the broker; the backlog drains automatically (BR5) | Every domain's *delivery* is delayed; no domain's committed state is affected |
| 14 | One queue / domain unavailable | That domain's messages stay undelivered | None | No | Outbox rows for that route stay unprocessed | Restore that route; relay stays fair to the others (QO3) | **Only that domain** |
| 15 | Quarantine / ODL storage failure | **Yes** — the delivery is **not** disposed of (DL8, TD11) | None yet | No | The source Outbox/Inbox row | P1: restore terminal storage; the visible backlog is the signal | The affected domain backs up |
| 16 | Replay of a still-invalid consumer delivery | No | **Back to quarantine** (RD2) | **No** | That consumer's quarantine record updated | The underlying defect was not fixed; do not coerce | Only that consumer's domain |
| 17 | Replay of an already-completed consumer delivery | Handled as a duplicate | None | **Yes** — and it is **not** repeated (RD3) | That consumer's existing completion record | None | None |
| 17a | Multi-consumer `EVENT`: consumer A handled, consumer B in ODL | B only; A is finished | ODL **for B alone** | Yes for A, no for B | Two independent records, each naming its consumer (DL16) | Replay **B's** delivery; A is never re-invoked (RA5b, C83) | Only B's domain — A's is untouched |
| 18 | Full projection rebuild backlog | Rebuild work retries within its own domain | ODL per batch on exhaustion | Projection rows are idempotent by the item 12 guard | Rebuild batch state | Add rebuild capacity; **never** an OLTP request fallback (R11, PJ7) | `core.projection.rebuild` only — incremental keeps its SLO (PJ2) |
| 19 | ERP retry storm | Yes, bounded, rate-limited and circuit-controlled | ODL on exhaustion | ERP writes resolved by idempotency/reconciliation (§27) | ODL records in `ext.erp`'s namespace | Triage per the ERP runbook | **`ext.erp` only** — never payments, inventory or projection (EP5, C71) |
| 20 | Notification-provider outage | Yes, bounded (TF-A); permanent recipient failures are TF-B | ODL on exhaustion | No | ODL records in that notification domain | Best-effort triage | `ext.email` **or** `ext.sms`, not both (NT1) |
| 21 | Payment reconciliation backlog | Work retries within its domain | ODL on exhaustion | Committed money state is unaffected by delivery | `core.payments` records; provider truth unchanged | **P1.** Reconciliation is the convergence mechanism; a backlog delays convergence, it does not corrupt state | `core.payments` — and it must be reachable *only* from within it (PY3) |

Every row's commercial impact is **none** for committed state: reservations, orders, payments and
prices are decided by durable PostgreSQL transactions under locks, never by message delivery
(ADR-0007, item 5, R11).

---

## 36. Relationship to the event registry

| # | Rule |
|---|---|
| RX1 | **Every declared consumer that may receive a production delivery carries a failure-domain assignment** in its own consumer declaration, naming a domain that exists in the matrix and has a normal-processing path (RT8, check A51). An `EVENT` with no declared consumers needs none (RT5). |
| RX2 | That assignment is **mutable operational metadata on the consumer declaration**, governed by item 8 §26.1's operational half. It is not part of the immutable contract half, and it is **not** an entry-global column of the `(event_type, schema_version)` row (RT3). |
| RX3 | **Changing a consumer's assignment never bumps `schema_version`**, never creates a new `event_type`, never re-declares supported versions and never alters an effect-idempotency mechanism (LY3, RT6, RT11). It affects only that consumer. |
| RX4 | The registry names the **domain**, never a queue, an exchange, a routing key, a priority, a retry schedule or a concurrency number (RT10). Those live in the matrix and in Phase 1 configuration. |
| RX5 | The matrix names **no `event_type`**. Item 8's registry ships empty by design, and the matrix must not become a back door for inventing a catalogue (item 8 RG8). It describes workload categories; registered messages point *at* it, not the reverse. |
| RX6 | The matrix confers **no ownership**. A semantic owner is the module that owns the fact (item 8 OW1); routing a consumer delivery into a domain gives that domain's operational owner an on-call responsibility, never contract authority. |
| RX7 | Item 9 adds **one operational field to each consumer declaration** and changes **no** item 8 rule, no status semantics, no invariant, no contract column and no consumer-cardinality rule. Item 8 KD2 (an `EVENT` may have zero, one or many consumers), KD3 (a `COMMAND` has exactly one) and IX13 (per-consumer effect idempotency) stand exactly as written; item 9's assignment simply joins them in the same per-consumer record. |

---

## 37. Checks a later phase must implement

Continuing the numbering established by items 3–8 (`A50`, `C69`, `V61` were the last used).

### 37.1 Static / architecture (`A` series)

| # | Check |
|---|---|
| A51 | **Every declared production consumer/handler that can receive a delivery has a valid failure-domain assignment.** For every registry entry whose status permits emission, each declared consumer names a logical failure domain that exists in the matrix and has a normal-processing path. A missing or unknown domain fails the build. This is **not** a check that "every event version has one failure domain" — an `EVENT`'s consumers may legitimately name different domains, and an `EVENT` with no declared consumers has nothing to check (RT3, RT4, RT5, RT8, RX1). |
| A52 | **No transport metadata in a business contract.** No payload field or envelope field is a queue, exchange, routing key, worker name, priority, retry count, attempt number, backoff interval or next-retry timestamp; no such name appears in a message contract module (RO2, LY2, item 8 EN3/EN7/EN10). |
| A53 | **No direct producer → broker publish.** No `domains/*`, `application/*` or `interfaces/*` module calls a broker/Celery publish, `apply_async`, `delay`, `send_task` or an equivalent. Producers write Outbox rows; only the relay and the transport layer publish (R2, BR3, item 3 §4.2/§4.3/§4.4). |
| A54 | **No provider I/O from a `core.*` domain.** No handler routed to a `core.*` failure domain reaches an `application/<a>/ports.py` outbound port, an `integrations/*` client, or any HTTP/SDK call (QN5, PY6, R4). |
| A55 | **No unbounded retry policy.** Every failure domain and every declared per-workload override has a finite attempt bound and/or a finite retry-age bound plus a terminal disposition; an infinite-retry, `max_retries=None`-equivalent or missing-bound configuration fails (RB1, RB2). |
| A56 | **No global undifferentiated dead-letter.** Every terminal destination is domain-scoped, and every terminal record carries its origin domain and its terminal kind (quarantine vs ODL). A shared bucket without a domain discriminator fails (TI2, DL3, DL4). |
| A57 | **No replay path mints a new identity.** No replay code path assigns a new `event_id`, or rewrites `event_type`, `schema_version`, `occurred_at` or payload (RA7, RA8). |
| A58 | **No force-apply path.** No replay, admin action or management command invokes a handler or applies a payload while bypassing registry lookup, schema validation, identity-integrity check or business-effect idempotency (RD1, RD2). |
| A59 | **No neighbouring item's vocabulary here.** This artifact and the matrix define no trace/correlation/causation field (item 10) and no `source_version` / revision / guarded-upsert mechanism (item 12), and invent no `event_type`, payload schema or `schema_version` (item 8). A reviewer-runnable grep-level check on the artifacts themselves. |

### 37.2 Behavioural / contract tests (`C` series)

| # | Test |
|---|---|
| C70 | **ERP outage does not block payment convergence.** With `ext.erp` fully wedged and saturated with retries, `core.payments` still applies durably ingested provider events within its SLO, and `ext.payments` still progresses for unaffected providers (WC5, PY3, EP5, master `# 24.8`). |
| C71 | **An ERP retry storm does not consume unrelated capacity.** Neither `core.payments`, `core.inventory` nor `core.projection.incremental` loses throughput while `ext.erp` is storming (EP4, EP5). |
| C72 | **A rebuild backlog does not starve incremental projection updates.** With `core.projection.rebuild` saturated by a full rebuild, incremental updates still meet their freshness SLO, and no request path falls back to OLTP joins (PJ2, PJ7, R11). |
| C73 | **A notification retry storm does not block projection or payment work.** `ext.email`/`ext.sms` saturated at their ceiling leaves `core.projection.incremental` and `core.payments` unaffected (NT5, WC3). |
| C74 | **Effect committed, acknowledgement lost → no second effect.** An injected crash between the durable commit and the acknowledgement produces exactly one business effect on redelivery, and the redelivery is **not** dead-lettered (AM5, AM6, item 8 IX8). |
| C75 | **Ambiguous provider timeout is not blindly duplicated.** A non-idempotent outbound call whose response is lost does not produce a second provider mutation; the outcome is resolved by an idempotency key or a status lookup (AX1–AX3). |
| C76 | **Quarantine commits before transport disposition.** An injected failure between validation and the quarantine commit leaves the delivery still available on the normal path; after the commit, the delivery leaves the normal path without being marked HANDLED (DL8–DL11, item 8 C69). |
| C77 | **Terminal replay preserves identity.** Replay from both quarantine and ODL preserves `event_id`, `event_type`, `schema_version`, `occurred_at` and payload byte-for-byte (RA7, item 8 C66). |
| C78 | **A still-invalid replay returns to quarantine.** Replaying an unsupported-version or invalid-payload message re-quarantines it, applies no partial effect and coerces nothing (RD2). |
| C79 | **Replay of a completed message duplicates nothing.** Replaying a message whose effect already committed produces no second effect and completes as a duplicate (RD3, R6). |
| C80 | **Broker unavailable at producer time does not roll back the business transaction.** With the broker down, a business operation still commits with its Outbox rows; nothing publishes; relay lag rises (BR1, BR2, §35 row 12). |
| C81 | **Relay resumes and stays fair.** After broker recovery the relay drains the backlog with no operator action; with one route persistently failing, the other domains' rows are still relayed (BR5, QO3). |
| C82 | **A terminal poison message does not restart automatic retries.** After a worker restart, a deployment and a broker redelivery, an already-terminal consumer delivery is recognised, runs no handler, restarts no retry budget, produces no effect and raises no new page (PM1–PM5, AL2). |
| C83 | **Replaying one failed consumer does not re-run the others.** One `EVENT` with consumers A and B: A succeeds, B exhausts its retries and reaches ODL. Replaying B runs or reconciles B exactly once and **A is not invoked again** — asserted by A's handler-invocation count, not merely by A's effect count, so an idempotent handler cannot mask a rebroadcast (RA5a, RA5b, DL13–DL15, RD7). |
| C84 | **One `EVENT`, two consumers, two failure domains.** An `EVENT` whose consumers are assigned to different domains is delivered to each in its own domain, with independent retry budgets and independent terminal states; wedging one consumer's domain leaves the other consumer's processing unaffected, and each terminal record names the consumer that produced it (RT4, DL16, DL17). |

### 37.3 Review-only (`V` series)

| # | Review item |
|---|---|
| V62 | One queue for everything, or one shared "external integrations" queue that includes payment work (FD7, PY4). |
| V63 | Priority used as the only isolation mechanism between two workloads with different criticality (PS1, PS5). |
| V64 | A software defect reported as a provider or transient failure, so the TF-D alert never fires (TD3). |
| V65 | A terminal state described merely as "failed", or a UI/metric/runbook that cannot distinguish quarantine from operational dead-letter (DL2). |
| V66 | A broker DLQ treated as the source of truth for a terminal state, or an ODL record insufficient to replay after the source row is archived (TD5–TD8). |
| V67 | A duplicate delivery or a lost acknowledgement routed to a terminal state instead of completing as a duplicate (AM6). |
| V68 | A replay that mints a new `event_id`, or a "new business attempt" implemented as a replay of an old message (RA8, RA9). |
| V69 | A retry, attempt count, backoff or queue name appearing in a payload to steer the transport (RO2). |
| V70 | Exact retry counts, backoff seconds, concurrency numbers or SLO values invented in an architecture artifact without master support (RB4, WC6, AL4). |
| V71 | A workload routed to a `CRITICAL` or `IMPORTANT` domain to avoid provisioning a `BEST_EFFORT` one, or a `BEST_EFFORT` workload sharing a critical domain's reserved capacity (NX4, WC1). |
| V72 | A `BEST_EFFORT` classification used to justify weaker durability, weaker validation, a skipped identity check or a droppable message (CR5, BP5). |
| V73 | Routing treated as a property of the message rather than of the consumer: one entry-global domain assumed for a multi-consumer `EVENT`; a producer choosing where its fact will be handled; a terminal record or an alert that names only the message and the domain, leaving the failed handler ambiguous; or a replay tool whose smallest addressable unit is the message (RT3, RT4, RT12, DL16, DL17, RD7). |

---

## 38. Acceptance checklist

- [x] Failure-domain definitions are explicit and finite; which are provisioned at launch follows from the enabled workloads, and the module MVP/later cut stays item 14's (§7, FD8, FD9, FD9a).
- [x] Routing is assigned **per consumer declaration**, never once per `(event_type, schema_version)` (RT3, RT4, A51).
- [x] A `COMMAND` has exactly one route; an `EVENT`'s consumers may have different ones; a zero-consumer `EVENT` needs none (RT4, RT5).
- [x] A producer never selects a failure domain (RT12, V73).
- [x] The unit of failure, terminal identity and replay is a **consumer delivery** (§22.3, DL13–DL18).
- [x] A terminal record names the failed consumer, not only the message and the domain (DL16, DL17, TD7, TI3).
- [x] Replaying one failed consumer never re-invokes a successful sibling consumer (RA5a, RA5b, RD7, C83).
- [x] Payment-critical work is isolated from every unrelated integration (§8, PY4, PY7).
- [x] The payment outbound / convergence isolation decision is explicit and reasoned (§8.2).
- [x] A projection rebuild cannot starve incremental updates (§9, PJ2, C72).
- [x] ERP batches cannot starve latency-sensitive work (§10, EP4, EP5, C71).
- [x] Notifications, CRM and support cannot consume critical worker capacity (§11, §12, NT5, NX4).
- [x] Queue identity is transport metadata, never event semantics (LY2, RT1).
- [x] A routing change never bumps `schema_version`, and affects only the consumer whose assignment moved (LY3, RT6, RT11, RX3).
- [x] Priority does not substitute for failure isolation (§15).
- [x] Critical domains have reserved worker capacity, and autoscaling alone does not satisfy it (WC1, WC4, WC5).
- [x] No normal queue retries forever (RB1, A55).
- [x] Retries preserve `event_id`, `occurred_at` and the whole message (TA2, RO4, R8).
- [x] Contract quarantine and operational dead-letter are two semantic states, never one "failed" (§22, DL1, DL2).
- [x] Quarantine is durable before any transport disposition (DL8–DL11, C76).
- [x] A broker DLQ is never the sole durable record; PostgreSQL is canonical (§23, TD5–TD7).
- [x] Every failure domain preserves terminal-origin identity, with no global bucket (§24, TI2, TI3).
- [x] Replay is explicit, authorised and audited (§28, RA1–RA4).
- [x] Replay preserves the original identity and never mints a new `event_id` (RA7, RA8, A57).
- [x] Replay re-enters normal validation and idempotency (§29, RD1–RD3).
- [x] No force-apply path exists (RD1, A58).
- [x] A crash after the effect and before the acknowledgement cannot duplicate the effect (AM5, C74).
- [x] Ambiguous provider outcomes are resolved by idempotency keys or reconciliation, never blind retry (§27, C75).
- [x] A broker outage cannot lose committed business state (§31, BR1, BR2, C80).
- [x] A single domain's outage does not block the others, and the relay stays fair (§32, C81).
- [x] Per-domain backlog, age, retry, terminal and latency metrics are required (§33, BP2).
- [x] No real event catalogue is invented (RX5).
- [x] Item 10's trace fields remain untouched (§1.2, A59).
- [x] Item 12's `source_version` remains untouched (PJ6, A59).
- [x] ADR-0010 was genuinely required and records four decisions, not the artifact (§1.3).
- [x] No contradiction with ADR-0001…ADR-0009 (§40 row 12).
- [x] No Celery configuration, queue, worker, model, migration, task or dependency created (§1.2).

---

## 39. Explicitly deferred decisions

| Deferred | Owner |
|---|---|
| Trace/correlation/causation envelope field names, message-header trace schema, propagation mechanics | item 10 |
| `Money` / `PublicId` implementation, including the concrete `event_id` type | item 11 |
| `source_version` generation, per-source mapping, guarded projection upsert SQL, the stale-row algorithm | item 12 |
| Whether async analytics exists, and therefore whether an analytics domain is ever added | item 13 |
| Real `event_type` names, payloads and `schema_version` values, and each declared consumer's routing assignment | item 8 + each owning module's phase |
| `CELERY_TASK_ROUTES`, broker settings, exchanges, routing keys, prefetch, acks-late, delayed-scheduling mechanism | Phase 1 |
| Physical queue topology, including whether a logical domain is split per provider or per lane (LY4) | Phase 1 |
| Worker process counts, concurrency, autoscaling policy, and the joint DB connection-pool budget | Phase 1 / operations |
| Retry attempt counts, retry ages, backoff seconds, jitter width, circuit thresholds and probe policy | Phase 1 / operations |
| Quarantine / dead-letter / Outbox / Inbox table schemas, columns, indexes, partitions, retention | Phase 1 (master `# 20.2`, `# 20.3`, `# 20.5`) |
| Circuit-breaker and rate-limiter libraries, and the `integrations/*` `BaseClient` implementation | Phase 1 (master `# 20.8`) |
| Replay tooling, its UI, its permission model and its audit storage | Phase 1 / operations |
| Alert thresholds, SLO values, severity routing, on-call rotation | operations (master `# 23.2`, `# 23.3`) |
| Runbook contents at `docs/runbooks/<alert-name>.md` | operations (master `# 23.3`) |
| Provider idempotency-key formats, reconciliation queries and maib/MIA protocol fields | the payments phase, `integrations/<provider>` |
| ERP payload fields, mappings and the `provider + external_id` schema | `application/erp_sync`, Phase 3 |
| Whether CRM is MVP or later, and therefore whether `ext.crm` is provisioned (its *shape* is frozen either way) | **item 14** (FD9a, NX1) |
| A support/Chatwoot domain; any new domain; merging or removing a frozen domain definition | §12 procedure; an ADR where NX6 applies |

---

## 40. Self-review record

| # | Question | Verdict |
|---|---|---|
| 1 | Is the scope exactly item 9? | Pass — §1.1 lists what is frozen, §1.2 and §39 hand every neighbouring item its territory, and PJ6, §1.2 and A59 hand back items 10 and 12 at the exact points where the temptation arises. |
| 2 | Is there "one Celery queue for everything", or one shared external queue including payments? | Pass — FD7 forbids a general-purpose normal-processing queue by name, PY4 forbids `external` for payments specifically, and QN7 removes `default`/`external`/`integrations`/`misc` from the legal name space. |
| 3 | Is priority used as an isolation mechanism? | Pass — §15 states why it cannot be, PS1 forbids realising any isolation guarantee with it, PS3 refuses to rely on Celery priority semantics for correctness, and PS4 confines it inside one domain. |
| 4 | Does a full rebuild share all capacity with incremental projection? | Pass — PJ1 splits the domains, PJ2 states the decidable rule, PJ4 forbids borrowing capacity, and C72 tests it. PJ5 keeps one writer and one code path so the split adds no consistency model. |
| 5 | Can an ERP retry storm consume payment workers? | Pass — EP4/EP5 forbid it, WC1 reserves `CRITICAL` capacity, WC5 makes the wedged-ERP configuration a stated requirement, and C70/C71 test it. |
| 6 | Does a queue name appear in an event payload, or does routing bump `schema_version`? | Pass — LY2/LY3, RT1, RO2 and RX3 all forbid it; A52 is the static check and V69 the review item. Item 8 EN3/EN7/EN10 are restated, not weakened. |
| 7 | Is a broker DLQ treated as the only source of truth? | Pass — §23 makes PostgreSQL canonical for both terminal states, TD5 gives the concrete loss modes, TD8 avoids demanding a second copy of every payload, and V66 is the review item. |
| 8 | Can a quarantined message be marked HANDLED? | Pass — DL5 restates item 8 QU4/QU15, DL10 keeps transport disposition semantically distinct, and §35 rows 6–8 record "no effect, never". |
| 9 | Are retries bounded everywhere? | Pass — RB1 states it absolutely, RB2 makes bounds + backoff + terminal disposition mandatory per domain, RB5 forbids loosening them per workload, A55 is the static check, and RB4 refuses to invent numbers. |
| 10 | Is an ambiguous provider timeout blindly retried? | Pass — AX1 forbids it, AX2/AX3 give the two admissible resolutions, AX4 puts the outcome in the workflow state machine rather than the queue, and §35 row 3 records "effect may already exist: yes". |
| 11 | Does a replay mint a new `event_id` or bypass validation? | Pass — RA7/RA8 and A57 forbid the first; §29, RD1/RD2 and A58 forbid the second. RA9 separates a genuinely new business attempt from a replay, which is the failure mode that would otherwise smuggle a new `event_id` in under the name "replay". |
| 12 | Contradiction with ADR-0001…0009? | Pass — **0001/0002/0003:** untouched. **0004:** QN5/PY2/PY6 apply §10's "no provider I/O in a durable transaction" as a queue boundary; R3/RT2 keep `tasks/*` as transport that decides *when*; HT6's "local ACID is not a saga" is respected — §27 resolves ambiguity through a workflow state machine, not an orchestrator or compensation framework. **0005:** RT2 leaves wiring with the composition root, AX7/PV7/EP6 leave provider internals with `integrations/*` and the owning application module, and no import edge is added. **0006:** untouched; no `core` primitive or allowlist changes. **0007:** PY2 makes the queue boundary coincide with the placement transaction boundary, and BR2/§35 row 12 keep the business commit independent of the broker. **0008:** PJ5/PJ7/R11 keep one writer, full rebuildability and the ban on a request-time OLTP fallback intact. **0009:** every item 8 rule is inherited (R5–R10), TF-C adds only topology, and RX7 confirms item 9 adds exactly one operational field to each consumer declaration and changes no item 8 rule — KD2's zero/one/many consumers, KD3's single command handler and IX13's per-consumer declaration are all used as written. |
| 13 | Are exact retry numbers, concurrency counts or SLO values invented? | Pass — RB4, WC6, AL4 and §39 push every number to Phase 1 or operations, and V70 makes inventing one a review finding. The only numeric references anywhere are master's own (`# 20.2`'s 500–1000 batch size, cited as the coalescing precedent, not re-frozen). |
| 14 | Does it produce code or configuration? | Pass — no package, module, model, migration, task, queue declaration, broker configuration or dependency. Every code-shaped block is an illustrative text diagram. |
| 15 | Does the matrix invent an event catalogue? | Pass — RX5 forbids it, the matrix names workload categories only, and item 8's registry still ships empty. |
| 16 | Is the payment split justified rather than assumed? | Pass, **after correction**. An earlier draft split "initiation" from "reconciliation", which is wrong because reconciliation itself calls the provider — that split would have put provider I/O inside the domain that must survive a provider outage. §8.2 splits by **I/O nature** instead, which is both the correct answer to the user's starvation test and exactly item 8 HT3/HT4's boundary, so the queue boundary and the transaction boundary coincide by construction (PY2). |
| 17 | Does the terminal-storage-failure case have a safe answer? | Pass, **after correction**. An early reading of DL9 ("remove the delivery after the commit") left the case where the *commit itself* fails undefined, which is the one path that could lose a message. TD11 and §35 row 15 make it explicit: no terminal record, no disposition — the delivery stays on the normal path, work backs up visibly, and the backlog is the secondary signal behind a P1 alert. |
| 18 | Is `BEST_EFFORT` accidentally a licence to lose data? | Pass, **after correction**. The criticality vocabulary read as an importance ladder, which invites exactly that inference. CR5 now states that criticality governs capacity, isolation and alerting only; CR6 forbids inferring business correctness from it; BP5/BP6 forbid dropping durable messages to reduce depth, TTL and max-length policies included; and V72 makes the inference a named review finding. |
| 19 | Is routing attached to the right thing? | Pass, **after correction**. The first draft put **one** `failure domain` field on the `(event_type, schema_version)` row, which is incoherent with item 8 KD2/IX13: an `EVENT` may have several independent consumers, and a notification handler, a CRM handler and a local state handler have nothing in common to route together. §13.1 now attaches the assignment to the **consumer declaration**, beside that consumer's supported versions and effect-idempotency mechanism (RT3); RT4 gives a `COMMAND` its single route and permits an `EVENT`'s consumers to differ; RT5 preserves item 8's zero-consumer allowance unchanged rather than forcing a consumer to exist; RT12 keeps producers out of the decision entirely; A51 checks per consumer rather than per version; and V73 names the whole failure mode. Item 8's cardinality rules are used, not amended (RX7). |
| 20 | Does the terminal/replay model survive a multi-consumer `EVENT`? | Pass, **after correction**, and it is the direct consequence of row 19. If routing is per consumer, then so is failure: §22.3 makes the **consumer delivery** the unit, DL13–DL15 make two consumers of one `event_id` independent rather than duplicates, DL16/DL17 require the terminal record to name the failed handler (the domain alone cannot, since consumers may share one), and RA5a/RA5b/RD4/RD7 scope replay to the failed delivery so a successful sibling is never re-invoked. C83 asserts that by **handler-invocation count**, not effect count, so an idempotent handler cannot mask a rebroadcast; C84 asserts two consumers can legally run in two domains. |
| 21 | Does item 9 decide anyone else's scope? | Pass, **after correction**. §7 and the matrix originally read "the complete frozen set for MVP" and "ten runbook owners at MVP", which asserts that CRM ships at launch — item 14's decision, still `TODO`. §7's preamble now separates a frozen **definition** from a launch **provisioning** decision; FD9a makes `ext.crm` explicitly conditional while keeping its isolation rule binding *if* enabled; FD10 distinguishes it from support and analytics, which have no frozen shape at all because master and ADR-0005 give item 9 nothing to freeze there. The other nine domains are untouched, and item 14 is not pulled forward. |
