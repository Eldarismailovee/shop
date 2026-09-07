# Queue / failure-domain matrix

- **Status:** structure and failure-domain definitions DONE / FROZEN
- **Governing contract:** [Phase 0 item 9](../phase-0/09-queue-failure-domain-dlq.md),
  [ADR-0010](../../adr/0010-async-failure-domain-isolation.md)
- **Related:** [event registry](event-registry.md), [Phase 0 item 8](../phase-0/08-event-registry-versioning.md),
  master `# 20.1`–`# 20.8`, `# 23.2`, `# 23.3`, `# 24.8`

This file is the platform's operational routing policy for asynchronous work: which **logical failure
domains** exist, what may share worker capacity with what, how failures are retried, where a message
goes when it can never succeed, and who may send it back through.

> **This matrix is operational architecture, not semantic contract ownership.** It names no
> `event_type`, defines no payload and confers no ownership. A message's meaning, owner and schema
> live in the [event registry](event-registry.md) and belong to the message's semantic owner
> (item 8 §5). Routing a consumer delivery into a domain gives that domain's operational owner an on-call
> responsibility — never contract authority (item 9 RX5, RX6).

> **Governing objective: failure isolation before throughput optimisation.** A broken, slow or
> hostile integration must not consume worker capacity that unrelated critical work depends on.

---

## 1. The three layers

```text
registered message contract     item 8    what the message MEANS
                                          immutable once published

logical failure domain          item 9    what it may FAIL TOGETHER WITH
                                          this file — operational, mutable, audited

physical broker queue           Phase 1   HOW it is carried
                                          free to change for throughput
```

A routing change is an **operational** change: it never bumps `schema_version`, never creates a new
`event_type` and never requires a consumer to redeclare support (item 9 LY3, RT6, RT11).

Queue identity never appears in an `event_type`, in the item 8 envelope, or in a payload
(item 8 EN3, NM4; item 9 LY2, A52).

**The assignment is per consumer, not per message version.** A failure domain describes a *handler's*
work and dependencies, so it attaches to a consumer declaration — beside that consumer's supported
versions and its effect-idempotency mechanism (item 8 IX13; item 9 RT3, LY7):

```text
one EVENT instance E, one event_id

  consumer A  → notification handler  → ext.email
  consumer B  → CRM handler           → ext.crm
  consumer C  → local state handler   → core.<domain>
```

A `COMMAND` has exactly one handler and therefore exactly one assignment (item 8 KD3; item 9 RT4). An
`EVENT` with no declared consumers needs no assignment at all — item 8 KD2's zero-consumer allowance is
unchanged; a consumer added later must receive one before it may take production deliveries (item 9
RT5, RT8). A producer never selects a failure domain for anyone (item 9 RT12).

---

## 2. The sharing rule

> **Messages share a normal-processing queue only when it is acceptable for one workload's latency,
> provider outage, poison-message rate and retry storm to consume the other's worker capacity.**

Never sufficient as a reason to share: same broker; all Celery tasks; all from the Outbox; low volume
today; code lives nearby; same module; same criticality label (item 9 FD2).

A general-purpose `external`, `integrations`, `default` or `misc` normal-processing queue is
**forbidden** (item 9 FD7). `core.high` and `core.low` are not failure-domain names (item 9 QN7,
§1.4).

---

## 3. Criticality classes

| Class | Meaning | Capacity | Alerting |
|---|---|---|---|
| `CRITICAL` | Correctness-critical convergence of committed commercial state. | **Reserved** capacity no other domain can consume. | Tightest backlog-age thresholds; a stall is P1. |
| `IMPORTANT` | Normal commerce depends on convergence within an SLO; delay degrades experience, not correctness. | Reserved where the SLO requires it. | Sustained stall is P2. |
| `BEST_EFFORT` | May lag substantially without commercial harm. | Non-zero floor, bounded ceiling. | Sustained backlog and terminal-failure growth only. |

