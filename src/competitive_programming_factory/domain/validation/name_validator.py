"""
competitive_programming_factory/domain/validation/name_validator.py

Validates that a candidate_name is a genuine human name using Claude.

Called once at session creation — rejects gibberish before a session is
wasted on a fake name.

Rejects:
  - Random strings ("asdf", "xxxxx", "test123")
  - Placeholder text ("John Doe", "Candidate", "User", "test")
  - Offensive or clearly fake names
  - Single characters or empty strings

Returns a NameValidationResult with:
  - is_valid:   bool
  - first_name: str  — extracted, title-cased, used for personalisation throughout
  - reason:     str  — shown to the user if invalid, empty string if valid

Fail-open on Claude API errors: if validation itself fails, the session
proceeds and first_name is inferred from the raw input.

Set VALIDATE_CANDIDATE_NAMES=False in .env to bypass (useful in tests).
"""
from __future__ import annotations

import json
from dataclasses import dataclass

import anthropic

from competitive_programming_factory.config import get_settings
from competitive_programming_factory.logging import get_logger

log = get_logger(__name__)


@dataclass
class NameValidationResult:
    is_valid:   bool
    first_name: str   # e.g. "Martin" from "Martin Hewing"
    reason:     str   # empty string if valid


_SYSTEM = """\
You are a name validator. Your only job is to determine whether a given string \
is a genuine human first name or full name.

REJECT:
- Random character sequences ("asdf", "qwerty", "abc123", "aaaa")
- Placeholder names ("test", "user", "candidate", "John Doe", "Sample User")
- Single letters or digits
- Names containing special characters that are clearly not names
- Offensive or clearly fake names

ACCEPT:
- Any plausible human name from any culture, language, or writing system
- Common nicknames that are recognisably human ("Alex", "Sam", "Priya", "Kai")
- Unusual names that are plausibly real
- Names that are also common words but commonly used as names ("Joy", "Faith", "Hunter")

Return ONLY valid JSON, nothing else:
{
  "is_valid": true or false,
  "first_name": "extracted first name, title-cased — empty string if invalid",
  "reason": "brief reason if invalid, empty string if valid"
}"""


def validate_candidate_name(raw_name: str) -> NameValidationResult:
    """
    Synchronous name validation via Claude.

    Called once at session creation — latency (~500ms) is acceptable here.
    Fail-open on Claude errors so API outages don't block sessions.

    Args:
        raw_name: The candidate_name field from CreateSessionRequest

    Returns:
        NameValidationResult — check .is_valid before proceeding
    """
    settings = get_settings()
    stripped = raw_name.strip()

    # Fast-reject obvious cases without a Claude call
    if not stripped or len(stripped) < 2:
        return NameValidationResult(
            is_valid   = False,
            first_name = "",
            reason     = "Name must be at least 2 characters.",
        )

    log.info("name_validator.start", raw=stripped[:40])

    try:
        client  = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        message = client.messages.create(
            model      = settings.anthropic_model,
            max_tokens = 150,
            system     = _SYSTEM,
            messages   = [
                {"role": "user", "content": f'Validate this name: "{stripped}"'}
            ],
        )
        raw_json = message.content[0].text.strip()

        # Strip markdown fences if model slips
        if raw_json.startswith("```"):
            lines = raw_json.split("```")
            raw_json = lines[1]
            if raw_json.startswith("json"):
                raw_json = raw_json[4:]

        data = json.loads(raw_json)

    except Exception as exc:
        # Fail open — don't block session creation on validator errors
        log.warning("name_validator.error", error=str(exc))
        first = stripped.split()[0].title()
        return NameValidationResult(is_valid=True, first_name=first, reason="")

    result = NameValidationResult(
        is_valid   = bool(data.get("is_valid", False)),
        first_name = (data.get("first_name") or "").strip() or stripped.split()[0].title(),
        reason     = data.get("reason", ""),
    )
    log.info(
        "name_validator.result",
        is_valid   = result.is_valid,
        first_name = result.first_name,
    )
    return result
