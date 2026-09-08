"""`BaseClient` — the classification that decides whether a repeat is safe.

Master `# 20.8`'s four guarantees, item 9 §21 PV3-PV4 and §27 AX1-AX6. The tests are
grouped by the question each outcome answers: *did it arrive, and did it apply?*
"""

from __future__ import annotations

import pytest

from integrations.base.circuit_breaker import CircuitState
from integrations.base.client import BaseClient
from integrations.base.faults import (
    AmbiguousOutcome,
    CircuitOpen,
    VendorProtocolError,
    VendorUnavailable,
    VendorUnreachable,
)
from integrations.base.retry import RetryPolicy, RetrySafety
from integrations.base.transport import Interrupted, Malformed, NotSent, VendorResponse
from tests.integrations.base.conftest import ScriptedTransport

SAFETIES = list(RetrySafety)


def ok(status: int = 200, **kwargs) -> VendorResponse:
    return VendorResponse(status_code=status, **kwargs)


def build(transport, clock, rng, retry, breaker, **overrides) -> BaseClient:
    return BaseClient(
        vendor="provider",
        transport=transport,
        retry=overrides.get("retry", retry),
        breaker=overrides.get("breaker", breaker),
        clock=clock,
        rng=rng,
    )


class TestTheDeclarationIsMandatory:
    def test_retry_safety_has_no_default(self, clock, rng, retry, breaker, request_):
        """AX1: the transport cannot know, so it is never allowed to assume."""
        client = build(ScriptedTransport([ok()]), clock, rng, retry, breaker)
        with pytest.raises(TypeError):
            client.send(request_, operation="charge")  # type: ignore[call-arg]


class TestAnAnsweredCall:
    def test_a_success_returns_the_response(self, clock, rng, retry, breaker, request_):
        transport = ScriptedTransport([ok(200, body=b"yes")])
        client = build(transport, clock, rng, retry, breaker)
        response = client.send(
            request_, operation="charge", retry_safety=RetrySafety.PROVIDER_KEYED
        )
        assert (response.status_code, response.body) == (200, b"yes")
        assert transport.calls == 1

    @pytest.mark.parametrize("status", [400, 401, 403, 404, 409, 422, 451])
    def test_a_rejection_is_returned_not_raised(self, clock, rng, retry, breaker, request_, status):
        """TB6: whether 'declined' is permanent is vendor knowledge, owned by its package."""
        transport = ScriptedTransport([ok(status)])
        client = build(transport, clock, rng, retry, breaker)
        response = client.send(
            request_, operation="charge", retry_safety=RetrySafety.UNSAFE_TO_REPEAT
        )
        assert response.status_code == status
        assert transport.calls == 1

    def test_a_rejection_is_evidence_the_vendor_is_healthy(
        self, clock, rng, retry, breaker, request_
    ):
        """A malformed request of ours must not open a circuit against a working provider."""
        transport = ScriptedTransport([ok(422) for _ in range(10)])
        client = build(transport, clock, rng, retry, breaker)
        for _ in range(10):
            client.send(request_, operation="charge", retry_safety=RetrySafety.PROVIDER_KEYED)
        assert client.circuit_state is CircuitState.CLOSED


class TestNothingArrived:
    """A connect failure is safe to repeat for every operation: nothing was sent."""

    @pytest.mark.parametrize("safety", SAFETIES, ids=lambda s: s.value)
    def test_it_is_retried_whatever_the_declaration(
        self, clock, rng, retry, breaker, request_, safety
    ):
        transport = ScriptedTransport([NotSent("ConnectTimeout"), ok(200)])
        client = build(transport, clock, rng, retry, breaker)
        assert client.send(request_, operation="charge", retry_safety=safety).status_code == 200
        assert transport.calls == 2

    def test_exhaustion_raises_unreachable(self, clock, rng, retry, breaker, request_):
        transport = ScriptedTransport([NotSent("ConnectError") for _ in range(3)])
        client = build(transport, clock, rng, retry, breaker)
        with pytest.raises(VendorUnreachable) as raised:
            client.send(request_, operation="charge", retry_safety=RetrySafety.UNSAFE_TO_REPEAT)
        assert raised.value.attempts == 3
        assert transport.calls == 3


