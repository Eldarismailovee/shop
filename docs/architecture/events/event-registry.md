# Asynchronous message registry

- **Status:** structure DONE / FROZEN — **no entries yet**
- **Governing contract:** [Phase 0 item 8](../phase-0/08-event-registry-versioning.md),
  [ADR-0009](../../adr/0009-event-contract-versioning.md)
- **Operational routing:** [queue / failure-domain matrix](queue-failure-domain-matrix.md),
  [Phase 0 item 9](../phase-0/09-queue-failure-domain-dlq.md),
  [ADR-0010](../../adr/0010-async-failure-domain-isolation.md)
- **Related:** master `# 20.1`–`# 20.7`, `# 23.3`, `# 24`

This file is the single index of every durable internal asynchronous message the platform emits
through the transactional Outbox and consumes through Inbox/idempotent handlers.

> **The registry indexes contracts. It owns none of them.** Each message type's meaning, payload and
> evolution belong to its semantic owner (item 8 §5). Adding a row here transfers no ownership, and a
> row that changes a contract without its owner's decision is invalid regardless of who wrote it.

**No message may be emitted unless it has a row here whose status permits emission** (item 8 RI11,
PE2). CI enforces this (check A42).

---

## 1. Scope

Governed (item 8 §4.1): durable internal asynchronous messages — domain business facts published for
asynchronous consumption, application workflow facts, projection-update triggers, and
integration-work triggers.

**Not** governed (item 8 §4.2): HTTP/DRF request and response bodies; `public.py` command and query
DTOs; external provider webhook wire payloads (raw maib / MIA / ERP / CRM / Chatwoot bodies); direct
synchronous calls; Redis cache entries; metrics, spans and logs; and Celery task argument formats as
an independent business contract.

When a provider webhook is translated into a durable internal message, **the provider wire schema and
the internal registered message are two separate contracts** with separate owners, identities and
versions (item 8 S11–S14). Provider vocabulary never becomes internal event vocabulary.

---

## 2. Entry columns

Every row records:

| Column | Meaning | Rule |
|---|---|---|
| `event_type` | Stable, lowercase, dot-separated, owner-qualified name. Never versioned in the name. | item 8 §8 |
| `schema_version` | Positive integer, starts at `1`, strictly increasing, never reused. | item 8 §14 |
| `kind` | `EVENT` (past-tense fact) or `COMMAND` (imperative work item). Fixed for the life of the type. | item 8 §7 |
| `status` | `DRAFT` / `ACTIVE` / `DEPRECATED` / `RETIRED`. | §3 |
| `semantic owner` | The single owning module. Identical across every version of the type. | item 8 OW1, RI2 |
| `payload contract` | Location of the **canonical** schema source, inside the owner's package, plus the generated versioned schema artifact derived from it. Nothing outside the owner imports the canonical source — the boundary is crossed by generated data (item 8 §6.3). | item 8 §27, §6.3 |
| `producer(s)` | Technical emitter(s). Equal to the owner unless a delegation is recorded. | item 8 RI9 |
| `consumers` | Each consuming module with **its own** declaration: the exact versions it supports, its **business-effect idempotency mechanism** — (a) / (b) / (c) — with the justification for it (§2.1), and its **logical failure-domain assignment** (§2.2). For a `COMMAND`, exactly one such declaration, the single handling owner. | item 8 §17, KD3, IX13–IX15; item 9 RT3 |
| `introduced` | Date and phase. | — |
| `emitted in production` | Whether current production code emits this version. | — |
| `exposure` | `internal-only` or `externally-consumed`. Governs which identifiers are legal in the payload. | item 8 PD14 |
| `supersedes` | **Forward** lineage, declared once on the newly introduced row, including retire-and-introduce pairs. The reverse `superseded by` view is **derived** from registry data — a published row is never edited merely to add a back-pointer. | item 8 BC16, RM2, RM3 |
| `upcasters` | Registered `from_version → to_version` transformations for this type. | item 8 §18 |
| `notes` | Reason for the version; compatibility and migration notes; ordering/staleness handling; **privacy classification** (does the payload carry personal data, and which categories). | item 8 SR6, SEC6 |

