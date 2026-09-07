"""The registered-message lookup mechanism — **shipping empty** (item 8 §7, §25, §26).

`core.events` owns *mechanism* only. It owns no business message type, no payload contract,
no `event_type` and no schema: a payload field named after a product, an order, a payment or
a provider does not belong in `core` (OW4, A46). The payload contract of each message is
owned by the producing module and lives in that module's package, and reaches a validator as
generated, versioned **data** — never as a producer-owned Python object crossing a package
boundary (§6.3, PI2, PI10).

This module is the runtime index over `(event_type, schema_version)`, and it ships with
**no entries** (RG8). The checked-in registry document
`docs/architecture/events/event-registry.md` is likewise empty by design; populating either
is each owning module's own phase. There is no sample entry here — a fixture proves the
mechanism instead, so that no `event_type` is invented merely to have something to look up.

`MESSAGE_REGISTRY` is a single registry of registered asynchronous *messages*, both kinds
(§7.1); the document keeps its frozen filename.

Deliberately absent, and belonging to later slices: emission (RI11's build-time check that
every emission site resolves to an entry, A42), consumer support declarations and their
per-consumer effect-idempotency justifications (§25.1, IX13), upcasters (§18), payload
validation against a registered schema (§28), the canonical schema artifact format (§27),
serialization (§29), routing (item 9), and the durable quarantine and dead-letter records
(§20). None of them is stubbed here.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from enum import Enum

from core.events.errors import UnknownEventType, UnsupportedSchemaVersion

__all__ = (
    "MESSAGE_REGISTRY",
    "MessageKind",
    "MessageRegistry",
    "MessageStatus",
    "RegisteredMessage",
)


class MessageKind(Enum):
    """The mandatory `EVENT` / `COMMAND` discriminator (§7).

    An `EVENT` states that a fact happened and may have any number of consumers, including
    none. A `COMMAND` asks one owner to do one thing and has exactly one handling owner.
    `kind` is fixed for the life of a type (KD4, RI12) and is registry-derived rather than
    an envelope field (EN5).
    """

    EVENT = "EVENT"
    COMMAND = "COMMAND"


class MessageStatus(Enum):
    """The registry lifecycle (§25.2).

    Transitions are one-way, `DRAFT -> ACTIVE -> DEPRECATED -> RETIRED`, and no status ever
    moves backwards (RG1). `DEPRECATED` is not a soft delete: such a version must not be
    newly emitted, but may still arrive from backlog, retry, quarantine or replay, so
    consumer support remains a live obligation (RG5). Reviving a retired version is not
    possible; the answer is a new version (RG2).
    """

    DRAFT = "DRAFT"
    ACTIVE = "ACTIVE"
    DEPRECATED = "DEPRECATED"
    RETIRED = "RETIRED"


@dataclass(frozen=True, slots=True, kw_only=True)
class RegisteredMessage:
    """One registered `(event_type, schema_version)` and its two mandatory attributes.

    Only the fields the *runtime* lookup needs are modelled. The rest of the registry
    entry — semantic owner (derivable from the owner-qualified name), payload contract
    location, producers, per-consumer declarations, lineage, exposure and notes — lives in
    the checked-in registry document, whose reviewed edit is the act of registration.
    """

    event_type: str
    schema_version: int
    kind: MessageKind
    status: MessageStatus

    def __post_init__(self) -> None:
        if type(self.event_type) is not str:
            raise TypeError(f"event_type must be a string, got {type(self.event_type).__name__}")
        if type(self.schema_version) is not int:
            raise TypeError(
                f"schema_version must be an int, got {type(self.schema_version).__name__}"
            )
        if self.schema_version < 1:
            raise ValueError(
                f"schema_version starts at 1 and strictly increases within a type, got "
                f"{self.schema_version}"
            )
        if type(self.kind) is not MessageKind:
            raise TypeError(f"kind must be a MessageKind, got {type(self.kind).__name__}")
        if type(self.status) is not MessageStatus:
            raise TypeError(f"status must be a MessageStatus, got {type(self.status).__name__}")


class MessageRegistry:
    """An immutable index of registered messages, keyed by `(event_type, schema_version)`."""

    __slots__ = ("_by_key", "_types")

    def __init__(self, entries: Iterable[RegisteredMessage] = ()) -> None:
        by_key: dict[tuple[str, int], RegisteredMessage] = {}
        for entry in entries:
            if type(entry) is not RegisteredMessage:
                raise TypeError(
                    f"a registry entry must be a RegisteredMessage, got {type(entry).__name__}"
                )
            key = (entry.event_type, entry.schema_version)
            if key in by_key:
                raise ValueError(f"(event_type, schema_version) is unique; {key!r} appears twice")
            by_key[key] = entry
        self._by_key = by_key
        self._types = frozenset(event_type for event_type, _ in by_key)

    def __len__(self) -> int:
        return len(self._by_key)

    @property
    def entries(self) -> tuple[RegisteredMessage, ...]:
        return tuple(self._by_key.values())

    def lookup(self, *, event_type: str, schema_version: int) -> RegisteredMessage:
        """Resolve an exact `(event_type, schema_version)`, or fail with a reason.

        The two failures are kept apart because §20 treats them as distinct rejection
        reasons that a quarantine record must be able to state. Neither is ever resolved by
        a fallback: no nearest version, no `max(supported)`, no "treat it as the latest",
        no default branch (QU2, QU3, CS2-CS5).
        """
        entry = self._by_key.get((event_type, schema_version))
        if entry is not None:
            return entry
        if event_type not in self._types:
            raise UnknownEventType(f"no registered message carries the event_type {event_type!r}")
        raise UnsupportedSchemaVersion(
            f"{event_type!r} is registered, but not at schema_version {schema_version}"
        )


#: RG8: the registry ships with no entries. Each owning module registers its own messages in
#: its own phase, by a reviewed edit to the registry document and an entry added here.
MESSAGE_REGISTRY = MessageRegistry()
