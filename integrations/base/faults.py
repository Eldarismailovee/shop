"""The vendor fault taxonomy (master `# 20.8`, item 9 §17 TF-A…TF-D, §27 AX1-AX6).

An adapter reports failure through the vendor-neutral contract of the port it implements
and **never raises or interprets a domain public error** (ADR-0006 §2, L21). So these
derive from `Exception`, not from `core.errors.DomainError`, and nothing here is a
business outcome: "the bank was unreachable" says nothing about whether a payment is
valid, and reporting it as one would state as fact something that was never determined.

The taxonomy is organised around the **one question the caller cannot answer for itself**:
*did the request reach the provider, and did it take effect?* Everything else — how many
attempts were made, which status came back — is diagnostic.

| Fault | The request was | Item 9 class |
|---|---|---|
| `VendorUnreachable` | provably **not** delivered | TF-A |
| `CircuitOpen` | provably not delivered — not even attempted | TF-A (PV4) |
| `VendorUnavailable` | delivered; the provider transiently refused, to exhaustion | TF-A |
| `AmbiguousOutcome` | delivered; **the outcome is unknown** | §27 |
| `VendorProtocolError` | exchanged, but the exchange itself was malformed | TF-C/TF-D |

`AmbiguousOutcome` is the one that matters. Item 9 AX1 forbids the inference "timeout,
therefore it is safe to send again", and AX4/AX5 put the resolution in the *workflow's*
state machine — a provider idempotency key (AX2) or an application-owned status lookup and
reconciliation (AX3) — never in the transport. This client's role on ambiguity is bounded
to stopping and saying so.

No fault carries a header, a body, a URL query, a credential or a provider payload: a fault
travels into logs and terminal records, which is exactly where a secret must never be
(master `# 21`, item 10 §11). The fields are the vendor, the operation label the call site
chose, how many attempts were made and how long they took.
"""

from __future__ import annotations

__all__ = (
    "AmbiguousOutcome",
    "CircuitOpen",
    "VendorFault",
    "VendorProtocolError",
    "VendorUnavailable",
    "VendorUnreachable",
)


class VendorFault(Exception):
    """The root of every outbound-integration failure.

    A caller may catch the root or a leaf; both are part of the contract. It is a technical
    fault and propagates untranslated (item 4 §13.5) until an application module that owns
    the workflow decides what the failure *means* for its state machine.
    """

    def __init__(
        self,
        *,
        vendor: str,
        operation: str,
        attempts: int,
        elapsed_seconds: float,
        detail: str = "",
    ) -> None:
        self.vendor = vendor
        self.operation = operation
        self.attempts = attempts
        self.elapsed_seconds = elapsed_seconds
        self.detail = detail
        summary = f"{vendor}.{operation}: {type(self).__name__.lower()}"
        if detail:
            summary = f"{summary} ({detail})"
        super().__init__(f"{summary} after {attempts} attempt(s), {elapsed_seconds:.3f}s")


class VendorUnreachable(VendorFault):
    """The request was provably **not** delivered: no connection, or none in time.

    A repeat is safe for any operation, idempotent or not, because nothing was sent.
    """


class CircuitOpen(VendorUnreachable):
    """The breaker was open, so no call was attempted (PV3).

    PV4: fast-failing changes how long a worker is held, never what happens to the work.
    The caller's message is retried within its own bounds and, on exhaustion, becomes a
    durable operational dead-letter — it is never dropped or marked handled because a
    circuit was open.
    """


class VendorUnavailable(VendorFault):
    """Delivered, and the provider transiently refused until the retry bounds ran out.

    A rate limit, a `503`, a gateway error. The provider is up enough to answer and is
    saying "not now"; whether the work survives is the caller's retry policy's business.
    """


class AmbiguousOutcome(VendorFault):
    """Sent, and **it is unknown whether the provider applied it** (§27).

    Raised when a request that may have taken effect failed after transmission — a read
    timeout, a connection dropped mid-flight — and the call site did not declare the
    operation provably safe to repeat. Resolving it is the workflow's job (AX3/AX4), and
    blind retry is forbidden (AX1): for a payment it is a double charge.
    """


class VendorProtocolError(VendorFault):
    """The exchange itself was malformed — an unreadable or undecodable response.

    Never retried on the normal path: repeating a request that produced garbage produces
    garbage again. It is a defect or a provider contract change, and both need a human.
    """