**Criticality governs capacity, isolation and alerting. It never governs durability, contract strength
or whether data may be lost.** A `BEST_EFFORT` message is still registered, versioned, validated,
durable, identity-checked, and still ends in a durable terminal record when it fails (item 9 CR5,
CR6, V72).

---

## 4. Naming

`core.<domain>` — no external vendor dependency. The prefix asserts a checkable property: **no work
routed to a `core.*` domain performs external provider I/O** (item 9 QN5, A54).

`ext.<provider-domain>` — provider-backed; inherits that provider's availability.

`<failure-domain>.dlq` — terminal namespace, generalising master `# 20.1`'s `ext.<vendor>.dlq` to
every domain (item 9 TI1).

A logical name never contains an environment, a schema version, a Python module/class name, a
broker/exchange/routing-key word, or a criticality word (item 9 QN3).

---

## 5. The matrix

Ten logical failure-domain **definitions**. This is the complete frozen set for the architecture as
currently known; adding one follows §9.

> **A frozen definition is not a launch commitment.** Each definition freezes a domain's name, class,
> isolation rule, retry class, terminal namespace and capacity relationship. **Which definitions are
> provisioned** — given a physical queue, workers, a terminal namespace and an on-call owner —
> follows from which workloads are actually enabled. `ext.crm` is explicitly **conditional** (§5.10),
> and the MVP/later cut per module is **item 14's** decision, not item 9's (item 9 FD9, FD9a).

> **Eligibility is about the consumer handler, not the producer.** A domain's *eligible handler /
> consumer owner* row says whose **handler** may run in that pool. A producer emits a fact and has no
> say in where it is handled; one `EVENT` may fan out to consumers in several domains, and an
> inventory-owned fact consumed by a payments handler does **not** put `domains/inventory` in
> `core.payments` (item 9 RT4, RT12).

### 5.1 `core.payments` — CRITICAL

| Field | Value |
|---|---|
| Purpose | Local durable payment-state convergence: applying durably ingested provider events (master `# 12.2` Inbox worker) and reconciliation findings to the payment state machine under row locks; inventory commit/release; resulting Outbox rows. |
| Accepted kinds | `EVENT`, `COMMAND` |
| Eligible handler / consumer owner | Consumers owned by `application/payments_gateway` that apply payment state locally. A fact **produced** by `domains/orders` or `domains/inventory` may be consumed here; that never means its producer runs in this pool (item 9 RT12). |
| Provider outage can block it | **No — and must not.** Applying an already-ingested authorisation requires no provider call. A realisation in which a provider outage stalls it is non-conformant (item 9 PY3, C70). |
| External I/O | **None.** If a provider call is needed, the intent is emitted and `ext.payments` performs it post-commit (item 9 PY6). |
| Dedicated capacity | **Yes — reserved.** |
| Concurrency relationship | Independent of every other domain; its reservation is never lent out. |
| Retry class | TF-A bounded retry; TF-D tightly bounded then terminal. |
| Terminal destination | `core.payments.dlq` namespace; canonical record in PostgreSQL. |
| Replay authority | Payments operational owner; financial-contour audit required. |
| Runbook owner | Payments / financial contour. |
| **Must not share its worker pool with** | `ext.payments`, `ext.erp`, `ext.crm`, `ext.email`, `ext.sms`, `core.projection.*`, `core.maintenance` — i.e. everything. |

### 5.2 `ext.payments` — CRITICAL, provider-backed

