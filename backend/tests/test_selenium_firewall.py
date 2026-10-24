import pytest
import httpx
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import Select, WebDriverWait


@pytest.mark.selenium
class TestFirewallCheck:
    def test_socket_disconnect_unblocks_retry(self, driver):
        driver.get("http://127.0.0.1:5173/#/modules/firewall-check")
        driver.execute_script("window.WebSocket = class extends WebSocket { constructor(...args) { super(...args); if (this.url.includes('/ws/scan/')) window.__scanSocket = this; } };")
        wait = WebDriverWait(driver, 15)
        wait.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(., 'Kiểm tra firewall')]"))).click()
        wait.until(lambda d: d.execute_script("return window.__scanSocket?.readyState === 1"))
        driver.execute_script("window.__scanSocket.close();")
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "[data-testid='error-banner']")))
        wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "[data-testid='scan-button']")))

    def test_leaving_running_scan_does_not_leave_global_busy(self, driver):
        driver.get("http://127.0.0.1:5173/#/modules/firewall-check")
        wait = WebDriverWait(driver, 75)
        wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "[data-testid='scan-button']"))).click()
        def running():
            return httpx.get("http://127.0.0.1:8000/api/v1/health", headers={"X-Local-Token": "test-token"}, timeout=2).json()["data"]["running_scans"]
        wait.until(lambda _: running() > 0)
        driver.find_element(By.CSS_SELECTOR, "[data-testid='nav-item-settings']").click()
        wait.until(lambda _: running() == 0)
        driver.find_element(By.CSS_SELECTOR, "[data-testid='nav-item-firewall-check']").click()
        wait.until(EC.text_to_be_present_in_element((By.CSS_SELECTOR, "[data-testid='scan-button']"), "Quét ngay"))
        assert "Đang quét" not in driver.find_element(By.CSS_SELECTOR, "[data-testid='scan-button']").text

    def test_firewall_navigation_is_active(self, driver):
        driver.get("http://127.0.0.1:5173/#/modules/port-scanner")
        nav = WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.CSS_SELECTOR, "[data-testid='nav-item-firewall-check']")))
        assert nav.get_attribute("data-status") == "active"
        nav.click()
        WebDriverWait(driver, 10).until(EC.text_to_be_present_in_element((By.CSS_SELECTOR, "[data-testid='page-title']"), "Firewall Check"))

    def test_scan_profiles_rules_guidance_and_history(self, driver):
        driver.get("http://127.0.0.1:5173/#/modules/firewall-check")
        wait = WebDriverWait(driver, 75)
        wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "[data-testid='scan-button']"))).click()
        wait.until(EC.any_of(
            EC.presence_of_element_located((By.CSS_SELECTOR, "[data-testid='firewall-results']")),
            EC.presence_of_element_located((By.CSS_SELECTOR, "[data-testid='error-banner']")),
        ))
        errors = driver.find_elements(By.CSS_SELECTOR, "[data-testid='error-banner']")
        assert not errors, " | ".join(e.text for e in errors)
        cards = driver.find_elements(By.CSS_SELECTOR, "[data-testid='firewall-profile']")
        assert len(cards) == 3
        assert {c.get_attribute("data-profile") for c in cards} == {"Domain", "Private", "Public"}
        assert "chưa kiểm chứng" in driver.find_element(By.CSS_SELECTOR, "[data-testid='firewall-limits']").text.lower()
        searches = driver.find_elements(By.CSS_SELECTOR, "input[type='search']")
        assert len(searches) == 1
        searches[0].send_keys("no-such-rule-xyz")
        assert "Không có rule" in driver.find_element(By.CSS_SELECTOR, "[data-testid='firewall-results']").text
        searches[0].clear()
        driver.get("http://127.0.0.1:5173/#/scan-history")
        select = wait.until(EC.presence_of_element_located((By.ID, "history-module")))
        Select(select).select_by_value("firewall-check")
        wait.until(lambda d: "profiles / rules" in d.find_element(By.TAG_NAME, "table").text.lower())
        action = wait.until(EC.element_to_be_clickable((By.XPATH, "//table//button[contains(., 'Mở module')]")))
        action.click()
        wait.until(EC.url_contains("/modules/firewall-check"))
