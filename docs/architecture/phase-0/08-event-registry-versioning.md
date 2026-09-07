# Phase 0 — Item 8: event registry and versioning policy

- **Status:** DONE / FROZEN
- **Date:** 2026-09-05
- **Phase:** 0 — Architecture Freeze
- **ADR:** [ADR-0009](../../adr/0009-event-contract-versioning.md) — required, see §1.3
- **Related:** [ADR-0004](../../adr/0004-four-layer-modular-monolith.md),
  [ADR-0005](../../adr/0005-dependency-and-integration-wiring.md),
  [ADR-0006](../../adr/0006-public-contract-primitives.md),
  [ADR-0007](../../adr/0007-place-order-atomic-idempotent-boundary.md),
  [ADR-0008](../../adr/0008-storefront-listing-projection.md),
  [item 3](03-dependency-matrix.md), [item 4](04-domain-public-contract.md),
  [item 5](05-place-order-use-case.md), [item 6](06-storefront-listing-projection.md),
  [event registry](../events/event-registry.md),
  master `# 5`, `# 12.2`, `# 20.1`–`# 20.8`, `# 23.3`, `# 24`

---

## 1. Purpose

### 1.1 What this item freezes

The platform's asynchronous contour already requires internal messages to be typed, versioned,
durable, idempotent, replay-safe and eventually trace-propagating (master `# 20`, item 5 EV1–EV5,
item 6 UP1–UP8). What was never decided is the **contract discipline** around them: who owns an event
type, what a version number means, whether a published schema may grow, what a consumer must declare,
and what happens when a message arrives that no consumer understands.

Frozen here:

- the **scope** of the registry — which messages it governs and which it deliberately does not (§4);
- **ownership**: one semantic owner per message type, no central `events` domain, no business event
  type in `core`, and a registry that indexes contracts without owning them (§5);
- **producer isolation**: the asynchronous boundary is a **data** boundary, never an import boundary;
  no consumer imports a producer's contract module, and no shared business-event package exists (§6);
- the **message kind** discriminator `EVENT | COMMAND` and what each kind means (§7);
- the **naming model** for `event_type` (§8);
- **instance identity** `event_id`, its survival across retries, and its separation from broker
  delivery identifiers and from provider `external_event_id` (§9);
- the **envelope / payload** split and the four semantic envelope fields (§10);
- `occurred_at` semantics (§11);
- **payload type discipline** and its relationship to item 4's identity rules (§12);
- the **snapshot vs reference** rule for payload content (§13);
- `schema_version` semantics — one integer per stable `event_type`, starting at `1` (§14);
- **immutability of a published version** — the strict policy, adopted deliberately (§15);
- what forces a **new version** and what forces a **new type** (§16);
- the **exact-version consumer support** model (§17);
- **upcasters** as registered version-to-version transformations, never as unknown-version guessing
  (§18);
- **producer emission** rules and the default **consumer-first migration sequence** (§19);
- the semantic result for an **unknown or invalid** message: durable quarantine + alert (§20);
- **consumer idempotency** and the three admissible durable mechanisms (§21);
- the **handler transaction rule** (§22);
- the reserved **causality/trace extension point**, deferred to item 10 (§23);
- **ordering**: no global order, and `schema_version` is not `source_version` (§24);
- the **registry artifact**: its columns, its four statuses and their meanings (§25);
- the **registry invariants** (§26);
- **one canonical schema source** per version, with generated representations (§27);
- **validation** at both edges, and its classification as an integrity failure rather than a business
  failure (§28);
- **serialization**: a JSON-compatible canonical representation, no Python-object serialization (§29);
- **replay and retention** obligations that make versioning meaningful (§30);
- **security and privacy** of payload content (§31);
- a failure matrix (§32) and the checks later phases must implement (§33) — A42–A50, C55–C69,
  V52–V61.

### 1.2 What this item does **not** do

No Python package, module, event class, Outbox/Inbox model, migration, Celery task, broker
configuration, serializer or dependency is created. Phase 0 produces documents and decisions only.
Every name in this artifact that looks like an event name is **illustrative** and is not a registry
entry; the registry (`docs/architecture/events/event-registry.md`) ships with **no entries**.

Specifically **not** decided here:

| Not decided | Owner |
|---|---|
| Queue names, routing, priorities, failure-domain topology, the DLQ/quarantine queue shape | **item 9** |
| Trace/correlation/causation envelope field names and their propagation mechanics | **item 10** |
| `Money` / `PublicId` implementation | **item 11** |
| `source_version` generation, per-source mapping, guarded projection upsert SQL | **item 12** |
| Concrete Outbox/Inbox/quarantine table schemas, columns, indexes, partitions | Phase 1 (master `# 20.2`, `# 20.3` sketch them) |
| The schema-definition tool, validator library, generator and serializer library | Phase 1 |
| The real catalogue of business events | each owning module's own phase |
| Provider webhook wire schemas | the payments/ERP/CRM phases |
| Numeric retention periods, alert thresholds, retry schedules | operations phases (master `# 20.5`, `# 23.3`) |

### 1.3 Why a new ADR **is** required

Item 15 already anticipates an ADR for event versioning, and item 8 makes decisions that satisfy
`docs/adr/README.md`'s "when an ADR is required" test on three counts:

| Decision | Why it needs an ADR |
|---|---|
| The payload contract of a business message is owned by the **producing module**, not by `core` | Master `# 20.6` places event declarations in `core/events`. Item 8 keeps the *mechanism* there and moves the *business contract* out. That is a placement/ownership decision against explicit master text — §1.4. |
| A **published `(event_type, schema_version)` is immutable**, additive change included | This is a public-contract compatibility rule of the same class as item 4 §17, and stricter than any rule currently frozen. |
| **Exact-version** consumer support, with unknown/invalid → durable quarantine + alert and never an acknowledgement | A consistency/failure-semantics rule; master `# 20.6` states the DLQ outcome but not the surrounding contract, and item 5 EV4 explicitly deferred all of it here. |

[ADR-0009](../../adr/0009-event-contract-versioning.md) records these. It changes **no**
dependency-matrix cell, adds **no** import edge, and extends **no** `core` submodule allowlist:
`core.events` is already an allowlisted submodule (item 3 §4.2 for `domains`, §4.3 for `application`,
§4.5 `FORBID` for `integrations`). L1–L21 stand unedited.

### 1.4 The one place item 8 departs from the master

Master `# 20.6` reads:

> Все события объявляются в `core/events` — with a `CatalogProjectBatch` dataclass as the example.

Taken literally, that puts catalog/storefront business vocabulary inside `core`, which fails
ADR-0004 §2's admission test on its first clause (*domain-independent, no business or vendor
vocabulary*) and would make `core` the de facto owner of every module's asynchronous language — the
central-events-package shape that dissolves module boundaries in exactly the way ADR-0004 §3 and
ADR-0005 §7 exist to prevent.

Item 8 preserves **every requirement** master `# 20.6` states and changes only the **placement of the
business contract**:

| Master `# 20.6` requirement | Item 8 |
|---|---|
| Every event is declared, typed and validated against a schema — a bare `event_type` string is not enough | **Kept** — §25, §27, §28 |
| `event_name` + `event_version` on every Outbox/Inbox row | **Kept**, under the logical names `event_type` + `schema_version` (§8, §14) |
| Consumers explicitly register supported versions | **Kept and tightened** — §17 |
| Unknown version → DLQ + alert, never silent fallback | **Kept and generalised** to unknown types and invalid payloads — §20 |
| Explicit `v1 → v2` upcaster rather than conditional interpretation of old JSON | **Kept**, bounded by §18 |
| Replay of old Outbox partitions stays deterministic | **Kept** — §15, §30 |
| Declarations live in `core/events` | **Changed:** `core.events` owns the **mechanism** (envelope, registry lookup, codec, validation, contract-failure signalling); the **payload contract of each message is owned by the producing module and lives in that module's package** — §5, §6 |

`event_name`/`event_version` in master `# 20.2`/`# 20.6` are the same two concepts under earlier
names. The physical Outbox/Inbox column names are Phase 1's; they must map **1:1** onto `event_type`
and `schema_version`, and no third concept may be introduced beside them.

One further master detail is already superseded by a frozen artifact and is only recorded here for
clarity: master `# 12.2` step 8 has the webhook boundary create an Outbox marker. Item 3 L13 forbids
`interfaces/*` from importing `core.outbox`. The frozen shape therefore stands: the inbound boundary
performs durable **Inbox** ingest and nothing else; the internal registered message is authored later
by the owning application module in the worker (§6.4). This is not a new decision by item 8.

---

## 2. Frozen principles inherited

| # | Inherited rule | Source |
|---|---|---|
| R1 | Domains are mutually invisible: no domain imports another domain, **not even its `public.py`**. | ADR-0004 §3, item 3 §4.2 |
| R2 | `core` is admitted by test: domain-independent, no business **or vendor** vocabulary, more than one consumer, mechanism-shaped. `core` is not `utils`. | ADR-0004 §2 |
| R3 | `application/<a>` reaches domains only through `<domain>.public`; `application → application` is forbidden with no MVP exception. | ADR-0005 §7, item 3 §4.3 |
| R4 | `domains/<x>/public.py` exports exactly eight categories (E1–E8). An event payload contract is **not** one of them. | item 4 §5 |
| R5 | A domain emits its integration events by writing an Outbox row through `core` **inside its own transaction**; it never schedules transport and never imports `tasks/*`. | item 4 §9.1, item 3 §4.2 |
| R6 | `interfaces/*` may import `core.inbox` for durable webhook ingest but **not** `core.outbox` and not `core.idempotency`. | item 3 L13, ADR-0005 §1 |
| R7 | `integrations/*` may import neither `core.events` nor `core.outbox`/`core.inbox`/`core.idempotency`; it stays pure Python, importable without the Django app registry. | item 3 §4.5, ADR-0005 §1 |
| R8 | A `tasks/*` handler deserialises, restores actor and trace, calls **one** use case or domain public command, and maps the result to success/retry/DLQ. It decides *when*, never *what it means*. | ADR-0004 §9, item 3 §4.6 |
| R9 | PostgreSQL is the source of truth for orders, payments, inventory, reservations, idempotency, consent and legal data. Redis is disposable acceleration and never the sole idempotency decision. | master `# 1`, `# 5` |
| R10 | Durable idempotency is claimed and completed **inside** the transaction that performs the effect; a rolled-back attempt leaves no record. | ADR-0007, item 5 §11 |
| R11 | External provider I/O never happens inside a durable business transaction. | ADR-0004 §10, ADR-0007, item 5 §14 |
| R12 | An internal bigint must never become a user locator, a public API payload identifier, an external webhook/integration identifier, or an **externally consumed** event identifier. Strictly internal versioned events and jobs may keep using one (I4). | item 4 I3, I4 |
| R13 | Public DTOs are `@dataclass(frozen=True, slots=True, kw_only=True)`, fully annotated, immutable **by field type**, serialization-neutral, with no `Any`, no ORM, no transport and no vendor types. | item 4 §7 |
| R14 | The storefront projection is **not** event-sourced: a full rebuild comes from OLTP truth, and an archived Outbox partition can never make it unreconstructible. | item 6 RB1, RB2; ADR-0008 §4 |
| R15 | Vendor payloads never pass into a domain or application contract directly; `integrations/*` is an anti-corruption boundary. | ADR-0004 §8, master `# 20.1` |
| R16 | Event names, payload schemas, versions and the registry were explicitly deferred **to this item** by item 4 §17.4, item 5 EV4 and item 6 UP4. | those artifacts |

Nothing below weakens any of these.

---

## 3. Vocabulary

| Term | Meaning here |
|---|---|
| **Registered message** | An asynchronous message whose `(event_type, schema_version)` pair has an entry in the registry. Only registered messages may be emitted. |
| **Message kind** | `EVENT` (a past-tense fact) or `COMMAND` (an imperative work item). §7. |
| **Semantic owner** | The single module that owns what a message type *means* and is the only party that may change its contract. |
| **Technical producer** | The module whose code physically writes the message. Normally identical to the semantic owner; different only under a registry-recorded delegation (§26 RI9). |
| **Consumer** | A module that handles a registered message. It declares the exact versions it supports. |
| **Envelope** | Generic, kind-independent metadata needed to route and interpret a message. §10.1. |
| **Payload** | The message-specific, owner-defined immutable data. `schema_version` versions the **payload**. §10.2. |
| **Published version** | A `(event_type, schema_version)` entry that has left `DRAFT`. Its contract is immutable from that moment. §15. |
| **Quarantine** | The durable terminal destination for a message that cannot be legitimately processed: retained, alerted on, never acknowledged as handled, never hot-looping. §20. |
| **Upcaster** | A registered, explicit, total transformation from one registered version of an `event_type` to a later registered version of the same `event_type`. §18. |
| **Asynchronous boundary** | The serialized data boundary between a producer and a consumer. It is crossed by bytes, never by an import. §6. |

