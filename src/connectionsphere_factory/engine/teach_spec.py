"""
connectionsphere_factory/engine/teach_spec.py

Curriculum-backed teach spec builder for Alex's lesson phase.

Public API
──────────
build_teach_spec(session_id, candidate_first_name, candidate_level,
                 problem_statement) -> dict

  Returns a fully merged teach spec — skeleton from curriculum.py enriched
  by one Claude call via teach_enrich.j2. The result is ready to cache in
  stage_specs["1"] and is a superset of the old teach_lesson.j2 output.

Design
──────
The old teach_lesson.j2 generated everything from scratch: concepts, analogies,
comprehension checks, the lot. This module replaces that with two deterministic
steps:

  STEP 1 — select_concepts_for_problem() [pure Python, instant]
    Maps the problem statement to the relevant CHAPTER_1_CONCEPTS subset.
    Always returns concepts in curriculum order.

  STEP 2 — build_teach_spec() via teach_enrich.j2 [one Claude call]
    Claude enriches the skeleton with:
      - A personalised greeting
      - Per-concept: analogy, hook, comprehension check wording, transition
      - A ready_summary closing sentence
    Everything else (core_facts, jordan_minimum_bar, drawing_rubric, etc.)
    comes directly from curriculum.py — Claude cannot alter it.

New fields in the returned spec (vs old teach_lesson.j2 output)
───────────────────────────────────────────────────────────────
  concept_id               — active concept id (first drawing concept or first)
  comprehension_check_mode — "drawing" | "verbal"
  drawing_rubric           — [{label, description, required}]
  all_concept_ids          — ordered list of all selected concept ids
  minimum_bar              — Jordan's minimum bar for the active concept
  concepts_tested          — same as all_concept_ids (for assess_submission.j2)

All existing fields from the old spec are preserved so no other consumer breaks.
"""

from __future__ import annotations

from connectionsphere_factory.curriculum import CHAPTER_1_CONCEPTS, Concept
from connectionsphere_factory.engine.prompt_renderer import render_and_call
from connectionsphere_factory.logging import get_logger

log = get_logger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Concept selection
# ─────────────────────────────────────────────────────────────────────────────

#: Always included — the Chapter 1 core eight.
_CORE_IDS: frozenset[str] = frozenset({
    "single_server",
    "database_separation",
    "scaling_models",
    "load_balancer",
    "database_replication",
    "cache_tier",
    "cdn",
    "stateless_web_tier",
})

#: Signal words → additional concepts
_GLOBAL_SIGNALS = [
    "global", "multi-region", "worldwide", "international",
    "multiple data center", "geo", "latency",
]
_ASYNC_SIGNALS = [
    "upload", "video", "photo", "image processing", "email",
    "notification", "queue", "worker", "job", "async",
    "background", "news feed", "timeline",
]
_SCALE_SIGNALS = [
    "billion", "petabyte", "terabyte", "massive scale",
    "sharding", "hundreds of million", "high write",
]


def select_concepts_for_problem(problem_statement: str) -> list[Concept]:
    """
    Map a problem statement to the relevant CHAPTER_1_CONCEPTS subset.

    Strategy:
      - Always include concepts 1-8 (the core Chapter 1 progression)
      - Add concept 9  (data_centers)      for "global" / "multi-region" problems
      - Add concept 10 (message_queue)     for async work / upload / notification problems
      - Add concept 11 (database_sharding) for "billions of users" / "petabyte" problems
      - Always append concept 12 (full_architecture) as the capstone

    Returns concepts in curriculum order (sorted by .order). Never shuffled.
    """
    p = problem_statement.lower()

    selected_ids: set[str] = set(_CORE_IDS)
    selected_ids.add("full_architecture")   # always the capstone

    if any(s in p for s in _GLOBAL_SIGNALS):
        selected_ids.add("data_centers")
    if any(s in p for s in _ASYNC_SIGNALS):
        selected_ids.add("message_queue")
    if any(s in p for s in _SCALE_SIGNALS):
        selected_ids.add("database_sharding")

    concepts = [c for c in CHAPTER_1_CONCEPTS if c.id in selected_ids]
    log.info(
        "teach_spec.concepts_selected",
        count       = len(concepts),
        concept_ids = [c.id for c in concepts],
    )
    return concepts


# ─────────────────────────────────────────────────────────────────────────────
# Spec builder
# ─────────────────────────────────────────────────────────────────────────────

