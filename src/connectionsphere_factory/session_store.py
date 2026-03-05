"""
connectionsphere_factory/session_store.py

In-memory session store for the skeleton.
Same interface as the Redis store — swap without touching any other file.
"""

from __future__ import annotations

from typing import Any

from connectionsphere_factory.domain.conversation.history import FactoryConversationHistory
from connectionsphere_factory.domain.fsm.machine import FactoryFSM

_store: dict[str, dict[str, Any]] = {}


def save(session_id: str, fsm: FactoryFSM, dll: FactoryConversationHistory) -> None:
    """Serialise FSM + DLL. Merges into existing entry — preserves fields from save_field."""
    existing = _store.get(session_id, {})
    existing["fsm"] = fsm.to_dict()
    existing["dll"] = dll.to_dict()
    _store[session_id] = existing


def save_field(session_id: str, key: str, value: Any) -> None:
    if session_id not in _store:
        _store[session_id] = {}
    _store[session_id][key] = value


def load(session_id: str) -> tuple[FactoryFSM, FactoryConversationHistory] | None:
    raw = _store.get(session_id)
    if not raw or "fsm" not in raw:
        return None
    return (
        FactoryFSM.from_dict(raw["fsm"]),
        FactoryConversationHistory.from_dict(raw["dll"]),
    )


def load_field(session_id: str, key: str) -> Any | None:
    raw = _store.get(session_id)
    if not raw:
        return None
    return raw.get(key)


def exists(session_id: str) -> bool:
    return session_id in _store


def all_sessions() -> list[str]:
    return list(_store.keys())


def list_all() -> list[str]:
    """Return all session IDs. Used by GET /sessions and health check."""
    return list(_store.keys())
