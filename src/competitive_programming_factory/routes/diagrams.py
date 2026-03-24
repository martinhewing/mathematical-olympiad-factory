"""
competitive_programming_factory/routes/diagrams.py

Concept diagram endpoints.

GET  /concept/{concept_id}/diagram          — SVG (image/svg+xml)
GET  /concept/{concept_id}/diagram/meta     — JSON metadata (rubric, solicit_drawing, etc.)
POST /concept/{concept_id}/diagram/invalidate  — force cache bust (admin)
POST /diagrams/pregenerate                  — warm all 12 concept caches (admin)
GET  /diagrams/cached                       — list which concepts are already cached

Diagram route design principles
────────────────────────────────
1. SVG is returned as raw image/svg+xml — the browser renders it inline.
   The UI embed pattern is simply:
     <img src="/concept/load_balancer/diagram" />
   or:
     const res = await fetch("/concept/load_balancer/diagram");
     const svg = await res.text();
     container.innerHTML = svg;

2. On cache miss, the first request generates the diagram (~2–5 seconds).
   Subsequent requests are instant (Redis/in-memory hit).
   The UI should show a loading skeleton while the first request resolves.

3. /meta returns the rubric and solicit_drawing flag so the UI knows whether
   to activate the whiteboard panel for this concept.

4. /invalidate and /pregenerate are admin-only (require API key).
   /diagram and /meta are public within a session context (no API key needed —
   the session_id check is implicit via the teach phase gating in the UI).

Registration
────────────
Add to app.py:

    from competitive_programming_factory.routes import diagrams as diagrams_router
    app.include_router(diagrams_router.router)

Or in the factory pattern used by the existing app.py:

    from competitive_programming_factory.routes.diagrams import router as diagrams_router
    app.include_router(diagrams_router)
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response

from competitive_programming_factory.curriculum import CONCEPT_BY_ID
from competitive_programming_factory.engine.diagram_generator import (
    DiagramGenerationError,
    get_or_generate_concept_diagram,
    invalidate_concept_diagram,
    list_cached_diagrams,
    pregenerate_all_diagrams,
)
from competitive_programming_factory.logging import get_logger

log = get_logger(__name__)
router = APIRouter(tags=["diagrams"])


# ─────────────────────────────────────────────────────────────────────────────
# GET /concept/{concept_id}/diagram
# ─────────────────────────────────────────────────────────────────────────────


@router.get(
    "/concept/{concept_id}/diagram",
    response_class=Response,
    responses={
        200: {
            "content": {"image/svg+xml": {}},
            "description": "Raw SVG diagram — embed directly or render inline.",
        },
        404: {"description": "concept_id not found in curriculum"},
        500: {"description": "Claude failed to generate a valid diagram"},
    },
    summary="Get concept diagram (SVG)",
    description=(
        "Returns the reference architecture diagram for this concept as raw SVG.\n\n"
        "**Cache behaviour**: first call generates the diagram via Claude (~3–5s). "
        "Subsequent calls are instant (global cache shared across all sessions).\n\n"
        "**Embed in HTML**: `<img src='/concept/load_balancer/diagram' />`\n\n"
        "**Inline SVG**: fetch as text and set `innerHTML` directly — allows CSS theming.\n\n"
        "**Concept IDs**: `single_server` · `database_separation` · `scaling_models` · "
        "`load_balancer` · `database_replication` · `cache_tier` · `cdn` · "
        "`stateless_web_tier` · `data_centers` · `message_queue` · "
        "`database_sharding` · `full_architecture`"
    ),
)
def get_concept_diagram(concept_id: str):
    """Return the SVG diagram for a concept. Generates and caches on first call."""
    _require_valid_concept(concept_id)

    try:
        result = get_or_generate_concept_diagram(concept_id)
    except DiagramGenerationError as exc:
        log.error(
            "diagram.route_generation_failed",
            concept_id=concept_id,
            error=str(exc),
        )
        raise HTTPException(
            status_code=500,
            detail=(
                f"Failed to generate diagram for '{concept_id}'. "
                "The AI model did not produce valid SVG. "
                "Try again or use /concept/{concept_id}/diagram/invalidate to reset."
            ),
        ) from exc

    return Response(
        content=result.svg,
        media_type="image/svg+xml",
        headers={
            # Allow the browser to cache the SVG — it only changes on explicit invalidation
            "Cache-Control": "public, max-age=86400",
            "X-Concept-Id": concept_id,
            "X-Cached": str(result.cached).lower(),
            "X-Book-Pages": result.book_pages.encode("ascii", errors="replace").decode("ascii"),
        },
    )


# ─────────────────────────────────────────────────────────────────────────────
# GET /concept/{concept_id}/diagram/meta
# ─────────────────────────────────────────────────────────────────────────────


@router.get(
    "/concept/{concept_id}/diagram/meta",
    summary="Get concept diagram metadata",
    description=(
        "Returns metadata for the concept diagram — rubric items, solicit_drawing flag, "
        "and diagram type. Use this to decide whether to activate the whiteboard panel.\n\n"
        "Does **not** generate the diagram if it isn't cached yet. "
        "Metadata is always available immediately (sourced directly from curriculum.py)."
    ),
)
def get_concept_diagram_meta(concept_id: str):
    """
    Return rubric, solicit_drawing, and diagram metadata for a concept.

    The UI uses `solicit_drawing` to decide whether to show the whiteboard
    panel and `drawing_rubric` to render the checklist after evaluation.
    """
    _require_valid_concept(concept_id)
    concept = CONCEPT_BY_ID[concept_id]

    cached_ids = list_cached_diagrams()

    return {
        "concept_id": concept.id,
        "concept_name": concept.name,
        "book_pages": concept.book_pages,
        "diagram_type": concept.diagram_type,
        "solicit_drawing": concept.solicit_drawing,
        "diagram_url": f"/concept/{concept_id}/diagram",
        "is_cached": concept_id in cached_ids,
        "drawing_rubric": [
            {
                "label": item.label,
                "description": item.description,
                "required": item.required,
            }
            for item in concept.drawing_rubric
        ],
        "jordan_minimum_bar": concept.jordan_minimum_bar,
        "faang_signal": concept.faang_signal,
        "why_it_matters": concept.why_it_matters,
    }


# ─────────────────────────────────────────────────────────────────────────────
# POST /concept/{concept_id}/diagram/invalidate   (admin)
# ─────────────────────────────────────────────────────────────────────────────


@router.post(
    "/concept/{concept_id}/diagram/invalidate",
    summary="Invalidate cached diagram (admin)",
    description=(
        "Removes the cached SVG for this concept. "
        "The next call to GET /concept/{concept_id}/diagram will regenerate it.\n\n"
        "Use this when `curriculum.py` changes the `diagram_prompt` for a concept."
    ),
)
def invalidate_diagram(concept_id: str):
    """Force regeneration of a concept diagram on next request."""
    _require_valid_concept(concept_id)

    existed = invalidate_concept_diagram(concept_id)
    return {
        "concept_id": concept_id,
        "invalidated": existed,
        "message": (
            f"Cache cleared for '{concept_id}'. Next GET will regenerate."
            if existed
            else f"No cached diagram found for '{concept_id}' — nothing to clear."
        ),
    }


# ─────────────────────────────────────────────────────────────────────────────
# POST /diagrams/pregenerate   (admin)
# ─────────────────────────────────────────────────────────────────────────────


@router.post(
    "/diagrams/pregenerate",
    summary="Warm the diagram cache for all concepts (admin)",
    description=(
        "Generates and caches diagrams for all 12 curriculum concepts. "
        "Already-cached concepts are skipped.\n\n"
        "This is a **long-running request** (~30–60 seconds for 12 diagrams). "
        "Run it after deployment or after `curriculum.py` changes.\n\n"
        "Returns a `results` dict mapping `concept_id → true/false` for each concept."
    ),
)
def pregenerate_diagrams():
    """Pre-generate all concept diagrams to warm the global cache."""
    log.info("diagram.pregenerate_all_requested")
    results = pregenerate_all_diagrams()
    succeeded = [cid for cid, ok in results.items() if ok]
    failed = [cid for cid, ok in results.items() if not ok]

    return {
        "total": len(results),
        "succeeded": len(succeeded),
        "failed": len(failed),
        "results": results,
        **({"failed_ids": failed} if failed else {}),
    }


# ─────────────────────────────────────────────────────────────────────────────
# GET /diagrams/cached
# ─────────────────────────────────────────────────────────────────────────────


@router.get(
    "/diagrams/cached",
    summary="List cached concept diagrams",
    description=(
        "Returns the concept_ids of all diagrams currently in the global cache.\n\n"
        "Useful for checking warm-up state after deployment."
    ),
)
def get_cached_diagrams():
    """List all concept_ids with a cached diagram."""
    cached = list_cached_diagrams()
    all_ids = list(CONCEPT_BY_ID.keys())
    return {
        "cached_count": len(cached),
        "total_concepts": len(all_ids),
        "cached": sorted(cached),
        "pending": sorted(set(all_ids) - set(cached)),
    }


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────


def _require_valid_concept(concept_id: str) -> None:
    if concept_id not in CONCEPT_BY_ID:
        raise HTTPException(
            status_code=404,
            detail=(
                f"Concept '{concept_id}' not found. "
                f"Valid concept_ids: {sorted(CONCEPT_BY_ID.keys())}"
            ),
        )
