# ADR-0016 — No application read replica at launch: primary is the default read source, and a future replica is a per-path, evidence-gated opt-in

- **Status:** Accepted — Frozen
- **Date:** 2026-09-06
- **Phase:** 0 — Architecture Freeze
- **Supersedes:** —
- **Related:** [ADR-0004](0004-four-layer-modular-monolith.md) §10 (the use case owns its
  transaction),
  [ADR-0007](0007-place-order-atomic-idempotent-boundary.md) (placement reads that feed a durable
  write),
  [ADR-0008](0008-storefront-listing-projection.md) (the projection is the storefront's serving
  source; a miss never falls back to OLTP joins),
  [ADR-0014](0014-storefront-projection-convergence.md) §3 (the builder's **authoritative-read
  contract**, which named this decision as item 15's),
  [ADR-0015](0015-postgresql-command-idempotency.md) (the idempotency claim and ownership reads),
  [item 12](../architecture/phase-0/12-source-version-guarded-upsert.md) CB10–CB14,
  [item 14](../architecture/phase-0/14-mvp-later-module-marking.md) §22 (read replica =
  `INFRASTRUCTURE GATE`),
  [item 15](../architecture/phase-0/15-adr-closure.md) (the closure artifact, its failure matrix and
  its checks),
  master `# 5` principle 23, `# 2` stack table, `# 3` "Реплика — explicit opt-in", `# 22.7`,
  `# 22.8`, `# 22.9`, `# 23.5`, `# 25` Phase 10

## Context

The master states the position in four places — principle 23, the stack table ("not required at the
start; explicit opt-in after measurement / for HA"), the `# 3` architecture note forbidding a global
"all SELECT → replica" router, and `# 22.8`'s replica policy with its four mandatory metrics — and
`# 25` Phase 10 lists the read replica among the optional infrastructure gates. Item 14 §22
classified it as `INFRASTRUCTURE GATE` and left the decision here. ADR-0014 §3 imposed an
authoritative-read contract on the projection builder and explicitly recorded that it is **not** the
platform-wide replica decision, which "remains item 15's".

So the material is all present, and yet nothing is decided. Three things are genuinely open, and each
resolves badly by default:

1. **What "no replica" actually forbids.** Read as "no PostgreSQL standby may exist", it would
   collide with the same stack table's "for HA" clause and with `# 23.5`'s backup/PITR obligations —
   and an ADR that contradicts the operational plan gets quietly ignored. Read as "no application
   read traffic goes to a lagging copy", it is precise, enforceable, and orthogonal to HA.
2. **What the launch build must contain.** Without a decision, a database router, a `replica` alias
   and a sticky-primary middleware get written "so it's ready" — infrastructure that is untested
   because it is unused, and that makes the first accidental `using("replica")` a silent correctness
   bug rather than an import error.
3. **What opening the gate later would mean.** The cheapest possible implementation of a read replica
   is a global router keyed on SQL verb, which the master forbids in prose but which nothing enforces.
   If the rule is not frozen now, it will be argued at the moment of maximum load pressure, which is
   the worst moment to argue it.

Alternatives considered and rejected: enabling a replica at launch for storefront reads (rejected —
the storefront already has its own serving projection, ADR-0008, so the replica would add a
consistency class without removing a query; and item 14's gate is measurement-driven, not
pre-approved); building the routing machinery now and leaving it disabled (rejected — item 14's
`NF10`/A128 forbid settings-gated present-but-unreachable code, and unused routing is untested
routing); forbidding physical standbys outright (rejected — see §2).

## Decision

**The launch application sends no read traffic to a PostgreSQL replica. Primary is the default and
current read source. A future application read replica is a measured, per-read-path, explicit
opt-in with lag safety and read-your-own-writes; an HA standby is a separate concept and is not
affected.**

### 1. The launch baseline

The launch application uses **PostgreSQL primary** as its application read and write database. There
is **no application read-replica routing at launch**:

- no request path intentionally selects a replica;
- no global ORM database router;
- no default read alias pointing at a replica;
- no replica-aware repository, selector or manager is required of any MVP module;
- no sticky-primary implementation is built merely to support a replica that is not used.

Primary is both the correctness source and the default source. This follows master `# 5` principle
23 and `# 22.8`, and implements item 14 §22's `INFRASTRUCTURE GATE` classification: the gate is
**closed**, and this ADR does not open it.

### 2. A read replica and an HA standby are different things

```text
read replica   = the application deliberately sends read traffic to a concurrently lagging copy
HA standby     = a copy the application never reads; if promoted, it becomes the primary
```

**This ADR decides only the first.** A provider-managed or physical streaming standby may exist for
backups, PITR, disaster recovery and failover — master `# 2`'s "for HA" clause and `# 23.5`'s
recovery obligations depend on that being allowed. What it may not be is an application read target.
A promoted standby is not a replica read: it *is* the primary, and the application's consistency
class is unchanged.

Failover topology, replication mode, promotion procedure and RPO/RTO targets are **not** designed
here; they are operations' work, and nothing in them opens the gate of §1.

### 3. Why not at launch

Recorded from the master rather than invented: the target scale (`# 2`: tens of thousands of
products/SKUs, tens of thousands of sessions per day) is expected to fit an optimized PostgreSQL
plus the listing projection plus cache; the storefront's hot path already has its **own** serving
read model (ADR-0008), so the largest read volume is not a candidate for a replica in the first
place; Redis and the CDN absorb disposable read traffic (`# 22.7`); a replica adds a second
consistency class, sticky-primary complexity and stale-read incidents before any measurement says
they buy anything; and query budgets, indexes and plans must be *fixed* rather than hidden behind
extra read capacity (`# 22.9`, `# 5` principle 21).

This is a simplicity-and-correctness decision at this scale, not a claim that read replicas are bad.

### 4. The global router is forbidden permanently, not just at launch

```text
"all SELECT → replica"   — forbidden, now and after the gate opens
```

No model-level or connection-level router may route by SQL verb, by model, by app label or by
request method. A read path reaches a replica only by **opting in explicitly**, and no domain
selector, application selector or public contract may silently change its consistency class because
infrastructure was enabled underneath it. Consistency class is a property of a read path's
contract, never a deployment side effect.

### 5. Reads that are never replica candidates

Independently of whether the gate ever opens, the following require primary / current authoritative
state:

- `place_order` preparation and in-transaction revalidation (ADR-0007 §1);
- inventory reservation and stock correctness;
- pricing, promotion and coupon validation used for a durable write;
- payment state and reconciliation decisions;
- the idempotency claim, fingerprint comparison and principal-ownership check (ADR-0015 §4, §7);
- actor, permission and ownership state used for an authorization decision (§9);
- Outbox relay claiming;
- Inbox / consumer-delivery dedupe, identity and state transitions;
- webhook durable ingest;
- every write and every lock-taking operation;
- **any read that immediately participates in a correctness write**;
- **`application/storefront`'s projection-builder source reads** — item 12 CB10–CB14 and ADR-0014 §3
  already forbid finalizing a candidate field from an asynchronously lagging copy. **Opening this
  gate later does not weaken that rule by one clause.**

This is a classification by correctness need, not a claim that every display read must forever use
primary: an ordinary, stale-tolerant, high-volume display read is exactly the kind of path §6 and §7
exist to admit, one at a time.

### 6. The future admission gate is evidence-based

An application read replica may be enabled only after a **recorded evidence review** demonstrating a
specific bottleneck that a replica actually relieves. The required evidence *categories* are frozen;
the numbers are not:

- measured primary CPU / I/O pressure attributable to reads;
- connection or pool pressure (and whether pool/query work resolves it without a replica);
- query budgets already satisfied (`# 5` principle 21) — a replica may not substitute for an
  unfixed N+1 or an unindexed plan;
- indexes and query plans reviewed for the candidate path;
- cache and projection strategy already applied to that path;
- evidence that the candidate read path contributes **material** primary load;
- the tolerated staleness of that path, stated explicitly.

**No numeric threshold is frozen in Phase 0.** Item 15 freezes the criteria categories; the values
belong to the gate's own review, under master `# 25` Phase 10.

### 7. Admission is per read path, never per module

Before any single read path is routed to a replica, the following is recorded for that path:

```text
path / use case
owner
maximum acceptable staleness, in semantic terms
what happens to this path immediately after a related write
fallback-to-primary rule
lag safety rule
metrics
tests
```

No package, domain or application module gains replica access because one of its selectors is safe.
One module may legitimately contain both primary-only and replica-eligible selectors; that
distinction is a property of each selector's contract and changes **nothing** in the dependency
architecture — no matrix cell, no import edge, no layer rule. Concrete API signatures and database
aliases are not designed here.

### 8. Read-your-own-writes, lag safety and outage

If the gate opens:

- **Read-your-own-writes / sticky-primary is required.** After an operation that writes state, any
  subsequent read whose UX or API contract expects that write remains on primary until the
  applicable consistency condition or causal window is satisfied. The owner of each admitted path
  defines that window. The cookie format, TTL, middleware, session field and routing code are
  **not** frozen here.
- **Lag safety is required and measured**, using master `# 22.8`'s four metrics: replication/replay
  lag, stale-read incidents, sticky-primary hit rate, fallback-to-primary count. When lag exceeds an
  admitted path's stated tolerance, **that path becomes ineligible and reads primary** (`# 23.5`).
  Known-too-stale data is never served merely to protect primary capacity. Thresholds are the gate's
  implementation decision.
- **A replica outage is never a correctness outage.** Correctness must always remain achievable from
  primary; replica use is capacity and acceleration, never truth. No write is blocked because a
  replica is down, and no primary-required read degrades to stale data. Whether one individually
  stale-tolerant high-volume display route sheds load or falls back to primary during an outage is
  that path's recorded gate policy. **At launch this case does not exist**, because no application
  read replica exists.
- **No transaction is split across sources.** A read on a replica followed by a write on primary is
  forbidden wherever correctness assumes that read participated in the write decision; any read
  feeding a local ACID write is primary/current-authoritative by definition (§5). This introduces no
  distributed-consistency assumption anywhere.

### 9. Security freshness is never traded for throughput

Authorization, ownership and current-account-state decisions do not read intentionally lagging data
where staleness could expose newly revoked access, miss an ownership transfer or revocation, or
accept stale account/security state. Public immutable reference data is a separate question that a
future gate review may evaluate on its own merits.

### 10. Out of scope of this ADR

Failover topology, replication mode, promotion procedure, RPO/RTO and backup/PITR design
(operations, `# 23.5`); numeric thresholds for lag, load, pool pressure or staleness (the gate's own
review); the concrete routing mechanism, database aliases, selector signatures, middleware and
cookie/session scheme should the gate open (that phase); which specific display paths would be
admitted first (that review); PgBouncer, OpenSearch and every other item 14 §22 gate, each of which
is a separate decision; and any change to item 12 CB10–CB14 / ADR-0014 §3, which this ADR does not
touch.

**This ADR changes no dependency-matrix cell, adds no import edge, extends no `core` submodule
allowlist, changes no public contract, and edits no accepted ADR.** L1–L21 stand unedited, and item
14's launch cut is applied, not reopened.

## Consequences

**Positive**

- The launch build has exactly one application database source, so "which copy did this read come
  from" is never a question during a checkout, payment or inventory incident.
- No untested routing machinery ships. The first accidental replica read is an error at build time
  rather than a silent stale-read bug in production.
- The global-router argument is settled while nobody is under load pressure, and settled
  permanently rather than only for launch.
- ADR-0014's authoritative-read contract stops being a local exception and becomes a consequence of
  a platform-wide default: the projection builder is safe today by construction, and stays safe
  through any future gate opening.
- The HA/backup plan is unobstructed: operations may run a standby without needing an exception to
  an architecture rule.
- Optimization pressure lands on query budgets, indexes and the projection — where the master wants
  it — instead of being absorbed by extra read capacity.

**Negative / accepted cost**

- **No read-scaling escape hatch on day one.** A load surprise must be met by query, index, cache or
  projection work, or by vertical capacity, and the replica option costs an evidence review before
  it can be used. Accepted: at the stated target scale that work is required anyway, and a replica
  added in a hurry is exactly how a stale-read incident reaches checkout.
- **Per-path admission is more work than a router.** Each admitted path costs a staleness statement,
  a fallback rule, metrics and tests. Accepted, and it is the point: the cheap alternative is the
  one the master forbids.
- **Sticky-primary complexity is deferred, not avoided.** Whoever opens the gate inherits it in
  full. Accepted: deferring it keeps the launch build simpler, and the requirement is frozen here so
  it cannot be skipped later.
- **A distinction operators must hold.** "We have a standby but no read replica" reads as a
  contradiction until §2 is read. Mitigated by stating it in the decision itself rather than in a
  footnote.

**Enforcement**

- The classification detail, the 18-row failure matrix and the check list are carried by the
  [item 15 artifact](../architecture/phase-0/15-adr-closure.md) §9, §10 and §13.
- **Phase 1** configures a primary-only application database and adds no replica alias and no
  router; **Phase 10** owns the gate itself, under master `# 25` and item 14 §22.
- **Static checks A139–A145:** no replica database alias in the launch configuration; no global
  router class; no `using(...)`/`db_manager(...)` naming a replica; no replica read on a
  correctness path (§5); the projection builder's source reads authoritative (already A98's
  neighbour); a replica-eligible read path identifiable only by explicit per-path opt-in.
- **Contract tests C191–C198:** launch reads resolve to primary; a read immediately after a write
  observes it; a simulated lagging source cannot become a projection candidate or an authorization
  decision; a replica-unavailable fixture leaves every correctness path working.
- **Review checks V156–V163:** "all SELECT → replica" in any form; a replica alias introduced "for
  later"; an HA standby described or used as an application read replica; a stale-tolerant claim
  asserted without a staleness statement, fallback rule or metric; a gate opened without a recorded
  evidence review; security or ownership freshness traded for throughput.
- Any change — enabling application replica reads at launch, a global router, a replica read on a
  §5 path, or weakening the read-your-own-writes / lag-safety requirements — requires a new ADR
  superseding this one.
