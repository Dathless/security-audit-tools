from __future__ import annotations

import json
import subprocess
from types import SimpleNamespace

import pytest

from core.scanner_base import ScanError




def install_snapshot(monkeypatch, snapshot):
    from modules.firewall_check import scanner
    monkeypatch.setattr(scanner.sys, "platform", "win32")
    monkeypatch.setattr(scanner.subprocess, "run", lambda *a, **kw: SimpleNamespace(stdout=json.dumps(snapshot), returncode=0))


async def test_scanner_contract(snapshot, monkeypatch):
    from modules.firewall_check.scanner import FirewallCheckModule
    install_snapshot(monkeypatch, snapshot)
    progress = []
    async def report(current, total, message):
        progress.append((current, total))
    scanner = FirewallCheckModule()
    result = await scanner.run(report)
    assert result.summary == {"total_profiles": 3, "total_rules": 1, "danger": 0, "warning": 1, "safe": 3}
    assert result.module_id == "firewall-check"
    assert not result.partial_result
    rule = result.items[-1]
    assert rule.title == "Ứng dụng thử nghiệm"
    assert rule.detail["reasons"] == ["BROAD_INBOUND_ALLOW"]
    assert rule.detail["guidance"]
    assert scanner.get_whitelist_key(rule) == "rule:rule-1"
    assert progress[-1][0] == progress[-1][1]


@pytest.mark.parametrize("empty_rules", [False, True])
async def test_progress_reports_only_work_already_evaluated(snapshot, monkeypatch, empty_rules):
    from modules.firewall_check.scanner import FirewallCheckModule
    if empty_rules:
        snapshot["rules"] = []
    install_snapshot(monkeypatch, snapshot)
    evaluated = []
    original = FirewallCheckModule._item
    def item(title, *args):
        evaluated.append(title)
        return original(title, *args)
    monkeypatch.setattr(FirewallCheckModule, "_item", staticmethod(item))
    events = []
    async def report(current, total, message):
        events.append((current, total, len(evaluated)))
    await FirewallCheckModule().run(report)
    count = 3 if empty_rules else 4
    assert events == [(0, 0, 0)] + [(index, count, index) for index in range(1, count + 1)]


async def test_collection_failure_never_reports_assessment_progress(monkeypatch):
    from modules.firewall_check.scanner import FirewallCheckModule
    def fail():
        raise ScanError("FIREWALL_TIMEOUT", "timed out")
    monkeypatch.setattr(FirewallCheckModule, "_collect", staticmethod(fail))
    events = []
    async def report(current, total, message):
        events.append((current, total))
    with pytest.raises(ScanError):
        await FirewallCheckModule().run(report)
    assert events == [(0, 0)]


@pytest.mark.parametrize("active,enabled,inbound,outbound,expected,reason", [
    (True, False, "Block", "Allow", "danger", "FIREWALL_DISABLED"),
    (False, False, "Block", "Allow", "warning", "FIREWALL_DISABLED"),
    (True, True, "Allow", "Allow", "danger", "DEFAULT_INBOUND_ALLOW"),
    (False, True, "Allow", "Allow", "warning", "DEFAULT_INBOUND_ALLOW"),
    (True, True, "NotConfigured", "Allow", "warning", "POLICY_UNDETERMINED"),
    (True, True, "Block", "NotConfigured", "warning", "POLICY_UNDETERMINED"),
    (True, True, "Block", "Allow", "safe", None),
])
async def test_profile_classification(snapshot, monkeypatch, active, enabled, inbound, outbound, expected, reason):
    from modules.firewall_check.scanner import FirewallCheckModule
    snapshot["active_profiles"] = ["Public"] if active else []
    snapshot["profiles"][-1].update(enabled=enabled, default_inbound_action=inbound, default_outbound_action=outbound)
    install_snapshot(monkeypatch, snapshot)
    item = (await FirewallCheckModule().run()).items[2]
    assert item.severity == expected
    assert (reason in item.detail["reasons"]) if reason else not item.detail["reasons"]


@pytest.mark.parametrize("changes,expected", [
    ({"action": "Block"}, "safe"), ({"direction": "Outbound"}, "safe"),
    ({"profiles": ["Private"]}, "safe"), ({"local_ports": ["443"]}, "safe"),
    ({"remote_addresses": ["LocalSubnet"]}, "safe"),
    ({"remote_addresses": ["192.168.1.0/24"]}, "safe"),
    ({"protocol": "ICMPv4"}, "safe"), ({"protocol": "UDP"}, "warning"),
    ({"protocol": "6", "remote_addresses": ["::/0"]}, "warning"),
    ({"local_ports": ["0-65535"], "profiles": ["Public"]}, "warning"),
])
async def test_rule_classification(snapshot, monkeypatch, changes, expected):
    from modules.firewall_check.scanner import FirewallCheckModule
    snapshot["rules"][0].update(changes)
    install_snapshot(monkeypatch, snapshot)
    assert (await FirewallCheckModule().run()).items[-1].severity == expected


