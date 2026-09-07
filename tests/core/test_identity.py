"""`PublicId` and `EventId`: two runtime-distinct semantic types over one value space.

Item 11 §22-§34, ADR-0013. The `C` ids are item 11 §40.2's behavioural checks.
"""

from __future__ import annotations

import dataclasses
import uuid

import pytest

from core.events.identity import EventId
from core.public_id import PublicId

IDENTITY_TYPES = (PublicId, EventId)

# The two types share no supertype on purpose (TY3), so the parametrised cases name both
# rather than a bare `type` — which would declare neither `.new()` nor `.parse()`.
IdentityType = type[PublicId] | type[EventId]

# ---------------------------------------------------------------------------
# Generation and canonical form
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("identity", IDENTITY_TYPES)
def test_generation_yields_distinct_valid_version_7_identifiers(identity: IdentityType) -> None:
    """C117 / GN1: standards-conforming UUIDv7, distinct across a batch."""
    minted = [identity.new() for _ in range(2_000)]
    assert all(one.value.version == 7 for one in minted)
    assert len(set(minted)) == len(minted)


@pytest.mark.parametrize("identity", IDENTITY_TYPES)
def test_the_canonical_form_round_trips_exactly(identity: IdentityType) -> None:
    """C119 / PA2, PA6: rendering yields the lowercase hyphenated form; parsing it returns
    the same value; the rendered form of a parsed canonical value is the input verbatim."""
    original = identity.new()
    rendered = str(original)
    assert rendered == rendered.lower()
    assert len(rendered) == 36 and rendered.count("-") == 4
    assert identity.parse(rendered) == original
    assert str(identity.parse(rendered)) == rendered


@pytest.mark.parametrize("identity", IDENTITY_TYPES)
@pytest.mark.parametrize(
    "spelling",
    [
        "018F6C1E-4A2B-7C3D-8E4F-5A6B7C8D9E0F",  # uppercase hex
        "{018f6c1e-4a2b-7c3d-8e4f-5a6b7c8d9e0f}",  # brace-wrapped
        "urn:uuid:018f6c1e-4a2b-7c3d-8e4f-5a6b7c8d9e0f",  # urn-prefixed
        "018f6c1e4a2b7c3d8e4f5a6b7c8d9e0f",  # unhyphenated
        " 018f6c1e-4a2b-7c3d-8e4f-5a6b7c8d9e0f",  # padded
    ],
)
def test_a_non_canonical_spelling_is_rejected_not_normalised(
    identity: IdentityType, spelling: str
) -> None:
    """C119 / PA3: several accepted spellings would give one resource several external
    identities, and therefore several URLs, cache keys and crawl targets."""
    with pytest.raises(ValueError):
        identity.parse(spelling)


@pytest.mark.parametrize("identity", IDENTITY_TYPES)
@pytest.mark.parametrize(
    "text", ["", "not-a-uuid", "018f6c1e-4a2b-7c3d-8e4f-5a6b7c8d9e0", "0" * 36]
)
def test_malformed_text_is_rejected_at_the_boundary(identity: IdentityType, text: str) -> None:
    """PA4: a malformed locator never becomes a database query."""
    with pytest.raises(ValueError):
        identity.parse(text)


@pytest.mark.parametrize("identity", IDENTITY_TYPES)
def test_parsing_a_non_string_is_a_type_error(identity: IdentityType) -> None:
    with pytest.raises(TypeError):
        identity.parse(uuid.uuid7())  # type: ignore[arg-type]


@pytest.mark.parametrize("identity", IDENTITY_TYPES)
@pytest.mark.parametrize("factory", [uuid.uuid4, uuid.uuid1, lambda: uuid.UUID(int=0)])
def test_a_uuid_of_another_version_never_becomes_an_identity(
    identity: IdentityType, factory
) -> None:
    """C118 / PA1: a structurally valid UUID of another version is not a platform identity."""
    foreign = factory()
    with pytest.raises(ValueError):
        identity(value=foreign)
    with pytest.raises(ValueError):
        identity.parse(str(foreign))


@pytest.mark.parametrize("identity", IDENTITY_TYPES)
def test_a_foreign_uuid_needs_an_explicit_visible_construction_step(identity: IdentityType) -> None:
    """C123 / EI5: a foreign *v7* passes every structural test — shape is not provenance, so
    admitting one is a deliberate act at the boundary that owns the mapping, never implicit.
    The primitive's contribution is that no implicit coercion from a bare UUID exists."""
    provider_value = uuid.uuid7()  # a well-formed v7 that happens to be somebody else's
    assert identity(value=provider_value).value == provider_value  # explicit, and visible
    assert identity.new() != provider_value
    assert provider_value != identity(value=provider_value)


