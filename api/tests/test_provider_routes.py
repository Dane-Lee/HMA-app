from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from fastapi.testclient import TestClient

from api.app.database import get_connection
from api.app.main import create_app

from test_api import build_settings


def test_create_employee_returns_record_and_audit(tmp_path: Path):
    client = TestClient(create_app(build_settings(tmp_path)))

    response = client.post(
        "/api/provider/employees",
        json={"name": "  Jamie  ", "employer": "Hendrickson", "email": "jamie@example.com"},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "Jamie"
    assert body["employer"] == "Hendrickson"
    assert body["email"] == "jamie@example.com"
    assert body["id"]
    assert body["created_at"]

    settings = build_settings(tmp_path)
    with get_connection(settings.db_path) as connection:
        row = connection.execute(
            "SELECT event_type FROM audit_events WHERE event_type = 'employee_create'"
        ).fetchone()
    assert row is not None


def test_create_employee_rejects_blank_name(tmp_path: Path):
    client = TestClient(create_app(build_settings(tmp_path)))

    response = client.post(
        "/api/provider/employees",
        json={"name": "   ", "employer": "Hendrickson"},
    )
    assert response.status_code == 422


def test_list_employees_filters_by_employer(tmp_path: Path):
    client = TestClient(create_app(build_settings(tmp_path)))

    client.post("/api/provider/employees", json={"name": "A", "employer": "Hendrickson"})
    client.post("/api/provider/employees", json={"name": "B", "employer": "OtherCo"})
    client.post("/api/provider/employees", json={"name": "C", "employer": "Hendrickson"})

    all_rows = client.get("/api/provider/employees").json()
    assert len(all_rows) == 3

    filtered = client.get("/api/provider/employees", params={"employer": "Hendrickson"}).json()
    assert {row["name"] for row in filtered} == {"A", "C"}


def test_issue_magic_link_returns_url_and_expiration(tmp_path: Path):
    client = TestClient(create_app(build_settings(tmp_path)))
    employee = client.post(
        "/api/provider/employees", json={"name": "Jamie", "employer": "Hendrickson"}
    ).json()

    response = client.post(f"/api/provider/employees/{employee['id']}/magic-link")
    assert response.status_code == 200
    body = response.json()

    assert body["url"].startswith("http://localhost:5181/self/start/")
    token = body["url"].rsplit("/", 1)[-1]
    assert len(token) >= 40
    assert body["expires_at"]


def test_issue_magic_link_for_unknown_employee(tmp_path: Path):
    client = TestClient(create_app(build_settings(tmp_path)))
    response = client.post("/api/provider/employees/does-not-exist/magic-link")
    assert response.status_code == 404


def test_revoke_links_invalidates_existing(tmp_path: Path):
    client = TestClient(create_app(build_settings(tmp_path)))
    employee = client.post(
        "/api/provider/employees", json={"name": "Jamie", "employer": "Hendrickson"}
    ).json()

    issued = client.post(f"/api/provider/employees/{employee['id']}/magic-link").json()
    token = issued["url"].rsplit("/", 1)[-1]

    revoke_response = client.post(f"/api/provider/employees/{employee['id']}/revoke-links")
    assert revoke_response.status_code == 200
    assert revoke_response.json()["revoked_count"] == 1

    consume_response = client.post("/api/self/session", json={"token": token})
    assert consume_response.status_code == 401


def test_provider_routes_require_pin_when_configured(tmp_path: Path):
    settings = replace(build_settings(tmp_path), access_pin="5380")
    client = TestClient(create_app(settings))

    response = client.post(
        "/api/provider/employees", json={"name": "Jamie", "employer": "Hendrickson"}
    )
    assert response.status_code == 401

    client.post("/api/auth", json={"pin": "5380"})

    response = client.post(
        "/api/provider/employees", json={"name": "Jamie", "employer": "Hendrickson"}
    )
    assert response.status_code == 201
