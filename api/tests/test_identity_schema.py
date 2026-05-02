from __future__ import annotations

from pathlib import Path

from api.app.database import get_connection, initialize_database


def _table_names(db_path: Path) -> set[str]:
    with get_connection(db_path) as connection:
        rows = connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    return {row["name"] for row in rows}


def _index_names(db_path: Path) -> set[str]:
    with get_connection(db_path) as connection:
        rows = connection.execute(
            "SELECT name FROM sqlite_master WHERE type='index'"
        ).fetchall()
    return {row["name"] for row in rows}


def _column_names(db_path: Path, table: str) -> list[str]:
    with get_connection(db_path) as connection:
        rows = connection.execute(f"PRAGMA table_info({table})").fetchall()
    return [row["name"] for row in rows]


def test_initialize_creates_identity_tables(tmp_path: Path):
    db_path = tmp_path / "hma.db"
    initialize_database(db_path)

    tables = _table_names(db_path)
    assert {"employees", "magic_link_tokens", "sessions"} <= tables


def test_employees_columns(tmp_path: Path):
    db_path = tmp_path / "hma.db"
    initialize_database(db_path)

    columns = _column_names(db_path, "employees")
    assert columns == [
        "id",
        "name",
        "email",
        "employer",
        "created_at",
        "created_by",
        "notes",
    ]


def test_magic_link_tokens_columns_and_unique(tmp_path: Path):
    db_path = tmp_path / "hma.db"
    initialize_database(db_path)

    columns = _column_names(db_path, "magic_link_tokens")
    assert columns == [
        "id",
        "token_hash",
        "employee_id",
        "created_at",
        "expires_at",
        "revoked_at",
        "last_used_at",
        "use_count",
    ]

    with get_connection(db_path) as connection:
        connection.execute(
            "INSERT INTO employees (id, name, employer, created_at) VALUES ('e1', 'Jamie', 'Hendrickson', '2026-05-01T00:00:00+00:00')"
        )
        connection.execute(
            "INSERT INTO magic_link_tokens (id, token_hash, employee_id, created_at, expires_at) "
            "VALUES ('t1', 'hashA', 'e1', '2026-05-01T00:00:00+00:00', '2026-05-08T00:00:00+00:00')"
        )
        connection.commit()

        try:
            connection.execute(
                "INSERT INTO magic_link_tokens (id, token_hash, employee_id, created_at, expires_at) "
                "VALUES ('t2', 'hashA', 'e1', '2026-05-01T00:00:00+00:00', '2026-05-08T00:00:00+00:00')"
            )
            connection.commit()
        except Exception as exc:
            assert "UNIQUE" in str(exc).upper()
        else:
            raise AssertionError("expected UNIQUE constraint on token_hash")


def test_magic_link_cascade_on_employee_delete(tmp_path: Path):
    db_path = tmp_path / "hma.db"
    initialize_database(db_path)

    with get_connection(db_path) as connection:
        connection.execute(
            "INSERT INTO employees (id, name, employer, created_at) VALUES ('e1', 'Jamie', 'Hendrickson', '2026-05-01T00:00:00+00:00')"
        )
        connection.execute(
            "INSERT INTO magic_link_tokens (id, token_hash, employee_id, created_at, expires_at) "
            "VALUES ('t1', 'hashA', 'e1', '2026-05-01T00:00:00+00:00', '2026-05-08T00:00:00+00:00')"
        )
        connection.commit()

        connection.execute("DELETE FROM employees WHERE id = 'e1'")
        connection.commit()

        remaining = connection.execute(
            "SELECT COUNT(*) AS n FROM magic_link_tokens WHERE employee_id = 'e1'"
        ).fetchone()
    assert remaining["n"] == 0


def test_sessions_columns(tmp_path: Path):
    db_path = tmp_path / "hma.db"
    initialize_database(db_path)

    columns = _column_names(db_path, "sessions")
    assert columns == [
        "token_hash",
        "role",
        "subject_id",
        "created_at",
        "expires_at",
        "last_seen_at",
    ]


def test_identity_indexes_present(tmp_path: Path):
    db_path = tmp_path / "hma.db"
    initialize_database(db_path)

    indexes = _index_names(db_path)
    assert "idx_employees_employer" in indexes
    assert "idx_magic_link_tokens_employee" in indexes
    assert "idx_sessions_expires_at" in indexes
    assert "idx_sessions_role_subject" in indexes


def test_initialize_is_idempotent(tmp_path: Path):
    db_path = tmp_path / "hma.db"
    initialize_database(db_path)
    initialize_database(db_path)

    tables = _table_names(db_path)
    assert {"employees", "magic_link_tokens", "sessions"} <= tables
