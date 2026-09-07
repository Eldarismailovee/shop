# Phase 0 — Item 10: trace and causality propagation through Outbox/Inbox

- **Status:** DONE / FROZEN
- **Date:** 2026-09-05
- **Phase:** 0 — Architecture Freeze
- **ADR:** [ADR-0011](../../adr/0011-async-trace-causality-envelope.md) — required, see §1.3
- **Related:** [ADR-0004](../../adr/0004-four-layer-modular-monolith.md),
  [ADR-0005](../../adr/0005-dependency-and-integration-wiring.md),
  [ADR-0006](../../adr/0006-public-contract-primitives.md),
  [ADR-0007](../../adr/0007-place-order-atomic-idempotent-boundary.md),
  [ADR-0009](../../adr/0009-event-contract-versioning.md),
  [ADR-0010](../../adr/0010-async-failure-domain-isolation.md),
  [item 3](03-dependency-matrix.md), [item 4](04-domain-public-contract.md),
  [item 5](05-place-order-use-case.md), [item 8](08-event-registry-versioning.md),
  [item 9](09-queue-failure-domain-dlq.md),
  [event registry](../events/event-registry.md),
  master `# 20.1`–`# 20.3`, `# 20.5`–`# 20.7`, `# 21`, `# 23.1`–`# 23.3`

---

## 1. Purpose

### 1.1 What this item freezes

Item 8 froze the semantic envelope as exactly four fields — `event_id`, `event_type`,
`schema_version`, `occurred_at` — plus **one reserved extension point** (EN6, CA3) for the trace and
causality fields item 10 owns. It named no field and took no position on which exist. Item 9 froze
transport, terminal states and replay, and explicitly left the same territory alone (A59, §39).

Item 10 fills that extension point with a **closed named set of exactly four fields** and freezes the
propagation semantics along the whole asynchronous chain:

```text
HTTP / system entry
  → business transaction
    → durable Outbox record
      → relay
        → broker transport
          → consumer delivery
            → durable Inbox record
              → handler
                → child Outbox messages
                  → further consumers
```

so that an operator can reconstruct

```text
request → order placement → emitted message → relay → consumer delivery
  → ERP / notification / payment / projection reaction → messages emitted by that reaction
```

**without any of it becoming part of business correctness.**

Frozen here:

- the **closed trace/causality envelope extension** (the *TCE*): `trace_id`, `producer_span_id`,
  `request_id`, `causation_event_id` — four fields, no more, and no free-form map (§5);
- the **rejection** of a generic `correlation_id`, of a metadata/`meta`/`context` bag, of persisted
  OpenTelemetry baggage, of persisted vendor `tracestate`, and of a free-form ancestry path (§10);
- exact **`trace_id`** semantics (§6) and the deliberate rename of master's ambiguous `span_id` to
  **`producer_span_id`**, with its capture point, its write-once immutability, and the rule that it
  is never a consumer's span (§7);
- **`request_id`** semantics: origin-request identity where one exists, transitively inherited,
  never regenerated per hop, absent for system origin, never actor identity (§8);
- **durable immediate-parent causation** `causation_event_id`: one hop, unchanged by retry and
  replay, never self-referential, never ordering, never authorization, never idempotency (§9);
- the distinction between the four **defined slots** and the values actually present, with **TCE
  state** (value *or* legitimate absence, per field) as the unit that is captured, copied, retained
  and compared — so "four fields" never means "four non-empty values" (FS10, §3);
- **presence, absence and malformed-value invariants**, including the trace/span pair rule, the
  normalisation of all-zero and malformed identifiers to absent, and the **canonical TCE state per
  origin** — request first hop, system first hop, child message (§11, PR9);
- **producer capture**: the TCE is written into the same durable Outbox record inside the same
  business transaction, populated by the envelope mechanism from ambient in-process context, never
  passed as a business argument and never involving network I/O (§12);
- **the Outbox record as the durable propagation source** — sufficient on its own after a process
  restart, a delayed relay, a broker outage, a retry or a deployment (§13);
- the **relay/transport rule**: headers are a *copy/carrier*, never the source of truth (§14);
- **consumer and Inbox capture**, the separation of the message's immutable TCE from the delivery's
  own operational trace context, and the resolution rule when headers and durable metadata disagree
  (§15, §16);
- **fan-out**: one message, one TCE, one processing span *per consumer delivery* (§17);
- **retry**: same delivery, unchanged TCE, a new span per attempt, attempt metadata never in the
  envelope (§18);
- **replay**: the message's TCE stays immutable historical lineage, while the replay is a **new
  operational action with its own trace** that *links* to the original context rather than pretending
  to have happened inside it (§19);
- the **distinctness table** — trace / span / request / causation / identity / business time / schema
  version / source version / failure domain are nine different things, none interchangeable, none an
  ordering counter (§20);
- the **correctness firewall**: sixteen classes of decision that may never read trace metadata (§21);
- **security and privacy** (§22) and **sampling** (§23);
- the **storage-before-partition invariant**: the four fields exist on Outbox and Inbox from their
  *initial* Phase 1 schema, and no partitioning migration precedes that (§24);
- **terminal-record diagnosability** after broker data is gone (§25);
- the **envelope-not-payload** rule and the restatement that item 10 never bumps a payload
  `schema_version` (§26);
- a 16-row failure matrix (§27) and the checks later phases must implement (§28) — **A60–A67,
  C85–C99, V74–V83**.

### 1.2 What this item does **not** do

No Python package, module, Django model, migration, database column, index, partition, Celery
configuration, middleware, serializer, OpenTelemetry SDK setup, propagator wiring, exporter,
sampler or dependency is created. Phase 0 produces documents and decisions only.

Specifically **not** decided here:

| Not decided | Owner |
|---|---|
| The concrete `event_id` / `PublicId` type, and therefore the concrete representation of `causation_event_id` | **item 11** |
| `Money` | **item 11** |
| `source_version` generation, per-source mapping, guarded projection upsert | **item 12** |
| Whether async analytics exists | **item 13** |
| The MVP / later module cut | **item 14** |
| Outbox / Inbox / dedupe / quarantine **physical** schemas: column names, SQL types, nullability encoding, indexes, partition keys, retention | Phase 1 (master `# 20.2`, `# 20.3`, `# 20.5`) |
| Celery task routing, headers API, message serializer, broker configuration, queue topology | Phase 1 (item 9 §39) |
| The OpenTelemetry SDK, propagator, exporter, span-processor and instrumentation wiring, and the physical module that owns ambient context capture | Phase 1 |
| Span names, attribute keys and the semantic-convention set | Phase 1 / operations |
| Numeric sampling rates, retention windows, alert thresholds and dashboards | operations (master `# 23.3`) |
| Provider-specific tracing headers and vendor trace correlation | the integration phases |
| Which trust boundary may adopt an inbound `traceparent` in a given deployment | Phase 1 / operations, bounded by §22 |

### 1.3 Why a new ADR **is** required

Master `# 25`'s Phase 0 list anticipates *"trace propagation fields in Outbox/Inbox before partition
migrations"*, and item 10 makes four decisions that meet `docs/adr/README.md`'s "when an ADR is
required" test:

| Decision | Why it needs an ADR |
|---|---|
| **The reserved envelope extension point is filled by a closed set of exactly four named fields**, with a generic `correlation_id` and every metadata-bag form rejected by name. | It changes the shape of a public, cross-cutting contract — the message envelope every producer and every consumer sees — which item 8 EN6/CA3 deliberately left open for exactly one decision. |
| **Master's `span_id` is renamed to `producer_span_id` and given an absolute, writer-independent meaning**, and `causation_event_id`, which the master names nowhere, is added. | It departs from the literal field list of master `# 20.2` / `# 20.6` while preserving their intent (§1.4), and it introduces a durable causality concept the master does not have. |
| **The durable Outbox/Inbox record — not broker headers, not an in-process context — is the source of truth for asynchronous trace context**, and the four fields must exist from the initial Phase 1 schema, before any partitioning migration. | A source-of-truth rule of the same class as ADR-0009's and ADR-0010's, plus a schema-ordering constraint that binds Phase 1 and is very expensive to retrofit onto a partitioned, high-volume table. |
| **A replay's historical lineage is immutable, and the replay executes in a new operational trace that links to the original** rather than being parented into it. | It is the only place where "what happened" and "when it was re-run" can be silently conflated, and getting it wrong corrupts item 9's identity-preserving replay model in the observability layer without any test failing. |

[ADR-0011](../../adr/0011-async-trace-causality-envelope.md) records these. It changes **no**
dependency-matrix cell, adds **no** import edge, extends **no** `core` submodule allowlist, changes
**no** ADR-0009 message-contract rule and **no** ADR-0010 transport rule. L1–L21 stand unedited.
ADR-0009 and ADR-0010 are **not** edited and **not** superseded; item 8 EN6 and CA3 anticipated this
artifact in writing, so filling the extension point is the exercise of a reserved right, not an
amendment.

### 1.4 The one place item 10 clarifies the master

Master `# 20.2` and `# 20.6` list `trace_id`, `span_id`, `request_id` on the durable row. Master
`# 20.7` states the mechanism — capture at INSERT, W3C trace context plus `request_id` carried in
message headers, worker restores the parent context and creates a child span — and gives the target
trace. Master `# 23.3` states that losing trace on the async boundary is an observability defect.
All of that is preserved. The mapping:

| Master | Item 10 |
|---|---|
| `trace_id` on `OutboxEvent` / `InboxEventPayload` | **Kept**, with exact semantics (§6) |
| `request_id` on the durable row, generated at the edge and propagated into Celery tasks (`# 23.1`) | **Kept**, with exact semantics, transitive inheritance and an explicit absent case (§8) |
| `span_id` on the durable row | **Renamed to `producer_span_id`** (§7.2). The master name does not say *whose* span it is, and the same column would otherwise be written by producers and consumers alike. The value and its position in W3C `traceparent` are unchanged. |
| Capture **at the moment of INSERT** (`# 20.7`) | **Kept and strengthened**: same transaction, same durable record, write-once, no network I/O (§12) |
| Relay carries W3C trace context + `request_id` into message headers; the worker restores parent context and creates a child span (`# 20.7`) | **Kept**, with headers explicitly demoted to a carrier and the durable record made authoritative (§14, §16) |
| Webhook trace starts at `interfaces/webhooks/*`; provider event id as a **span attribute** (`# 20.7`) | **Kept** (§15.3) — the provider identifier stays a span attribute and never becomes a TCE field |
| Loss of trace continuity is an observability defect (`# 23.3`) | **Kept** and made a firewall rule (§21) |
| — (the master names no causality field) | **Added:** `causation_event_id` (§9). Trace data is sampled and short-lived; the causal chain of durable messages must be reconstructable weeks later, after a replay, from PostgreSQL alone. |
| — (the master names no `correlation_id`) | **Not added** (§10.1) |

Nothing else in master `# 20` or `# 23` changes.

---

## 2. Frozen principles inherited

