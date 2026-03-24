"""
competitive_programming_factory/domain/fsm/machine.py

Factory Session Finite State Machine.

mermaid() — renders FSM as Mermaid markup, piped into every Claude prompt.
probe_limit_reached — when True, session engine must transition to FLAGGED.

Per-concept architecture (new sessions):
  advance_concept() — moves to next concept, resets counters.
  CONCEPT_STAGE is the probe state; CONCEPT_TEACH/CHECK are Alex states.

Legacy architecture (old sessions) is preserved — OOD_STAGE probe logic
is unchanged and all legacy states/transitions remain valid.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from competitive_programming_factory.domain.fsm.context import FSMContext, Transition
from competitive_programming_factory.domain.fsm.states import VALID_TRANSITIONS, State


class FSMTransitionError(Exception):
    def __init__(self, from_state: str, to_state: str, valid_transitions: set[str]) -> None:
        self.from_state = from_state
        self.to_state = to_state
        self.valid_transitions = valid_transitions
        super().__init__(
            f"Invalid transition: {from_state!r} -> {to_state!r}. "
            f"Valid from here: {sorted(valid_transitions)}"
        )


PROBE_LIMIT = 10


class FactoryFSM:
    """
    Finite State Machine for the factory session.
    Enforces valid transitions and maintains a full audit trail.
    Serialised to JSONB after every transition.
    """

    def __init__(
        self,
        candidate_name: str = "",
        candidate_id: str = "",
        candidate_level: str = "senior",
        problem_statement: str = "",
        problem_id: str = "",
        initial_state: State = State.SESSION_START,
    ) -> None:
        self._state: State = initial_state
        self._context: FSMContext = FSMContext(
            candidate_name=candidate_name,
            candidate_id=candidate_id,
            candidate_level=candidate_level,
            problem_statement=problem_statement,
            problem_id=problem_id,
        )
        self._history: list[Transition] = []
        self._function_calls: list[dict[str, str]] = []
        self._turns_in_state: int = 0

    # ── Properties ───────────────────────────────────────────────────────

    @property
    def state(self) -> State:
        return self._state

    @state.setter
    def state(self, value: State) -> None:
        self._state = value

    @property
    def context(self) -> FSMContext:
        return self._context

    @context.setter
    def context(self, value: FSMContext) -> None:
        self._context = value

    @property
    def history(self) -> list[Transition]:
        return self._history

    @property
    def function_calls(self) -> list[dict[str, str]]:
        return self._function_calls

    @property
    def turns_in_current_state(self) -> int:
        return self._turns_in_state

    @property
    def phase(self) -> str:
        return self._state.phase

    @property
    def probe_limit_reached(self) -> bool:
        """
        True when the probe limit has been reached on the current concept.

        Covers both the new per-concept architecture (CONCEPT_STAGE) and
        the legacy architecture (OOD_STAGE).
        """
        return (
            self._state in {State.CONCEPT_STAGE, State.OOD_STAGE}
            and self._context.probe_rounds >= PROBE_LIMIT
        )

    @property
    def requires_voice(self) -> bool:
        return self._state.requires_voice

    @property
    def is_concept_session(self) -> bool:
        """True if this session uses the new per-concept architecture."""
        return bool(self._context.concept_ids)

    # ── Transitions ──────────────────────────────────────────────────────

    def transition_to(self, new_state: State, trigger: str | None = None) -> None:
        if not self.can_transition_to(new_state):
            raise FSMTransitionError(
                from_state=self._state.value,
                to_state=new_state.value,
                valid_transitions={s.value for s in self.get_valid_transitions()},
            )

        self._history.append(
            Transition(
                from_state=self._state.value,
                to_state=new_state.value,
                timestamp=datetime.now().isoformat(),
                trigger=trigger,
            )
        )

        now = datetime.now().isoformat()

        # ── Timestamp milestones ──────────────────────────────────────────
        # New architecture milestones
        if new_state == State.CONCEPT_STAGE and self._context.simulate_started_at == "":
            self._context.simulate_started_at = now
        if new_state == State.EVALUATE and self._context.evaluate_started_at == "":
            self._context.evaluate_started_at = now
        if (
            new_state == State.CONCEPT_TEACH_CHECK
            and self._state == State.CONCEPT_TEACH
            and self._context.teach_completed_at == ""
        ):
            self._context.teach_completed_at = now

        # Legacy architecture milestones (preserved)
        if new_state == State.REQUIREMENTS and self._context.simulate_started_at == "":
            self._context.simulate_started_at = now
        if new_state == State.TEACH_CHECK and self._context.teach_completed_at == "":
            self._context.teach_completed_at = now

        self._context.current_phase = new_state.phase
        self._state = new_state
        self._turns_in_state = 0

    def increment_turn(self) -> None:
        """
        Increment turn counter and probe rounds.

        For CONCEPT_STAGE (new): probe_rounds increments on each submission.
        For OOD_STAGE (legacy): same behaviour, preserved.
        For CONCEPT_TEACH_CHECK: teach_check_attempts increments.
        """
        self._turns_in_state += 1
        if self._state in {State.CONCEPT_STAGE, State.OOD_STAGE}:
            self._context.probe_rounds += 1
        elif self._state == State.CONCEPT_TEACH_CHECK:
            self._context.teach_check_attempts += 1

    def can_transition_to(self, new_state: State) -> bool:
        return new_state in VALID_TRANSITIONS.get(self._state, set())

    def get_valid_transitions(self) -> set[State]:
        return VALID_TRANSITIONS.get(self._state, set()).copy()

    # ── Per-concept helpers ───────────────────────────────────────────────

    def advance_concept(self) -> None:
        """
        Advance to the next concept in the curriculum.

        Delegates to context.advance_concept() which increments concept_index
        and resets probe_rounds and reteach_count.

        Call this from session_engine after Jordan CONFIRMS or FLAGS a concept,
        before transitioning to CONCEPT_TEACH for the next concept or EVALUATE.
        """
        self._context.advance_concept()

    def confirm_current_concept(self) -> None:
        """Mark the current concept as confirmed. Call before advance_concept()."""
        self._context.confirm_current_concept()

    def flag_current_concept(self, reason: str = "") -> None:
        """Mark the current concept as flagged. Call before advance_concept()."""
        self._context.flag_current_concept(reason)

    def increment_reteach(self) -> None:
        """Called each time Alex reteaches the current concept."""
        self._context.increment_reteach()

    @property
    def current_concept_id(self) -> str | None:
        """Convenience accessor for the current concept ID."""
        return self._context.current_concept_id

    @property
    def all_concepts_done(self) -> bool:
        """True when all concepts have been advanced past."""
        return self._context.all_concepts_done

    # ── Claude prompt context ─────────────────────────────────────────────

    def prompt_context(self) -> dict[str, Any]:
        ctx = {
            "current_state": self._state.value,
            "state_description": self._state.description,
            "phase": self.phase,
            "agent": self._state.agent,
            "turns_in_state": self._turns_in_state,
            "probe_rounds": self._context.probe_rounds,
            "probe_limit": PROBE_LIMIT,
            "probe_limit_reached": self.probe_limit_reached,
            "requires_voice": self.requires_voice,
            "valid_transitions": [s.value for s in self.get_valid_transitions()],
            "progress": self._context.progress_summary,
            "candidate_level": self._context.candidate_level,
            "problem_statement": self._context.problem_statement,
            "recent_history": [t.to_dict() for t in self._history[-5:]],
            "fsm_mermaid": self.mermaid(),
        }
        # Per-concept extras
        if self.is_concept_session:
            ctx["concept_id"] = self._context.current_concept_id
            ctx["concept_index"] = self._context.concept_index
            ctx["concepts_total"] = self._context.concepts_total
            ctx["concepts_confirmed"] = self._context.concepts_confirmed
            ctx["concepts_flagged"] = self._context.concepts_flagged
            ctx["reteach_count"] = self._context.reteach_count
        return ctx

    def mermaid(self) -> str:
        """
        Renders the current FSM position as Mermaid stateDiagram-v2.
        Current state marked ★, valid next states marked →.
        Legacy states omitted for new-architecture sessions to reduce noise.
        """
        valid_next = {s.name for s in self.get_valid_transitions()}
        legacy_names = {
            "TEACH",
            "TEACH_CHECK",
            "REQUIREMENTS",
            "SYSTEM_DESIGN",
            "NODE_SESSION",
            "OOD_STAGE",
        }

        lines = ["stateDiagram-v2"]

        for from_state, targets in VALID_TRANSITIONS.items():
            # Skip legacy states in concept sessions
            if self.is_concept_session and from_state.name in legacy_names:
                continue

            for to_state in targets:
                if self.is_concept_session and to_state.name in legacy_names:
                    continue

                from_label = from_state.name
                to_label = to_state.name

                if from_state == self._state:
                    from_label = f"{from_state.name} ★"
                if to_state == self._state:
                    to_label = f"{to_state.name} ★"
                if from_state == self._state and to_state.name in valid_next:
                    to_label = f"{to_state.name} →"

                lines.append(f"    {from_label} --> {to_label}")

        return "\n".join(lines)

    # ── Function call logging ─────────────────────────────────────────────

    def log_function_call(self, function_name: str) -> None:
        self._function_calls.append(
            {
                "function": function_name,
                "state": self._state.value,
                "timestamp": datetime.now().isoformat(),
            }
        )
        self._function_calls = self._function_calls[-5:]
        self._context.function_path = [fc["function"] for fc in self._function_calls]

    # ── Serialisation ─────────────────────────────────────────────────────

    def to_dict(self) -> dict[str, Any]:
        return {
            "state": self._state.value,
            "context": self._context.to_dict(),
            "history": [t.to_dict() for t in self._history],
            "function_calls": self._function_calls.copy(),
            "turns_in_state": self._turns_in_state,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> FactoryFSM:
        state_value = data.get("state", State.SESSION_START.value)
        state = next(
            (s for s in State if s.value == state_value),
            State.SESSION_START,
        )
        fsm = cls(initial_state=state)
        fsm._context = FSMContext.from_dict(data.get("context", {}))
        fsm._turns_in_state = data.get("turns_in_state", 0)
        for item in data.get("history", []):
            if isinstance(item, dict):
                fsm._history.append(Transition.from_dict(item))
        fsm._function_calls = data.get("function_calls", [])
        return fsm

    def get_current_state_info(self) -> dict[str, Any]:
        return {
            "current_state": self._state.value,
            "state_name": self._state.name,
            "phase": self.phase,
            "agent": self._state.agent,
            "is_terminal": self._state.is_terminal,
            "requires_voice": self.requires_voice,
            "description": self._state.description,
            "valid_transitions": [s.value for s in self.get_valid_transitions()],
            "turns_in_state": self._turns_in_state,
            "probe_rounds": self._context.probe_rounds,
            "probe_limit_reached": self.probe_limit_reached,
            "history_length": len(self._history),
            "recent_transitions": [t.to_dict() for t in self._history[-3:]],
            "context": self._context.to_dict(),
        }

    def __repr__(self) -> str:
        concept = (
            f", concept={self._context.current_concept_id!r}" if self.is_concept_session else ""
        )
        return (
            f"FactoryFSM("
            f"state={self._state.name!r}, "
            f"phase={self.phase!r}, "
            f"turns={self._turns_in_state}"
            f"{concept}"
            f")"
        )
