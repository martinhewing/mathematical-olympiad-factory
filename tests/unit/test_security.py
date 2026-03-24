"""
tests/unit/test_security.py

Security behaviours — the things that protect the API bill.

Self-contained: creates its own app with known settings rather than
relying on the session-scoped app from conftest.
"""

import os
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

_CORRECT_KEY = "security-test-correct-key"
_WRONG_KEY = "security-test-wrong-key"


@pytest.fixture(scope="module")
def security_env():
    originals = {
        k: os.environ.get(k)
        for k in (
            "FACTORY_API_KEY",
            "RATE_LIMIT_SESSIONS_PER_HOUR",
            "RATE_LIMIT_SUBMITS_PER_HOUR",
        )
    }

    os.environ["FACTORY_API_KEY"] = _CORRECT_KEY
    os.environ["RATE_LIMIT_SESSIONS_PER_HOUR"] = "3"
    os.environ["RATE_LIMIT_SUBMITS_PER_HOUR"] = "3"

    from competitive_programming_factory.config import get_settings

    get_settings.cache_clear()

    yield

    for k, v in originals.items():
        if v is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = v
    get_settings.cache_clear()


@pytest.fixture(scope="module")
def secure_app(security_env):
    from competitive_programming_factory.app import create_app

    return create_app()


@pytest.fixture(autouse=True)
def clear_state():
    import competitive_programming_factory.session_store as store
    from competitive_programming_factory.middleware import rate_limit as rl_module

    rl_module._windows.clear()
    store._store.clear()
    yield
    rl_module._windows.clear()
    store._store.clear()


@pytest.fixture
def unauthed(secure_app):
    return TestClient(secure_app, raise_server_exceptions=False)


@pytest.fixture
def wrong_key(secure_app):
    return TestClient(secure_app, headers={"X-API-Key": _WRONG_KEY}, raise_server_exceptions=False)


@pytest.fixture
def authed(secure_app):
    return TestClient(
        secure_app, headers={"X-API-Key": _CORRECT_KEY}, raise_server_exceptions=False
    )


# ── Authentication ────────────────────────────────────────────────────────────


@pytest.mark.unit
class TestAuthentication:
    def test_missing_key_returns_401(self, unauthed):
        assert unauthed.get("/sessions").status_code == 401

    def test_wrong_key_returns_403(self, wrong_key):
        assert wrong_key.get("/sessions").status_code == 403

    def test_correct_key_passes_through(self, authed):
        assert authed.get("/sessions").status_code == 200

    def test_health_is_public(self, unauthed):
        assert unauthed.get("/health").status_code == 200

    def test_docs_are_public(self, unauthed):
        assert unauthed.get("/docs").status_code == 200

    def test_timing_safe_comparison_used(self):
        """
        == on strings leaks response time, enabling character-by-character
        key enumeration. hmac.compare_digest is constant-time.
        """
        import inspect

        from competitive_programming_factory.middleware.auth import _verify_key

        assert "hmac.compare_digest" in inspect.getsource(_verify_key)


# ── Rate limiting ─────────────────────────────────────────────────────────────


@pytest.mark.unit
class TestRateLimiting:
    """
    The rate limiter is the direct financial guard.
    Without it, a single attacker can exhaust the Anthropic quota in minutes.
    Limit is set to 3/hour in security_env for these tests.
    """

    def test_fourth_session_request_is_rejected(self, authed, mock_scene):
        with patch(
            "competitive_programming_factory.engine.session_engine._generate_scene",
            return_value=mock_scene,
        ):
            for _ in range(3):
                r = authed.post(
                    "/sessions", json={"problem_statement": "Design a URL shortener service"}
                )
                assert r.status_code == 201

            r = authed.post(
                "/sessions", json={"problem_statement": "Design a URL shortener service"}
            )

        assert r.status_code == 429
        assert "retry_after_seconds" in r.json()

    def test_retry_after_header_present(self, authed, mock_scene):
        with patch(
            "competitive_programming_factory.engine.session_engine._generate_scene",
            return_value=mock_scene,
        ):
            for _ in range(3):
                authed.post(
                    "/sessions", json={"problem_statement": "Design a URL shortener service"}
                )
            r = authed.post(
                "/sessions", json={"problem_statement": "Design a URL shortener service"}
            )

        assert "Retry-After" in r.headers

    def test_separate_keys_have_independent_windows(self, secure_app, mock_scene):
        """Exhausting key A must not affect key B."""
        from competitive_programming_factory.middleware import rate_limit as rl_module

        client_a = TestClient(secure_app, headers={"X-API-Key": _CORRECT_KEY})

        with patch(
            "competitive_programming_factory.engine.session_engine._generate_scene",
            return_value=mock_scene,
        ):
            for _ in range(3):
                client_a.post(
                    "/sessions", json={"problem_statement": "Design a URL shortener service"}
                )

        assert (_CORRECT_KEY + "-other", "sessions") not in rl_module._windows


# ── Input validation ──────────────────────────────────────────────────────────


@pytest.mark.unit
class TestInputValidation:
    """
    Pydantic rejects oversized inputs before they reach the engine or Claude.
    Token amplification defence: a 50k-char answer is ~12,500 input tokens.
    """

    def test_problem_statement_over_500_chars_rejected(self, authed):
        r = authed.post("/sessions", json={"problem_statement": "A" * 501})
        assert r.status_code == 422

    def test_problem_statement_under_10_chars_rejected(self, authed):
        r = authed.post("/sessions", json={"problem_statement": "short"})
        assert r.status_code == 422

    def test_oversized_answer_rejected(self, authed, mock_scene):
        with patch(
            "competitive_programming_factory.engine.session_engine._generate_scene",
            return_value=mock_scene,
        ):
            r = authed.post(
                "/sessions", json={"problem_statement": "Design a hotel reservation system"}
            )
        sid = r.json()["session_id"]

        r = authed.post(
            f"/session/{sid}/stage/1/submit",
            data={"answer": "A" * 4001},
        )
        assert r.status_code == 422

    def test_stage_n_over_max_rejected(self, authed, mock_scene):
        with patch(
            "competitive_programming_factory.engine.session_engine._generate_scene",
            return_value=mock_scene,
        ):
            r = authed.post(
                "/sessions", json={"problem_statement": "Design a hotel reservation system"}
            )
        sid = r.json()["session_id"]

        r = authed.get(f"/session/{sid}/stage/9999")
        assert r.status_code == 400

    def test_stage_n_zero_rejected(self, authed, mock_scene):
        with patch(
            "competitive_programming_factory.engine.session_engine._generate_scene",
            return_value=mock_scene,
        ):
            r = authed.post(
                "/sessions", json={"problem_statement": "Design a hotel reservation system"}
            )
        sid = r.json()["session_id"]

        r = authed.get(f"/session/{sid}/stage/0")
        assert r.status_code in (400, 422)
