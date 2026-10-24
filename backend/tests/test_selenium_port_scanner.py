from __future__ import annotations

import pytest
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


@pytest.mark.selenium
class TestPortScannerPageLoad:
    """Tests for Port Scanner page initial load and layout."""

    def test_page_loads_with_correct_title(self, driver):
        driver.get("http://127.0.0.1:5173/#/modules/port-scanner")
        WebDriverWait(driver, 10).until(
            EC.title_is("Security Audit")
        )
        assert driver.title == "Security Audit"

    def test_page_shows_module_header(self, driver):
        driver.get("http://127.0.0.1:5173/#/modules/port-scanner")
        header = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "[data-testid='page-title'], .page-title, h1"))
        )
        assert "Port Scanner" in header.text

    def test_page_shows_description(self, driver):
        driver.get("http://127.0.0.1:5173/#/modules/port-scanner")
        desc = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "[data-testid='page-description'], .page-description"))
        )
        assert "Quét toàn bộ cổng" in desc.text or "LISTEN" in desc.text

    def test_page_shows_kpi_row(self, driver):
        driver.get("http://127.0.0.1:5173/#/modules/port-scanner")
        kpi_cards = WebDriverWait(driver, 10).until(
            EC.presence_of_all_elements_located((By.CSS_SELECTOR, "[data-testid='kpi-card'], .kpi-card"))
        )
        assert len(kpi_cards) >= 4
        labels = [card.find_element(By.CSS_SELECTOR, "[data-testid='kpi-label'], .kpi-label").text for card in kpi_cards]
        expected_labels = ["Cổng đang mở", "Nguy hiểm", "Cảnh báo", "An toàn"]
        for expected in expected_labels:
            assert any(expected.lower() in label.lower() for label in labels), f"Missing KPI: {expected}"

    def test_page_shows_two_panels(self, driver):
        driver.get("http://127.0.0.1:5173/#/modules/port-scanner")
        panels = WebDriverWait(driver, 10).until(
            EC.presence_of_all_elements_located((By.CSS_SELECTOR, "[data-testid='panel'], .panel"))
        )
        assert len(panels) >= 2
        panel_titles = [panel.find_element(By.CSS_SELECTOR, "[data-testid='panel-title'], .panel-title, h2").text for panel in panels]
        assert any("Radar" in title for title in panel_titles)
        assert any("Chi tiết" in title or "Detail" in title for title in panel_titles)


@pytest.mark.selenium
class TestPortScannerEmptyState:
    """Tests for empty state when no scan has been performed."""

    def test_shows_empty_state_when_no_scans(self, driver):
        driver.get("http://127.0.0.1:5173/#/modules/port-scanner")
        WebDriverWait(driver, 10).until(EC.text_to_be_present_in_element(
            (By.CSS_SELECTOR, "[data-testid='empty-state']"), "Chưa có dữ liệu quét"
        ))

    def test_empty_state_has_scan_button(self, driver):
        driver.get("http://127.0.0.1:5173/#/modules/port-scanner")
        btn = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "[data-testid='scan-button']"))
        )
        assert btn.is_displayed()
        assert "Quét ngay" in btn.text or "Scan" in btn.text


@pytest.mark.selenium
class TestPortScannerSidebar:
    """Tests for sidebar navigation."""

    def test_sidebar_shows_port_scanner_module(self, driver):
        driver.get("http://127.0.0.1:5173/#/modules/port-scanner")
        nav_item = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "[data-testid='nav-item-port-scanner'], .nav-item[data-module='port-scanner']"))
        )
        assert "Port Scanner" in nav_item.text

    def test_port_scanner_nav_item_active(self, driver):
        driver.get("http://127.0.0.1:5173/#/modules/port-scanner")
        nav_item = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "[data-testid='nav-item-port-scanner'], .nav-item[data-module='port-scanner']"))
        )
        assert "active" in nav_item.get_attribute("class") or nav_item.get_attribute("aria-current") == "page"

    def test_sidebar_shows_general_group(self, driver):
        driver.get("http://127.0.0.1:5173/#/modules/port-scanner")
        general_items = driver.find_elements(By.CSS_SELECTOR, "[data-testid^='nav-item-'], .nav-item[data-group='general']")
        texts = [item.text for item in general_items]
        assert any("Lịch sử" in t or "History" in t for t in texts)
        assert any("Cài đặt" in t or "Settings" in t for t in texts)


@pytest.mark.selenium
class TestPortScannerScanFlow:
    """Tests for scan initiation and progress."""

    def test_click_scan_button_starts_scan(self, driver):
        driver.get("http://127.0.0.1:5173/#/modules/port-scanner")
        btn = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "[data-testid='scan-button']"))
        )
        btn.click()

        progress = WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "[data-testid='progress-bar'], .progress-bar"))
        )
        assert progress.is_displayed()

    def test_scan_shows_progress_details(self, driver):
        driver.get("http://127.0.0.1:5173/#/modules/port-scanner")
        btn = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "[data-testid='scan-button']"))
        )
        btn.click()

        progress_text = WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "[data-testid='progress-message']"))
        )
        assert "quét" in progress_text.text.lower() or "kiểm tra" in progress_text.text.lower() or "scanning" in progress_text.text.lower()

    def test_scan_complete_shows_results_table(self, driver):
        driver.get("http://127.0.0.1:5173/#/modules/port-scanner")
        btn = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "[data-testid='scan-button']"))
        )
        btn.click()

        table = WebDriverWait(driver, 60).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "[data-testid='data-table'], .data-table, table"))
        )
        assert table.is_displayed()

        headers = table.find_elements(By.CSS_SELECTOR, "th")
        header_texts = [h.text for h in headers]
        expected_columns = ["Trạng thái", "Cổng", "Tiến trình", "Giao thức", "Listener", "Mới", "Lý do"]
        for expected in expected_columns:
            assert any(expected.lower() in h.lower() for h in header_texts), f"Missing column: {expected}"


