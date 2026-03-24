<h1 align="center">Mathematical Olympiad Factory</h1>

<p align="center">
  <strong>A voice-driven mathematical olympiad tutor, calibrated to competition and FAANG problem-solving bar.</strong>
</p>

<p align="center">
  <a href="https://math-olympiad.connectaiml.com/docs"><img src="https://img.shields.io/badge/API_Explorer-math--olympiad.connectaiml.com%2Fdocs-00cfff?style=for-the-badge" alt="API Explorer" /></a>
</p>
<p align="center">
  Session UI: <code>https://math-olympiad.connectaiml.com/session/{id}/interview</code>
</p>

<p align="center">
  <a href="#quick-start">Quick&nbsp;Start</a>&ensp;·&ensp;
  <a href="#how-a-session-works">How&nbsp;It&nbsp;Works</a>&ensp;·&ensp;
  <a href="#api-reference">API&nbsp;Reference</a>&ensp;·&ensp;
  <a href="#curriculum">Curriculum</a>&ensp;·&ensp;
  <a href="#open-source-contributions">OSS&nbsp;Contributions</a>
</p>

<p align="center">
  <img src="https://github.com/martinhewing/mathematical-olympiad-factory/actions/workflows/ci.yml/badge.svg" alt="CI" />
  <img src="https://img.shields.io/badge/python-3.12-blue" alt="Python 3.12" />
  <img src="https://img.shields.io/badge/license-MIT-lightgrey" alt="MIT License" />
</p>

---

## What Is This?

Most mathematical olympiad prep is reading solutions after you've given up. Mathematical Olympiad Factory is different — you **speak** your reasoning into a live tutoring session, and two AI agents teach, probe, and score you in real time.

Give it a problem — *"Prove that every integer n ≥ 8 can be written as 3a + 5b"*, *"Find all consecutive-integer representations of 1000"*, *"State and prove Bézout's identity"* — and it runs a full session loop: concept teaching, comprehension checks, proof-rigour probes, and a detailed debrief at the end.

Built around the curriculum of *First Step to Mathematical Olympiad Problems* (Mathematical Olympiad Series, Derek Holton, Chapter 1).

### Try it now

```bash
# 1. Create a session (returns a session_id)
curl -X POST https://math-olympiad.connectaiml.com/sessions \
  -H "X-API-Key: YOUR_KEY" \
  -H "Content-Type: application/json" \
  -d '{"problem_statement": "Prove the Frobenius coin theorem for r=3, s=5", "candidate_name": "Your Name"}'

# 2. Open the session UI in your browser
#    → https://math-olympiad.connectaiml.com/session/{session_id}/interview
```

The session UI is a single-page voice interface — Alistair teaches, Imogen examines, you speak your reasoning.

---

## The Two Agents

Every session is run by two agents with distinct voices, roles, and a defined handover protocol.

### Alistair — *Tutor* (Cartesia: Oliver)

Alistair owns the **teaching phase**. Before you face the examination, he walks you through the core concepts relevant to your specific problem — the problem-solving framework, Bézout's identity, linear combinations, the stamp problem, and the Frobenius theorem. He uses analogies, flags where proofs break down, and runs a comprehension check before handing you to Imogen.

If you struggle with a concept, Alistair reteaches it with a fresh example. His bar is calibrated to Imogen's — he will not pass you through until you can articulate what Imogen will ask.

### Imogen — *Examiner* (Cartesia: Evie)

Imogen owns the **examination**. She opens with a precise mathematical statement, asks her opening question, and listens. When you hand-wave a proof step she issues targeted follow-up probes. When spatial or structural understanding matters — the achievability table, the factorisation argument, the inductive step — she can ask you to write it out and will score your work against a rubric.

Imogen holds the session to competition and FAANG problem-solving bar. Correct answers without justification earn deeper probes. Conjectures stated without proof do not pass.

> **You can switch back to Alistair at any point.** When you return, Imogen resumes from where she left off.

---

