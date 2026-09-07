# ADR-0011 — The asynchronous trace/causality envelope: four closed fields, durable in the Outbox, immutable through replay

- **Status:** Accepted — Frozen
- **Date:** 2026-09-05
- **Phase:** 0 — Architecture Freeze (item 10)
- **Supersedes:** —
- **Related:** [ADR-0004](0004-four-layer-modular-monolith.md), [ADR-0005](0005-dependency-and-integration-wiring.md),
  [ADR-0006](0006-public-contract-primitives.md), [ADR-0007](0007-place-order-atomic-idempotent-boundary.md),
  [ADR-0009](0009-event-contract-versioning.md), [ADR-0010](0010-async-failure-domain-isolation.md),
  [Phase 0 item 10](../architecture/phase-0/10-async-trace-propagation.md),
  [Phase 0 item 8](../architecture/phase-0/08-event-registry-versioning.md),
  [Phase 0 item 9](../architecture/phase-0/09-queue-failure-domain-dlq.md),
  master `# 20.2`, `# 20.3`, `# 20.6`, `# 20.7`, `# 23.1`, `# 23.3`

## Context

ADR-0009 froze the semantic envelope of an asynchronous message as exactly four fields —
`event_id`, `event_type`, `schema_version`, `occurred_at` — plus **one reserved extension point**
for the trace and causality fields a later item would own. It named no field, took no position on
which exist, and forbade the extension point from becoming a metadata bag. ADR-0010 froze transport,
terminal states and replay, and deliberately left the same territory alone.

The Outbox breaks the request context. A durable message may be relayed minutes or months after the
process that produced it has exited, delivered to several consumers independently, retried across
deployments, and replayed by an operator long after the originating trace has fallen out of the
tracing backend's retention. Master `# 20.2` and `# 20.6` list `trace_id`, `span_id`, `request_id`
on the durable row; `# 20.7` describes capture at INSERT and W3C propagation through the relay;
`# 23.3` calls loss of trace continuity on the asynchronous boundary an observability defect. That
sketch leaves four questions unanswered, and each can be got wrong in a way that no test catches:

1. **What, exactly, is that span?** A column named `span_id` on a row written by a producer, read by
   a relay, read by N consumers and re-read by a replay tool answers "whose span?" differently to
   each reader. The predictable outcome is that some path eventually writes the *consumer's* span
   into it, the fan-out picture collapses to whichever consumer wrote last, and nothing fails.
2. **What holds the causal chain together once the trace is gone?** Traces are sampled and
   short-lived. Reconstructing *request → placement → message → reaction → messages emitted by that
   reaction* weeks later must be possible from PostgreSQL alone.
3. **Where does the truth live?** Broker headers are the convenient carrier and the wrong answer:
   they vanish on acknowledgement, on a purge, or when the broker is replaced — which is precisely
   when a terminal record most needs to be diagnosable.
4. **What does a replay look like in a trace?** A replay preserves the original message identity
   (ADR-0010) but happens *now*. Rewriting the message's trace fields destroys the lineage the
   fields exist for; parenting the replay into the original trace claims the work happened during a
   request that ended months ago.

The item is scheduled **before** the Outbox/Inbox partition migrations for a mechanical reason:
adding a column to a partitioned, high-volume, actively-retained table afterwards is expensive, and
every row already written stays permanently blind.

## Decision

### 1. The reserved extension point is filled by a closed set of exactly four fields

The **trace/causality envelope extension (TCE)** is:

| Field | Meaning |
|---|---|
| `trace_id` | The distributed trace containing **this message's production** — the trace active when the durable Outbox record was written. W3C trace-id value space. |
| `producer_span_id` | The span active in the producing process **at the instant the durable record was written**. The producer's own span; never a parent of it, never a consumer's. W3C span-id value space; occupies the `parent-id` position of an outbound `traceparent`. |
| `request_id` | The **originating synchronous request** of the causal chain, where one exists. Inherited transitively and unchanged by every descendant message; **absent** for system origin (schedules, reconciliation, rebuilds). Opaque, bounded, observability-only. |
| `causation_event_id` | The **`event_id` of the immediate parent message** — the one whose handling emitted this message. One hop. Absent when emitted from a request or a system job. Same semantic type as `event_id`; its concrete representation is item 11's. |

Every field is **optional by construction** and **write-once at message creation**. `trace_id` and
`producer_span_id` form a pair: both present or both absent; exactly one present is a recorded
integrity defect that never blocks processing. Malformed, wrong-length and all-zero identifiers are
normalised to absent at capture and never stored. `causation_event_id` never equals the message's
own `event_id`, and a dangling reference to an archived parent is expected, never a validation
failure and never a foreign key.

This is ADR-0009 EN6's **single** reserved extension point, now spent. There is no second one, and
ADR-0009 EN7 stands: a field that is not one of the envelope's four and not one of these four does
not exist.

**Rejected by name:**

