# Phase 0 — Item 4: `public.py` contract template per domain

- **Status:** DONE / FROZEN
- **Date:** 2026-09-04
- **Phase:** 0 — Architecture Freeze
- **Related:** [ADR-0001](../../adr/0001-product-vs-sku-sellable-unit.md),
  [ADR-0004](../../adr/0004-four-layer-modular-monolith.md),
  [ADR-0005](../../adr/0005-dependency-and-integration-wiring.md),
  [item 2 artifact](02-four-layer-architecture.md),
  [item 3 artifact](03-dependency-matrix.md),
  master `# 4.1`, `# 4.4`
- **New ADR:** [ADR-0006](../../adr/0006-public-contract-primitives.md). See §1.3.

---

## 1. Purpose

### 1.1 What this item freezes

Item 3 froze *which* module may be imported across a boundary: `domains/<x>/public.py` and nothing
else (§10, L4). It deliberately deferred *what that module may contain* and *how the actor is carried
into a domain call* (item 3 §18) to this item.

This artifact freezes **one uniform external contract shape** for every `domains/<x>/public.py`, so
that Phase 1 can create domain skeletons without inventing a different contract style per domain, and
so that a reviewer can decide "is this a legal public export?" from a written rule rather than from
precedent.

Frozen here: the physical shape of the module; the categories of symbol that may cross; the forbidden
categories; the DTO style; identity rules in public contracts; command semantics; selector semantics;
mandatory actor scoping for private state; transaction participation; the public error strategy;
public enum rules; collection/pagination rules; the compatibility/change policy; and the contract
checks Phase 1 must implement.

### 1.2 What this item does **not** do

It does not define the public API of any domain. `Catalog`, `Pricing`, `Inventory`, `Orders`,
`Payments` and every other domain get their surfaces in their own phases, using this template. No
signature in this document is a real signature; every code fragment is illustrative pseudo-code for a
fictional `domains/example`.

It also creates no Python package, no `public.py`, no DTO and no test. Phase 0 produces documents and
decisions only (PHASE0_STATUS.md).

### 1.3 Why ADR-0006 is required

Most of this template specifies decisions ADR-0004 and ADR-0005 already froze — the façade shape, the
DTO style, command/selector semantics, transaction composability, the compatibility policy — and
those need no ADR.

Two rules do not fit that description. Both introduce a `core` primitive that did not exist and both
**extend a `core` submodule allowlist frozen by ADR-0005 §1**, which is exactly the class of change
that must be deliberate rather than discovered later as an undocumented import:

1. **The authorization subject (§11.3).** A domain-independent actor type in `core`, consumed by
   `domains`, `application`, `interfaces` and `tasks` — an authorization primitive placed in front of
   `interfaces/*`.
2. **The public error categories (§13.1).** A closed, business-free structural taxonomy in `core`,
   read by four families for domain definition, workflow handling and transport mapping.

Both are therefore decided in
**[ADR-0006 — `core` primitives of the public contract](../../adr/0006-public-contract-primitives.md)**,
which records the extended allowlists and, equally importantly, the two negative rules:
`integrations/*` gains access to **neither** primitive. An adapter answers no authorization question
and raises no domain error; it reports failure through the vendor-neutral edge types of the
`application/<a>/ports.py` it implements (ADR-0005 §6.3). Membership in `core` grants an adapter
nothing — the allowlist decides, not the package. Migrations consume neither primitive. `core.outbox`
and `core.idempotency` remain forbidden to `interfaces/*` (L13); ADR-0005's text is extended by
reference, not rewritten.

If a later change wants to weaken any rule in §4–§17 — an optional actor, an ORM type in a contract,
a transport concept in a domain error — that too *is* an ADR.

---

## 2. Frozen principles inherited from ADR-0004 / ADR-0005 / item 3

| # | Principle | Source |
|---|---|---|
| R1 | `domains/<x>/public.py` is the only importable module of the domain. | item 3 §10, L4 |
| R2 | Domains are mutually invisible — a domain imports no other domain, not even its `public`. | ADR-0004 §3, L2 |
| R3 | No ORM model, manager, instance or QuerySet crosses any module boundary; what crosses is a frozen DTO or value object. | item 3 §12, master `# 4.1` |
| R4 | Object-level authorization belongs to the module owning the state, via its policy and actor-scoped selector. | ADR-0004 §6 |
| R5 | A domain command is a composable transaction participant: it does not commit on its own behalf and performs no external HTTP. | ADR-0004 §10 |
| R6 | Domains carry no vendor vocabulary and no vendor types. | ADR-0004 §3, §8; V3 |
| R7 | `interfaces` may call `<domain>.public` directly for a genuine single-domain request; `tasks` likewise for a single-domain background command. | ADR-0004 §5, §9; item 3 §10 |
| R8 | `application` orchestrates domains exclusively through `<domain>.public`. | item 3 §4.3 |
| R9 | `__init__.py` under `domains/` stays empty; no re-export shortcuts. | ADR-0005 §1, A8 |
| R10 | Public locators are `PublicId`/UUIDv7; internal bigint PKs do not appear in URLs or external contracts. | ADR-0001, master `# 5` |

Nothing below weakens any of these.

---

## 3. Vocabulary

| Term | Meaning in this document |
|---|---|
| **Public contract** | The set of symbols listed in `domains/<x>/public.py`'s `__all__`. Nothing else about the domain is externally supported. |
| **Command** | A public callable that may change domain state. |
| **Selector** | A public callable that changes no domain state observable by any caller. |
| **Public state** | Domain state a request may read without an authorization subject (published catalog data, public store list). |
| **Private state** | Domain state whose visibility depends on who is asking (`Order`, `Review` in moderation, `Address`, `PaymentAttempt`). |
| **Actor** | The explicit authorization subject passed into a protected command/selector. Includes an explicit system/privileged variant. |
| **Category error** | One of the fixed structural error kinds (`NotFound`, `NotAllowed`, `Conflict`, `InvalidState`, `Validation`) a caller may branch on. |
| **Edge type** | A type that legally appears in a public signature: frozen DTO, value object, public enum, public error, or a stdlib/`core` primitive. |

---

## 4. Physical shape of `domains/<x>/public.py`

### 4.1 Frozen rule

`public.py` is a **thin, explicit façade**: a module docstring, explicit `from .<internal> import
<name>` statements, and one explicit `__all__`. Nothing else.

Frozen constraints:

| # | Constraint |
|---|---|
| S1 | No `class` and no `def` statement in `public.py`. Implementations live in internal modules. |
| S2 | No wildcard import (`from .dto import *`). |
| S3 | No module re-export (`from . import dto`) — only names cross, never internal module objects. |
| S4 | No aliasing (`import X as Y`): the public name **is** the internal name, so a symbol cannot have two identities. |
| S5 | `__all__` is an explicit tuple of string literals, grouped by category with comments, and matches the imported names exactly. |
| S6 | No conditional import, no `if TYPE_CHECKING` block, no module-level `__getattr__`, no lazy import machinery. The contract is readable statically and at a glance. |
| S7 | No side effect at import time: no Django app-registry access, no settings read, no I/O, no logging configuration, no signal registration. |
| S8 | No business logic: no computation, no validation, no branching, no wrapper function that adds behaviour. |
| S9 | `public.py` imports nothing outside its own domain except, where a public signature needs them, `core` value/edge primitives (`core.money`, `core.public_id`, `core.actor`, `core.errors`) and stdlib typing. |

S1 is what makes the module mechanically checkable and what stops "just this one thin wrapper" from
becoming a second service layer above the domain.

