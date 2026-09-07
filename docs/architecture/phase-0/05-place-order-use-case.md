# Phase 0 — Item 5: `application/checkout` ownership and contract of `place_order`

- **Status:** DONE / FROZEN
- **Date:** 2026-09-04
- **Phase:** 0 — Architecture Freeze
- **Related:** [ADR-0004](../../adr/0004-four-layer-modular-monolith.md),
  [ADR-0005](../../adr/0005-dependency-and-integration-wiring.md),
  [ADR-0006](../../adr/0006-public-contract-primitives.md),
  [item 2 artifact](02-four-layer-architecture.md),
  [item 3 artifact](03-dependency-matrix.md),
  [item 4 artifact](04-domain-public-contract.md),
  master `# 3` (cross-domain write-path, synchronous zone), `# 5.1`, `# 5.2`, `# 8.1`, `# 8.3`,
  `# 8.4`, `# 9.2`, `# 11.2`, `# 11.4`, `# 12.1`, `# 12.6`, `# 15.3`, `# 20.4`
- **New ADR:** [ADR-0007](../../adr/0007-place-order-atomic-idempotent-boundary.md). See §1.3.

---

## 1. Purpose

### 1.1 What this item freezes

Item 2 named the owner of order placement (`application/checkout/use_cases/place_order.py`) and
deferred its internal design to this item. Item 3 froze how that module may reach everything it
needs. Item 4 froze the shape of the domain contracts it calls. This item freezes the **use case
itself**, as an architectural contract:

the ownership rule and its negative form; the responsibility split across the participating domains;
the architectural role of `CheckoutSession`; the semantic input contract and its trust rules; the
transaction boundary; the canonical placement sequence with its lock order and concurrency analysis;
inventory-reservation and pricing-snapshot semantics at placement; the durable idempotency
behavioural contract, including its authorization scoping; the result contract; the payment
boundary; the Outbox responsibility; a failure matrix; the error-ownership split; and the checks a
later phase must implement.

### 1.2 What this item does **not** do

It designs no schema and no signature. It does not define `CheckoutSession`'s fields, `Order`'s or
`OrderItem`'s columns, the `IdempotencyKey` table, `PaymentAttempt`, the reservation table, any
domain's `public.py`, the event registry, delivery pricing, promotion internals, or any
serializer/template. Every identifier below is a *role*, not a name.

It creates no Python package, no module, no model, no migration and no test. Phase 0 produces
documents and decisions only (PHASE0_STATUS.md).

Where the master has already decided something (the placement sequence, the `IdempotencyKey`
mechanism, reservation atomicity, the order snapshot, post-commit payment initiation), this artifact
**records and sharpens** it rather than re-deciding it. Where the master leaves room — the ownership
of the post-commit payment step, the actor scoping of an idempotent replay, the status of the
preparation phase relative to the placement transaction, the price-change UX policy — this artifact
either freezes a decision (and ADR-0007 records it) or defers it explicitly (§24).

### 1.3 Why ADR-0007 is required

Most of what follows is specification of decisions ADR-0004 and ADR-0005 already froze — that
`place_order` lives in `application/checkout`, that domains are reached through `public.py`, that
the application owns the transaction, that a domain performs no vendor I/O. Those need no ADR.

Three decisions are not of that kind, and each matches a trigger in the ADR README:

1. **One local ACID placement transaction, and the status of the preparation phase.** ADR-0004 §10
   says a cross-domain use case *may* coordinate inside one local `transaction.atomic()`. Master
   `# 11.4` shows a two-block `PREPARE` / `SHORT TX` structure. Read carelessly, those two are in
   tension. §7 resolves it: exactly **one** durable write transaction, preceded by a read-only
   preparation phase that writes nothing and holds no lock. That is a consistency rule, and freezing
   it is an ADR-level act.
2. **Canonical idempotent placement semantics.** Master `# 5.2` gives the mechanism and the schema;
   it does not decide when the record becomes completed relative to the Order commit, what happens
   to the claim on rollback, or that a replay is scoped to the same principal. §11 and §12 decide
   those. Actor-scoped replay is an identity/authorization rule.
3. **Provider payment strictly post-commit, and not owned by `place_order`.** ADR-0005 §2 froze
   `application/payments_gateway` as the owner of the payment provider port, and ADR-0005 §7 forbids
   application→application imports. Together those two make the post-commit provider step
   **someone else's use case** — an ownership assignment that exists nowhere yet. §14 makes it
   explicit.

They are therefore decided in
**[ADR-0007 — `place_order`: one local ACID placement transaction, in-transaction idempotency claim,
provider payment strictly post-commit](../../adr/0007-place-order-atomic-idempotent-boundary.md)**.

ADR-0007 changes **no** dependency-matrix cell and **no** `core` submodule allowlist. It adds no
import edge that item 3 did not already permit. §22 records that explicitly.

---

## 2. Frozen principles inherited from ADR-0004 / ADR-0005 / ADR-0006 / items 2–4

| # | Principle | Source |
|---|---|---|
| R1 | Any operation touching two or more domains has exactly one owner in `application/`. | ADR-0004 §4 |
| R2 | Order placement is frozen to `application/checkout/use_cases/place_order.py`. | item 2 §13 Q4, master `# 3`, `# 11.4` |
| R3 | `application` orchestrates domains exclusively through `<domain>.public`; a missing capability becomes a new public symbol, never an internal import. | item 3 §4.3, §11.1 |
| R4 | Domains are mutually invisible; no domain imports another to implement checkout. | ADR-0004 §3 |
| R5 | The application use case owns the transaction of a cross-domain operation; interfaces and tasks own none; a domain command never commits independently. | ADR-0004 §10, item 4 T2/T6 |
| R6 | Local ACID is not a saga. No compensation machinery for a flow whose participants are tables in one PostgreSQL. | ADR-0004 §10, item 2 §12.2 |
| R7 | No external/vendor network I/O inside a domain command, and none inside the critical transaction. | item 4 T4, master `# 3` synchronous zone |
| R8 | `CheckoutSession` is application-owned state; its object-level authorization belongs to `application/checkout`. | ADR-0004 §6, item 2 §11 |
| R9 | Durable idempotency is PostgreSQL (`IdempotencyKey`/Inbox); Redis is an optional anti-storm layer, never the truth. | master `# 5.2`, `# 20.4` |
| R10 | Money is `Money`/minor units; public locators are `PublicId`/UUIDv7; internal bigint PKs never become external locators. | master `# 5.1`, `# 5.3`, item 4 §8 |
| R11 | Every outbound vendor port lives at `application/<a>/ports.py`; `application/payments_gateway` owns the payment provider port; application→application imports are forbidden. | ADR-0005 §2, §7 |
| R12 | Expected domain failures are domain-owned errors over the five `core.errors` categories; technical faults propagate untranslated. | item 4 §13, ADR-0006 §2 |
| R13 | `PriceProjection` and `ProductListingProjection` are read models, never checkout truth. | ADR-0003, master `# 8.2`, `# 8.4` |

Nothing below weakens any of these.

---

## 3. Ownership

### 3.1 The frozen rule

```text
application/checkout
    owns place_order
```

`place_order` is the **only** owner of the operation that turns a validated checkout intent into a
durable `Order`. It is cross-domain orchestration: it decides *in what order* capabilities are
invoked; it decides no domain's rules.

### 3.2 The negative form

| Candidate home | Verdict | Why |
|---|---|---|
| `domains/orders` | **Forbidden** | `place_order` is not `orders`' merely because an `Order` comes out of it (item 2 §6). It would need `inventory`, `pricing` and `payments` — a domain→domain edge (R4). |
| `domains/inventory` / `domains/pricing` / `domains/payments` | **Forbidden** | Same reason, with an even weaker claim to ownership. |
| an interface (view, DRF action, admin action) | **Forbidden** | Interfaces call one use case or one domain contract and own no business rule (ADR-0004 §5). |
| a Celery task body | **Forbidden** | Tasks are transport; a task body reaching two domains is a static failure (ADR-0005 §5). |
| `core` | **Forbidden** | Fails every `core` admission test: it is pure business policy over named domains (ADR-0004 §2). |
| an integration adapter | **Forbidden** | Adapters own no domain truth and decide no business policy (ADR-0004 §8). |
| a second `application` module | **Forbidden** | One owner, or the rule means nothing (R1). Another application module wanting to place an order calls the same transport-level entry, or the owners merge (ADR-0005 §7). |

### 3.3 Entry

```text
interfaces/web  ─┐
                 ├─→ application/checkout.public.place_order(actor, ...)
interfaces/api  ─┘
```

The interface parses transport input, authenticates, constructs the actor, calls **one** use case,
and renders the returned DTO. It performs no ownership-field comparison, computes no total, and
combines no two domains' results (item 4 Z6, A4/V10).

A `tasks/*` handler may in principle call the same use case, but **no task reproduces the
orchestration**: a task that sequenced pricing, inventory and orders itself would be a second,
divergent owner and a static failure.

### 3.4 What "one owner" means for reuse

There is exactly one placement path. A backoffice-created order, a retried placement, a future
telephone-order flow and an API placement all enter through `place_order` with the appropriate
actor (including an explicit system context, item 4 Z3). "A slightly different placement for case
X" is a parameter of this use case or a new use case that *calls no second placement path* — never a
copy.

---

