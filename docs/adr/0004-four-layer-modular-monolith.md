# ADR-0004 — Four-layer modular monolith: core / domains / application / interfaces

- **Status:** Accepted — Frozen
- **Date:** 2026-09-03
- **Phase:** 0 — Architecture Freeze
- **Supersedes:** —
- **Related:** [ADR-0001](0001-product-vs-sku-sellable-unit.md), [ADR-0002](0002-typed-eav-source-of-truth.md),
  [ADR-0003](0003-catalog-boundary-vs-storefront-projection.md),
  [Phase 0 item 2 artifact](../architecture/phase-0/02-four-layer-architecture.md),
  master `# 3`, `# 4`

## Context

The platform is one Django deployment on one PostgreSQL. That is the right shape for a checkout that
must be ACID, and the wrong shape for a codebase left unstructured: the same properties that make a
local transaction cheap also make it cheap for `orders` to import `inventory.models`, for a view to
orchestrate four domains, and for `catalog` to grow a `price` column.

Master `# 3` and `# 4` already name four layers and a dependency direction. What they do not settle
is the set of questions that decide every future placement argument:

- what actually qualifies for `core`, as opposed to what merely feels generic;
- whether an interface may ever call a domain directly, or must always route through `application`;
- whether a domain may reach a sibling domain through its `public.py`;
- who owns the transaction of a cross-domain use case, and whether that is a saga;
- where a disposable cross-domain read model lives;
- who owns a webhook signature check versus the payment decision behind it;
- where object-level authorization happens.

These have to be answered before Phase 1 creates the packages, because a directory tree encodes the
answers whether or not anyone wrote them down. This ADR records the decision; the Phase 0 item 2
artifact carries the full reasoning, tables and examples.

The immediately available alternatives were: a conventional Django app-per-feature layout (rejected:
no enforceable direction, cross-app imports are invisible), a strict layer-by-layer pass-through
(rejected: produces pass-through modules and an `application` god-layer), and starting from services
(rejected: forfeits local ACID for checkout and buys distribution problems before any measured
need).

## Decision

### 1. Four layers with a one-directional, skip-allowed dependency graph

`interfaces → application → domains → core`.

A layer may depend on **any** layer below it, never upward and never sideways at the domain level.
Skipping downward is legal: `interfaces → domains` and `application → core` are permitted edges.
"Every call must pass through the layer immediately below" is explicitly **not** the rule.

Downward calls cross a contract — `<domain>.public` plus immutable DTO/value objects — never an
implementation. `core` depends on nothing in this project but itself.

### 2. `core` is admitted by test, not by feel

A helper enters `core` only if it is domain-independent, carries no business *or vendor* vocabulary,
has (or clearly will have) more than one consumer, and is mechanism-shaped rather than
policy-shaped. Failing any of the four, it stays with the module that needed it. `core` is not
`utils`.

### 3. Domains are mutually invisible

No domain imports another domain — not its internals, and **not its `public.py`**. A domain knows
itself and `core`. A domain also carries no vendor wire-protocol detail. Cross-domain work never
lands in a domain because that domain looks like the "main" one.

### 4. `application` owns workflows; domains own invariants

Any operation touching two or more domains has exactly one owner in `application/`, organised by use
case under a named application. `application` decides **when** capabilities are called and in what
order; domains decide **what** their rules mean. Reservation semantics stay in `inventory`, pricing
rules in `pricing`, order state in `orders`, payment state in `payments`.

`ProductListingProjection` and the storefront read model belong to `application/storefront`, not
`domains/catalog` — consistent with ADR-0003.

### 5. Interfaces delegate; they never decide

Interfaces parse transport input, authenticate, apply coarse endpoint-level permission, construct
the actor/context, call **one** use case or **one** domain public contract, and render DTOs. They
own no business rule and never combine two domains' results themselves.

An interface may call `<domain>.public` directly when the request is satisfied by a single domain
and the interface adds no cross-domain sequencing. The second domain in a request moves the flow to
`application`.

### 6. Authorization splits at the transport boundary

Interfaces own authentication, credential/signed-token validation, coarse endpoint permission and
actor construction.

**Object-level authorization follows state ownership**: it belongs to the architectural module that
owns the protected state, reached through that owner's policy and actor-scoped selector. For
domain-owned state — `Order` (orders), `Review` (reviews), `Address` (accounts), `PaymentAttempt`
(payments) — that is the owning domain, exposed through its `public.py`. For genuinely
application-owned state — `CheckoutSession` (`application/checkout`), and any future
application-owned workflow entity or private read state — it is the owning `application` module.
Application-owned state is **not** pushed into an artificial domain to satisfy this rule.

An `application` use case may compose authorization decisions from several owning modules; it must
not reimplement a domain's object-level rule (decision 4).

An interface must not authorize by loading an ORM row and comparing an ownership field. This holds
equally for the legal direct `interfaces → <domain>.public` call, which uses that domain's
actor-scoped contract, and for `interfaces → application/<owner>` for an application-owned private
object.

