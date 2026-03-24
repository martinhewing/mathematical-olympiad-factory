"""
competitive_programming_factory/engine/prompt_renderer.py

Renders Jinja2 prompt templates and calls the Anthropic API.
Single responsibility: template -> Claude -> parsed dict.
"""

from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any

import anthropic
from jinja2 import Environment, FileSystemLoader, StrictUndefined

from competitive_programming_factory.config import get_settings
from competitive_programming_factory.logging import get_logger

log = get_logger(__name__)

_TEMPLATE_DIR = Path(__file__).parent.parent / "templates"

_jinja_env = Environment(
    loader=FileSystemLoader(str(_TEMPLATE_DIR)),
    undefined=StrictUndefined,
    trim_blocks=True,
    lstrip_blocks=True,
    autoescape=False,
)

_client: anthropic.Anthropic | None = None


def _get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic(api_key=get_settings().anthropic_api_key)
    return _client


def render(template_name: str, context: dict[str, Any]) -> str:
    return _jinja_env.get_template(template_name).render(**context)


def call_claude(prompt: str, max_tokens: int = 2000, images: list | None = None) -> str:
    settings = get_settings()
    start = time.perf_counter()

    try:
        message = _get_client().messages.create(
            model=settings.anthropic_model,
            max_tokens=max_tokens,  # default 600 in dev
            messages=[{"role": "user", "content": prompt}],
        )
    except Exception as exc:
        log.error(
            "claude.call_failed",
            model=settings.anthropic_model,
            prompt_chars=len(prompt),
            error=str(exc),
        )
        raise

    log.info(
        "claude.call",
        model=settings.anthropic_model,
        input_tokens=getattr(message.usage, "input_tokens", 0),
        output_tokens=getattr(message.usage, "output_tokens", 0),
        duration_ms=int((time.perf_counter() - start) * 1000),
        prompt_chars=len(prompt),
    )
    return message.content[0].text


def render_and_call(
    template_name: str,
    context: dict[str, Any],
    max_tokens: int = 2000,
    images: list | None = None,
) -> dict[str, Any]:
    return _parse_json(
        call_claude(render(template_name, context), max_tokens, images=images), template_name
    )


def _parse_json(raw: str, source: str = "") -> dict[str, Any]:
    text = raw.strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    match = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if match:
        try:
            return json.loads(match.group(1).strip())
        except json.JSONDecodeError:
            pass

    log.warning(
        "claude.json_parse_failed",
        template=source,
        response_len=len(text),
        preview=text[:200],
    )
    raise ValueError(
        f"Could not parse JSON from Claude response (template: {source}). "
        f"First 300 chars: {text[:300]!r}"
    )
