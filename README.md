<p align="center">
  <img src="docs/assets/logo.svg" alt="Competitive Programming Factory" width="64" />
</p>

<h1 align="center">Competitive Programming Factory</h1>

<p align="center">
  <strong>A voice-driven mathematical olympiad tutor, calibrated to competition and FAANG technical-interview problem-solving bar.</strong>
</p>

<p align="center">
  <a href="https://competitive-programming.connectaiml.com/docs"><img src="https://img.shields.io/badge/API_Explorer-competitive--programming.connectaiml.com%2Fdocs-c8ff00?style=for-the-badge" alt="API Explorer" /></a>
</p>
<p align="center">
  Session UI: <code>https://competitive-programming.connectaiml.com/session/{id}/interview</code>
</p>

<p align="center">
  <a href="#quick-start">Quick&nbsp;Start</a>&ensp;·&ensp;
  <a href="#how-a-session-works">How&nbsp;It&nbsp;Works</a>&ensp;·&ensp;
  <a href="#api-reference">API&nbsp;Reference</a>&ensp;·&ensp;
  <a href="#curriculum">Curriculum</a>
</p>

<p align="center">
  <img src="https://github.com/martinhewing/competitive-programming-factory/actions/workflows/ci.yml/badge.svg" alt="CI" />
  <img src="https://img.shields.io/badge/python-3.12-blue" alt="Python 3.12" />
  <img src="https://img.shields.io/badge/license-MIT-lightgrey" alt="MIT License" />
</p>

---

## What Is This?

Most competitive programming prep is reading solutions after you've given up. Competitive Programming Factory is different — you **speak** your reasoning into a live tutoring session, and two AI agents teach, probe, and score you in real time.

Give it a problem — *"Prove that every integer n ≥ 8 can be written as 3a + 5b"*, *"Find all consecutive-integer representations of 1000"*, *"State and prove Bézout's identity"* — and it runs a full session loop: concept teaching, comprehension checks, proof-rigour probes, and a detailed debrief at the end.

Built around the curriculum of *First Step to Mathematical Olympiad Problems* (Mathematical Olympiad Series, Derek Holton, Chapter 1).

### Try it now

```bash
# 1. Create a session (returns a session_id)
curl -X POST https://competitive-programming.connectaiml.com/sessions \
  -H "X-API-Key: YOUR_KEY" \
  -H "Content-Type: application/json" \
  -d '{"problem_statement": "Prove the Frobenius coin theorem for r=3, s=5", "candidate_name": "Your Name"}'

# 2. Open the session UI in your browser
#    → https://competitive-programming.connectaiml.com/session/{session_id}/interview
```

The session UI is a single-page voice interface — Alistair teaches, Imogen examines, you speak your reasoning.

---

## The Two Agents

Every session is run by two agents with distinct voices, roles, and a defined handover protocol.

### Alistair — *Tutor*

Alistair owns the **teaching phase**. Before you face the examination, he walks you through the core concepts relevant to your specific problem — the problem-solving framework, Bézout's identity, linear combinations, the stamp problem, and the Frobenius theorem. He uses analogies, flags where proofs break down, and runs a comprehension check before handing you to Imogen.

If you struggle with a concept, Alistair reteaches it with a fresh example. His bar is calibrated to Imogen's — he will not pass you through until you can articulate what Imogen will ask.

### Imogen — *Examiner*

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

**1 · Problem statement** — You provide a problem. The system selects which concepts Alistair will teach and which probes Imogen will use.

