"""The actor primitive — the public contract's authorization subject (ADR-0006 §1).

ADR-0004 §6 froze that object-level authorization follows state ownership, and item 4 §11
made the consequence structural: every operation on **private** domain state takes an
explicit, mandatory, non-optional authorization subject, and privileged access uses an
explicit system context rather than `actor=None`. Four families must name one type —
`interfaces` constructs it after authentication, `tasks` restores it from a message,
`application` passes it through, `domains` consume it — so the type is domain-independent
and cannot live in any of them. `integrations/*` may not depend on it at all: an adapter
answers no authorization question and receives vendor-neutral port edge types. That
asymmetry is L20, and `tools/arch_check` reports it.

**There is no third form.** A public read of public state takes no actor at all; a read of
private state takes a mandatory one. `actor=None` never means "system", "admin", "trusted
caller" or "skip the check" (Z2), and neither type here has a default or an optional field,
so no value of either is constructible as "unauthenticated but privileged".

**No union alias is provided, deliberately.** A callable that genuinely accepts either
subject writes `Actor | SystemActor` in its own signature, which keeps every privileged
admission visible at the call site and greppable in review (Z3, Z4). A convenient alias
would become the thing everyone annotates with, and Z4 would quietly stop meaning anything.

This is a public-contract primitive and nothing more. It is not a user model, an
authentication backend, a permissions framework, a session, a request or a vendor concept
(D2-D5). Whether the subject eventually carries roles, capabilities, a session or a tenant
is the authentication phase's decision (ADR-0006 §3, item 4 §11.3); the rule that the
subject is explicit, mandatory and typed does not depend on any of it, and a domain never
builds one from raw request data.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from core.public_id import PublicId

__all__ = ("Actor", "SystemActor")

#: A bounded, greppable mechanism token — never a free-text message, so a purpose cannot
#: become the channel through which a secret or a personal datum reaches a log (SE6, X3).
_PURPOSE = re.compile(r"\A[a-z][a-z0-9_]*\Z")


@dataclass(frozen=True, slots=True, kw_only=True)
class Actor:
    """An authenticated principal, addressed by its platform locator.

    The principal is identified by a `PublicId`, not by a bare `UUID` and not by an
    internal `bigint` (PI3, TY1, TY2): the type states which identity space the value
    belongs to, so an event identity or a provider identifier cannot occupy the position.
    Which entity that locator addresses is the authentication phase's to state — `core`
    holds no entity vocabulary (OW5).

    A domain does not read this to decide *what* the principal may do; it passes the
    subject to its own policy and actor-scoped selector, and never accepts a pre-computed
    decision such as `is_owner: bool` from a caller (Z5, Z7).
    """

    principal_id: PublicId

    def __post_init__(self) -> None:
        if type(self.principal_id) is not PublicId:
            raise TypeError(
                f"principal_id must be a PublicId, got {type(self.principal_id).__name__}; "
                f"an authorization subject is never identified by a bare UUID or an "
                f"internal identifier"
            )


@dataclass(frozen=True, slots=True, kw_only=True)
class SystemActor:
    """An explicit privileged/system context (Z3, Z4).

    Background work, scheduled jobs, reconciliation passes and bootstrap-time operations
    are authorized as *something*, and this is the type that says so out loud. It is a
    sibling of `Actor`, not a subtype: no value satisfies both, so a system-only operation
    can be typed such that only a system context passes, and an ordinary actor can never
    drift into a privileged position through a widened annotation.

    `purpose` names the privileged use so that every construction site is self-describing
    and auditable. It is a structural mechanism token chosen by the caller — `core` requires
    only that one is present and well-formed, and attaches no meaning to any value.
    """

    purpose: str

    def __post_init__(self) -> None:
        if type(self.purpose) is not str:
            raise TypeError(f"purpose must be a mechanism token, got {type(self.purpose).__name__}")
        if not _PURPOSE.fullmatch(self.purpose):
            raise ValueError(
                f"{self.purpose!r} is not a purpose token (lowercase, starting with a "
                f"letter, digits and underscores); a privileged context names why it is one"
            )
