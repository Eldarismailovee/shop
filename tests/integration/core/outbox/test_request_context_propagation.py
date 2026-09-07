"""The edge-to-durable-row half of C85, as far as this slice can honestly claim it.

Before this slice the capture mechanism was complete and nothing bound its context, so every
message a request produced recorded `request_id` as absent — indistinguishable from the
genuine absence that means system origin. These cases close that gap: a request handled
through the middleware produces a row carrying the identifier the edge minted.

C85's trace half is **not** claimed. This process runs no tracer, so the trace pair is
legitimately absent (the middleware's own tests assert that it stays absent rather than
adopting a peer's span), and the full first-hop row belongs to the slice that adds an
OpenTelemetry bridge.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from django.db import transaction
from django.http import HttpRequest, HttpResponse
from django.test import RequestFactory

from core.observability.request_id import normalised_request_id
from core.outbox.emit import emit
from core.outbox.models import OutboxMessage
from interfaces.request_context import REQUEST_ID_HEADER, RequestContextMiddleware

pytestmark = pytest.mark.django_db

OCCURRED = datetime(2026, 9, 7, 12, 0, tzinfo=UTC)


def emitting_view(request: HttpRequest) -> HttpResponse:
    """A stand-in for any entry point that performs a durable effect and announces it."""
    with transaction.atomic():
        emit(
            event_type="fixture.thing_happened",
            schema_version=1,
            occurred_at=OCCURRED,
            payload={"a": 1},
        )
    return HttpResponse("ok")


class TestRequestOriginChain:
    def test_a_message_emitted_in_a_request_carries_the_edge_identifier(self) -> None:
        response = RequestContextMiddleware(emitting_view)(RequestFactory().post("/"))

        row = OutboxMessage.objects.get()
        assert row.request_id == response.headers[REQUEST_ID_HEADER]
        assert normalised_request_id(row.request_id) is not None

    def test_two_requests_produce_rows_that_name_their_own_chains(self) -> None:
        first = RequestContextMiddleware(emitting_view)(RequestFactory().post("/"))
        second = RequestContextMiddleware(emitting_view)(RequestFactory().post("/"))

        recorded = {row.request_id for row in OutboxMessage.objects.all()}
        assert recorded == {
            first.headers[REQUEST_ID_HEADER],
            second.headers[REQUEST_ID_HEADER],
        }

    def test_the_trace_pair_is_absent_and_that_is_a_complete_state(self) -> None:
        """FS5/FS10 — untraced is a legal TCE state, not a partially captured one."""
        RequestContextMiddleware(emitting_view)(RequestFactory().post("/"))

        row = OutboxMessage.objects.get()
        assert row.trace_id is None
        assert row.producer_span_id is None
        assert row.causation_event_id is None


class TestSystemOriginChain:
    def test_a_message_emitted_outside_a_request_records_no_identifier(self) -> None:
        """RQ3 — absence means system origin, and nothing mints a synthetic stand-in."""
        with transaction.atomic():
            emit(
                event_type="fixture.thing_happened",
                schema_version=1,
                occurred_at=OCCURRED,
                payload={"a": 1},
            )

        assert OutboxMessage.objects.get().request_id is None

    def test_the_identifier_does_not_leak_out_of_the_request_that_bound_it(self) -> None:
        RequestContextMiddleware(emitting_view)(RequestFactory().post("/"))
        with transaction.atomic():
            emit(
                event_type="fixture.thing_happened",
                schema_version=1,
                occurred_at=OCCURRED,
                payload={"a": 1},
            )

        rows = OutboxMessage.objects.order_by("id")
        assert rows[0].request_id is not None
        assert rows[1].request_id is None
