<p align="center">
  <img src="docs/assets/logo.svg" alt="ConnectionSphere Factory" width="64" />
</p>

<h1 align="center">ConnectionSphere Factory</h1>

<p align="center">
  <strong>A voice-driven system design interview simulator, calibrated to FAANG principal-engineer hire bar.</strong>
</p>

<p align="center">
  <a href="https://system-design.connectaiml.com/docs"><img src="https://img.shields.io/badge/API_Explorer-system--design.connectaiml.com%2Fdocs-c8ff00?style=for-the-badge" alt="API Explorer" /></a>
</p>
<p align="center">
  Interview UI: <code>https://system-design.connectaiml.com/session/{id}/interview</code>
</p>

<p align="center">
  <a href="#quick-start">Quick&nbsp;Start</a>&ensp;·&ensp;
  <a href="#how-a-session-works">How&nbsp;It&nbsp;Works</a>&ensp;·&ensp;
  <a href="#api-reference">API&nbsp;Reference</a>&ensp;·&ensp;
  <a href="#curriculum">Curriculum</a>
</p>

<p align="center">
  <img src="https://github.com/martinhewing/connectionsphere-factory/actions/workflows/ci.yml/badge.svg" alt="CI" />
  <img src="https://img.shields.io/badge/python-3.12-blue" alt="Python 3.12" />
  <img src="https://img.shields.io/badge/tests-57%20passing-brightgreen" alt="Tests" />
  <img src="https://img.shields.io/badge/license-MIT-lightgrey" alt="MIT License" />
</p>

---

## What Is This?

Most system design prep is reading and re-reading the same diagrams. ConnectionSphere Factory is different — you **speak** your answers into a live interview simulation, and two AI agents teach, probe, and score you in real time.

Give it a problem statement — *"Design YouTube"*, *"Design a hotel reservation system"*, *"Design a rate limiter"* — and it runs a full-session loop: concept teaching, comprehension checks, FAANG-style interview probes, whiteboard diagram scoring, and a detailed debrief at the end.

Built around the curriculum of *System Design Interview — An Insider's Guide* (Volumes 1 & 2, Alex Xu).

### Try it now

```bash
# 1. Create a session (returns a session_id)
curl -X POST https://system-design.connectaiml.com/sessions \
  -H "X-API-Key: YOUR_KEY" \
  -H "Content-Type: application/json" \
  -d '{"problem_statement": "Design a URL shortener", "candidate_name": "Your Name"}'

# 2. Open the interview UI in your browser
#    → https://system-design.connectaiml.com/session/{session_id}/interview
```

The interview UI is a single-page voice interface — Alex teaches, Jordan interviews, you speak your answers.

---

## The Two Agents

Every session is run by two agents with distinct voices, roles, and a defined handover protocol.

### Alex — Senior Staff Engineer · *Tutor*

Alex owns the **teaching phase**. Before you face the interview, he walks you through the core concepts relevant to your specific problem — load balancers, database replication, caching tiers, sharding, and so on. He uses analogies, flags what interviewers test hardest, and runs a comprehension check before handing you to Jordan.

If you struggle with a concept, Alex reteaches it with a fresh example. His bar is calibrated to Jordan's — he will not pass you through until you can articulate what Jordan will ask.

### Jordan — Principal Engineer · *Interviewer*

Jordan owns the **interview**. He opens with a concrete engineering scenario, asks his opening question, and listens. When you miss something critical he issues targeted follow-up probes. When spatial understanding matters — load balancer topology, master/slave replication, stateless web tier — he can ask you to draw it on the whiteboard and will score your diagram against a rubric.

Jordan holds the session to FAANG hire-bar standards. Surface-level answers earn deeper probes. Vocabulary recall without trade-off reasoning does not pass.

> **You can switch back to Alex at any point.** When you return, Jordan resumes from where he left off.

---

## How a Session Works

```
┌────────────────┐     ┌─────────────────────┐     ┌────────────────────┐     ┌───────────┐
│  1. PROBLEM    │────▶│  2. TEACH (Alex)     │────▶│  3. INTERVIEW      │────▶│ 4. DEBRIEF│
│  You provide   │     │  Concepts + analogies│     │  (Jordan)          │     │  Full     │
│  a problem     │     │  Comprehension check │     │  Probes + diagrams │     │  breakdown│
│  statement     │     │  Pass → hand off     │     │  Verdict per stage │     │           │
└────────────────┘     └─────────────────────┘     └────────────────────┘     └───────────┘
                              ▲         │
                              │         │  ◀── You can go back
                              └─────────┘       to Alex any time
```

