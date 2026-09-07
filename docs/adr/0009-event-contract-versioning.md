# ADR-0009 — Event contracts: producer-owned, immutably versioned, consumed by exact version

- **Status:** Accepted — Frozen
- **Date:** 2026-09-05
- **Phase:** 0 — Architecture Freeze
- **Supersedes:** —
- **Related:** [ADR-0004](0004-four-layer-modular-monolith.md),
  [ADR-0005](0005-dependency-and-integration-wiring.md),
  [ADR-0006](0006-public-contract-primitives.md),
  [ADR-0007](0007-place-order-atomic-idempotent-boundary.md),
  [ADR-0008](0008-storefront-listing-projection.md),
  [Phase 0 item 8 artifact](../architecture/phase-0/08-event-registry-versioning.md),
  [asynchronous message registry](../architecture/events/event-registry.md),
  master `# 20.2`, `# 20.4`, `# 20.6`, `# 23.3`, `# 24`

## Context

The asynchronous contour is already required to be typed, versioned, durable, idempotent and
replay-safe (master `# 20`), and three frozen artifacts explicitly deferred the contract discipline
to Phase 0 item 8: item 4 §17.4 (event compatibility is a separate contract), item 5 EV4 (no event
name, schema or version is fixed by `place_order`) and item 6 UP4 (the projection update path names
no event).

What was undecided is everything that makes "versioned" mean something in practice:

- **Who owns an event contract.** Master `# 20.6` says all events are declared in `core/events`, with
  a `CatalogProjectBatch` dataclass as its example. Taken literally that puts catalog and storefront
  business vocabulary inside `core`, which fails ADR-0004 §2's admission test on its first clause and
  makes `core` the owner of every module's asynchronous language — the central-events-package shape
  that ADR-0004 §3 and ADR-0005 §7 exist to prevent. Every other frozen artifact keeps business
  vocabulary out of `core`; this one line is the exception, and it was written before the layering
  ADRs were.
