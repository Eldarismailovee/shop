"""The HTTP boundary that binds `request_id` (item 10 §8, RQ8, PR4-PR6, PV5-PV6).

`config.urls` routes nothing yet, so these cases drive the middleware directly over a
`RequestFactory` request and a stand-in view. That is the whole unit under test: no route is
invented to make it exercisable, and the view is a closure that records what it observed.
"""

from __future__ import annotations

from collections.abc import Callable

import pytest
from django.http import HttpRequest, HttpResponse
from django.test import RequestFactory, override_settings

from core.observability.context import (
    current_request_id,
    current_span_id,
    current_trace_id,
)
from core.observability.request_id import normalised_request_id
from interfaces.request_context import REQUEST_ID_HEADER, RequestContextMiddleware


def observing_view(seen: list[str | None]) -> Callable[[HttpRequest], HttpResponse]:
    def view(request: HttpRequest) -> HttpResponse:
        seen.append(current_request_id())
        return HttpResponse("ok")

    return view


def call(request: HttpRequest, seen: list[str | None]) -> HttpResponse:
    return RequestContextMiddleware(observing_view(seen))(request)


@pytest.fixture
def factory() -> RequestFactory:
    return RequestFactory()


class TestMinting:
    def test_a_request_without_a_header_gets_a_minted_identifier(
        self, factory: RequestFactory
    ) -> None:
        seen: list[str | None] = []
        call(factory.get("/"), seen)
        assert normalised_request_id(seen[0]) is not None

    def test_the_identifier_is_echoed_on_the_response(self, factory: RequestFactory) -> None:
        seen: list[str | None] = []
        response = call(factory.get("/"), seen)
        assert response.headers[REQUEST_ID_HEADER] == seen[0]

    def test_two_requests_get_different_identifiers(self, factory: RequestFactory) -> None:
        seen: list[str | None] = []
        call(factory.get("/"), seen)
        call(factory.get("/"), seen)
        assert seen[0] != seen[1]


class TestTrustPolicy:
    @override_settings(OBSERVABILITY_TRUST_EDGE_REQUEST_ID=False)
    def test_an_edge_value_is_ignored_when_the_deployment_does_not_trust_it(
        self, factory: RequestFactory
    ) -> None:
        """RQ8/PV6 — a client-supplied identifier is untrusted input by default."""
        seen: list[str | None] = []
        call(factory.get("/", headers={"x-request-id": "supplied-by-the-caller"}), seen)
        assert seen[0] != "supplied-by-the-caller"

    @override_settings(OBSERVABILITY_TRUST_EDGE_REQUEST_ID=True)
    def test_a_trusted_well_formed_edge_value_is_adopted(self, factory: RequestFactory) -> None:
        seen: list[str | None] = []
        call(factory.get("/", headers={"x-request-id": "edge-9f2c1a7b"}), seen)
        assert seen[0] == "edge-9f2c1a7b"

    @override_settings(OBSERVABILITY_TRUST_EDGE_REQUEST_ID=True)
    @pytest.mark.parametrize("supplied", ["", "has space", "-", "unknown", "x" * 129])
    def test_a_malformed_trusted_value_is_replaced_rather_than_repaired(
        self, factory: RequestFactory, supplied: str
    ) -> None:
        """PR4/PR5 — normalise to absent, then mint; never pad, trim or re-case."""
        seen: list[str | None] = []
        response = call(factory.get("/", headers={"x-request-id": supplied}), seen)
        assert seen[0] != supplied
        assert normalised_request_id(seen[0]) is not None
        assert response.status_code == 200


class TestScope:
    def test_the_trace_pair_stays_absent_because_this_process_runs_no_tracer(
        self, factory: RequestFactory
    ) -> None:
        """SP3 — `producer_span_id` means *our* span; adopting a peer's would be a lie."""
        observed: list[tuple[str | None, str | None]] = []

        def view(request: HttpRequest) -> HttpResponse:
            observed.append((current_trace_id(), current_span_id()))
            return HttpResponse("ok")

        RequestContextMiddleware(view)(
            factory.get("/", headers={"traceparent": f"00-{'a' * 32}-{'b' * 16}-01"})
        )
        assert observed == [(None, None)]

    def test_the_context_is_unbound_after_the_response(self, factory: RequestFactory) -> None:
        seen: list[str | None] = []
        call(factory.get("/"), seen)
        assert current_request_id() is None

    def test_the_context_is_unbound_when_the_view_raises(self, factory: RequestFactory) -> None:
        def failing(request: HttpRequest) -> HttpResponse:
            raise RuntimeError("boom")

        with pytest.raises(RuntimeError):
            RequestContextMiddleware(failing)(factory.get("/"))
        assert current_request_id() is None
