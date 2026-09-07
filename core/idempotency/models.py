"""The durable `IdempotencyKey` row (ADR-0015, item 15 §15 clause 4).

The PostgreSQL row is the **only** thing that decides whether a command executes twice,
whether a retry replays, whether a request is a conflict, and who owns a key (ADR-0015 §2).
There is no Redis path here, and none may be added: a Redis miss, flush, eviction, outage or
cold start must change none of those four answers.

Two structural properties are worth stating out loud, because each is a rule made physical:

**There is no state column at all** (A132). ADR-0015 §6 refines master `# 5.2`'s
`processing / completed / failed` sketch: `processing` may exist only as uncommitted,
transaction-local state — the row a transaction has inserted but not yet committed, which is
precisely what serializes contenders — and the generic mechanism requires no durable
`failed` state, so that a transient fault can never reserve a key forever. The cleanest way
to guarantee a column has one legal committed value is for the column not to exist. The
existence of a committed row *is* the completed state.

**No polymorphic cross-domain foreign key.** ADR-0015 §9 marks master's
`resource_type`/`resource_public_id` pair as illustrative. A created resource is remembered
by its semantic `PublicId` only; the table never grows a generic FK across domains, and
never exposes an internal bigint because it happens to hold one.

`core` knows no domain: nothing here carries Order, Payment, Product or Inventory
vocabulary, and the scope set that would name such a command ships empty
(`core/idempotency/scopes.py`).
"""

from __future__ import annotations

from django.db import models

from core.idempotency.bounds import (
    FINGERPRINT_HEX_LENGTH,
    MAX_KEY_LENGTH,
    MAX_PRINCIPAL_PURPOSE_LENGTH,
    MAX_RESULT_KIND_LENGTH,
    MAX_SCOPE_LENGTH,
)
from core.idempotency.principal import PrincipalKind

__all__ = ("IdempotencyKey",)

#: The exact stored form of a SHA-256 digest: lowercase hex, fixed width. `max_length` alone
#: would allow a short or upper-case value, so the alphabet and the length are constrained
#: in SQL rather than trusted from Python.
_FINGERPRINT_PATTERN = rf"^[0-9a-f]{{{FINGERPRINT_HEX_LENGTH}}}$"


class IdempotencyKey(models.Model):
    """One committed claim: this command, this key, this principal, this input.

    The row is inserted inside the same transaction as the protected durable effect and its
    completion becomes durable at the same instant (ADR-0015 §6). A rollback therefore leaves
    **no** durable claim — the key is simply unused again — which is why no failure path
    needs to clean anything up.
    """

    #: One semantic command, from the platform-owned set. Never request data (A133).
    scope = models.CharField(max_length=MAX_SCOPE_LENGTH)

    #: Opaque. No authorization, no timestamp, no ordering, no parseable meaning, and
    #: **stored verbatim**: nothing trims, folds case or normalises it, because two keys that
    #: differ only in whitespace are two keys (ADR-0015 §3).
    key = models.CharField(max_length=MAX_KEY_LENGTH)

    #: Which authorization subject claimed the row; see `core/idempotency/principal.py`.
    principal_kind = models.CharField(
        max_length=16,
        choices=[(member.value, member.value) for member in PrincipalKind],
    )
    principal_id = models.UUIDField(null=True)
    principal_purpose = models.CharField(max_length=MAX_PRINCIPAL_PURPOSE_LENGTH, null=True)

    #: SHA-256 over canonical semantic command input, as lowercase hex (ADR-0015 §5).
    request_fingerprint = models.CharField(max_length=FINGERPRINT_HEX_LENGTH)

    created_at = models.DateTimeField()

    #: The end of the replay promise (ADR-0015 §10). Reaching it does not free the key on its
    #: own — `core/idempotency/claim.py` reclaims an expired row under a row lock, so that two
    #: callers can never both conclude "this looks expired, so I may insert".
    expires_at = models.DateTimeField()

    #: The bounded semantic result (ADR-0015 §9). Null between the claim insert and the
    #: completion update *within one transaction*; never null on a committed row, which
    #: `Claimed` enforces by refusing to let its block end uncompleted.
    result_kind = models.CharField(max_length=MAX_RESULT_KIND_LENGTH, null=True)
    result_public_id = models.UUIDField(null=True)

    #: The one heavy column, and the reason A136 has a subject: it is never selected on the
    #: claim path, only when a replay actually needs it. `jsonb` imposes no application byte
    #: limit, so the 4 KiB cap is applied in Python before the write.
    result_detail = models.JSONField(null=True)

    class Meta:
        # Explicit, so that renaming the app label can never rename the table.
        db_table = "core_idempotency_key"
        constraints = [
            # ADR-0015 §3 / A130 / master `# 5.4`. This also creates the only index the
            # claim path needs, so no second (scope, key) index is declared.
            models.UniqueConstraint(
                fields=("scope", "key"),
                name="core_idem_scope_key_uniq",
            ),
            models.CheckConstraint(
                condition=~models.Q(scope="") & ~models.Q(key=""),
                name="core_idem_identity_not_empty",
            ),
            # ADR-0015 §4: exactly one principal shape, so `NULL` can never mean "anybody".
            models.CheckConstraint(
                condition=(
                    models.Q(
                        principal_kind=PrincipalKind.ACTOR.value,
                        principal_id__isnull=False,
                        principal_purpose__isnull=True,
                    )
                    | models.Q(
                        principal_kind=PrincipalKind.SYSTEM.value,
                        principal_id__isnull=True,
                        principal_purpose__isnull=False,
                    )
                ),
                name="core_idem_principal_shape_valid",
            ),
            models.CheckConstraint(
                condition=models.Q(request_fingerprint__regex=_FINGERPRINT_PATTERN),
                name="core_idem_fingerprint_is_sha256",
            ),
            models.CheckConstraint(
                condition=models.Q(expires_at__gt=models.F("created_at")),
                name="core_idem_expiry_after_created",
            ),
            # Result material is coherent or absent: a locator or a detail snapshot without
            # a result kind is a half-written completion, and a replay could not name it.
            models.CheckConstraint(
                condition=(
                    models.Q(result_kind__isnull=False)
                    | (
                        models.Q(result_public_id__isnull=True)
                        & models.Q(result_detail__isnull=True)
                    )
                ),
                name="core_idem_result_shape_valid",
            ),
        ]

    def __str__(self) -> str:
        # The key is opaque and the principal is not this row's business to advertise.
        return f"{self.scope}/<key>"
