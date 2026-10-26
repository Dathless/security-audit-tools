from __future__ import annotations

import os
import sqlite3
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
def selenium_database(tmp_path_factory):
    return tmp_path_factory.mktemp("selenium") / "test.db"


@pytest.fixture(scope="session")
def backend_process(selenium_database) -> Generator[subprocess.Popen, None, None]:
    """Start backend server for UI tests."""
    env = os.environ.copy()
    env["PYTHONPATH"] = str(BACKEND_DIR)
    env["SELENIUM_DATABASE"] = str(selenium_database)
    log_path = Path(env["SELENIUM_DATABASE"]).with_name("backend.log")
    log_file = log_path.open("w", encoding="utf-8")
    script = (
        "import os; from core.config import config; "
        "config.settings.app.local_token='test-token'; "
        "config.settings.app.require_local_token=True; "
        "from core.config import ModuleSettings; "
        "config.settings.modules['firewall-check']=ModuleSettings(enabled=True); "
        "from storage.db import db; db.configure('sqlite:///' + os.environ['SELENIUM_DATABASE']); "
        # Repeated Chrome socket teardown can stop Windows IOCP accepts (WinError 64).
        "import uvicorn; uvicorn.run('main:app', host='127.0.0.1', port=8000, "
        "loop='asyncio:SelectorEventLoop' if os.name == 'nt' else 'auto')"
    )
    proc = subprocess.Popen(
        [sys.executable, "-c", script],
        cwd=BACKEND_DIR,
        env=env,
        stdout=log_file,
        stderr=subprocess.STDOUT,
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
        proc.wait(timeout=5)
        log_file.close()
        pytest.fail(f"Backend failed to start:\n{log_path.read_text(encoding='utf-8', errors='replace')}")
    yield proc
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=5)
    log_file.close()


@pytest.fixture(scope="session")
def frontend_process(backend_process, request) -> Generator[subprocess.Popen, None, None]:
    """Start frontend dev server for UI tests."""
    env = os.environ.copy()
    env["VITE_API_BASE"] = "http://127.0.0.1:8000/api/v1"
    env["VITE_LOCAL_TOKEN"] = "" if request.config.getoption("--selenium-no-env-token") else "test-token"
    # Start Node directly so fixture teardown terminates Vite rather than a shell shim.
    cmd = ["node", str(FRONTEND_DIR / "node_modules/vite/bin/vite.js"), "--host", "127.0.0.1", "--port", "5173", "--strictPort"]
    proc = subprocess.Popen(
        cmd,
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


def _create_chrome_driver(headless: bool = SELENIUM_HEADLESS) -> WebDriver:
    options = ChromeOptions()
    if headless:
        options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1366,768")
    options.add_argument("--disable-extensions")
    options.add_argument("--disable-web-security")
    options.add_argument("--allow-running-insecure-content")
    return webdriver.Chrome(options=options)


def _create_firefox_driver(headless: bool = SELENIUM_HEADLESS) -> WebDriver:
    options = FirefoxOptions()
    if headless:
        options.add_argument("--headless")
    options.add_argument("--width=1366")
    options.add_argument("--height=768")
    return webdriver.Firefox(options=options)


@pytest.fixture(scope="function")
def driver(request, frontend_process, selenium_database) -> Generator[WebDriver, None, None]:
    """Selenium WebDriver fixture."""
    import httpx
    for _ in range(400):
        health = httpx.get(f"{SELENIUM_API_URL}/api/v1/health", headers={"X-Local-Token": "test-token"}, timeout=2).json()
        if health["data"]["running_scans"] == 0:
            break
        time.sleep(0.2)
    else:
        pytest.fail("Previous Selenium scan did not finish")
    with sqlite3.connect(selenium_database) as connection:
        for table in ("port_scanner_reviews", "scan_diff_log", "scan_items", "whitelist_entries", "scans", "port_scanner_config"):
            connection.execute(f"DELETE FROM {table}")
    headless = str(request.config.getoption("--selenium-headless", "true")).lower() != "false"
    browser = str(request.config.getoption("--selenium-browser", "chrome")).lower()
    if browser == "firefox":
        drv = _create_firefox_driver(headless)
    else:
        drv = _create_chrome_driver(headless)
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
            EC.element_to_be_clickable((By.CSS_SELECTOR, "[data-testid='scan-button']"))
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
    parser.addoption("--selenium-no-env-token", action="store_true", default=False, help="Test Settings/storage recovery without a Vite token")
