"""`PublicId` — the platform's public locator (item 11 §22-§31, ADR-0001 §3).

A `PublicId` addresses a platform object that must be externally or user-addressable:
URLs, public API payloads, email links, Track & Trace. It is a **locator and nothing
else**.

What it is not, stated once because each line is a real failure mode:

* **not authorization** (AZ1-AZ4). Knowing `/order/<public_id>` authorizes nothing. A
  protected resource is reached through an actor-scoped selector/policy or a
  purpose-bound signed token; "nobody will guess 128 bits" is not an access-control
  argument.
* **not a secret** (LG1, LG2). Logging one is not a credential leak — and equally, it is
  not protected by anything, so logging one discharges no PII or redaction policy.
* **not a primary key** (PK1-PK3). The compact internal `bigint` stays the PK and FK and
  never leaves the database; `PublicId` is added where an entity is externally
  addressable, not everywhere.
* **not a keyset tiebreaker** (PK5-PK7). Its approximate chronological ordering is not an
  argument for using it as a pagination key.
* **not a version, an ordering key or business time** (TS1-TS6). The embedded UUIDv7
  timestamp is never decoded: no filter, branch, policy, retention rule or "which came
  first" conclusion reads those bits, which is what makes clock behaviour incapable of
  changing a business outcome.
* **not an `EventId`** (TY3, TX5). See `core.events.identity`.

Immutable, never recycled and never derived from another identifier (IM1-IM6): a derived
locator leaks its input, becomes enumerable through it, and silently changes identity when
the input changes.

`PublicId` carries no entity type tag (OW5/PI6). There is no `OrderPublicId` family; which
entity a locator addresses is stated by the field name in the owning contract.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from core import _uuid7

__all__ = ("PublicId",)


@dataclass(frozen=True, slots=True, kw_only=True)
class PublicId:
    """A runtime-distinct immutable value over the UUIDv7 value space (PI1, TY1-TY5).

    The distinction is a property of the **value**, not of an annotation: this is a frozen
    validating wrapper rather than a `typing.NewType`, whose runtime constructor would
    return the underlying UUID unchanged and leave `PublicId(U)` and `EventId(U)`
    indistinguishable (PI4, TY5, ADR-0013).

    Equality and hashing follow the ordinary contract within the type (EQ3, EQ5). No
    ordering is defined: sorting locators has no business meaning (EQ6).
    """

    value: uuid.UUID

    def __post_init__(self) -> None:
        _uuid7.validated(self.value)

    @classmethod
    def new(cls) -> PublicId:
        """Mint a locator for a platform-owned entity (GN1, GN3).

        Generation is server-side; a client never chooses the locator of a new entity
        (GN4), and uniqueness is enforced by the database, not by generation luck (GN5).
        """
        return cls(value=_uuid7.generate())

    @classmethod
    def parse(cls, text: str) -> PublicId:
        """Parse untrusted external text into a locator (TY4, PA1-PA4).

        Malformed input, a non-canonical spelling and a non-v7 UUID are all rejected here,
        at the boundary, before any selector, policy or domain call runs — so a malformed
        locator never becomes a database query.
        """
        return cls(value=_uuid7.parse_canonical(text))

    def __str__(self) -> str:
        """The canonical outward form (PA2), so one value never has two spellings."""
        return _uuid7.render(self.value)