def build_teach_spec(
    session_id:           str,
    candidate_first_name: str,
    candidate_level:      str,
    problem_statement:    str,
) -> dict:
    """
    Build a complete teach spec for Alex's lesson phase.

    Calls select_concepts_for_problem() to get the skeleton, then calls
    Claude via teach_enrich.j2 for analogy, hook, check wording, transitions,
    greeting, and ready_summary.

    Returns a dict that is a superset of the old teach_lesson.j2 output,
    plus all new fields required by the whiteboard UI.
    """
    concepts = select_concepts_for_problem(problem_statement)
    if not concepts:
        concepts = list(CHAPTER_1_CONCEPTS)   # fallback — should never happen

    # Serialise concepts for Jinja2 (attribute access on dicts)
    concept_dicts = [
        {
            "id":                c.id,
            "name":              c.name,
            "book_pages":        c.book_pages,
            "core_facts":        c.core_facts,
            "alex_analogy_seed": c.alex_analogy_seed,
            "why_it_matters":    c.why_it_matters,
            "jordan_probes":     c.jordan_probes,
            "solicit_drawing":   c.solicit_drawing,
        }
        for c in concepts
    ]

    log.info(
        "teach_spec.enrichment_start",
        session_id   = session_id,
        concept_count = len(concepts),
    )

    enrichment = render_and_call(
        "teach_enrich.j2",
        {
            "candidate_first_name": candidate_first_name,
            "candidate_level":      candidate_level,
            "problem_statement":    problem_statement,
            "concepts":             concept_dicts,
        },
        max_tokens = 3000,
    )

    log.info("teach_spec.enrichment_done", session_id=session_id)

    return _merge(concepts, enrichment, candidate_first_name)


# ─────────────────────────────────────────────────────────────────────────────
# Merge skeleton + enrichment
# ─────────────────────────────────────────────────────────────────────────────

def _merge(
    concepts:    list[Concept],
    enrichment:  dict,
    first_name:  str,
) -> dict:
    """
    Merge the hard-coded curriculum skeleton with Claude's enrichment.

    Core_facts come from curriculum — Claude cannot alter them.
    Analogy, hook, comprehension_check wording, and transitions come
    from the enrichment dict.
    """
    enrichment_by_id: dict[str, dict] = {
        e["concept_id"]: e
        for e in enrichment.get("concept_enrichments", [])
        if "concept_id" in e
    }

    # Build merged concepts list (shape = superset of old teach_lesson.j2 concepts)
    merged: list[dict] = []
    for c in concepts:
        e = enrichment_by_id.get(c.id, {})
        merged.append({
            # ── Existing UI fields ──────────────────────────────────────────
            "name":          c.name,
            "explanation":   " ".join(c.core_facts),          # verbatim from book
            "example":       e.get("analogy", c.alex_analogy_seed),   # Claude-varied
            "probe_warning": c.jordan_probes[0] if c.jordan_probes else "",

            # ── New curriculum fields ───────────────────────────────────────
            "concept_id":               c.id,
            "book_pages":               c.book_pages,
            "why_it_matters":           c.why_it_matters,
            "hook":                     e.get("hook", c.why_it_matters),
            "comprehension_check":      e.get("comprehension_check", ""),
            "comprehension_check_mode": e.get("comprehension_check_mode", "verbal"),
            "transition":               e.get("transition", ""),
            "solicit_drawing":          c.solicit_drawing,
            "drawing_rubric": [
                {
                    "label":       item.label,
                    "description": item.description,
                    "required":    item.required,
                }
                for item in c.drawing_rubric
            ],
            "jordan_minimum_bar": c.jordan_minimum_bar,
            "common_mistakes":    c.common_mistakes,
            "faang_signal":       c.faang_signal,
        })

    # Active concept for the whiteboard: first drawing concept, else first concept
    drawing = [c for c in concepts if c.solicit_drawing]
    active  = drawing[0] if drawing else concepts[0]
    e_active = enrichment_by_id.get(active.id, {})

    return {
        # ── Existing spec fields (all consumers read these) ─────────────────
        "lesson_title":       enrichment.get("lesson_title", "System Design Foundations"),
        "greeting":           enrichment.get("greeting", f"Hey {first_name}, let's get you ready."),
        "concepts":           merged,
        "ready_summary":      enrichment.get("ready_summary", ""),
        "comprehension_check": e_active.get(
            "comprehension_check",
            # fallback: last concept's check
            enrichment_by_id.get(concepts[-1].id, {}).get("comprehension_check", ""),
        ),

        # ── New whiteboard / diagram fields ─────────────────────────────────
        "concept_id":               active.id,
        "comprehension_check_mode": "drawing" if active.solicit_drawing else "verbal",
        "drawing_rubric": [
            {
                "label":       item.label,
                "description": item.description,
                "required":    item.required,
            }
            for item in active.drawing_rubric
        ],
        "all_concept_ids": [c.id for c in concepts],

        # ── Pass-through for teach_check.j2, audio, and assess_submission.j2 ─
        "stage_title":     enrichment.get("lesson_title", "System Design Foundations"),
        "minimum_bar":     active.jordan_minimum_bar,
        "concepts_tested": [c.id for c in concepts],
        "opening_question": enrichment.get("greeting", ""),  # TTS in teach phase
    }
