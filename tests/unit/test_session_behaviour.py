"""
tests/unit/test_session_behaviour.py

Unit tests for FactoryFSM and FactoryConversationHistory.

Testing:
  - FSM rejects paths that skip required stages
  - Probe limit triggers FLAGGED — not another probe
  - DLL records the full journey in traversable order
  - Context window prioritises current stage, then comprehension records
"""

import pytest

from competitive_programming_factory.domain.fsm.machine import PROBE_LIMIT, FSMTransitionError
from competitive_programming_factory.domain.fsm.states import State


@pytest.mark.unit
@pytest.mark.skip(reason="FSM refactored to concept architecture")
class TestFSMEnforcesSessionOrder:
    """
    The FSM is the contract that prevents a candidate from jumping
    straight to evaluation without passing through the required stages.
    Any bypass is a bug — these tests catch it.
    """

    def test_cannot_skip_teach_phase(self, fsm):
        """A candidate cannot jump from start straight to requirements."""
        with pytest.raises(FSMTransitionError):
            fsm.transition_to(State.REQUIREMENTS)

    def test_cannot_skip_to_evaluate_from_requirements(self, fsm_at_requirements):
        """Requirements gathering cannot skip directly to evaluation."""
        with pytest.raises(FSMTransitionError):
            fsm_at_requirements.transition_to(State.EVALUATE)

    def test_valid_path_reaches_ood(self, fsm):
        """The full required path from start to OOD stage succeeds."""
        fsm.transition_to(State.TEACH)
        fsm.transition_to(State.TEACH_CHECK)
        fsm.transition_to(State.REQUIREMENTS)
        fsm.transition_to(State.SYSTEM_DESIGN)
        fsm.transition_to(State.NODE_SESSION)
        fsm.transition_to(State.OOD_STAGE)
        assert fsm.state == State.OOD_STAGE

    def test_failed_transition_does_not_advance_state(self, fsm):
        """A rejected transition leaves the FSM exactly where it was."""
        with pytest.raises(FSMTransitionError):
            fsm.transition_to(State.EVALUATE)
        assert fsm.state == State.SESSION_START

    def test_teach_gate_can_loop_back(self, fsm):
        """If the lesson didn't land, the FSM can return to TEACH."""
        fsm.transition_to(State.TEACH)
        fsm.transition_to(State.TEACH_CHECK)
        fsm.transition_to(State.TEACH)  # lesson failed — re-teach
        assert fsm.state == State.TEACH


@pytest.mark.unit
@pytest.mark.skip(reason="FSM refactored to concept architecture")
class TestProbeLimitEnforcement:
    """
    The probe limit prevents infinite loops on a struggling candidate.
    When hit, the FSM must transition to FLAGGED — not issue probe round 4.
    """

    def test_probe_limit_not_reached_before_ceiling(self, fsm_at_ood):
        for _ in range(PROBE_LIMIT - 1):
            fsm_at_ood.increment_turn()
        assert fsm_at_ood.probe_limit_reached is False

    def test_probe_limit_reached_at_ceiling(self, fsm_at_ood):
        for _ in range(PROBE_LIMIT):
            fsm_at_ood.increment_turn()
        assert fsm_at_ood.probe_limit_reached is True

    def test_probe_rounds_only_increment_in_ood_stage(self, fsm_at_requirements):
        """Turns in REQUIREMENTS do not consume probe rounds."""
        for _ in range(PROBE_LIMIT + 5):
            fsm_at_requirements.increment_turn()
        assert fsm_at_requirements.probe_limit_reached is False

    def test_transition_to_flagged_is_valid_from_ood(self, fsm_at_ood):
        """FLAGGED is a valid transition from OOD_STAGE — the engine relies on this."""
        fsm_at_ood.transition_to(State.FLAGGED, trigger="probe_limit")
        assert fsm_at_ood.state == State.FLAGGED

    def test_flagged_records_reason_in_context(self, fsm_at_ood):
        """The flag reason must survive for the human reviewer."""
        fsm_at_ood.context.raise_flag(
            reason="3 probe rounds exhausted on STAGE-1",
            label_id="STAGE-1",
        )
        assert fsm_at_ood.context.flagged is True
        assert "STAGE-1" in fsm_at_ood.context.flag_label_id


@pytest.mark.unit
class TestDLLRecordsJourney:
    """
    The DLL is the candidate's complete session history in traversable form.
    Claude uses context_window_build() to decide what to include in each prompt.
    If the DLL loses data or links break, Claude loses context mid-session.
    """

    def test_stages_added_in_order_are_traversable_oldest_first(self, dll):
        dll.add_stage("teach_001", "teach")
        dll.add_stage("requirements_001", "requirements")
        dll.add_stage("ood_STAGE-1_001", "ood_stage")

        ids = [n.stage_id for n in dll.iterate_oldest_first()]
        assert ids == ["teach_001", "requirements_001", "ood_STAGE-1_001"]

    def test_current_always_points_to_most_recent_stage(self, dll):
        dll.add_stage("teach_001", "teach")
        dll.add_stage("ood_001", "ood_stage")
        assert dll.current.stage_id == "ood_001"

    def test_context_window_includes_comprehension_records_from_past_stages(self, dll):
        """
        Confirmed labels from past stages must appear in the context window.
        Claude needs this to avoid re-asking confirmed concepts.
        """
        past = dll.add_stage("ood_STAGE-1_001", "ood_stage")
        past.label_id = "STAGE-1"
        past.confirm(
            {
                "label_id": "STAGE-1",
                "concepts_demonstrated": ["requirements_clarification"],
                "evidence_summary": "Candidate asked about scale and separation of flows.",
            }
        )

        dll.add_stage("ood_STAGE-2_002", "ood_stage")  # now current

        context = dll.context_window_build()
        all_text = " ".join(t.get("content", "") for t in context)
        assert "STAGE-1" in all_text
        assert "requirements_clarification" in all_text

    def test_confirmed_labels_list_excludes_unconfirmed_stages(self, dll):
        confirmed = dll.add_stage("ood_STAGE-1_001", "ood_stage")
        confirmed.label_id = "STAGE-1"
        confirmed.confirm({"label_id": "STAGE-1", "concepts_demonstrated": []})

        incomplete = dll.add_stage("ood_STAGE-2_002", "ood_stage")
        incomplete.label_id = "STAGE-2"

        assert dll.confirmed_labels == ["STAGE-1"]
        assert "STAGE-2" not in dll.confirmed_labels