## 4. Domain responsibilities

Responsibility is frozen; method names are not. Each row is reached through that domain's
`public.py` and returns frozen DTOs (item 4 §5–§7).

| Domain | Owns (authoritative) | `place_order` must **not** |
|---|---|---|
| **pricing** | Authoritative sell price computation from OLTP sources; the discounts and promotion effects pricing owns; currency; pricing invariants and rounding; the structured result in minor units with the list of applied rules (master `# 8.4`). | Trust a client-supplied price, discount or total; recompute a price itself; read `PriceProjection` as placement truth (R13). |
| **inventory** | Availability semantics; reservation creation and every state transition; quantity/state invariants; the atomic, DB-enforced protection against concurrent depletion (master `# 9.2`). | Touch balance or reservation rows with ad-hoc ORM; perform check-then-write outside inventory; infer availability from a projection. |
| **orders** | The `Order` aggregate and its state machine; `OrderItem` creation semantics; the immutable commercial snapshot; order number / business identity; order-state invariants. | Create order rows directly; assemble an `Order` from ORM objects; assign the order number itself. |
| **catalog** | Stable product/SKU facts required by the workflow — that the SKU exists, is sellable, and the display facts the snapshot needs (ADR-0001, ADR-0003). | Expect price or stock from catalog; both are explicitly outside its boundary. |
| **promotions** | Where promotion/coupon behaviour crosses the pricing boundary, the redemption right and its atomic consumption under its own constraints (master `# 8.1`). | Design promotion internals here; decide redemption eligibility in checkout; mark a coupon used outside its owner's command. |
| **delivery** | Any domain rule about the chosen delivery method / store / zone, and the authoritative delivery amount where such a rule exists (master `# 15.3`). | Invent routing or tariff logic; compare a free-shipping threshold against anything but the final discounted total in the same currency and minor units. |
| **payments** | `PaymentAttempt` and the payment state machine; amount/currency matching; the interpretation of an authenticated, normalized provider event (master `# 12.1`–`# 12.3`). | Call maib/MIA/any provider HTTP — never, transaction or not (§14). |

Two domains not in the placement path deserve naming: `accounts` supplies no authorization decision
to checkout beyond the actor itself (item 4 Z7), and `storefront` is an application read model, not a
domain, and is never consulted at placement.

Whether a given participant is called at all in the MVP (`trade-in`, loyalty) is a scope question
for the implementing phase; the ownership rule does not change if the list grows.

---

## 5. `CheckoutSession` — architectural role only

`CheckoutSession` is **application-owned state under `application/checkout`** (item 2 §11, ADR-0004
§6). Frozen role:

| # | Rule |
|---|---|
| CS1 | It holds workflow/input state accumulated before final placement: contact snapshot inputs, delivery selection, payment-method selection, the displayed pricing snapshot, expiry and status (master `# 11.2` lists these as roles, not as a frozen schema). |
| CS2 | It is **not** `Order` truth. An `Order` is a separate entity created by `orders`; a `CheckoutSession` never becomes one. |
| CS3 | It is **not** price truth. Its pricing snapshot is a *display* record of what the user was shown, and is never the basis of a committed line (master `# 11.4.1`: the cached snapshot is not trusted). |
| CS4 | It is **not** inventory truth. A quantity it records is a request, not a guarantee; only a reservation held by `inventory` is a guarantee. |
| CS5 | It is not a substitute for domain-owned validation. Every commercially material fact it carries is revalidated against its owning domain at placement time. |
| CS6 | Access is actor-scoped through `application/checkout`'s own policy and selector; `public_id` is a locator, never an authorization (master `# 11.2`). For a guest, the additional proof is the current guest session or a signed purpose-bound token — never the `public_id` alone. |
| CS7 | Its schema, step model and full state machine are **not** designed here (§24). §18 freezes only the placement-concurrency semantics. |

The single governing sentence: **`place_order` revalidates authoritative domain facts at placement
time, and never treats a value as authoritative merely because a `CheckoutSession` previously
displayed it.**

---

## 6. Input contract

### 6.1 Semantic shape

Frozen as *information the input must be able to carry*, not as fields:

| # | Element | Note |
|---|---|---|
| IN1 | The **actor** — an explicit, mandatory, non-optional authorization subject, or an explicit system context. First parameter (item 4 Z1–Z4). | Never `None`, never a raw `user_id` from the request. |
| IN2 | The **workflow locator** — the checkout session (or equivalent) the placement acts on, as a `PublicId`. | Resolved through the actor-scoped selector, never an unscoped `.get()`. |
| IN3 | The **intended line items** — SKU identity and quantity. | Requested input; see §6.2. |
| IN4 | The **delivery choice** — method and, where applicable, store/zone/address selection. | Validated by its owner. |
| IN5 | The **payment-method choice**, where relevant. | Method/provider selection only — never an amount (master `# 11.4` step 3). |
| IN6 | **Customer/order-contact snapshot inputs**, where applicable (guest checkout). | Normalized server-side; an email match never auto-links an account (master `# 11.3`). |
| IN7 | The **durable idempotency identity and context** — the key plus what is needed to compute the request fingerprint (§11). | Mandatory; `place_order` has no non-idempotent form. |

Structured input is a frozen input DTO (item 4 §9.2), carries no transport object, and crosses the
application boundary with the same no-ORM/no-vendor/no-transport rules as a domain contract (§19).

### 6.2 The trust rule

> **Client- and session-supplied values are REQUESTED INPUT. They are never authoritative
> commercial truth.**

Never accepted as authoritative from a client or from a cached workflow snapshot:

| Value | Authority |
|---|---|
| final unit price, discount amount, line total, order total | `pricing` (with `delivery` for the delivery amount), recomputed at placement |
| stock availability | `inventory`, decided by the atomic reservation, not by a prior read |
| reservation success | `inventory`'s command result |
| payment success | `payments`, driven by webhook + reconciliation — never by a client, a return URL or a redirect (master `# 12.6`) |
| coupon validity / redemption right | `promotions` / `pricing`, consumed atomically under its own constraint |
| sellability of a SKU | `catalog` |
| an authorization decision (`is_owner`, `allowed`) | the module owning the state; never passed in (item 4 Z7) |

The requested line items (IN3) are **compared against**, never merged into, the server-side workflow
state. If the request's material terms and the server-side state disagree, that is a placement
conflict surfaced to the caller — never a silent overwrite in either direction.

---

## 7. Transaction boundary

### 7.1 The frozen rule

> **`application/checkout.place_order` owns exactly ONE outer local PostgreSQL
> `transaction.atomic()`, and every durable write of the placement happens inside it.**
>
> Either the placement transaction commits as one durable result, or every local change rolls back.
> There is no intermediate durable state.

Inside it, `place_order` coordinates domain public commands and selectors. Each domain command is a
composable participant (item 4 §12): it may open its own `atomic()`, which becomes a savepoint; it
never commits, never rolls back the outer block, never uses `durable=True`.

This is a **local transaction, not a saga** (R6). No compensating command, no orchestration state
table, no outbox-driven rollback path exists for the placement itself. Introducing any of them is an
architecture change requiring a new ADR.

### 7.2 The preparation phase — read-only, and not a second transaction

Master `# 11.4` requires the pricing pipeline and other read-heavy work to run **before** hot row
locks are taken, so that a popular `InventoryBalance` or `Coupon` row is held for tens of
milliseconds rather than for the whole pipeline.

Frozen reconciliation with §7.1:

| # | Rule |
|---|---|
| TX1 | The preparation phase performs **no durable write of any kind** — no order, no reservation, no redemption, no idempotency claim, no counter, no audit row. It reads and computes. |
| TX2 | It takes **no** row lock and holds no lock across its own duration. |
| TX3 | Every commercially material prepared fact is **revalidated inside the placement transaction through its owning module, using that owner's freshness/concurrency contract**, before it is used to write. Preparation output is a *candidate*, never a decision. The frozen requirement is the outcome — **prepared data may never be used for a durable write after becoming stale** — not any particular mechanism (§7.4). |
| TX4 | Because of TX1, preparation has nothing to roll back, and §7.1's all-or-nothing guarantee is unaffected by it. It is not a second phase of a two-phase commit and creates no intermediate durable state. |
| TX5 | If in-transaction revalidation fails, the transaction rolls back and preparation may be repeated a **bounded** number of times. An unbounded retry loop under contention is a defect, not a design. |
| TX6 | Preparation is an optimization of *when* work happens, never of *whether* it is validated. Skipping the in-transaction revalidation to "save a query" is forbidden. |

### 7.3 What is forbidden inside the transaction

No provider HTTP, no ERP, no CRM, no email/SMS, no broker publish, no long computation while hot
rows are locked, no unbounded external wait. §14 states the payment case in full; §21 states the
locking discipline.

### 7.4 Revalidation is owner-defined — the freshness guard

> **Frozen requirement:** a prepared fact may never be used for a durable write after it has become
> stale. **Deferred:** the mechanism by which each owner proves freshness.

`place_order` revalidates through the owning module's public contract and its **freshness /
revalidation guard** (equivalently, an owner-defined concurrency/freshness token). It does not
define, assume or standardise that guard.