---

## 4. Scope of the registry

### 4.1 What the registry governs

| # | Rule |
|---|---|
| S1 | The registry governs **durable internal asynchronous messages emitted through the transactional Outbox and consumed through Inbox/idempotent handlers**. Membership in the registry is what makes a message emittable (RI11). |
| S2 | Conceptually in scope: domain business facts published for asynchronous consumption; application workflow facts; projection-update triggers (item 6 §14); integration-work triggers that cause an `application` module to perform outbound vendor work through its port. |
| S3 | A message is in scope **because it is durable and crosses the asynchronous boundary**, not because of the technology that carries it. Changing the relay or broker never changes what is registered. |

### 4.2 What the registry does **not** govern

| # | Not governed | Why |
|---|---|---|
| S4 | HTTP request/response bodies and DRF serializer shapes | Transport representations owned by `interfaces/*` (item 4 X5). |
| S5 | `public.py` command/query DTOs of a domain or application module | A separate, synchronous contract with its own compatibility policy (item 4 §17.4). A public API change is not automatically an event change, and vice versa. |
| S6 | External provider webhook wire payloads — raw maib / MIA / ERP / CRM / Chatwoot bodies | Vendor protocol, owned at the `interfaces/webhooks/<provider>` + `integrations/<provider>/protocol` edge (ADR-0004 §7, ADR-0005 §6). |
| S7 | Direct synchronous function calls | No asynchronous boundary is crossed. |
| S8 | Redis cache entries, cached fragments, single-flight markers | Disposable acceleration (R9), never a contract. |
| S9 | Metrics, spans, structured log records | Ephemeral observability; master `# 23`. |
| S10 | Celery task argument formats **as an independent business contract** | A task is transport (R8). Its arguments carry a registered message or an identifier of one; they are not a second, unregistered business contract with its own versioning. |

### 4.3 The provider-to-internal translation rule

