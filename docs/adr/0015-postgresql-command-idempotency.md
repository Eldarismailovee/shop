# ADR-0015 — Command idempotency: a PostgreSQL-canonical `(scope, key)` claim committed with the effect it protects

- **Status:** Accepted — Frozen
- **Date:** 2026-09-06
- **Phase:** 0 — Architecture Freeze
- **Supersedes:** —
- **Related:** [ADR-0004](0004-four-layer-modular-monolith.md) §10 (the use case owns its transaction;
  local ACID is not a saga),
  [ADR-0006](0006-public-contract-primitives.md) (the actor primitive and the structural error
  categories),
  [ADR-0007](0007-place-order-atomic-idempotent-boundary.md) §2 (placement idempotency **behaviour**,
  which explicitly defers the generic mechanism here),
  [ADR-0009](0009-event-contract-versioning.md) §7 (message identity and consumer effect
  idempotency — **untouched**),
  [ADR-0010](0010-async-failure-domain-isolation.md) (ambiguous provider outcomes, replay),
  [ADR-0013](0013-event-id-distinct-identity-type.md) (`EventId` is message identity),
  [item 5](../architecture/phase-0/05-place-order-use-case.md) §11–§12 ID1–ID7,
  [item 8](../architecture/phase-0/08-event-registry-versioning.md) §17,
  [item 15](../architecture/phase-0/15-adr-closure.md) (the closure artifact, its failure matrix and
  its checks),
  master `# 5` principle 3, `# 5.2`, `# 5.4`, `# 11.4`, `# 12.1`, `# 20.4`, `# 20.5`

## Context

Master `# 5.2` names `IdempotencyKey` as the platform's single mechanism for protecting repeated
**commands**, gives it a `UNIQUE (scope, key)` constraint, requires the claim to happen in the same
PostgreSQL transaction as the domain entity it protects, and demotes Redis to an optional L1
anti-storm filter. Master `# 20.4` separates it from two neighbours: `InboxDedupeKey` for repeated
external events, and domain `UNIQUE`/state machines for worker retries.

ADR-0007 §2 froze the *behaviour* this gives `place_order` — claim and completion inside the
placement transaction, a rollback leaving no claim, replay scoped to the principal, a different
fingerprint producing `Conflict` — and closed with one sentence that created this ADR:

> The `IdempotencyKey` schema, retention specifics and the generic idempotency ADR remain out of
> scope (Phase 0 item 15).

The other scope names master `# 20.4` lists — `payment.initialize`, `refund.create`, `coupon.redeem`,
`tradein.redeem`, `digital.fulfillment.allocate` — are **illustrative names whose exact owning-command
semantics belong to their implementing phase**; in particular, a name does not establish that the
workflow it labels is a single local ACID command (§6 states the split, and `payment.initialize` is
the case that makes it matter). Each of those phases will nevertheless reach the same three questions.
Left unanswered, they get answered locally, and each has a plausible-looking wrong answer:

1. **What does the master's `state = processing / completed / failed` column mean?** Read literally,
   `processing` is a durable value, which requires a committed row *before* the business effect —
   a two-transaction pattern that ADR-0007 §1 forbids for placement and that would produce exactly
   the two failure modes ADR-0007 rejected: a completed-looking claim outliving a rolled-back
   effect, and a key poisoned by a transient fault. `failed` has the same shape: an accidental
   validation error would durably reserve a key the caller should be able to retry with.
2. **Is `response_body_json` the mechanism's truth?** Taken as mandatory, every command would have
   to persist a raw HTTP response — cookies, headers, unbounded JSON — turning an integrity table
   into a response cache with a privacy surface, and putting a heavy column on the claim path that
   master `# 20.5` explicitly says must not be read there.
3. **Is one table enough for everything called "idempotency"?** The platform has five distinct
   duplicate-protection mechanisms with five different lifetimes and owners. Collapsing them is the
   single most attractive simplification available here, and it would break all of them: it would
   make `EventId` a command key (contradicting ADR-0009 and ADR-0013), give a permanent business
   invariant a retention-limited home, and make a provider's key a substitute for local truth.

