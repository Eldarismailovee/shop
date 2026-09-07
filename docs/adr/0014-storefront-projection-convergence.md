# ADR-0014 — Storefront projection convergence: an application-owned per-row CAS over a current-state rebuild, not a producer-supplied source version

- **Status:** Accepted — Frozen
- **Date:** 2026-09-06
- **Phase:** 0 — Architecture Freeze
- **Supersedes:** —
- **Related:** [ADR-0003](0003-catalog-boundary-vs-storefront-projection.md) §3 (no read-model state
  in catalog), [ADR-0004](0004-four-layer-modular-monolith.md) §4,
  [ADR-0005](0005-dependency-and-integration-wiring.md) §7,
  [ADR-0008](0008-storefront-listing-projection.md) (the projection's ownership, rebuildability and
  eventual-consistency classification; lists this mechanism as out of scope),
  [ADR-0009](0009-event-contract-versioning.md) §7 (`schema_version` is not a source version),
  [ADR-0010](0010-async-failure-domain-isolation.md) (projection failure domains, replay),
  [ADR-0013](0013-event-id-distinct-identity-type.md) (`EventId` is identity, not order),
  [item 6](../architecture/phase-0/06-storefront-listing-projection.md) §16 PU1–PU10,
  [item 8](../architecture/phase-0/08-event-registry-versioning.md) §24 OR6–OR8,
  [item 12](../architecture/phase-0/12-source-version-guarded-upsert.md) (the full artifact),
  master `# 5` principle 36, `# 7.6`, `# 20.2`, `# 20.6`, `# 22.1`, `# 24`, `# 25` Phase 4, `# 26`

## Context

`ProductListingProjection` is a derived serving read model whose row (`Product × Language`) is
composed from five independent authoritative sources — catalog, pricing, inventory, promotions and
reviews. Item 6 froze the correctness requirement and deferred the mechanism:

> **PU4** A stale update must never overwrite newer projected state. **PU5** Two independent sources
> changing different aspects of the same product must not lose each other's effect through
> last-writer-wins on the whole row.

The master proposes a concrete mechanism for this: a `source_version bigint` column on the serving
row (`# 7.6`), supplied by the producer as a payload field (`# 20.6`'s
`CatalogProjectBatch { product_ids, source_version }`), applied with

```sql
ON CONFLICT (product_id, language) DO UPDATE SET …
WHERE EXCLUDED.source_version > product_listing_projection.source_version
```

Item 6 §16.2 recorded this as master text rather than as a decision, and item 8 OR7 confirmed that
item 12 owns the mechanism outright. Item 12 evaluated it and found it unsound in three independent
ways, each of which is fatal on its own:

1. **There is no admissible generator.** A total order across five domains needs either a shared
   cross-domain counter (an ownerless business object — item 6 R2/R3, ADR-0005 §2), or a
   projection-motivated version column in each domain (ADR-0003 §3, item 6 PU10), or a producer
   transaction writing `application/storefront` state (item 6 O1/UP2). All three are already
   forbidden. Comparing `pricing` revision `P2` with `inventory` revision `I7` is arithmetic, not
   semantics.

2. **A pre-commit sequence does not order commits.** `TX-A` takes version `10` and stalls; `TX-B`
   takes `11` and commits; the projection applies `11`; `TX-A` commits. `TX-A`'s change is now
   authoritative, and the guard rejects it as stale — the guard rejects a *fact*, not a stale write.
   The same objection disqualifies transaction ids and, for different reasons, WAL positions and
   commit timestamps (item 12 §5).

3. **The rebuild has no version to write, and PU5 is lost.** ADR-0008 and item 6 RB1/RB2 require full
   reconstruction from OLTP with no event history; a rebuild has no message and therefore no
   `source_version`, leaving only options that either make the repair mechanism unable to repair or
   make it able to swallow every subsequent update. Separately, a candidate built from `(P2, I1)`
   that happens to carry the higher version permanently erases a committed inventory change whose
   trigger has already been consumed — precisely the case master `# 7.6` names as the motivation, and
   precisely the case its predicate does not solve.

Item 12 also evaluated a per-source version vector. It fails for a different reason: pricing,
inventory, promotions and reviews have no per-Product revision of their own, so each component would
have to be invented for the read model's benefit and exposed through that owner's public contract —
making item 6 O2 ("a domain does not know it is projected") false in substance — and a component-wise
merge has no defined answer for the row's cross-source derived fields (discount, display
availability, visibility, badges, sort keys).

