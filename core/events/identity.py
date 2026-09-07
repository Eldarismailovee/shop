"""`EventId` — durable message identity (item 11 §32-§34, ADR-0013).

`EventId` is a semantic type **distinct from `PublicId`**, over the same UUIDv7 value
space. The reason is semantic, not stylistic: a `PublicId` addresses a thing a user or a
partner can ask for, while an `EventId` identifies one emission of a fact inside the
platform's own asynchronous machinery. They have different lifecycles, different exposure
rules and different consumers. With one type, `order_public_id` and `event_id` become
mutually assignable and nothing but a field name stops a message identity reaching a URL
builder — the exact confusion `PublicId` was created to prevent, at a second boundary.

It lives in `core.events` because `event_id` *is* an envelope field, so its type is
envelope mechanism (OW3). `core.events` is already forbidden to `integrations/*`, which is
a feature rather than a gap: an adapter has no business minting internal message identity,
and a provider's `external_event_id` is a different identity space entirely (ID6, EI7).

What an `EventId` is not (MI5-MI9, MI12): a `PublicId`; a broker or transport delivery
identifier (a Celery task id, an AMQP delivery tag, a Redis stream id, an Outbox row PK, a
retry counter); a `source_version`, an ordering key or a sequence number; an authorization
token; an HTTP command's idempotency key; or a provider's `external_event_id`.

Identity behaviour across retries and replay — one identity per emission, preserved through
relay retries, broker redelivery, worker retries and terminal-state replay (MI2, MI3, MI11)
— is a property of the *event-processing* machinery that carries this value, not of the
value type. That machinery arrives with the Outbox/Inbox slice; this module provides only
the primitive it will carry.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from core import _uuid7

__all__ = ("EventId",)


@dataclass(frozen=True, slots=True, kw_only=True)
class EventId:
    """A runtime-distinct immutable UUIDv7 message identity (TY5, EQ4, TX5).

    Runtime-distinct, not merely annotation-distinct: `PublicId(value=U)` and
    `EventId(value=U)` built from the same UUID are different values — they do not compare
    equal, and neither passes through the other's constructor or parser. A bare
    `typing.NewType` over `uuid.UUID` cannot deliver that, because its runtime constructor
    returns the underlying value unchanged (ADR-0013).

    Hash collision between the two types is legal and expected; correctness never rests on
    its absence (EQ5). No ordering is defined: identity establishes no sequence (EQ6, MI7).
    """

    value: uuid.UUID

    def __post_init__(self) -> None:
        _uuid7.validated(self.value)

    @classmethod
    def new(cls) -> EventId:
        """Mint the identity of one emission (MI1)."""
        return cls(value=_uuid7.generate())

    @classmethod
    def parse(cls, text: str) -> EventId:
        """Parse the canonical form of a durable or transported identity (PA1-PA4)."""
        return cls(value=_uuid7.parse_canonical(text))

    def __str__(self) -> str:
        return _uuid7.render(self.value)