Alternatives considered and rejected: a Redis-TTL or Redis-lock claim (rejected — master `# 5`
principle 3 and `# 5.2` make PostgreSQL the truth, and a cache flush must not be able to create a
second commercial operation); a globally unique key across all scopes (rejected — it makes two
unrelated use cases collide on a caller-chosen value and turns key uniqueness into cross-scope
coupling); an unscoped replay keyed on the key alone (rejected by ADR-0007 §2 already — it turns an
idempotency key into an object-access token); a durable `failed` record for every rejected attempt
(rejected — see §6).

## Decision

**Command idempotency is durable PostgreSQL state, identified by `(scope, key)`, bound to the
claiming principal and to a semantic request fingerprint, and committed atomically with the effect
it protects.**

### 1. What this mechanism is, and the four neighbours it does not replace

`IdempotencyKey` protects **one invocation of one semantic command** — a user-facing or
internally-invoked write use case — from executing its commercial effect more than once. It is one
of five mechanisms, and the separation is frozen:

| Mechanism | Protects | Identity | Owner |
|---|---|---|---|
| **`IdempotencyKey`** | a command invocation | `(scope, key)` | the application module owning the command |
| **Inbox / consumer identity** | an asynchronous message delivery | `event_id` + per-consumer delivery (ADR-0009 §7, ADR-0010) | the consuming module |
| **Provider `external_event_id`** | an inbound provider/webhook delivery | `(provider, external_event_id)` (master `# 5.4`) | the ingesting interface + owning application |
| **Provider idempotency key** | an outbound provider call retry | the provider's own contract | the owning `application/<a>` |
| **Domain `UNIQUE` / state machine** | the business effect itself, permanently | the domain's own constraint | the owning domain |

None of these is derivable from another. In particular: **an `EventId` is never a command
idempotency key**, no event handler is forced through `IdempotencyKey` merely because it is a
handler, and `IdempotencyKey` never becomes the permanent home of a business invariant (§9, §10).
ADR-0009's message-identity and per-consumer effect-idempotency model is used exactly as written and
is **not** amended by this ADR.

### 2. PostgreSQL is the truth; Redis is disposable

The durable PostgreSQL row is the only thing that decides whether a command executes twice, whether
a retry replays, whether a request is a `Conflict`, and who owns a key. Redis may damp bursts and
short-circuit obvious duplicates. **A Redis miss, flush, eviction, outage or cold start changes none
of those four answers** — it can only make the durable path do more work. No Redis lock, TTL key or
in-process mutex may stand in for the claim, and no command may be correct only while Redis is warm.

### 3. The logical key is `(scope, key)`

Durable uniqueness is a database `UNIQUE (scope, key)` constraint, exactly as master `# 5.4`
requires.

**`scope`** is platform-owned: it names **one semantic command/use case**, comes from a bounded,
stable, platform-defined set, and is never taken from client input, a header, a path segment or a
tenant string. `checkout.place_order` and master `# 20.4`'s other names are documentation examples;
this ADR does not enumerate every future scope, and adding one is the owning command's phase.

**`key`** is opaque: caller-supplied or platform-bound according to that command's own contract,
bounded in representation, carrying **no** authorization, **no** timestamp, **no** ordering and
**no** parseable meaning. Two different scopes may legitimately hold the same `key` value; the key
is **not** globally unique and nothing may assume it is.

### 4. Principal binding

A committed row is bound to the principal/context that claimed it, and resolution against a
**committed** row is:

```text
same (scope, key) + same principal + same fingerprint   → replay the committed outcome
same (scope, key) + same principal + other fingerprint  → Conflict
same (scope, key) + different principal                 → NotAllowed  (ownership refusal)
```

A different principal presenting an existing key receives neither the outcome nor confirmation that
the key exists, and the attempt is logged as a security event. **The key is not an object-access
token and its unpredictability is not an authorization mechanism** — this generalises ADR-0007 §2's
rule for every scope.

