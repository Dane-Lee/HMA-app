from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from .auth import hash_password, hash_token, verify_password
from .database import get_connection


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def compute_score_band(total_score: int) -> str:
    if total_score <= 5:
        return "High opportunity for improvement"
    if total_score <= 10:
        return "Moderate opportunity for improvement"
    return "Low opportunity for improvement"


class ManualRepository:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path

    # ---- Providers and sessions -----------------------------------------

    def provider_count(self) -> int:
        with get_connection(self.db_path) as connection:
            row = connection.execute("SELECT COUNT(*) AS count FROM providers").fetchone()
        return int(row["count"])

    def create_provider(
        self,
        *,
        username: str,
        display_name: str,
        password: str,
        mfa_secret: str | None = None,
        role: str = "admin",
    ) -> dict[str, Any]:
        record = {
            "id": str(uuid4()),
            "username": username.strip().lower(),
            "display_name": display_name.strip() or username.strip(),
            "password_hash": hash_password(password),
            "mfa_secret": mfa_secret or None,
            "mfa_enabled": 1 if mfa_secret else 0,
            "role": role,
            "created_at": now_utc().isoformat(),
        }
        with get_connection(self.db_path) as connection:
            connection.execute(
                """
                INSERT INTO providers (
                    id, username, display_name, password_hash, mfa_secret,
                    mfa_enabled, role, created_at
                )
                VALUES (
                    :id, :username, :display_name, :password_hash, :mfa_secret,
                    :mfa_enabled, :role, :created_at
                )
                """,
                record,
            )
            connection.commit()
        return self.get_provider(record["id"])  # type: ignore[return-value]

    def get_provider(self, provider_id: str) -> dict[str, Any] | None:
        with get_connection(self.db_path) as connection:
            row = connection.execute(
                "SELECT * FROM providers WHERE id = ?",
                (provider_id,),
            ).fetchone()
        return self._provider_from_row(row) if row else None

    def get_provider_by_username(self, username: str) -> dict[str, Any] | None:
        with get_connection(self.db_path) as connection:
            row = connection.execute(
                "SELECT * FROM providers WHERE username = ?",
                (username.strip().lower(),),
            ).fetchone()
        return self._provider_from_row(row) if row else None

    def verify_provider_password(self, provider: dict[str, Any], password: str) -> bool:
        return verify_password(password, provider["password_hash"])

    def record_login_failure(self, provider_id: str, *, max_failures: int = 5) -> None:
        provider = self.get_provider(provider_id)
        if provider is None:
            return
        failed_count = int(provider["failed_login_count"]) + 1
        locked_until = None
        if failed_count >= max_failures:
            locked_until = (now_utc() + timedelta(minutes=15)).isoformat()
        with get_connection(self.db_path) as connection:
            connection.execute(
                """
                UPDATE providers
                SET failed_login_count = ?, locked_until = ?
                WHERE id = ?
                """,
                (failed_count, locked_until, provider_id),
            )
            connection.commit()

    def record_login_success(self, provider_id: str) -> None:
        with get_connection(self.db_path) as connection:
            connection.execute(
                """
                UPDATE providers
                SET failed_login_count = 0, locked_until = NULL, last_login_at = ?
                WHERE id = ?
                """,
                (now_utc().isoformat(), provider_id),
            )
            connection.commit()

    def create_provider_session(self, *, provider_id: str, token: str, expires_at: datetime) -> None:
        now = now_utc().isoformat()
        with get_connection(self.db_path) as connection:
            connection.execute(
                """
                INSERT INTO provider_sessions (token_hash, provider_id, created_at, expires_at, last_seen_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (hash_token(token), provider_id, now, expires_at.isoformat(), now),
            )
            connection.commit()

    def get_provider_by_session(self, token: str, *, now_iso: str) -> dict[str, Any] | None:
        with get_connection(self.db_path) as connection:
            row = connection.execute(
                """
                SELECT p.*
                FROM provider_sessions s
                JOIN providers p ON p.id = s.provider_id
                WHERE s.token_hash = ?
                  AND datetime(s.expires_at) > datetime(?)
                  AND p.status = 'active'
                """,
                (hash_token(token), now_iso),
            ).fetchone()
            if row is not None:
                connection.execute(
                    "UPDATE provider_sessions SET last_seen_at = ? WHERE token_hash = ?",
                    (now_iso, hash_token(token)),
                )
                connection.commit()
        return self._provider_from_row(row) if row else None

    def delete_provider_session(self, token: str) -> bool:
        with get_connection(self.db_path) as connection:
            cursor = connection.execute(
                "DELETE FROM provider_sessions WHERE token_hash = ?",
                (hash_token(token),),
            )
            connection.commit()
        return cursor.rowcount > 0

    def purge_expired_provider_sessions(self, *, now_iso: str) -> int:
        with get_connection(self.db_path) as connection:
            cursor = connection.execute(
                "DELETE FROM provider_sessions WHERE datetime(expires_at) <= datetime(?)",
                (now_iso,),
            )
            connection.commit()
        return cursor.rowcount

    def _provider_from_row(self, row) -> dict[str, Any]:
        record = dict(row)
        record["mfa_enabled"] = bool(record["mfa_enabled"])
        return record

    # ---- Employees, assessments, scores ---------------------------------

    def create_employee(
        self,
        *,
        name: str,
        employer: str,
        email: str | None = None,
        notes: str | None = None,
    ) -> dict[str, Any]:
        record = {
            "id": str(uuid4()),
            "name": name.strip(),
            "employer": employer.strip(),
            "email": (email or "").strip() or None,
            "notes": (notes or "").strip() or None,
            "created_at": now_utc().isoformat(),
        }
        with get_connection(self.db_path) as connection:
            connection.execute(
                """
                INSERT INTO employees (id, name, employer, email, notes, created_at)
                VALUES (:id, :name, :employer, :email, :notes, :created_at)
                """,
                record,
            )
            connection.commit()
        return record

    def get_employee(self, employee_id: str) -> dict[str, Any] | None:
        with get_connection(self.db_path) as connection:
            row = connection.execute(
                "SELECT * FROM employees WHERE id = ?",
                (employee_id,),
            ).fetchone()
        return dict(row) if row else None

    def create_assessment(
        self,
        *,
        participant_name: str,
        provider_id: str,
        employee_id: str | None,
        consent_notice_version: str,
        consent_scope: dict[str, bool],
        retention_days: int,
    ) -> dict[str, Any]:
        created_at = now_utc()
        record = {
            "id": str(uuid4()),
            "participant_name": participant_name.strip(),
            "employee_id": employee_id,
            "created_by_provider_id": provider_id,
            "status": "draft",
            "total_score": 0,
            "score_band": compute_score_band(0),
            "consent_notice_version": consent_notice_version,
            "consent_scope_json": json.dumps(consent_scope, sort_keys=True),
            "created_at": created_at.isoformat(),
            "retention_expires_at": (created_at + timedelta(days=retention_days)).isoformat(),
        }
        with get_connection(self.db_path) as connection:
            connection.execute(
                """
                INSERT INTO manual_assessments (
                    id, participant_name, employee_id, created_by_provider_id,
                    status, total_score, score_band, consent_notice_version,
                    consent_scope_json, created_at, retention_expires_at
                )
                VALUES (
                    :id, :participant_name, :employee_id, :created_by_provider_id,
                    :status, :total_score, :score_band, :consent_notice_version,
                    :consent_scope_json, :created_at, :retention_expires_at
                )
                """,
                record,
            )
            connection.commit()
        return self.get_assessment(record["id"])  # type: ignore[return-value]

    def assessment_exists(self, assessment_id: str) -> bool:
        with get_connection(self.db_path) as connection:
            row = connection.execute(
                "SELECT 1 FROM manual_assessments WHERE id = ?",
                (assessment_id,),
            ).fetchone()
        return row is not None

    def list_assessments(self) -> list[dict[str, Any]]:
        with get_connection(self.db_path) as connection:
            rows = connection.execute(
                """
                SELECT a.*,
                       e.name AS employee_name,
                       e.employer AS employee_employer,
                       (
                           SELECT COUNT(*)
                           FROM manual_review_videos v
                           WHERE v.assessment_id = a.id AND v.deleted_at IS NULL AND v.video_path IS NOT NULL
                       ) AS remaining_video_count
                FROM manual_assessments a
                LEFT JOIN employees e ON e.id = a.employee_id
                ORDER BY datetime(a.created_at) DESC
                """
            ).fetchall()
        return [self._assessment_summary_from_row(row) for row in rows]

    def get_assessment(self, assessment_id: str) -> dict[str, Any] | None:
        with get_connection(self.db_path) as connection:
            assessment = connection.execute(
                """
                SELECT a.*,
                       e.name AS employee_name,
                       e.employer AS employee_employer,
                       e.email AS employee_email,
                       (
                           SELECT COUNT(*)
                           FROM manual_review_videos v
                           WHERE v.assessment_id = a.id AND v.deleted_at IS NULL AND v.video_path IS NOT NULL
                       ) AS remaining_video_count
                FROM manual_assessments a
                LEFT JOIN employees e ON e.id = a.employee_id
                WHERE a.id = ?
                """,
                (assessment_id,),
            ).fetchone()
            if assessment is None:
                return None
            movement_rows = connection.execute(
                """
                SELECT *
                FROM manual_movement_results
                WHERE assessment_id = ?
                ORDER BY movement_key
                """,
                (assessment_id,),
            ).fetchall()
            video_rows = connection.execute(
                """
                SELECT *
                FROM manual_review_videos
                WHERE assessment_id = ?
                ORDER BY datetime(created_at), movement_key, side
                """,
                (assessment_id,),
            ).fetchall()
            upload_rows = connection.execute(
                """
                SELECT id, employee_id, assessment_id, status, created_at, expires_at, revoked_at, submitted_at
                FROM upload_sessions
                WHERE assessment_id = ?
                ORDER BY datetime(created_at) DESC
                """,
                (assessment_id,),
            ).fetchall()
        record = self._assessment_summary_from_row(assessment)
        record["movement_results"] = [self._movement_result_from_row(row) for row in movement_rows]
        record["review_videos"] = [self._review_video_from_row(row) for row in video_rows]
        record["upload_sessions"] = [dict(row) for row in upload_rows]
        return record

    def list_expired_assessments(self, now_iso: str) -> list[dict[str, Any]]:
        with get_connection(self.db_path) as connection:
            rows = connection.execute(
                """
                SELECT id
                FROM manual_assessments
                WHERE retention_expires_at IS NOT NULL
                  AND datetime(retention_expires_at) <= datetime(?)
                """,
                (now_iso,),
            ).fetchall()
        return [dict(row) for row in rows]

    def delete_assessment(self, assessment_id: str) -> bool:
        with get_connection(self.db_path) as connection:
            cursor = connection.execute(
                "DELETE FROM manual_assessments WHERE id = ?",
                (assessment_id,),
            )
            connection.commit()
        return cursor.rowcount > 0

    def save_manual_score(
        self,
        *,
        assessment_id: str,
        movement_key: str,
        right_score: int | None,
        left_score: int | None,
        faults: dict[str, list[str]],
        provider_note: str | None,
    ) -> dict[str, Any]:
        scores = [score for score in (right_score, left_score) if score is not None]
        final_score = min(scores)
        reviewed_at = now_utc().isoformat()
        record = {
            "id": str(uuid4()),
            "assessment_id": assessment_id,
            "movement_key": movement_key,
            "right_score": right_score,
            "left_score": left_score,
            "final_score": final_score,
            "faults_json": json.dumps(faults, sort_keys=True),
            "provider_note": provider_note,
            "reviewed_at": reviewed_at,
        }
        with get_connection(self.db_path) as connection:
            connection.execute(
                """
                INSERT INTO manual_movement_results (
                    id, assessment_id, movement_key, right_score, left_score,
                    final_score, faults_json, provider_note, reviewed_at
                )
                VALUES (
                    :id, :assessment_id, :movement_key, :right_score, :left_score,
                    :final_score, :faults_json, :provider_note, :reviewed_at
                )
                ON CONFLICT(assessment_id, movement_key)
                DO UPDATE SET
                    right_score = excluded.right_score,
                    left_score = excluded.left_score,
                    final_score = excluded.final_score,
                    faults_json = excluded.faults_json,
                    provider_note = excluded.provider_note,
                    reviewed_at = excluded.reviewed_at
                """,
                record,
            )
            self._recalculate_total(connection, assessment_id)
            connection.commit()
        return self.get_assessment(assessment_id)  # type: ignore[return-value]

    def complete_assessment(
        self,
        assessment_id: str,
        *,
        videos_deleted_at: str | None = None,
    ) -> dict[str, Any] | None:
        with get_connection(self.db_path) as connection:
            connection.execute(
                """
                UPDATE manual_assessments
                SET status = 'completed',
                    completed_at = COALESCE(completed_at, ?),
                    videos_deleted_at = COALESCE(?, videos_deleted_at)
                WHERE id = ?
                """,
                (now_utc().isoformat(), videos_deleted_at, assessment_id),
            )
            connection.commit()
        return self.get_assessment(assessment_id)

    def _recalculate_total(self, connection, assessment_id: str) -> None:
        row = connection.execute(
            """
            SELECT COALESCE(SUM(final_score), 0) AS total_score
            FROM manual_movement_results
            WHERE assessment_id = ?
            """,
            (assessment_id,),
        ).fetchone()
        total = int(row["total_score"])
        connection.execute(
            """
            UPDATE manual_assessments
            SET total_score = ?, score_band = ?
            WHERE id = ?
            """,
            (total, compute_score_band(total), assessment_id),
        )

    def _assessment_summary_from_row(self, row) -> dict[str, Any]:
        record = dict(row)
        consent_json = record.pop("consent_scope_json", None)
        record["consent_scope"] = json.loads(consent_json) if consent_json else None
        record["remaining_video_count"] = int(record.get("remaining_video_count") or 0)
        return record

    def _movement_result_from_row(self, row) -> dict[str, Any]:
        record = dict(row)
        record["faults"] = json.loads(record.pop("faults_json"))
        return record

    # ---- Review videos ----------------------------------------------------

    def get_review_video_by_slot(self, assessment_id: str, movement_key: str, side: str) -> dict[str, Any] | None:
        with get_connection(self.db_path) as connection:
            row = connection.execute(
                """
                SELECT *
                FROM manual_review_videos
                WHERE assessment_id = ? AND movement_key = ? AND side = ?
                """,
                (assessment_id, movement_key, side),
            ).fetchone()
        return self._review_video_from_row(row) if row else None

    def get_review_video(self, assessment_id: str, video_id: str) -> dict[str, Any] | None:
        with get_connection(self.db_path) as connection:
            row = connection.execute(
                """
                SELECT *
                FROM manual_review_videos
                WHERE assessment_id = ? AND id = ?
                """,
                (assessment_id, video_id),
            ).fetchone()
        return self._review_video_from_row(row) if row else None

    def list_review_videos(self, assessment_id: str) -> list[dict[str, Any]]:
        with get_connection(self.db_path) as connection:
            rows = connection.execute(
                """
                SELECT *
                FROM manual_review_videos
                WHERE assessment_id = ?
                ORDER BY datetime(created_at), movement_key, side
                """,
                (assessment_id,),
            ).fetchall()
        return [self._review_video_from_row(row) for row in rows]

    def upsert_review_video(
        self,
        *,
        assessment_id: str,
        upload_session_id: str | None,
        movement_key: str,
        side: str,
        client_video_id: str | None,
        original_filename: str | None,
        content_type: str | None,
        file_size_bytes: int,
        video_path: str,
        upload_source: str,
        expires_at: str,
    ) -> dict[str, Any]:
        record = {
            "id": str(uuid4()),
            "assessment_id": assessment_id,
            "upload_session_id": upload_session_id,
            "movement_key": movement_key,
            "side": side,
            "client_video_id": client_video_id,
            "original_filename": original_filename,
            "content_type": content_type,
            "file_size_bytes": file_size_bytes,
            "video_path": video_path,
            "upload_source": upload_source,
            "created_at": now_utc().isoformat(),
            "expires_at": expires_at,
        }
        with get_connection(self.db_path) as connection:
            connection.execute(
                """
                INSERT INTO manual_review_videos (
                    id, assessment_id, upload_session_id, movement_key, side,
                    client_video_id, original_filename, content_type,
                    file_size_bytes, video_path, upload_source, created_at, expires_at
                )
                VALUES (
                    :id, :assessment_id, :upload_session_id, :movement_key, :side,
                    :client_video_id, :original_filename, :content_type,
                    :file_size_bytes, :video_path, :upload_source, :created_at, :expires_at
                )
                ON CONFLICT(assessment_id, movement_key, side)
                DO UPDATE SET
                    id = excluded.id,
                    upload_session_id = excluded.upload_session_id,
                    client_video_id = excluded.client_video_id,
                    original_filename = excluded.original_filename,
                    content_type = excluded.content_type,
                    file_size_bytes = excluded.file_size_bytes,
                    video_path = excluded.video_path,
                    upload_source = excluded.upload_source,
                    created_at = excluded.created_at,
                    expires_at = excluded.expires_at,
                    deleted_at = NULL,
                    deleted_by_provider_id = NULL,
                    deletion_reason = NULL
                """,
                record,
            )
            row = connection.execute(
                "SELECT * FROM manual_review_videos WHERE id = ?",
                (record["id"],),
            ).fetchone()
            connection.commit()
        return self._review_video_from_row(row)

    def mark_review_videos_deleted(
        self,
        video_ids: list[str],
        *,
        deleted_at: str,
        provider_id: str | None,
        reason: str,
    ) -> int:
        if not video_ids:
            return 0
        placeholders = ",".join("?" for _ in video_ids)
        with get_connection(self.db_path) as connection:
            cursor = connection.execute(
                f"""
                UPDATE manual_review_videos
                SET video_path = NULL,
                    deleted_at = ?,
                    deleted_by_provider_id = ?,
                    deletion_reason = ?
                WHERE id IN ({placeholders})
                """,
                (deleted_at, provider_id, reason, *video_ids),
            )
            connection.commit()
        return cursor.rowcount

    def list_expired_review_videos(self, now_iso: str) -> list[dict[str, Any]]:
        with get_connection(self.db_path) as connection:
            rows = connection.execute(
                """
                SELECT *
                FROM manual_review_videos
                WHERE video_path IS NOT NULL
                  AND deleted_at IS NULL
                  AND datetime(expires_at) <= datetime(?)
                """,
                (now_iso,),
            ).fetchall()
        return [self._review_video_from_row(row) for row in rows]

    def _review_video_from_row(self, row) -> dict[str, Any]:
        record = dict(row)
        record["video_url"] = None
        if record.get("video_path") and not record.get("deleted_at"):
            record["video_url"] = (
                f"/api/assessments/{record['assessment_id']}/review-videos/{record['id']}/file"
            )
        return record

    # ---- Upload sessions --------------------------------------------------

    def create_upload_session(
        self,
        *,
        employee_id: str,
        assessment_id: str,
        provider_id: str,
        plaintext_token: str,
        allowed_slots: list[dict[str, str]],
        expires_at: datetime,
    ) -> dict[str, Any]:
        record = {
            "id": str(uuid4()),
            "token_hash": hash_token(plaintext_token),
            "employee_id": employee_id,
            "assessment_id": assessment_id,
            "created_by_provider_id": provider_id,
            "allowed_slots_json": json.dumps(allowed_slots, sort_keys=True),
            "status": "active",
            "created_at": now_utc().isoformat(),
            "expires_at": expires_at.isoformat(),
        }
        with get_connection(self.db_path) as connection:
            connection.execute(
                """
                INSERT INTO upload_sessions (
                    id, token_hash, employee_id, assessment_id,
                    created_by_provider_id, allowed_slots_json, status,
                    created_at, expires_at
                )
                VALUES (
                    :id, :token_hash, :employee_id, :assessment_id,
                    :created_by_provider_id, :allowed_slots_json, :status,
                    :created_at, :expires_at
                )
                """,
                record,
            )
            connection.commit()
        return self.get_upload_session_by_token(plaintext_token, now_iso=now_utc().isoformat())  # type: ignore[return-value]

    def get_upload_session_by_token(self, token: str, *, now_iso: str) -> dict[str, Any] | None:
        with get_connection(self.db_path) as connection:
            row = connection.execute(
                """
                SELECT *
                FROM upload_sessions
                WHERE token_hash = ?
                  AND revoked_at IS NULL
                  AND datetime(expires_at) > datetime(?)
                """,
                (hash_token(token), now_iso),
            ).fetchone()
        return self._upload_session_from_row(row) if row else None

    def revoke_upload_session(self, session_id: str, *, now_iso: str) -> bool:
        with get_connection(self.db_path) as connection:
            cursor = connection.execute(
                """
                UPDATE upload_sessions
                SET revoked_at = ?, status = 'revoked'
                WHERE id = ? AND revoked_at IS NULL
                """,
                (now_iso, session_id),
            )
            connection.commit()
        return cursor.rowcount > 0

    def submit_upload_session(self, session_id: str, *, now_iso: str) -> bool:
        with get_connection(self.db_path) as connection:
            cursor = connection.execute(
                """
                UPDATE upload_sessions
                SET submitted_at = ?, status = 'submitted'
                WHERE id = ? AND revoked_at IS NULL
                """,
                (now_iso, session_id),
            )
            connection.commit()
        return cursor.rowcount > 0

    def _upload_session_from_row(self, row) -> dict[str, Any]:
        record = dict(row)
        record["allowed_slots"] = json.loads(record.pop("allowed_slots_json"))
        return record

    # ---- Audit ------------------------------------------------------------

    def log_audit_event(
        self,
        event_type: str,
        *,
        provider_id: str | None = None,
        employee_id: str | None = None,
        assessment_id: str | None = None,
        movement_key: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        record = {
            "id": str(uuid4()),
            "created_at": now_utc().isoformat(),
            "event_type": event_type,
            "provider_id": provider_id,
            "employee_id": employee_id,
            "assessment_id": assessment_id,
            "movement_key": movement_key,
            "metadata_json": json.dumps(metadata or {}, sort_keys=True),
        }
        with get_connection(self.db_path) as connection:
            connection.execute(
                """
                INSERT INTO audit_events (
                    id, created_at, event_type, provider_id, employee_id,
                    assessment_id, movement_key, metadata_json
                )
                VALUES (
                    :id, :created_at, :event_type, :provider_id, :employee_id,
                    :assessment_id, :movement_key, :metadata_json
                )
                """,
                record,
            )
            connection.commit()