**1 · Problem statement** — You provide a problem. The system selects which concepts Alex will teach and which probes Jordan will use.

**2 · Teaching phase (Alex)** — Alex teaches concepts in order of complexity, from single-server setup to full distributed architecture. Each concept gets an explanation, a real-world analogy, and a probe warning. For drawable concepts (load balancer, database replication, stateless web tier, sharding, full architecture), Alex activates the whiteboard. When you say you're ready, he runs a comprehension check — if you pass, you hand over to Jordan; if not, he identifies the gap, reteaches, and checks again.

**3 · Interview phase (Jordan)** — Jordan opens with a concrete engineering context, then asks his opening question. Your answers are assessed in real time against a defined minimum bar per stage. Jordan issues targeted follow-up probes when you miss something and has a configurable probe limit per stage. For concepts where spatial understanding matters, he can request a diagram, gate his verdict on it, and score it against the curriculum rubric.

**4 · Debrief** — Every stage, every verdict, concepts confirmed, concepts missed, and the internal notes Jordan made during assessment.

---

## Whiteboard & Diagram Scoring

The whiteboard activates automatically when a drawing concept is reached. It shows the **reference architecture diagram** (generated by Claude, cached globally) alongside a drop zone for your uploaded drawing, plus the rubric Jordan will score against.

If Jordan marks a diagram as required, you cannot submit your audio answer until you have uploaded a drawing. Jordan scores your diagram using **Claude Vision** against the curriculum rubric — each item gets **PRESENT**, **PARTIAL**, or **MISSING**. A drawing that passes all required items can upgrade a PARTIAL verdict to CONFIRMED.

---

## Why This Isn't a Wrapper Around Claude

A user can open claude.ai and type *"interview me on system design."* Claude will do a reasonable job. So what does this system do that Claude UI cannot?

The test is simple: can someone replicate the core value by opening Claude in one tab and Cartesia's playground in another? The answer is no — because the cross-turn state tracking, multi-agent orchestration, live scoring, and diagram gating are doing real work that neither tool provides alone. The product is the orchestration layer, not the API calls.

### What Claude UI cannot do

| Capability | Claude UI | ConnectionSphere Factory |
|------------|-----------|--------------------------|
| **Stateful answer accumulation across utterances** | Each message is evaluated in isolation — partial progress is discarded | Redis hot cache tracks demonstrated concepts across turns using set-union. A candidate who covers 2 concepts in turn 1 and 3 more in turn 2 passes — they never repeat themselves |
| **Multi-agent coordination with handover protocol** | One persona per conversation. Switching requires the user to re-prompt | Two agents (Alex and Jordan) with distinct system prompts, distinct Cartesia voices, and an orchestrator that routes between them based on FSM state, concept coverage, and silence duration |
| **Real-time structured scoring with live progress** | Claude can grade after the fact but can't show "3/5 concepts covered" updating live | The evaluator reads from Redis Sets in real-time and returns per-concept verdicts (CONFIRMED / PARTIAL / MISSING) after every turn |
| **Diagram gating and Vision scoring** | Cannot require a drawing before accepting an answer, cannot score a drawing against a rubric | The whiteboard gates Jordan's verdict on drawable concepts. Claude Vision scores uploads against the curriculum rubric item-by-item |
| **Semantic turn boundaries** | Waits for the user to hit send | Streaming SSM-based STT processes audio continuously. The system determines when a turn ends based on linguistic context, not just silence duration |
| **Session history with backtracking** | Flat message list — no structured traversal | A doubly linked list tracks every stage and turn. The candidate can return to Alex mid-interview; Jordan resumes from where he left off |

### The CS concepts powering the system

The system is built on a set of formal structures, not just API calls stitched together.

**Finite State Machine (FSM)** — Every session is a state machine with defined states (`TEACH → TEACH_CHECK → REQUIREMENTS → SYSTEM_DESIGN → EVALUATE`) and guarded transitions. The FSM enforces the session protocol: Alex cannot hand off to Jordan until the comprehension check passes. Jordan cannot advance a stage until the concept bar is met. The FSM is visualisable at any point via the `/fsm-visualize` endpoint, which renders the current state diagram as SVG.

**Doubly Linked List (DLL)** — Session history is a DLL where each node is a stage containing an ordered list of turns. O(1) append at the tail for new turns. O(1) access to head and tail. The `prev` pointer enables backtracking — when a candidate returns to Alex, the DLL navigates backward without losing Jordan's position. The DLL is the audit trail; Redis is the accumulator. They serve different purposes.