### 2.1 The consumer declaration is per consumer

Business-effect idempotency is chosen **per consumer/handler**, never once for the whole
`(event_type, schema_version)` entry (item 8 IX10, IX13). For every declared consumer of every
`ACTIVE` or `DEPRECATED` version the registry records:

```text
consumer
  → exact supported version(s)
  → business-effect idempotency mechanism: (a) | (b) | (c)
  → justification
  → logical failure-domain assignment                          [item 9, §2.2]
```

An **`EVENT`** may have several independent consumers, and different consumers of one version may
legally choose different mechanisms — each performs its own effect (item 8 IX14). A **`COMMAND`** has
exactly one handling owner, so its consumer declaration naturally contains exactly one handler (item 8
IX15).

The **message-identity integrity** obligation is separate and does not vary per consumer: every
consumer retains first-seen `event_id`, `event_type`, `schema_version` and canonical payload
fingerprint regardless of which effect mechanism it chose (§8, item 8 IX16).

### 2.2 The failure-domain assignment is **per consumer**, and operational

A failure domain describes a *handler's* work and its dependencies, so — exactly like the
effect-idempotency mechanism of §2.1 — it is declared **per consumer**, never once for the whole
`(event_type, schema_version)` row. There is **no entry-global `failure domain` column**.

```text
one EVENT instance E, one event_id

  consumer A  → notification handler  → ext.email
  consumer B  → CRM handler           → ext.crm
  consumer C  → local state handler   → core.<domain>
```

All three receive the same fact with the same `event_id` and retain it unchanged; their handler
executions belong to three different failure domains, because a mail provider outage, a CRM outage and
a local state transition share no blast radius.

**A declared consumer may not receive production deliveries without a valid assignment** to a domain
that exists in the [queue / failure-domain matrix](queue-failure-domain-matrix.md) and has a
normal-processing path (item 9 RT8, RX1; check A51).

```text
event registry               → contract / owner / versions
                               + per consumer: supported versions,
                                               effect idempotency + justification  [item 8]
                                               failure-domain assignment           [item 9]

queue-failure-domain matrix  → isolation, capacity, criticality, retry class,
                               terminal destination, replay authority, runbook owner
```

| Rule | |
|---|---|
| A **`COMMAND`** has exactly one handling owner and therefore exactly one assignment. An **`EVENT`**'s consumers may — and often should — be assigned to different domains. | item 8 KD2, KD3; item 9 RT4 |
| An **`EVENT` with zero declared consumers has no assignment and needs none.** Item 8's zero-consumer allowance is unchanged; a consumer added later must receive a valid assignment before it may take production deliveries. | item 8 KD2; item 9 RT5 |
| The assignment is **mutable operational metadata on the consumer declaration** (§4.1), never part of the immutable contract half. | item 9 RX2 |
| **Changing one consumer's assignment never bumps `schema_version`**, never creates a new `event_type`, never re-declares supported versions and never alters an effect-idempotency mechanism. It may require a rollout order and a runbook — drain the old route, or accept dual consumption during the window — recorded in the entry's notes. It never affects another consumer of the same message. | item 8 §26.1; item 9 LY3, RT6, RT11, RX3 |
| The registry names the **domain**, never a queue, exchange, routing key, priority, retry schedule or concurrency number. Those live in the matrix and in Phase 1 configuration. | item 9 RT10, RX4 |
| **A producer never selects a failure domain.** A semantic owner emits a fact; where it is handled is a consumer-side operational fact. Eligibility in the matrix is about the **consumer handler**, not the producing module. | item 9 RT12 |
| The matrix names **no `event_type`**. It describes workload categories; consumer declarations point at it, not the reverse. Routing a consumer into a domain gives that domain's operational owner an on-call responsibility, never contract authority. | item 9 RX5, RX6 |

The exact serialization of a consumer declaration is **not** frozen — only that it carries item 8's
support and effect-idempotency metadata and item 9's routing assignment, and that editing the routing
assignment alone is an operational edit.

