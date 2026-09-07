# ADR-0013 — `EventId` is a semantic type distinct from `PublicId`, over the same UUIDv7 value space

- **Status:** Accepted — Frozen
- **Date:** 2026-09-05
- **Phase:** 0 — Architecture Freeze
- **Supersedes:** —
- **Related:** [ADR-0001](0001-product-vs-sku-sellable-unit.md) §3 (the three identity spaces),
  [ADR-0004](0004-four-layer-modular-monolith.md) §2, [ADR-0005](0005-dependency-and-integration-wiring.md) §1,
  [ADR-0006](0006-public-contract-primitives.md) (precedent for a `core` primitive's placement),
  [ADR-0009](0009-event-contract-versioning.md) (`core.events` owns the mechanism),
  [ADR-0011](0011-async-trace-causality-envelope.md) (`causation_event_id`),
  [item 8](../architecture/phase-0/08-event-registry-versioning.md) §9 ID1–ID8,
  [item 10](../architecture/phase-0/10-async-trace-propagation.md) §9 CZ4, R16,
  [item 11](../architecture/phase-0/11-money-public-id.md) §32–§34,
  master `# 5.1`, `# 5.3`, `# 20.3`, `# 20.6`

## Context

Item 8 froze the four-field message envelope and, with it, `event_id` — but deliberately left the
concrete type open. ID7 reads:

> `event_id` is conceptually the project's UUID-based identity primitive (`PublicId`/UUIDv7,
> master `# 5`). **Item 11 owns the implementation**; item 8 requires only that the value be a
> stable, globally unique, non-sequential, opaque UUID assigned once. No sequential bigint is
> acceptable here.