### 4.2 Where the implementations live

Outsiders cannot import any of these; they are the domain's internals, named consistently with item 3
§12 so L4's forbidden-module list stays accurate:

| Module family | Holds |
|---|---|
| `models.py` | Django ORM. Never exported, never referenced in a public annotation. |
| `dto.py` | Frozen input/output DTOs and value objects, both public and internal. |
| `enums.py` | Domain enums, both public and internal. |
| `errors.py` | The domain's public error types and internal exceptions. |
| `services/`, `commands/` | Command implementations, invariants, state transitions. |
| `selectors/` | Read implementations, materialisation into DTOs. |
| `policies.py` | Object-level authorization decisions. |
| `state_machine.py`, `pipeline.py`, `repositories.py` | Internal mechanism. |

Exact file names and the `services/` vs `commands/` choice remain a Phase 1 decision (§21); the
*rule* — a public symbol is defined in an internal module and only listed in `public.py` — is frozen.

### 4.3 A domain has exactly one public surface

There is no second "web contract", no "fast path for the API", no `public_web.py`, no
`internal_public.py`. `application`, `interfaces`, `tasks` and contract tests consume the same
symbols (§16). A capability that only one caller needs is still a normal public symbol or is not
public at all.

---

## 5. Allowed public export categories

Exactly these categories may appear in `__all__`:

| # | Category | Rule |
|---|---|---|
| E1 | **Immutable input DTO** | Structured command input. Frozen dataclass, §7. |
| E2 | **Immutable output/result DTO** | Returned by selectors and commands. Frozen dataclass, §7. |
| E3 | **Domain value object** | Only when the value is intentionally part of the external contract (a domain-specific quantity, code or identifier wrapper). Immutable, no persistence behaviour. |
| E4 | **Public enum** | Only under §14. |
| E5 | **Command** | A module-level callable, §9. |
| E6 | **Selector** | A module-level callable, §10. |
| E7 | **Actor-scoped selector / policy predicate** | The public form of authorization for private state, §11. A *predicate callable* may be exported; a policy *class* may not. |
| E8 | **Public domain error** | A small, stable, intentional error contract, §13. |

Two rules bound the list:

- **Intent test.** A symbol is exported because the domain intends to support it externally, not
  because a caller currently needs it. "`application/checkout` imports it today" is not a
  justification; "this is a capability the domain offers" is.
- **No convenience escape.** If a required capability is missing, the answer is a new intentional
  public symbol (§17.2), never an import of an internal module (item 3 §11.1 states the symmetric
  rule for applications).

---

## 6. Forbidden exports

No symbol in any of these categories may be exported from `public.py`, appear in a public signature
(parameter or return annotation), or be reachable through a returned object:

**Persistence**

- Django `Model` classes and model instances;
- `QuerySet`, `Manager`, `RawQuerySet`, `Prefetch`, `Q`, `F`, expression objects;
- repository implementations and repository interfaces;
- `Model.DoesNotExist`, `MultipleObjectsReturned`, `IntegrityError`, `OperationalError`,
  `DataError`, `DatabaseError`, and any other `django.db` exception — none of these may be
  **exported** in `__all__`, named in a public annotation, or documented as something a caller is
  expected to catch. That is a rule about the *contract surface*; what happens to an unexpected
  technical fault at runtime is §13.5, and the answer there is neither "export it" nor "convert it
  into a business error";
- transaction-management objects or flags (`atomic` handles, savepoint ids,
  `connection.in_atomic_block` state) (§12).

**Internal structure**

- internal service classes, command classes, pipelines, state-machine objects;
- policy or selector *implementation objects* (only their callable results cross, per E7);
- internal DTOs not intended as contract, internal enums (§14);
- anything mutable that behaves like a domain entity (§7.4).

**Transport**

- `HttpRequest`, `HttpResponse`, `Http404`, redirect/response helpers;
- DRF `Serializer`, `ViewSet`, `APIView`, `Response`, DRF exceptions;
- Django `Form`, `ModelForm`, `ModelAdmin`, admin actions;
- migration classes and operations;
- Celery `Task` objects, signatures, routing keys, `AsyncResult`;
- HTTP status codes, header names, URL paths, template names, content types (§13.6).

**Vendor**

- integration/vendor DTOs and wire codecs;
- provider SDK types and clients;
- raw provider statuses and provider error codes, including under a neutral type name (V3);
- vendor exceptions.

**Lazy / deferred evaluation**

- lazy objects, `SimpleLazyObject`, deferred model instances, generators, iterators or callables
  whose evaluation issues SQL after the boundary is crossed (§10.3).

The single governing sentence: **no public export may become a backdoor to domain internals.** If a
symbol would let a caller reach `models.py` — directly, through an attribute, through a property, or
through an exception's `__cause__` — it is not a public export.

---

## 7. DTO style

### 7.1 Baseline

```python
@dataclass(frozen=True, slots=True, kw_only=True)
```

is the frozen default for every public DTO and value object. Departure requires a stated architectural
reason recorded next to the type.

- `frozen=True` — immutability is the contract, not a convention.
- `slots=True` — no ad-hoc attribute injection by a caller; smaller instances on read paths.
  Consequence: `functools.cached_property` is unavailable, which is intended (§7.3).
- `kw_only=True` — construction is by keyword, so adding an optional field stays a backward-compatible
  change (§17.2) instead of a positional break.

A value object with meaningful arithmetic or ordering may add `order=True` / `__post_init__`
validation; it stays frozen.

### 7.2 Requirements

| # | Requirement |
|---|---|
| D1 | Fully type-annotated; no bare `Any`, no untyped field. |
| D2 | No ORM inheritance, no model reference, no Django import of any kind. |
| D3 | Serialization-neutral: no `to_json`/`from_json`, no DRF serializer, no schema decorator, no framework metadata. Transport chooses its own representation. |
| D4 | No transport fields: no HTTP status, URL, header, template name, content type. |
| D5 | No vendor fields, and no neutral-looking field holding a vendor value (V3). |
| D6 | No hidden database access — see §7.3. |
| D7 | Instants are timezone-aware `datetime` in UTC. Naive datetimes are forbidden in public contracts; localisation and formatting are transport concerns. |
| D8 | Money is `Money` (integer minor units + currency); floats are forbidden for money anywhere. Non-money decimals use `Decimal`, never `float`, where exactness matters. |
| D9 | Externally addressable identity is `PublicId` (§8). |
| D10 | Optionality is explicit (`X \| None`) and means "absent", never "unknown, ask the database". |

`Money` and `PublicId` are referenced here as already-frozen semantic types; their implementation is
item 11 and is not designed here.

### 7.3 Methods and properties on a DTO

A public DTO may expose a property or method only when it is **pure and total**: computed from the
instance's own fields, with no I/O, no database access, no network, no global state, no caching, no
exception beyond a documented value error. `cached_property`, descriptors touching a database, and
lazy attributes are forbidden — this is the rule D6 exists to enforce, and `slots=True` removes the
most common way to violate it accidentally.

### 7.4 Immutability depth — the precise rule

Deep runtime freezing is **not** required and must not be implemented — no recursive freeze helpers,
no wrapper objects applied at construction. Immutability is guaranteed **by field type**, so that
every allowed type is already immutable at runtime and the guarantee is checkable statically:

