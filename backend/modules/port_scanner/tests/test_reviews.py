from __future__ import annotations

import json
from datetime import datetime

import pytest
from sqlalchemy import select

from core.executor import execute_scan
from helpers import FakeProcess, fake_conn
from modules.port_scanner.manifest import manifest
from storage.db import Scan, ScanItem, WhitelistEntry, db

BASE = "/api/v1/modules/port-scanner"


async def snapshot(patch_psutil, scan_id, process="app.exe", pid=1, denied=False, empty=False, partial=False):
    connections = [] if empty else [fake_conn("0.0.0.0", 4444, pid)]
    if partial:
        connections.append(fake_conn("invalid-address", 8080, pid))
    patch_psutil(connections,
                 {pid: FakeProcess(process, access_denied=denied)})
    await execute_scan(manifest, scan_id)
    with db.session() as session:
        assert session.get(Scan, scan_id).status == "done"
        item = session.scalar(select(ScanItem).where(ScanItem.scan_id == scan_id))
        return item.id if item else None


def acknowledge(client, scan_id, item_id):
    response = client.post(BASE + "/reviews", json={"scan_id": scan_id, "item_id": item_id, "note": "known endpoint"})
    assert response.status_code == 200, response.text
    return response.json()["data"]


async def test_acknowledgement_is_idempotent_and_never_changes_risk(client, patch_psutil):
    item_id = await snapshot(patch_psutil, "first")
    first = acknowledge(client, "first", item_id)
    second = acknowledge(client, "first", item_id)
    assert first["id"] == second["id"]
    assert second["created"] is False
    data = client.get(BASE + "/scans/latest").json()["data"]
    assert data["items"][0]["severity"] == "danger"
    assert data["items"][0]["review_status"] == "reviewed"
    assert data["summary"]["danger"] == 1
    assert data["summary"]["reviewed_count"] == 1
    assert data["summary"]["needs_review_count"] == 0


async def test_review_survives_pid_restart_but_not_owner_a_b_a(client, patch_psutil):
    item_id = await snapshot(patch_psutil, "a")
    acknowledge(client, "a", item_id)
    await snapshot(patch_psutil, "a-restart", pid=99)
    assert client.get(BASE + "/scans/latest").json()["data"]["items"][0]["review_status"] == "reviewed"
    await snapshot(patch_psutil, "b", process="other.exe")
    await snapshot(patch_psutil, "a-again")
    data = client.get(BASE + "/scans/latest").json()["data"]
    assert data["items"][0]["review_status"] == "needs_review"
    assert data["items"][0]["detail"]["change_type"] == "changed"
    assert data["items"][0]["detail"]["previous_evidence"]["owners"][0]["name"] == "other.exe"


async def test_incomplete_metadata_suspends_without_expiring_review(client, patch_psutil):
    item_id = await snapshot(patch_psutil, "known")
    acknowledge(client, "known", item_id)
    denied_id = await snapshot(patch_psutil, "denied", denied=True)
    data = client.get(BASE + "/scans/latest").json()["data"]
    assert data["items"][0]["review_status"] == "needs_review"
    temporary = acknowledge(client, "denied", denied_id)
    assert temporary["scope"] == "scan"
    await snapshot(patch_psutil, "recovered")
    assert client.get(BASE + "/scans/latest").json()["data"]["items"][0]["review_status"] == "reviewed"


async def test_disappearance_expires_review_and_reappearance_needs_new_ack(client, patch_psutil):
    item_id = await snapshot(patch_psutil, "present")
    acknowledge(client, "present", item_id)
    await snapshot(patch_psutil, "empty", empty=True)
    await snapshot(patch_psutil, "returned")
    assert client.get(BASE + "/scans/latest").json()["data"]["items"][0]["review_status"] == "needs_review"


async def test_stale_or_cross_scan_review_target_is_rejected(client, patch_psutil):
    first_id = await snapshot(patch_psutil, "old")
    second_id = await snapshot(patch_psutil, "new")
    assert client.post(BASE + "/reviews", json={"scan_id": "old", "item_id": first_id}).status_code == 409
    assert client.post(BASE + "/reviews", json={"scan_id": "new", "item_id": first_id}).status_code == 404
    assert client.post(BASE + "/reviews", json={"scan_id": "new", "item_id": second_id, "note": "x" * 501}).status_code == 422


async def test_review_delete_and_pagination(client, patch_psutil):
    item_id = await snapshot(patch_psutil, "target")
    record = acknowledge(client, "target", item_id)
    data = client.get(BASE + "/reviews?page=0&page_size=999").json()["data"]
    assert (data["total"], data["page"], data["page_size"]) == (1, 1, 100)
    assert client.delete(BASE + f"/reviews/{record['id']}").status_code == 200
    assert client.get(BASE + "/scans/latest").json()["data"]["items"][0]["review_status"] == "needs_review"