| Field | Value |
|---|---|
| Purpose | Provider-facing payment I/O: initiation, capture, refund, status query / reconciliation polling, through `application/payments_gateway`'s port. |
| Accepted kinds | `COMMAND` primarily; `EVENT` where a fact triggers provider work. |
| Eligible handler / consumer owner | Consumers owned by `application/payments_gateway` that perform provider-facing payment calls through its port. |
| Provider outage can block it | **Yes, by design** — that is what isolating it buys. |
| Dedicated capacity | **Yes — reserved**, with a **per-provider** concurrency, rate-limit and circuit budget inside it, so one provider's outage cannot exhaust another's share (item 9 PY5, PV2). |
| Concurrency relationship | Independent of every other domain. May be split into per-provider physical queues in Phase 1 without any contract change (item 9 LY4). |
| Retry class | TF-A bounded retry with jitter, `Retry-After` clamped to the domain's bounds; circuit fail-fast is TF-A, never a drop (item 9 PV4). Ambiguous outcomes follow item 9 §27 — **never blindly retried**. |
| Terminal destination | `ext.payments.dlq` namespace; canonical record in PostgreSQL. |
| Replay authority | Payments operational owner; replay of a provider mutation requires the §27 ambiguity resolution first. |
| Runbook owner | Payments / financial contour. |
| **Must not share its worker pool with** | Every other domain, `core.payments` included. |

### 5.3 `core.inventory` — CRITICAL

| Field | Value |
|---|---|
| Purpose | Reservation expiry and inventory state transitions (master `# 9.2`; expiry backlog is an alerted condition within minutes). |
| Accepted kinds | `EVENT`, `COMMAND` |
| Eligible handler / consumer owner | Consumers that apply inventory state transitions and reservation expiry. Facts produced by `application/checkout` may be consumed here; the producer does not thereby run in this pool. |
| Provider outage can block it | **No.** No external dependency. |
| External I/O | **None.** ERP reconciliation of balances is `ext.erp` work; the site's own `reserved` is never overwritten by an ERP value (master `# 9.3`). |
| Dedicated capacity | **Yes — reserved.** |
| Concurrency relationship | Independent. Notably separate from `core.payments`: an expiry backlog must not delay money-state convergence, and vice versa (item 9 §1.4, PY4). |
| Retry class | TF-A bounded; TF-D tightly bounded then terminal. |
| Terminal destination | `core.inventory.dlq` namespace; canonical record in PostgreSQL. |
| Replay authority | Inventory operational owner. |
| Runbook owner | Inventory / fulfilment. |
| **Must not share its worker pool with** | Every `ext.*` domain, `core.projection.*`, `core.maintenance`. |

### 5.4 `core.projection.incremental` — IMPORTANT

| Field | Value |
|---|---|
| Purpose | Incremental, coalesced `ProductListingProjection` updates owned by `application/storefront` (item 6). Latency-sensitive: bound by a freshness SLO and alerted as *Listing Projection Lag* (master `# 23.2`). |
| Accepted kinds | `COMMAND` primarily (bounded batch work items); `EVENT` where a fact drives an update. |
| Eligible handler / consumer owner | Consumers owned by `application/storefront`, the single projection writer (item 6, ADR-0008). Any owner's fact may be consumed here; only storefront's handler runs here. |
| Provider outage can block it | **No.** |
| Dedicated capacity | **Yes — reserved**, because its SLO is alerted and a lagging projection has **no** request-time OLTP fallback (item 6, item 9 R11, PJ7). |
| Concurrency relationship | Independent of `core.projection.rebuild`; a rebuild backlog may never delay it beyond its SLO (item 9 PJ2, C72). |
| Retry class | TF-A bounded; TF-D tightly bounded then terminal. |
| Terminal destination | `core.projection.incremental.dlq` namespace; canonical record in PostgreSQL. |
| Replay authority | Storefront operational owner. Reconciliation and targeted rebuild are the normal repair path; replay is for individual terminal records. |
| Runbook owner | Storefront. |
| **Must not share its worker pool with** | `core.projection.rebuild`, every `ext.*` domain, `core.maintenance`. |

### 5.5 `core.projection.rebuild` — IMPORTANT (throughput-shaped)

