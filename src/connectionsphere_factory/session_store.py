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


# ── Global key-value store (session-independent) ──────────────────────────────
# Used for data shared across all sessions: concept diagrams, etc.
# Key format convention: "{namespace}:{identifier}"
# e.g. "concept_diagram:load_balancer"

_global_store: dict[str, str] = {}


def save_global(key: str, value: str) -> None:
    """Persist a global (session-independent) string value."""
    _global_store[key] = value


def load_global(key: str) -> str | None:
    """Retrieve a global value. Returns None if absent."""
    return _global_store.get(key)


def delete_global(key: str) -> bool:
    """Remove a global value. Returns True if it existed."""
    return _global_store.pop(key, None) is not None


def list_global(prefix: str = "") -> list[str]:
    """Return all global keys, optionally filtered by prefix."""
    return [k for k in _global_store if k.startswith(prefix)]