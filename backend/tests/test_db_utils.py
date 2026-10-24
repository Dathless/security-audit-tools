from __future__ import annotations

import re
from datetime import datetime

from storage.db import DATETIME_FMT, Database, dt_to_iso, now_iso


# ---------------------------------------------------------------------------
# UT-DB-001..002: now_iso / dt_to_iso
# ---------------------------------------------------------------------------


def test_now_iso_format():
    """UT-DB-001: now_iso() match pattern %Y-%m-%dT%H:%M:%S.%fZ."""
    result = now_iso()
    assert re.match(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{6}Z$", result)


def test_dt_to_iso_with_datetime():
    """UT-DB-002: dt_to_iso(datetime) → trả ISO string đúng format."""
    dt = datetime(2026, 1, 15, 10, 30, 45, 123456)
    result = dt_to_iso(dt)
    assert result == "2026-01-15T10:30:45.123456Z"


# ---------------------------------------------------------------------------
# UT-DB-003: dt_to_iso with None
# ---------------------------------------------------------------------------


def test_dt_to_iso_with_none():
    """UT-DB-003: dt_to_iso(None) → trả None."""
    assert dt_to_iso(None) is None


# ---------------------------------------------------------------------------
# UT-DB-004..006: Database session_scope / create_all
# ---------------------------------------------------------------------------


def test_database_session_scope_commit(tmp_path):
    """UT-DB-004: Operation thành công → data persist."""
    db = Database(f"sqlite:///{tmp_path / 'test.db'}")
    db.create_all()
    from storage.db import Scan

    gen = db.session_scope()
    s = next(gen)
    try:
        s.add(Scan(id="db-scope-1", module_id="test", status="running", started_at=datetime.utcnow()))
    finally:
        try:
            next(gen)
        except StopIteration:
            pass

    with db.session() as s:
        row = s.get(Scan, "db-scope-1")
        assert row is not None
        assert row.status == "running"


def test_database_session_scope_rollback_on_error(tmp_path):
    """UT-DB-005: Exception giữa chừng → rollback, data không persist."""
    db = Database(f"sqlite:///{tmp_path / 'test.db'}")
    db.create_all()
    from storage.db import Scan

    gen = db.session_scope()
    s = next(gen)
    try:
        s.add(Scan(id="db-scope-fail", module_id="test", status="running", started_at=datetime.utcnow()))
        raise ValueError("boom")
    except ValueError:
        s.rollback()
    finally:
        try:
            next(gen)
        except StopIteration:
            pass

    with db.session() as s:
        row = s.get(Scan, "db-scope-fail")
        assert row is None


def test_database_create_all_creates_tables(tmp_path):
    """UT-DB-006: Gọi create_all → tất cả bảng tồn tại."""
    db = Database(f"sqlite:///{tmp_path / 'test.db'}")
    db.create_all()

    from sqlalchemy import inspect

    inspector = inspect(db.engine)
    tables = inspector.get_table_names()
    assert "scans" in tables
    assert "scan_items" in tables
    assert "whitelist_entries" in tables
    assert "scan_diff_log" in tables