| # | Inherited rule | Source |
|---|---|---|
| R1 | The semantic envelope is exactly `event_id`, `event_type`, `schema_version`, `occurred_at`, plus **one** reserved extension point for item 10; it is not a metadata bag, and no free-form map is permitted. | item 8 EN1, EN6, EN7 |
| R2 | `schema_version` versions the **payload only**. Adding, renaming or removing an item 10 envelope field never bumps any message's `schema_version`. | item 8 SV2, SV7, CA4 |
| R3 | Causal linkage is **observability and diagnosis**, never a correctness mechanism: no handler branches on it, no ordering derives from it, no idempotency decision depends on it. | item 8 CA5 |
| R4 | Losing trace continuity across the asynchronous boundary is an **observability defect**, not a message-contract defect. | item 8 CA6, master `# 23.3` |
| R5 | A producer writes its Outbox row inside its own business transaction; it never publishes to a broker directly and never schedules transport. | item 8 PI1, item 9 R2 |
| R6 | No external provider I/O — no HTTP, no SDK call — inside a durable business or handler transaction. | ADR-0004 §10, ADR-0007, item 8 HT3 |
| R7 | `event_id` is assigned once, at emission, and is preserved unchanged across every retry, redelivery and replay. Broker delivery identifiers are never event identity. | item 8 ID3, ID5, ID8 |
| R8 | Retry, redelivery and replay preserve `event_id`, `event_type`, `schema_version`, `occurred_at` and payload byte-for-byte. | item 8 ID3, TS3; item 9 R8, RA7 |
| R9 | The unit of failure, terminal identity and replay is a **consumer delivery**, not a message; two consumers of one `event_id` are independent deliveries. | item 9 §22.3, DL13–DL18 |
| R10 | Replay is explicit, authorised, audited, identity-preserving, re-enters normal validation, mints no new `event_id`, and is **scoped to the failed consumer delivery** — it never rebroadcasts to a sibling consumer. | item 9 RA1–RA9, RA5a, RA5b, RD7 |
| R11 | An unknown type, unsupported version or invalid payload is durably quarantined and alerted (TF-C). A technical handler fault is a bounded retry (TF-A). Neither category is invented or extended by item 10. | item 8 §20; item 9 §17 |
| R12 | The envelope carries **no transport concern**: no queue, exchange, routing key, retry counter, attempt number, delivery id, broker timestamp, worker identity or priority. | item 8 EN3; item 9 LY2 |
| R13 | A failure domain attaches to a **consumer**, never to a message version and never to a producer. | item 9 LY7, RT3, RT4 |
| R14 | A `tasks/*` handler deserialises, restores actor and trace, calls **one** use case or domain public command, and maps the result to success / retry / dead-letter. It decides *when*, never *what it means*. | ADR-0004 §9, item 3 §4.6, item 9 R3 |
| R15 | No secrets, tokens, credentials or personal data beyond need cross the asynchronous boundary; message content is subject to the platform's redaction rules in logs, traces, alerts and terminal displays. | item 8 SEC2, SEC3, SEC8; master `# 21`, `# 23.1` |
| R16 | `Money` and `PublicId` implementations, including the concrete `event_id` type, are item 11's. | item 8 ID7; item 9 §39 |

Nothing below weakens any of these.

---

## 3. Vocabulary

| Term | Meaning here |
|---|---|
| **TCE** — trace/causality envelope extension | The closed set of four **defined fields** item 10 freezes into item 8's reserved extension point (§5). Envelope metadata, never payload. "Four fields" always means four *slots*, several of which are legitimately empty on any given message. |
| **TCE state** | The complete four-slot state of one message: for each field, its value **or its absence**. The unit that is captured, copied, retained and compared. "Unchanged" and "byte-identical" TCE always mean this whole state, absences included (FS10). |
| **Production context** | The in-process trace context active at the instant a durable message record is written. `trace_id` + `producer_span_id` capture it. |
| **Processing span** | A span created for **one execution attempt of one consumer delivery**. It is never stored in the message's TCE. |
| **Replay operation trace** | The trace of an authorised replay action (§19). A new trace in a new moment in time; it never replaces a message's production context. |
| **Delivery** | Item 9's consumer delivery: one (message, declared consumer) pair. The unit of failure, terminal identity, replay — and of processing spans. |
| **Carrier** | A transport representation of trace context (a broker header, a task header). A copy. Never a source of truth (§14). |
| **Origin request** | The one synchronous external request — HTTP, webhook or equivalent boundary invocation — that causally started a chain of durable messages, where such a request exists. |
| **System origin** | A chain started with no synchronous request: a schedule, a reconciliation pass, a rebuild, a management action, a relay-internal maintenance job. |
| **Untraced production** | A durable message written while no trace context was active. Legal; both trace fields are absent (§11). |
| **Observability defect** | A loss or inconsistency of trace metadata. Alerted and fixed; never a business failure, never TF-C, never a reason to stop processing a valid message (R4, §21). |

---

## 4. The propagation chain

```text
  HTTP request / webhook / schedule
        │  (edge: request_id exists or does not; trace starts or continues)
        ▼
  business transaction ─────────────────────────────────────────────┐
        │  domain/application work                                  │ one local
        │                                                           │ atomic()
        ▼                                                           │
  durable Outbox record                                             │
    envelope: event_id, event_type, schema_version, occurred_at     │
    TCE:      trace_id, producer_span_id, request_id,               │
              causation_event_id                                    │
        └───────────────────────────────────────────────────── COMMIT
        │
        ▼
  relay  ── reads the durable row; needs nothing else ──────────────► broker
        │        builds carrier headers from the durable TCE
        ▼
  consumer delivery  (per declared consumer — item 9 R9)
        │  extract carrier → validate → new processing span,
        │  child of the message's production context
        ▼
  durable Inbox / consumer-delivery record
    retains the message's TCE verbatim (immutable)
    + its own operational trace context per attempt (separate)
        │
        ▼
  handler  ── emits child Outbox messages ──────────────────────────┐
        │      child.trace_id        = trace of the child's production
        │      child.producer_span_id= the handler's current span
        │      child.request_id      = inherited origin request_id
        │      child.causation_event_id = this message's event_id
        └──────────────────────────────────────────────────────────► further consumers
```

---

## 5. The closed field set

### 5.1 The candidates, evaluated

