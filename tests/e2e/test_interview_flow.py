"""
tests/e2e/test_interview_flow.py

End-to-end tests: full HTTP flows through the FastAPI app.
Claude is mocked — testing API contract, routing, HTML rendering, HTMX fragments.

Testing:
  - Complete 3-stage session from POST /sessions to GET /evaluate
  - Assessment fragment contains the verdict the client needs
  - Flagged state is reachable and renderable via HTTP
  - FSM and DLL visualisation endpoints return renderable content
"""

import pytest
from unittest.mock import patch


@pytest.mark.e2e
class TestCompleteSessionFlow:
    """
    A candidate starts a session, answers three stages, reaches evaluation.
    Every HTTP hop must return the right shape for the next hop to work.
    """

    def _create_session(self, client, mock_scene):
        with patch("competitive_programming_factory.engine.session_engine._generate_scene", return_value=mock_scene):
            r = client.post("/sessions", json={
                "problem_statement": "Design a notification system",
                "candidate_name":    "Test Candidate",
                "candidate_level":   "senior",
            })
        assert r.status_code == 201
        return r.json()

    def test_session_creation_returns_stage_url(self, client, mock_scene):
        data = self._create_session(client, mock_scene)
        assert "stage_url" in data
        assert data["stage_url"].startswith("/session/")
        assert data["stage_url"].endswith("/stage/1")

    def test_stage_page_renders_opening_question(
        self, client, mock_scene, mock_stage_spec
    ):
        data = self._create_session(client, mock_scene)
        sid  = data["session_id"]

        with patch("competitive_programming_factory.engine.session_engine.render_and_call", return_value=mock_stage_spec):
            r = client.get(f"/session/{sid}/stage/1")

        assert r.status_code == 200
        assert mock_stage_spec["opening_question"] in r.text

    def test_stage_page_embeds_session_scene(
        self, client, mock_scene, mock_stage_spec
    ):
        """The interviewer scene must be visible on every stage page."""
        data = self._create_session(client, mock_scene)
        sid  = data["session_id"]

        with patch("competitive_programming_factory.engine.session_engine.render_and_call", return_value=mock_stage_spec):
            r = client.get(f"/session/{sid}/stage/1")

        assert mock_scene["scene"][:40] in r.text

    def test_confirmed_submission_returns_next_stage_url(
        self, client, mock_scene, mock_stage_spec, mock_confirmed_assessment
    ):
        data = self._create_session(client, mock_scene)
        sid  = data["session_id"]

        with patch("competitive_programming_factory.engine.session_engine.get_or_generate_stage", return_value=mock_stage_spec), \
             patch("competitive_programming_factory.engine.session_engine.render_and_call", return_value=mock_confirmed_assessment):
            r = client.post(
                f"/session/{sid}/stage/1/submit",
                data={"answer": "I would clarify the scale first."},
            )

        assert r.status_code == 200
        body = r.json()
        assert body["verdict"]  == "CONFIRMED"
        assert body["next_url"] == f"/session/{sid}/stage/2"

    def test_partial_submission_returns_probe_question(
        self, client, mock_scene, mock_stage_spec, mock_partial_assessment
    ):
        data = self._create_session(client, mock_scene)
        sid  = data["session_id"]

        with patch("competitive_programming_factory.engine.session_engine.get_or_generate_stage", return_value=mock_stage_spec), \
             patch("competitive_programming_factory.engine.session_engine.render_and_call", return_value=mock_partial_assessment):
            r = client.post(
                f"/session/{sid}/stage/1/submit",
                data={"answer": "I would use a database."},
            )

        body = r.json()
        assert body["verdict"] == "PARTIAL"
        assert body["probe"]   is not None
        assert len(body["probe"]) > 10

    def test_three_confirmed_stages_reaches_evaluate(
        self, client, mock_scene, mock_stage_spec, mock_confirmed_assessment
    ):
        """The full happy path: 3 confirmed stages → evaluate URL."""
        data = self._create_session(client, mock_scene)
        sid  = data["session_id"]

        last_next_url = None
        for stage_n in range(1, 4):
            with patch("competitive_programming_factory.engine.session_engine.get_or_generate_stage", return_value=mock_stage_spec), \
                 patch("competitive_programming_factory.engine.session_engine.render_and_call", return_value=mock_confirmed_assessment):
                r = client.post(
                    f"/session/{sid}/stage/{stage_n}/submit",
                    data={"answer": "Good answer."},
                )
            last_next_url = r.json()["next_url"]

        assert last_next_url == f"/session/{sid}/evaluate"

    def test_evaluate_page_is_renderable_after_session_complete(
        self, client, mock_scene, mock_stage_spec, mock_confirmed_assessment
    ):
        data = self._create_session(client, mock_scene)
        sid  = data["session_id"]

        for stage_n in range(1, 4):
            with patch("competitive_programming_factory.engine.session_engine.get_or_generate_stage", return_value=mock_stage_spec), \
                 patch("competitive_programming_factory.engine.session_engine.render_and_call", return_value=mock_confirmed_assessment):
                client.post(
                    f"/session/{sid}/stage/{stage_n}/submit",
                    data={"answer": "Good answer."},
                )

        r = client.get(f"/session/{sid}/evaluate")
        assert r.status_code == 200
        assert "Session Complete" in r.text