| Field | Value |
|---|---|
| Purpose | Full and targeted `ProductListingProjection` rebuild batches and periodic reconciliation (item 6 RB1/RB2). |
| Accepted kinds | `COMMAND` |
| Eligible handler / consumer owner | Rebuild consumers owned by `application/storefront` only. |
| Provider outage can block it | **No.** |
| Dedicated capacity | **Yes — its own bounded capacity**, which it may not exceed and may not borrow from the incremental domain. |
| Concurrency relationship | Bounded, resumable, interleavable batches (500–1000 rows per iteration is master `# 20.2`'s precedent, not a frozen number). A rebuild never runs as one long-held unit of work (item 9 PJ3, PJ4). |
| Retry class | TF-A bounded per batch; each batch independently idempotent. |
| Terminal destination | `core.projection.rebuild.dlq` namespace; canonical record in PostgreSQL. |
| Replay authority | Storefront operational owner. |
| Runbook owner | Storefront. |
| **Must not share its worker pool with** | `core.projection.incremental` — this separation is the whole reason the domain exists — and every other domain. |

### 5.6 `core.maintenance` — BEST_EFFORT

| Field | Value |
|---|---|
| Purpose | Internal housekeeping with no external dependency and no commercial-correctness role: cache re-warm, sitemap generation, retention/partition lifecycle, aggregate recomputation. Exists so "everything else" has an explicit home and never lands in a critical domain by default. |
| Accepted kinds | `COMMAND` primarily. |
| Eligible handler / consumer owner | Any consumer whose handler genuinely has no correctness role and no external dependency. |
| Provider outage can block it | **No.** |
| Dedicated capacity | No reservation beyond a non-zero floor; bounded ceiling. |
| Concurrency relationship | Yields to every `CRITICAL` and `IMPORTANT` domain under contention (item 9 BP4). |
| Retry class | TF-A bounded; TF-D tightly bounded then terminal. |
| Terminal destination | `core.maintenance.dlq` namespace; canonical record in PostgreSQL. |
| Replay authority | Platform operational owner. |
| Runbook owner | Platform / operations. |
| **Must not share its worker pool with** | Any `CRITICAL` or `IMPORTANT` domain. It is never a fallback home for work that failed to get its own domain (item 9 NX4). |

### 5.7 `ext.erp` — IMPORTANT, provider-backed

| Field | Value |
|---|---|
| Purpose | 1C imports, exports and sync batches (master `# 9.3`, `# 20.1`). |
| Accepted kinds | `EVENT`, `COMMAND` |
| Eligible handler / consumer owner | Consumers owned by `application/erp_sync` only. |
| Provider outage can block it | **Yes, by design.** Master's six-hour ERP outage must affect nothing else. |
| Dedicated capacity | **Yes — bounded and reserved *to* it**, which also bounds what it can take from others. |
| Concurrency relationship | Independent. Batches are bounded, set-based, resumable and idempotent; an import never fans out into per-row tasks (item 9 EP2, EP3). |
| Retry class | TF-A bounded with jitter, provider rate limits and a circuit; TF-B permanent rejections per the workload's declaration. |
| Terminal destination | `ext.erp.dlq` namespace (master `# 20.1`); canonical record in PostgreSQL. |
| Replay authority | ERP operational owner; replay of a non-idempotent ERP mutation follows item 9 §27. |
| Runbook owner | ERP / integrations. |
| **Must not share its worker pool with** | Every other domain. One malformed ERP batch stops ERP work only (item 9 EP5, C71). |

### 5.8 `ext.email` — BEST_EFFORT, provider-backed

| Field | Value |
|---|---|
| Purpose | Outbound transactional and lifecycle email (master `# 20.1`). |
| Accepted kinds | `COMMAND` primarily. |
| Eligible handler / consumer owner | Notification-sending consumers owned by the application module that owns each notification workflow, through its port. A fact produced anywhere may have such a consumer. |
| Provider outage can block it | **Yes, by design.** |
| Dedicated capacity | Non-zero floor, bounded ceiling. |
| Concurrency relationship | Independent of `ext.sms`: a bulk email backlog must not delay an SMS (item 9 NT1). |
| Retry class | TF-A bounded with jitter and provider rate limits; a permanently invalid recipient is **TF-B**, never a schema quarantine (item 9 NT3). |
| Terminal destination | `ext.email.dlq` namespace (master `# 20.1`); canonical record in PostgreSQL. |
| Replay authority | Notifications operational owner. |
| Runbook owner | Notifications / integrations. |
| **Must not share its worker pool with** | Every `CRITICAL` and `IMPORTANT` domain, and `ext.sms`. |

### 5.9 `ext.sms` — BEST_EFFORT, provider-backed

| Field | Value |
|---|---|
| Purpose | Outbound SMS (master `# 20.1`). |
| Accepted kinds | `COMMAND` primarily. |
| Eligible handler / consumer owner | Notification-sending consumers owned by the application module that owns each notification workflow, through its port. A fact produced anywhere may have such a consumer. |
| Provider outage can block it | **Yes, by design.** |
| Dedicated capacity | Non-zero floor, bounded ceiling. |
| Concurrency relationship | Independent of `ext.email` — different provider, different rate limits, different cost and different outage profile. |
| Retry class | As `ext.email`. |
| Terminal destination | `ext.sms.dlq` namespace (master `# 20.1`); canonical record in PostgreSQL. |
| Replay authority | Notifications operational owner. |
| Runbook owner | Notifications / integrations. |
| **Must not share its worker pool with** | Every `CRITICAL` and `IMPORTANT` domain, and `ext.email`. |
| Note | **SMS is not made `CRITICAL` pre-emptively.** If a future security flow depends on SMS latency for correctness, *that flow's* messages get their own domain and class, with an ADR — not a re-labelling of all SMS (item 9 NT4). |

### 5.10 `ext.crm` — BEST_EFFORT, provider-backed, **conditional / not provisioned**

| Field | Value |
|---|---|
| Purpose | CRM synchronisation (master `# 20.1`). |
| Status | **Conditional reserved definition.** Name, class and isolation rule are frozen **if and when CRM is enabled**; the domain is **not provisioned until the CRM integration is enabled by the product/MVP roadmap**. **Whether CRM is MVP or later is item 14's decision** — item 9 takes no position and asserts no launch scope (item 9 FD9a, NX1). The definition is not deleted meanwhile; removing or merging it still follows §9, which is a separate question from whether the feature is enabled. |
| Accepted kinds | `EVENT`, `COMMAND` |
| Eligible handler / consumer owner | CRM-sync consumers owned by the application module that owns CRM sync, through its port. |
| Provider outage can block it | **Yes, by design.** |
| Dedicated capacity | Non-zero floor, bounded ceiling, once provisioned. |
| Concurrency relationship | Independent. |
| Retry class | TF-A bounded with jitter and provider rate limits; TF-B per the workload's declaration. |
| Terminal destination | `ext.crm.dlq` namespace (master `# 20.1`); canonical record in PostgreSQL. |
| Replay authority | CRM operational owner. |
| Runbook owner | CRM / integrations. |
| **Must not share its worker pool with** | Every `CRITICAL` and `IMPORTANT` domain. |

### 5.11 Deliberately **not** reserved

| Not reserved | Why |
|---|---|
| A support / Chatwoot domain | No frozen shape at all, conditional or otherwise. If it ships it gets its own `BEST_EFFORT` domain (`ext.support`) rather than sharing `ext.crm`, unless the two satisfy §2 with independently enforced per-provider rate limits (item 9 NX2). |
| An analytics domain | Whether asynchronous analytics exists at all is **item 13's** decision. A queue named now for undecided work is an operational surface with no owner and no runbook (item 9 NX3, master `# 23.3`). |
| A `search` / OpenSearch domain | OpenSearch is deferred by the master's own MVP scope; PostgreSQL is the MVP search engine (item 6). |

### 5.12 The Outbox relay

The relay is **not** a consumer failure domain. It is a producer-side transport component with its own
capacity, never sized or scheduled out of a consumer domain's budget (item 9 FD11), and it must stay
**fair across domains**: a persistently failing route is skipped or deferred with its own backoff
while other routes continue (item 9 QO3, QO4, C81).

---

## 6. Isolation summary

| | `core.payments` | `ext.payments` | `core.inventory` | `proj.incr` | `proj.rebuild` | `core.maint` | `ext.erp` | `ext.email` | `ext.sms` | `ext.crm` |
|---|---|---|---|---|---|---|---|---|---|---|
| Class | CRITICAL | CRITICAL | CRITICAL | IMPORTANT | IMPORTANT | BEST_EFFORT | IMPORTANT | BEST_EFFORT | BEST_EFFORT | BEST_EFFORT |
| Provider-backed | no | **yes** | no | no | no | no | **yes** | **yes** | **yes** | **yes** |
| Reserved capacity | **yes** | **yes** | **yes** | **yes** | own bounded | floor only | bounded, reserved | floor only | floor only | floor only |
| Provisioning | on enablement of its workloads | " | " | " | " | " | " | " | " | **conditional — item 14** (§5.10) |
| May share a worker pool with | none | none | none | none | none | none | none | none | none | none |

**No two logical failure domains share a worker pool.** That is the frozen position, and merging two
of them is not a Phase 1 tuning decision — it requires an ADR (item 9 LY5, NX6). It binds each domain
whenever it is provisioned; a definition that is not yet enabled imposes no worker pool, no terminal
queue and no on-call burden.

**Priority is not isolation.** No isolation guarantee in this matrix may be realised by message
priority inside one shared pool (item 9 §15). Priority is admissible only *inside* one domain.

---

## 7. Retry and terminal-state policy

### 7.1 Failure taxonomy

| Class | What it is | Retry on normal queue | Terminal destination |
|---|---|---|---|
| **TF-A** transient technical | Provider timeout, temporary 5xx, connection reset, retryable rate limit, transient DB/network fault, lock timeout. | Yes, bounded backoff with jitter. | Operational dead-letter on exhaustion. |
| **TF-B** permanent workload rejection | Provider permanently rejects a valid request; recipient permanently invalid; external entity gone. | **No.** | Terminal domain state and/or ODL, per the workload's declaration. **Never a schema quarantine.** |
| **TF-C** contract / identity | Unknown `event_type`, unsupported `schema_version`, invalid payload, same `event_id` with conflicting content. | **No.** | **Quarantine** + alert (item 8 §20). |
| **TF-D** programmer / invariant | Impossible branch, unexpected exception, violated assumption. | Yes, tightly bounded. | Operational dead-letter, **high severity**. Never disguised as a provider failure. |

### 7.2 Bounds

Every domain declares a **finite** attempt bound and/or retry-age bound, a backoff policy, and an
explicit terminal disposition. **No message retries forever on its normal queue** (item 9 RB1, A55).

Backoff is increasing and capped, with **mandatory jitter** on every provider-backed domain. A
provider `Retry-After` may inform scheduling, clamped to the domain's bounds. Immediate tight loops
are forbidden, and a waiting retry must not occupy a worker slot where delayed scheduling exists
(item 9 §20).

**Exact attempt counts, ages, seconds, jitter widths and circuit thresholds are Phase 1 / operations.**
Master freezes none, and this matrix invents none (item 9 RB4, V70).

### 7.3 Quarantine vs operational dead-letter

```text
QUARANTINE                              OPERATIONAL DEAD-LETTER
"we cannot understand this message"     "we understood it; execution failed"
TF-C                                    TF-A exhausted, TF-B (ii)/(iii), TF-D
never any business effect               an effect may partially or fully exist upstream
fix: producer / deploy order / schema   fix: provider / data / code / manual completion
```

**Neither is ever called simply "failed"** — not in a table, a metric, a log line, an alert, an admin
screen or a runbook (item 9 DL2, V65). Phase 1 may map both onto one physical mechanism, but never
onto one semantic state; a shared structure carries an explicit terminal-kind discriminator, and every
query, metric, alert and replay path distinguishes them (item 9 DL3, DL4).

### 7.4 Terminal-state durable truth

> **PostgreSQL is the canonical durable truth for both terminal states. A broker DLQ is transport —
> a parking place and an operational reference — never the sole durable record.**

A broker DLQ can be lost to a restart with non-durable configuration, a topology change, a queue
redeclaration, a purge, a TTL or a broker migration. None of those may lose a payment reconciliation
that needs manual completion (item 9 §23, TD5).

The payload need not be stored twice where the original Outbox/Inbox row still retains it within its
retention window; the requirement is **sufficiency for replay and diagnosis**, not duplication
(item 9 TD8).

Ordering at the transport boundary is fixed:

```text
validate → persist the durable terminal record → COMMIT
         → only then remove the delivery from the normal processing path
```

Never dispose before the commit; never leave a permanently failing message hot-looping after it
(item 9 DL8–DL11). If terminal storage is unavailable, the delivery is **not** disposed of — work
backs up visibly rather than disappearing quietly, and that is a P1 (item 9 TD11).

### 7.5 Terminal-origin identity, and the unit of failure

Each domain has its own terminal namespace, `<failure-domain>.dlq`, generalising master `# 20.1`'s
`ext.<vendor>.dlq` to internal domains too. **One global undifferentiated `dead_letters` bucket is
forbidden** (item 9 TI2, A56). The origin domain and terminal kind are part of the durable record, not
only of the queue it landed on. A global operational view may aggregate for triage; storage and
routing identity always preserve origin (item 9 TI3, TI4).

**The unit of failure is a consumer delivery, not a message** (item 9 §22.3):

```text
EVENT E, one event_id

  consumer A → handled, effect committed
  consumer B → retries exhausted → operational dead-letter
  consumer C → still retrying
```

- Two consumers processing the same `event_id` are **two independent consumer deliveries**, never
  duplicate effects of one handler, and each keeps its own Inbox/identity/effect state (item 8 IX2 is
  already per consumer; item 9 DL13, DL14).
- **One consumer may succeed while another dead-letters or quarantines.** That is normal for a
  multi-consumer `EVENT`, not an incident (item 9 DL15).
- **A terminal record must identify which registered consumer/handler failed** (item 9 DL16). The
  failure domain alone is insufficient, because several consumers may legitimately share one domain
  (item 9 DL17, LY6).

No key, column or index is designed here; Phase 1 owns the structure (item 9 DL18, TD9).

---

## 8. Replay

Replay is **explicit, authorised, audited, idempotent** and never automatic — not on a deployment, a
restart, a circuit closing, a provider recovering or a backlog draining (item 9 §28).

It preserves the original `event_id`, `event_type`, `schema_version`, `occurred_at` and payload
byte-for-byte. **A replay never mints a new `event_id`** (item 9 RA7, RA8, A57).

A **new business attempt** is a different operation: its owner emits a **new** message with a **new**
`event_id` through the normal Outbox path. Replay re-delivers a fact; a new attempt creates one
(item 9 RA9).

**Replay is scoped to the failed consumer delivery**, never to the message (item 9 RA5a). A replayed
delivery re-enters at the **normal validation and handler boundary** of the domain **that consumer** is
currently assigned to, and reaches **only that consumer**:

```text
quarantine replay  → B's current failure domain → registry lookup → schema validation
(consumer B)       → B's identity-integrity check → B's handler

ODL replay         → B's current failure domain → normal handler transport boundary
(consumer B)       → B's identity-integrity check → B's effect idempotency → B's handler

consumers A and C are not invoked.
```

**A replay never rebroadcasts the message to the other consumers of the same `EVENT`.** A consumer
that already succeeded is never re-executed because a sibling is being replayed (item 9 RA5b, RD4,
C83) — relying on the sibling's effect idempotency to absorb a stray re-delivery is not a design. A
replay tool whose smallest addressable unit is the message is **not conformant**; bulk replay is an
explicitly selected set of consumer deliveries (item 9 RD7).

**There is no force-apply path** (item 9 RD1, A58). A still-invalid replay returns to quarantine and
is never coerced (RD2). A replay of an already-completed consumer delivery produces no second effect
(RD3). Bulk replay is rate-limited into the target domain so that recovering from an incident does not
create a second one (RA10).

A `RETIRED` `schema_version` has proved it has no legitimate replay requirement: a normal replay of one
is **not supported** and arrives as an unknown version — quarantine plus an alert saying the retirement
proof was wrong. Forensic decoding of an archived message stays possible; reading it is not executing
it (item 9 §30). A `DEPRECATED` version is fully replayable and remains a live consumer obligation.

---

## 9. Adding, changing or removing a domain

**Adding** a logical failure domain requires: a row here with every cell filled; a named operational
owner and a runbook path; a criticality with its justification; a retry class; a terminal namespace; a
declared capacity relationship to every existing domain; and an update to item 9 §7's set. No ADR is
needed unless the addition changes an isolation guarantee item 9 freezes (item 9 NX5).

**Removing or merging** a frozen domain **requires an ADR**: each frozen domain is an isolation
guarantee the others were sized against (item 9 NX6, LY5).

**Splitting** one logical domain into several physical queues for throughput is a Phase 1 decision and
needs no change here, provided the split does not weaken the domain's isolation guarantee and the
domain keeps one terminal namespace and one replay authority (item 9 LY4).

**Changing a consumer's domain assignment** is operational: no `schema_version` bump, no new
`event_type`, no re-declaration of supported versions, no change to the effect-idempotency mechanism.
It may need a rollout order and a runbook — drain the old route or accept dual consumption during the
window — recorded in the registry entry's notes. Moving one consumer never affects another consumer of
the same message (item 9 RT6, RT11).

**Enabling or not enabling a workload** is a product/roadmap decision, not this file's. A definition
that is not yet enabled stays here, unprovisioned, and creates no worker pool, terminal queue or
on-call burden (item 9 FD9, FD9a).

---

## 10. Required per-domain observability

Per **failure domain**, not platform-wide — a platform-wide aggregate hides exactly the isolation
failure these metrics exist to catch (item 9 BP2):

- ready depth;
- oldest-message age;
- retry rate;
- terminal-failure rate, **split by terminal kind** (quarantine vs ODL) **and by failed consumer** —
  the domain alone does not identify the handler when several consumers share it (item 9 DL16, DL17);
- quarantine count;
- processing latency.

Backlog is an operational signal, not an error. Backpressure favours preserving critical-domain
progress over draining best-effort backlog, and **durable messages are never dropped to reduce queue
depth** — not by TTL, not by a max-length policy, not by a purge (item 9 BP4–BP6).

Metric names, labels, exporters, dashboards and thresholds belong to observability (master `# 23.1`,
`# 23.2`). Every alert carries a `runbook_url` and an explicit owner; a domain without a runbook owner
is not a valid domain (master `# 23.3`; item 9 AL3).

Alert severity classes are frozen in item 9 §34. **Alert on sustained or terminal conditions, never on
every retry**, and deduplicate repeated recognition of an already-terminal message (item 9 AL1, AL2).

---

## 11. What this matrix does not decide

| Not decided | Owner |
|---|---|
| Physical queues, exchanges, routing keys, `CELERY_TASK_ROUTES`, prefetch, acks-late, delayed-scheduling mechanism | Phase 1 |
| Worker process counts, concurrency, autoscaling, the joint DB connection-pool budget | Phase 1 / operations |
| Retry attempt counts, retry ages, backoff seconds, jitter widths, circuit thresholds | Phase 1 / operations |
| Quarantine / dead-letter / Outbox / Inbox schemas, columns, indexes, partitions, retention | Phase 1 |
| Circuit-breaker and rate-limiter libraries, `integrations/*` `BaseClient` | Phase 1 |
| Replay tooling, its UI, permission model and audit storage | Phase 1 / operations |
| Alert thresholds, SLO numbers, severity routing, on-call rotation, runbook contents | operations |
| Trace / correlation / causation fields and their propagation | **item 10** |
| `source_version` generation and the guarded projection upsert | **item 12** |
| Whether async analytics exists | **item 13** |
| The MVP / later cut per module — including whether CRM ships at launch and `ext.crm` is ever provisioned | **item 14** |
| Every real `event_type`, its payload and its schema version | **item 8** + each owning module's phase |
