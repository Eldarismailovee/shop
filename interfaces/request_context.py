"""The HTTP boundary that binds ambient observability context (master `# 23.1`, item 10 §8).

Every durable Outbox record captures its `request_id` from ambient in-process context at the
instant of the `INSERT` (item 10 §12, PC7) — no `public.py` signature, command DTO or selector
parameter ever carries one. Something has to *put* a value into that context at the edge of a
synchronous request, and this is it. Without this middleware the mechanism is complete and
permanently empty: every message a request produces would record a legitimate-looking absence
that actually means "nobody bound the chain's origin".

It is a shared transport helper inside `interfaces/` (item 3 §4.4 `SELF ONLY`), used by every
entry point rather than owned by one of them.

### Adoption is a trust decision, and defaults to refusing

Master `# 23.1` places `request_id` generation at the reverse proxy and expects the
application to carry it through. Item 10 RQ8/PV5/PV6 bound that: a client-supplied identifier
is **untrusted input**, adoptable only after shape validation and only where the deployment's
trust policy permits, because a value from a public unauthenticated endpoint lets an outsider
colour internal logs and forge correlation across unrelated chains.

So adoption is off unless a deployment turns it on, and even then a header that fails the
shape rule is replaced by a minted value rather than repaired. In every case adoption affects
observability only: the value influences no authorization, no rate limiting, no identity and
no business decision anywhere (RQ4, PV5).

### The trace pair is deliberately *not* bound here

`producer_span_id` means "the span that was active when the durable record was written"
(SP3) — absolutely named, so no other component's span can occupy the slot. This process runs
no tracer yet, so it has no span, and adopting the `traceparent` of an upstream peer would
write *that peer's* span into a column whose meaning is "ours". Every message emitted from a
request therefore records the trace pair as absent, which is a complete and legal state
(FS5, FS10), and PR2's pair-defect signal keeps meaning what it says.

Binding the real pair belongs to the slice that introduces an OpenTelemetry bridge — which is
also where a `traceparent` adoption policy per entry point belongs (item 10 §1.2, PV6). The
absence of that bridge is the absence of a call, not a stub.
"""

from __future__ import annotations

from collections.abc import Callable

from django.conf import settings
from django.http import HttpRequest, HttpResponse

from core.observability.context import observability_context
from core.observability.request_id import new_request_id, normalised_request_id

__all__ = ("REQUEST_ID_HEADER", "RequestContextMiddleware")

#: The header the reverse proxy sets, and the one echoed back on the response so an operator
#: and a customer report can be joined without a session or an identity.
REQUEST_ID_HEADER = "X-Request-Id"


class RequestContextMiddleware:
    """Bind the chain's `request_id` for the duration of one request.

    The trust policy is read once, at construction. That is configuration — a bounded scalar
    the deployment owns — and not service location: no dependency is *resolved* here, no
    module is imported by name, and `interfaces/` still imports nothing from `config/`
    (item 3 §7.2, L16).
    """

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self._get_response = get_response
        self._adopt_edge_value = bool(
            getattr(settings, "OBSERVABILITY_TRUST_EDGE_REQUEST_ID", False)
        )

    def __call__(self, request: HttpRequest) -> HttpResponse:
        request_id = self._request_id(request)
        # Every value is passed explicitly, absences included: this scope is a request-origin
        # chain that is untraced, and saying so is not the same as leaving whatever an outer
        # scope happened to bind. `observability_context` restores the previous state on the
        # way out, including when the view raises.
        with observability_context(trace_id=None, span_id=None, request_id=request_id):
            response = self._get_response(request)
        response.headers[REQUEST_ID_HEADER] = request_id
        return response

    def _request_id(self, request: HttpRequest) -> str:
        """Adopt a trusted, well-formed edge value, or mint an opaque one.

        A malformed or over-long header is not an error and is not reported to the client: it
        normalises to absent (PR4, PR5) and the chain gets a minted identifier instead, so a
        broken proxy configuration degrades correlation rather than requests.
        """
        if self._adopt_edge_value:
            adopted = normalised_request_id(request.headers.get(REQUEST_ID_HEADER))
            if adopted is not None:
                return adopted
        return new_request_id()