@pytest.mark.e2e
class TestVisualisationEndpoints:
    """
    The FSM and DLL diagrams are embedded in Scalar.
    They must return renderable content — SVG or HTML fallback.
    A 500 here breaks the candidate's session view.
    """

    def test_fsm_visualize_returns_renderable_content(self, client, mock_scene):
        with patch("competitive_programming_factory.engine.session_engine._generate_scene", return_value=mock_scene):
            r = client.post("/sessions", json={"problem_statement": "Design a cache"})
        sid = r.json()["session_id"]

        r = client.get(f"/session/{sid}/fsm-visualize")
        assert r.status_code == 200
        assert r.headers["content-type"] in (
            "image/svg+xml",
            "text/html; charset=utf-8",
        )

    def test_dll_visualize_returns_renderable_content(self, client, mock_scene):
        with patch("competitive_programming_factory.engine.session_engine._generate_scene", return_value=mock_scene):
            r = client.post("/sessions", json={"problem_statement": "Design a cache"})
        sid = r.json()["session_id"]

        r = client.get(f"/session/{sid}/dll-visualize")
        assert r.status_code == 200

    def test_state_endpoint_returns_correct_fields(self, client, mock_scene):
        with patch("competitive_programming_factory.engine.session_engine._generate_scene", return_value=mock_scene):
            r = client.post("/sessions", json={"problem_statement": "Design a cache"})
        sid = r.json()["session_id"]

        r = client.get(f"/session/{sid}/state")
        assert r.status_code == 200
        body = r.json()
        for field in ("fsm_state", "phase", "probe_rounds", "requires_voice", "valid_transitions"):
            assert field in body, f"Missing field: {field}"


@pytest.mark.e2e
class TestFlaggedFlow:
    """
    When probe limit is hit the candidate lands on the flagged page.
    That page must render and offer a path forward — not a dead end.
    """

    def test_flagged_page_renders_after_probe_limit(self, client, mock_scene, mock_stage_spec):
        with patch("competitive_programming_factory.engine.session_engine._generate_scene", return_value=mock_scene):
            r = client.post("/sessions", json={"problem_statement": "Design a search engine"})
        sid = r.json()["session_id"]

        import competitive_programming_factory.session_store as store
        from competitive_programming_factory.domain.fsm.machine import PROBE_LIMIT
        from competitive_programming_factory.domain.fsm.states import State

        fsm, dll = store.load(sid)
        fsm.transition_to(State.SYSTEM_DESIGN, trigger="test")
        fsm.transition_to(State.NODE_SESSION,  trigger="test")
        fsm.transition_to(State.OOD_STAGE,     trigger="test")
        for _ in range(PROBE_LIMIT):
            fsm.increment_turn()
        store.save(sid, fsm, dll)

        with patch("competitive_programming_factory.engine.session_engine.get_or_generate_stage", return_value=mock_stage_spec):
            r = client.post(
                f"/session/{sid}/stage/1/submit",
                data={"answer": "I don't know."},
            )

        next_url = r.json()["next_url"]
        assert "flagged" in next_url

        r = client.get(next_url)
        assert r.status_code == 200
        assert "Continue" in r.text or "stage" in r.text
