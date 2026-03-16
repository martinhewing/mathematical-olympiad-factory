"""
tests/conftest.py

Shared fixtures. Scoped correctly:
  - Mutable state  → function scope (always)
  - Expensive setup → session scope
"""

import os
import pytest
from fastapi.testclient import TestClient

import competitive_programming_factory.session_store as store
from competitive_programming_factory.domain.conversation.history import FactoryConversationHistory
from competitive_programming_factory.domain.fsm.machine import FactoryFSM
from competitive_programming_factory.domain.fsm.states import State

_TEST_API_KEY = "test-key-do-not-use-in-production"


# ── App / HTTP client ─────────────────────────────────────────────────────────

@pytest.fixture(scope="session", autouse=True)
def set_test_env():
    os.environ["FACTORY_API_KEY"] = _TEST_API_KEY
    os.environ["DEBUG"] = "true"


@pytest.fixture(scope="session")
def app(set_test_env):
    from competitive_programming_factory.config import get_settings
    get_settings.cache_clear()

    from competitive_programming_factory.app import create_app
    return create_app()


@pytest.fixture
def client(app):
    """HTTP client with the test API key pre-set on every request."""
    return TestClient(app, headers={"X-API-Key": _TEST_API_KEY})


# ── Clean store between tests ─────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def clear_store():
    """
    Session store is module-level state — must be cleared between tests
    or tests bleed into each other.
    """
    store._store.clear()
    yield
    store._store.clear()


# ── Domain objects ────────────────────────────────────────────────────────────

@pytest.fixture
def fsm():
    return FactoryFSM(
        candidate_name    = "Test Candidate",
        candidate_level   = "senior",
        problem_statement = "Design a hotel reservation system",
    )


@pytest.fixture
def dll():
    return FactoryConversationHistory()


@pytest.fixture
def fsm_at_requirements(fsm):
    fsm.transition_to(State.TEACH)
    fsm.transition_to(State.TEACH_CHECK)
    fsm.transition_to(State.REQUIREMENTS)
    return fsm


@pytest.fixture
def fsm_at_ood(fsm):
    fsm.transition_to(State.TEACH)
    fsm.transition_to(State.TEACH_CHECK)
    fsm.transition_to(State.REQUIREMENTS)
    fsm.transition_to(State.SYSTEM_DESIGN)
    fsm.transition_to(State.NODE_SESSION)
    fsm.transition_to(State.OOD_STAGE)
    return fsm


# ── Claude mock payloads ──────────────────────────────────────────────────────

@pytest.fixture
def mock_scene():
    return {
        "scene": (
            "You are the lead engineer at a hotel chain operating across 40 countries. "
            "Millions of guests book rooms each year. Your CEO wants a new reservation "
            "platform live within 18 months."
        ),
        "primary_tension":      "availability vs consistency",
        "deliberate_omissions": ["peak load", "overbooking policy", "cancellation rules"],
        "strong_opening_move":  "Clarify whether search and booking are separate read/write flows",
        "weak_signals":         ["jumps to database schema", "skips scale questions"],
        "scale_clarifications": {"will_answer": [], "will_deflect": []},
    }


@pytest.fixture
def mock_stage_spec():
    return {
        "stage_title":           "Requirements and Scale",
        "opening_question":      "Walk me through how you would approach this problem.",
        "minimum_bar":           "Must clarify scale and identify core entities.",
        "strong_answer_signals": ["asks about concurrent bookings", "separates search from write"],
        "weak_answer_signals":   ["jumps to database design without clarifying scale"],
        "probe_questions":       ["What happens under 10x peak load?"],
        "concepts_tested":       ["requirements_clarification", "scale_estimation"],
        "stakeholder_question":  {
            "audience": "engineering_manager",
            "prompt":   "Explain your approach to your EM in plain English.",
        },
    }


@pytest.fixture
def mock_confirmed_assessment():
    return {
        "verdict":               "CONFIRMED",
        "feedback":              "Strong requirements gathering. Good separation of concerns.",
        "probe":                 None,
        "concepts_demonstrated": ["requirements_clarification", "scale_estimation"],
        "concepts_missing":      [],
        "internal_notes":        "Candidate asked about scale, concurrency, and separation of flows.",
    }


@pytest.fixture
def mock_partial_assessment():
    return {
        "verdict":               "PARTIAL",
        "feedback":              "Good start but missed the read/write separation.",
        "probe":                 "How would you handle search traffic separately from booking writes?",
        "concepts_demonstrated": ["requirements_clarification"],
        "concepts_missing":      ["scale_estimation"],
        "internal_notes":        "Surface-level requirements — needs probing.",
    }


# ── Rate limiter state ────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def clear_rate_limit_windows():
    """
    Rate limiter uses module-level state that persists across tests.
    Clear it between tests or the 20-sessions/hour limit fires mid-suite.
    """
    from competitive_programming_factory.middleware import rate_limit
    rate_limit._windows.clear()
    yield
    rate_limit._windows.clear()
