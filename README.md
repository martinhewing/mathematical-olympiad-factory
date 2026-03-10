# ConnectionSphere Factory

![CI](https://github.com/martinhewing/connectionsphere-factory/actions/workflows/ci.yml/badge.svg)
![Python](https://img.shields.io/badge/python-3.12-blue)
![Tests](https://img.shields.io/badge/tests-57%20passing-brightgreen)
![License](https://img.shields.io/badge/license-MIT-lightgrey)

A voice-driven system design interview simulator tuned to the standard of a FAANG principal engineer interview. Provide a problem statement. The system generates the scene, teaches the relevant concepts, conducts the interview, evaluates your responses, and produces a full debrief.

Built around the curriculum of *System Design Interview — An Insider's Guide* (Volumes 1 and 2).

---

## Curriculum

The simulator covers the following problem domains:

- Scale From Zero To Millions Of Users
- Back-of-the-envelope Estimation
- A Framework For System Design Interviews
- Design A Rate Limiter
- Design Consistent Hashing
- Design A Key-value Store
- Design A Unique ID Generator In Distributed Systems
- Design A URL Shortener
- Design A Web Crawler
- Design A Notification System
- Design A News Feed System
- Design A Chat System
- Design A Search Autocomplete System
- Design YouTube
- Design Google Drive

---

## Quick Start

```bash
# 1. Install UV (skip if already installed)
curl -LsSf https://astral.sh/uv/install.sh | sh

# 2. Clone and install
git clone https://github.com/martinhewing/connectionsphere-factory
cd connectionsphere-factory
uv sync

# 3. Configure
cp .env.example .env
# Edit .env — set the three required keys (see Configuration below)

# 4. Run
uv run uvicorn connectionsphere_factory.app:app --reload --port 8391
```

Open **http://localhost:8391/docs**

---

## Configuration

Three keys are required before the application will start.

```bash
# .env
ANTHROPIC_API_KEY=sk-ant-...    # console.anthropic.com
CARTESIA_API_KEY=...             # play.cartesia.ai
FACTORY_API_KEY=...              # generate locally — see below
```

Generate `FACTORY_API_KEY`:

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

All other configuration has working defaults. See `.env.example` for the full reference.

---

## How It Works

Each session has two phases.

**Teaching phase (Alex)** — A Senior Staff Engineer walks you through the core concepts relevant to the problem before the interview begins. You can ask questions by voice. When you are ready, you hand over to the interviewer.

**Interview phase (Jordan)** — A Principal Engineer conducts a structured FAANG-style system design interview. Responses are evaluated in real time against a defined minimum bar. Probing follow-up questions are generated dynamically based on gaps in your answers. At any point you can return to Alex to revisit the teaching material.

At the end of the session a full debrief is produced covering confirmed concepts, identified gaps, and a stage-by-stage assessment.

---

## Development

**Run tests**

```bash
uv run pytest                          # all 57 tests
uv run pytest -m unit                  # fast, isolated — run while editing (~4s)
uv run pytest -m integration           # engine and store wired together
uv run pytest -m e2e                   # full HTTP flows
uv run pytest -m smoke                 # post-deploy sanity (<10s)
uv run pytest --cov=connectionsphere_factory
```

**Lint and format**

```bash
uv run ruff check .
uv run ruff format .
```

**Docker**

```bash
docker build -t factory .
docker run -p 8391:8391 --env-file .env factory
```

---

## Deployment

Merge to `main`. CI runs tests, then deploys automatically via GitHub Actions.

For first-time server provisioning: `deploy/provision.sh`

For operational reference: `docs/runbook.md`

---

## Stack

| Layer   | Tool                                       |
|---------|--------------------------------------------|
| API     | FastAPI + Scalar                           |
| AI      | Anthropic Claude                           |
| Voice   | Cartesia TTS + Deepgram STT                |
| State   | FSM + Doubly Linked List (session history) |
| Storage | PostgreSQL + Redis + Digital Ocean Spaces  |
| Build   | UV + Docker                                |
| CI/CD   | GitHub Actions                             |
| Host    | Digital Ocean VPS                          |

---

## License

MIT