from __future__ import annotations

import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .database import initialize_database
from .middleware.pin_auth import PinAuthMiddleware
from .repository import AssessmentRepository
from .routes.assessments import router as assessments_router
from .routes.auth import router as auth_router
from .routes.provider import router as provider_router
from .routes.self_session import router as self_session_router
from .runtime import RuntimeState
from .services.catalog import MovementCatalog
from .services.scoring.service import ScoringService
from .settings import AppSettings, get_settings


def create_app(settings: AppSettings | None = None) -> FastAPI:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-8s %(name)s — %(message)s",
        datefmt="%H:%M:%S",
    )
    settings = settings or get_settings()
    initialize_database(settings.db_path)

    app = FastAPI(title="HMA MVP API", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.dev_cors_origins),
        allow_origin_regex=r"http://localhost:\d+",
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(PinAuthMiddleware)

    runtime = RuntimeState(
        settings=settings,
        repository=AssessmentRepository(settings.db_path),
        catalog=MovementCatalog(settings.movements_config_path),
        scoring_service=ScoringService(settings.thresholds_path),
    )
    app.state.runtime = runtime
    app.include_router(auth_router)
    app.include_router(assessments_router)
    app.include_router(provider_router)
    app.include_router(self_session_router)
    _mount_static_app(app, settings.web_dist_dir)
    return app


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
                "message": "Build the Vite frontend in web/dist or run the dev server.",
                "api_docs": "/docs",
            }
        )

    @app.get("/{full_path:path}", include_in_schema=False)
    def spa_fallback(full_path: str):
        if _is_reserved_app_path(full_path):
            return JSONResponse({"detail": "Not found."}, status_code=404)
        static_file = _resolve_dist_file(web_dist_dir, full_path)
        if static_file:
            return FileResponse(static_file)
        if index_file.exists():
            return FileResponse(index_file)
        return JSONResponse({"detail": f"Unknown path '{full_path}'."}, status_code=404)


def _is_reserved_app_path(full_path: str) -> bool:
    return (
        full_path == "api"
        or full_path.startswith("api/")
        or full_path == "docs"
        or full_path.startswith("docs/")
        or full_path.startswith("openapi")
    )


def _resolve_dist_file(web_dist_dir: Path, full_path: str) -> Path | None:
    try:
        dist_root = web_dist_dir.resolve()
        requested = (dist_root / full_path).resolve()
        requested.relative_to(dist_root)
    except (OSError, ValueError):
        return None

    if requested.is_file():
        return requested
    return None


app = create_app()
