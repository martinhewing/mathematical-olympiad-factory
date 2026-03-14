"""
connectionsphere_factory/domain/agents/registry.py

Maps FSM states → agents.

  TEACH, TEACH_CHECK  → TutorAgent  (Alex — warm senior FAANG staff engineer)
  All other states    → InterviewerAgent  (Jordan — FAANG principal)

Usage:
    agent = get_agent_for_state(fsm_state_value)
    voice_id = agent.voice_id(settings)
    system_prompt = agent.system_prompt(candidate_first_name)
"""
from __future__ import annotations

from enum import Enum

from connectionsphere_factory.domain.agents.base import BaseAgent
from connectionsphere_factory.domain.agents.tutor import TutorAgent
from connectionsphere_factory.domain.agents.interviewer import InterviewerAgent


class AgentType(Enum):
    TUTOR       = "tutor"
    INTERVIEWER = "interviewer"


# States where the tutor agent is active
_TUTOR_STATES = {
    "Concept Teach",
    "Concept Teach Check",
    "Teach",
    "Teach Comprehension Check",
    "TEACH",
    "TEACH_CHECK",
}

# Singletons — agents are stateless, reuse them
_TUTOR       = TutorAgent()
_INTERVIEWER = InterviewerAgent()


def get_agent_for_state(fsm_state: str) -> BaseAgent:
    """
    Return the appropriate agent for the given FSM state value.

    Args:
        fsm_state: The State.value string, e.g. "Teach" or "Requirements Gathering"

    Returns:
        TutorAgent for teach-phase states, InterviewerAgent for all others.
    """
    if fsm_state in _TUTOR_STATES:
        return _TUTOR
    return _INTERVIEWER


def get_agent_type(fsm_state: str) -> AgentType:
    """Return the AgentType enum for a given FSM state."""
    if fsm_state in _TUTOR_STATES:
        return AgentType.TUTOR
    return AgentType.INTERVIEWER