**Monotonic Accumulation over a Join-Semilattice** — This is the formal model for how partial answers accumulate across turns. A join-semilattice is a partially ordered set where any two elements have a least upper bound (join). Here, the elements are subsets of required concepts, the join operation is set union, and the ordering is subset inclusion:

```
Let C = {c₁, c₂, ... cₙ}  — required concepts for a stage
Let Sₜ ⊆ C                 — concepts demonstrated at turn t

Progress after t turns: S₁ ∪ S₂ ∪ ... ∪ Sₜ
Monotone property:      demonstrated concepts never decrease
PASS condition:         ∪Sₜ = C
```

Redis `SADD` implements the join — it's idempotent and commutative, exactly the properties the semilattice requires. The evaluator reads `SMEMBERS` (the union of all turns), not the last turn in isolation. Without this, the system would violate monotonicity by forcing candidates to reproduce the full concept set in a single utterance.

**State Space Models (SSMs)** — The voice pipeline runs on Cartesia's Ink (STT) and Sonic (TTS), both built on state space models rather than transformers. SSMs compress audio into a fixed-size hidden state that evolves per chunk in O(n) with constant memory, rather than the O(n²) attention mechanism transformers require. This means streaming is the natural operating mode — each audio chunk updates the state incrementally, producing partial transcripts faster and more frequently than batch models. There is no KV-cache; the fixed-size state *is* the cache.

**Connectionist Temporal Classification (CTC)** — The STT decoder uses CTC to align variable-length audio input to output label sequences without explicit segmentation. This is what allows the system to transcribe speech without knowing where word boundaries are in advance.

**Multi-Agent Orchestration** — The orchestrator is the component that doesn't exist in any off-the-shelf product. It routes between agents based on shared state:

```
┌──────────────────────────┐
│      Redis Hot Cache      │
│  concepts: {A, B, C}     │
│  silence_duration: 3s    │
│  turn_count: 4           │
└───────┬──────────┬───────┘
        │          │
   ┌────▼───┐ ┌───▼────┐
   │  ALEX  │ │ JORDAN │
   │ Tutor  │ │Interviewer│
   │Claude A│ │Claude B │
   │Voice 01│ │Voice 02 │
   └────────┘ └────────┘
```

Alex reads the concept set to decide what to teach. Jordan reads the same set to decide what to probe. The orchestrator decides who speaks based on FSM state, concept gaps, and the candidate's request. This coordination through shared state is what makes it an agentic system, not a wrapper.

---

## Quick Start

### Use the live instance

```bash
# 1. Create a session
curl -X POST https://system-design.connectaiml.com/sessions \
  -H "X-API-Key: YOUR_KEY" \
  -H "Content-Type: application/json" \
  -d '{"problem_statement": "Design YouTube", "candidate_name": "Your Name"}'

# Response includes session_id, e.g. "a3f7c2d1"

# 2. Open the interview UI
#    https://system-design.connectaiml.com/session/a3f7c2d1/interview
```

