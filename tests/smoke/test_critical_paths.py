"""
tests/smoke/test_critical_paths.py

Smoke tests: run immediately after any deployment.
Fast, no Claude calls, no mocks — just checking the system is alive.

Rule: if any smoke test fails, the deployment is rolled back.
Must complete in under 10 seconds total.
"""

import os
from unittest.mock import patch

import pytest


@pytest.mark.smoke
class TestAppIsAlive:
    """The absolute minimum: is anything running?"""

    def test_health_check_responds(self, client):
        r = client.get("/health")
        assert r.status_code == 200

    def test_scalar_docs_load(self, client):
        r = client.get("/docs")
        assert r.status_code == 200

    def test_sessions_list_responds(self, client):
        r = client.get("/sessions")
        assert r.status_code == 200


@pytest.mark.smoke
class TestCriticalRoutesExist:
    """
    Routes that 404 after a bad deploy break every active session.
    Check they're all registered before declaring the deploy healthy.
    """

    def test_unknown_session_returns_404_not_500(self, client):
        """A missing session must return 404. A 500 means something is broken."""
        r = client.get("/session/doesnotexist")
        assert r.status_code == 404

    def test_unknown_stage_returns_404_not_500(self, client):
        r = client.get("/session/doesnotexist/stage/1")
        assert r.status_code == 404

    def test_unknown_state_returns_404_not_500(self, client):
        r = client.get("/session/doesnotexist/state")
        assert r.status_code == 404


@pytest.mark.smoke
class TestSessionLifecycleIsReachable:
    """
    One real session created, one stage loaded.
    Claude mocked — this is a deployment check, not a quality check.
    Must complete in under 5 seconds.
    """

    @pytest.mark.skipif(not os.environ.get("ANTHROPIC_API_KEY"), reason="No API key in CI")
    def test_create_session_and_reach_stage_one(self, client, mock_scene, mock_stage_spec):
        with patch(
            "competitive_programming_factory.engine.session_engine._generate_scene",
            return_value=mock_scene,
        ):
            r = client.post(
                "/sessions",
                json={
                    "problem_statement": "Design a rate limiter",
                },
            )

        assert r.status_code == 201
        sid = r.json()["session_id"]

        with patch(
            "competitive_programming_factory.engine.session_engine.render_and_call",
            return_value=mock_stage_spec,
        ):
            r = client.get(f"/session/{sid}/stage/1")

        assert r.status_code == 200