| Field type | Status |
|---|---|
| `str`, `int`, `bool`, `bytes`, `Decimal`, `date`, aware `datetime`, `timedelta`, `UUID`, `Enum` | Allowed |
| `Money`, `PublicId`, other frozen `core` value types | Allowed |
| another frozen public DTO / value object | Allowed |
| `tuple[T, ...]`, `frozenset[T]` | Allowed — the frozen collection shapes |
| `list`, `dict`, `set`, `bytearray`, or any mutable custom class | **Forbidden as a declared public field type** |
| `Mapping[K, V]`, `MutableMapping`, `Sequence`, `Iterable`, `Collection` and other abstract shapes | **Forbidden as a declared public field type** — see below |
| `Any`, untyped, `object` | Forbidden |
| `float` for money | Forbidden |

**Key/value data uses a frozen sequence, not a mapping.** A bare `Mapping` annotation does not make
the underlying object immutable — the runtime value is normally a `dict`, and a consumer that casts
or a producer that keeps a reference can mutate it. Allowing it would make the frozen-DTO guarantee
partly a convention, which is not a guarantee. `Sequence`/`Iterable` fail for the same reason and add
a second one: an `Iterable` field can hide a generator, which §10 forbids outright.

Until an immutable mapping type is deliberately approved, key/value collections in a public DTO are
represented as:

- `tuple[SomePairDTO, ...]` — preferred where the pair has meaning worth naming; or
- `tuple[tuple[K, V], ...]` — for a plain association list.

Where semantics depend on it, the contract documents the ordering/canonicalisation (for example
"sorted by key, keys unique"), because a sequence carries an order that a mapping did not.

No immutable-map dependency is introduced in Phase 0, and none is implied. If a real immutable
mapping type is later needed, it is approved deliberately — a project-approved immutable
implementation with a concrete value type — and this table is amended then.

So a public DTO is immutable to exactly the depth its type annotations promise, every allowed field
type is genuinely immutable at runtime, and the promise is machine-checkable (A17).

---

## 8. Identity in public contracts

ADR-0001 distinguishes three identifier roles: the **public locator** (`PublicId`/UUIDv7, safe to put
in a URL or an API payload), the **external contract identifier** (a provider's or ERP's id, which
lives at the integration boundary), and the **internal bigint PK** (a storage detail).

Frozen rules:

| # | Rule |
|---|---|
| I1 | Any public contract parameter or DTO field that identifies an **externally or user-addressable object** uses `PublicId`. |
| I2 | A public DTO must not declare a field named `id` or `pk`. Identity fields are named for their role: `public_id`, `<entity>_public_id`. |
| I3 | An internal bigint must never become a **user/public locator**, a **public HTTP/API payload identifier**, an **external webhook or integration contract identifier**, or an **externally consumed event identifier**. Where an internal identifier legitimately appears in a public contract (I4), the field is named unambiguously (`internal_<entity>_id`) and typed distinctly enough that it cannot be mistaken for a locator. |
| I4 | I3 is not a licence for the reverse: this item does **not** require every internal field to be a UUID. Strictly internal application-to-domain orchestration, and strictly internal versioned events and jobs, may use internal identifiers where the already-frozen identity and event rules permit. Event schemas themselves are **not** designed here — Phase 0 item 8 owns them, including which identifier a given event carries and whether that event is internal or externally consumed. |
| I5 | Provider/ERP external identifiers do not appear in a domain public contract at all — they are integration-boundary state owned by the corresponding `application` sync module (ADR-0005 §4, ADR-0003 §2). |

The item-4 invariant is narrow and specific: **a domain public DTO must not accidentally turn an
internal storage key into an externally visible locator** — typically because a field named `id` was
rendered into a template or a JSON body. I2 makes that shape visible in review and to a static check
(A16). Nothing here restricts internal identifiers inside strictly internal machinery.

---

## 9. Commands

### 9.1 Semantics

A command:

- represents one intentional, business-named, state-changing domain operation (`reserve`, `release`,
  `cancel_order`, `approve_review` — illustrative only);
- is a module-level callable exported by name; not a class, not a method on an exported object;
- enforces that domain's invariants itself and does not trust caller-supplied derived values;
- validates its input at the boundary of the domain;
- returns a frozen DTO / value object / public enum, or `None`;
- never returns an ORM instance, QuerySet, manager, or a mutable entity;
- makes **no direct call to an external system or provider** (R5, ADR-0004 §10; outbound capability
  is an `application` port implemented by an adapter, ADR-0005 §2). PostgreSQL work owned by the
  domain, including the transactional Outbox row, is not external I/O — see T4;
- signals every **expected** failure as a listed public domain error; technical and unexpected faults
  propagate untranslated (§13);
- participates in, but never owns unconditionally, the ambient transaction (§12);
- emits its integration events by writing an Outbox row through `core` inside the same transaction —
  it never schedules a task and never imports `tasks/*` (item 3 §4.2).

### 9.2 Shape

```text
def <business_verb>(actor: Actor, *, <explicit keyword parameters>) -> <ResultDTO> | None
```

- the actor is first and mandatory for protected operations (§11);
- everything else is keyword-only, so parameter additions stay backward compatible;
- structured input uses a frozen input DTO rather than a long parameter list;
- `**kwargs` is forbidden in a public callable; so is a bare `Any` parameter or return annotation.

### 9.3 Not frozen here

No actual command signature for any real domain. `reserve(...)`, `cancel_order(...)` and friends are
named in this document only to show the naming register (imperative, business vocabulary, no transport
and no vendor words).

---

## 10. Selectors

### 10.1 Semantics

A selector:

- is read-only from every caller's semantic perspective — it changes no state a caller can observe;
- returns frozen DTOs / value objects / public enums, or an immutable collection of them (§15);
- **completes all SQL before returning.** What crosses the boundary is materialised data;
- never returns a QuerySet, a lazy object, a deferred model instance, a generator or an iterator;
- never hides a future query behind an attribute, property or `__getattr__` (§7.3);
- signals expected failures as listed public domain errors, and lets technical faults propagate (§13);
- makes no direct call to an external system or provider (T4); its PostgreSQL reads, and the
  disposable cache/metrics/tracing side effects of §10.2, are not that.

### 10.2 The only side effects a selector may have

A selector may perform **disposable technical side effects with no business, audit or compliance
truth semantics**:

- read-through cache population;
- metrics;
- tracing/observability spans.

These are disposable by definition (Redis and telemetry are acceleration, not truth — master `# 22`),
so losing them changes no commercial fact.

A selector **must not perform a durable PostgreSQL write that changes business, authorization, audit
or compliance state.** The following are therefore **not** selector side effects:

| Write | Why not |
|---|---|
| `last_seen_at` / "viewed at" touch | Durable state a later decision or report can depend on. |
| audit or access-history row | Compliance truth; its absence is a compliance defect, not a cache miss. |
| consent record | Legal state (master `# 21`). |
| security decision record (lockout counter, failed-attempt log) | Authorization truth. |
| popularity / view / sales counter used as business truth | Commercial fact; also a write-amplification hazard on the hot read path. |

If such state must change as a consequence of a read, it is modelled as an **explicit command**, or
as a separately owned post-read/event mechanism — designed by the feature that needs it, not here.

The selector's semantic rule is unchanged: **a materialised read contract with no caller-visible
business mutation.**

### 10.3 Why "materialised" is a contract term, not a style preference

If a QuerySet or lazy object crosses `public.py`, three frozen guarantees break at once: the caller can
extend the query and reach columns the contract never promised (R1/R3); SQL executes outside the
domain's transaction and error-handling context (§12, §13); and the storefront query budget stops
being measurable because the query count depends on what the template touches (master `# 22`). This is
why §6 lists lazy evaluation as a forbidden export category and not merely as a caution.

