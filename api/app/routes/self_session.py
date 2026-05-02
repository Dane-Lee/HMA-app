from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException, Request, Response, status
from pydantic import BaseModel

from ..auth_tokens import generate_token

router = APIRouter(prefix="/api/self", tags=["self"])


class ConsumeMagicLinkRequest(BaseModel):
    token: str


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _employee_payload(employee: dict) -> dict:
    return {
        "id": employee["id"],
        "name": employee["name"],
        "email": employee.get("email"),
        "employer": employee["employer"],
        "created_at": employee["created_at"],
        "notes": employee.get("notes"),
    }


@router.post("/session")
def consume_link(payload: ConsumeMagicLinkRequest, request: Request, response: Response):
    runtime = request.app.state.runtime
    now = _now_utc()
    now_iso = now.isoformat()
    runtime.repository.purge_expired_sessions(now_iso=now_iso)
    runtime.repository.purge_expired_magic_link_tokens(now_iso=now_iso)

    token_value = payload.token.strip()
    if not token_value:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Token is required.")

    employee = runtime.repository.consume_magic_link_token(token_value, now_iso=now_iso)
    if employee is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Link is invalid or expired.")

    runtime.repository.log_audit_event(
        "magic_link_consume",
        metadata={"employee_id": employee["id"]},
    )
    session_token = generate_token()
    expires_at = now + timedelta(hours=runtime.settings.employee_session_hours)
    runtime.repository.create_session(
        role="employee",
        subject_id=employee["id"],
        plaintext_token=session_token,
        expires_at=expires_at.isoformat(),
    )
    runtime.repository.log_audit_event(
        "employee_session_start",
        metadata={"employee_id": employee["id"]},
    )
    is_secure = request.url.scheme == "https"
    response.set_cookie(
        key="hma_employee_session",
        value=session_token,
        httponly=True,
        samesite="lax",
        secure=is_secure,
        max_age=runtime.settings.employee_session_hours * 60 * 60,
    )
    return {"ok": True, "employee": _employee_payload(employee)}


@router.get("/me")
def me(request: Request):
    runtime = request.app.state.runtime
    employee_id = getattr(request.state, "employee_id", None)
    if not employee_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required.")
    employee = runtime.repository.get_employee(employee_id)
    if employee is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Employee not found.")
    return {"employee": _employee_payload(employee), "assessment_id": None}


@router.delete("/session")
def end_session(request: Request, response: Response):
    runtime = request.app.state.runtime
    cookie = request.cookies.get("hma_employee_session", "")
    if cookie:
        runtime.repository.delete_session(cookie)
    response.delete_cookie("hma_employee_session")
    return {"ok": True}
