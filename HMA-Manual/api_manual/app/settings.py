from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


@dataclass(slots=True)
class ManualSettings:
    base_dir: Path
    db_path: Path
    movements_config_path: Path
    review_capture_dir: Path
    web_dist_dir: Path
    public_base_url: str
    max_upload_bytes: int
    review_capture_retention_days: int
    assessment_retention_days: int
    provider_session_hours: int
    upload_session_lifetime_days: int
    require_mfa: bool
    bootstrap_username: str
    bootstrap_password: str
    bootstrap_display_name: str
    bootstrap_mfa_secret: str
    dev_cors_origins: tuple[str, ...]


def _truthy(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() not in {"", "0", "false", "no", "off"}


def _resolve_data_dir(base_dir: Path) -> Path:
    raw = os.environ.get("MANUAL_DATA_DIR", "data/manual").strip() or "data/manual"
    path = Path(raw)
    if not path.is_absolute():
        path = base_dir / path
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_settings() -> ManualSettings:
    base_dir = Path(__file__).resolve().parents[2]
    load_dotenv(base_dir / ".env.manual", override=False)
    data_dir = _resolve_data_dir(base_dir)
    review_capture_dir = data_dir / "review-captures"
    review_capture_dir.mkdir(parents=True, exist_ok=True)
    max_upload_mb = int(os.environ.get("MANUAL_MAX_UPLOAD_MB", "150"))
    public_base_url = os.environ.get(
        "MANUAL_PUBLIC_BASE_URL",
        "http://localhost:5182",
    ).strip().rstrip("/")
    return ManualSettings(
        base_dir=base_dir,
        db_path=data_dir / "hma_manual.db",
        movements_config_path=base_dir / "config_manual" / "movements.json",
        review_capture_dir=review_capture_dir,
        web_dist_dir=base_dir / "web_manual" / "dist",
        public_base_url=public_base_url,
        max_upload_bytes=max_upload_mb * 1024 * 1024,
        review_capture_retention_days=int(os.environ.get("REVIEW_CAPTURE_RETENTION_DAYS", "7")),
        assessment_retention_days=int(os.environ.get("MANUAL_ASSESSMENT_RETENTION_DAYS", "365")),
        provider_session_hours=int(os.environ.get("MANUAL_PROVIDER_SESSION_HOURS", "12")),
        upload_session_lifetime_days=int(os.environ.get("MANUAL_UPLOAD_SESSION_DAYS", "7")),
        require_mfa=_truthy(os.environ.get("MANUAL_REQUIRE_MFA"), default=False),
        bootstrap_username=os.environ.get("MANUAL_BOOTSTRAP_USERNAME", "").strip(),
        bootstrap_password=os.environ.get("MANUAL_BOOTSTRAP_PASSWORD", ""),
        bootstrap_display_name=os.environ.get("MANUAL_BOOTSTRAP_DISPLAY_NAME", "Manual Admin").strip(),
        bootstrap_mfa_secret=os.environ.get("MANUAL_BOOTSTRAP_MFA_SECRET", "").strip(),
        dev_cors_origins=(
            "http://localhost:5182",
            "http://127.0.0.1:5182",
        ),
    )
