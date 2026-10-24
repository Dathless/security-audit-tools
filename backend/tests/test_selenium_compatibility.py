import json
import sqlite3

import httpx
import pytest
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait


def save_snapshot(database, module_id, detail, summary):
    with sqlite3.connect(database) as connection:
        connection.execute(
            "INSERT INTO scans (id,module_id,status,started_at,finished_at,summary_json,partial_result) VALUES (?,?, 'done', ?,?,?,0)",
            ("saved-snapshot", module_id, "2026-01-01 00:00:00", "2026-01-01 00:00:01", json.dumps(summary)),
        )
        connection.execute(
            "INSERT INTO scan_items (scan_id,module_id,whitelist_key,severity,title,detail_json,is_new) VALUES (?,?,?, 'safe',?,?,0)",
            ("saved-snapshot", module_id, "saved-item", "Saved item", json.dumps(detail)),
        )


@pytest.mark.selenium
def test_historical_port_snapshot_keeps_listener_and_note(driver, selenium_database):
    detail = {"port": 8080, "ip": "127.0.0.2", "note": "Legacy scan note", "protocol": "tcp", "pid": None}
    save_snapshot(selenium_database, "port-scanner", detail, {"total_open": 1, "danger": 0, "warning": 0, "safe": 1})
    response = httpx.get("http://127.0.0.1:8000/api/v1/modules/port-scanner/scans/latest", headers={"X-Local-Token": "test-token"})
    assert response.status_code == 200
    assert response.json()["data"]["items"][0]["detail"] == detail
    driver.get("http://127.0.0.1:5173/#/modules/port-scanner")
    wait = WebDriverWait(driver, 10)
    wait.until(lambda d: "8080" in d.find_element(By.TAG_NAME, "table").text)
    table = driver.find_element(By.TAG_NAME, "table").text
    assert "127.0.0.2" in table
    assert "Legacy scan note" in table


@pytest.mark.selenium
def test_outbound_rule_labels_remote_address_neutrally(driver, selenium_database):
    detail = {
        "kind": "rule", "name": "outbound-example", "profiles": ["Public"],
        "direction": "Outbound", "action": "Allow", "protocol": "TCP",
        "local_ports": ["Any"], "remote_ports": ["443"],
        "local_addresses": ["Any"], "remote_addresses": ["203.0.113.10"],
        "program": "Any", "service": "Any", "policy_source": "Local", "reasons": [],
    }
    save_snapshot(selenium_database, "firewall-check", detail, {"total_profiles": 0, "total_rules": 1, "danger": 0, "warning": 0, "safe": 1})
    driver.get("http://127.0.0.1:5173/#/modules/firewall-check")
    WebDriverWait(driver, 10).until(lambda d: "203.0.113.10" in d.find_element(By.TAG_NAME, "table").text)
    assert "Từ xa: 203.0.113.10" in driver.find_element(By.TAG_NAME, "table").text
