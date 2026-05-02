from __future__ import annotations

from datetime import datetime, timezone

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse


_ALWAYS_PUBLIC_API_PATHS = frozenset({
    "/api/health",
    "/api/auth",
    "/api/self/session",
})


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _unauthorized() -> JSONResponse:
    return JSONResponse({"detail": "Authentication required."}, status_code=401)


class PinAuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        runtime = request.app.state.runtime
        path = request.url.path

        # Non-API paths: SPA shell, static assets, etc.
        if not path.startswith("/api/"):
            return await call_next(request)

        if path in _ALWAYS_PUBLIC_API_PATHS:
            return await call_next(request)

        # Employee-scoped routes always require an employee session, regardless of PIN config.
        if path.startswith("/api/self/"):
            cookie = request.cookies.get("hma_employee_session", "")
            if cookie:
                session = runtime.repository.get_session(cookie, now_iso=_now_iso())
                if session is not None and session["role"] == "employee":
                    request.state.employee_id = session["subject_id"]
                    return await call_next(request)
            return _unauthorized()

        # Provider routes: PIN session if a PIN is configured, otherwise open (dev/local).
        if not runtime.settings.access_pin:
            return await call_next(request)
        cookie = request.cookies.get("hma_session", "")
        if cookie:
            session = runtime.repository.get_session(cookie, now_iso=_now_iso())
            if session is not None and session["role"] == "provider":
                return await call_next(request)
        return _unauthorized()
