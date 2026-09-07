"""How a claim resolves against a committed row (ADR-0015 §4, §9).

ADR-0015 §4 fixes three resolutions against a **committed** row::

    same (scope, key) + same principal + same fingerprint   -> replay the committed outcome
    same (scope, key) + same principal + other fingerprint  -> Conflict
    same (scope, key) + different principal                 -> NotAllowed (ownership refusal)

They are **returned as values, not raised.** The concrete public error for a business
conflict is owned by the domain that has the business rule: item 4 §13.1 / A23 require a
public error to inherit a domain root *and* exactly one `core.errors` category, and
`core.idempotency` is not a domain. Having `core` raise a `DomainError` subclass would give
it concrete public-error identity that ADR-0004 §2 does not allow it to own. The owning
command maps `Conflicted` and `NotOwned` onto its own errors under its own contract, which is
also the only layer that knows whether an ownership refusal should read as "not found" or
"not allowed" for its own existence-leak policy (item 4 Z8).

ADR-0015 mandates the three-way *resolution*, not an exception shape, so this is a choice of
spelling within the frozen decision, not a change to it.
"""

from __future__ import annotations

from dataclasses import dataclass

from core.public_id import PublicId

__all__ = ("Conflicted", "NotOwned", "Replay", "SemanticResult")


@dataclass(frozen=True, slots=True, kw_only=True)
class SemanticResult:
    """The bounded, semantic material a replay reconstructs from (ADR-0015 §9).

    Not a verbatim transport response. Master `# 5.2`'s `response_body_json` is an optional
    per-scope strategy, never universal truth, and cookies, authorization headers, CSRF
    tokens, credentials, secrets and arbitrary request headers are never stored at all. The
    interface layer rebuilds an HTTP/HTML/JSON response *from this*; it does not replay one.

    `public_id` is the created resource's semantic locator where the command created one. It
    is never an internal bigint, and no polymorphic cross-domain foreign key exists to point
    at the resource — master's `resource_type` pair is illustrative (§9).

    `detail_json` is canonical JSON text (`core.idempotency.canonical`), bounded at 4 KiB.
    Text rather than a parsed object, because a public value here must be immutable by field
    type (item 4 §7) and a `dict` is not.
    """

    kind: str
    public_id: PublicId | None
    detail_json: str | None


@dataclass(frozen=True, slots=True, kw_only=True)
class Replay:
    """The same principal presented the same key and the same input.

    No second effect is performed and **no compensation is attempted** — the committed
    commercial operation stands (§8). The caller reconstructs its response from `result`.
    """

    result: SemanticResult


@dataclass(frozen=True, slots=True, kw_only=True)
class Conflicted:
    """The same principal reused a committed key with materially different input.

    A committed key can never be reused for materially different input. The caller refuses
    the request; it does not execute it under a fresh key on the caller's behalf.
    """


@dataclass(frozen=True, slots=True, kw_only=True)
class NotOwned:
    """A different principal presented an existing key.

    The caller receives no result data and learns nothing about whether the key exists: the
    key is **not an object-access token** and its unpredictability is not an authorization
    mechanism (§4). This outcome carries no fields precisely so that nothing about the row
    can leak through it, and ADR-0015 §4 additionally requires the attempt to be logged as a
    security event — an obligation recorded against the slice that introduces
    `core.observability`, since no such module exists yet.
    """
