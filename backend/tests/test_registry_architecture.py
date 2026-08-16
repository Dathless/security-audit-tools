from __future__ import annotations

import importlib
import pkgutil
import types
from pathlib import Path

from core.module_registry import ModuleManifest


def _backend_dir() -> Path:
    return Path(__file__).resolve().parent.parent


def _core_files() -> list[Path]:
    return sorted((_backend_dir() / "core").glob("*.py"))


# ---------------------------------------------------------------------------
# ARCHITECTURE (TC-MODULE-005)
# ---------------------------------------------------------------------------


def test_core_does_not_import_modules():
    """TC-MODULE-005: core/ không import ngược modules/ (trừ module_registry)."""
    for path in _core_files():
        if path.name == "module_registry.py":
            continue
        text = path.read_text(encoding="utf-8")
        for line in text.splitlines():
            stripped = line.strip()
            if stripped.startswith("#"):
                continue
            assert not stripped.startswith("import modules"), f"{path.name}: {stripped}"
            assert not stripped.startswith("from modules"), f"{path.name}: {stripped}"


def test_module_registry_only_uses_modules_namespace():
    """module_registry chỉ được phép đọc namespace `modules`, không import submodule."""
    path = _backend_dir() / "core" / "module_registry.py"
    text = path.read_text(encoding="utf-8")
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            continue
        assert "from modules" not in stripped, f"module_registry.py: {stripped}"
    assert "import modules" in text


# ---------------------------------------------------------------------------
# REGISTRY EDGE CASES (TC-MODULE-003/004)
# ---------------------------------------------------------------------------


def _patch_discovery(monkeypatch, packages):
    """Giả lập pkgutil.iter_modules chỉ thấy các package được chỉ định."""
    real_import = importlib.import_module

    def fake_iter(path):
        for name in packages:
            yield (None, name, True)

    monkeypatch.setattr(pkgutil, "iter_modules", fake_iter)
    return real_import


def test_module_discovery_failure_isolation(monkeypatch):
    """TC-MODULE-004: module lỗi khi discovery -> không crash, module hợp lệ vẫn đăng ký."""
    from core import module_registry as mr

    real_import = _patch_discovery(monkeypatch, ["port_scanner", "broken_module"])

    def fake_import(name):
        if name == "modules.broken_module.manifest":
            raise RuntimeError("boom on discovery")
        return real_import(name)

    monkeypatch.setattr(importlib, "import_module", fake_import)

    registry = mr.discover_modules()
    assert "port-scanner" in registry
    assert "broken_module" not in registry


def test_module_registry_no_duplicate_ids(monkeypatch):
    """TC-MODULE-003: hai module trùng ID -> registry không crash, không có ID lặp."""
    from core import module_registry as mr

    real_import = _patch_discovery(monkeypatch, ["dup_one", "dup_two"])

    dup_manifest = ModuleManifest(id="dup-id", display_name="Dup", version="1.0", scanner_cls=None)

    def fake_import(name):
        if name in ("modules.dup_one.manifest", "modules.dup_two.manifest"):
            mod = types.ModuleType(name)
            mod.manifest = dup_manifest
            return mod
        return real_import(name)

    monkeypatch.setattr(importlib, "import_module", fake_import)

    registry = mr.discover_modules()
    ids = list(registry.keys())
    assert len(ids) == len(set(ids))
    assert ids == ["dup-id"]