| Prepared fact | Where its freshness is decided |
|---|---|
| `CheckoutSession` state | `application/checkout` itself, by lock/reload plus conditional state validation at C2 |
| inventory availability | decided **authoritatively at C4** by `inventory`'s atomic reservation command — the command *is* the concurrency gate; nothing prepared about stock is ever trusted |
| coupon / promotion / trade-in redemption right | decided **authoritatively at C5** by its owner's atomic command, under that owner's own constraint |
| prepared catalog / pricing / delivery facts | the owning domain's public contract must offer enough provenance, or a revalidation capability, to prove that the prepared result is still valid before it is committed |

An owner may later implement its guard as an opaque revision token, an `updated_at`/revision check, a
hash of its authoritative inputs, a minimal authoritative re-read, a conditional command carrying
expected values, or another owner-defined concurrency token. **Item 5 does not choose**, and a
freshness guard is not required to be a stored column at all.

Negative rules for checkout:

| # | Rule |
|---|---|
| FG1 | `place_order` never imports or reads a domain's internal version/`updated_at` column; a guard crosses only as part of that domain's public contract (R3). |
| FG2 | `place_order` must not assume that every domain has a version field, or that any two owners express freshness the same way. |
| FG3 | No shared, global or cross-domain version counter is introduced. |
| FG4 | Where an owner's authoritative command already decides the fact atomically (inventory, redemptions), that command is the guard; adding a separate pre-check would reintroduce check-then-write (LK1). |

**This does not consume, extend or redefine Phase 0 item 12.** Item 12 owns `source_version`
generation and the guarded **storefront projection** upsert — a monotonic read-model concern
(master `# 7.6`, ADR-0003). It is not a general OLTP versioning scheme, catalog `Product`/
`ProductVariant` gain no storefront `source_version` state, and nothing in this artifact requires
them to.

---

## 8. Canonical placement sequence

### 8.1 The frozen sequence

```text
PREPARE — read-only, no locks, no durable writes (§7.2)
  P1  authenticate/authorize is already done by the interface; resolve the actor-scoped
      CheckoutSession through application/checkout's own policy + selector
  P2  normalize the request and compute the idempotency request fingerprint
  P3  fast-path (optional, non-authoritative): if a completed placement already exists for
      this idempotency identity, replay it (§11.5) and stop — subject to the same principal
      scoping as any replay (§12); the authoritative duplicate check is still C1 below, and
      omitting this fast-path changes no outcome
  P4  load and validate authoritative SKU/catalog facts through catalog.public
  P5  compute authoritative pricing through pricing.public (items), then the authoritative
      delivery amount through delivery.public, then the order total — in that order, because
      a free-shipping threshold compares against the final discounted total (master # 15.3)
  P6  validate non-locking business rules: delivery choice, contact snapshot, payment-method
      eligibility, checkout status/expiry
  P7  build the immutable OrderItem commercial snapshot payloads (§10)

BEGIN — one transaction.atomic() (§7.1); lock rank order per §21.2
  C1  claim the durable IdempotencyKey — the authoritative duplicate protection (§11)
  C2  lock and reload the CheckoutSession row; re-check status/expiry/ownership
  C3  revalidate every commercially material fact P4–P7 produced, through its owning module
      and that owner's freshness/revalidation guard (§7.4); on mismatch → rollback,
      bounded re-preparation (TX5)
  C4  create the inventory reservation atomically through inventory.public (§9)
  C5  consume coupon / promotion / trade-in redemption rights atomically through their owners
  C6  create the Order and its immutable OrderItem snapshots through orders.public (§10)
  C7  associate reservation ↔ Order as the domain contracts require (§9.4)
  C8  create PaymentAttempt(created) through payments.public — local row only, no provider I/O
  C9  transition the CheckoutSession to its terminal placement state (§18)
  C10 write the Outbox record(s) for the placement, in this transaction (§15)
  C11 record the completed idempotency outcome — visible only at commit (§11.4)
COMMIT

AFTER COMMIT — never inside the transaction
  X1  provider/payment interaction, owned by application/payments_gateway (§14)
  X2  ERP/CRM/notification work, driven by the Outbox relay (§15)
```

### 8.2 Where this refines the drafted ordering

The sequence sketched in the task brief is preserved in substance, with three deliberate
refinements, each forced by a frozen invariant:

1. **Catalog validation and pricing (P4, P5) move into the read-only preparation phase and are
   revalidated in-transaction (C3)** through each owner's freshness guard (§7.4), rather than
   executing between hot locks. Forced by master `# 11.4`'s lock-duration requirement; safe because
   of TX1/TX3.
2. **Delivery pricing is sequenced after item pricing, not merely "validated"** — the free-shipping
   threshold is defined against the final discounted total (master `# 15.3`), so the reverse order
   would compute a wrong delivery amount.
3. **`PaymentAttempt(created)` is created inside the transaction (C8)**, because master `# 11.4`
   step 2 explicitly places it there. This is a local row insert, not a provider call, so R7 is
   intact. Only the *provider interaction* is post-commit.

The brief's ordering of reservation before order creation is preserved: it is also the master's, and
it is what allows the reservation to be the concurrency gate before any order identity exists.

### 8.3 Concurrency analysis

| Scenario | Why this sequence is safe |
|---|---|
| **Concurrent stock depletion** — two placements for the last unit | C4 is a single conditional `UPDATE` owned by `inventory` whose `WHERE` clause carries the availability predicate (master `# 9.2`). The loser's `rowcount` is 0 and it receives a domain conflict; no read-then-decrement window exists. Both placements may have passed P4–P7 with identical optimistic conclusions — that is exactly why availability is decided only at C4. |
| **Duplicate HTTP retry** (client retries after a timeout) | C1 claims `(scope, key)` under a unique constraint. If the first attempt committed, the second's claim fails and the outcome is a replay (§11.5) — never a second Order. |
| **Duplicate double-click** (two concurrent requests, same key) | Both reach C1; the unique constraint serializes them. The contender waits for the winner's commit or rollback: on commit it applies ID4 against the now-committed record (replay / `Conflict` / `NotAllowed`), on rollback it claims the key itself and proceeds (§11.6). Without a key, §18's checkout-state transition (C9) is the second gate: one logical checkout cannot produce two orders. |
| **Failure after reservation, before order creation** | Both are inside one transaction; the rollback removes the reservation row *and* the balance increment together. An orphan committed reservation caused by a failed placement is structurally impossible, not merely unlikely. |
| **Failure after order creation, before commit** | Nothing is durable. No Order, no reservation, no redemption, no idempotency claim, no Outbox row. |
| **Ambiguous client timeout after commit** | The Order, the reservation, the redemption, the `PaymentAttempt`, the Outbox rows and the completed idempotency record all became visible at the same instant. A retry with the same key replays that outcome (§11.7). |
| **Two placements against the same checkout without an idempotency key collision** | C2's row lock plus C9's conditional state transition make the second attempt observe a terminal checkout and fail; the placement state transition is atomic with the Order (§18). |

---

## 9. Inventory reservation semantics

| # | Rule |
|---|---|
| INV1 | A reservation is created and transitioned **only** by `inventory.public`. `place_order` calls a command and reads its result. |
| INV2 | The operation is concurrency-safe and database-enforced: a conditional atomic update guarded by DB constraints (master `# 9.2`, `# 5.4`). `place_order` performs no check-then-write, no ad-hoc decrement, and no read-then-reserve across statements. |
| INV3 | Availability is never inferred from `ProductListingProjection`, `PriceProjection`, a cached badge, or an earlier selector call. Only the reservation command's result is a guarantee (R13). |
| INV4 | The reservation participates in the **same local transaction** as the `Order` at launch. There is no independently committed reservation and therefore no compensation path. |
| INV5 | If the reservation fails for lack of stock, `place_order` aborts: the transaction rolls back and the caller receives a stable, non-technical placement outcome owned by the failing domain (§20). No partial Order commits. |
| INV6 | The reservation state at placement, and whether a given payment method commits it at placement or later, is decided by the reservation state machine's owner (master `# 9.2`, `# 11.4` step 4). Whatever the answer, any commit is exactly **one** atomic transition, applied once, from an allowed predecessor state. |
| INV7 | The placement guarantee is: **at commit, the ordered quantities are durably reserved** — not merely "were available a moment ago". |
| INV8 | Table constraints, index shapes and the reservation SQL are **not** designed here; the inventory phase owns them. |

### 9.4 Reservation ↔ Order association

The association is made inside the same transaction (C7), through the contracts of the owning
domains. `place_order` does not write a foreign key itself, and does not assume the direction of the
association: master `# 9.2` models `InventoryReservation` as pointing at `CheckoutSession` with a
nullable `Order` reference, and the exact linkage is the inventory/orders phases' to finalize.

---

## 10. Pricing and the immutable snapshot

