"""
competitive_programming_factory/engine/diagram_evaluator.py

Scores a candidate's hand-drawn diagram against a rubric using Claude Vision.

Public API
──────────
evaluate_diagram(images, rubric) -> list[DiagramScore]
  Send 1-N diagram images to Claude with a rubric list.
  Returns one DiagramScore per rubric item: label, status, notes.

DiagramScore.status values
  PRESENT  — rubric item clearly shown in the diagram
  PARTIAL  — rubric item partially shown or implied but not explicit
  MISSING  — rubric item absent from the diagram

Design notes
────────────
- Calls the Anthropic API directly (not via render_and_call) so we can
  pass image content blocks in the user message.
- Uses claude-sonnet-4-20250514 — same model as everything else in the project.
- Images arrive as raw bytes; we base64-encode them for the API.
- Non-fatal: if evaluation fails for any reason, we return UNKNOWN status for
  all items so the interview can continue. The caller (process_submission)
  treats diagram_scores as advisory input to assess_submission.j2, not a blocker.
- Max 4 images per evaluation call (Claude Vision limit per message).
- Rubric items capped at 10 to keep the prompt bounded.

Cache behaviour
───────────────
No caching — every submitted diagram is a fresh evaluation. Diagram submissions
are rare (one per probe, only on drawing concepts) so the cost is minimal.
"""

from __future__ import annotations

import base64
import json
import re
import time
from dataclasses import dataclass
from typing import Literal

import anthropic

from competitive_programming_factory.config import get_settings
from competitive_programming_factory.logging import get_logger

log = get_logger(__name__)

StatusValue = Literal["PRESENT", "PARTIAL", "MISSING", "UNKNOWN"]

_MAX_IMAGES = 4
_MAX_RUBRIC = 10

_SYSTEM_PROMPT = """\
You are a senior staff engineer evaluating a candidate's hand-drawn system design diagram.
Score each rubric item against what you can see in the image(s).
Be fair: partial credit is available. Penalise absence of required elements, not aesthetics.
Return ONLY valid JSON — no preamble, no markdown fences."""


@dataclass
class DiagramScore:
    label: str
    status: StatusValue
    notes: str = ""

    def to_dict(self) -> dict:
        return {"label": self.label, "status": self.status, "notes": self.notes}


class DiagramEvaluationError(Exception):
    pass


# ─────────────────────────────────────────────────────────────────────────────
# Public entry point
# ─────────────────────────────────────────────────────────────────────────────


def evaluate_diagram(
    images: list[bytes],
    rubric: list[dict],
    *,
    mime_type: str = "image/png",
) -> list[DiagramScore]:
    """
    Evaluate candidate diagram image(s) against a rubric.

    Args:
        images:    List of raw image bytes (PNG/JPEG). Up to 4 used.
        rubric:    List of rubric dicts: {label, description, required}.
                   Up to 10 items used.
        mime_type: MIME type for all images (default image/png).
                   Pass image/jpeg for JPEG uploads.

    Returns:
        List of DiagramScore — one per rubric item, in rubric order.
        On total failure, returns UNKNOWN scores so the session continues.
    """
    if not images:
        log.warning("diagram_evaluator.no_images")
        return [
            DiagramScore(
                label=r.get("label", f"item_{i}"), status="UNKNOWN", notes="No diagram submitted"
            )
            for i, r in enumerate(rubric[:_MAX_RUBRIC])
        ]

    if not rubric:
        log.warning("diagram_evaluator.no_rubric")
        return []

    images_to_use = images[:_MAX_IMAGES]
    rubric_to_use = rubric[:_MAX_RUBRIC]

    try:
        return _call_claude_vision(images_to_use, rubric_to_use, mime_type)
    except Exception as exc:
        log.error("diagram_evaluator.failed", error=str(exc))
        return [
            DiagramScore(
                label=r.get("label", f"item_{i}"),
                status="UNKNOWN",
                notes=f"Evaluation error: {type(exc).__name__}",
            )
            for i, r in enumerate(rubric_to_use)
        ]


# ─────────────────────────────────────────────────────────────────────────────
# Claude Vision call
# ─────────────────────────────────────────────────────────────────────────────