---

## 3. Statuses

| Status | Emittable? | Consumer support | Contract |
|---|---|---|---|
| `DRAFT` | **No.** No durable row of this version may exist anywhere. | Not yet required. | Still editable — that is what `DRAFT` is for. |
| `ACTIVE` | Yes. | **Mandatory** for every declared consumer. | **Frozen.** |
| `DEPRECATED` | **No** — no producer may newly emit it. | **Still mandatory**: it can still legitimately arrive from backlog, retry, DLQ or partition replay. | Frozen. |
| `RETIRED` | **No.** | May be removed. An arrival of a retired version is quarantined as an unknown version. | Frozen; the schema is retained as long as an archived message could still be read. |

Transitions are **one-way**: `DRAFT → ACTIVE → DEPRECATED → RETIRED`. A retired version is never
revived — the answer is a new version. Retirement requires recorded **proof** that no retained,
queued, quarantined or replayable message of that version remains (item 8 PE7, RR3, RG6).

`DEPRECATED` is not a soft delete. It is a live obligation on every declared consumer.

---

## 4. Invariants

Enforced by review and by CI checks A42–A50 (item 8 §33.1):

| # | Invariant |
|---|---|
| RI1 | `(event_type, schema_version)` is unique. |
| RI2 | Exactly one semantic owner per `event_type`, identical across all its versions. |
| RI3 | An `event_type` is never reused for a different semantic fact, including after retirement. |
| RI4 | A published `event_type`'s semantic owner is **immutable and never edited in place** (§4.1). Moving responsibility is a retire-and-introduce under a new owner-qualified name; where the move changes a frozen module or domain boundary it additionally requires an ADR. |
| RI5 | `schema_version` starts at `1` and strictly increases within a type. |
| RI6 | Version numbers are never reused, including after retirement. |
| RI7 | At most one `ACTIVE` emission version per (technical producer, `event_type`), unless a migration exception with an explicit end condition is recorded in the entry. |
| RI8 | A published version's **contract columns** are immutable; its **operational columns** evolve under their own rules without changing what the version means (§4.1). |
| RI9 | One semantic owner; a second technical producer only by explicit, recorded delegation naming the delegate, the reason and a review date. Accidental multi-producer semantics is a modelling error. |
| RI10 | No `RETIRED` and no `DRAFT` version is emitted. |
| RI11 | No unregistered message is emitted. |
| RI12 | `kind` is fixed for the life of a type. |
| RI13 | Every `ACTIVE` and `DEPRECATED` entry names its exposure classification, and **every declared consumer of it** names its own business-effect idempotency mechanism with a justification — one mechanism stated for the whole entry does not satisfy this (item 8 IX13). **Neither an entry nor a consumer declaration may claim message-identity integrity detection is unavailable** — it binds every consumer unconditionally (item 8 IX2, IX5, IX6). |
| RI14 | Every `ACTIVE` and `DEPRECATED` entry has a complete consumer list for the versions still requiring support, and **every listed consumer that may take production deliveries names a valid failure domain** (§2.2, item 9 RT8; check A51). An `EVENT` with no declared consumers is not thereby invalid (item 8 KD2, item 9 RT5). |
| RI15 | Every registered upcaster references two registered versions of the same type, with `from_version < to_version`. |

### 4.1 Immutable contract vs mutable operational metadata

An entry carries a contract and an operational record. They are governed differently (item 8 §26.1).

**Immutable from publication:** `event_type`, `schema_version`, `kind`, `semantic owner` for that
type, the canonical payload contract/schema for that version, its **payload field semantics**,
`exposure` for that version, and `introduced`. A published payload schema never changes — the answer
is always a new version (item 8 §15, §16).

**Mutable, audited, and never a change to the payload schema:** `status` (one-way transitions only),
current consumer support declarations, registered `upcasters`, `notes` including retirement proof,
the current `emitted in production` state, **each consumer's failure-domain assignment** (§2.2),
technical-producer delegations **only** under RI9's explicit recorded-delegation rule, and each
consumer's effect-idempotency mechanism declaration **only** while the semantic effect contract is
unchanged.

