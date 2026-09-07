"""The durable encoding of a claiming principal (ADR-0015 §4).

ADR-0015 §4 freezes the *semantic* requirement, not a column: a committed row identifies its
claiming principal well enough to make this decision deterministically::

    same (scope, key) + same principal + same fingerprint   -> replay
    same (scope, key) + same principal + other fingerprint  -> Conflict
    same (scope, key) + different principal                 -> ownership refusal

and **`NULL` never means "anybody"** — an absent or unresolvable principal on a committed row
is a defect, not a wildcard.

The encoding is two columns plus a kind discriminator rather than one opaque string, because
the platform has two structurally different authorization subjects and neither can be
expressed as the other (`core/actor.py`): an `Actor` is addressed by a `PublicId`, while a
`SystemActor` has no locator at all — only a `purpose` token. Flattening them into one text
column would make `"system:reconciliation"` and an actor whose locator happened to render
that way indistinguishable, and would put the burden of never colliding on a string format.

The database refuses any other shape: `core_idem_principal_shape_valid` requires exactly one
of the two forms, so "no principal recorded" is not a storable state.

This module holds no permission model. Whether the subject eventually carries roles,
capabilities, a session or a tenant is the authentication phase's decision (ADR-0006 §3);
the three-way decision above depends on none of it.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from enum import Enum

from core.actor import Actor, SystemActor

__all__ = ("PrincipalKind", "PrincipalRef")


class PrincipalKind(Enum):
    """Which of the two authorization subjects claimed the key."""

    ACTOR = "ACTOR"
    SYSTEM = "SYSTEM"


@dataclass(frozen=True, slots=True, kw_only=True)
class PrincipalRef:
    """A claim row's principal, in the form the three-way decision compares.

    Ordinary frozen-dataclass equality *is* the "same principal" test, so no hand-written
    comparison can drift from the stored shape.
    """

    kind: PrincipalKind
    actor_id: uuid.UUID | None
    purpose: str | None

    def __post_init__(self) -> None:
        if self.kind is PrincipalKind.ACTOR:
            if self.actor_id is None or self.purpose is not None:
                raise ValueError("an actor principal is identified by a locator alone")
        elif self.actor_id is not None or self.purpose is None:
            raise ValueError("a system principal is identified by a purpose alone")

    @classmethod
    def of(cls, principal: Actor | SystemActor) -> PrincipalRef:
        """Encode either authorization subject.

        The union is written out rather than hidden behind an alias, exactly as item 4 Z3/Z4
        require of every callable that accepts both: a privileged claim stays visible and
        greppable at the call site.
        """
        if type(principal) is Actor:
            return cls(
                kind=PrincipalKind.ACTOR,
                actor_id=principal.principal_id.value,
                purpose=None,
            )
        if type(principal) is SystemActor:
            return cls(kind=PrincipalKind.SYSTEM, actor_id=None, purpose=principal.purpose)
        raise TypeError(
            f"a claim is made by an Actor or a SystemActor, got "
            f"{type(principal).__name__}; there is no third form and None is not one"
        )
