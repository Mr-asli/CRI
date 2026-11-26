import importlib
from fastapi.testclient import TestClient


def load_app(monkeypatch, tmp_path, admin="a" * 32, approval="b" * 32):
    monkeypatch.setenv("CRI_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("CRI_AUDIT_FILE", str(tmp_path / "audit.jsonl"))
    monkeypatch.setenv("CRI_KILL_FILE", str(tmp_path / "KILL"))
    monkeypatch.setenv("CRI_NONCE_DB", str(tmp_path / "nonce.sqlite"))
    monkeypatch.setenv("CRI_ADMIN_TOKEN", admin)
    monkeypatch.setenv("CRI_APPROVAL_SECRET", approval)
    import cri.main as main

    return importlib.reload(main)


def test_sensitive_routes_require_bearer(monkeypatch, tmp_path):
    main = load_app(monkeypatch, tmp_path)
    with TestClient(main.app) as client:
        assert client.post("/api/kill").status_code == 401
        assert client.get("/api/audit/verify").status_code == 401
        assert client.get("/api/memory").status_code == 401
        assert (
            client.post(
                "/api/kill", headers={"Authorization": "Bearer " + "a" * 32}
            ).status_code
            == 200
        )


def test_agents_endpoint_does_not_claim_agents_are_running(monkeypatch, tmp_path):
    main = load_app(monkeypatch, tmp_path)
    with TestClient(main.app) as client:
        agents = client.get("/api/agents").json()
        assert len(agents) == 6
        assert all(agent["implemented"] is True for agent in agents)
        assert all(agent["status"] == "available_not_running" for agent in agents)


def test_authenticated_api_routes_and_fail_closed_workflow(monkeypatch, tmp_path):
    main = load_app(monkeypatch, tmp_path)

    def unavailable(code):
        raise main.SandboxUnavailable(
            "Docker Engine unavailable; execution denied"
        )

    monkeypatch.setattr(main.FLOW.s, "run", unavailable)
    headers = {"Authorization": "Bearer " + "a" * 32}
    with TestClient(main.app) as client:
        assert client.get("/").status_code == 200
        assert client.get("/api/status").status_code == 200
        assert client.get("/api/logs", headers=headers).status_code == 200
        assert client.get("/api/audit/verify", headers=headers).json()["valid"] is True
        assert client.get("/api/memory", headers=headers).json() == []
        assert (
            client.post(
                "/api/memory",
                headers=headers,
                json={"kind": "lesson", "text": "deterministic tests"},
            ).status_code
            == 200
        )
        assert (
            client.post(
                "/api/memory",
                headers=headers,
                json={"kind": "lesson", "text": "my secret is x"},
            ).status_code
            == 400
        )
        created = client.post(
            "/api/tasks", headers=headers, json={"goal": "verify sandbox fail closed"}
        )
        assert created.status_code == 200
        pid = created.json()["id"]
        tested = client.post(f"/api/tasks/{pid}/test", headers=headers)
        assert tested.status_code == 503
        assert (
            client.post(f"/api/approvals/token/{pid}", headers=headers).status_code
            == 403
        )
        assert (
            client.post(
                "/api/approvals",
                headers=headers,
                json={
                    "proposal_id": pid,
                    "decision": "approve",
                    "reason": "test",
                    "token": "x" * 20,
                },
            ).status_code
            == 403
        )
        assert (
            client.post(
                "/api/approvals",
                headers=headers,
                json={
                    "proposal_id": pid,
                    "decision": "invalid",
                    "reason": "test",
                    "token": "x" * 20,
                },
            ).status_code
            == 422
        )
        assert client.post("/api/restart", headers=headers).status_code == 200


def test_application_refuses_missing_admin_secret(monkeypatch, tmp_path):
    main = load_app(monkeypatch, tmp_path)
    monkeypatch.setattr(main, "ADMIN_TOKEN", "")
    try:
        with TestClient(main.app):
            assert False, "startup should fail without admin token"
    except RuntimeError as exc:
        assert "CRI_ADMIN_TOKEN" in str(exc)


def test_agent_execution_requires_admin_and_runs_real_agent(monkeypatch, tmp_path):
    main = load_app(monkeypatch, tmp_path)
    with TestClient(main.app) as client:
        assert (
            client.post("/api/agents/master/run", json={"goal": "test"}).status_code
            == 401
        )
        headers = {"Authorization": "Bearer " + "a" * 32}
        response = client.post(
            "/api/agents/master/run", headers=headers, json={"goal": "test CRI"}
        )
        assert response.status_code == 200
        assert response.json()["output"]["requires_human_approval"] is True
        assert (
            client.post("/api/agents/nope/run", headers=headers, json={}).status_code
            == 404
        )


def test_tasks_list_requires_admin_and_returns_proposals(monkeypatch, tmp_path):
    main = load_app(monkeypatch, tmp_path)
    headers = {"Authorization": "Bearer " + "a" * 32}
    with TestClient(main.app) as client:
        assert client.get("/api/tasks").status_code == 401
        created = client.post(
            "/api/tasks", headers=headers, json={"goal": "list task proposals"}
        )
        assert created.status_code == 200
        listed = client.get("/api/tasks", headers=headers)
        assert listed.status_code == 200
        assert listed.json()[0]["id"] == created.json()["id"]


def test_kill_latch_blocks_agent_execution(monkeypatch, tmp_path):
    main = load_app(monkeypatch, tmp_path)
    headers = {"Authorization": "Bearer " + "a" * 32}
    with TestClient(main.app) as client:
        assert client.post("/api/kill", headers=headers).status_code == 200
        denied = client.post(
            "/api/agents/master/run",
            headers=headers,
            json={"goal": "must remain blocked"},
        )
        assert denied.status_code == 423
        assert client.get("/api/status").json()["status"] == "stopped"


def test_status_reports_admission_latch_not_false_running_state(monkeypatch, tmp_path):
    main = load_app(monkeypatch, tmp_path)
    with TestClient(main.app) as client:
        status = client.get("/api/status").json()
        assert status["status"] == "enabled"
        assert status["control_plane"] == "reachable"
        assert status["execution_guarantee"] == "not_independently_supervised"
        assert status["sandbox"] == "unavailable"


def test_invalid_proposal_ids_fail_as_not_found(monkeypatch, tmp_path):
    main = load_app(monkeypatch, tmp_path)
    headers = {"Authorization": "Bearer " + "a" * 32}
    with TestClient(main.app) as client:
        assert client.post("/api/tasks/not-a-uuid/test", headers=headers).status_code == 404
        assert client.post("/api/approvals/token/not-a-uuid", headers=headers).status_code == 404


def test_agent_payload_size_is_bounded(monkeypatch, tmp_path):
    main = load_app(monkeypatch, tmp_path)
    headers = {"Authorization": "Bearer " + "a" * 32}
    with TestClient(main.app) as client:
        response = client.post("/api/agents/master/run", headers=headers, json={"goal": "x" * 12000})
        assert response.status_code == 422
