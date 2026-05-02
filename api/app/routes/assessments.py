from __future__ import annotations

import logging
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

import yaml
from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile, status
from fastapi.responses import FileResponse, Response

from ..repository import AssessmentRepository
from ..runtime import RuntimeState
from ..schemas import (
    AssessmentCreateRequest,
    CaptureResponse,
    DraftCaptureResponse,
    FinalizeMovementRequest,
    MovementDefinitionResponse,
    ProviderReviewRequest,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["assessments"])
VIDEO_SUFFIXES = {".webm", ".mp4", ".mov", ".m4v", ".avi", ".mpeg", ".mpg"}


def get_runtime(request: Request) -> RuntimeState:
    return request.app.state.runtime


def get_repository(request: Request) -> AssessmentRepository:
    return get_runtime(request).repository


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _is_video_upload(video: UploadFile) -> bool:
    suffix = Path(video.filename or "").suffix.lower()
    content_type = (video.content_type or "").lower()
    return content_type.startswith("video/") or suffix in VIDEO_SUFFIXES


def _is_under_directory(path: Path, directory: Path) -> bool:
    try:
        path.resolve().relative_to(directory.resolve())
        return True
    except ValueError:
        return False


def _consent_scope(payload: AssessmentCreateRequest) -> dict[str, bool]:
    return {
        "voluntary_wellness": payload.consent.voluntary_wellness,
        "purpose_limited": payload.consent.purpose_limited,
        "no_employment_decision": payload.consent.no_employment_decision,
        "video_retention_acknowledged": payload.consent.video_retention_acknowledged,
    }


def _draft_capture_response(record: dict, request: Request) -> DraftCaptureResponse:
    video_url = None
    if record.get("video_path"):
        video_url = (
            f"/api/assessments/{record['assessment_id']}/draft-captures/{record['id']}/video"
        )
    return DraftCaptureResponse(
        id=record["id"],
        assessment_id=record["assessment_id"],
        movement_key=record["movement_key"],
        side=record["side"],
        client_capture_id=record["client_capture_id"],
        score=record["score"],
        detected_faults=record["detected_faults"],
        confidence=record["confidence"],
        metrics=record["metrics"],
        source=record["source"],
        pose_trace=record.get("pose_trace"),
        quality=record.get("quality"),
        original_filename=record["original_filename"],
        content_type=record["content_type"],
        file_size_bytes=record["file_size_bytes"],
        created_at=record["created_at"],
        expires_at=record["expires_at"],
        video_url=video_url,
        video_deleted_at=record["video_deleted_at"],
    )


def _cleanup_expired_draft_videos(runtime: RuntimeState) -> None:
    now = _now_utc().isoformat()
    expired = runtime.repository.list_expired_draft_videos(now)
    deleted_ids: list[str] = []
    for record in expired:
        raw_path = record.get("video_path")
        if not raw_path:
            continue
        path = Path(raw_path)
        if path.exists() and _is_under_directory(path, runtime.settings.draft_capture_dir):
            path.unlink()
        deleted_ids.append(record["id"])
    runtime.repository.mark_draft_videos_deleted(deleted_ids, now)


def _delete_assessment_files_and_row(
    runtime: RuntimeState,
    assessment_id: str,
    *,
    event_type: str,
    metadata: dict | None = None,
) -> bool:
    draft_captures = runtime.repository.list_draft_captures(assessment_id)
    removed_video_count = 0
    for record in draft_captures:
        raw_path = record.get("video_path")
        if not raw_path:
            continue
        path = Path(raw_path)
        if path.exists() and _is_under_directory(path, runtime.settings.draft_capture_dir):
            path.unlink()
            removed_video_count += 1
    deleted = runtime.repository.delete_assessment(assessment_id)
    if deleted:
        runtime.repository.log_audit_event(
            event_type,
            assessment_id=assessment_id,
            metadata={
                **(metadata or {}),
                "draft_videos_removed": removed_video_count,
            },
        )
    return deleted


