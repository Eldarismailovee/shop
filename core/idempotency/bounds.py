"""The physical bounds of a claim row (ADR-0015 §3, §5, §9).

ADR-0015 requires `scope`, `key`, the fingerprint and the stored result to be **bounded**
and fixes no numbers. The numbers are chosen here, in one place, so that "bounded" is a
physical guarantee of the schema rather than an intention in prose. Every one of them is
also a database constraint (`core/idempotency/models.py`), because a Python-side bound is
not a bound against `bulk_create`, raw SQL or a concurrent writer.

Widening one of these is a migration and a recorded decision, not an edit.
"""

from __future__ import annotations

__all__ = (
    "FINGERPRINT_HEX_LENGTH",
    "MAX_FINGERPRINT_MATERIAL_BYTES",
    "MAX_KEY_LENGTH",
    "MAX_PRINCIPAL_PURPOSE_LENGTH",
    "MAX_RESULT_DETAIL_BYTES",
    "MAX_RESULT_KIND_LENGTH",
    "MAX_SCOPE_LENGTH",
    "RETENTION_FLOOR_HOURS",
)

#: An owner-qualified command name such as `<owner>.<command>`. Generous for a dotted
#: platform-owned name; it is not user input, so it never needs to be long.
MAX_SCOPE_LENGTH = 128

#: The opaque caller- or platform-supplied key. 255 accommodates every common client
#: idempotency-key convention (a UUID, a ULID, a digest) without inviting a payload.
MAX_KEY_LENGTH = 255

#: `SystemActor.purpose` is a lowercase mechanism token, not a sentence (`core/actor.py`).
MAX_PRINCIPAL_PURPOSE_LENGTH = 128

#: SHA-256 rendered as lowercase hex. Fixed width, and the alphabet is checkable in SQL.
FINGERPRINT_HEX_LENGTH = 64

#: A ceiling on the canonical JSON handed to `fingerprint()`. The digest is over *semantic*
#: command input (ADR-0015 §5); a megabyte of it is a raw body by another name.
MAX_FINGERPRINT_MATERIAL_BYTES = 65_536

#: A bounded result token such as `created` or `already_settled`, chosen by the scope owner.
MAX_RESULT_KIND_LENGTH = 64

#: ADR-0015 §9: a *bounded, semantic* result, never a raw response body. PostgreSQL `jsonb`
#: imposes no application byte limit, so the cap is enforced in Python before the write.
MAX_RESULT_DETAIL_BYTES = 4_096

#: ADR-0015 §10: the HTTP command baseline is master `# 5.2`'s floor of at least 24 hours.
#: Financial and high-risk scopes declare longer, owner-defined retention.
RETENTION_FLOOR_HOURS = 24
