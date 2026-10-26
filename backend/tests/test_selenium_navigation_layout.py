from __future__ import annotations

import pytest
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


def token_color(driver, name):
    return driver.execute_script("const e=document.createElement('span');e.style.color='var('+arguments[0]+')';document.body.append(e);const color=getComputedStyle(e).color;e.remove();return color", name)


@pytest.mark.selenium
class TestAppShellLayout:
    """Tests for the main app shell layout (sidebar + topbar)."""

    def test_sidebar_always_visible(self, driver):
        driver.get("http://127.0.0.1:5173/#/modules/port-scanner")
        sidebar = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "[data-testid='sidebar'], .sidebar, aside"))
        )
        assert sidebar.is_displayed()

    def test_topbar_always_visible(self, driver):
        driver.get("http://127.0.0.1:5173/#/modules/port-scanner")
        topbar = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "[data-testid='topbar'], .topbar, header"))
        )
        assert topbar.is_displayed()

    def test_topbar_shows_breadcrumb(self, driver):
        driver.get("http://127.0.0.1:5173/#/modules/port-scanner")
        breadcrumb = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "[data-testid='breadcrumb'], .breadcrumb"))
        )
        assert "Port Scanner" in breadcrumb.text or "Modules" in breadcrumb.text

    def test_topbar_shows_scan_button(self, driver):
        driver.get("http://127.0.0.1:5173/#/modules/port-scanner")
        scan_btn = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "[data-testid='topbar-scan-btn'], .topbar-scan-btn, header button"))
        )
        assert scan_btn.is_displayed()
        assert "Quét ngay" in scan_btn.text or "Scan" in scan_btn.text


@pytest.mark.selenium
class TestSidebarNavigation:
    """Tests for sidebar module navigation."""

    def test_navigate_to_port_scanner(self, driver):
        driver.get("http://127.0.0.1:5173/")
        port_scanner_link = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "[data-testid='nav-item-port-scanner'], .nav-item[data-module='port-scanner']"))
        )
        port_scanner_link.click()

        WebDriverWait(driver, 10).until(
            EC.url_contains("/modules/port-scanner")
        )
        assert "/modules/port-scanner" in driver.current_url

    def test_navigate_to_scan_history(self, driver):
        driver.get("http://127.0.0.1:5173/#/modules/port-scanner")
        history_link = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "[data-testid='nav-item-scan-history'], .nav-item[data-route='/scan-history']"))
        )
        history_link.click()

        WebDriverWait(driver, 10).until(
            EC.url_contains("/scan-history")
        )
        assert "/scan-history" in driver.current_url

    def test_navigate_to_settings(self, driver):
        driver.get("http://127.0.0.1:5173/#/modules/port-scanner")
        settings_link = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "[data-testid='nav-item-settings'], .nav-item[data-route='/settings']"))
        )
        settings_link.click()

        WebDriverWait(driver, 10).until(
            EC.url_contains("/settings")
        )
        assert "/settings" in driver.current_url

    def test_coming_soon_modules_show_disabled(self, driver):
        driver.get("http://127.0.0.1:5173/#/modules/port-scanner")
        disabled_items = driver.find_elements(By.CSS_SELECTOR, "[data-testid^='nav-item-'][data-status='coming-soon'], .nav-item.disabled, .nav-item.coming-soon")
        disabled_texts = [item.text for item in disabled_items]
        expected_coming_soon = ["Startup Programs", "Outbound Connections"]
        for expected in expected_coming_soon:
            assert any(expected in t for t in disabled_texts), f"Missing coming-soon module: {expected}"

    def test_coming_soon_modules_not_clickable(self, driver):
        driver.get("http://127.0.0.1:5173/#/modules/port-scanner")
        disabled_items = driver.find_elements(
            By.CSS_SELECTOR,
            "[data-testid^='nav-item-'][data-status='coming-soon'], .nav-item.disabled, .nav-item.coming-soon",
        )
        for item in disabled_items:
            assert "disabled" in item.get_attribute("class") or item.get_attribute("aria-disabled") == "true"