A decision was therefore unavoidable, and it changes master text.

## Decision

**Storefront projection convergence is an optimistic compare-and-set, owned by
`application/storefront`, over a candidate rebuilt from current authoritative state.**

1. **A trigger is a dirty-identity signal, not a snapshot.** An asynchronous message (or dirty-set
   entry) says *which products may need rebuilding*. No serving field is ever taken from a payload;
   the builder re-reads authoritative state through `<domain>.public` batch selectors and computes
   the **whole** candidate — every field, every language — exactly as a rebuild would. A per-source
   partial merge is forbidden without a new ADR supplying an owned field-to-source decomposition.

2. **The guard token is `projection_revision`**, replacing `source_version` for this purpose: a
   64-bit signed integer, `NOT NULL`, **one value per serving row**, generated by
   `application/storefront` inside the guarded write, starting at `1` and advancing by at least one
   **iff** the row's serving state actually changes. No producer, domain, task, interface,
   integration or cache supplies or advances it. It is compared **only for equality, only against a
   value observed earlier from that same row**; ordered comparison, `MAX`/`GREATEST`, `ORDER BY` and
   cross-row comparison are forbidden.

   **Non-reuse is scoped to a projection generation, and a reset is legal only behind a fence.**
   Within a generation — ordinary incremental work, targeted rebuild, in-place full rebuild,
   reconciliation, withdrawal and tombstoning — a row identity's token never decreases and never
   repeats a committed value; that is what makes ordinary concurrent writers ABA-safe. A **fenced**
   destructive operation — a destructive rebuild, a physical tombstone collection, a table
   replacement, a build-then-swap, or recovery from total projection loss — ends the generation and
   **may reinitialize tokens at `1`**, but only if the fence drains or invalidates every observation
   taken against the old structure, so that no pre-fence observation can execute a compare-and-set
   against a post-fence row. The protection is therefore *either* preserve non-reuse *or* invalidate
   every prior observation before reuse becomes possible — and explicitly **not** retained per-row
   token maxima, a durable epoch column, a token-history table or any backup, replication or
   retention obligation. The projection and its tokens stay disposable: the whole table can be lost
   and rebuilt from OLTP with no retained token history and no retained event history.