- a generic **`correlation_id`** — every precise meaning it could carry is already carried by
  `request_id`, `causation_event_id`, `trace_id` or `event_id`, and a genuine *business* correlation
  identifier belongs to the owning module's contract or durable state, not to universal observability
  metadata. What remains is a one-entry metadata bag;
- a **metadata bag** in any disguise: `meta`, `extra`, `context`, `attributes`, `headers`, `tags`,
  `dict[str, Any]`, "one JSON column for future use";
- persisted **OpenTelemetry baggage** and **W3C `tracestate`** — unbounded upstream key/value data
  and unowned vendor state, both durable leak channels by construction;
- an **ancestry list / causal path** — unbounded, mutated at every hop, and read as a sequence, which
  is exactly the ordering inference causation must never support;
- any **queue, failure domain, attempt, retry or worker** field: routing is per-consumer transport
  metadata (ADR-0010) and does not travel in the envelope.

Changing this set requires a new ADR superseding this one. Because every field is absence-tolerant,
**no envelope version field is introduced**.

### 2. Master's `span_id` is renamed to `producer_span_id`, and durable causation is added

The value, the capture point and the wire position of master `# 20.2`/`# 20.6`/`# 20.7`'s `span_id`
are preserved exactly. Only the **name** changes, to one that is absolute rather than
reader-relative, so that no future writer can reasonably put a consumer's span in it.
`parent_span_id` was rejected for the same reason in mirror image: "parent" is relative to whoever
reads the row.

`causation_event_id` is **added**, and the master names no equivalent. It exists because trace data
is sampled and short-lived while the causal chain of durable commercial facts must be reconstructable
from PostgreSQL weeks later, after a replay, from a terminal record, with the tracing backend
contributing nothing.

`trace_id` and `request_id` keep the master's names and gain exact semantics. Both are kept
deliberately: they are not substitutes. A trace is legitimately *discontinuous* across a replay or a
months-later relay; `request_id` survives every such discontinuity and is already required on every
structured log line by master `# 23.1`.

### 3. The durable Outbox record is the source of truth; transport headers are a copy

The TCE is captured **at the instant the durable record is written**, inside the **same** business
transaction, into the **same** record as the payload and the envelope, from ambient in-process
context — with **no network I/O of any kind**, no collector, no exporter flush, no remote sampler
lookup. A failure to capture context never fails the business transaction; the fields are simply
absent.

The durable record alone must suffice to restore asynchronous trace context after a process restart,
a delayed relay, a broker outage, a retry, a deployment, and a relay running in another process or
release. **The relay must never require the originating HTTP process to still exist.** The relay
reads the durable row and copies the values into a standards-compatible carrier (W3C `traceparent`
plus a `request_id` entry); it never writes back into the message row. When a carrier and the durable
record disagree, **the durable record wins**, the discrepancy is an observability defect, and the
message is processed normally.

A consumer creates a **new processing span per consumer delivery**, child of the message's
production context, and the message's four fields stay immutable at the consumer. The consumer's own
identifiers — processing span, attempt, worker — live in the delivery's **separate** operational
trace context, never in the message's TCE. The consumer-delivery/Inbox record retains the message's
four values verbatim so that later diagnosis does not depend on broker data, and quarantine and
operational-dead-letter records retain or durably reference the same, extending ADR-0010's
sufficiency requirement.

The TCE is **populated by the envelope mechanism**, which ADR-0009 already placed in `core.events`
alongside envelope construction, codec and validation. **No `public.py` signature, command input
DTO, selector parameter or DTO field gains a trace parameter**, and boundary restoration remains the
`interfaces/*` / `tasks/*` responsibility ADR-0004 §9 and ADR-0005 already assign. This ADR therefore
adds **no `core` primitive**, moves **no** dependency-matrix cell, adds **no** import edge and
extends **no** `core` submodule allowlist; L1–L21 stand unedited.

**Consequently, the four fields must exist on the Outbox and Inbox schema from their initial Phase 1
migration, and no partitioning migration may precede that schema decision.** No TCE field is a
partition key, an ordering key or a uniqueness constraint.

### 4. Replay preserves historical lineage and executes in its own operational trace

A retry is the same consumer delivery of the same message: the four fields and `event_id` are
unchanged, each attempt gets its own processing span, and attempt metadata lives on the transport row
and as span attributes — never in the envelope.

A **replay** is a new operational action at a new moment in time. The message's four TCE values are
**immutable through it**, exactly as `event_id`, `event_type`, `schema_version`, `occurred_at` and
payload are. The replay executes in a **new operational trace**; the consumer's replay processing
span **links** to the original production context and carries the message's identifiers as
attributes, rather than being parented into a trace that has probably expired. Observability never
claims the replay happened during the original request. Replay mints no new `event_id`, changes no
causation, and remains **scoped to the failed consumer delivery** — ADR-0010's model is used as
written and amended nowhere.

