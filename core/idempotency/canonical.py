"""One canonical JSON spelling, shared by the fingerprint and the stored result.

Two places in this mechanism need "the same value always renders the same way": the request
fingerprint, whose whole worth is that one semantic input has exactly one digest (ADR-0015
§5), and the bounded semantic result, which round-trips through `jsonb` and must come back
in a stable form (§9). They use one codec, so the two can never drift apart.

The canonical form is: keys sorted, compact separators, no insignificant whitespace, no
`NaN`/`Infinity`, and **no floats anywhere**. Money is integer minor units with an explicit
currency (`core/money.py`); a float here is either money spelled wrongly or a value whose
rendering is platform-dependent, and both make the form unstable.

Size limits are deliberately *not* imposed here — the fingerprint and the result have
different, separately justified caps (`core/idempotency/bounds.py`), and each applies its
own.
"""

from __future__ import annotations

import json
from typing import Any

from core.idempotency.errors import InvalidClaimInput

__all__ = ("decode", "encode")

_SEPARATORS = (",", ":")


def encode(value: Any) -> str:
    """Render a JSON-shaped value in the one canonical spelling.

    Accepted shapes are JSON's: `None`, `bool`, `int`, `str`, `list`/`tuple`, and `dict` with
    string keys. A `set`, a `datetime`, a `Decimal`, a `Money` or a model instance is refused
    rather than coerced — a lossy rendering would produce a digest that no longer
    discriminates.
    """
    _reject_floats(value, path="$")
    try:
        return json.dumps(
            value,
            sort_keys=True,
            separators=_SEPARATORS,
            ensure_ascii=False,
            allow_nan=False,
        )
    except (TypeError, ValueError) as exc:
        raise InvalidClaimInput(
            f"value must be JSON-shaped (null, bool, int, str, list, dict with string keys); {exc}"
        ) from exc


def decode(text: str) -> Any:
    """Parse text that is **already** in canonical form, refusing anything else.

    Non-canonical input is refused rather than normalised. Silently canonicalizing here would
    hide a call site that builds its material inconsistently, and the disagreement needs to
    surface where it is caused rather than be papered over at the last moment.
    """
    if type(text) is not str:
        raise InvalidClaimInput(f"canonical JSON must be text, got {type(text).__name__}")
    try:
        value = json.loads(text, parse_float=_reject_float, parse_constant=_reject_constant)
    except InvalidClaimInput:
        raise
    except ValueError as exc:
        raise InvalidClaimInput(f"not valid JSON: {exc}") from exc
    if encode(value) != text:
        raise InvalidClaimInput(
            "text is not in canonical form (sorted keys, compact separators, no "
            "insignificant whitespace); build it with core.idempotency.canonical.encode"
        )
    return value


def _reject_float(raw: str) -> float:
    raise InvalidClaimInput(
        f"the fractional number {raw!r} is not admissible; money is integer minor units "
        f"with an explicit currency, and no other quantity may be a float here"
    )


def _reject_constant(raw: str) -> float:
    raise InvalidClaimInput(f"{raw!r} is not canonical JSON")


def _reject_floats(value: Any, *, path: str) -> None:
    if isinstance(value, float):
        raise InvalidClaimInput(
            f"a float appears at {path}; money is integer minor units with an explicit "
            f"currency, and no other quantity may be a float here"
        )
    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str):
                raise InvalidClaimInput(
                    f"JSON object keys are strings; {path} has a {type(key).__name__} key"
                )
            _reject_floats(item, path=f"{path}.{key}")
    elif isinstance(value, list | tuple):
        for index, item in enumerate(value):
            _reject_floats(item, path=f"{path}[{index}]")
