from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path

from fastapi.testclient import TestClient

from api.app.database import get_connection
from api.app.main import create_app
from api.app.settings import AppSettings


def consent_payload() -> dict:
    return {
        "notice_version": "privacy-notice-v1",
        "voluntary_wellness": True,
        "purpose_limited": True,
        "no_employment_decision": True,
        "video_retention_acknowledged": True,
    }


def create_payload(name: str) -> dict:
    return {"name": name, "consent": consent_payload()}


def build_settings(tmp_path: Path) -> AppSettings:
    data_dir = tmp_path / "data"
    temp_dir = data_dir / "uploads"
    draft_capture_dir = data_dir / "draft-captures"
    temp_dir.mkdir(parents=True, exist_ok=True)
    draft_capture_dir.mkdir(parents=True, exist_ok=True)
    return AppSettings(
        base_dir=Path(__file__).resolve().parents[2],
        db_path=data_dir / "test.db",
        movements_config_path=Path(__file__).resolve().parents[2] / "config" / "movements.json",
        thresholds_path=Path(__file__).resolve().parents[2] / "config" / "scoring_thresholds.yaml",
        temp_dir=temp_dir,
        draft_capture_dir=draft_capture_dir,
        web_dist_dir=tmp_path / "missing-dist",
        access_pin="",
        max_upload_bytes=150 * 1024 * 1024,
        draft_capture_retention_days=7,
        assessment_retention_days=365,
    )


def test_assessment_creation_requires_consent(tmp_path: Path):
    client = TestClient(create_app(build_settings(tmp_path)))

    response = client.post("/api/assessments", json={"name": "Jamie"})
    assert response.status_code == 422


def test_assessment_creation_stores_consent_and_retention(tmp_path: Path):
    client = TestClient(create_app(build_settings(tmp_path)))

    response = client.post("/api/assessments", json=create_payload("Jamie"))
    assert response.status_code == 201
    assessment = response.json()

    assert assessment["name"] == "Jamie"
    assert assessment["consent_notice_version"] == "privacy-notice-v1"
    assert assessment["consent_accepted_at"]
    assert assessment["privacy_posture"] == "voluntary_ergonomic_wellness"
    assert assessment["retention_expires_at"]
    assert assessment["consent_scope"] == {
        "voluntary_wellness": True,
        "purpose_limited": True,
        "no_employment_decision": True,
        "video_retention_acknowledged": True,
    }


def test_assessment_creation_and_finalize_flow(tmp_path: Path):
    client = TestClient(create_app(build_settings(tmp_path)))

    create_response = client.post("/api/assessments", json=create_payload("Jamie"))
    assert create_response.status_code == 201
    assessment = create_response.json()

    capture_response = client.post(
        f"/api/assessments/{assessment['id']}/movements/cervical_rotation/captures",
        data={"side": "right"},
        files={"video": ("good-right.webm", b"video-data", "video/webm")},
    )
    assert capture_response.status_code == 200
    capture_payload = capture_response.json()
    assert "score" in capture_payload

    finalize_response = client.post(
        f"/api/assessments/{assessment['id']}/movements/cervical_rotation/finalize",
        json={
            "right": {"score": 3, "detected_faults": []},
            "left": {"score": 2, "detected_faults": ["shoulder_drift"]},
        },
    )
    assert finalize_response.status_code == 200
    finalized = finalize_response.json()
    assert finalized["total_score"] == 2
    assert finalized["score_band"] == "High opportunity for improvement"


def test_temp_uploads_are_deleted(tmp_path: Path):
    settings = build_settings(tmp_path)
    client = TestClient(create_app(settings))
    assessment = client.post("/api/assessments", json=create_payload("Taylor")).json()

    response = client.post(
        f"/api/assessments/{assessment['id']}/movements/trunk_rotation/captures",
        data={"side": "left"},
        files={"video": ("limited-left.webm", b"video-data", "video/webm")},
    )
    assert response.status_code == 200
    assert list(settings.temp_dir.iterdir()) == []


def test_mobile_capture_draft_upload_is_persisted_and_idempotent(tmp_path: Path):
    settings = build_settings(tmp_path)
    client = TestClient(create_app(settings))

    assessment = client.post("/api/mobile-capture/assessments", json=create_payload("Morgan")).json()
    response = client.post(
        f"/api/assessments/{assessment['id']}/draft-captures",
        data={
            "movement_key": "cervical_rotation",
            "side": "right",
            "client_capture_id": "client-clip-1",
        },
        files={"video": ("good-right.webm", b"video-data", "video/webm")},
    )

    assert response.status_code == 200
    capture = response.json()
    assert capture["movement_key"] == "cervical_rotation"
    assert capture["side"] == "right"
    assert capture["client_capture_id"] == "client-clip-1"
    assert capture["video_url"]
    assert capture["pose_trace"] is None
    assert capture["quality"]["overlay_available"] is False
    assert capture["quality"]["status"] == "unavailable"
    assert len(list(settings.draft_capture_dir.iterdir())) == 1

    duplicate_response = client.post(
        f"/api/assessments/{assessment['id']}/draft-captures",
        data={
            "movement_key": "cervical_rotation",
            "side": "right",
            "client_capture_id": "client-clip-1",
        },
        files={"video": ("good-right-again.webm", b"new-video-data", "video/webm")},
    )
    assert duplicate_response.status_code == 200
    assert duplicate_response.json()["id"] == capture["id"]
    assert len(list(settings.draft_capture_dir.iterdir())) == 1

    list_response = client.get(f"/api/assessments/{assessment['id']}/draft-captures")
    assert list_response.status_code == 200
    assert len(list_response.json()) == 1
    assert list_response.json()[0]["quality"]["source"] == "fallback"

    video_response = client.get(capture["video_url"])
    assert video_response.status_code == 200


