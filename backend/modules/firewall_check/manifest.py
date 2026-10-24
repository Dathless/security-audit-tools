from core.module_registry import ModuleManifest

from .routes import router
from .scanner import FirewallCheckModule

manifest = ModuleManifest(
    id="firewall-check",
    display_name="Firewall Check",
    version="0.1.0",
    scanner_cls=FirewallCheckModule,
    router=router,
)