async def test_multiple_adapters_singleton_rule_and_no_rules(snapshot, monkeypatch):
    from modules.firewall_check.scanner import FirewallCheckModule
    snapshot["active_profiles"] = ["Public", "Private", "Private"]
    snapshot["rules"] = snapshot["rules"][0]
    install_snapshot(monkeypatch, snapshot)
    result = await FirewallCheckModule().run()
    assert [i.detail["active"] for i in result.items[:3]] == [False, True, True]
    snapshot["rules"] = []
    result = await FirewallCheckModule().run()
    assert result.summary["total_rules"] == 0


@pytest.mark.parametrize("change", [
    {"profiles": []}, {"active_profiles": ["Unknown"]}, {"rules": None},
    {"profiles": [{"name": "Public", "enabled": "False"}]},
])
async def test_invalid_snapshot_fails(snapshot, monkeypatch, change):
    from modules.firewall_check.scanner import FirewallCheckModule
    snapshot.update(change)
    install_snapshot(monkeypatch, snapshot)
    with pytest.raises(ScanError) as exc:
        await FirewallCheckModule().run()
    assert exc.value.code == "FIREWALL_INVALID_DATA"


async def test_duplicate_rule_identity_fails(snapshot, monkeypatch):
    from modules.firewall_check.scanner import FirewallCheckModule
    snapshot["rules"].append(dict(snapshot["rules"][0]))
    install_snapshot(monkeypatch, snapshot)
    with pytest.raises(ScanError) as exc:
        await FirewallCheckModule().run()
    assert exc.value.code == "FIREWALL_INVALID_DATA"


@pytest.mark.parametrize("field", ["name", "local_ports", "remote_addresses", "program", "service"])
async def test_missing_rule_evidence_fails(snapshot, monkeypatch, field):
    from modules.firewall_check.scanner import FirewallCheckModule
    del snapshot["rules"][0][field]
    install_snapshot(monkeypatch, snapshot)
    with pytest.raises(ScanError):
        await FirewallCheckModule().run()


@pytest.mark.parametrize("error,code", [
    (PermissionError(), "SCAN_PERMISSION_DENIED"),
    (FileNotFoundError(), "FIREWALL_UNAVAILABLE"),
    (subprocess.TimeoutExpired("powershell", 60), "FIREWALL_TIMEOUT"),
    (subprocess.CalledProcessError(1, "powershell", stderr="FIREWALL_PERMISSION_DENIED"), "SCAN_PERMISSION_DENIED"),
    (subprocess.CalledProcessError(1, "powershell", stderr="FIREWALL_UNAVAILABLE"), "FIREWALL_UNAVAILABLE"),
    (subprocess.CalledProcessError(1, "powershell", stderr="failure"), "FIREWALL_QUERY_FAILED"),
])
async def test_command_failure(monkeypatch, error, code):
    from modules.firewall_check import scanner
    monkeypatch.setattr(scanner.sys, "platform", "win32")
    def fail(*args, **kwargs):
        raise error
    monkeypatch.setattr(scanner.subprocess, "run", fail)
    with pytest.raises(ScanError) as exc:
        await scanner.FirewallCheckModule().run()
    assert exc.value.code == code


async def test_non_windows(monkeypatch):
    from modules.firewall_check import scanner
    monkeypatch.setattr(scanner.sys, "platform", "linux")
    with pytest.raises(ScanError) as exc:
        await scanner.FirewallCheckModule().run()
    assert exc.value.code == "UNSUPPORTED_PLATFORM"


async def test_command_is_bounded_and_json_is_validated(snapshot, monkeypatch):
    from modules.firewall_check import scanner
    monkeypatch.setattr(scanner.sys, "platform", "win32")
    calls = []
    def run(args, **kwargs):
        calls.append((args, kwargs))
        return SimpleNamespace(stdout="not json")
    monkeypatch.setattr(scanner.subprocess, "run", run)
    with pytest.raises(ScanError) as exc:
        await scanner.FirewallCheckModule().run()
    assert exc.value.code == "FIREWALL_INVALID_DATA"
    args, kwargs = calls[0]
    assert "-NonInteractive" in args and "-NoProfile" in args
    assert "-Command" in args and "-ExecutionPolicy" not in args
    assert kwargs["timeout"] == 60 and kwargs["check"] is True
    assert not kwargs.get("shell", False)
    assert kwargs["creationflags"] != 0
