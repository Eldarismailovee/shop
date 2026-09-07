"""The security-event log (ADR-0015 §4, item 5 AU6, master `# 21`, `# 23.1`).

Some refusals are not ordinary business outcomes. When a principal presents an idempotency key
that belongs to somebody else, the caller must learn nothing — not the outcome, not even that
the key exists (ADR-0015 §4) — and the platform must learn everything it safely can, because a
sequence of such attempts is what an attempt to use a key as an object-access token looks like.
The refusal is returned to the caller as an opaque outcome; the *attempt* is recorded here.

### A closed vocabulary, not a message

`SecurityEventCode` is the whole message. A free-text description would be the obvious channel
through which a key, a token or a personal datum eventually reaches this log — and a log an
alert rule matches on needs a stable string anyway. Adding a member is a deliberate, greppable
act; interpolating a detail into the message is not possible.

The structured fields are likewise a fixed set rather than a mapping. A `dict[str, Any]` detail
bag is how "just this one extra field" becomes an unbounded, unreviewed leak surface, and it is
rejected here for the same reason item 10 §10.2 rejects it in the message envelope.

### What a record may and may not carry

May: the code, the platform-owned bounded subject the attempt was against (a command scope
name), and the identification of the **attempting** principal — master `# 23.1` requires the
acting identity on a security-relevant line, and `core.public_id` locators are not secrets.

May not, per AU6 and ADR-0015 §4: the idempotency key itself, the request fingerprint, any
payload, any credential, any personal datum. The owning principal of the contested row is not
recorded either — it is not needed to alert on the attempt, and recording it would put a
second party's identity into a line about somebody else's behaviour.

### Not transactional, on purpose

Emission is a log call, not a database write, so it is unaffected by whether the caller's
transaction later commits. That is the required behaviour: a refused attempt happened whether
or not the surrounding transaction survives, and a security signal that disappears on rollback
is a security signal an attacker can suppress. It performs no network I/O and no database work
on the caller's path (A65); where the line is routed is deployment configuration.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from enum import Enum

__all__ = (
    "SECURITY_LOGGER_NAME",
    "SecurityEvent",
    "SecurityEventCode",
    "record_security_event",
)

#: The dedicated logger. Named so that a deployment can route security lines to their own
#: sink and alert policy without filtering the whole application stream by content.
SECURITY_LOGGER_NAME = "security"

_LOGGER = logging.getLogger(SECURITY_LOGGER_NAME)

#: A platform-owned bounded token: a command scope, a mechanism name. Never free text, never a
#: user-supplied string, never an opaque key.
_SUBJECT = re.compile(r"\A[a-z][a-z0-9_.]*\Z")
_SUBJECT_MAX_LENGTH = 64

#: A principal reference as it is rendered for a log line — a locator or a purpose token.
#: Bounded and charset-checked so that no unexpected material reaches the line through it.
_PRINCIPAL_REF = re.compile(r"\A[A-Za-z0-9._:-]{1,64}\Z")


class SecurityEventCode(Enum):
    """The closed set of security events the platform records.

    One member per genuinely security-relevant refusal. A member is added by the slice that
    creates the refusal it names, together with the alert rule that consumes it.
    """

    #: ADR-0015 §4 / item 5 AU6: a principal presented a committed idempotency key that is
    #: owned by a different principal, and was refused without disclosure.
    IDEMPOTENCY_KEY_OWNERSHIP_REFUSED = "idempotency_key_ownership_refused"


@dataclass(frozen=True, slots=True, kw_only=True)
class SecurityEvent:
    """One recordable security-relevant attempt.

    `principal_kind` / `principal_id` / `principal_purpose` mirror the two structurally
    different authorization subjects rather than flattening them into one string: an actor is
    identified by a locator and a system context by a purpose, and a single text field would
    make `"system:reconciliation"` and an actor whose locator rendered that way
    indistinguishable. Every field is optional because not every event has every part.
    """

    code: SecurityEventCode
    subject: str | None = None
    principal_kind: str | None = None
    principal_id: str | None = None
    principal_purpose: str | None = None

    def __post_init__(self) -> None:
        if type(self.code) is not SecurityEventCode:
            raise TypeError(
                f"code must be a SecurityEventCode, got {type(self.code).__name__}; the "
                f"vocabulary is closed so that a description cannot become a leak channel"
            )
        _require_token(self.subject, "subject", _SUBJECT, _SUBJECT_MAX_LENGTH)
        _require_token(self.principal_kind, "principal_kind", _SUBJECT, _SUBJECT_MAX_LENGTH)
        _require_token(self.principal_id, "principal_id", _PRINCIPAL_REF, 64)
        _require_token(self.principal_purpose, "principal_purpose", _SUBJECT, _SUBJECT_MAX_LENGTH)


def record_security_event(event: SecurityEvent) -> None:
    """Record one security event at `WARNING`.

    `WARNING` rather than `ERROR`: a refused attempt is the mechanism working correctly, not a
    fault of the platform. The alert that matters is a *rate* of these, which is an operations
    threshold rather than a per-line severity.
    """
    if type(event) is not SecurityEvent:
        raise TypeError(
            f"record_security_event() takes a SecurityEvent, got {type(event).__name__}"
        )

    context = {
        "security_event": event.code.value,
        "security_subject": event.subject,
        "principal_kind": event.principal_kind,
        "principal_id": event.principal_id,
        "principal_purpose": event.principal_purpose,
    }
    _LOGGER.warning(
        event.code.value,
        extra={key: value for key, value in context.items() if value is not None},
    )


def _require_token(value: str | None, field: str, pattern: re.Pattern[str], limit: int) -> None:
    if value is None:
        return
    if type(value) is not str:
        raise TypeError(f"{field} must be a string or absent, got {type(value).__name__}")
    if len(value) > limit or not pattern.fullmatch(value):
        raise ValueError(
            f"{value!r} is not a bounded {field} token; a security line carries platform-owned "
            f"identifiers only, never a key, a fingerprint or free text"
        )
