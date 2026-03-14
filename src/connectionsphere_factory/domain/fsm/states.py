"""
connectionsphere_factory/domain/fsm/states.py

Factory Session FSM — state definitions and valid transition table.

State flow (happy path — per-concept architecture):
  SESSION_START
    → CONCEPT_TEACH          (Alex teaches concept N)
    → CONCEPT_TEACH_CHECK    (Alex comprehension check)
    → CONCEPT_STAGE          (Jordan tests concept N)
    → CONCEPT_TEACH          (advance to concept N+1)
    → ... (repeat for all selected concepts)
    → EVALUATE
    → SESSION_COMPLETE

Legacy states (TEACH, TEACH_CHECK, REQUIREMENTS, SYSTEM_DESIGN,
NODE_SESSION, OOD_STAGE) are retained for backward compatibility with
sessions created under the old schema. New sessions use CONCEPT_* only.
"""

from enum import Enum


class State(Enum):
    # ── Lifecycle ────────────────────────────────────────────────────────
    SESSION_START    = "Session Start"
    SESSION_COMPLETE = "Session Complete"
    SESSION_ERROR    = "Session Error"
    RESTART          = "Restart"

    # ── Per-concept teach phase ───────────────────────────────────────────
    CONCEPT_TEACH       = "Concept Teach"         # Alex teaches concept N
    CONCEPT_TEACH_CHECK = "Concept Teach Check"   # Alex comprehension check

    # ── Per-concept simulate phase ────────────────────────────────────────
    CONCEPT_STAGE       = "Concept Stage"         # Jordan tests concept N

    # ── Evaluate phase ───────────────────────────────────────────────────
    EVALUATE         = "Evaluate"

    # ── Control ──────────────────────────────────────────────────────────
    FLAGGED          = "Flagged"

    # ── Legacy states (old schema — do not use for new sessions) ─────────
    TEACH            = "Teach"                    # legacy
    TEACH_CHECK      = "Teach Comprehension Check"  # legacy
    REQUIREMENTS     = "Requirements Gathering"   # legacy
    SYSTEM_DESIGN    = "System Design"            # legacy
    NODE_SESSION     = "Node Session"             # legacy
    OOD_STAGE        = "OOD Stage"                # legacy

    # ── Properties ───────────────────────────────────────────────────────

    @property
    def is_terminal(self) -> bool:
        return self in {State.SESSION_COMPLETE, State.SESSION_ERROR}

    @property
    def is_teach_phase(self) -> bool:
        return self in {
            State.CONCEPT_TEACH,
            State.CONCEPT_TEACH_CHECK,
            # legacy
            State.TEACH,
            State.TEACH_CHECK,
        }

    @property
    def is_simulate_phase(self) -> bool:
        return self in {
            State.CONCEPT_STAGE,
            # legacy
            State.REQUIREMENTS,
            State.SYSTEM_DESIGN,
            State.NODE_SESSION,
            State.OOD_STAGE,
        }

    @property
    def is_concept_phase(self) -> bool:
        """True for new per-concept states only (not legacy)."""
        return self in {
            State.CONCEPT_TEACH,
            State.CONCEPT_TEACH_CHECK,
            State.CONCEPT_STAGE,
        }

    @property
    def requires_voice(self) -> bool:
        return self in {
            State.CONCEPT_STAGE,
            State.CONCEPT_TEACH,
            State.CONCEPT_TEACH_CHECK,
            State.EVALUATE,
            # legacy
            State.REQUIREMENTS,
            State.OOD_STAGE,
        }

    @property
    def phase(self) -> str:
        if self in {State.CONCEPT_TEACH, State.CONCEPT_TEACH_CHECK, State.TEACH, State.TEACH_CHECK}:
            return "teach"
        if self in {State.CONCEPT_STAGE, State.REQUIREMENTS, State.SYSTEM_DESIGN,
                    State.NODE_SESSION, State.OOD_STAGE}:
            return "simulate"
        if self == State.EVALUATE:
            return "evaluate"
        return "lifecycle"

    @property
    def agent(self) -> str:
        """Which agent owns this state."""
        if self.is_teach_phase:
            return "alex"
        if self in {State.CONCEPT_STAGE, State.REQUIREMENTS, State.SYSTEM_DESIGN,
                    State.NODE_SESSION, State.OOD_STAGE, State.EVALUATE}:
            return "jordan"
        return "system"

    @property
    def description(self) -> str:
        return _STATE_DESCRIPTIONS.get(self, self.value)

    def __str__(self) -> str:
        return self.value

    def __repr__(self) -> str:
        return f"<State.{self.name}: {self.value!r}>"


