# Phase 1 — Slice 2: the `core` primitives

- **Status:** DONE
- **Date:** 2026-09-07
- **Phase:** 1 — first production code
- **ADRs:** **none required.** Every choice below fills a deferral Phase 0 explicitly assigned to
  Phase 1 — item 11 §42, ADR-0012's "physical Python construct, module and member names",
  ADR-0013's out-of-scope list, ADR-0006 §3, item 4 §11.3 / §13.1. No frozen artifact or accepted
  ADR was edited, and no frozen rule was changed.
- **Implements:** item 15 §15 clause 3; item 11 PART A/B/C; ADR-0012; ADR-0013; ADR-0006 §1/§2 and
  their L20/L21 import rules; item 8 OW4 (`core.events` as mechanism only, registry empty).
- **Builds on:** [Slice 1](01-repository-bootstrap.md), which is accepted and unchanged apart from
  the two harness extension points it left open for this slice.

> This artifact records **only** what Phase 0 deferred: physical module and member names, and
> concrete technical representations. Where a rule is quoted it is quoted to say which frozen rule a
> choice serves, never to restate or reinterpret it.

---

## 1. Scope

Created: `Money`, `RoundingPolicy`, `PublicId`, `EventId`, the actor primitive, the structural
public-error categories, and the minimum `core.events` mechanism — with the event registry
**empty**. Plus the enforcement and tests those physical names make possible.

Deliberately **not** created: `IdempotencyKey`; Outbox; Inbox; quarantine or dead-letter persistence;
any event business contract; any domain model, application use case, port or adapter; Celery; DRF;
a cache client; any migration; the query-budget harness; any `LATER` module. No infrastructure gate
was opened. §10 lists what remains deferred and to whom.

---

## 2. Physical layout

Item 11 §42 row 1 deferred "the physical `core` modules, file layout, member names and signatures".
Frozen for this repository:

```text
core/
  _uuid7.py            the shared UUIDv7 mechanism — internal, exported to nobody (TX2, TX3)
  money.py             Money · RoundingPolicy · money_from_decimal
  public_id.py         PublicId
  actor.py             Actor · SystemActor
  errors.py            DomainError + the five structural categories
  events/
    identity.py        EventId
    envelope.py        Envelope (the four EN1 fields + the four TCE fields)
    registry.py        MessageKind · MessageStatus · RegisteredMessage · MessageRegistry ·
                       MESSAGE_REGISTRY (empty)
    errors.py          MessageContractError · UnknownEventType · UnsupportedSchemaVersion
```

`core/money.py` and `core/public_id.py` match master `# 3`/`# 4`'s placement, which item 11 §1.4
preserved. `EventId` sits in `core.events` because `event_id` *is* an envelope field (OW3), and
`core.events` is already allowlisted for `domains`/`application`/`tasks`/`config` and already
`FORBID` for `integrations/*`. **No `core` submodule allowlist entry was added, removed or widened**
(OW6, TX6), and the `interfaces` allowlist gained only the two modules ADR-0006 §1/§2 authorised.

`core/__init__.py` and `core/events/__init__.py` stay **empty**: no umbrella re-export exists, and
`core` follows its own frozen per-family allowlists rather than the `public.py` façade convention, so
no `core/public.py` was created (task §8, item 4 §4).

---

## 3. `Money`

### 3.1 The currency representation — the one genuinely open choice

Item 11 §4 writes `currency : currency — an explicit, canonical currency code` and leaves the
physical form to Phase 1. **Chosen: a `str` field, validated structurally at construction.** It is
the narrowest implementation that satisfies every frozen rule: CU1's canonical uppercase, CU3's
"exactly three ASCII letters `A`–`Z`" as the whole of `core`'s currency knowledge, CU5's rejection of
`"mdl"`/`" MDL"`/`"Mdl"` rather than normalisation, and MS4's "no third field".

A distinct `Currency` wrapper type was considered and rejected: it would add a second value type with
its own equality, hashing and parsing story without strengthening a single frozen rule — the
structural validation and the exact-type check already prevent every failure a wrapper would prevent.
`core` still holds **no** currency list, no ISO registry and no currency library (CU3), so *which*
currencies are tradeable remains the owning module's policy (CU4).

