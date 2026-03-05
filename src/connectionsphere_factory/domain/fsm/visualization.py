"""
connectionsphere_factory/domain/fsm/visualization.py

Graphviz visualisation of the Factory FSM.
Served at GET /session/{session_id}/fsm-visualize
"""

from __future__ import annotations

import graphviz

from connectionsphere_factory.domain.fsm.machine import FactoryFSM
from connectionsphere_factory.domain.fsm.states import VALID_TRANSITIONS, State

_PHASE_COLORS: dict[str, str] = {
    "lifecycle": "#E8E8E8",
    "teach":     "#DBEAFE",
    "simulate":  "#FEF3C7",
    "evaluate":  "#D1FAE5",
}

_CONTROL_COLOR  = "#FEE2E2"
_TERMINAL_COLOR = "#F3F4F6"
_CURRENT_COLOR  = "#6366F1"
_CURRENT_FONT   = "#FFFFFF"


def _node_fill(state: State, is_current: bool) -> str:
    if is_current:
        return _CURRENT_COLOR
    if state.is_terminal:
        return _TERMINAL_COLOR
    if state == State.FLAGGED:
        return _CONTROL_COLOR
    return _PHASE_COLORS.get(state.phase, "#FFFFFF")


def _node_font_color(is_current: bool) -> str:
    return _CURRENT_FONT if is_current else "#111827"


class FSMVisualizer:
    """Renders FactoryFSM as a Graphviz Digraph for Scalar display."""

    def __init__(self, fsm: FactoryFSM) -> None:
        self.fsm = fsm

    def visualize(self) -> graphviz.Digraph:
        dot = graphviz.Digraph(name="FactoryFSM", comment="Factory Session State Machine")
        dot.attr(
            rankdir  = "TB",
            label    = (
                f"Factory Session FSM\n"
                f"Candidate: {self.fsm.context.candidate_name or 'unknown'}  |  "
                f"State: {self.fsm.state.value}  |  "
                f"Phase: {self.fsm.phase}"
            ),
            labelloc = "t",
            fontsize = "13",
            fontname = "Helvetica",
            bgcolor  = "#FAFAFA",
        )
        dot.attr("node", fontname="Helvetica", fontsize="11", style="filled")
        dot.attr("edge", fontname="Helvetica", fontsize="9",  color="#6B7280")

        valid_next = self.fsm.get_valid_transitions()

        for state in State:
            is_current = (state == self.fsm.state)
            is_next    = (state in valid_next)

            label = state.value
            if is_current:
                label = f"*  {state.value}"
            elif is_next:
                label = f"-> {state.value}"

            dot.node(
                state.name,
                label     = label,
                fillcolor = _node_fill(state, is_current),
                fontcolor = _node_font_color(is_current),
                penwidth  = "3" if is_current else ("2" if is_next else "1"),
                color     = _CURRENT_COLOR if is_current else ("#10B981" if is_next else "#9CA3AF"),
            )

        seen_edges: set[tuple[str, str]] = set()
        for from_state, targets in VALID_TRANSITIONS.items():
            for to_state in targets:
                edge_key = (from_state.name, to_state.name)
                if edge_key in seen_edges:
                    continue
                seen_edges.add(edge_key)
                is_active = (from_state == self.fsm.state and to_state in valid_next)
                dot.edge(
                    from_state.name,
                    to_state.name,
                    color    = "#6366F1" if is_active else "#D1D5DB",
                    penwidth = "2"       if is_active else "1",
                )

        with dot.subgraph(name="cluster_legend") as legend:
            legend.attr(label="Legend", style="dashed", color="#D1D5DB", fontsize="10")
            for phase, color in _PHASE_COLORS.items():
                legend.node(
                    f"legend_{phase}",
                    label=phase.capitalize(), fillcolor=color,
                    fontcolor="#374151", penwidth="1", color="#9CA3AF", shape="box",
                )
            legend.node(
                "legend_current", label="Current state",
                fillcolor=_CURRENT_COLOR, fontcolor=_CURRENT_FONT,
                penwidth="1", color=_CURRENT_COLOR, shape="box",
            )
            legend.node(
                "legend_flagged", label="Flagged",
                fillcolor=_CONTROL_COLOR, fontcolor="#374151",
                penwidth="1", color="#9CA3AF", shape="box",
            )

        return dot