Item 10 then defined `causation_event_id` as "the same semantic type as `event_id`", with its
representation explicitly deferred to item 11 (CZ4, R16, ADR-0011's out-of-scope list). So two
frozen artifacts now depend on a decision nobody has taken, and the parenthetical in ID7 reads as a
hint toward using `PublicId` itself.

The binding requirements from ID7 are: a UUID value space, stable, globally unique, non-sequential,
opaque, assigned once, never a sequential bigint. **No frozen artifact requires the `PublicId`
semantic type.** Item 11 is therefore genuinely free, and the choice matters:

- The platform already has a distinct type for public locators precisely to stop identifier
  confusion. Master `# 5.3` gives the reason in one sentence: `PublicId` exists as a separate type so
  that an internal `bigint` and an external UUIDv7 "cannot be accidentally confused in a function
  signature or a URL builder".
- If `event_id` is a `PublicId`, then `order_public_id` and `event_id` become mutually assignable,
  and nothing but a field name prevents a message identity reaching a URL builder or an order
  locator reaching a consumer dedupe key. The exact confusion `PublicId` was created to prevent
  reappears at a second boundary.
- The two identities also differ in what governs their exposure. Item 8 PD14 says an
  externally consumed message "carries `PublicId` locators only" — a rule about **payload**
  identifiers of business objects. If the envelope identity were also a `PublicId`, that rule would
  become ambiguous about the envelope, and a reviewer would have to reason about which `PublicId` in
  a message is a locator and which is not.
- They differ in lifecycle and in ownership. A `PublicId` is created with an entity, is immutable
  for that entity's life, and is addressable by users and partners. An `EventId` is created with one
  emission of a fact, lives inside the platform's asynchronous machinery, is subject to message
  retention rather than entity lifetime, and addresses nothing a user can request.

The alternative of using a bare `uuid.UUID` for `event_id` was also available and is worse than
either: it satisfies ID7's letter while abandoning its "typed distinctly enough" spirit, and it
makes every identity position in the async machinery accept every 128-bit value in the codebase,
including a provider's.

The cost of a second type is real: two types over one value space is more machinery than one, and
somebody has to keep them from drifting.

## Decision

**`EventId` is a semantic type distinct from `PublicId`, over the same UUIDv7 value space. It is
the type of `event_id` and, therefore, of `causation_event_id`.**

1. **Two semantic types, one value space.** `PublicId` addresses an externally addressable platform
   resource. `EventId` identifies one durable asynchronous message instance. Both are
   standards-conforming UUIDv7 values; neither is assignable to the other.

2. **One shared low-level mechanism, kept `core`-internal.** UUIDv7 generation, parsing and
   version validation are implemented once inside `core` and used by both types, so there is one
   algorithm and one standards-conforming library decision. That mechanism is **not** an exported
   surface for any package family: every module imports the **semantic type** it needs, never a
   generic `new_uuid7()`/`parse_uuid7()` pair — which would let every call site produce a value that
   fits both types and dissolve the distinction exactly where it matters.

3. **Placement, with no allowlist change.** `PublicId` sits with the identity primitives already
   allowlisted as `core.public_id` (item 3 §4.2–§4.7). `EventId` sits with the envelope mechanism
   ADR-0009 §1 already assigned to `core.events`, because `event_id` *is* an envelope field.
   `core.events` is already allowlisted for `domains`, `application`, `tasks` and the composition
   root, and is already `FORBID` for `integrations/*` — which is correct and deliberate: an adapter
   has no business minting internal message identity, and item 8 ID6 already separates a provider's
   `external_event_id` from the internal one. **No `core` submodule allowlist entry is added,
   removed or widened.**

4. **`causation_event_id` has exactly this type**, discharging item 10 CZ4. Item 10's rules for it
   are unchanged: one hop, never self-referential, never ordering, never authorization, never
   idempotency, never a foreign key, and expected to dangle once the parent partition is archived.

5. **This clarifies ID7's deferral; it amends nothing.** Every ID7 requirement is satisfied — stable,
   globally unique, non-sequential, opaque UUID, assigned once, never a sequential bigint. Every
   item 8 identity rule (ID1–ID8) and every item 9 and item 10 rule stands as written. **ADR-0009,
   ADR-0010 and ADR-0011 are neither edited nor superseded.**

6. **An `EventId` is not, and never becomes:** a `PublicId`; a broker or transport delivery
   identifier; a `source_version` or any other version; an ordering key or sequence number; an
   authorization token; an idempotency key for an arbitrary HTTP command (master `# 5.2`'s
   `IdempotencyKey` is a separate, scoped mechanism); or a provider `external_event_id`.

**The distinction is required at runtime, not only in annotations.** "Distinct semantic type" here
means that the semantic type survives into the value: `PublicId(U)` and `EventId(U)` built from the
same UUID value do not compare equal, hash consistently with that inequality, are not mutually
assignable, and do not pass silently through each other's constructor, parser or lookup path
(item 11 TY5, EQ4, C127). Consequently, **a static-only alias or a bare `typing.NewType` over
`uuid.UUID` is incompatible with this ADR**: its runtime constructor returns the underlying value
unchanged, so two such types are indistinguishable at runtime and would satisfy the type checker
while leaving the confusion this ADR exists to prevent fully reachable. The underlying
*representation* may still be a `uuid.UUID`; what is excluded is a bare UUID value serving as the
identity.

**Out of scope of this ADR:** the exact Python construct for either type — it remains Phase 1's,
bounded only by the requirement above that it provide runtime-distinct immutable semantic values
satisfying item 11 TY1–TY5 (a frozen validating wrapper value object is an admissible shape; any
other construct is admissible only if it genuinely preserves all of them) — together with the module
and member names, the UUIDv7 library choice, and the Outbox/Inbox/quarantine/dead-letter column
types. Also out of scope: `PublicId`'s own semantics, which ADR-0001 §3 and master `# 5.1` already
froze and item 11 §22–§31 specifies.

## Consequences

**Positive**

- A message identity and a resource locator can no longer be substituted for one another by
  accident. The type checker reports it; no field-naming convention has to hold the line.
- Item 8 PD14 stays unambiguous: a `PublicId` in a message is a payload locator subject to the
  internal-only / externally-consumed classification, and the envelope identity is a different type
  entirely.
- Items 8 and 10 get their deferred answer without either being reopened, and `causation_event_id`
  acquires a concrete representation that is guaranteed to match `event_id`'s by construction rather
  than by convention.
- The `integrations/*` boundary is reinforced structurally: an adapter cannot even name the internal
  message identity type, which is exactly item 8 ID6's separation expressed as an import rule that
  already existed.

**Negative / accepted cost**

- Two semantic types over one value space is more machinery than one, and Phase 1 must implement the
  shared mechanism carefully enough that the two types cannot drift apart in validation behaviour.
- Anywhere a diagnostic or operator surface handles both a resource locator and a message identity,
  the conversion between them and their common textual form is explicit. That verbosity is the
  feature being paid for.
- If a future operator-facing interface must render an `EventId`, `core.events` is not in
  `interfaces/*`'s `core` allowlist, so that placement question is answered then — recorded as an
  explicit allowlist decision on ADR-0006's precedent, exactly as item 10 PC9 anticipated for the
  trace-capture module. This ADR requests no extension and pre-empts none.

**Enforcement**

| Mechanism | What it enforces |
|---|---|
| Phase 1 implementation | Two **runtime-distinct** immutable semantic types satisfying item 11 TY1–TY5; one shared `core`-internal UUIDv7 mechanism, exported to no package family. |
| Type checker (item 11 TY1–TY3) | `PublicId` is not assignable from `int`, from a bare `UUID`, or from `EventId`, and vice versa. |
| Item 11 **TY5** | The distinction survives into the runtime value, so a construct that erases it — a bare `typing.NewType` over `uuid.UUID` — cannot be used to satisfy this ADR. |
| Item 11 **A82** (static/AST) | No bare `uuid.UUID` annotation in a locator position; no package outside `core` imports a generic UUID utility instead of a semantic type. |
| Item 11 **C126** | `causation_event_id` is the same semantic type as `event_id`, asserted structurally and by the type checker rejecting a `PublicId` there. |
| Item 11 **C127** | A `PublicId` and an `EventId` with identical underlying UUID bytes are not equal, not mutually assignable, and neither resolves in the other's lookup path. |
| Item 11 **C124 / C125** | Retry and replay preserve the `EventId`; a genuinely new fact gets a new one — item 8's rules, now asserted against the named type. |
| Item 11 **V100 / V101** (review) | No construct that lets the two types become mutually assignable; no `EventId` minted on retry, used as an HTTP idempotency key, or adopted from a provider. |
| `import-linter` | Unchanged. `core.events` stays `FORBID` for `integrations/*`; no contract is added or relaxed. |

Phase 1 implements the types and the checks. No dependency-matrix cell moves, no import edge is
added, no `core` submodule allowlist changes, and no ADR-0009/0010/0011 rule is modified. `L1–L21`
stand unedited.
</content>
