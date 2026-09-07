"""The semantic request fingerprint and its canonical codec (ADR-0015 §5)."""

from __future__ import annotations

import hashlib

import pytest

from core.idempotency import canonical
from core.idempotency.bounds import (
    FINGERPRINT_HEX_LENGTH,
    MAX_FINGERPRINT_MATERIAL_BYTES,
)
from core.idempotency.errors import InvalidClaimInput
from core.idempotency.fingerprint import canonicalize, fingerprint, is_fingerprint


def test_the_digest_is_sha256_over_the_canonical_bytes() -> None:
    text = canonicalize({"b": 2, "a": 1})
    assert text == '{"a":1,"b":2}'
    assert fingerprint(text) == hashlib.sha256(text.encode("utf-8")).hexdigest()
    assert len(fingerprint(text)) == FINGERPRINT_HEX_LENGTH


def test_key_order_does_not_change_the_digest() -> None:
    assert canonicalize({"a": 1, "b": 2}) == canonicalize({"b": 2, "a": 1})


def test_a_materially_different_input_changes_the_digest() -> None:
    assert fingerprint(canonicalize({"qty": 1})) != fingerprint(canonicalize({"qty": 2}))


def test_non_canonical_text_is_refused_rather_than_normalised() -> None:
    """A call site that builds material inconsistently must surface, not be papered over."""
    with pytest.raises(InvalidClaimInput, match="canonical form"):
        fingerprint('{"b": 2, "a": 1}')


def test_whitespace_alone_is_refused() -> None:
    with pytest.raises(InvalidClaimInput, match="canonical form"):
        fingerprint('{"a": 1}')


def test_invalid_json_is_refused() -> None:
    with pytest.raises(InvalidClaimInput, match="not valid JSON"):
        fingerprint("{not json")


def test_a_non_string_is_refused() -> None:
    with pytest.raises(InvalidClaimInput):
        fingerprint({"a": 1})  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Floats: money is integer minor units with an explicit currency
# ---------------------------------------------------------------------------


def test_a_float_in_material_is_refused() -> None:
    with pytest.raises(InvalidClaimInput, match="float"):
        canonicalize({"total": 19.99})


def test_a_nested_float_is_refused() -> None:
    with pytest.raises(InvalidClaimInput, match=r"appears at \$\.items\[0\]\.price"):
        canonicalize({"items": [{"price": 1.5}]})


def test_a_fractional_number_in_text_is_refused() -> None:
    with pytest.raises(InvalidClaimInput, match="fractional number"):
        fingerprint('{"total":19.99}')


def test_nan_is_refused() -> None:
    with pytest.raises(InvalidClaimInput):
        fingerprint('{"x":NaN}')


def test_minor_units_are_the_admissible_spelling() -> None:
    assert canonicalize({"amount_minor": 1999, "currency": "MDL"})


# ---------------------------------------------------------------------------
# Shape and bounds
# ---------------------------------------------------------------------------


def test_a_non_json_value_is_refused() -> None:
    with pytest.raises(InvalidClaimInput, match="JSON-shaped"):
        canonicalize({"seen": {1, 2}})


def test_a_non_string_key_is_refused() -> None:
    with pytest.raises(InvalidClaimInput, match="string"):
        canonicalize({1: "a"})


def test_material_over_the_bound_is_refused() -> None:
    oversized = {"k": "x" * (MAX_FINGERPRINT_MATERIAL_BYTES + 1)}
    with pytest.raises(InvalidClaimInput, match="over the"):
        canonicalize(oversized)


def test_a_bool_is_not_silently_an_int() -> None:
    assert canonicalize({"flag": True}) != canonicalize({"flag": 1})


# ---------------------------------------------------------------------------
# is_fingerprint — the exact form the column constrains
# ---------------------------------------------------------------------------


def test_a_real_digest_is_recognised() -> None:
    assert is_fingerprint(fingerprint(canonicalize({"a": 1})))


@pytest.mark.parametrize(
    "value",
    [
        "",
        "0" * 63,
        "0" * 65,
        "0" * 63 + "A",  # uppercase hex is not the stored form
        "0" * 63 + "g",
        b"0" * 64,
        None,
    ],
)
def test_anything_else_is_not_a_fingerprint(value: object) -> None:
    assert not is_fingerprint(value)


# ---------------------------------------------------------------------------
# The codec is shared with the stored result, so the two cannot drift
# ---------------------------------------------------------------------------


def test_the_codec_round_trips_canonically() -> None:
    text = canonical.encode({"b": [1, 2], "a": None})
    assert canonical.encode(canonical.decode(text)) == text


def test_a_tuple_encodes_as_a_json_array() -> None:
    assert canonical.encode({"a": (1, 2)}) == '{"a":[1,2]}'
