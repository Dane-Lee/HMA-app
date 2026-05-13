from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Literal
from urllib.parse import quote
from uuid import uuid4

from fastapi import FastAPI, File, Form, HTTPException, Request, Response, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator

from .auth import generate_token, verify_totp
from .database import initialize_database
from .repository import ManualRepository, now_utc
from .settings import ManualSettings, get_settings


logger = logging.getLogger(__name__)
VIDEO_SUFFIXES = {".webm", ".mp4", ".mov", ".m4v", ".avi", ".mpeg", ".mpg"}


class ConsentPayload(BaseModel):
    notice_version: str = Field(default="hma-manual-v1", min_length=1, max_length=80)
    voluntary_wellness: Literal[True]
    purpose_limited: Literal[True]
    no_employment_decision: Literal[True]
    video_retention_acknowledged: Literal[True]


class LoginPayload(BaseModel):
    username: str = Field(min_length=1, max_length=120)
    password: str = Field(min_length=1, max_length=500)
    mfa_code: str | None = Field(default=None, max_length=20)


class AssessmentCreatePayload(BaseModel):
    participant_name: str = Field(min_length=1, max_length=120)
    consent: ConsentPayload

    @field_validator("participant_name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("participant_name is required")
        return normalized


class EmployeePayload(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    employer: str = Field(min_length=1, max_length=120)
    email: str | None = Field(default=None, max_length=200)
    notes: str | None = Field(default=None, max_length=2000)

    @field_validator("name", "employer")
    @classmethod
    def normalize_required(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("field is required")
        return normalized

    @field_validator("email", "notes")
    @classmethod
    def normalize_optional(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None


class UploadSessionPayload(BaseModel):
    employee: EmployeePayload


class SideManualScore(BaseModel):
    score: int = Field(ge=0, le=3)
    faults: list[str] = Field(default_factory=list)

    @field_validator("faults")
    @classmethod
    def normalize_faults(cls, values: list[str]) -> list[str]:
        normalized: list[str] = []
        for value in values:
            fault = value.strip().lower().replace(" ", "_")
            if not fault:
                continue
            if len(fault) > 120:
                raise ValueError("fault labels must be 120 characters or fewer")
            normalized.append(fault)
        return sorted(set(normalized))


class ManualScorePayload(BaseModel):
    right: SideManualScore | None = None
    left: SideManualScore | None = None
    provider_note: str | None = Field(default=None, max_length=2000)

    @field_validator("provider_note")
    @classmethod
    def normalize_note(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None


class CompleteAssessmentPayload(BaseModel):
    confirm_delete_videos: bool = False


class TokenPayload(BaseModel):
    token: str


def create_app(settings: ManualSettings | None = None) -> FastAPI:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-8s %(name)s - %(message)s",
        datefmt="%H:%M:%S",
    )
    settings = settings or get_settings()
    initialize_database(settings.db_path)
    repository = ManualRepository(settings.db_path)
    _bootstrap_provider(repository, settings)

    app = FastAPI(title="HMA-Manual API", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.dev_cors_origins),
        allow_origin_regex=r"http://localhost:\d+",
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.state.settings = settings
    app.state.repository = repository
    app.state.movements = _load_movements(settings.movements_config_path)

    _register_api(app)
    _mount_static_app(app, settings.web_dist_dir)
    return app


def _register_api(app: FastAPI) -> None:
    @app.get("/api/health")
    def healthcheck() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/api/auth")
    def auth_status(request: Request):
        provider = _optional_provider(request)
        return {
            "authenticated": provider is not None,
            "provider": _provider_payload(provider) if provider else None,
            "mfa_required": request.app.state.settings.require_mfa,
        }

    @app.post("/api/auth")
    def login(payload: LoginPayload, request: Request, response: Response):
        repository: ManualRepository = request.app.state.repository
        settings: ManualSettings = request.app.state.settings
        provider = repository.get_provider_by_username(payload.username)
        if provider is None or provider["status"] != "active":
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid username or password.")

        if _is_locked(provider):
            raise HTTPException(status_code=423, detail="Provider account is temporarily locked.")

        if not repository.verify_provider_password(provider, payload.password):
            repository.record_login_failure(provider["id"])
            repository.log_audit_event("provider_login_failed", provider_id=provider["id"])
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid username or password.")

        if settings.require_mfa and not provider["mfa_enabled"]:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="MFA enrollment is required.")
        if provider["mfa_enabled"]:
            if not payload.mfa_code or not verify_totp(payload.mfa_code, provider["mfa_secret"] or ""):
                repository.record_login_failure(provider["id"])
                repository.log_audit_event("provider_mfa_failed", provider_id=provider["id"])
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid MFA code.")

        token = generate_token()
        expires_at = now_utc() + timedelta(hours=settings.provider_session_hours)
        repository.create_provider_session(provider_id=provider["id"], token=token, expires_at=expires_at)
        repository.record_login_success(provider["id"])
        repository.log_audit_event("provider_login", provider_id=provider["id"])
        response.set_cookie(
            key="hma_manual_provider_session",
            value=token,
            httponly=True,
            secure=request.url.scheme == "https",
            samesite="lax",
            max_age=settings.provider_session_hours * 60 * 60,
        )
        return {"ok": True, "provider": _provider_payload(repository.get_provider(provider["id"]))}

    @app.delete("/api/auth")
    def logout(request: Request, response: Response):
        repository: ManualRepository = request.app.state.repository
        token = request.cookies.get("hma_manual_provider_session", "")
        if token:
            repository.delete_provider_session(token)
        response.delete_cookie("hma_manual_provider_session")
        return {"ok": True}

    @app.get("/api/movements")
    def list_movements(request: Request):
        _require_provider(request)
        return request.app.state.movements

    @app.get("/api/assessments")
    def list_assessments(request: Request):
        _require_provider(request)
        _purge_expired_review_videos(request)
        return request.app.state.repository.list_assessments()

    @app.post("/api/assessments", status_code=status.HTTP_201_CREATED)
    def create_assessment(payload: AssessmentCreatePayload, request: Request):
        provider = _require_provider(request)
        repository: ManualRepository = request.app.state.repository
        settings: ManualSettings = request.app.state.settings
        assessment = repository.create_assessment(
            participant_name=payload.participant_name,
            provider_id=provider["id"],
            employee_id=None,
            consent_notice_version=payload.consent.notice_version,
            consent_scope=_consent_scope(payload.consent),
            retention_days=settings.assessment_retention_days,
        )
        repository.log_audit_event(
            "manual_assessment_create",
            provider_id=provider["id"],
            assessment_id=assessment["id"],
        )
        return _assessment_response(assessment)

    @app.get("/api/assessments/{assessment_id}")
    def get_assessment(assessment_id: str, request: Request):
        _require_provider(request)
        _purge_expired_review_videos(request)
        assessment = request.app.state.repository.get_assessment(assessment_id)
        if assessment is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assessment not found.")
        return _assessment_response(assessment)

    @app.delete("/api/assessments/{assessment_id}", status_code=status.HTTP_204_NO_CONTENT)
    def delete_assessment(assessment_id: str, request: Request):
        provider = _require_provider(request)
        repository: ManualRepository = request.app.state.repository
        settings: ManualSettings = request.app.state.settings
        assessment = repository.get_assessment(assessment_id)
        if assessment is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assessment not found.")
        _delete_review_video_files(
            repository,
            settings,
            assessment["review_videos"],
            provider_id=provider["id"],
            reason="assessment_delete",
        )
        repository.delete_assessment(assessment_id)
        repository.log_audit_event(
            "manual_assessment_delete",
            provider_id=provider["id"],
            assessment_id=assessment_id,
        )
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    @app.post("/api/assessments/{assessment_id}/movements/{movement_key}/manual-score")
    def save_manual_score(assessment_id: str, movement_key: str, payload: ManualScorePayload, request: Request):
        provider = _require_provider(request)
        repository: ManualRepository = request.app.state.repository
        movement = _require_movement(request, movement_key)
        if not repository.assessment_exists(assessment_id):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assessment not found.")
        right_score = payload.right.score if payload.right else None
        left_score = payload.left.score if payload.left else None
        for side in movement["sides"]:
            if side == "right" and right_score is None:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Right score is required.")
            if side == "left" and left_score is None:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Left score is required.")
        faults = {
            "right": payload.right.faults if payload.right else [],
            "left": payload.left.faults if payload.left else [],
            "summary": sorted(
                {
                    *(payload.right.faults if payload.right else []),
                    *(payload.left.faults if payload.left else []),
                }
            ),
        }
        assessment = repository.save_manual_score(
            assessment_id=assessment_id,
            movement_key=movement_key,
            right_score=right_score,
            left_score=left_score,
            faults=faults,
            provider_note=payload.provider_note,
        )
        repository.log_audit_event(
            "manual_score_save",
            provider_id=provider["id"],
            assessment_id=assessment_id,
            movement_key=movement_key,
            metadata={"sides": movement["sides"]},
        )
        return _assessment_response(assessment)

    @app.post("/api/assessments/{assessment_id}/review-videos", status_code=status.HTTP_201_CREATED)
    async def upload_provider_review_video(
        assessment_id: str,
        request: Request,
        movement_key: str = Form(...),
        side: str = Form(...),
        client_video_id: str | None = Form(default=None),
        video: UploadFile = File(...),
    ):
        provider = _require_provider(request)
        return await _store_review_video(
            request,
            assessment_id=assessment_id,
            movement_key=movement_key,
            side=side,
            client_video_id=client_video_id,
            video=video,
            upload_source="provider",
            provider_id=provider["id"],
            upload_session_id=None,
        )

    @app.get("/api/assessments/{assessment_id}/review-videos")
    def list_review_videos(assessment_id: str, request: Request):
        _require_provider(request)
        repository: ManualRepository = request.app.state.repository
        if not repository.assessment_exists(assessment_id):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assessment not found.")
        _purge_expired_review_videos(request)
        return [_review_video_response(video) for video in repository.list_review_videos(assessment_id)]

    @app.get("/api/assessments/{assessment_id}/review-videos/{video_id}/file")
    def stream_review_video(assessment_id: str, video_id: str, request: Request):
        provider = _require_provider(request)
        repository: ManualRepository = request.app.state.repository
        settings: ManualSettings = request.app.state.settings
        video = repository.get_review_video(assessment_id, video_id)
        if video is None or not video.get("video_path") or video.get("deleted_at"):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Review video is unavailable.")
        path = Path(video["video_path"])
        if not _is_under_directory(path, settings.review_capture_dir) or not path.exists():
            repository.mark_review_videos_deleted(
                [video_id],
                deleted_at=now_utc().isoformat(),
                provider_id=provider["id"],
                reason="missing_or_invalid_path",
            )
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Review video is unavailable.")
        repository.log_audit_event(
            "review_video_view",
            provider_id=provider["id"],
            assessment_id=assessment_id,
            movement_key=video["movement_key"],
            metadata={"video_id": video_id, "side": video["side"]},
        )
        return FileResponse(
            path,
            media_type=video["content_type"] or "video/mp4",
            filename=video["original_filename"] or path.name,
        )

    @app.delete("/api/assessments/{assessment_id}/review-videos/{video_id}", status_code=status.HTTP_204_NO_CONTENT)
    def delete_review_video(assessment_id: str, video_id: str, request: Request):
        provider = _require_provider(request)
        repository: ManualRepository = request.app.state.repository
        settings: ManualSettings = request.app.state.settings
        video = repository.get_review_video(assessment_id, video_id)
        if video is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Review video not found.")
        _delete_review_video_files(
            repository,
            settings,
            [video],
            provider_id=provider["id"],
            reason="provider_delete",
        )
        repository.log_audit_event(
            "review_video_delete",
            provider_id=provider["id"],
            assessment_id=assessment_id,
            movement_key=video["movement_key"],
            metadata={"video_id": video_id, "side": video["side"]},
        )
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    @app.post("/api/assessments/{assessment_id}/delete-videos")
    def delete_all_review_videos(assessment_id: str, request: Request):
        provider = _require_provider(request)
        repository: ManualRepository = request.app.state.repository
        settings: ManualSettings = request.app.state.settings
        videos = repository.list_review_videos(assessment_id)
        deleted_count = _delete_review_video_files(
            repository,
            settings,
            videos,
            provider_id=provider["id"],
            reason="provider_confirm_done_scoring",
        )
        repository.log_audit_event(
            "review_videos_delete_all",
            provider_id=provider["id"],
            assessment_id=assessment_id,
            metadata={"deleted_count": deleted_count},
        )
        return {"deleted_count": deleted_count, "assessment": _assessment_response(repository.get_assessment(assessment_id))}

    @app.post("/api/assessments/{assessment_id}/complete")
    def complete_assessment(assessment_id: str, payload: CompleteAssessmentPayload, request: Request):
        provider = _require_provider(request)
        repository: ManualRepository = request.app.state.repository
        settings: ManualSettings = request.app.state.settings
        assessment = repository.get_assessment(assessment_id)
        if assessment is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assessment not found.")
        remaining = [video for video in assessment["review_videos"] if video.get("video_path") and not video.get("deleted_at")]
        deleted_at = None
        if remaining:
            if not payload.confirm_delete_videos:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Review videos remain. Confirm deletion before completing this assessment.",
                )
            deleted_at = now_utc().isoformat()
            _delete_review_video_files(
                repository,
                settings,
                remaining,
                provider_id=provider["id"],
                reason="complete_assessment",
                deleted_at=deleted_at,
            )
        assessment = repository.complete_assessment(assessment_id, videos_deleted_at=deleted_at)
        repository.log_audit_event(
            "manual_assessment_complete",
            provider_id=provider["id"],
            assessment_id=assessment_id,
            metadata={"deleted_remaining_videos": bool(remaining)},
        )
        return _assessment_response(assessment)

    @app.post("/api/assessments/{assessment_id}/upload-session", status_code=status.HTTP_201_CREATED)
    def create_upload_session(assessment_id: str, payload: UploadSessionPayload, request: Request):
        provider = _require_provider(request)
        repository: ManualRepository = request.app.state.repository
        settings: ManualSettings = request.app.state.settings
        assessment = repository.get_assessment(assessment_id)
        if assessment is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assessment not found.")
        employee = repository.create_employee(
            name=payload.employee.name,
            employer=payload.employee.employer,
            email=payload.employee.email,
            notes=payload.employee.notes,
        )
        token = generate_token()
        expires_at = now_utc() + timedelta(days=settings.upload_session_lifetime_days)
        upload_session = repository.create_upload_session(
            employee_id=employee["id"],
            assessment_id=assessment_id,
            provider_id=provider["id"],
            plaintext_token=token,
            allowed_slots=_allowed_slots(request.app.state.movements),
            expires_at=expires_at,
        )
        repository.log_audit_event(
            "upload_session_issue",
            provider_id=provider["id"],
            employee_id=employee["id"],
            assessment_id=assessment_id,
            metadata={"expires_at": expires_at.isoformat()},
        )
        base = settings.public_base_url.rstrip("/")
        return {
            "id": upload_session["id"],
            "url": f"{base}/self/start/{quote(token, safe='')}",
            "expires_at": expires_at.isoformat(),
            "employee": employee,
        }

    @app.post("/api/upload-sessions/{session_id}/revoke")
    def revoke_upload_session(session_id: str, request: Request):
        provider = _require_provider(request)
        repository: ManualRepository = request.app.state.repository
        revoked = repository.revoke_upload_session(session_id, now_iso=now_utc().isoformat())
        if not revoked:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Upload session not found.")
        repository.log_audit_event("upload_session_revoke", provider_id=provider["id"], metadata={"session_id": session_id})
        return {"ok": True}

    # ---- Employee scoped flow -------------------------------------------

    @app.post("/api/self/session")
    def consume_upload_link(payload: TokenPayload, request: Request, response: Response):
        repository: ManualRepository = request.app.state.repository
        settings: ManualSettings = request.app.state.settings
        token = payload.token.strip()
        if not token:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Token is required.")
        upload_session = repository.get_upload_session_by_token(token, now_iso=now_utc().isoformat())
        if upload_session is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Link is invalid or expired.")
        response.set_cookie(
            key="hma_manual_upload_session",
            value=token,
            httponly=True,
            secure=request.url.scheme == "https",
            samesite="lax",
            max_age=settings.upload_session_lifetime_days * 24 * 60 * 60,
        )
        repository.log_audit_event(
            "upload_session_open",
            employee_id=upload_session["employee_id"],
            assessment_id=upload_session["assessment_id"],
        )
        return _self_payload(request, upload_session)

    @app.get("/api/self/me")
    def self_me(request: Request):
        upload_session = _require_upload_session(request)
        return _self_payload(request, upload_session)

    @app.post("/api/self/review-videos", status_code=status.HTTP_201_CREATED)
    async def upload_employee_review_video(
        request: Request,
        movement_key: str = Form(...),
        side: str = Form(...),
        client_video_id: str | None = Form(default=None),
        video: UploadFile = File(...),
    ):
        upload_session = _require_upload_session(request)
        if {"movement_key": movement_key, "side": side} not in upload_session["allowed_slots"]:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="This movement slot is not assigned.")
        return await _store_review_video(
            request,
            assessment_id=upload_session["assessment_id"],
            movement_key=movement_key,
            side=side,
            client_video_id=client_video_id,
            video=video,
            upload_source="employee",
            provider_id=None,
            upload_session_id=upload_session["id"],
        )

    @app.post("/api/self/submit")
    def submit_employee_uploads(request: Request):
        upload_session = _require_upload_session(request)
        repository: ManualRepository = request.app.state.repository
        repository.submit_upload_session(upload_session["id"], now_iso=now_utc().isoformat())
        repository.log_audit_event(
            "upload_session_submit",
            employee_id=upload_session["employee_id"],
            assessment_id=upload_session["assessment_id"],
        )
        return {"ok": True}

    @app.delete("/api/self/session")
    def end_employee_session(request: Request, response: Response):
        response.delete_cookie("hma_manual_upload_session")
        return {"ok": True}


async def _store_review_video(
    request: Request,
    *,
    assessment_id: str,
    movement_key: str,
    side: str,
    client_video_id: str | None,
    video: UploadFile,
    upload_source: str,
    provider_id: str | None,
    upload_session_id: str | None,
):
    repository: ManualRepository = request.app.state.repository
    settings: ManualSettings = request.app.state.settings
    movement = _require_movement(request, movement_key)
    if not repository.assessment_exists(assessment_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assessment not found.")
    if side not in movement["sides"]:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid side for movement.")
    if not _is_video_upload(video):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Upload must be a video file.")

    body = await video.read()
    await video.close()
    if len(body) > settings.max_upload_bytes:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="Video file is too large.")

    suffix = Path(video.filename or "review-video.webm").suffix.lower() or ".webm"
    if suffix not in VIDEO_SUFFIXES:
        suffix = ".webm"
    settings.review_capture_dir.mkdir(parents=True, exist_ok=True)
    stored_path = settings.review_capture_dir / f"{uuid4()}{suffix}"
    existing = repository.get_review_video_by_slot(assessment_id, movement_key, side)
    try:
        stored_path.write_bytes(body)
        expires_at = now_utc() + timedelta(days=settings.review_capture_retention_days)
        record = repository.upsert_review_video(
            assessment_id=assessment_id,
            upload_session_id=upload_session_id,
            movement_key=movement_key,
            side=side,
            client_video_id=(client_video_id or "").strip() or None,
            original_filename=video.filename,
            content_type=video.content_type,
            file_size_bytes=len(body),
            video_path=str(stored_path),
            upload_source=upload_source,
            expires_at=expires_at.isoformat(),
        )
    except Exception:
        if stored_path.exists():
            stored_path.unlink()
        raise

    if existing and existing.get("video_path") and existing["video_path"] != str(stored_path):
        _unlink_review_path(Path(existing["video_path"]), settings.review_capture_dir)
    repository.log_audit_event(
        "review_video_upload",
        provider_id=provider_id,
        assessment_id=assessment_id,
        movement_key=movement_key,
        metadata={
            "side": side,
            "upload_source": upload_source,
            "file_size_bytes": len(body),
            "replaced_existing": bool(existing),
            "scoring_invoked": False,
        },
    )
    return _review_video_response(record)


def _bootstrap_provider(repository: ManualRepository, settings: ManualSettings) -> None:
    if repository.provider_count() > 0:
        return
    if not settings.bootstrap_username or not settings.bootstrap_password:
        logger.warning("No HMA-Manual provider exists. Set MANUAL_BOOTSTRAP_USERNAME and MANUAL_BOOTSTRAP_PASSWORD.")
        return
    provider = repository.create_provider(
        username=settings.bootstrap_username,
        display_name=settings.bootstrap_display_name,
        password=settings.bootstrap_password,
        mfa_secret=settings.bootstrap_mfa_secret or None,
        role="admin",
    )
    repository.log_audit_event("provider_bootstrap", provider_id=provider["id"])


def _load_movements(path: Path) -> list[dict]:
    return json.loads(path.read_text(encoding="utf-8"))


def _optional_provider(request: Request) -> dict | None:
    token = request.cookies.get("hma_manual_provider_session", "")
    if not token:
        return None
    repository: ManualRepository = request.app.state.repository
    return repository.get_provider_by_session(token, now_iso=now_utc().isoformat())


def _require_provider(request: Request) -> dict:
    provider = _optional_provider(request)
    if provider is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Provider authentication required.")
    return provider


def _require_upload_session(request: Request) -> dict:
    token = request.cookies.get("hma_manual_upload_session", "")
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Upload link authentication required.")
    upload_session = request.app.state.repository.get_upload_session_by_token(token, now_iso=now_utc().isoformat())
    if upload_session is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Link is invalid or expired.")
    return upload_session


def _require_movement(request: Request, movement_key: str) -> dict:
    movement = next((item for item in request.app.state.movements if item["key"] == movement_key), None)
    if movement is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unknown movement.")
    return movement


def _provider_payload(provider: dict | None) -> dict | None:
    if provider is None:
        return None
    return {
        "id": provider["id"],
        "username": provider["username"],
        "display_name": provider["display_name"],
        "role": provider["role"],
        "mfa_enabled": provider["mfa_enabled"],
    }


def _is_locked(provider: dict) -> bool:
    locked_until = provider.get("locked_until")
    if not locked_until:
        return False
    try:
        return datetime.fromisoformat(locked_until) > now_utc()
    except ValueError:
        return False


def _consent_scope(payload: ConsentPayload) -> dict[str, bool]:
    return {
        "voluntary_wellness": payload.voluntary_wellness,
        "purpose_limited": payload.purpose_limited,
        "no_employment_decision": payload.no_employment_decision,
        "video_retention_acknowledged": payload.video_retention_acknowledged,
    }


def _allowed_slots(movements: list[dict]) -> list[dict[str, str]]:
    return [
        {"movement_key": movement["key"], "side": side}
        for movement in movements
        for side in movement["sides"]
    ]


def _is_video_upload(video: UploadFile) -> bool:
    suffix = Path(video.filename or "").suffix.lower()
    content_type = (video.content_type or "").lower()
    return content_type.startswith("video/") or suffix in VIDEO_SUFFIXES


def _is_under_directory(path: Path, directory: Path) -> bool:
    try:
        path.resolve().relative_to(directory.resolve())
        return True
    except (OSError, ValueError):
        return False


def _unlink_review_path(path: Path, directory: Path) -> bool:
    if path.exists() and _is_under_directory(path, directory):
        path.unlink()
        return True
    return False


def _delete_review_video_files(
    repository: ManualRepository,
    settings: ManualSettings,
    videos: list[dict],
    *,
    provider_id: str | None,
    reason: str,
    deleted_at: str | None = None,
) -> int:
    deleted_at = deleted_at or now_utc().isoformat()
    deleted_ids: list[str] = []
    for video in videos:
        raw_path = video.get("video_path")
        if not raw_path or video.get("deleted_at"):
            continue
        _unlink_review_path(Path(raw_path), settings.review_capture_dir)
        deleted_ids.append(video["id"])
    repository.mark_review_videos_deleted(
        deleted_ids,
        deleted_at=deleted_at,
        provider_id=provider_id,
        reason=reason,
    )
    return len(deleted_ids)


def _purge_expired_review_videos(request: Request) -> None:
    repository: ManualRepository = request.app.state.repository
    settings: ManualSettings = request.app.state.settings
    expired = repository.list_expired_review_videos(now_utc().isoformat())
    deleted_count = _delete_review_video_files(
        repository,
        settings,
        expired,
        provider_id=None,
        reason="review_capture_retention_expired",
    )
    for video in expired:
        repository.log_audit_event(
            "review_video_retention_purge",
            assessment_id=video["assessment_id"],
            movement_key=video["movement_key"],
            metadata={"video_id": video["id"], "deleted": deleted_count > 0},
        )


def _assessment_response(assessment: dict | None) -> dict | None:
    if assessment is None:
        return None
    result = dict(assessment)
    if "review_videos" in result:
        result["review_videos"] = [_review_video_response(video) for video in result["review_videos"]]
    return result


def _review_video_response(video: dict) -> dict:
    result = dict(video)
    return result


def _self_payload(request: Request, upload_session: dict) -> dict:
    repository: ManualRepository = request.app.state.repository
    employee = repository.get_employee(upload_session["employee_id"])
    assessment = repository.get_assessment(upload_session["assessment_id"])
    videos = [
        _review_video_response(video)
        for video in repository.list_review_videos(upload_session["assessment_id"])
    ]
    return {
        "employee": employee,
        "assessment": _assessment_response(assessment),
        "upload_session": {
            "id": upload_session["id"],
            "status": upload_session["status"],
            "expires_at": upload_session["expires_at"],
            "allowed_slots": upload_session["allowed_slots"],
        },
        "movements": request.app.state.movements,
        "review_videos": videos,
    }


def _mount_static_app(app: FastAPI, web_dist_dir: Path) -> None:
    assets_dir = web_dist_dir / "assets"
    index_file = web_dist_dir / "index.html"
    if assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

    @app.get("/", include_in_schema=False)
    def root():
        if index_file.exists():
            return FileResponse(index_file)
        return JSONResponse(
            {
                "message": "Build the HMA-Manual frontend in web_manual/dist or run the dev server.",
                "api_docs": "/docs",
            }
        )

    @app.get("/{full_path:path}", include_in_schema=False)
    def spa_fallback(full_path: str):
        if full_path == "api" or full_path.startswith("api/") or full_path.startswith("docs"):
            return JSONResponse({"detail": "Not found."}, status_code=404)
        static_file = _resolve_dist_file(web_dist_dir, full_path)
        if static_file:
            return FileResponse(static_file)
        if index_file.exists():
            return FileResponse(index_file)
        return JSONResponse({"detail": f"Unknown path '{full_path}'."}, status_code=404)


def _resolve_dist_file(web_dist_dir: Path, full_path: str) -> Path | None:
    try:
        dist_root = web_dist_dir.resolve()
        requested = (dist_root / full_path).resolve()
        requested.relative_to(dist_root)
    except (OSError, ValueError):
        return None
    return requested if requested.is_file() else None


app = create_app()
