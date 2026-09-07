# ADR-0007 — `place_order`: one local ACID placement transaction, in-transaction idempotency claim, provider payment strictly post-commit

- **Status:** Accepted — Frozen
- **Date:** 2026-09-04
- **Phase:** 0 — Architecture Freeze
- **Supersedes:** —
- **Related:** [ADR-0004](0004-four-layer-modular-monolith.md),
  [ADR-0005](0005-dependency-and-integration-wiring.md),
  [ADR-0006](0006-public-contract-primitives.md),
  [Phase 0 item 5 artifact](../architecture/phase-0/05-place-order-use-case.md),
  [Phase 0 item 2 artifact](../architecture/phase-0/02-four-layer-architecture.md),
  master `# 3`, `# 5.2`, `# 8.4`, `# 9.2`, `# 11.4`, `# 12.2`, `# 12.7`, `# 20.4`

## Context

ADR-0004 §4 froze that a cross-domain operation has exactly one owner in `application/`, and item 2
named that owner for order placement: `application/checkout/use_cases/place_order.py`. ADR-0004 §10
froze that the use case owns its transaction and that local ACID is not a saga. ADR-0005 froze the
import matrix, the port owners and the composition root. Item 4 froze the contract shape of the
domains that placement calls.

What none of them settles is how the placement itself behaves under concurrency, retry and provider
failure. Three questions are genuinely open, and each is the kind that gets answered by whoever
writes the code first if it is not answered here:

1. **Is placement one transaction or two?** ADR-0004 §10 says a cross-domain use case *may*
   coordinate inside one local `transaction.atomic()`. Master `# 11.4` shows placement as a
   `PREPARE` block followed by a `BEGIN SHORT TX` block, so that the pricing pipeline does not run
   while a popular `InventoryBalance` or `Coupon` row is locked. Read carelessly, those two are in
   tension, and the tension resolves badly by default: a developer who takes "two blocks" literally
   writes a durable write into the preparation phase, and the all-or-nothing guarantee is gone.
2. **What exactly does durable idempotency promise for this operation?** Master `# 5.2` gives the
   `IdempotencyKey` mechanism, the `(scope, key)` unique constraint and a `processing/completed/
   failed` state column. It does not say when the record becomes completed relative to the `Order`
   commit, what happens to the claim when the transaction rolls back, or whether a replay is scoped
   to the principal that created it. Each of those has a plausible-looking wrong answer: claiming
   the key in its own committed transaction (which produces a completed record that can outlive a
   rolled-back order, and a poisoned key after a transient failure), and treating the key as
   sufficient proof of ownership (which turns an idempotency key into an object-access token).
3. **Who performs the provider payment call, and when?** Master `# 11.4` step 3 places initiation
   after the local commit, and `# 12.2`/`# 12.7` make webhook plus reconciliation the mechanism that
   converges payment state. But no artifact says *which module* owns that post-commit step. The
   obvious-looking answer — a post-commit continuation inside `place_order` — collides with two
   frozen rules at once: ADR-0005 §2 makes `application/payments_gateway` the owner of the payment
   provider port, and ADR-0005 §7 forbids application→application imports. Left unstated, the
   collision is discovered at implementation time and resolved with an exception.

The alternatives considered and rejected: a saga/compensation design for placement (rejected —
every participant is a table in the same PostgreSQL, so it would replace a database guarantee with
weaker hand-written code; ADR-0004 §10, item 2 §12.2); a Redis lock or Redis TTL key as duplicate
protection (rejected — master `# 5.2` and `# 11.4` already make PostgreSQL the truth, and a cache
flush must not be able to create a second order); committing the `Order` only after the provider
confirms payment (rejected — it holds a database transaction across a bank call, and the master
freezes the opposite order).

## Decision

### 1. Exactly one durable placement transaction

`application/checkout.place_order` owns **one** outer local `transaction.atomic()`. Every durable
write of the placement — the idempotency claim, the inventory reservation, the promotion redemption,
the `Order` and its `OrderItem` snapshots, the `PaymentAttempt(created)` row, the checkout state
transition and the Outbox records — happens inside it. Either the placement commits as one durable
result, or every local change rolls back. There is no intermediate durable state, and there is no
compensating command.

The read-heavy preparation that master `# 11.4` requires to run before hot row locks is **not a
second transaction**. It performs no durable write of any kind, takes no row lock, and produces only
candidates. Because it writes nothing, it has nothing to roll back and the all-or-nothing guarantee
is unaffected. Re-preparation after a revalidation mismatch is bounded.

What *is* frozen about revalidation is the requirement, not a mechanism: **a prepared fact may never
be used for a durable write after it has become stale.** Every commercially material prepared fact
is revalidated inside the placement transaction **through its owning module, using that owner's
freshness/revalidation guard** — for inventory and for redemption rights, the owner's atomic command
*is* that guard. Checkout does not define, standardise or assume the mechanism: it never reads a
domain's internal version or `updated_at` column, never assumes every owner has a version field, and
introduces no shared global version counter. An owner may later implement its guard as an opaque
revision token, an `updated_at`/revision check, a hash of its authoritative inputs, a minimal
authoritative re-read, a conditional command carrying expected values, or another owner-defined
token.

