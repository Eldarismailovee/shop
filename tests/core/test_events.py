"""The `core.events` mechanism: a closed envelope and an **empty** registry.

Item 8 §10.1, §20, §25, §26; item 10 §5-§11; ADR-0009, ADR-0011, ADR-0013.

No sample `event_type` is created to give the registry something to hold. Every case that
needs a registered message builds one locally, so the shipped registry stays provably empty
and no business message contract is invented in order to test the mechanism.
"""

from __future__ import annotations

import ast
import dataclasses
from datetime import UTC, datetime, timedelta, timezone
from typing import Any

import pytest

from core.events.envelope import Envelope
from core.events.errors import MessageContractError, UnknownEventType, UnsupportedSchemaVersion
from core.events.identity import EventId
from core.events.registry import (
    MESSAGE_REGISTRY,
    MessageKind,
    MessageRegistry,
    MessageStatus,
    RegisteredMessage,
)
from core.public_id import PublicId
from tests.conftest import REPO_ROOT

OCCURRED_AT = datetime(2026, 9, 7, 12, 0, tzinfo=UTC)

#: A local fixture, not a registration: this name exists only inside this module.
FIXTURE_TYPE = "example_owner.something_happened"


def envelope(**overrides: object) -> Envelope:
    fields: dict[str, object] = {
        "event_id": EventId.new(),
        "event_type": FIXTURE_TYPE,
        "schema_version": 1,
        "occurred_at": OCCURRED_AT,
    }
    fields.update(overrides)
    return Envelope(**fields)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# The registry ships empty
# ---------------------------------------------------------------------------


def test_the_registry_begins_empty() -> None:
    """RG8: populating the registry is each owning module's own phase."""
    assert len(MESSAGE_REGISTRY) == 0
    assert MESSAGE_REGISTRY.entries == ()


def test_no_business_message_appears_by_default() -> None:
    """OW4, A46: `core` owns no business message type. Every name below is a master
    illustration or a neighbouring item's vocabulary, and none of them is registered."""
    for candidate in (
        "catalog.project.batch",
        "inventory.reservation_changed",
        "orders.order_placed",
        "payments.payment_captured",
        "review.approved",
        "storefront.reproject_products",
    ):
        with pytest.raises(UnknownEventType):
            MESSAGE_REGISTRY.lookup(event_type=candidate, schema_version=1)


