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
        scoring_mode: str = "ai_assisted",
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
            "scoring_mode": scoring_mode,
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
                    scoring_mode,
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
                    :scoring_mode,
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
                SELECT id, name, created_at, scoring_mode, total_score, score_band,
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
                SELECT id, name, created_at, scoring_mode, total_score, score_band,
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
                       app_score_available, provider_score, provider_right_score, provider_left_score,
                       provider_final_score, provider_faults_json, provider_note, review_reason,
                       review_status, reviewed_at
                FROM movement_results
                WHERE assessment_id = ?
                ORDER BY movement_key
                """,
                (assessment_id,),
            ).fetchall()
        result = dict(assessment)
        consent_scope_json = result.pop("consent_scope_json", None)
        result["consent_scope"] = json.loads(consent_scope_json) if consent_scope_json else None
        result["movement_results"] = [self._movement_result_from_row(row) for row in movement_rows]
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

    def _movement_result_from_row(self, row) -> dict[str, Any]:
        record = dict(row)
        record["detected_faults"] = json.loads(record.pop("detected_faults_json"))
        app_metrics_json = record.pop("app_metrics_json", None)
        pose_trace_json = record.pop("pose_trace_json", None)
        quality_json = record.pop("quality_json", None)
        provider_faults_json = record.pop("provider_faults_json", None)
        record["app_metrics"] = json.loads(app_metrics_json) if app_metrics_json else None
        record["pose_trace"] = json.loads(pose_trace_json) if pose_trace_json else None
        record["quality"] = json.loads(quality_json) if quality_json else default_capture_quality()
        record["app_score_available"] = bool(record.get("app_score_available", 1))
        record["provider_faults"] = (
            json.loads(provider_faults_json) if provider_faults_json else None
        )
        provider_final_score = record.get("provider_final_score")
        if provider_final_score is None:
            provider_final_score = record.get("provider_score")
        record["effective_right_score"] = (
            record.get("provider_right_score")
            if record.get("provider_right_score") is not None
            else record.get("right_score")
        )
        record["effective_left_score"] = (
            record.get("provider_left_score")
            if record.get("provider_left_score") is not None
            else record.get("left_score")
        )
        record["effective_final_score"] = (
            provider_final_score
            if provider_final_score is not None
            else record["final_score"]
        )
        return record

    def _recalculate_assessment_total(self, connection, assessment_id: str) -> None:
        total_row = connection.execute(
            """
            SELECT COALESCE(SUM(COALESCE(provider_final_score, provider_score, final_score)), 0)
                   AS total_score
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
            "app_score_available": 1,
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
                    quality_json,
                    app_score_available
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
                    :quality_json,
                    :app_score_available
                )
                ON CONFLICT(assessment_id, movement_key)
                DO UPDATE SET
                    right_score = excluded.right_score,
                    left_score = excluded.left_score,
                    final_score = excluded.final_score,
                    detected_faults_json = excluded.detected_faults_json,
                    app_metrics_json = excluded.app_metrics_json,
                    pose_trace_json = excluded.pose_trace_json,
                    quality_json = excluded.quality_json,
                    app_score_available = excluded.app_score_available
                """,
                record,
            )
            self._recalculate_assessment_total(connection, assessment_id)
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
            "app_score_available": True,
            "effective_right_score": right_score,
            "effective_left_score": left_score,
            "effective_final_score": final_score,
        }

    def save_provider_review(
        self,
        assessment_id: str,
        movement_key: str,
        provider_score: int,
        provider_note: str | None,
        review_reason: str = "provider_review",
    ) -> bool:
        reviewed_at = datetime.now(timezone.utc).isoformat()
        with get_connection(self.db_path) as connection:
            cursor = connection.execute(
                """
                UPDATE movement_results
                SET provider_score = ?,
                    provider_final_score = ?,
                    provider_note = ?,
                    review_reason = ?,
                    reviewed_at = ?,
                    review_status = 'reviewed'
                WHERE assessment_id = ? AND movement_key = ?
                """,
                (
                    provider_score,
                    provider_score,
                    provider_note,
                    review_reason,
                    reviewed_at,
                    assessment_id,
                    movement_key,
                ),
            )
            if cursor.rowcount:
                self._recalculate_assessment_total(connection, assessment_id)
            connection.commit()
        return cursor.rowcount > 0

    def save_manual_scores(
        self,
        *,
        assessment_id: str,
        movement_key: str,
        right: dict[str, Any] | None,
        left: dict[str, Any] | None,
        provider_note: str | None,
        review_reason: str,
        accepted_for_learning: bool,
    ) -> bool:
        if right is None and left is None:
            return False

        reviewed_at = datetime.now(timezone.utc).isoformat()
        existing = self.get_assessment(assessment_id)
        existing_result = None
        if existing is not None:
            existing_result = next(
                (
                    result for result in existing["movement_results"]
                    if result["movement_key"] == movement_key
                ),
                None,
            )
        movement_exists = existing_result is not None
        right_effective = (
            right["score"] if right is not None
            else None if existing_result is None
            else existing_result.get("provider_right_score")
            if existing_result.get("provider_right_score") is not None
            else existing_result.get("right_score")
        )
        left_effective = (
            left["score"] if left is not None
            else None if existing_result is None
            else existing_result.get("provider_left_score")
            if existing_result.get("provider_left_score") is not None
            else existing_result.get("left_score")
        )
        effective_scores = [
            score for score in (right_effective, left_effective)
            if score is not None
        ]
        provider_final_score = min(effective_scores)
        existing_provider_faults = (
            existing_result.get("provider_faults") if existing_result else None
        ) or {}
        right_faults = (
            right["faults"] if right is not None
            else existing_provider_faults.get("right", [])
        )
        left_faults = (
            left["faults"] if left is not None
            else existing_provider_faults.get("left", [])
        )
        provider_faults = {
            "right": right_faults,
            "left": left_faults,
            "summary": sorted({*right_faults, *left_faults}),
        }

        with get_connection(self.db_path) as connection:
            if movement_exists:
                connection.execute(
                    """
                    UPDATE movement_results
                    SET provider_right_score = COALESCE(?, provider_right_score),
                        provider_left_score = COALESCE(?, provider_left_score),
                        provider_final_score = ?,
                        provider_score = ?,
                        provider_faults_json = ?,
                        provider_note = ?,
                        review_reason = ?,
                        reviewed_at = ?,
                        review_status = 'reviewed'
                    WHERE assessment_id = ? AND movement_key = ?
                    """,
                    (
                        None if right is None else right["score"],
                        None if left is None else left["score"],
                        provider_final_score,
                        provider_final_score,
                        json.dumps(provider_faults),
                        provider_note,
                        review_reason,
                        reviewed_at,
                        assessment_id,
                        movement_key,
                    ),
                )
            else:
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
                        app_score_available,
                        provider_right_score,
                        provider_left_score,
                        provider_final_score,
                        provider_score,
                        provider_faults_json,
                        provider_note,
                        review_reason,
                        reviewed_at,
                        review_status
                    )
                    VALUES (
                        :id,
                        :assessment_id,
                        :movement_key,
                        :right_score,
                        :left_score,
                        :final_score,
                        :detected_faults_json,
                        :app_score_available,
                        :provider_right_score,
                        :provider_left_score,
                        :provider_final_score,
                        :provider_score,
                        :provider_faults_json,
                        :provider_note,
                        :review_reason,
                        :reviewed_at,
                        'reviewed'
                    )
                    """,
                    {
                        "id": str(uuid4()),
                        "assessment_id": assessment_id,
                        "movement_key": movement_key,
                        "right_score": None if right is None else right["score"],
                        "left_score": None if left is None else left["score"],
                        "final_score": provider_final_score,
                        "detected_faults_json": json.dumps(provider_faults),
                        "app_score_available": 0,
                        "provider_right_score": None if right is None else right["score"],
                        "provider_left_score": None if left is None else left["score"],
                        "provider_final_score": provider_final_score,
                        "provider_score": provider_final_score,
                        "provider_faults_json": json.dumps(provider_faults),
                        "provider_note": provider_note,
                        "review_reason": review_reason,
                        "reviewed_at": reviewed_at,
                    },
                )

            for side_name, side_payload in (("right", right), ("left", left)):
                if side_payload is None:
                    continue
                app_metrics = side_payload.get("app_metrics")
                excluded_reason = None
                accepted = bool(accepted_for_learning)
                if not app_metrics:
                    accepted = False
                    excluded_reason = "no_app_metrics"
                self._insert_manual_score_entry(
                    connection,
                    assessment_id=assessment_id,
                    movement_key=movement_key,
                    side=side_name,
                    provider_score=side_payload["score"],
                    provider_faults=side_payload["faults"],
                    provider_other_fault=side_payload.get("other_fault"),
                    provider_note=provider_note,
                    review_reason=review_reason,
                    app_score=side_payload.get("app_score"),
                    app_metrics=app_metrics,
                    app_quality=side_payload.get("app_quality"),
                    app_source=side_payload.get("app_source"),
                    accepted_for_learning=accepted,
                    excluded_reason=excluded_reason,
                )
            self._recalculate_assessment_total(connection, assessment_id)
            connection.commit()
        return True

    def _insert_manual_score_entry(
        self,
        connection,
        *,
        assessment_id: str,
        movement_key: str,
        side: str,
        provider_score: int,
        provider_faults: list[str],
        provider_other_fault: str | None,
        provider_note: str | None,
        review_reason: str,
        app_score: int | None,
        app_metrics: dict[str, Any] | None,
        app_quality: dict[str, Any] | None,
        app_source: str | None,
        accepted_for_learning: bool,
        excluded_reason: str | None,
    ) -> None:
        connection.execute(
            """
            INSERT INTO manual_score_entries (
                id,
                created_at,
                assessment_id,
                movement_key,
                side,
                provider_score,
                provider_faults_json,
                provider_other_fault,
                provider_note,
                review_reason,
                app_score,
                app_metrics_json,
                app_quality_json,
                app_source,
                accepted_for_learning,
                excluded_reason
            )
            VALUES (
                :id,
                :created_at,
                :assessment_id,
                :movement_key,
                :side,
                :provider_score,
                :provider_faults_json,
                :provider_other_fault,
                :provider_note,
                :review_reason,
                :app_score,
                :app_metrics_json,
                :app_quality_json,
                :app_source,
                :accepted_for_learning,
                :excluded_reason
            )
            """,
            {
                "id": str(uuid4()),
                "created_at": datetime.now(timezone.utc).isoformat(),
                "assessment_id": assessment_id,
                "movement_key": movement_key,
                "side": side,
                "provider_score": provider_score,
                "provider_faults_json": json.dumps(provider_faults),
                "provider_other_fault": provider_other_fault,
                "provider_note": provider_note,
                "review_reason": review_reason,
                "app_score": app_score,
                "app_metrics_json": json.dumps(app_metrics) if app_metrics else None,
                "app_quality_json": json.dumps(app_quality) if app_quality else None,
                "app_source": app_source,
                "accepted_for_learning": 1 if accepted_for_learning else 0,
                "excluded_reason": excluded_reason,
            },
        )

    def list_learning_entries(self) -> list[dict[str, Any]]:
        with get_connection(self.db_path) as connection:
            rows = connection.execute(
                """
                SELECT id, created_at, assessment_id, movement_key, side,
                       provider_score, provider_faults_json, provider_other_fault,
                       review_reason, app_score, app_metrics_json, app_quality_json,
                       app_source, accepted_for_learning, excluded_reason
                FROM manual_score_entries
                WHERE accepted_for_learning = 1
                  AND app_metrics_json IS NOT NULL
                ORDER BY datetime(created_at) ASC
                """
            ).fetchall()
        entries: list[dict[str, Any]] = []
        for row in rows:
            record = dict(row)
            record["provider_faults"] = json.loads(record.pop("provider_faults_json"))
            record["app_metrics"] = json.loads(record.pop("app_metrics_json"))
            app_quality_json = record.pop("app_quality_json", None)
            record["app_quality"] = json.loads(app_quality_json) if app_quality_json else None
            record["accepted_for_learning"] = bool(record["accepted_for_learning"])
            entries.append(record)
        return entries

    def get_active_threshold_overrides(self) -> dict[str, dict[str, float]]:
        with get_connection(self.db_path) as connection:
            rows = connection.execute(
                """
                SELECT movement_key, threshold_key, new_value
                FROM scoring_threshold_decisions
                WHERE status = 'approved'
                ORDER BY datetime(created_at) ASC
                """
            ).fetchall()
        overrides: dict[str, dict[str, float]] = {}
        for row in rows:
            movement = overrides.setdefault(row["movement_key"], {})
            movement[row["threshold_key"]] = float(row["new_value"])
        return overrides

    def save_threshold_decision(
        self,
        *,
        movement_key: str,
        threshold_key: str,
        old_value: float,
        new_value: float,
        status: str,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        record = {
            "id": str(uuid4()),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "movement_key": movement_key,
            "threshold_key": threshold_key,
            "old_value": old_value,
            "new_value": new_value,
            "status": status,
            "metadata_json": json.dumps(metadata or {}, sort_keys=True),
        }
        with get_connection(self.db_path) as connection:
            connection.execute(
                """
                INSERT INTO scoring_threshold_decisions (
                    id,
                    created_at,
                    movement_key,
                    threshold_key,
                    old_value,
                    new_value,
                    status,
                    metadata_json
                )
                VALUES (
                    :id,
                    :created_at,
                    :movement_key,
                    :threshold_key,
                    :old_value,
                    :new_value,
                    :status,
                    :metadata_json
                )
                """,
                record,
            )
            connection.commit()
        return record

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
