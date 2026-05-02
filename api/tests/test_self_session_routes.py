from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from fastapi.testclient import TestClient

from api.app.main import create_app

from test_api import build_settings


def _create_employee_and_link(client: TestClient) -> tuple[dict, str]:
    employee = client.post(
        "/api/provider/employees", json={"name": "Jamie", "employer": "Hendrickson"}
    ).json()
    issued = client.post(f"/api/provider/employees/{employee['id']}/magic-link").json()
    token = issued["url"].rsplit("/", 1)[-1]
    return employee, token


def test_consume_link_creates_employee_session(tmp_path: Path):
    client = TestClient(create_app(build_settings(tmp_path)))
    employee, token = _create_employee_and_link(client)

    response = client.post("/api/self/session", json={"token": token})
    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["employee"]["id"] == employee["id"]
    assert client.cookies.get("hma_employee_session")


def test_consume_invalid_link_returns_401(tmp_path: Path):
    client = TestClient(create_app(build_settings(tmp_path)))

    response = client.post("/api/self/session", json={"token": "nope"})
    assert response.status_code == 401


def test_consume_blank_token_returns_400(tmp_path: Path):
    client = TestClient(create_app(build_settings(tmp_path)))

    response = client.post("/api/self/session", json={"token": "   "})
    assert response.status_code == 400


def test_self_me_requires_employee_session(tmp_path: Path):
    client = TestClient(create_app(build_settings(tmp_path)))

    response = client.get("/api/self/me")
    assert response.status_code == 401


def test_self_me_returns_employee_after_consume(tmp_path: Path):
    client = TestClient(create_app(build_settings(tmp_path)))
    employee, token = _create_employee_and_link(client)
    client.post("/api/self/session", json={"token": token})

    response = client.get("/api/self/me")
    assert response.status_code == 200
    body = response.json()
    assert body["employee"]["id"] == employee["id"]
    assert body["employee"]["employer"] == "Hendrickson"
    assert body["assessment_id"] is None


def test_self_session_delete_clears_cookie(tmp_path: Path):
    client = TestClient(create_app(build_settings(tmp_path)))
    _, token = _create_employee_and_link(client)
    client.post("/api/self/session", json={"token": token})
    assert client.get("/api/self/me").status_code == 200

    response = client.delete("/api/self/session")
    assert response.status_code == 200

    assert client.get("/api/self/me").status_code == 401


def test_employee_session_uses_configured_lifetime(tmp_path: Path):
    settings = replace(build_settings(tmp_path), employee_session_hours=1)
    client = TestClient(create_app(settings))
    _, token = _create_employee_and_link(client)
    response = client.post("/api/self/session", json={"token": token})
    assert response.status_code == 200

    cookie_header = response.headers.get("set-cookie", "")
    assert "Max-Age=3600" in cookie_header