## How a Session Works

```
┌────────────────┐     ┌─────────────────────┐     ┌────────────────────┐     ┌───────────┐
│  1. PROBLEM    │────▶│  2. TEACH (Alistair) │────▶│  3. EXAMINE        │────▶│ 4. DEBRIEF│
│  You provide   │     │  Concepts + analogies│     │  (Imogen)          │     │  Full     │
│  a problem     │     │  Comprehension check │     │  Probes + proofs   │     │  breakdown│
│  statement     │     │  Pass → hand off     │     │  Verdict per stage │     │           │
└────────────────┘     └─────────────────────┘     └────────────────────┘     └───────────┘
                              ▲         │
                              │         │  ◀── You can go back
                              └─────────┘       to Alistair any time
```

**1 · Problem statement** — You provide a problem. All 8 Holton Chapter 1 concepts are always taught in full — the curriculum is a linear progression, not problem-filtered.

**2 · Teaching phase (Alistair)** — Alistair teaches concepts in order of complexity, from the problem-solving framework through to the Frobenius theorem. Each concept gets an explanation, a real-world analogy, and a proof warning. For provable concepts (Bézout's identity, Theorem 2, Theorem 3, the Frobenius theorem), Alistair activates the proof panel. When you say you're ready, he runs a comprehension check — if you pass, you hand over to Imogen; if not, he identifies the gap, reteaches, and checks again.

**3 · Examination phase (Imogen)** — Imogen opens with a precise mathematical statement, then asks her opening question. Your answers are assessed in real time against a defined minimum bar per stage. Imogen issues targeted follow-up probes when you miss something and has a configurable probe limit per stage. For concepts where proof-writing matters, she can request a written proof, gate her verdict on it, and score it against the curriculum rubric.

**4 · Debrief** — Every stage, every verdict, concepts confirmed, concepts missed, and the internal notes Imogen made during assessment.

---

## Proof Panel & Written Work

The proof panel is **always visible** at every stage — written work, proof sketches, and diagrams can be uploaded at any point in the session, during both teaching and examination. This reflects the dual oral-and-written focus of the platform.

For provable concepts (`solicit_drawing=True` in the curriculum), the panel activates with a required rubric. Imogen scores uploaded work using **Claude Vision** against the rubric — each item gets **PRESENT**, **PARTIAL**, or **MISSING**. A proof that passes all required items can upgrade a PARTIAL verdict to CONFIRMED.

For all other concepts the panel remains in optional mode — upload anything useful and Imogen will factor it in.

---

## Mathematical Notation

The session UI renders all mathematical notation using **KaTeX**. Problem statements, examination questions, probes, and feedback all use LaTeX delimiters (`$...$` for inline, `$$...$$` for display math).

The platform handles notation in two directions:

- **Display (UI)** — KaTeX renders `$...$` after every dynamic content injection. Problem statements are auto-converted server-side (e.g. `n >= 8` → `$n \geq 8$`) before the page is served.
- **Speech (TTS)** — LaTeX is stripped before passing text to Cartesia Sonic. `$n \geq 8$` becomes *"n greater than or equal to 8"* in audio via `_strip_latex()` — a ~40-line regex preprocessor that converts LaTeX notation to natural speech. All Claude templates output LaTeX notation so display and speech paths are always in sync.

---

## Voice Pipeline

The voice pipeline uses **Cartesia Sonic** (TTS) and **Cartesia Ink** (STT), both built on state space models (SSMs).

### Speech-to-Text (STT) — Ink

Candidate voice answers are transcribed by Cartesia Ink (`ink-whisper`) with **word-level timestamps** enabled:

```python
response = await client.stt.transcribe(
    model="ink-whisper",
    file=audio_file,
    language="en",
    timestamp_granularities=["word"],
)
```

The structured response (`{transcript, words, word_count, duration}`) drives quality gating:

- **Word count** — answers with fewer than 8 words are treated as mic noise and return a soft nudge without affecting the session state
- **Duration** — audio under 1.0 second triggers a short-recording guard
- **Transcript length** — answers over 4000 characters are rejected to prevent token overflow

This replaces our earlier heuristic approach of gating on `len(audio_bytes)` and `len(transcript.split())`, giving us structured signal from the model instead of string-splitting guesswork.

### Text-to-Speech (TTS) — Sonic

Interviewer speech is generated by Cartesia Sonic with dual voice personas:

- **Alistair** (tutor) — Cartesia voice: Oliver
- **Imogen** (examiner) — Cartesia voice: Evie

Voice switching happens per-agent based on FSM state. LaTeX is normalised to natural speech via `_strip_latex()` before every TTS call.

---

## Why This Isn't a Wrapper Around Claude

A user can open claude.ai and type *"quiz me on Bézout's identity."* Claude will do a reasonable job. So what does this system do that Claude UI cannot?

The test is simple: can someone replicate the core value by opening Claude in one tab and Cartesia's playground in another? The answer is no — because the cross-turn state tracking, multi-agent orchestration, live scoring, and proof gating are doing real work that neither tool provides alone. The product is the orchestration layer, not the API calls.

| Capability | Claude UI | Mathematical Olympiad Factory |
|------------|-----------|-------------------------------|
| **Stateful answer accumulation** | Each message evaluated in isolation | Redis tracks demonstrated concepts across turns via set-union |
| **Multi-agent coordination** | One persona per conversation | Two agents with distinct voices, orchestrated by FSM state |
| **Real-time structured scoring** | Can grade after the fact | Per-concept verdicts (CONFIRMED / PARTIAL / MISSING) after every turn |
| **Proof gating + Vision scoring** | Cannot gate on written proof | Claude Vision scores uploads against curriculum rubric |
| **LaTeX rendering + TTS normalisation** | No display/speech separation | KaTeX for display; `_strip_latex()` for speech |
| **Session history with backtracking** | Flat message list | DLL with O(1) append and backward traversal |

### The CS concepts powering the system

**Finite State Machine (FSM)** — Every session is a state machine with defined states and guarded transitions. The FSM enforces the session protocol: Alistair cannot hand off to Imogen until the comprehension check passes.

**Doubly Linked List (DLL)** — Session history is a DLL where each node is a stage containing an ordered list of turns. The `prev` pointer enables backtracking without losing Imogen's position.

**Monotonic Accumulation over a Join-Semilattice** — Partial answers accumulate across turns. Redis `SADD` implements the join — idempotent and commutative. The evaluator reads `SMEMBERS` (the union of all turns), not the last turn in isolation.

**State Space Models (SSMs)** — Cartesia's Ink and Sonic compress audio into a fixed-size hidden state that evolves per chunk in O(n) with constant memory, enabling true streaming.

---

## Quick Start

### Use the live instance

```bash
# 1. Create a session
curl -X POST https://math-olympiad.connectaiml.com/sessions \
  -H "X-API-Key: YOUR_KEY" \
  -H "Content-Type: application/json" \
  -d '{"problem_statement": "Prove Theorem 2: every n >= 8 is expressible as 3a + 5b", "candidate_name": "Your Name"}'

# 2. Open the session UI
#    https://math-olympiad.connectaiml.com/session/{session_id}/interview
```

API explorer: **[math-olympiad.connectaiml.com/docs](https://math-olympiad.connectaiml.com/docs)**

### Run locally

```bash
# 1. Install UV
curl -LsSf https://astral.sh/uv/install.sh | sh

# 2. Clone and install
git clone git@github.com:martinhewing/mathematical-olympiad-factory.git
cd mathematical-olympiad-factory
uv sync

# 3. Configure — three keys required
cp .env.example .env
# ANTHROPIC_API_KEY  → console.anthropic.com
# CARTESIA_API_KEY   → play.cartesia.ai
# FACTORY_API_KEY    → generate with: python -c "import secrets; print(secrets.token_hex(32))"

# 4. Run
PYTHONPATH=src uv run uvicorn competitive_programming_factory.app:app --reload --port 8395
```

Local API explorer: **http://localhost:8395/docs**

---

## Configuration

All configuration lives in `.env`. Three keys are required; everything else has working defaults.

| Variable | Required | Description |
|----------|----------|-------------|
| `ANTHROPIC_API_KEY` | Yes | Claude API key from console.anthropic.com |
| `CARTESIA_API_KEY` | Yes | Cartesia key from play.cartesia.ai (TTS + STT) |
| `FACTORY_API_KEY` | Yes | Your API key — generate with `python -c "import secrets; print(secrets.token_hex(32))"` |
| `CP_DB_DSN` | Yes (prod) | PostgreSQL DSN |
| `REDIS_URL` | No | Default: `redis://localhost:6379/1` |
| `ANTHROPIC_MODEL` | No | Default: `claude-sonnet-4-20250514` |
| `PROBE_LIMIT` | No | Max follow-up probes per stage (default: 3) |
| `MAX_STAGE_N` | No | Max stages per session (default: 20) |

See `.env.example` for the full reference.

---

## API Reference

Full interactive documentation at [math-olympiad.connectaiml.com/docs](https://math-olympiad.connectaiml.com/docs).

```
POST   /sessions                                  → Create session
GET    /session/{id}/stage/1                       → Load first stage
POST   /session/{id}/stage/1/voice                 → Submit voice answer + optional proof
POST   /session/{id}/stage/1/submit                → Submit text answer
GET    /session/{id}/state                         → Poll FSM state
GET    /session/{id}/evaluate                      → Final debrief
GET    /session/{id}/interview                     → Candidate-facing UI
GET    /session/{id}/stage/{n}/audio/file           → Download stage audio
POST   /diagrams/pregenerate                       → Warm all 8 reference diagrams
```

All endpoints except `/docs` and the session UI require the `X-API-Key` header.

---

## Curriculum

Hard-coded from *First Step to Mathematical Olympiad Problems* (Holton, Chapter 1). Eight concepts, always taught in full, in order.

| # | Concept | Proof |
|---|---------|:-----:|
| 1 | The Problem-Solving Framework | |
| 2 | The Jug Problem: Exploration and Efficiency | |
| 3 | Bézout's Identity and Integer Linear Combinations | ✓ |
| 4 | The Consecutive Numbers Problem | ✓ |
| 5 | The Stamp Problem: Discovery by Systematic Exploration | ✓ |
| 6 | Proving the Threshold: All n ≥ 8 from 3¢ and 5¢ | ✓ |
| 7 | Generalising the Threshold: 3¢ and s¢ Stamps | ✓ |
| 8 | The Frobenius Coin Problem: General Coprime Case | ✓ |

The six provable concepts activate the proof panel with a required rubric.

---

## Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                        FastAPI + Scalar                          │
│  /sessions  /stage  /voice  /interview  /evaluate  /visualize   │
└────────┬──────────┬──────────┬──────────┬──────────┬────────────┘
         │          │          │          │          │
    ┌────▼────┐ ┌───▼───┐ ┌───▼────┐ ┌───▼───┐ ┌───▼────┐
    │ Session │ │  FSM  │ │ Claude │ │  TTS  │ │  STT   │
    │ Engine  │ │       │ │(Sonnet)│ │Cartesia│ │Cartesia│
    └────┬────┘ └───┬───┘ └───┬────┘ └───────┘ └────────┘
         │          │         │
    ┌────▼──────────▼─────────▼────┐
    │     Domain Layer             │
    │  FSM · DLL · Agents · Rubric │
    └──────────────┬───────────────┘
                   │
    ┌──────────────▼───────────────┐
    │     Storage                  │
    │  PostgreSQL · Redis · Spaces │
    └──────────────────────────────┘
```

| Layer | Tool |
|-------|------|
| API | FastAPI + Scalar |
| AI | Anthropic Claude (Sonnet) |
| TTS | Cartesia Sonic — dual voice personas (Alistair/Oliver + Imogen/Evie) |
| STT | Cartesia Ink — word-level timestamps for quality gating |
| Vision | Claude Vision — proof scoring against curriculum rubric |
| Math | KaTeX (display) + `_strip_latex()` (speech normalisation) |
| State | FSM + DLL + Redis Sets (concept accumulator) |
| Storage | PostgreSQL + Redis + Digital Ocean Spaces |
| Build | UV + Docker |
| CI/CD | GitHub Actions |
| Host | Digital Ocean VPS |

---

## Open Source Contributions

Building this platform exposed friction in the voice AI ecosystem. We document and upstream those findings as part of a structured open source contribution programme.

**Contribution design documents:** [oss.connectaiml.com](https://oss.connectaiml.com)

Current proposals:

| ID | Target | Status | Summary |
|----|--------|--------|---------|
| CSP-001 | [cartesia-ai/cartesia-python](https://github.com/cartesia-ai/cartesia-python) | Drafted | Text preprocessing hook for TTS — our `_strip_latex()` as evidence |
| CSP-002 | Internal | Shipped | Word-level timestamps from Ink STT for quality gating |
| CSP-003 | [KoljaB/RealtimeSTT](https://github.com/KoljaB/RealtimeSTT) | Planned | Cartesia Ink engine implementation |
| CSP-004 | [KoljaB/RealtimeTTS](https://github.com/KoljaB/RealtimeTTS) | Planned | Cartesia Sonic engine implementation |
| CSP-005 | [snakers4/silero-vad](https://github.com/snakers4/silero-vad) | Candidate | Cartesia Ink + VAD integration example |
| CSP-006 | [livekit/agents](https://github.com/livekit/agents) | Candidate | Multi-voice persona support in Cartesia plugin |

Each proposal follows a fix-first-then-upstream pattern: identify friction → build a local workaround → adopt existing SDK features → file an issue or PR for the remaining gap with working code as evidence.

---

## Development

### Tests

```bash
uv run pytest                          # all tests
uv run pytest -m unit                  # fast, isolated (~4s)
uv run pytest -m integration           # engine + store wired together
uv run pytest -m e2e                   # full HTTP flows
uv run pytest -m smoke                 # post-deploy sanity (<10s)
uv run pytest --cov=competitive_programming_factory
```

### Lint & format

```bash
uv run ruff check .
uv run ruff format .
```

### Docker

```bash
docker build -t math-olympiad-factory .
docker run -p 8395:8395 --env-file .env math-olympiad-factory
```

---

## Deployment

Merge to `main` — CI runs the full test suite, then deploys automatically via GitHub Actions.

| Task | Reference |
|------|-----------|
| First-time server provisioning | `deploy/provision.sh` |
| Operational runbook | `docs/runbook.md` |

---

## Project Structure

```
src/competitive_programming_factory/
├── app.py                          # FastAPI application factory
├── config.py                       # Settings from .env
├── curriculum.py                   # Holton Chapter 1 — 8 concepts
├── domain/
│   ├── agents/                     # Alistair (tutor/Oliver) + Imogen (examiner/Evie)
│   ├── conversation/               # DLL-based session history
│   └── fsm/                        # Finite state machine + transitions
├── engine/
│   ├── session_engine.py           # Coordinates FSM, DLL, and Claude
│   ├── teach_spec.py               # Linear curriculum selector (all 8 concepts)
│   └── prompt_renderer.py          # Jinja2 → Claude prompt pipeline
├── routes/
│   ├── voice.py                    # TTS, STT, LaTeX normalisation, interview UI
│   └── ...                         # sessions, stages, state, visualize, diagrams
├── templates/                      # Jinja2 prompt templates
└── voice/
    ├── tts.py                      # Cartesia Sonic — stream + generate modes
    └── stt.py                      # Cartesia Ink — word timestamps + structured result
```

---

## License

MIT