This neither consumes nor redefines **Phase 0 item 12**, which owns `source_version` generation and
the guarded **storefront projection** upsert — a monotonic read-model concern. That is not a general
OLTP versioning scheme; catalog `Product`/`ProductVariant` gain no storefront `source_version`
state, and nothing in this decision requires them to.

Consequences that follow and are therefore also frozen: an inventory reservation is created in the
same transaction as the `Order`, so an orphan committed reservation from a failed placement is
structurally impossible; and a domain command remains a participant that never commits on its own
behalf (item 4 T2).

**`COMMIT` is also the dividing line for failure semantics.** A technical fault *before* commit — an
`OperationalError`, a programmer error, an unexpected invariant defect, a timeout while the
transaction is still active — rolls everything back: no `Order`, no reservation, no
`PaymentAttempt`, no idempotency record, and a retry with the same key re-executes. A technical
fault *after* a successful commit — a bug while building the result, process death, a transport
failure, a disconnected client — changes nothing durable: the `Order` and every other committed
placement row exist, the committed idempotency outcome exists, the invocation may still fail
technically, and a retry with the same key replays rather than creating a second `Order`. In that
case **no compensation, rollback, cancellation or cleanup of the committed placement is attempted**;
a commercial reversal, if the business wants one, is a separate business operation with its own
owner and state transition, never an error-handling side effect. Neither case is ever converted into
a business outcome.

### 2. Canonical idempotent placement semantics

Placement is idempotent by durable PostgreSQL state under scope `checkout.place_order`. Redis may
damp bursts and must never be the only protection against a duplicate `Order`.

- **The claim and the completed outcome are written inside the placement transaction.** Completion
  therefore becomes visible at exactly the instant the `Order` does. **No idempotency record may
  become "completed" before the `Order` transaction commits.**
- **A rollback rolls the claim back with it.** For this scope an expected business failure is not
  durably remembered; only a *committed* placement is replayable. A retry after a transient
  shortage re-executes rather than replaying a stale failure, and no key can be poisoned by a
  failure.
- **Against an existing COMMITTED record**, and only then: same fingerprint → **replay** the
  committed outcome, referenced by public locator; a materially different fingerprint → a
  **`Conflict`**, never a second operation and never a second `Order`; a different authorized
  principal → **`NotAllowed`**. A committed record binds its key to its committed fingerprint for
  the retention period.
- **When no committed record exists** — before any attempt, or after one that rolled back — there is
  no durable fingerprint to compare against and the key is simply unused: a later request claims it
  normally and proceeds under its own fingerprint, whether or not that fingerprint matches the
  abandoned attempt's. A rolled-back attempt is deliberately not remembered, so no conflict can be
  detected against it. The invariant is therefore precise: **a *committed* key can never be reused
  for materially different input**, and a failed attempt does not reserve a key.
- **A concurrent contender is serialized by the durable uniqueness mechanism**, with no separately
  committed "processing" claim — one would require a second transaction and contradict §1. When the
  first attempt commits, the contender applies the committed-record rules above (replay, `Conflict`
  or `NotAllowed`); when it rolls back, the contender claims the key and proceeds under its own
  fingerprint; exceeding a bounded lock/statement timeout is a *technical* fault, never a fabricated
  business outcome.
- **Replay is scoped to the authorized principal/context.** An idempotency key is not an
  object-access token. Another actor presenting the same key receives neither the order data nor
  confirmation that it exists; the mismatch is refused as `NotAllowed` and logged as a security
  event.

The `IdempotencyKey` schema, retention specifics and the generic idempotency ADR remain out of scope
(Phase 0 item 15). What is frozen here is the behaviour `place_order`'s correctness depends on.

### 3. Provider payment strictly post-commit, and owned by `application/payments_gateway`

`place_order` performs no provider, ERP, CRM, notification or broker I/O, and schedules none
directly — on **no** branch and for **no** payment method. Creating the local
`PaymentAttempt(created)` row through `payments.public` inside the transaction is domain PostgreSQL
work, not external I/O (item 4 T4), and stays where master `# 11.4` puts it.

A successful provider payment is **not** a prerequisite for committing the `Order`:

```text
Order committed locally → payment action initiated after commit → webhook/reconciliation converge
```

The post-commit provider interaction is **a separate application use case owned by
`application/payments_gateway`**, which ADR-0005 §2 already made the owner of the payment provider
port; ADR-0005 §7 forbids `application/checkout` from importing it. It receives its bound port by
injection from the composition root and acts on an already-committed `Order`/`PaymentAttempt`. Two
triggers are legal — an Outbox record dispatched to a `tasks/*` handler, or a second transport entry
point — and both keep one use case per entry point. Which applies per payment method is deferred to
the payments phase; neither can reintroduce provider I/O into `place_order`.

