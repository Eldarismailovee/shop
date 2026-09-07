"""The shared UUIDv7 mechanism — internal to `core`, exported to nobody.

Item 11 TX2 / ADR-0013 §2: `PublicId` and `EventId` share **one** generation, parsing
and version-validation implementation, so there is a single algorithm and a single
standards-conforming library decision and the two types cannot drift apart in validation
behaviour. TX3/TX4 then close the obvious hole: the mechanism is **not** a `core` surface
for any package family. A generic exported `new_uuid7()` / `parse_uuid7()` pair would let
every call site mint a value that fits *both* semantic types, and the distinction would
evaporate at exactly the boundaries where it matters. Every module outside `core` imports
the semantic type it needs; `tools/arch_check` reports A82 otherwise, and the leading
underscore says the same thing to a reader.

GN2 forbids a hand-rolled bit layout, timestamp source or entropy scheme. The pinned
runtime supplies the standards-conforming implementation directly: Python 3.14's
`uuid.uuid7()` generates an RFC 9562 version-7 UUID, verified against the installed
interpreter rather than assumed.

Nothing here reads the embedded timestamp. TS1-TS6: those bits are an encoding and an
index-locality property, never business time, ordering or a version.
"""

from __future__ import annotations

import re
import uuid

#: PA2/PA3. The canonical rendered form is the lowercase hyphenated 8-4-4-4-12
#: representation, and only that spelling is accepted at an input boundary. Uppercase
#: hex, brace-wrapped, `urn:uuid:`-prefixed and unhyphenated 32-character spellings are
#: **rejected, not normalised**: accepting several spellings would give one resource
#: several external identities, and therefore several canonical URLs, several cache keys
#: and several crawl targets.
_CANONICAL_FORM = re.compile(r"\A[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\Z")

#: PA1. A structurally valid UUID of another version is not a platform identity.
_VERSION = 7


def generate() -> uuid.UUID:
    """Mint a fresh standards-conforming UUIDv7 (GN1, GN2)."""
    return uuid.uuid7()


def validated(value: uuid.UUID) -> uuid.UUID:
    """Return `value` if it is genuinely a version-7 UUID; reject anything else (PA1).

    A UUIDv4, a non-RFC-4122 variant and a non-`UUID` object are all refused. A foreign
    *v7* — a provider's, an ERP's, a legacy system's — passes this structural test by
    construction and is refused by the boundary that owns the mapping instead (EI5, V99):
    shape is not provenance, and this mechanism only claims to check shape.
    """
    if type(value) is not uuid.UUID:
        raise TypeError(f"expected a uuid.UUID, got {type(value).__name__}")
    if value.version != _VERSION:
        raise ValueError(f"expected a UUID version {_VERSION}, got version {value.version}")
    return value


def parse_canonical(text: str) -> uuid.UUID:
    """Parse the canonical lowercase hyphenated form of a UUIDv7 (PA1-PA4)."""
    if type(text) is not str:
        raise TypeError(f"expected the canonical text form, got {type(text).__name__}")
    if not _CANONICAL_FORM.fullmatch(text):
        raise ValueError(
            f"{text!r} is not the canonical lowercase hyphenated 8-4-4-4-12 form; "
            "non-canonical spellings are rejected rather than normalised"
        )
    return validated(uuid.UUID(text))


def render(value: uuid.UUID) -> str:
    """The one outward textual form (PA2): lowercase, hyphenated, round-tripping (PA6)."""
    return str(value)
