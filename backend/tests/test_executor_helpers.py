from __future__ import annotations

from datetime import datetime

import pytest
from sqlalchemy import select

from core.executor import _keys_of_scan, _mark_failed, _previous_scan, _whitelist_keys
from storage.db import Scan, ScanItem, WhitelistEntry, db


# ---------------------------------------------------------------------------
# UT-EXEC-001..002: _mark_failed
# ---------------------------------------------------------------------------


def _make_scan(scan_id: str, status: str = "running"):
    with db.session() as s:
        s.add(Scan(id=scan_id, module_id="port-scanner", status=status, started_at=datetime.utcnow()))
        s.commit()


def test_mark_failed_updates_status(clean_db):
    """UT-EXEC-001: Scan record tồn tại → status = "error", error_message set."""
    _make_scan("mk-1")
    _mark_failed("mk-1", "TIMEOUT", "scan timed out")
    with db.session() as s:
        row = s.get(Scan, "mk-1")
        assert row.status == "error"
        assert row.error_message == "scan timed out"
        assert row.finished_at is not None


def test_mark_failed_scan_not_found(clean_db):
    """UT-EXEC-002: Scan record không có → không crash, không exception."""
    _mark_failed("nonexistent-id", "CODE", "msg")
    with db.session() as s:
        assert s.get(Scan, "nonexistent-id") is None


# ---------------------------------------------------------------------------
# UT-EXEC-003..005: _previous_scan
# ---------------------------------------------------------------------------


def test_previous_scan_returns_predecessor(clean_db):
    """UT-EXEC-003: Có 2 scan → trả scan cũ hơn (không tính scan hiện tại)."""
    with db.session() as s:
        s.add(Scan(id="prev-old", module_id="mod1", status="done", started_at=datetime(2026, 1, 1)))
        s.add(Scan(id="prev-new", module_id="mod1", status="done", started_at=datetime(2026, 1, 2)))
        s.commit()

    with db.session() as s:
        prev = _previous_scan(s, "mod1", "prev-new")
        assert prev is not None
        assert prev.id == "prev-old"


def test_previous_scan_first_scan_returns_none(clean_db):
    """UT-EXEC-004: Scan đầu tiên → trả None."""
    _make_scan("first-scan")
    with db.session() as s:
        prev = _previous_scan(s, "port-scanner", "first-scan")
        assert prev is None


def test_previous_scan_ignores_failed_running_and_partial(clean_db):
    with db.session() as s:
        for index, (status, partial) in enumerate([("done", False), ("error", False), ("running", False), ("done", True)]):
            s.add(Scan(id=f"baseline-{index}", module_id="firewall-check", status=status, partial_result=partial, started_at=datetime(2026, 1, index + 1)))
        s.commit()
        assert _previous_scan(s, "firewall-check", "current").id == "baseline-0"


def test_previous_scan_excludes_current(clean_db):
    """UT-EXEC-005:传入 exclude_scan_id → scan đó bị loại khỏi kết quả."""
    with db.session() as s:
        s.add(Scan(id="exc-a", module_id="mod2", status="done", started_at=datetime(2026, 1, 1)))
        s.add(Scan(id="exc-b", module_id="mod2", status="done", started_at=datetime(2026, 1, 2)))
        s.commit()

    with db.session() as s:
        prev = _previous_scan(s, "mod2", "exc-b")
        assert prev is not None
        assert prev.id == "exc-a"

        prev2 = _previous_scan(s, "mod2", "exc-a")
        assert prev2 is not None
        assert prev2.id == "exc-b"


# ---------------------------------------------------------------------------
# UT-EXEC-006..007: _keys_of_scan
# ---------------------------------------------------------------------------


def test_keys_of_scan_returns_keys(clean_db):
    """UT-EXEC-006: Scan có 3 items → trả set 3 whitelist_key."""
    _make_scan("keys-scan")
    with db.session() as s:
        for key in ["80:nginx", "4444", "31337:app"]:
            s.add(ScanItem(scan_id="keys-scan", module_id="port-scanner", whitelist_key=key, severity="safe", title="t", detail_json="{}"))
        s.commit()

    with db.session() as s:
        keys = _keys_of_scan(s, "keys-scan")
        assert keys == {"80:nginx", "4444", "31337:app"}


def test_keys_of_scan_empty(clean_db):
    """UT-EXEC-007: Scan không có items → trả set rỗng."""
    _make_scan("empty-scan")
    with db.session() as s:
        keys = _keys_of_scan(s, "empty-scan")
        assert keys == set()


# ---------------------------------------------------------------------------
# UT-EXEC-008..010: _whitelist_keys
# ---------------------------------------------------------------------------


def test_whitelist_keys_returns_keys(clean_db):
    """UT-EXEC-008: Có 2 entries → trả set 2 key."""
    with db.session() as s:
        s.add(WhitelistEntry(module_id="port-scanner", whitelist_key="4444:proc", label="a"))
        s.add(WhitelistEntry(module_id="port-scanner", whitelist_key="80:nginx", label="b"))
        s.commit()

    with db.session() as s:
        keys = _whitelist_keys(s, "port-scanner")
        assert keys == {"4444:proc", "80:nginx"}


def test_whitelist_keys_empty(clean_db):
    """UT-EXEC-009: Không có entry → trả set rỗng."""
    with db.session() as s:
        keys = _whitelist_keys(s, "port-scanner")
        assert keys == set()


def test_whitelist_keys_per_module(clean_db):
    """UT-EXEC-010: Module A có key X, Module B có key X → query module A chỉ trả key X của A."""
    with db.session() as s:
        s.add(WhitelistEntry(module_id="mod-A", whitelist_key="key-X", label="a"))
        s.add(WhitelistEntry(module_id="mod-B", whitelist_key="key-X", label="b"))
        s.add(WhitelistEntry(module_id="mod-A", whitelist_key="key-Y", label="c"))
        s.commit()

    with db.session() as s:
        keys_a = _whitelist_keys(s, "mod-A")
        assert keys_a == {"key-X", "key-Y"}

        keys_b = _whitelist_keys(s, "mod-B")
        assert keys_b == {"key-X"}