A provider outage after commit never rolls back a committed `Order`; payment state converges through
webhook and reconciliation.

### 4. Checkout application errors use the `core.errors` categories

`application/checkout` may define public errors for orchestration semantics no single domain owns
(an expired checkout, an idempotency conflict, a cross-principal replay attempt), over the same five
`core.errors` categories and under a checkout application root. It does not duplicate or rewrap a
domain's error, and technical faults propagate untranslated (item 4 §13.5). This specifies
ADR-0006 §2's listed `application` consumer; it adds no category and no business vocabulary to
`core`.

### 5. Out of scope of this ADR

`CheckoutSession`/`Order`/`OrderItem`/reservation/`PaymentAttempt`/`IdempotencyKey` schemas; the
`place_order` signature, input DTO and result DTO fields; the request-fingerprint field list; how a
principal is fingerprinted from the `Actor`; the **mechanism** of each owner's freshness/revalidation
guard (each owning domain's own phase) and Phase 0 item 12's storefront `source_version` decision,
which is untouched; event names, schemas and versions (Phase 0 item 8);
delivery and promotion internals; the concrete locking SQL; and the UX policy on whether a price
that changed at placement is auto-accepted or requires user reconfirmation — deferred deliberately,
while authoritative re-pricing at placement is frozen.

**This ADR changes no dependency-matrix cell and no `core` submodule allowlist.** It adds no import
edge that ADR-0005 did not already permit, and removes none. L1–L21 stand unedited.

## Consequences

**Positive**

- Placement atomicity is a database guarantee rather than an application convention: a partially
  committed order/reservation pair is impossible by construction, not by care.
- The apparent conflict between "one local transaction" and the master's `PREPARE`/`SHORT TX`
  structure has one written answer, so the optimization cannot decay into a durable two-phase write.
- Duplicate submissions, double-clicks, HTTP retries and commit ambiguity — a vanished client or a
  technical fault after `COMMIT` — all have one mechanism and one answer, and the answer survives a
  Redis flush.
- Revalidation is expressed as a requirement each owner satisfies its own way, so no domain is
  forced into a version column it does not need and checkout cannot grow a hidden dependency on one.
- An idempotency key cannot be used to read someone else's order — the most likely IDOR shape in a
  checkout API is closed before any code exists.
- The bank is never inside a database transaction, and a provider outage degrades payment state
  without touching commercial state.
- The post-commit payment owner is derived from already-frozen rules, so no "just this once"
  exception to ADR-0005 §7 is needed at implementation time.

**Negative / accepted cost**

- Preparation work can be thrown away and repeated when in-transaction revalidation fails under
  contention. Accepted: the alternative is holding hot locks for the whole pricing pipeline, and the
  retry is bounded.
- A business failure discards the idempotency claim, so a duplicate submission that races a failing
  placement may execute the (failing) work twice, and a key whose first attempt rolled back may
  afterwards be claimed by a request with a *different* fingerprint. Accepted, and deliberate: the
  alternative — remembering failures — poisons keys, makes a retry after a transient shortage
  impossible, and would require committing a claim outside the placement transaction. The guarantee
  that matters is preserved in full: a *committed* key can never be reused for materially different
  input.
- The user does not receive a bank redirect from the same call that places the order; a second step
  (task-dispatched or a second request) is required. Accepted: this is exactly what keeps provider
  latency and provider failure out of the transaction.
- Placement cannot be assembled from a domain, a view or a task, even for a "simple" case; every
  path pays for one application use case. Accepted: a second placement path is a second, divergent
  set of invariants.

**Enforcement**

- The behavioural contract, sequence, lock rank order and failure matrix are carried by the
  [item 5 artifact](../architecture/phase-0/05-place-order-use-case.md).
- Static checks **A24–A28** (no orchestration shape outside `application`, no provider call or task
  dispatch inside `atomic()` in checkout, no manual commit/rollback, no ORM/vendor/transport type on
  the checkout application boundary, no optional actor) and contract tests **C11–C23** (atomicity
  before commit, no orphan reservation, last-unit concurrency, idempotent retry, fingerprint conflict
  from a committed record, no phantom conflict after a rollback, contender behaviour both ways,
  principal-scoped replay, commit ambiguity from a client disconnect **and** from a technical fault
  after commit, socket blocking, post-commit provider outage, technical faults unlaundered on both
  sides of `COMMIT`, projection independence, snapshot immutability, statement/lock budget) are
  implemented by the phases that build checkout — not in Phase 0.
- Review items **V19–V26** cover what a checker cannot see: a second placement path, an application
  reimplementing a domain invariant, a trusted `CheckoutSession` price, provider work smuggled in
  through a signal or `save()` override, saga machinery or a post-commit "cleanup" that reverses a
  committed placement, a key used as an access token, an unbounded retry loop, and checkout reaching
  into a domain's internal version column or assuming a uniform version field.
- Any weakening — a second placement path, provider I/O inside the transaction, Redis-only duplicate
  protection, an unscoped replay, or compensation machinery for the local flow — requires a new ADR
  superseding this one.