async def test_partial_observed_owner_change_expires_review_but_absence_does_not(client, patch_psutil):
    item_id = await snapshot(patch_psutil, "a")
    acknowledge(client, "a", item_id)
    await snapshot(patch_psutil, "partial-missing", empty=True, partial=True)
    await snapshot(patch_psutil, "a-present")
    assert client.get(BASE + "/scans/latest").json()["data"]["items"][0]["review_status"] == "reviewed"
    await snapshot(patch_psutil, "partial-b", process="other.exe", partial=True)
    await snapshot(patch_psutil, "returned-a")
    assert client.get(BASE + "/scans/latest").json()["data"]["items"][0]["review_status"] == "needs_review"


async def test_module_summary_uses_current_review_counts(client, patch_psutil):
    item_id = await snapshot(patch_psutil, "sidebar")
    acknowledge(client, "sidebar", item_id)
    modules = client.get("/api/v1/modules").json()["data"]["modules"]
    summary = next(module for module in modules if module["id"] == "port-scanner")["last_scan"]["summary"]
    assert summary["danger"] == 1
    assert summary["needs_review_count"] == 0


def test_legacy_whitelist_is_read_delete_only_and_history_is_not_reclassified(client):
    with db.session() as session:
        legacy = WhitelistEntry(module_id="port-scanner", whitelist_key="4444:old.exe")
        session.add(legacy)
        session.add(Scan(id="legacy", module_id="port-scanner", status="done", started_at=datetime.utcnow(), summary_json='{"safe":1}'))
        session.add(ScanItem(scan_id="legacy", module_id="port-scanner", whitelist_key="4444:old.exe", severity="safe", title="old", detail_json='{"port":4444}'))
        session.commit()
        legacy_id = legacy.id
    assert client.post(BASE + "/whitelist", json={"whitelist_key": "4444:old.exe"}).status_code == 410
    assert len(client.get(BASE + "/whitelist").json()["data"]) == 1
    assert client.delete(BASE + f"/whitelist/{legacy_id}").status_code == 200
    data = client.get(BASE + "/scans/latest").json()["data"]
    assert data["assessment_status"] == "legacy"
    assert data["items"][0]["severity"] == "safe"


def test_review_routes_require_token(client):
    for method, path, kwargs in [("get", "/reviews", {}), ("post", "/reviews", {"json": {"scan_id": "x", "item_id": 1}}), ("delete", "/reviews/1", {})]:
        assert getattr(client, method)(BASE + path, headers={"X-Local-Token": "bad"}, **kwargs).status_code == 401


async def test_expiry_rolls_back_when_snapshot_persistence_fails(client, patch_psutil, monkeypatch):
    from modules.port_scanner.models import PortReview
    from modules.port_scanner.scanner import PortScannerModule
    item_id = await snapshot(patch_psutil, "stable")
    acknowledge(client, "stable", item_id)
    original = PortScannerModule.on_persist
    def broken(self, session, scan_id, result, previous):
        original(self, session, scan_id, result, previous)
        raise RuntimeError("fail after review expiry")
    monkeypatch.setattr(PortScannerModule, "on_persist", broken)
    patch_psutil([], {})
    await execute_scan(manifest, "rollback-review")
    with db.session() as session:
        assert session.get(Scan, "rollback-review").status == "error"
        assert session.scalar(select(PortReview)).expired_at is None


def test_openapi_documents_review_and_migration_conflicts(client):
    paths = client.get("/openapi.json").json()["paths"]
    assert "409" in paths[BASE + "/reviews"]["post"]["responses"]
    assert "410" in paths[BASE + "/whitelist"]["post"]["responses"]
    assert "409" in paths[BASE + "/scan"]["post"]["responses"]
    assert "delete" in paths[BASE + "/reviews/{review_id}"]


async def test_multiple_owner_order_is_stable_but_removed_owner_invalidates_review(client, patch_psutil):
    async def collect(scan_id, owners):
        patch_psutil([fake_conn("0.0.0.0", 4444, pid) for pid in owners],
                     {1: FakeProcess("first.exe"), 2: FakeProcess("second.exe")})
        await execute_scan(manifest, scan_id)
        return client.get(BASE + "/scans/latest").json()["data"]["items"][0]
    first = await collect("owners-a", [1, 2])
    acknowledge(client, "owners-a", first["id"])
    assert (await collect("owners-reordered", [2, 1]))["review_status"] == "reviewed"
    assert (await collect("owners-removed", [1]))["review_status"] == "needs_review"
    assert (await collect("owners-restored", [1, 2]))["review_status"] == "needs_review"


async def test_changed_risk_invalidates_review_even_when_owner_is_unchanged(client, patch_psutil, monkeypatch):
    from core.config import config, ModuleSettings
    item_id = await snapshot(patch_psutil, "risky")
    acknowledge(client, "risky", item_id)
    monkeypatch.setitem(config.settings.modules, "port-scanner", ModuleSettings(extra={"known_risky_ports": []}))
    await snapshot(patch_psutil, "no-risky-list")
    item = client.get(BASE + "/scans/latest").json()["data"]["items"][0]
    assert item["severity"] == "warning"
    assert item["review_status"] == "needs_review"
    monkeypatch.setitem(config.settings.modules, "port-scanner", ModuleSettings(extra={"known_risky_ports": [4444]}))
    await snapshot(patch_psutil, "risky-again")
    assert client.get(BASE + "/scans/latest").json()["data"]["items"][0]["review_status"] == "needs_review"
