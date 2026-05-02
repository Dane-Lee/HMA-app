from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from fastapi.testclient import TestClient

from api.app.main import create_app

from test_api import build_settings


def _make_pinned_client(tmp_path: Path) -> TestClient:
    settings = replace(build_settings(tmp_path), access_pin="5380")
    return TestClient(create_app(settings))


def _seed_employee_link(provider_client: TestClient) -> str:
    employee = provider_client.post(
        "/api/provider/employees", json={"name": "Jamie", "employer": "Hendrickson"}
    ).json()
    issued = provider_client.post(
        f"/api/provider/employees/{employee['id']}/magic-link"
    ).json()
    return issued["url"].rsplit("/", 1)[-1]


def test_employee_cookie_cannot_access_provider_routes(tmp_path: Path):
    provider_client = _make_pinned_client(tmp_path)
    provider_client.post("/api/auth", json={"pin": "5380"})
    token = _seed_employee_link(provider_client)

    settings = replace(build_settings(tmp_path), access_pin="5380")
    employee_client = TestClient(create_app(settings))
    employee_client.post("/api/self/session", json={"token": token})
    assert employee_client.cookies.get("hma_employee_session")
    assert employee_client.cookies.get("hma_session") is None

    response = employee_client.post(
        "/api/provider/employees", json={"name": "Other", "employer": "Hendrickson"}
    )
    assert response.status_code == 401


def test_provider_cookie_cannot_access_self_routes(tmp_path: Path):
    client = _make_pinned_client(tmp_path)
    client.post("/api/auth", json={"pin": "5380"})
    assert client.cookies.get("hma_session")

    response = client.get("/api/self/me")
    assert response.status_code == 401


def test_self_session_route_is_public_even_with_pin(tmp_path: Path):
    client = _make_pinned_client(tmp_path)

    response = client.post("/api/self/session", json={"token": "garbage"})
    # Public, but token is invalid → 401 from the route itself, not the middleware.
    assert response.status_code == 401
    assert response.json()["detail"] == "Link is invalid or expired."
