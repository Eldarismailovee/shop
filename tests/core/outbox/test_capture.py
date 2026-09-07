"""TCE capture: the canonical origin states, normalisation, and the PR2 pair defect.

Item 10 PR9 tabulates the canonical TCE state per origin, and the first three classes below
are that table, asserted. These are the *capture-level* halves of C85, C86 and C87 — the
end-to-end halves need a real producer and a real consumer and are recorded as deferred.

Nothing here touches a database: capture is a pure read of ambient in-process context, which
is exactly what PC2 requires it to be.
"""

from __future__ import annotations

import pytest

from core.events.context import handling_message
from core.events.identity import EventId
from core.observability.context import observability_context
from core.outbox.capture import capture

TRACE = "4bf92f3577b34da6a3ce929d0e0e4736"
SPAN = "00f067aa0ba902b7"
OTHER_SPAN = "b7ad6b7169203331"


class TestCanonicalOriginStates:
    """PR9's three rows. 'Four fields' never means 'four non-empty values' (FS10)."""

    def test_first_hop_from_a_request(self) -> None:
        """Trace pair present, `request_id` present, causation **absent**.

        Asserting causation present here would be wrong: no parent durable message exists yet.
        """
        with observability_context(trace_id=TRACE, span_id=SPAN, request_id="req-1"):
            state = capture(event_id=EventId.new())

        assert state.trace_id == TRACE
        assert state.producer_span_id == SPAN
        assert state.request_id == "req-1"
        assert state.causation_event_id is None
        assert not state.pair_defect

    def test_system_origin(self) -> None:
        """Trace pair present, `request_id` **absent**, causation absent.

        No synthetic request identifier is minted anywhere: absence is the spelling.
        """
        with observability_context(trace_id=TRACE, span_id=SPAN):
            state = capture(event_id=EventId.new())

        assert state.trace_id == TRACE
        assert state.request_id is None
        assert state.causation_event_id is None

    def test_a_child_message_inherits_request_id_and_carries_causation(self) -> None:
        """CZ1/PC13: causation is the immediate parent's `event_id`, one hop."""
        parent = EventId.new()
        child = EventId.new()

        with observability_context(trace_id=TRACE, span_id=SPAN, request_id="req-1"):
            with handling_message(parent):
                state = capture(event_id=child)

        assert state.causation_event_id == parent
        assert state.request_id == "req-1"

    def test_a_child_of_a_system_origin_chain_still_has_no_request_id(self) -> None:
        """`request_id` is inherited **including its absence** (PR9)."""
        with observability_context(trace_id=TRACE, span_id=SPAN):
            with handling_message(EventId.new()):
                state = capture(event_id=EventId.new())

        assert state.request_id is None
        assert state.causation_event_id is not None

    def test_untraced_production_is_a_legal_state(self) -> None:
        """PR3: no ambient context at all yields four absences and no error."""
        state = capture(event_id=EventId.new())

        assert state.trace_id is None
        assert state.producer_span_id is None
        assert state.request_id is None
        assert state.causation_event_id is None
        assert not state.pair_defect


class TestThePairRule:
    """PR2: both halves, or neither. Exactly one is a defect that is reported, not repaired."""

    def test_a_trace_without_a_span_is_reported_and_read_as_untraced(self) -> None:
        with observability_context(trace_id=TRACE):
            state = capture(event_id=EventId.new())

        assert state.pair_defect
        assert state.trace_id is None
        assert state.producer_span_id is None

    def test_a_span_without_a_trace_is_reported_and_read_as_untraced(self) -> None:
        with observability_context(span_id=SPAN):
            state = capture(event_id=EventId.new())

        assert state.pair_defect
        assert state.trace_id is None

    def test_the_defect_does_not_raise(self) -> None:
        """PC3: capture has no error path. A broken pair must not fail a business transaction."""
        with observability_context(trace_id=TRACE):
            capture(event_id=EventId.new())  # no exception is the assertion

    def test_a_complete_pair_reports_no_defect(self) -> None:
        with observability_context(trace_id=TRACE, span_id=SPAN):
            assert not capture(event_id=EventId.new()).pair_defect