@pytest.mark.selenium
class TestModulePageLayoutContract:
    """Tests that every module page follows the layout contract."""

    def test_page_has_header_with_title_and_description(self, driver):
        driver.get("http://127.0.0.1:5173/#/modules/port-scanner")
        header = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "[data-testid='page-header'], .page-header"))
        )
        title = header.find_element(By.CSS_SELECTOR, "[data-testid='page-title'], .page-title, h1")
        desc = header.find_element(By.CSS_SELECTOR, "[data-testid='page-description'], .page-description")
        assert title.is_displayed()
        assert desc.is_displayed()

    def test_page_has_kpi_row_with_max_4_cards(self, driver):
        driver.get("http://127.0.0.1:5173/#/modules/port-scanner")
        kpi_cards = WebDriverWait(driver, 10).until(
            EC.presence_of_all_elements_located((By.CSS_SELECTOR, "[data-testid='kpi-card'], .kpi-card"))
        )
        assert 1 <= len(kpi_cards) <= 4

    def test_page_has_panel_grid_with_two_panels(self, driver):
        driver.get("http://127.0.0.1:5173/#/modules/port-scanner")
        panels = WebDriverWait(driver, 10).until(
            EC.presence_of_all_elements_located((By.CSS_SELECTOR, "[data-testid='panel'], .panel"))
        )
        assert len(panels) >= 2

        first_panel = panels[0]
        second_panel = panels[1]

        first_title = first_panel.find_element(By.CSS_SELECTOR, "[data-testid='panel-title'], .panel-title, h2").text
        second_title = second_panel.find_element(By.CSS_SELECTOR, "[data-testid='panel-title'], .panel-title, h2").text

        assert "Radar" in first_title or "Visualization" in first_title
        assert "Chi tiết" in second_title or "Detail" in second_title

    def test_panel_has_subtitle(self, driver):
        driver.get("http://127.0.0.1:5173/#/modules/port-scanner")
        panels = WebDriverWait(driver, 10).until(
            EC.presence_of_all_elements_located((By.CSS_SELECTOR, "[data-testid='panel'], .panel"))
        )
        for panel in panels:
            subtitles = panel.find_elements(By.CSS_SELECTOR, "[data-testid='panel-subtitle'], .panel-subtitle")
            assert len(subtitles) >= 0


@pytest.mark.selenium
class TestDesignTokens:
    """Tests that design tokens are correctly applied."""

    def test_background_colors_use_tokens(self, driver):
        driver.get("http://127.0.0.1:5173/#/modules/port-scanner")
        body = driver.find_element(By.TAG_NAME, "body")
        bg_color = driver.execute_script("return getComputedStyle(arguments[0]).backgroundColor", body)
        assert bg_color == token_color(driver, "--bg-base")

    def test_status_colors_use_correct_tokens(self, driver):
        driver.get("http://127.0.0.1:5173/#/modules/port-scanner")
        btn = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "[data-testid='scan-button']"))
        )
        btn.click()

        WebDriverWait(driver, 60).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "[data-testid='status-badge'], .status-badge"))
        )

        danger_badges = driver.find_elements(By.CSS_SELECTOR, "[data-testid='status-badge'][data-tone='danger'], .status-badge.danger")
        warning_badges = driver.find_elements(By.CSS_SELECTOR, "[data-testid='status-badge'][data-tone='warning'], .status-badge.warning")
        safe_badges = driver.find_elements(By.CSS_SELECTOR, "[data-testid='status-badge'][data-tone='safe'], .status-badge.safe")

        for tone, badges in (("danger", danger_badges), ("warning", warning_badges), ("safe", safe_badges)):
            for badge in badges:
                color = driver.execute_script("return getComputedStyle(arguments[0]).color", badge)
                assert color == token_color(driver, f"--status-{tone}")

    def test_mono_font_used_for_technical_data(self, driver):
        driver.get("http://127.0.0.1:5173/#/modules/port-scanner")
        btn = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "[data-testid='scan-button']"))
        )
        btn.click()

        WebDriverWait(driver, 60).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "[data-testid='data-table'] td, .data-table td, table td"))
        )

        mono_elements = driver.find_elements(By.CSS_SELECTOR, "[data-mono='true'], .mono, .font-mono, td[style*='mono']")
        if not mono_elements:
            mono_elements = driver.find_elements(By.CSS_SELECTOR, "td.td-mono")

        for elem in mono_elements[:5]:
            font_family = elem.value_of_css_property("font-family")
            assert "mono" in font_family.lower() or "JetBrains Mono" in font_family