def _purge_expired_assessments(runtime: RuntimeState) -> None:
    now = _now_utc().isoformat()
    for assessment in runtime.repository.list_expired_assessments(now):
        _delete_assessment_files_and_row(
            runtime,
            assessment["id"],
            event_type="retention_purge",
            metadata={"reason": "assessment_retention_expired"},
        )


@router.get("/health")
def healthcheck() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/movements", response_model=list[MovementDefinitionResponse])
def list_movements(request: Request):
    return get_runtime(request).catalog.list()


@router.get("/thresholds")
def get_thresholds(request: Request):
    path = get_runtime(request).settings.thresholds_path
    return yaml.safe_load(path.read_text(encoding="utf-8"))


@router.post("/assessments", status_code=status.HTTP_201_CREATED)
def create_assessment(payload: AssessmentCreateRequest, request: Request):
    runtime = get_runtime(request)
    _purge_expired_assessments(runtime)
    repository = runtime.repository
    assessment = repository.create_assessment(
        payload.name,
        consent_notice_version=payload.consent.notice_version,
        consent_scope=_consent_scope(payload),
        retention_days=runtime.settings.assessment_retention_days,
    )
    repository.log_audit_event(
        "assessment_create",
        assessment_id=assessment["id"],
        metadata={
            "privacy_posture": assessment["privacy_posture"],
            "assessment_retention_days": runtime.settings.assessment_retention_days,
        },
    )
    detail = repository.get_assessment(assessment["id"])
    return detail


@router.post("/mobile-capture/assessments", status_code=status.HTTP_201_CREATED)
def create_mobile_capture_assessment(payload: AssessmentCreateRequest, request: Request):
    return create_assessment(payload, request)


@router.get("/assessments")
def list_assessments(request: Request):
    runtime = get_runtime(request)
    _purge_expired_assessments(runtime)
    return runtime.repository.list_assessments()


@router.get("/assessments/{assessment_id}")
def get_assessment(assessment_id: str, request: Request):
    runtime = get_runtime(request)
    _purge_expired_assessments(runtime)
    assessment = runtime.repository.get_assessment(assessment_id)
    if assessment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assessment not found.")
    return assessment