| # | Rule |
|---|---|
| S11 | When an external provider webhook or import is turned into a durable internal message, the **provider wire schema and the internal registered message are two separate contracts** with separate identities, separate versions and separate owners. |
| S12 | **Provider vocabulary never becomes internal event vocabulary.** A provider status string, provider error code, provider field name or provider event name may not appear as an `event_type` segment, a payload field name, or a payload enum value (§8 NM6, §12 PD8, and V3 of item 3). |
| S13 | The translation is owned by the application module that owns the workflow (ADR-0005 §2's frozen port owners); the raw provider body stays in Inbox storage (master `# 20.3`) and is not the payload of the internal message. |
| S14 | A provider schema change therefore never forces an internal `schema_version` bump, and an internal version bump never forces a provider-side change. Decoupling the two is the point of S11. |

---

## 5. Ownership

| # | Rule |
|---|---|
| OW1 | **Every registered message type has exactly one semantic owner**, and ownership follows the fact being published: a domain business fact is owned by that domain; an application workflow fact is owned by that application module. |
| OW2 | The owner is the only party that may introduce a new version of the type, change its status, deprecate or retire it. **A consumer never edits a producer's contract.** A consumer that needs a different shape asks the owner for a new version, or derives what it needs on its own side. |
| OW3 | **No central `events` domain is created.** There is no `domains/events`, no `application/events`, no shared `contracts/` or `messages/` package. A package with no owner cannot refuse an addition (ADR-0005 §2). |
| OW4 | **`core` owns no business message type.** `core.events` owns *mechanism* only: the envelope type, registry lookup/dispatch mechanism, codec and validation machinery, and the structural contract-failure signalling. Mechanism-shaped, domain-independent, multi-consumer — it passes ADR-0004 §2 exactly as `core.outbox` and `core.idempotency` do. A payload field named after a product, an order, a payment or a provider does not belong in `core`. |
| OW5 | The **registry indexes contracts; it owns none of them.** It is a documentation/data artifact that records who owns what, which versions exist and who supports them. Adding a row to the registry does not transfer ownership, and the registry's own maintenance is not an architectural authority (§25 RG9). |
| OW6 | The owner of a type is recorded once and applies to **every** version of that type. Moving ownership requires an ADR (RI4). |
| OW7 | A **transport package is never a semantic owner and never a technical producer.** `interfaces/*` cannot emit at all (R6/L13); `tasks/*` never authors a payload — it invokes the owning module, which emits (R8). `integrations/*` cannot reach `core.events` at all (R7). |
| OW8 | Ownership is stated in business terms, not in terms of who happens to consume. "`application/storefront` needs it" never makes storefront the owner of a catalog fact; it makes storefront a consumer. |

Illustrative only, and **not** registry entries: a stock-reservation fact would be owned by
`domains/inventory`; a placement fact by `application/checkout` (item 5 EV3); a projection-update work
item by `application/storefront` (item 6 UP1); an ERP export trigger by `application/erp_sync`
(ADR-0005 §2). None of these names is frozen by this item.

---

## 6. Producer isolation — the asynchronous boundary is a data boundary

### 6.1 The decision

> **A consumer never imports a producer's message contract. The asynchronous boundary is crossed by
> a serialized, registry-described payload, never by a Python import.**

This is not a preference; it is forced by rules already frozen. A consumer application module cannot
import `domains/<x>/events.py` (item 3 §4.3: `PUBLIC ONLY`), a domain cannot import a sibling's
anything (R1), a domain cannot import an application module (item 3 §4.2), and
`application → application` is forbidden outright (R3). Item 4 §5's eight export categories do not
include an event contract, so routing contracts through `public.py` would require widening a frozen
list. The only remaining honest boundary is the data boundary — which is also the one that survives a
replay of a durable row written by code that no longer exists (§30 RR3).

### 6.2 Rules

| # | Rule |
|---|---|
| PI1 | A producer records its message through its own contract and the `core` Outbox mechanism, inside its own transaction (R5, item 5 EV1/EV3). |
| PI2 | A consumer obtains a validated payload **from the registered schema**, through the `core.events` mechanism, and materialises **its own** internal representation. It never imports, references or type-annotates against the producer's contract object. |
| PI3 | **No shared package containing business message classes exists** — not in `core`, not in a `contracts/` package, not in a "just the events" module imported by everyone (OW3, OW4). |
| PI4 | Per-owner contract modules are legal and expected (`domains/<x>/<contracts module>`, `application/<a>/<contracts module>`); they stay **internal to the owning package**, exactly as its ORM and services do (ADR-0005 §7). Physical file names are Phase 1's. |
| PI5 | The registry may be documentation and machine-readable data used for validation and CI checks. It **must not become a backdoor import graph**: no runtime module may import another module's internals "through" the registry, and no registry-driven lookup may return a producer-owned object into a consumer's process as that producer's type. |
| PI6 | A module consuming its **own** message type is the trivial case: `SELF ONLY` already permits it, and no boundary is crossed. |

### 6.3 How a schema reaches the validator without an import

> **The canonical contract is owner-internal. Any schema representation consumed outside the owner
> crosses the package boundary as generated, versioned **data** — never as a producer-owned Python
> object.**

The pipeline is frozen; only its file format and tooling are Phase 1's:

```text
owner-internal canonical schema source          (§27, internal to domains/<x> or application/<a>)
  → deterministic build/generation step
  → checked-in, versioned schema artifact/data
  → core.events validator / registry mechanism
  → consumer validation
```

| # | Rule |
|---|---|
| PI7 | The generated artifact is **derived**, never a second hand-maintained source of truth (SC1, SC3). It is regenerated deterministically and the regeneration is verified in CI (A48). |
| PI8 | The artifact is **checked in and versioned**, so an old version stays decodable after its producer's code has changed or been deleted (SC4, RR3). |
| PI9 | If a typed Python contract is canonical, the generated JSON-compatible schema data **must** be checked in. If a data schema is canonical, that representation is used directly and any other representation is generated from it. |
| PI10 | **The composition root may not import an owner-internal message contract.** `config/ → domains/<x>` is `PUBLIC ONLY` and `config/ → application/<a>` reaches only `public.py`/`ports.py` (item 3 §4, ADR-0005 §3/§7); the message schema is deliberately owner-internal and is **not** a `public.py` export (item 4 §5). Registering owner schemas into `core.events` by importing them at startup is therefore **not** an admissible realisation, and no matrix exception is requested for it. |
| PI11 | No realisation may create a consumer → producer import edge, move a dependency-matrix cell, widen `public.py`'s export categories, or introduce a shared business-message Python package. An option that requires any of these is rejected without further discussion. |

### 6.4 Inbound provider events

| # | Rule |
|---|---|
| PI12 | `interfaces/webhooks/<provider>` verifies provider protocol facts and performs durable **Inbox** ingest, and does nothing else (ADR-0004 §7, item 3 §4.4/L13). It authors no registered message. |
| PI13 | The internal registered message derived from a provider event is authored by the **owning application module** running in the worker, after the raw body is durably ingested. Its `event_id` is its own (§9 ID6) and its vocabulary is internal (S12). |

---

## 7. Message kind: `EVENT` and `COMMAND`

### 7.1 The decision

The registry is a **single registry of registered asynchronous messages** with a mandatory `kind`
discriminator whose closed value set is `EVENT | COMMAND`.

This was a real choice. An event-only registry was rejected because the platform demonstrably carries
both kinds through the same Outbox: a past-tense business fact with several independent reactions, and
an imperative bounded work item with exactly one handler — master `# 20.2`'s coalesced batch
projection work item is unmistakably the second, and calling it an "event" would make the word
meaningless on the first page of the registry. A **second, separate** registry was rejected because
every rule in this artifact — identity, versioning, immutability, exact-version support, quarantine,
idempotency, validation, retention — applies to both kinds without modification, and duplicating them
into a parallel document guarantees the two copies diverge.

The cost is one column. That is cheaper than either alternative.

### 7.2 Rules

| # | Rule |
|---|---|
| KD1 | `kind` is a **registry field**, mandatory on every entry, drawn from the closed set `EVENT | COMMAND`. Adding a third kind requires an ADR. |
| KD2 | An **`EVENT`** is a past-tense fact: *something happened / became true*. It names no handler, mandates no implementation, and may have zero, one or many independent consumers. Adding or removing a consumer is not a contract change for the producer. |
| KD3 | A **`COMMAND`** is an imperative work item: *perform X*. It has **exactly one** designated handling owner, recorded in the registry. A command with two independent handlers is a modelling error — it is an event that has been misnamed. |
| KD4 | `kind` is **fixed for the life of an `event_type`**. An `EVENT` never becomes a `COMMAND` and vice versa; that is a different fact and therefore a different type (§16 BC13). |
| KD5 | Every rule in §8–§32 applies **identically** to both kinds unless a rule says otherwise. Only §25's `consumers` semantics differ (a command names its single handler; an event lists its consumers). |
| KD6 | `kind` is **derivable from the registry** given the `event_type`; it is therefore **not** a semantic envelope field (§10 EN5). Whether it is denormalized onto a transport row for routing is item 9's and Phase 1's; a denormalized copy is never a second source of truth. |
| KD7 | Item 8 introduces **no `core` enum, no `core` package and no runtime type** for `kind`. If Phase 1 needs a runtime discriminator, it is a structural mechanism value inside `core.events` — an already-allowlisted submodule (item 3 §4.2/§4.3) — carrying no business vocabulary, and it requires no allowlist change. |
| KD8 | "Async command" here means a durable registered work item on the Outbox transport. It is **not** the `IdempotencyKey`-scoped user command of master `# 20.4`, and it is **not** a domain `public.py` command (item 4 §9). Three different things; the registry governs only the first. |

Where the roadmap says "event registry", read: this registry, whose events are its `EVENT` rows.

---

## 8. `event_type` — the naming model

| # | Rule |
|---|---|
| NM1 | `event_type` is a stable, lowercase, machine-readable string of dot-separated segments; each segment matches `[a-z][a-z0-9_]*`. It is not a display name and is never localized. |
| NM2 | The **first segment is the semantic owner's stable module name** (`inventory`, `orders`, `checkout`, `storefront`, `erp_sync`, …). Owner-qualification is what makes the type globally unique without a central authority and lets the registry be validated mechanically. |
| NM3 | The remaining segments name the fact (for an `EVENT`, in the **past tense**) or the work item (for a `COMMAND`, in the **imperative**). |
| NM4 | Forbidden in an `event_type`: a Python module path, a class name, a table name, a broker/queue/exchange/routing-key name, a transport word, a version suffix, an environment name, and a UI/marketing term. |
| NM5 | **Version is never encoded in the name.** `something_v2` is forbidden; `schema_version` carries the version (§14 SV6). The logical fact must remain identifiable across every version of its schema. |
| NM6 | A **vendor or provider name is forbidden as the first segment** and is forbidden anywhere when the fact is provider-independent. It may appear in a later segment **only** when the fact is genuinely provider-specific, and even then the first segment is still the owning application module — never the vendor. |
| NM7 | Once a type is published, **its meaning is immutable**. A retired type is never reused for a different meaning, and never reused at all (RI3). Names are cheap; a silently re-pointed name is a production incident that no test catches. |
| NM8 | The `event_type` string is externally immutable in the same sense as a public identifier: it appears in durable rows, quarantined messages, alerts, runbooks and replay tooling. Renaming it is a retire-and-introduce operation (§16 BC16), never an edit. |

Illustrative shape only, **not** frozen names:

```text
inventory.reservation_changed      # EVENT   — owner: domains/inventory
storefront.reproject_products      # COMMAND — owner: application/storefront
payments_gateway.provider_callback_normalized
                                  # EVENT   — owner: application/payments_gateway
                                  #           provider-neutral vocabulary (S12)
```

Counter-example, forbidden by NM6 and S12: `maib.callback_success`.

Master `# 20.2`/`# 20.6`'s `catalog.project.batch`, master `# 14.1`'s `review.approved`, master
`# 12.2`'s `payment.webhook.received` and item 5's placement records are **master illustrations, not
registry entries**. Each is registered — with its owner, kind, final name and version — in its own
phase. Item 8 adopts none of them as frozen.

---

## 9. Instance identity — `event_id`

| # | Rule |
|---|---|
| ID1 | Every emitted message instance carries a globally unique, immutable `event_id`, assigned by the producer **at emission**, in the same transaction that writes the message (R5). |
| ID2 | `event_id` is used for: consumer deduplication (§21), Inbox idempotency, correlation with the Outbox row and its delivery attempts, quarantine identity, and operational diagnosis. |
| ID3 | **A retry of the same logical emitted message keeps the same `event_id`.** Relay retries, broker redelivery, worker retries and DLQ replay all carry the original identity forward unchanged. This is what makes §21's exactly-once effect possible at all. |
| ID4 | A producer that emits a **genuinely new** business fact assigns a **new** `event_id`, even when the payload is byte-identical to an earlier one. Identity is per emission, not per content. |
| ID5 | **Broker/transport delivery identifiers are not event identity.** A Celery task id, an AMQP delivery tag, a Redis stream id, a retry counter and an Outbox row primary key are transport facts. None of them may be used for deduplication, correlation across a replay, or as a stand-in for `event_id`. |
| ID6 | For a message derived from an external provider event, the provider's `external_event_id` and the internal `event_id` are **two identity spaces**. The provider identifier deduplicates the *provider's* delivery in `InboxDedupeKey` (master `# 20.3`); the internal `event_id` identifies the *internal* message. Neither substitutes for the other, and the provider identifier never becomes the internal identity. |
| ID7 | `event_id` is conceptually the project's UUID-based identity primitive (`PublicId`/UUIDv7, master `# 5`). **Item 11 owns the implementation**; item 8 requires only that the value be a stable, globally unique, non-sequential, opaque UUID assigned once. No sequential bigint is acceptable here — a message identity is by definition consumed outside its producer (R12/I3). |
| ID8 | `event_id` is never reused, never regenerated on a re-emission of the same logical fact, and never derived from mutable payload content. |

---

## 10. Envelope and payload

### 10.1 Envelope

| # | Rule |
|---|---|
| EN1 | The **semantic envelope** is kind-independent, message-independent metadata required to route, identify and interpret a message. It is frozen as exactly four fields: `event_id`, `event_type`, `schema_version`, `occurred_at`. |
| EN2 | Producer/owner identity is **derivable** from `event_type` plus the registry (NM2, OW6) and is therefore **not** an envelope field. Where a delegated technical producer differs from the semantic owner (RI9), that fact is recorded in the **registry** and, if operationally required, in Outbox row metadata — never in the semantic envelope. |
| EN3 | The envelope carries **no transport concern**: no queue or exchange name, no routing key, no retry counter, no attempt number, no delivery id, no broker timestamp, no worker/host identity, no priority. Those are item 9's and the relay's, and they live on the transport row or in message headers. |
| EN4 | The envelope carries **no business data**. If a value is meaningful to a handler's business decision, it is payload. |
| EN5 | `kind` is registry-derived and is not an envelope field (KD6). |
| EN6 | The envelope has **one reserved extension point** for the causality/trace fields item 10 owns (§23). Item 8 neither names nor shapes those fields. |
| EN7 | The envelope is not a metadata bag: no `meta`, no `extra`, no `context`, no `dict[str, Any]`, no free-form headers map. A field that is not one of EN1's four, or an item 10 field, does not exist. |

### 10.2 Payload

| # | Rule |
|---|---|
| EN8 | The **payload** is the message-specific, immutable data defined by the semantic owner. |
| EN9 | **`schema_version` versions the payload contract, and only the payload contract** (§14 SV2). |
| EN10 | The payload is not a metadata bag either: no `dict[str, Any]`, no `extra`/`meta`/`attributes` map, no arbitrary JSON blob, no "we'll put the rest in here" field. Every field is declared, named and typed (§12). |
| EN11 | The payload never carries envelope fields as duplicates. `event_id`, `event_type`, `schema_version` and `occurred_at` appear once, in the envelope. |

---

## 11. `occurred_at`

| # | Rule |
|---|---|
| TS1 | `occurred_at` means **when the producer's business or application fact became true** — the moment the owning module decided the fact, inside the transaction that recorded it. It is not a publication time, not an enqueue time, not a delivery time, and not a handling time. |
| TS2 | It is a timezone-aware **UTC** instant (item 4 D7's aware-UTC rule). A naive datetime is a contract violation. |
| TS3 | **Retries never change `occurred_at`.** Redelivery, DLQ replay and cross-partition replay all preserve the original value, exactly as they preserve `event_id` (ID3). |
| TS4 | `occurred_at` is **not** an ordering key and carries no total order (§24 OR3). Two producers' clocks are not comparable, and even one producer's transactions do not commit in `occurred_at` order. |
| TS5 | If a publication, first-delivery or processing timestamp is needed operationally, it is **transport/Outbox/Inbox metadata** — a column on the durable row, never a second business time in the envelope and never a replacement for `occurred_at`. |
| TS6 | No additional timestamp is added to the envelope or the payload without a stated semantic need, a name that says what it means, and a registry note. "It might be useful" is not a need. |

---

## 12. Payload type discipline

Item 4's DTO discipline (R13) applies, adapted for a contract that must survive serialization and
outlive the code that wrote it.

| # | Rule |
|---|---|
| PD1 | Every payload field is **explicitly declared, named and fully typed**. No bare `Any`, no untyped field, no optional-by-accident field. |
| PD2 | The contract is **immutable**: frozen structures, immutable collection semantics (ordered sequences and sets expressed as immutable shapes, never mutable containers), no in-place mutation by a handler of the value it was given. |
| PD3 | The contract is **serialization-neutral in shape and serializable in fact**: it maps onto §29's canonical representation without custom hooks, without framework metadata and without decoder-side code execution. |
| PD4 | The payload is **bounded**. Unbounded collections are forbidden; a batch payload declares an explicit maximum size, and bulk work uses coalesced bounded batches or a dirty-set/staging table (master `# 20.2`, item 6 UP5). A payload that can grow with the size of the catalog is a defect. |
| PD5 | The payload is **deterministic**: the same logical fact produces the same canonical serialized form, so a content fingerprint is meaningful (§21 IX5, §29 SZ4). No wall-clock, random, hostname, hash-salt or iteration-order-dependent content. |
| PD6 | **Forbidden in a payload**: ORM model instances, `QuerySet`/`Manager`/`Prefetch`/expression objects, lazy or deferred model objects, generators and iterators; Django `HttpRequest`/`HttpResponse`, DRF serializers/`Response`; Celery task objects and signatures; provider SDK objects, vendor DTOs, vendor exceptions, raw provider statuses and provider error codes — including under a neutral type name (item 3 V3); file handles, connections and any object whose meaning depends on a live process. |
| PD7 | **No raw database row dumps, no `model.__dict__`, no `values()` output, no "whole row as JSON".** A payload is an authored contract, not a serialization of whatever the ORM happened to hold. |
| PD8 | Field names use internal business vocabulary, never provider vocabulary (S12), never column names as an accident of the ORM, and never transport words. |
| PD9 | Values carry **explicit units and semantics**: money as integer minor units plus an explicit currency (never a float, never a bare number — master `# 5`, item 11 owns the type); quantities with their unit; instants as aware UTC; enumerations as stable structural codes, never as a database integer whose meaning lives in Python. |
| PD10 | An enumeration value in a payload is part of the versioned contract. Its **set of legal values and their interpretation** are frozen with the version (§16 BC6). |

### 12.1 Identifiers in a payload — the careful part

| # | Rule |
|---|---|
| PD11 | Item 4 I3 stands unchanged: an internal bigint must never become a user locator, a public API payload identifier, an external webhook/integration contract identifier, or an **externally consumed** event identifier. |
| PD12 | Item 4 I4 stands unchanged, and item 8 is the item it deferred to: a **strictly internal** registered message — one that never leaves the platform, is never forwarded to a provider, is never rendered to a user and is never exposed in a public API — **may** carry an internal stable identifier where the owning module's identity rules permit it. Master `# 20.6`'s `product_ids: tuple[int, ...]` batch shape and item 6 I5's internal-join identifiers are legitimate under this rule. |
| PD13 | Where a legitimate internal identifier appears, it is named unambiguously (`internal_<entity>_id`, per item 4 I3) and typed distinctly enough that it cannot be mistaken for a locator. |
| PD14 | A registered message is classified in the registry as **internal-only** or **externally consumed**. An externally consumed message — one forwarded to a provider, surfaced in a public API, rendered to a user, or delivered to a third party — carries `PublicId` locators only, and PD12's allowance does **not** apply to it. |
| PD15 | Reclassifying a message from internal-only to externally consumed is a **breaking change** requiring a new version, because it changes which identifiers are legal (§16 BC5). It is also a security review item (V57). |
| PD16 | Item 8 does **not** require every internal payload field to be a `PublicId`. Requiring that would contradict I4 and would push UUID lookups onto every batch worker for no security gain. |

---

## 13. Snapshot vs reference

### 13.1 The rule

> **A message carries enough immutable information to express the fact that occurred and to let its
> intended consumers behave idempotently. It does not duplicate an entire aggregate.**

Both extremes are rejected by name:

| Rejected | Why |
|---|---|
| **(A) A complete aggregate snapshot in every message** | Unbounded payloads (PD4), a copy of another module's model shape smuggled across the boundary, and a contract that must be re-versioned every time an unrelated field of the aggregate changes. It also maximises the PII and secret surface (§31). |
| **(B) An identifier alone, with no evidence of what changed** | The consumer cannot tell what happened, cannot be idempotent without re-deriving state, and cannot distinguish a stale replay from a new fact. It converts every message into a mandatory synchronous re-read and pushes the load back onto the producer. |

### 13.2 Rules

| # | Rule |
|---|---|
| SR1 | A payload contains: the identity of the subject of the fact; the **fact itself** in immutable terms (what became true, and where it matters, what it was before); and any value the consumer needs that would be **unsafe or impossible to re-read later** — most importantly a value that is only true at `occurred_at`. |
| SR2 | A payload does **not** contain fields carried only because "a consumer might want them". An unused field is contract surface with no benefit and an immutability obligation (§15). |
| SR3 | A consumer that needs **current authoritative state** may legally call the owning module's public selector or use case where the frozen dependency graph permits it (item 3 §4.3/§4.6). This is the normal, expected shape; item 6 UP8 already requires it for a full projection-row recompute. |
| SR4 | A payload is **never authoritative for a commercial decision**. It is evidence that a fact occurred, at a time; ADR-0007's and item 5's trust rules are unaffected, and a consumer performing a durable commercial write revalidates through the owning module (item 5 §7.4). |
| SR5 | For **projection-update** messages, identifiers plus appropriate change/revision information may be the whole payload (item 6 UP5, UP8). The concrete revision/`source_version` mechanism, its generation and the guarded upsert are **item 12's** and are neither designed nor constrained here beyond §24 OR6. |
| SR6 | Where a consumer must distinguish "this fact, again" from "a newer fact", the **payload or the owning state must carry enough information to make that decision** (§24 OR5). Which of the two carries it is the owner's choice, recorded in the registry entry. |
| SR7 | Item 8 designs **no actual payload** for any real message. SR1–SR6 are the rule a payload is later judged against. |

---

## 14. `schema_version` semantics

| # | Rule |
|---|---|
| SV1 | `schema_version` is a **positive integer**, starting at `1` for the first published version of an `event_type`. |
| SV2 | It versions **the payload contract of one stable `event_type`** — its field set, field types, requiredness, value semantics, units, enumerations and collection semantics. Nothing else. |
| SV3 | Version numbers **increase monotonically** within a type and are **never reused**, not even after a version is retired and its support removed (RI6). |
| SV4 | A version is introduced **only** for an incompatible or semantic change to the payload contract (§15, §16). |
| SV5 | A version is **not** bumped because: the producer's implementation changed; a query, index or model behind it changed; the broker, queue, routing or worker changed; the relay batch size changed; a consumer was added or removed; a log line, metric or alert changed; a docstring changed. |
| SV6 | A version is **not** expressed in the type name (NM5) and the type name is not expressed in the version. Two orthogonal identifiers. |
| SV7 | Item 10's envelope trace fields are **not** payload and do not bump `schema_version` (§23 CA4). If a future envelope change ever requires a compatibility signal, that is an envelope-level concern for item 10 and an ADR — never a silent reuse of the payload version. |
| SV8 | **Semantic-version strings are forbidden.** No `1.2.0`, no `v1.1`, no major/minor/patch. A single integer, precisely because the only distinction the system can act on is "this consumer supports this exact contract, or it does not". |
| SV9 | `schema_version` is **not** a business version, a revision counter, an aggregate version or an ordering key (§24 OR6). This is stated again in §24 because it is the mistake this design is most likely to attract. |

---

## 15. Immutability of a published version

### 15.1 The decision

Three policies were evaluated:

| Option | Verdict |
|---|---|
| **A. Every payload field addition bumps the version** | Adopted, as the consequence of C. |
| **B. Optional additive fields may stay on the same version** | **Rejected.** |
| **C. No in-place schema mutation after publication** | Adopted as the governing rule. |

> **Once `(event_type, schema_version)` has left `DRAFT`, its field set and its field semantics are
> immutable. Even a purely additive, optional field produces a new `schema_version`.**

Option B is the tempting one and is wrong here for a specific reason: these messages are **durable and
replayable**. A row written in March and replayed in September must be interpretable in exactly one
way. Under B, `(order_something, 3)` means two different things depending on when it was written, and
nothing in the row says which — the consumer must guess from field presence, which is precisely the
"conditional interpretation of old JSON" master `# 20.6` forbids. Under B a validator also cannot be
strict: it must accept both shapes forever, so it stops catching the producer bug it exists to catch.
Under C, a version number is a complete, checkable description of a payload, replay is deterministic,
validation is strict, and the registry can answer "what does this row mean" from the row alone.

**The cost is accepted deliberately:** more version rows, a migration cycle (§19) for changes that
another system would ship as a nullable field, and consumers that must keep more than one decoder
alive during a migration window. In exchange, no message in the system is ever ambiguous.

### 15.2 Rules

| # | Rule |
|---|---|
| IM1 | A `DRAFT` version's contract may be edited freely — that is what `DRAFT` is for. It must not be emitted while in `DRAFT` (RG3), so no durable row can depend on the pre-edit shape. |
| IM2 | The moment a version becomes `ACTIVE`, its payload contract is **frozen**: no field added, removed, renamed, retyped, made optional, made required, re-defaulted or re-interpreted. |
| IM3 | This holds through `DEPRECATED` and `RETIRED`. A retired version's schema stays in the repository as long as any retained or archived message could still be read, and a retired version's contract is still never edited (RR4). |
| IM4 | "Additive and optional" is **not** an exemption (option B rejected). Neither is "no consumer reads that field yet", "it defaults to null", or "we only changed the description of what the field means" — that last one is the most dangerous of the three (§16 BC9). |
| IM5 | Fixing a producer bug that made emitted payloads not match the published schema is a **producer fix**, never a schema edit. The schema is what was published; the producer is what was wrong. If the published schema itself is wrong, the correction is a new version. |
| IM6 | The registry entry for a published version splits into an **immutable contract half** and a **mutable, audited operational half** (§26.1). The contract half is append-only from publication; the operational half necessarily evolves, and evolving it never changes what the version means. |

---

## 16. What forces a new version, and what forces a new type

### 16.1 A new `schema_version` is required for at least

| # | Change |
|---|---|
| BC1 | Field removal. |
| BC2 | Field rename. |
| BC3 | Field type change, including a widening or narrowing of a numeric type, and a change of representation (string ↔ number, scalar ↔ object, single ↔ collection). |
| BC4 | Requiredness change in either direction (required → optional, optional → required), and a default-value change. |
| BC5 | Identifier semantic change: which entity an identifier points at, which identity space it is drawn from (internal vs `PublicId`), or a change of the message's internal-only/externally-consumed classification (PD15). |
| BC6 | Enumeration change: adding a value a consumer must handle, removing a value, or changing what a value means. |
| BC7 | Unit, currency, precision, rounding, timezone or time-semantics change of an existing field. |
| BC8 | **Meaning change of an existing field** while its name and type stay identical. |
| BC9 | Collection semantics change: ordered ↔ unordered, unique ↔ duplicates-allowed, a change in what the order signifies, or a change in the bound. |
| BC10 | Payload splitting or merging that changes interpretation — one message becoming two, or two becoming one, in a way that alters what a consumer must do. |
| BC11 | Any addition at all, per IM4. |

| # | Rule |
|---|---|
| BC12 | **An already-published version is never mutated in place**, for any of the above (IM2). |

### 16.2 New version vs new type

```text
same fact, new representation      →  new schema_version   (same event_type)
different fact or different meaning →  new event_type      (schema_version restarts at 1)
```

| # | Rule |
|---|---|
| BC13 | If the **business meaning** changes enough that it is no longer the same fact — a different subject, a different moment, a different guarantee, a different `kind` (KD4), a different semantic owner (OW6) — the answer is a **new `event_type`**, not `schema_version + 1`. |
| BC14 | The test is a consumer test, not a producer test: *could a consumer that correctly handled the old fact make a correct decision about the new one by reading the same field names?* If not, it is a different fact. |
| BC15 | Splitting one fact into two, or merging two into one, is a new-type operation on both sides (with BC10 covering the payload-level case where the fact itself is unchanged). |
| BC16 | Renaming a type is a **retire-and-introduce**: the old type is deprecated then retired under its own name, the new type starts at version `1`, and the registry records the relationship in both entries. The old name is never reused (NM7, RI3). |

---

## 17. Consumer support model

| # | Rule |
|---|---|
| CS1 | Every consumer **explicitly declares the exact `(event_type, schema_version)` pairs it supports**, and that declaration is recorded in the registry. |
| CS2 | A handler **dispatches on the exact registered pair**. There is no default branch, no fallback handler and no catch-all. |
| CS3 | **No consumer assumes "latest".** A consumer that says "whatever version the producer is on" has declared nothing, and will silently break on the next migration. |
| CS4 | **No consumer decodes an unknown future version on a best-effort basis**, by field presence, by duck-typing, by ignoring unknown fields, or by any other means. |
| CS5 | **No consumer treats an unknown version as the nearest known version** — not the highest supported, not the lowest, not "probably compatible". |
| CS6 | Unknown-field tolerance is **not** a compatibility strategy here. Under §15 a payload either matches its published version exactly or is invalid (§28 VL3). |
| CS7 | A consumer's supported set may legitimately contain **several versions of one type** — that is precisely what §19's migration sequence requires. |
| CS8 | A consumer may satisfy a supported version either with a **native handler** for that version or through a **registered upcaster** to a version it handles natively (§18). Either way, the support is explicit and registered. |
| CS9 | Support is declared per consumer, not per platform. Two consumers of one type may support different version sets; the type's retirement is governed by the union of what may still arrive (§30 RR2). |

The registry can therefore answer, mechanically:

- who **owns** this type, and who **produces** it;
- which **versions exist**, and what status each is in;
- which **consumers** support which versions;
- which version is **active for new emissions**;
- whether an old version is **still required** for replay or backlog, and therefore whether its
  decoder may be deleted.

Queue routing is **not** among these questions — that is item 9's.

---

## 18. Upcasters

Master `# 20.6` requires an explicit `v1 → v2` upcaster rather than conditional interpretation of old
JSON. That is preserved and bounded.

| # | Rule |
|---|---|
| UC1 | An upcaster is a **registered, explicit, total** transformation from one **registered** version of an `event_type` to a **later registered** version of the **same** `event_type`. |
| UC2 | An upcaster is registered against `(event_type, from_version, to_version)` and appears in the registry entries of both versions. |
| UC3 | An upcaster is a **consumer-side adaptation**: the producer's published versions are immutable and the producer has moved on. It exists so a consumer can support an old version without maintaining a second native handler. |
| UC4 | An upcaster may be registered **only if the transformation is total** — defined for every valid instance of `from_version` — and only if any value it must supply comes from a **rule stated in the registry entry**, never from a guess, never from a database read, and never from a default that could be mistaken for a real value. If the transformation cannot be total on those terms, the consumer keeps a **native** handler for the old version. That impossibility is usually the reason the new version exists. |
| UC5 | An upcaster is **pure**: no I/O, no clock, no randomness, no state. The same input always produces the same output, so a replay is deterministic. |
| UC6 | An upcaster **never applies to an unknown version** and never chains through an unregistered one. Unknown means quarantine (§20), always. |
| UC7 | An upcaster **never changes envelope fields** — not `event_id`, not `event_type`, not `occurred_at`. Only `schema_version` is reinterpreted, and only within the consumer's own processing. |
| UC8 | An upcaster is **not** a substitute for a native handler when the semantics differ. Upcasting a fact into a different fact is forbidden; that is BC13's new-type case. |

---

## 19. Producer emission and migration

| # | Rule |
|---|---|
| PE1 | A producer emits **exactly one registered `schema_version` per logical message instance**. One instance, one version, one `event_id`. |
| PE2 | **No producer may emit an unregistered `event_type`, an unregistered `schema_version`, a `DRAFT` version or a `RETIRED` version** (RI10, RI11, RG3, RG6). |
| PE3 | At most **one `ACTIVE` emission version per (technical producer, `event_type`)**, except during a migration window recorded in the registry with an explicit end condition (RI7). |
| PE4 | **Dual-publishing v1 and v2 of the same logical fact is not the default and is discouraged.** Where a deliberate migration plan requires it, the two emissions are **two distinct message instances with two distinct `event_id`s** and are recorded as such, so that a consumer can never mistake them for two deliveries of one message (§21 IX4) nor apply both effects to one fact. The registry entry states which side is responsible for suppressing the duplicate business effect. |
| PE5 | The default migration sequence is **consumer-first** and is frozen: |

```text
1. Register vN+1 as DRAFT; review the contract with the owner.
2. Deploy consumers that support BOTH vN and vN+1 (native or via a registered upcaster, §18).
  Verify support is live before step 3.
3. Promote vN+1 to ACTIVE; switch the producer to emit vN+1. Mark vN DEPRECATED —
  it may still arrive; it is no longer emitted.
4. Drain the vN backlog. Prove no retained, queued, quarantined or replayable
  vN message remains within retention (§30 RR2).
5. Only then: retire vN, and only then may a consumer drop vN support.
```

| # | Rule |
|---|---|
| PE6 | Steps 2 and 3 are never reordered. A producer that emits a version before its consumers support it manufactures a quarantine incident out of an ordinary deployment. |
| PE7 | Step 5's "proof" is evidence, not confidence: no queued or unprocessed row of that version, no quarantined instance awaiting replay, and no retained partition within the replay window that could contain one (§30). "We deployed a while ago" is not evidence. |
| PE8 | Rolling back a producer to an earlier version is legal **only while that earlier version is still `ACTIVE` or `DEPRECATED` and still supported**. Rolling back to a retired version is emitting a retired version (PE2). |

---

## 20. Unknown or invalid messages

This is the rule the rest of the design exists to make enforceable.

### 20.1 The decision

> **An unknown `event_type`, an unknown or unsupported `schema_version`, or a payload that is invalid
> for a known version becomes a durable quarantined message plus an operational alert. It is never
> processed, never marked as successfully HANDLED, and never retried indefinitely on the normal
> queue. Once quarantine is durable, the delivery is terminally removed from the normal processing
> path (§20.3).**

### 20.2 Rules

| # | Rule |
|---|---|
| QU1 | Such a message is **never silently ignored** and never dropped. |
| QU2 | It is **never coerced** — not into a known version, not into a partial object, not by discarding unknown fields, not by supplying defaults. |
| QU3 | It is **never treated as the latest**, the nearest, or the most similar known version (CS5). |
| QU4 | It is **never marked as successfully HANDLED**: never recorded as Inbox `HANDLED`/`SUCCEEDED`, never recorded as having produced its intended business effect, never treated by business logic as processed. This is a statement about **semantic completion**, not about the broker (QU13). |
| QU5 | It is **never partially consumed.** A handler does not apply "the part it understood" (§28 VL5). |
| QU6 | It is **not retried forever on the normal queue.** Endless retry of a message that cannot ever succeed is an outage of the queue it sits on, not resilience. |
| QU7 | The outcome is **durable quarantine**: the message is retained in full, with its envelope, its payload, the reason for rejection and the identity needed to replay it after the defect is fixed. |
| QU8 | The outcome **raises an operational alert**. Master `# 23.3` already names this alert (*Event Schema Reject: consumer received an unsupported `event_version` — alert + DLQ, no silent fallback*); item 8 widens its trigger to unknown types and invalid payloads. |
| QU9 | **Quarantine state is durable and identity-bearing.** The consumer's Inbox/quarantine state retains enough identity (at minimum `event_id`, `event_type`, `schema_version` and the rejection reason) that a redelivery of the same message is recognised as already quarantined and does **not** re-enter the processing loop. Preventing an infinite hot loop is part of the frozen semantics, not an optimisation. |
| QU10 | Quarantine is a **terminal state for that delivery**, not a business outcome. It is never surfaced as a domain error, never mapped to a business state transition, and never causes a compensating business action on its own. |
| QU11 | Replay out of quarantine is an explicit, authorised operation that preserves `event_id` and `occurred_at` (ID3, TS3) and re-enters validation from the start. |
| QU12 | **Item 9 owns the topology** — which queue, which DLQ, per-failure-domain isolation, replay tooling and the alert routing (master `# 20.1`'s `ext.*.dlq` shape). Item 8 freezes only the semantic result above. **Item 8 invents no table name and no queue name.** |

### 20.3 Semantic completion vs transport disposition

QU4 is about **business semantics**; it does not forbid the transport from disposing of the delivery.
The order is what matters:

```text
validate
  → persist durable quarantine + rejection identity
  → COMMIT the quarantine state
  → terminally remove that delivery from the normal processing path
```

| # | Rule |
|---|---|
| QU13 | **Once the quarantine state has committed**, the transport **may** perform the appropriate terminal disposition of that delivery — ack after quarantine, reject/nack without requeue, or the equivalent broker-specific operation. The message is durable elsewhere; leaving it on the normal queue would achieve nothing but QU6's hot loop. |
| QU14 | **The transport must never dispose of the delivery before quarantine durability commits.** Acking first and persisting afterwards loses the message on a crash between the two. |
| QU15 | A transport disposition is **not** a semantic completion. It never sets Inbox `HANDLED`/`SUCCEEDED`, never records a business effect, and is never reported as successful processing (QU4). |
| QU16 | The two invariants together: **never lose the message before quarantine is durable, and never leave a permanently invalid message hot-looping on the normal queue.** |
| QU17 | **The exact transport action and topology — which broker operation, which queue it lands on, which DLQ — is item 9's.** Item 8 freezes no broker acknowledgement API and names no operation as required. |

---

## 21. Message identity integrity and consumer idempotency

These are **two separate responsibilities** and were conflated in an earlier draft. Message-identity
integrity is a **mandatory, universal** observation about the message; business-effect idempotency is
a **per-handler** guarantee about the effect. One never substitutes for the other.

### 21.1 Message-identity integrity — mandatory for every consumer

| # | Rule |
|---|---|
| IX1 | Delivery is **at-least-once**. Duplicate delivery of the same `event_id` is normal, expected, and never an error condition (master `# 20`). |
| IX2 | **Every registered consumer durably retains, on first sight of an `event_id`, enough identity to verify every subsequent delivery of it.** Conceptually: `event_id`, `event_type`, `schema_version`, a canonical payload fingerprint, and whatever processing/terminal identity state the handler needs. The record is durable in PostgreSQL (R9). |
| IX3 | Deterministic canonical serialization (PD5, SZ4) is what makes the fingerprint meaningful; without it, IX5 could not be decided. |
| IX4 | A redelivery of the same `event_id` with the **same** `event_type`, `schema_version` and payload is an ordinary **duplicate delivery**: the handler does not repeat the effect and completes normally. |
| IX5 | The same `event_id` with a **materially different** `event_type`, `schema_version` or payload is a **data-integrity violation**, not a duplicate. It is quarantined and alerted (§20), the conflicting delivery is **never applied**, and it never overwrites the recorded first observation. This is what a producer bug, a mis-copied identity or a corrupted row looks like, and it must be loud. |
| IX6 | **IX2 and IX5 apply to every registered consumer, without exception, regardless of how its business effect is made idempotent.** No registry entry may declare IX5 detection unavailable, and no handler may opt out on the grounds that its effect is naturally idempotent. |
| IX7 | Item 8 designs **no Inbox/dedupe/quarantine SQL schema, no column list, no index and no partition strategy.** Master `# 20.3`'s `(provider, external_event_id, payload_hash)` compact-dedupe shape is the existing precedent for the external case; whether internal `event_id` identity reuses that shape or a sibling structure is Phase 1's, informed by item 9. |

### 21.2 Business-effect idempotency — chosen per handler

| # | Rule |
|---|---|
| IX8 | **The consumer-visible business effect happens once** per `event_id`, no matter how many times it is delivered. |
| IX9 | The mechanism guaranteeing IX8 is **durable in PostgreSQL** (R9). **Redis is never the only protection**; it may be an L1 anti-storm filter and nothing more (master `# 5`, `# 20.4`). |
| IX10 | Master `# 20.4`'s three durable mechanisms remain the admissible ones for the **effect**. The choice is made **per consumer/handler**, not once per message version, and each consumer's choice is **recorded against that consumer** in the registry (IX13): |

| Mechanism | When it is the right one |
|---|---|
| **(a) Inbox/`event_id` completion dedupe** | The default. **Mandatory** whenever the effect is not idempotent by construction. Its completion record is naturally colocated with the IX2 identity record, but the two obligations remain distinct. |
| **(b) A domain uniqueness constraint or a state-machine transition that is idempotent by construction** | The effect is already exactly-once by a DB constraint or a legal-transition guard (master `# 20.4`'s "domain unique/state machines" for worker retries). The registry entry must state **why** the effect is naturally idempotent. |
| **(c) An `IdempotencyKey`-scoped command** | The handler invokes a durable idempotent use case that owns its own key (ADR-0007, item 5 §11). |

| # | Rule |
|---|---|
| IX11 | **Mechanisms (b) and (c) satisfy IX8 only. They never discharge IX2 or IX5** — a naturally idempotent effect says nothing about whether two deliveries claiming one `event_id` carried the same content. The identity record is required either way. |
| IX12 | Idempotency of the *consumer* never substitutes for idempotency of the *business command* it calls, and vice versa. They are separate mechanisms at separate levels (master `# 20.4`). |
| IX13 | **The declaration is per consumer.** For every declared consumer of every `ACTIVE` or `DEPRECATED` version, the registry records that consumer, its exact supported version(s), its business-effect idempotency mechanism — (a), (b) or (c) — and the justification for it: |

```text
consumer
  → exact supported version(s)
  → business-effect idempotency mechanism: (a) | (b) | (c)
  → justification
```

| # | Rule |
|---|---|
| IX14 | An **`EVENT`** may have several independent consumers, and **different consumers of one version may legally choose different mechanisms** — the effect each one performs is its own. A single mechanism stated for the whole entry would be either wrong or meaningless. |
| IX15 | A **`COMMAND`** has exactly one handling owner (KD3), so its per-consumer declaration naturally contains exactly one handler. The rule is the same; the cardinality is what differs. |
| IX16 | The per-consumer effect declaration never varies the **identity-integrity** obligation, which is one universal rule (`event_id`, `event_type`, `schema_version`, canonical payload fingerprint) binding every consumer regardless of the mechanism it chose (IX2, IX5, IX6, IX11). |

---

## 22. The handler transaction rule

### 22.1 The shape

```text
BEGIN                                  # one local PostgreSQL transaction
  claim / deduplicate the Inbox record for event_id      (§21)
  perform the durable local effect
  write any resulting Outbox message rows                (R5)
  mark the Inbox record handled
COMMIT
```

### 22.2 Rules

| # | Rule |
|---|---|
| HT1 | Where atomicity is required for correctness, the claim, the durable effect, the resulting Outbox rows and the Inbox completion happen in **one local PostgreSQL transaction**. |
| HT2 | **The Inbox record is never marked successfully handled before its durable effect commits.** A completion visible without its effect is exactly the state that turns an at-least-once system into a lost-message system. |
| HT3 | **No external provider I/O inside that transaction** (R11) — no HTTP, no SDK call, no third-party SDK's implicit network access, regardless of timeout. |
| HT4 | Where a consumer's work genuinely requires provider I/O, the shape is: |

```text
consume the message
  → persist local workflow state and/or the next Outbox intent
  → COMMIT
  → perform the external workflow through its application port    (ADR-0005 §2)
```

| # | Rule |
|---|---|
| HT5 | Item 4 §12's transaction-participation rules and item 5's placement rules are unchanged. A handler is an ordinary caller: one semantic operation, no independent commit inside a domain command, no `durable=True` inside a nested call. |
| HT6 | **No saga machinery, no orchestrator, no compensation framework and no distributed transaction is designed here.** ADR-0004 §10's "local ACID is not a saga" stands; a durable local transaction plus at-least-once delivery plus idempotent handlers is the whole model. |
| HT7 | A handler that cannot complete for a **technical** reason (database unavailable, lock timeout, transient fault) fails and is retried by the transport (R8) with the same `event_id` (ID3). That is not quarantine; quarantine is for messages that can never succeed (§20). |
| HT8 | A handler that fails for a **business** reason states so through the owning module's public error contract (item 4 §13). Whether that is retryable, terminal or a quarantine case is the handler's declared policy, recorded in the registry entry — never an unclassified swallowed exception. |

---

## 23. Causality and event chains

| # | Rule |
|---|---|
| CA1 | A message emitted **while handling another message** must be able to preserve causal/trace linkage back to it. Master `# 20.7`'s target trace (`HTTP checkout → place_order → Outbox(order.placed) → relay → ERP export / email / fiscalization`) depends on this. |
| CA2 | **Item 10 owns the fields.** Item 8 defines no `trace_id`, no `span_id`, no `request_id`, no `correlation_id` and no `causation_id`, and takes no position on which of these exist. Master `# 20.2`/`# 20.6` already name `trace_id`/`span_id`/`request_id` on the durable row; confirming, extending or replacing that set is item 10's decision, not a fact item 8 may lean on. |
| CA3 | Item 8 reserves **one envelope extension point** for those fields (EN6). It is an extension point, not a bag: item 10 names a closed set of fields, and EN7 continues to forbid a free-form map. |
| CA4 | **`schema_version` versions the payload, never observability metadata** (SV2, SV7). Adding, renaming or removing an item 10 envelope field does not bump any message's `schema_version`, and an envelope-level compatibility signal — if one is ever needed — is item 10's problem plus an ADR. |
| CA5 | Causal linkage is **observability and diagnosis**, never a correctness mechanism. No handler may branch on it, no ordering may be derived from it, and no idempotency decision may depend on it (§24, §21). |
| CA6 | Losing trace continuity across the asynchronous boundary is an observability defect (master `# 23.4`), not a message-contract defect. |

---

## 24. Ordering

| # | Rule |
|---|---|
| OR1 | **Consumers must not assume global ordering across messages.** There is no total order, across types, across producers, or across instances of one type. |
| OR2 | **Broker ordering is never relied upon for correctness.** Retries, per-queue concurrency, failure-domain isolation (master `# 20.1`), DLQ replay and partition replay all reorder freely. |
| OR3 | **`occurred_at` is not an ordering key** (TS4). Neither is an Outbox row id, which orders *insertion into one table*, not the facts of one entity across producers, and is not preserved across replay. |
| OR4 | **Duplicate delivery is normal. Out-of-order delivery is normal.** Both are contract-level expectations, not incidents. |
| OR5 | Where ordering matters for **one source entity or fact stream**, the contract or the owning state must give the consumer enough information to **recognise and reject stale state** (SR6). "The queue will deliver them in order" is not a design. |
| OR6 | **`schema_version` is the schema version. It is not a source version, not a business revision, not an aggregate version and not an ordering key.** Using it to decide which of two messages is newer is a defect, and one this design must be read as forbidding explicitly (SV9, checks A47/V56). |
| OR7 | The concrete stale-update mechanism for the storefront projection — the `source_version` column, its generation, its per-source mapping and the guarded upsert SQL — is **entirely item 12's** (item 6 §16.2, PU8). Item 8 neither designs it, nor constrains it, nor may be cited as authority for a version scheme. |
| OR8 | Master `# 20.6`'s own example is the clearest statement of OR6: its dataclass carries `version: ClassVar[int] = 1` (the **schema** version, envelope-level) alongside a `source_version: int` **payload field** (the **ordering** version). Two numbers, two levels, two owners — item 8 and item 12. |

---

## 25. The registry artifact

The registry lives at [`docs/architecture/events/event-registry.md`](../events/event-registry.md).

### 25.1 Entry columns

| Column | Meaning |
|---|---|
| `event_type` | The stable owner-qualified name (§8). |
| `schema_version` | Positive integer (§14). |
| `kind` | `EVENT` or `COMMAND` (§7). Fixed for the life of the type. |
| `status` | `DRAFT` / `ACTIVE` / `DEPRECATED` / `RETIRED` (§25.2). |
| `semantic owner` | The single owning module (§5). Identical across every version of the type. |
| `payload contract` | Where the canonical schema source lives, as an owner-internal location (§27). |
| `producer(s)` | The technical emitter(s). Equal to the owner unless a delegation is recorded (RI9). |
| `consumers` | One declaration **per consuming module**: the consumer, its exact supported version(s), **its own business-effect idempotency mechanism** — IX10 (a)/(b)/(c) — and the justification for it (IX13). Different consumers of one version may legally differ (IX14); a `COMMAND` has exactly one such declaration, its single handling owner (KD3, IX15). This never covers the mandatory identity-integrity obligation, which is separate and binds every consumer alike (IX6, IX11, IX16). |
| `introduced` | Date and phase. |
| `emitted in production` | Whether current production code emits this version. |
| `exposure` | `internal-only` or `externally-consumed` (PD14). |
| `supersedes` | **Forward** lineage, declared once on the newly introduced row, including retire-and-introduce pairs (BC16, RM2). The reverse `superseded by` view is derived from registry data (RM2, RM3). |
| `upcasters` | Registered `from_version → to_version` transformations (§18). |
| `notes` | Compatibility and migration notes, ordering/staleness handling (SR6), PII/privacy classification (§31), and the reason for the version. |

### 25.2 Statuses

| Status | Meaning |
|---|---|
| `DRAFT` | Registered so the name, version and contract can be reviewed. **Must not be emitted.** No durable row of this version may exist anywhere. Its contract may still be edited (IM1). |
| `ACTIVE` | May be emitted, and its declared consumers must handle it. Its contract is frozen (IM2). |
| `DEPRECATED` | **Must not be newly emitted** by any producer. May still legitimately arrive from backlog, retry, DLQ or partition replay, so **consumer support remains mandatory**. Contract still frozen. |
| `RETIRED` | No legitimate backlog, replay or consumer requirement remains, and that has been **proved** (PE7, RR2). Must not be emitted. Consumer support may be removed. An arrival of a retired version is an unknown-version quarantine event (§20). |

| # | Rule |
|---|---|
| RG1 | Status transitions are **one-way**: `DRAFT → ACTIVE → DEPRECATED → RETIRED`. No status ever moves backwards. |
| RG2 | Reviving a retired version is not possible; the answer is a **new version** (SV3, RI6). |
| RG3 | A `DRAFT` version must not be emitted — this is the property that makes IM1's editability safe. |
| RG4 | `ACTIVE` and `DEPRECATED` differ only in emission: both must be consumable. |
| RG5 | `DEPRECATED` is not a soft delete. It is a live obligation on every declared consumer. |
| RG6 | `RETIRED` requires the evidence of PE7/RR2 recorded in the entry, not an assertion. |
| RG7 | A type is retired when **all** of its versions are retired. |
| RG8 | The registry ships with **no entries**. Populating it is each owning module's own phase. Item 8 defines the shape and the rules, and deliberately invents no catalogue (§1.2). |
| RG9 | Maintaining the registry confers **no** ownership (OW5). A registry edit that changes a contract without its owner's decision is invalid regardless of who made it. |

---

## 26. Registry invariants

### 26.1 Two classes of registry field

A registry entry carries a contract and an operational record. Conflating them either freezes fields
that must evolve (`emitted in production` can never be a permanent statement) or licenses editing the
ones that must not.

**Immutable from publication — the semantic identity and schema contract:**

| Field | Why |
|---|---|
| `event_type` | Externally immutable; appears in durable rows, alerts and runbooks (NM7, NM8). |
| `schema_version` | RI5, RI6. |
| `kind` | Fixed for the life of the type (KD4, RI12). |
| `semantic owner` **for that `event_type`** | Owner-qualified by construction (NM2); see §26.2. |
| canonical payload contract/schema for that version | §15, SC1. |
| payload **field semantics** | IM2, BC8 — the meaning, not just the field list. |
| `exposure` for that version | Changing it changes which identifiers are legal (PD14, PD15, BC5). |
| `introduced` identity/date | A historical fact. |

**Mutable, under its own rules, without touching the payload schema — the audited operational record:**

| Field | Governing rule |
|---|---|
| `status` | One-way transitions only (RG1). |
| current consumer support declarations | CS1, CS9, RI14. |
| registered `upcasters` | UC1–UC8, RI15. |
| `notes`, including retirement proof | RG6, RR3, RR5. |
| current `emitted in production` state | A live operational fact; it necessarily changes at every migration step. |
| technical-producer delegations | **Only** under RI9's explicit, recorded delegation rule. |
| per-consumer effect-idempotency **implementation/mechanism** declarations | IX10, IX13 — legal **only** while the semantic effect contract is unchanged. A change to what the effect *means* is a contract change, not a metadata edit. |

| # | Rule |
|---|---|
| RM1 | Editing the operational half is a normal, audited registry operation. Editing the contract half of a published version is not an operation at all — the answer is a new version (§15, §16). |
| RM2 | **Lineage is declared forward, once, on the newly introduced row**: `supersedes = <old type/version>`. The old row's `superseded by` is **derived** from registry data. Adding a reverse pointer is never a reason to edit a published row. |
| RM3 | If a stored reverse pointer is kept for convenience, it is explicitly **mutable derived registry metadata**, not contract schema, and carries no semantic weight of its own. |

### 26.2 Semantic owner cannot change in place

Because `event_type` is **owner-qualified** (NM2), the owner is part of the name, and the name's
meaning is immutable (NM7). An already-published type's semantic owner therefore cannot be edited: a
row whose owner column disagreed with its own first name segment would be self-contradictory.

| # | Rule |
|---|---|
| RM4 | If responsibility genuinely moves to another module, the operation is a **retire-and-introduce**: deprecate then retire the old owner-qualified `event_type`, and introduce a **new** owner-qualified `event_type` at `schema_version = 1` (BC16). The old name is never reused (RI3). |
| RM5 | **Editing `semantic owner` on an existing type is never the mechanism**, with or without an ADR. An ADR is separately required when the move changes a frozen module or domain boundary — but the ADR authorises the re-homing, it does not authorise an in-place edit. |

### 26.3 Invariants

| # | Invariant |
|---|---|
| RI1 | `(event_type, schema_version)` is **unique**. |
| RI2 | **Exactly one semantic owner per `event_type`**, identical across all its versions (OW1, OW6). |
| RI3 | An `event_type` is **never reused** for a different semantic fact, including after retirement (NM7). |
| RI4 | A published `event_type`'s **semantic owner is immutable and is never edited in place** (RM4, RM5). Moving responsibility is a retire-and-introduce under a new owner-qualified name; where the move changes a frozen module or domain boundary it additionally requires an **ADR**. |
| RI5 | `schema_version` starts at `1` and **strictly increases** within a type. |
| RI6 | Version numbers are **never reused**, including after retirement (SV3). |
| RI7 | **At most one `ACTIVE` emission version per (technical producer, `event_type`)**, unless a migration exception with an explicit end condition is recorded in the entry (PE3, PE4). |
| RI8 | A published version's **contract fields are immutable** (§26.1 first table). Its **operational fields** (§26.1 second table) evolve under their own rules, and doing so never changes the meaning of the version (IM6, RM1). |
| RI9 | **One semantic owner; a second technical producer only by explicit, recorded delegation from that owner.** Accidental multi-producer semantics — two modules that both "naturally" emit the same fact — is a modelling error: either the fact has one owner and the other module emits its own distinct fact, or the fact belongs to a module that owns neither and must be re-homed. A delegation entry names the delegate, the reason and the review date. |
| RI10 | **No `RETIRED` version is emitted**, and no `DRAFT` version is emitted (PE2). |
| RI11 | **No unregistered message is emitted.** An emission whose `(event_type, schema_version)` has no entry is a build/CI failure (A42), and at runtime a producer-side integrity failure. |
| RI12 | `kind` is fixed for the life of a type (KD4). |
| RI13 | Every `ACTIVE` and `DEPRECATED` entry names its **exposure** classification (PD14), and **every declared consumer of it** names its own business-effect idempotency mechanism with a justification (IX13). One mechanism stated for the whole entry does not satisfy this. No entry and no consumer declaration may claim IX5 identity-integrity detection is unavailable — IX2/IX5/IX6 bind every consumer unconditionally. |
| RI14 | Every `ACTIVE` and `DEPRECATED` entry has a **complete consumer list** for the versions still requiring support; a consumer that handles a message without a registry row is a defect on both sides. |
| RI15 | Every registered upcaster references two registered versions of the **same** type, with `from_version < to_version` (UC1, UC2). |

---

## 27. The canonical schema source

| # | Rule |
|---|---|
| SC1 | There is **exactly one canonical schema source per `(event_type, schema_version)`**, owned by and located inside the owning module's package (PI4). |
| SC2 | Every other representation — validator input, JSON Schema document, registry table, generated documentation, test fixtures — is **derived** from it. |
| SC3 | **Two hand-maintained schemas for one version are forbidden.** Two sources that must agree, agree until the day they do not, and the failure surfaces as a production message that one side accepts and the other rejects. |
| SC4 | The canonical source must be able to **outlive the producing implementation**: a `DEPRECATED` or retained-`RETIRED` version's schema stays available for as long as a message of that version could still be read (IM3, RR3). Deleting a producer's current code must never make an old durable row undecodable. |
| SC5 | The canonical source is **owner-internal** and is never imported across a package boundary (PI2, PI3). |
| SC6 | Phase 1 chooses the concrete form. The options evaluated, none of which is frozen here: |

| Option | Assessment |
|---|---|
| **Python immutable dataclass contract as canonical, validation/JSON Schema generated from it** | Matches item 4 §7's DTO discipline and keeps one authored artifact. **Requires** the generated schema data to be checked in and versioned (PI8, PI9) so §6.3's pipeline works without importing the producer. |
| **A data schema (JSON Schema or equivalent) as canonical, typed structures generated from it** | Language-neutral and already in the shape §6.3 needs; further from the codebase's existing DTO idiom. Used directly by the validator; any other representation is generated from it (PI9). |
| **Both hand-written** | **Rejected outright** by SC3. |

| # | Rule |
|---|---|
| SC7 | Whichever is chosen must satisfy §6.3's frozen pipeline and PI7–PI11: one canonical owner-internal source, a deterministic generation step, a checked-in versioned data artifact, no consumer → producer import, and no import of an owner-internal contract by the composition root. The pipeline, not the tool, is the frozen part. |
| SC8 | The canonical source is **versioned in the repository**, reviewed like any contract, and never generated at runtime from live code introspection — introspecting the current classes tells you what the code does today, not what the March row meant. |

---

## 28. Validation

| # | Rule |
|---|---|
| VL1 | The **producer validates** the payload against the registered schema **before** the message is written to the Outbox, inside the emitting transaction. An invalid message is never made durable. |
| VL2 | The **consumer validates** the envelope and payload against the registered schema **before** any business logic is invoked. |
| VL3 | Validation is **strict against the exact version** (CS6): the declared field set, the declared types, the declared requiredness, the declared enumerations, the declared bounds (PD4). An unknown field is a validation failure, not a tolerated extra. |
| VL4 | A **known type and version with an invalid payload is not a domain or business failure.** It is a contract/infrastructure integrity failure: quarantine + alert (§20), never a business error, never a state transition, never a compensating action (QU10). |
| VL5 | **No best-effort partial consumption.** A handler never applies the part of a payload that validated. |
| VL6 | Validation **must not rely on trusting the producer's Python classes alone.** Durable rows outlive the code that wrote them, replay crosses deployments, and a producer bug is exactly the case validation exists to catch. The check is against the registered schema for the row's declared version (SC4, SC8). |
| VL7 | A producer-side validation failure is a **producer defect**: it fails loudly, aborts the emitting transaction with the business operation, and is never silently downgraded to "emit anyway". |
| VL8 | Item 8 chooses **no validation or serialization library**. Phase 1 does. |

---

## 29. Serialization

| # | Rule |
|---|---|
| SZ1 | The canonical durable and on-the-wire representation of envelope and payload is a **JSON-compatible structure**. Master `# 20.2`/`# 20.3` already store `payload`/`raw_payload` on the durable rows and master `# 20.6` speaks of old JSON; item 8 records JSON-compatibility as the frozen representation class. The physical column type (`jsonb` vs alternatives) is Phase 1's. |
| SZ2 | **Forbidden**: `pickle`, `marshal`, `shelve`, any Python-object serialization, any format whose decoding can execute code or instantiate arbitrary classes, and any format that requires the producer's classes to be importable in order to decode (PI2, VL6). |
| SZ3 | Only **serialization-neutral primitives** appear in the encoded form: strings, integers, booleans, null, arrays and objects with string keys. Money is minor units plus an explicit currency string; instants are aware-UTC textual instants; decimals are exact textual or integer-scaled representations, never binary floats (PD9). |
| SZ4 | Serialization is **deterministic**: the same logical payload always produces the same canonical bytes (stable key order, stable number and instant formatting, no locale dependence). This is what makes the IX7 fingerprint and the §32 integrity check meaningful. |
| SZ5 | Inspectability is a requirement, not a nicety: an operator reading a quarantined row, a retained partition or a DLQ entry must be able to understand it without running application code. |
| SZ6 | **No binary schema system** (protobuf/avro/msgpack and friends) is introduced. The master does not require one, and adding one would add a second schema authority against SC1/SC3. Introducing one later is an ADR. |
| SZ7 | The broker message body carries the same canonical representation; the transport library is Phase 1's, and no transport-specific encoding may become a second contract (S10). |

---

## 30. Replay and retention

| # | Rule |
|---|---|
| RR1 | Persisted Outbox rows, Inbox rows and quarantined messages routinely **outlive the producer code that wrote them** (master `# 20.5`'s partition lifecycle). Versioning is only meaningful if this is treated as normal. |
| RR2 | A consumer **must retain support for every version that can still legitimately arrive**: queued, unprocessed, retrying, quarantined-awaiting-replay, or present in an online retained partition within the replay window. |
| RR3 | **Deleting a decoder, a native handler or an upcaster requires proof** that no retained, backlogged or replayable message needs it (PE7). The registry records that proof at retirement (RG6). |
| RR4 | A retired version's **schema stays in the repository** as long as any archived message of that version could still be read for a legal, financial or forensic reason, even after its handler is gone (SC4, IM3). |
| RR5 | Retirement is a **deliberate, recorded act**, never an inferred consequence of "nobody has seen one lately". |
| RR6 | **Numeric retention periods, replay windows and alert thresholds are not frozen here.** Master `# 20.5` and `# 23.3` own the policy shape; the numbers belong to the operations phases. |
| RR7 | A **full storefront projection rebuild does not replay historical messages** — item 6 RB1/RB2 froze rebuild from OLTP truth, and an archived Outbox partition can never make the projection unreconstructible (R14). Nothing in item 8 creates an event-sourcing dependency for any read model. |
| RR8 | No mechanism in this artifact may be read as making the Outbox an **event store**. It is a delivery mechanism with retention, not a history of record. |

---

## 31. Security and privacy

| # | Rule |
|---|---|
| SEC1 | A payload carries **only the data its intended consumers need** (SR2). Minimisation is a contract rule, not a review suggestion. |
| SEC2 | **Never in a payload**: secrets, API keys, access or refresh tokens, signing keys, provider credentials, session identifiers or cookies, passwords or password hashes, raw card data, CVV, full PAN, payment provider secrets, or any value whose disclosure would be a security incident. |
| SEC3 | **Never in a payload**: a full customer object, a full user profile, or PII beyond the minimum the consumer legitimately requires. Where a consumer needs customer-scoped data, prefer an identifier the consumer re-reads under its own authorization (SR3) over a copied personal-data snapshot. |
| SEC4 | **The message bus is not a private-data broadcast channel.** A consumer's ability to read a payload field is not authorization to use it; ownership and access boundaries survive the asynchronous boundary intact (ADR-0004 §6). |
| SEC5 | **A payload is never an authorization decision.** No handler treats "the message contained it" as proof that the actor was permitted (item 6 SEC3's analogous rule for the projection, ADR-0008). |
| SEC6 | Every registry entry carries a **privacy classification** in its notes: whether the payload contains personal data, and which categories. An entry that carries personal data is a consent/retention concern in the security and privacy phases (master `# 21`), and the classification is what makes it findable then. |
| SEC7 | Item 8 adds **no actor to the envelope**. Where an async consumer must perform a protected operation, the actor is reconstructed by the transport (item 3 §4.6, ADR-0006 §1) or the operation runs under an explicit system context (item 4 §11). Whether a payload carries a principal *reference* is the owning module's contract decision, bounded by SEC1–SEC3. |
| SEC8 | Payload content is subject to the platform's redaction rules in logs, traces, alerts, fixtures and quarantine displays (master `# 20.8`, `# 21`, `# 23.1`). A quarantined message is retained (QU7) but is not thereby exempt from redaction in what is *displayed*. |
| SEC9 | **Exact privacy retention, erasure and anonymization rules for message payloads belong to the security/privacy phases**, not here. Item 8 freezes the minimisation rule and the classification obligation. |

---

## 32. Failure matrix

**Commercial impact** is assessed against the frozen invariants: no order, payment, reservation or
price outcome may depend on message delivery (SR4, R10, R14).

| # | Situation | Consumer effect | Commercial impact | Resolution |
|---|---|---|---|---|
| 1 | Duplicate delivery, same `event_id`, same content | Effect applied once (IX2) | None | Normal operation (IX4) |
| 2 | Out-of-order delivery within one entity's stream | Stale message recognised and rejected by the fact/state contract (OR5); for projections, item 12's guard | None — checkout revalidates (SR4, item 5 §7.4) | Normal operation (OR4) |
| 3 | Same `event_id`, different payload/type/version | No effect | None | **Quarantine + alert** as an integrity violation (IX5) |
| 4 | Unknown `event_type` | No effect, never marked HANDLED | None | **Quarantine + alert** (§20); investigate producer or deployment order |
| 5 | Known type, unsupported/unknown `schema_version` | No effect, never marked HANDLED | None | **Quarantine + alert** (§20, QU3); usually PE6 violated — fix by deploying consumer support, then replay |
| 6 | Known type and version, invalid payload | No effect, no partial application (VL5) | None | **Quarantine + alert** as an integrity failure (VL4); producer defect |
| 7 | Retired version arrives | No effect | None | Treated as unknown (RG-`RETIRED`) → quarantine + alert; retirement proof (RR3) was wrong |
| 8 | Handler technical fault (DB unavailable, lock timeout) | No effect; not marked handled (HT2) | None | Transport retry with the same `event_id` (HT7) |
| 9 | Handler crash after the local effect commits but before the ack | Effect committed once; message redelivered | None | Redelivery is recognised as a duplicate (IX4) and the effect is not repeated (IX8) |
| 10 | Handler crash after ack but before an external port call (HT4) | Local state committed; external step not yet performed | None commercially; the external workflow is pending | The next Outbox intent / retry drives the external step; provider interaction stays post-commit (R11) |
| 11 | Relay lag or backlog | Consumers lag; state converges late | None — item 5 EV5, item 6 CM1 | Alert on relay lag (master `# 23.3`) |
| 12 | Producer emits an unregistered `(type, version)` | Nothing consumes it | None | CI should have caught it (A42); at runtime the emission is an integrity failure (RI11) |
| 13 | Producer switched to vN+1 before consumers supported it (PE6 violated) | vN+1 quarantined | None | Deploy consumer support, replay from quarantine (QU11) |
| 14 | Old-version backlog still draining during migration | Both versions handled by the consumer (CS7) | None | Normal step 4 of PE5 |
| 15 | Outbox partition archived before delivery | Those messages are gone | None for the projection (RR7); for a business workflow, the owning module's reconciliation covers it (master `# 12.3`, `# 20.1`) | Retention policy defect; reconciliation + alert |
| 16 | Quarantined message redelivered repeatedly | Recognised as quarantined; no reprocessing loop (QU9) | None | Operational triage |
| 17 | Provider changes its wire schema | Internal contract unaffected (S14) | None | Adapter/translation change at the integration edge only |

---

## 33. Checks a later phase must implement

Continuing the numbering established by items 3–7 (`A41`, `C54`, `V51` were the last used).

### 33.1 Static / AST (`A` series)

| # | Check |
|---|---|
| A42 | **No unregistered emission.** Every emission site's `(event_type, schema_version)` resolves to a registry entry whose status permits emission. A literal or computed type/version with no entry fails the build (RI11, PE2). |
| A43 | **No unknown-version fallback.** No consumer dispatch has a default/else/catch-all branch over `schema_version`, no `max(supported)` or "nearest version" selection, and no `try v2 except: v1` shape (CS2–CS5). |
| A44 | **No provider SDK type, vendor DTO, wire codec type or raw provider status** appears in a message contract module or in a payload field type (PD6, S12, item 3 V3). |
| A45 | **No ORM object in a payload**: no `Model` class or instance, `QuerySet`, `Manager`, `Prefetch`, expression object, `values()`/`__dict__` expansion, Django request/response, DRF serializer, or Celery task object in a contract module or payload field type (PD6, PD7). |
| A46 | **No business message contract in `core`.** No module under `core/` declares a message payload contract, and no `core` symbol carries business or vendor vocabulary in a message type name or field name (OW4, R2). Symmetrically: no shared cross-package contract module exists outside an owner's package (OW3, PI3). |
| A47 | **`schema_version` and `source_version` are never conflated**: no comparison, ordering, `max`/`min`, staleness guard or upsert predicate reads `schema_version`, and no payload field named `schema_version`/`event_version` is used as a revision (OR6, SV9). |
| A48 | **One canonical schema source**: exactly one canonical artifact per `(event_type, schema_version)`; a second hand-maintained schema for the same version fails (SC1, SC3). Generated artifacts are recognisably generated and are regenerated deterministically in CI. |
| A49 | **A retired or draft version cannot be emitted**: no emission site references a `RETIRED` or `DRAFT` entry (RG3, RG6, RI10). |
| A50 | **No cross-package message-contract import**: no module imports another package's message contract module — **the composition root included** (PI10) — and no registry-driven lookup returns a producer-owned contract object across a package boundary (PI2, PI3, PI5, PI10, PI11). |

### 33.2 Behavioural / contract tests (`C` series)

| # | Test |
|---|---|
| C55 | **Duplicate delivery, one effect:** the same `event_id` with identical type/version/payload delivered N times is recognised against the retained first-seen identity record and produces exactly one consumer-visible business effect (IX2, IX4, IX8). |
| C56 | **Identity integrity, for every consumer:** the same `event_id` with a different `event_type`, `schema_version` or payload is quarantined and alerted, is not applied, and does not overwrite the first observation — asserted **including** for handlers whose business effect uses mechanism (b) or (c), which never discharge this obligation (IX2, IX5, IX6, IX11). |
| C57 | **Known type, supported version:** handled exactly once, effect committed, Inbox marked complete (IX8, HT1). |
| C58 | **Known type, unsupported version:** quarantined + alerted; no effect; never marked HANDLED/SUCCEEDED (QU1–QU4, QU15). |
| C59 | **Unknown type:** quarantined + alerted; no effect (§20). |
| C60 | **Invalid payload for a known version:** quarantined + alerted; **no partial application** of the fields that did validate (VL4, VL5). |
| C61 | **Producer-side validation:** an invalid payload never becomes a durable Outbox row, and the emitting transaction fails with it (VL1, VL7). |
| C62 | **Consumer-first migration:** with consumers supporting vN and vN+1 and the producer still on vN, both are handled; after the producer switches, both continue to be handled (PE5 steps 2–3, CS7). |
| C63 | **Old backlog during migration:** vN messages written before the switch are still handled after the producer moved to vN+1 (PE5 step 4, RR2). |
| C64 | **No premature completion:** an injected failure after the local effect but before commit leaves **no** Inbox completion, **no** effect and **no** Outbox rows; the redelivery is handled normally (HT1, HT2). |
| C65 | **No provider I/O in the durable transaction:** an outbound port call inside the consumer transaction fails the test (HT3), and the post-commit shape of HT4 is asserted. |
| C66 | **Retry preserves identity:** redelivery, DLQ replay and partition replay preserve `event_id` and `occurred_at` byte-for-byte (ID3, TS3). |
| C67 | **Ordering independence:** delivering a stream of messages in a shuffled order produces the same final state as in-order delivery, and no code path uses `schema_version`, `occurred_at` or an Outbox row id to decide which is newer (OR1–OR3, OR6). |
| C68 | **Replay fixtures:** a stored fixture of every non-retired version decodes and is handled by the current consumer, with no reference to the producer's current code (RR2, VL6, SC4). |
| C69 | **Quarantine is durable before disposal, and does not hot-loop:** an injected failure between validation and the quarantine commit leaves the delivery still available (QU14); after the commit the delivery leaves the normal path without being marked HANDLED (QU13, QU15); and repeated redelivery of a quarantined message is recognised, producing no reprocessing and no repeated alert storm (QU9, QU16). |
| — | **Projection stale-update handling remains item 12's.** Item 6 C27 already covers stale/out-of-order projection updates; item 8 adds no test that fixes a `source_version` mechanism (OR7). |

### 33.3 Review-only (`V` series)

| # | Review item |
|---|---|
| V52 | A message type whose owner is chosen because a consumer needed it, rather than because the fact belongs to that module (OW1, OW8). |
| V53 | Provider vocabulary leaking inward: a provider status, error code, field name or event name appearing as an `event_type` segment, a payload field name or an enum value (S12, NM6). |
| V54 | A payload that is really a full aggregate snapshot, or one that is a bare identifier with no evidence of what changed (§13). |
| V55 | A version bumped for a non-contract reason — an implementation change, a queue change, a trace-field change (SV5, SV7). |
| V56 | `schema_version` used as an ordering or revision signal anywhere, in code or in reasoning (OR6). |
| V57 | A message reclassified from internal-only to externally consumed without a new version and a security review (PD14, PD15). |
| V58 | An "additive, harmless" field added to a published version, in any of its disguises (IM4). |
| V59 | A quarantine outcome dressed up as a business error, a business state transition, or a compensating action (QU10, VL4). |
| V60 | A second technical producer of one fact appearing without a recorded delegation (RI9). |
| V61 | Personal data, a secret or a token in a payload; or a payload treated as an authorization decision (SEC2–SEC5). |

---

## 34. Acceptance checklist

- [x] Every message type has exactly one semantic owner (OW1, RI2).
- [x] The registry indexes contracts and owns none (OW5, RG9).
- [x] No central business-event package, and no business event type in `core` (OW3, OW4, A46).
- [x] Stable `event_type` and `schema_version` are separate concepts (§8, §14, NM5).
- [x] `schema_version` starts at 1, increases monotonically, is never reused (SV1, SV3, RI5, RI6).
- [x] A published `(event_type, schema_version)` is immutable, additive change included (§15).
- [x] A different fact produces a new `event_type`, not a version bump (BC13–BC16).
- [x] `event_id` survives every retry and replay (ID3, C66).
- [x] Broker delivery ids are not event identity (ID5).
- [x] `occurred_at` survives retries and means business time (TS1, TS3).
- [x] Consumer support is exact-version and explicitly declared (CS1–CS5).
- [x] An unknown type or version cannot be silently consumed (QU1–QU4, A43).
- [x] A quarantined message is never marked business-successful, yet can still leave the normal delivery path once quarantine is durable (QU4, QU13–QU17).
- [x] An invalid payload cannot reach business logic (VL2, VL4, VL5).
- [x] Unsupported and invalid messages are durably quarantined and alerted (§20).
- [x] Duplicate delivery is idempotent (IX1, IX4, IX8).
- [x] Every consumer retains first-seen message identity, so the same `event_id` with different content is always a detectable integrity violation (IX2, IX5, IX6, IX11).
- [x] Business-effect idempotency may still use any of mechanisms (a)/(b)/(c), declared **per consumer** with its justification, so two consumers of one event may differ (IX10, IX13–IX15).
- [x] `emitted in production`, status, consumers, upcasters and notes stay mutable; the payload contract does not (§26.1, RI8).
- [x] A published type's semantic owner cannot be edited in place (RI4, RM4, RM5).
- [x] Reverse lineage is derived and never requires editing a published row (RM2, RM3).
- [x] Handler durable effect and Inbox completion are transactionally safe (HT1, HT2).
- [x] No provider I/O inside the durable consumer transaction (HT3, HT4).
- [x] Producer migration is consumer-first by default (PE5, PE6).
- [x] Old-version support is removed only after backlog/retention proof (PE7, RR3).
- [x] `schema_version` is not `source_version` and not an ordering version (SV9, OR6, OR8).
- [x] Global ordering is never assumed (OR1–OR4).
- [x] Payloads contain no ORM, vendor or transport objects (PD6, PD7, A44, A45).
- [x] Internal identifier rules stay compatible with item 4 I3/I4 (PD11–PD16).
- [x] Trace fields remain item 10's (CA2, CA3, SV7).
- [x] Queue/DLQ topology remains item 9's (QU12, EN3).
- [x] The projection stale-update mechanism remains item 12's (OR7, SR5).
- [x] No real event catalogue is invented (RG8, §8's illustrations are labelled as such).
- [x] ADR-0009 records the genuinely new decisions (§1.3).
- [x] No contradiction with ADR-0001…ADR-0008 (§36 row 12).
- [x] No Python package, model, migration, task, broker config or dependency created (§1.2).

---

## 35. Explicitly deferred decisions

| Deferred | Owner |
|---|---|
| Queue names, routing, priorities, failure-domain isolation, DLQ/quarantine queue topology, replay tooling, alert routing | item 9 |
| Trace/correlation/causation envelope field names and propagation mechanics | item 10 |
| `Money` and `PublicId` implementation, including the concrete `event_id` type | item 11 |
| `source_version` generation, per-source mapping, guarded projection upsert SQL | item 12 |
| Outbox / Inbox / dedupe / quarantine table schemas, columns, indexes, partitions | Phase 1 (master `# 20.2`, `# 20.3`) |
| Physical Outbox column names for `event_type` / `schema_version` (1:1 mapping required, §1.4) | Phase 1 |
| Whether the canonical schema is a typed Python contract or a data schema, the generator, and the artifact's file format (SC6) — the §6.3 pipeline itself is frozen | Phase 1 |
| The validation library, the serialization library, and the transport message encoder | Phase 1 |
| Physical file/module names for owner-internal contract modules (PI4) | Phase 1 |
| Whether a runtime `kind` discriminator exists, and its form (KD7) | Phase 1 |
| Every real `event_type`, its payload fields, and each of its consumers with that consumer's supported versions and effect-idempotency mechanism | each owning module's phase |
| Provider webhook wire schemas and their translation mappings | payments / ERP / CRM phases |
| Numeric retention periods, replay windows, freshness/lag thresholds, retry schedules | operations phases (master `# 20.5`, `# 23.3`) |
| Privacy retention, erasure and anonymization rules for payload personal data | security/privacy phases (master `# 21`) |
| Any binary schema system, event store, saga/orchestration framework, or third `kind` | a new ADR (SZ6, HT6, KD1) |

---

## 36. Self-review record

| # | Question | Verdict |
|---|---|---|
| 1 | Is the scope exactly item 8? | Pass — §4 draws the boundary, §1.2 and §35 name every neighbouring item's territory, and §20 QU12, §23 CA2, §24 OR7 hand back item 9, 10 and 12 explicitly at the point where the temptation to decide arises. |
| 2 | Does it design queue routing? | Pass — no. EN3 keeps transport out of the envelope, QU12 defers the topology, and no queue, exchange or DLQ name appears anywhere. |
| 3 | Does it freeze trace fields? | Pass — no. CA2/CA3 reserve an extension point and name no field; SV7/CA4 keep them off `schema_version`. |
| 4 | Does it freeze `source_version`? | Pass — no. OR6–OR8 and SR5 state repeatedly that it is item 12's, and OR8 uses the master's own example to separate the two numbers. |
| 5 | Is `core` kept free of business event types? | Pass — OW4 splits mechanism from contract, A46 is the static check, and §1.4 records the departure from master `# 20.6` openly rather than quietly. |
| 6 | Does anything create a new import edge or move a matrix cell? | Pass — §6 derives the data boundary *from* the existing matrix rather than asking for an exception, and §6.3 freezes a **data** pipeline in which no package imports an owner-internal contract. PI10 rules out startup registration by the composition root explicitly, because `config/ → domains/<x>` is `PUBLIC ONLY` and a message schema is not a `public.py` export; PI11 forbids any realisation that would need a matrix cell, a widened export list or a shared contract package. No new `L` rule is required and L1–L21 stand unedited. |
| 7 | Is the event/command decision made deliberately, with reasons? | Pass — §7.1 states the choice, names both rejected alternatives and their failure modes, and KD5 keeps one rule set. KD7 keeps it out of `core` and out of the roadmap's scope creep. |
| 8 | Is the immutable-schema policy stated as a deliberate, costed choice? | Pass — §15.1 evaluates all three options, explains why the tempting one fails under replay, and accepts the overhead in writing. |
| 9 | Does it invent a catalogue? | Pass — RG8 ships the registry empty; §8's names are labelled illustrative; master's four example names are explicitly identified as master illustrations that item 8 does not adopt. |
| 10 | Does it contradict item 4's identity rules? | Pass — PD11–PD16 restate I3 and I4 rather than reinterpreting them, add the internal-only/externally-consumed classification that I4 implied, and PD16 refuses the over-correction I4 warned against. |
| 11 | Does it preserve master `# 20`? | Pass — §1.4's table maps every master `# 20.6` requirement to a rule here; the upcaster (§18), the DLQ+alert outcome (§20), the consumer version registration (§17), the `event_name`/`event_version` pair (§1.4) and deterministic replay (§30) are all kept. One placement decision changes, and it is recorded as such. |
| 12 | Contradiction with ADR-0001…0008? | Pass — **0001/0002/0003:** untouched; no catalog or identity rule changes; PD11–PD14 reuse the frozen identity boundaries. **0004:** OW4 applies §2's admission test rather than bending it; OW7 applies §5 and §9 (transport decides *when*, not *what*); HT3/HT6 apply §10 and its "local ACID is not a saga". **0005:** §6 is derived from §1's allowlists and §7's one-surface rule; PI10 keeps the composition root out of owner-internal contracts rather than claiming §3 licenses reaching them, so §7's "application-owned internals are internal" is respected on the `config/` side too; R7 keeps `integrations/*` out of `core.events`. **0006:** SEC7 uses the actor primitive without extending it, and adds no `core` vocabulary; VL4/QU10 keep contract-integrity failures out of the business error taxonomy. **0007:** HT1/HT2/HT5 reuse the in-transaction claim-and-complete shape; HT3/HT4 and §32 row 10 keep provider interaction strictly post-commit; SR4 keeps a payload from ever becoming commercial truth. **0008:** RR7/R14 keep the projection rebuildable from OLTP and non-event-sourced; SR5/OR7 leave the update semantics with items 6 and 12. |
| 13 | Is anything here unenforceable by the mechanism it claims? | Pass — §33 splits the rules honestly: A42–A50 are AST/static (an emission site, an import, a contract module, a `core` symbol are all visible statically); C55–C69 are behavioural because quarantine, idempotency and transaction boundaries can only be observed at runtime; V52–V61 are review items because ownership judgement, payload minimisation and "is this the same fact" are not decidable by a linter. No claim is made that a linter can see a V-rule. |
| 14 | Does it produce code? | Pass — no package, module, class, model, migration, task, broker configuration, dependency or schema file is created. The registry ships empty; every code-shaped fragment is an illustrative text block. |
| 15 | Is the identity-integrity obligation unconditional? | Pass, **after correction**. An earlier draft made IX5 detection contingent on the effect mechanism, so a handler using (b)/(c) could declare it unavailable — an invariant that can be opted out of is not an invariant. §21 now separates the two responsibilities: IX2/IX5/IX6 bind every consumer, IX10's (a)/(b)/(c) govern the **effect** only, IX11 states that (b)/(c) never discharge the identity obligation, RI13 forbids a registry entry from claiming otherwise, and C56 asserts it specifically for (b)/(c) handlers. |
| 16 | Can a permanently invalid message both stay durable and leave the queue? | Pass, **after correction**. QU4's earlier "never acknowledged" read as forbidding any transport disposition, which collided with QU6's no-hot-loop rule. §20.3 now separates semantic completion from transport disposition: never marked HANDLED (QU4, QU15), quarantine committed **before** disposal (QU14), terminal removal permitted after it (QU13), both invariants stated together (QU16), and the broker operation and topology left to item 9 (QU17). No broker API is named. |
| 17 | Does the registry freeze fields that must evolve? | Pass, **after correction**. §26.1 splits the entry into an immutable contract half (identity, kind, owner, schema, field semantics, exposure, introduction) and a mutable audited operational half (status, consumers, upcasters, notes, `emitted in production`, recorded delegations, effect-mechanism declarations). RM2/RM3 make lineage a forward declaration with a derived reverse view, so no published row is edited to add a back-pointer. |
| 18a | Is the effect-idempotency declaration unambiguous for a multi-consumer event? | Pass, **after correction**. The registry previously carried one `idempotency mechanism` column on the whole `(event_type, schema_version)` entry, which is meaningless for an `EVENT` with several independent consumers running different handlers. IX10/IX13 now place the declaration inside each **consumer's** record alongside its supported versions and justification; IX14 permits different consumers of one version to differ; IX15 notes a `COMMAND` naturally has exactly one; IX16 keeps the identity obligation universal and unaffected; RI13 requires a declaration per declared consumer rather than one per entry. Mechanisms (a)/(b)/(c), C55/C56 and every other frozen rule are untouched. |
| 18 | Can a semantic owner be re-homed by editing a row? | Pass, **after correction**. Because `event_type` is owner-qualified, an edited owner column would contradict the name itself. RI4/RM4/RM5 make re-homing a retire-and-introduce under a new owner-qualified name at version `1`; an ADR is separately required when a frozen boundary moves, and it authorises the re-homing, never an in-place edit. |
