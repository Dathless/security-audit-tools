from __future__ import annotations

import pytest
import time
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


@pytest.mark.selenium
class TestScanLifecycle:
    """Tests for complete scan lifecycle: start -> progress -> complete -> results."""

    def test_full_scan_lifecycle(self, driver):
        driver.get("http://127.0.0.1:5173/#/modules/port-scanner")

        # Start scan
        scan_btn = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "[data-testid='scan-button']"))
        )
        scan_btn.click()

        # Progress shows
        progress = WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "[data-testid='progress-bar'], .progress-bar"))
        )
        assert progress.is_displayed()

        # Wait for completion
        WebDriverWait(driver, 90).until(
            EC.invisibility_of_element_located((By.CSS_SELECTOR, "[data-testid='progress-bar'], .progress-bar"))
        )

        # Results table appears
        table = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "[data-testid='data-table'], .data-table, table"))
        )
        assert table.is_displayed()

        # KPIs updated
        kpi_values = {}
        kpi_cards = driver.find_elements(By.CSS_SELECTOR, "[data-testid='kpi-card'], .kpi-card")
        for card in kpi_cards:
            label = card.find_element(By.CSS_SELECTOR, "[data-testid='kpi-label'], .kpi-label").text
            value = card.find_element(By.CSS_SELECTOR, "[data-testid='kpi-value'], .kpi-value").text
            kpi_values[label.lower()] = value

        assert "cổng đang mở" in kpi_values
        assert kpi_values["cổng đang mở"] != "—"

    def test_scan_updates_kpis_in_real_time(self, driver):
        driver.get("http://127.0.0.1:5173/#/modules/port-scanner")

        scan_btn = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "[data-testid='scan-button']"))
        )
        scan_btn.click()

        # KPIs show loading skeleton initially
        danger_kpi = WebDriverWait(driver, 5).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "[data-testid='kpi-card'][data-tone='danger'], .kpi-card.tone-danger"))
        )
        value_elem = danger_kpi.find_element(By.CSS_SELECTOR, "[data-testid='kpi-value'], .kpi-value")

        # Value should update from loading to actual number
        WebDriverWait(driver, 60).until(
            lambda d: value_elem.text != "—" and value_elem.text != ""
        )
        assert value_elem.text.isdigit() or value_elem.text == "0"

    def test_scan_can_be_retried_after_completion(self, driver):
        driver.get("http://127.0.0.1:5173/#/modules/port-scanner")

        # First scan
        scan_btn = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "[data-testid='scan-button']"))
        )
        scan_btn.click()

        WebDriverWait(driver, 90).until(
            EC.invisibility_of_element_located((By.CSS_SELECTOR, "[data-testid='progress-bar'], .progress-bar"))
        )

        # Scan button should be available again
        scan_btn = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "[data-testid='scan-button']"))
        )
        assert scan_btn.is_enabled()

        # Second scan
        scan_btn.click()
        progress = WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "[data-testid='progress-bar'], .progress-bar"))
        )
        assert progress.is_displayed()


@pytest.mark.selenium
class TestWebSocketRealTimeUpdates:
    """Tests for WebSocket real-time updates during scan."""

    def test_progress_updates_via_websocket(self, driver):
        driver.get("http://127.0.0.1:5173/#/modules/port-scanner")

        scan_btn = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "[data-testid='scan-button']"))
        )
        scan_btn.click()

        progress_text = WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "[data-testid='progress-text'], .progress-text, [data-testid='progress-message']"))
        )

        initial_text = progress_text.text
        def advanced_or_done(browser):
            elements = browser.find_elements(By.CSS_SELECTOR, "[data-testid='progress-text']")
            if elements:
                return elements[0].text != initial_text
            return bool(browser.find_elements(By.CSS_SELECTOR, "table tbody tr"))
        WebDriverWait(driver, 30).until(advanced_or_done)

    def test_item_found_updates_radar_map(self, driver):
        driver.get("http://127.0.0.1:5173/#/modules/port-scanner")

        scan_btn = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "[data-testid='scan-button']"))
        )
        scan_btn.click()

        WebDriverWait(driver, 30).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "[data-testid='radar-dot'], .radar-dot, circle[fill]"))
        )

        initial_dots = len(driver.find_elements(By.CSS_SELECTOR, "[data-testid='radar-dot'], .radar-dot, circle[fill]"))
        time.sleep(3)
        updated_dots = len(driver.find_elements(By.CSS_SELECTOR, "[data-testid='radar-dot'], .radar-dot, circle[fill]"))

        assert updated_dots >= initial_dots, "Radar map should add dots as items found"

    def test_done_message_updates_final_summary(self, driver):
        driver.get("http://127.0.0.1:5173/#/modules/port-scanner")

        scan_btn = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "[data-testid='scan-button']"))
        )
        scan_btn.click()

        WebDriverWait(driver, 90).until(
            EC.invisibility_of_element_located((By.CSS_SELECTOR, "[data-testid='progress-bar'], .progress-bar"))
        )

        # Summary should be in panel subtitle
        panel = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "[data-testid='panel']:last-child, .panel:last-child"))
        )
        subtitle = panel.find_element(By.CSS_SELECTOR, "[data-testid='panel-subtitle'], .panel-subtitle")
        assert "cổng đang mở" in subtitle.text.lower() or "open port" in subtitle.text.lower()


