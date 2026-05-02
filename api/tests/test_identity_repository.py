from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from api.app.auth_tokens import generate_token, hash_token
from api.app.database import get_connection, initialize_database
from api.app.repository import AssessmentRepository


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _later(seconds: int) -> str:
    return (datetime.now(timezone.utc) + timedelta(seconds=seconds)).isoformat()


def _earlier(seconds: int) -> str:
    return (datetime.now(timezone.utc) - timedelta(seconds=seconds)).isoformat()


def _build_repo(tmp_path: Path) -> AssessmentRepository:
    db_path = tmp_path / "hma.db"
    initialize_database(db_path)
    return AssessmentRepository(db_path)


# ---- Employees -------------------------------------------------------------


def test_create_employee_persists_expected_fields(tmp_path: Path):
    repo = _build_repo(tmp_path)

    record = repo.create_employee(
        "Jamie",
        "Hendrickson",
        email="jamie@example.com",
        notes="pilot cohort",
        created_by="provider",
    )

    assert record["id"]
    assert record["name"] == "Jamie"
    assert record["employer"] == "Hendrickson"
    assert record["email"] == "jamie@example.com"
    assert record["notes"] == "pilot cohort"
    assert record["created_by"] == "provider"
    assert record["created_at"]


def test_create_employee_allows_optional_fields_to_be_null(tmp_path: Path):
    repo = _build_repo(tmp_path)

    record = repo.create_employee("Alex", "Hendrickson")

    assert record["email"] is None
    assert record["notes"] is None
    assert record["created_by"] is None


def test_get_employee_returns_row_or_none(tmp_path: Path):
    repo = _build_repo(tmp_path)

    created = repo.create_employee("Jamie", "Hendrickson")

    fetched = repo.get_employee(created["id"])
    assert fetched is not None
    assert fetched["id"] == created["id"]
    assert fetched["name"] == "Jamie"

    assert repo.get_employee("does-not-exist") is None


def test_list_employees_filter_and_order(tmp_path: Path):
    repo = _build_repo(tmp_path)

    repo.create_employee("First", "Hendrickson")
    repo.create_employee("Second", "OtherCo")
    repo.create_employee("Third", "Hendrickson")

    all_rows = repo.list_employees()
    assert {row["name"] for row in all_rows} == {"First", "Second", "Third"}

    hendrickson_only = repo.list_employees(employer="Hendrickson")
    assert {row["name"] for row in hendrickson_only} == {"First", "Third"}


def test_list_employees_orders_newest_first(tmp_path: Path):
    repo = _build_repo(tmp_path)

    older = repo.create_employee("Older", "Hendrickson")
    newer = repo.create_employee("Newer", "Hendrickson")

    with get_connection(repo.db_path) as connection:
        connection.execute(
            "UPDATE employees SET created_at = ? WHERE id = ?",
            ("2026-01-01T00:00:00+00:00", older["id"]),
        )
        connection.execute(
            "UPDATE employees SET created_at = ? WHERE id = ?",
            ("2026-04-30T00:00:00+00:00", newer["id"]),
        )
        connection.commit()

    rows = repo.list_employees()
    assert [row["name"] for row in rows] == ["Newer", "Older"]


# ---- Magic-link tokens -----------------------------------------------------


def test_create_magic_link_token_stores_hash_not_plaintext(tmp_path: Path):
    repo = _build_repo(tmp_path)
    employee = repo.create_employee("Jamie", "Hendrickson")
    plaintext = generate_token()

    record = repo.create_magic_link_token(
        employee["id"],
        plaintext_token=plaintext,
        expires_at=_later(60),
    )

    assert record["token_hash"] == hash_token(plaintext)
    assert record["token_hash"] != plaintext

    with get_connection(repo.db_path) as connection:
        row = connection.execute(
            "SELECT token_hash FROM magic_link_tokens WHERE id = ?",
            (record["id"],),
        ).fetchone()
    assert row["token_hash"] == hash_token(plaintext)


def test_consume_magic_link_token_returns_employee_and_increments_use(tmp_path: Path):
    repo = _build_repo(tmp_path)
    employee = repo.create_employee("Jamie", "Hendrickson")
    plaintext = generate_token()
    repo.create_magic_link_token(
        employee["id"],
        plaintext_token=plaintext,
        expires_at=_later(60),
    )

    consumed = repo.consume_magic_link_token(plaintext, now_iso=_now())
    assert consumed is not None
    assert consumed["id"] == employee["id"]

    consumed_again = repo.consume_magic_link_token(plaintext, now_iso=_now())
    assert consumed_again is not None

    with get_connection(repo.db_path) as connection:
        row = connection.execute(
            "SELECT use_count, last_used_at FROM magic_link_tokens WHERE employee_id = ?",
            (employee["id"],),
        ).fetchone()
    assert row["use_count"] == 2
    assert row["last_used_at"]