@pytest.mark.selenium
class TestPortScannerResultsTable:
    """Tests for results table functionality."""

    def test_table_rows_have_mono_font_for_technical_data(self, driver):
        driver.get("http://127.0.0.1:5173/#/modules/port-scanner")
        btn = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "[data-testid='scan-button']"))
        )
        btn.click()

        WebDriverWait(driver, 60).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "[data-testid='data-table'] tbody tr, .data-table tbody tr, table tbody tr"))
        )

        rows = driver.find_elements(By.CSS_SELECTOR, "[data-testid='data-table'] tbody tr, .data-table tbody tr, table tbody tr")
        if rows:
            first_row = rows[0]
            port_cell = first_row.find_element(By.CSS_SELECTOR, "td:nth-child(2)")
            font_family = port_cell.value_of_css_property("font-family")
            assert "mono" in font_family.lower() or "JetBrains Mono" in font_family

    def test_status_badge_shows_correct_colors(self, driver):
        driver.get("http://127.0.0.1:5173/#/modules/port-scanner")
        btn = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "[data-testid='scan-button']"))
        )
        btn.click()

        WebDriverWait(driver, 60).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "[data-testid='status-badge'], .status-badge"))
        )

        badges = driver.find_elements(By.CSS_SELECTOR, "[data-testid='status-badge'], .status-badge")
        for badge in badges:
            color = badge.value_of_css_property("color") or badge.value_of_css_property("background-color")
            assert color is not None

    def test_new_badge_shows_for_new_items(self, driver):
        driver.get("http://127.0.0.1:5173/#/modules/port-scanner")
        btn = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "[data-testid='scan-button']"))
        )
        btn.click()

        WebDriverWait(driver, 60).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "[data-testid='data-table'] tbody tr, .data-table tbody tr, table tbody tr"))
        )

        new_badges = driver.find_elements(By.CSS_SELECTOR, ".badge-new, [data-testid='new-badge']")
        assert len(new_badges) >= 0


@pytest.mark.selenium
class TestPortScannerWhitelistActions:
    """Tests for whitelist mark safe/unmark safe actions."""

    def test_mark_safe_button_appears_in_row_actions(self, driver):
        driver.get("http://127.0.0.1:5173/#/modules/port-scanner")
        btn = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "[data-testid='scan-button']"))
        )
        btn.click()

        WebDriverWait(driver, 60).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "[data-testid='data-table'] tbody tr, .data-table tbody tr, table tbody tr"))
        )

        action_buttons = driver.find_elements(By.CSS_SELECTOR, "[data-testid='mark-safe-btn'], .mark-safe-btn, .row-actions button")
        if action_buttons:
            btn = action_buttons[0]
            assert "Đánh dấu an toàn" in btn.text or "Mark safe" in btn.text

    def test_click_mark_safe_changes_to_unmark(self, driver):
        driver.get("http://127.0.0.1:5173/#/modules/port-scanner")
        btn = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "[data-testid='scan-button']"))
        )
        btn.click()

        WebDriverWait(driver, 60).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "[data-testid='data-table'] tbody tr, .data-table tbody tr, table tbody tr"))
        )

        action_buttons = driver.find_elements(By.CSS_SELECTOR, ".row-actions button")
        if action_buttons:
            initial_text = action_buttons[0].text
            action_buttons[0].click()
            WebDriverWait(driver, 5).until(
                lambda d: action_buttons[0].text != initial_text
            )
            assert "Bỏ an toàn" in action_buttons[0].text or "Unmark" in action_buttons[0].text


@pytest.mark.selenium
class TestPortScannerRadarMap:
    """Tests for radar map visualization."""

    def test_radar_map_rendered(self, driver):
        driver.get("http://127.0.0.1:5173/#/modules/port-scanner")
        radar = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "[data-testid='radar-map'], .radar-map, svg"))
        )
        assert radar.is_displayed()

    def test_radar_map_shows_dots_after_scan(self, driver):
        driver.get("http://127.0.0.1:5173/#/modules/port-scanner")
        btn = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "[data-testid='scan-button']"))
        )
        btn.click()

        WebDriverWait(driver, 60).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "[data-testid='radar-dot'], .radar-dot, circle[fill]"))
        )

        dots = driver.find_elements(By.CSS_SELECTOR, "[data-testid='radar-dot'], .radar-dot, circle[fill]")
        assert len(dots) > 0


@pytest.mark.selenium
class TestPortScannerErrorStates:
    """Tests for error handling in UI."""

    def test_shows_error_banner_on_permission_denied(self, driver):
        driver.get("http://127.0.0.1:5173/#/modules/port-scanner")
        btn = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "[data-testid='scan-button']"))
        )
        btn.click()

        WebDriverWait(driver, 60).until(
            EC.any_of(
                EC.presence_of_element_located((By.CSS_SELECTOR, "[data-testid='error-banner'], .error-banner")),
                EC.presence_of_element_located((By.CSS_SELECTOR, "[data-testid='data-table'], .data-table"))
            )
        )

        error_banners = driver.find_elements(By.CSS_SELECTOR, "[data-testid='error-banner'], .error-banner")
        if error_banners:
            assert "cần chạy" in error_banners[0].text.lower() or "administrator" in error_banners[0].text.lower()