### 10.4 Naming register

Public reads are named for their access mode, so that the mode is visible at the call site:
`get_public_product(...)`, `list_public_products(...)`, `get_order_for_actor(...)`,
`list_orders_for_actor(...)` — illustrative only. Real catalog/order read APIs are designed in their
own items and phases (§21).

---

## 11. Authorization by construction

### 11.1 The frozen rule

ADR-0004 §6: **object-level authorization follows state ownership.** For private domain state, the
public contract itself must make the authorization context mandatory — authorization is not something
a caller may forget.

| Shape | Verdict |
|---|---|
| `get_order(order_id)` for private state | **Forbidden.** The contract permits an unauthorized read. |
| `get_order(actor=None, ...)`, `cancel_order(order_id, user_id=None)` | **Forbidden.** An optional actor is an authorization switch disguised as a default. |
| `get_order_for_actor(actor, order_public_id)` | Correct: the subject is structural. |
| `get_public_product(public_id)` — public state, no actor at all | Correct: public reads take no actor rather than an ignorable one. |

The split between "public read, no actor parameter" and "private read, mandatory actor parameter" is
the frozen mechanism. There is no third form in which an actor exists but may be `None`.

### 11.2 Frozen constraints

| # | Constraint |
|---|---|
| Z1 | For every command or selector touching private state, the actor is the **first positional parameter**, has **no default**, and is **not** `Optional`. |
| Z2 | `actor=None` never means "system", "admin", "trusted caller" or "skip the check". No public symbol accepts `None` as an authorization subject. |
| Z3 | Privileged/background access uses an **explicit** type or capability — a `SystemActor` (or equivalent explicit trusted-context type) — so privileged use is visible at every call site and greppable in review. |
| Z4 | A system-only operation is additionally named or typed so that its privileged nature is apparent (`..._as_system`, or a parameter type that only a system context satisfies). |
| Z5 | Object-level authorization is decided inside the domain, by its policy plus its actor-scoped selector. The public callable never returns an object for the caller to check afterwards. |
| Z6 | Interfaces perform no ownership-field comparison (A4). They authenticate, build the actor, and call the actor-scoped contract. |
| Z7 | A domain must not accept a pre-computed authorization decision (`is_owner: bool`, `allowed: bool`) from a caller. Passing the decision instead of the subject reintroduces exactly the trust the rule removes. |
| Z8 | The failure mode is a public error, not a truthy/falsy sentinel: a forbidden access raises the `NotAllowed` category (§13); whether a non-visible object raises `NotFound` or `NotAllowed` is a per-domain decision recorded in that domain's contract, because the choice leaks existence information. |

### 11.3 The actor type — item 3's deferred question, answered

`Actor` is a **domain-independent identity/authorization-subject carrier owned by `core`** (working
name `core.actor`). It qualifies under the ADR-0004 §2 admission test: domain-independent, carrying no
business or vendor vocabulary, consumed by every layer, and mechanism-shaped.

Frozen: interfaces and tasks construct/restore it (ADR-0004 §5, §9); application passes it through;
domains consume it; it is never built inside a domain from raw request data; `SystemActor` is an
explicit sibling type in the same module.

The `core` allowlist consequence is decided in [ADR-0006](../../adr/0006-public-contract-primitives.md)
§1: `domains`, `application`, `interfaces` and `tasks` may name the actor type; the composition root
may pass such a value but owns no actor semantics; **`integrations/*` may not depend on it at all**,
and neither may migrations. A vendor adapter receives vendor-neutral port edge types, never an
authorization subject.

**Deliberately not frozen here:** the actor's fields, whether it carries roles, capabilities, a
session or a tenant, its construction API, and whether policies consume capabilities or roles. Those
belong to the phase that implements authentication. The rule that the actor is explicit, mandatory and
typed does not depend on any of them.

---

## 12. Transaction participation

### 12.1 Frozen rule

**One semantic command per capability.** A public command must be correct both as the whole use case
and as a participant inside an application-owned outer transaction. The following are forbidden as a
*public contract distinction*:

```text
reserve_with_transaction(...)   vs   reserve_without_transaction(...)
reserve(..., manage_transaction: bool = True)
```

A caller must never have to choose a variant, and a command must not branch on
`connection.in_atomic_block` to decide its own semantics.

### 12.2 Constraints