| # | Rule |
|---|---|
| PR1 | Before `Order` creation, `place_order` obtains authoritative pricing from `pricing.public`, computed from OLTP sources (master `# 8.4`). |
| PR2 | `PriceProjection` and `ProductListingProjection` are storefront read models. **The storefront projection is never authoritative for checkout pricing** (ADR-0003, master `# 8.2`). |
| PR3 | `Order` creation receives a **complete commercial snapshot** sufficient for historical truth. Conceptually it carries: SKU identity; the product/SKU display facts history requires; quantity; unit price; the discount components or summary the business requires; line total; currency; and the tax/legal amounts where applicable (master `# 8.3`). |
| PR4 | The snapshot's exact DTO fields are **not** frozen here (§24). Its *sufficiency* is: a committed order must be reconstructible and legally presentable without reading any current catalog, pricing or promotion row. |
| PR5 | **After an `Order` is committed, later catalog/pricing/promotion changes never rewrite its commercial snapshot.** A correction is a new business event (an amendment, a refund, a new order), never an in-place edit of the snapshot. |
| PR6 | All money crossing this boundary is `Money`/minor units; `Decimal` appears only for rates and rendering, `float` never (master `# 5.3`, `# 15.3`). |
| PR7 | Redemption of a coupon or other limited right is atomic and lives in the same transaction, so a rolled-back order also rolls back the redemption (master `# 8.1`). |

---

## 11. Idempotency — behavioural contract

### 11.1 Mandatory and durable

`place_order` has no non-idempotent form. Durable idempotency in PostgreSQL is mandatory
(master `# 5.2`, `# 20.4`, scope `checkout.place_order`).

> **Redis must never be the only protection against duplicate `Order` creation.** A Redis layer is
> permitted purely as a burst damper; flushing it changes no outcome (master `# 11.4`).

### 11.2 Ownership

| Question | Answer |
|---|---|
| Who owns the **mechanism**? | `core` — the idempotency infrastructure is `core`-owned mechanism, not policy (item 2 §5, `core.idempotency`), and `interfaces/*` may not import it (item 3 L13). |
| Who owns the **semantics** for this operation? | `application/checkout`. It chooses the scope, defines what the request fingerprint covers, decides what the stored outcome is, and decides what a replay returns. |
| Who claims the record? | `application/checkout.place_order`, through the `core` mechanism, inside its own placement transaction. |
| Who may *not* own it? | An interface (it may transport the key, never claim it); a task; a domain (a domain command is a participant, and T7 keeps durable idempotency below the transport boundary). |

### 11.3 Identity, scope and fingerprint

| # | Rule |
|---|---|
| ID1 | The idempotency identity is `(scope, key)` under a database unique constraint, with `scope = "checkout.place_order"` (master `# 5.2`, `# 20.4`). |
| ID2 | The key is client-supplied or pre-bound to the checkout session, and is an opaque UUID/strictly bounded string. It is **not** a locator and grants no access to anything (§12). |
| ID3 | A **request fingerprint** covers the commercially material terms of the request — the workflow locator, the line set and quantities, the delivery choice, the payment-method choice, applied coupon codes and the contact snapshot inputs. Rule of admission: *anything whose change would produce a materially different `Order` is inside the fingerprint*; transport noise (headers, trace ids, timing) is outside it. The exact field list is the checkout phase's (§24). |
| ID4 | **Against an existing COMMITTED record** for `(scope, key)`: same fingerprint → **replay** the committed outcome (§11.5); different fingerprint → **`Conflict`** (never a second operation, never a second `Order`); different authorized principal → **`NotAllowed`** (§12). The committed record binds that key to its committed fingerprint for the whole retention period. |
| ID5 | **When no committed record exists**, there is no durable fingerprint to compare against, and the key is simply unused: a request may claim it normally and proceeds under **its own** fingerprint. This is the case both before any attempt and after an attempt that rolled back (§11.7) — for this scope the system deliberately remembers no failed attempt, so a rolled-back attempt leaves nothing that a later different fingerprint could be detected against. |
| ID6 | Consequently the invariant is stated precisely: **a *committed* key can never be reused for materially different input.** A failed or rolled-back attempt does not reserve the key. |
| ID7 | The retention of a committed record is at least the master's floor for HTTP commands, longer for financial scopes (master `# 5.2`); the schema, columns and indexes are **deferred** to the generic idempotency item/ADR (§24). |

### 11.4 The completion rule

> **An idempotency record must not become "completed" before the `Order` transaction commits.**

Frozen mechanism: the claim (C1) and the completed outcome (C11) are written **inside the placement
transaction**, so completion becomes visible to any other session at exactly the instant the `Order`
does — atomically, by the database, with no window in which a completed record refers to an order
that does not exist (master `# 5.2`: the claim happens in the same transaction as the domain
entity).

The durable completed outcome references the created resource by its **public locator** — the
`Order`'s `PublicId` (and where relevant the `PaymentAttempt`'s) — plus whatever minimal replay
payload the checkout phase defines. It never stores an ORM object, an internal PK as a locator, a
provider payload, or PII beyond what the result contract already exposes (item 4 X3, master `# 21`).

### 11.5 Replay

A retry matching ID4's replay case returns the same outcome the original placement produced, re-derived from or
referenced through the committed `Order` — not a second placement, not a second reservation, not a
second redemption, not a second `PaymentAttempt`, and not a re-run of the pricing pipeline as a
commercial act.

### 11.6 An in-progress duplicate

A concurrent contender with the same identity waits on the durable uniqueness mechanism at C1 until
the first attempt resolves. There is **no separately committed "processing" claim** — inventing one
would require a second transaction and would contradict §7.1.

- the first **commits** → the contender's claim fails against a now-committed record; it rolls back
  its own (still empty) work and applies ID4 to that record: replay, `Conflict` or `NotAllowed`
  according to its own fingerprint and principal;
- the first **rolls back** → no record exists (ID5); the contender's claim succeeds and it proceeds
  normally, under its own fingerprint, whether or not that fingerprint matches the abandoned
  attempt's;
- the bounded wait is exceeded (statement/lock timeout) → a **technical fault** propagates
  untranslated (item 4 §13.5). It is not reported as a business outcome, and a retry with the same
  key remains safe.

### 11.7 Rollback and timeout behaviour

| Situation | Frozen behaviour |
|---|---|
| The placement transaction rolls back for any reason (business failure, technical failure, revalidation mismatch) | The claim rolls back with it. Nothing durable remains — no record, and therefore no retained fingerprint. The key is **unused again** and a later request may claim it normally, under its own fingerprint (ID5). |
| An expected business failure (no stock, invalid coupon, expired checkout) | Same as above: for `checkout.place_order` a failure is **not** durably remembered. Only a *committed* placement is replayable, and only a committed record can produce a fingerprint `Conflict`. This is deliberate — it lets a retry after a transient shortage succeed rather than replaying a stale failure, and it removes the "poisoned key" failure mode. Scopes whose failure must survive across transactions (for example provider initiation) are a different scope's concern. |
| The commit succeeded but the caller never received the result — client disconnect, client timeout, a bug while building the result, or a process/technical failure immediately after `COMMIT` | The `Order` and every other committed placement row exist, and so does the committed idempotency outcome. The current invocation may still fail technically; **no compensation and no rollback is attempted** (§16.2). A retry with the same key and the same fingerprint replays the committed outcome (§11.5); a second `Order` is impossible because the unique constraint is already satisfied. |
| The caller times out before commit | Either the transaction had already rolled back (nothing exists, key unused) or it commits without a listener (the `Order` exists and is replayable). Both are safe; the caller resolves the ambiguity by retrying with the same key. |

---

## 12. Idempotency and authorization

> **An idempotency key is not an object-access token.**

| # | Rule |
|---|---|
| AU1 | The authorized principal/context is part of the idempotency identity — either as a scoping component of the record or as a mandatory authorization check performed on every replay. Master `# 5.2`'s `actor_fingerprint` is the mechanism's hook for this. |
| AU2 | A replay is served **only** to the same authorized principal/context that created the record. Another actor presenting the same key never receives somebody else's `Order`, in whole or in part — including its `PublicId`, its totals, or the fact that it exists. |
| AU3 | A principal mismatch **against a committed record** is refused as a `NotAllowed`-category outcome owned by `application/checkout`. It is not a replay, and it is not silently converted into a fresh placement (which the unique constraint would refuse anyway). Where no committed record exists the question does not arise: the key is unused, and the requesting principal simply claims it for its own placement (ID5). |
| AU4 | The replayed result is additionally constrained by the ordinary actor-scoped read path: `place_order` never returns order data the requesting actor could not read through `orders`' own actor-scoped contract. |
| AU5 | A guest principal is scoped by the same rules that protect the `CheckoutSession` itself (CS6): the current guest session or a signed purpose-bound token, never a bare `public_id` or a bare key. |
| AU6 | A principal mismatch is a security-relevant event and is logged as such — without the key, without PII, without secrets (master `# 21`, `# 23.1`). |
| AU7 | The `Actor`'s fields, and how a "principal/context" is fingerprinted from it, are **deferred** to the authentication phase (item 4 §11.3, §24). The rule that replay is principal-scoped does not depend on that answer. |

---

## 13. Result contract

Frozen conceptually. It is small, and it is a frozen application DTO (item 4 §7 rules apply at the
application boundary, §19).

| May carry | Note |
|---|---|
| the `Order`'s `PublicId` | the only order locator that crosses (R10) |
| the durable order state | a public enum owned by `orders`, or a checkout-level placement outcome enum — decided in the implementing phase |
| whether a **payment action is required** | a boolean/enum fact, decided from the committed local state |
| a vendor-neutral **next-action descriptor**, if a later phase needs one | neutral by construction: no provider name semantics, no provider URL obtained during placement (§14) |
| whether the result was **replayed** rather than newly created, where a caller legitimately needs it | optional; must not leak another actor's existence (AU2) |

Never exposed:

