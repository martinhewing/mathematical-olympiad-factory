"""
tests/unit/test_concept_store.py

Unit tests for the concept accumulation layer.
Tests the semilattice evaluator — the core logic that was missing.

ConnectSphere uses an in-memory session store, so no mocking needed —
we just clear _store between tests.

Testing:
  - Concepts accumulate across turns (union, not replace)
  - Confidence gate rejects low-confidence concepts
  - Semilattice passes when union covers required set
  - Semilattice fails when union is incomplete
  - Retraction removes a single concept
  - Clear wipes the stage cleanly
  - Coverage is computed correctly
"""

import pytest

import competitive_programming_factory.session_store as store
from competitive_programming_factory.engine.concept_store import (
    CONFIDENCE_THRESHOLD,
    accumulate,
    clear_stage,
    evaluate,
    get_accumulated,
    get_required,
    record_fragment,
    retract,
)


@pytest.fixture(autouse=True)
def clean_store():
    """Wipe the in-memory store between tests."""
    store._store.clear()
    store._store["test-session"] = {}
    yield
    store._store.clear()


SID = "test-session"


# ── Accumulation ──────────────────────────────────────────────────────────────


@pytest.mark.unit
class TestAccumulation:
    def test_single_turn_stores_concepts(self):
        result = accumulate(SID, 1, ["requirements_clarification", "scale_estimation"])
        assert result == {"requirements_clarification", "scale_estimation"}

    def test_multiple_turns_build_union(self):
        accumulate(SID, 1, ["requirements_clarification"])
        result = accumulate(SID, 1, ["scale_estimation", "api_design"])
        assert result == {"requirements_clarification", "scale_estimation", "api_design"}

    def test_duplicates_are_idempotent(self):
        accumulate(SID, 1, ["requirements_clarification"])
        accumulate(SID, 1, ["requirements_clarification"])
        assert get_accumulated(SID, 1) == {"requirements_clarification"}

    def test_empty_concepts_list_is_safe(self):
        accumulate(SID, 1, [])
        assert get_accumulated(SID, 1) == set()

    def test_stages_are_independent(self):
        accumulate(SID, 1, ["requirements_clarification"])
        accumulate(SID, 2, ["data_model"])
        assert get_accumulated(SID, 1) == {"requirements_clarification"}
        assert get_accumulated(SID, 2) == {"data_model"}


# ── Confidence gate ───────────────────────────────────────────────────────────


@pytest.mark.unit
class TestConfidenceGate:
    def test_high_confidence_accepted(self):
        result = accumulate(
            SID,
            1,
            ["requirements_clarification"],
            confidence_scores={"requirements_clarification": 0.95},
        )
        assert "requirements_clarification" in result

    def test_low_confidence_rejected(self):
        result = accumulate(
            SID,
            1,
            ["requirements_clarification"],
            confidence_scores={"requirements_clarification": 0.50},
        )
        assert "requirements_clarification" not in result

    def test_exact_threshold_accepted(self):
        result = accumulate(
            SID,
            1,
            ["requirements_clarification"],
            confidence_scores={"requirements_clarification": CONFIDENCE_THRESHOLD},
        )
        assert "requirements_clarification" in result

    def test_missing_confidence_defaults_to_accepted(self):
        """Backward compat: prompts that don't return confidence yet."""
        result = accumulate(SID, 1, ["requirements_clarification"], confidence_scores={})
        assert "requirements_clarification" in result

    def test_none_confidence_scores_accepts_all(self):
        result = accumulate(SID, 1, ["requirements_clarification"], confidence_scores=None)
        assert "requirements_clarification" in result

    def test_mixed_confidence(self):
        result = accumulate(
            SID,
            1,
            ["requirements_clarification", "scale_estimation"],
            confidence_scores={
                "requirements_clarification": 0.95,
                "scale_estimation": 0.40,
            },
        )
        assert "requirements_clarification" in result
        assert "scale_estimation" not in result