def test_the_core_events_package_declares_no_payload_contract() -> None:
    """A46: no module under `core/events` defines a message payload or business vocabulary."""
    package = REPO_ROOT / "core" / "events"
    declared: set[str] = set()
    for path in sorted(package.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        declared |= {n.name for n in ast.walk(tree) if isinstance(n, ast.ClassDef)}
    assert declared == {
        "EventId",
        "Envelope",
        "MessageContractError",
        "MessageKind",
        "MessageRegistry",
        "MessageStatus",
        "RegisteredMessage",
        "UnknownEventType",
        "UnsupportedSchemaVersion",
    }


def test_the_checked_in_registry_document_still_has_no_entries() -> None:
    """The runtime index and the reviewed document agree: both are empty by design."""
    document = (REPO_ROOT / "docs" / "architecture" / "events" / "event-registry.md").read_text(
        encoding="utf-8"
    )
    assert "no entries" in document


# ---------------------------------------------------------------------------
# Registry lookup and its two rejection reasons
# ---------------------------------------------------------------------------


def test_lookup_resolves_an_exact_registered_pair() -> None:
    entry = RegisteredMessage(
        event_type=FIXTURE_TYPE,
        schema_version=2,
        kind=MessageKind.EVENT,
        status=MessageStatus.ACTIVE,
    )
    registry = MessageRegistry([entry])
    assert registry.lookup(event_type=FIXTURE_TYPE, schema_version=2) is entry
    assert registry.entries == (entry,)
    assert len(registry) == 1


def test_an_unknown_type_and_an_unsupported_version_are_different_failures() -> None:
    """§20: a quarantine record must be able to state *which* reason applied."""
    registry = MessageRegistry(
        [
            RegisteredMessage(
                event_type=FIXTURE_TYPE,
                schema_version=1,
                kind=MessageKind.EVENT,
                status=MessageStatus.ACTIVE,
            )
        ]
    )
    with pytest.raises(UnknownEventType):
        registry.lookup(event_type="example_owner.other_thing", schema_version=1)
    with pytest.raises(UnsupportedSchemaVersion):
        registry.lookup(event_type=FIXTURE_TYPE, schema_version=2)


def test_lookup_never_falls_back_to_a_nearby_version() -> None:
    """QU2, QU3, CS2-CS5: not the latest, not the nearest, not the most similar."""
    registry = MessageRegistry(
        [
            RegisteredMessage(
                event_type=FIXTURE_TYPE,
                schema_version=version,
                kind=MessageKind.EVENT,
                status=MessageStatus.ACTIVE,
            )
            for version in (1, 2)
        ]
    )
    with pytest.raises(UnsupportedSchemaVersion):
        registry.lookup(event_type=FIXTURE_TYPE, schema_version=3)
    with pytest.raises(UnsupportedSchemaVersion):
        registry.lookup(event_type=FIXTURE_TYPE, schema_version=99)


def test_the_registry_key_is_unique() -> None:
    """RI1: `(event_type, schema_version)` is unique."""
    duplicate = RegisteredMessage(
        event_type=FIXTURE_TYPE,
        schema_version=1,
        kind=MessageKind.EVENT,
        status=MessageStatus.ACTIVE,
    )
    with pytest.raises(ValueError):
        MessageRegistry([duplicate, duplicate])


def test_an_entry_is_immutable_and_structurally_validated() -> None:
    entry = RegisteredMessage(
        event_type=FIXTURE_TYPE,
        schema_version=1,
        kind=MessageKind.COMMAND,
        status=MessageStatus.DRAFT,
    )
    with pytest.raises(dataclasses.FrozenInstanceError):
        entry.status = MessageStatus.ACTIVE  # type: ignore[misc]

    # Each case is a deliberately ill-typed field: the point is that the *runtime*
    # rejects it, so the payload is assembled as `Any` rather than as the valid shape.
    broken: dict[str, Any]
    for broken in (
        {"schema_version": 0},  # RI5: versions start at 1
        {"schema_version": True},  # a bool is not a version
        {"kind": "EVENT"},  # the discriminator is a value, not a string
        {"status": "ACTIVE"},
        {"event_type": 1},
    ):
        payload: dict[str, Any] = {
            "event_type": FIXTURE_TYPE,
            "schema_version": 1,
            "kind": MessageKind.EVENT,
            "status": MessageStatus.ACTIVE,
            **broken,
        }
        with pytest.raises((TypeError, ValueError)):
            RegisteredMessage(**payload)


def test_the_registry_holds_only_registry_entries() -> None:
    with pytest.raises(TypeError):
        MessageRegistry([{"event_type": FIXTURE_TYPE, "schema_version": 1}])  # type: ignore[list-item]


def test_the_two_closed_registry_vocabularies() -> None:
    """§7.1 `kind` and §25.2 `status`, both closed sets."""
    assert {member.name for member in MessageKind} == {"EVENT", "COMMAND"}
    assert {member.name for member in MessageStatus} == {
        "DRAFT",
        "ACTIVE",
        "DEPRECATED",
        "RETIRED",
    }


# ---------------------------------------------------------------------------
# The envelope: a closed eight-slot shape
# ---------------------------------------------------------------------------


def test_the_envelope_is_exactly_the_four_frozen_fields_plus_the_closed_tce() -> None:
    """EN1, FS1, FS2: one extension point, now spent. There is no second one."""
    assert tuple(field.name for field in dataclasses.fields(Envelope)) == (
        "event_id",
        "event_type",
        "schema_version",
        "occurred_at",
        "trace_id",
        "producer_span_id",
        "request_id",
        "causation_event_id",
    )


def test_the_rejected_field_names_are_absent() -> None:
    """§10 / FS3, EN3, EN7: `correlation_id`, a metadata bag in any spelling, baggage,
    `tracestate`, an ancestry path, and every transport concern."""
    declared = {field.name for field in dataclasses.fields(Envelope)}
    assert not declared & {
        "correlation_id",
        "meta",
        "extra",
        "context",
        "attributes",
        "headers",
        "tags",
        "annotations",
        "baggage",
        "tracestate",
        "causal_path",
        "ancestry",
        "sampled",
        "idempotency_key",
        "queue",
        "routing_key",
        "failure_domain",
        "attempt",
        "worker",
        "priority",
        "kind",
        "producer",
    }


def test_an_envelope_is_immutable_and_slotted() -> None:
    one = envelope()
    with pytest.raises(dataclasses.FrozenInstanceError):
        one.schema_version = 2  # type: ignore[misc]
    with pytest.raises(AttributeError):
        one.retry_count = 1  # type: ignore[attr-defined]


def test_every_tce_field_is_optional_by_construction() -> None:
    """FS5, FS10: absence is a complete state, not a partial one."""
    minimal = envelope()
    assert (
        minimal.trace_id,
        minimal.producer_span_id,
        minimal.request_id,
        minimal.causation_event_id,
    ) == (None, None, None, None)


def test_the_canonical_tce_states_by_origin_all_construct() -> None:
    """PR9: none of the three rows is a degraded case."""
    trace = "4bf92f3577b34da6a3ce929d0e0e4736"
    span = "00f067aa0ba902b7"

    # First hop from a synchronous request: request present, no parent message.
    envelope(trace_id=trace, producer_span_id=span, request_id="r-01HQ")
    # First hop of system origin: no request id at all.
    envelope(trace_id=trace, producer_span_id=span)
    # Child emitted while handling another message: causation present, request inherited.
    envelope(
        trace_id=trace,
        producer_span_id=span,
        request_id="r-01HQ",
        causation_event_id=EventId.new(),
    )
    # Untraced production is legitimate (PR3).
    envelope(request_id="r-01HQ")


def test_a_broken_trace_pair_is_permitted_because_processing_must_continue() -> None:
    """PR2: exactly one of the pair present is an observability defect that is *recorded and
    alerted* while the message is read as untraced and processed normally. Raising here
    would stop the processing the rule requires to continue; recording and alerting belong
    to the capture and consume slice."""
    assert envelope(trace_id="4bf92f3577b34da6a3ce929d0e0e4736").producer_span_id is None
    assert envelope(producer_span_id="00f067aa0ba902b7").trace_id is None


# ---------------------------------------------------------------------------
# Deterministic rejection of invalid mechanism input
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "event_type",
    [
        "",
        "orders",  # NM2/NM3: owner-qualified, so at least two segments
        "Orders.placed",  # NM1: lowercase only
        "orders.Placed",
        "orders..placed",
        "orders.placed.",
        "1orders.placed",
        "orders-service.placed",
        "orders placed",
    ],
)
def test_a_malformed_event_type_is_rejected(event_type: str) -> None:
    with pytest.raises(ValueError):
        envelope(event_type=event_type)


