"""Ingest-path failures (item 8 §21, item 9 §21).

`IntegrityViolation` is the one that carries architectural weight. Item 8 IX5 classifies the
same `event_id` arriving with a materially different `event_type`, `schema_version` or payload
as a **data-integrity violation**, not a duplicate: it is what a producer bug, a mis-copied
identity or a corrupted row looks like, the conflicting delivery is **never applied**, it never
overwrites the recorded first observation, and it must be loud. Its outcome is durable
quarantine plus an alert.

None of these is a `core.errors.DomainError`, for the reason `MessageContractError` is not: a
contract- or identity-integrity failure is never a business outcome and must not be catchable
as one.
"""

from __future__ import annotations

__all__ = (
    "IngestError",
    "IngestOutsideTransaction",
    "IntegrityViolation",
    "UnknownDelivery",
)


class IngestError(Exception):
    """The root of Inbox ingest defects."""


class IngestOutsideTransaction(IngestError):
    """`observe_delivery()` was called outside a transaction.

    Item 8's handler transaction rule requires claim, effect, any emitted Outbox rows and
    completion to commit together. A claim that commits on its own would survive a rolled-back
    effect and permanently suppress the redelivery that would have retried it.
    """


class IntegrityViolation(IngestError):
    """One `event_id`, two materially different contents (IX5).

    Carries the committed first observation and the conflicting arrival so the quarantine
    record can state precisely what disagreed. The conflicting delivery is not applied and the
    first observation is not overwritten.
    """

    def __init__(
        self,
        message: str,
        *,
        consumer: str,
        first_seen_fingerprint: str,
        arriving_fingerprint: str,
    ) -> None:
        super().__init__(message)
        self.consumer = consumer
        self.first_seen_fingerprint = first_seen_fingerprint
        self.arriving_fingerprint = arriving_fingerprint


class UnknownDelivery(IngestError):
    """A completion or terminal transition named a delivery that was never observed."""