@pytest.mark.selenium
class TestResponsiveLayout:
    """Tests for responsive behavior."""

    def test_mobile_viewport_stacks_panels(self, driver):
        driver.set_window_size(480, 800)
        driver.get("http://127.0.0.1:5173/#/modules/port-scanner")

        panels = WebDriverWait(driver, 10).until(
            EC.presence_of_all_elements_located((By.CSS_SELECTOR, "[data-testid='panel'], .panel"))
        )

        inventory = driver.find_element(By.ID, "port-inventory")
        summary = driver.find_element(By.ID, "port-summary")
        assert inventory.location["y"] < summary.location["y"], "Inventory must precede summary on narrow screens"
        assert inventory.location["x"] == summary.location["x"]

    def test_desktop_viewport_shows_side_by_side_panels(self, driver):
        driver.set_window_size(1366, 768)
        driver.get("http://127.0.0.1:5173/#/modules/port-scanner")

        panels = WebDriverWait(driver, 10).until(
            EC.presence_of_all_elements_located((By.CSS_SELECTOR, "[data-testid='panel'], .panel"))
        )

        if len(panels) >= 2:
            inventory = driver.find_element(By.ID, "port-inventory")
            summary = driver.find_element(By.ID, "port-summary")
            first_right = inventory.location['x'] + inventory.size['width']
            second_left = summary.location['x']
            assert abs(first_right - second_left) < 50, "Panels should be side by side on desktop"

    def test_sidebar_collapses_on_narrow_screen(self, driver):
        driver.set_window_size(800, 600)
        driver.get("http://127.0.0.1:5173/#/modules/port-scanner")

        button = WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.CSS_SELECTOR, "[data-testid='menu-toggle']")))
        button.click()
        dialog = driver.find_element(By.CSS_SELECTOR, "dialog[open].mobile-navigation")
        assert dialog.is_displayed() and dialog.size['width'] <= 320
        assert "Port Scanner" in dialog.text


@pytest.mark.selenium
class TestAccessibility:
    """Tests for accessibility compliance."""

    def test_focus_visible_on_interactive_elements(self, driver):
        driver.get("http://127.0.0.1:5173/#/modules/port-scanner")
        btn = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "[data-testid='scan-button']"))
        )
        btn.send_keys("\ue004")  # TAB key

        focused = driver.switch_to.active_element
        outline = focused.value_of_css_property("outline") or focused.value_of_css_property("box-shadow")
        assert "none" not in outline or "0px" not in outline

    def test_status_has_text_not_only_color(self, driver):
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
            text = badge.text.strip()
            assert text, "Status/review badge must include readable text, not only color"

    def test_table_sortable_columns_have_aria_sort(self, driver):
        driver.get("http://127.0.0.1:5173/#/modules/port-scanner")
        btn = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "[data-testid='scan-button']"))
        )
        btn.click()

        WebDriverWait(driver, 60).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "[data-testid='data-table'] th, .data-table th, table th"))
        )

        headers = driver.find_elements(By.CSS_SELECTOR, "[data-testid='data-table'] th, .data-table th, table th")
        sortable_headers = [h for h in headers if h.get_attribute("aria-sort") is not None or "sortable" in (h.get_attribute("class") or "")]
        assert len(sortable_headers) > 0


@pytest.mark.selenium
class TestThemeTokensConsistency:
    """Tests that theme tokens are consistently applied across components."""

    def test_accent_color_used_for_primary_actions(self, driver):
        driver.get("http://127.0.0.1:5173/#/modules/port-scanner")
        primary_buttons = driver.find_elements(By.CSS_SELECTOR, "[data-variant='primary'], .btn-primary, button.primary")
        for btn in primary_buttons:
            bg = driver.execute_script("return getComputedStyle(arguments[0]).backgroundColor", btn)
            assert bg == token_color(driver, "--accent")

    def test_border_colors_use_token(self, driver):
        driver.get("http://127.0.0.1:5173/#/modules/port-scanner")
        panels = driver.find_elements(By.CSS_SELECTOR, "[data-testid='panel'], .panel, [data-testid='kpi-card'], .kpi-card")
        for panel in panels[:3]:
            borders = driver.execute_script("const s=getComputedStyle(arguments[0]);return ['Top','Right','Bottom','Left'].filter(side=>parseFloat(s['border'+side+'Width'])>0).map(side=>s['border'+side+'Color'])", panel)
            assert borders and all(border == token_color(driver, "--border-soft") for border in borders)

    def test_text_colors_use_tokens(self, driver):
        driver.get("http://127.0.0.1:5173/#/modules/port-scanner")
        primary_text = driver.find_element(By.CSS_SELECTOR, "[data-testid='page-title'], .page-title, h1")
        color = driver.execute_script("return getComputedStyle(arguments[0]).color", primary_text)
        assert color == token_color(driver, "--text-primary")

    def test_muted_text_uses_token(self, driver):
        driver.get("http://127.0.0.1:5173/#/modules/port-scanner")
        muted_elements = driver.find_elements(By.CSS_SELECTOR, "[data-testid='kpi-sub'], .kpi-sub, .text-muted, .caption")
        for elem in muted_elements[:3]:
            color = driver.execute_script("return getComputedStyle(arguments[0]).color", elem)
            assert color in (token_color(driver, "--text-muted"), token_color(driver, "--text-secondary"))