class TestAmbiguity:
    """§27: sent, and it is unknown whether the provider applied it."""

    @pytest.mark.parametrize(
        "safety",
        [RetrySafety.NATURALLY_IDEMPOTENT, RetrySafety.PROVIDER_KEYED],
        ids=lambda s: s.value,
    )
    def test_a_declared_safe_operation_is_retried(
        self, clock, rng, retry, breaker, request_, safety
    ):
        transport = ScriptedTransport([Interrupted("ReadTimeout"), ok(200)])
        client = build(transport, clock, rng, retry, breaker)
        assert client.send(request_, operation="charge", retry_safety=safety).status_code == 200

    def test_an_unsafe_operation_stops_at_once(self, clock, rng, retry, breaker, request_):
        """AX1/AX6: for a payment, the blind retry is a double charge."""
        transport = ScriptedTransport([Interrupted("ReadTimeout"), ok(200)])
        client = build(transport, clock, rng, retry, breaker)
        with pytest.raises(AmbiguousOutcome) as raised:
            client.send(request_, operation="charge", retry_safety=RetrySafety.UNSAFE_TO_REPEAT)
        assert raised.value.attempts == 1
        assert transport.calls == 1

    def test_exhausting_the_bounds_on_a_safe_operation_still_raises_ambiguity(
        self, clock, rng, retry, breaker, request_
    ):
        """The caller must learn *which* uncertainty it has, not merely that it failed."""
        transport = ScriptedTransport([Interrupted("ReadTimeout") for _ in range(3)])
        client = build(transport, clock, rng, retry, breaker)
        with pytest.raises(AmbiguousOutcome):
            client.send(request_, operation="charge", retry_safety=RetrySafety.PROVIDER_KEYED)


class TestStatusClassification:
    @pytest.mark.parametrize("status", [429, 503])
    @pytest.mark.parametrize("safety", SAFETIES, ids=lambda s: s.value)
    def test_a_refusal_at_the_edge_is_repeatable_for_any_operation(
        self, clock, rng, retry, breaker, request_, status, safety
    ):
        """The provider states it did not process the request, so a repeat cannot double it."""
        transport = ScriptedTransport([ok(status), ok(200)])
        client = build(transport, clock, rng, retry, breaker)
        assert client.send(request_, operation="charge", retry_safety=safety).status_code == 200
        assert transport.calls == 2

    def test_exhausting_a_refusal_raises_unavailable(self, clock, rng, retry, breaker, request_):
        transport = ScriptedTransport([ok(503) for _ in range(3)])
        client = build(transport, clock, rng, retry, breaker)
        with pytest.raises(VendorUnavailable) as raised:
            client.send(request_, operation="charge", retry_safety=RetrySafety.NATURALLY_IDEMPOTENT)
        assert raised.value.attempts == 3

    @pytest.mark.parametrize("status", [408, 500, 502, 504])
    def test_a_failure_behind_the_edge_is_ambiguous(
        self, clock, rng, retry, breaker, request_, status
    ):
        """The request reached the provider and failed *while being processed*.

        This is the row that a plain 'retry every 5xx' policy gets wrong: a `500` may have
        applied. It is AX1's forbidden inference wearing a status code.
        """
        transport = ScriptedTransport([ok(status), ok(200)])
        client = build(transport, clock, rng, retry, breaker)
        with pytest.raises(AmbiguousOutcome) as raised:
            client.send(request_, operation="charge", retry_safety=RetrySafety.UNSAFE_TO_REPEAT)
        assert raised.value.attempts == 1
        assert transport.calls == 1

    @pytest.mark.parametrize("status", [408, 500, 502, 504])
    def test_the_same_status_is_retried_under_a_provider_key(
        self, clock, rng, retry, breaker, request_, status
    ):
        """AX2: the key is what makes the repeat provably the same operation."""
        transport = ScriptedTransport([ok(status), ok(200)])
        client = build(transport, clock, rng, retry, breaker)
        assert (
            client.send(
                request_, operation="charge", retry_safety=RetrySafety.PROVIDER_KEYED
            ).status_code
            == 200
        )


