"""Claiming a command key, and resolving against one already committed (ADR-0015 §6-§8).

Usage, and the only sanctioned shape::

    with transaction.atomic():                      # the caller's transaction
        outcome = claim_or_resolve(
            scope="<registered scope>",
            key=key,
            principal=actor,
            fingerprint=fingerprint(canonicalize(material)),
        )
        match outcome:
            case Claimed() as claimed:
                with claimed:
                    ...the protected durable effect...
                    claimed.complete(kind="created", public_id=thing.public_id)
            case Replay(result=result):
                ...rebuild the response from result...
            case Conflicted():
                ...refuse...
            case NotOwned():
                ...refuse, disclosing nothing...

**The claim is inserted inside the caller's transaction**, so the claim, the effect and the
replayable completion commit together and a rollback leaves no durable claim (§6). There is
no separately committed `processing` row, no `atomic(durable=True)`, no autocommit write and
no `on_commit` claim (A131) — a two-transaction pattern is forbidden by name.

**PostgreSQL is the truth; there is no Redis here** (§2, A129). No lock, TTL key or
in-process mutex stands in for the claim, and contenders serialize on the durable uniqueness
constraint rather than on an application mutex or an advisory lock (§7).

### Expiry, and why an expired row is never simply ignored

`UNIQUE (scope, key)` holds for as long as the row exists, but §10 ends the replay promise at
`expires_at` and a key must then re-execute. Those are reconciled by an explicit procedure,
**not** by treating an expired row as absent: an expired row is never read *as* a valid claim
and never bypassed. The existing row is taken under `SELECT ... FOR UPDATE`, deleted, and
re-inserted; a contender re-resolves against the winner's new row under §4.

To be precise about which mechanism guarantees what: the *correctness* guarantee — one
reclaim, one effect — comes from the same unique constraint as every other path, because a
losing re-insert conflicts and is resolved rather than executed. The explicit row lock takes
the lock at the point of decision instead of relying on the implicit lock the subsequent
`DELETE` would take anyway, which keeps the single-threading of the reclaim a property one
can read in this module rather than one inferred from PostgreSQL's row-locking rules.

Re-execution after expiry is safe precisely because this table is **not** where permanent
business uniqueness lives (§11, IK11). A permanently single-use operation is refused by its
own domain `UNIQUE` and state machine. Because the claim path reclaims expired rows itself,
the retention purge is housekeeping for disk space only, never a correctness dependency.
"""

from __future__ import annotations

import uuid
from types import TracebackType
from typing import Any, Literal

from django.db import IntegrityError, transaction
from django.utils import timezone

from core.actor import Actor, SystemActor
from core.idempotency import canonical
from core.idempotency.bounds import (
    MAX_KEY_LENGTH,
    MAX_RESULT_DETAIL_BYTES,
    MAX_RESULT_KIND_LENGTH,
)
from core.idempotency.errors import (
    ClaimContention,
    ClaimOutsideTransaction,
    IncompleteClaim,
    InvalidClaimInput,
)
from core.idempotency.fingerprint import is_fingerprint
from core.idempotency.models import IdempotencyKey
from core.idempotency.outcomes import Conflicted, NotOwned, Replay, SemanticResult
from core.idempotency.principal import PrincipalKind, PrincipalRef
from core.idempotency.scopes import COMMAND_SCOPES
from core.observability.security_events import (
    SecurityEvent,
    SecurityEventCode,
    record_security_event,
)
from core.public_id import PublicId

__all__ = ("Claimed", "Outcome", "claim_or_resolve")

#: The claim path selects bounded columns only. `result_detail` is excluded, so the one heavy
#: column is read exclusively when a replay actually needs it (A136, master `# 20.5`).
_CLAIM_PATH_FIELDS = (
    "scope",
    "key",
    "principal_kind",
    "principal_id",
    "principal_purpose",
    "request_fingerprint",
    "created_at",
    "expires_at",
    "result_kind",
    "result_public_id",
)

#: §7 allows exactly one re-attempt after a resolved conflict; beyond that is a technical
#: fault, never a fabricated business outcome.
_MAX_ATTEMPTS = 2


