from __future__ import annotations

from sqlalchemy import select

from helpers import FakeProcess, fake_conn
from storage.db import Scan, ScanItem, WhitelistEntry, db


# ---------------------------------------------------------------------------
# CL-WL-001: Whitelist override danger → safe
# ---------------------------------------------------------------------------


async def test_whitelist_override_danger_to_safe(clean_db, patch_psutil, port_manifest):
    """CL-WL-001: Tạo whitelist key `4444:proc` → Scan thấy port 4444 → severity = safe."""
    from core.executor import execute_scan

    # Scan không có whitelist → 4444 là danger
    patch_psutil([fake_conn("127.0.0.1", 4444, pid=10)], {10: FakeProcess("myapp.exe")})
    await execute_scan(port_manifest, "wl-d1")
    with db.session() as s:
        item = s.scalars(select(ScanItem).where(ScanItem.scan_id == "wl-d1")).one()
        assert item.severity == "danger"
        assert item.whitelist_key == "4444:myapp.exe"

    # Tạo whitelist
    with db.session() as s:
        s.add(WhitelistEntry(module_id="port-scanner", whitelist_key="4444:myapp.exe", label="known app"))
        s.commit()

    # Scan lại → severity = safe
    patch_psutil([fake_conn("127.0.0.1", 4444, pid=10)], {10: FakeProcess("myapp.exe")})
    await execute_scan(port_manifest, "wl-d2")
    with db.session() as s:
        item2 = s.scalars(select(ScanItem).where(ScanItem.scan_id == "wl-d2")).one()
        assert item2.severity == "safe"


# ---------------------------------------------------------------------------
# CL-WL-002: Whitelist override warning → safe
# ---------------------------------------------------------------------------


async def test_whitelist_override_warning_to_safe(clean_db, patch_psutil, port_manifest):
    """CL-WL-002: Tạo whitelist key cho port bind 0.0.0.0 → Scan → severity = safe."""
    from core.executor import execute_scan

    patch_psutil([fake_conn("0.0.0.0", 8080)])
    await execute_scan(port_manifest, "wl-w1")
    with db.session() as s:
        item = s.scalars(select(ScanItem).where(ScanItem.scan_id == "wl-w1")).one()
        assert item.severity == "warning"

    with db.session() as s:
        s.add(WhitelistEntry(module_id="port-scanner", whitelist_key="8080", label="web server"))
        s.commit()

    patch_psutil([fake_conn("0.0.0.0", 8080)])
    await execute_scan(port_manifest, "wl-w2")
    with db.session() as s:
        item2 = s.scalars(select(ScanItem).where(ScanItem.scan_id == "wl-w2")).one()
        assert item2.severity == "safe"


# ---------------------------------------------------------------------------
# CL-WL-003: Remove whitelist khôi phục severity
# ---------------------------------------------------------------------------


async def test_remove_whitelist_restores_severity(clean_db, patch_psutil, port_manifest):
    """CL-WL-003: Whitelist exist → scan = safe → remove whitelist → scan lại = danger."""
    from core.executor import execute_scan

    with db.session() as s:
        s.add(WhitelistEntry(module_id="port-scanner", whitelist_key="4444:app.exe", label="known"))
        s.commit()

    patch_psutil([fake_conn("127.0.0.1", 4444, pid=5)], {5: FakeProcess("app.exe")})
    await execute_scan(port_manifest, "wl-r1")
    with db.session() as s:
        item = s.scalars(select(ScanItem).where(ScanItem.scan_id == "wl-r1")).one()
        assert item.severity == "safe"

    # Xoá whitelist
    with db.session() as s:
        entry = s.scalars(select(WhitelistEntry).where(WhitelistEntry.whitelist_key == "4444:app.exe")).one()
        s.delete(entry)
        s.commit()

    patch_psutil([fake_conn("127.0.0.1", 4444, pid=5)], {5: FakeProcess("app.exe")})
    await execute_scan(port_manifest, "wl-r2")
    with db.session() as s:
        item2 = s.scalars(select(ScanItem).where(ScanItem.scan_id == "wl-r2")).one()
        assert item2.severity == "danger"


