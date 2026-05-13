from __future__ import annotations

import sqlite3
from pathlib import Path


SCHEMA_SQL = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS assessments (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    created_at TEXT NOT NULL,
    scoring_mode TEXT NOT NULL DEFAULT 'ai_assisted',
    total_score INTEGER NOT NULL DEFAULT 0,
    score_band TEXT NOT NULL DEFAULT 'High opportunity for improvement',
    consent_notice_version TEXT,
    consent_accepted_at TEXT,
    consent_scope_json TEXT,
    privacy_posture TEXT NOT NULL DEFAULT 'voluntary_ergonomic_wellness',
    retention_expires_at TEXT
);

CREATE TABLE IF NOT EXISTS movement_results (
    id TEXT PRIMARY KEY,
    assessment_id TEXT NOT NULL,
    movement_key TEXT NOT NULL,
    right_score INTEGER,
    left_score INTEGER,
    final_score INTEGER NOT NULL,
    detected_faults_json TEXT NOT NULL,
    pose_trace_json TEXT,
    quality_json TEXT,
    app_score_available INTEGER NOT NULL DEFAULT 1,
    provider_right_score INTEGER,
    provider_left_score INTEGER,
    provider_final_score INTEGER,
    provider_faults_json TEXT,
    review_reason TEXT,
    reviewed_at TEXT,
    FOREIGN KEY (assessment_id) REFERENCES assessments(id) ON DELETE CASCADE,
    UNIQUE (assessment_id, movement_key)
);

CREATE TABLE IF NOT EXISTS draft_captures (
    id TEXT PRIMARY KEY,
    assessment_id TEXT NOT NULL,
    movement_key TEXT NOT NULL,
    side TEXT NOT NULL,
    client_capture_id TEXT NOT NULL,
    score INTEGER NOT NULL,
    detected_faults_json TEXT NOT NULL,
    metrics_json TEXT NOT NULL,
    pose_trace_json TEXT,
    quality_json TEXT,
    confidence REAL NOT NULL,
    source TEXT NOT NULL,
    original_filename TEXT,
    content_type TEXT,
    file_size_bytes INTEGER NOT NULL,
    video_path TEXT,
    created_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    video_deleted_at TEXT,
    FOREIGN KEY (assessment_id) REFERENCES assessments(id) ON DELETE CASCADE,
    UNIQUE (assessment_id, movement_key, side),
    UNIQUE (assessment_id, client_capture_id)
);

