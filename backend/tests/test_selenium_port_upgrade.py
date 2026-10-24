import json
import sqlite3

import pytest
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

pytestmark = pytest.mark.selenium


def seed_endpoints(database, running=False):
    summary = {"identity_version": 2, "assessment_version": 2, "total_open": 2, "total_endpoints": 2,
               "danger": 1, "warning": 1, "safe": 0, "unique_ports": 1, "unique_processes": 1}
    with sqlite3.connect(database) as connection:
        connection.execute("INSERT INTO scans (id,module_id,status,started_at,summary_json,partial_result) VALUES ('seed-v2','port-scanner',?,?,?,0)",
                           ("running" if running else "done", "2026-10-24 00:00:00", json.dumps(summary)))
        for protocol, address, severity in [("tcp", "0.0.0.0", "danger"), ("udp", "127.0.0.1", "warning")]:
            detail = {"identity_version": 2, "assessment_version": 2, "protocol": protocol, "family": "ipv4",
                      "listener": address, "port": 4444, "process_name": "demo.exe", "pid": 321,
                      "owners": [{"pid": 321, "name": "demo.exe", "exe": "C:\\Demo\\demo.exe", "username": "DEMO\\user", "status": {"exe": "ok", "username": "ok"}}],
                      "reasons": ["PORT_IN_RISKY_LIST"], "guidance": ["Kiểm tra nhu cầu sử dụng"], "change_type": "initial"}
            key = json.dumps(["endpoint-v2", protocol, "ipv4", address, 4444], separators=(",", ":"))
            connection.execute("INSERT INTO scan_items (scan_id,module_id,whitelist_key,severity,title,detail_json,is_new) VALUES ('seed-v2','port-scanner',?,?,?,?,0)",
                               (key, severity, f"{protocol} endpoint", json.dumps(detail)))


def test_same_port_protocols_are_separate_endpoint_rows(driver, selenium_database):
    seed_endpoints(selenium_database)
    driver.get("http://127.0.0.1:5173/#/modules/port-scanner")
    wait = WebDriverWait(driver, 10)
    wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "table tbody tr")))
    rows = driver.find_elements(By.CSS_SELECTOR, "table tbody tr")
    assert len(rows) == 2
    assert "C:\\Demo\\demo.exe" in driver.find_element(By.TAG_NAME, "table").text


def test_review_preserves_risk_kpi_and_can_be_revoked(driver, selenium_database):
    seed_endpoints(selenium_database)
    driver.get("http://127.0.0.1:5173/#/modules/port-scanner")
    wait = WebDriverWait(driver, 10)
    first = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "[data-testid='review-endpoint-btn']")))
    first.click()
    wait.until(EC.text_to_be_present_in_element((By.TAG_NAME, "table"), "Hủy xác nhận"))
    danger = driver.find_element(By.CSS_SELECTOR, "[data-testid='kpi-card'][data-tone='danger'] [data-testid='kpi-value']")
    assert danger.text == "1"
    driver.find_element(By.XPATH, "//table//button[contains(.,'Hủy xác nhận')]").click()
    wait.until(lambda d: "Hủy xác nhận" not in d.find_element(By.TAG_NAME, "table").text)


def test_running_scan_resumes_and_disconnect_shows_recovery(driver, selenium_database):
    driver.get("http://127.0.0.1:5173/#/settings")
    WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.CSS_SELECTOR, "[data-testid='page-title']")))
    seed_endpoints(selenium_database, running=True)
    driver.execute_script("window.WebSocket = class extends WebSocket { constructor(...args) { super(...args); if (this.url.includes('/ws/scan/')) window.__portSocket=this; } };")
    try:
        driver.find_element(By.CSS_SELECTOR, "[data-testid='nav-item-port-scanner']").click()
        wait = WebDriverWait(driver, 10)
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "[data-testid='progress-bar']")))
        wait.until(lambda d: d.execute_script("return window.__portSocket?.readyState === 1"))
        driver.execute_script("window.__portSocket.close()")
        wait.until(EC.text_to_be_present_in_element((By.CSS_SELECTOR, "[data-testid='error-banner']"), "Mất kết nối"))
        wait.until(EC.invisibility_of_element_located((By.CSS_SELECTOR, "[data-testid='progress-bar']")))
    finally:
        with sqlite3.connect(selenium_database) as connection:
            connection.execute("UPDATE scans SET status='error' WHERE id='seed-v2'")


