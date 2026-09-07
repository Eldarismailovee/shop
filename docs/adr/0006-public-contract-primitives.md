# ADR-0006 — `core` primitives of the public contract: the actor and the structural error categories

- **Status:** Accepted — Frozen
- **Date:** 2026-09-04
- **Phase:** 0 — Architecture Freeze
- **Supersedes:** —
- **Related:** [ADR-0004](0004-four-layer-modular-monolith.md),
  [ADR-0005](0005-dependency-and-integration-wiring.md),
  [Phase 0 item 4 artifact](../architecture/phase-0/04-domain-public-contract.md),
  [Phase 0 item 3 artifact](../architecture/phase-0/03-dependency-matrix.md),
  master `# 4.1`

## Context

ADR-0004 §6 froze that object-level authorization follows state ownership and is reached through the
owner's policy and actor-scoped selector. ADR-0005 §1 froze `core` submodule access as an
**allowlist per package family**, precisely so that "everyone may import `core`" could never become
the hole through which a family acquires a capability it should not have.

Phase 0 item 4 makes the domain public contract uniform. Two of its rules need a `core` primitive
that does not exist yet, and each grants a package family access to it:

- **the actor.** Item 4 requires that every operation on private domain state take an explicit,
  mandatory, non-optional authorization subject as its first parameter, and that privileged access
  use an explicit system context rather than `actor=None`. That type is constructed by `interfaces`,
  restored by `tasks`, passed through `application`, and consumed by `domains`. Four families must
  name one type, so the type is domain-independent and cannot live in any of them.
- **the public error categories.** Item 4 freezes that every *expected* domain failure crossing
  `public.py` is a domain-owned error carrying a stable structural category, so that a caller can
  branch on `NotFound` / `NotAllowed` / `Conflict` / `InvalidState` / `Validation` without
  enumerating every domain's class names. Without a shared marker, a transport mapper must list each
  domain's errors by hand and a newly added domain silently maps to a 500.

Item 4 first recorded these as mere specification of ADR-0004. That was wrong on one point that
matters: ADR-0005 froze the **allowlists**, and item 4 extends two of them — it puts an
authorization primitive in front of `interfaces/*`, and it introduces a `core` module that four
families read. Extending a frozen allowlist is exactly the class of change ADR-0005 exists to make
deliberate. Hence this ADR.

The alternatives considered were: putting the actor in `interfaces` (rejected: domains would import
upward), duplicating an actor per domain (rejected: no common type at the four call sites, and
`application` could not pass one through), a concrete shared business-error hierarchy in `core`
(rejected: gives `core` business vocabulary, against the ADR-0004 §2 admission test), and per-domain
categories with no shared root (rejected: the silent-500 failure above).

## Decision

### 1. The authorization subject is a `core` primitive

A domain-independent authorization-subject type — conceptually `core.actor`, carrying the actor and
an explicit privileged/system variant — lives in `core`. It passes the ADR-0004 §2 admission test:
domain-independent, no business or vendor vocabulary, more than one consumer, mechanism-shaped.

**Allowed consumers, extending the ADR-0005 §1 allowlists:**

| Family | Access | Reason |
|---|---|---|
| `domains/*` | ALLOW | Consumes the actor in actor-scoped selectors, policies and commands (ADR-0004 §6). |
| `application/*` | ALLOW | Passes it through a cross-domain workflow and composes authorization decisions from owning modules. |
| `interfaces/*` | **ALLOW — this is the allowlist extension** | Constructs the actor after authentication (ADR-0004 §6). It is a transport/security primitive of the same class as `core.security`. |
| `tasks/*` | ALLOW | Restores the actor from the message so a background command is authorized like any other (ADR-0004 §9). |
| composition root (`config/`) | ALLOW to *pass* values | It may hand a system context to a bootstrap-time operation. It owns **no** actor semantics: no roles, no capability decisions, no policy. |
| `integrations/*` | **FORBID** | An adapter answers no authorization question. It receives vendor-neutral port edge types (ADR-0005 §6.3); an authorization subject is not one. Membership in `core` grants an adapter nothing — the allowlist, not the package, decides. |
| `**/migrations/**` | FORBID | Migrations consume no runtime authorization type (ADR-0005 §8). |

This does **not** weaken ADR-0005: `core.outbox` and `core.idempotency` remain forbidden to
`interfaces/*` (L13), and `integrations/*` keeps its narrow pure-Python `core` subset (L10).