@pytest.mark.parametrize("version", [0, -1])
def test_schema_version_starts_at_one(version: int) -> None:
    """RI5."""
    with pytest.raises(ValueError):
        envelope(schema_version=version)


@pytest.mark.parametrize("version", [True, 1.0, "1", None])
def test_schema_version_is_an_exact_integer(version: object) -> None:
    with pytest.raises(TypeError):
        envelope(schema_version=version)


def test_occurred_at_must_be_an_aware_utc_instant() -> None:
    """TS2, D7: a naive datetime is a contract violation, and one instant has one spelling."""
    with pytest.raises(ValueError):
        envelope(occurred_at=datetime(2026, 9, 7, 12, 0))
    with pytest.raises(ValueError):
        envelope(occurred_at=datetime(2026, 9, 7, 14, 0, tzinfo=timezone(timedelta(hours=2))))
    with pytest.raises(TypeError):
        envelope(occurred_at="2026-09-07T12:00:00Z")


def test_the_event_id_is_an_event_id_and_not_a_locator() -> None:
    """TY3, MI6: a `PublicId` never occupies the envelope identity position."""
    with pytest.raises(TypeError):
        envelope(event_id=PublicId.new())
    with pytest.raises(TypeError):
        envelope(event_id=str(EventId.new()))


@pytest.mark.parametrize(
    "trace_id",
    ["0" * 32, "4BF92F3577B34DA6A3CE929D0E0E4736", "4bf92f35", "z" * 32, ""],
)
def test_a_malformed_trace_id_is_rejected(trace_id: str) -> None:
    """TR2, PR4: 32 lowercase hex, all-zero invalid; never repaired by invention."""
    with pytest.raises(ValueError):
        envelope(trace_id=trace_id)


@pytest.mark.parametrize("span_id", ["0" * 16, "00F067AA0BA902B7", "00f067aa", "z" * 16])
def test_a_malformed_producer_span_id_is_rejected(span_id: str) -> None:
    """SP4."""
    with pytest.raises(ValueError):
        envelope(producer_span_id=span_id)


@pytest.mark.parametrize(
    "request_id", ["", "-", "none", "NONE", "unknown", "null", "a b", "x" * 129]
)
def test_a_placeholder_or_unbounded_request_id_is_rejected(request_id: str) -> None:
    """PR6, RQ6: present or absent, with no third state and no placeholder stand-in."""
    with pytest.raises(ValueError):
        envelope(request_id=request_id)


def test_causation_is_the_same_semantic_type_as_the_identity_it_names() -> None:
    """C126 / CZ4, MI10: `causation_event_id` is exactly `event_id`'s type."""
    fields = {field.name: field.type for field in dataclasses.fields(Envelope)}
    assert fields["causation_event_id"] == "EventId | None"
    with pytest.raises(TypeError):
        envelope(causation_event_id=PublicId.new())


def test_self_causation_is_a_defect() -> None:
    """CZ6."""
    identity = EventId.new()
    with pytest.raises(ValueError):
        envelope(event_id=identity, causation_event_id=identity)


def test_a_dangling_causation_parent_is_expected_and_never_a_validation_failure() -> None:
    """CZ10: the parent's partition may have been archived; that is normal, not an error."""
    assert envelope(causation_event_id=EventId.new()).causation_event_id is not None


def test_the_contract_failure_root_is_not_a_business_error() -> None:
    """VL4, QU10, stated from the events side as well as from `core.errors`."""
    from core.errors import DomainError

    assert issubclass(UnknownEventType, MessageContractError)
    assert issubclass(UnsupportedSchemaVersion, MessageContractError)
    assert not issubclass(MessageContractError, DomainError)
