# ConnectionSphere Factory

![CI](https://github.com/martinhewing/connectionsphere-factory/actions/workflows/ci.yml/badge.svg)
![Python](https://img.shields.io/badge/python-3.12-blue)
![Tests](https://img.shields.io/badge/tests-57%20passing-brightgreen)
![License](https://img.shields.io/badge/license-MIT-lightgrey)

A voice-driven system design interview simulator. Give it a problem statement.
It generates the scene, asks the questions, evaluates your answers, and gives you
a debrief — at the standard of a FAANG principal engineer interview.

Tuned against *System Design Interview Vol. 2* and *OOD Interview* (ByteByteGo).

---

## Quick start

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
uv run uvicorn factory.app:app --reload --port 8391
```

Open **http://localhost:8391/docs**

---

## Configuration

Three keys are required before the application will do anything useful.

```bash
# .env

ANTHROPIC_API_KEY=sk-ant-...          # console.anthropic.com
CARTESIA_API_KEY=...                   # play.cartesia.ai
FACTORY_API_KEY=...                    # generate locally — see below
```

Generate `FACTORY_API_KEY`:

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

All other configuration has working defaults. See `.env.example` for the full reference.

---

## Development

**Run tests**

```bash
uv run pytest                   # all 57 tests
uv run pytest -m unit           # fast, isolated — run while editing (~4s)
uv run pytest -m integration    # engine and store wired together
uv run pytest -m e2e            # full HTTP flows
uv run pytest -m smoke          # post-deploy sanity (<10s)
uv run pytest --cov=factory     # with coverage report
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

Merge to `main`. CI runs, then deploys automatically via GitHub Actions.

For first-time server provisioning: `deploy/provision.sh`  
For operational reference: `docs/runbook.md`

---

## Stack

| Layer | Tool |
|---|---|
| API | FastAPI + Scalar |
| AI | Anthropic Claude |
| Voice | Cartesia TTS + Deepgram STT |
| State | FSM + Doubly Linked List (session history) |
| Storage | PostgreSQL + Redis + Digital Ocean Spaces |
| Build | UV + Docker |
| CI/CD | GitHub Actions |
| Host | Digital Ocean VPS |