- **What a version number means, and whether a published schema may grow.** These messages are
  durable and replayable across deployments (master `# 20.5`'s partition lifecycle). A row written in
  March and replayed in September must have exactly one interpretation, and nothing in the row says
  which code wrote it.
- **What a consumer must declare, and what happens to a message nobody understands.** Master `# 20.6`
  states the outcome for one case ("unknown version → DLQ + alert") and master `# 23.3` names the
  alert, but neither states the surrounding contract: whether a consumer may fall back, whether an
  unknown *type* or an invalid *payload* behave the same way, whether such a message may be
  acknowledged, and what prevents it from hot-looping.

Left undecided, each of these resolves itself the cheap way at the moment code is written: a shared
events package because it is the only place both sides can import from; an optional field added to
v1 because "it's additive"; a consumer that handles `>= 1` because that is one line shorter. Each is
individually defensible and collectively fatal to replay.

The additional constraint that shaped the answer: **a consumer cannot import a producer's contract at
all.** Domains are mutually invisible (ADR-0004 §3), `application → domains` is `PUBLIC ONLY` and
`application → application` is forbidden (ADR-0005 §7), and item 4 §5's eight `public.py` export
categories do not include an event contract. Any design in which the two sides share a Python type
requires either a shared package with no owner or a widened frozen list.

## Decision

### 1. The payload contract of a message is owned by the producing module; `core` owns only mechanism

Every registered message type has **exactly one semantic owner**, and ownership follows the fact:
a domain business fact is owned by that domain, an application workflow fact by that application
module. The owner is the only party that may version, deprecate or retire the contract; a consumer
never edits it.

> **`core.events` owns the mechanism — the envelope, the registry lookup/dispatch, the codec, the
> validation machinery and the structural contract-failure signalling. It owns no business message
> type, and no message payload contract lives in `core`.**

There is no `domains/events`, no `application/events`, no shared `contracts/` or `messages/` package.
Per-owner contract modules are expected and stay **internal to the owning package**, exactly as its
ORM and services do (ADR-0005 §7). Transport packages are never owners and never producers:
`interfaces/*` cannot emit at all (ADR-0005 §1 / item 3 L13), `tasks/*` never authors a payload
(ADR-0004 §9), and `integrations/*` cannot reach `core.events` (item 3 §4.5).

This **changes the placement** master `# 20.6` states and **preserves every requirement** it states:
declared and typed messages, `event_name` + `event_version` on every row (frozen here under the
logical names `event_type` + `schema_version`, mapping 1:1 onto whatever Phase 1 names the columns),
consumers registering supported versions, unknown version → DLQ + alert with no silent fallback,
explicit `v1 → v2` upcasters rather than conditional interpretation of old JSON, and deterministic
replay of old partitions.

### 2. The asynchronous boundary is a data boundary, never an import boundary

> **A consumer never imports a producer's message contract. What crosses is a serialized,
> registry-described payload; the consumer validates it against the registered schema and
> materialises its own internal representation.**

This is not a preference — it is the only shape the already-frozen matrix permits (see Context), and
it is also the only one that survives replay of a row written by code that no longer exists.

The canonical contract stays **owner-internal**, and any schema representation consumed outside the
owner crosses the package boundary as generated, versioned **data**:

```text
owner-internal canonical schema source
  → deterministic build/generation step
  → checked-in, versioned schema artifact/data
  → core.events validator / registry mechanism
  → consumer validation
```

The generated artifact is derived, never a second hand-maintained source of truth, and it is checked
in so an old version stays decodable after its producer's code has changed. If a typed Python
contract is canonical, the generated JSON-compatible schema data must be versioned alongside it; if a
data schema is canonical, it is used directly and other representations are generated from it. The
format and tooling are Phase 1's; the pipeline is not.

**The composition root may not import an owner-internal message contract.** `config/ → domains/<x>`
is `PUBLIC ONLY` and `config/ → application/<a>` reaches only `public.py`/`ports.py` (ADR-0005 §3,
§7); a message schema is deliberately owner-internal and is **not** a `public.py` export. Registering
owner schemas by importing them at startup is therefore not an admissible realisation, and this ADR
requests no matrix exception for it. The binding constraint on every realisation: **no consumer →
producer import edge, no dependency-matrix cell moves, no widened `public.py` export list, and no
shared business-message Python package.** The registry may be documentation and machine-readable data
used for validation; it must not become a backdoor import graph.

### 3. Stable `event_type`, separate integer `schema_version`

`event_type` is a stable, lowercase, dot-separated, **owner-qualified** name whose first segment is
the owning module. It never encodes a version (`something_v2` is forbidden), never contains a module
path, class name, broker/queue name or transport word, and never carries vendor vocabulary — a
provider name may appear only in a later segment of a genuinely provider-specific fact, never as the
first segment. Once published, a type's meaning is immutable and a retired type is never reused.

`schema_version` is a positive integer starting at `1`, strictly increasing within a type, never
reused. **Semantic-version strings are forbidden**: the only distinction the system can act on is
"this consumer supports this exact contract, or it does not".

The registry carries a mandatory `kind` discriminator, `EVENT | COMMAND`, because the platform
demonstrably carries both a past-tense fact with independent reactors and an imperative bounded work
item with exactly one handler through the same Outbox. One registry with one column was chosen over
an event-only registry (which would have to call a batch work item an "event") and over two parallel
registries (which would duplicate every rule below and then diverge). Every rule here applies to both
kinds. No `core` enum, package or runtime type is introduced for it.

### 4. A published `(event_type, schema_version)` is immutable — additive change included

> **Once a version leaves `DRAFT`, its field set and its field semantics are frozen. Even a purely
> additive, optional field produces a new `schema_version`.**

The tempting alternative — optional additive fields on the same version — was rejected for a specific
reason: under it, `(type, 3)` means two different things depending on when the row was written, and
nothing in the row says which, so the consumer must infer from field presence. That is exactly the
"conditional interpretation of old JSON" master `# 20.6` forbids, and it also forces the validator to
accept both shapes forever, which stops it catching the producer bug it exists to catch.

A new version is required for field removal, rename, type change, requiredness or default change,
identifier semantic change, enum change, unit/currency/precision/time semantic change, meaning change
of an existing field, collection-semantics change, payload splitting or merging, and any addition.
**An already-published version is never mutated in place.** If the *meaning of the fact* changed
rather than its representation, the answer is a **new `event_type`** starting at version `1`, not
`schema_version + 1`.

**The cost is accepted deliberately:** more version rows, and a migration cycle for changes another
system would ship as a nullable field. In exchange, no message in the system is ever ambiguous, and a
version number is a complete, checkable description of a payload.

### 5. Exact-version consumer support; unsupported or invalid → durable quarantine + alert

Every consumer declares the exact `(event_type, schema_version)` pairs it supports, recorded in the
registry, and dispatches on the exact pair. No consumer assumes "latest", decodes an unknown future
version best-effort, or treats an unknown version as the nearest known one. Unknown-field tolerance
is not a compatibility strategy here: under §4 a payload either matches its version exactly or is
invalid. A consumer may satisfy a supported version natively or through a **registered upcaster** —
explicit, total, pure, always between two *registered* versions of the *same* type, never applied to
an unknown version and never supplying a guessed value.

> **An unknown `event_type`, an unknown or unsupported `schema_version`, or an invalid payload for a
> known version becomes a durably quarantined message plus an operational alert.**

It is never silently ignored, never coerced, never treated as the latest, **never marked as
successfully HANDLED** — never recorded as Inbox `HANDLED`/`SUCCEEDED`, never recorded as having
produced its business effect, never treated by business logic as processed — never partially applied,
and never retried indefinitely on the normal queue. This is a contract/infrastructure integrity
failure, never a business error and never a business state transition.

**Semantic completion and transport disposition are separate.** The order is binding:

```text
validate → persist durable quarantine + rejection identity → COMMIT
        → terminally remove that delivery from the normal processing path
```

The transport must not dispose of the delivery before the quarantine state commits — acking first
loses the message on a crash between the two. **After** it commits, the transport may perform the
appropriate terminal disposition (ack after quarantine, reject/nack without requeue, or the
equivalent broker operation); that disposition is never a semantic completion. Quarantine state
retains enough identity that a redelivery is recognised and does not re-enter the processing loop.
The two invariants together: **never lose the message before quarantine is durable, and never leave a
permanently invalid message hot-looping on the normal queue.** **Item 9 owns the exact transport
action, queue and DLQ topology**; this ADR names no broker acknowledgement API and freezes only the
semantic result.

The producer validates before writing to the Outbox; the consumer validates before invoking business
logic; and validation is against the **registered schema for the row's declared version**, not
against the producer's current Python classes — durable rows outlive the code that wrote them. There
is **one canonical schema source per version**, owned by the producer, with every other
representation generated from it; two hand-maintained schemas for one version are forbidden.

### 6. Consumer-first migration is the default sequence

```text
1. Register vN+1 as DRAFT.
2. Deploy consumers supporting BOTH vN and vN+1; verify support is live.
3. Promote vN+1 to ACTIVE; switch the producer. Mark vN DEPRECATED.
4. Drain the vN backlog.
5. Only then retire vN, and only then may a consumer drop vN support.
```

Steps 2 and 3 are never reordered. Dual-publishing two versions of one logical fact is not the
default; where a migration plan requires it, the two emissions are two distinct instances with two
distinct `event_id`s, and the registry records which side suppresses the duplicate business effect.
Removing old-version support requires **evidence** — nothing queued, quarantined or within the
retained replay window — not confidence.

### 7. Message identity survives retries; delivery identifiers are not identity

Every instance carries a globally unique immutable `event_id`, assigned by the producer in the
emitting transaction. **A retry, redelivery or replay of the same logical message keeps the same
`event_id` and the same `occurred_at`**; a genuinely new fact gets a new one even if the payload is
identical. Broker delivery identifiers — Celery task id, delivery tag, Outbox row id, retry counter —
are transport facts and are never event identity, never a deduplication key, and never a correlation
key across a replay. For a message derived from a provider event, the provider's `external_event_id`
and the internal `event_id` are two separate identity spaces.

`occurred_at` is when the producer's fact became true, in aware UTC — not a publication, delivery or
handling time, and not an ordering key.

Delivery is at-least-once, and **message-identity integrity and business-effect idempotency are two
separate obligations**:

- **Identity integrity — mandatory for every consumer.** Every registered consumer durably retains,
  on first sight of an `event_id`, enough identity to verify later deliveries: conceptually
  `event_id`, `event_type`, `schema_version`, a canonical payload fingerprint, and the processing or
  terminal state it needs. The same `event_id` with identical type, version and payload is an
  ordinary duplicate; with a **materially different** type, version or payload it is a
  **data-integrity violation** — quarantined and alerted, never applied, never overwriting the first
  observation. **No consumer is exempt and no registry entry may declare this detection
  unavailable.**
- **Effect idempotency — chosen per consumer.** The consumer-visible business effect happens once per
  `event_id`, guaranteed by one of master `# 20.4`'s three durable PostgreSQL mechanisms —
  Inbox/`event_id` completion dedupe, a domain uniqueness constraint or state-machine transition
  idempotent by construction, or an `IdempotencyKey`-scoped command. Redis is never the only
  protection. **The choice is recorded per consumer, not once per message version**: each declared
  consumer of an `ACTIVE` or `DEPRECATED` version records its exact supported versions, its own
  mechanism and its justification. An `EVENT` may have several independent consumers that legally
  choose **different** mechanisms; a `COMMAND` has one handling owner and therefore exactly one such
  declaration. **The second and third mechanisms satisfy the effect obligation only; they never
  discharge the identity obligation above, which is one universal rule binding every consumer alike.**

Where atomicity is required, the Inbox claim, the durable effect, the resulting Outbox rows and the
Inbox completion happen in one local PostgreSQL transaction; **the Inbox record is never marked
handled before its effect commits**, and **no provider I/O happens inside that transaction**
(ADR-0004 §10, ADR-0007).

### 8. `schema_version` is a schema version, not an ordering version

Consumers must not assume global ordering; broker order is never relied on for correctness; and
`occurred_at` and Outbox row ids are not ordering keys. Duplicate and out-of-order delivery are both
contract-level expectations.

> **`schema_version` is the version of the payload contract. It is not a source version, not a
> business revision, not an aggregate version, and never decides which of two messages is newer.**

Master `# 20.6`'s own example makes the distinction visible: a `version: ClassVar[int] = 1` schema
version alongside a `source_version: int` payload field. Two numbers, two levels, two owners. The
`source_version` mechanism — its generation, per-source mapping and guarded upsert — belongs
**entirely to Phase 0 item 12** (item 6 §16.2), and nothing in this ADR may be cited as authority for
a version scheme.

### 9. The registry indexes contracts and owns none

A central registry (`docs/architecture/events/event-registry.md`) records, per
`(event_type, schema_version)`: kind, status, semantic owner, canonical payload-contract location,
producers, consumers with their supported versions, introduction date/phase, whether production emits
it, internal-only vs externally-consumed exposure, forward lineage, registered upcasters, and notes
including a privacy classification. Consumers are recorded individually, each with its supported
versions **and its own business-effect idempotency mechanism and justification**. Statuses are `DRAFT`
(must not be emitted; still editable), `ACTIVE` (emittable; contract frozen), `DEPRECATED` (must not
be newly emitted; **consumer support still mandatory**) and `RETIRED` (proved unneeded; must not be
emitted; an arrival is quarantined). Transitions are one-way.

An entry splits into **two classes of field**. Immutable from publication: `event_type`,
`schema_version`, `kind`, the semantic owner of that type, the canonical payload contract/schema for
that version, its payload **field semantics**, its exposure classification, and its introduction
record. Mutable, audited, and never a change to the payload schema: status, current consumer support
declarations, registered upcasters, notes and retirement proof, the current `emitted in production`
state, technical-producer delegations under the recorded-delegation rule, and the effect-idempotency
declaration while the semantic effect contract is unchanged. **Lineage is declared forward, once, on
the newly introduced row** (`supersedes`), with the reverse view derived from registry data — a
published row is never edited merely to add a back-pointer, and any stored reverse pointer is mutable
derived metadata rather than contract schema.

**A published type's semantic owner cannot be edited in place.** `event_type` is owner-qualified, so
an edited owner column would contradict the name itself. Moving responsibility is a
retire-and-introduce: deprecate then retire the old owner-qualified type, and introduce a new
owner-qualified type at `schema_version = 1`. Where the move changes a frozen module or domain
boundary an ADR is separately required — and it authorises the re-homing, not an in-place edit.

**Maintaining the registry confers no ownership.** No unregistered message may be emitted, no
`DRAFT` or `RETIRED` version may be emitted, and at most one `ACTIVE` emission version exists per
(technical producer, type) outside a recorded migration window. One semantic owner; a second
*technical* producer only by explicit recorded delegation — accidental multi-producer semantics is a
modelling error, not a configuration.

The registry ships **empty**: this ADR freezes the discipline and deliberately invents no catalogue.
Master's `catalog.project.batch`, `review.approved` and `payment.webhook.received` are master
illustrations, not registry entries; each is registered in its owning module's own phase.

### 10. What this ADR does not decide

**Out of scope:** queue names, routing, priorities, failure-domain isolation and DLQ topology
(**item 9**); trace/correlation/causation envelope field names and their propagation — this ADR
reserves an envelope extension point and names no field, and confirms that an item 10 envelope change
does **not** bump any payload's `schema_version` (**item 10**); `Money`/`PublicId` implementation
including the concrete `event_id` type (**item 11**); `source_version` (**item 12**); Outbox, Inbox,
dedupe and quarantine table schemas, columns, indexes and partitions, the physical column names, the
schema-definition and validation tooling, the serialization library, and the physical module layout
(**Phase 1**); every real message type and its payload (**each owning module's phase**); provider
webhook wire schemas (**the integration phases**); and numeric retention periods, replay windows,
alert thresholds and retry schedules (**operations phases**). A binary schema system, an event store,
saga/orchestration machinery, or a third message `kind` each require a new ADR.

Serialization is frozen only to the extent that it must be: a **JSON-compatible canonical
representation** with deterministic encoding, explicit units, and no `pickle`, no Python-object
serialization, no format whose decoding executes code, and no format requiring the producer's classes
to be importable in order to decode.

This ADR changes **no** dependency-matrix cell, adds **no** import edge, and extends **no** `core`
submodule allowlist — `core.events` is already allowlisted (item 3 §4.2/§4.3, `FORBID` for
`integrations/*` in §4.5). L1–L21 stand unedited and no new `L` rule is required.

## Consequences

**Positive**

- A durable row is self-describing: `(event_type, schema_version)` is a complete, checkable statement
  of what it means, so replaying a March partition in September is deterministic rather than
  archaeological.
- Module boundaries survive the asynchronous contour. Without §1 and §2, the event layer becomes the
  one place where every module's vocabulary meets, and the modular monolith quietly becomes a
  distributed one with shared types.
- A validator can be strict, so it catches producer bugs instead of tolerating them.
- "Unknown" has exactly one meaning everywhere — quarantine and alert — so no consumer invents a
  local coping strategy, and no message is ever recorded as handled without its effect.
- Ownership questions have mechanical answers: who may change this, who must support it, and whether
  an old decoder may be deleted are all registry lookups.
- Provider changes stop at the integration edge; an internal version bump never forces a provider
  change and vice versa.

**Negative / accepted cost**

- **More versions than a tolerant policy would produce.** Every additive field is a migration cycle.
  Accepted: §4's Context is the reason, and the alternative's cost lands at 3 a.m. during a replay.
- **Consumers carry more than one decoder during a migration**, and the migration has five steps
  rather than one deploy. Accepted: consumer-first is the only order that does not manufacture a
  quarantine incident out of an ordinary deployment.
- **The producer's typed contract is not reusable by the consumer.** Both sides describe the same
  payload, one authoring it and one validating against the registered schema. Accepted: sharing the
  type requires a shared package with no owner, and a shared type would in any case be the wrong tool
  for decoding a row written by a version of the code that is gone.
- **Registry maintenance is real work** and can go stale. Accepted, and mitigated: A42 makes an
  unregistered emission a build failure, so the registry cannot silently fall behind the code that
  matters.
- **A `kind` column on a document some readers will call "the event registry".** Accepted: one column
  is cheaper than either misnaming batch work items or maintaining two divergent rule sets.

**Enforcement**

- **Phase 1** implements the static checks A42–A50 in CI: no unregistered emission; no
  unknown-version fallback branch; no vendor SDK/wire type and no ORM object in a message contract or
  payload; no business message contract in `core` and no shared cross-package contract module; no
  conflation of `schema_version` with a source/ordering version; exactly one canonical schema source
  per version; no emission of a `DRAFT` or `RETIRED` version; and no cross-package message-contract
  import — **the composition root included**.
- **The implementing phase of each message** carries the behavioural contract tests C55–C69
  (duplicate delivery → one effect; same `event_id` with different content → integrity failure,
  asserted **including** for consumers whose effect idempotency comes from a domain constraint or an
  `IdempotencyKey`; supported version → handled; unsupported version, unknown type and invalid payload
  → quarantine + alert with no partial application and never marked HANDLED; producer-side validation
  aborts the emitting transaction; consumer-first migration and old-backlog handling; no completion
  before commit; no provider I/O in the durable transaction; retry preserves
  `event_id`/`occurred_at`; ordering independence; replay fixtures for every non-retired version;
  quarantine is durable before the delivery is disposed of, and does not hot-loop).
- V52–V61 are review-checklist items carried in §33.3 of the
  [item 8 artifact](../architecture/phase-0/08-event-registry-versioning.md); anything proposed
  against them needs a new ADR.
- The registry itself is the operational enforcement point: A42 ties emission to a row, and
  retirement requires recorded backlog/retention proof.
