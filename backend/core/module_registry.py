from __future__ import annotations

import importlib
import logging
import pkgutil
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from fastapi import APIRouter

    from .scanner_base import ScannerBase

logger = logging.getLogger(__name__)

import modules  # noqa: E402  (modules package must be importable from backend root)


@dataclass
class ModuleManifest:
    id: str
    display_name: str
    version: str
    scanner_cls: type["ScannerBase"]
    router: Optional["APIRouter"] = None
    default_schedule: Optional[str] = None
    enabled: bool = True
    meta: dict = field(default_factory=dict)


def discover_modules() -> dict[str, ModuleManifest]:
    """Quét tất cả gói con dưới `modules/`, nạp manifest của gói nào có manifest.py.

    Gói không có manifest.py (vd: thư mục đang phát triển dở) bị bỏ qua
    một cách an toàn — registry không bao giờ làm sập app khi gặp module lỗi.
    """
    found: dict[str, ModuleManifest] = {}
    for _, name, ispkg in pkgutil.iter_modules(modules.__path__):
        if not ispkg:
            continue
        try:
            manifest_mod = importlib.import_module(f"modules.{name}.manifest")
            manifest = manifest_mod.manifest
            if isinstance(manifest, ModuleManifest):
                found[manifest.id] = manifest
                logger.info("Module registered: %s (%s)", manifest.id, manifest.display_name)
            else:
                logger.warning("modules.%s.manifest không export `ModuleManifest`", name)
        except ModuleNotFoundError:
            logger.debug("modules.%s chưa có manifest.py, bỏ qua", name)
        except Exception:
            logger.exception("Lỗi khi nạp manifest modules.%s", name)
    return found