def test_finalize_persists_pose_trace_and_quality(tmp_path: Path):
    client = TestClient(create_app(build_settings(tmp_path)))
    assessment = client.post("/api/assessments", json=create_payload("Jordan")).json()
    pose_trace = {
        "schema_version": 1,
        "source": "mediapipe",
        "movement_key": "trunk_rotation",
        "side": "right",
        "width": 640,
        "height": 360,
        "fps": 30.0,
        "duration_seconds": 2.0,
        "sampled_frames": 1,
        "frames": [
            {
                "time_seconds": 0.0,
                "landmarks": [
                    {"name": "left_shoulder", "x": 0.4, "y": 0.3, "z": 0.0, "visibility": 0.9},
                    {"name": "right_shoulder", "x": 0.6, "y": 0.3, "z": 0.0, "visibility": 0.9},
                ],
            }
        ],
    }
    quality = {
        "schema_version": 1,
        "status": "good",
        "overlay_available": True,
        "source": "mediapipe",
        "sampled_frames": 1,
        "detection_rate": 1.0,
        "required_landmark_visibility": {"left_shoulder": 0.9, "right_shoulder": 0.9},
        "warnings": [],
        "width": 640,
        "height": 360,
        "fps": 30.0,
        "duration_seconds": 2.0,
    }

    response = client.post(
        f"/api/assessments/{assessment['id']}/movements/trunk_rotation/finalize",
        json={
            "right": {
                "score": 2,
                "detected_faults": ["lower_extremity_movement"],
                "metrics": {"trunk_rotation_angle_degrees": 42.0},
                "pose_trace": pose_trace,
                "quality": quality,
            },
            "left": {"score": 3, "detected_faults": [], "metrics": {}},
        },
    )

    assert response.status_code == 200
    result = response.json()["movement_results"][0]
    assert result["pose_trace"]["frames"][0]["landmarks"][0]["name"] == "left_shoulder"
    assert result["quality"]["overlay_available"] is True


def test_expired_draft_video_is_deleted_but_score_remains(tmp_path: Path):
    settings = replace(build_settings(tmp_path), draft_capture_retention_days=-1)
    client = TestClient(create_app(settings))
    assessment = client.post("/api/mobile-capture/assessments", json=create_payload("Riley")).json()

    response = client.post(
        f"/api/assessments/{assessment['id']}/draft-captures",
        data={
            "movement_key": "trunk_rotation",
            "side": "left",
            "client_capture_id": "client-clip-expired",
        },
        files={"video": ("limited-left.webm", b"video-data", "video/webm")},
    )
    assert response.status_code == 200
    assert len(list(settings.draft_capture_dir.iterdir())) == 1

    list_response = client.get(f"/api/assessments/{assessment['id']}/draft-captures")
    assert list_response.status_code == 200
    capture = list_response.json()[0]
    assert capture["score"] is not None
    assert capture["video_url"] is None
    assert capture["video_deleted_at"] is not None
    assert list(settings.draft_capture_dir.iterdir()) == []


def test_manual_assessment_delete_removes_rows_and_draft_video(tmp_path: Path):
    settings = build_settings(tmp_path)
    client = TestClient(create_app(settings))
    assessment = client.post("/api/mobile-capture/assessments", json=create_payload("Quinn")).json()
    upload_response = client.post(
        f"/api/assessments/{assessment['id']}/draft-captures",
        data={
            "movement_key": "cervical_rotation",
            "side": "right",
            "client_capture_id": "client-clip-delete",
        },
        files={"video": ("good-right.webm", b"video-data", "video/webm")},
    )
    assert upload_response.status_code == 200
    assert len(list(settings.draft_capture_dir.iterdir())) == 1

    delete_response = client.delete(f"/api/assessments/{assessment['id']}")
    assert delete_response.status_code == 204
    assert list(settings.draft_capture_dir.iterdir()) == []
    assert client.get(f"/api/assessments/{assessment['id']}").status_code == 404

    with get_connection(settings.db_path) as connection:
        assessment_row = connection.execute(
            "SELECT 1 FROM assessments WHERE id = ?",
            (assessment["id"],),
        ).fetchone()
        draft_row = connection.execute(
            "SELECT 1 FROM draft_captures WHERE assessment_id = ?",
            (assessment["id"],),
        ).fetchone()
    assert assessment_row is None
    assert draft_row is None


