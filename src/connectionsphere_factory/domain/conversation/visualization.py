"""
connectionsphere_factory/domain/conversation/visualization.py

Graphviz visualisation of the factory session conversation history (DLL).
Served at GET /session/{session_id}/dll-visualize
"""

from __future__ import annotations

import graphviz

from connectionsphere_factory.domain.conversation.history import (
    FactoryConversationHistory,
    FactoryNode,
)

_TYPE_COLORS: dict[str, str] = {
    "teach":         "#DBEAFE",
    "teach_check":   "#EDE9FE",
    "requirements":  "#F3E8FF",
    "system_design": "#FEF3C7",
    "node_session":  "#FFEDD5",
    "ood_stage":     "#CCFBF1",
    "evaluate":      "#D1FAE5",
    "flagged":       "#FEE2E2",
}

_CURRENT_FILL = "#6366F1"
_CURRENT_FONT = "#FFFFFF"
_DEFAULT_FILL = "#F9FAFB"


class DLLVisualizer:
    """Renders FactoryConversationHistory as a left-to-right Graphviz diagram."""

    def __init__(self, history: FactoryConversationHistory) -> None:
        self.history = history

    def visualize(self) -> graphviz.Digraph:
        dot = graphviz.Digraph(name="FactoryDLL", comment="Factory Session Conversation History")
        dot.attr(
            rankdir  = "LR",
            label    = "Session Conversation History (DLL)  ·  <- older | newer ->",
            labelloc = "t",
            fontsize = "13",
            fontname = "Helvetica",
            bgcolor  = "#FAFAFA",
        )
        dot.attr("node", fontname="Helvetica", fontsize="10", style="filled", shape="box")
        dot.attr("edge", fontname="Helvetica", fontsize="8")

        if self.history.size == 0:
            dot.node(
                "empty", "No stages yet\n(session not started)",
                fillcolor=_DEFAULT_FILL, color="#D1D5DB", style="filled,dashed",
            )
            return dot

        for node in self.history.iterate_oldest_first():
            dot.node(node.stage_id, label=self._label(node), **self._style(node))

        for node in self.history.iterate_oldest_first():
            if node.next:
                dot.edge(node.stage_id, node.next.stage_id,
                         label="next", color="#374151", fontsize="8")
                dot.edge(node.next.stage_id, node.stage_id,
                         label="prev", color="#9CA3AF", fontsize="8", style="dashed")

        self._add_legend(dot)
        return dot

    def _label(self, node: FactoryNode) -> str:
        is_current = (node == self.history.current)
        is_head    = (node == self.history.head)
        is_tail    = (node == self.history.tail)

        lines = []
        if is_current:
            lines.append("> CURRENT")
        if node.status == "confirmed":
            lines.append("+ CONFIRMED")
        elif node.status == "flagged":
            lines.append("! FLAGGED")

        lines.append(node.stage_id)
        lines.append(f"[{node.stage_type.upper()}]")

        if node.label_id:
            lines.append(f"Label: {node.label_id}")
        if node.node_id:
            lines.append(f"Node: {node.node_id}")

        lines.append(f"Turns: {node.turn_count}")

        if is_head and is_tail:
            lines.append("(HEAD / TAIL)")
        elif is_head:
            lines.append("(HEAD - newest)")
        elif is_tail:
            lines.append("(TAIL - oldest)")

        return "\\n".join(lines)

    def _style(self, node: FactoryNode) -> dict:
        if node == self.history.current:
            return {
                "fillcolor": _CURRENT_FILL,
                "fontcolor": _CURRENT_FONT,
                "penwidth":  "3",
                "color":     _CURRENT_FILL,
            }
        return {
            "fillcolor": _TYPE_COLORS.get(node.stage_type, _DEFAULT_FILL),
            "fontcolor": "#111827",
            "penwidth":  "2" if node.status == "confirmed" else "1",
            "color":     "#EF4444" if node.status == "flagged" else "#D1D5DB",
        }

    def _add_legend(self, dot: graphviz.Digraph) -> None:
        with dot.subgraph(name="cluster_legend") as legend:
            legend.attr(label="Stage types", style="dashed", color="#D1D5DB", fontsize="10")
            for stage_type, color in _TYPE_COLORS.items():
                legend.node(
                    f"legend_{stage_type}",
                    label=stage_type.replace("_", " ").title(),
                    fillcolor=color, fontcolor="#374151",
                    penwidth="1", color="#9CA3AF",
                    shape="box", fontsize="9",
                )