### 3.2 Shape and operations

`@dataclass(frozen=True, slots=True, kw_only=True)` per item 4 §7.1, with `minor: int` and
`currency: str`. `order=True` is **not** used; the four ordered comparisons are written by hand behind
one currency guard (ADR-0012, OD3).

| Chosen | Serves |
|---|---|
| `__add__`, `__sub__`, `__neg__`, `__mul__`/`__rmul__` by an exact `int` count | AR1, AR3, AR4, SG5 |
| `__lt__`, `__le__`, `__gt__`, `__ge__`, each guarded | OD1, OD2, ADR-0012 |
| no `__truediv__`, no `__floordiv__` | AR5 — splitting is proportional allocation, owned by a domain |
| `__radd__`/`__rsub__` that reject a bare number | AR7, and it is what makes ZR2 self-enforcing |
| no `__str__`, no `format`, no `to_json` | CV6, SN4 — `Money` renders nothing |
| no aggregation, ordering, FX or formatting helper in `core` | OD6, HR4, FX3, A80, V90, V91 |

**No `sum()` helper was written, deliberately.** `sum(values)` starts at bare `0`, reaches
`Money.__radd__` and raises, so the naive aggregation of a possibly empty sequence fails loudly
exactly as ZR2 requires; `sum(values, Money(minor=0, currency=...))` is the correct spelling and needs
nothing from `core`. That is a smaller mechanism than a helper *and* a stricter one.

### 3.3 How a rejection is raised

Item 11 §37 classifies every misuse here as a **programmer error** that propagates untranslated and
is never mapped to a `core.errors` category. **Chosen: the builtins.** `TypeError` for a wrong type
(`bool`/`float`/`Decimal`/`str` as `minor`, a non-`str` currency, a bare number in a money
expression, a non-`RoundingPolicy` policy); `ValueError` for a structurally invalid or incommensurable
value (a non-canonical currency spelling, a cross-currency operation, a negative exponent, a
non-finite `Decimal`).

No new exception class was introduced anywhere in the money mechanism. ER2 says a new `core` public
error primitive for item 11 would need its own ADR; item 4 §13.5 already names `TypeError` and friends
as technical faults, so the builtins carry this correctly and add no `core` vocabulary.

### 3.4 `money_from_decimal` — the single materialisation point

```python
money_from_decimal(*, amount: Decimal, currency: str, exponent: int, rounding: RoundingPolicy) -> Money
```

Every parameter is keyword-only and **required**; a test asserts that, because RP1/CV5's "no default
anywhere" is the rule most easily lost to a convenience default. `exponent` is passed in, never
discovered (EX6) — so nothing assumes two decimals, and a zero-exponent and a three-exponent currency
are covered by the tests exactly as C100 requires.

Determinism (CV7, RP4, DE6) is achieved by running the scaling and the quantisation inside an
**explicit** `decimal.Context` whose precision is derived from the operand, rather than inheriting the
caller's ambient context. A test re-runs the conversion under a deliberately hostile ambient context
(`prec=3`, `ROUND_UP`) and asserts the same result.

`float` is rejected at the door, in construction, arithmetic, comparison and conversion (IG3, FL1,
CV2). No conversion **out** of `Money` was written: rendering and provider mapping are boundary work
that arrives with the interface and integration slices (CV6, DT2, DT3).

---

## 4. `RoundingPolicy`

RP7 deferred the member set to Phase 1 and named "half-even, half-up, down and up" as an
**expectation, not a decision**. **Chosen: exactly four members**, spelled so the tie direction is
unambiguous for the signed amounts SG1 permits:

| Member | Decimal rule | Why this spelling |
|---|---|---|
| `HALF_EVEN` | `ROUND_HALF_EVEN` | banker's rounding |
| `HALF_UP` | `ROUND_HALF_UP` | ties away from zero — the near-universal name, kept |
| `TOWARD_ZERO` | `ROUND_DOWN` | "down" is ambiguous once an amount may be negative |
| `AWAY_FROM_ZERO` | `ROUND_UP` | likewise for "up" |