@pytest.mark.parametrize("identity", IDENTITY_TYPES)
@pytest.mark.parametrize("value", [1, "018f6c1e-4a2b-7c3d-8e4f-5a6b7c8d9e0f", None, 2**64])
def test_an_internal_bigint_or_bare_text_cannot_occupy_an_identity_position(
    identity: IdentityType, value: object
) -> None:
    """C120 / TY1: the internal `bigint` and the external UUIDv7 are not confusable."""
    with pytest.raises(TypeError):
        identity(value=value)  # type: ignore[arg-type]  # the rejection is the assertion


# ---------------------------------------------------------------------------
# Immutability, equality and hashing
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("identity", IDENTITY_TYPES)
def test_an_identity_is_immutable_and_slotted(identity: IdentityType) -> None:
    """IM1: assigned once, never rewritten."""
    one = identity.new()
    with pytest.raises(dataclasses.FrozenInstanceError):
        one.value = uuid.uuid7()  # type: ignore[misc]  # frozen at runtime, not only statically
    with pytest.raises(AttributeError):
        one.note = "x"  # type: ignore[union-attr]  # __slots__ admits no new attribute


@pytest.mark.parametrize("identity", IDENTITY_TYPES)
def test_equality_and_hashing_follow_the_ordinary_contract_within_a_type(
    identity: IdentityType,
) -> None:
    """EQ3, EQ5: equal iff the same underlying value; hashable, consistently."""
    value = uuid.uuid7()
    assert identity(value=value) == identity(value=value)
    assert identity(value=value) != identity(value=uuid.uuid7())
    assert hash(identity(value=value)) == hash(identity(value=value))
    assert {identity(value=value): "x"}[identity(value=value)] == "x"


@pytest.mark.parametrize("identity", IDENTITY_TYPES)
def test_an_identity_never_equals_the_bare_uuid_it_carries(identity: IdentityType) -> None:
    """PI7: the underlying representation may be a UUID; a bare UUID is never the identity."""
    value = uuid.uuid7()
    assert identity(value=value) != value
    assert value != identity(value=value)


@pytest.mark.parametrize("identity", IDENTITY_TYPES)
def test_no_business_ordering_is_defined(identity: IdentityType) -> None:
    """EQ6, TS3, MI7: no business rule, sequence or "which came first" rests on an identity."""
    for operator in ("__lt__", "__le__", "__gt__", "__ge__"):
        assert getattr(identity, operator) is getattr(object, operator)


# ---------------------------------------------------------------------------
# The distinction itself (ADR-0013, TY5, EQ4, TX5)
# ---------------------------------------------------------------------------


def test_the_two_types_are_distinct_at_runtime_over_identical_bytes() -> None:
    """C127: the frozen three cases, asserted together so the test pins the distinction
    rather than merely a failure."""
    value = uuid.uuid7()
    locator, message = PublicId(value=value), EventId(value=value)

    assert PublicId(value=value) == locator
    assert EventId(value=value) == message
    assert locator != message
    assert message != locator
    assert len({locator, message}) == 2  # unequal values, whatever their hashes


def test_neither_type_is_a_subclass_of_the_other() -> None:
    """TY3: not mutually assignable, and no shared supertype makes them interchangeable."""
    assert not issubclass(PublicId, EventId)
    assert not issubclass(EventId, PublicId)
    assert PublicId.__mro__[1:] == (object,)
    assert EventId.__mro__[1:] == (object,)


def test_neither_resolves_in_the_other_s_lookup_path() -> None:
    """C127: a locator handed to a message-keyed index finds nothing, and vice versa."""
    value = uuid.uuid7()
    by_message = {EventId(value=value): "handled"}
    assert PublicId(value=value) not in by_message
    by_locator = {PublicId(value=value): "the order"}
    assert EventId(value=value) not in by_locator


def test_the_shared_uuid7_mechanism_is_not_a_core_surface() -> None:
    """TX3, TX4 / A82: one algorithm, two types, and no exported generic utility.

    The import rule is enforced by `tools/arch_check`; this asserts the naming that tells a
    reader the same thing, and that neither semantic module re-exports the mechanism.
    """
    import core._uuid7 as mechanism

    assert mechanism.__name__.rsplit(".", 1)[-1].startswith("_")

    import core.events.identity as identity_module
    import core.public_id as public_id_module

    assert public_id_module.__all__ == ("PublicId",)
    assert identity_module.__all__ == ("EventId",)


def test_the_embedded_timestamp_is_never_decoded() -> None:
    """TS1-TS5, A83: neither type exposes any route to the time component, so clock
    behaviour cannot change a business outcome."""
    for identity in IDENTITY_TYPES:
        exposed = {name for name in dir(identity) if not name.startswith("__")}
        assert exposed == {"new", "parse", "value"}
