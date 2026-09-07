"""`request_id` — its shape, and where a value comes from (item 10 §8, RQ1-RQ10).

`request_id` identifies the **originating synchronous request of a causal chain**: the HTTP
request or inbound webhook invocation that started it. It is inherited unchanged by every
durable message emitted while that chain is processed, and it is legitimately **absent** for
a chain of system origin — a schedule, a reconciliation pass, a rebuild (RQ3, PR6).

### Why the shape rule lives here rather than in `core.events`

The value is *minted* at the transport boundary and *bound* into ambient observability
context, and `interfaces/*` may import `core.observability` but not `core.events` at all
(item 3 §4.4). The rule that decides whether a candidate is a `request_id` therefore has to
be readable from here, and stating it twice would let the boundary that adopts a value and
the envelope that stores it drift apart on a security-relevant validation. `core.events`
imports these definitions; there is one owner and one regex.

### What a value is, and is not

`request_id` is a **bounded-length opaque token** (RQ6). The platform parses no structure out
of it, derives nothing from it, and sorts nothing by it. It is observability metadata only:
not actor identity, not a principal, not a session identifier, not an authentication token,
not an authorization input, not a tenant selector (RQ4), and not a business correlation key —
a workflow that needs one owns its own identifier with its own lifecycle (RQ5).

A minted value is **opaque and random** (RQ7, PV2). Deriving it from a user, a session or a
cart would turn every log line and every durable row into a personal-data record.
"""

from __future__ import annotations

import re
import secrets

__all__ = ("REQUEST_ID_MAX_LENGTH", "new_request_id", "normalised_request_id")

#: RQ6: a bounded-length opaque token. The bound is a Phase-1 choice, wide enough for any
#: reverse-proxy convention in use (a UUID, a 32-character hex token, an nginx request id)
#: and narrow enough that a header cannot become a storage channel.
REQUEST_ID_MAX_LENGTH = 128

#: Printable ASCII with no spaces: what an HTTP header can carry unambiguously and what a
#: log aggregator can index without escaping. The platform reads no meaning into it.
_REQUEST_ID = re.compile(r"\A[\x21-\x7e]+\Z")

#: PR6: `request_id` is present or absent, with no third state. These are the stand-ins that
#: would smuggle one in — a chain of system origin is spelled by absence, never by `"-"`.
_PLACEHOLDERS = frozenset({"-", "none", "null", "unknown"})

#: 16 random bytes rendered as 32 hex characters. Enough entropy that two concurrent requests
#: never collide, and no structure for anyone to parse back out.
_MINTED_BYTES = 16


def normalised_request_id(value: object) -> str | None:
    """A valid `request_id`, or `None` — never an exception and never a repair (PR4, PR5).

    This is the boundary decision for a *candidate* value: an inbound header, a carrier entry,
    a stored column read back. A malformed, over-long, non-string, placeholder or absent value
    becomes **absent**, which is a complete and legal state; it is never padded, re-cased,
    truncated to fit or invented.

    A client-supplied value reaching this function is untrusted input (RQ8, PV5). Passing the
    shape check makes a value *storable*, never *trusted*: it still influences no
    authorization, no rate limiting and no business decision anywhere.
    """
    if type(value) is not str or len(value) > REQUEST_ID_MAX_LENGTH:
        return None
    if not _REQUEST_ID.fullmatch(value) or value.lower() in _PLACEHOLDERS:
        return None
    return value


def new_request_id() -> str:
    """Mint an opaque random `request_id` for a chain that arrived without one.

    Used by the transport boundary when no trusted edge value is available. `secrets` rather
    than `random`: not because the value is a credential — it is not, and it authorises
    nothing — but because a predictable identifier invites exactly the "it is unguessable, so
    it must be safe to key on" reasoning that RQ4 forbids.
    """
    return secrets.token_hex(_MINTED_BYTES)