@router.delete("/assessments/{assessment_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_assessment(assessment_id: str, request: Request):
    runtime = get_runtime(request)
    _purge_expired_assessments(runtime)
    if not runtime.repository.assessment_exists(assessment_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assessment not found.")
    _delete_assessment_files_and_row(
        runtime,
        assessment_id,
        event_type="assessment_delete",
        metadata={"reason": "manual_delete"},
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/assessments/{assessment_id}/movements/{movement_key}/captures",
    response_model=CaptureResponse,
)
async def score_capture(
    assessment_id: str,
    movement_key: str,
    request: Request,
    side: str = Form(...),
    video: UploadFile = File(...),
):
    runtime = get_runtime(request)
    _purge_expired_assessments(runtime)
    if not runtime.repository.assessment_exists(assessment_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assessment not found.")
    movement = runtime.catalog.get(movement_key)
    if movement is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unknown movement.")
    if side not in movement["sides"]:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid side for movement.")

    suffix = Path(video.filename or "capture.webm").suffix or ".webm"
    temp_path = runtime.settings.temp_dir / f"{uuid4()}{suffix}"
    logger.debug("TEMP | created %s", temp_path)
    try:
        temp_path.write_bytes(await video.read())
        result = runtime.scoring_service.analyze_capture(movement_key, side, temp_path)
        return CaptureResponse(
            movement_key=result.movement_key,
            side=result.side,  # type: ignore[arg-type]
            score=result.score,
            detected_faults=result.detected_faults,
            confidence=result.confidence,
            metrics=result.metrics,
            source=result.source,
            pose_trace=asdict(result.pose_trace) if result.pose_trace else None,
            quality=asdict(result.quality),
        )
    finally:
        await video.close()
        if temp_path.exists():
            temp_path.unlink()
            logger.debug("TEMP | deleted %s", temp_path)


@router.get(
    "/assessments/{assessment_id}/draft-captures",
    response_model=list[DraftCaptureResponse],
)
def list_draft_captures(assessment_id: str, request: Request):
    runtime = get_runtime(request)
    _purge_expired_assessments(runtime)
    if not runtime.repository.assessment_exists(assessment_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assessment not found.")
    _cleanup_expired_draft_videos(runtime)
    return [
        _draft_capture_response(record, request)
        for record in runtime.repository.list_draft_captures(assessment_id)
    ]


@router.post(
    "/assessments/{assessment_id}/draft-captures",
    response_model=DraftCaptureResponse,
)
async def upload_draft_capture(
    assessment_id: str,
    request: Request,
    movement_key: str = Form(...),
    side: str = Form(...),
    client_capture_id: str = Form(...),
    video: UploadFile = File(...),
):
    runtime = get_runtime(request)
    _purge_expired_assessments(runtime)
    if not runtime.repository.assessment_exists(assessment_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assessment not found.")
    movement = runtime.catalog.get(movement_key)
    if movement is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unknown movement.")
    if side not in movement["sides"]:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid side for movement.")
    if not client_capture_id.strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing client capture id.")
    if not _is_video_upload(video):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Upload must be a video file.")

    existing = runtime.repository.get_draft_capture_by_client_id(
        assessment_id,
        client_capture_id.strip(),
    )
    if existing is not None:
        return _draft_capture_response(existing, request)

    body = await video.read()
    await video.close()
    if len(body) > runtime.settings.max_upload_bytes:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="Video file is too large.")

    suffix = Path(video.filename or "capture.webm").suffix.lower() or ".webm"
    if suffix not in VIDEO_SUFFIXES:
        suffix = ".webm"
    runtime.settings.draft_capture_dir.mkdir(parents=True, exist_ok=True)
    capture_id = str(uuid4())
    stored_path = runtime.settings.draft_capture_dir / f"{capture_id}{suffix}"
    old_record = runtime.repository.get_draft_capture_by_slot(assessment_id, movement_key, side)

    try:
        stored_path.write_bytes(body)
        result = runtime.scoring_service.analyze_capture(movement_key, side, stored_path)
        created_at = _now_utc()
        expires_at = created_at + timedelta(days=runtime.settings.draft_capture_retention_days)
        record = runtime.repository.upsert_draft_capture(
            assessment_id=assessment_id,
            movement_key=movement_key,
            side=side,
            client_capture_id=client_capture_id.strip(),
            score=result.score,
            detected_faults=result.detected_faults,
            metrics=result.metrics,
            pose_trace=asdict(result.pose_trace) if result.pose_trace else None,
            quality=asdict(result.quality),
            confidence=result.confidence,
            source=result.source,
            original_filename=video.filename,
            content_type=video.content_type,
            file_size_bytes=len(body),
            video_path=str(stored_path),
            created_at=created_at.isoformat(),
            expires_at=expires_at.isoformat(),
        )
    except Exception:
        if stored_path.exists():
            stored_path.unlink()
        raise

    if old_record and old_record.get("video_path") and old_record["video_path"] != str(stored_path):
        old_path = Path(old_record["video_path"])
        if old_path.exists() and _is_under_directory(old_path, runtime.settings.draft_capture_dir):
            old_path.unlink()
    runtime.repository.log_audit_event(
        "draft_capture_upload",
        assessment_id=assessment_id,
        movement_key=movement_key,
        metadata={
            "side": side,
            "file_size_bytes": len(body),
            "replaced_existing": bool(old_record),
        },
    )
    return _draft_capture_response(record, request)


@router.get("/assessments/{assessment_id}/draft-captures/{capture_id}/video")
def get_draft_capture_video(assessment_id: str, capture_id: str, request: Request):
    runtime = get_runtime(request)
    _purge_expired_assessments(runtime)
    if not runtime.repository.assessment_exists(assessment_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assessment not found.")
    _cleanup_expired_draft_videos(runtime)
    record = runtime.repository.get_draft_capture(assessment_id, capture_id)
    if record is None or not record.get("video_path"):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Review video is unavailable.")
    path = Path(record["video_path"])
    if not _is_under_directory(path, runtime.settings.draft_capture_dir):
        runtime.repository.mark_draft_videos_deleted([capture_id], _now_utc().isoformat())
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Review video is unavailable.")
    if not path.exists():
        runtime.repository.mark_draft_videos_deleted([capture_id], _now_utc().isoformat())
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Review video is unavailable.")
    return FileResponse(
        path,
        media_type=record["content_type"] or "video/mp4",
        filename=record["original_filename"] or path.name,
    )


@router.delete(
    "/assessments/{assessment_id}/draft-captures/{capture_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_draft_capture(assessment_id: str, capture_id: str, request: Request):
    runtime = get_runtime(request)
    _purge_expired_assessments(runtime)
    if not runtime.repository.assessment_exists(assessment_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assessment not found.")
    record = runtime.repository.delete_draft_capture(assessment_id, capture_id)
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Draft capture not found.")
    if record.get("video_path"):
        path = Path(record["video_path"])
        if path.exists() and _is_under_directory(path, runtime.settings.draft_capture_dir):
            path.unlink()
    runtime.repository.log_audit_event(
        "draft_capture_delete",
        assessment_id=assessment_id,
        movement_key=record["movement_key"],
        metadata={
            "side": record["side"],
            "had_video": bool(record.get("video_path")),
        },
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/assessments/{assessment_id}/movements/{movement_key}/finalize")
def finalize_movement(
    assessment_id: str,
    movement_key: str,
    payload: FinalizeMovementRequest,
    request: Request,
):
    runtime = get_runtime(request)
    _purge_expired_assessments(runtime)
    if not runtime.repository.assessment_exists(assessment_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assessment not found.")
    movement = runtime.catalog.get(movement_key)
    if movement is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unknown movement.")

    provided_scores = [capture.score for capture in (payload.right, payload.left) if capture is not None]
    if not provided_scores:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="At least one capture score is required.")

    detected_faults = {
        "right": payload.right.detected_faults if payload.right else [],
        "left": payload.left.detected_faults if payload.left else [],
        "summary": sorted(
            {
                *([] if payload.right is None else payload.right.detected_faults),
                *([] if payload.left is None else payload.left.detected_faults),
            }
        ),
    }

    # Store metrics from the worse-scoring side — that side drove final_score = min(...)
    if payload.right and payload.left:
        worse = payload.right if payload.right.score <= payload.left.score else payload.left
    elif payload.right:
        worse = payload.right
    else:
        worse = payload.left
    app_metrics = worse.metrics if worse and worse.metrics else None
    pose_trace = worse.pose_trace if worse and worse.pose_trace else None
    quality = worse.quality if worse and worse.quality else None

    runtime.repository.upsert_movement_result(
        assessment_id=assessment_id,
        movement_key=movement_key,
        right_score=payload.right.score if payload.right else None,
        left_score=payload.left.score if payload.left else None,
        final_score=min(provided_scores),
        detected_faults=detected_faults,
        app_metrics=app_metrics,
        pose_trace=pose_trace.model_dump() if hasattr(pose_trace, "model_dump") else pose_trace,
        quality=quality.model_dump() if hasattr(quality, "model_dump") else quality,
    )
    runtime.repository.log_audit_event(
        "movement_finalize",
        assessment_id=assessment_id,
        movement_key=movement_key,
        metadata={"sides": sorted(side for side in ("left", "right") if getattr(payload, side) is not None)},
    )
    return runtime.repository.get_assessment(assessment_id)


@router.post("/assessments/{assessment_id}/movements/{movement_key}/review")
def submit_provider_review(
    assessment_id: str,
    movement_key: str,
    payload: ProviderReviewRequest,
    request: Request,
):
    runtime = get_runtime(request)
    _purge_expired_assessments(runtime)
    if not runtime.repository.assessment_exists(assessment_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assessment not found.")
    updated = runtime.repository.save_provider_review(
        assessment_id=assessment_id,
        movement_key=movement_key,
        provider_score=payload.provider_score,
        provider_note=payload.provider_note,
    )
    if not updated:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Movement result not found.")
    runtime.repository.log_audit_event(
        "provider_review",
        assessment_id=assessment_id,
        movement_key=movement_key,
        metadata={},
    )
    return runtime.repository.get_assessment(assessment_id)
