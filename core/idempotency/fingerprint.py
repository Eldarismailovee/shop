"""The semantic request fingerprint (ADR-0015 §5, A134).

Every scope defines a **semantic request fingerprint**: a SHA-256 digest over the
*canonical semantic command input*, not over the raw transport payload. The properties
ADR-0015 §5 requires, and where each is discharged:

* **Deterministic and canonical** — field order, JSON whitespace, key ordering and encoding
  variation must not change the digest. `core.idempotency.canonical` owns the one spelling,
  and this module refuses to hash anything not already in it, so two renderings of one input
  cannot produce two digests.
* **Discriminating** — any semantically material change yields a different digest. That is
  SHA-256's job, given canonical input.
* **Storable without the request** — the digest is 64 hex characters; the raw body is never
  retained in order to compare fingerprints later.
* **Free of transport noise** — headers, cookies, trace ids, timing and client version are
  outside the material unless a scope makes one semantically material.
* **Free of secrets** — no credential, token, cookie, CSRF value or authentication material
  is fed in merely to compute it (A134). That is a property of the material a *scope*
  chooses, enforced at the call site by `tools/arch_check` and review; this module cannot
  inspect a value and know it is a token, and pretending otherwise would be theatre.

**The field list is per scope, not global** (ADR-0015 §5). Each command owner defines its own
material as part of that command's contract. This module owns the digest and nothing else,
and therefore knows no business vocabulary.
"""

from __future__ import annotations

import hashlib
from typing import Any

from core.idempotency import canonical
from core.idempotency.bounds import (
    FINGERPRINT_HEX_LENGTH,
    MAX_FINGERPRINT_MATERIAL_BYTES,
)
from core.idempotency.errors import InvalidClaimInput

__all__ = ("canonicalize", "fingerprint", "is_fingerprint")

_HEX_DIGITS = frozenset("0123456789abcdef")


def canonicalize(material: Any) -> str:
    """Render scope-chosen material as canonical JSON text.

    Offered so that a command owner never hand-builds canonical JSON and never discovers, a
    year later, that two call sites disagreed about key order.
    """
    text = canonical.encode(material)
    _check_size(text)
    return text


def fingerprint(canonical_json: str) -> str:
    """Digest canonical material into 64 lowercase hex characters."""
    if type(canonical_json) is not str:
        raise InvalidClaimInput(
            f"fingerprint material must be canonical JSON text, got {type(canonical_json).__name__}"
        )
    _check_size(canonical_json)
    canonical.decode(canonical_json)  # refuses non-canonical form, floats and NaN
    return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()


def is_fingerprint(value: object) -> bool:
    """Whether a value is a well-formed digest, in the exact form the column constrains."""
    return (
        type(value) is str
        and len(value) == FINGERPRINT_HEX_LENGTH
        and _HEX_DIGITS.issuperset(value)
    )


def _check_size(text: str) -> None:
    size = len(text.encode("utf-8"))
    if size > MAX_FINGERPRINT_MATERIAL_BYTES:
        raise InvalidClaimInput(
            f"fingerprint material is {size} bytes, over the {MAX_FINGERPRINT_MATERIAL_BYTES} "
            f"byte bound; a fingerprint is over semantic command input, not a raw body"
        )
