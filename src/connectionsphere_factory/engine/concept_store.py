"""
connectionsphere_factory/engine/concept_store.py

Concept accumulation layer — the semilattice evaluator.

Each interview stage requires a *set* of concepts to be demonstrated.
Claude returns concepts per turn, but the pass/fail verdict must be
evaluated against the **union** of all turns — not just the last one.

Storage backend: session_store (save_field / load_field).
When session_store moves to Redis, this becomes SADD/SMEMBERS for free.
The interface stays identical.

Confidence gate: only concepts with confidence >= CONFIDENCE_THRESHOLD
are accumulated. Prevents hallucinated concepts from locking in.

Negation handling: if a candidate corrects themselves ("wait, not X —
I mean Y"), the retract() function removes the concept from the
accumulated set.
"""

from __future__ import annotations

from typing import Any

import connectionsphere_factory.session_store as store
from connectionsphere_factory.logging import get_logger

log = get_logger(__name__)

# ── Configuration ─────────────────────────────────────────────────────────────

CONFIDENCE_THRESHOLD = 0.85

REQUIRED_CONCEPTS: dict[int, set[str]] = {
    1: {
        "requirements_clarification",
        "scale_estimation",
        "api_design",
    },
    2: {
        "data_model",
        "storage_choice",
        "schema_design",
    },
    3: {
        "system_components",
        "scalability",
        "fault_tolerance",
    },
}


def _key(session_id: str, stage_n: int) -> str:
    return f"accumulated_concepts:{stage_n}"


def _fragments_key(session_id: str, stage_n: int) -> str:
    return f"answer_fragments:{stage_n}"


# ── Public interface ──────────────────────────────────────────────────────────

def accumulate(
    session_id:        str,
    stage_n:           int,
    concepts:          list[str],
    confidence_scores: dict[str, float] | None = None,
) -> set[str]:
    """
    Add demonstrated concepts to the stage's accumulated set.

    Only concepts with confidence >= CONFIDENCE_THRESHOLD are stored.
    If confidence_scores is None, all concepts are accepted (backwards
    compatible with prompts that don't return confidence yet).

    Returns the updated accumulated set.
    """
    current = get_accumulated(session_id, stage_n)

    for concept in concepts:
        confidence = (confidence_scores or {}).get(concept, 1.0)
        if confidence >= CONFIDENCE_THRESHOLD:
            current.add(concept)
        else:
            log.debug(
                "concept.below_threshold",
                session_id = session_id,
                stage_n    = stage_n,
                concept    = concept,
                confidence = confidence,
            )

    store.save_field(session_id, _key(session_id, stage_n), sorted(current))

    log.info(
        "concepts.accumulated",
        session_id  = session_id,
        stage_n     = stage_n,
        added       = concepts,
        total       = sorted(current),
    )
    return current


def record_fragment(session_id: str, stage_n: int, answer: str) -> None:
    """Append a raw answer fragment for audit trail."""
    key       = _fragments_key(session_id, stage_n)
    fragments = store.load_field(session_id, key) or []
    fragments.append(answer)
    store.save_field(session_id, key, fragments)


def get_accumulated(session_id: str, stage_n: int) -> set[str]:
    """Return the current accumulated concept set for a stage."""
    raw = store.load_field(session_id, _key(session_id, stage_n))
    if not raw:
        return set()
    return set(raw)


def get_required(stage_n: int) -> set[str]:
    """
    Return the required concepts for a stage.

    Falls back to a generic pair if the stage isn't in the map.
    """
    return REQUIRED_CONCEPTS.get(
        stage_n,
        {f"concept_{stage_n}_a", f"concept_{stage_n}_b"},
    )


def evaluate(session_id: str, stage_n: int) -> dict[str, Any]:
    """
    Semilattice evaluation: does the accumulated union cover the required set?

    Returns:
        {
            "passed":      bool,
            "accumulated": set[str],
            "required":    set[str],
            "missing":     set[str],
            "coverage":    float,     # 0.0 – 1.0
        }
    """
    accumulated = get_accumulated(session_id, stage_n)
    required    = get_required(stage_n)
    missing     = required - accumulated

    coverage = (
        len(required & accumulated) / len(required)
        if required
        else 1.0
    )

    return {
        "passed":      len(missing) == 0,
        "accumulated": accumulated,
        "required":    required,
        "missing":     missing,
        "coverage":    coverage,
    }


def retract(session_id: str, stage_n: int, concept: str) -> set[str]:
    """
    Remove a concept from the accumulated set.

    Used by the negation detector when a candidate corrects themselves.
    """
    current = get_accumulated(session_id, stage_n)
    current.discard(concept)
    store.save_field(session_id, _key(session_id, stage_n), sorted(current))

    log.info(
        "concept.retracted",
        session_id = session_id,
        stage_n    = stage_n,
        concept    = concept,
        remaining  = sorted(current),
    )
    return current


def clear_stage(session_id: str, stage_n: int) -> None:
    """Wipe accumulated concepts for a stage. Used on session restart."""
    store.save_field(session_id, _key(session_id, stage_n), [])
    store.save_field(session_id, _fragments_key(session_id, stage_n), [])
    log.info("concepts.cleared", session_id=session_id, stage_n=stage_n)