**Lineage is declared forward, once, on the new row** (`supersedes`); the reverse `superseded by` view
is derived from registry data. A published row is never edited merely to add a back-pointer, and any
stored reverse pointer is mutable derived metadata, not contract schema (item 8 RM2, RM3).

**The semantic owner cannot change in place.** `event_type` is owner-qualified, so an edited owner
column would contradict the name itself. If responsibility genuinely moves:

```text
deprecate → retire the old owner-qualified event_type
→ introduce a NEW owner-qualified event_type at schema_version = 1
```

An ADR is separately required when the move changes a frozen module or domain boundary — it
authorises the re-homing, never an in-place edit (item 8 RM4, RM5).

---

## 5. Registered messages

**None.** Phase 0 freezes the contract discipline and deliberately invents no catalogue (item 8 RG8).

Each owning module registers its own messages in its own implementation phase, following §6.

| `event_type` | `ver` | `kind` | `status` | owner | payload contract | producer(s) | consumers (+ per-consumer effect idempotency **and failure domain**) | introduced | in prod | exposure | supersedes | upcasters | notes |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| _(no entries)_ | | | | | | | | | | | | | |

### 5.1 Row shape — illustrative, **not** a registered message

The following is a formatting example only. `inventory.reservation_changed` is **not** a registered
message, is not owned by anyone, and must not be emitted or implemented on the strength of this
block.

```text
event_type            inventory.reservation_changed
schema_version        1
kind                  EVENT
status                DRAFT
semantic owner        domains/inventory
payload contract      <owner-internal canonical schema source>        (item 8 §27)
producer(s)           domains/inventory
consumers
  <module-a>          supports: {1}
                      effect idempotency: (a) Inbox/event_id completion dedupe
                      justification: the effect is not idempotent by construction
                      failure domain: <domain from the queue matrix>  (item 9 §2.2)
  <module-b>          supports: {1}
                      effect idempotency: (b) domain uniqueness
                      justification: <why the effect is naturally idempotent>
                      failure domain: <a DIFFERENT domain is legal here> (item 9 RT4)
                      (message-identity retention is mandatory for both, item 8 IX2/IX6/IX16)
introduced            <date> / Phase <n>
emitted in production no
exposure              internal-only                                   (item 8 PD14)
supersedes            —
upcasters             —
notes                 no personal data; ordering handled by the owning state machine
```

---

## 6. How to register a message

1. **Confirm the owner.** The semantic owner is the module that owns the *fact*, not the module that
   wants to react to it (item 8 OW1, OW8). If two modules both seem to own it, it is either two facts
   or one that is homed in the wrong place.
2. **Pick the kind.** Past-tense fact with independent reactors → `EVENT`. Imperative work item with
   exactly one handler → `COMMAND` (item 8 §7).
3. **Name it.** `<owner>.<fact_in_past_tense>` or `<owner>.<imperative>`; lowercase; no version
   suffix, no module path, no class name, no queue name, no vendor name (item 8 §8).
4. **Author the canonical schema** in the owner's package — exactly one canonical source, everything
   else generated (item 8 §27). Apply the payload discipline of item 8 §12 and the snapshot-vs-
   reference rule of §13.
5. **Add a `DRAFT` row here** with every column filled, including exposure, the privacy
   classification, and — per consumer — the intended business-effect idempotency mechanism with its
   justification (§2.1).
6. **Assign a failure domain to each declared consumer** from the
   [queue / failure-domain matrix](queue-failure-domain-matrix.md). No consumer may take production
   deliveries without one (§2.2); an `EVENT` with no consumers yet needs none. Different consumers of
   one `EVENT` may legitimately name different domains. If no existing domain suits a consumer, add
   one by the matrix's own procedure — never route critical work into a best-effort domain to avoid
   provisioning one (item 9 RT4, RT5, NX4, NX5).