_STATE_DESCRIPTIONS: dict[State, str] = {
    State.SESSION_START:        "Session initialising.",
    State.CONCEPT_TEACH:        "Alex is teaching concept N — explanation, analogy, example.",
    State.CONCEPT_TEACH_CHECK:  "Alex is running the comprehension check for concept N.",
    State.CONCEPT_STAGE:        "Jordan is testing concept N — opening question + probes.",
    State.EVALUATE:             "Jordan delivers the full session debrief.",
    State.FLAGGED:              "Probe limit reached — concept flagged, advancing.",
    State.SESSION_COMPLETE:     "Session complete.",
    State.SESSION_ERROR:        "Unrecoverable error.",
    State.RESTART:              "Session restarting.",
    # legacy
    State.TEACH:            "Legacy: monolithic teach phase.",
    State.TEACH_CHECK:      "Legacy: monolithic teach comprehension check.",
    State.REQUIREMENTS:     "Legacy: requirements gathering.",
    State.SYSTEM_DESIGN:    "Legacy: system design.",
    State.NODE_SESSION:     "Legacy: node session.",
    State.OOD_STAGE:        "Legacy: OOD stage.",
}


# ── Transition table ──────────────────────────────────────────────────────────

VALID_TRANSITIONS: dict[State, set[State]] = {

    State.SESSION_START: {State.CONCEPT_TEACH},

    # Per-concept teach loop
    State.CONCEPT_TEACH: {
        State.CONCEPT_TEACH_CHECK,
        State.CONCEPT_STAGE,  # allow skip via Ready for Interview button
    },
    State.CONCEPT_TEACH_CHECK: {
        State.CONCEPT_STAGE,    # comprehension confirmed → hand to Jordan
        State.CONCEPT_TEACH,    # comprehension partial → reteach
    },

    # Per-concept simulate
    State.CONCEPT_STAGE: {
        State.CONCEPT_TEACH,    # concept confirmed → advance to next concept (Alex teaches it)
        State.CONCEPT_STAGE,    # probe → same concept
        State.FLAGGED,          # probe limit reached
        State.EVALUATE,         # all concepts done
    },

    State.FLAGGED: {
        State.CONCEPT_TEACH,    # skip to next concept
        State.EVALUATE,         # final concept was flagged
    },

    State.EVALUATE: {State.SESSION_COMPLETE, State.SESSION_START},

    State.SESSION_COMPLETE: set(),
    State.SESSION_ERROR:    set(),
    State.RESTART:          {State.SESSION_START},

    # ── Legacy transitions (preserved for old sessions) ───────────────────
    State.TEACH:       {State.TEACH_CHECK},
    State.TEACH_CHECK: {State.REQUIREMENTS, State.TEACH},
    State.REQUIREMENTS:  {State.REQUIREMENTS, State.SYSTEM_DESIGN},
    State.SYSTEM_DESIGN: {State.NODE_SESSION, State.REQUIREMENTS},
    State.NODE_SESSION: {State.OOD_STAGE, State.NODE_SESSION, State.EVALUATE},
    State.OOD_STAGE:    {State.OOD_STAGE, State.NODE_SESSION, State.FLAGGED},
}


def _add_universal_transitions() -> None:
    """Add RESTART and SESSION_ERROR as valid from any non-terminal state."""
    for state, targets in VALID_TRANSITIONS.items():
        if not state.is_terminal and state not in {State.RESTART, State.SESSION_ERROR}:
            targets.add(State.RESTART)
            targets.add(State.SESSION_ERROR)


_add_universal_transitions()