**2 · Teaching phase (Alistair)** — Alistair teaches concepts in order of complexity, from the problem-solving framework through to the Frobenius theorem. Each concept gets an explanation, a real-world analogy, and a proof warning. For provable concepts (Bézout's identity, Theorem 2, Theorem 3, the Frobenius theorem), Alistair activates the proof panel. When you say you're ready, he runs a comprehension check — if you pass, you hand over to Imogen; if not, he identifies the gap, reteaches, and checks again.

**3 · Examination phase (Imogen)** — Imogen opens with a precise mathematical statement, then asks her opening question. Your answers are assessed in real time against a defined minimum bar per stage. Imogen issues targeted follow-up probes when you miss something and has a configurable probe limit per stage. For concepts where proof-writing matters, she can request a written proof, gate her verdict on it, and score it against the curriculum rubric.

**4 · Debrief** — Every stage, every verdict, concepts confirmed, concepts missed, and the internal notes Imogen made during assessment.

---

## Proof Panel & Rubric Scoring

The proof panel activates automatically when a provable concept is reached. It shows the **reference diagram or proof-flow** (generated by Claude, cached globally) alongside a drop zone for your uploaded proof or sketch, plus the rubric Imogen will score against.

If Imogen marks a proof as required, you cannot submit your audio answer until you have uploaded your written work. Imogen scores your proof using **Claude Vision** against the curriculum rubric — each item gets **PRESENT**, **PARTIAL**, or **MISSING**. A proof that passes all required items can upgrade a PARTIAL verdict to CONFIRMED.

---

## Why This Isn't a Wrapper Around Claude

A user can open claude.ai and type *"quiz me on Bézout's identity."* Claude will do a reasonable job. So what does this system do that Claude UI cannot?

The test is simple: can someone replicate the core value by opening Claude in one tab and Cartesia's playground in another? The answer is no — because the cross-turn state tracking, multi-agent orchestration, live scoring, and proof gating are doing real work that neither tool provides alone. The product is the orchestration layer, not the API calls.

### What Claude UI cannot do

| Capability | Claude UI | Competitive Programming Factory |
|------------|-----------|----------------------------------|
| **Stateful answer accumulation across utterances** | Each message is evaluated in isolation — partial progress is discarded | Redis hot cache tracks demonstrated concepts across turns using set-union. A candidate who covers 2 concepts in turn 1 and 3 more in turn 2 passes — they never repeat themselves |
| **Multi-agent coordination with handover protocol** | One persona per conversation. Switching requires the user to re-prompt | Two agents (Alistair and Imogen) with distinct system prompts, distinct Cartesia voices, and an orchestrator that routes between them based on FSM state, concept coverage, and silence duration |
| **Real-time structured scoring with live progress** | Claude can grade after the fact but can't show "3/5 concepts covered" updating live | The evaluator reads from Redis Sets in real-time and returns per-concept verdicts (CONFIRMED / PARTIAL / MISSING) after every turn |
| **Proof gating and Vision scoring** | Cannot require a written proof before accepting an answer, cannot score a proof against a rubric | The proof panel gates Imogen's verdict on provable concepts. Claude Vision scores uploads against the curriculum rubric item-by-item |
| **Semantic turn boundaries** | Waits for the user to hit send | Streaming SSM-based STT processes audio continuously. The system determines when a turn ends based on linguistic context, not just silence duration |
| **Session history with backtracking** | Flat message list — no structured traversal | A doubly linked list tracks every stage and turn. The candidate can return to Alistair mid-session; Imogen resumes from where she left off |

### The CS concepts powering the system

**Finite State Machine (FSM)** — Every session is a state machine with defined states (`TEACH → TEACH_CHECK → REQUIREMENTS → EXAMINE → EVALUATE`) and guarded transitions. The FSM enforces the session protocol: Alistair cannot hand off to Imogen until the comprehension check passes. Imogen cannot advance a stage until the concept bar is met.

**Doubly Linked List (DLL)** — Session history is a DLL where each node is a stage containing an ordered list of turns. O(1) append at the tail for new turns. The `prev` pointer enables backtracking — when a candidate returns to Alistair, the DLL navigates backward without losing Imogen's position.

**Monotonic Accumulation over a Join-Semilattice** — The formal model for how partial answers accumulate across turns:

```
Let C = {c₁, c₂, ... cₙ}  — required concepts for a stage
Let Sₜ ⊆ C                 — concepts demonstrated at turn t

Progress after t turns: S₁ ∪ S₂ ∪ ... ∪ Sₜ
Monotone property:      demonstrated concepts never decrease
PASS condition:         ∪Sₜ = C
```

**State Space Models (SSMs)** — The voice pipeline runs on Cartesia's Ink (STT) and Sonic (TTS), both built on state space models. SSMs compress audio into a fixed-size hidden state that evolves per chunk in O(n) with constant memory, enabling true streaming transcription.

**Multi-Agent Orchestration** — The orchestrator routes between agents based on shared state:

```
┌──────────────────────────┐
│      Redis Hot Cache      │
│  concepts: {A, B, C}     │
│  silence_duration: 3s    │
│  turn_count: 4           │
└───────┬──────────┬───────┘
        │          │
   ┌────▼────┐ ┌───▼──────┐
   │ALISTAIR │ │  IMOGEN  │
   │  Tutor  │ │ Examiner │
   │Claude A │ │ Claude B │
   │Voice 01 │ │ Voice 02 │
   └─────────┘ └──────────┘
```

---

## Quick Start

### Use the live instance

```bash
# 1. Create a session
curl -X POST https://competitive-programming.connectaiml.com/sessions \
  -H "X-API-Key: YOUR_KEY" \
  -H "Content-Type: application/json" \
  -d '{"problem_statement": "Prove Theorem 2: every n >= 8 is expressible as 3a + 5b", "candidate_name": "Your Name"}'

# Response includes session_id, e.g. "a3f7c2d1"

# 2. Open the session UI
#    https://competitive-programming.connectaiml.com/session/a3f7c2d1/interview
```

API explorer: **[competitive-programming.connectaiml.com/docs](https://competitive-programming.connectaiml.com/docs)**

### Run locally

```bash
# 1. Install UV (skip if already installed)
curl -LsSf https://astral.sh/uv/install.sh | sh

# 2. Clone and install
git clone git@github.com:martinhewing/competitive-programming-factory.git
cd competitive-programming-factory
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
| `CP_DB_DSN` | Yes (prod) | PostgreSQL DSN — `postgresql://cp_user:password@localhost:5432/competitive_programming` |
| `REDIS_URL` | No | Default: `redis://localhost:6379/1` |
| `ANTHROPIC_MODEL` | No | Default: `claude-sonnet-4-20250514` |
| `PROBE_LIMIT` | No | Max follow-up probes per stage (default: 3) |
| `MAX_STAGE_N` | No | Max stages per session (default: 20) |
| `RATE_LIMIT_SESSIONS_PER_HOUR` | No | Per-key rate limit for session creation (default: 20) |
| `RATE_LIMIT_SUBMITS_PER_HOUR` | No | Per-key rate limit for answer submissions (default: 100) |

See `.env.example` for the full reference including CORS, logging, and Digital Ocean Spaces storage.

---

## API Reference

The API is fully documented in the interactive Scalar explorer at [competitive-programming.connectaiml.com/docs](https://competitive-programming.connectaiml.com/docs).

```
POST   /sessions                                  → Create session, get session_id
GET    /session/{id}/stage/1                       → Load first stage (teach phase)
POST   /session/{id}/stage/1/voice                 → Submit voice answer + optional proof scan
POST   /session/{id}/stage/1/submit                → Submit text answer (alternative)
GET    /session/{id}/state                         → Poll FSM state
GET    /session/{id}/evaluate                      → Final debrief

GET    /session/{id}/interview                     → Full candidate-facing UI
GET    /session/{id}/stage/{n}/audio/file           → Download stage audio (WAV)

GET    /session/{id}/fsm-visualize                 → FSM state diagram (SVG)
GET    /session/{id}/dll-visualize                 → Session journey diagram (SVG)
GET    /session/{id}/fsm-mermaid                   → FSM as Mermaid markup

POST   /diagrams/pregenerate                       → Warm all 8 reference diagrams
POST   /concept/{slug}/diagram/invalidate          → Force-regenerate a single diagram
```

All endpoints except `/docs` and the session UI require the `X-API-Key` header.

---

## Curriculum

The curriculum is hard-coded from *First Step to Mathematical Olympiad Problems* (Holton, Chapter 1) and covers 8 concepts, taught in order:

| # | Concept | Proof / Sketch |
|---|---------|:--------------:|
| 1 | The Problem-Solving Framework | |
| 2 | The Jug Problem: Exploration and Efficiency | |
| 3 | Bézout's Identity and Integer Linear Combinations | ✓ |
| 4 | The Consecutive Numbers Problem | ✓ |
| 5 | The Stamp Problem: Discovery by Systematic Exploration | ✓ |
| 6 | Proving the Threshold: All n ≥ 8 from 3¢ and 5¢ | ✓ |
| 7 | Generalising the Threshold: 3¢ and s¢ Stamps | ✓ |
| 8 | The Frobenius Coin Problem: General Coprime Case | ✓ |

The six provable concepts activate the proof panel automatically. Reference diagrams and proof-flow SVGs are generated by Claude on first request and cached globally (in-memory locally, Redis in production).

Mathematical notation throughout uses LaTeX — the session UI renders it via KaTeX.

### Warming the diagram cache

```bash
# Pre-generate all 8 diagrams at startup
curl -X POST -H "X-API-Key: $FACTORY_API_KEY" https://competitive-programming.connectaiml.com/diagrams/pregenerate

# Force-regenerate one diagram after a curriculum change
curl -X POST -H "X-API-Key: $FACTORY_API_KEY" https://competitive-programming.connectaiml.com/concept/bezout_identity/diagram/invalidate
```

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
| AI | Anthropic Claude (Sonnet) — reasoning, assessment, concept extraction |
| TTS | Cartesia Sonic — SSM-based speech synthesis, dual voice personas (Alistair + Imogen) |
| STT | Cartesia Ink (ink-whisper) — SSM-based streaming transcription |
| Vision | Claude Vision — proof scoring against curriculum rubric |
| State | FSM (session protocol) + DLL (turn history) + Redis Sets (concept accumulator) |
| Storage | PostgreSQL (DB: competitive_programming) + Redis (DB: 1) + Digital Ocean Spaces |
| Build | UV + Docker |
| CI/CD | GitHub Actions |
| Host | Digital Ocean VPS (port 8395) |

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
docker build -t cp-factory .
docker run -p 8395:8395 --env-file .env cp-factory
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
│   ├── agents/                     # Alistair (tutor) + Imogen (examiner)
│   ├── conversation/               # DLL-based session history
│   └── fsm/                        # Finite state machine + transitions
├── engine/
│   ├── session_engine.py           # Coordinates FSM, DLL, and Claude
│   └── prompt_renderer.py          # Jinja2 → Claude prompt pipeline
├── middleware/                      # Auth, rate limiting, request logging
├── models/                         # Pydantic schemas
├── routes/                         # sessions, stages, state, voice, visualize
├── templates/                      # Jinja2 prompt templates
└── voice/                          # TTS (Cartesia) + STT (Cartesia ink-whisper)
```

---

## License

MIT