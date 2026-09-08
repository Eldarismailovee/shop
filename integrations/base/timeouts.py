"""The connect / read / total budget every outbound call carries (master `# 20.8` §1).

> *"Explicit timeout: никакого HTTP без connect/read/total budget. Baseline: connect ~3 s,
> read ~10 s; override только осознанно."*

The rule is not "there is a default timeout somewhere" — it is that **no call can be made
without one**. That is why `TimeoutBudget` has no default: it is a required constructor
argument of the transport, so the unbounded call is not a mistake anyone can make, it is a
program that does not type-check and does not run. `M20.8-TIMEOUT` keeps the generic HTTP
client inside `integrations/base`, so there is no second way to reach a socket either.

Three bounds rather than one, because they fail differently and an operator reads them
differently. A **connect** timeout means the provider is down or the network is broken and
nothing was sent; a **read** timeout means the request is out there and the answer never
came, which is the ambiguous case §27 exists for. Collapsing them into one number throws
away exactly the distinction the caller needs to decide whether a retry is safe.

`total` is per **attempt**, not per operation. The bound across attempts is the retry
policy's `max_age` (item 9 RB2/RB3), and the two are kept separate because they answer
different questions: `total` bounds how long one exchange may take, `max_age` bounds how
long the client keeps trying. Master `# 20.8` states both, as items 1 and 3 of one list.
"""

from __future__ import annotations

from dataclasses import dataclass

__all__ = ("TimeoutBudget",)


@dataclass(frozen=True, slots=True, kw_only=True)
class TimeoutBudget:
    """Seconds. Every field is required, and every field must be finite and positive."""

    #: Establishing the connection, including TLS and any wait for a pooled slot.
    connect: float
    #: Waiting for the next chunk of the response.
    read: float
    #: The whole exchange, connect included. The client enforces it as a deadline.
    total: float

    def __post_init__(self) -> None:
        for name in ("connect", "read", "total"):
            value = getattr(self, name)
            # `bool` is an `int` by a language accident; a budget of `True` seconds is a
            # programming error, not a one-second timeout (the same check `Money` makes).
            if type(value) not in (int, float) or isinstance(value, bool):
                raise TypeError(f"{name} must be a real number of seconds, got {value!r}")
            if not value > 0:
                raise ValueError(f"{name} must be positive, got {value}")
            if value != value or value == float("inf"):
                raise ValueError(f"{name} must be finite, got {value}")
        # A total below one of its parts is always a misconfiguration: it would make the
        # part it contradicts unreachable, and the number the operator wrote a lie.
        if self.total < self.connect:
            raise ValueError(f"total ({self.total}) is below connect ({self.connect})")
        if self.total < self.read:
            raise ValueError(f"total ({self.total}) is below read ({self.read})")
