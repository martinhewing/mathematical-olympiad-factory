"""
tests/integration/test_session_engine.py

Integration tests: session engine + FSM + DLL + store working together.
Claude is mocked — testing the wiring, not the AI response.

Testing:
  - create_session correctly initialises FSM, DLL, and store in lockstep
  - CONFIRMED verdict advances the FSM and confirms the DLL node
  - PARTIAL verdict stays in place and records the probe
  - Probe limit triggers FLAGGED — engine does not call Claude again
  - Session state survives a store round-trip (simulates reconnect)
"""

import pytest
from unittest.mock import patch

import competitive_programming_factory.session_store as store
from competitive_programming_factory.domain.fsm.states import State
from competitive_programming_factory.engine import session_engine as engine


@pytest.mark.integration
class TestSessionCreation:
    """
    create_session is the integration point that initialises every layer.
    If anything is wired wrong here, nothing downstream works.
    """

    def test_session_exists_in_store_after_creation(self, mock_scene):
        with patch("competitive_programming_factory.engine.session_engine._generate_scene", return_value=mock_scene):
            sid = engine.create_session("Design a hotel reservation system")

        assert store.exists(sid)

    def test_fsm_is_at_requirements_after_creation(self, mock_scene):
        with patch("competitive_programming_factory.engine.session_engine._generate_scene", return_value=mock_scene):
            sid = engine.create_session("Design a hotel reservation system")

        fsm, _ = store.load(sid)
        assert fsm.state == State.REQUIREMENTS

    def test_dll_has_staged_nodes_after_creation(self, mock_scene):
        """Teach, teach-check, and requirements nodes must all be present."""
        with patch("competitive_programming_factory.engine.session_engine._generate_scene", return_value=mock_scene):
            sid = engine.create_session("Design a hotel reservation system")

        _, dll = store.load(sid)
        ids = [n.stage_id for n in dll.iterate_oldest_first()]
        assert "teach_001" in ids
        assert "requirements_001" in ids

    def test_scene_is_stored_and_retrievable(self, mock_scene):
        with patch("competitive_programming_factory.engine.session_engine._generate_scene", return_value=mock_scene):
            sid = engine.create_session("Design a hotel reservation system")

        scene = store.load_field(sid, "scene")
        assert scene["scene"] == mock_scene["scene"]
        assert scene["primary_tension"] == "availability vs consistency"


@pytest.mark.integration
class TestSubmissionDrivesState:
    """
    process_submission is where FSM, DLL, and Claude meet.
    Critical behaviours: confirmed advances, partial probes, not_met moves on.
    """

    def _make_session(self, mock_scene):
        with patch("competitive_programming_factory.engine.session_engine._generate_scene", return_value=mock_scene):
            return engine.create_session("Design a hotel reservation system")

    def test_confirmed_verdict_advances_fsm_to_next_stage(
        self, mock_scene, mock_stage_spec, mock_confirmed_assessment
    ):
        sid = self._make_session(mock_scene)

        with patch("competitive_programming_factory.engine.session_engine.get_or_generate_stage", return_value=mock_stage_spec), \
             patch("competitive_programming_factory.engine.session_engine.render_and_call", return_value=mock_confirmed_assessment):
            result = engine.process_submission(sid, stage_n=1, answer="I would start by clarifying scale.")

        assert result.verdict  == "CONFIRMED"
        assert result.next_url == f"/session/{sid}/stage/2"

    def test_confirmed_verdict_writes_comprehension_record_to_dll(
        self, mock_scene, mock_stage_spec, mock_confirmed_assessment
    ):
        sid = self._make_session(mock_scene)

        with patch("competitive_programming_factory.engine.session_engine.get_or_generate_stage", return_value=mock_stage_spec), \
             patch("competitive_programming_factory.engine.session_engine.render_and_call", return_value=mock_confirmed_assessment):
            engine.process_submission(sid, stage_n=1, answer="Strong answer.")

        _, dll   = store.load(sid)
        confirmed = [n for n in dll.iterate_oldest_first() if n.status == "confirmed"]
        assert len(confirmed) >= 1

    def test_partial_verdict_stays_on_same_stage(
        self, mock_scene, mock_stage_spec, mock_partial_assessment
    ):
        sid = self._make_session(mock_scene)

        with patch("competitive_programming_factory.engine.session_engine.get_or_generate_stage", return_value=mock_stage_spec), \
             patch("competitive_programming_factory.engine.session_engine.render_and_call", return_value=mock_partial_assessment):
            result = engine.process_submission(sid, stage_n=1, answer="Partial answer.")

        assert result.verdict  == "PARTIAL"
        assert result.next_url == f"/session/{sid}/stage/1"
        assert result.probe    is not None

    def test_probe_limit_triggers_flagged_without_calling_claude(
        self, mock_scene, mock_stage_spec
    ):
        """
        Once probe limit is reached the engine must NOT call Claude.
        Calling Claude after probe limit would generate a 4th probe — a bug.
        """
        sid = self._make_session(mock_scene)

        fsm, dll = store.load(sid)
        fsm.transition_to(State.SYSTEM_DESIGN, trigger="test")
        fsm.transition_to(State.NODE_SESSION,  trigger="test")
        fsm.transition_to(State.OOD_STAGE,     trigger="test")

        from competitive_programming_factory.domain.fsm.machine import PROBE_LIMIT
        for _ in range(PROBE_LIMIT):
            fsm.increment_turn()
        store.save(sid, fsm, dll)

        with patch("competitive_programming_factory.engine.session_engine.get_or_generate_stage", return_value=mock_stage_spec), \
             patch("competitive_programming_factory.engine.session_engine.render_and_call") as mock_claude:
            result = engine.process_submission(sid, stage_n=1, answer="Still struggling.")

        mock_claude.assert_not_called()
        assert result.verdict == "NOT_MET"
        assert "flagged" in (result.next_url or "")


@pytest.mark.integration
class TestStatePolling:
    """
    get_state is called on every Scalar poll.
    It must reflect the current FSM accurately — stale state breaks the UI.
    """

    def test_state_reflects_fsm_phase_after_creation(self, mock_scene):
        with patch("competitive_programming_factory.engine.session_engine._generate_scene", return_value=mock_scene):
            sid = engine.create_session("Design a URL shortener")

        state = engine.get_state(sid)
        assert state["fsm_state"] == "Requirements Gathering"
        assert state["phase"]     == "simulate"

    def test_state_returns_none_for_unknown_session(self):
        assert engine.get_state("nonexistent") is None

    def test_confirmed_stage_advances_next_url_to_stage_2(
        self, mock_scene, mock_stage_spec, mock_confirmed_assessment
    ):
        with patch("competitive_programming_factory.engine.session_engine._generate_scene", return_value=mock_scene):
            sid = engine.create_session("Design a rate limiter")

        with patch("competitive_programming_factory.engine.session_engine.get_or_generate_stage", return_value=mock_stage_spec), \
             patch("competitive_programming_factory.engine.session_engine.render_and_call", return_value=mock_confirmed_assessment):
            result = engine.process_submission(sid, stage_n=1, answer="Good answer.")

        assert result.next_url == f"/session/{sid}/stage/2"
