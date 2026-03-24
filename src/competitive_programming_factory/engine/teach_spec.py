"""
competitive_programming_factory/engine/teach_spec.py

Curriculum-backed teach spec builder for Alistair's lesson phase.

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

from competitive_programming_factory.curriculum import CHAPTER_1_CONCEPTS, Concept
from competitive_programming_factory.engine.prompt_renderer import render_and_call
from competitive_programming_factory.logging import get_logger

log = get_logger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Concept selection
# ─────────────────────────────────────────────────────────────────────────────

#: All 8 Holton Chapter 1 concepts — always taught in full, in order.
_ALL_CP_IDS: frozenset[str] = frozenset(
    {
        "problem_solving_framework",
        "jug_problem",
        "bezout_identity",
        "consecutive_numbers",
        "stamp_problem_discovery",
        "threshold_proof_3_5",
        "generalisation_3_s",
        "frobenius_theorem",
    }
)


def select_concepts_for_problem(problem_statement: str) -> list[Concept]:
    """
    For the CP instance, all 8 Holton Chapter 1 concepts are always included.
    The curriculum is a linear progression — no problem-specific filtering.
    Returns concepts in curriculum order. Never shuffled.
    """
    concepts = [c for c in CHAPTER_1_CONCEPTS if c.id in _ALL_CP_IDS]
    log.info(
        "teach_spec.concepts_selected",
        count=len(concepts),
        concept_ids=[c.id for c in concepts],
    )
    return concepts


# ─────────────────────────────────────────────────────────────────────────────
# Spec builder
# ─────────────────────────────────────────────────────────────────────────────


def build_teach_spec(
    session_id: str,
    candidate_first_name: str,
    candidate_level: str,
    problem_statement: str,
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
        concepts = list(CHAPTER_1_CONCEPTS)  # fallback — should never happen

    # Serialise concepts for Jinja2 (attribute access on dicts)
    concept_dicts = [
        {
            "id": c.id,
            "name": c.name,
            "book_pages": c.book_pages,
            "core_facts": c.core_facts,
            "alex_analogy_seed": c.alex_analogy_seed,
            "why_it_matters": c.why_it_matters,
            "jordan_probes": c.jordan_probes,
            "solicit_drawing": c.solicit_drawing,
        }
        for c in concepts
    ]

    log.info(
        "teach_spec.enrichment_start",
        session_id=session_id,
        concept_count=len(concepts),
    )

    enrichment = render_and_call(
        "teach_enrich.j2",
        {
            "candidate_first_name": candidate_first_name,
            "candidate_level": candidate_level,
            "problem_statement": problem_statement,
            "concepts": concept_dicts,
        },
        max_tokens=3000,
    )

    log.info("teach_spec.enrichment_done", session_id=session_id)

    return _merge(concepts, enrichment, candidate_first_name)


# ─────────────────────────────────────────────────────────────────────────────
# Merge skeleton + enrichment
# ─────────────────────────────────────────────────────────────────────────────


def _merge(
    concepts: list[Concept],
    enrichment: dict,
    first_name: str,
) -> dict:
    """
    Merge the hard-coded curriculum skeleton with Claude's enrichment.

    Core_facts come from curriculum — Claude cannot alter them.
    Analogy, hook, comprehension_check wording, and transitions come
    from the enrichment dict.
    """
    enrichment_by_id: dict[str, dict] = {
        e["concept_id"]: e for e in enrichment.get("concept_enrichments", []) if "concept_id" in e
    }

    # Build merged concepts list (shape = superset of old teach_lesson.j2 concepts)
    merged: list[dict] = []
    for c in concepts:
        e = enrichment_by_id.get(c.id, {})
        merged.append(
            {
                # ── Existing UI fields ──────────────────────────────────────────
                "name": c.name,
                "explanation": " ".join(c.core_facts),  # verbatim from book
                "example": e.get("analogy", c.alex_analogy_seed),  # Claude-varied
                "probe_warning": c.jordan_probes[0] if c.jordan_probes else "",
                # ── New curriculum fields ───────────────────────────────────────
                "concept_id": c.id,
                "book_pages": c.book_pages,
                "why_it_matters": c.why_it_matters,
                "hook": e.get("hook", c.why_it_matters),
                "comprehension_check": e.get("comprehension_check", ""),
                "comprehension_check_mode": e.get("comprehension_check_mode", "verbal"),
                "transition": e.get("transition", ""),
                "solicit_drawing": c.solicit_drawing,
                "drawing_rubric": [
                    {
                        "label": item.label,
                        "description": item.description,
                        "required": item.required,
                    }
                    for item in c.drawing_rubric
                ],
                "jordan_minimum_bar": c.jordan_minimum_bar,
                "common_mistakes": c.common_mistakes,
                "faang_signal": c.faang_signal,
            }
        )

    # Active concept for the whiteboard: first drawing concept, else first concept
    drawing = [c for c in concepts if c.solicit_drawing]
    active = drawing[0] if drawing else concepts[0]
    e_active = enrichment_by_id.get(active.id, {})

    return {
        # ── Existing spec fields (all consumers read these) ─────────────────
        "lesson_title": enrichment.get("lesson_title", "System Design Foundations"),
        "greeting": enrichment.get("greeting", f"Hey {first_name}, let's get you ready."),
        "concepts": merged,
        "ready_summary": enrichment.get("ready_summary", ""),
        "comprehension_check": e_active.get(
            "comprehension_check",
            # fallback: last concept's check
            enrichment_by_id.get(concepts[-1].id, {}).get("comprehension_check", ""),
        ),
        # ── New whiteboard / diagram fields ─────────────────────────────────
        "concept_id": active.id,
        "comprehension_check_mode": "drawing" if active.solicit_drawing else "verbal",
        "drawing_rubric": [
            {
                "label": item.label,
                "description": item.description,
                "required": item.required,
            }
            for item in active.drawing_rubric
        ],
        "all_concept_ids": [c.id for c in concepts],
        # ── Pass-through for teach_check.j2, audio, and assess_submission.j2 ─
        "stage_title": enrichment.get("lesson_title", "System Design Foundations"),
        "minimum_bar": active.jordan_minimum_bar,
        "concepts_tested": [c.id for c in concepts],
        "opening_question": enrichment.get("greeting", ""),  # TTS in teach phase
    }


# ─────────────────────────────────────────────────────────────────────────────
# Per-concept spec builders (new architecture)
# ─────────────────────────────────────────────────────────────────────────────


def build_single_concept_teach_spec(
    session_id: str,
    concept: Concept,
    candidate_first_name: str,
    candidate_level: str,
    problem_statement: str,
    concept_index: int,
    concepts_total: int,
) -> dict:
    """
    Build Alex's teach spec for a single concept.

    One Claude call via teach_concept.j2. Returns a spec dict that the
    session engine caches under stage_specs[str(stage_n)].

    The spec is a strict superset of what the UI expects from a teach stage —
    all existing fields plus the per-concept additions needed by the whiteboard.

    Args:
        session_id:           For logging.
        concept:              The Concept dataclass from curriculum.py.
        candidate_first_name: Alex addresses the candidate by name.
        candidate_level:      Calibrates tone and depth.
        problem_statement:    Grounds analogy and example in the real problem.
        concept_index:        0-based position in session concept list (for "4 of 9" display).
        concepts_total:       Total concepts selected for this session.

    Returns:
        dict with all fields expected by voice.py _stage_text(), teach_check.j2,
        and the whiteboard UI.
    """
    rubric_dicts = [
        {"label": r.label, "description": r.description, "required": r.required} for r in concept.drawing_rubric
    ]

    log.info(
        "teach_spec.single_concept.start",
        session_id=session_id,
        concept_id=concept.id,
        concept_index=concept_index,
    )

    spec = render_and_call(
        "teach_concept.j2",
        {
            "candidate_first_name": candidate_first_name,
            "candidate_level": candidate_level,
            "problem_statement": problem_statement,
            "concept_name": concept.name,
            "concept_id": concept.id,
            "book_pages": concept.book_pages,
            "concept_index": concept_index,
            "concepts_total": concepts_total,
            "core_facts": concept.core_facts,
            "why_it_matters": concept.why_it_matters,
            "jordan_minimum_bar": concept.jordan_minimum_bar,
            "faang_signal": concept.faang_signal,
            "common_mistakes": concept.common_mistakes,
            "alex_analogy_seed": concept.alex_analogy_seed,
            "solicit_drawing": concept.solicit_drawing,
            "drawing_rubric": rubric_dicts,
        },
        max_tokens=2000,
    )

    log.info(
        "teach_spec.single_concept.done",
        session_id=session_id,
        concept_id=concept.id,
    )

    # Normalise — ensure all fields the engine and UI need are present
    spec.setdefault("stage_title", concept.name)
    spec.setdefault("concept_id", concept.id)
    spec.setdefault("agent", "alex")
    spec.setdefault("greeting", "")
    spec.setdefault("explanation", " ".join(concept.core_facts))
    spec.setdefault("analogy", concept.alex_analogy_seed)
    spec.setdefault("example", "")
    spec.setdefault("probe_warning", concept.jordan_probes[0] if concept.jordan_probes else "")
    spec.setdefault("comprehension_check", "")
    spec.setdefault("comprehension_check_mode", "drawing" if concept.solicit_drawing else "verbal")
    spec.setdefault("transition", "")
    spec.setdefault("ready_summary", "")
    spec.setdefault("minimum_bar", concept.jordan_minimum_bar)
    spec.setdefault("solicit_drawing", concept.solicit_drawing)
    spec.setdefault("drawing_rubric", rubric_dicts)
    spec.setdefault("concepts_tested", [concept.id])

    # Fields expected by voice.py _stage_text() in teach phase
    spec.setdefault(
        "concepts",
        [
            {
                "name": concept.name,
                "explanation": " ".join(concept.core_facts),
                "example": spec.get("analogy", concept.alex_analogy_seed),
                "probe_warning": concept.jordan_probes[0] if concept.jordan_probes else "",
            }
        ],
    )

    return spec


def build_single_concept_jordan_spec(
    session_id: str,
    concept: Concept,
    problem_statement: str,
    candidate_level: str,
    concept_index: int,
    concepts_total: int,
    concepts_confirmed: list[str],
) -> dict:
    """
    Build Jordan's stage spec for a single concept.

    One Claude call via generate_concept_stage.j2. Claude generates only
    the opening_question and scene_hook — everything else (probes, minimum
    bar, signals, rubric) comes from curriculum.py and is passed through.

    Args:
        session_id:          For logging.
        concept:             The Concept dataclass from curriculum.py.
        problem_statement:   Grounds the opening question in the real problem.
        candidate_level:     Calibrates Jordan's question difficulty.
        concept_index:       0-based position (for "4 of 9" display).
        concepts_total:      Total concepts selected for this session.
        concepts_confirmed:  concept_ids already confirmed earlier this session.

    Returns:
        dict with all fields expected by stages.py GET route, assess_submission.j2,
        and the whiteboard UI.
    """
    rubric_dicts = [
        {"label": r.label, "description": r.description, "required": r.required} for r in concept.drawing_rubric
    ]

    # Build strong/weak answer signals from curriculum fields
    # jordan_probes[0] is the first probe — use core_facts as signals fallback
    strong_signals = [concept.faang_signal] if concept.faang_signal else []
    weak_signals = concept.common_mistakes[:2] if concept.common_mistakes else []

    log.info(
        "teach_spec.jordan_concept.start",
        session_id=session_id,
        concept_id=concept.id,
        concept_index=concept_index,
    )

    spec = render_and_call(
        "generate_concept_stage.j2",
        {
            "problem_statement": problem_statement,
            "candidate_level": candidate_level,
            "concept_name": concept.name,
            "concept_id": concept.id,
            "concept_index": concept_index,
            "concepts_total": concepts_total,
            "concepts_confirmed": concepts_confirmed,
            "jordan_minimum_bar": concept.jordan_minimum_bar,
            "faang_signal": concept.faang_signal,
            "jordan_probes": concept.jordan_probes,
            "common_mistakes": concept.common_mistakes,
            "strong_answer_signals": strong_signals,
            "weak_answer_signals": weak_signals,
            "solicit_drawing": concept.solicit_drawing,
            "drawing_rubric": rubric_dicts,
        },
        max_tokens=2000,
    )

    log.info(
        "teach_spec.jordan_concept.done",
        session_id=session_id,
        concept_id=concept.id,
    )

    # Normalise — ensure all fields the engine and UI need are present
    spec.setdefault("stage_title", concept.name)
    spec.setdefault("concept_id", concept.id)
    spec.setdefault("agent", "jordan")
    spec.setdefault("scene_hook", "")
    spec.setdefault("opening_question", "")
    spec.setdefault("minimum_bar", concept.jordan_minimum_bar)
    spec.setdefault("strong_answer_signals", strong_signals)
    spec.setdefault("weak_answer_signals", weak_signals)
    spec.setdefault("probe_questions", concept.jordan_probes)
    spec.setdefault("concepts_tested", [concept.id])
    spec.setdefault("solicit_drawing", concept.solicit_drawing)
    spec.setdefault("drawing_rubric", rubric_dicts)

    # assess_submission.j2 reads these field names
    spec.setdefault("strong_answer_signals", strong_signals)
    spec.setdefault("weak_answer_signals", weak_signals)

    return spec
