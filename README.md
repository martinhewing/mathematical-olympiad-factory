<p align="center">
  <img src="docs/assets/logo.svg" alt="ConnectionSphere Factory" width="64" />
</p>

<h1 align="center">ConnectionSphere Factory</h1>

<p align="center">
  <strong>A voice-driven system design interview simulator, calibrated to FAANG principal-engineer hire bar.</strong>
</p>

<p align="center">
  <a href="https://system-design.connectaiml.com">Live&nbsp;Demo</a>&ensp;·&ensp;
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

**Try it now →** [system-design.connectaiml.com](https://system-design.connectaiml.com)

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

## Quick Start

**Live instance** — no setup needed: **[system-design.connectaiml.com](https://system-design.connectaiml.com)**

**Run locally:**

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
| AI | Anthropic Claude (Sonnet) |
| Voice | Cartesia TTS + Deepgram STT |
| Vision | Claude Vision (diagram scoring) |
| State | FSM + Doubly Linked List (session history) |
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