The durable encoding of the principal is Phase 1 / actor-implementation work: this ADR freezes the
*semantic requirement* (a committed row identifies its claiming principal well enough to make the
three-way decision above deterministically), not a `user_id` column. A genuinely system-owned
command uses a stable system principal/namespace under ADR-0006's actor model and item 4 §11's
explicit system context. **`NULL` never means "anybody"**: an absent or unresolvable principal on a
committed row is a defect, not a wildcard.

### 5. The request fingerprint

Every scope defines a **semantic request fingerprint**: a cryptographic digest (SHA-256 or a
security-equivalent digest — master `# 5.2`'s `request_hash`) over the *canonical semantic command
input*, not over the raw transport payload.

- Deterministic: the same semantically material input always yields the same fingerprint.
- Discriminating: any input whose change would produce a materially different effect yields a
  different fingerprint.
- Canonical: field order, JSON whitespace, key ordering, encoding variations and transport framing
  do not change it; transport noise (headers, cookies, trace ids, timing, client version) is outside
  it unless a scope makes it semantically material.
- Storable without the request: the raw body need not be retained to compare fingerprints later.
- **No secret, credential, token, cookie, CSRF value or authentication material is fed into the
  fingerprint** merely to compute it (§11).

**The field list is per scope, not global.** Each command owner defines its fingerprint material as
part of that command's contract; for `place_order`, item 5 ID3 remains authoritative and still owns
its eventual field list.

### 6. Lifecycle — claim, effect and completion commit together

**Applicability.** For every command scope whose protected durable effect is defined as **one local
ACID transaction** (ADR-0004 §10), the following is frozen. That is the shape `place_order` has
(ADR-0007 §1), and the shape a locally-defined refund transition, a coupon redemption or any other
wholly-local command effect has; each such scope's own phase defines its effect, and this ADR freezes
nothing about them beyond the lifecycle below.

- The idempotency claim is inserted **inside the same transaction as the protected durable effect**.
- The replayable completion becomes durable **at the same instant** as the effect, never before.
- **A rollback leaves no durable claim** and no durable failed reservation. The key is simply unused
  again, and a later request claims it normally under its own fingerprint.
- **No separately committed `processing` row is required, permitted as a correctness device, or
  relied upon by any contender.** A two-transaction pattern (`TX1` commits `processing`; `TX2`
  performs the effect) is forbidden: it contradicts ADR-0007 §1 and reintroduces both failure modes
  that ADR rejected.

**This refines master `# 5.2`'s `state = processing / completed / failed` sketch.** `processing` may
exist only as uncommitted, transaction-local state — the row a transaction has inserted but not yet
committed, which is precisely what serializes contenders in §7. It is not a durable lifecycle stage.
The **generic mechanism therefore requires no durable `failed` state**: a rolled-back attempt —
whether the cause was validation, a business rejection or a technical fault — leaves nothing behind,
so an accidental failure can never reserve a key forever. If a scope retains a state column at all,
its only legal *committed* value is the completed one.

A single narrow exception exists and must be taken deliberately: a specific scope may durably record
a **rejected outcome** only if that command's own contract states the behaviour and the reason it is
required, and only for a rejection the business genuinely wants to be non-retryable with the same
key. It is never the default, never a consequence of an ordinary validation error, and never added
to the generic mechanism.

**A command whose protected effect is not one local ACID transaction is out of scope of this ADR.**
ADR-0015 defines no idempotency protocol for a non-local workflow, and it is not evidence that such
a workflow shape is absent from this architecture — a provider-facing operation is precisely the
shape that is present, and it is already covered by a different, separately frozen layer.

**The local / provider split, stated explicitly.** A provider-facing use case such as payment
initiation has **two** idempotency layers, and they never merge:

```text
LOCAL durable state transition / scheduling decision
    → wholly local and ACID: may be a command scope under this ADR (§6)

PROVIDER network operation (initiate / capture / refund / status query)
    → the provider's own idempotency key, the payment state machine,
      and ambiguous-outcome reconciliation — ADR-0007 §3, ADR-0010, §12 below
```

The provider HTTP call is **never** the durable effect that this ADR claims atomically with an
`IdempotencyKey` row. No database transaction spans a network call (ADR-0007 §3, item 9's
`core.payments` / `ext.payments` split by I/O nature), and no local `IdempotencyKey` makes an
external provider operation transactionally atomic. Any future command that genuinely needs one
command-level idempotency contract spanning multiple commits or an external effect requires its own
architectural decision and ADR; it may not claim compliance with this one.

**Master `# 20.4`'s scope list is illustrative.** `checkout.place_order`, `payment.initialize`,
`refund.create`, `coupon.redeem`, `tradein.redeem` and `digital.fulfillment.allocate` are names, not
proofs of shape: a scope name does not establish that the workflow it labels is a local ACID command,
and it does not override the split above. For **`payment.initialize`** in particular, the payments
phase must identify which precise **local durable** command/effect, if any, is protected by an
`IdempotencyKey` under §6; the provider call it eventually triggers stays separately idempotent under
the provider's contract and converges through webhook and reconciliation. The illustrative name stays
in the master's list and is neither adopted nor rejected here.

### 7. Claim concurrency

Two callers presenting the same `(scope, key)` concurrently: exactly one may execute the protected
effect. The other is serialized on the **durable uniqueness constraint** — not on an application
mutex, not on a Redis lock, not on advisory locking as the correctness device — and resolves once
the winner's transaction settles:

- **winner commits** → the contender applies §4's committed-row rules (replay / `Conflict` /
  `NotAllowed`);
