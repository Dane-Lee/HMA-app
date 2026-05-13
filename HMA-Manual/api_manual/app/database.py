from __future__ import annotations

import sqlite3
from pathlib import Path


SCHEMA_SQL = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS providers (
    id TEXT PRIMARY KEY,
    username TEXT NOT NULL UNIQUE,
    display_name TEXT NOT NULL,
    password_hash TEXT NOT NULL,
    mfa_secret TEXT,
    mfa_enabled INTEGER NOT NULL DEFAULT 0,
    role TEXT NOT NULL DEFAULT 'provider',
    status TEXT NOT NULL DEFAULT 'active',
    failed_login_count INTEGER NOT NULL DEFAULT 0,
    locked_until TEXT,
    created_at TEXT NOT NULL,
    last_login_at TEXT
);

CREATE TABLE IF NOT EXISTS provider_sessions (
    token_hash TEXT PRIMARY KEY,
    provider_id TEXT NOT NULL,
    created_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    last_seen_at TEXT NOT NULL,
    FOREIGN KEY (provider_id) REFERENCES providers(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS employees (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    employer TEXT NOT NULL,
    email TEXT,
    notes TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS manual_assessments (
    id TEXT PRIMARY KEY,
    participant_name TEXT NOT NULL,
    employee_id TEXT,
    created_by_provider_id TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'draft',
    total_score INTEGER NOT NULL DEFAULT 0,
    score_band TEXT NOT NULL DEFAULT 'High opportunity for improvement',
    consent_notice_version TEXT,
    consent_scope_json TEXT,
    created_at TEXT NOT NULL,
    retention_expires_at TEXT,
    completed_at TEXT,
    videos_deleted_at TEXT,
    FOREIGN KEY (employee_id) REFERENCES employees(id) ON DELETE SET NULL,
    FOREIGN KEY (created_by_provider_id) REFERENCES providers(id) ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS manual_movement_results (
    id TEXT PRIMARY KEY,
    assessment_id TEXT NOT NULL,
    movement_key TEXT NOT NULL,
    right_score INTEGER,
    left_score INTEGER,
    final_score INTEGER NOT NULL,
    faults_json TEXT NOT NULL DEFAULT '{}',
    provider_note TEXT,
    reviewed_at TEXT NOT NULL,
    FOREIGN KEY (assessment_id) REFERENCES manual_assessments(id) ON DELETE CASCADE,
    UNIQUE (assessment_id, movement_key)
);

CREATE TABLE IF NOT EXISTS manual_review_videos (
    id TEXT PRIMARY KEY,
    assessment_id TEXT NOT NULL,
    upload_session_id TEXT,
    movement_key TEXT NOT NULL,
    side TEXT NOT NULL,
    client_video_id TEXT,
    original_filename TEXT,
    content_type TEXT,
    file_size_bytes INTEGER NOT NULL,
    video_path TEXT,
    upload_source TEXT NOT NULL,
    created_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    deleted_at TEXT,
    deleted_by_provider_id TEXT,
    deletion_reason TEXT,
    FOREIGN KEY (assessment_id) REFERENCES manual_assessments(id) ON DELETE CASCADE,
    FOREIGN KEY (deleted_by_provider_id) REFERENCES providers(id) ON DELETE SET NULL,
    UNIQUE (assessment_id, movement_key, side)
);

CREATE TABLE IF NOT EXISTS upload_sessions (
    id TEXT PRIMARY KEY,
    token_hash TEXT NOT NULL UNIQUE,
    employee_id TEXT NOT NULL,
    assessment_id TEXT NOT NULL,
    created_by_provider_id TEXT NOT NULL,
    allowed_slots_json TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active',
    created_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    revoked_at TEXT,
    submitted_at TEXT,
    FOREIGN KEY (employee_id) REFERENCES employees(id) ON DELETE CASCADE,
    FOREIGN KEY (assessment_id) REFERENCES manual_assessments(id) ON DELETE CASCADE,
    FOREIGN KEY (created_by_provider_id) REFERENCES providers(id) ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS audit_events (
    id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    event_type TEXT NOT NULL,
    provider_id TEXT,
    employee_id TEXT,
    assessment_id TEXT,
    movement_key TEXT,
    metadata_json TEXT NOT NULL DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_manual_assessments_created_at
ON manual_assessments (created_at);

CREATE INDEX IF NOT EXISTS idx_manual_review_videos_expiry
ON manual_review_videos (expires_at, deleted_at);

CREATE INDEX IF NOT EXISTS idx_upload_sessions_assessment
ON upload_sessions (assessment_id, expires_at);

CREATE INDEX IF NOT EXISTS idx_audit_events_assessment
ON audit_events (assessment_id, created_at);
"""


def get_connection(db_path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def initialize_database(db_path: Path) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with get_connection(db_path) as connection:
        connection.executescript(SCHEMA_SQL)
        connection.commit()
