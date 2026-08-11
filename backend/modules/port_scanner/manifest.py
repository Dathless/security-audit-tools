from core.module_registry import ModuleManifest

from .routes import router
from .scanner import PortScannerModule

manifest = ModuleManifest(
    id="port-scanner",
    display_name="Port Scanner",
    version="0.1.0",
    scanner_cls=PortScannerModule,
    router=router,
    default_schedule=None,
)