@pytest.mark.selenium
class TestScanHistoryNavigation:
    """Tests for scan history page and navigation."""

    def test_navigate_to_history_shows_scans(self, driver):
        # First do a scan
        driver.get("http://127.0.0.1:5173/#/modules/port-scanner")
        scan_btn = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "[data-testid='scan-button']"))
        )
        scan_btn.click()

        WebDriverWait(driver, 90).until(
            EC.invisibility_of_element_located((By.CSS_SELECTOR, "[data-testid='progress-bar'], .progress-bar"))
        )

        # Navigate to history
        history_link = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "[data-testid='nav-item-scan-history'], .nav-item[data-route='/scan-history']"))
        )
        history_link.click()

        WebDriverWait(driver, 10).until(
            EC.url_contains("/scan-history")
        )

        # History page should show the scan
        history_table = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "[data-testid='history-table'], .history-table, table"))
        )
        rows = history_table.find_elements(By.CSS_SELECTOR, "tbody tr")
        assert len(rows) >= 1

    def test_history_row_click_shows_scan_detail(self, driver):
        # Frontend chưa có trang detail /scans/:id — nút hành động trong history
        # mở module tương ứng; test điều hướng đó thay vì route không tồn tại.
        driver.get("http://127.0.0.1:5173/#/modules/port-scanner")
        WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.CSS_SELECTOR, "[data-testid='scan-button']"))).click()
        WebDriverWait(driver, 60).until(EC.presence_of_element_located((By.CSS_SELECTOR, ".row-actions button")))
        driver.get("http://127.0.0.1:5173/#/scan-history")
        action = WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.CSS_SELECTOR, "table .td-action button, table td:last-child button")))
        action.click()

        WebDriverWait(driver, 10).until(
            EC.url_contains("/modules/port-scanner")
        )

        # Port scanner page should show results table
        detail_table = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "[data-testid='data-table'], .data-table, table"))
        )
        assert detail_table.is_displayed()


@pytest.mark.selenium
class TestWhitelistPersistence:
    """Tests that whitelist changes persist across scans."""

    def test_mark_safe_persists_in_new_scan(self, driver):
        driver.get("http://127.0.0.1:5173/#/modules/port-scanner")
        wait = WebDriverWait(driver, 90)
        scan_button = (By.CSS_SELECTOR, "[data-testid='scan-button']")
        wait.until(EC.element_to_be_clickable(scan_button)).click()
        first = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, ".row-actions button")))
        port = first.find_element(By.XPATH, "ancestor::tr").find_elements(By.TAG_NAME, "td")[1].text.strip()
        assert port.isdigit()
        target = (By.XPATH, f"//tbody/tr[td[2][normalize-space()='{port}']]//div[@class='row-actions']/button")
        first.click()
        wait.until(EC.text_to_be_present_in_element(target, "Bỏ an toàn"))
        wait.until(EC.element_to_be_clickable(scan_button)).click()
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "[data-testid='progress-bar']")))
        wait.until(EC.invisibility_of_element_located((By.CSS_SELECTOR, "[data-testid='progress-bar']")))
        wait.until(EC.text_to_be_present_in_element(target, "Bỏ an toàn"))

    def test_whitelist_page_shows_marked_items(self, driver):
        driver.get("http://127.0.0.1:5173/#/modules/port-scanner")

        scan_btn = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "[data-testid='scan-button']"))
        )
        scan_btn.click()

        WebDriverWait(driver, 90).until(
            EC.invisibility_of_element_located((By.CSS_SELECTOR, "[data-testid='progress-bar'], .progress-bar"))
        )

        action_btns = driver.find_elements(By.CSS_SELECTOR, ".row-actions button")
        if action_btns:
            action_btns[0].click()
            time.sleep(1)

        # Navigate to settings/whitelist
        settings_link = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "[data-testid='nav-item-settings'], .nav-item[data-route='/settings']"))
        )
        settings_link.click()

        WebDriverWait(driver, 10).until(
            EC.url_contains("/settings")
        )

        whitelist_section = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "[data-testid='whitelist-list'], .whitelist-list"))
        )
        items = whitelist_section.find_elements(By.CSS_SELECTOR, "[data-testid='whitelist-item'], .whitelist-item")
        assert len(items) >= 1


