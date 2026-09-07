"""Deterministic payload serialization and the content fingerprint (item 8 §29, SZ4, IX3).

Two properties of the asynchronous machinery rest entirely on this module:

* **Item 8 IX5's integrity check.** The same `event_id` arriving with materially different
  content is a data-integrity violation rather than a duplicate. Deciding that requires a
  fingerprint, and a fingerprint is only meaningful if one logical payload always produces
  one byte string (PD5, IX3, SZ4).
* **Item 9 C77's replay guarantee.** Replay preserves the payload **byte-for-byte**. That is
  why the durable column holds the canonical *text* this module produced, and why a replay
  never re-serializes a reconstructed object: a value that round-trips through today's DTOs
  and today's encoder is a *new* rendering that merely resembles the original.

The canonical form is: keys sorted, compact separators, no insignificant whitespace, no
`NaN`/`Infinity`, and **no floats anywhere**. Money is integer minor units with an explicit
currency (`core/money.py`, item 8 PD8); a float here is either money spelled wrongly or a
value whose rendering is platform-dependent, and both make the form unstable.

### Why this is not `core.idempotency.canonical`

The two look alike and are deliberately not shared. ADR-0015 §1 separates five
duplicate-protection mechanisms and forbids collapsing them or naming one after another;
`core.idempotency` may not import `core.events` (A137), and the reverse edge would be the
same mistake drawn the other way — the message mechanism would then depend on the command
mechanism's error type, bounds and evolution. They also protect different things: the
idempotency codec renders *semantic command input* chosen per scope, this one renders a
*published payload contract* whose bytes must survive verbatim into a terminal record. A
shared helper would make one mechanism's change a silent change to the other.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from core.events.bounds import FINGERPRINT_HEX_LENGTH, MAX_PAYLOAD_BYTES
from core.events.errors import InvalidPayload

__all__ = ("RESERVED_PAYLOAD_FIELDS", "decode", "encode", "fingerprint", "is_fingerprint")

_SEPARATORS = (",", ":")

_HEX_DIGITS = frozenset("0123456789abcdef")

#: Item 10 EV3 / A61 / item 8 EN11: no payload field is named after an envelope or trace slot.
#: The envelope is not payload, and a payload field wearing one of these names is how a
#: handler ends up branching on trace metadata (FW4) or how a second, unversioned envelope
#: grows beside the frozen one. Checked at the top level, where a contract declares its
#: fields; a nested value named `trace_id` inside a genuine business sub-object is a review
#: matter, not something a codec can adjudicate.
RESERVED_PAYLOAD_FIELDS = frozenset(
    {
        "event_id",
        "event_type",
        "schema_version",
        "occurred_at",
        "trace_id",
        "span_id",
        "producer_span_id",
        "parent_span_id",
        "request_id",
        "correlation_id",
        "causation_id",
        "causation_event_id",
        "traceparent",
        "tracestate",
        "baggage",
    }
)


def encode(payload: Any) -> str:
    """Render a payload in the one canonical spelling, or refuse it.

    Accepted shapes are JSON's: `None`, `bool`, `int`, `str`, `list`/`tuple`, and `dict` with
    string keys. A `set`, a `datetime`, a `Decimal`, a `Money` or a model instance is refused
    rather than coerced — a lossy rendering would produce bytes that no longer reproduce the
    fact, and item 8 PD8 forbids an ORM object, a row dump or a `dict[str, Any]` reaching a
    payload in the first place.
    """
    _reject_floats(payload, path="$")
    _reject_reserved_fields(payload)
    try:
        text = json.dumps(
            payload,
            sort_keys=True,
            separators=_SEPARATORS,
            ensure_ascii=False,
            allow_nan=False,
        )
    except (TypeError, ValueError) as exc:
        raise InvalidPayload(
            f"a payload must be JSON-shaped (null, bool, int, str, list, dict with string "
            f"keys); {exc}"
        ) from exc
    _check_size(text)
    return text


def decode(text: str) -> Any:
    """Parse text that is **already** canonical, refusing anything else.

    Non-canonical input is refused rather than normalised. Silently canonicalizing here would
    hide a producer that builds its payload inconsistently, and would break IX5: two spellings
    of one fact would fingerprint differently and read as an integrity violation, while a
    normalising decoder would make the stored bytes and the compared bytes different things.
    """
    if type(text) is not str:
        raise InvalidPayload(f"canonical payload text expected, got {type(text).__name__}")
    _check_size(text)
    try:
        value = json.loads(text, parse_float=_reject_float, parse_constant=_reject_constant)
    except InvalidPayload:
        raise
    except ValueError as exc:
        raise InvalidPayload(f"not valid JSON: {exc}") from exc
    if encode(value) != text:
        raise InvalidPayload(
            "text is not in canonical form (sorted keys, compact separators, no "
            "insignificant whitespace); build it with core.events.codec.encode"
        )
    return value


def fingerprint(canonical_payload: str) -> str:
    """Digest canonical payload text into 64 lowercase hex characters.

    The digest is taken over the **exact bytes** that are stored, so a fingerprint comparison
    and a byte comparison can never disagree. It is an identity-integrity mechanism (IX5) and
    nothing else: it is not an ordering key, not a version, and not a substitute for the
    stored payload — item 9 C77 replays the bytes, never a value rebuilt from the digest.
    """
    if type(canonical_payload) is not str:
        raise InvalidPayload(
            f"fingerprint material must be canonical payload text, got "
            f"{type(canonical_payload).__name__}"
        )
    _check_size(canonical_payload)
    decode(canonical_payload)  # refuses non-canonical form, floats and NaN
    return hashlib.sha256(canonical_payload.encode("utf-8")).hexdigest()


def is_fingerprint(value: object) -> bool:
    """Whether a value is a well-formed digest, in the exact form the column constrains."""
    return (
        type(value) is str
        and len(value) == FINGERPRINT_HEX_LENGTH
        and _HEX_DIGITS.issuperset(value)
    )


def _check_size(text: str) -> None:
    size = len(text.encode("utf-8"))
    if size > MAX_PAYLOAD_BYTES:
        raise InvalidPayload(
            f"the payload is {size} bytes, over the {MAX_PAYLOAD_BYTES} byte bound; a message "
            f"carries a bounded fact, and a large body belongs behind a reference"
        )


def _reject_reserved_fields(payload: Any) -> None:
    if not isinstance(payload, dict):
        return
    offending = sorted(name for name in payload if name in RESERVED_PAYLOAD_FIELDS)
    if offending:
        raise InvalidPayload(
            f"payload field {offending[0]!r} is an envelope or trace slot name; the envelope "
            f"is not payload, and no payload field carries those values under any name"
        )


def _reject_float(raw: str) -> float:
    raise InvalidPayload(
        f"the fractional number {raw!r} is not admissible in a payload; money is integer "
        f"minor units with an explicit currency, and no other quantity may be a float"
    )


def _reject_constant(raw: str) -> float:
    raise InvalidPayload(f"{raw!r} is not canonical JSON")


def _reject_floats(value: Any, *, path: str) -> None:
    if isinstance(value, float):
        raise InvalidPayload(
            f"a float appears at {path}; money is integer minor units with an explicit "
            f"currency, and no other quantity may be a float in a payload"
        )
    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str):
                raise InvalidPayload(
                    f"JSON object keys are strings; {path} has a {type(key).__name__} key"
                )
            _reject_floats(item, path=f"{path}.{key}")
    elif isinstance(value, list | tuple):
        for index, item in enumerate(value):
            _reject_floats(item, path=f"{path}[{index}]")