- an `Order` (or any) ORM model or QuerySet;
- an internal bigint PK as a public locator (master `# 5.1`, item 4 I3);
- a provider SDK object, a maib/MIA raw payload, or a provider status;
- a mutable `CheckoutSession` — or any mutable object at all;
- a transport concept: HTTP status, URL, header, template (item 4 D4, X5).

The final DTO shape is **not** designed here beyond ownership and forbidden leakage (§24).

---

## 14. Payment boundary

### 14.1 Inside the placement transaction — forbidden

| Forbidden inside `atomic()` |
|---|
| maib HTTP; MIA HTTP; any bank/provider call |
| bank redirect or provider payment-session creation |
| CRM call; ERP/1C call |
| email or SMS dispatch |
| message-broker publish outside the transactional Outbox |
| any Celery `.delay()`/`apply_async` (item 4 T5) |

What *is* permitted at C8 is a local `PaymentAttempt(created)` row through `payments.public` — a
PostgreSQL write owned by a domain, which R7 explicitly does not classify as external I/O
(item 4 T4), and which master `# 11.4` step 2 places in this transaction.

### 14.2 The unambiguous rule

> **`place_order` never performs provider I/O, and never schedules it directly. Not sometimes. Not
> for one payment method. Not "just the redirect".**

There is no branch of `place_order` in which the outcome depends on a provider's response. A
successful provider payment is **not** a prerequisite for committing the `Order`; the master freezes
the opposite order (master `# 11.4` step 3: initiation happens after the local commit) and freezes
webhook + reconciliation as the mechanism that converges payment state (master `# 12.2`, `# 12.7`).

```text
Order committed locally
   → payment action initiated after commit
   → webhook / reconciliation drive payment state
```

### 14.3 Who owns the post-commit payment step

**Not `place_order`, and not `application/checkout`.** This follows from two frozen rules rather
than from preference:

- ADR-0005 §2 freezes `application/payments_gateway` as the owner of the payment provider port;
- ADR-0005 §7 forbids application→application imports.

So `application/checkout` can neither hold the port nor call the module that does. The post-commit
provider interaction is therefore **a separate application use case owned by
`application/payments_gateway`**, receiving its bound port by injection from the composition root
(ADR-0005 §3), and operating on an already-committed `Order`/`PaymentAttempt`.

Two triggers are legal, and both keep every entry point calling exactly one use case:

| Trigger | Shape |
|---|---|
| **T-a — Outbox-driven** | The placement transaction writes an Outbox record; the relay dispatches to a `tasks/*` handler, which calls the `application/payments_gateway` use case with its injected port (ADR-0005 §5). |
| **T-b — a second transport entry** | The interface, having received "payment action required", issues a *separate* request to a payment-initiation entry point that calls the same `application/payments_gateway` use case. This is what makes a synchronous bank redirect possible without any provider I/O inside the placement transaction. |

Which trigger applies to which payment method is **deferred** to the payments phase (§24). The
choice cannot reintroduce provider I/O into `place_order` under either option, which is why leaving
it open is safe.

### 14.4 Stability across retries

Provider initiation reuses the stable provider idempotency key / `PaymentAttempt.public_id`
(master `# 11.4` step 3). A provider timeout continues the existing `PaymentAttempt`; it never
creates a second `Order` and never creates a second reservation. A provider outage after commit
leaves the `Order` committed and the payment state pending until webhook or reconciliation resolves
it — the placement is never rolled back to accommodate a provider (§16, row 15).

For post-pay methods (cash, IBAN, POS on delivery) the `Order` moves through its own allowed state
transitions and the reservation is committed exactly once by an atomic transition (master `# 11.4`
step 4) — still with no provider call inside the placement transaction.

---

## 15. Outbox and events

| # | Rule |
|---|---|
| EV1 | State changes at placement that must cause asynchronous work write durable Outbox records **in the placement transaction** (C10). If the placement rolls back, so do they. |
| EV2 | `place_order` never calls Celery `.delay()`, never publishes to a broker, never calls ERP/CRM/email/SMS directly. |
| EV3 | Each domain command emits the integration events it owns by writing an Outbox row through `core` (item 4 §9.1); `place_order` writes the placement-level record(s) it owns through the same `core` mechanism. Coalescing a placement into one record where appropriate is permitted (master `# 20.2`). |
| EV4 | Event **names, payload schemas, versions, the registry and trace-propagation fields** are **not** defined here. They are Phase 0 item 8 (and item 10). Nothing in this artifact may be read as fixing an event name. |
| EV5 | Dispatch is the relay's; delivery latency is never part of the placement's correctness. |

---

## 16. Failure matrix

### 16.1 The matrix

Columns: **TX** = the placement transaction's fate; **Order?** = whether an `Order` exists
afterwards; **Same-key retry safe?** = whether retrying with the same idempotency key is safe;
**Surfaced by** = who owns the surfaced error/result and its `core.errors` category.

No row maps to an HTTP status: transport mapping is the interface's (item 4 X5).

