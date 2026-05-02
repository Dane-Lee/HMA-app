from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from .auth_tokens import hash_token
from .database import get_connection


PRIVACY_POSTURE = "voluntary_ergonomic_wellness"


def default_capture_quality() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "status": "unavailable",
        "overlay_available": False,
        "source": "legacy",
        "sampled_frames": 0,
        "detection_rate": 0.0,
        "required_landmark_visibility": {},
        "warnings": ["legacy_capture_no_pose_quality"],
        "width": 0,
        "height": 0,
        "fps": 0.0,
        "duration_seconds": 0.0,
    }


def compute_score_band(total_score: int) -> str:
    if total_score <= 5:
        return "High opportunity for improvement"
    if total_score <= 10:
        return "Moderate opportunity for improvement"
    return "Low opportunity for improvement"


class AssessmentRepository:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path

    def create_assessment(
        self,
        name: str,
        *,
        consent_notice_version: str,
        consent_scope: dict[str, bool],
        retention_days: int,
    ) -> dict[str, Any]:
        created_at = datetime.now(timezone.utc)
        retention_expires_at = created_at + timedelta(days=retention_days)
        record = {
            "id": str(uuid4()),
            "name": name,
            "created_at": created_at.isoformat(),
            "total_score": 0,
            "score_band": compute_score_band(0),
            "consent_notice_version": consent_notice_version,
            "consent_accepted_at": created_at.isoformat(),
            "consent_scope_json": json.dumps(consent_scope, sort_keys=True),
            "privacy_posture": PRIVACY_POSTURE,
            "retention_expires_at": retention_expires_at.isoformat(),
        }
        with get_connection(self.db_path) as connection:
            connection.execute(
                """
                INSERT INTO assessments (
                    id,
                    name,
                    created_at,
                    total_score,
                    score_band,
                    consent_notice_version,
                    consent_accepted_at,
                    consent_scope_json,
                    privacy_posture,
                    retention_expires_at
                )
                VALUES (
                    :id,
                    :name,
                    :created_at,
                    :total_score,
                    :score_band,
                    :consent_notice_version,
                    :consent_accepted_at,
                    :consent_scope_json,
                    :privacy_posture,
                    :retention_expires_at
                )
                """,
                record,
            )
            connection.commit()
        return record

    def assessment_exists(self, assessment_id: str) -> bool:
        with get_connection(self.db_path) as connection:
            row = connection.execute(
                "SELECT 1 FROM assessments WHERE id = ?",
                (assessment_id,),
            ).fetchone()
        return row is not None

    def list_assessments(self) -> list[dict[str, Any]]:
        with get_connection(self.db_path) as connection:
            rows = connection.execute(
                """
                SELECT id, name, created_at, total_score, score_band,
                       consent_notice_version, consent_accepted_at,
                       privacy_posture, retention_expires_at
                FROM assessments
                ORDER BY datetime(created_at) DESC
                """
            ).fetchall()
        return [dict(row) for row in rows]

    def get_assessment(self, assessment_id: str) -> dict[str, Any] | None:
        with get_connection(self.db_path) as connection:
            assessment = connection.execute(
                """
                SELECT id, name, created_at, total_score, score_band,
                       consent_notice_version, consent_accepted_at, consent_scope_json,
                       privacy_posture, retention_expires_at
                FROM assessments
                WHERE id = ?
                """,
                (assessment_id,),
            ).fetchone()
            if assessment is None:
                return None
            movement_rows = connection.execute(
                """
                SELECT id, assessment_id, movement_key, right_score, left_score, final_score,
                       detected_faults_json, app_metrics_json, pose_trace_json, quality_json,
                       provider_score, provider_note, review_status
                FROM movement_results
                WHERE assessment_id = ?
                ORDER BY movement_key
                """,
                (assessment_id,),
            ).fetchall()
        result = dict(assessment)
        consent_scope_json = result.pop("consent_scope_json", None)
        result["consent_scope"] = json.loads(consent_scope_json) if consent_scope_json else None
        result["movement_results"] = [
            {
                **dict(row),
                "detected_faults": json.loads(row["detected_faults_json"]),
                "app_metrics": json.loads(row["app_metrics_json"]) if row["app_metrics_json"] else None,
                "pose_trace": json.loads(row["pose_trace_json"]) if row["pose_trace_json"] else None,
                "quality": json.loads(row["quality_json"]) if row["quality_json"] else default_capture_quality(),
            }
            for row in movement_rows
        ]
        return result

    def list_expired_assessments(self, now_iso: str) -> list[dict[str, Any]]:
        with get_connection(self.db_path) as connection:
            rows = connection.execute(
                """
                SELECT id, retention_expires_at
                FROM assessments
                WHERE retention_expires_at IS NOT NULL
                  AND datetime(retention_expires_at) <= datetime(?)
                """,
                (now_iso,),
            ).fetchall()
        return [dict(row) for row in rows]

    def delete_assessment(self, assessment_id: str) -> bool:
        with get_connection(self.db_path) as connection:
            cursor = connection.execute(
                "DELETE FROM assessments WHERE id = ?",
                (assessment_id,),
            )
            connection.commit()
        return cursor.rowcount > 0

    def log_audit_event(
        self,
        event_type: str,
        *,
        assessment_id: str | None = None,
        movement_key: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        record = {
            "id": str(uuid4()),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "event_type": event_type,
            "assessment_id": assessment_id,
            "movement_key": movement_key,
            "metadata_json": json.dumps(metadata or {}, sort_keys=True),
        }
        with get_connection(self.db_path) as connection:
            connection.execute(
                """
                INSERT INTO audit_events (
                    id,
                    created_at,
                    event_type,
                    assessment_id,
                    movement_key,
                    metadata_json
                )
                VALUES (
                    :id,
                    :created_at,
                    :event_type,
                    :assessment_id,
                    :movement_key,
                    :metadata_json
                )
                """,
                record,
            )
            connection.commit()

    def list_audit_events(self) -> list[dict[str, Any]]:
        with get_connection(self.db_path) as connection:
            rows = connection.execute(
                """
                SELECT id, created_at, event_type, assessment_id, movement_key, metadata_json
                FROM audit_events
                ORDER BY datetime(created_at), event_type
                """
            ).fetchall()
        return [dict(row) for row in rows]

    def upsert_movement_result(
        self,
        assessment_id: str,
        movement_key: str,
        right_score: int | None,
        left_score: int | None,
        final_score: int,
        detected_faults: dict[str, list[str]],
        app_metrics: dict[str, Any] | None = None,
        pose_trace: dict[str, Any] | None = None,
        quality: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        record = {
            "id": str(uuid4()),
            "assessment_id": assessment_id,
            "movement_key": movement_key,
            "right_score": right_score,
            "left_score": left_score,
            "final_score": final_score,
            "detected_faults_json": json.dumps(detected_faults),
            "app_metrics_json": json.dumps(app_metrics) if app_metrics is not None else None,
            "pose_trace_json": json.dumps(pose_trace) if pose_trace is not None else None,
            "quality_json": json.dumps(quality) if quality is not None else None,
        }
        with get_connection(self.db_path) as connection:
            connection.execute(
                """
                INSERT INTO movement_results (
                    id,
                    assessment_id,
                    movement_key,
                    right_score,
                    left_score,
                    final_score,
                    detected_faults_json,
                    app_metrics_json,
                    pose_trace_json,
                    quality_json
                )
                VALUES (
                    :id,
                    :assessment_id,
                    :movement_key,
                    :right_score,
                    :left_score,
                    :final_score,
                    :detected_faults_json,
                    :app_metrics_json,
                    :pose_trace_json,
                    :quality_json
                )
                ON CONFLICT(assessment_id, movement_key)
                DO UPDATE SET
                    right_score = excluded.right_score,
                    left_score = excluded.left_score,
                    final_score = excluded.final_score,
                    detected_faults_json = excluded.detected_faults_json,
                    app_metrics_json = excluded.app_metrics_json,
                    pose_trace_json = excluded.pose_trace_json,
                    quality_json = excluded.quality_json
                """,
                record,
            )
            total_row = connection.execute(
                """
                SELECT COALESCE(SUM(final_score), 0) AS total_score
                FROM movement_results
                WHERE assessment_id = ?
                """,
                (assessment_id,),
            ).fetchone()
            total_score = int(total_row["total_score"])
            score_band = compute_score_band(total_score)
            connection.execute(
                """
                UPDATE assessments
                SET total_score = ?, score_band = ?
                WHERE id = ?
                """,
                (total_score, score_band, assessment_id),
            )
            connection.commit()
        return {
            "id": record["id"],
            "assessment_id": assessment_id,
            "movement_key": movement_key,
            "right_score": right_score,
            "left_score": left_score,
            "final_score": final_score,
            "detected_faults": detected_faults,
            "app_metrics": app_metrics,
            "pose_trace": pose_trace,
            "quality": quality,
        }

    def save_provider_review(
        self,
        assessment_id: str,
        movement_key: str,
        provider_score: int,
        provider_note: str | None,
    ) -> bool:
        with get_connection(self.db_path) as connection:
            cursor = connection.execute(
                """
                UPDATE movement_results
                SET provider_score = ?, provider_note = ?, review_status = 'reviewed'
                WHERE assessment_id = ? AND movement_key = ?
                """,
                (provider_score, provider_note, assessment_id, movement_key),
            )
            connection.commit()
        return cursor.rowcount > 0

    def get_draft_capture_by_client_id(
        self,
        assessment_id: str,
        client_capture_id: str,
    ) -> dict[str, Any] | None:
        with get_connection(self.db_path) as connection:
            row = connection.execute(
                """
                SELECT *
                FROM draft_captures
                WHERE assessment_id = ? AND client_capture_id = ?
                """,
                (assessment_id, client_capture_id),
            ).fetchone()
        return self._draft_capture_from_row(row) if row else None

    def get_draft_capture_by_slot(
        self,
        assessment_id: str,
        movement_key: str,
        side: str,
    ) -> dict[str, Any] | None:
        with get_connection(self.db_path) as connection:
            row = connection.execute(
                """
                SELECT *
                FROM draft_captures
                WHERE assessment_id = ? AND movement_key = ? AND side = ?
                """,
                (assessment_id, movement_key, side),
            ).fetchone()
        return self._draft_capture_from_row(row) if row else None

    def get_draft_capture(self, assessment_id: str, capture_id: str) -> dict[str, Any] | None:
        with get_connection(self.db_path) as connection:
            row = connection.execute(
                """
                SELECT *
                FROM draft_captures
                WHERE assessment_id = ? AND id = ?
                """,
                (assessment_id, capture_id),
            ).fetchone()
        return self._draft_capture_from_row(row) if row else None

    def list_draft_captures(self, assessment_id: str) -> list[dict[str, Any]]:
        with get_connection(self.db_path) as connection:
            rows = connection.execute(
                """
                SELECT *
                FROM draft_captures
                WHERE assessment_id = ?
                ORDER BY datetime(created_at) ASC
                """,
                (assessment_id,),
            ).fetchall()
        return [self._draft_capture_from_row(row) for row in rows]

    def upsert_draft_capture(
        self,
        *,
        assessment_id: str,
        movement_key: str,
        side: str,
        client_capture_id: str,
        score: int,
        detected_faults: list[str],
        metrics: dict[str, Any],
        pose_trace: dict[str, Any] | None,
        quality: dict[str, Any] | None,
        confidence: float,
        source: str,
        original_filename: str | None,
        content_type: str | None,
        file_size_bytes: int,
        video_path: str,
        created_at: str,
        expires_at: str,
    ) -> dict[str, Any]:
        record = {
            "id": str(uuid4()),
            "assessment_id": assessment_id,
            "movement_key": movement_key,
            "side": side,
            "client_capture_id": client_capture_id,
            "score": score,
            "detected_faults_json": json.dumps(detected_faults),
            "metrics_json": json.dumps(metrics),
            "pose_trace_json": json.dumps(pose_trace) if pose_trace is not None else None,
            "quality_json": json.dumps(quality) if quality is not None else None,
            "confidence": confidence,
            "source": source,
            "original_filename": original_filename,
            "content_type": content_type,
            "file_size_bytes": file_size_bytes,
            "video_path": video_path,
            "created_at": created_at,
            "expires_at": expires_at,
            "video_deleted_at": None,
        }
        with get_connection(self.db_path) as connection:
            connection.execute(
                """
                INSERT INTO draft_captures (
                    id,
                    assessment_id,
                    movement_key,
                    side,
                    client_capture_id,
                    score,
                    detected_faults_json,
                    metrics_json,
                    pose_trace_json,
                    quality_json,
                    confidence,
                    source,
                    original_filename,
                    content_type,
                    file_size_bytes,
                    video_path,
                    created_at,
                    expires_at,
                    video_deleted_at
                )
                VALUES (
                    :id,
                    :assessment_id,
                    :movement_key,
                    :side,
                    :client_capture_id,
                    :score,
                    :detected_faults_json,
                    :metrics_json,
                    :pose_trace_json,
                    :quality_json,
                    :confidence,
                    :source,
                    :original_filename,
                    :content_type,
                    :file_size_bytes,
                    :video_path,
                    :created_at,
                    :expires_at,
                    :video_deleted_at
                )
                ON CONFLICT(assessment_id, movement_key, side)
                DO UPDATE SET
                    id = excluded.id,
                    client_capture_id = excluded.client_capture_id,
                    score = excluded.score,
                    detected_faults_json = excluded.detected_faults_json,
                    metrics_json = excluded.metrics_json,
                    pose_trace_json = excluded.pose_trace_json,
                    quality_json = excluded.quality_json,
                    confidence = excluded.confidence,
                    source = excluded.source,
                    original_filename = excluded.original_filename,
                    content_type = excluded.content_type,
                    file_size_bytes = excluded.file_size_bytes,
                    video_path = excluded.video_path,
                    created_at = excluded.created_at,
                    expires_at = excluded.expires_at,
                    video_deleted_at = excluded.video_deleted_at
                """,
                record,
            )
            row = connection.execute(
                "SELECT * FROM draft_captures WHERE id = ?",
                (record["id"],),
            ).fetchone()
            connection.commit()
        return self._draft_capture_from_row(row)

    def delete_draft_capture(self, assessment_id: str, capture_id: str) -> dict[str, Any] | None:
        existing = self.get_draft_capture(assessment_id, capture_id)
        if existing is None:
            return None
        with get_connection(self.db_path) as connection:
            connection.execute(
                "DELETE FROM draft_captures WHERE assessment_id = ? AND id = ?",
                (assessment_id, capture_id),
            )
            connection.commit()
        return existing

    def list_expired_draft_videos(self, now_iso: str) -> list[dict[str, Any]]:
        with get_connection(self.db_path) as connection:
            rows = connection.execute(
                """
                SELECT *
                FROM draft_captures
                WHERE video_path IS NOT NULL AND datetime(expires_at) <= datetime(?)
                """,
                (now_iso,),
            ).fetchall()
        return [self._draft_capture_from_row(row) for row in rows]

    def mark_draft_videos_deleted(self, capture_ids: list[str], deleted_at: str) -> None:
        if not capture_ids:
            return
        placeholders = ",".join("?" for _ in capture_ids)
        with get_connection(self.db_path) as connection:
            connection.execute(
                f"""
                UPDATE draft_captures
                SET video_path = NULL, video_deleted_at = ?
                WHERE id IN ({placeholders})
                """,
                (deleted_at, *capture_ids),
            )
            connection.commit()

    def _draft_capture_from_row(self, row) -> dict[str, Any]:
        record = dict(row)
        record["detected_faults"] = json.loads(record.pop("detected_faults_json"))
        record["metrics"] = json.loads(record.pop("metrics_json"))
        pose_trace_json = record.pop("pose_trace_json", None)
        quality_json = record.pop("quality_json", None)
        record["pose_trace"] = json.loads(pose_trace_json) if pose_trace_json else None
        record["quality"] = json.loads(quality_json) if quality_json else default_capture_quality()
        return record

    # ---- Employees ---------------------------------------------------------

    def create_employee(
        self,
        name: str,
        employer: str,
        *,
        email: str | None = None,
        notes: str | None = None,
        created_by: str | None = None,
    ) -> dict[str, Any]:
        record = {
            "id": str(uuid4()),
            "name": name,
            "email": email,
            "employer": employer,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "created_by": created_by,
            "notes": notes,
        }
        with get_connection(self.db_path) as connection:
            connection.execute(
                """
                INSERT INTO employees (id, name, email, employer, created_at, created_by, notes)
                VALUES (:id, :name, :email, :employer, :created_at, :created_by, :notes)
                """,
                record,
            )
            connection.commit()
        return record

    def get_employee(self, employee_id: str) -> dict[str, Any] | None:
        with get_connection(self.db_path) as connection:
            row = connection.execute(
                """
                SELECT id, name, email, employer, created_at, created_by, notes
                FROM employees WHERE id = ?
                """,
                (employee_id,),
            ).fetchone()
        return dict(row) if row else None

    def list_employees(self, *, employer: str | None = None) -> list[dict[str, Any]]:
        with get_connection(self.db_path) as connection:
            if employer is None:
                rows = connection.execute(
                    """
                    SELECT id, name, email, employer, created_at, created_by, notes
                    FROM employees
                    ORDER BY datetime(created_at) DESC
                    """
                ).fetchall()
            else:
                rows = connection.execute(
                    """
                    SELECT id, name, email, employer, created_at, created_by, notes
                    FROM employees
                    WHERE employer = ?
                    ORDER BY datetime(created_at) DESC
                    """,
                    (employer,),
                ).fetchall()
        return [dict(row) for row in rows]

    # ---- Magic-link tokens -------------------------------------------------

    def create_magic_link_token(
        self,
        employee_id: str,
        *,
        plaintext_token: str,
        expires_at: str,
    ) -> dict[str, Any]:
        record = {
            "id": str(uuid4()),
            "token_hash": hash_token(plaintext_token),
            "employee_id": employee_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "expires_at": expires_at,
        }
        with get_connection(self.db_path) as connection:
            connection.execute(
                """
                INSERT INTO magic_link_tokens (id, token_hash, employee_id, created_at, expires_at)
                VALUES (:id, :token_hash, :employee_id, :created_at, :expires_at)
                """,
                record,
            )
            connection.commit()
        return record

    def consume_magic_link_token(
        self,
        plaintext_token: str,
        *,
        now_iso: str,
    ) -> dict[str, Any] | None:
        token_hash_value = hash_token(plaintext_token)
        with get_connection(self.db_path) as connection:
            token_row = connection.execute(
                """
                SELECT id, employee_id
                FROM magic_link_tokens
                WHERE token_hash = ?
                  AND revoked_at IS NULL
                  AND datetime(expires_at) > datetime(?)
                """,
                (token_hash_value, now_iso),
            ).fetchone()
            if token_row is None:
                return None
            connection.execute(
                """
                UPDATE magic_link_tokens
                SET use_count = use_count + 1, last_used_at = ?
                WHERE id = ?
                """,
                (now_iso, token_row["id"]),
            )
            employee_row = connection.execute(
                """
                SELECT id, name, email, employer, created_at, created_by, notes
                FROM employees WHERE id = ?
                """,
                (token_row["employee_id"],),
            ).fetchone()
            connection.commit()
        return dict(employee_row) if employee_row else None

    def revoke_magic_link_token(self, token_id: str, *, now_iso: str) -> bool:
        with get_connection(self.db_path) as connection:
            cursor = connection.execute(
                """
                UPDATE magic_link_tokens
                SET revoked_at = ?
                WHERE id = ? AND revoked_at IS NULL
                """,
                (now_iso, token_id),
            )
            connection.commit()
        return cursor.rowcount > 0

    def revoke_employee_magic_links(self, employee_id: str, *, now_iso: str) -> int:
        with get_connection(self.db_path) as connection:
            cursor = connection.execute(
                """
                UPDATE magic_link_tokens
                SET revoked_at = ?
                WHERE employee_id = ? AND revoked_at IS NULL
                """,
                (now_iso, employee_id),
            )
            connection.commit()
        return cursor.rowcount

    def purge_expired_magic_link_tokens(self, *, now_iso: str) -> int:
        with get_connection(self.db_path) as connection:
            cursor = connection.execute(
                "DELETE FROM magic_link_tokens WHERE datetime(expires_at) <= datetime(?)",
                (now_iso,),
            )
            connection.commit()
        return cursor.rowcount

    # ---- Sessions ----------------------------------------------------------

    def create_session(
        self,
        *,
        role: str,
        subject_id: str | None,
        plaintext_token: str,
        expires_at: str,
    ) -> dict[str, Any]:
        now = datetime.now(timezone.utc).isoformat()
        record = {
            "token_hash": hash_token(plaintext_token),
            "role": role,
            "subject_id": subject_id,
            "created_at": now,
            "expires_at": expires_at,
            "last_seen_at": now,
        }
        with get_connection(self.db_path) as connection:
            connection.execute(
                """
                INSERT INTO sessions (token_hash, role, subject_id, created_at, expires_at, last_seen_at)
                VALUES (:token_hash, :role, :subject_id, :created_at, :expires_at, :last_seen_at)
                """,
                record,
            )
            connection.commit()
        return record

    def get_session(
        self,
        plaintext_token: str,
        *,
        now_iso: str,
    ) -> dict[str, Any] | None:
        token_hash_value = hash_token(plaintext_token)
        with get_connection(self.db_path) as connection:
            row = connection.execute(
                """
                SELECT token_hash, role, subject_id, created_at, expires_at, last_seen_at
                FROM sessions
                WHERE token_hash = ?
                  AND datetime(expires_at) > datetime(?)
                """,
                (token_hash_value, now_iso),
            ).fetchone()
            if row is None:
                return None
            connection.execute(
                "UPDATE sessions SET last_seen_at = ? WHERE token_hash = ?",
                (now_iso, token_hash_value),
            )
            connection.commit()
        return dict(row)

    def delete_session(self, plaintext_token: str) -> bool:
        token_hash_value = hash_token(plaintext_token)
        with get_connection(self.db_path) as connection:
            cursor = connection.execute(
                "DELETE FROM sessions WHERE token_hash = ?",
                (token_hash_value,),
            )
            connection.commit()
        return cursor.rowcount > 0

    def purge_expired_sessions(self, *, now_iso: str) -> int:
        with get_connection(self.db_path) as connection:
            cursor = connection.execute(
                "DELETE FROM sessions WHERE datetime(expires_at) <= datetime(?)",
                (now_iso,),
            )
            connection.commit()
        return cursor.rowcount