class TestMalformedExchanges:
    def test_it_is_never_retried(self, clock, rng, retry, breaker, request_):
        transport = ScriptedTransport([Malformed("InvalidURL"), ok(200)])
        client = build(transport, clock, rng, retry, breaker)
        with pytest.raises(VendorProtocolError):
            client.send(request_, operation="charge", retry_safety=RetrySafety.NATURALLY_IDEMPOTENT)
        assert transport.calls == 1

    def test_our_defect_is_not_charged_to_the_vendors_breaker(
        self, clock, rng, retry, breaker, request_
    ):
        """TD3: a software defect is never dressed as a provider failure."""
        transport = ScriptedTransport([Malformed("InvalidURL") for _ in range(10)])
        client = build(transport, clock, rng, retry, breaker)
        for _ in range(10):
            with pytest.raises(VendorProtocolError):
                client.send(request_, operation="charge", retry_safety=RetrySafety.PROVIDER_KEYED)
        assert client.circuit_state is CircuitState.CLOSED


class TestTheCircuit:
    def test_it_opens_and_then_fast_fails_without_calling_the_vendor(
        self, clock, rng, request_, breaker
    ):
        policy = RetryPolicy(
            max_attempts=2,
            max_age_seconds=30.0,
            initial_backoff_seconds=0.2,
            multiplier=2.0,
            max_backoff_seconds=2.0,
        )
        transport = ScriptedTransport([NotSent("ConnectError"), NotSent("ConnectError")])
        client = BaseClient(
            vendor="provider",
            transport=transport,
            retry=policy,
            breaker=type(breaker)(failure_threshold=2, cooldown_seconds=30.0),
            clock=clock,
            rng=rng,
        )
        with pytest.raises(VendorUnreachable):
            client.send(request_, operation="charge", retry_safety=RetrySafety.PROVIDER_KEYED)
        assert client.circuit_state is CircuitState.OPEN

        with pytest.raises(CircuitOpen) as raised:
            client.send(request_, operation="charge", retry_safety=RetrySafety.PROVIDER_KEYED)
        # PV4: the work is not disposed of — the caller's message keeps its own bounds.
        # The vendor was simply never contacted.
        assert transport.calls == 2
        assert raised.value.attempts == 0

    def test_circuit_open_is_a_kind_of_unreachable(self):
        """Nothing was sent, so the fault the caller catches says exactly that."""
        assert issubclass(CircuitOpen, VendorUnreachable)


class TestBounds:
    def test_the_attempt_bound_holds(self, clock, rng, breaker, request_):
        policy = RetryPolicy(
            max_attempts=5,
            max_age_seconds=300.0,
            initial_backoff_seconds=0.2,
            multiplier=2.0,
            max_backoff_seconds=2.0,
        )
        transport = ScriptedTransport([NotSent("ConnectError") for _ in range(5)])
        client = BaseClient(
            vendor="provider",
            transport=transport,
            retry=policy,
            breaker=breaker,
            clock=clock,
            rng=rng,
        )
        with pytest.raises(VendorUnreachable):
            client.send(request_, operation="fetch", retry_safety=RetrySafety.PROVIDER_KEYED)
        assert transport.calls == 5

    def test_the_age_bound_holds_before_the_attempt_bound(self, clock, rng, breaker, request_):
        """RB3: bounding by age is what stops a fast-failing circuit from burning attempts."""
        policy = RetryPolicy(
            max_attempts=100,
            max_age_seconds=1.0,
            initial_backoff_seconds=0.4,
            multiplier=2.0,
            max_backoff_seconds=2.0,
        )
        transport = ScriptedTransport([NotSent("ConnectError") for _ in range(100)])
        client = BaseClient(
            vendor="provider",
            transport=transport,
            retry=policy,
            breaker=breaker,
            clock=clock,
            rng=rng,
        )
        with pytest.raises(VendorUnreachable):
            client.send(request_, operation="fetch", retry_safety=RetrySafety.PROVIDER_KEYED)
        assert transport.calls < 100
        assert clock.now - 1000.0 <= policy.max_age_seconds

    def test_the_remaining_age_is_the_budget_each_attempt_gets(
        self, clock, rng, retry, breaker, request_
    ):
        transport = ScriptedTransport([NotSent("ConnectError"), ok(200)])
        client = build(transport, clock, rng, retry, breaker)
        client.send(request_, operation="fetch", retry_safety=RetrySafety.PROVIDER_KEYED)
        assert transport.budgets[0] == retry.max_age_seconds
        assert transport.budgets[1] < transport.budgets[0]


