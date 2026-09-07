"""Mechanism failures of the command-idempotency layer (ADR-0015).

The single most important property of these classes is what they do **not** inherit::

    IdempotencyMechanismError is not a core.errors.DomainError

Nothing here is a business outcome. A `Conflict` and an ownership refusal — the two
resolutions ADR-0015 §4 names — are **returned** as outcomes by
`core.idempotency.claim.claim_or_resolve`, not raised, because the concrete public error
for a business conflict is owned by the domain that has the business rule (item 4 §13.1,
A23: a public error inherits a domain root *and* exactly one `core.errors` category, and
`core.idempotency` is not a domain).

What is left here is the mechanism being used wrongly or failing technically: an
unregistered scope, malformed claim input, a claim that was never completed, a claim made
outside a transaction, or contention that outlived its bounded retry. Each is a programmer
defect or a technical fault, and item 4 §13.5 requires exactly that they are **not** dressed
as business errors on their way to the platform boundary.
"""

from __future__ import annotations

__all__ = (
    "ClaimContention",
    "ClaimOutsideTransaction",
    "IdempotencyMechanismError",
    "IncompleteClaim",
    "InvalidClaimInput",
    "UnregisteredScope",
)


class IdempotencyMechanismError(Exception):
    """The root of command-idempotency mechanism failures.

    Deliberately rooted at `Exception` rather than at `core.errors.DomainError`, so that a
    mechanism fault cannot be caught by a handler's `except DomainError` and quietly turned
    into an ordinary business outcome.
    """


class UnregisteredScope(IdempotencyMechanismError):
    """The scope is not in the platform-owned scope set (ADR-0015 §3, A133).

    `scope` names one semantic command and comes from a bounded, stable, platform-defined
    set. It is never taken from client input, a header, a path segment or a tenant string,
    so an unknown value is a defect rather than a rejected request.
    """


class InvalidClaimInput(IdempotencyMechanismError, ValueError):
    """Claim or result material violates a bound the mechanism guarantees.

    Also a `ValueError`, because that is what it is: a caller passed material the mechanism
    cannot store within the bounds ADR-0015 §5 and §9 require. The idempotency table is an
    integrity mechanism, not a response cache, so an oversized result is refused rather than
    truncated.
    """


class IncompleteClaim(IdempotencyMechanismError):
    """A claim was taken and its transaction left without a completion (ADR-0015 §6).

    The replayable completion becomes durable at the same instant as the effect. A committed
    claim row with no recorded result would promise a replay it cannot deliver, so the
    mechanism refuses to let the block end that way; the raised error aborts the caller's
    transaction, which is exactly the outcome §6 requires — no durable claim at all.
    """


class ClaimOutsideTransaction(IdempotencyMechanismError):
    """The claim was attempted outside an open transaction (ADR-0015 §6, A131).

    The claim is inserted *inside the same transaction as the protected durable effect*. In
    autocommit the insert would commit on its own, which is the separately committed
    `processing` row ADR-0015 §6 forbids by name.
    """


class ClaimContention(IdempotencyMechanismError):
    """Contention outlived the bounded retry (ADR-0015 §7).

    §7 allows exactly one re-attempt after a resolved conflict. Anything beyond that is a
    technical fault and is surfaced as one — never as a fabricated business outcome.
    """
