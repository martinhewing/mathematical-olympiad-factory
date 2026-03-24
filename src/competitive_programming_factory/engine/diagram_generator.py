"""
competitive_programming_factory/engine/diagram_generator.py

Concept diagram generation — the only file that calls Claude to produce SVGs.

Public API
──────────
get_or_generate_concept_diagram(concept_id: str) -> DiagramResult
    Returns the cached SVG for this concept, or generates it via Claude.
    Global cache: shared across all sessions. Survives process restarts
    in production (Redis). In dev (in-memory store), regenerates on restart.

invalidate_concept_diagram(concept_id: str) -> bool
    Removes the cached SVG so the next call regenerates it.
    Used by the admin invalidation route.

pregenerate_all_diagrams() -> dict[str, bool]
    Warms the cache for all 12 concepts. Call on startup or via admin route.
    Returns {concept_id: success} mapping.

DiagramResult fields
────────────────────
  concept_id      — stable key from curriculum.py
  concept_name    — display name (e.g. "Load Balancer")
  svg             — raw SVG string starting with <svg
  book_pages      — source page reference
  solicit_drawing — True if Alex/Jordan will ask the candidate to draw this
  drawing_rubric  — list of {label, description, required} for candidate eval
  diagram_type    — "reference" | "evolution"
  cached          — True if this was a cache hit; False if freshly generated

Claude call design
──────────────────
SVG generation is fundamentally different from JSON generation:
  - We want raw SVG, NOT JSON — render_and_call() is wrong here
  - The model must not wrap output in markdown fences
  - SVGs can be 2–5 KB; we need 4000 tokens minimum
  - We enforce the contract via a system prompt + explicit instructions
    in the user message, then strip any accidental fences defensively

We call the Anthropic client directly rather than through prompt_renderer
to (a) supply a system prompt and (b) avoid the JSON parsing step.

Retry policy
────────────
One retry on invalid SVG (does not start with <svg after stripping).
If both attempts fail, raises DiagramGenerationError with the raw response
for debugging. We do NOT silently return placeholder SVGs — bad diagrams
mislead candidates and are worse than an error.

Caching key format
──────────────────
  "concept_diagram:{concept_id}"
  e.g. "concept_diagram:load_balancer"

The diagram_prompt in curriculum.py is deterministic for a given concept_id,
so the same key always maps to the same correct diagram. There is no
per-session variation in the reference diagrams — Claude enriches the
verbal explanation, not the diagram.
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass
from typing import Any

import anthropic

import competitive_programming_factory.session_store as store
from competitive_programming_factory.config import get_settings
from competitive_programming_factory.curriculum import CONCEPT_BY_ID, Concept, DrawingRubricItem
from competitive_programming_factory.logging import get_logger

log = get_logger(__name__)

_CACHE_KEY_PREFIX = "concept_diagram:"

# Diagram generation uses Sonnet — SVG quality degrades noticeably on Haiku.
# This is a one-time cost per concept (then cached), so the extra token cost
# is justified.
_DIAGRAM_MODEL = "claude-sonnet-4-20250514"

_DIAGRAM_MAX_TOKENS = 6000

_SYSTEM_PROMPT = """\
You are an expert SVG diagram generator for system design architecture diagrams.

CRITICAL RULES — follow every one without exception:
1. Return ONLY raw SVG code. Your entire response must start with <svg and end with </svg>.
2. Do NOT include DOCTYPE declarations, XML declarations, or <html> tags.
3. Do NOT wrap the SVG in markdown code fences (no ``` or ```svg).
4. Do NOT include any explanation, preamble, or text outside the SVG tags.
5. Every element must be valid SVG 1.1. Do not use HTML elements inside SVG.
6. All text must use the font-family specified in the style guide.
7. Arrowhead markers must be defined inside a <defs> block at the top of the SVG.
8. The viewBox must be exactly as specified in the style guide.
9. Do not use <foreignObject> or any HTML embedding.
10. Ensure all paths, rects, and circles have explicit fill and stroke attributes.

