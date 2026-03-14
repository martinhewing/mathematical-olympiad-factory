"""
connectionsphere_factory/domain/fsm/context.py

FSM context — metadata carried through the factory session.

New in per-concept architecture:
  concept_ids        — ordered list of concept IDs for this session (set at creation)
  concept_index      — 0-based index of the current concept
  concepts_confirmed — concept IDs Jordan confirmed
  concepts_flagged   — concept IDs that hit the probe limit
  reteach_count      — how many times Alex has retaught the current concept

All new fields serialise/deserialise cleanly alongside existing fields.
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

    # ── Legacy session progress (old schema) ─────────────────────────────
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

    # ── Teach phase (legacy) ─────────────────────────────────────────────
    lesson_id:        str  = ""
    lesson_confirmed: bool = False

    # ── Timestamps ───────────────────────────────────────────────────────
    session_started_at:  str = field(default_factory=lambda: datetime.now().isoformat())
    teach_completed_at:  str = ""
    simulate_started_at: str = ""
    evaluate_started_at: str = ""

    # ── Debug ────────────────────────────────────────────────────────────
    function_path: list[str] = field(default_factory=list)

    # ── Per-concept tracking (new architecture) ───────────────────────────
    # Set at session creation from select_concepts_for_problem()
    concept_ids: list[str] = field(default_factory=list)

    # 0-based index into concept_ids — points at the concept currently being
    # taught (Alex) or tested (Jordan)
    concept_index: int = 0

    # concept_ids that Jordan has confirmed
    concepts_confirmed: list[str] = field(default_factory=list)

    # concept_ids that hit the probe limit and were flagged
    concepts_flagged: list[str] = field(default_factory=list)

    # How many times Alex has retaught the current concept in this reteach loop
    reteach_count: int = 0

    # ── Per-concept properties ────────────────────────────────────────────

    @property
    def current_concept_id(self) -> str | None:
        """The concept_id currently being taught or tested. None if all done."""
        if self.concept_index < len(self.concept_ids):
            return self.concept_ids[self.concept_index]
        return None

    @property
    def all_concepts_done(self) -> bool:
        """True when concept_index has advanced past the last concept."""
        return self.concept_index >= len(self.concept_ids)

    @property
    def concepts_total(self) -> int:
        return len(self.concept_ids)

    @property
    def concepts_pending(self) -> list[str]:
        """concept_ids not yet started."""
        done = set(self.concepts_confirmed) | set(self.concepts_flagged)
        current = self.current_concept_id
        pending = []
        for cid in self.concept_ids:
            if cid not in done and cid != current:
                pending.append(cid)
        return pending

    # ── Per-concept mutators ──────────────────────────────────────────────

    def advance_concept(self) -> None:
        """
        Advance to the next concept. Resets probe_rounds and reteach_count.
        Call after Jordan confirms OR flags a concept.
        """
        self.concept_index  += 1
        self.probe_rounds    = 0
        self.reteach_count   = 0

    def confirm_current_concept(self) -> None:
        """Mark the current concept as confirmed by Jordan."""
        cid = self.current_concept_id
        if cid and cid not in self.concepts_confirmed:
            self.concepts_confirmed.append(cid)

    def flag_current_concept(self, reason: str = "") -> None:
        """Mark the current concept as flagged (probe limit reached)."""
        cid = self.current_concept_id
        if cid and cid not in self.concepts_flagged:
            self.concepts_flagged.append(cid)
        # Also set the legacy flag fields for backward compat
        self.flagged       = True
        self.flag_reason   = reason or f"Probe limit reached on {cid}"
        self.flag_label_id = cid or ""

    def increment_reteach(self) -> None:
        """Called each time Alex reteaches the current concept."""
        self.reteach_count += 1

    def clear_flag(self) -> None:
        self.flagged       = False
        self.flag_reason   = ""
        self.flag_label_id = ""

    # ── Legacy mutators (old schema — preserved for backward compat) ──────

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

    def raise_flag(self, reason: str, label_id: str = "") -> None:
        self.flagged       = True
        self.flag_reason   = reason
        self.flag_label_id = label_id

    # ── Progress summaries ────────────────────────────────────────────────

    @property
    def progress_summary(self) -> str:
        """Human-readable summary for Claude prompts."""
        if self.concept_ids:
            # New per-concept architecture
            current = self.current_concept_id or "complete"
            return (
                f"Concept {self.concept_index + 1}/{self.concepts_total}: {current}. "
                f"Confirmed: {', '.join(self.concepts_confirmed) or 'none'}. "
                f"Flagged: {', '.join(self.concepts_flagged) or 'none'}."
            )
        # Legacy
        return (
            f"Nodes: {self.nodes_confirmed}/{self.nodes_total} confirmed. "
            f"Current node: {self.current_node_id or 'none'}. "
            f"Labels: {self.labels_confirmed}/{self.labels_total}. "
            f"Probe rounds: {self.probe_rounds}."
        )

    @property
    def all_nodes_confirmed(self) -> bool:
        return self.nodes_total > 0 and self.nodes_confirmed >= self.nodes_total

    @property
    def all_labels_confirmed(self) -> bool:
        return self.labels_total > 0 and self.labels_confirmed >= self.labels_total

    # ── Serialisation ─────────────────────────────────────────────────────

    def to_dict(self) -> dict[str, Any]:
        return {
            # Candidate
            "candidate_name":       self.candidate_name,
            "candidate_id":         self.candidate_id,
            "candidate_level":      self.candidate_level,
            # Problem
            "problem_statement":    self.problem_statement,
            "problem_id":           self.problem_id,
            # Legacy progress
            "current_phase":        self.current_phase,
            "current_node_id":      self.current_node_id,
            "current_node_label":   self.current_node_label,
            "current_stage_number": self.current_stage_number,
            "nodes_total":          self.nodes_total,
            "nodes_confirmed":      self.nodes_confirmed,
            "labels_total":         self.labels_total,
            "labels_confirmed":     self.labels_confirmed,
            # Gate counters
            "probe_rounds":         self.probe_rounds,
            "teach_check_attempts": self.teach_check_attempts,
            "requirements_turns":   self.requirements_turns,
            # Flags
            "flagged":              self.flagged,
            "flag_reason":          self.flag_reason,
            "flag_label_id":        self.flag_label_id,
            # Legacy teach
            "lesson_id":            self.lesson_id,
            "lesson_confirmed":     self.lesson_confirmed,
            # Timestamps
            "session_started_at":   self.session_started_at,
            "teach_completed_at":   self.teach_completed_at,
            "simulate_started_at":  self.simulate_started_at,
            "evaluate_started_at":  self.evaluate_started_at,
            # Debug
            "function_path":        self.function_path,
            # Per-concept (new)
            "concept_ids":          self.concept_ids,
            "concept_index":        self.concept_index,
            "concepts_confirmed":   self.concepts_confirmed,
            "concepts_flagged":     self.concepts_flagged,
            "reteach_count":        self.reteach_count,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> FSMContext:
        ctx = cls()
        for field_name in ctx.to_dict():
            if field_name in data:
                setattr(ctx, field_name, data[field_name])
        return ctx