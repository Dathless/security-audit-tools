from __future__ import annotations

import json
import pytest
from sqlalchemy import select
from helpers import FakeProcess, fake_conn
from storage.db import Scan, ScanItem, WhitelistEntry, db


@pytest.mark.parametrize("address,port,expected", [("127.0.0.1",4444,"warning"),("0.0.0.0",4444,"danger"),("127.0.0.1",8080,"safe")])
async def test_legacy_or_matching_endpoint_whitelist_never_lowers_raw_risk(clean_db, patch_psutil, port_manifest, address, port, expected):
    from core.executor import execute_scan
    key = json.dumps(["endpoint-v2","tcp","ipv4",address,port],separators=(",",":"))
    with db.session() as session:
        session.add(WhitelistEntry(module_id="port-scanner",whitelist_key=key))
        session.commit()
    patch_psutil([fake_conn(address,port,1)],{1:FakeProcess("app.exe")})
    await execute_scan(port_manifest,"legacy-does-not-override")
    with db.session() as session:
        item = session.scalar(select(ScanItem))
        summary = json.loads(session.get(Scan,"legacy-does-not-override").summary_json)
        assert item.severity == expected
        assert summary[expected] == 1


def test_legacy_delete_cannot_remove_other_module_entry(client):
    with db.session() as session:
        entry=WhitelistEntry(module_id="other",whitelist_key="8080")
        session.add(entry)
        session.commit()
        entry_id=entry.id
    assert client.delete(f"/api/v1/modules/port-scanner/whitelist/{entry_id}").status_code == 404
    with db.session() as session:
        assert session.get(WhitelistEntry,entry_id) is not None