If you cannot produce a valid SVG matching the requirements, produce the closest
valid SVG you can — do not output an error message or explanation."""


class DiagramGenerationError(Exception):
    """Raised when Claude fails to produce a valid SVG after all retries."""

    def __init__(self, concept_id: str, raw_response: str, attempt: int):
        self.concept_id = concept_id
        self.raw_response = raw_response
        self.attempt = attempt
        super().__init__(
            f"diagram_generator: failed to produce valid SVG for '{concept_id}' "
            f"after {attempt} attempt(s). "
            f"Response preview: {raw_response[:200]!r}"
        )


@dataclass
class DiagramResult:
    concept_id: str
    concept_name: str
    svg: str
    book_pages: str
    solicit_drawing: bool
    drawing_rubric: list[dict[str, Any]]  # serialised DrawingRubricItem
    diagram_type: str
    cached: bool

    @classmethod
    def from_concept(cls, concept: Concept, svg: str, *, cached: bool) -> DiagramResult:
        return cls(
            concept_id=concept.id,
            concept_name=concept.name,
            svg=svg,
            book_pages=concept.book_pages,
            solicit_drawing=concept.solicit_drawing,
            drawing_rubric=_serialise_rubric(concept.drawing_rubric),
            diagram_type=concept.diagram_type,
            cached=cached,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "concept_id": self.concept_id,
            "concept_name": self.concept_name,
            "book_pages": self.book_pages,
            "diagram_type": self.diagram_type,
            "solicit_drawing": self.solicit_drawing,
            "drawing_rubric": self.drawing_rubric,
            "cached": self.cached,
            # SVG omitted from dict — returned separately as raw bytes
        }


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────


def get_or_generate_concept_diagram(concept_id: str) -> DiagramResult:
    """
    Return the SVG diagram for a concept.

    Checks the global store first. On miss, calls Claude, validates the SVG,
    and caches the result before returning. Thread-safe at the store level
    (last-write-wins on concurrent generation — acceptable for diagrams).

    Args:
        concept_id: Must match a key in CONCEPT_BY_ID from curriculum.py.

    Returns:
        DiagramResult with svg field containing raw SVG string.

    Raises:
        KeyError: concept_id is not in curriculum.
        DiagramGenerationError: Claude failed to produce valid SVG after retries.
    """
    if concept_id not in CONCEPT_BY_ID:
        raise KeyError(f"concept_id '{concept_id}' not found in curriculum. Valid ids: {sorted(CONCEPT_BY_ID.keys())}")

    concept = CONCEPT_BY_ID[concept_id]
    cache_key = f"{_CACHE_KEY_PREFIX}{concept_id}"

    # ── Cache hit ────────────────────────────────────────────────────────────
    cached_svg = store.load_global(cache_key)
    if cached_svg:
        log.info("diagram.cache_hit", concept_id=concept_id, svg_bytes=len(cached_svg))
        return DiagramResult.from_concept(concept, cached_svg, cached=True)

    # ── Cache miss — generate ─────────────────────────────────────────────────
    log.info("diagram.generating", concept_id=concept_id, concept_name=concept.name)
    svg = _generate_svg(concept)

    store.save_global(cache_key, svg)
    log.info(
        "diagram.generated_and_cached",
        concept_id=concept_id,
        svg_bytes=len(svg),
        cache_key=cache_key,
    )
    return DiagramResult.from_concept(concept, svg, cached=False)


def invalidate_concept_diagram(concept_id: str) -> bool:
    """
    Remove the cached diagram for a concept, forcing regeneration on next request.

    Returns True if a cached diagram existed and was removed, False otherwise.
    """
    if concept_id not in CONCEPT_BY_ID:
        raise KeyError(f"concept_id '{concept_id}' not found in curriculum.")

    cache_key = f"{_CACHE_KEY_PREFIX}{concept_id}"
    existed = store.delete_global(cache_key)
    log.info("diagram.invalidated", concept_id=concept_id, existed=existed)
    return existed


def pregenerate_all_diagrams() -> dict[str, bool]:
    """
    Warm the diagram cache for all concepts in curriculum.py.

    Intended for use at startup or via admin endpoint. Safe to call
    when diagrams are already cached — those will be skipped.

    Returns:
        Dict mapping concept_id → True (success) | False (failed).
    """
    results: dict[str, bool] = {}
    for concept_id in CONCEPT_BY_ID:
        cache_key = f"{_CACHE_KEY_PREFIX}{concept_id}"
        if store.load_global(cache_key):
            log.info("diagram.pregenerate_skip", concept_id=concept_id, reason="already_cached")
            results[concept_id] = True
            continue
        try:
            get_or_generate_concept_diagram(concept_id)
            results[concept_id] = True
        except Exception as exc:
            log.error("diagram.pregenerate_failed", concept_id=concept_id, error=str(exc))
            results[concept_id] = False

    successes = sum(v for v in results.values())
    log.info(
        "diagram.pregenerate_complete",
        total=len(results),
        succeeded=successes,
        failed=len(results) - successes,
    )
    return results


def list_cached_diagrams() -> list[str]:
    """Return concept_ids for all currently cached diagrams."""
    prefix = _CACHE_KEY_PREFIX
    return [key[len(prefix) :] for key in store.list_global(prefix)]


# ─────────────────────────────────────────────────────────────────────────────
# Internal helpers
# ─────────────────────────────────────────────────────────────────────────────


def _generate_svg(concept: Concept, *, attempt: int = 1) -> str:
    """
    Call Claude to generate the SVG for this concept.
    Retries once on invalid response. Raises DiagramGenerationError on failure.
    """
    settings = get_settings()
    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

    prompt = _build_prompt(concept)

    start = time.perf_counter()
    try:
        message = client.messages.create(
            model=_DIAGRAM_MODEL,
            max_tokens=_DIAGRAM_MAX_TOKENS,
            system=_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
        )
    except anthropic.APIError as exc:
        log.error(
            "diagram.api_error",
            concept_id=concept.id,
            attempt=attempt,
            error=str(exc),
        )
        raise

    duration_ms = int((time.perf_counter() - start) * 1000)
    raw = message.content[0].text

    log.info(
        "diagram.claude_call",
        concept_id=concept.id,
        attempt=attempt,
        input_tokens=getattr(message.usage, "input_tokens", 0),
        output_tokens=getattr(message.usage, "output_tokens", 0),
        duration_ms=duration_ms,
    )

    svg = _extract_svg(raw)

    if svg is None:
        log.warning(
            "diagram.invalid_response",
            concept_id=concept.id,
            attempt=attempt,
            preview=raw[:300],
        )
        if attempt < 2:
            log.info("diagram.retrying", concept_id=concept.id)
            return _generate_svg(concept, attempt=attempt + 1)
        raise DiagramGenerationError(concept.id, raw, attempt)

    return svg


def _build_prompt(concept: Concept) -> str:
    """
    Assemble the full user-turn prompt from the concept's diagram_prompt.

    The diagram_prompt already embeds the SVG_STYLE_GUIDE from curriculum.py,
    so this function just adds a firm closing instruction.
    """
    return (
        f"Generate the following architecture diagram:\n\n"
        f"{concept.diagram_prompt}\n\n"
        "─────────────────────────────────────────\n"
        "REMINDER: Return ONLY raw SVG starting with <svg. "
        "No preamble. No markdown fences. No explanation after </svg>."
    )


def _extract_svg(raw: str) -> str | None:
    """
    Extract a valid SVG string from Claude's raw response.

    Handles:
      1. Clean response — starts with <svg directly
      2. Wrapped in ```svg ... ``` or ``` ... ``` fences
      3. Leading/trailing whitespace or explanation text
      4. Responses where <svg appears after a short preamble

    Returns None if no valid SVG can be extracted.
    """
    text = raw.strip()

    # Case 1: clean response
    if text.lower().startswith("<svg"):
        return _validate_svg(text)

    # Case 2: markdown fences
    fence_match = re.search(
        r"```(?:svg|xml)?\s*(<svg[\s\S]*?</svg>)\s*```",
        text,
        re.IGNORECASE,
    )
    if fence_match:
        return _validate_svg(fence_match.group(1).strip())

    # Case 3: SVG buried in text (short preamble before <svg)
    svg_match = re.search(r"(<svg[\s\S]*?</svg>)", text, re.IGNORECASE)
    if svg_match:
        candidate = svg_match.group(1).strip()
        # Sanity-check: must have at least one rect or path to be a real diagram
        if re.search(r"<(rect|path|circle|polygon|line|text)\b", candidate):
            return _validate_svg(candidate)

    return None


def _validate_svg(svg: str) -> str | None:
    """
    Lightweight structural validation — checks minimum required elements.
    Returns the svg string if valid, None if it looks malformed.
    """
    if not svg.lower().startswith("<svg"):
        return None
    if "</svg>" not in svg.lower():
        return None
    # Must contain at least some drawing primitives
    if not re.search(r"<(rect|path|circle|polygon|line|text|g)\b", svg, re.IGNORECASE):
        return None
    return svg


def _serialise_rubric(rubric: list[DrawingRubricItem]) -> list[dict[str, Any]]:
    return [
        {
            "label": item.label,
            "description": item.description,
            "required": item.required,
        }
        for item in rubric
    ]
