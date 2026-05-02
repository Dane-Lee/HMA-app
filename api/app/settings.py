from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


@dataclass(slots=True)
class AppSettings:
    base_dir: Path
    db_path: Path
    movements_config_path: Path
    thresholds_path: Path
    temp_dir: Path
    draft_capture_dir: Path
    web_dist_dir: Path
    access_pin: str
    max_upload_bytes: int
    draft_capture_retention_days: int
    assessment_retention_days: int
    magic_link_lifetime_days: int = 7
    employee_session_hours: int = 12
    public_base_url: str = "http://localhost:5181"
    enable_pose_overlays: bool = True
    max_pose_trace_frames: int = 48
    dev_cors_origins: tuple[str, ...] = ("http://localhost:5181", "http://127.0.0.1:5181")


def _load_repo_env(base_dir: Path) -> None:
    load_dotenv(base_dir / ".env", override=False)


def _resolve_data_dir(base_dir: Path) -> Path:
    raw_data_dir = os.environ.get("DATA_DIR", "data").strip() or "data"
    data_dir = Path(raw_data_dir)
    if not data_dir.is_absolute():
        data_dir = base_dir / data_dir
    return data_dir


def get_settings() -> AppSettings:
    base_dir = Path(__file__).resolve().parents[2]
    _load_repo_env(base_dir)
    data_dir = _resolve_data_dir(base_dir)
    data_dir.mkdir(parents=True, exist_ok=True)
    temp_dir = data_dir / "uploads"
    temp_dir.mkdir(parents=True, exist_ok=True)
    draft_capture_dir = data_dir / "draft-captures"
    draft_capture_dir.mkdir(parents=True, exist_ok=True)
    max_upload_mb = int(os.environ.get("MAX_UPLOAD_MB", "150"))
    draft_capture_retention_days = int(os.environ.get("DRAFT_CAPTURE_RETENTION_DAYS", "7"))
    assessment_retention_days = int(os.environ.get("ASSESSMENT_RETENTION_DAYS", "365"))
    magic_link_lifetime_days = int(os.environ.get("MAGIC_LINK_LIFETIME_DAYS", "7"))
    employee_session_hours = int(os.environ.get("EMPLOYEE_SESSION_HOURS", "12"))
    public_base_url = os.environ.get("PUBLIC_BASE_URL", "http://localhost:5181").strip().rstrip("/")
    enable_pose_overlays = os.environ.get("ENABLE_POSE_OVERLAYS", "1").strip().lower() not in {
        "0",
        "false",
        "no",
        "off",
    }
    max_pose_trace_frames = int(os.environ.get("MAX_POSE_TRACE_FRAMES", "48"))
    return AppSettings(
        base_dir=base_dir,
        db_path=data_dir / "hma.db",
        movements_config_path=base_dir / "config" / "movements.json",
        thresholds_path=base_dir / "config" / "scoring_thresholds.yaml",
        temp_dir=temp_dir,
        draft_capture_dir=draft_capture_dir,
        web_dist_dir=base_dir / "web" / "dist",
        access_pin=os.environ.get("ACCESS_PIN", "").strip(),
        max_upload_bytes=max_upload_mb * 1024 * 1024,
        draft_capture_retention_days=draft_capture_retention_days,
        assessment_retention_days=assessment_retention_days,
        magic_link_lifetime_days=magic_link_lifetime_days,
        employee_session_hours=employee_session_hours,
        public_base_url=public_base_url,
        enable_pose_overlays=enable_pose_overlays,
        max_pose_trace_frames=max_pose_trace_frames,
    )
