import pytest


@pytest.fixture
def snapshot():
    return {
        "profiles": [
            {"name": name, "enabled": True, "default_inbound_action": "Block", "default_outbound_action": "Allow"}
            for name in ("Domain", "Private", "Public")
        ],
        "active_profiles": ["Public"],
        "rules": [{
            "name": "rule-1", "display_name": "Ứng dụng thử nghiệm", "profiles": ["Any"],
            "direction": "Inbound", "action": "Allow", "protocol": "TCP",
            "local_ports": ["Any"], "remote_ports": ["Any"],
            "local_addresses": ["Any"], "remote_addresses": ["Any"],
            "program": "Any", "service": "Any", "policy_source": "Local",
        }],
    }



@pytest.fixture
def mock_firewall(snapshot, monkeypatch):
    from core.config import config, ModuleSettings
    from modules.firewall_check.scanner import FirewallCheckModule, FirewallSnapshot
    monkeypatch.setitem(config.settings.modules, "firewall-check", ModuleSettings(enabled=True))
    monkeypatch.setattr(FirewallCheckModule, "_collect", staticmethod(lambda: FirewallSnapshot.model_validate(snapshot)))
    return snapshot
