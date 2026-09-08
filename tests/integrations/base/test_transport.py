"""`HttpxTransport` — the one wire implementation, and the translation it owns.

The mapping is the substance: the policy above must be able to ask *was it delivered?* and
get a truthful answer whichever exception the library raised. These run against
`httpx.MockTransport`, so the real code path and the real exception classes are exercised
with no socket and no waiting.
"""

from __future__ import annotations

import httpx
import pytest

from integrations.base.timeouts import TimeoutBudget
from integrations.base.transport import (
    HttpxTransport,
    Interrupted,
    Malformed,
    NotSent,
    VendorRequest,
    VendorResponse,
)

BUDGET = TimeoutBudget(connect=3.0, read=10.0, total=15.0)
REQUEST = VendorRequest(method="POST", url="https://provider.example/v1/charge", body=b"{}")


def wired(handler) -> HttpxTransport:
    """A transport whose client is wired to a scripted handler instead of the network."""
    transport = HttpxTransport(budget=BUDGET)
    transport._client.close()
    transport._client = httpx.Client(transport=httpx.MockTransport(handler), follow_redirects=False)
    return transport


def raising(error: Exception):
    def handler(request: httpx.Request) -> httpx.Response:
        raise error

    return handler


class TestTheBudgetIsStructural:
    def test_a_transport_cannot_be_built_without_one(self):
        """Master `# 20.8` §1 and the Phase 1 DoD, as a constructor signature."""
        with pytest.raises(TypeError):
            HttpxTransport()  # type: ignore[call-arg]

    def test_the_budget_reaches_the_library(self):
        seen: list[dict[str, float]] = []

        def handler(request: httpx.Request) -> httpx.Response:
            seen.append(request.extensions["timeout"])
            return httpx.Response(200)

        wired(handler).send(REQUEST, budget_seconds=100.0)
        assert seen == [{"connect": 3.0, "read": 10.0, "write": 10.0, "pool": 3.0}]

    def test_a_smaller_remaining_budget_caps_every_component(self):
        """`total` is a deadline and httpx has no total timeout to enforce it with."""
        seen: list[dict[str, float]] = []

        def handler(request: httpx.Request) -> httpx.Response:
            seen.append(request.extensions["timeout"])
            return httpx.Response(200)

        wired(handler).send(REQUEST, budget_seconds=1.5)
        assert seen == [{"connect": 1.5, "read": 1.5, "write": 1.5, "pool": 1.5}]

    def test_the_budgets_own_total_caps_a_generous_caller(self):
        seen: list[dict[str, float]] = []

        def handler(request: httpx.Request) -> httpx.Response:
            seen.append(request.extensions["timeout"])
            return httpx.Response(200)

        wired(handler).send(REQUEST, budget_seconds=3600.0)
        assert seen[0]["read"] == BUDGET.read


class TestNothingArrived:
    @pytest.mark.parametrize(
        "error",
        [
            httpx.ConnectTimeout("connect timed out"),
            httpx.ConnectError("connection refused"),
            httpx.PoolTimeout("no free connection"),
            httpx.ProxyError("proxy refused"),
        ],
        ids=lambda e: type(e).__name__,
    )
    def test_a_connection_failure_is_provably_not_sent(self, error):
        with pytest.raises(NotSent) as raised:
            wired(raising(error)).send(REQUEST, budget_seconds=10.0)
        assert raised.value.detail == type(error).__name__


class TestAmbiguity:
    @pytest.mark.parametrize(
        "error",
        [
            httpx.ReadTimeout("read timed out"),
            httpx.WriteTimeout("write timed out"),
            httpx.ReadError("connection reset"),
            httpx.WriteError("broken pipe"),
            httpx.RemoteProtocolError("server disconnected"),
        ],
        ids=lambda e: type(e).__name__,
    )
    def test_a_failure_after_transmission_is_interrupted(self, error):
        """The request is out there; the ambiguity is what must survive the translation."""
        with pytest.raises(Interrupted):
            wired(raising(error)).send(REQUEST, budget_seconds=10.0)

    def test_an_unrecognised_transport_fault_is_not_assumed_harmless(self):
        class NovelFault(httpx.TransportError):
            pass

        with pytest.raises(Interrupted):
            wired(raising(NovelFault("something new"))).send(REQUEST, budget_seconds=10.0)


class TestOurOwnDefects:
    """TD3: a software defect is never dressed as a provider failure."""

    def test_an_unusable_url_is_malformed_not_unreachable(self):
        transport = HttpxTransport(budget=BUDGET)
        try:
            with pytest.raises(Malformed):
                transport.send(VendorRequest(method="GET", url="://nonsense"), budget_seconds=10.0)
        finally:
            transport.close()

    def test_an_unsupported_scheme_is_malformed(self):
        transport = HttpxTransport(budget=BUDGET)
        try:
            with pytest.raises(Malformed):
                transport.send(
                    VendorRequest(method="GET", url="gopher://provider.example/x"),
                    budget_seconds=10.0,
                )
        finally:
            transport.close()

    def test_a_malformed_fault_is_never_a_not_sent_fault(self):
        """The distinction is what keeps the retry policy from repeating our own bug."""
        assert not issubclass(Malformed, NotSent)


class TestTheExchange:
    def test_a_response_is_translated_whole(self):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(201, headers={"X-Trace": "abc"}, content=b"created")

        response = wired(handler).send(REQUEST, budget_seconds=10.0)
        assert isinstance(response, VendorResponse)
        assert (response.status_code, response.body) == (201, b"created")
        assert response.header("x-trace") == "abc"

    def test_the_request_reaches_the_provider_as_written(self):
        seen: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            seen.append(request)
            return httpx.Response(200)

        wired(handler).send(
            VendorRequest(
                method="PUT",
                url="https://provider.example/v1/stock",
                headers=(("X-Api-Version", "2"),),
                body=b"payload",
            ),
            budget_seconds=10.0,
        )
        assert seen[0].method == "PUT"
        assert seen[0].headers["x-api-version"] == "2"
        assert seen[0].content == b"payload"

    def test_duplicate_response_headers_survive(self):
        """A dict would silently drop one; `Set-Cookie` is the everyday case."""

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, headers=[("Set-Cookie", "a=1"), ("Set-Cookie", "b=2")])

        response = wired(handler).send(REQUEST, budget_seconds=10.0)
        assert [value for key, value in response.headers if key.lower() == "set-cookie"] == [
            "a=1",
            "b=2",
        ]

    def test_a_missing_header_is_absent_not_empty(self):
        response = VendorResponse(status_code=200)
        assert response.header("Retry-After") is None

    def test_a_redirect_is_returned_not_followed(self):
        """Following one can replay an `Authorization` header at a host the response chose."""
        calls: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            calls.append(str(request.url))
            return httpx.Response(302, headers={"Location": "https://elsewhere.example/"})

        response = wired(handler).send(REQUEST, budget_seconds=10.0)
        assert response.status_code == 302
        assert calls == ["https://provider.example/v1/charge"]