- **winner rolls back** → no row exists durably, and the contender claims the key normally and
  proceeds under its own fingerprint.

A uniqueness race is never allowed to surface as duplicate commerce, and exceeding a bounded
lock/statement timeout while waiting is a **technical** fault, never a fabricated business outcome.
The concrete PostgreSQL savepoint/lock/conflict-handling SQL is Phase 1's.

### 8. Commit ambiguity

If the database `COMMIT` succeeds and the response is then lost — a dead connection, a crashed
process, a vanished client, a bug while building the response — the commercial operation **stands**.
The committed row exists, a retry with the same key by the same principal replays the same logical
result, and **no compensation, reversal or cleanup is attempted merely because the caller did not
receive the response.** This generalises ADR-0007 §1's post-commit rule to every scope and changes
none of it.

### 9. Result replay is a bounded semantic result, not a verbatim transport response

The mechanism durably retains enough **bounded, semantic** information to reconstruct the promised
replay result — typically the result kind, the created resource's `PublicId`, and a bounded status
or result snapshot where a scope's contract needs one. The interface layer reconstructs an
HTTP/HTML/JSON response from that stored semantic result.

- **Not required:** a complete raw HTTP response body for every command. Master `# 5.2`'s
  `response_body_json` is an **optional per-scope result strategy**, not universal truth.
- **Never stored:** cookies, authorization headers, CSRF tokens, credentials, secrets, arbitrary
  request headers, or unbounded response JSON.
- **Never on the claim path:** a heavy result column is not selected while claiming — only when a
  replay actually needs it (master `# 20.5`).
- **Never a leak:** a replay is delivered only to the principal that owns the row (§4).

If the command created an externally addressable resource, the row may retain that resource's
semantic `PublicId`. It never exposes an internal bigint because the table happens to hold one, and
**no generic polymorphic ORM foreign key across domains is created** — master's
`resource_type`/`resource_public_id` is illustrative. What is frozen is the *capability* to replay a
semantic result; the concrete storage shape belongs to Phase 1 and the owning command.

### 10. Retention, and the honesty rule about expiry

- **Every scope has an explicit, bounded, operationally manageable retention policy**, recorded with
  that command's contract.
- Retention covers **at least** the retry/replay window the use case or API promises. The HTTP
  command baseline is master `# 5.2`'s floor of **at least 24 hours**; financial and high-risk
  scopes require longer, owner-defined retention.