def test_retention_purge_removes_expired_assessment(tmp_path: Path):
    settings = replace(build_settings(tmp_path), assessment_retention_days=-1)
    client = TestClient(create_app(settings))
    assessment = client.post("/api/assessments", json=create_payload("Avery")).json()

    list_response = client.get("/api/assessments")
    assert list_response.status_code == 200
    assert list_response.json() == []
    assert client.get(f"/api/assessments/{assessment['id']}").status_code == 404

    with get_connection(settings.db_path) as connection:
        audit = connection.execute(
            "SELECT event_type, assessment_id, metadata_json FROM audit_events WHERE event_type = 'retention_purge'"
        ).fetchone()
    assert audit is not None
    assert audit["assessment_id"] == assessment["id"]
    assert json.loads(audit["metadata_json"])["reason"] == "assessment_retention_expired"


def test_audit_events_are_minimal_and_non_identifying(tmp_path: Path):
    settings = build_settings(tmp_path)
    client = TestClient(create_app(settings))
    assessment = client.post("/api/mobile-capture/assessments", json=create_payload("Patient Name")).json()

    client.post(
        f"/api/assessments/{assessment['id']}/draft-captures",
        data={
            "movement_key": "cervical_rotation",
            "side": "right",
            "client_capture_id": "client-clip-audit",
        },
        files={"video": ("good-right.webm", b"video-data", "video/webm")},
    )
    client.post(
        f"/api/assessments/{assessment['id']}/movements/cervical_rotation/finalize",
        json={
            "right": {"score": 3, "detected_faults": []},
            "left": {"score": 2, "detected_faults": ["shoulder_drift"]},
        },
    )
    client.post(
        f"/api/assessments/{assessment['id']}/movements/cervical_rotation/review",
        json={"provider_score": 1, "provider_note": "Reported pain"},
    )

    with get_connection(settings.db_path) as connection:
        rows = connection.execute(
            "SELECT event_type, assessment_id, movement_key, metadata_json FROM audit_events"
        ).fetchall()

    event_types = {row["event_type"] for row in rows}
    assert {"assessment_create", "draft_capture_upload", "movement_finalize", "provider_review"} <= event_types

    audit_text = "\n".join(
        f"{row['event_type']} {row['assessment_id']} {row['movement_key']} {row['metadata_json']}"
        for row in rows
    )
    assert "Patient Name" not in audit_text
    assert "shoulder_drift" not in audit_text
    assert "Reported pain" not in audit_text
    assert "chin_midline" not in audit_text


def test_pin_auth_leaves_spa_shell_public_but_protects_api(tmp_path: Path):
    client = TestClient(create_app(replace(build_settings(tmp_path), access_pin="5380")))

    root_response = client.get("/")
    assert root_response.status_code == 200

    auth_response = client.get("/api/auth")
    assert auth_response.status_code == 200
    assert auth_response.json() == {"auth_required": True, "authenticated": False}

    protected_response = client.get("/api/assessments")
    assert protected_response.status_code == 401


def test_built_public_asset_is_served_before_spa_fallback(tmp_path: Path):
    settings = build_settings(tmp_path)
    web_dist_dir = tmp_path / "web-dist"
    logo_dir = web_dist_dir / "ati-logo"
    logo_dir.mkdir(parents=True)
    (web_dist_dir / "index.html").write_text("<html>SPA shell</html>", encoding="utf-8")
    (logo_dir / "ATI-logo.png").write_bytes(b"png-bytes")

    client = TestClient(create_app(replace(settings, web_dist_dir=web_dist_dir)))

    logo_response = client.get("/ati-logo/ATI-logo.png")
    assert logo_response.status_code == 200
    assert logo_response.content == b"png-bytes"
    assert logo_response.headers["content-type"].startswith("image/png")

    route_response = client.get("/history")
    assert route_response.status_code == 200
    assert "SPA shell" in route_response.text


def test_pin_auth_unlocks_api_after_successful_login(tmp_path: Path):
    client = TestClient(create_app(replace(build_settings(tmp_path), access_pin="5380")))

    login_response = client.post("/api/auth", json={"pin": "5380"})
    assert login_response.status_code == 200

    assessments_response = client.get("/api/assessments")
    assert assessments_response.status_code == 200


def test_pin_auth_logout_clears_session(tmp_path: Path):
    client = TestClient(create_app(replace(build_settings(tmp_path), access_pin="5380")))

    client.post("/api/auth", json={"pin": "5380"})
    assert client.get("/api/assessments").status_code == 200

    logout_response = client.delete("/api/auth")
    assert logout_response.status_code == 200

    assert client.get("/api/assessments").status_code == 401


def test_pin_auth_session_survives_app_recreation(tmp_path: Path):
    settings = replace(build_settings(tmp_path), access_pin="5380")

    first_app = create_app(settings)
    first_client = TestClient(first_app)
    first_client.post("/api/auth", json={"pin": "5380"})
    cookie = first_client.cookies.get("hma_session")
    assert cookie

    second_app = create_app(settings)
    second_client = TestClient(second_app)
    second_client.cookies.set("hma_session", cookie)

    response = second_client.get("/api/assessments")
    assert response.status_code == 200