Four rather than two, because these are the four genuinely distinct rules a minor-unit materialisation
can need and they are the set Phase 0 anticipated; fewer would be an arbitrary cut that RP7's
"under-commit" horn warns against. Each member names an **arithmetic rule**, never a business step
(RP5) — `A77` now checks that mechanically. Adding a member later is additive; removing one is not.

`core` still chooses nothing: which policy a business step uses is stated and tested by the module
that owns the step (RP6), and no default exists at any level (RP1).

---

## 5. `PublicId` and `EventId`

### 5.1 The construct

PI4/TY5 bound Phase 1 to "a runtime-distinct immutable value representation", admitting a frozen
validating wrapper and excluding a bare `typing.NewType`. **Chosen: two separate frozen validating
wrapper value objects**, `@dataclass(frozen=True, slots=True, kw_only=True)` over a single
`value: uuid.UUID` field, each with `.new()`, `.parse()` and a canonical `__str__`.

They are **not** given a shared base class. Sharing the *validation* is what ADR-0013's negative
consequence asks for, and that is achieved through the shared functions in §5.2; a shared supertype
would additionally create a common annotation that both types satisfy, which is precisely the
interchangeability TY3/TX5 exist to prevent. Twenty duplicated lines is the cheaper of the two costs.

The distinction is asserted at runtime, not only in annotations: `PublicId(value=U) != EventId(value=U)`,
neither resolves in the other's lookup path, and same-type equality is asserted alongside so the test
pins the distinction rather than merely a failure (C127). Hash collision across the two types is left
unasserted, as EQ5 requires.

### 5.2 The shared mechanism and the UUIDv7 implementation

`core/_uuid7.py` holds `generate`, `validated`, `parse_canonical` and `render` — one algorithm, one
library decision, two semantic types (TX2, EV4). It is a surface of `core` for **nobody** (TX3): the
leading underscore says so to a reader, the family allowlists exclude it, and `A82`'s import half now
reports any module outside `core` that reaches it.

GN2 required a standards-conforming implementation chosen against the pinned Python version.
**Chosen: the pinned runtime's own `uuid.uuid7()`.** Verified against the installed interpreter
(CPython 3.14.7, matching `requires-python = "==3.14.*"`): the function exists and produces RFC 9562
version-7 values. **No dependency was added**, and no bit layout, timestamp source or entropy scheme
is hand-rolled here.

Canonical parsing accepts only the lowercase hyphenated 8-4-4-4-12 form and only version 7 (PA1–PA3);
uppercase, brace-wrapped, `urn:uuid:`-prefixed and unhyphenated spellings are **rejected, not
normalised**. A foreign *v7* passes the structural test by construction — shape is not provenance —
and stays the owning boundary's problem exactly as EI5/V99 place it; the primitive's contribution is
that no implicit coercion from a bare `uuid.UUID` exists anywhere.

Nothing reads the embedded timestamp, and neither type exposes a route to it (TS1–TS6, A83).

---

## 6. The actor primitive and the structural errors

### 6.1 `core/actor.py`

ADR-0006 §3 and item 4 §11.3 deferred the module name, the class names and the fields.

| Chosen | Serves |
|---|---|
| module `core.actor` | ADR-0006 §1's working name, now the physical one; L20 keys off it |
| `Actor(principal_id: PublicId)` | the authenticated principal, identified in the public identity space (D9, PI3, TY1/TY2) rather than by a bare `UUID` or an internal `bigint` |
| `SystemActor(purpose: str)` | Z3's explicit privileged context, as an explicit **sibling type** (item 4 §11.3), so Z4's "a parameter type that only a system context satisfies" is expressible |
| both frozen, slotted, keyword-only, **no field default** | Z1, Z2 — no partially built and no "unauthenticated but privileged" value exists |
| `purpose` validated as `[a-z][a-z0-9_]*` | a bounded, greppable mechanism token rather than free text, so a purpose cannot become a channel for a secret or a personal datum (X3, SE6) |
| **no union alias** | a callable that accepts either writes `Actor \| SystemActor` itself, keeping every privileged admission visible and greppable (Z3, Z4). An alias would become the default annotation and Z4 would quietly stop meaning anything |