class TestNormalisation:
    """PR3/PR5: malformed becomes absent. Nothing is padded, re-cased or invented."""

    @pytest.mark.parametrize(
        "bad_trace",
        [
            "0" * 32,  # the all-zero identifier is invalid, not "no trace yet"
            TRACE.upper(),  # lowercase hex is the canonical form
            "abc",  # too short
            TRACE + "00",  # too long
            "zzzz2f3577b34da6a3ce929d0e0e4736",  # not hex
            42,  # not even text
        ],
    )
    def test_a_malformed_trace_id_becomes_absent(self, bad_trace: object) -> None:
        with observability_context(trace_id=bad_trace, span_id=SPAN):  # type: ignore[arg-type]
            state = capture(event_id=EventId.new())

        assert state.trace_id is None
        # The pair rule then applies to what survived normalisation, so the valid span goes
        # too: half a pair is never stored.
        assert state.producer_span_id is None
        assert state.pair_defect

    @pytest.mark.parametrize("bad_span", ["0" * 16, SPAN.upper(), "abc", 42])
    def test_a_malformed_span_id_becomes_absent(self, bad_span: object) -> None:
        with observability_context(trace_id=TRACE, span_id=bad_span):  # type: ignore[arg-type]
            assert capture(event_id=EventId.new()).producer_span_id is None

    @pytest.mark.parametrize("placeholder", ["-", "none", "null", "unknown", "NONE", "Unknown"])
    def test_a_request_id_placeholder_becomes_absent(self, placeholder: str) -> None:
        """PR6: present or absent, with no third state. A placeholder is the third state."""
        with observability_context(request_id=placeholder):
            assert capture(event_id=EventId.new()).request_id is None

    def test_an_oversized_request_id_becomes_absent(self) -> None:
        with observability_context(request_id="x" * 200):
            assert capture(event_id=EventId.new()).request_id is None

    def test_a_valid_request_id_survives_verbatim(self) -> None:
        with observability_context(request_id="01JB2K3M4N5P6Q7R"):
            assert capture(event_id=EventId.new()).request_id == "01JB2K3M4N5P6Q7R"


class TestSelfCausation:
    def test_a_message_never_causes_itself(self) -> None:
        """CZ6: self-causation is a defect a later reader cannot distinguish from a loop."""
        identity = EventId.new()

        with handling_message(identity):
            state = capture(event_id=identity)

        assert state.causation_event_id is None

    def test_a_genuinely_different_parent_survives(self) -> None:
        parent, child = EventId.new(), EventId.new()

        with handling_message(parent):
            assert capture(event_id=child).causation_event_id == parent


class TestContextIsolation:
    def test_context_unwinds_after_a_block(self) -> None:
        with observability_context(trace_id=TRACE, span_id=SPAN, request_id="req-1"):
            pass
        assert capture(event_id=EventId.new()).trace_id is None

    def test_context_unwinds_after_an_exception(self) -> None:
        with pytest.raises(RuntimeError):
            with observability_context(trace_id=TRACE, span_id=SPAN):
                raise RuntimeError("boom")
        assert capture(event_id=EventId.new()).trace_id is None

    def test_nested_scopes_restore_the_outer_values(self) -> None:
        with observability_context(trace_id=TRACE, span_id=SPAN, request_id="outer"):
            with observability_context(trace_id=TRACE, span_id=OTHER_SPAN, request_id="inner"):
                assert capture(event_id=EventId.new()).request_id == "inner"
            state = capture(event_id=EventId.new())

        assert state.request_id == "outer"
        assert state.producer_span_id == SPAN

    def test_handling_message_refuses_a_foreign_identity_space(self) -> None:
        """A `PublicId` or a bare UUID in an envelope slot is exactly what ADR-0013 prevents."""
        from core.public_id import PublicId

        with pytest.raises(TypeError, match="EventId"):
            with handling_message(PublicId.new()):  # type: ignore[arg-type]
                pass

    def test_handling_message_accepts_an_explicit_absence(self) -> None:
        """CZ2: 'no parent' is a state a caller may state, not only one it may omit."""
        with handling_message(None):
            assert capture(event_id=EventId.new()).causation_event_id is None
