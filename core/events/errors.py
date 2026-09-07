"""Contract-failure signalling for the message mechanism (item 8 §20, VL4, QU10).

An unknown `event_type`, an unknown or unsupported `schema_version`, or a payload that is
invalid for a known version is a **contract/infrastructure integrity failure**. It is never
silently ignored, never coerced into a known version, never treated as the nearest or
latest version, never partially consumed and never marked HANDLED. Its outcome is durable
quarantine plus an operational alert.

The single most important property of these classes is what they do **not** inherit:

    MessageContractError is not a core.errors.DomainError

A quarantine outcome is not a business error, is never mapped to a business state
transition, and never causes a compensating business action on its own (QU10, VL4). Keeping
the two hierarchies disjoint is what stops a contract-integrity failure being caught by a
handler's `except DomainError` and quietly turned into an ordinary business outcome.

These are the failures the *generic mechanism* can raise today. The durable quarantine
record, the dead-letter record, the alert, the transport disposition ordering and the
authorised replay path are the Outbox/Inbox slice's; item 9 owns the topology. Nothing here
names a table or a queue.
"""

from __future__ import annotations

__all__ = (
    "InvalidPayload",
    "MessageContractError",
    "UnknownEventType",
    "UnsupportedSchemaVersion",
)


class MessageContractError(Exception):
    """The root of message-contract integrity failures.

    Deliberately rooted at `Exception` rather than at `core.errors.DomainError`: this is
    not a business failure and must not be catchable as one.
    """


class UnknownEventType(MessageContractError):
    """No registered message carries this `event_type` at any version."""


class InvalidPayload(MessageContractError):
    """The payload is not admissible for a durable message (item 8 PD5, PD8, §29).

    Raised on both edges by `core/events/codec.py`: at emission, when a producer offers a
    shape that cannot be rendered deterministically or exceeds the bound; and at consumption,
    when stored or transported text is not in canonical form. Like its siblings it is **not**
    a `core.errors.DomainError` — an invalid payload is a contract-integrity failure whose
    outcome is durable quarantine plus an alert, never a business state transition.
    """


class UnsupportedSchemaVersion(MessageContractError):
    """The `event_type` is registered, but not at this `schema_version`.

    Never resolved to the nearest or latest known version, and never fulfilled by a
    default, `else` or catch-all branch — that fallback is exactly what CS2-CS5 forbid and
    what A43 will check once a consumer dispatch exists.
    """
