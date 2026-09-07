"""The payload codec: determinism, the byte guarantee, and the reserved-name gate.

Item 8 IX3/PD5/SZ4 and item 9 C77 both rest on this module, so the properties asserted here
are the ones those checks name — one logical payload, one byte string; the stored bytes are
the replayed bytes; and no payload declares an envelope or trace slot as one of its own fields.
"""

from __future__ import annotations

import pytest

from core.events.codec import RESERVED_PAYLOAD_FIELDS, decode, encode, fingerprint, is_fingerprint
from core.events.errors import InvalidPayload, MessageContractError


class TestDeterminism:
    def test_key_order_does_not_change_the_bytes(self) -> None:
        """PD5/SZ4: the same logical fact produces the same canonical form.

        Without this, IX5 could not be decided at all: two spellings of one payload would
        fingerprint differently and read as an integrity violation.
        """
        assert encode({"b": 2, "a": 1}) == encode({"a": 1, "b": 2})

    def test_the_fingerprint_follows_the_bytes(self) -> None:
        assert fingerprint(encode({"b": 2, "a": 1})) == fingerprint(encode({"a": 1, "b": 2}))

    def test_materially_different_content_fingerprints_differently(self) -> None:
        assert fingerprint(encode({"a": 1})) != fingerprint(encode({"a": 2}))

    def test_canonical_text_round_trips_to_an_equal_value(self) -> None:
        payload = {"order": {"items": [1, 2, 3]}, "note": "ünïcode"}
        assert decode(encode(payload)) == payload

    def test_encoding_the_decoded_text_reproduces_the_same_bytes(self) -> None:
        """C77's byte guarantee, at the codec level: nothing drifts on a round trip."""
        text = encode({"z": [1, {"y": True, "x": None}], "a": "value"})
        assert encode(decode(text)) == text


class TestNonCanonicalInputIsRefused:
    def test_whitespace_is_not_silently_normalised(self) -> None:
        """A normalising decoder would make the stored bytes and the compared bytes differ."""
        with pytest.raises(InvalidPayload):
            decode('{"a": 1}')

    def test_unsorted_keys_are_refused(self) -> None:
        with pytest.raises(InvalidPayload):
            decode('{"b":2,"a":1}')

    def test_a_fingerprint_over_non_canonical_text_is_refused(self) -> None:
        with pytest.raises(InvalidPayload):
            fingerprint('{"a": 1}')


class TestFloatsAreBanned:
    def test_a_float_in_a_payload_is_refused(self) -> None:
        """Money is integer minor units with an explicit currency; nothing else may be a float."""
        with pytest.raises(InvalidPayload, match="minor units"):
            encode({"amount": 10.5})

    def test_a_nested_float_is_refused(self) -> None:
        with pytest.raises(InvalidPayload, match=r"\$\.order\.total"):
            encode({"order": {"total": 1.0}})

    def test_a_float_inside_a_list_is_refused(self) -> None:
        with pytest.raises(InvalidPayload, match=r"\$\.rates\[1\]"):
            encode({"rates": [1, 2.5]})

    def test_a_float_in_decoded_text_is_refused(self) -> None:
        with pytest.raises(InvalidPayload):
            decode('{"amount":1.5}')

    def test_nan_and_infinity_are_refused(self) -> None:
        for constant in ("NaN", "Infinity", "-Infinity"):
            with pytest.raises(InvalidPayload):
                decode(f'{{"x":{constant}}}')


class TestReservedFieldNames:
    """A61 / EV3 / item 8 EN11: the envelope is not payload."""

    @pytest.mark.parametrize("field", sorted(RESERVED_PAYLOAD_FIELDS))
    def test_every_reserved_name_is_refused_at_the_top_level(self, field: str) -> None:
        with pytest.raises(InvalidPayload, match="envelope or trace slot"):
            encode({field: "anything"})

    def test_the_four_tce_slots_are_among_the_reserved_names(self) -> None:
        assert {
            "trace_id",
            "producer_span_id",
            "request_id",
            "causation_event_id",
        } <= RESERVED_PAYLOAD_FIELDS

    def test_an_ordinary_business_field_is_accepted(self) -> None:
        """The gate is a closed list, not a heuristic over anything that looks like an id."""
        assert encode({"reference_id": "abc"}) == '{"reference_id":"abc"}'


class TestBounds:
    def test_an_oversized_payload_is_refused_rather_than_truncated(self) -> None:
        with pytest.raises(InvalidPayload, match="bounded fact"):
            encode({"blob": "x" * 300_000})

    def test_a_payload_at_the_bound_is_accepted(self) -> None:
        assert encode({"blob": "x" * 200_000})


class TestShapeRefusals:
    def test_a_non_json_shape_is_refused_rather_than_coerced(self) -> None:
        with pytest.raises(InvalidPayload):
            encode({"when": object()})

    def test_a_non_string_key_is_refused(self) -> None:
        with pytest.raises(InvalidPayload, match="keys are strings"):
            encode({1: "one"})

    def test_a_payload_error_is_not_a_domain_error(self) -> None:
        """QU10/VL4: a contract-integrity failure must not be catchable as a business outcome.

        Asserted through the hierarchy rather than by inspecting a class attribute, because
        the property that matters is what `except` clauses will and will not catch.
        """
        assert issubclass(InvalidPayload, MessageContractError)
        from core.errors import DomainError

        assert not issubclass(InvalidPayload, DomainError)


class TestIsFingerprint:
    def test_a_real_digest_is_recognised(self) -> None:
        assert is_fingerprint(fingerprint(encode({"a": 1})))

    @pytest.mark.parametrize(
        "value",
        ["", "abc", "A" * 64, "g" * 64, "0" * 63, "0" * 65, None, 0],
    )
    def test_anything_else_is_not(self, value: object) -> None:
        assert not is_fingerprint(value)
