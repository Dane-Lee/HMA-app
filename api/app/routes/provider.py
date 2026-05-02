from __future__ import annotations

from datetime import datetime, timedelta, timezone
from urllib.parse import quote

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, Field, field_validator

from ..auth_tokens import generate_token

router = APIRouter(prefix="/api/provider", tags=["provider"])


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _employee_payload(record: dict) -> dict:
    return {
        "id": record["id"],
        "name": record["name"],
        "email": record.get("email"),
        "employer": record["employer"],
        "created_at": record["created_at"],
        "notes": record.get("notes"),
    }


class CreateEmployeeRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    employer: str = Field(min_length=1, max_length=120)
    email: str | None = Field(default=None, max_length=200)
    notes: str | None = Field(default=None, max_length=2000)

    @field_validator("name", "employer")
    @classmethod
    def _normalize_required(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("must not be blank")
        return normalized

    @field_validator("email", "notes")
    @classmethod
    def _normalize_optional(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None


@router.post("/employees", status_code=status.HTTP_201_CREATED)
def create_employee(payload: CreateEmployeeRequest, request: Request):
    runtime = request.app.state.runtime
    record = runtime.repository.create_employee(
        payload.name,
        payload.employer,
        email=payload.email,
        notes=payload.notes,
    )
    runtime.repository.log_audit_event(
        "employee_create",
        metadata={"employee_id": record["id"], "employer": record["employer"]},
    )
    return _employee_payload(record)


@router.get("/employees")
def list_employees(request: Request, employer: str | None = None):
    runtime = request.app.state.runtime
    rows = runtime.repository.list_employees(employer=employer)
    return [_employee_payload(row) for row in rows]


@router.post("/employees/{employee_id}/magic-link")
def issue_magic_link(employee_id: str, request: Request):
    runtime = request.app.state.runtime
    employee = runtime.repository.get_employee(employee_id)
    if employee is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Employee not found.")
    now = _now_utc()
    runtime.repository.purge_expired_magic_link_tokens(now_iso=now.isoformat())
    plaintext = generate_token()
    expires_at = now + timedelta(days=runtime.settings.magic_link_lifetime_days)
    runtime.repository.create_magic_link_token(
        employee_id,
        plaintext_token=plaintext,
        expires_at=expires_at.isoformat(),
    )
    runtime.repository.log_audit_event(
        "magic_link_issue",
        metadata={
            "employee_id": employee_id,
            "expires_at": expires_at.isoformat(),
        },
    )
    base = runtime.settings.public_base_url.rstrip("/")
    url = f"{base}/self/start/{quote(plaintext, safe='')}"
    return {"url": url, "expires_at": expires_at.isoformat()}


@router.post("/employees/{employee_id}/revoke-links")
def revoke_links(employee_id: str, request: Request):
    runtime = request.app.state.runtime
    employee = runtime.repository.get_employee(employee_id)
    if employee is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Employee not found.")
    revoked_count = runtime.repository.revoke_employee_magic_links(
        employee_id, now_iso=_now_utc().isoformat()
    )
    runtime.repository.log_audit_event(
        "magic_link_revoke",
        metadata={"employee_id": employee_id, "revoked_count": revoked_count},
    )
    return {"revoked_count": revoked_count}