@pytest.mark.parametrize("failed", [False, True])
def test_delayed_review_cannot_replace_newer_completed_scan(driver, selenium_database, failed):
    seed_endpoints(selenium_database)
    driver.get("http://127.0.0.1:5173/#/modules/port-scanner")
    wait = WebDriverWait(driver, 15)
    button = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "[data-testid='review-endpoint-btn']")))
    driver.execute_script("""
        const failed = arguments[0];
        const original = window.fetch;
        window.__scanGets = [];
        window.fetch = async (url, init) => {
            if (String(url).includes('/port-scanner/scans/')) window.__scanGets.push(String(url));
            const response = await original(url, init);
            if (String(url).endsWith('/port-scanner/reviews') && init?.method === 'POST') {
                window.__reviewReady = true;
                await new Promise(resolve => window.__releaseReview = resolve);
                if (failed) return new Response(JSON.stringify({success:false,error:{code:'DELAYED_REVIEW_ERROR',message:'Old review failed'}}), {status:500});
            }
            if (String(url).endsWith('/port-scanner/scan') && init?.method === 'POST') {
                window.__newScanId = (await response.clone().json()).data.scan_id;
            }
            return response;
        };
    """, failed)
    button.click()
    wait.until(lambda d: d.execute_script("return window.__reviewReady === true"))
    driver.find_element(By.CSS_SELECTOR, "[data-testid='scan-button']").click()
    wait.until(lambda d: d.execute_script("return !!window.__newScanId && window.__scanGets.some(url => url.endsWith(window.__newScanId))"))
    wait.until(EC.invisibility_of_element_located((By.CSS_SELECTOR, "[data-testid='progress-bar']")))
    driver.execute_async_script("const done = arguments[0]; window.__releaseReview(); setTimeout(done, 300);")
    assert not driver.execute_script("return window.__scanGets.some(url => url.endsWith('/seed-v2'))")
    assert not driver.find_elements(By.CSS_SELECTOR, "[data-testid='error-banner']")


def test_owner_metadata_failure_statuses_are_visible(driver, selenium_database):
    seed_endpoints(selenium_database)
    with sqlite3.connect(selenium_database) as connection:
        for item_id, raw in connection.execute("SELECT id,detail_json FROM scan_items").fetchall():
            detail = json.loads(raw)
            detail["owners"][0].update(exe=None, username=None)
            detail["owners"][0]["status"].update(exe="access_denied" if detail["protocol"] == "tcp" else "gone", username="unknown")
            connection.execute("UPDATE scan_items SET detail_json=? WHERE id=?", (json.dumps(detail), item_id))
    driver.get("http://127.0.0.1:5173/#/modules/port-scanner")
    table = WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.TAG_NAME, "table")))
    assert "Thiếu quyền" in table.text
    assert "Đã thoát" in table.text
    assert "Chưa xác định" in table.text


def test_history_uses_endpoint_and_no_finding_labels(driver, selenium_database):
    seed_endpoints(selenium_database)
    driver.get("http://127.0.0.1:5173/#/scan-history")
    table = WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.TAG_NAME, "table")))
    headers = [cell.text.lower() for cell in table.find_elements(By.TAG_NAME, "th")]
    assert "endpoint" in headers
    assert "ưu tiên cao" in headers
    assert "không có phát hiện" in headers


def test_stale_sidebar_initialization_does_not_restore_reviewed_badge(driver, selenium_database):
    seed_endpoints(selenium_database)
    driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {"source": """
        const original = window.fetch;
        window.fetch = async (url, init) => {
            const response = await original(url, init);
            if (String(url).endsWith('/api/v1/modules')) {
                window.__modulesReady = true;
                await new Promise(resolve => window.__releaseModules = resolve);
            }
            return response;
        };
    """})
    driver.get("http://127.0.0.1:5173/#/modules/port-scanner")
    wait = WebDriverWait(driver, 10)
    wait.until(lambda d: d.execute_script("return window.__modulesReady === true"))
    for count in (1, 2):
        button = wait.until(EC.element_to_be_clickable((By.XPATH, "//table//button[contains(.,'Xác nhận đã xem')]")))
        button.click()
        wait.until(lambda d: len(d.find_elements(By.XPATH, "//table//button[contains(.,'Hủy xác nhận')]")) == count)
    driver.execute_async_script("const done=arguments[0]; window.__releaseModules(); setTimeout(done,300);")
    assert not driver.find_elements(By.CSS_SELECTOR, "[data-testid='nav-item-port-scanner'] .nav-item-badge")


def test_settings_revocation_updates_sidebar_attention_count(driver, selenium_database):
    seed_endpoints(selenium_database)
    driver.get("http://127.0.0.1:5173/#/modules/port-scanner")
    wait = WebDriverWait(driver, 10)
    for count in (1, 2):
        wait.until(EC.element_to_be_clickable((By.XPATH, "//table//button[contains(.,'Xác nhận đã xem')]"))).click()
        wait.until(lambda d: len(d.find_elements(By.XPATH, "//table//button[contains(.,'Hủy xác nhận')]")) == count)
    driver.find_element(By.CSS_SELECTOR, "[data-testid='nav-item-settings']").click()
    wait.until(EC.element_to_be_clickable((By.XPATH, "//*[@data-testid='port-reviews-list']//button[contains(.,'Hủy xác nhận')]"))).click()
    wait.until(EC.text_to_be_present_in_element((By.CSS_SELECTOR, "[data-testid='nav-item-port-scanner']"), "1"))