7. **Deploy consumer support first** (item 8 PE5 step 2), then promote to `ACTIVE` and switch the
   producer.

### 6.1 Introducing a new version of an existing type

A new `schema_version` is required for **any** change to a published payload contract, additive
changes included — field addition, removal, rename, type change, requiredness change, identifier
semantic change, enum change, unit/currency/time semantic change, meaning change, collection-order
change, and payload splitting or merging (item 8 §16.1).

**A published `(event_type, schema_version)` is never edited in place.** If the *meaning of the fact*
changed rather than its representation, the answer is a **new `event_type`** starting at version `1`,
not `schema_version + 1` (item 8 §16.2).

Follow the frozen consumer-first migration sequence (item 8 PE5):

```text
1. Register vN+1 as DRAFT; review the contract with the owner.
2. Deploy consumers supporting BOTH vN and vN+1; verify support is live.
3. Promote vN+1 to ACTIVE; switch the producer. Mark vN DEPRECATED.
4. Drain the vN backlog; prove nothing of that version can still arrive.
5. Only then retire vN, and only then may a consumer drop vN support.
```

### 6.2 Retiring a version

Retirement requires **evidence**, recorded in the entry: no queued or unprocessed row of that version,
no quarantined instance awaiting replay, and no retained partition within the replay window that could
contain one (item 8 PE7, RR2, RR3). "We deployed a while ago" is not evidence. The version's schema
stays in the repository for as long as an archived message of that version could still need to be read
(item 8 RR4).

---

## 7. What a consumer must declare

Every consumer declares the exact `(event_type, schema_version)` pairs it supports, and that
declaration appears in the `consumers` column (item 8 §17).

- No consumer assumes "latest".
- No consumer decodes an unknown future version on a best-effort basis.
- No consumer treats an unknown version as the nearest known version.
- Support is satisfied either by a native handler or by a **registered upcaster** to a natively
  handled version (item 8 §18).

An unknown `event_type`, an unknown or unsupported `schema_version`, or a payload that is invalid for
a known version is **durably quarantined and alerted** — never ignored, never coerced, never marked
as successfully HANDLED, never retried indefinitely on the normal queue (item 8 §20). Once the
quarantine state has committed, the transport may terminally dispose of that delivery so it does not
hot-loop; that disposition is never a semantic completion, and the exact broker operation, queue and
DLQ topology is **item 9's** (item 8 §20.3).

Item 9 realises that topology and adds the distinction the operator needs: **contract quarantine**
(*"we cannot understand this message"*) is a different semantic state from an **operational
dead-letter** (*"we understood it; execution failed"* — retry bounds exhausted, a permanent provider
rejection, or a handler defect). Neither is ever called simply "failed", both are canonically durable
in PostgreSQL rather than in a broker DLQ, and each failure domain keeps its own terminal namespace
([queue matrix](queue-failure-domain-matrix.md) §7; item 9 §22–§24).

**Both terminal states are scoped to a consumer delivery, not to the message.** For a multi-consumer
`EVENT`, one consumer may succeed while another quarantines or dead-letters; each keeps its own state,
each terminal record names **which** consumer failed, and replay re-runs **only** that consumer —
never rebroadcasting to a sibling that already succeeded (item 9 §22.3, RA5a, RA5b).

## 8. What every consumer must retain

Independently of how its business effect is made idempotent, every registered consumer durably
retains, on first sight of an `event_id`, enough identity to verify later deliveries — conceptually
`event_id`, `event_type`, `schema_version`, a canonical payload fingerprint, and the processing or
terminal state it needs (item 8 IX2).

```text
same event_id + same type/version/payload   → ordinary duplicate delivery
same event_id + different type/version/payload
                                            → integrity violation
                                            → quarantine + alert
                                            → the conflicting delivery is never applied
```

This is mandatory for **every** consumer. Mechanisms (b) and (c) in a consumer's effect-idempotency
declaration make that consumer's *effect* idempotent; they never discharge this obligation, and
neither an entry nor a consumer declaration may claim the detection is unavailable (item 8 IX6,
IX11, IX16, RI13).