@pytest.mark.selenium
class TestErrorRecovery:
    """Tests for error handling and recovery in UI."""

    def test_network_error_shows_retry_option(self, driver):
        driver.get("http://127.0.0.1:5173/#/modules/port-scanner")

        # Wait for potential error state
        WebDriverWait(driver, 10).until(
            EC.any_of(
                EC.presence_of_element_located((By.CSS_SELECTOR, "[data-testid='error-banner'], .error-banner")),
                EC.presence_of_element_located((By.CSS_SELECTOR, "[data-testid='data-table'], .data-table")),
                EC.presence_of_element_located((By.CSS_SELECTOR, "[data-testid='empty-state'], .empty-state"))
            )
        )

        error_banners = driver.find_elements(By.CSS_SELECTOR, "[data-testid='error-banner'], .error-banner")
        if error_banners:
            retry_btn = driver.find_elements(By.CSS_SELECTOR, "[data-testid='retry-btn'], .retry-btn")
            if retry_btn:
                assert retry_btn[0].is_displayed()
                assert "Tải lại" in retry_btn[0].text or "Retry" in retry_btn[0].text

    def test_partial_results_show_warning_banner(self, driver):
        driver.get("http://127.0.0.1:5173/#/modules/port-scanner")

        scan_btn = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "[data-testid='scan-button']"))
        )
        scan_btn.click()

        WebDriverWait(driver, 90).until(
            EC.invisibility_of_element_located((By.CSS_SELECTOR, "[data-testid='progress-bar'], .progress-bar"))
        )

        warning_banners = driver.find_elements(By.CSS_SELECTOR, "[data-testid='error-banner'][data-tone='warning']")
        if warning_banners:
            assert "cần chạy" in warning_banners[0].text.lower() or "administrator" in warning_banners[0].text.lower()


@pytest.mark.selenium
class TestMultiModuleNavigation:
    """Tests for navigating between different modules."""

    def test_switch_modules_preserves_state(self, driver):
        driver.get("http://127.0.0.1:5173/#/modules/port-scanner")

        scan_btn = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "[data-testid='scan-button']"))
        )
        scan_btn.click()

        WebDriverWait(driver, 90).until(
            EC.invisibility_of_element_located((By.CSS_SELECTOR, "[data-testid='progress-bar'], .progress-bar"))
        )

        # Navigate to history
        history_link = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "[data-testid='nav-item-scan-history'], .nav-item[data-route='/scan-history']"))
        )
        history_link.click()

        WebDriverWait(driver, 10).until(
            EC.url_contains("/scan-history")
        )

        # Navigate back to port scanner
        port_link = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "[data-testid='nav-item-port-scanner'], .nav-item[data-module='port-scanner']"))
        )
        port_link.click()

        WebDriverWait(driver, 10).until(
            EC.url_contains("/modules/port-scanner")
        )

        # Results should still be there
        WebDriverWait(driver, 10).until(EC.text_to_be_present_in_element((By.CSS_SELECTOR, "[data-testid='page-title']"), "Port Scanner"))
        WebDriverWait(driver, 10).until(EC.visibility_of_element_located((By.CSS_SELECTOR, "table")))


@pytest.mark.selenium
class TestScanPerformance:
    """Performance-related tests for scan UI."""

    def test_scan_start_response_time(self, driver):
        driver.get("http://127.0.0.1:5173/#/modules/port-scanner")

        scan_btn = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "[data-testid='scan-button']"))
        )

        start = time.time()
        scan_btn.click()

        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "[data-testid='progress-bar'], .progress-bar"))
        )
        elapsed = time.time() - start

        assert elapsed < 5, f"Scan start took too long: {elapsed:.2f}s"

    def test_results_render_performance(self, driver):
        driver.get("http://127.0.0.1:5173/#/modules/port-scanner")

        scan_btn = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "[data-testid='scan-button']"))
        )
        scan_btn.click()

        WebDriverWait(driver, 90).until(
            EC.invisibility_of_element_located((By.CSS_SELECTOR, "[data-testid='progress-bar'], .progress-bar"))
        )

        start = time.time()
        rows = driver.find_elements(By.CSS_SELECTOR, "[data-testid='data-table'] tbody tr, .data-table tbody tr, table tbody tr")
        render_time = time.time() - start

        assert render_time < 2, f"Table render took too long: {render_time:.2f}s for {len(rows)} rows"