class Claimed:
    """A claim taken in this transaction, awaiting its completion.

    Unlike its sibling outcomes this is a handle rather than a frozen value, because it
    carries the one obligation the mechanism cannot express as data: §6 requires the
    replayable completion to become durable *at the same instant* as the effect, so a
    committed row with no recorded result would promise a replay it cannot deliver.

    `__exit__` therefore refuses to let the block end successfully without a completion. The
    raised `IncompleteClaim` aborts the caller's transaction, which is exactly what §6 wants
    — no durable claim at all — rather than a half-written row nobody notices for a month.
    If an exception is already propagating, it is left alone: that path rolls back too.
    """

    __slots__ = ("_completed", "_entered", "_row_id")

    def __init__(self, *, row_id: int) -> None:
        self._row_id = row_id
        self._entered = False
        self._completed = False

    def __enter__(self) -> Claimed:
        self._entered = True
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> Literal[False]:
        if exc_type is None and not self._completed:
            raise IncompleteClaim(
                "the claim block ended without complete(); a committed claim must carry the "
                "result it promises to replay (ADR-0015 §6)"
            )
        return False

    def complete(
        self,
        *,
        kind: str,
        public_id: PublicId | None = None,
        detail: Any = None,
    ) -> None:
        """Record the bounded semantic result, in the same transaction as the effect.

        `detail` is JSON-shaped material the scope's own contract defines, capped at
        `MAX_RESULT_DETAIL_BYTES`. PostgreSQL `jsonb` imposes no application byte limit, so
        the cap is applied here, before the write — and an oversized result is **refused**,
        never truncated: this table is an integrity mechanism, not a response cache (§9).
        """
        if not self._entered:
            raise IncompleteClaim(
                "complete() is called inside `with claimed:`; the block is what guarantees a "
                "claim cannot be committed without its result"
            )
        if self._completed:
            raise IncompleteClaim("this claim has already been completed")

        detail_value = _validated_detail(detail)
        IdempotencyKey.objects.filter(pk=self._row_id).update(
            result_kind=_validated_result_kind(kind),
            result_public_id=_validated_public_id(public_id),
            result_detail=detail_value,
        )
        self._completed = True


Outcome = Claimed | Replay | Conflicted | NotOwned


def claim_or_resolve(
    *,
    scope: str,
    key: str,
    principal: Actor | SystemActor,
    fingerprint: str,
) -> Outcome:
    """Claim `(scope, key)` for this principal, or resolve against a committed row.

    The `Actor | SystemActor` union is written out rather than hidden behind an alias, so a
    privileged claim stays visible and greppable at the call site (item 4 Z3/Z4). There is no
    third form: `principal` has no default and `None` is not a value it accepts.
    """
    command_scope = COMMAND_SCOPES.resolve(scope)
    _validate_key(key)
    if not is_fingerprint(fingerprint):
        raise InvalidClaimInput(
            "fingerprint must be a SHA-256 digest in lowercase hex; build it with "
            "core.idempotency.fingerprint.fingerprint()"
        )
    reference = PrincipalRef.of(principal)

    if not transaction.get_connection().in_atomic_block:
        raise ClaimOutsideTransaction(
            "claim_or_resolve() runs inside the transaction that performs the protected "
            "effect; in autocommit the claim would commit on its own, which is the "
            "separately committed `processing` row ADR-0015 §6 forbids"
        )

    now = timezone.now()
    last_conflict: IntegrityError | None = None

    for _ in range(_MAX_ATTEMPTS):
        row_id, last_conflict = _try_insert(
            scope=command_scope.name,
            key=key,
            reference=reference,
            fingerprint=fingerprint,
            created_at=now,
            expires_at=now + command_scope.retention,
        )
        if row_id is not None:
            return Claimed(row_id=row_id)

        existing = _lock_existing(scope=command_scope.name, key=key)
        if existing is None:
            # The winning contender rolled back, so no row exists durably and the key is
            # claimable normally under this request's own fingerprint (§7).
            continue
        if existing.expires_at <= now:
            # The replay promise has lapsed (§10). The row lock taken above is what makes
            # this delete-and-reclaim single-threaded.
            existing.delete()
            continue
        return _resolve(existing, reference=reference, fingerprint=fingerprint)

    raise ClaimContention(
        f"the claim on scope {command_scope.name!r} did not settle within {_MAX_ATTEMPTS} attempts"
    ) from last_conflict


def _try_insert(
    *,
    scope: str,
    key: str,
    reference: PrincipalRef,
    fingerprint: str,
    created_at: Any,
    expires_at: Any,
) -> tuple[int | None, IntegrityError | None]:
    """Insert the claim inside a savepoint, so a uniqueness race is recoverable.

    Nesting is a savepoint implementation detail of one semantic command (item 4 §12), not an
    independent transaction: nothing here commits, and the outer transaction still owns every
    durable write.
    """
    row = IdempotencyKey(
        scope=scope,
        key=key,
        principal_kind=reference.kind.value,
        principal_id=reference.actor_id,
        principal_purpose=reference.purpose,
        request_fingerprint=fingerprint,
        created_at=created_at,
        expires_at=expires_at,
    )
    try:
        with transaction.atomic():
            row.save(force_insert=True)
    except IntegrityError as conflict:
        return None, conflict
    return row.pk, None


def _lock_existing(*, scope: str, key: str) -> IdempotencyKey | None:
    """Take the committed row under a row lock, reading bounded columns only (A136).

    The lock serializes contenders on the **existing** row at the point where the expiry
    decision is made. It is not the correctness guarantee — that stays the unique constraint,
    as everywhere else in §7 — but it puts the reclaim's single-threading in this function
    rather than leaving it to the lock the following `DELETE` would take implicitly.
    """
    return (
        IdempotencyKey.objects.select_for_update()
        .only(*_CLAIM_PATH_FIELDS)
        .filter(scope=scope, key=key)
        .first()
    )