### 7. Provider protocol verification and business interpretation have separate owners

Inbound provider protocol facts — raw-body signature/HMAC, provider timestamp, replay window,
provider event-identifier format — are verified by the **inbound adapter/boundary**
(`interfaces/webhooks/<provider>`, or a provider-specific security helper it uses), which then
performs durable Inbox ingest. These are vendor/protocol concerns, not payment invariants.

`domains/payments` owns the `PaymentAttempt` state machine, legal transitions, amount/currency
matching, duplicate-business-effect prevention, and the interpretation of an already-authenticated,
normalized event. Provider signature algorithms, vendor statuses and raw payload structures must not
appear in the payments domain.

Reconciliation is split with no overlap: *when it runs* is a task/application concern; *the provider
API call* is the integration adapter's; *validating and applying the normalized result under the
state machine* is the payments domain's.

### 8. `integrations/` is an outbound anti-corruption boundary — conceptually only

`integrations/*` adapters own no domain truth, hold the vendor protocol and client DTOs, isolate
vendor SDKs/enums/statuses/errors, decide no business policy, perform network/protocol translation
only, may use domain-independent `core` primitives where appropriate, and must never expose
vendor-specific types into a domain or application public contract. What crosses the adapter edge is
described neutrally as `vendor DTO ↔ stable internal integration contract/value types`.

A durable `provider + external_id ↔ internal entity` mapping is **integration/synchronization
boundary state**, not domain state — ADR-0003's rule that ERP/1C identity never sits on catalog
entities stands unchanged.

**Out of scope of this ADR**, by deliberate deferral to Phase 0 item 3: whether an adapter imports a
port or DTO defined elsewhere, whether dependency inversion is used and in which direction, which
layer imports an adapter, which layers an adapter may import, where the stable contract types live,
and the physical package/model home of the identity mapping (whose concrete ERP schema is Phase 3).

### 9. `tasks/` is transport, peer to `interfaces/`

A Celery task deserialises arguments, restores actor and trace, calls **one** use case or domain
public command, and maps the result to success/retry/DLQ. It may decide *when* an operation runs;
never *what it means*. Retry is a transport concern; idempotency is durable in PostgreSQL and lives
below the task.

Neither `integrations/` nor `tasks/` is a fifth business layer.

### 10. The transaction owner is the use-case owner; local ACID is not a saga

A cross-domain `application` use case owns its transaction boundary; a single-domain command owns
its own; interfaces and tasks own none. Domain commands are composable participants that neither
commit on their own behalf nor perform external HTTP inside the critical section.

**While the ACID core lives in one PostgreSQL, a cross-domain application use case may coordinate
the operation inside one local `transaction.atomic()`. That does not make it a distributed saga. A
saga/compensation design is required only when an ACID participant moves across a real process or
database boundary.**

## Consequences

**Positive**

- Placement arguments are resolved by a written rule instead of by whoever writes the code first.
- Every cross-domain flow is discoverable in `application/`; the dependency graph stays a DAG.
- Each domain is independently testable — the Phase 2 catalog DoD depends on exactly this.
- Checkout keeps a real ACID guarantee from PostgreSQL rather than a hand-written saga.
- Vendor churn stops at the adapter; a provider rename or status change touches no domain.
- A future extraction of a non-ACID-core domain (content, notifications, analytics, search) is a
  contract-and-operations change, not a rewrite.

**Negative / accepted cost**

- Some genuinely small cross-domain operations need an `application` module that would have been
  three lines inside a domain. Accepted: the alternative is an invisible domain→domain edge.
- Forbidding domain→`public.py`→domain is stricter than strictly necessary for any single call, and
  will occasionally feel bureaucratic. Accepted: it is the only version of the rule that is
  mechanically checkable and cycle-free.
- The product page and the grid require composition in `application/storefront` from the first
  sprint; there is no "just join it" shortcut (already accepted in ADR-0003).
- Splitting webhook verification from payment interpretation means two modules touch one vendor
  event. Accepted: it is what keeps vendor protocol out of the domain.
- Object-level authorization below the transport boundary costs a policy/selector call where a
  one-line ownership comparison in a view would have "worked".

**Enforcement**

- **Phase 0 item 3** turns this decision into the explicit dependency matrix, including the
  integration wiring/port direction this ADR deliberately leaves open.
- **Phase 1** implements that matrix as `import-linter` + AST contracts in CI. A forbidden
  cross-domain import must fail the build (Phase 1 DoD).
- Layer *content* rules that a linter cannot see — no business rule in a view or task body, no
  vendor type in a public contract, no object authorization in an interface, no provider identity
  column on a domain entity — are review-checklist items, carried in §16 of the
  [Phase 0 item 2 artifact](../architecture/phase-0/02-four-layer-architecture.md). Anything
  proposed against them needs a new ADR.
- Security-relevant halves of this decision (actor-scoped selectors, webhook verification at the
  boundary, no trusted client input) are additionally covered by the security and concurrency test
  suites named in master `# 24`.
