#!/usr/bin/env python3
"""
patch_stt_word_timestamps.py
Run from repo root: python3 patch_stt_word_timestamps.py

Upgrades voice/stt.py to request word-level timestamps from Cartesia Ink,
and upgrades routes/voice.py to use structured word data instead of the
crude 8-word / 1000-byte heuristics.

What changes:
  1. stt.py  — transcribe() now passes timestamp_granularities=["word"]
               and returns a dict with transcript + words + duration
  2. voice.py — submit_voice_answer() uses word count and duration from
               the structured response instead of len(transcript.split())

Run against either factory:
  cd connectionsphere-factory && python3 patch_stt_word_timestamps.py
  cd competitive-programming-factory && python3 patch_stt_word_timestamps.py
"""
import pathlib
import sys

# ── Detect which factory we're in ─────────────────────────────────────────────
candidates = list(pathlib.Path("src").glob("*/voice/stt.py"))
if not candidates:
    sys.exit("ERROR: no voice/stt.py found under src/. Run from the repo root.")

stt_path = candidates[0]
voice_path = stt_path.parent.parent / "routes" / "voice.py"
pkg = stt_path.parent.parent.name

print(f"Factory:    {pkg}")
print(f"stt.py:     {stt_path}")
print(f"voice.py:   {voice_path}")
print()

changes = []
failures = []

# ══════════════════════════════════════════════════════════════════════════════
# PATCH 1 — stt.py: add word timestamps, return structured result
# ══════════════════════════════════════════════════════════════════════════════

stt_src = stt_path.read_text()

# Check if already patched
if "timestamp_granularities" in stt_src:
    print("  SKIP  stt.py — timestamp_granularities already present")
    changes.append("stt.py — already patched")
else:
    # Replace the transcribe call to add timestamp_granularities
    OLD_CALL = """    async with AsyncCartesia(api_key=settings.cartesia_api_key) as client:
        response = await client.stt.transcribe(
            model = "ink-whisper",
            file  = audio_file,
        )

    transcript = getattr(response, "text", None) or getattr(response, "transcript", None) or ""
    log.info("stt.transcribe.complete", chars=len(transcript))
    return transcript.strip()"""

    NEW_CALL = """    async with AsyncCartesia(api_key=settings.cartesia_api_key) as client:
        response = await client.stt.transcribe(
            model = "ink-whisper",
            file  = audio_file,
            language = "en",
            timestamp_granularities = ["word"],
        )

    transcript = getattr(response, "text", None) or getattr(response, "transcript", None) or ""
    words      = getattr(response, "words", None) or []
    duration   = getattr(response, "duration", None)

    word_count = len(words) if words else len(transcript.split())

    log.info(
        "stt.transcribe.complete",
        chars=len(transcript),
        word_count=word_count,
        duration=duration,
        has_word_timestamps=bool(words),
    )

    return {
        "transcript": transcript.strip(),
        "words": words,
        "word_count": word_count,
        "duration": duration,
    }"""

    if OLD_CALL in stt_src:
        stt_src = stt_src.replace(OLD_CALL, NEW_CALL, 1)
        stt_path.write_text(stt_src)
        print("  OK    stt.py — word timestamps + structured return")
        changes.append("stt.py — timestamp_granularities + structured return dict")
    else:
        print("  ✗     stt.py — could not find transcribe call to patch")
        print("        Manual edit required. Add to client.stt.transcribe():")
        print('            language = "en",')
        print('            timestamp_granularities = ["word"],')
        print("        And return a dict: {transcript, words, word_count, duration}")
        failures.append("stt.py — anchor not found")


# ══════════════════════════════════════════════════════════════════════════════
# PATCH 2 — voice.py: use structured STT result for quality gating
# ══════════════════════════════════════════════════════════════════════════════

if not voice_path.exists():
    print(f"  ✗     {voice_path} not found — skipping voice.py patch")
    failures.append("voice.py — file not found")
