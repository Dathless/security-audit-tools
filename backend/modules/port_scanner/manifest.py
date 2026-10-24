from core.module_registry import ModuleManifest

from .routes import router
from .scanner import PortScannerModule
from .reviews import port_summary

manifest = ModuleManifest(
    id="port-scanner",
    display_name="Port Scanner",
    version="0.2.0",
    scanner_cls=PortScannerModule,
    router=router,
    default_schedule=None,
    meta={"identity_version": 2, "serialize_scans": True, "whitelist_override": False, "summary_serializer": port_summary},
)