API explorer: **[system-design.connectaiml.com/docs](https://system-design.connectaiml.com/docs)**

### Run locally

```bash
# 1. Install UV (skip if already installed)
curl -LsSf https://astral.sh/uv/install.sh | sh

# 2. Clone and install
git clone https://github.com/martinhewing/connectionsphere-factory
cd connectionsphere-factory
uv sync

# 3. Configure — three keys required
cp .env.example .env
# ANTHROPIC_API_KEY  → console.anthropic.com
# CARTESIA_API_KEY   → play.cartesia.ai
# FACTORY_API_KEY    → generate with: python -c "import secrets; print(secrets.token_hex(32))"

# 4. Run
PYTHONPATH=src uv run uvicorn connectionsphere_factory.app:app --reload --port 8391
```

Local API explorer: **http://localhost:8391/docs**

---

## Configuration

All configuration lives in `.env`. Three keys are required; everything else has working defaults.

| Variable | Required | Description |
|----------|----------|-------------|
| `ANTHROPIC_API_KEY` | Yes | Claude API key from console.anthropic.com |
| `CARTESIA_API_KEY` | Yes | Cartesia key from play.cartesia.ai (TTS + STT) |
| `FACTORY_API_KEY` | Yes | Your API key — generate with `python -c "import secrets; print(secrets.token_hex(32))"` |
| `ANTHROPIC_MODEL` | No | Default: `claude-sonnet-4-20250514` |
| `PROBE_LIMIT` | No | Max follow-up probes per stage (default: 3) |
| `MAX_STAGE_N` | No | Max stages per session (default: 20) |
| `RATE_LIMIT_SESSIONS_PER_HOUR` | No | Per-key rate limit for session creation (default: 20) |
| `RATE_LIMIT_SUBMITS_PER_HOUR` | No | Per-key rate limit for answer submissions (default: 100) |

See `.env.example` for the full reference including CORS, logging, and Digital Ocean Spaces storage.

---

## API Reference

The API is fully documented in the interactive Scalar explorer at [system-design.connectaiml.com/docs](https://system-design.connectaiml.com/docs). Here is the shape of a typical session:

```
POST   /sessions                                  → Create session, get session_id
GET    /session/{id}/stage/1                       → Load first stage (teach phase)
POST   /session/{id}/stage/1/voice                 → Submit voice answer + optional diagrams
POST   /session/{id}/stage/1/submit                → Submit text answer (alternative)
GET    /session/{id}/state                         → Poll FSM state
GET    /session/{id}/evaluate                      → Final debrief

GET    /session/{id}/interview                     → Full candidate-facing UI
GET    /session/{id}/stage/{n}/audio/file           → Download stage audio (WAV)

GET    /session/{id}/fsm-visualize                 → FSM state diagram (SVG)
GET    /session/{id}/dll-visualize                 → Session journey diagram (SVG)
GET    /session/{id}/fsm-mermaid                   → FSM as Mermaid markup

POST   /diagrams/pregenerate                       → Warm all 12 reference diagrams
POST   /concept/{slug}/diagram/invalidate          → Force-regenerate a single diagram
```

The candidate-facing interview UI for any session is at:
**`https://system-design.connectaiml.com/session/{id}/interview`**

All endpoints except `/docs` and the interview UI require the `X-API-Key` header.

---

## Curriculum

The curriculum is hard-coded from *System Design Interview — An Insider's Guide* and covers 12 Chapter 1 concepts, taught in order:

| # | Concept | Drawing |
|---|---------|:-------:|
| 1 | Single Server Setup | |
| 2 | Database Tier Separation | |
| 3 | Vertical vs Horizontal Scaling | |
| 4 | Load Balancer | ✓ |
| 5 | Database Replication (Master/Slave) | ✓ |
| 6 | Cache Tier | ✓ |
| 7 | Content Delivery Network | |
| 8 | Stateless Web Tier | ✓ |
| 9 | Data Centers & GeoDNS | |
| 10 | Message Queue | |
| 11 | Database Sharding | ✓ |
| 12 | Full Architecture Capstone | ✓ |

The six drawable concepts activate the whiteboard automatically. Reference SVG diagrams are generated by Claude on first request and cached globally (in-memory locally, Redis in production).

### Warming the diagram cache

```bash
# Pre-generate all 12 diagrams at startup
curl -X POST -H "X-API-Key: $FACTORY_API_KEY" https://system-design.connectaiml.com/diagrams/pregenerate

# Force-regenerate one diagram after a curriculum change
curl -X POST -H "X-API-Key: $FACTORY_API_KEY" https://system-design.connectaiml.com/concept/load_balancer/diagram/invalidate
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
| TTS | Cartesia Sonic — SSM-based speech synthesis, dual voice personas (Alex + Jordan) |
| STT | Cartesia Ink (ink-whisper) — SSM-based streaming transcription |
| Vision | Claude Vision — diagram scoring against curriculum rubric |
| State | FSM (session protocol) + DLL (turn history) + Redis Sets (concept accumulator) |
| Storage | PostgreSQL + Redis + Digital Ocean Spaces |
| Build | UV + Docker |
| CI/CD | GitHub Actions |
| Host | Digital Ocean VPS |

---

## Development

### Tests

```bash
uv run pytest                          # all 57 tests
uv run pytest -m unit                  # fast, isolated (~4s)
uv run pytest -m integration           # engine + store wired together
uv run pytest -m e2e                   # full HTTP flows
uv run pytest -m smoke                 # post-deploy sanity (<10s)
uv run pytest --cov=connectionsphere_factory
```

### Lint & format

```bash
uv run ruff check .
uv run ruff format .
```

### Docker

```bash
docker build -t factory .
docker run -p 8391:8391 --env-file .env factory
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
src/connectionsphere_factory/
├── app.py                          # FastAPI application factory
├── config.py                       # Settings from .env
├── domain/
│   ├── agents/                     # Alex (tutor) + Jordan (interviewer)
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