Exact module name, class names, fields, and whether the actor carries roles, capabilities, a session
or a tenant remain **Phase 1 / the authentication phase**. What is frozen here is where the type
lives and who may name it.

### 2. The public error categories are a closed `core` taxonomy

A small structural error taxonomy lives in `core` — conceptually a root `DomainError` plus
`NotFound`, `NotAllowed`, `Conflict`, `InvalidState`, `Validation`. These are **markers**: no
messages, no business vocabulary, no domain names, no vendor concepts, no HTTP status, no transport.
Every *concrete* error stays owned by its domain and inherits its domain root plus one category.

The taxonomy is **closed by rule**: adding a category requires an ADR; adding a business error to
`core` is forbidden outright.

**Allowed consumers, extending the ADR-0005 §1 allowlists:**

| Family | Access | Reason |
|---|---|---|
| `domains/*` | ALLOW | Defines its concrete public errors over the categories. |
| `application/*` | ALLOW | Maps a category to workflow behaviour (compensate, abort, surface). |
| `interfaces/*` | **ALLOW — this is the allowlist extension** | Maps a category to transport behaviour. This mapping is the reason the taxonomy exists. |
| `tasks/*` | ALLOW | Classifies a failure as permanent vs retryable where the category makes that decision correct. |
| composition root (`config/`) | ALLOW | May install a shared translation/handler at bootstrap; it defines no error semantics. |
| `integrations/*` | **FORBID** | An adapter expresses failure through the vendor-neutral contract of the `application/<a>/ports.py` it implements. It never raises a domain public error, and never interprets one: doing so would put business meaning in an anti-corruption layer (ADR-0004 §8, ADR-0005 §6). |
| `**/migrations/**` | FORBID | Migrations carry no runtime business error contract. |

`core.errors` is therefore **not** open to every package family. The two `FORBID` rows are the
substance of the decision, not a footnote.

### 3. What this ADR does not decide

Out of scope: the concrete module/class names of either primitive; the actor's fields and permission
model; the error taxonomy's payload fields beyond "structural, no secrets, no PII"; the rest of the
item 4 template (façade shape, DTO style, command/selector semantics, transaction composability,
compatibility policy) — that is specification of ADR-0004 and ADR-0005 and needs no ADR; and the
distinction between an expected domain failure and a technical fault, which item 4 §13 owns and this
ADR neither widens nor narrows.

ADR-0005's decisions stand unedited. This ADR **extends** two allowlist rows and states the two new
`FORBID` rows explicitly; it rewrites nothing in ADR-0005.

## Consequences

**Positive**

- The actor-scoped contract of ADR-0004 §6 becomes expressible: four families can name one type, so
  "the actor is mandatory and explicit" is checkable rather than aspirational.
- A transport boundary maps five categories instead of every domain's error names; a new domain is
  mapped correctly on the day it is created.
- Domains keep ownership of their business errors, and `core` keeps its admission test intact.
- `integrations/*` stays an anti-corruption layer with no authorization and no business-error
  vocabulary, in either direction.
- The allowlist extension is written down once, in the artifact family that owns allowlists, instead
  of being discovered later as an undocumented `core` import in a view.

**Negative / accepted cost**

- Two more `core` submodules with per-family rules to remember, against ADR-0005's own complaint that
  the allowlist is bookkeeping. Accepted: the alternative is an unwritten exception.
- The `core` error root is a shared type that every domain's errors inherit, which superficially
  resembles the global hierarchy ADR-0004 §2 warns about. Accepted: the taxonomy is closed at six
  business-free classes, and the closure is the rule that keeps it from growing into one.
- Freezing the *location* while deferring the *fields* means Phase 1 still has real design work on
  the actor. Accepted: the permission model depends on authentication decisions that Phase 0 cannot
  make responsibly.

**Enforcement**

- **Phase 1** adds the two modules to the per-family `core` allowlist contracts in `import-linter`,
  including the negative rules: `integrations/* → core.actor` and `integrations/* → core.errors` fail
  the build, as does any `**/migrations/**` use of either.
- An AST check verifies that every concrete public error inherits a domain root plus exactly one
  category (item 4 §19.1, A23), and that no public callable declares the actor with a default or an
  `Optional` annotation (A19).
- That the composition root passes actor values without owning actor semantics, and that an adapter
  reports failure through its port's edge types rather than a domain error, are review items
  (item 3 §15.3, V-series).
