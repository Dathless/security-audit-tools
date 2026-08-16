from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Generator

import pytest
from selenium import webdriver
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.firefox.options import Options as FirefoxOptions
from selenium.webdriver.firefox.service import Service as FirefoxService
from selenium.webdriver.remote.webdriver import WebDriver

BACKEND_DIR = Path(__file__).resolve().parent.parent
FRONTEND_DIR = BACKEND_DIR.parent / "frontend"
PROJECT_ROOT = BACKEND_DIR.parent

SELENIUM_BASE_URL = os.getenv("SELENIUM_BASE_URL", "http://127.0.0.1:5173")
SELENIUM_API_URL = os.getenv("SELENIUM_API_URL", "http://127.0.0.1:8000")
SELENIUM_BROWSER = os.getenv("SELENIUM_BROWSER", "chrome")
SELENIUM_HEADLESS = os.getenv("SELENIUM_HEADLESS", "true").lower() == "true"


@pytest.fixture(scope="session")
def backend_process() -> Generator[subprocess.Popen, None, None]:
    """Start backend server for UI tests."""
    env = os.environ.copy()
    env["PYTHONPATH"] = str(BACKEND_DIR)
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "main:app", "--host", "127.0.0.1", "--port", "8000"],
        cwd=BACKEND_DIR,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    for _ in range(30):
        try:
            import httpx
            httpx.get("http://127.0.0.1:8000/api/v1/health", timeout=1.0)
            break
        except Exception:
            time.sleep(0.5)
    else:
        proc.terminate()
        stdout, stderr = proc.communicate(timeout=5)
        pytest.fail(f"Backend failed to start:\nSTDOUT:\n{stdout.decode()}\nSTDERR:\n{stderr.decode()}")
    yield proc
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()


@pytest.fixture(scope="session")
def frontend_process(backend_process) -> Generator[subprocess.Popen, None, None]:
    """Start frontend dev server for UI tests."""
    env = os.environ.copy()
    env["VITE_API_BASE_URL"] = "http://127.0.0.1:8000"
    proc = subprocess.Popen(
        ["pnpm", "run", "dev", "--host", "127.0.0.1", "--port", "5173"],
        cwd=FRONTEND_DIR,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    for _ in range(30):
        try:
            import httpx
            httpx.get("http://127.0.0.1:5173", timeout=1.0)
            break
        except Exception:
            time.sleep(0.5)
    else:
        proc.terminate()
        stdout, stderr = proc.communicate(timeout=5)
        pytest.fail(f"Frontend failed to start:\nSTDOUT:\n{stdout.decode()}\nSTDERR:\n{stderr.decode()}")
    yield proc
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()


def _create_chrome_driver() -> WebDriver:
    options = ChromeOptions()
    if SELENIUM_HEADLESS:
        options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1366,768")
    options.add_argument("--disable-extensions")
    options.add_argument("--disable-web-security")
    options.add_argument("--allow-running-insecure-content")
    return webdriver.Chrome(options=options)


def _create_firefox_driver() -> WebDriver:
    options = FirefoxOptions()
    if SELENIUM_HEADLESS:
        options.add_argument("--headless")
    options.add_argument("--width=1366")
    options.add_argument("--height=768")
    return webdriver.Firefox(options=options)


@pytest.fixture(scope="function")
def driver(frontend_process) -> Generator[WebDriver, None, None]:
    """Selenium WebDriver fixture."""
    if SELENIUM_BROWSER.lower() == "firefox":
        drv = _create_firefox_driver()
    else:
        drv = _create_chrome_driver()
    drv.set_page_load_timeout(30)
    drv.implicitly_wait(5)
    yield drv
    drv.quit()


@pytest.fixture(scope="function")
def wait_for_angular(driver: WebDriver):
    """Wait for React app to be ready."""
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.common.by import By

    WebDriverWait(driver, 15).until(
        EC.presence_of_element_located((By.ID, "root"))
    )
    WebDriverWait(driver, 15).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, "[data-testid='app-shell'], .app-shell, #root > div"))
    )


@pytest.fixture(autouse=True)
def _setup_token(request):
    if not request.config.getoption("--selenium"):
        return
    if request.node.get_closest_marker("selenium") is None:
        return
    driver = request.getfixturevalue("driver")
    driver.get(SELENIUM_BASE_URL)
    driver.execute_script("localStorage.setItem('local_token', 'test-token');")
    driver.refresh()



# Helper functions for tests
class PageHelpers:
    @staticmethod
    def wait_for_scan_complete(driver: WebDriver, timeout: int = 30):
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        from selenium.webdriver.common.by import By

        WebDriverWait(driver, timeout).until(
            EC.invisibility_of_element_located((By.CSS_SELECTOR, "[data-testid='progress-bar'], .progress-bar"))
        )

    @staticmethod
    def get_kpi_values(driver: WebDriver) -> dict:
        from selenium.webdriver.common.by import By
        kpis = {}
        cards = driver.find_elements(By.CSS_SELECTOR, "[data-testid='kpi-card'], .kpi-card")
        for card in cards:
            label = card.find_element(By.CSS_SELECTOR, "[data-testid='kpi-label'], .kpi-label").text
            value = card.find_element(By.CSS_SELECTOR, "[data-testid='kpi-value'], .kpi-value").text
            kpis[label] = value
        return kpis

    @staticmethod
    def get_table_rows(driver: WebDriver) -> list[dict]:
        from selenium.webdriver.common.by import By
        rows = []
        table = driver.find_element(By.CSS_SELECTOR, "[data-testid='data-table'], .data-table, table")
        headers = [h.text for h in table.find_elements(By.CSS_SELECTOR, "th")]
        for row in table.find_elements(By.CSS_SELECTOR, "tbody tr"):
            cells = row.find_elements(By.CSS_SELECTOR, "td")
            if len(cells) >= len(headers):
                rows.append({headers[i]: cells[i].text for i in range(len(headers))})
        return rows

    @staticmethod
    def click_scan_button(driver: WebDriver):
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC

        btn = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "[data-testid='scan-button'], button:contains('Quét ngay'), .scan-button"))
        )
        btn.click()

    @staticmethod
    def wait_for_empty_state(driver: WebDriver, timeout: int = 10):
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        from selenium.webdriver.common.by import By

        WebDriverWait(driver, timeout).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "[data-testid='empty-state'], .empty-state"))
        )


@pytest.fixture
def page_helpers() -> PageHelpers:
    return PageHelpers()


# Pytest markers for Selenium tests
def pytest_configure(config):
    config.addinivalue_line("markers", "selenium: mark test as Selenium UI test")
    config.addinivalue_line("markers", "slow: mark test as slow running")


# Skip selenium tests if not explicitly requested
def pytest_collection_modifyitems(config, items):
    if not config.getoption("--selenium"):
        skip_selenium = pytest.mark.skip(reason="need --selenium option to run")
        for item in items:
            if "selenium" in item.keywords:
                item.add_marker(skip_selenium)


def pytest_addoption(parser):
    parser.addoption("--selenium", action="store_true", default=False, help="Run Selenium UI tests")
    parser.addoption("--selenium-browser", action="store", default="chrome", help="Browser for Selenium tests")
    parser.addoption("--selenium-headless", action="store", default="true", help="Run headless")