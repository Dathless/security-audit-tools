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