# ---------------------------------------------------------------------------
# CL-WL-004: Whitelist không ảnh hưởng item khác
# ---------------------------------------------------------------------------


async def test_whitelist_does_not_affect_other_items(clean_db, patch_psutil, port_manifest):
    """CL-WL-004: Whitelist key `80:nginx` → port 4444 vẫn giữ severity gốc."""
    from core.executor import execute_scan

    with db.session() as s:
        s.add(WhitelistEntry(module_id="port-scanner", whitelist_key="80:nginx", label="web"))
        s.commit()

    patch_psutil([fake_conn("127.0.0.1", 80, pid=1), fake_conn("127.0.0.1", 4444, pid=2)], {1: FakeProcess("nginx"), 2: FakeProcess("app.exe")})
    await execute_scan(port_manifest, "wl-ix")
    with db.session() as s:
        items = s.scalars(select(ScanItem).where(ScanItem.scan_id == "wl-ix")).all()
        by_key = {it.whitelist_key: it.severity for it in items}
        assert by_key["80:nginx"] == "safe"
        assert by_key["4444:app.exe"] == "danger"


# ---------------------------------------------------------------------------
# CL-WL-005: Whitelist persists qua 3 lần scan
# ---------------------------------------------------------------------------


async def test_whitelist_persists_across_scans(clean_db, patch_psutil, port_manifest):
    """CL-WL-005: Scan #1 (danger) → whitelist → Scan #2 (safe) → Scan #3 (vẫn safe)."""
    from core.executor import execute_scan

    # Scan #1: danger
    patch_psutil([fake_conn("127.0.0.1", 4444, pid=5)], {5: FakeProcess("app.exe")})
    await execute_scan(port_manifest, "wl-p1")
    with db.session() as s:
        item = s.scalars(select(ScanItem).where(ScanItem.scan_id == "wl-p1")).one()
        assert item.severity == "danger"

    # Tạo whitelist
    with db.session() as s:
        s.add(WhitelistEntry(module_id="port-scanner", whitelist_key="4444:app.exe", label="ok"))
        s.commit()

    # Scan #2: safe
    patch_psutil([fake_conn("127.0.0.1", 4444, pid=5)], {5: FakeProcess("app.exe")})
    await execute_scan(port_manifest, "wl-p2")
    with db.session() as s:
        item2 = s.scalars(select(ScanItem).where(ScanItem.scan_id == "wl-p2")).one()
        assert item2.severity == "safe"

    # Scan #3: vẫn safe
    patch_psutil([fake_conn("127.0.0.1", 4444, pid=5)], {5: FakeProcess("app.exe")})
    await execute_scan(port_manifest, "wl-p3")
    with db.session() as s:
        item3 = s.scalars(select(ScanItem).where(ScanItem.scan_id == "wl-p3")).one()
        assert item3.severity == "safe"


# ---------------------------------------------------------------------------
# CL-WL-006: Whitelist ID không duplicate
# ---------------------------------------------------------------------------


def test_whitelist_duplicate_via_api(client):
    """CL-WL-006: Thêm cùng key 2 lần qua API → chỉ 1 record, HTTP không crash."""
    resp1 = client.post(
        "/api/v1/modules/port-scanner/whitelist",
        json={"whitelist_key": "4444:dup", "label": "first"},
    )
    assert resp1.status_code == 200
    assert resp1.json()["data"]["created"] is True

    resp2 = client.post(
        "/api/v1/modules/port-scanner/whitelist",
        json={"whitelist_key": "4444:dup", "label": "second"},
    )
    assert resp2.status_code == 200
    assert resp2.json()["data"]["created"] is False

    # Verify chỉ có 1 record
    resp3 = client.get("/api/v1/modules/port-scanner/whitelist")
    entries = resp3.json()["data"]
    assert len(entries) == 1
    assert entries[0]["whitelist_key"] == "4444:dup"