# ── Semilattice evaluation ────────────────────────────────────────────────────


@pytest.mark.unit
class TestSemilatticeEvaluation:
    def test_passes_when_all_required_demonstrated(self):
        accumulate(SID, 1, ["requirements_clarification", "scale_estimation", "api_design"])
        result = evaluate(SID, 1)
        assert result["passed"] is True
        assert result["missing"] == set()
        assert result["coverage"] == 1.0

    def test_fails_when_missing_concepts(self):
        accumulate(SID, 1, ["requirements_clarification"])
        result = evaluate(SID, 1)
        assert result["passed"] is False
        assert "scale_estimation" in result["missing"]
        assert "api_design" in result["missing"]

    def test_passes_across_multiple_turns(self):
        """The core behaviour: union across turns, not just last turn."""
        accumulate(SID, 1, ["requirements_clarification"])
        accumulate(SID, 1, ["scale_estimation"])
        accumulate(SID, 1, ["api_design"])
        result = evaluate(SID, 1)
        assert result["passed"] is True

    def test_coverage_is_fractional(self):
        accumulate(SID, 1, ["requirements_clarification"])
        result = evaluate(SID, 1)
        assert abs(result["coverage"] - 1 / 3) < 0.01

    def test_empty_stage_has_zero_coverage(self):
        result = evaluate(SID, 1)
        assert result["passed"] is False
        assert result["coverage"] == 0.0

    def test_superset_still_passes(self):
        """Extra concepts beyond required don't break anything."""
        accumulate(
            SID,
            1,
            [
                "requirements_clarification",
                "scale_estimation",
                "api_design",
                "bonus_insight",
            ],
        )
        result = evaluate(SID, 1)
        assert result["passed"] is True


# ── Required concepts ─────────────────────────────────────────────────────────


@pytest.mark.unit
class TestRequiredConcepts:
    def test_known_stages_return_defined_sets(self):
        assert get_required(1) == {"requirements_clarification", "scale_estimation", "api_design"}
        assert get_required(2) == {"data_model", "storage_choice", "schema_design"}
        assert get_required(3) == {"system_components", "scalability", "fault_tolerance"}

    def test_unknown_stage_returns_fallback(self):
        result = get_required(99)
        assert len(result) == 2
        assert all("concept_99" in c for c in result)


# ── Retraction ────────────────────────────────────────────────────────────────


@pytest.mark.unit
class TestRetraction:
    def test_retract_removes_concept(self):
        accumulate(SID, 1, ["requirements_clarification", "scale_estimation"])
        result = retract(SID, 1, "requirements_clarification")
        assert "requirements_clarification" not in result
        assert "scale_estimation" in result

    def test_retract_nonexistent_is_safe(self):
        accumulate(SID, 1, ["requirements_clarification"])
        result = retract(SID, 1, "never_added")
        assert result == {"requirements_clarification"}

    def test_retract_from_empty_stage_is_safe(self):
        result = retract(SID, 1, "anything")
        assert result == set()


# ── Fragment recording ────────────────────────────────────────────────────────


@pytest.mark.unit
class TestFragmentRecording:
    def test_fragments_accumulate(self):
        record_fragment(SID, 1, "First answer about requirements")
        record_fragment(SID, 1, "Second answer about scale")
        fragments = store.load_field(SID, "answer_fragments:1")
        assert len(fragments) == 2
        assert fragments[0] == "First answer about requirements"


# ── Clear ─────────────────────────────────────────────────────────────────────


@pytest.mark.unit
class TestClearStage:
    def test_clear_wipes_concepts_and_fragments(self):
        accumulate(SID, 1, ["requirements_clarification"])
        record_fragment(SID, 1, "Some answer")
        clear_stage(SID, 1)
        assert get_accumulated(SID, 1) == set()
        assert store.load_field(SID, "answer_fragments:1") == []