| Candidate | Verdict | Reason |
|---|---|---|
| `trace_id` | **Adopted** | The only field that lets a distributed trace be assembled at all, and the one master `# 20.2`/`# 20.6`/`# 20.7` already require. |
| `span_id` (master's name) | **Adopted with a rename** | The value is required; the *name* does not say whose span it is, which is exactly the ambiguity that turns one column into "producer's span, except when a consumer wrote it". Frozen as `producer_span_id` (§7.2). |
| `parent_span_id` | **Rejected as a name** | "Parent" is relative to the reader. From the consumer's side it is the parent; from the producer's side it is the *current* span, not its parent. An absolute name is required for a durable column that outlives both. |
| `request_id` | **Adopted** | Not redundant with `trace_id`. A trace is sampled, short-lived and legitimately *discontinuous* across a replay or a months-later relay; `request_id` is a durable join key for the whole causal chain that survives all of that, and master `# 23.1` already requires it on every log line. |
| `correlation_id` (generic) | **Rejected** | §10.1. Every precise meaning it could carry is already carried by `request_id`, `causation_event_id` or `event_id`; the only meaning left is "some identifier somebody found useful", which is a metadata bag with one field. |
| `causation_id` / `causation_event_id` | **Adopted as `causation_event_id`** | The durable chain must be reconstructable from PostgreSQL alone after trace retention has expired. The longer name says what the value *is* — another message's `event_id` — and prevents it being read as a span, a request or a business reference. |
| An ancestry list / causal path | **Rejected** | §10.4. Unbounded, mutated by every hop, and a standing invitation to derive ordering from it. |
| Envelope `sampled` flag | **Rejected as a durable field** | §23.3. A sampling decision taken hours earlier is a stale policy decision; persisting it makes retention policy leak into durable business rows. |
| Failure domain / queue on the envelope | **Rejected** | R12, item 9 LY2. Routing is per-consumer transport metadata and does not travel with the message. |

### 5.2 The frozen set

| # | Rule |
|---|---|
| FS1 | The TCE is exactly four fields: **`trace_id`**, **`producer_span_id`**, **`request_id`**, **`causation_event_id`**. It is a closed, named set. |
| FS2 | The TCE **is item 8 EN6's single reserved extension point, now spent**. There is no second extension point. Item 8 EN7 stands unchanged: a field that is not one of EN1's four and not one of FS1's four does not exist. |
| FS3 | **No metadata bag, in any disguise**: no `meta`, `extra`, `context`, `attributes`, `headers`, `annotations`, `tags`, `dict[str, Any]`, JSON blob, arbitrary key/value map, OpenTelemetry `baggage`, W3C `tracestate` or vendor tracing blob is persisted in or beside the envelope (§10.2, §10.3, A60). |
| FS4 | The TCE is **envelope metadata, never payload** (§26). No registered payload schema contains any of the four, or any alias of them. |
| FS5 | Every TCE field is **optional by construction**. A reader must tolerate any of the four being absent and must still process the message (§11, §21). |
| FS6 | Every TCE field is **write-once at message creation** and immutable thereafter — through every retry, redelivery, replay, terminal transition and archival (§18, §19, A66). |
| FS7 | **Changing the TCE set requires a new ADR** superseding ADR-0011. Because FS5 makes every field absence-tolerant, no envelope version field is introduced and none may be added without that ADR (item 8 CA4). |
| FS8 | The TCE carries **no transport concern** (R12) and **no business data** (item 8 EN4). A value that a handler would branch on is, by definition, not a TCE field. |
| FS9 | The four fields are populated by the **envelope mechanism**, not by business code: no `public.py` signature, command input DTO, selector argument or payload gains a trace parameter (§12.3, A64, item 4 §5 export categories unchanged). |
| FS10 | **"Four fields" means four defined slots, never four present values.** Because every field is optional (FS5), the meaningful unit is the **TCE state** (§3): for each of the four, its value *or* its legitimate absence. A message with `causation_event_id` absent has a *complete* TCE, not a partial one. Wherever this artifact says a TCE is *captured*, *copied*, *retained*, *unchanged*, *byte-identical* or *preserved*, it means the whole state — **values and absence states alike** — so preserving a TCE never means making an absent field present, and never permits an absent field to acquire a value or a present one to lose it. No rule, test or check anywhere requires all four to be non-empty on any message (PR1, PR6, PR7, CZ2). |

---

## 6. `trace_id`

| # | Rule |
|---|---|
| TR1 | **`trace_id` identifies the distributed trace that contains the production of this message** — the trace active in the process at the instant the durable Outbox record was written. It identifies nothing else. |
| TR2 | Its value space is a **W3C Trace Context trace-id**: 16 bytes, rendered as 32 lowercase hexadecimal characters, all-zero being invalid. This is frozen so that the value is interoperable with the propagation format master `# 20.7` already requires, and so that validation is decidable. |
| TR3 | The **physical storage representation** — column name, SQL type (text, `bytea`, `uuid`-shaped), nullability encoding, and whether an index exists — is **Phase 1's** (§24). The semantic value space above is frozen; the DDL is not. |
| TR4 | A child message produced while handling another message is produced **in the trace that contains that production**. Under normal handling the handler continues the parent message's trace, so the child's `trace_id` equals the parent's; under a replay the production genuinely happens in the replay operation trace, and the child's `trace_id` is that one (§19.4). `trace_id` is therefore never "copied forward" as a rule — it always means TR1, and the equality is a consequence. |
| TR5 | `trace_id` is **not** an identity, not a deduplication key, not an ordering key, not a partition key and not a business reference (§20, §21). Two unrelated messages sharing a `trace_id` is normal; one message's chain spanning several traces is normal. |
| TR6 | `trace_id` is **not unique per message.** One trace routinely contains many messages; expecting uniqueness is a defect. |
| TR7 | A `trace_id` value is never invented to fill a gap. If no trace was active, the field is absent (§11), and a synthetic identifier is never minted merely so a column is non-null. |

---

## 7. `producer_span_id`

### 7.1 Semantics

| # | Rule |
|---|---|
| SP1 | **`producer_span_id` is the span that was active in the producing process at the instant the durable message record was written** — the span *inside which* the Outbox row came into existence. It is the producer's own span, never its parent, and never a consumer's. |
| SP2 | It is captured at exactly the same instant as `trace_id`, inside the same business transaction, from the same ambient context (§12). |
| SP3 | It is **write-once and immutable** (FS6). No consumer, no retry, no replay, no relay and no operator tool ever writes a span identifier back into a message's `producer_span_id`. |
| SP4 | Its value space is a **W3C Trace Context span-id**: 8 bytes, rendered as 16 lowercase hexadecimal characters, all-zero being invalid. The physical storage representation is Phase 1's (TR3). |
| SP5 | When the relay serialises the durable context into a W3C `traceparent` carrier, `producer_span_id` occupies the **`parent-id` position** — which is precisely what that position means to the receiver: "the span that produced what you are now handling". The durable field's name states this absolutely so it cannot be read two ways depending on who opens the row. |
| SP6 | A consumer's processing span is a **child** of `(trace_id, producer_span_id)` under normal handling (§15), and is **linked** to it under replay (§19). In neither case does it overwrite it. |
| SP7 | `producer_span_id` is meaningless without `trace_id` and never appears alone (§11, PR2). |

### 7.2 Why master's `span_id` is renamed

Master `# 20.2` and `# 20.6` list a bare `span_id` column on `OutboxEvent` and `InboxEventPayload`.
The value is right; the name is the failure mode. A column called `span_id` on a row that is written
by a producer, read by a relay, read by N consumers and re-read by a replay tool answers the question
"whose span?" differently to each reader, and the predictable outcome is that some code path
eventually writes the *consumer's* span into it — after which the column means "the last span that
touched this row", the fan-out picture collapses to whichever consumer wrote last, and no test fails.
`producer_span_id` is unambiguous for every reader and for every future writer, and the rename costs
nothing: the value, the capture point and the wire position are exactly master `# 20.7`'s.

---

## 8. `request_id`

| # | Rule |
|---|---|
| RQ1 | **`request_id` identifies the originating synchronous request of the causal chain**, where such a request exists: the HTTP request, the inbound webhook invocation or the equivalent boundary invocation that started it. |
| RQ2 | It is **inherited transitively and unchanged** by every durable message emitted, directly or indirectly, while that chain is being processed. It is **not regenerated at each asynchronous hop** and not re-derived per message. |
| RQ3 | It is **absent** for a chain of **system origin** (§3): schedules, reconciliation passes, projection rebuilds, expiry sweeps, relay-internal maintenance, management actions. Absence is a normal, expected state, not a gap to be filled with a synthetic value. |
| RQ4 | It is **observability metadata only**. It is not actor identity, not a principal, not a session identifier, not an authentication token, not an authorization input and not a tenant/scope selector. No handler may derive who the actor is, or what they may do, from it (§21). |
| RQ5 | It is **not a business correlation identifier**. Where a business workflow genuinely needs to correlate work — a placement attempt, a payment attempt, a reconciliation run, an ERP batch — that identifier belongs to the owning module's own contract or durable state, with its own name, its own semantics and its own lifecycle. Using `request_id` for it makes an observability field load-bearing and is forbidden (§10.1, V75). |
| RQ6 | Its value is a **bounded-length opaque token**. The platform parses no structure out of it, derives nothing from it, and sorts nothing by it. |
| RQ7 | It **never encodes personal data or identity** — no user id, email, phone, session id, cart id or anything derived from them (§22, V83). Where the edge mints it, it mints an opaque random value. |
| RQ8 | A **client-supplied** request identifier is untrusted input. It may be adopted only after boundary validation of charset and length, and only where the deployment's trust policy permits; otherwise the edge mints its own. Either way it never influences authorization, rate limiting or any business decision (§22, RQ4). Master `# 23.1` already places generation at the reverse proxy; which peers are trusted is Phase 1 / operations. |
| RQ9 | `request_id` is **not** an ordering key, not an identity, not a deduplication key and not unique per message. One request routinely produces many messages (§20). |
| RQ10 | `request_id` and `trace_id` are **not substitutes for each other.** `trace_id` describes where a production event sits in a *trace*, which is sampled, short-lived and legitimately discontinuous across a replay; `request_id` describes which *origin request* a durable fact belongs to, survives every discontinuity, and is present in structured logs where trace data may not be (master `# 23.1`). Keeping both is deliberate. |

---

## 9. `causation_event_id`

| # | Rule |
|---|---|
| CZ1 | **`causation_event_id` is the `event_id` of the immediate parent message** — the registered durable message whose handling caused this one to be emitted. |
| CZ2 | It is **present iff** the message was emitted while handling another registered durable message. It is **absent** for a message emitted directly from a synchronous request or from a system-origin job. Absence is normal and is not a gap. |
| CZ3 | It is **one hop only**. It is not a list, not a path, not a root reference and not an ancestry chain. Full chains are reconstructed by **following retained records** — each row points at its immediate parent — for as long as those records are retained (§10.4). |
| CZ4 | Its semantic type is **the same as `event_id`'s**. The concrete representation is **item 11's** (R16); item 10 requires only that whatever `event_id` is, `causation_event_id` is a value of that same space. |
| CZ5 | It is **immutable across retry and replay of the emitting message**, exactly as `event_id` is (FS6, R8). A message re-delivered, re-tried or replayed keeps the parent it was born with. |
| CZ6 | **`causation_event_id` never equals the message's own `event_id`.** Self-causation is a defect, checkable statically at the emission site and behaviourally in tests (A66, C87). |
| CZ7 | It establishes **no ordering**. Causation is a shape, not a sequence: it says B was emitted while A was handled, never that B's effect happens after any other message's, and never that two children of one parent are ordered relative to each other (item 8 OR1–OR4, §20). |
| CZ8 | It establishes **no authorization**. "This descends from a message the actor caused" is not permission to do anything (item 8 SEC5, §21). |
| CZ9 | It establishes **no idempotency and no deduplication**. Duplicate detection is item 8 §21's, keyed on `event_id` per consumer, and never on the parent (§21). |
| CZ10 | It **does not require the parent record to exist, now or ever.** The parent's Outbox partition may have been archived (master `# 20.2`, `# 20.5`); the parent may be beyond retention. A dangling `causation_event_id` is expected and is never a validation failure, never a foreign key, never a join the platform requires at runtime, and never a reason to quarantine (§21, C98). |
| CZ11 | It is **not a business reference.** A handler that needs the parent's *content* re-reads the owning module's public selector or receives the data it needs in its own payload (item 8 §13 SR3), never by resolving a causation link. |
| CZ12 | An `EVENT` fanned out to N consumers produces, in general, **N independent causal branches**: every child message each consumer emits carries the *same* `causation_event_id` — the shared parent — while their `event_id`s and production contexts differ (§17). |

---

## 10. Rejected fields

### 10.1 `correlation_id`

**Rejected.** Every precise meaning it could carry is already carried:

| Meaning someone might attach to it | Already carried by |
|---|---|
| "which request started all this" | `request_id` (§8) |
| "which message caused this one" | `causation_event_id` (§9) |
| "which trace does this belong to" | `trace_id` (§6) |
| "which message is this" | `event_id` (item 8 §9) |
| "which business workflow is this part of" | the owning module's own contract or durable state — **not** universal observability metadata (RQ5) |

What remains is a field with no definition, which is a metadata bag with one entry: every producer
puts something different in it, every consumer eventually reads it, and within a year someone
branches on it. A vague correlation identifier is therefore forbidden by name (V75). Should a
genuine, precisely-defined universal need ever appear that none of the five rows above covers, it is
a new field, a new ADR superseding ADR-0011, and a stated semantic (FS7).

### 10.2 A metadata bag

**Rejected**, in every disguise: `meta`, `extra`, `context`, `attributes`, `headers`, `tags`,
`annotations`, `dict[str, Any]`, "just one JSON column for future use". Item 8 EN7 and EN10 already
forbid it for the envelope and the payload; FS3 extends the same rule to the TCE, so that the
extension point item 8 reserved cannot be spent on a bag (A60).

### 10.3 OpenTelemetry `baggage` and W3C `tracestate`

**Not persisted.** Baggage is unbounded, propagates key/value data written by anything upstream, and
is precisely the shape of an accidental durable PII channel (§22). `tracestate` is vendor state whose
meaning the platform does not own. Neither is written into an Outbox or Inbox record. Both may exist
transiently in transport carriers if a Phase 1 propagator emits them; nothing durable reads them, and
nothing business-facing depends on them. Persisting either requires a specific bounded need, a named
justification and a new ADR (FS3, FS7, V78).

### 10.4 An ancestry list or causal path

**Rejected.** A `causal_path: [...]` field grows without bound along a chain, is mutated by every hop
(contradicting FS6), and reads as a sequence — which is exactly the ordering inference CZ7 forbids.
One hop, followed backwards through retained rows, gives the same reconstruction with none of those
properties (CZ3).

### 10.5 A queue, failure domain, attempt or worker field

**Rejected**, restating R12 and item 9 LY2/RT3. Routing is per-consumer transport metadata; an
attempt counter is transport state on the delivery row; a worker identity is operational. None
travels in the envelope, and item 9 stays untouched (§17.2).

---

## 11. Presence, absence and malformed values

| # | Rule |
|---|---|
| PR1 | Every TCE field is optional (FS5). Absence is a legal, expected state — never an error that stops processing (§21). |
| PR2 | **`trace_id` and `producer_span_id` are a pair.** Both present, or both absent. Exactly one present is a **TCE integrity defect**: it is recorded and alerted as an observability defect, the message is read as untraced, and processing continues normally (A62, C99). |
| PR3 | **An absent pair means untraced production**: no trace context was active in the process when the durable record was written. Legitimate cases include a management command run without instrumentation, an early-startup path, and a deployment with tracing disabled. It is not a defect by itself; on a route that is expected to be traced, the *rate* of untraced production is the operational signal. |
| PR4 | **Malformed values are normalised to absent at capture and never stored**: wrong length, non-hexadecimal characters, or the all-zero identifier that W3C defines as invalid. A malformed value is never persisted, never propagated and never repaired by invention. |
| PR5 | The same normalisation applies on **extraction from a carrier** (§14, §16): a malformed inbound trace header yields absent context, a fresh root processing span, and an observability-defect signal — never TF-C, never payload invalidity, never a business error (§21, C92). |
| PR6 | `request_id` present means "this chain has an origin request". Absent means system origin (RQ3). There is no third state and no placeholder value; the empty string, `"none"`, `"-"` and `"unknown"` are not permitted stand-ins. |
| PR7 | `causation_event_id` present means "emitted while handling that message". Absent means emitted from a request or a system-origin job (CZ2). A present value that does not resolve to a retained record is expected (CZ10). |
| PR8 | **No TCE field is ever back-filled after the fact.** A later process that discovers what a value "should have been" does not write it into the message row; the gap is a diagnostic fact, and rewriting history to hide it is worse than the gap (FS6, A66). |
| PR9 | The **canonical TCE state by origin** follows from the rules above and is what tests assert (FS10): |

| Origin of the emitted message | `trace_id` / `producer_span_id` | `request_id` | `causation_event_id` |
|---|---|---|---|
| **First hop from a synchronous request** (HTTP, webhook) | present when the producing execution is traced; absent as a pair when it is not (PR2, PR3) | **present** (RQ1) | **absent** — there is no parent durable message yet (CZ2) |
| **First hop of system origin** (schedule, reconciliation, rebuild, maintenance) | same pair rule | **absent** (RQ3) | **absent** (CZ2) |
| **Child emitted while handling another registered durable message** | same pair rule, capturing the handler's context (PC11, PC12) | **inherited from the handled message**, present or absent exactly as it was (PC13, RQ2) | **present** — the handled message's `event_id` (PC14) |

None of the three rows is a degraded case; each is the complete and correct TCE state for its origin.

---

## 12. Producer capture

### 12.1 The shape

```text
BEGIN                                       # the producer's own business transaction
  domain / application work
  build envelope:  event_id, event_type, schema_version, occurred_at
  capture TCE:     trace_id, producer_span_id   ← ambient in-process trace context
                   request_id                   ← ambient origin-request context (or absent)
                   causation_event_id           ← ambient handled-message context (or absent)
  write ONE durable Outbox record: payload + envelope + TCE
COMMIT
```

### 12.2 Rules

| # | Rule |
|---|---|
| PC1 | The TCE is captured **at the instant the durable record is written**, inside the **same** transaction that writes it, and is stored in the **same** durable record as the payload and the envelope. Master `# 20.7`'s "trace metadata is saved at the moment of INSERT" is the binding statement; item 10 adds only that it is one record and one transaction. |
| PC2 | **No network I/O of any kind during capture** — no collector, no exporter flush, no broker, no provider, no remote sampler lookup. Reading ambient in-process context is permitted and is the whole mechanism (R6, A65). |
| PC3 | A failure to capture trace context **never fails the business transaction**. If context is unavailable, the fields are absent (PR3) and the commit proceeds unchanged (§21, C97). |
| PC4 | Capture is **not conditional on a sampling decision**. The four identifiers are persisted whenever they exist, whatever the sampler decided (§23, C97). |
| PC5 | The producer never writes a *consumer's* context and never writes a value it did not observe (SP3, PR8). |

### 12.3 Who populates it

| # | Rule |
|---|---|
| PC6 | The TCE is **envelope metadata populated by the envelope mechanism**, which item 8 OW4 already places in `core.events` alongside envelope construction, registry lookup, codec and validation. Item 10 adds a responsibility to an existing mechanism; it introduces **no `core` primitive and extends no `core` submodule allowlist** (ADR-0005 §1, ADR-0006's precedent). |
| PC7 | The values come from **ambient, in-process, request/message-scoped context**, not from arguments. **No `domains/<x>/public.py` or `application/<a>/public.py` signature, command input DTO, selector parameter, DTO field or payload gains a trace, span, request or causation parameter** (FS9, A64). Item 4 §5's eight export categories are untouched. |
| PC8 | Restoring ambient context at a transport boundary is **`interfaces/*` and `tasks/*` work**, exactly as item 3 §4.6 and ADR-0004 §9 already assign it (R14). Domains and application modules neither read transport headers nor assemble carriers. |
| PC9 | The **physical module** that owns ambient capture and restoration, and the OpenTelemetry API/SDK surface it uses, are **Phase 1's**. If Phase 1 places it in a `core` submodule that ADR-0005 §1 does not already allowlist, that placement records an allowlist extension then — as ADR-0006 did for the actor primitive — and item 10 neither pre-empts nor requires it. |

### 12.4 Child messages emitted by a handler

| # | Rule |
|---|---|
| PC10 | A handler that emits a child message **inside its handler transaction** (item 8 HT1) captures the child's TCE by the same mechanism, at the same instant, in the same record. |
| PC11 | `child.trace_id` = the trace containing the child's production (TR4) — under normal handling, the parent message's trace, continued. |
| PC12 | `child.producer_span_id` = **the handler's currently active span**, which is the consumer's processing span. This is the one and only place a consumer's span identifier is durably recorded, and it is recorded as the **producer** context of a *different, new* message — never written back into the parent's row (SP3). |
| PC13 | `child.request_id` = the parent message's `request_id`, inherited unchanged, including absence (RQ2, RQ3). |
| PC14 | `child.causation_event_id` = the parent message's `event_id` (CZ1). |
| PC15 | These four assignments happen **before** any external work. Provider I/O stays post-commit (R6, item 8 HT4); the trace context of a post-commit port call is ordinary tracing and produces no durable message field. |

---

## 13. The Outbox record is the durable propagation source

| # | Rule |
|---|---|
| OB1 | **The durable Outbox record alone is sufficient to restore asynchronous trace and causality context.** Neither an in-memory context, nor a broker header, nor a live originating process is required. |
| OB2 | Sufficiency holds specifically after: a **process restart**; a **delayed relay**; a **broker outage** and later drain; a **retry**; a **deployment**; a relay running in **another process, another host or another release**; and an operator reading the row **weeks later**. |
| OB3 | **The relay must never require the originating HTTP process, worker process or request scope to still exist.** A design in which the relay reads context from anywhere but the durable row is non-conformant (C89). |
| OB4 | This is the reason item 10 precedes partition migrations: the fields must exist on the *initial* Outbox and Inbox schema, because adding a column to a partitioned, high-volume, already-retained table later is expensive and leaves every historical row permanently blind (§24). |
| OB5 | No concrete column type, index, partition key or migration is designed here (§1.2, TR3). |

---

## 14. Relay and transport carriers

```text
durable Outbox TCE  →  relay  →  transport carrier (headers/context)  →  consumer
     source of truth            copy, in flight only, never authoritative
```

| # | Rule |
|---|---|
| RL1 | The relay **reads** the message's TCE state from the durable row and **copies** it into the transport carrier: present values are carried, and an absent field is carried as absent. It composes; it does not decide, does not enrich, and **does not invent a value for an empty field** (FS10, PR4). |
| RL2 | **A transport carrier is never a source of truth.** Headers are a convenience for automatic context restoration; the durable record is authoritative in every conflict (§16). |
| RL3 | The relay **never writes back** into the message row: no relay span, no publish timestamp, no attempt count in the TCE. Operational relay state lives in transport columns on the row, which item 8 TS5 and EN3 already permit and keep out of the envelope. |
| RL4 | **A standards-compatible propagation model is used**: W3C Trace Context (`traceparent`) for the trace pair, and a platform-defined carrier entry for `request_id`, exactly as master `# 20.7` requires. Whether `causation_event_id` is carried in the transport at all is a Phase 1 optimisation and carries no semantics — the consumer's authoritative copy is the durable message record (§15.2). |
| RL5 | The relay's own execution may of course be traced. Its spans belong to the relay's operational trace and are **linked to** — never substituted for — the message's production context. |
| RL6 | **No queue, failure domain, routing key, priority or attempt field is added to the TCE** by the relay or anyone else (§10.5, R12). Item 9's routing model is untouched (§17.2). |
| RL7 | The exact Celery/broker header names, the message serializer, the propagator implementation and the OTel wiring are **Phase 1's** (§1.2). Item 10 freezes the direction of the copy and the location of the truth, not the API. |

---

## 15. Consumer entry and Inbox capture

### 15.1 At consumer entry

| # | Rule |
|---|---|
| CN1 | The transport boundary **extracts and validates** carrier trace context (PR4, PR5), then creates a **new processing span for this consumer delivery** (R9). |
| CN2 | Under normal delivery the processing span is a **child of the message's production context** `(trace_id, producer_span_id)`. That is what makes master `# 20.7`'s target trace assemble. |
| CN3 | **The message's TCE is immutable at the consumer.** No consumer, at any point, writes its span, its trace, its attempt number, its worker identity or its failure domain into the message's four fields (SP3, FS6, A66). |
| CN4 | The consumer's own identifiers — processing span, attempt, worker, delivery — belong to the **delivery's operational trace context**, which is a *separate* set of operational columns/records from the message's TCE. Two concepts, two homes, never one column (§15.2). |
| CN5 | Restoration is boundary work (`interfaces/*`, `tasks/*`), per R14/PC8. The handler receives a restored context and a validated message; it never parses headers. |

### 15.2 The Inbox / consumer-delivery record

| # | Rule |
|---|---|
| CN6 | The durable consumer-delivery record **retains the message's TCE state verbatim** — present values and legitimate absences alike (FS10) — as received in the durable message, alongside `event_id`, `event_type` and `schema_version` (item 8 IX2). An absent field is retained as absent, never completed from the carrier or from the consumer's own context. |
| CN7 | The purpose is explicit: **later diagnosis must not depend on broker data**, which is transport and is gone after acknowledgement, after a purge, or after the broker is replaced (item 9 TD5–TD8). Master `# 20.3` already lists `trace_id`/`span_id`/`request_id` on `InboxEventPayload`; CN6 states *why* and adds `causation_event_id`. |
| CN8 | The delivery record **additionally** carries its own operational trace context per attempt — the processing trace/span of the attempt, and for a replay the replay operation trace (§19). These are operational columns, mutable per attempt, and are never confused with, merged into, or allowed to overwrite CN6's copy (CN4, A62). |
| CN9 | Physical schema — table shape, column names, types, indexes, partitioning, retention — is **Phase 1's** (master `# 20.3`, §24). |

### 15.3 Inbound provider webhooks

| # | Rule |
|---|---|
| CN10 | An inbound provider event has **no prior internal durable record**, so there is nothing to restore from. The trace **starts at `interfaces/webhooks/<provider>`**, exactly as master `# 20.7` states, and the durable ingest record captures that boundary context as its TCE. |
| CN11 | The provider's `external_event_id` is recorded as a **span attribute** and in the provider dedupe record (master `# 20.3`, item 8 ID6). It is **never** a TCE field and never becomes internal message identity. |
| CN12 | A provider-supplied trace header is **untrusted input** and is subject to §22's adoption rules; it never influences signature verification, authorization, replay-window checks or any other security decision (item 8 SEC5, §21). |
| CN13 | The internal registered message the owning application module authors later in the worker (item 8 §1.4's correction of master `# 12.2`) captures its own TCE by the ordinary producer rules (§12), with `causation_event_id` referring to the internal message being handled where one exists — never to the provider's identifier (CZ4, CN11). |

---

## 16. When the carrier and the durable record disagree

| # | Rule |
|---|---|
| SR1 | **The durable message record wins.** For storage, for diagnosis, and for parenting the consumer's processing span, the values used are the message's TCE, not the carrier's. |
| SR2 | A disagreement is an **observability defect**: recorded, counted and alerted per the operations policy. It is **not** TF-C, **not** payload invalidity, **not** an identity-integrity violation under item 8 IX5 (which is about `event_id`/type/version/payload, and is untouched), and **not** a business error (§21, C93). |
| SR3 | The message **is processed normally**. A disagreement about how a trace is drawn can never determine whether an order, a payment, a reservation or a projection update happens (§21). |
| SR4 | A missing carrier is not a disagreement: the durable values are simply used, and if those are absent too, the consumer starts a **new root processing span** and records an untraced-continuation signal (PR3, C91). |
| SR5 | The consumer never "repairs" the durable record to match the carrier, or the carrier to match the record (PR8). |

---

## 17. Fan-out and per-consumer execution

### 17.1 The model

```text
one EVENT:  event_id = E,  TCE = (trace T, producer span P, request R, causation C)

  consumer A  → delivery A → processing span A   (child of T/P, or linked under replay)
  consumer B  → delivery B → processing span B
  consumer D  → delivery D → processing span D

  the message's TCE is written once, read three times, mutated never.
```

| # | Rule |
|---|---|
| FO1 | One `EVENT` delivered to N declared consumers has **one** `event_id` and **one** TCE, and **N independent processing spans** — one per consumer delivery (R9). |
| FO2 | Under normal delivery all N processing spans are children of the same `(trace_id, producer_span_id)`, so the trace shows a genuine fan-out rather than a chain. |
| FO3 | **One consumer's trace processing never mutates another consumer's records and never mutates the message.** A's span never appears in B's delivery record, and neither appears in the message's TCE (CN3, CN4). |
| FO4 | Each consumer's child messages carry that consumer's processing span as their `producer_span_id` (PC12) and the same shared `causation_event_id` (CZ12). The branches diverge from the parent, not from each other. |
| FO5 | One consumer succeeding while another retries, quarantines, dead-letters or is replayed changes **nothing** about the message's TCE (item 9 DL13–DL18). |

### 17.2 Item 9 is not reopened

| # | Rule |
|---|---|
| FO6 | **Failure-domain routing remains per consumer declaration** and remains entirely separate from tracing (R13, item 9 RT3/RT4). No failure domain, queue, criticality or routing value is a TCE field (§10.5, RL6). |
| FO7 | Item 10 adds **no** field to the event registry, **no** column to the queue/failure-domain matrix, and **no** consumer declaration attribute. ADR-0010's one operational addition — the per-consumer failure-domain assignment — is untouched. |
| FO8 | Item 9's terminal states, retry taxonomy, replay authority and consumer-delivery model are used exactly as written and are amended in no respect (§19, §25). |

---

## 18. Retry

| # | Rule |
|---|---|
| TY1 | **A retry is the same consumer delivery of the same message identity** (item 9 §17, R8). It is not a new message and not a new delivery. |
| TY2 | The message's TCE is **unchanged**: no new `trace_id`, no new `producer_span_id`, no new `request_id`, no new `causation_event_id` — and no new `event_id` (R7, R8, FS6). |
| TY3 | **Each processing attempt gets its own processing span**, created at the transport boundary exactly as the first attempt's was (CN1), and parented the same way (CN2). Attempts are siblings under the message's production context, not a chain of children. |
| TY4 | **Attempt metadata is never in the semantic envelope or the TCE**: attempt number, retry count, backoff, next-retry time, worker identity and queue live on the transport/delivery row and, where useful, as **span attributes** (R12, item 8 EN3, item 9 RO2). |
| TY5 | **A trace or span identifier is never retry identity, delivery identity or deduplication identity.** Retry identity is item 9's delivery; deduplication identity is item 8's `event_id` per consumer (§21, V76). |
| TY6 | A retry that crosses a process, a host or a deployment restores context from the durable record exactly as the first attempt did (OB1–OB3). |

---

## 19. Replay

### 19.1 The problem

Item 9 freezes replay as an authorised, audited, identity-preserving re-injection of **one consumer
delivery**, which mints no new `event_id` and never rebroadcasts to a sibling consumer (R10). A
replay is nevertheless a **new action at a new moment in time**, often months after the original
request, in a different deployment, when the original trace has long since fallen out of retention.
Two mistakes are available and both are silent:

- **rewriting** the message's TCE to the replay's context — which destroys the historical lineage
  that is the whole reason the fields are durable, and contradicts R8;
- **parenting** the replay's processing span into the original trace — which makes the replay
  invisible in the operation that actually caused it, misrepresents chronology as though the work
  happened during the original request, and depends on a trace that retention may have dropped.

### 19.2 The frozen model

```text
message (durable)      TCE = (T, P, R, C)          immutable historical lineage
                                                   unchanged by the replay

replay operation       new trace T'                its own operational action, now
  operator/tool span
    consumer replay processing span                child of T'
      link → (T, P)                                reference to the original production
      attributes: event_id, T, P, R, C, consumer,
                  terminal state replayed from
```

| # | Rule |
|---|---|
| RP1 | **The message's TCE state is immutable through replay** — values and absences alike (FS10) — exactly as `event_id`, `event_type`, `schema_version`, `occurred_at` and payload are (R8, item 9 RA7, FS6). No replay path writes to it, and a replay never completes a field the original emission left empty (A66, PR8, C95). |
| RP2 | **A replay executes in its own operational trace**, rooted at the authorised replay action. It does not continue the original trace. |
| RP3 | The consumer's replay processing span **links** to the original production context `(trace_id, producer_span_id)` and carries the message's `event_id`, `request_id` and `causation_event_id` as attributes, so the historical chain is one hop away in the tooling without pretending to be the parent. |
| RP4 | **Observability never claims the replay happened during the original request.** The replay's timestamps, its trace and its operator attribution are all of *now*; the original context is a reference, not a container. |
| RP5 | **A replay mints no new `event_id`** and changes no causation (R10, item 9 RA8, A57). A genuinely new business attempt is a **new message with a new `event_id`**, whose TCE is captured by the ordinary producer rules with the *current* context — that is not a replay (item 9 RA9). |
| RP6 | **A replay reaches only the consumer being replayed** (R10, item 9 RA5a/RA5b/RD7). No sibling consumer's delivery record, processing span or TCE copy is touched, and no sibling is re-invoked (item 9 C83, unchanged). |
| RP7 | The replay's operational trace identifier belongs in **item 9's replay audit record** (RA4) and, if useful, in the delivery's operational trace context (CN8). It is **never** written into the message's TCE and never into the message row (RP1). |
| RP8 | A replayed delivery that is still invalid returns to quarantine (item 9 RD2); a replayed delivery that already completed produces no second effect (item 9 RD3). Neither outcome changes any TCE value. |
| RP9 | If the original trace's data has expired from the tracing backend, the link simply resolves to nothing. **The durable identifiers still reconstruct the chain from PostgreSQL** — which is exactly why `request_id` and `causation_event_id` are durable rather than trace-only (RQ10, CZ3, C98). |
| RP10 | The OpenTelemetry API used to express a link, and the span/attribute naming, are **Phase 1's**. Item 10 freezes the semantics: new trace, linked, never rewritten, never re-parented. |

### 19.3 Why not the alternatives

| Alternative | Rejected because |
|---|---|
| Rewrite the message's TCE to the replay's context | Destroys the historical lineage the fields exist for; contradicts R8 and item 9 RA7, which preserve every other message field byte-for-byte; makes the second replay of the same message unable to see the first. |
| Parent the replay span into the original trace | Misrepresents chronology; hides the replay from the operation that caused it; depends on trace retention the platform does not guarantee; makes a months-old trace grow new children indefinitely. |
| Give the replay no trace at all | The replay is exactly the operation an operator most needs to observe: who ran it, when, over which deliveries, with what outcome (item 9 RA4). |

### 19.4 Child messages emitted during a replay

| # | Rule |
|---|---|
| RP11 | A child message emitted by a replayed handler is a **new message**, produced **now**. Its `trace_id` and `producer_span_id` are the **replay** trace and the replay processing span (TR4, PC11, PC12) — because that is where and when it was genuinely produced. |
| RP12 | Its `request_id` is **inherited from the message being handled** (RQ2, PC13), because that value identifies the origin request of the *causal chain*, not the trace of the production. This asymmetry between `trace_id` and `request_id` is deliberate and is the clearest demonstration of RQ10. |
| RP13 | Its `causation_event_id` is the handled message's `event_id`, exactly as in normal handling (PC14, CZ5). **A replay never changes causation.** |
| RP14 | Emitting a child during a replay is not a rebroadcast and does not violate RP6: the child is a new fact travelling the normal Outbox path to *its own* declared consumers, not a re-delivery of the parent to the parent's siblings. Where a handler's effect idempotency means the child was already emitted on the original run, item 8 §21's effect-idempotency mechanism prevents the second emission — item 10 adds no rule there. |

---

## 20. Trace, causation, chronology, identity and version are distinct

| Concept | Field | Means | Is never |
|---|---|---|---|
| Trace lineage | `trace_id` | the trace containing this message's production | identity, ordering, uniqueness, a partition key |
| Tracing parent context | `producer_span_id` | the span active when the durable record was written | a consumer's span, a parent of the producer, mutable |
| Origin request correlation | `request_id` | the originating synchronous request of the chain, where one exists | actor identity, authorization, a business correlation key, ordering, unique per message |
| Immediate durable causality | `causation_event_id` | the `event_id` of the message whose handling emitted this one | ordering, authorization, idempotency, a foreign key, an ancestry list |
| Message identity | `event_id` (item 8 §9) | this emission | a broker delivery id, a trace id, reusable |
| Business fact time | `occurred_at` (item 8 §11) | when the fact became true | publication, delivery or handling time; an ordering key |
| Payload schema version | `schema_version` (item 8 §14) | which payload contract | a source version, a revision, an ordering key |
| Projection freshness | `source_version` (**item 12**) | item 12's stale-update guard | anything item 10 defines, names or constrains |
| Operational routing | consumer failure domain (**item 9**) | where a consumer's work runs and fails | a message property, a producer choice, a TCE field |

| # | Rule |
|---|---|
| DX1 | **No two of the nine are interchangeable**, and none may be substituted for another in code, in a query, in a dashboard or in reasoning. |
| DX2 | **None of the nine is an ordering counter.** Ordering assumptions are forbidden by item 8 OR1–OR6 and are not rehabilitated by any TCE field. |
| DX3 | Item 10 defines **no** `source_version`, no revision, no monotonic counter and no staleness guard, and may not be cited as authority for one (item 8 OR7, item 9 A59, A67). |
| DX4 | Item 10 defines **no** concrete identity type. `causation_event_id` is "whatever `event_id` is" (CZ4, R16). |

---

## 21. The correctness firewall

| # | Rule |
|---|---|
| FW1 | **Trace, request and causation metadata never decides**: authorization; authentication; actor identity; money; stock; reservation state; payment state; order placement; idempotency; duplicate detection; schema compatibility; retry classification; queue routing; stale-projection acceptance; event ordering; or whether a message is valid. |
| FW2 | **A valid business message is always processable regardless of its trace metadata.** Absent, partial, malformed or contradictory trace context never blocks, delays past normal handling, quarantines or fails a message whose *contract* is valid (PR1, PR5, SR3). |
| FW3 | **Losing trace continuity is an observability defect only** (R4, master `# 23.3`): it is measured, alerted and fixed; it is never a TF-A retry reason, never a TF-C quarantine, never a TF-B rejection and never a business error (item 9 §17, unchanged). |
| FW4 | **No handler branches on a TCE value.** No conditional, no policy, no selector filter, no authorization check and no idempotency key reads `trace_id`, `producer_span_id`, `request_id` or `causation_event_id` (A63, item 8 CA5). |
| FW5 | **A trace or request identifier is never an idempotency key, a deduplication key or a dedupe fingerprint.** Item 8 §21's identity model — first-seen `event_id`/type/version/payload fingerprint per consumer — is unchanged and unextended. |
| FW6 | **A `request_id` is never an actor, a principal or a permission.** Protected async work reconstructs the actor at the transport boundary or runs under an explicit system context (item 8 SEC7, ADR-0006, item 4 §11), never from observability metadata. |
| FW7 | **Causation is never ordering and never a prerequisite.** A message is processed without its parent existing, without its parent having been processed first, and without any sibling having been processed at all (CZ7, CZ10). |
| FW8 | **An observability outage changes nothing commercially**: a collector, exporter, sampler or tracing backend that is unavailable, misconfigured or disabled has no effect on whether an Outbox row is written, whether a consumer runs, or what the business outcome is (§23, C97). |
| FW9 | The firewall is **testable**, not aspirational: C91, C92, C93, C97 assert it directly, and A63 makes the code-level violation a build failure. |

---

## 22. Security and privacy

| # | Rule |
|---|---|
| PV1 | **No personal data in the TCE.** The four fields are opaque identifiers by construction: no email, phone, name, address, user identifier, cart or order content, price, token, cookie, session identifier or credential, in any of them, in any encoding (R15, item 8 SEC2, SEC3). |
| PV2 | `request_id` in particular **encodes no identity and no derivation of identity** (RQ7). An edge-minted value is opaque and random. A scheme that embeds a user or session identifier in it turns every log line and every durable row into a personal-data record (master `# 23.1`, `# 21`). |
| PV3 | **No OpenTelemetry baggage is persisted** into Outbox, Inbox, quarantine or dead-letter records (§10.3). Baggage carries arbitrary upstream key/value data and is a durable leak channel by design. |
| PV4 | **No `tracestate` or vendor tracing blob is persisted** without a specific bounded need, a named justification and a new ADR (§10.3, FS7). |
| PV5 | **Inbound trace context is untrusted input.** It is validated for shape and bounded in length (PR4); it is never trusted for authorization, authentication, identity, rate-limit exemption or replay-window decisions (FW1, CN12). |
| PV6 | Whether an inbound `traceparent` is **adopted** at a given entry point is a trust-boundary decision: adoption is appropriate for an authenticated peer, a verified provider webhook or the platform's own reverse proxy, and is not the default for a public unauthenticated endpoint, where an attacker-supplied value would let an outsider colour internal traces. The specific policy per entry point is Phase 1 / operations, bounded by this rule; in every case adoption affects observability only (PV5). |
| PV7 | **Malformed incoming trace context is sanitized or dropped as trace context**, never treated as business input, never echoed into a payload, and never surfaced unescaped in an operator UI (PR4, PR5). |
| PV8 | **Logs, alerts and traces may reference `trace_id`, `request_id`, `event_id`, `causation_event_id`, `event_type` and `schema_version` freely** — these are the intended correlation keys and are exactly what master `# 23.1` requires on every line. Diagnosis must **not** require raw payload logging; payload content stays subject to redaction everywhere, quarantine displays included (R15, item 8 SEC8). |
| PV9 | **The TCE never becomes a durable data channel.** Any proposal to "just put a small field in the trace metadata" is a proposal to add a field to a closed set and requires a new ADR (FS1, FS7). |
| PV10 | Retention and erasure policy for durable trace metadata follows the owning table's retention (master `# 20.5`) and the privacy phases (master `# 21`). Item 10 freezes no numeric period. |

---

## 23. Sampling

| # | Rule |
|---|---|
| SM1 | **Sampling is observability policy only.** It governs which spans are exported and retained; it governs nothing else. |
| SM2 | A sampling decision **never affects**: whether an Outbox message is written; whether it is relayed; whether a consumer runs; whether an effect commits; idempotency; retry; terminal classification; or any business outcome (FW8). |
| SM3 | **The durable identifiers are persisted regardless of the sampling decision** (PC4). A message produced in an unsampled trace still records `trace_id` and `producer_span_id`, because durable correlation must survive a policy that only ever governed export. |
| SM3a | **The observability-neutrality invariant.** A collector, exporter, sampler or tracing-backend state — unavailable, failing, misconfigured or disabled — must leave the **TCE state that would have been captured without it** durably persisted, exactly (FS10). Concretely, such a state **must not turn a present TCE value absent, must not invent a value for an absent one, and must not change business processing**. For a first-hop message from an HTTP request that means the trace pair still follows the tracing context, `request_id` is still present and `causation_event_id` is still absent; for a child message it means `causation_event_id` is still present. This is the invariant C97 asserts — never "all four are non-empty", which PR9 shows is false for every first hop. |
| SM4 | **The sampled flag is not a durable TCE field** (§5.1). The relay applies the platform's *current* propagation and sampling policy when it constructs a carrier; a flag captured hours or months earlier is a stale decision, and persisting it would make retention policy leak into durable business rows. |
| SM5 | **Accepted cost of SM4:** a trace sampled *in* at the edge may have its asynchronous continuation sampled *out* under a later policy, so the exported trace can be incomplete. This is acceptable because (a) the durable identifiers still reconstruct the chain from PostgreSQL and from structured logs (RQ10, CZ3), and (b) master `# 23.3` already mandates 100 % or tail-based retention for checkout, payment, refund, webhook and reconciliation routes — the flows where completeness actually matters. |
| SM6 | **Exact sampling rates, tail-based rules and per-route policy are operations'** (master `# 23.3`). Item 10 freezes no percentage. |

---

## 24. The storage-before-partition invariant

| # | Rule |
|---|---|
| ST1 | **All four TCE fields must exist as columns on the Outbox and Inbox durable records from their initial Phase 1 schema and initial migration.** They are not a later addition. This is a requirement on the *schema*, not on the *rows*: every field is optional and many rows legitimately leave one or more empty (FS5, FS10, PR9), so the Phase 1 representation must be able to express absence. |
| ST2 | **No partitioning migration for Outbox or Inbox may be authored before that schema decision exists.** Master `# 20.2` partitions `OutboxEvent` by `created_at` and `# 20.3` partitions `InboxEventPayload`; adding a column across a partitioned, high-volume, actively-retained table afterwards is expensive, and every already-written row stays permanently blind. This ordering is the reason item 10 sits where it does in the roadmap. |
| ST3 | The same requirement extends to the **quarantine and operational dead-letter** records (§25), so a terminal record is diagnosable on its own. |
| ST4 | **Future partition keys, indexes, column types and retention windows are not designed here** (§1.2). Only the *existence* of the fields on the initial schema is frozen. |
| ST5 | **No TCE field is a partition key, a clustering key, an ordering key or a uniqueness constraint** (DX2, TR5, RQ9). Whether any of them is *indexed* for diagnostic lookup is a Phase 1 decision driven by measured query patterns. |
| ST6 | No SQL, DDL, model or migration is written in Phase 0. |

---

## 25. Terminal records and diagnosability after broker loss

| # | Rule |
|---|---|
| TM1 | A **contract quarantine** record and an **operational dead-letter** record (item 9 §22, §23) each **retain or durably reference** the message's TCE state as emitted — absences included (FS10) — alongside item 9's required content: the message identity, the failed **consumer** (item 9 DL16, DL17), the terminal kind and the origin domain. |
| TM2 | This is item 9 TD5–TD8's sufficiency requirement extended to trace: a terminal record must be diagnosable **after the broker's data is gone**, after the source Outbox partition has been archived (master `# 20.2`, `# 20.5`), and after the tracing backend's retention has expired (C98). |
| TM3 | "Durably reference" is satisfied by retaining the values, or by referencing a retained record that holds them for at least as long as the terminal record lives. A reference whose target expires first does not satisfy TM1. |
| TM4 | A terminal record's own **operational** context — when it was quarantined or dead-lettered, by which attempt, and the replay operations performed against it — is delivery/operational state (CN8, item 9 RA4), never written into the message's TCE (RP7, FS6). |
| TM5 | Redaction applies to what a terminal record **displays**, not to whether it is retained (item 8 SEC8, PV8). The four TCE fields are correlation identifiers and are not redacted. |
| TM6 | Terminal-record physical schema, retention and tooling remain **Phase 1 / operations'** (item 9 §39). |

---

## 26. Envelope, not payload

| # | Rule |
|---|---|
| EV1 | The TCE is **envelope metadata**. It is not payload, not part of any registered payload schema, and not part of any `(event_type, schema_version)` contract (FS4). |
| EV2 | **Item 10 never bumps a payload `schema_version`.** Adding, renaming or removing a TCE field does not bump any message's version, and no registry entry changes because of this artifact (item 8 SV2, SV7, CA4, R2). `schema_version` is not redefined here in any respect. |
| EV3 | **No payload field is named** `trace_id`, `span_id`, `producer_span_id`, `parent_span_id`, `request_id`, `correlation_id`, `causation_id`, `causation_event_id`, `traceparent`, `tracestate` or `baggage`, and no payload field carries those values under another name (A61, item 8 EN11). |
| EV4 | Item 8 EN7's prohibition survives intact: the envelope is EN1's four fields plus FS1's four, and nothing else. FS2 records that the reserved extension point is now spent. |
| EV5 | Because every TCE field is absence-tolerant (FS5), a durable record written before or after any future TCE change remains readable, so **no envelope version field is introduced**. Introducing one would require the ADR item 8 CA4 already anticipates (FS7). |
| EV6 | Item 10 adds **no column to the event registry** and no consumer-declaration attribute (FO7). The registry's immutable/mutable split (item 8 §26.1) and ADR-0010's single operational addition stand unchanged. |

---

## 27. Failure matrix

**Business correctness** is assessed against the frozen invariants: no order, payment, reservation,
inventory or projection outcome may depend on trace metadata (FW1, FW2).

| # | Situation | Business correctness | Durable trace/cause state | Processing-span behaviour | Operator-visible defect / recovery |
|---|---|---|---|---|---|
| 1 | Normal HTTP → Outbox → consumer | Unaffected | TCE state captured at INSERT (PR9, first-hop-from-request row): trace pair present, `request_id` present, `causation_event_id` **absent** — there is no parent durable message yet | Consumer span is a child of `(trace_id, producer_span_id)` | None; master `# 20.7`'s target trace assembles |
| 2 | Scheduled / system origin, no HTTP request | Unaffected | Trace pair present; **`request_id` absent** (RQ3); causation absent | Root span in the job's own trace; consumer span is its child | None — absence is the correct state, not a gap |
| 3 | Handler emits a child message | Unaffected | Child: trace of its production, handler's span as `producer_span_id`, inherited `request_id`, `causation_event_id` = parent `event_id` (PC10–PC14) | Child production happens inside the consumer's processing span | None; the chain is one hop per row |
| 4 | Fan-out to N consumers | Unaffected | **One** TCE, read N times, mutated never (FO1, FO3) | N sibling processing spans under one production context | None |
| 5 | Relay runs after the originating process is gone | Unaffected | Restored **entirely from the durable row** (OB1–OB3) | Relay span links to the production context; consumer span parents to it | None; this is the designed case, not a degradation |
| 6 | Broker outage, delivery hours later | Unaffected — the business transaction committed with its Outbox row (item 9 BR1) | Unchanged; still complete on the durable row | Consumer span parents to the original production context, timestamped now | Relay-lag alert (master `# 23.3`); no trace action |
| 7 | Broker trace headers missing | Unaffected (FW2) | Unchanged; the durable record still has them | Durable values are used for parenting (SR1); if those are absent too, a new **root** span (SR4) | Observability defect counted; **never** quarantine |
| 8 | Broker trace headers malformed / all-zero | Unaffected | Unchanged | Carrier normalised to absent (PR4, PR5); parenting falls back to the durable record | Observability defect counted; **never** TF-C, never payload invalidity |
| 9 | Carrier disagrees with the durable record | Unaffected | Unchanged — **the durable record wins** (SR1) | Parented from the durable record | Observability defect + alert; investigate the relay/serializer (SR2) |
| 10 | Worker crash before the effect commits | No effect, nothing marked handled (item 8 HT2) | Message TCE unchanged; the attempt's operational context ends unfinished | The attempt's span ends with an error status | Normal TF-A retry (item 9 §17) |
| 11 | Retry after that crash | Exactly one effect (item 8 IX8) | **Unchanged** — no new `event_id`, `trace_id`, `request_id` or causation (TY2) | A **new** processing span for the attempt, sibling of the previous one; attempt number is a span attribute (TY3, TY4) | None |
| 12 | Replay of a failed consumer long after the original trace | Exactly one effect; identity preserved (item 9 RD3, RA7) | **Immutable** — the historical lineage is not rewritten (RP1) | Replay processing span in a **new** trace, **linked** to the original production context (RP2, RP3) | Replay audit record (item 9 RA4); if the original trace has expired, durable ids still reconstruct the chain (RP9) |
| 13 | Sibling consumer already succeeded while another is replayed | The succeeded sibling is **not** re-invoked (item 9 RA5b, C83) | Sibling's records and the message TCE untouched (RP6, FO5) | Only the replayed consumer gets a new span | None; item 9's model is unchanged |
| 14 | Trace collector / exporter unavailable | **Unaffected** (FW8) | Identical to the state that would have been captured with the collector up — no present value lost, no absent one invented (SM3a, PC4) | Spans are created and dropped at export; processing is identical | Observability alert; commerce continues |
| 15 | Sampling disabled or the trace sampled out | **Unaffected** (SM2) | Identical to the state that would have been captured under any other sampling decision; the trace pair is still recorded (SM3, SM3a) | Spans may not be exported | Possible incomplete exported trace (SM5, accepted); durable correlation intact |
| 16 | Terminal/quarantine diagnosis after broker data is gone | No business effect (already terminal) | Terminal record retains or durably references the message's TCE state as emitted, absences included, plus the **failed consumer** (TM1, TM2, FS10) | No span; the record is read, not executed | Full diagnosis from PostgreSQL alone; replay proceeds under item 9 §28–§29 |

---

## 28. Checks a later phase must implement

Continuing the numbering established by items 3–9 (`A59`, `C84`, `V73` were the last used).

### 28.1 Static / AST (`A` series)

| # | Check |
|---|---|
| A60 | **The TCE is closed.** Exactly `trace_id`, `producer_span_id`, `request_id`, `causation_event_id` exist as envelope trace metadata on the Outbox/Inbox/terminal records. No fifth envelope trace field, and no `meta`/`extra`/`context`/`attributes`/`headers`/`tags`/`dict[str, Any]`/JSON-blob/`baggage`/`tracestate` field beside them (FS1, FS3, §10.2, §10.3). |
| A61 | **No TCE name in a payload contract.** No registered payload schema or contract module declares a field named `trace_id`, `span_id`, `producer_span_id`, `parent_span_id`, `request_id`, `correlation_id`, `causation_id`, `causation_event_id`, `traceparent`, `tracestate` or `baggage` (FS4, EV3, item 8 EN11). |
| A62 | **One writer per trace column.** No code path outside message creation assigns a message's `producer_span_id` / `trace_id` / `request_id` / `causation_event_id`; specifically, no consumer, handler, relay, retry or replay path writes a span identifier into a message row, and the delivery's operational trace context is a **separate** target (SP3, CN3, CN4, PR2). |
| A63 | **No business branch on trace metadata.** No conditional, authorization check, policy, selector filter, idempotency key, dedupe key, ordering expression, routing decision or retry classification reads a TCE value (FW1, FW4, item 8 CA5). |
| A64 | **No trace parameter in a contract.** No `domains/<x>/public.py` or `application/<a>/public.py` signature, command input DTO, selector parameter or public DTO field carries a trace, span, request or causation parameter (FS9, PC7, item 4 §5). |
| A65 | **No observability network I/O inside a durable transaction or an emission path** — no collector, exporter flush, remote-sampler lookup or broker call between `BEGIN` and `COMMIT` of a business or handler transaction (PC2, R6). |
| A66 | **TCE fields are write-once.** No retry, replay, relay, reconciliation, admin action or management command mutates a message's TCE state or back-fills a field the emission left empty, and no emission site can produce `causation_event_id == event_id` (FS6, FS10, PR8, RP1, CZ6). |
| A67 | **No neighbouring item's vocabulary here.** This artifact and ADR-0011 define no `source_version`, revision or staleness guard (item 12); no failure domain, queue or routing value (item 9); no `event_type`, payload schema or `schema_version` semantics (item 8); and no concrete `PublicId`/`Money`/`event_id` type (item 11). A reviewer-runnable grep-level check on the artifacts themselves (DX3, DX4, §1.2). |

### 28.2 Behavioural / contract tests (`C` series)

| # | Test |
|---|---|
| C85 | **End-to-end propagation, first hop.** An HTTP request that places an order produces a durable Outbox record whose TCE state is exactly PR9's first-hop-from-request row: `trace_id` **present** and `producer_span_id` **present and paired with it** (the request being traced), `request_id` **present**, `causation_event_id` **absent** — because no parent durable message exists yet, and asserting it present would be wrong. End to end, unchanged: the consumer's processing span is a **child of `(trace_id, producer_span_id)`**, and the `request_id` observed at the consumer equals the one minted at the edge (PC1, CN2, RQ2, PR9, master `# 20.7`). |
| C86 | **System origin.** A scheduled/reconciliation-origin message matches PR9's system-origin row: trace pair present, **`request_id` absent** and **`causation_event_id` absent**; it is processed normally, and no synthetic request identifier or placeholder is minted anywhere (RQ3, PR6, CZ2). |
| C87 | **Child-message causation.** A message B emitted while handling A matches PR9's child row: `B.causation_event_id` is **present** and `== A.event_id`; `B.request_id == A.request_id`, **absence included** (so a child of a system-origin chain still has none); `B.event_id != B.causation_event_id`; and `B.event_id != A.event_id` (PC13, PC14, CZ6, PR9). |
| C88 | **Fan-out independence.** One `EVENT` with three declared consumers yields three distinct processing spans, one unchanged durable TCE, and no consumer's identifiers in another's delivery record or in the message row (FO1, FO3, CN3). |
| C89 | **Relay without the originating process.** With the producing process terminated and every in-memory context destroyed, the relay reconstructs the full carrier from the durable row alone, and the consumer parents correctly (OB1–OB3). |
| C90 | **Broker outage then delivery.** After a broker outage and a later drain, the message's TCE is byte-identical to what was committed and parenting is unchanged (item 9 BR1, OB2). |
| C91 | **Missing carrier context does not block.** A delivery whose transport trace headers were stripped is processed to a normal business effect; the durable values are used for parenting; the event is counted as an observability defect and is **not** quarantined (FW2, SR4). |
| C92 | **Malformed carrier context does not block.** A malformed, over-long or all-zero `traceparent` is normalised to absent, the message is processed normally, and the outcome is neither TF-C, nor payload invalidity, nor a business error (PR4, PR5, FW3). |
| C93 | **Carrier/durable disagreement resolves to durable.** With deliberately mismatched header and row values, the durable record's values are used and stored, the message is processed, and a discrepancy signal is recorded (SR1–SR3). |
| C94 | **Retry preserves message trace state.** Across N retries of one delivery, the message's TCE state and `event_id` are byte-identical — values **and** absences alike, so a retry neither fills an absent field nor empties a present one (FS10); each attempt has its own processing span; and no attempt number, retry count or worker identity appears in the envelope or the TCE (TY2–TY4). |
| C95 | **Replay preserves historical lineage and does not fake chronology.** Replaying a terminal delivery leaves the message's TCE state byte-identical, values **and** absences alike (asserted against the pre-replay row, FS10); it executes in a **new** trace, and records a link plus the original identifiers on the replay processing span rather than a parent-child edge into the original trace (RP1–RP4). |
| C96 | **Replay stays scoped to one consumer delivery.** Replaying consumer B never re-invokes consumer A — asserted by A's handler-invocation count, as in item 9 C83 — and leaves A's delivery record, A's operational trace context and the message's TCE untouched (RP6, FO5). |
| C97 | **Observability outage is commercially invisible and TCE-neutral.** With the collector unreachable, the exporter failing and sampling disabled, an order still places, the Outbox row is still written, the consumer still runs and the effect is identical; and the **persisted TCE state is the one that would have been captured without the outage** (SM3a, FS10) — asserted per origin against PR9, so a first-hop message still has `request_id` present and `causation_event_id` absent, and a child message still has `causation_event_id` present. No present value is lost and no absent one is invented (FW8, SM2, SM3, PC3, PC4). |
| C98 | **Terminal diagnosability after broker loss.** With the broker's data purged and the source Outbox partition archived, a quarantine record and an ODL record each still yield the message identity, the message's **TCE state as emitted** (absences preserved, not filled) and the failed consumer; a dangling `causation_event_id` whose parent has been archived is not an error, and an absent one is not a defect (TM1–TM3, CZ10, FS10). |
| C99 | **Envelope, not payload; and pair integrity.** No registered `(event_type, schema_version)` changes as a result of trace handling; a stored fixture with **all four TCE fields empty** still validates and is handled normally; and a record with exactly one of `trace_id`/`producer_span_id` present is read as untraced, processed, and flagged (EV2, FS5, PR2). |

### 28.3 Review-only (`V` series)

| # | Review item |
|---|---|
| V74 | A bare `span_id`, or any durable trace column whose meaning depends on which component last wrote it (§7.2, SP1). |
| V75 | A generic `correlation_id` reappearing under any name; or `request_id` promoted into a business correlation key, a workflow identifier or a join key in domain state (§10.1, RQ5). |
| V76 | A trace, span or request identifier used as actor identity, authorization input, idempotency key, deduplication key, retry identity or ordering key (FW1, FW5, FW6, TY5). |
| V77 | Causation used to derive ordering, to build an ancestry list or path, or as an invariant that the parent record must still exist (CZ3, CZ7, CZ10, §10.4). |
| V78 | OpenTelemetry baggage, `tracestate`, a vendor tracing blob or a free-form header map persisted into a durable record (§10.3, PV3, PV4). |
| V79 | Broker headers treated as durable truth, or a diagnosis procedure that stops working once broker data is purged (RL2, SR1, TM2). |
| V80 | A retry or replay that rewrites the historical trace/cause fields; a replay parented into the original trace as though it happened then; or a replay tool that writes its own trace into the message row (RP1–RP4, RP7, PR8). |
| V81 | A trace collector, exporter or sampler outage able to block, delay or alter commerce; or any code path that skips an Outbox write, a relay step or a handler because tracing is unavailable or unsampled (FW8, SM2). |
| V82 | An Outbox/Inbox partitioning migration authored before the TCE columns exist; a TCE field used as a partition, ordering or uniqueness key; or a terminal record that cannot be diagnosed on its own (ST1, ST2, ST5, TM1). |
| V83 | Personal data, session or user identity encoded into `request_id`; an unvalidated client-supplied trace header adopted at a public unauthenticated entry point; or trace metadata used to justify raw payload logging (PV1, PV2, PV5, PV6, PV8). |

---

## 29. Acceptance checklist

- [x] The trace/causality field set is **closed**: exactly four named fields (FS1, A60).
- [x] No free-form metadata, headers map, baggage or `tracestate` is persisted (FS3, §10.2, §10.3, A60).
- [x] The TCE is **envelope metadata, never payload** (FS4, EV1, EV3, A61).
- [x] Item 10 **never bumps a payload `schema_version`**, and `schema_version` is not redefined (EV2, R2).
- [x] The durable Outbox record carries context across process lifetime, restart, outage and deployment (OB1–OB3, C89).
- [x] The Inbox / consumer-delivery record preserves the original durable context (CN6, CN7, C98).
- [x] Trace and span semantics are unambiguous, with an absolute, writer-independent span name (TR1, SP1, §7.2).
- [x] Presence invariants are defined: pair rule, untraced production, malformed normalisation, no back-fill (PR1–PR8), and the canonical TCE state per origin (PR9).
- [x] "Four fields" means four **defined slots**, never four present values; no rule or test requires all four to be non-empty on any message (FS5, FS10, PR9).
- [x] An observability outage or sampling decision persists the TCE state that would have been captured without it — losing no present value and inventing none (SM3a, C97).
- [x] `request_id` semantics are explicit, including its absent case and its non-identity (RQ1–RQ10).
- [x] Immediate causation semantics are explicit, one hop, with no ordering, authorization or idempotency meaning (CZ1–CZ12).
- [x] A child message links to its immediate parent event (PC14, C87).
- [x] Fan-out creates independent per-consumer processing spans over one immutable TCE (FO1–FO5, C88).
- [x] Retry preserves the message's trace/cause metadata and creates a new span per attempt (TY1–TY6, C94).
- [x] Replay preserves the message's metadata byte-for-byte (RP1, C95).
- [x] Replay does not pretend to have occurred in the original chronology (RP2–RP4, C95).
- [x] Replay remains scoped to one consumer delivery; no sibling is rebroadcast (RP6, C96; item 9 unchanged).
- [x] Missing or corrupt transport context never blocks a valid business message (FW2, PR5, SR3, C91, C92).
- [x] Trace metadata is never authorization, identity, idempotency, ordering or routing truth (FW1, A63).
- [x] Sampling never changes correctness, and never suppresses durable identifiers (SM1–SM3, C97).
- [x] No arbitrary baggage, `tracestate` or PII is made durable (PV1–PV4, PV9).
- [x] Terminal records stay diagnosable after broker data is gone (TM1–TM3, C98).
- [x] No concrete item 11 identity type is invented (CZ4, DX4, A67).
- [x] No `source_version` vocabulary or mechanism is invented (DX3, A67).
- [x] No Celery, OpenTelemetry, Django, model, migration or dependency is created (§1.2, §24 ST6).
- [x] No contradiction with ADR-0001…ADR-0010, and neither ADR-0009 nor ADR-0010 is edited or superseded (§1.3, §31 row 12).
- [x] Item 8's reserved extension point is spent exactly once, and no second one is created (FS2, EV4).
- [x] Item 9's routing, terminal-state and replay model is used as written and amended nowhere (FO6–FO8).
- [x] ADR-0011 was genuinely required and records four decisions, not the artifact (§1.3).

---

## 30. Explicitly deferred decisions

| Deferred | Owner |
|---|---|
| The concrete `event_id` / `PublicId` type, and therefore `causation_event_id`'s representation; `Money` | **item 11** |
| `source_version` generation, per-source mapping, guarded projection upsert SQL | **item 12** |
| Whether async analytics exists at all | **item 13** |
| The MVP / later module cut | **item 14** |
| Outbox / Inbox / quarantine / ODL **physical** schemas: column names, SQL types, nullability encoding, indexes, partition keys, retention windows | Phase 1 (master `# 20.2`, `# 20.3`, `# 20.5`) |
| Whether any TCE field is indexed for diagnostic lookup, driven by measured query patterns | Phase 1 |
| Celery task headers, message serializer, broker configuration, routing and queue topology | Phase 1 (item 9 §39) |
| The OpenTelemetry SDK, propagator, exporter, span processor, instrumentation and the API used to express a span link | Phase 1 |
| The physical module owning ambient trace-context capture and restoration, and any `core` allowlist extension its placement implies | Phase 1 (PC9; ADR-0006's precedent) |
| Span names, attribute keys and semantic-convention set | Phase 1 / operations |
| Which peers and entry points may adopt an inbound `traceparent` in a given deployment | Phase 1 / operations, bounded by PV6 |
| Numeric sampling rates and tail-based rules; trace retention periods | operations (master `# 23.3`) |
| Alert thresholds and dashboards for trace-continuity and TCE-integrity defects | operations (master `# 23.2`, `# 23.3`) |
| Privacy retention and erasure rules for durable trace metadata | security/privacy phases (master `# 21`) |
| Provider-specific tracing headers and vendor trace correlation | the integration phases |
| Any change to the closed four-field set; persisting `tracestate` or baggage; an envelope version field | a new ADR superseding ADR-0011 (FS7, EV5, PV4) |

---

## 31. Self-review record

| # | Question | Verdict |
|---|---|---|
| 1 | Is `span_id` left ambiguous anywhere? | Pass — §7.2 states the failure mode explicitly, SP1 gives an absolute definition, SP3/CN3/A62 forbid a consumer ever writing it, and PC12 names the single place a consumer's span is recorded — as a *different* message's producer context. V74 is the review item. |
| 2 | Is trace context ever business input? | Pass — FW1 enumerates sixteen forbidden decisions, FW4 forbids any branch, A63 is the static check, and C91/C92/C93/C97 assert processing continues under every trace degradation. FS8 states the rule constructively: a value a handler would branch on is by definition not a TCE field. |
| 3 | Is a trace id ever an idempotency or dedupe key? | Pass — FW5 forbids it, TY5 forbids it for retry identity, DX1 forbids substitution generally, and item 8 §21's identity model is restated as unchanged and unextended. |
| 4 | Is causation ever ordering? | Pass — CZ7 states it directly, DX2 generalises it, FW7 makes independence testable, and §10.4 rejects the ancestry-path field precisely because it reads as a sequence. |
| 5 | Is `request_id` ever actor or security identity? | Pass — RQ4, RQ7, FW6, PV2 and V83. RQ8 handles the client-supplied case: validated, optionally adopted, never authoritative. |
| 6 | Is arbitrary baggage or a free-form header map persisted? | Pass — FS3, §10.2, §10.3, PV3, PV4, A60, V78. Persisting `tracestate` requires a bounded need *and* a new ADR. |
| 7 | Are broker headers ever durable truth? | Pass — RL2 demotes them to a carrier, SR1 resolves every conflict to the durable record, CN7 states why (broker data is transport and disappears), TM2 extends it to terminal records, and C93/C98 assert both. |
| 8 | Does anything require the original HTTP process to still exist? | Pass — OB1–OB3 are stated as a requirement, not an aspiration; OB3 declares the alternative non-conformant; C89 kills the producing process and asserts reconstruction from the row alone. |
| 9 | Do retries mutate durable trace fields? | Pass — TY2 forbids it, FS6 makes every field write-once, A66 is the static check, C94 asserts byte-identity across N attempts, and TY4 sends attempt metadata to the transport row and span attributes instead. |
| 10 | Does replay rewrite historical trace or cause fields? | Pass — RP1 forbids it, §19.3 records *why* both tempting alternatives were rejected, RP7 keeps the replay's own trace in item 9's audit record, PR8 forbids back-fill generally, and C95 asserts against the pre-replay row. |
| 11 | Does replay rebroadcast to sibling consumers? | Pass — RP6 restates item 9 RA5a/RA5b/RD7 without amending them, FO5 keeps siblings' records untouched, C96 asserts by handler-invocation count as item 9 C83 does, and RP14 explains why emitting a *child* during a replay is not a rebroadcast. |
| 12 | Can a trace collector outage block commerce? | Pass — FW8, PC2, PC3, PC4, SM2, SM3, and C97 asserts an identical business outcome with the collector down, the exporter failing and sampling disabled. Matrix rows 14 and 15 state it per situation. |
| 13 | Does item 10 define `source_version`? | Pass — no. DX3 and A67 forbid it, §20's table lists it as item 12's with an explicit "is never" column, and the phrase appears nowhere as a mechanism. |
| 14 | Does item 10 choose a concrete `event_id` type? | Pass — no. CZ4 defines `causation_event_id` as "whatever `event_id` is"; DX4, R16 and A67 keep the implementation with item 11. TR2/SP4 freeze only the W3C value spaces, which are trace-format facts, not identity-primitive decisions, and TR3 defers the DDL. |
| 15 | Is any Django, Celery or OTel code produced? | Pass — no package, module, model, migration, column, task, header name, propagator, sampler or dependency. Every code-shaped block is an illustrative text diagram. §1.2 and §30 name each deferral's owner. |
| 16 | Is `request_id` genuinely non-redundant with `trace_id`? | Pass — RQ10 and RP12 give the discriminating case: under replay, production genuinely happens in a new trace while the chain's origin request is unchanged, so the two values legitimately diverge. §5.1 records this as the adoption reason rather than "the master lists it". |
| 17 | Was a generic `correlation_id` rejected on evidence rather than taste? | Pass — §10.1 enumerates all five meanings it could carry, shows each is already carried, and states what remains: a one-entry metadata bag. RQ5 sends genuine business correlation to the owning contract, and FS7 leaves a precisely-defined future field possible under a new ADR. |
| 18 | Does anything move a matrix cell, add an import edge or extend a `core` allowlist? | Pass — PC6 places the TCE inside the envelope mechanism item 8 OW4 already assigned to `core.events`, which item 3 §4.2/§4.3 already allowlists. PC7/A64 keep trace out of every public signature, so no contract widens. PC8 uses item 3 §4.6's existing `interfaces`/`tasks` responsibility verbatim. PC9 leaves the physical capture module to Phase 1 and states that an allowlist extension, if its placement implies one, is recorded then — as ADR-0006 did — rather than pre-empted here. L1–L21 stand unedited. |
| 19 | Is item 9 reopened? | Pass — no. FO6–FO8 state it explicitly: no failure-domain, queue or routing field enters the envelope; no registry column and no consumer-declaration attribute is added; the terminal-state, retry and replay models are cited as written. §25 *extends* item 9 TD5–TD8's sufficiency requirement to the four fields without changing what item 9 froze. |
| 20 | Are ADR-0009 and ADR-0010 edited or superseded? | Pass — no. §1.3 records that item 8 EN6/CA3 reserved this decision in writing, so filling the extension point exercises a reserved right. Cross-references point *forward* from item 10; neither earlier ADR is touched. |
| 21 | Is the sampling decision honest about its cost? | Pass — SM4 rejects a durable sampled flag with a stated reason, SM5 names the resulting incompleteness as an accepted cost and gives the two mitigations, and SM6 leaves every number to operations. |
| 22 | Is anything here unenforceable by the mechanism it claims? | Pass — §28 splits honestly. A60–A67 are statically visible (a field set, a payload field name, an assignment target, a signature, a call inside a transaction). C85–C99 are behavioural because parenting, immutability across replay and "the collector is down but the order still places" are only observable at runtime. V74–V83 are review items because "is this really a correlation id" and "does this diagnosis still work when the broker is gone" are judgement, not lint. |
| 23 | Contradiction with ADR-0001…0010? | Pass — **0001/0002/0003:** untouched; no catalog, identity or projection rule changes. **0004:** PC8/R14 use §9's transport role as written; PC2/R6 keep §10's transaction rule. **0005:** §18 above; no cell, edge or allowlist moves. **0006:** FW6 reconstructs the actor through the existing primitive and adds no `core` vocabulary. **0007:** PC1 writes the TCE inside the *same* single placement transaction and adds no I/O to it; PC15 keeps provider interaction post-commit. **0008:** DX3/A67 leave the projection's freshness mechanism to items 6 and 12 entirely. **0009:** R1–R4, EV2 and FS2 use EN6/EN7/CA3/CA4/SV7 exactly as written; the envelope grows only into the point that ADR was written to reserve. **0010:** FO6–FO8 and §25 keep every transport, terminal and replay rule intact. |
| 24 | Does anything conflate "four defined fields" with "four present values"? | Pass, **after correction**. An earlier draft asserted in C85, C97 and failure-matrix rows 1, 14 and 16 that a message carried or persisted "all four TCE values", which contradicts PR1/PR6/PR7/CZ2 — a first-hop message *never* has a causation, and a system-origin one has neither causation nor `request_id`. FS10 now defines the four as **slots** and "TCE state" as the value-or-absence unit; PR9 tabulates the canonical state for all three origins; SM3a states the observability-neutrality invariant positively; C85 asserts `causation_event_id` **absent** on the first hop; C86 adds the system-origin absences; C97 asserts the would-have-been state per origin rather than non-emptiness; RL1, CN6, RP1, TM1, ST1, C94, C95, C98 and C99 were reworded to carry, retain and compare absences as first-class. No field, invariant, replay rule, sampling rule or ADR-0011 decision changed. |
