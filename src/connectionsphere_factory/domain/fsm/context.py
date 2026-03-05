"""
connectionsphere_factory/domain/fsm/context.py

FSM context — metadata carried through the factory session.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class Transition:
    from_state: str
    to_state:   str
    timestamp:  str
    trigger:    str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "from_state": self.from_state,
            "to_state":   self.to_state,
            "timestamp":  self.timestamp,
            "trigger":    self.trigger,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Transition:
        return cls(
            from_state = data.get("from_state", ""),
            to_state   = data.get("to_state",   ""),
            timestamp  = data.get("timestamp",  ""),
            trigger    = data.get("trigger"),
        )


@dataclass
class FSMContext:
    # ── Candidate ────────────────────────────────────────────────────────
    candidate_name:  str = ""
    candidate_id:    str = ""
    candidate_level: str = ""

    # ── Problem ──────────────────────────────────────────────────────────
    problem_statement: str = ""
    problem_id:        str = ""

    # ── Session progress ─────────────────────────────────────────────────
    current_phase:        str = "lifecycle"
    current_node_id:      str = ""
    current_node_label:   str = ""
    current_stage_number: int = 0

    nodes_total:      int = 0
    nodes_confirmed:  int = 0
    labels_total:     int = 0
    labels_confirmed: int = 0

    # ── Gate counters ────────────────────────────────────────────────────
    probe_rounds:         int = 0
    teach_check_attempts: int = 0
    requirements_turns:   int = 0

    # ── Flags ────────────────────────────────────────────────────────────
    flagged:       bool = False
    flag_reason:   str  = ""
    flag_label_id: str  = ""

    # ── Teach phase ──────────────────────────────────────────────────────
    lesson_id:        str  = ""
    lesson_confirmed: bool = False

    # ── Timestamps ───────────────────────────────────────────────────────
    session_started_at:  str = field(default_factory=lambda: datetime.now().isoformat())
    teach_completed_at:  str = ""
    simulate_started_at: str = ""
    evaluate_started_at: str = ""

    # ── Debug ────────────────────────────────────────────────────────────
    function_path: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "candidate_name":       self.candidate_name,
            "candidate_id":         self.candidate_id,
            "candidate_level":      self.candidate_level,
            "problem_statement":    self.problem_statement,
            "problem_id":           self.problem_id,
            "current_phase":        self.current_phase,
            "current_node_id":      self.current_node_id,
            "current_node_label":   self.current_node_label,
            "current_stage_number": self.current_stage_number,
            "nodes_total":          self.nodes_total,
            "nodes_confirmed":      self.nodes_confirmed,
            "labels_total":         self.labels_total,
            "labels_confirmed":     self.labels_confirmed,
            "probe_rounds":         self.probe_rounds,
            "teach_check_attempts": self.teach_check_attempts,
            "requirements_turns":   self.requirements_turns,
            "flagged":              self.flagged,
            "flag_reason":          self.flag_reason,
            "flag_label_id":        self.flag_label_id,
            "lesson_id":            self.lesson_id,
            "lesson_confirmed":     self.lesson_confirmed,
            "session_started_at":   self.session_started_at,
            "teach_completed_at":   self.teach_completed_at,
            "simulate_started_at":  self.simulate_started_at,
            "evaluate_started_at":  self.evaluate_started_at,
            "function_path":        self.function_path,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> FSMContext:
        ctx = cls()
        for field_name in ctx.to_dict():
            if field_name in data:
                setattr(ctx, field_name, data[field_name])
        return ctx

    # ── Mutators ─────────────────────────────────────────────────────────

    def advance_to_node(self, node_id: str, labels_total: int) -> None:
        self.current_node_id  = node_id
        self.labels_total     = labels_total
        self.labels_confirmed = 0
        self.probe_rounds     = 0

    def confirm_label(self, label_id: str) -> None:
        self.labels_confirmed  += 1
        self.probe_rounds       = 0
        self.current_node_label = ""

    def confirm_node(self) -> None:
        self.nodes_confirmed  += 1
        self.current_node_id   = ""
        self.labels_total      = 0
        self.labels_confirmed  = 0

    def raise_flag(self, reason: str, label_id: str) -> None:
        self.flagged       = True
        self.flag_reason   = reason
        self.flag_label_id = label_id

    def clear_flag(self) -> None:
        self.flagged       = False
        self.flag_reason   = ""
        self.flag_label_id = ""

    @property
    def all_nodes_confirmed(self) -> bool:
        return self.nodes_total > 0 and self.nodes_confirmed >= self.nodes_total

    @property
    def all_labels_confirmed(self) -> bool:
        return self.labels_total > 0 and self.labels_confirmed >= self.labels_total

    @property
    def progress_summary(self) -> str:
        return (
            f"Nodes: {self.nodes_confirmed}/{self.nodes_total} confirmed. "
            f"Current node: {self.current_node_id or 'none'}. "
            f"Labels: {self.labels_confirmed}/{self.labels_total}. "
            f"Probe rounds: {self.probe_rounds}."
        )