| # | Situation | TX | Order? | Same-key retry safe? | Surfaced by |
|---|---|---|---|---|---|
| 1 | Checkout session unknown, or not visible to this actor | rolls back / never opens | No | Yes (deterministically fails again) | `application/checkout` — `NotFound`/`NotAllowed`, per its existence-leak policy (item 4 Z8) |
| 2 | Checkout session expired or in a non-placeable state | rolls back | No | Yes — the claim rolled back too (§11.7) | `application/checkout` — `InvalidState` (workflow semantics it owns) |
| 3 | Stale checkout content: requested lines disagree with server-side workflow state | rolls back | No | Yes | `application/checkout` — `Conflict` |
| 4 | SKU no longer sellable / withdrawn | rolls back | No | Yes | `catalog` (or `pricing` where it detects it) — `Validation`/`Conflict` |
| 5 | Price changed between preparation and revalidation (the owner's freshness guard rejects the prepared fact, §7.4) | rolls back, bounded re-preparation (TX5) | No, unless a retry succeeds | Yes | internal on retry; if it must surface, `application/checkout` — see §17 |
| 6 | Coupon/promotion no longer valid, or its redemption limit was consumed concurrently | rolls back | No | Yes | `promotions`/`pricing` — `Conflict`/`Validation` |
| 7 | Insufficient stock at reservation | rolls back | No | Yes (may fail again) | `inventory` — `Conflict` |
| 8 | Reservation conflict (lost the atomic race, `rowcount = 0`) | rolls back | No | Yes | `inventory` — `Conflict` |
| 9 | Duplicate request, same key, same fingerprint, first attempt **committed** | second TX rolls back its own empty work | Yes — the **first** one | Yes | `application/checkout` — success, replayed (§11.5) |
| 10 | Duplicate request, same key, first attempt **still running** | the contender waits on the durable uniqueness mechanism (§11.6) | depends on the first: exactly one either way | Yes | if the first commits → ID4 applies (replay / `Conflict` / `NotAllowed`); if it rolls back → the contender claims the key and proceeds; a bounded-wait timeout is a technical fault, never a fabricated business outcome |
| 11 | Same key, **different** fingerprint, against an **already committed** record | rolls back | No new one; the committed original exists | No — this key is bound to its committed fingerprint; the request must change its key or its content | `application/checkout` — `Conflict` (ID4) |
| 11a | Same key, different fingerprint, but the earlier attempt **rolled back** | proceeds normally | Yes — one, from this request | Yes | none — no committed record and therefore no retained fingerprint exists (ID5, §11.7); this is a fresh claim, not a conflict |
| 12 | Same key, **different principal**, against an already committed record | rolls back | No new one | No | `application/checkout` — `NotAllowed`; logged as a security event (AU3, AU6) |
| 13 | Database failure/unavailability **before** commit | rolls back | No | Yes | **technical fault, untranslated** to the platform boundary (item 4 §13.5); never a checkout business error |
| 14 | Caller never receives the committed response — client disconnect/timeout, **or** a technical failure after `COMMIT` (result-construction bug, process death, transport failure) | already committed | Yes | Yes — replays (§11.7, §16.2) | none at placement; the current invocation may still fail technically, and the retry receives the replayed success |
| 15 | Payment provider unavailable **after** the Order commit | already committed — **not** rolled back | Yes | Yes (replay; provider initiation retries separately) | `application/payments_gateway` / `payments`; the Order stays committed and the payment state converges by webhook/reconciliation |
| 16 | Outbox relay lag or failure after commit | already committed | Yes | Yes | none — the relay retries; placement correctness is unaffected (EV5) |
| 17 | Programmer error (`TypeError`, broken invariant) or any technical fault **while the placement transaction is still active** | rolls back | No | Yes, once fixed | **technical fault, untranslated**; never dressed as a checkout outcome |
| 18 | Programmer error or technical fault **after `COMMIT` succeeded** — see §16.2 | already committed, unaffected | Yes | Yes — replays | **technical fault, untranslated**; no compensation, no rollback, and never converted into a business result |

### 16.2 Technical failure: before commit vs after commit

The two are different outcomes and must not be collapsed. `COMMIT` is the dividing line.

| | **Before `COMMIT`** | **After `COMMIT`** |
|---|---|---|
| Examples | `OperationalError`, programmer error, an unexpected invariant defect, a timeout while the transaction is still active | a bug while constructing or mapping the result DTO, process failure immediately after commit, transport failure or disconnect, any other technical fault once the durable transaction has completed |
| Transaction | rolls back | already committed; nothing can undo it |
| `Order` | does not exist | **exists**, with the reservation, redemptions, `PaymentAttempt`, checkout state transition and Outbox rows |
| Idempotency record | none — the claim rolled back; the key is unused again (ID5) | the **committed** outcome exists and is replayable |
| This invocation | fails technically, untranslated (item 4 §13.5) | may still fail technically, untranslated — the caller's failure says nothing about the durable result |
| Recovery | retry with the same key re-executes the placement | retry with the same key **replays** the committed outcome; no second `Order` |
| Compensation | not applicable — nothing was written | **forbidden.** No rollback, no reversal, no cancellation is attempted for a committed placement. A commercial reversal, if the business wants one, is a separate business operation (an order cancellation with its own owner, actor and state transition), never an error-handling side effect (R6, V23). |

Neither column is ever converted into a business outcome: "we committed but the response failed" is
not out-of-stock, not a conflict, and not a placement failure.

---

## 17. Price-change policy

Two questions are deliberately separated:

| Question | Status |
|---|---|
| **Is the price recomputed authoritatively at placement, from OLTP, ignoring any cached or client-supplied value?** | **Frozen — yes**, always (master `# 8.4`, `# 11.4` step 1; PR1, PR2, §6.2). A stale client or session price is never authoritative and never becomes a committed line. |
| **If the authoritative price differs from what the user was shown, is the new price accepted automatically or must the user reconfirm?** | **Deferred.** This is a UX/business policy, and the master does not decide it. It is not invented here. |

What the architecture must support either way, and therefore freezes now:

- a *freshness race* (the prepared price was invalidated under a concurrent write, §7.4) and a *material
  commercial change* (the price differs from what the user was shown) are **different things**: the
  first is resolved by bounded internal re-preparation (TX5); the second is a business outcome and
  must be representable in the result/error contract without redesigning the use case;
- the placement never commits at a stale price under either policy;
- the eventual policy is a decision of `application/checkout` (it is workflow semantics, not a
  domain invariant), and adopting a reconfirmation policy is a normal additive change to the
  checkout contract, not an architecture change.

---

## 18. `CheckoutSession` placement concurrency

Only the minimum required for the placement invariant is frozen; the full state machine is deferred.

| # | Rule |
|---|---|
| SM1 | **One logical checkout cannot produce two `Order`s.** |
| SM2 | The checkout's placement state transition is **atomic with the `Order` result**: it happens inside the placement transaction (C9), from an allowed predecessor state, conditionally — so a concurrent second attempt cannot also observe a placeable checkout. |
| SM3 | A retry can **discover the previously committed result** — through the idempotency replay (§11.5) and, independently, through the terminal checkout state pointing at the committed order. |
| SM4 | Concurrent `place_order` attempts are serialized or rejected through **durable database state** — the idempotency unique constraint and the checkout row lock/conditional transition — never through a Redis lock. A Redis layer may damp bursts; removing it changes no outcome. |
| SM5 | Everything else about the checkout state machine — the step model, expiry handling, abandonment, resumption, guest→account linking — is deferred (§24). |

---

## 19. The application public boundary

```text
application/checkout/public.py
    exports place_order
    and only the stable checkout application DTOs / errors its callers need
```

Frozen (item 3 §7/§11 conventions, applied to checkout):

| # | Rule |
|---|---|
| AP1 | `application/checkout/public.py` is the module's only importable surface. `CheckoutSession` and every other application-owned ORM object is internal to the module, exactly as domain ORM is internal to its domain. |
| AP2 | The application contract obeys the same **no-ORM / no-vendor / no-transport / no-lazy** rules as a domain contract (item 4 §6, §7): frozen DTOs, `Money`, `PublicId`, aware UTC instants, immutable collections, no `Mapping`/`Sequence` field shapes, no field named `id`/`pk`. |
| AP3 | The actor is explicit, mandatory and non-optional; `actor=None` is banned; privileged placement uses an explicit system context (item 4 Z1–Z4). |
| AP4 | Application→application imports remain forbidden; another module needing a placement enters through a transport boundary, or the owners merge (ADR-0005 §7). |
| AP5 | `place_order` **does not reimplement** a domain invariant. It sequences; pricing rules stay in `pricing`, availability in `inventory`, order state in `orders`, payment state in `payments`. A rule that has migrated into checkout is a review failure (V-series, §22). |
| AP6 | Checkout does **not** duplicate a domain's error implementation. It defines an application error only for orchestration-level semantics that no single domain owns (§20). |
| AP7 | The file is **not** created in Phase 0. |

---

## 20. Error ownership

### 20.1 Domain errors stay with their domains

Insufficient stock (`inventory`), invalid pricing input or an unusable promotion
(`pricing`/`promotions`), an illegal order state (`orders`), an illegal payment state
(`payments`) — each is a public error owned and raised by its domain, over exactly one `core.errors`
category (item 4 §13.1). `place_order` maps a category to workflow behaviour; it does not rename,
rewrap or re-implement the error.

### 20.2 Checkout application errors

`application/checkout` defines its own public errors **only** for workflow semantics no single
domain owns, over the same `core.errors` categories and under a checkout application root. Conceptual
examples, names not frozen:

| Concept | Category |
|---|---|
| the checkout expired or is not placeable | `InvalidState` |
| a **committed** placement's idempotency key was reused with a materially different request | `Conflict` |
| a placement already completed and the incoming request is incompatible with it | `Conflict` |
| an idempotency replay requested by a different principal | `NotAllowed` |
| the requested lines disagree with server-side workflow state | `Conflict` |

### 20.3 Technical faults

Database unavailability, an unclassified `DatabaseError`, a lock/statement timeout, corruption and
programmer bugs propagate **untranslated** to the platform boundary (item 4 §13.5). They are never
laundered into a checkout outcome — an outage reported as "out of stock" or "conflict" would convert
a page-the-operator condition into a business result and make every retry policy built on the
category do the wrong thing.

No error defined by `place_order` or by any domain it calls carries an HTTP status number; the
interface maps categories to transport (item 4 X5, §13.6).

---

## 21. Locking and concurrency discipline

### 21.1 Principles

| # | Rule |
|---|---|
| LK1 | **No check-then-write for stock.** Availability is decided by the owning domain's atomic conditional update, not by an earlier read (INV2). |
| LK2 | Hot-row locks are taken **as late as possible and held as briefly as possible**; read-heavy work runs in the preparation phase (§7.2). |
| LK3 | Checkout and idempotency state are serialized **durably in PostgreSQL** where serialization is required — a unique constraint, a row lock, or a conditional state transition. Never a Redis lock (SM4). |
| LK4 | **No external I/O while a lock is held** — the strongest practical form of R7 (§7.3, §14.1). |
| LK5 | Lock acquisition order across placement participants is **deterministic**; multi-row locks within one participant (several SKUs, several balances) are acquired in a stable, documented order to prevent deadlocks between concurrent placements. |
| LK6 | Bounded waits: lock and statement timeouts are configured, and exceeding one is a technical fault (§11.6), not a business outcome. |

### 21.2 The frozen lock rank order

Placement acquires locks in this rank order, which matches §8.1:

```text
1. IdempotencyKey (scope, key)      — unique-constraint claim, first
2. CheckoutSession row              — the workflow gate
3. inventory rows                   — hot; ordered deterministically within the step
4. promotion / coupon redemption    — hot; ordered deterministically within the step
5. order / order item inserts       — new rows, no contention on existing hot rows
6. payment attempt insert           — new row
```

The rank order is frozen; the SQL that implements it (`SELECT … FOR UPDATE`, conditional `UPDATE`,
`INSERT … ON CONFLICT`, skip-locked variants, timeout values) belongs to the implementing phases.

---

## 22. Checks a later phase must implement

These **extend** the enforcement maps of item 3 §15 and item 4 §19; those remain authoritative and
unchanged. Nothing here is implemented in Phase 0.

### 22.1 Import graph (`L` series)

**No new `L` rule, and no new `core` allowlist entry.** Every import this use case needs —
`application/checkout` → `<domain>.public`, → `core` (including `core.idempotency` and
`core.outbox`), → its own internal ORM — is already permitted by item 3 §4; every import it must not
make — `integrations/*`, `config/*`, another `application/*`, a domain's internals — is already
forbidden there. ADR-0007 moves no matrix cell.

### 22.2 Static / AST (continuing the `A` series)

| # | Rule |
|---|---|
| A24 | No module under `domains/*` or `interfaces/*` or `tasks/*` contains a placement orchestration shape — that is, a body reaching two or more `<domain>.public` modules in one callable (extends A5/A6's one-domain rules to the use case's signature shape). |
| A25 | No provider/vendor call, and no `.delay()`/`apply_async`/broker publish, appears lexically inside an `atomic()` block in `application/checkout` (§14.1, EV2). |
| A26 | `application/checkout` contains no `transaction.commit`/`rollback`/`set_autocommit`, and no second `atomic(durable=True)` in the placement path (§7.1). |
| A27 | No application public DTO in `application/checkout/public.py` exposes an ORM type, a provider type, a transport type, a field named `id`/`pk`, or a mutable/abstract field shape (AP2 — the item 4 A16/A17/A20 checks applied to the application boundary). |
| A28 | `place_order`'s actor parameter has no default and is not `Optional` (AP3 — item 4 A19 applied here). |

### 22.3 Behavioural / contract tests (continuing the `C` series)

| # | Rule |
|---|---|
| C11 | **Atomicity before commit:** an injected failure at each of C2–C11 — that is, at any point before `COMMIT` — leaves *no* `Order`, *no* reservation, *no* redemption, *no* `PaymentAttempt`, *no* Outbox row and *no* idempotency record. Asserted per step, not once. |
| C12 | **No orphan reservation:** forcing an order-creation failure after a successful reservation leaves the `InventoryBalance.reserved` counter and the reservation table exactly as they were. |
| C13 | **Concurrency — last unit:** N concurrent placements for a stock of 1 produce exactly one `Order` and exactly one reservation; the losers receive an inventory conflict, never a technical error and never a negative counter. |
| C14 | **Idempotent retry:** the same key + same fingerprint, executed twice sequentially and concurrently, produces exactly one `Order`; the second call returns the replayed outcome. |
| C15 | **Fingerprint conflict, from a committed record:** starting from an **already committed** first placement, the same key with a materially different request never creates a second `Order` and surfaces a `Conflict` category (ID4). |
| C15a | **No phantom conflict after a rollback:** starting from a first attempt that **rolled back**, the same key with a *different* fingerprint is accepted as a fresh claim and places exactly one `Order` — no `Conflict` is raised, because no committed record and no retained fingerprint exist (ID5). |
| C15b | **Contender behaviour both ways:** with two concurrent attempts sharing a key, the contender replays/conflicts/refuses when the winner commits, and claims the key and proceeds when the winner rolls back (§11.6). |
| C16 | **Replay is principal-scoped:** a different actor presenting a valid key receives neither the order data nor a confirmation that it exists (AU2, AU3). |
| C17 | **Commit ambiguity — client side:** simulating a client disconnect/timeout after commit and retrying with the same key yields the same `Order` and no second one. |
| C17a | **Commit ambiguity — technical failure after commit:** with the commit succeeding and a fault injected **after** it (result construction, process death, transport), the `Order` and the committed idempotency outcome exist, nothing is compensated or rolled back, and a retry with the same key returns the committed `Order` — exactly one in total (§16.2). |
| C18 | **No external I/O in the transaction:** a socket-blocking fixture that permits only PostgreSQL and Redis is active for the whole placement path (extends item 4 C7 to the application layer). |
| C19 | **Post-commit provider outage:** with the provider adapter failing, the `Order` stays committed and reaches a defined pending payment state; nothing rolls back. |
| C20 | **Technical faults are not laundered:** an injected `OperationalError`/`TypeError` **before commit** propagates as a technical fault and leaves no `Order`, no reservation, no `PaymentAttempt` and no idempotency record; the same fault injected **after commit** also propagates untranslated but leaves the committed rows intact and triggers no compensation (§16.2, extends item 4 C9). |
| C21 | **Projection is not truth:** with `PriceProjection`/`ProductListingProjection` deliberately stale or emptied, placement pricing and availability outcomes are unchanged. |
| C22 | **Snapshot immutability:** changing catalog/pricing/promotion rows after commit changes no field of the committed `OrderItem` snapshot. |
| C23 | **Query/lock budget:** the placement transaction's statement count and its hot-row lock duration are bounded and asserted, so a regression that moves pricing back inside the locks fails CI (master `# 22.5`). |

### 22.4 Review-only (continuing the `V` series)

| # | Rule |
|---|---|
| V19 | A second placement path appearing anywhere — a view, a task, a management command, a backoffice action — that sequences pricing/inventory/orders itself instead of calling `place_order` (§3.4). |
| V20 | `application/checkout` reimplementing a domain invariant: recomputing a price, deciding availability, or advancing an order/payment state machine itself (AP5). |
| V21 | A `CheckoutSession` value used as authoritative commercial truth at placement (CS3, CS4). |
| V22 | Provider or notification work smuggled into the placement transaction through an indirect route — a signal handler, a model `save()` override, an `on_commit` inside a domain, a "small" synchronous adapter call (§14.1, item 4 T5). |
| V23 | Compensation/saga machinery introduced for the local placement flow — including a "cleanup" path that cancels, reverses or deletes a **committed** placement because the response failed (R6, §16.2). |
| V24 | An idempotency record used as an access token, or a replay path that skips the actor-scoped read (§12). |
| V25 | A retry loop over preparation that is not bounded (TX5). |
| V26 | Checkout reading a domain's internal version/`updated_at` column, assuming a uniform version field across owners, or introducing a shared global version counter instead of using each owner's freshness guard (FG1–FG3). |

---

## 23. Acceptance checklist

- [ ] `place_order` has exactly one architectural owner: `application/checkout` (§3.1), and the
      forbidden homes are enumerated (§3.2).
- [ ] No interface, task or domain reproduces the orchestration (§3.3, §3.4, A24, V19).
- [ ] Every domain is reached through its `public.py`; no domain imports another (§4, R3, R4).
- [ ] Client/session price, discount, total, stock, reservation success and payment success are
      never authoritative (§6.2).
- [ ] One outer PostgreSQL `transaction.atomic()` owns every durable write of the placement; the
      preparation phase writes nothing and holds no lock (§7).
- [ ] Reservation and `Order` cannot partially commit — they are the same transaction (INV4, C11,
      C12).
- [ ] An idempotent retry cannot create a second `Order` (§11.5, C14).
- [ ] Against a **committed** record, the same key with a materially different request is rejected,
      not executed (ID4, C15); after a **rolled-back** attempt the key is simply unused and no
      phantom conflict is claimed (ID5, C15a).
- [ ] A concurrent contender behaves correctly whether the winner commits or rolls back (§11.6,
      C15b).
- [ ] An idempotency replay is principal/context-scoped and leaks nothing across actors (§12, C16).
- [ ] Commit ambiguity — client timeout **or** a technical failure after `COMMIT` — is recoverable
      with the same key, and no compensation is attempted (§11.7, §16.2, C17, C17a).
- [ ] Prepared facts are revalidated through each owner's freshness guard; no generic
      `source_version` is assumed for catalog/pricing/delivery, and item 12's storefront
      `source_version` decision is untouched (§7.4, FG1–FG4, V26).
- [ ] No external/provider I/O occurs inside the placement transaction, on any branch (§14, A25,
      C18).
- [ ] The storefront/price projection is never checkout truth (PR2, INV3, C21).
- [ ] The `Order` snapshot is immutable historical truth after commit (PR5, C22).
- [ ] A payment provider outage after commit does not roll back a committed `Order` (§14.4, C19).
- [ ] Technical failures propagate untranslated and are never converted into checkout outcomes;
      before commit they leave no `Order`, after commit they leave the committed placement intact
      (§16.2, §20.3, C20).
- [ ] No ORM, vendor or transport object crosses `application/checkout/public.py` (AP2, A27).
- [ ] Event names, schemas and versions remain deferred to item 8 (EV4).
- [ ] The price-change UX policy is deferred, not invented; authoritative re-pricing is frozen
      (§17).
- [ ] No contradiction with ADR-0001…ADR-0007 (§25, rows 15, 23).

---

## 24. Explicitly deferred decisions

| Deferred | Owner |
|---|---|
| `CheckoutSession` schema, step model and full state machine (beyond SM1–SM4) | the checkout implementation phase |
| `Order` / `OrderItem` schema, and the exact fields of the commercial snapshot (PR4) | the orders phase (master `# 8.3` lists the intended content) |
| `InventoryReservation` / `InventoryBalance` schema, constraints, indexes and reservation SQL | the inventory phase (master `# 9.2`, `# 5.4`) |
| Whether a given payment method commits the reservation at placement or later (INV6) | the payments/inventory phases (master `# 11.4` step 4) |
| `IdempotencyKey` columns, indexes, retention specifics and the generic idempotency ADR | the idempotency item/ADR (Phase 0 item 15); this artifact freezes only the behavioural contract place_order's correctness needs |
| The exact field list of the request fingerprint (ID3) | the checkout implementation phase |
| The **mechanism** of each owner's freshness/revalidation guard — revision token, `updated_at` check, input hash, authoritative re-read, conditional command, or another owner-defined token (§7.4) | each owning domain, in its own phase. Item 12's storefront `source_version` is a separate, read-model decision and is not consumed here. |
| How a principal/context is fingerprinted from the `Actor`, and the `Actor`'s fields (AU7) | the authentication phase (item 4 §11.3, ADR-0006 §1) |
| The final `place_order` signature, its input DTO and its result DTO fields (§13) | the checkout implementation phase |
| Which post-commit payment trigger (T-a Outbox-driven / T-b second transport entry) applies per payment method (§14.3) | the payments phase |
| Whether a materially changed price is auto-accepted or requires user reconfirmation (§17) | a deliberate business/UX decision, recorded when made |
| Event names, payload schemas, versions, registry and trace fields (EV4) | Phase 0 items 8 and 10 |
| Delivery pricing/routing algorithms and promotion internals | the delivery and promotions phases |
| `Money` / `PublicId` implementation | Phase 0 item 11 |
| Concrete SQL for the frozen lock rank order — `FOR UPDATE`, conditional `UPDATE`, `ON CONFLICT`, timeout values (§21.2) | the implementing phases |
| The AST/contract-test implementations for A24–A28 and C11–C23 | Phase 1+ |
| Any weakening of §3–§21 — a second placement path, an optional actor, provider I/O in the transaction, Redis-only duplicate protection, saga machinery | requires a new ADR |

---

## 25. Self-review record

| # | Check | Result |
|---|---|---|
| 1 | `place_order` cannot accidentally become the `orders` domain's | Pass — §3.1 states the owner, §3.2 rejects `domains/orders` by name with the reason (an `Order` coming out of it is not ownership; it would need three sibling domains, violating R4), and §4 gives `orders` a bounded responsibility that stops at its own aggregate. V19/V20 cover the review-only drift. |
| 2 | No inventory reservation can commit independently of the `Order` | Pass — INV4 puts them in one transaction, §8.3 shows the rollback removes both the reservation row and the balance increment, C12 asserts it, and §7.1 forbids any independent commit. No compensation path exists because none is needed (R6, V23). |
| 3 | No external payment HTTP inside `atomic()` | Pass — §14.1 enumerates the forbidden calls, §14.2 states the rule with no per-method exception, A25 checks the lexical shape, C18 blocks sockets in tests, V22 covers indirect routes (signals, `save()` overrides, `on_commit` inside a domain). The only payment work inside the transaction is a local `PaymentAttempt` row, which master `# 11.4` places there and item 4 T4 classifies as domain PostgreSQL work, not external I/O. |
| 4 | A cached `CheckoutSession` price can never be trusted | Pass — CS3 denies it price truth, §6.2 lists it among non-authoritative values, PR1/PR2 route pricing through `pricing.public` from OLTP, C3 revalidates in-transaction, and §17 freezes authoritative re-pricing independently of the deferred UX policy. |
| 5 | An idempotency record cannot become "completed" before the `Order` commits | Pass — §11.4: claim (C1) and completion (C11) are written inside the placement transaction, so both become visible at the same instant as the `Order`, by the database. §11.7 covers the rollback case: nothing durable survives, so no completed record can point at a non-existent order. |
| 6 | A replay cannot leak an `Order` across actors | Pass — §12: AU1 scopes the identity, AU2 forbids serving another principal, AU3 refuses with `NotAllowed` rather than replaying, AU4 additionally re-applies the actor-scoped read, AU5 covers guests, AU6 logs it, C16 tests it, V24 covers the "key as access token" drift. |
| 7 | Duplicate protection is never Redis-only | Pass — R9, §11.1 and SM4 all state it; the mechanism is the `(scope, key)` unique constraint plus the checkout row's conditional transition. Redis is admitted only as a burst damper whose loss changes no outcome. |
| 8 | A timeout/retry cannot produce a duplicate order | Pass — §11.6 (contender serialized on the unique constraint), §11.7 and §16.2 (commit ambiguity replays, whether the caller vanished or the failure was technical), §8.3 rows 2–3 and 7, matrix rows 9, 10, 14, 18, and tests C14/C17/C17a. |
| 9 | The storefront/price projection is never used for price or stock | Pass — PR2 and INV3 forbid it, R13 inherits it from ADR-0003, §4 removes price/stock from `catalog`'s responsibility, and C21 asserts placement outcomes are unchanged with the projections stale or empty. |
| 10 | No hidden saga inside a local transaction | Pass — §7.1 and R6 state the rule, §7.2 shows the preparation phase is read-only and therefore not a phase of a distributed protocol (TX1/TX4), and V23 flags compensation machinery as a review failure. The only cross-boundary step (provider payment) is explicitly *outside* the transaction and *outside* this use case (§14.3). |
| 11 | The application does not reimplement pricing/inventory/order invariants | Pass — §4 assigns every authoritative decision to a domain, AP5 states the rule, §13 Q2 of item 2 supplies the test ("wrong about the sequence, not about the business"), and V20 is the review check. `place_order` decides order and timing only. |
| 12 | The one-transaction rule and master `# 11.4`'s PREPARE/SHORT-TX split are reconciled, not glossed over | Pass — §7.2 states six explicit rules (TX1–TX6) making preparation read-only, lock-free, revalidated, bounded and non-durable, and §1.3 records this as one of the three reasons ADR-0007 exists. §8.2 names the three places where the drafted ordering was refined and why. |
| 13 | The payment boundary is unambiguous | Pass — §14.2 forbids provider I/O on every branch; §14.3 derives the post-commit owner from ADR-0005 §2 + §7 rather than from preference, and names two legal triggers that both keep one use case per entry point; the trigger choice is deferred (§24) and cannot reintroduce I/O into `place_order` under either option. |
| 14 | Nothing here designs what a later item owns | Pass — §1.2 and §24: no schema, no signature, no DTO fields, no event names (EV4 → item 8), no idempotency columns (→ item 15), no `ProductCard`/facet shapes (items 6, 7), no `Money`/`PublicId` implementation (item 11), no delivery or promotion internals. Every named error and step is labelled conceptual. |
| 15 | No contradiction with ADR-0001…ADR-0006 | Pass — **0001:** §13 and R10 keep `PublicId` as the only external locator and internal bigints internal. **0002:** untouched. **0003:** PR2/INV3/R13 keep the projection out of the checkout path and price/stock out of `catalog`. **0004:** §3 applies §4 (one application owner) and §5 (interfaces delegate); §7 applies §10 (transaction ownership, local ACID is not a saga); §5/CS6 apply §6 (authorization follows state ownership, `CheckoutSession` to `application/checkout`); §14.1 applies §7's payment/webhook split. **0005:** §14.3 applies §2 (port owner) and §7 (no application→application); §22.1 confirms no matrix cell moves; AP1 applies §7's one-entry-point rule. **0006:** §20 uses the `core.errors` categories with `application` as a listed consumer and adds no business vocabulary to `core`; AP3 uses the `core` actor primitive; `integrations/*` gains nothing. |
| 16 | The failure matrix has no ambiguous or unsafe cell | Pass — §16.1 gives every row a transaction fate, an order-existence answer, a retry-safety answer and an owner. Committed-order rows (14, 15, 16, 18) keep the `Order` committed; technical rows (13, 17, 18) refuse translation into business outcomes; row 11 refuses a second operation against a committed record while 11a records that a rolled-back attempt leaves nothing to conflict with; row 12 refuses a cross-actor replay. |
| 17 | Failure semantics of the idempotency key are decided, not left implicit | Pass — §11.7 freezes that a `checkout.place_order` failure rolls the claim back with the transaction, so only a *committed* placement is replayable. That removes the poisoned-key failure mode, is consistent with master `# 5.2` (claim in the same transaction as the domain entity), and confines the master's `failed` state to scopes that genuinely need cross-transaction memory. |
| 19 | Fingerprint semantics and the rollback-frees-the-key rule are mutually consistent | Pass — the earlier unconditional pair ("different fingerprint → `Conflict`" and "a rollback erases the record") is now conditioned on the same fact: ID4 governs the case where a **committed** record exists, ID5 the case where none does, ID6 states the resulting invariant, and §11.6/§11.7/matrix rows 11 and 11a/C15/C15a/C15b say the same thing in the concurrency, retry, matrix and test views. No statement anywhere claims a rolled-back attempt leaves a comparable fingerprint, and none invents a separately committed `processing` claim, which would contradict §7.1. |
| 20 | Freshness revalidation is a requirement, not a mechanism | Pass — §7.4 freezes only the outcome (stale prepared data may never back a durable write), routes every fact to its owner, and defers the guard's implementation; FG1–FG4 forbid reading internal version columns, assuming a uniform version field or inventing a global counter, and keep inventory/promotion atomic commands as their own authoritative gates; TX3, C3, §8.2, matrix row 5 and §17 use the neutral term; V26 is the review check. |
| 21 | Item 12 is not consumed or contradicted | Pass — §7.4's closing paragraph states that item 12 owns `source_version` generation and the guarded **storefront projection** upsert as a read-model concern, that this is not a general OLTP versioning scheme, and that catalog `Product`/`ProductVariant` gain no storefront `source_version` state. No rule here requires one. |
| 22 | Technical failure is split at `COMMIT`, and no compensation is introduced | Pass — §16.2 tabulates both sides (transaction fate, `Order`, idempotency record, this invocation, recovery, compensation) and forbids reversing a committed placement as error handling; matrix rows 17 and 18 carry the split; row 14 merges client-side and technical commit ambiguity; C11 is explicitly the before-commit assertion, C17a and C20 cover the after-commit side, and V23 flags a post-commit "cleanup" path as a review failure. A commercial reversal remains a separate business operation with its own owner. |
| 23 | No contradiction with ADR-0007 after this correction | Pass — ADR-0007 §2 and §1 were amended in the same change: the committed-vs-rolled-back distinction, the "no separately committed processing claim" rule, the owner-defined freshness guard and the before/after-commit split now read identically in the ADR and in this artifact. The ADR's frozen decisions — one placement transaction, in-transaction claim, post-commit provider payment — are unchanged. |
| 18 | Nothing in this artifact requires a new import edge or a `core` allowlist change | Pass — §22.1: every needed import is already `ALLOW`/`PUBLIC ONLY` in item 3 §4; every forbidden one is already `FORBID`. ADR-0007 records that it moves no cell, so L1–L21 and the `core` allowlists stand unedited. |

Verdict: **PASS**.