def test_consume_magic_link_token_rejects_expired(tmp_path: Path):
    repo = _build_repo(tmp_path)
    employee = repo.create_employee("Jamie", "Hendrickson")
    plaintext = generate_token()
    repo.create_magic_link_token(
        employee["id"],
        plaintext_token=plaintext,
        expires_at=_earlier(60),
    )

    assert repo.consume_magic_link_token(plaintext, now_iso=_now()) is None


def test_consume_magic_link_token_rejects_revoked(tmp_path: Path):
    repo = _build_repo(tmp_path)
    employee = repo.create_employee("Jamie", "Hendrickson")
    plaintext = generate_token()
    record = repo.create_magic_link_token(
        employee["id"],
        plaintext_token=plaintext,
        expires_at=_later(60),
    )

    revoked = repo.revoke_magic_link_token(record["id"], now_iso=_now())
    assert revoked is True

    assert repo.consume_magic_link_token(plaintext, now_iso=_now()) is None


def test_consume_magic_link_token_rejects_unknown(tmp_path: Path):
    repo = _build_repo(tmp_path)
    assert repo.consume_magic_link_token("garbage", now_iso=_now()) is None


def test_revoke_employee_magic_links_revokes_all_active(tmp_path: Path):
    repo = _build_repo(tmp_path)
    employee = repo.create_employee("Jamie", "Hendrickson")
    plain_a = generate_token()
    plain_b = generate_token()
    repo.create_magic_link_token(employee["id"], plaintext_token=plain_a, expires_at=_later(60))
    repo.create_magic_link_token(employee["id"], plaintext_token=plain_b, expires_at=_later(60))

    revoked_count = repo.revoke_employee_magic_links(employee["id"], now_iso=_now())
    assert revoked_count == 2
    assert repo.consume_magic_link_token(plain_a, now_iso=_now()) is None
    assert repo.consume_magic_link_token(plain_b, now_iso=_now()) is None


def test_purge_expired_magic_link_tokens_removes_only_expired(tmp_path: Path):
    repo = _build_repo(tmp_path)
    employee = repo.create_employee("Jamie", "Hendrickson")
    plain_active = generate_token()
    plain_expired = generate_token()
    repo.create_magic_link_token(employee["id"], plaintext_token=plain_active, expires_at=_later(60))
    repo.create_magic_link_token(employee["id"], plaintext_token=plain_expired, expires_at=_earlier(60))

    purged = repo.purge_expired_magic_link_tokens(now_iso=_now())
    assert purged == 1

    assert repo.consume_magic_link_token(plain_active, now_iso=_now()) is not None


# ---- Sessions --------------------------------------------------------------


def test_create_and_get_session_round_trip(tmp_path: Path):
    repo = _build_repo(tmp_path)
    plaintext = generate_token()

    repo.create_session(
        role="employee",
        subject_id="employee-1",
        plaintext_token=plaintext,
        expires_at=_later(60),
    )

    session = repo.get_session(plaintext, now_iso=_now())
    assert session is not None
    assert session["role"] == "employee"
    assert session["subject_id"] == "employee-1"
    assert session["token_hash"] == hash_token(plaintext)


def test_get_session_returns_none_for_expired(tmp_path: Path):
    repo = _build_repo(tmp_path)
    plaintext = generate_token()
    repo.create_session(
        role="provider",
        subject_id=None,
        plaintext_token=plaintext,
        expires_at=_earlier(60),
    )

    assert repo.get_session(plaintext, now_iso=_now()) is None


def test_get_session_updates_last_seen_at(tmp_path: Path):
    repo = _build_repo(tmp_path)
    plaintext = generate_token()
    repo.create_session(
        role="employee",
        subject_id="employee-1",
        plaintext_token=plaintext,
        expires_at=_later(60),
    )

    first_now = _now()
    repo.get_session(plaintext, now_iso=first_now)
    later_now = _later(5)
    repo.get_session(plaintext, now_iso=later_now)

    with get_connection(repo.db_path) as connection:
        row = connection.execute(
            "SELECT last_seen_at FROM sessions WHERE token_hash = ?",
            (hash_token(plaintext),),
        ).fetchone()
    assert row["last_seen_at"] == later_now


def test_delete_session_removes_row(tmp_path: Path):
    repo = _build_repo(tmp_path)
    plaintext = generate_token()
    repo.create_session(
        role="provider",
        subject_id=None,
        plaintext_token=plaintext,
        expires_at=_later(60),
    )

    assert repo.delete_session(plaintext) is True
    assert repo.get_session(plaintext, now_iso=_now()) is None
    assert repo.delete_session(plaintext) is False


def test_purge_expired_sessions_removes_only_expired(tmp_path: Path):
    repo = _build_repo(tmp_path)
    active = generate_token()
    expired = generate_token()
    repo.create_session(
        role="provider", subject_id=None, plaintext_token=active, expires_at=_later(60)
    )
    repo.create_session(
        role="employee",
        subject_id="employee-1",
        plaintext_token=expired,
        expires_at=_earlier(60),
    )

    purged = repo.purge_expired_sessions(now_iso=_now())
    assert purged == 1
    assert repo.get_session(active, now_iso=_now()) is not None