def _build_prompt(rubric: list[dict]) -> str:
    rubric_lines = "\n".join(
        f"  {i + 1}. [{r['label']}] "
        f"{'(REQUIRED) ' if r.get('required') else ''}"
        f"{r.get('description', '')}"
        for i, r in enumerate(rubric)
    )
    labels_json = json.dumps([r["label"] for r in rubric])

    return f"""\
Evaluate this system design diagram against the rubric below.

RUBRIC ITEMS:
{rubric_lines}

For each rubric item, decide:
  PRESENT — clearly visible and correct in the diagram
  PARTIAL — implied or partially shown but not fully explicit
  MISSING — not present in the diagram

Score every item, even if the diagram is rough or hand-drawn.
Focus on whether the CONCEPT is represented, not artistic quality.

Return a JSON object with exactly this structure:
{{
  "scores": [
    {{"label": "<exact label from rubric>", "status": "PRESENT"|"PARTIAL"|"MISSING", "notes": "one brief sentence"}}
  ]
}}

The scores array must have exactly {len(rubric)} items, in the same order as the rubric.
Labels must be exactly: {labels_json}
Return ONLY valid JSON. No preamble. No markdown fences."""


def _call_claude_vision(
    images: list[bytes],
    rubric: list[dict],
    mime_type: str,
) -> list[DiagramScore]:
    settings = get_settings()
    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

    # Build content: one image block per image, then the text prompt
    content: list[dict] = []
    for img_bytes in images:
        b64 = base64.standard_b64encode(img_bytes).decode("ascii")
        content.append(
            {
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": mime_type,
                    "data": b64,
                },
            }
        )
    content.append({"type": "text", "text": _build_prompt(rubric)})

    start = time.perf_counter()
    try:
        response = client.messages.create(
            model=settings.anthropic_model,
            max_tokens=1024,
            system=_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": content}],
        )
    except Exception as exc:
        log.error(
            "diagram_evaluator.api_error",
            error=str(exc),
            image_count=len(images),
            rubric_count=len(rubric),
        )
        raise DiagramEvaluationError(str(exc)) from exc

    duration_ms = int((time.perf_counter() - start) * 1000)
    raw_text = response.content[0].text

    log.info(
        "diagram_evaluator.scored",
        image_count=len(images),
        rubric_count=len(rubric),
        duration_ms=duration_ms,
        input_tokens=getattr(response.usage, "input_tokens", 0),
        output_tokens=getattr(response.usage, "output_tokens", 0),
    )

    return _parse_scores(raw_text, rubric)


# ─────────────────────────────────────────────────────────────────────────────
# Response parsing
# ─────────────────────────────────────────────────────────────────────────────

_VALID_STATUSES: frozenset[str] = frozenset({"PRESENT", "PARTIAL", "MISSING"})


def _parse_scores(raw: str, rubric: list[dict]) -> list[DiagramScore]:
    text = raw.strip()

    # Strip markdown fences if present
    fenced = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if fenced:
        text = fenced.group(1).strip()

    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        log.error("diagram_evaluator.parse_error", raw=text[:200], error=str(exc))
        raise DiagramEvaluationError(f"Could not parse evaluator JSON: {exc}") from exc

    raw_scores: list[dict] = data.get("scores", [])

    # Build a lookup by label for resilience against ordering drift
    score_by_label = {s.get("label", ""): s for s in raw_scores}

    results: list[DiagramScore] = []
    for r in rubric:
        label = r.get("label", "")
        scored = score_by_label.get(label, {})
        status = scored.get("status", "UNKNOWN")
        if status not in _VALID_STATUSES:
            status = "UNKNOWN"
        results.append(
            DiagramScore(
                label=label,
                status=status,  # type: ignore[arg-type]
                notes=scored.get("notes", ""),
            )
        )

    return results


# ─────────────────────────────────────────────────────────────────────────────
# Aggregate helpers — used by session_engine to decide verdict influence
# ─────────────────────────────────────────────────────────────────────────────


def diagram_passes_minimum(scores: list[DiagramScore], rubric: list[dict]) -> bool:
    """
    True if all REQUIRED rubric items are PRESENT or PARTIAL.
    Optional items are ignored for the pass/fail decision.
    """
    required_labels = {r["label"] for r in rubric if r.get("required")}
    if not required_labels:
        # No required items — pass if any item is PRESENT
        return any(s.status == "PRESENT" for s in scores)

    score_map = {s.label: s.status for s in scores}
    return all(score_map.get(lbl, "MISSING") in ("PRESENT", "PARTIAL") for lbl in required_labels)


def diagram_summary(scores: list[DiagramScore]) -> str:
    """One-line human-readable summary for log / internal_notes."""
    counts = {"PRESENT": 0, "PARTIAL": 0, "MISSING": 0, "UNKNOWN": 0}
    for s in scores:
        counts[s.status] = counts.get(s.status, 0) + 1
    return (
        f"{counts['PRESENT']} present, "
        f"{counts['PARTIAL']} partial, "
        f"{counts['MISSING']} missing"
        + (f", {counts['UNKNOWN']} unknown" if counts["UNKNOWN"] else "")
    )
