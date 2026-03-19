"""
competitive_programming_factory/models/schemas.py

Pydantic request/response models.
Field length limits are the first line of defence against token amplification.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class CandidateLevel(str, Enum):
    JUNIOR    = "junior"
    SENIOR    = "senior"
    STAFF     = "staff"
    PRINCIPAL = "principal"


class CreateSessionRequest(BaseModel):
    problem_statement: str = Field(
        default    = "First Step to Mathematical Olympiad Problems — Chapter 1",
        min_length = 10,
        max_length = 500,
        examples   = ["First Step to Mathematical Olympiad Problems — Chapter 1"],
    )
    candidate_name:  str           = Field(default="Candidate", max_length=100)
    candidate_level: CandidateLevel = CandidateLevel.SENIOR


class SubmitStageRequest(BaseModel):
    field_id: str = Field(..., max_length=64)
    answer:   str = Field(..., min_length=10, max_length=8000)
    stage_n:  int = Field(..., ge=1, le=20)


class SessionResponse(BaseModel):
    session_id:        str
    candidate_name:    str
    problem_statement: str
    fsm_state:         str
    phase:             str
    stage_url:         str


class StateResponse(BaseModel):
    session_id:          str
    fsm_state:           str
    phase:               str
    turns_in_state:      int
    probe_rounds:        int
    probe_limit_reached: bool
    requires_voice: bool
    agent_name:     str = ""
    agent_role:     str = ""
    valid_transitions:   list[str]
    current_node:        str
    current_label:       str
    progress:            str


class AssessmentResponse(BaseModel):
    verdict:               str
    feedback:              str
    probe:                 str | None
    concepts_demonstrated: list[str]
    concepts_missing:      list[str]
    next_url:              str | None
    session_complete:      bool = False
    # Diagram fields — set by process_submission when Jordan requests / evaluates a drawing
    diagram_request:  dict | None = None   # Jordan's diagram_request payload (nullable)
    diagram_scores:   list[dict]  = Field(default_factory=list)  # rubric scores from evaluator
