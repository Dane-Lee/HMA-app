from __future__ import annotations

import hmac
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel

from ..auth_tokens import generate_token

router = APIRouter(prefix="/api", tags=["auth"])

PROVIDER_SESSION_HOURS = 12


class PinRequest(BaseModel):
    pin: str


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


@router.get("/auth")
def auth_status(request: Request):
    runtime = request.app.state.runtime
    auth_required = bool(runtime.settings.access_pin)
    if not auth_required:
        return {"auth_required": False, "authenticated": True}
    token = request.cookies.get("hma_session", "")
    authenticated = False
    if token:
        session = runtime.repository.get_session(token, now_iso=_now_utc().isoformat())
        authenticated = session is not None and session["role"] == "provider"
    return {"auth_required": True, "authenticated": authenticated}


@router.post("/auth")
def authenticate(payload: PinRequest, request: Request, response: Response):
    runtime = request.app.state.runtime
    if not runtime.settings.access_pin:
        return {"ok": True}
    if not hmac.compare_digest(payload.pin.strip(), runtime.settings.access_pin):
        raise HTTPException(status_code=401, detail="Incorrect PIN.")
    now = _now_utc()
    runtime.repository.purge_expired_sessions(now_iso=now.isoformat())
    token = generate_token()
    expires_at = now + timedelta(hours=PROVIDER_SESSION_HOURS)
    runtime.repository.create_session(
        role="provider",
        subject_id=None,
        plaintext_token=token,
        expires_at=expires_at.isoformat(),
    )
    runtime.repository.log_audit_event("provider_session_start", metadata={})
    is_secure = request.url.scheme == "https"
    response.set_cookie(
        key="hma_session",
        value=token,
        httponly=True,
        samesite="lax",
        secure=is_secure,
        max_age=PROVIDER_SESSION_HOURS * 60 * 60,
    )
    return {"ok": True}


@router.delete("/auth")
def logout(request: Request, response: Response):
    runtime = request.app.state.runtime
    token = request.cookies.get("hma_session", "")
    if token:
        runtime.repository.delete_session(token)
    response.delete_cookie("hma_session")
    return {"ok": True}
