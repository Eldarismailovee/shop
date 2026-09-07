"""The platform-owned command-scope set — **shipping empty** (ADR-0015 §3, §10, A133).

`scope` names one semantic command. It comes from a bounded, stable, platform-defined set
and is **never** taken from client input, a header, a path segment or a tenant string. That
is the whole reason this registry exists rather than a plain string parameter: a scope that
cannot be looked up cannot be claimed.

This registry ships with **no entries**, exactly as `core.events`' message registry does
(`docs/architecture/phase-1/02-core-primitives.md` §7.2). A scope is registered by the phase
that owns the command it names, together with that command's fingerprint material and its
retention period.

**Master `# 20.4`'s scope list is illustrative and is not registered here.**
`checkout.place_order`, `payment.initialize`, `refund.create`, `coupon.redeem`,
`tradein.redeem` and `digital.fulfillment.allocate` are names, not proofs of shape
(ADR-0015 §6): a scope name does not establish that the workflow it labels is one local ACID
command. For `payment.initialize` in particular, the payments phase must identify which
precise *local durable* effect, if any, is protected here; the provider call it eventually
triggers stays separately idempotent under the provider's own contract.

There is no sample scope. Tests that need a registered one build it locally.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import timedelta

from core.idempotency.bounds import MAX_SCOPE_LENGTH, RETENTION_FLOOR_HOURS
from core.idempotency.errors import UnregisteredScope

__all__ = ("COMMAND_SCOPES", "CommandScope", "ScopeRegistry")

#: Lowercase, dot-separated, owner-qualified. No version suffix, no queue or transport word,
#: no vendor name: a scope names a command, and its spelling carries no other meaning.
_SCOPE_NAME = re.compile(r"\A[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*)+\Z")

#: A scope names a command, and its spelling carries nothing else. A version suffix in
#: particular is refused outright: a scope is not versioned, and `place_order.v2` would be a
#: second scope silently protecting the same command — two keys for one business effect.
_VERSION_SUFFIX = re.compile(r"\Av\d+\Z")

_RETENTION_FLOOR = timedelta(hours=RETENTION_FLOOR_HOURS)


@dataclass(frozen=True, slots=True, kw_only=True)
class CommandScope:
    """One registered command scope and the retention it promises.

    ADR-0015 §10: every scope has an explicit, bounded retention that covers **at least**
    the retry/replay window its use case advertises, and expiry ends the replay promise. The
    two must agree, so retention is declared here rather than configured globally — a single
    platform-wide TTL cannot be right for both an HTTP form post and a financial command.
    """

    name: str
    retention: timedelta

    def __post_init__(self) -> None:
        if type(self.name) is not str:
            raise TypeError(f"a scope name must be a string, got {type(self.name).__name__}")
        if len(self.name) > MAX_SCOPE_LENGTH:
            raise ValueError(
                f"a scope name is at most {MAX_SCOPE_LENGTH} characters, got {len(self.name)}"
            )
        if not _SCOPE_NAME.fullmatch(self.name):
            raise ValueError(
                f"{self.name!r} is not an owner-qualified command scope "
                f"(lowercase, dot-separated, at least two segments)"
            )
        if _VERSION_SUFFIX.fullmatch(self.name.rsplit(".", 1)[-1]):
            raise ValueError(
                f"{self.name!r} carries a version suffix; a scope is not versioned, and a "
                f"second spelling would protect one command with two keys"
            )
        if type(self.retention) is not timedelta:
            raise TypeError(f"retention must be a timedelta, got {type(self.retention).__name__}")
        if self.retention < _RETENTION_FLOOR:
            raise ValueError(
                f"retention is at least {RETENTION_FLOOR_HOURS}h for a command scope "
                f"(ADR-0015 §10), got {self.retention}"
            )


class ScopeRegistry:
    """An immutable index of registered command scopes, keyed by name."""

    __slots__ = ("_by_name",)

    def __init__(self, scopes: Iterable[CommandScope] = ()) -> None:
        by_name: dict[str, CommandScope] = {}
        for scope in scopes:
            if type(scope) is not CommandScope:
                raise TypeError(
                    f"a registry entry must be a CommandScope, got {type(scope).__name__}"
                )
            if scope.name in by_name:
                raise ValueError(f"a scope name is unique; {scope.name!r} appears twice")
            by_name[scope.name] = scope
        self._by_name = by_name

    def __len__(self) -> int:
        return len(self._by_name)

    @property
    def names(self) -> frozenset[str]:
        return frozenset(self._by_name)

    def resolve(self, name: str) -> CommandScope:
        """Resolve a registered scope, or refuse the claim outright.

        There is no fallback, no default scope and no "register on first use": an
        unregistered value means the caller invented a scope, which is the exact failure
        A133 exists to prevent.
        """
        scope = self._by_name.get(name)
        if scope is None:
            raise UnregisteredScope(
                f"{name!r} is not a registered command scope; a scope comes from the "
                f"platform-owned set, never from request data"
            )
        return scope


#: ADR-0015 §3: the set ships empty. Each command's own phase registers its scope.
COMMAND_SCOPES = ScopeRegistry()