class TestRetryAfterIsHonoured:
    def test_a_provider_hint_lengthens_the_wait(self, clock, rng, retry, breaker, request_):
        transport = ScriptedTransport([ok(429, headers=(("Retry-After", "2"),)), ok(200)])
        client = build(transport, clock, rng, retry, breaker)
        client.send(request_, operation="fetch", retry_safety=RetrySafety.PROVIDER_KEYED)
        assert clock.slept == [2.0]

    def test_a_hint_never_shortens_it(self, clock, rng, retry, breaker, request_):
        """BO3/BO4: a provider may not talk the client into a tight loop."""
        transport = ScriptedTransport([ok(429, headers=(("Retry-After", "0"),)), ok(200)])
        client = build(transport, clock, rng, retry, breaker)
        client.send(request_, operation="fetch", retry_safety=RetrySafety.PROVIDER_KEYED)
        assert clock.slept and clock.slept[0] >= 0.1


class TestNothingSensitiveEscapes:
    """Master `# 21`, item 10 §11: a fault and a log line are exactly where a secret must not be."""

    def test_a_fault_carries_no_url_header_or_body(self, clock, rng, retry, breaker):
        from integrations.base.transport import VendorRequest

        secret_request = VendorRequest(
            method="POST",
            url="https://provider.example/v1/charge?access_token=SECRET-TOKEN",
            headers=(("Authorization", "Bearer SECRET-TOKEN"),),
            body=b'{"pan":"4111111111111111"}',
        )
        transport = ScriptedTransport([NotSent("ConnectError") for _ in range(3)])
        client = build(transport, clock, rng, retry, breaker)
        with pytest.raises(VendorUnreachable) as raised:
            client.send(secret_request, operation="charge", retry_safety=RetrySafety.PROVIDER_KEYED)
        rendered = str(raised.value)
        assert "SECRET-TOKEN" not in rendered
        assert "4111111111111111" not in rendered
        assert "provider.example" not in rendered
        assert raised.value.vendor == "provider"
        assert raised.value.operation == "charge"

    def test_a_log_line_carries_no_url_header_or_body(self, clock, rng, retry, breaker, caplog):
        from integrations.base.transport import VendorRequest

        secret_request = VendorRequest(
            method="POST",
            url="https://provider.example/v1/charge?access_token=SECRET-TOKEN",
            headers=(("Authorization", "Bearer SECRET-TOKEN"),),
            body=b'{"pan":"4111111111111111"}',
        )
        transport = ScriptedTransport([ok(503), ok(200)])
        client = build(transport, clock, rng, retry, breaker)
        with caplog.at_level("INFO", logger="integrations.client"):
            client.send(secret_request, operation="charge", retry_safety=RetrySafety.PROVIDER_KEYED)
        records = [r for r in caplog.records if r.name == "integrations.client"]
        assert len(records) == 2
        for record in records:
            rendered = str(record.__dict__)
            assert "SECRET-TOKEN" not in rendered
            assert "4111111111111111" not in rendered
            assert "provider.example" not in rendered
        assert [r.outcome for r in records] == ["refused", "answered"]
        assert records[0].vendor == "provider"
        assert records[0].attempt == 1