def _resolve(
    existing: IdempotencyKey,
    *,
    reference: PrincipalRef,
    fingerprint: str,
) -> Replay | Conflicted | NotOwned:
    """Apply §4's three-way decision to a committed row.

    Ownership is checked **before** the fingerprint, deliberately: a principal that does not
    own the key must learn nothing at all, including whether its own input would have matched.

    The refusal is recorded as a security event **here**, at the point of detection, rather
    than left to each caller: this is the only place that knows *why* the outcome is
    `NotOwned` — the caller receives an opaque refusal precisely so that it cannot tell — and a
    per-scope obligation to remember to log would be discharged inconsistently the first time
    a scope was added in a hurry (ADR-0015 §4, item 5 AU3/AU6).
    """
    stored = PrincipalRef(
        kind=PrincipalKind(existing.principal_kind),
        actor_id=existing.principal_id,
        purpose=existing.principal_purpose,
    )
    if stored != reference:
        _record_ownership_refusal(scope=existing.scope, attempted_by=reference)
        return NotOwned()
    if existing.request_fingerprint != fingerprint:
        return Conflicted()
    return Replay(result=_stored_result(existing))


def _record_ownership_refusal(*, scope: str, attempted_by: PrincipalRef) -> None:
    """Record the attempt, carrying nothing the refusal itself must not disclose.

    The `scope` is a platform-owned bounded token and safe to name. The **key** and the request
    fingerprint are deliberately absent: AU6 requires the line without the key, and a key is
    not an object-access token whose value would help an operator anyway. The principal
    recorded is the one that *attempted*; the owner of the contested row is a second party
    whose identity has no place in a line about somebody else's behaviour.

    A log call, not a database write — so the signal survives the rollback that a refused
    command's transaction is about to perform.
    """
    record_security_event(
        SecurityEvent(
            code=SecurityEventCode.IDEMPOTENCY_KEY_OWNERSHIP_REFUSED,
            subject=scope,
            principal_kind=attempted_by.kind.value.lower(),
            principal_id=None if attempted_by.actor_id is None else str(attempted_by.actor_id),
            principal_purpose=attempted_by.purpose,
        )
    )


def _stored_result(existing: IdempotencyKey) -> SemanticResult:
    if existing.result_kind is None:
        raise IncompleteClaim(
            "a committed claim carries no result; this row was written by something that "
            "bypassed Claimed.complete()"
        )
    locator = existing.result_public_id
    # Reading `result_detail` is what loads the deferred column, and it happens here only —
    # on an actual replay, never while claiming (A136).
    detail = existing.result_detail
    return SemanticResult(
        kind=existing.result_kind,
        public_id=None if locator is None else PublicId(value=locator),
        detail_json=None if detail is None else canonical.encode(detail),
    )


def _validate_key(key: str) -> None:
    """Bound the key, and change nothing about it.

    Stored verbatim: no strip, no case folding, no Unicode normalization. The key is opaque
    with no parseable meaning (§3), so normalising it would merge two distinct claims.
    """
    if type(key) is not str:
        raise InvalidClaimInput(f"key must be a string, got {type(key).__name__}")
    if not key:
        raise InvalidClaimInput("key must not be empty")
    if len(key) > MAX_KEY_LENGTH:
        raise InvalidClaimInput(f"key is at most {MAX_KEY_LENGTH} characters, got {len(key)}")


def _validated_result_kind(kind: str) -> str:
    if type(kind) is not str:
        raise InvalidClaimInput(f"result kind must be a string, got {type(kind).__name__}")
    if not kind:
        raise InvalidClaimInput("result kind must not be empty")
    if len(kind) > MAX_RESULT_KIND_LENGTH:
        raise InvalidClaimInput(
            f"result kind is at most {MAX_RESULT_KIND_LENGTH} characters, got {len(kind)}"
        )
    return kind


def _validated_public_id(public_id: PublicId | None) -> uuid.UUID | None:
    if public_id is None:
        return None
    if type(public_id) is not PublicId:
        raise InvalidClaimInput(
            f"a replayed resource is addressed by a PublicId, got "
            f"{type(public_id).__name__}; an internal identifier never leaves the database"
        )
    return public_id.value


def _validated_detail(detail: Any) -> Any:
    if detail is None:
        return None
    text = canonical.encode(detail)
    size = len(text.encode("utf-8"))
    if size > MAX_RESULT_DETAIL_BYTES:
        raise InvalidClaimInput(
            f"the stored result is {size} bytes, over the {MAX_RESULT_DETAIL_BYTES} byte "
            f"bound; ADR-0015 §9 stores a bounded semantic result, never a response body"
        )
    return detail
