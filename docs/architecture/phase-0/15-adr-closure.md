# Phase 0 — Item 15: ADR closure and the Phase 0 Architecture Freeze

- **Status:** DONE / FROZEN
- **Date:** 2026-09-06
- **Phase:** 0 — Architecture Freeze
- **ADRs:** **two required and created** —
  [ADR-0015](../../adr/0015-postgresql-command-idempotency.md) (generic command idempotency),
  [ADR-0016](../../adr/0016-no-application-read-replica-at-launch.md) (no application read replica at
  launch). The other three requirements of master `# 25`'s Phase 0 ADR line are already covered by
  accepted ADRs; §3–§5 record the audit rather than assuming it.
- **Related:** ADR-0001…ADR-0016, items 1–14, master `# 5` principles 3, 21, 23, `# 5.2`, `# 5.4`,
  `# 11.4`, `# 20.4`, `# 20.5`, `# 22.7`, `# 22.8`, `# 22.9`, `# 23.5`, `# 25` Phase 0 / Phase 1 /
  Phase 10, `# 26`

---

## 1. Purpose

Master `# 25`'s Phase 0 checklist closes with one line:

> `[ ] ADR: listing projection, idempotency, no replica launch, module boundaries, event versioning.`

Fourteen items have since been frozen, and most of that line was satisfied along the way — each time
by an ADR written for the item that actually needed it, not by a checklist sweep. Item 15 does three
things and nothing else:

1. **audits** the five-way requirement against the accepted ADR corpus, so the closure is evidence
   rather than assertion (§2–§7);
2. **fills the two real gaps** with exactly two ADRs (§8, §9);
3. **closes Phase 0** — a final dependency/decision audit, the DoD verification, and the Phase 1
   handoff (§11–§15).

### 1.1 What this item does **not** do

It creates no Python package, module, Django app, model, migration, setting, database router, Celery
configuration, dependency or SQL. It edits no accepted ADR. It reopens no frozen item: item 14's
launch cut, item 13's source set, item 12's convergence protocol, item 11's primitives and items
2–10's boundaries stand exactly as frozen. It opens no infrastructure gate, and it does not claim
that any check is implemented — every `A`/`C`/`V` identifier in this corpus is an obligation on a
later phase.

---

## 2. The original five-ADR coverage matrix