3. **The protocol is observe → build → guarded write**, and **the observation strictly precedes
   every source read of that unit of work** — where "precedes" means the source read's **visibility
   point** is established after the observation, not merely that the call is issued later.
   Accordingly, **every source read used to build a candidate is an authoritative read of committed
   owner state**: no candidate field may be finalized from a cache entry, an asynchronously lagging
   read replica or any bounded-stale copy, and if Phase 4 wraps a unit's source reads in a database
   transaction or snapshot, that snapshot is opened **after** the observation, never before. A cache
   may accelerate or short-circuit work, but may not be the final source of a candidate field. This
   is narrowly a constraint on the projection builder's source-read path: it is **not** the
   platform-wide read-replica decision (item 15's), the platform default already satisfies it, it
   requires no domain to know it is projected, and it fixes no database alias or selector signature.
   These two ordering rules, together with the atomicity of the per-row compare-and-set and the
   within-generation non-reuse of point 2, are the complete premise set of the safety proof in item
   12 §27 — which concerns **state-visibility chronology, not value trajectory**: a source moving
   `100 → 120 → 100` is converging, not regressing.

4. **The guard predicate is equality**, not `>`:

   ```text
   apply the candidate only if the row's stored projection_revision still equals the value
   observed before the candidate was built (or the row is still absent, if that is what was
   observed)
   ```

   **The logical guard unit is the product; the physical write transaction is the bounded batch.**
   Verification is **all-or-nothing across one product's language rows**, and a guard miss on one
   product leaves the other products of the same batch eligible for the same write — the shared
   transaction is a container, not a shared guard. What is asserted between two different products
   is that they share no freshness or ordering relationship; it is *not* asserted that they never
   share a transaction, a lock or a technical failure, because with a bounded batch they do: a
   technical abort (deadlock, lock timeout, serialization failure, crash) rolls the whole batch
   back, writes nothing durable, and is retried with every product re-observed and rebuilt. Locks
   are serving-row locks taken in a deterministic product → language order for the short
   verify-and-write window; there is no global or table-wide correctness mutex and no
   correctness-serialized writer fleet.

   A guard miss means only that another projection writer committed first: the candidate is
   discarded **whole**, never merged and never partially applied; the unit re-observes and rebuilds
   under a bounded, jittered retry budget, then re-coalesces through the projection workflow and, on
   exhaustion, through the ordinary transient-failure handling of ADR-0010. A guard miss is never a
   business error, never a quarantine and never visible to a request.

5. **No-op suppression is mandatory and total.** If the candidate equals the stored serving state —
   compared over serving fields only, excluding `projection_revision` and `updated_at` — nothing is
   written: no `UPDATE`, no token advance, no `updated_at` change. A duplicate delivery therefore
   performs zero row writes.

6. **Rebuild, reconciliation and replay use the identical protocol and have no privileges.** There
   is **no force-write path** — no flag, parameter, management command, admin action or reconciler
   argument may write a serving row without a satisfied guard. A build-then-swap rebuild is admitted
   only with an explicit fence point, a catch-up of every change committed during the build, and a
   swap that invalidates every observation taken before it — after which, per point 2, the swapped-in
   generation may start its tokens over; "build a table for an hour and rename it over live state"
   is forbidden. A repair over a key range whose tokens are untrusted is a fenced, authorised,
   audited operational action, never an ambient code path, and — being a generation boundary — it
   may reinitialize those rows' tokens rather than attempting to recover the corrupted values.

7. **Withdrawal is a forward content change to a not-visible state, not a delete, in the ordinary
   update path.** Deleting the row would destroy the guard token, and a destroyed token cannot fail
   a stale writer's compare-and-set (the ABA hole). Physical tombstone removal is a fenced
   maintenance operation. This narrows item 6 LC2's latitude for the update path only; LC1, LC3 and
   LC8 are unchanged, and genuine reactivation remains an ordinary forward change.

**Out of scope of this decision:** the physical schema, column definition, indexes and Django model;
the serving-row unique constraint's definition; batch sizes, retry counts, backoff and jitter; the
concrete no-op comparison technique; in-place vs build-then-swap and the swap's implementation; the
concrete fence mechanism by which a generation boundary drains or invalidates prior observations;
how an owning module exposes an authoritative-read capability to the builder (no database alias and
no selector signature is chosen here); tombstone retention; the fenced-repair tooling, permission
model and runbook; metric names and thresholds; every `event_type` and payload schema (item 8 and
each owning module's phase); **the platform-wide read-replica decision, which remains item 15's**;
whether an analytics source is ever admitted (item 13); and the MVP/later cut (item 14).

## Consequences

**Positive**

- PU4 and PU5 hold by construction, with a proof (item 12 §27) that assumes no message ordering, no
  clock, no producer sequence, no retained event history, no retained token history, no isolation
  level, no cross-domain atomic snapshot and no monotonic movement of business values. Successive
  committed writes to a row have strictly increasing **visibility points** on **every** source, so
  each committed candidate sees a superset of its predecessor's source commits and no source's
  contribution can be dropped.
- Rebuildability (ADR-0008, item 6 RB1/RB2) is native rather than reconciled with the guard: the
  token is application-owned and its non-reuse is generation-scoped, so deleting the whole
  projection and the whole event history still permits reconstruction with rows starting over at
  `1`, and the rebuild competes fairly with incremental writers instead of bypassing or being
  rejected by them.
- Domain blindness is preserved in substance, not only in form: the builder asks domains for facts,
  never for revisions, so no domain gains a column, a public symbol or an awareness that it is
  projected.
- Admitting a future source (item 13's analytics, or any other) costs one builder input and one
  trigger — no token change, no migration, no re-proof.
- An old replay cannot carry old prices back into a row: it causes a rebuild from current truth,
  normally a no-op.
- Duplicate deliveries are free: zero row writes, no token churn, no write amplification on hot rows.

**Negative / accepted cost**

- **A whole-candidate rebuild for a single-field change.** A stock change re-reads catalog, pricing,
  promotions and reviews for the affected products. Accepted: work is batched and coalesced, no-op
  suppression keeps the write side cheap, and it runs off the request path in its own failure
  domain. The alternative — a partial merge — costs a field-to-source decomposition the architecture
  does not own and ends the "rebuild ≡ incremental" property.
- **Wasted work under contention.** A lost race discards a built candidate. Accepted, bounded by the
  retry budget and by coalescing; the guard-conflict rate is an explicit metric rather than a hidden
  cost.
- **One extra read per batch** for the observation. Negligible, and off the request path.
- **The builder may not lean on the cache or on a replica.** Its source reads must be authoritative,
  so a cheap warm-cache build is not available to it and a future read-scaling move cannot silently
  include this path. Accepted: without it the safety proof's premise is unenforceable, and the
  builder already runs batched and off the request path in its own failure domain, which is where
  read cost can be absorbed.
- **A generation boundary needs a real fence.** Destructive rebuild, tombstone collection and
  build-then-swap each acquire an operational obligation — drain or invalidate every prior
  observation — that Phase 4 must actually implement, not merely intend. Accepted as the cheaper
  half of the alternative: the other way to close ABA is retained per-row token maxima or a durable
  epoch, which would make the projection non-disposable and give a derived read model a retention
  and backup obligation it must never have.
- **A departure from master text** that a reader of `# 7.6`, `# 20.6`, `# 25` or `# 26` must
  reconcile. Mitigated by item 12 §1.4, which maps every master statement to preserved / refined /
  departed. Master `# 5` principle 36's requirement is preserved in full; only its illustrative
  mechanism changes. No published contract needs migration: the event registry ships empty, and
  master's `CatalogProjectBatch` was already identified as an illustration item 8 did not adopt.
- **A retired field name.** `source_version` no longer names anything in this platform. Accepted
  deliberately: keeping the name would keep inviting the `>` predicate the design forbids.
- **Withdrawal keeps a row.** Tombstones accumulate until a fenced collector removes them, and that
  collector is a Phase 4 obligation rather than a free `DELETE`.
- **The correctness of the whole mechanism rests on one ordering rule** (observe before read), which
  is easy to violate silently in a refactor. Mitigated by making it a named, checked invariant
  (A98) rather than a comment.

**Enforcement**

- **Phase 4** implements the projection model, the serving-row unique constraint that the insert
  guard depends on, the guarded-write component and the rebuild/reconciliation paths.
- **Static checks (item 12 §29.2, A86–A100):** no projection-motivated version on a domain table; no
  freshness comparison over `schema_version`, `EventId`/`PublicId`/UUID timestamps, `occurred_at`,
  `updated_at`, an Outbox row id or a cache counter; equality-only use of `projection_revision`; only
  `application/storefront` reads or writes it; every serving-row write originates in the single
  guarded-write component; no force parameter; no token in any public DTO, serializer, template, URL
  or cursor; no serving field assigned from a trigger payload; observation ordered before the source
  reads; **no candidate field finalized from a cache or a lagging replica**; **any read
  transaction/snapshot opened after the observation**.
- **Behavioural tests (item 12 §29.3, C128–C147):** classic stale writer; independent price/inventory
  convergence to `(P2, I2)`; reverse delivery; duplicate trigger writing nothing; withdrawal not
  resurrected; reactivation; insert race; crash after commit before acknowledgement; incremental vs
  rebuild; rebuild with the event history deleted; overlapping batches and a technical batch abort;
  two language rows; source change during build; hot contention; replay of an old trigger; rebuild
  idempotence; reconciliation honouring the guard; **a stale cache/replica fixture that cannot become
  the committed candidate**; **snapshot-after-observation ordering**; **a fenced generation reset
  that a pre-fence observation cannot act on, with the unfenced delete-and-recreate asserted as the
  negative case**.
- **Review checks (item 12 §29.4, V102–V118):** an ordered token comparison; a producer-supplied
  freshness token reappearing; a version column on a domain table; a force path; a swap without
  catch-up; a global projection mutex; an unbounded retry loop; a payload used as a snapshot; no-op
  suppression weakened; `updated_at` promoted to a guard; the token leaking into public shape; the
  ABA hole via unfenced physical deletion; an unfenced repair or a write-back into a domain; an
  ad-hoc partial merge; **either half of the non-reuse/fence disjunction dropped — an unfenced token
  reset, or a durable epoch/token-history table that would make the projection non-disposable**; **a
  candidate field taken from bounded-stale data, or an early snapshot**; **the false claim that
  different products never share a transaction, a lock or a technical failure**.
- This ADR changes **no** dependency-matrix cell, adds **no** import edge, extends **no** `core`
  submodule allowlist, adds **no** event-registry column or consumer-declaration attribute, and edits
  **no** accepted ADR. L1–L21 stand unedited.
