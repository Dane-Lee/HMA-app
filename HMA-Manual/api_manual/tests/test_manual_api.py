from __future__ import annotations

import sys
from pathlib import Path
from urllib.parse import urlparse
from uuid import uuid4

from fastapi.testclient import TestClient

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from api_manual.app.main import create_app
from api_manual.app.settings import ManualSettings


def make_test_dir(name: str) -> Path:
    path = PROJECT_ROOT / ".manual-test-data" / f"{name}-{uuid4()}"
    path.mkdir(parents=True, exist_ok=True)
    return path


def make_settings(tmp_path: Path) -> ManualSettings:
    return ManualSettings(
        base_dir=PROJECT_ROOT,
        db_path=tmp_path / "manual.db",
        movements_config_path=PROJECT_ROOT / "config_manual" / "movements.json",
        review_capture_dir=tmp_path / "review-captures",
        web_dist_dir=tmp_path / "dist",
        public_base_url="http://testserver",
        max_upload_bytes=10 * 1024 * 1024,
        review_capture_retention_days=7,
        assessment_retention_days=365,
        provider_session_hours=12,
        upload_session_lifetime_days=7,
        require_mfa=False,
        bootstrap_username="admin",
        bootstrap_password="secret-password",
        bootstrap_display_name="Manual Admin",
        bootstrap_mfa_secret="",
        dev_cors_origins=("http://localhost:5182",),
    )


def login(client: TestClient) -> None:
    response = client.post(
        "/api/auth",
        json={"username": "admin", "password": "secret-password"},
    )
    assert response.status_code == 200


def consent() -> dict:
    return {
        "notice_version": "test",
        "voluntary_wellness": True,
        "purpose_limited": True,
        "no_employment_decision": True,
        "video_retention_acknowledged": True,
    }


def create_assessment(client: TestClient) -> str:
    response = client.post(
        "/api/assessments",
        json={"participant_name": "Jordan", "consent": consent()},
    )
    assert response.status_code == 201
    return response.json()["id"]


def test_manual_score_and_review_video_lifecycle() -> None:
    tmp_path = make_test_dir("video-lifecycle")
    app = create_app(make_settings(tmp_path))
    client = TestClient(app)
    login(client)
    assessment_id = create_assessment(client)

    score_response = client.post(
        f"/api/assessments/{assessment_id}/movements/cervical_rotation/manual-score",
        json={
            "right": {"score": 3, "faults": []},
            "left": {"score": 2, "faults": ["shoulder_drift"]},
            "provider_note": "Manual observation only.",
        },
    )
    assert score_response.status_code == 200
    result = score_response.json()["movement_results"][0]
    assert result["final_score"] == 2
    assert "confidence" not in result
    assert "app_score" not in result
    assert "pose_trace" not in result

    upload_response = client.post(
        f"/api/assessments/{assessment_id}/review-videos",
        data={"movement_key": "cervical_rotation", "side": "right", "client_video_id": "client-1"},
        files={"video": ("clip.webm", b"fake-video", "video/webm")},
    )
    assert upload_response.status_code == 201
    video = upload_response.json()
    assert video["video_url"]

    anonymous = TestClient(app)
    assert anonymous.get(video["video_url"]).status_code == 401

    blocked = client.post(
        f"/api/assessments/{assessment_id}/complete",
        json={"confirm_delete_videos": False},
    )
    assert blocked.status_code == 409

    completed = client.post(
        f"/api/assessments/{assessment_id}/complete",
        json={"confirm_delete_videos": True},
    )
    assert completed.status_code == 200
    body = completed.json()
    assert body["status"] == "completed"
    assert body["remaining_video_count"] == 0
    assert body["review_videos"][0]["deleted_at"] is not None


def test_employee_upload_session_is_scoped_to_assessment() -> None:
    tmp_path = make_test_dir("employee-upload")
    app = create_app(make_settings(tmp_path))
    provider = TestClient(app)
    login(provider)
    assessment_id = create_assessment(provider)

    issued = provider.post(
        f"/api/assessments/{assessment_id}/upload-session",
        json={"employee": {"name": "Jamie", "employer": "ATI", "email": "jamie@example.com"}},
    )
    assert issued.status_code == 201
    token = Path(urlparse(issued.json()["url"]).path).name

    employee = TestClient(app)
    session = employee.post("/api/self/session", json={"token": token})
    assert session.status_code == 200
    assert session.json()["assessment"]["id"] == assessment_id

    upload = employee.post(
        "/api/self/review-videos",
        data={"movement_key": "cervical_rotation", "side": "right", "client_video_id": "employee-1"},
        files={"video": ("clip.webm", b"fake-video", "video/webm")},
    )
    assert upload.status_code == 201

    forbidden = employee.post(
        "/api/self/review-videos",
        data={"movement_key": "cervical_rotation", "side": "middle", "client_video_id": "employee-2"},
        files={"video": ("clip.webm", b"fake-video", "video/webm")},
    )
    assert forbidden.status_code in {400, 403}


def test_mfa_required_blocks_provider_without_secret() -> None:
    tmp_path = make_test_dir("mfa")
    settings = make_settings(tmp_path)
    settings.require_mfa = True
    app = create_app(settings)
    client = TestClient(app)
    response = client.post(
        "/api/auth",
        json={"username": "admin", "password": "secret-password"},
    )
    assert response.status_code == 403
