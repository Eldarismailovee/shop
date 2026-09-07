"""The schema's own guarantees, proved against PostgreSQL rather than against Python.

Every bound this slice chose is a **database** constraint, because a Python-side check is not
a check against `bulk_create`, raw SQL, or a concurrent writer. Each test below writes
directly to the model — bypassing `claim_or_resolve` entirely — so what is proved is that the
database refuses it, not that the mechanism happens not to ask.
"""

from __future__ import annotations

from datetime import timedelta

import pytest
from django.db import IntegrityError, connection, transaction
from django.db.utils import DataError
from django.utils import timezone

from core.idempotency.bounds import (
    FINGERPRINT_HEX_LENGTH,
    MAX_KEY_LENGTH,
    MAX_RESULT_DETAIL_BYTES,
    MAX_SCOPE_LENGTH,
)
from core.idempotency.models import IdempotencyKey
from core.public_id import PublicId

pytestmark = pytest.mark.django_db

#: The exact constraint set this slice deploys. Losing one in a later migration fails here.
EXPECTED_CONSTRAINTS = {
    "core_idem_scope_key_uniq",
    "core_idem_identity_not_empty",
    "core_idem_principal_shape_valid",
    "core_idem_fingerprint_is_sha256",
    "core_idem_expiry_after_created",
    "core_idem_result_shape_valid",
}

_DIGEST = "a" * FINGERPRINT_HEX_LENGTH


def _row(**overrides: object) -> IdempotencyKey:
    now = timezone.now()
    fields: dict[str, object] = {
        "scope": "fixture.do_thing",
        "key": "k",
        "principal_kind": "ACTOR",
        "principal_id": PublicId.new().value,
        "principal_purpose": None,
        "request_fingerprint": _DIGEST,
        "created_at": now,
        "expires_at": now + timedelta(hours=24),
        "result_kind": "created",
        "result_public_id": None,
        "result_detail": None,
    }
    fields.update(overrides)
    return IdempotencyKey(**fields)


def _refuses(row: IdempotencyKey, constraint: str) -> None:
    with pytest.raises(IntegrityError, match=constraint), transaction.atomic():
        row.save(force_insert=True)


# ---------------------------------------------------------------------------
# The constraints exist, by name
# ---------------------------------------------------------------------------


def test_every_declared_constraint_is_deployed() -> None:
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT conname FROM pg_constraint "
            "WHERE conrelid = %s::regclass AND contype IN ('u', 'c')",
            [IdempotencyKey._meta.db_table],
        )
        deployed = {name for (name,) in cursor.fetchall()}
    assert EXPECTED_CONSTRAINTS <= deployed


def test_the_table_is_named_explicitly() -> None:
    """`db_table` is explicit, so renaming the app label can never rename the table."""
    assert IdempotencyKey._meta.db_table == "core_idempotency_key"


def test_the_unique_index_is_the_only_index_on_scope_and_key() -> None:
    """`UniqueConstraint(scope, key)` already indexes the claim path; a second would be dead
    weight on a hot, frequently written table."""
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT indexdef FROM pg_indexes WHERE tablename = %s",
            [IdempotencyKey._meta.db_table],
        )
        definitions = [definition for (definition,) in cursor.fetchall()]
    on_scope_key = [d for d in definitions if "scope" in d and "key" in d]
    assert len(on_scope_key) == 1
    assert "UNIQUE" in on_scope_key[0]


# ---------------------------------------------------------------------------
# ...and each one refuses a direct violating insert
# ---------------------------------------------------------------------------


def test_a_duplicate_scope_and_key_is_refused() -> None:
    _row().save(force_insert=True)
    _refuses(_row(), "core_idem_scope_key_uniq")


def test_the_same_key_under_another_scope_is_accepted() -> None:
    _row().save(force_insert=True)
    _row(scope="fixture.other").save(force_insert=True)
    assert IdempotencyKey.objects.count() == 2


def test_an_empty_key_is_refused() -> None:
    _refuses(_row(key=""), "core_idem_identity_not_empty")


def test_an_empty_scope_is_refused() -> None:
    _refuses(_row(scope=""), "core_idem_identity_not_empty")


