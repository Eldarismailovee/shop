"""`request_id` shape and minting (item 10 RQ6-RQ8, PR4-PR6, PV2)."""

from __future__ import annotations

import pytest

from core.observability.request_id import (
    REQUEST_ID_MAX_LENGTH,
    new_request_id,
    normalised_request_id,
)


class TestNormalisation:
    def test_an_ordinary_opaque_token_is_kept_verbatim(self) -> None:
        assert normalised_request_id("9f2c1a7b4e") == "9f2c1a7b4e"

    def test_a_uuid_shaped_edge_value_is_accepted(self) -> None:
        """A reverse proxy that mints UUIDs is the common deployment (master `# 23.1`)."""
        value = "6f1b1f4e-9c33-7b0a-8e2d-1a2b3c4d5e6f"
        assert normalised_request_id(value) == value

    @pytest.mark.parametrize("placeholder", ["-", "none", "null", "unknown", "NONE", "Null"])
    def test_a_placeholder_normalises_to_absent(self, placeholder: str) -> None:
        """PR6 — present or absent, with no third state, in any casing."""
        assert normalised_request_id(placeholder) is None

    @pytest.mark.parametrize("value", ["", "has space", "tab\there", "line\nbreak", "café"])
    def test_a_malformed_value_normalises_to_absent(self, value: str) -> None:
        assert normalised_request_id(value) is None

    def test_an_over_long_value_normalises_to_absent_rather_than_being_truncated(self) -> None:
        """PR5 — never padded, never trimmed to fit; a bad value becomes absent."""
        assert normalised_request_id("a" * (REQUEST_ID_MAX_LENGTH + 1)) is None

    def test_a_value_at_the_bound_is_accepted(self) -> None:
        value = "a" * REQUEST_ID_MAX_LENGTH
        assert normalised_request_id(value) == value

    @pytest.mark.parametrize("value", [None, 17, b"bytes", ["list"], object()])
    def test_a_non_string_normalises_to_absent_and_never_raises(self, value: object) -> None:
        """The boundary decides; it does not fail the request that carried a bad header."""
        assert normalised_request_id(value) is None


class TestMinting:
    def test_a_minted_value_is_valid_by_construction(self) -> None:
        assert normalised_request_id(new_request_id()) is not None

    def test_minted_values_do_not_repeat(self) -> None:
        assert len({new_request_id() for _ in range(1000)}) == 1000

    def test_a_minted_value_is_opaque_and_carries_no_identity(self) -> None:
        """RQ7/PV2 — random hex, so nothing about the caller can be read back out of it."""
        value = new_request_id()
        assert len(value) == 32
        assert set(value) <= set("0123456789abcdef")