`principal_id` names the platform account neutrally: `core` holds no entity vocabulary (OW5), and
which entity the locator addresses is the authentication phase's to state. Roles, capabilities,
sessions and tenants remain that phase's (ADR-0006 §3) and none of them is stubbed here. No user
model, authentication backend, permissions framework, HTTP/session concept or vendor concept was
created.

### 6.2 `core/errors.py`

Item 4 §13.1 already wrote the six names; this slice makes them physical: `DomainError` plus
`NotFoundError`, `NotAllowedError`, `ConflictError`, `InvalidStateError`, `ValidationError`, each
deriving from the root so a concrete domain error can inherit `(<DomainRoot>, <Category>)` exactly as
§13.1's example shows.

They are **markers**: no fields, no `__init__`, no `code`, no message, no HTTP status, no DRF
exception, no Django persistence error, no provider vocabulary, no domain meaning. The module imports
nothing. A test asserts the class set *is* the six, so growth cannot happen quietly — the taxonomy is
closed by rule and a new category needs an ADR.

### 6.3 L20 / L21 — both halves closed

Slice 1 §6.4 left `CORE_PUBLIC_CONTRACT_PRIMITIVES` as an explicitly empty tuple with "no name is
guessed". It is now `("core.actor", "core.errors")`, and the two rules report under their own frozen
ids:

| Family | `core.actor` (L20) | `core.errors` (L21) | Mechanism |
|---|---|---|---|
| `domains` · `application` · `tasks` · `config` | ALLOW | ALLOW | already legal; proved by fixture |
| `interfaces` | **ALLOW** — ADR-0006's allowlist extension | **ALLOW** | added to `INTERFACES_CORE_ALLOWLIST`; the import no longer reports `M4.4-CORE` |
| `integrations` | **FORBID → L20** | **FORBID → L21** | `tools/arch_check` **and** a new `import-linter` contract |
| `**/migrations/**` | **FORBID → L20** | **FORBID → L21** | `tools/arch_check` (A6's path); no migration exists for a path-scoped contract yet |

Reporting the adapter and migration cases under `L20`/`L21` rather than under the generic `L10`/`A6`
that already covered them follows the `L13` precedent Slice 1 §6.4 set for
`core.outbox`/`core.idempotency`. **The generic `integrations` `core` allowlist was not widened** —
`INTEGRATIONS_CORE_ALLOWLIST`, `PORTS_CORE_ALLOWLIST` and `MIGRATION_CORE_ALLOWLIST` are byte-for-byte
unchanged, and a test asserts that an adapter reaching `core.events`/`core.inbox` still reports `L10`
and nothing else.

---

## 7. `core.events` — mechanism only, registry empty

### 7.1 What was built

| Module | Contents | Frozen basis |
|---|---|---|
| `identity.py` | `EventId` | OW3, ADR-0013 |
| `envelope.py` | `Envelope`: the four EN1 fields plus the four TCE fields, structurally validated | EN1–EN7, FS1–FS10 |
| `registry.py` | `MessageKind`, `MessageStatus`, `RegisteredMessage`, `MessageRegistry`, `MESSAGE_REGISTRY` | §7.1, §25.1, §25.2, RI1, RI5, RG8 |
| `errors.py` | `MessageContractError`, `UnknownEventType`, `UnsupportedSchemaVersion` | §20, VL4, QU10 |

**The envelope vocabulary is exactly the frozen eight**, flat and in order: `event_id`, `event_type`,
`schema_version`, `occurred_at`, `trace_id`, `producer_span_id`, `request_id`, `causation_event_id`.
A test asserts both the tuple and the absence of `correlation_id`, every metadata-bag spelling,
`baggage`, `tracestate`, an ancestry path, a generic `idempotency_key` and every transport field.

Structural validation, and only structural validation: NM1's `event_type` grammar with owner
qualification, `schema_version >= 1` by exact `int`, an aware **UTC** `occurred_at`, the W3C value
spaces for `trace_id` (32 lowercase hex, all-zero invalid) and `producer_span_id` (16), a bounded
opaque `request_id` with PR6's placeholders rejected, `causation_event_id` typed as `EventId`, and
CZ6's self-causation ban. NM4/NM5/NM6's prohibitions on *meaning* stay with registry review.

**Two deliberate permissions, both required by the frozen rules.** A broken `trace_id`/`producer_span_id`
pair is *permitted* rather than rejected, because PR2 says such a message is read as untraced and
**processing continues normally** — recording and alerting the defect is capture-and-consume
behaviour. And a `causation_event_id` that resolves to nothing is permitted, because CZ10 makes a
dangling parent expected once its partition is archived.

Phase-1 choices recorded: the `request_id` bound is **128 characters**, printable non-whitespace ASCII
(RQ6 requires "bounded" and leaves the number open); `RegisteredMessage` models the four registry
fields the *runtime* lookup needs — the key plus `kind` (§7.1's mandatory discriminator, authorised as
a runtime value by KD7) and `status` (§25.2) — while the semantic owner, payload-contract location,
producers, per-consumer declarations, lineage, exposure and notes stay in the reviewed document.

### 7.2 The registry is empty, and provably so

`MESSAGE_REGISTRY = MessageRegistry()` — no entries. Tests assert `len(...) == 0` and `entries == ()`,
and additionally assert that six names a reader might expect (`catalog.project.batch`,
`inventory.reservation_changed`, `orders.order_placed`, `payments.payment_captured`,
`review.approved`, `storefront.reproject_products` — all master illustrations, none a registry entry)
raise `UnknownEventType`. A further test walks `core/events/**` and asserts the exact set of classes
declared there, so no payload contract can appear unnoticed (A46).

**No sample event was created to exercise the mechanism.** Every case that needs a registered message
builds one locally in the test module under a fixture name that exists nowhere else.
`docs/architecture/events/event-registry.md` was not touched and still reads "no entries".

### 7.3 A contract failure is not a business error

`MessageContractError` derives from `Exception`, **not** from `DomainError`, and tests assert that
from both sides. That is VL4/QU10 made structural: a quarantine outcome cannot be caught by a
handler's `except DomainError` and quietly turned into a business outcome.

### 7.4 What was left out of `core.events`, and why

A canonical JSON codec was **not** written, although §7 of the task admits one. Item 8 VL8/SZ1 leave
the serialization and validation library to "Phase 1" without saying which slice, and nothing in this
slice serializes: there is no payload, no schema artifact format (§27 is deferred), no Outbox row and
no transport. Building an encoder with no consumer would be a mechanism kept alive by its tests alone.
It arrives with the Outbox/Inbox slice that has something to encode.

---

## 8. Enforcement harness changes

Narrow, and only where a subject now physically exists.

| Rule | Status | What it checks |
|---|---|---|
| **L20 / L21** | **now full**, both halves | §6.3 |
| **A75** | partial | *Static half:* the money value type declares no `dataclass(order=...)` generation — ADR-0012's dedicated check for the one-word regression. *Behavioural half:* that the four comparisons it does define are currency-guarded is asserted in both operand orders and through `min`/`max`/`sorted` (C103) |
| **A70** | partial | *Vocabulary half:* no name defined in `core.money` carries discount/VAT/tax/promo/promotion/loyalty/delivery/price/pricelist/provider vocabulary, matched segment-wise so `private` does not read as `vat`. *Sign/range half:* an `assert_non_negative`-shaped helper stays a review shape (V91) |
| **A77** | full | no `RoundingPolicy` member is named for a business step; reported under its own id, separately from A70 |
| **A71** | full | no three-letter currency literal anywhere in `core` |
| **A82** | partial | *Import half:* no package outside `core` reaches the UUIDv7 mechanism. *Annotation half* — no bare `uuid.UUID` in a locator position — waits for the first public signature or DTO |

`import-linter` gained one contract, "L20/L21 the public-contract primitives are closed to adapters"
(13 contracts, all `KEPT`). Nothing else in the harness changed: no allowlist was broadened, and every
Slice-1 rule still reports the id it reported before.

### 8.1 The Slice-1 deferral list, re-evaluated honestly

| Check | Verdict now |
|---|---|
| **A16** no `id`/`pk` on a public DTO, locators `PublicId`-typed | **still deferred** — the subject is a DTO exported from a `public.py`; none exists |
| **A17** exported classes are frozen dataclasses with allowed field types | **still deferred** — same subject |
| **A18** no `**kwargs`, unannotated parameter or `Any` in a public signature | **still deferred** — same subject |
| **A19** no `actor` parameter with a default or `Optional` | **still deferred.** The actor *type* now exists, so the rule is implementable the day a public callable does; there is no public callable to inspect, and checking an empty tree would be fabrication. That both types reject `None` and declare no default is asserted behaviourally instead |
| **A20** no transport/vendor/ORM type in a public annotation | **still deferred** — no public annotation exists |
| **A21** no `transaction.commit/rollback/set_autocommit`, no `atomic(durable=True)` in a domain | **still deferred** — no domain code exists |
| **A22** no `transaction.on_commit` scheduling transport work in a domain | **still deferred** — no domain code exists |
| **A23** every public error inherits a domain root plus exactly one `core.errors` category | **still deferred.** The five categories now exist and the composition is proved by a fixture-level test, but the rule's subject is a *concrete domain error*, and no domain publishes one |
| **A2**, second half of **A13** | still deferred — no vendor client |
| **A4**, **A7**, **C1–C8**, L19's path-scoped migration exclusion, `MIGRATION_CORE_ALLOWLIST` entry | still deferred, unchanged from Slice 1 |

None of the eight A16–A23 rules is recorded as passing.

---

## 9. Verification

`make check`, from a shell with `DJANGO_SECRET_KEY` and every `POSTGRES_*` variable unset:

```text
ruff check .                    All checks passed
lint-imports                    13 contracts kept, 0 broken
python -m tools.arch_check .    OK
pytest                          403 passed
manage.py check                 System check identified no issues
```

Slice 1's 118 tests are included and unchanged; 285 were added. No database is contacted.

---

## 10. Deliberately deferred to later slices

| Deferred | Owner |
|---|---|
| `IdempotencyKey` model and migration | ADR-0015 slice (item 15 §15 clause 4) |
| Outbox/Inbox initial schema with the four TCE fields, quarantine and dead-letter tables | clause 5 |
| **TCE capture**: populating the four fields at the Outbox INSERT inside the business transaction, PR2's pair-integrity record-and-alert, PR4's normalise-malformed-to-absent at capture, and the relay/consumer carrier rules | the Outbox/Inbox slice |
| **Canonical serialization** (§29) and payload validation against a registered schema (§28), plus the schema-artifact format and generation pipeline (§27, §6.3) | the slice that has a payload to encode |
| Registration of any `(event_type, schema_version)`, consumer support declarations, per-consumer effect-idempotency declarations, upcasters, emission checks (A42, A43, A49, A50) | each owning module's own phase |
| Routing, failure domains, queues, replay tooling | item 9's topology, in its slice |
| The **currency-exponent** source — a checked-in static table or an approved library (EX5) | the boundary that first parses a major-unit amount; `core` holds none |
| Conversion **out** of `Money` for display or a provider (CV6, DT2, DT3, DT4) | the interface and integration slices |
| Any FX mechanism, rate source or conversion API (FX4) | a future phase, on a new decision |
| Additional `RoundingPolicy` members, each justified by the domain that needs it (RP7) | that domain's phase |
| The actor's permission model — roles, capabilities, session, tenant — and its construction API | the authentication phase (ADR-0006 §3) |
| Django field classes, columns, `CHECK` constraints and indexes for money and `public_id` (PS7, PK8) | each owning schema's phase |
| The signed guest/access token; the keyset cursor codec | the security/checkout phases; Phase 4 |
| A type checker (`Y1`–`Y3` are typing obligations that need one) | not required by this slice |
| Query-budget / N+1 harness; CI job wiring | unchanged from Slice 1 §11 |

Nothing in this slice required changing a frozen boundary, so no superseding ADR is needed.
