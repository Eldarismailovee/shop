"""Strict data masking (master `# 23.1`'s four forbidden categories, `# 21`)."""

from __future__ import annotations

import pytest

from core.observability.masking import MASKED, TRUNCATED, is_sensitive, masked


class TestVocabulary:
    @pytest.mark.parametrize(
        "name",
        [
            # Master `# 23.1` item 1: passwords and their hashes.
            "password",
            "password_hash",
            "passwordHash",
            "user.password",
            "PWD",
            # Item 2: card and bank data.
            "card_number",
            "cardholder_name",
            "cvv",
            "pan",
            "iban",
            # Item 3: integration secrets and cryptographic keys.
            "api_key",
            "apiKey",
            "secret",
            "signing_key",
            "webhook_signature",
            "authorization",
            "access_token",
            # Item 4: decrypted vouchers and digital licence codes.
            "voucher_code",
            "license_key",
            "serial",
            # ADR-0015 §4 / AU6: the idempotency key never reaches a line either.
            "idempotency_key",
            # Personal data (`# 21`).
            "email",
            "phone_number",
            "shipping_address",
        ],
    )
    def test_a_sensitive_name_is_recognised(self, name: str) -> None:
        assert is_sensitive(name) is True

    @pytest.mark.parametrize(
        "name",
        [
            "order_id",
            "scope",
            "author",  # not `auth`
            "pinned_at",  # not `pin`
            "status",
            "latency_ms",
            "http_status",
            "event_type",
            "schema_version",
            "request_fingerprint",
            "principal_kind",
        ],
    )
    def test_an_ordinary_name_is_left_alone(self, name: str) -> None:
        assert is_sensitive(name) is False

    def test_a_non_string_name_is_not_sensitive(self) -> None:
        assert is_sensitive(None) is False
        assert is_sensitive(7) is False


class TestMasking:
    def test_a_sensitive_value_is_replaced_and_a_neighbour_is_kept(self) -> None:
        assert masked({"order_id": 42, "password": "hunter2"}) == {
            "order_id": 42,
            "password": MASKED,
        }

    def test_masking_reaches_into_nested_structures(self) -> None:
        source = {"payment": {"provider": "maib", "card": {"pan": "4111111111111111"}}}
        assert masked(source) == {"payment": {"provider": "maib", "card": MASKED}}

    def test_masking_reaches_into_sequences_of_mappings(self) -> None:
        source = {"attempts": [{"token": "abc", "status": "failed"}]}
        assert masked(source) == {"attempts": [{"token": MASKED, "status": "failed"}]}

    def test_a_tuple_or_set_becomes_a_list_and_is_still_walked(self) -> None:
        assert masked({"items": ({"secret": 1},)}) == {"items": [{"secret": MASKED}]}

    def test_a_string_is_a_value_and_is_never_walked_into(self) -> None:
        assert masked("password=hunter2") == "password=hunter2"

    def test_a_scalar_passes_through_unchanged(self) -> None:
        assert masked(42) == 42
        assert masked(None) is None

    def test_a_deeply_nested_structure_is_truncated_rather_than_walked_forever(self) -> None:
        deep: dict[str, object] = {"leaf": 1}
        for _ in range(12):
            deep = {"next": deep}
        assert TRUNCATED in repr(masked(deep))

    def test_a_non_string_key_is_still_rendered_and_checked(self) -> None:
        assert masked({7: "value"}) == {"7": "value"}

    def test_masking_does_not_mutate_its_input(self) -> None:
        source = {"password": "hunter2"}
        masked(source)
        assert source == {"password": "hunter2"}
