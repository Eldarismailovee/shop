"""The wire boundary: what a request and a response are, and the one real implementation.

`Transport` is the seam that makes the retry and breaker policy testable without a network
and without a clock that really sleeps. `HttpxTransport` is the only production
implementation, and — by `M20.8-TIMEOUT` — the only module in the platform that may import
a generic HTTP client at all. Everything above it speaks in `VendorRequest` /
`VendorResponse` and in the three signals below.

### Why three signals and not the library's exceptions

The policy above needs exactly one thing from a failed exchange, and it is not which
library raised what: *was the request delivered, and can we tell what happened to it?*

```text
NotSent      nothing left this process, or nothing arrived   → safe to repeat, always
Interrupted  it went out; the answer did not come back       → §27 ambiguity
Malformed    the exchange itself is broken                   → a human, not a retry
```

Translating `httpx`'s hierarchy once, here, keeps that question answerable in one place and
keeps the library out of the policy. It also keeps item 9 TD3 honest — *"a software defect
is never dressed as a provider failure"* — so an unusable URL or an unsupported scheme,
which is our bug and not the vendor's, surfaces as `Malformed` and never as "the provider
was unreachable", where it would be retried, alerted on and blamed on the wrong system.

`RemoteProtocolError` is mapped to `Interrupted` rather than `Malformed` deliberately: the
server broke the protocol *after* our request was on the wire, so the outcome is unknown,
and the ambiguity is the property that must survive the translation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

import httpx

from integrations.base.timeouts import TimeoutBudget

__all__ = (
    "HttpxTransport",
    "Interrupted",
    "Malformed",
    "NotSent",
    "Transport",
    "TransportError",
    "VendorRequest",
    "VendorResponse",
)


class TransportError(Exception):
    """Root of the three wire signals. Carries a class name, never a payload."""

    def __init__(self, detail: str) -> None:
        self.detail = detail
        super().__init__(detail)


class NotSent(TransportError):
    """The request provably did not reach the provider."""


class Interrupted(TransportError):
    """The request was sent and no complete response came back."""


class Malformed(TransportError):
    """The exchange is unusable — an unreadable response, or a request we built wrong."""


@dataclass(frozen=True, slots=True, kw_only=True)
class VendorRequest:
    """One outbound exchange, fully built by the vendor adapter that owns the protocol.

    Headers are a tuple of pairs rather than a mapping: the value must be immutable like
    every other contract type here, and duplicates are legal in HTTP and would be silently
    lost by a dict.
    """

    method: str
    url: str
    headers: tuple[tuple[str, str], ...] = ()
    body: bytes | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class VendorResponse:
    """What came back. Interpreting it is the vendor package's job, not this layer's."""

    status_code: int
    headers: tuple[tuple[str, str], ...] = ()
    body: bytes = b""

    def header(self, name: str) -> str | None:
        """The first value of `name`, case-insensitively; `None` when absent."""
        wanted = name.lower()
        for key, value in self.headers:
            if key.lower() == wanted:
                return value
        return None


class Transport(Protocol):
    """Send one request, once. No retrying, no breaker, no policy of any kind."""

    def send(self, request: VendorRequest, *, budget_seconds: float) -> VendorResponse:
        """Perform the exchange within `budget_seconds`, or raise a `TransportError`."""


@dataclass(slots=True)
class HttpxTransport:
    """The production transport. A budget is required to construct one.

    That requirement is master `# 20.8` §1 made structural: there is no argument to omit,
    no `None` to pass and no default to inherit, so an unbounded outbound call is not a
    mistake this codebase can express.

    Redirects are **not** followed. On an API call a redirect is a protocol surprise rather
    than a feature, and following one can replay an `Authorization` header at whatever host
    the response names — a credential leak decided by the other end.
    """

    budget: TimeoutBudget
    _client: httpx.Client = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self._client = httpx.Client(
            timeout=httpx.Timeout(
                connect=self.budget.connect,
                read=self.budget.read,
                write=self.budget.read,
                pool=self.budget.connect,
            ),
            follow_redirects=False,
        )

    def send(self, request: VendorRequest, *, budget_seconds: float) -> VendorResponse:
        # The caller's remaining budget caps every component: `total` is a deadline for the
        # whole exchange, and httpx has no total timeout of its own to enforce it with.
        # A stalled body could still take one further `read` window past the deadline —
        # bounded, and stated rather than claimed away.
        allowance = min(budget_seconds, self.budget.total)
        timeout = httpx.Timeout(
            connect=min(self.budget.connect, allowance),
            read=min(self.budget.read, allowance),
            write=min(self.budget.read, allowance),
            pool=min(self.budget.connect, allowance),
        )
        try:
            response = self._client.request(
                request.method,
                request.url,
                headers=list(request.headers),
                content=request.body,
                timeout=timeout,
            )
            body = response.read()
        except (httpx.ConnectTimeout, httpx.ConnectError, httpx.PoolTimeout, httpx.ProxyError) as e:
            raise NotSent(type(e).__name__) from e
        except (httpx.InvalidURL, httpx.UnsupportedProtocol, httpx.TooManyRedirects) as e:
            raise Malformed(type(e).__name__) from e
        except httpx.DecodingError as e:
            raise Malformed(type(e).__name__) from e
        except httpx.TransportError as e:
            # Read/write timeouts, dropped connections, protocol violations after send.
            # The catch-all lands here and not in `NotSent` on purpose: an unrecognised
            # fault must not be assumed harmless to repeat.
            raise Interrupted(type(e).__name__) from e

        return VendorResponse(
            status_code=response.status_code,
            headers=tuple((key, value) for key, value in response.headers.multi_items()),
            body=body,
        )

    def close(self) -> None:
        self._client.close()