| Master requirement | Covered by | New ADR needed? |
|---|---|---|
| **listing projection** | [ADR-0003](../../adr/0003-catalog-boundary-vs-storefront-projection.md) §3 (the projection is *not* catalog's), [ADR-0008](../../adr/0008-storefront-listing-projection.md) (ownership, grain, same-variant correctness, rebuildability, no request-time OLTP fallback), [ADR-0014](../../adr/0014-storefront-projection-convergence.md) (convergence/concurrency: per-row CAS over a whole-candidate rebuild) | **No** — §3 |
| **module boundaries** | [ADR-0004](../../adr/0004-four-layer-modular-monolith.md) (the four layers, the `core` admission test, transaction ownership), [ADR-0005](../../adr/0005-dependency-and-integration-wiring.md) (the full import matrix, ports, the composition root), [ADR-0006](../../adr/0006-public-contract-primitives.md) (the `core` primitives the public contract needs) | **No** — §4 |
| **event versioning** | [ADR-0009](../../adr/0009-event-contract-versioning.md) (producer-owned contracts, immutable published versions, exact-version consumers, quarantine) | **No** — §5 |
| **idempotency** | [ADR-0007](../../adr/0007-place-order-atomic-idempotent-boundary.md) §2 (placement **behaviour**), [ADR-0009](../../adr/0009-event-contract-versioning.md) §7 (message identity + per-consumer effect idempotency) — **the generic command mechanism was missing** | **Yes — ADR-0015** (§6, §8) |
| **no replica launch** | master `# 5` principle 23, `# 2`, `# 3`, `# 22.8`, `# 25` Phase 10; item 14 §22 classified it `INFRASTRUCTURE GATE` and deferred here; ADR-0014 §3 explicitly named it item 15's — **no ADR existed** | **Yes — ADR-0016** (§7, §9) |

Two gaps, two ADRs. No redundant ADR is written to make the count symmetrical, and §3–§5 state the
positive case for each non-creation rather than merely asserting coverage.

---

## 3. Why listing projection needs no new ADR

The master's phrase names one subject; the corpus decides it in three separable places, and every
part of the subject has an owner:

| Question | Decided by |
|---|---|
| Does the projection live in `catalog`? | **No** — ADR-0003 §3 (no price, no stock, no ERP identity, no projection in catalog) |
| Who owns and writes it? | ADR-0008 — `application/storefront`, sole owner **and** sole writer, with every alternative home rejected by name |
| What is its grain, and are its facets correct? | ADR-0008 — `Product × Language` with the per-variant satisfier structure that makes variant-scope conjunctions exact |
| Is it ever commercial or security truth? | ADR-0008 — no: derived serving read model, eventually consistent, never an authorization basis, no request-time OLTP fallback |
| Can it be rebuilt? | ADR-0008 — full rebuildability from OLTP, events as acceleration only |
| What does the read path look like, and what does it return? | ADR-0008 + item 7 (the DTO contract, which item 7 §1 recorded as needing no ADR of its own) |
| How do concurrent updates converge without losing a source? | **ADR-0014** — application-owned per-row CAS over a whole-candidate rebuild, with master `# 7.6`'s producer-supplied `source_version` and its `>` predicate evaluated and rejected |

A fourth ADR here would either restate ADR-0008 or contradict it. The one thing that *was* still open
after ADR-0008 — the stale-update mechanism, deferred by item 6 PU4/PU5 — is exactly what ADR-0014
decided. **Requirement satisfied; nothing created.**

---

## 4. Why module boundaries need no new ADR

| Question | Decided by |
|---|---|
| What layers exist, what may each know, and which way do dependencies point? | ADR-0004 |
| What is admitted into `core`? | ADR-0004 §2's admission test |
| Who owns a cross-domain operation? | ADR-0004 §4 — exactly one `application/` module |
| Who owns a transaction, and is a local flow a saga? | ADR-0004 §10 — the use case; no |
| Exactly which package family may import which, cell by cell? | ADR-0005 — the full `ALLOW`/`PUBLIC ONLY`/`PORT ONLY`/`SELF ONLY`/`FORBID`/`SPECIAL CASE` matrix, L1–L21 |
| Where do outbound ports live, who binds adapters, and who injects them? | ADR-0005 §2/§7 — `application/<a>/ports.py`; the single composition root in `config/`; entry points receive, never locate |
| What may cross a domain boundary as a value? | Item 4's `public.py` template (frozen with no ADR of its own) + **ADR-0006** for the two `core` primitives that template required |

The boundary rules are not only stated but **classified for enforcement** — item 3 §15 assigns every
rule to `import-linter`, AST/static analysis, or review — which is the form the master's Phase 0 DoD
actually needs. **Requirement satisfied; nothing created.**

---

## 5. Why event versioning needs no new ADR

ADR-0009 decides the whole of it: `event_type` stability and naming, an integer `schema_version`
starting at `1` and never reused, **immutability of a published version** (an additive optional
field is a new version), the eleven breaking-change triggers, the `same fact → new version` /
`different fact → new event_type` split, **exact-version consumer support** with registered
upcasters and no best-effort decoding, the consumer-first migration sequence, and unknown /
unsupported / invalid → **durable quarantine + alert**, never silently coerced or marked HANDLED.

Its neighbours are decided too and do not reopen it: ADR-0010 owns routing, terminal states and
replay (and freezes that a routing change never bumps `schema_version`); ADR-0011 fills the reserved
envelope extension point without touching a message-contract rule; ADR-0013 types `event_id`.

One boundary is worth stating explicitly here, because §6's gap sits next to it: ADR-0009 §7 covers
**message-delivery** identity and per-consumer effect idempotency. That is not the same subject as a
user- or system-invoked **command** — which is why the idempotency line of the master's checklist was
still open while the event line was not. **Requirement satisfied; nothing created.**

---

## 6. The generic command-idempotency gap

What existed:

- **ADR-0007 §2** froze placement behaviour — claim and completion inside the placement transaction,
  a rollback leaving no claim, committed-record resolution as replay / `Conflict` / `NotAllowed`,
  principal-scoped replay — and closed with "the `IdempotencyKey` schema, retention specifics and the
  generic idempotency ADR remain out of scope (Phase 0 item 15)".
- **Item 5 ID1–ID7** carried the same behaviour in artifact form, and ID7 deferred retention and
  schema here.
- **ADR-0009 §7** covered the asynchronous side, explicitly as a different mechanism.

What was missing, and would have been decided ad hoc by whichever phase wrote the second command
scope:

1. the **mechanism** as a platform rule rather than as one use case's behaviour — master `# 20.4`
   already names five scopes, four of which belong to phases that have not started;
2. the meaning of master `# 5.2`'s **`processing / completed / failed`** state column, whose literal
   reading requires a separately committed claim and therefore contradicts ADR-0007 §1;
3. whether **`response_body_json`** is mandatory truth or one optional result strategy;
4. **retention** semantics — and the honesty rule that expiry ends the replay promise;
5. the **separation** of command idempotency from the four neighbouring duplicate-protection
   mechanisms, which is stated in master prose but never frozen as a rule;
6. **which workflows the mechanism even applies to** — master `# 20.4`'s scope names are illustrative,
   and `payment.initialize` labels a workflow whose provider step is already frozen as post-commit
   external I/O (ADR-0007 §3) routed to `ext.payments` rather than `core.payments` (ADR-0010). Without
   an explicit local/provider split, a reader could take a scope name as licence to claim a provider
   HTTP call inside a database transaction.

Each is a correctness or privacy decision with an attractive wrong answer. Hence ADR-0015.

---

## 7. The no-replica-at-launch gap

What existed: master `# 5` principle 23, the `# 2` stack table, the `# 3` note forbidding a global
router, `# 22.8`'s policy and metrics, `# 25` Phase 10's gate, item 14 §22's `INFRASTRUCTURE GATE`
classification, and ADR-0014 §3's narrowly-scoped authoritative-read contract for the projection
builder — which stated in as many words that the platform-wide decision "remains item 15's".

What was missing: the decision itself, and with it three things master prose does not settle —
whether "no replica" forbids a physical HA standby (it does not), whether the launch build should
contain unused routing machinery (it must not, and item 14 NF10/A128 already forbid settings-gated
unreachable code), and what opening the gate later would require. The master requires a Phase 0 ADR
for this precisely because the cheap implementation — a global SELECT router — is the one it forbids,
and that argument otherwise happens under load pressure. Hence ADR-0016.

---

## 8. ADR-0015 summary

**[ADR-0015](../../adr/0015-postgresql-command-idempotency.md) — Command idempotency: a
PostgreSQL-canonical `(scope, key)` claim committed with the effect it protects.**

Decision, in one paragraph:

> Command idempotency is durable PostgreSQL state identified by `(scope, key)` under a database
> unique constraint, bound to the claiming principal and to a semantic request fingerprint. For a
> local ACID command the claim, the commercial effect and the replayable completion commit together;
> a rollback leaves no durable claim, so the key is simply unused again. Redis is disposable
> anti-storm acceleration only, and never decides whether a command executed twice.

The frozen points:

| # | Rule |
|---|---|
| IK1 | PostgreSQL is the correctness truth; Redis loss/flush/eviction/outage changes no execution, replay, `Conflict` or ownership decision (§2). |
| IK2 | `UNIQUE (scope, key)`. `scope` is platform-owned, bounded, stable, never client input; `key` is opaque, bounded, carries no authorization, no timestamp and no ordering, and is **not** globally unique across scopes (§3). |
| IK3 | A committed row is bound to its claiming principal; replay is principal-scoped, a different principal gets an ownership refusal and learns nothing, and `NULL` never means "anybody" (§4). |
| IK4 | The request fingerprint is a cryptographic digest over the **canonical semantic** command input: deterministic, discriminating, canonicalization-stable, computable without retaining the raw body, and never containing a secret (§5). The field list is **per scope**; `place_order`'s stays item 5 ID3's. |
| IK5 | **Applicability:** for a command scope whose protected durable effect is **one local ACID transaction**, claim + effect + completion are that one transaction. No separately committed `processing` row is required or permitted as a correctness device; no two-transaction pattern (§6). |
| IK5a | **The local / provider split.** A provider network operation is **never** the effect IK5 commits atomically — no transaction spans a network call, and no local `IdempotencyKey` makes an external provider operation atomic. A provider-facing workflow has a local layer (which may be a scope under IK5) and a provider layer (provider idempotency key + state machine + reconciliation, ADR-0007 §3 / ADR-0010). Master `# 20.4`'s scope names are **illustrative**: a name proves nothing about shape, `payment.initialize`'s local durable command — if any — is the payments phase's to identify, and a command needing one idempotency contract across multiple commits or an external effect requires its own ADR rather than claiming this one (§6). |
| IK6 | The generic mechanism has **no durable `failed` state**. A rolled-back attempt — validation, business rejection or technical fault — leaves nothing, so an accidental failure can never reserve a key. A scope wanting a durable rejected outcome must state that behaviour and its reason in its own contract (§6). |
| IK7 | Contenders serialize on the durable uniqueness constraint — never an application mutex, never Redis. After a winner commits, §4's three-way resolution applies; after a rollback, the key is claimable normally. A uniqueness race never surfaces as duplicate commerce (§7). |
| IK8 | Commit ambiguity (COMMIT succeeded, response lost) leaves the operation committed; a same-key retry replays and **no compensation is attempted** (§8). |
| IK9 | Replay is a **bounded semantic result** — result kind, resource `PublicId`, a bounded status snapshot where needed — reconstructed into a transport response by the interface. `response_body_json` is one optional per-scope strategy, never universal truth; no cookies, headers, credentials or unbounded JSON are stored; heavy result material is not read on the claim path (§9). |
| IK10 | Retention is explicit per scope, at least the supported retry window, ≥ 24 h for HTTP commands, longer for financial ones, bounded and purgeable only after the guaranteed window. **Expiry ends the replay promise**, and advertised retry guarantees must agree with retention (§10). |
| IK11 | Idempotency ≠ business uniqueness. A permanently single-use rule lives in a domain `UNIQUE`/state machine; deleting an expired row never makes such an operation repeatable (§11). |
| IK12 | `IdempotencyKey` does **not** replace Inbox/`EventId` identity, provider `external_event_id` dedupe, provider outbound idempotency keys, or domain constraints. An `EventId` is never a command key, and no handler is forced through `IdempotencyKey` merely for being a handler (§1, §12). |
| IK13 | Local command idempotency and outbound provider idempotency are separate layers: a provider key never replaces local truth, a provider response never decides whether the local `Order` exists, and ambiguity is resolved by status lookup/reconciliation (§12). |
| IK14 | Key ≠ authorization; fingerprint ≠ authentication; no credential in fingerprint or result material; logs use scope + redacted/hashed key where a scope treats key values as sensitive (§13). |

### 8.1 The `IdempotencyKey` lifecycle, as frozen

```text
request arrives
  → canonicalize semantic input → fingerprint
  → (optional) Redis anti-storm short-circuit                 [never authoritative]
  → BEGIN
       INSERT claim (scope, key, principal, fingerprint)      [uncommitted; serializes contenders]
       … the protected commercial effect …
       write the bounded semantic result
     COMMIT                                                   [claim + effect + result, atomically]
  → response

rollback anywhere before COMMIT   → no row at all; key unused again
COMMIT then lost response         → operation stands; same-key retry replays; no compensation
retry, same principal, same fp    → replay of the bounded semantic result
retry, same principal, other fp   → Conflict
any principal that is not the owner → ownership refusal, no data, no existence disclosure
after retention expiry            → the key re-executes; the domain invariant is what still refuses
```

This is the lifecycle of a **local-ACID command scope**. Where a workflow also has a provider-facing
step, that step sits **after** this `COMMIT`, in its own use case, under the provider's idempotency
key and reconciliation — never inside the transaction above (IK5a).

### 8.2 Treatment of master `# 5.2`'s `processing / completed / failed` sketch

| Master value | Status in ADR-0015 |
|---|---|
| `processing` | **Refined.** Legal only as *uncommitted transaction-local* state — which is exactly what serializes a contender. Never a durable lifecycle stage, and never committed before the business effect. |
| `completed` | **Preserved in substance.** A committed row *is* the completed, replayable outcome, because completion and effect commit together (ADR-0007 §2 generalised). |
| `failed` | **Not adopted in the generic mechanism.** A rolled-back attempt leaves no row, so no accidental validation error can reserve a key forever. A scope may define a durable rejected outcome only explicitly, with a stated reason. |
| `response_body_json` | **Demoted to an optional per-scope strategy**, with §9's privacy and claim-path rules binding on any scope that uses it. |
| `resource_type` / `resource_public_id` | **Illustrative.** The semantic replay capability is frozen; the relation/storage shape is Phase 1's, with no polymorphic cross-domain FK and no internal bigint exposure. |
| `UNIQUE (scope, key)`, in-transaction claim, Redis-as-L1-only, ≥ 24 h retention | **Adopted verbatim** (master `# 5.2`, `# 5.4`, `# 20.4`, `# 20.5`). |

No published contract needs migration: no `IdempotencyKey` table exists yet, since Phase 0 creates
no code.

---

## 9. ADR-0016 summary

**[ADR-0016](../../adr/0016-no-application-read-replica-at-launch.md) — No application read replica
at launch: primary is the default read source, and a future replica is a per-path, evidence-gated
opt-in.**

Decision, in one paragraph:

> The launch application sends no read traffic to a PostgreSQL replica. Primary is the default and
> current source. A future application read replica is a measured, per-read-path, explicit opt-in
> with lag safety and read-your-own-writes; an HA standby is a separate concept and is unaffected.

The frozen points:

| # | Rule |
|---|---|
| RR1 | Launch baseline: no request path selects a replica, no global ORM router, no default read alias on a replica, no replica-aware selector required of any MVP module, and **no sticky-primary machinery built for a replica that is not used** (§1). |
| RR2 | **Read replica ≠ HA standby.** A managed/physical standby may exist for backups, PITR, DR and failover; it is simply never an application read target, and a promoted standby *is* the primary. Failover topology is not designed here (§2). |
| RR3 | The reasons are the master's: target scale, the storefront's own serving projection, Redis/CDN absorbing disposable reads, query budgets that must be fixed rather than hidden, and unnecessary sticky-primary complexity. Not a claim that replicas are bad (§3). |
| RR4 | **"All SELECT → replica" is forbidden permanently**, not only at launch. No router by SQL verb, model, app label or request method; no read path changes consistency class because infrastructure was enabled (§4). |
| RR5 | An enumerated set of reads is never a replica candidate — placement, inventory, pricing/promotions feeding a write, payment/reconciliation state, the idempotency claim and ownership check, actor/security state, Outbox relay claiming, Inbox dedupe and state, webhook ingest, every write and lock, any read that immediately participates in a correctness write, and **the item 12 projection builder's source reads** (§5). |
| RR6 | A future replica is admitted only after a **recorded evidence review** over frozen criteria *categories* — primary CPU/I-O pressure, connection/pool pressure, query budgets already met, indexes/plans reviewed, cache/projection already applied, material load contribution, explicit tolerated staleness. **No numeric threshold is frozen in Phase 0** (§6). |
| RR7 | Admission is **per read path**, recording path, owner, staleness semantics, post-write behaviour, fallback rule, lag-safety rule, metrics and tests. No module gains access wholesale; one module may hold both primary-only and replica-eligible selectors, and the dependency architecture does not change (§7). |
| RR8 | If the gate opens: read-your-own-writes / sticky-primary is **required** (window per path owner; no cookie/TTL/middleware frozen); lag safety is required and measured on master `# 22.8`'s four metrics; exceeding an admitted path's tolerance makes that path ineligible → primary; known-too-stale data is never served to protect capacity (§8). |
| RR9 | A replica outage is never a correctness outage: correctness always remains achievable from primary, no write is blocked, no primary-required read degrades to stale data. At launch the case does not exist (§8). |
| RR10 | No transaction is split across sources: a read feeding a local ACID write is primary/current-authoritative by definition, and no distributed-consistency assumption is introduced (§8). |
| RR11 | Security freshness is never traded for throughput — authorization, ownership and account-state decisions do not read intentionally lagging data (§9). |

### 9.1 What "no replica at launch" precisely means

```text
FORBIDDEN at launch:  application read traffic to a concurrently lagging copy;
                      a global/verb-based ORM router (forbidden permanently);
                      a replica alias, router or sticky-primary implementation shipped unused.

UNAFFECTED:           a provider-managed or physical streaming standby used for
                      backups, PITR, disaster recovery and HA failover — it receives
                      no application reads, and on promotion it becomes the primary.
```

---

## 10. Failure matrices

### 10.1 ADR-0015 — command idempotency (20 rows)

Columns: **Effect?** = may the protected commercial effect execute on this path — **Row?** = does a
durable `IdempotencyKey` row exist afterwards — **Outcome** = what the caller gets — **Fallback** =
what still protects the business if idempotency does not — **Commercial impact**.

| # | Case | Effect? | Row? | Outcome | Fallback | Impact |
|---|---|---|---|---|---|---|
| 1 | First use of a key | Yes, once | Yes (with the effect) | Success | domain invariants | None |
| 2 | Exact sequential retry, same principal | No | Yes (unchanged) | Replay of the bounded semantic result | — | None |
| 3 | Concurrent duplicate, same fingerprint | Once only; the contender never executes concurrently | Yes (one row) | Winner: success. Contender: replay after the winner commits | uniqueness constraint | None |
| 4 | Concurrent duplicate, **different** payload, same key | Once only | Yes (the winner's) | Winner: success. Contender: `Conflict` | uniqueness constraint | None — no second operation |
| 5 | Same key, **different principal** | No | Yes (owner's, untouched) | Ownership refusal; no data, no existence disclosure; security log | actor policy | None |
| 6 | Validation fails **before** the transaction | No | **No** | Business/validation error | — | None; key still unused |
| 7 | Business command rolls back after the claim insert | No (rolled back) | **No** | Business error | domain invariants | None; key still unused, retry re-executes |
| 8 | Technical DB failure before `COMMIT` | No | **No** | Technical fault, untranslated | — | None |
| 9 | `COMMIT` succeeds, response lost | Already committed | Yes | Retry replays; **no compensation** | — | None — one operation, one row |
| 10 | Redis unavailable | Yes, once | Yes | Normal (more durable work, no behaviour change) | PostgreSQL claim | None |
| 11 | Redis flushed between retries | No second effect | Yes | Replay, unchanged | PostgreSQL claim | None |
| 12 | Completed replay needs the stored result | No | Yes | Result reconstructed from bounded semantic material; heavy material read only here | — | None |
| 13 | Key expires after the guaranteed retry window | n/a | Row purged | A later same-key request is treated as new | domain invariants | None — the promise had already lapsed (IK10) |
| 14 | Re-submission after expiry hits a permanent domain `UNIQUE` | Attempted, refused by the domain | New row **not** committed (the transaction rolls back) | Business error from the owning domain | **the domain constraint — the point of IK11** | None |
| 15 | Duplicate **event** delivery arrives | Consumer effect once | Not applicable — no `IdempotencyKey` involved | ADR-0009 §7 identity + per-consumer effect idempotency | Inbox / domain state | None |
| 16 | Provider times out after the local commit | Local effect stands | Yes | Payment state converges by webhook/reconciliation | payment state machine | None commercially; payment state pending |
| 17 | Provider call retried with the **provider's** idempotency key | No new local effect | Unchanged | Provider-side dedupe; local truth untouched | `PaymentAttempt` state machine | None |
| 18 | A scope's replay result is heavy | No | Yes | Heavy column not selected on the claim path (master `# 20.5`) | — | None; a latency concern only |
| 19 | Canonicalization order changes, semantics identical | No | Yes | **Replay** — same fingerprint | — | None |
| 20 | Fingerprint material changes **materially** | No second effect under this key | Yes (unchanged) | `Conflict` | domain invariants | None — never a second operation |

Every commercial-impact cell is `None`. Rows 6–8 are the ones that motivated IK6: without them, an
ordinary validation error would durably reserve a key.

### 10.2 ADR-0016 — read replica (18 rows)

| # | State | Allowed route | Correctness impact | Fallback | Gate / metric action |
|---|---|---|---|---|---|
| 1 | **Launch** — no replica configured for application reads | Primary only | None — one source | n/a | Gate closed (RR1) |
| 2 | Primary healthy | Primary | None | n/a | Ordinary `# 22.9` observability |
| 3 | Primary load rises, no evidence review yet | Primary | None | n/a | **Gate stays closed**; query/index/cache/projection work first (RR6) |
| 4 | A global ORM router is proposed | **Rejected** | Would silently change every read's consistency class | n/a | RR4 — forbidden permanently; V156 |
| 5 | One explicitly stale-tolerant display path admitted later | That path only, after its record | None if RR7's record is complete | primary | Per-path opt-in; its own metrics/tests |
| 6 | Read immediately after a related write | **Primary** until the causal window closes | Would otherwise show pre-write state | primary | Sticky-primary / read-your-own-writes required (RR8) |
| 7 | Lag exceeds the admitted path's tolerance | **Primary** — the path becomes ineligible | Known-too-stale data never served | primary | `# 22.8` replication lag + fallback count; alert |
| 8 | Replica unavailable | Primary | **None** — replica is capacity, not truth | primary | Fallback-to-primary count; RR9 |
| 9 | A primary-required selector is accidentally routed to a replica | **Forbidden** | Would corrupt a correctness decision | primary | A142 static check; V158 |
| 10 | Projection builder attempts a replica read | **Forbidden** | Would break item 12 CB10–CB14 / ADR-0014 §3's safety premise | primary/authoritative | A143; C193; unchanged by any gate opening (RR5) |
| 11 | Auth / ownership read on a replica | **Forbidden** | Could accept revoked access or miss a transfer | primary | RR11; C194; V163 |
| 12 | A category/listing display read evaluated as a future candidate | Primary until admitted | None | primary | Needs RR6 evidence + RR7 record; note the projection already serves it |
| 13 | A managed HA standby exists, receives no application reads | Primary | None | n/a | Legitimate (RR2); not a replica |
| 14 | HA standby promoted to primary | The promoted node **is** primary | None architecturally | n/a | Operations' failover procedure; consistency class unchanged |
| 15 | Query-budget regression appears after a replica is enabled | Per each path's record | Budgets are CI invariants regardless | primary | Budget failure is a build failure (`# 5` principle 21); the replica excuses nothing |
| 16 | Cache miss | Primary (single-flight + stale fallback, `# 22.7`) | None — no cache is a correctness source | primary | Unchanged by this ADR |
| 17 | Replica returns an older but structurally valid row | Only on an admitted stale-tolerant path | Within that path's stated tolerance, else ineligible | primary | Stale-read incident metric (`# 22.8`) |
| 18 | Connection/pool pressure resolved by pool + query work | Primary | None | n/a | Gate stays closed — RR6 requires the replica to be the thing that actually relieves the bottleneck |

---

## 11. Interactions with items 5, 8, 9, 10, 11, 12 and 14

| Item | Interaction | Anything reopened? |
|---|---|---|
| **5** (`place_order`) | ADR-0015 **generalises** ADR-0007 §2 to every **local-ACID** command scope — not to a provider-facing workflow, whose post-commit provider step stays ADR-0007 §3's — and fills the schema/retention deferral of ID7. ID1–ID6 are restated, not altered; `place_order`'s fingerprint field list stays item 5 ID3's. ADR-0016 RR5 lists placement preparation and revalidation as primary-required, which is what ADR-0007 §1 already assumed. | **No.** |
| **8** (event registry) | ADR-0015 §1 keeps `EventId`/Inbox identity and per-consumer effect idempotency exactly as ADR-0009 §7 wrote them, and forbids collapsing them into the command table. No registry column, consumer-declaration attribute or envelope field is added. | **No.** |
| **9** (failure domains) | Ambiguous provider outcomes stay ADR-0010's (status lookup / reconciliation, never blind retry). Replay stays scoped to a consumer delivery and never becomes a command replay. RR5 puts Outbox relay claiming and Inbox state transitions on primary, which is what the durable-truth model already required. | **No.** |
| **10** (trace/causality) | Untouched. The four TCE fields are not idempotency material, not fingerprint material and never a routing or correctness input; ADR-0015 adds no envelope field and ADR-0016 adds no trace obligation. | **No.** |
| **11** (`Money`/`PublicId`/`EventId`) | ADR-0015 §9 replays a resource by its `PublicId` and never an internal bigint, and §1/§12 keep `EventId` out of command keying — both are ADR-0013's distinctness rule applied, not extended. No `core` primitive, module or allowlist changes. | **No.** |
| **12** (projection convergence) | ADR-0016 RR5 makes the builder's authoritative-read requirement a consequence of the platform default instead of a local exception, and §5 states that opening the gate later does not weaken CB10–CB14 by one clause. ADR-0014 §3's narrow scoping is honoured exactly. | **No.** |
| **14** (launch cut) | ADR-0016 **applies** item 14 §22's `INFRASTRUCTURE GATE` classification and keeps the gate closed; item 14 NF10/A128's ban on settings-gated unreachable code is why RR1 forbids shipping unused routing. The MVP/`LATER`/`REDUCED SCOPE` classification is untouched, and the failure-domain provisioning view is unchanged. | **No.** |

Neither ADR changes a dependency-matrix cell, adds an import edge, extends a `core` submodule
allowlist, adds an event-registry column or consumer-declaration attribute, or edits an accepted ADR.
**L1–L21 stand unedited, and item 15 adds no `L` rule.**

---

## 12. Phase 0 final dependency and decision audit

| Property | Status | Evidence |
|---|---|---|
| No domain↔domain import is architecturally permitted | Frozen | ADR-0005 / item 3 §5 (`domains → domains` = `SELF ONLY`), classified for `import-linter` enforcement in item 3 §15 |
| Every frozen cross-domain use case has exactly one owner | Frozen | ADR-0004 §4; `place_order` → `application/checkout` (ADR-0007); listing projection → `application/storefront` (ADR-0008); `provider + external_id` mapping → `application/erp_sync` (ADR-0005); post-commit payment → `application/payments_gateway` (ADR-0007 §3) |
| `public.py` template frozen | Frozen | Item 4 + ADR-0006 |
| Checkout owner frozen | Frozen | ADR-0007, item 5 |
| Storefront owner frozen | Frozen | ADR-0008, item 6 |
| Public DTO contract frozen | Frozen | Item 7 (instantiates ADR-0008 + item 4) |
| Event registry and versioning frozen | Frozen | ADR-0009, item 8; the registry ships empty |
| Failure domains, DLQ/quarantine and replay frozen | Frozen | ADR-0010, item 9 |
| Trace/causality envelope frozen | Frozen | ADR-0011, item 10 |
| `Money` / `PublicId` / `EventId` frozen | Frozen | ADR-0012, ADR-0013, item 11 |
| Projection CAS convergence frozen | Frozen | ADR-0014, item 12 |
| Analytics MVP decision frozen | Frozen | Item 13 (no ADR required, recorded) |
| Launch cut frozen | Frozen | Item 14 (no ADR required, recorded) |
| Command idempotency frozen | Frozen | **ADR-0015**, this item |
| No application read replica at launch frozen | Frozen | **ADR-0016**, this item |
| No production code created in Phase 0 | Holds | Phase 0 produced only `docs/` artifacts; the repository contains no Django package, model, migration, setting or dependency |
| No infrastructure gate opened | Holds | Item 14 §22 + ADR-0016 §1; OpenSearch, replica, PgBouncer, service extraction, PostGIS all remain closed |
| ADR-0001…ADR-0014 unedited | Holds | Item 15 created two new files and edited no accepted ADR |

**On enforcement:** every `A*`/`C*`/`V*` identifier across items 3–15 is an **obligation recorded for
a later phase**. Phase 0 asserts no CI check, `import-linter` contract or test exists today; Phase 1
and each implementing phase build them.

### 12.1 Phase 0 DoD verification

Master `# 25`'s Phase 0 DoD has three clauses. Each is verified against an artifact, not asserted:

| DoD clause | Verification |
|---|---|
| "The architectural dependency graph contains no domain↔domain imports" | **Met as an architectural rule.** ADR-0005 / item 3 §5 make `domains → domains` `SELF ONLY`, and item 3 §15 classifies it as an `import-linter` contract. There is no source graph yet to violate it; Phase 1 creates both the packages and the contract that enforces this. |
| "Every cross-domain use case has an owner" | **Met.** ADR-0004 §4 requires exactly one `application/` owner; every cross-domain flow this corpus names has one (§12's table), and item 3 §13 fixes the admission path for a future one — which is why item 14 could classify `application/backoffice` LATER without leaving an ownerless flow behind. |
| "Public contracts and event schemas are approved before any production migration" | **Met.** Item 4 + ADR-0006 freeze the `public.py` contract shape; ADR-0009 + item 8 freeze the event contract and versioning policy, with the registry shipping **empty**; and no migration exists, so nothing has run ahead of an approved contract. ADR-0011's storage-before-partition invariant and this item's handoff (§15) keep it that way into Phase 1. |

---

## 13. Checks

Continuing the corpus numbering after item 14 (A128 / C176 / V145).

### 13.1 Architecture and static checks — idempotency (A129–A138)

| # | Check |
|---|---|
| A129 | The command idempotency claim is a PostgreSQL write. No Redis command, in-process lock, file lock or advisory-lock-only path is the claim mechanism (IK1). |
| A130 | A `UNIQUE (scope, key)` database constraint exists on the idempotency model (IK2, master `# 5.4`). |
| A131 | No idempotency write is committed outside the transaction that performs the protected effect — no separate `atomic(durable=True)`, no autocommit write, no `on_commit` claim (IK5). |
| A132 | No durable `processing` or `failed` value is written by the generic mechanism; a state column, if present, has exactly one legal committed value (IK6). |
| A133 | `scope` values come from a platform-owned constant set, never from request data, headers, path segments or user input (IK2). |
| A134 | Fingerprint material is a canonicalized semantic structure, not a raw body, and contains no credential, token, cookie or CSRF value (IK4, IK14). |
| A135 | Stored result material is bounded and contains no cookies, authorization headers, CSRF tokens, secrets or arbitrary request headers (IK9). |
| A136 | No heavy result column is selected on the claim path (IK9, master `# 20.5`). |
| A137 | No `EventId` is used as a command idempotency key, and no `IdempotencyKey` row is created to deduplicate a message delivery (IK12). |
| A138 | Every replay path filters by the owning principal; no lookup resolves a key without the principal predicate (IK3). |

### 13.2 Architecture and static checks — read replica (A139–A145)

| # | Check |
|---|---|
| A139 | The launch database configuration defines no replica alias for application reads (RR1). |
| A140 | No global database router class exists, and no router routes by SQL verb, model, app label or request method (RR4). |
| A141 | No `using(...)`/`db_manager(...)` call names a replica alias anywhere in the launch source (RR1). |
| A142 | No read on an RR5 correctness path is routed to a non-primary source (RR5). |
| A143 | The projection builder's source reads are authoritative — no cache entry and no lagging copy finalizes a candidate field (RR5; the neighbour of item 12's A98). |
| A144 | Any replica-eligible read is identifiable by an explicit per-path opt-in, never by a package-wide or module-wide setting (RR7). |
| A145 | No sticky-primary/replica routing machinery ships while the gate is closed (RR1; item 14 NF10/A128). |

### 13.3 Contract and behavioural tests — idempotency (C177–C190)

| # | Test |
|---|---|
| C177 | First use executes exactly once and leaves one committed row. |
| C178 | An exact sequential retry replays and performs no second effect. |
| C179 | Two concurrent identical requests produce one effect; the loser replays after the winner commits. |
| C180 | Two concurrent requests with the same key and different fingerprints produce one effect and one `Conflict`. |
| C181 | A different principal presenting an existing key is refused, receives no result data and learns nothing about the key's existence. |
| C182 | A validation failure before the transaction leaves no durable row, and the key is claimable afterwards. |
| C183 | A business rollback after the claim insert leaves no durable row; a retry re-executes rather than replaying a stale failure. |
| C184 | A technical fault before `COMMIT` leaves no durable row and is surfaced untranslated. |
| C185 | A crash/disconnect after `COMMIT` leaves the effect committed; the same-key retry replays and no compensation runs. |
| C186 | With Redis unavailable, and again with Redis flushed between attempts, behaviour is unchanged. |
| C187 | Replay reconstructs the promised result from stored semantic material, with no raw response body persisted. |
| C188 | After retention expiry the key re-executes, and a permanently single-use business operation is refused by its **domain** constraint (IK11). |
| C189 | A duplicate event delivery is handled by ADR-0009 §7's mechanism, with no `IdempotencyKey` row created. |
| C190 | A provider-side retry using the provider's idempotency key produces no second local effect and does not alter local truth. |

### 13.4 Contract and behavioural tests — read replica (C191–C198)

| # | Test |
|---|---|
| C191 | With the launch configuration, every application read resolves to primary. |
| C192 | A read issued immediately after a related write observes that write. |
| C193 | A deliberately lagging source fixture can never become a committed projection candidate. |
| C194 | An authorization/ownership decision cannot be satisfied from a lagging source fixture. |
| C195 | With a replica made unavailable, every correctness path still completes on primary and no write is blocked. |
| C196 | A simulated lag beyond an admitted path's tolerance moves that path to primary rather than serving stale data. |
| C197 | A promoted standby behaves as the primary, and no path treats it as a lagging read source. |
| C198 | Removing an admitted path's staleness statement, fallback rule or metrics fails its own contract test. |

### 13.5 Review checks (V146–V163)

| # | Review item |
|---|---|
| V146 | Redis described, documented or relied upon as idempotency truth. |
| V147 | A claim committed before the business effect, in any form (a helper, a decorator, a signal, a middleware). |
| V148 | A durable `failed` row created for an ordinary rolled-back command. |
| V149 | An idempotency key used as an access token, or key unpredictability cited as authorization. |
| V150 | A fingerprint computed over a raw request body, or containing a secret, token or credential. |
| V151 | Every event handler routed through `IdempotencyKey`, or an `EventId` used as an HTTP idempotency key. |
| V152 | Provider idempotency conflated with local command idempotency, or a provider response deciding local commercial truth. |
| V153 | An expired key described as permanent protection, or a retry guarantee advertised beyond its scope's retention. |
| V154 | A permanent business invariant left to a retention-limited idempotency row instead of a domain `UNIQUE`/state machine. |
| V155 | A second, parallel duplicate-protection table introduced beside the five frozen mechanisms. |
| V156 | A global ORM read router, or "all GET/SELECT → replica" in any wording. |
| V157 | A replica alias, router or sticky-primary implementation added "for later" while the gate is closed. |
| V158 | A replica read on an RR5 correctness path — placement, inventory, pricing-for-write, payments, idempotency, actor/security state, Outbox/Inbox, webhook ingest. |
| V159 | The item 12 projection builder reading a lagging copy, or CB10–CB14 weakened because a gate opened. |
| V160 | An HA standby described or used as an application read replica. |
| V161 | A replica enabled at launch, or an infrastructure gate opened without item 15 / Phase 10's evidence review. |
| V162 | An arbitrary numeric threshold (lag seconds, CPU %, QPS) attributed to Phase 0 rather than to the gate's own review. |
| V163 | Security or ownership freshness traded for read throughput; or a stale-tolerant claim made without a staleness statement, fallback rule and metric. |

---

## 14. Acceptance checklist

**Coverage**

- [x] 1. The listing-projection requirement is covered without a new ADR (§3: ADR-0003 + ADR-0008 + ADR-0014).
- [x] 2. The module-boundaries requirement is covered without a new ADR (§4: ADR-0004 + ADR-0005 + ADR-0006).
- [x] 3. The event-versioning requirement is covered without a new ADR (§5: ADR-0009).
- [x] 4. Generic command idempotency receives exactly one new ADR (ADR-0015).
- [x] 5. No-replica-at-launch receives exactly one new ADR (ADR-0016).

**Idempotency**

- [x] 6. PostgreSQL is the durable truth (IK1).
- [x] 7. Redis is disposable acceleration only (IK1).
- [x] 8. `(scope, key)` uniqueness is frozen (IK2).
- [x] 9. Principal binding is frozen (IK3).
- [x] 10. The semantic request fingerprint is frozen (IK4).
- [x] 11. Same key + same semantic request → replay (IK3, C178).
- [x] 12. Same key + materially different request → `Conflict` (IK3, C180).
- [x] 13. Same key + different principal → no replay, no data, no disclosure (IK3, C181).
- [x] 14. Claim, effect and completion are one local transaction **for a local-ACID command scope**, with provider I/O explicitly outside it (IK5, IK5a).
- [x] 15. Rollback leaves no durable claim (IK6, C183).
- [x] 16. No separately committed `processing` row is required or permitted (IK5, A131).
- [x] 17. Commit ambiguity is replay-safe with no compensation (IK8, C185).
- [x] 18. Result replay storage is bounded and privacy-aware (IK9, A135).
- [x] 19. Retention is explicit and at least the supported retry window (IK10).
- [x] 20. Idempotency does not replace permanent business invariants (IK11, C188).
- [x] 21. `IdempotencyKey` does not replace Inbox/`EventId` (IK12, C189).
- [x] 22. Provider idempotency remains a separate layer (IK13, C190).

**Replica**

- [x] 23. No application replica reads at launch (RR1).
- [x] 24. Primary is the default and current source (RR1).
- [x] 25. A global SELECT router is forbidden — permanently (RR4).
- [x] 26. HA standby is distinguished from a read replica (RR2).
- [x] 27. A future replica is evidence-gated, with categories frozen and no numbers (RR6).
- [x] 28. A future route is a per-path explicit opt-in (RR7).
- [x] 29. Read-your-own-writes is frozen as a requirement, without a mechanism (RR8).
- [x] 30. Lag safety and fallback-to-primary are frozen (RR8).
- [x] 31. Correctness write decisions never read a lagging replica (RR5, RR10).
- [x] 32. Item 12's projection builder remains authoritative-read only, unchanged by any gate (RR5).
- [x] 33. Security freshness is not traded for throughput (RR11).
- [x] 34. A replica outage cannot become a correctness outage (RR9).

**Closure**

- [x] 35. Item 15 is DONE / FROZEN.
- [x] 36. Items 1–15 are all DONE / FROZEN (§12, `PHASE0_STATUS.md`).
- [x] 37. Phase 0 is marked COMPLETE / FROZEN.
- [x] 38. Item 14's launch cut is unchanged (§11).
- [x] 39. Every infrastructure gate remains unopened (§12).
- [x] 40. No production code, model, migration, setting or dependency was created.
- [x] 41. ADR-0001…ADR-0014 are untouched.
- [x] 42. The Phase 1 handoff is recorded (§15) and not implemented.

---

## 15. Phase 1 handoff

Recorded, not started. Only the architecture-relevant obligations are listed; master `# 25` Phase 1
owns the rest.

1. **Package skeletons for `FOUNDATION` and `MVP` modules only**, per item 14's matrix. **No empty
   `LATER` package is created** — not `domains/analytics`, not `domains/tradein`, not
   `integrations/crm`, not `integrations/chatwoot` (item 14 NF1–NF12).
2. **Enforcement harness:** `import-linter` contracts for L1–L21 and the AST/static checks the corpus
   records, wired into CI, plus the query-budget/N+1 harness.
3. **`core` primitives:** `Money` + `RoundingPolicy` (member set chosen here, per item 11), `PublicId`
   and `EventId` as runtime-distinct value types over UUIDv7 with one non-exported internal
   mechanism, the actor primitive and the structural error categories (ADR-0006), and `core.events`
   as **mechanism only**, with the registry shipping **empty**.
4. **`IdempotencyKey` physical model and migration per ADR-0015:** `UNIQUE (scope, key)`, durable
   principal identification, the fingerprint column, bounded semantic result storage, retention
   columns, and indexes that keep the claim path off any heavy column. No durable `processing`/
   `failed` state; no polymorphic cross-domain FK.
5. **Outbox/Inbox initial schema carrying item 10's four TCE fields from the first migration** —
   ADR-0011's storage-before-partition invariant means no partitioning migration precedes them —
   together with the quarantine and dead-letter tables ADR-0010 requires as PostgreSQL-canonical
   terminal state.
6. **Primary-only application database configuration per ADR-0016:** one application alias, no
   replica alias, no router, no sticky-primary machinery. An HA standby, if operations runs one,
   receives no application reads.
7. **No infrastructure gate is opened** — OpenSearch, read replica, PgBouncer, separate services,
   ACID-core extraction and PostGIS all stay closed pending their own evidence reviews.
8. **No migration or setting may contradict a frozen Phase 0 artifact.** Where Phase 1 must choose
   something Phase 0 deliberately deferred (a `RoundingPolicy` member set, a column type, an index,
   an injection mechanism), it records the choice in that phase's artifact; where it would change a
   frozen rule, it writes an ADR that supersedes the one it changes.

---

## 16. Phase 0 status

```text
Items 1–15                       DONE / FROZEN
PHASE 0 ARCHITECTURE FREEZE      COMPLETE
```

Sixteen ADRs are accepted and frozen. The architectural dependency graph permits no domain↔domain
import, every frozen cross-domain use case has exactly one owner, and the public contracts and event
schema policy are approved before any production migration — master `# 25`'s Phase 0 DoD, met.
Enforcement of these rules begins in Phase 1.
