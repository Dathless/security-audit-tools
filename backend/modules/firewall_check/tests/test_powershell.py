import json
import subprocess
import sys
from pathlib import Path

import pytest


@pytest.mark.skipif(sys.platform != "win32", reason="Windows PowerShell collector")
def test_empty_rule_store_does_not_query_unassociated_filters():
    # Exercise the real script with deterministic cmdlets, never the host firewall.
    commands = """
function Get-NetFirewallProfile {
    foreach ($profileName in @('Domain', 'Private', 'Public')) {
        [pscustomobject]@{Name=$profileName; Enabled='True'; DefaultInboundAction='Block'; DefaultOutboundAction='Allow'}
    }
}
function Get-NetConnectionProfile {}
function Get-NetFirewallRule {}
function Get-NetFirewallPortFilter { throw 'Unexpected unassociated filter query' }
function Get-NetFirewallAddressFilter { throw 'Unexpected unassociated filter query' }
function Get-NetFirewallApplicationFilter { throw 'Unexpected unassociated filter query' }
function Get-NetFirewallServiceFilter { throw 'Unexpected unassociated filter query' }
"""
    script = Path(__file__).parents[1] / "collect.ps1"
    result = subprocess.run(
        ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", commands + script.read_text(encoding="utf-8")],
        capture_output=True, text=True, encoding="utf-8", timeout=30,
        creationflags=subprocess.CREATE_NO_WINDOW,
    )
    assert result.returncode == 0, result.stderr
    data = json.loads(result.stdout)
    assert len(data["profiles"]) == 3
    assert data["active_profiles"] == []
    assert data["rules"] == []