| # | Constraint |
|---|---|
| T1 | A domain command may open `transaction.atomic()` around its own writes. Nested `atomic()` becomes a savepoint under an outer atomic — that is an **implementation detail**, never a contract distinction. |
| T2 | A domain command performs no independent commit: no `transaction.commit()`, no `rollback()`, no `set_autocommit()`, no `atomic(durable=True)` (which would make composition inside an application transaction raise), no connection or transaction handle in a signature. |
| T3 | Rolling back only its own work is expressed with a savepoint, not by attempting to commit around the caller. |
| T4 | **No direct external/vendor network I/O inside a domain command or selector** — ever, transaction or not (R5). Forbidden: an HTTP/API call to a payment provider (maib, MIA), ERP/1C, CRM, an email or SMS provider, Chatwoot or any other vendor; and direct message-broker publishing as an external side effect. Allowed, per rules already frozen elsewhere: PostgreSQL reads and writes owned by the domain; the transactional Outbox row (dispatch is the relay's); a selector's disposable read-through cache population in Redis (§10.2); metrics, tracing and observability. This is not a licence for arbitrary infrastructure I/O — anything not on the allowed list needs a rule of its own before it appears in a domain. |
| T5 | A domain command does not register transport side effects: no `transaction.on_commit` scheduling a Celery task, no cache invalidation that a caller is required to know about for correctness. |
| T6 | The **application** owns the outer transaction of a cross-domain workflow; a single-domain command called directly by an interface or task owns its own; interfaces and tasks own none (ADR-0004 §10). |
| T7 | Durable idempotency stays below the transport boundary (PostgreSQL `IdempotencyKey`/Inbox), and is never delegated to the caller by the public contract. |
| T8 | A command must not require being outermost, must not assert on transaction state, and must not leave the connection in a broken state on failure — see §13.4. |

### 12.3 Consequence for selectors

A selector inherits T4 and the materialisation rule (§10). It must not open a transaction to keep a
QuerySet alive across the boundary, because no QuerySet crosses it.

---

## 13. Errors crossing `public.py`

### 13.1 The decision

**Per-domain public error types (option B), rooted in a fixed, business-free structural category set
owned by `core` (`core.errors`, name provisional).**

- `core` owns exactly one root plus five categories: `DomainError`, `NotFoundError`,
  `NotAllowedError`, `ConflictError`, `InvalidStateError`, `ValidationError`. These are structural
  markers: no messages, no business vocabulary, no HTTP, no vendor, no domain names.
- **Every concrete public error is defined and owned by its domain**, in `domains/<x>/errors.py`, and
  inherits both its domain root and the applicable category:

```python
class ExampleError(DomainError): ...                       # domain root
class WidgetNotFound(ExampleError, NotFoundError): ...     # concrete, domain-owned
```

Pure option A (a shared hierarchy of concrete business errors in `core`) was rejected: it would give
`core` business vocabulary, against ADR-0004 §2. Pure option B (per-domain categories with no shared
marker) was rejected for a concrete failure: every transport mapper would have to enumerate each
domain's error names, and a new domain would silently map to 500. The hybrid keeps ownership in the
domain and gives callers five stable things to branch on.

`core.errors` is closed by rule: adding a category is an ADR; adding a business error to it is
forbidden.

Its consumers are fixed by [ADR-0006](../../adr/0006-public-contract-primitives.md) §2 and are **not**
"every package family": `domains` define concrete errors over the categories, `application` maps a
category to workflow behaviour, `interfaces` to transport behaviour, `tasks` to retry/failure
classification, and the composition root may install a shared handler. **`integrations/*` is
excluded** — an adapter reports failure through the vendor-neutral contract of the
`application/<a>/ports.py` it implements and never raises or interprets a domain public error.
Migrations are excluded too.

### 13.2 What the contract covers: expected semantic failures

The public error contract covers **expected domain failures** — outcomes the domain anticipates and
assigns meaning to:

- an object intentionally not found or not visible to this actor;
- an authorization/policy denial;
- an expected business conflict;
- an invalid or illegal state transition;
- a business-rule or input validation failure;
- an **expected** database uniqueness/concurrency race whose meaning is a known domain `Conflict`
  (§13.4).

Each of these is translated inside the domain into a listed public error carrying its category.

### 13.3 Constraints

| # | Constraint |
|---|---|
| X1 | Every **expected** domain failure crossing `public.py` is a public domain error listed in `__all__`, carrying exactly one `core` category. An expected failure that escapes as something else — a bare `ValueError`, an unlisted exception, a `None` sentinel standing in for a denial — is a contract defect. |
| X2 | An error carries structural data only: a stable `code`, and optional frozen detail fields following §7. No ORM object, no vendor payload, no request, no response. |
| X3 | No error message or field contains a secret, a token, or PII (master `# 21`). |
| X4 | The domain root and the category are both part of the contract: callers may catch either. |
| X5 | Interfaces map a category to transport behaviour (`NotFound` → 404, `NotAllowed` → 403/404 per §11.2 Z8, `Conflict` → 409, `Validation` → 400/422); applications map a category to workflow behaviour. Neither mapping lives in the domain. |
| X6 | The contract makes **no** promise about technical or unexpected faults, and no `__all__` entry exists for them (§13.5). |

### 13.4 Expected persistence races, and the savepoint rule

A domain may translate a database error into a semantic public error **only when it can reliably
identify the violated invariant** — a named unique constraint, a named exclusion constraint, a
specific check constraint. "An `IntegrityError` happened somewhere in this block" is not
identification, and translating it is guessing.

Where the translation is legitimate, the failing statement must sit inside its **own nested
`atomic()` savepoint**. A database integrity failure marks the surrounding atomic block as
unrecoverable, so without the savepoint the domain "handles" the error and hands its caller a
transaction that can no longer commit — the exact defect T8 exists to prevent. This applies whether
the command is outermost or composed inside an application-owned transaction.

Deliberate examples:

| Situation | Correct outcome |
|---|---|
| Expected absence of a row the contract may legitimately not find | domain `NotFound` |
| Expected uniqueness race on a named constraint, caught at a savepoint | domain `Conflict` |
| `MultipleObjectsReturned` where uniqueness was expected | **not** a business error — a broken invariant, i.e. a defect, unless a domain explicitly and deliberately defines that plurality as a business case |

### 13.5 Technical and unexpected faults are not business errors

These are **not** part of the public contract and **must not** be converted into `NotFound`,
`Conflict`, `Validation` or any other category merely to satisfy the façade:

- PostgreSQL unavailable, `OperationalError`, connection loss, timeout at the database;
- unexpected `DatabaseError`, `DataError`, an `IntegrityError` whose invariant the domain cannot
  identify (§13.4);
- data corruption or an impossible invariant breach that indicates a defect;
- programming errors — `TypeError`, `AttributeError`, `KeyError`, `AssertionError`, and friends;
- anything unknown or unclassified.

They **propagate as technical faults** to the platform boundary, where they belong: observability and
Sentry, 5xx handling in `interfaces`, and retry/DLQ policy in `tasks` (master `# 20`, `# 23`). They
are not listed in `__all__`, not documented as catchable, and not wrapped.

The precise promise: **the contract guarantees that expected *domain* failures use the semantic
hierarchy. It does not guarantee that arbitrary infrastructure or programmer failures are wrapped.**

Masking a database outage as a `Conflict` is the worse of the two failure modes this section
prevents: it converts a page-the-operator condition into a business outcome, and a retry policy
built on the category then does the wrong thing.

### 13.6 Never exported

`Model.DoesNotExist`, `MultipleObjectsReturned`, `IntegrityError`, `OperationalError`, any other
`django.db` exception, vendor exceptions, provider error codes, DRF/HTTP exceptions, and HTTP status
numbers are never exported, never named in a public annotation and never documented as part of the
contract. A public error that carries an HTTP status is a transport concept inside a domain and is
forbidden.

This is the contract-surface rule; it does not mean such an exception is caught and rewritten at the
boundary — §13.5 governs that.

---

## 14. Public enums and states

| # | Rule |
|---|---|
| N1 | An enum is public only when its semantics genuinely belong to the external contract and a caller legitimately branches on it. |
| N2 | Internal workflow/implementation states stay internal. A database choice enum is **not** public merely because it exists in `models.py`. |
| N3 | A public enum is defined in the domain's enum/DTO module, not as a Django `TextChoices`/`IntegerChoices` class — a choices class is an ORM-coupled type and §6 forbids it crossing. A domain may map internally between the two. |
| N4 | Public enum members are string-valued with explicit, stable values. Integer database values never become contract values. |
| N5 | The **member name and its meaning** are the contract. Renaming, removing or repurposing a member is a breaking change (§17.3); adding a member is breaking **for callers that exhaustively match** and must therefore be reviewed as such, not assumed additive. |
| N6 | A public enum carries no vendor status (V3) and no transport concept. |

---

## 15. Collections and pagination

| # | Rule |
|---|---|
| K1 | A public selector returning a collection returns an explicit immutable result — `tuple[DTO, ...]` — never a QuerySet, list, generator, iterator or paginator. |
| K2 | Django `Paginator`, `Page` and `page.object_list` never cross a public boundary. |
| K3 | When pagination metadata is part of a contract, it is a frozen DTO owned by that contract (a small `items: tuple[DTO, ...]` + cursor/total shape), designed by the item that needs it. |
| K4 | An unbounded public list selector is a defect: a collection contract states its bound (an explicit limit parameter or a documented natural bound). |
| K5 | Storefront pagination, facets and the listing projection are **not** designed here (ADR-0003; Phase 0 items 6, 7). |

---

## 16. Consumers of the contract

The same `public.py` serves all four consumers; none of them gets a private variant:

| Consumer | Use | Bound |
|---|---|---|
| `application/<a>` | Cross-domain orchestration | `PUBLIC ONLY`; a missing capability becomes a new public symbol, never a `models.py` import (item 3 §4.3, §11) |
| `interfaces/*` | Genuine single-domain request | At most **one** domain per request; the second domain moves the flow to `application` (A5, V10) |
| `tasks/*` | Genuine single-domain background command | At most one domain per task function; the task maps the result to success/retry/DLQ (ADR-0004 §9, L11) |
| `tests/*` | Contract tests | Domain unit tests may reach internals per the item 3 §14.2 tier policy; **contract tests use `public.py` only** |

Transport mapping — HTML, JSON, admin rendering, status codes, serializers — stays outside the domain
in every case. A DTO returned to `interfaces/web` and to `interfaces/api` is the same DTO (master
`# 4.4`).

Conversely, not every internal helper becomes public. The intent test in §5 applies in both
directions: contracts grow deliberately, or they stop being contracts.

---

## 17. Compatibility and change policy

### 17.1 Internal change

Implementation changes behind an unchanged `public.py`: refactoring a service, adding an index,
changing a query, splitting an internal module, renaming an internal symbol.

Requires: normal tests. **No ADR, no contract review.**

### 17.2 Backward-compatible public addition

A new selector; a new command; a new optional keyword parameter with a behaviour-preserving default; a
new field on a result DTO that existing callers can ignore; a new public error subtype under an
existing category.

Requires: contract review, tests, explicit addition to `__all__`, and a check that the addition does
not contradict this template.

Does **not** automatically require an ADR. An ADR is needed only if the addition changes a frozen
architectural decision — for example a public symbol that would perform outbound I/O, expose an ORM
type, or move authorization out of the owning module.

Note the two additions that are *not* purely additive and must be reviewed as breaking: a new required
parameter, and a new member of a public enum that callers match exhaustively (N5).

### 17.3 Breaking public contract change

Removing or renaming a command, selector, DTO, field or error; changing the meaning of an argument;
changing authorization semantics (including which actor may do what); changing identifier semantics;
changing or removing a required field of a result DTO; an incompatible public enum change; exposing an
ORM, vendor or transport concept; changing transaction semantics callers rely on.

Requires: deliberate migration of all callers in the same change (the monolith makes callers
enumerable — this is a compile-time-visible refactor, not a deprecation window across services), tests
updated at the same abstraction level, and a contract review.

An **ADR is required when the breaking change modifies a frozen architectural decision** — ADR-0001…
0005 or this template. A rename or a signature change that leaves every frozen rule intact is recorded
by the normal implementation/versioning process, not by an ADR. Not every API edit is an ADR.

### 17.4 Event schemas are a separate contract

Outbox/Inbox event compatibility is versioned separately and is owned by Phase 0 item 8. A public API
change is not automatically an event change, and vice versa.

---

## 18. Pseudo-template (non-production, illustrative)

Fictional domain, deliberately trivial, deliberately incomplete. It exists to show *structure*, not to
be copied into Phase 1 as content.

```python
# domains/example/dto.py
@dataclass(frozen=True, slots=True, kw_only=True)
class WidgetActivationInput:            # E1 — immutable input DTO
    widget_public_id: PublicId
    effective_at: datetime              # tz-aware, UTC (D7)
    note: str | None = None

@dataclass(frozen=True, slots=True, kw_only=True)
class WidgetSummary:                    # E2 — immutable result DTO
    public_id: PublicId                 # I2 — never `id`
    title: str
    state: WidgetState                  # E4 — public enum
    activated_at: datetime | None
    tags: tuple[str, ...]               # D/§7.4 — frozen collection shape
```

```python
# domains/example/enums.py
class WidgetState(StrEnum):             # N3/N4 — not a Django choices class
    DRAFT = "draft"
    ACTIVE = "active"
    RETIRED = "retired"
```

```python
# domains/example/errors.py
class ExampleError(DomainError): ...                      # domain root
class WidgetNotFound(ExampleError, NotFoundError): ...
class WidgetAlreadyActive(ExampleError, ConflictError): ...
class WidgetActivationNotAllowed(ExampleError, NotAllowedError): ...
```

```python
# domains/example/selectors/widgets.py
def get_public_widget(public_id: PublicId) -> WidgetSummary: ...
    # public state: no actor parameter at all (§11.1)

def list_widgets_for_actor(actor: Actor, *, limit: int) -> tuple[WidgetSummary, ...]: ...
    # private state: actor first, mandatory, non-optional (Z1); bounded (K4); materialised (§10)
```

```python
# domains/example/services/activation.py
def activate_widget(actor: Actor, *, data: WidgetActivationInput) -> WidgetSummary: ...
    # command (§9): business verb, actor-scoped, returns a frozen DTO,
    # participates in the ambient transaction (§12), raises public errors only (§13)
```

```python
# domains/example/public.py
"""Public contract of the example domain. The only externally importable module."""

from .dto import WidgetActivationInput, WidgetSummary
from .enums import WidgetState
from .errors import (
    ExampleError,
    WidgetActivationNotAllowed,
    WidgetAlreadyActive,
    WidgetNotFound,
)
from .selectors.widgets import get_public_widget, list_widgets_for_actor
from .services.activation import activate_widget

__all__ = (
    # DTOs
    "WidgetActivationInput",
    "WidgetSummary",
    # enums
    "WidgetState",
    # errors
    "ExampleError",
    "WidgetActivationNotAllowed",
    "WidgetAlreadyActive",
    "WidgetNotFound",
    # selectors
    "get_public_widget",
    "list_widgets_for_actor",
    # commands
    "activate_widget",
)
```

Note what the module does **not** contain: no `def`, no `class`, no alias, no wildcard, no
`if TYPE_CHECKING`, no module re-export, no logic (S1–S9).

---

## 19. Contract checks Phase 1 must implement

These **extend** the item 3 §15 enforcement map; that map's L1–L19, A1–A13 and V1–V10 stay
authoritative and unchanged. The import-graph additions that ADR-0006 requires are in §19.5. Nothing
here is implemented in Phase 0.

### 19.1 Static / AST (continuing item 3's `A` series)

| # | Rule |
|---|---|
| A14 | `public.py` contains no `class`/`def` statement, no wildcard import, no `import ... as ...`, no module re-export (`from . import x`), no `if TYPE_CHECKING`, no module-level `__getattr__` (S1–S6). |
| A15 | `__all__` exists in every `public.py`, is a tuple of string literals, and matches exactly the set of imported names (S5). Extends A11, which already forbids re-exporting an ORM symbol. |
| A16 | No public DTO declares a field named `id` or `pk`; public locator fields are `PublicId`-typed (I1, I2). |
| A17 | Every class exported from `public.py` that is not an error or enum is a `@dataclass(frozen=True, ...)`; no public DTO field is annotated `list`/`dict`/`set`/`Any`/`float`-as-money, and none is annotated with a mutable-backed abstract shape — `Mapping`, `MutableMapping`, `Sequence`, `Iterable`, `Collection` (§7.1, §7.4). Key/value data is `tuple[PairDTO, ...]` or `tuple[tuple[K, V], ...]`. |
| A18 | No public signature contains `**kwargs`, an unannotated parameter, or `Any` (D1, §9.2). |
| A19 | No public callable declares a parameter named `actor` (or the frozen actor type) with a default or an `Optional` annotation (Z1, Z2). |
| A20 | No transport/vendor/ORM type appears in a public annotation: `HttpRequest`, `HttpResponse`, DRF types, `Task`, `QuerySet`, `Manager`, model classes, `integrations.*` types (§6). |
| A21 | No `transaction.commit/rollback/set_autocommit` call and no `atomic(durable=True)` inside a domain package (T2). |
| A22 | No `transaction.on_commit` in a domain package that schedules transport work (T5). |
| A23 | Every concrete public error inherits both a domain root deriving from `DomainError` and exactly one `core.errors` category (§13.1). |

### 19.2 Behavioural / contract tests (new `C` series)

| # | Rule |
|---|---|
| C1 | Every public selector returns a fully materialised immutable result: the returned object is a frozen DTO or `tuple` of them, and no SQL is issued after the call returns (query-count assertion around attribute access). |
| C2 | Mutating a returned DTO raises; a returned collection is not a `list`. |
| C3 | A private selector/command called with a non-owning actor raises the `NotAllowed` (or per-domain `NotFound`) category — never returns data. |
| C4 | Privileged access requires the explicit system context; there is no argument value that disables the check (Z2, Z3). |
| C5 | **Expected** failures are semantic: a missing object surfaces as `NotFound`, a denial as `NotAllowed`, and a forced violation of a *named* unique constraint as a `Conflict`-category public error — with the surrounding transaction still committable afterwards, asserted by committing it (§13.4). No `Model.DoesNotExist` and no vendor exception escapes a public callable. |
| C6 | Every public command produces the same outcome when called standalone and when called inside an outer `atomic()`; no command commits independently (T1, T2). |
| C7 | No public command or selector calls an external system or provider — asserted in the domain test tier with a fixture that blocks outbound sockets to anything but PostgreSQL and Redis, so legitimate database and disposable-cache I/O still runs. |
| C8 | Contract tests import `<domain>.public` **only**; a contract test that needs an internal import is a contract defect, not a test fixture problem. |
| C9 | **Technical faults are not laundered:** with the database made unavailable (or an `OperationalError` injected), a public callable raises a technical fault, **not** a `DomainError` category; likewise an injected `TypeError`/`AssertionError` propagates unchanged. A test asserting "any exception becomes a domain error" is itself the defect (§13.5). |
| C10 | A public selector performs **no** durable write: a write-counting assertion around a selector call shows no `INSERT`/`UPDATE`/`DELETE` against business, audit, consent or security state. Cache, metrics and tracing side effects are permitted and asserted separately (§10.2). |

### 19.3 Typing

| # | Rule |
|---|---|
| Y1 | `public.py` and every symbol it exports type-check in strict mode; the contract is usable by callers without `type: ignore`. |
| Y2 | Application/interface/task callers rely on declared contract types, never on duck-typed ORM attributes (`obj.pk`, `obj._meta`, `obj.refresh_from_db`). |
| Y3 | A public signature's types are stable enough to be referenced by callers: an exported type is not a private alias that changes shape between releases. |

### 19.4 Review-only (continuing item 3's `V` series)

| # | Rule |
|---|---|
| V11 | A symbol exported because one caller needed it, rather than because the domain intends to support it (§5 intent test). |
| V12 | A public enum that is a model-choices leak in disguise (N2). |
| V13 | A public DTO field that is technically immutable but semantically a vendor status or a transport concept (extends V3). |
| V14 | An internal bigint field on a public DTO that is in fact used as a user-facing locator (I3). |
| V15 | A "thin" public wrapper that has quietly acquired business logic or a second contract style inside a domain (S8, §4.3). |
| V16 | A selector performing a durable business/audit/consent/security write under a "technical side effect" label (§10.2). |
| V17 | An expected domain failure escaping as a technical fault, or a technical fault dressed as a business error, where the imports and shapes look legal (§13.2, §13.5). |
| V18 | An `integrations/*` adapter reasoning about an authorization subject or a domain error category through some indirect route (ADR-0006 §1, §2). |

### 19.5 Import-graph additions (continuing item 3's `L` series)

| # | Rule |
|---|---|
| L20 | `core.actor` (final name Phase 1) is importable by `domains.*`, `application.*`, `interfaces.*`, `tasks.*` and `config.*`; **`integrations.*` and `**/migrations/**` are forbidden sources** (ADR-0006 §1). |
| L21 | `core.errors` (final name Phase 1) is importable by `domains.*`, `application.*`, `interfaces.*`, `tasks.*` and `config.*`; **`integrations.*` and `**/migrations/**` are forbidden sources** (ADR-0006 §2). |

L13 is unchanged: `core.outbox` and `core.idempotency` remain forbidden to `interfaces/*`. L10 is
unchanged: `integrations/*` keeps its narrow pure-Python `core` subset, which these two modules do
not join.

---

## 20. Acceptance checklist

A `public.py` (and any change to one) is compatible with this freeze when every line holds:

- [ ] The module contains only a docstring, explicit imports and one explicit `__all__` tuple.
- [ ] No wildcard, no alias, no module re-export, no conditional/lazy import, no import-time side effect.
- [ ] Every exported symbol falls into one of E1–E8, and was exported deliberately.
- [ ] No ORM model, instance, manager, QuerySet, repository, service class, policy object, form, admin,
      migration, task, serializer, request/response, vendor DTO/SDK/exception, or lazy object is
      exported or reachable from an exported symbol.
- [ ] Every public DTO is `@dataclass(frozen=True, slots=True, kw_only=True)`, fully annotated, with
      only allowed field types; no `list`/`dict`/`set`/`Any`; no money `float`; no `Mapping`,
      `Sequence` or other mutable-backed abstract shape — key/value data is `tuple[PairDTO, ...]` or
      `tuple[tuple[K, V], ...]` with documented ordering where it matters.
- [ ] Every public DTO property/method is pure and total; nothing lazily queries the database.
- [ ] Instants are timezone-aware UTC `datetime`; money is `Money`; public locators are `PublicId`.
- [ ] No public DTO field is named `id` or `pk`; no internal identifier can become a user locator, a
      public API payload identifier, an external webhook/integration identifier or an externally
      consumed event identifier; any legitimate internal identifier is named `internal_*`.
- [ ] Every command has a business-imperative name, returns a frozen DTO/value or `None`, and makes
      no direct call to an external system or provider (its own PostgreSQL work and the transactional
      Outbox row are not that).
- [ ] Every selector returns fully materialised immutable data, issues no SQL after returning, and
      performs no durable write to business, authorization, audit or compliance state — only
      disposable cache/metrics/tracing side effects.
- [ ] Every operation on private state takes an explicit, mandatory, non-optional actor as its first
      parameter; no `actor=None`; privileged access is an explicit system context.
- [ ] No caller-supplied authorization decision is accepted as a parameter.
- [ ] No command commits, rolls back, toggles autocommit or uses `durable=True`; every command composes
      correctly inside an application-owned outer transaction.
- [ ] Every **expected** domain failure is a listed public domain error with exactly one
      `core.errors` category; a database error is translated only when the violated invariant is
      identified by name, and only at a nested savepoint.
- [ ] **Technical and unexpected faults** — database unavailable, unclassified `DatabaseError`,
      corruption, programmer bugs — propagate untranslated to the platform boundary and appear in no
      `__all__`; none of them is rewritten as `NotFound`/`Conflict`/`Validation`.
- [ ] No Django/vendor/HTTP exception, error code or status number is exported or named in a public
      annotation.
- [ ] Public enums are intentional contract types, string-valued, not Django choices classes.
- [ ] Collections are `tuple[DTO, ...]` with a stated bound; no paginator or `Page` crosses.
- [ ] The same contract serves application, interfaces (one domain per request), tasks and contract
      tests; no second surface exists.
- [ ] The change is classified as internal / additive / breaking per §17, with an ADR only where a
      frozen architectural decision moves.

---

## 21. Explicitly deferred decisions

| Deferred | Owner |
|---|---|
| The actor type's fields, roles/capabilities model and construction API; the final module name `core.actor` (its **placement and consumers** are frozen by ADR-0006 §1) | the phase implementing authentication (Phase 1 baseline, refined per domain) |
| The final module name and exact class names of the `core.errors` categories (their **placement and consumers** are frozen by ADR-0006 §2) | Phase 1 |
| Whether a project-approved **immutable mapping** type is adopted, and with which concrete value type; until then key/value data is a frozen tuple of pairs (§7.4) | a later deliberate approval + an amendment to §7.4 |
| The mechanism by which state legitimately changes as a consequence of a read (explicit command, post-read event, or a separately owned counter pipeline) | the feature that needs it (§10.2) |
| Physical file layout inside a domain (`services/` vs `commands/`, one file vs package per family) | Phase 1 |
| The AST checker implementation for A14–A23 and the contract-test harness for C1–C8 | Phase 1 |
| `Money` / `PublicId` implementation | Phase 0 item 11 |
| The public API of Catalog, Pricing, Inventory, Orders, Payments, Reviews, Accounts, … | the phase implementing each domain |
| `place_order` internal design and `application/checkout`'s public surface | Phase 0 item 5 |
| Storefront read model, `ProductCard`/Facet DTO fields, pagination shape | Phase 0 items 6, 7 |
| Event registry, event names and versioning policy (a separate contract, §17.4) | Phase 0 item 8 |
| Whether a specific domain answers a non-visible private object with `NotFound` or `NotAllowed` (Z8) | per domain, recorded in that domain's contract |
| Any weakening of §4–§17 (optional actor, ORM/vendor/transport type in a contract, second public surface) | requires a new ADR |

---

## 22. Self-review record

| # | Check | Result |
|---|---|---|
| 1 | No ORM model/instance/manager/QuerySet can legally cross `public.py` | Pass — §6 forbids the category, §7.4 forbids the field types, A11/A17/A20 check shapes, C1/C2 check behaviour, and §10.3 states why materialisation is a contract term. |
| 2 | No domain→domain import becomes legal | Pass — nothing here grants a domain a new import. §4.1 S9 limits `public.py`'s own imports to its domain plus `core` edge primitives; R2/L2 stand. The `core.errors`/`core.actor` additions are `core`, which every domain already imports (item 3 §4.2). |
| 3 | Application, interfaces and tasks consume the same contract | Pass — §4.3 forbids a second surface; §16 lists all four consumers against one `public.py`, preserving A5/V10's one-domain-per-request bound. |
| 4 | Private access is actor-scoped by construction | Pass — §11.1's two shapes (no actor for public state / mandatory actor for private state) leave no third form; Z1, Z5–Z7, A19, C3. |
| 5 | System access never relies on `actor=None` | Pass — Z2 forbids the value, Z3 requires an explicit system type, Z4 requires it to be visible in the name/type, A19 and C4 check it. |
| 6 | Domain public errors expose no HTTP/vendor/Django persistence semantics | Pass — §13.6 enumerates what is never exported; X2/X5 keep mapping outside the domain; §13.4 handles the savepoint hazard so translation cannot corrupt the caller's transaction; C5 tests it. |
| 7 | Public commands make no direct external/vendor call | Pass — §9.1 and T4 forbid it unconditionally and name both sides precisely: forbidden are provider/ERP/CRM/email/SMS/Chatwoot calls and direct broker publishing; allowed are the domain's own PostgreSQL work, the transactional Outbox row, a selector's disposable Redis cache population and observability. Outbound capability remains an `application` port implemented by an adapter (ADR-0005 §2); C7 asserts it with a socket-blocking fixture that still permits PostgreSQL and Redis. |
| 8 | Public commands compose inside an application-owned outer transaction | Pass — §12.1 forbids the variant split and `in_atomic_block` branching; T1 makes nesting a savepoint an implementation detail; T2 bans `durable=True` and manual commits; T6 restates ownership; C6 tests both call shapes. |
| 9 | Selectors return fully materialised immutable DTOs | Pass — §10.1, §10.3, K1, C1. |
| 10 | No public DTO hides lazy database access | Pass — §7.3 requires pure and total members, `slots=True` removes `cached_property`, §6 lists lazy objects as a forbidden export, C1 measures queries after return. |
| 11 | `public.py` cannot become a wildcard/re-export dump | Pass — S1–S9 with A14/A15; the §5 intent test plus V11 cover the meaning a checker cannot see. |
| 12 | Public enums are intentional contract types, not model-choice leakage | Pass — N1–N6, V12; N3 additionally keeps the ORM `TextChoices` type itself from crossing. |
| 13 | Internal bigint identifiers cannot become public locators | Pass — I1–I3 with A16 and V14. I3 now names the four externally visible roles an internal identifier may never take (user locator, public API payload identifier, external webhook/integration identifier, externally consumed event identifier); I4 keeps strictly internal orchestration and strictly internal versioned events/jobs legal, so the wording no longer contradicts the frozen internal-event rules, and event schemas stay with item 8. |
| 14 | The template defines no domain-specific API belonging to a later phase | Pass — §1.2 and §21; every code fragment is `domains/example`; §9.3, §10.3 and K5 explicitly disclaim the illustrative names. |
| 15 | No contradiction with ADR-0001…0006 | Pass — ADR-0001: §8 restates the three identifier roles and adds no fourth. ADR-0002: untouched. ADR-0003: K5 keeps the projection out; I5 keeps provider identity at the integration boundary. ADR-0004: §3 (§4.1 S9), §5/§9 (§16), §6 (§11), §10 (§12) all preserved. ADR-0005: §7's one-entry-point rule is specified, not widened; its text is unedited, and the two allowlist extensions are decided by ADR-0006 by reference, leaving L10 and L13 intact. |
| 16 | The error strategy keeps `core` free of business vocabulary | Pass — §13.1: `core.errors` holds one root and five structural categories, closed by rule; every concrete error is domain-owned. Both rejected alternatives are recorded with their failure mode. |
| 17 | The `core` allowlist extensions are decided, not assumed | Pass — §1.3 and [ADR-0006](../../adr/0006-public-contract-primitives.md) record both extensions with their consumer tables, L20/L21 make them enforceable, and the earlier claim that no ADR was needed is withdrawn. |
| 18 | `integrations/*` gains no actor and no domain-error coupling | Pass — ADR-0006 §1 and §2 list `integrations/*` as `FORBID` for both primitives, §11.3 and §13.1 restate it, L20/L21 enforce it, and V18 covers the indirect route. An adapter reports failure through its port's vendor-neutral edge types (ADR-0005 §6.3). |
| 19 | A technical fault cannot be laundered into a business error | Pass — §13.5 lists the fault classes, forbids the conversion, keeps them out of `__all__`, and states the precise promise; X6 records the non-guarantee; C9 tests a database outage and an injected programmer error; V17 covers the review-only variant. §13.4 restricts translation to a *named*, identified invariant, so an unclassified `IntegrityError` cannot slip through as a `Conflict`. |
| 20 | Expected persistence races are still translated safely | Pass — §13.4 keeps the nested-savepoint requirement and ties it to T8; C5 asserts the surrounding transaction is still committable; `MultipleObjectsReturned` under an expected uniqueness assumption is classified as a defect, not a business error. |
| 21 | DTO immutability no longer rests on a convention | Pass — §7.4 removes `Mapping` and the other mutable-backed abstract shapes from the allowed field types, replaces them with `tuple[PairDTO, ...]` / `tuple[tuple[K, V], ...]` plus documented ordering, introduces no immutable-map dependency in Phase 0, and defers a real immutable mapping type to a deliberate approval; A17 checks the annotations, C2 checks the behaviour. |
| 22 | Selectors cannot write durable business or audit state | Pass — §10.2 permits only cache/metrics/tracing, names the five common durable writes as forbidden (`last_seen_at`, audit/access history, consent, security decision, business counters), and routes the need to an explicit command or a separately owned mechanism designed elsewhere; C10 and V16 enforce it. |

Verdict: **PASS**.