else:
    voice_src = voice_path.read_text()

    if "word_count" in voice_src and "stt_result" in voice_src:
        print("  SKIP  voice.py — structured STT already in use")
        changes.append("voice.py — already patched")
    else:
        # Patch the transcript extraction to use the new dict return
        # Pattern: transcript = await transcribe(audio_bytes, content_type=content_type)
        OLD_TRANSCRIBE = "    transcript = await transcribe(audio_bytes, content_type=content_type)"
        NEW_TRANSCRIBE = """    stt_result = await transcribe(audio_bytes, content_type=content_type)

    # Structured result from upgraded STT — use word-level data for quality gating
    if isinstance(stt_result, dict):
        transcript = stt_result["transcript"]
        word_count = stt_result["word_count"]
        duration   = stt_result.get("duration")
    else:
        # Fallback for plain string (shouldn't happen after patch)
        transcript = stt_result if isinstance(stt_result, str) else str(stt_result)
        word_count = len(transcript.split())
        duration   = None"""

        if OLD_TRANSCRIBE in voice_src:
            voice_src = voice_src.replace(OLD_TRANSCRIBE, NEW_TRANSCRIBE, 1)
            changes.append("voice.py — extract structured STT result")
        else:
            print("  ✗     voice.py — transcribe call not found")
            failures.append("voice.py — transcribe call anchor not found")

        # Patch the 8-word heuristic to use word_count
        OLD_WORD_CHECK = "    if len(transcript.split()) < 8:"
        NEW_WORD_CHECK = "    if word_count < 8:"

        if OLD_WORD_CHECK in voice_src:
            voice_src = voice_src.replace(OLD_WORD_CHECK, NEW_WORD_CHECK, 1)
            changes.append("voice.py — word count from STT (not string split)")
        else:
            print("  NOTE  voice.py — 8-word check not found (may use different threshold)")

        # Patch the 4000-char check to also log duration
        OLD_LENGTH_CHECK = "    if len(transcript.strip()) > 4000:"
        NEW_LENGTH_CHECK = """    if duration and duration < 1.0:
        nudge = (
            "That was very short — make sure your microphone is working "
            "and try again."
        )
        return {
            "verdict":               "PARTIAL",
            "feedback":              nudge,
            "probe":                 nudge,
            "transcript":            transcript,
            "concepts_demonstrated": [],
            "concepts_missing":      [],
            "next_url":              f"/session/{session_id}/stage/{stage_n}",
            "session_complete":      False,
            "input_mode":            "voice",
        }

    if len(transcript.strip()) > 4000:"""

        if OLD_LENGTH_CHECK in voice_src:
            voice_src = voice_src.replace(OLD_LENGTH_CHECK, NEW_LENGTH_CHECK, 1)
            changes.append("voice.py — duration-based guard (< 1s)")
        else:
            print("  NOTE  voice.py — 4000-char check not found")

        voice_path.write_text(voice_src)
        print("  OK    voice.py — structured STT + improved quality gating")


# ══════════════════════════════════════════════════════════════════════════════
# Summary
# ══════════════════════════════════════════════════════════════════════════════

print()
print("=" * 60)
print("SUMMARY")
print("=" * 60)
for c in changes:
    print(f"  ✓  {c}")
if failures:
    print()
    print("MANUAL FIXES NEEDED:")
    for f in failures:
        print(f"  ✗  {f}")
else:
    print()
    print(f"  All patches applied to {pkg}.")
    print()
    print("  What changed:")
    print("    stt.py   — requests word-level timestamps from Ink")
    print("               returns {transcript, words, word_count, duration}")
    print("    voice.py — uses word_count instead of len(transcript.split())")
    print("               adds duration < 1s guard (replaces byte-length heuristic)")
    print()
    print("  Test locally:")
    print("    uv run pytest -m unit")
    print()
    print("  Then commit:")
    print("    git add -A")
    print('    git commit -m "feat(voice): use word timestamps from Ink STT for quality gating"')
    print("    git push origin main")