A child message emitted by a *replayed* handler is produced now: its `trace_id` and
`producer_span_id` are the replay's, its `request_id` is inherited from the message being handled,
and its `causation_event_id` is that message's `event_id`. That asymmetry between `trace_id` and
`request_id` is deliberate and is the clearest demonstration of why both fields exist.

### 5. The correctness firewall

Trace, request and causation metadata **never decides** authorization, authentication, actor
identity, money, stock, reservation state, payment state, order placement, idempotency, duplicate
detection, schema compatibility, retry classification, queue routing, stale-projection acceptance,
event ordering, or whether a message is valid. Absent, partial, malformed or contradictory trace
context never quarantines, rejects or delays a message whose *contract* is valid: losing trace
continuity is an observability defect only. Sampling is observability policy only — the durable
identifiers are persisted whatever the sampler decided, and a collector, exporter or sampler outage
has no commercial effect whatsoever.

**Out of scope of this ADR:** physical column names, SQL types, nullability encoding, indexes,
partition keys and retention (Phase 1); Celery headers, serializer, broker and routing configuration
(Phase 1); the OpenTelemetry SDK, propagator, exporter and the API used to express a link (Phase 1);
span names and attribute keys (Phase 1 / operations); numeric sampling rates, retention windows and
alert thresholds (operations); which peers may adopt an inbound `traceparent` in a given deployment
(Phase 1 / operations); the concrete `event_id` / `PublicId` type (item 11); `source_version`
(item 12); and provider-specific tracing headers (the integration phases).

## Consequences

**Positive**

- Master `# 20.7`'s target trace assembles, and the durable chain behind it survives sampling, trace
  retention, broker purges, partition archival and replay, because it is reconstructable from
  PostgreSQL alone.
- One durable span column with one absolute meaning cannot be quietly turned into "the last component
  that touched this row", so a fan-out stays visible as a fan-out.
- Observability is structurally incapable of affecting commerce: no branch reads it, no outage blocks
  it, no sampling decision suppresses it.
- A terminal record — quarantine or operational dead-letter — is diagnosable on its own, months
  later, with the broker gone.
- The envelope stays a closed named set: no bag, no baggage, no vendor blob, and therefore no durable
  PII channel opened by accident.
- The schema-ordering constraint is stated before it becomes expensive.

**Negative / accepted cost**

- **Four columns on two of the highest-volume tables in the system, from day one**, most of them
  frequently absent. Accepted: they are small, fixed-width identifiers, and the alternative — adding
  them after partitioning — is the expensive outcome this item exists to prevent.
- **A rename away from the master's literal `span_id`.** Accepted: the value and the mechanism are
  unchanged, and the cost is one documented mapping row against a class of silent corruption.
- **No durable sampled flag**, so a trace sampled *in* at the edge may have its asynchronous
  continuation sampled *out* under a later policy, and an exported trace can be incomplete. Accepted:
  the durable identifiers and structured logs still reconstruct the chain, and master `# 23.3`
  already mandates 100 % or tail-based retention for checkout, payment, refund, webhook and
  reconciliation.
- **Causal chains are followed one hop at a time**, and a hop whose parent has been archived simply
  ends. Accepted: the alternative is an unbounded ancestry field that is mutated at every hop and
  invites ordering inference.
- **A replay's trace is not continuous with the original.** An operator follows a link rather than
  scrolling one trace. Accepted: the alternative misrepresents chronology and depends on retention
  the platform does not guarantee.
- **`request_id` and `trace_id` overlap in the common case**, where one implies the other. Accepted:
  they diverge exactly where diagnosis is hardest — replay, delayed relay, unsampled traces — and
  that is the case the durable fields exist for.

**Enforcement**

Phase 0 freezes it in [item 10](../architecture/phase-0/10-async-trace-propagation.md), which defines
the checks later phases implement:

- **A60–A67** (static/AST): the closed field set with no bag/baggage/`tracestate`; no TCE name in a
  payload contract; one writer per trace column; no business branch on trace metadata; no trace
  parameter in a public signature; no observability network I/O inside a durable transaction;
  write-once fields with no self-causation; and no neighbouring item's vocabulary in these artifacts.
- **C85–C99** (behavioural): end-to-end propagation; system origin with absent `request_id`;
  child-message causation; fan-out independence; relay with the producing process destroyed; broker
  outage; missing, malformed and contradictory carrier context each processing normally; retry and
  replay byte-identity; replay scoped to one consumer with the sibling's handler-invocation count
  asserted; an identical business outcome with the collector down and sampling off; terminal
  diagnosability after broker and partition loss; and no `(event_type, schema_version)` changed.
- **V74–V83** (review): ambiguous span naming; a resurrected `correlation_id`; trace metadata as
  auth/idempotency/ordering truth; ancestry paths; persisted baggage; broker headers as truth;
  history-rewriting retries or replays; observability outages reaching commerce; a partition
  migration authored too early; and PII or identity encoded into `request_id`.

Violating the schema-ordering constraint is caught at review of the first Outbox/Inbox migration:
a partitioning migration whose table lacks the four fields is rejected.
