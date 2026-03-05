"""
connectionsphere_factory/domain/fsm/states.py

Factory Session FSM — state definitions and valid transition table.

State flow (happy path):
  SESSION_START
    → TEACH
    → TEACH_CHECK
    → REQUIREMENTS
    → SYSTEM_DESIGN
    → NODE_SESSION
      → OOD_STAGE        (repeats per label)
      → NODE_SESSION     (repeats per node)
    → EVALUATE
    → SESSION_COMPLETE
"""

from enum import Enum


class State(Enum):
    # ── Lifecycle ────────────────────────────────────────────────────────
    SESSION_START    = "Session Start"
    SESSION_COMPLETE = "Session Complete"
    SESSION_ERROR    = "Session Error"
    RESTART          = "Restart"

    # ── Teach phase ──────────────────────────────────────────────────────
    TEACH            = "Teach"
    TEACH_CHECK      = "Teach Comprehension Check"

    # ── Simulate phase — system layer ────────────────────────────────────
    REQUIREMENTS     = "Requirements Gathering"
    SYSTEM_DESIGN    = "System Design"

    # ── Simulate phase — node layer ──────────────────────────────────────
    NODE_SESSION     = "Node Session"
    OOD_STAGE        = "OOD Stage"

    # ── Evaluate phase ───────────────────────────────────────────────────
    EVALUATE         = "Evaluate"

    # ── Control ──────────────────────────────────────────────────────────
    FLAGGED          = "Flagged"

    @property
    def is_terminal(self) -> bool:
        return self in {State.SESSION_COMPLETE, State.SESSION_ERROR}

    @property
    def is_simulate_phase(self) -> bool:
        return self in {
            State.REQUIREMENTS,
            State.SYSTEM_DESIGN,
            State.NODE_SESSION,
            State.OOD_STAGE,
        }

    @property
    def is_teach_phase(self) -> bool:
        return self in {State.TEACH, State.TEACH_CHECK}

    @property
    def requires_voice(self) -> bool:
        return self in {State.REQUIREMENTS, State.OOD_STAGE, State.EVALUATE}

    @property
    def phase(self) -> str:
        if self.is_teach_phase:
            return "teach"
        if self.is_simulate_phase:
            return "simulate"
        if self == State.EVALUATE:
            return "evaluate"
        return "lifecycle"

    @property
    def description(self) -> str:
        return _STATE_DESCRIPTIONS.get(self, self.value)

    def __str__(self) -> str:
        return self.value

    def __repr__(self) -> str:
        return f"<State.{self.name}: {self.value!r}>"


_STATE_DESCRIPTIONS: dict[State, str] = {
    State.SESSION_START:    "The session is initialising — greet the candidate and confirm the problem statement.",
    State.TEACH:            "Deliver the lesson for the upcoming simulation — teach the concepts the candidate will need.",
    State.TEACH_CHECK:      "Run the light comprehension gate — verify the lesson landed before advancing to simulation.",
    State.REQUIREMENTS:     "Gather requirements — the candidate is asking clarifying questions about the problem scope.",
    State.SYSTEM_DESIGN:    "The candidate is proposing the system topology — assess their boundary decisions.",
    State.NODE_SESSION:     "A node has been selected — introduce the node and transition to OOD stage.",
    State.OOD_STAGE:        "Running an OOD label stage — assess the candidate's understanding of this pattern.",
    State.EVALUATE:         "Deliver the debrief — verdict, specific strengths and gaps, next lesson.",
    State.FLAGGED:          "Probe limit reached — flag for human review before this stage can advance.",
    State.SESSION_COMPLETE: "Session is complete — no further interaction required.",
    State.SESSION_ERROR:    "An unrecoverable error occurred — surface it clearly to the candidate.",
    State.RESTART:          "The session is restarting — greet the candidate and confirm you are beginning again.",
}


VALID_TRANSITIONS: dict[State, set[State]] = {

    State.SESSION_START: {State.TEACH},

    State.TEACH:       {State.TEACH_CHECK},
    State.TEACH_CHECK: {State.REQUIREMENTS, State.TEACH},

    State.REQUIREMENTS:  {State.REQUIREMENTS, State.SYSTEM_DESIGN},
    State.SYSTEM_DESIGN: {State.NODE_SESSION, State.REQUIREMENTS},

    State.NODE_SESSION: {State.OOD_STAGE, State.NODE_SESSION, State.EVALUATE},
    State.OOD_STAGE:    {State.OOD_STAGE, State.NODE_SESSION, State.FLAGGED},

    State.FLAGGED: {State.OOD_STAGE, State.NODE_SESSION, State.EVALUATE},

    State.EVALUATE: {State.SESSION_COMPLETE, State.SESSION_START},

    State.SESSION_COMPLETE: set(),
    State.SESSION_ERROR:    set(),
    State.RESTART:          {State.SESSION_START},
}


def _add_universal_transitions() -> None:
    for state, targets in VALID_TRANSITIONS.items():
        if not state.is_terminal and state not in {State.RESTART, State.SESSION_ERROR}:
            targets.add(State.RESTART)
            targets.add(State.SESSION_ERROR)


_add_universal_transitions()