- Purge or expiry may happen **only after** the guaranteed replay window has passed.
- **Once a key has legitimately expired, the platform no longer promises replay for it.** Retention
  and the advertised retry guarantee must therefore agree; an API may not promise a retry window
  longer than its scope's retention.
- **No scope may rely on `IdempotencyKey` for eternal uniqueness.** A permanently single-use business
  rule lives in domain state (§11), not in a retention-limited row.

### 11. Idempotency is not business uniqueness

```text
idempotency  ≠  business uniqueness
```

`IdempotencyKey` suppresses duplicate **command execution** within a retention window. A business
rule that must hold forever — a coupon redeemed once, a reservation transitioned once, one refund
per allowed transition, one `DigitalCode` assigned once, one provider event applied once — is
enforced by a domain `UNIQUE` constraint or state machine (master `# 5.4`). **Deleting an expired
`IdempotencyKey` row must never make a permanently single-use business operation legally
repeatable**; after expiry, a re-submitted command re-executes and is refused by the domain
invariant, which is the correct outcome.

### 12. Local command idempotency and provider idempotency are separate layers

A provider idempotency key is **not** automatically the same semantic key as the local command's.
The owning application module (for payments, `application/payments_gateway` under ADR-0005 §2 and
ADR-0007 §3) may derive or reuse a stable identifier — master `# 11.4` step 3's stable provider key /
`PaymentAttempt.public_id` — where the provider contract allows it. But:

- the provider key never replaces the durable PostgreSQL command truth;
- a provider response never decides whether the local `Order` was placed;
- an ambiguous provider outcome is resolved by provider status lookup / reconciliation inside the
  owning workflow's state machine (ADR-0010), never by a blind transport retry and never by
  consulting an `IdempotencyKey` row.

**A provider-facing payment attempt is not evidence that its provider HTTP effect is protected by the
local ACID transaction of §6.** A local `PaymentAttempt` row, a local workflow-state transition and
any local scheduling decision commit locally; the provider call happens strictly **after** that
commit, owned by `application/payments_gateway` (ADR-0007 §3) and routed to `ext.payments` rather
than `core.payments` precisely because it performs provider I/O (ADR-0010). Nothing in this ADR moves
that call inside a transaction, and nothing here lets a local `IdempotencyKey` stand in for the
provider's own idempotency contract.

This ADR redesigns nothing about payments.

### 13. Security and privacy

The key is not authorization; the fingerprint is not authentication. No raw credential, token or
secret enters fingerprint material or stored result material. No unbounded request or response body
is persisted. Logging uses the scope plus a redacted or hashed key where a scope treats key values
as sensitive, and never logs stored result material that would be refused to the requesting
principal. A principal that does not own a key never receives the owner's replay data, and never
learns whether the key exists.

### 14. Out of scope of this ADR

