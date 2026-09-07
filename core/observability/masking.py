"""Strict data masking for logs and error reports (master `# 23.1`, `# 21`).

The logging and error-tracking surface is built on **zero trust in the data it is handed**.
Master `# 23.1` names four categories that must never reach a log line — user passwords and
their hashes, full card data, integration secrets and cryptographic keys, decrypted vouchers
and digital licence codes — and requires a forced filter that masks them rather than a review
convention that asks people to remember.

This module is that filter, and the same function later serves an error tracker's
`before_send`: one vocabulary, one replacement token, one place to extend.

### The rule is by field name, deliberately

A value is masked because of **what it is called**, not because of what it looks like. Value
inspection — "does this look like a card number, does this look like a JWT" — was rejected: it
is simultaneously too eager (an order total that happens to be sixteen digits) and too lax (a
secret that happens to look ordinary), and a heuristic that is wrong in both directions gives
false confidence. A name is what a developer chooses deliberately, so a name-based rule is
predictable and greppable.

The consequence is explicit rather than hidden: **a sensitive value stored under a harmless
name is not caught here.** That half of the protection is a static rule
(`tools/arch_check` `M23.1-MASK`), which refuses to let a sensitive-named binding be passed
into a log call in the first place, and a review rule for genuinely novel material.

### Over-masking is the safe direction, and is chosen on purpose

`key` matches `api_key`, `secret_key`, `private_key`, `signing_key` — and also
`idempotency_key`, which ADR-0015 §4 and item 5 AU6 independently require to stay out of the
security log. `card` matches a payment card and also a `ProductCard`. Losing a card of the
second kind from a log line costs a diagnostic detail; keeping one of the first kind costs a
breach. The vocabulary is chosen with that asymmetry in mind and is not tuned for elegance.

### What this module is not

It is not encryption, not tokenization, not anonymization and not a privacy policy. It
discharges no consent, retention or erasure obligation, and holds no domain vocabulary: it
knows a set of words and how to walk a container.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

__all__ = ("MASKED", "SENSITIVE_WORDS", "is_sensitive", "masked")

#: The literal that replaces a masked value. A fixed, greppable marker, so an operator reading
#: a log line can tell "this field was withheld" from "this field was empty".
MASKED = "[MASKED]"

#: What replaces a structure nested deeper than `_MAX_DEPTH`.
TRUNCATED = "[TRUNCATED]"

#: Field-name segments that make a value sensitive. Matched **segment-wise** against the name,
#: so `password_hash`, `passwordHash` and `user.password` all match `password`, while `author`
#: does not match `auth` and `pinned` does not match `pin`.
#:
#: Four groups, in master `# 23.1`'s order, plus the personal data `# 21` keeps out of logs:
#: credentials, card data, secrets and keys, redeemable codes, and direct identifiers.
SENSITIVE_WORDS: frozenset[str] = frozenset(
    {
        # Credentials and session material.
        "auth",
        "authorization",
        "bearer",
        "cookie",
        "credential",
        "credentials",
        "csrf",
        "otp",
        "passphrase",
        "passwd",
        "password",
        "pwd",
        "session",
        # Card and bank data.
        "card",
        "cardholder",
        "cvc",
        "cvv",
        "iban",
        "pan",
        # Secrets, keys and signatures.
        "hmac",
        "key",
        "secret",
        "signature",
        "token",
        # Redeemable codes and digital goods.
        "licence",
        "license",
        "pin",
        "serial",
        "voucher",
        # Raw material a payload-redaction rule covers (PV8, item 8 SEC8).
        "body",
        "payload",
        # Direct personal identifiers.
        "address",
        "email",
        "idnp",
        "msisdn",
        "passport",
        "phone",
    }
)

#: A container nested deeper than this is replaced wholesale. A log line is a diagnostic, not
#: a data export, and an unbounded walk over a cyclic or enormous structure is a way to hang
#: the process that produced it.
_MAX_DEPTH = 6

_WORD = re.compile(r"[A-Za-z0-9]+")
_CAMEL_BOUNDARY = re.compile(r"(?<=[a-z0-9])(?=[A-Z])")


def _segments(name: str) -> list[str]:
    """Split a field name into lowercase word segments, across both naming conventions."""
    return [
        part.lower()
        for chunk in _WORD.findall(name)
        for part in _CAMEL_BOUNDARY.split(chunk)
        if part
    ]


def is_sensitive(name: object) -> bool:
    """True when a field of this name must never carry its value into a log or a trace."""
    if type(name) is not str:
        return False
    return any(segment in SENSITIVE_WORDS for segment in _segments(name))


def masked(value: Any) -> Any:
    """Return `value` with every sensitively-named field replaced by `MASKED`.

    Mappings are walked by key; lists, tuples and sets are walked by element and returned as
    lists; every other value is returned unchanged. Strings and bytes are values, never
    containers, so they are never walked into.

    The function is total and raises nothing. It runs on the logging path, where an exception
    would either lose the record or replace a diagnostic with a formatter error — and it is
    reached most often precisely when something has already gone wrong.
    """
    return _walk(value, 0)


def _walk(value: Any, depth: int) -> Any:
    if depth > _MAX_DEPTH:
        return TRUNCATED
    if isinstance(value, Mapping):
        return {
            str(key): MASKED if is_sensitive(str(key)) else _walk(item, depth + 1)
            for key, item in value.items()
        }
    if isinstance(value, list | tuple | set | frozenset):
        return [_walk(item, depth + 1) for item in value]
    return value
