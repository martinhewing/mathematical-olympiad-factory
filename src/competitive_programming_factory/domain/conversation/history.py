"""
competitive_programming_factory/domain/conversation/history.py

Doubly Linked List for factory session conversation history.

Structure (oldest -> newest):
    tail <-> node <-> node <-> node <-> head
                                        ^ current

Each node = one stage (teach, requirements, ood_stage, evaluate, etc.)
with its full turn history, voice transcripts, and comprehension record.

context_window_build() selects what Claude sees each turn, respecting
the token budget — full current node, summary of previous, all
comprehension records for confirmed nodes.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import datetime
from typing import Any


class FactoryNode:
    """A single stage in the factory session conversation."""

    def __init__(self, stage_id: str, stage_type: str) -> None:
        self.stage_id   = stage_id
        self.stage_type = stage_type
        self.timestamp  = datetime.now()
        self.status     = "active"    # active | confirmed | flagged | skipped

        self.prev: FactoryNode | None = None
        self.next: FactoryNode | None = None

        self.turns:             list[dict[str, Any]] = []
        self.voice_transcripts: list[dict[str, Any]] = []
        self.silence_events:    list[dict[str, Any]] = []
        self.ink_patterns_used: list[str]            = []

        self.spec:                 dict | None = None
        self.assessments:          list[dict]  = []
        self.comprehension_record: dict | None = None
        self.summary:              str         = ""

        self.label_id:      str              = ""
        self.node_id:       str              = ""
        self.confirmed_at:  datetime | None  = None
        self.flagged_at:    datetime | None  = None

    # ── Turn management ───────────────────────────────────────────────────

    def add_turn(
        self,
        speaker:     str,
        content:     str,
        turn_type:   str = "",
        ink_pattern: str = "",
        **extra: Any,
    ) -> None:
        self.turns.append({
            "timestamp":   datetime.now().isoformat(),
            "speaker":     speaker,
            "content":     content,
            "turn_type":   turn_type,
            "ink_pattern": ink_pattern,
            **extra,
        })

    def add_voice_transcript(
        self,
        transcript:  str,
        audio_url:   str   = "",
        duration_ms: int   = 0,
        confidence:  float = 0.0,
    ) -> None:
        self.voice_transcripts.append({
            "timestamp":   datetime.now().isoformat(),
            "transcript":  transcript,
            "audio_url":   audio_url,
            "duration_ms": duration_ms,
            "confidence":  confidence,
        })
        self.add_turn("candidate", transcript, turn_type="voice", audio_url=audio_url)

    def add_silence_event(self, silence_type: str, duration_ms: int) -> None:
        self.silence_events.append({
            "timestamp":    datetime.now().isoformat(),
            "silence_type": silence_type,
            "duration_ms":  duration_ms,
        })

    def confirm(self, comprehension_record: dict | None = None) -> "FactoryNode":
        self.status               = "confirmed"
        self.confirmed_at         = datetime.now()
        self.comprehension_record = comprehension_record
        return self

    def flag(self, reason: str) -> None:
        self.status     = "flagged"
        self.flagged_at = datetime.now()
        self.add_turn("system", f"Stage flagged: {reason}", turn_type="system")

    @property
    def turn_count(self) -> int:
        return len(self.turns)

    @property
    def last_candidate_turn(self) -> str:
        for turn in reversed(self.turns):
            if turn["speaker"] == "candidate":
                return turn["content"]
        return ""

    @property
    def all_transcripts(self) -> str:
        return " ".join(vt["transcript"] for vt in self.voice_transcripts)

    # ── Serialisation ─────────────────────────────────────────────────────

    def to_dict(self) -> dict[str, Any]:
        return {
            "stage_id":             self.stage_id,
            "stage_type":           self.stage_type,
            "timestamp":            self.timestamp.isoformat(),
            "status":               self.status,
            "prev":                 self.prev.stage_id if self.prev else None,
            "next":                 self.next.stage_id if self.next else None,
            "turns":                self.turns,
            "voice_transcripts":    self.voice_transcripts,
            "silence_events":       self.silence_events,
            "ink_patterns_used":    self.ink_patterns_used,
            "spec":                 self.spec,
            "assessments":          self.assessments,
            "comprehension_record": self.comprehension_record,
            "summary":              self.summary,
            "label_id":             self.label_id,
            "node_id":              self.node_id,
            "confirmed_at":         self.confirmed_at.isoformat() if self.confirmed_at else None,
            "flagged_at":           self.flagged_at.isoformat()   if self.flagged_at   else None,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> FactoryNode:
        node = cls(stage_id=data["stage_id"], stage_type=data["stage_type"])
        node.status               = data.get("status", "active")
        node.turns                = data.get("turns", [])
        node.voice_transcripts    = data.get("voice_transcripts", [])
        node.silence_events       = data.get("silence_events", [])
        node.ink_patterns_used    = data.get("ink_patterns_used", [])
        node.spec                 = data.get("spec")
        node.assessments          = data.get("assessments", [])
        node.comprehension_record = data.get("comprehension_record")
        node.summary              = data.get("summary", "")
        node.label_id             = data.get("label_id", "")
        node.node_id              = data.get("node_id", "")

        ts = data.get("timestamp")
        if ts:
            node.timestamp = datetime.fromisoformat(ts)

        for field in ("confirmed_at", "flagged_at"):
            val = data.get(field)
            if val:
                setattr(node, field, datetime.fromisoformat(val))

        return node


class FactoryConversationHistory:
    """
    Doubly Linked List of FactoryNode instances.

    Head = newest. Tail = oldest. Current = active stage.

    Two purposes:
      1. Persistent audit trail — serialised to Postgres after every turn.
      2. Claude context source — context_window_build() selects what
         Claude sees on each turn, respecting the token budget.
    """

    def __init__(self) -> None:
        self.head:    FactoryNode | None = None
        self.tail:    FactoryNode | None = None
        self.current: FactoryNode | None = None
        self.size:    int = 0

    def add_stage(self, stage_id: str, stage_type: str) -> FactoryNode:
        node = FactoryNode(stage_id=stage_id, stage_type=stage_type)

        if self.head is None:
            self.head = node
            self.tail = node
        else:
            node.prev      = self.head
            self.head.next = node
            self.head      = node

        self.current = node
        self.size   += 1
        return node

    def find(self, stage_id: str) -> FactoryNode | None:
        for node in self.iterate_oldest_first():
            if node.stage_id == stage_id:
                return node
        return None

    def navigate_back(self) -> FactoryNode | None:
        if self.current and self.current.prev:
            self.current = self.current.prev
        return self.current

    def navigate_forward(self) -> FactoryNode | None:
        if self.current and self.current.next:
            self.current = self.current.next
        return self.current

    def navigate_to(self, stage_id: str) -> FactoryNode | None:
        node = self.find(stage_id)
        if node:
            self.current = node
        return node

    # ── Claude context window ─────────────────────────────────────────────

    def context_window_build(self, max_turns: int = 20) -> list[dict[str, Any]]:
        """
        Builds Claude's context from the DLL.

        Priority:
          1. Current node — full turn history
          2. Previous node — summary only (saves tokens)
          3. All comprehension records — always included
        """
        context: list[dict[str, Any]] = []

        if self.current:
            context.extend(self.current.turns[-max_turns:])

        if self.current and self.current.prev and self.current.prev.summary:
            context.insert(0, {
                "speaker":   "system",
                "content":   (
                    f"[Previous stage: {self.current.prev.stage_type} "
                    f"({self.current.prev.stage_id})] "
                    f"{self.current.prev.summary}"
                ),
                "turn_type": "system",
            })

        for node in self.iterate_oldest_first():
            if node.comprehension_record and node != self.current:
                rec = node.comprehension_record
                context.insert(0, {
                    "speaker":   "system",
                    "content":   (
                        f"[Confirmed: {rec.get('label_id', node.label_id)}] "
                        f"Concepts demonstrated: "
                        f"{', '.join(rec.get('concepts_demonstrated', []))}. "
                        f"{rec.get('evidence_summary', '')}"
                    ),
                    "turn_type": "system",
                })

        return context

    @property
    def all_comprehension_records(self) -> list[dict[str, Any]]:
        return [
            node.comprehension_record
            for node in self.iterate_oldest_first()
            if node.comprehension_record is not None
        ]

    @property
    def confirmed_labels(self) -> list[str]:
        return [
            node.label_id
            for node in self.iterate_oldest_first()
            if node.status == "confirmed" and node.label_id
        ]

    def iterate_oldest_first(self) -> Iterator[FactoryNode]:
        node = self.tail
        while node is not None:
            yield node
            node = node.next

    def iterate_newest_first(self) -> Iterator[FactoryNode]:
        node = self.head
        while node is not None:
            yield node
            node = node.prev

    def last_n_turns(self, n: int) -> list[dict[str, Any]]:
        if not self.current:
            return []
        return self.current.turns[-n:]

    # ── Serialisation ─────────────────────────────────────────────────────

    def to_dict(self) -> dict[str, Any]:
        return {
            "head":    self.head.stage_id    if self.head    else None,
            "tail":    self.tail.stage_id    if self.tail    else None,
            "current": self.current.stage_id if self.current else None,
            "size":    self.size,
            "nodes":   [node.to_dict() for node in self.iterate_oldest_first()],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> FactoryConversationHistory:
        history = cls()

        if not data.get("nodes"):
            return history

        nodes_by_id: dict[str, FactoryNode] = {}
        for node_data in data["nodes"]:
            node = FactoryNode.from_dict(node_data)
            nodes_by_id[node.stage_id] = node

        for node_data in data["nodes"]:
            node    = nodes_by_id[node_data["stage_id"]]
            prev_id = node_data.get("prev")
            next_id = node_data.get("next")
            if prev_id and prev_id in nodes_by_id:
                node.prev = nodes_by_id[prev_id]
            if next_id and next_id in nodes_by_id:
                node.next = nodes_by_id[next_id]

        if data.get("tail")    and data["tail"]    in nodes_by_id:
            history.tail    = nodes_by_id[data["tail"]]
        if data.get("head")    and data["head"]    in nodes_by_id:
            history.head    = nodes_by_id[data["head"]]
        if data.get("current") and data["current"] in nodes_by_id:
            history.current = nodes_by_id[data["current"]]

        history.size = data.get("size", len(nodes_by_id))
        return history

    def __len__(self) -> int:
        return self.size

    def __bool__(self) -> bool:
        return self.size > 0

    def __repr__(self) -> str:
        return (
            f"FactoryConversationHistory("
            f"size={self.size}, "
            f"current={self.current.stage_id if self.current else None!r}"
            f")"
        )
