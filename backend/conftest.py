from __future__ import annotations

import sys
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from core.config import config  # noqa: E402

# Test: token cố định, không ghi ra config.yaml trong lúc chạy test
config.settings.app.local_token = "test-token"
config.settings.app.require_local_token = True


@pytest.fixture(scope="session", autouse=True)
def _configure_db(tmp_path_factory) -> None:
    from core.module_registry import discover_modules

    # Import toàn bộ module trước khi tạo bảng để Base.metadata có đủ bảng riêng module
    discover_modules()

    from storage.db import db

    db.configure(f"sqlite:///{tmp_path_factory.mktemp('data') / 'test.db'}")
    db.create_all()
    yield
    db.engine.dispose()


@pytest.fixture()
def clean_db(_configure_db):
    from storage.db import Base, db

    Base.metadata.drop_all(db.engine)
    Base.metadata.create_all(db.engine)
    yield


@pytest.fixture()
def client(clean_db):
    from fastapi.testclient import TestClient

    from main import app

    with TestClient(app) as tc:
        tc.headers["X-Local-Token"] = "test-token"
        yield tc


@pytest.fixture()
def client_no_raise(clean_db):
    """TestClient không re-raise server exception — dùng cho test 500 error envelope."""
    from fastapi.testclient import TestClient

    from main import app

    with TestClient(app, raise_server_exceptions=False) as tc:
        tc.headers["X-Local-Token"] = "test-token"
        yield tc


@pytest.fixture()
def patch_psutil(monkeypatch):
    """Patch `psutil` trong modules/port_scanner/scanner.py bằng FakePsutil.

    Trả về callable: patch_psutil(conns=None, proc_map=None, deny_net=False).
    """
    from helpers import FakePsutil

    def _patch(conns=None, proc_map=None, deny_net=False):
        fake = FakePsutil(conns, proc_map)
        fake.deny_net = deny_net
        monkeypatch.setattr("modules.port_scanner.scanner.psutil", fake)
        return fake

    return _patch


@pytest.fixture()
def port_manifest():
    from core.module_registry import discover_modules

    return discover_modules()["port-scanner"]


@pytest.fixture()
def event_collector():
    """Thu thập các event phát qua event_bus trong lúc test chạy (pattern scan.#)."""
    from core.event_bus import event_bus

    collected: list[tuple[str, dict]] = []
    unsubs = []

    async def _collect(topic, message):
        collected.append((topic, message))

    unsubs.append(event_bus.subscribe("scan.#", _collect))
    yield collected
    for unsub in unsubs:
        unsub()