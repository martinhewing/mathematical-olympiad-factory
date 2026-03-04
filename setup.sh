#!/usr/bin/env bash
# setup.sh
# Run from the repo root. Creates every directory and file in the project.
# Existing files are not overwritten — touch only sets the timestamp if the file exists.

set -euo pipefail

# ── Root config files ─────────────────────────────────────────────────────────
touch .env.example
touch .gitignore
touch .dockerignore
touch .python-version
touch Dockerfile
touch pyproject.toml
touch README.md
touch run.py

# ── GitHub Actions ────────────────────────────────────────────────────────────
mkdir -p .github/workflows
touch .github/workflows/ci.yml
touch .github/workflows/deploy.yml

# ── Deploy ────────────────────────────────────────────────────────────────────
mkdir -p deploy
touch deploy/factory.service
touch deploy/provision.sh

# ── Docs ──────────────────────────────────────────────────────────────────────
mkdir -p docs
touch docs/runbook.md

# ── Source ────────────────────────────────────────────────────────────────────
mkdir -p src/connectionsphere_factory/domain/fsm
mkdir -p src/connectionsphere_factory/domain/conversation
mkdir -p src/connectionsphere_factory/engine
mkdir -p src/connectionsphere_factory/logging
mkdir -p src/connectionsphere_factory/middleware
mkdir -p src/connectionsphere_factory/models
mkdir -p src/connectionsphere_factory/routes
mkdir -p src/connectionsphere_factory/templates

touch src/connectionsphere_factory/__init__.py
touch src/connectionsphere_factory/app.py
touch src/connectionsphere_factory/config.py
touch src/connectionsphere_factory/session_store.py

touch src/connectionsphere_factory/domain/__init__.py

touch src/connectionsphere_factory/domain/fsm/__init__.py
touch src/connectionsphere_factory/domain/fsm/states.py
touch src/connectionsphere_factory/domain/fsm/context.py
touch src/connectionsphere_factory/domain/fsm/machine.py
touch src/connectionsphere_factory/domain/fsm/visualization.py

touch src/connectionsphere_factory/domain/conversation/__init__.py
touch src/connectionsphere_factory/domain/conversation/history.py
touch src/connectionsphere_factory/domain/conversation/visualization.py

touch src/connectionsphere_factory/engine/__init__.py
touch src/connectionsphere_factory/engine/prompt_renderer.py
touch src/connectionsphere_factory/engine/session_engine.py

touch src/connectionsphere_factory/logging/__init__.py
touch src/connectionsphere_factory/logging/config.py

touch src/connectionsphere_factory/middleware/__init__.py
touch src/connectionsphere_factory/middleware/auth.py
touch src/connectionsphere_factory/middleware/rate_limit.py
touch src/connectionsphere_factory/middleware/request_logging.py

touch src/connectionsphere_factory/models/__init__.py
touch src/connectionsphere_factory/models/schemas.py

touch src/connectionsphere_factory/routes/__init__.py
touch src/connectionsphere_factory/routes/sessions.py
touch src/connectionsphere_factory/routes/stages.py
touch src/connectionsphere_factory/routes/state.py
touch src/connectionsphere_factory/routes/visualize.py

touch src/connectionsphere_factory/templates/generate_scene.j2
touch src/connectionsphere_factory/templates/generate_stage.j2
touch src/connectionsphere_factory/templates/assess_submission.j2

# ── Tests ─────────────────────────────────────────────────────────────────────
mkdir -p tests/unit
mkdir -p tests/integration
mkdir -p tests/e2e
mkdir -p tests/smoke

touch tests/__init__.py
touch tests/conftest.py

touch tests/unit/__init__.py
touch tests/unit/test_session_behaviour.py
touch tests/unit/test_security.py

touch tests/integration/__init__.py
touch tests/integration/test_session_engine.py

touch tests/e2e/__init__.py
touch tests/e2e/test_interview_flow.py

touch tests/smoke/__init__.py
touch tests/smoke/test_critical_paths.py

echo "Directory structure created."
echo "Copy file contents from the skeleton into src/connectionsphere_factory/ and tests/."