def test_a_row_with_no_principal_is_refused() -> None:
    """§4: `NULL` never means "anybody" — that state is not storable."""
    _refuses(
        _row(principal_kind="ACTOR", principal_id=None, principal_purpose=None),
        "core_idem_principal_shape_valid",
    )


def test_an_actor_row_carrying_a_purpose_is_refused() -> None:
    _refuses(_row(principal_purpose="reconciliation"), "core_idem_principal_shape_valid")


def test_a_system_row_carrying_a_locator_is_refused() -> None:
    _refuses(
        _row(
            principal_kind="SYSTEM",
            principal_id=PublicId.new().value,
            principal_purpose="reconciliation",
        ),
        "core_idem_principal_shape_valid",
    )


def test_a_system_row_with_a_purpose_alone_is_accepted() -> None:
    _row(principal_kind="SYSTEM", principal_id=None, principal_purpose="reconciliation").save(
        force_insert=True
    )
    assert IdempotencyKey.objects.count() == 1


def test_a_short_fingerprint_is_refused() -> None:
    _refuses(
        _row(request_fingerprint="a" * (FINGERPRINT_HEX_LENGTH - 1)),
        "core_idem_fingerprint_is_sha256",
    )


def test_an_uppercase_fingerprint_is_refused() -> None:
    """One digest has one stored spelling, or two rows could disagree about equality."""
    _refuses(_row(request_fingerprint="A" * FINGERPRINT_HEX_LENGTH), "core_idem_fingerprint")


def test_a_non_hex_fingerprint_is_refused() -> None:
    _refuses(_row(request_fingerprint="z" * FINGERPRINT_HEX_LENGTH), "core_idem_fingerprint")


def test_an_expiry_at_or_before_creation_is_refused() -> None:
    now = timezone.now()
    _refuses(_row(created_at=now, expires_at=now), "core_idem_expiry_after_created")
    _refuses(
        _row(created_at=now, expires_at=now - timedelta(seconds=1)),
        "core_idem_expiry_after_created",
    )


def test_a_result_locator_without_a_result_kind_is_refused() -> None:
    """A half-written completion: a replay could not name what it is replaying."""
    _refuses(
        _row(result_kind=None, result_public_id=PublicId.new().value),
        "core_idem_result_shape_valid",
    )


def test_a_result_detail_without_a_result_kind_is_refused() -> None:
    _refuses(_row(result_kind=None, result_detail={"a": 1}), "core_idem_result_shape_valid")


def test_an_uncompleted_claim_row_is_representable() -> None:
    """It has to be: the claim inserts before the effect runs, within one transaction."""
    _row(result_kind=None, result_public_id=None, result_detail=None).save(force_insert=True)
    assert IdempotencyKey.objects.count() == 1


# ---------------------------------------------------------------------------
# Column widths are real widths
# ---------------------------------------------------------------------------


def test_an_oversized_key_is_refused_by_the_column() -> None:
    with pytest.raises(DataError), transaction.atomic():
        _row(key="x" * (MAX_KEY_LENGTH + 1)).save(force_insert=True)


def test_an_oversized_scope_is_refused_by_the_column() -> None:
    with pytest.raises(DataError), transaction.atomic():
        _row(scope="x" * (MAX_SCOPE_LENGTH + 1)).save(force_insert=True)


def test_a_key_at_the_bound_is_accepted() -> None:
    _row(key="x" * MAX_KEY_LENGTH).save(force_insert=True)
    assert IdempotencyKey.objects.count() == 1


# ---------------------------------------------------------------------------
# The result detail cap, which `jsonb` cannot impose on its own
# ---------------------------------------------------------------------------


def test_jsonb_itself_imposes_no_application_byte_limit() -> None:
    """The reason the cap lives in Python: the column would happily take a megabyte.

    This is the negative half of the guarantee. The positive half — that
    `Claimed.complete()` refuses the same payload — is asserted in the mechanism's own tests.
    """
    oversized = {"blob": "x" * (MAX_RESULT_DETAIL_BYTES * 4)}
    _row(result_detail=oversized).save(force_insert=True)
    assert IdempotencyKey.objects.get().result_detail == oversized