The physical `IdempotencyKey` model, columns, types, indexes, partitioning and migration (Phase 1);
the durable encoding of the principal/actor fingerprint (Phase 1 / the authentication phase); the
concrete canonicalization function and digest library (Phase 1); the exact fingerprint field list of
any scope (each command's own phase — `place_order`'s remains item 5 ID3's); the full scope registry
beyond the illustrative names (each owning phase); numeric retention periods per scope beyond the
24-hour HTTP floor (each owning phase / operations); the purge job's mechanics (Phase 1 /
operations); the concrete claim/contention SQL, savepoints and timeouts (Phase 1); HTTP status
mapping and header names such as `X-Idempotency-Key` (the Web/DRF phases); **which precise local
durable effect, if any, each of master `# 20.4`'s illustrative scope names protects — `payment.initialize`
included (the payments phase, bounded by §6's local/provider split)**; the provider-facing side of any
such workflow, which stays with ADR-0007 §3, ADR-0010 and §12's provider layer; and **any command
whose protected effect is not a single local ACID transaction** — including any command-level
idempotency contract spanning multiple commits or an external effect — which needs its own ADR
rather than an assumed extension of this one.

**This ADR changes no dependency-matrix cell, adds no import edge, extends no `core` submodule
allowlist, adds no event-registry column or consumer-declaration attribute, and edits no accepted
ADR.** L1–L21 stand unedited, and ADR-0007 §2 is generalised, not altered.

## Consequences

**Positive**

- Every command scope inherits one answer instead of re-deriving one: `place_order`'s frozen
  behaviour becomes the platform rule, so `refund.create` and `digital.fulfillment.allocate` cannot
  quietly invent weaker semantics.
- The correctness of a duplicate submission survives a Redis flush, a cold start and a Redis outage,
  because Redis was never load-bearing.
- The `processing`/`failed` trap is closed before any code exists: no transient fault can poison a
  key, and no committed claim can outlive a rolled-back effect.
- An idempotency key cannot be used to read another principal's result — the most likely IDOR shape
  in a retryable commercial API — in any scope, not only checkout.
- The idempotency table stays an integrity mechanism rather than becoming a response cache with a
  privacy surface and a heavy column on the hot path.
- The five duplicate-protection mechanisms stay legible and separately owned, so an event handler is
  not forced through a command table and a permanent business rule is not left to a retention
  window.

**Negative / accepted cost**

- **A rolled-back attempt is forgotten**, so a retry after a business rejection re-executes the
  (failing) work, and a key whose first attempt rolled back may later be claimed with a *different*
  fingerprint. Accepted and deliberate — ADR-0007 §2's reasoning applies to every scope: remembering
  failures poisons keys and requires a claim committed outside the effect's transaction. The
  guarantee that matters survives intact: a **committed** key can never be reused for materially
  different input.
- **Replay is a reconstruction, not a recording.** A caller replaying a command may receive a
  response rebuilt from semantic material rather than the byte-identical original. Accepted: byte
  fidelity would require persisting raw responses, which §9 rejects on privacy and cost grounds, and
  clients contract on semantics.
- **Expiry ends the promise.** After retention, the same key re-executes and is stopped only by the
  domain invariant. Accepted: the alternative is unbounded growth of a hot table, and §11 puts the
  permanent guarantee where it belongs.
- **Every command owner must define fingerprint material and a retention period**, rather than
  inheriting one global list. Accepted: a global field list would either under-cover a scope (silent
  duplicate execution of a materially different request) or over-cover it (spurious `Conflict`s from
  transport noise).
- **A per-scope key namespace** means an operator debugging a key must know its scope. Accepted;
  the alternative couples unrelated use cases on a caller-chosen value.

**Enforcement**

- The behavioural detail, the 20-row failure matrix and the check list are carried by the
  [item 15 artifact](../architecture/phase-0/15-adr-closure.md) §8, §10 and §13.
- **Phase 1** implements the physical `IdempotencyKey` model, its `UNIQUE (scope, key)` constraint
  and its migration; each command's own phase implements that scope's fingerprint and retention.
- **Static checks A129–A138:** PostgreSQL-only claim; the unique constraint present; no Redis or
  in-process lock as the claim mechanism; no idempotency write committed outside the protected
  effect's transaction; no durable `failed`/`processing` value; no raw request/response body,
  credential or header in fingerprint or result storage; no `EventId` used as a command key; no
  unscoped or actor-less replay; no heavy result column on the claim path.
- **Contract tests C177–C190:** the failure matrix rows — sequential retry, concurrent duplicate,
  concurrent different payload, cross-principal refusal, rollback leaving no claim, commit ambiguity,
  Redis flushed between retries, expiry followed by a domain-invariant refusal, and the separation
  from Inbox and provider identity.
- **Review checks V146–V155:** a key treated as an access token, a fingerprint over the raw body, a
  scope taken from client input, a globally unique key assumption, a business invariant left to
  retention, a second duplicate-protection table, and an "idempotency" claim that in fact protects
  nothing durable.
- Any weakening — a separately committed claim, a Redis-only path, an unscoped replay, a universal
  duplicate-protection table, or a durable failed state added to the generic mechanism — requires a
  new ADR superseding this one.