CREATE TABLE IF NOT EXISTS audit_events (
    id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    event_type TEXT NOT NULL,
    assessment_id TEXT,
    movement_key TEXT,
    metadata_json TEXT NOT NULL DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_audit_events_assessment
ON audit_events (assessment_id, created_at);

CREATE TABLE IF NOT EXISTS manual_score_entries (
    id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    assessment_id TEXT NOT NULL,
    movement_key TEXT NOT NULL,
    side TEXT NOT NULL,
    provider_score INTEGER NOT NULL,
    provider_faults_json TEXT NOT NULL,
    provider_other_fault TEXT,
    provider_note TEXT,
    review_reason TEXT NOT NULL DEFAULT 'manual_entry',
    app_score INTEGER,
    app_metrics_json TEXT,
    app_quality_json TEXT,
    app_source TEXT,
    accepted_for_learning INTEGER NOT NULL DEFAULT 1,
    excluded_reason TEXT,
    FOREIGN KEY (assessment_id) REFERENCES assessments(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_manual_score_entries_movement
ON manual_score_entries (movement_key, side, created_at);

CREATE TABLE IF NOT EXISTS scoring_threshold_decisions (
    id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    movement_key TEXT NOT NULL,
    threshold_key TEXT NOT NULL,
    old_value REAL NOT NULL,
    new_value REAL NOT NULL,
    status TEXT NOT NULL,
    metadata_json TEXT NOT NULL DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_scoring_threshold_decisions_lookup
ON scoring_threshold_decisions (movement_key, threshold_key, status, created_at);

CREATE TABLE IF NOT EXISTS employees (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    email TEXT,
    employer TEXT NOT NULL,
    created_at TEXT NOT NULL,
    created_by TEXT,
    notes TEXT
);

CREATE INDEX IF NOT EXISTS idx_employees_employer
ON employees (employer);

CREATE TABLE IF NOT EXISTS magic_link_tokens (
    id TEXT PRIMARY KEY,
    token_hash TEXT NOT NULL UNIQUE,
    employee_id TEXT NOT NULL,
    created_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    revoked_at TEXT,
    last_used_at TEXT,
    use_count INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY (employee_id) REFERENCES employees(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_magic_link_tokens_employee
ON magic_link_tokens (employee_id, expires_at);

CREATE TABLE IF NOT EXISTS sessions (
    token_hash TEXT PRIMARY KEY,
    role TEXT NOT NULL,
    subject_id TEXT,
    created_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    last_seen_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_sessions_expires_at
ON sessions (expires_at);

CREATE INDEX IF NOT EXISTS idx_sessions_role_subject
ON sessions (role, subject_id);
"""


def get_connection(db_path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(db_path)
    connection.execute("PRAGMA foreign_keys = ON")
    connection.row_factory = sqlite3.Row
    return connection


ASSESSMENT_MIGRATIONS: list[tuple[str, str]] = [
    ("scoring_mode", "TEXT NOT NULL DEFAULT 'ai_assisted'"),
    ("consent_notice_version", "TEXT"),
    ("consent_accepted_at", "TEXT"),
    ("consent_scope_json", "TEXT"),
    ("privacy_posture", "TEXT NOT NULL DEFAULT 'voluntary_ergonomic_wellness'"),
    ("retention_expires_at", "TEXT"),
]


MOVEMENT_RESULTS_MIGRATIONS: list[tuple[str, str]] = [
    ("app_metrics_json", "TEXT"),
    ("pose_trace_json", "TEXT"),
    ("quality_json", "TEXT"),
    ("app_score_available", "INTEGER NOT NULL DEFAULT 1"),
    ("provider_score", "INTEGER"),
    ("provider_right_score", "INTEGER"),
    ("provider_left_score", "INTEGER"),
    ("provider_final_score", "INTEGER"),
    ("provider_faults_json", "TEXT"),
    ("provider_note", "TEXT"),
    ("review_reason", "TEXT"),
    ("reviewed_at", "TEXT"),
    ("review_status", "TEXT NOT NULL DEFAULT 'unreviewed'"),
]


DRAFT_CAPTURES_MIGRATIONS: list[tuple[str, str]] = [
    ("pose_trace_json", "TEXT"),
    ("quality_json", "TEXT"),
]


def initialize_database(db_path: Path) -> None:
    with get_connection(db_path) as connection:
        connection.executescript(SCHEMA_SQL)
        connection.commit()
    _run_column_migrations(db_path)


def _run_column_migrations(db_path: Path) -> None:
    with get_connection(db_path) as connection:
        for column_name, column_def in ASSESSMENT_MIGRATIONS:
            try:
                connection.execute(
                    f"ALTER TABLE assessments ADD COLUMN {column_name} {column_def}"
                )
                connection.commit()
            except sqlite3.OperationalError as exc:
                if "duplicate column name" not in str(exc).lower():
                    raise
        for column_name, column_def in MOVEMENT_RESULTS_MIGRATIONS:
            try:
                connection.execute(
                    f"ALTER TABLE movement_results ADD COLUMN {column_name} {column_def}"
                )
                connection.commit()
            except sqlite3.OperationalError as exc:
                if "duplicate column name" not in str(exc).lower():
                    raise
        for column_name, column_def in DRAFT_CAPTURES_MIGRATIONS:
            try:
                connection.execute(
                    f"ALTER TABLE draft_captures ADD COLUMN {column_name} {column_def}"
                )
                connection.commit()
            except sqlite3.OperationalError as exc:
                if "duplicate column name" not in str(exc).lower():
                    raise
