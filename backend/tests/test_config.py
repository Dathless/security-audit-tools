from __future__ import annotations

import pytest
import yaml


# ---------------------------------------------------------------------------
# UT-CONFIG-001..003: Config load
# ---------------------------------------------------------------------------


def test_config_load_from_yaml(tmp_path):
    """UT-CONFIG-001: Config load từ file YAML."""
    cfg_file = tmp_path / "config.yaml"
    cfg_file.write_text(
        yaml.dump(
            {
                "app": {"host": "0.0.0.0", "port": 9000},
                "modules": {
                    "port-scanner": {"enabled": True, "schedule": "0 * * * *"},
                },
            }
        ),
        encoding="utf-8",
    )

    from core.config import Config

    c = Config(cfg_file)
    assert c.app.host == "0.0.0.0"
    assert c.app.port == 9000
    m = c.module("port-scanner")
    assert m.enabled is True
    assert m.schedule == "0 * * * *"


def test_config_missing_file_uses_defaults(tmp_path):
    """UT-CONFIG-002: file không tồn tại → dùng default values, không crash."""
    from core.config import Config

    c = Config(tmp_path / "nonexistent.yaml")
    assert c.app.host == "127.0.0.1"
    assert c.app.port == 8000
    assert c.database.url == "sqlite:///./data/security_audit.db"


def test_config_module_unknown_returns_disabled():
    """UT-CONFIG-003: module_id không tồn tại → trả ModuleSettings(enabled=False)."""
    from core.config import Config, ModuleSettings

    c = Config()
    m = c.module("unknown-module-xyz")
    assert isinstance(m, ModuleSettings)
    assert m.enabled is False
    assert m.schedule is None
    assert m.extra == {}


# ---------------------------------------------------------------------------
# UT-CONFIG-004: Config.module() known module
# ---------------------------------------------------------------------------


def test_config_module_known(tmp_path):
    """UT-CONFIG-004: module_id có trong config → trả đúng settings."""
    cfg_file = tmp_path / "config.yaml"
    cfg_file.write_text(
        yaml.dump({"modules": {"my-mod": {"enabled": False, "schedule": "0 * * * *"}}}),
        encoding="utf-8",
    )
    from core.config import Config

    c = Config(cfg_file)
    m = c.module("my-mod")
    assert m.enabled is False
    assert m.schedule == "0 * * * *"


# ---------------------------------------------------------------------------
# UT-CONFIG-005..006: ensure_local_token
# ---------------------------------------------------------------------------


def test_ensure_local_token_generates_when_empty(tmp_path):
    """UT-CONFIG-005: Token rỗng → generate token mới, persist vào file."""
    cfg_file = tmp_path / "config.yaml"
    cfg_file.write_text(yaml.dump({"app": {"local_token": ""}}), encoding="utf-8")

    from core.config import Config

    c = Config(cfg_file)
    token = c.ensure_local_token()
    assert token  # non-empty
    assert len(token) > 10

    saved = yaml.safe_load(cfg_file.read_text(encoding="utf-8"))
    assert saved["app"]["local_token"] == token


def test_ensure_local_token_existing(tmp_path):
    """UT-CONFIG-006: Token đã tồn tại → trả token đó, không ghi đè."""
    cfg_file = tmp_path / "config.yaml"
    cfg_file.write_text(yaml.dump({"app": {"local_token": "existing-tok"}}), encoding="utf-8")

    from core.config import Config

    c = Config(cfg_file)
    token = c.ensure_local_token()
    assert token == "existing-tok"

    saved = yaml.safe_load(cfg_file.read_text(encoding="utf-8"))
    assert saved["app"]["local_token"] == "existing-tok"


# ---------------------------------------------------------------------------
# UT-CONFIG-007..008: ModuleSettings.from_config
# ---------------------------------------------------------------------------


def test_module_settings_from_config_full():
    """UT-CONFIG-007: Dict có enabled, schedule, extra keys → parse đúng."""
    from core.config import ModuleSettings

    m = ModuleSettings.from_config({"enabled": False, "schedule": "*/5 * * * *", "scan_mode": "nmap", "timeout": 30})
    assert m.enabled is False
    assert m.schedule == "*/5 * * * *"
    assert m.get("scan_mode") == "nmap"
    assert m.get("timeout") == 30


def test_module_settings_from_config_empty():
    """UT-CONFIG-008: Dict rỗng/None → default enabled=True, schedule=None."""
    from core.config import ModuleSettings

    m = ModuleSettings.from_config(None)
    assert m.enabled is True
    assert m.schedule is None
    assert m.extra == {}

    m2 = ModuleSettings.from_config({})
    assert m2.enabled is True
    assert m2.schedule is None


# ---------------------------------------------------------------------------
# UT-CONFIG-009..010: ModuleSettings.get
# ---------------------------------------------------------------------------


def test_module_settings_get_existing_key():
    """UT-CONFIG-009: get(key) key tồn tại → trả giá trị từ extra."""
    from core.config import ModuleSettings

    m = ModuleSettings.from_config({"scan_mode": "socket"})
    assert m.get("scan_mode") == "socket"


def test_module_settings_get_missing_key():
    """UT-CONFIG-010: Key không có → trả default."""
    from core.config import ModuleSettings

    m = ModuleSettings.from_config({})
    assert m.get("nonexistent", "fallback") == "fallback"
    assert m.get("nonexistent") is None
