from __future__ import annotations

import pytest
import json
import sqlite3
from pathlib import Path
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import Select, WebDriverWait
from selenium.webdriver.common.keys import Keys
from tests.test_selenium_port_upgrade import seed_endpoints

pytestmark = pytest.mark.selenium
URL = "http://127.0.0.1:5173"
ARTIFACTS = Path(__file__).resolve().parents[2] / "docs/testing/reports/ui-console-assets"


def capture(driver, name):
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    driver.save_screenshot(str(ARTIFACTS / f"{name}.png"))


def theme_control(driver):
    return WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, "[data-testid='theme-selector']"))
    )


def theme(driver):
    return driver.find_element(By.TAG_NAME, "html").get_attribute("data-theme")


def test_theme_defaults_persists_and_rejects_invalid_storage(driver):
    driver.get(URL + "/#/modules/port-scanner")
    control = theme_control(driver)
    assert theme(driver) == "technical"
    assert [option.get_attribute("value") for option in Select(control).options] == ["technical", "graphite", "light"]
    Select(control).select_by_value("graphite")
    assert theme(driver) == "graphite"
    driver.refresh()
    assert theme_control(driver).get_attribute("value") == "graphite"
    driver.execute_script("localStorage.setItem('sec_audit_theme', 'untrusted-theme')")
    driver.refresh()
    assert theme_control(driver).get_attribute("value") == "technical"
    assert theme(driver) == "technical"


def test_theme_settings_mirrors_shell(driver):
    viewport(driver, 1440, 900)
    driver.get(URL + "/#/settings")
    theme_control(driver)
    controls = driver.find_elements(By.CSS_SELECTOR, "[data-testid='theme-selector']")
    assert len(controls) == 2
    token = driver.find_element(By.CSS_SELECTOR, ".settings-input").get_attribute("value")
    assert driver.find_element(By.CSS_SELECTOR, ".settings-input").get_attribute("type") == "password"
    Select(controls[1]).select_by_value("light")
    assert all(control.get_attribute("value") == "light" for control in controls)
    assert theme(driver) == "light"
    assert driver.find_element(By.CSS_SELECTOR, ".settings-input").get_attribute("value") == token
    for value in ("technical", "graphite", "light"):
        Select(controls[1]).select_by_value(value)
        assert all(control.get_attribute("value") == value for control in controls)
        assert driver.find_element(By.CSS_SELECTOR, ".settings-input").get_attribute("value") == token
        capture(driver, f"{value}-settings-1440x900")
    driver.find_element(By.CSS_SELECTOR, "[data-testid='nav-item-port-scanner']").click()
    assert theme_control(driver).get_attribute("value") == "light"


def test_theme_storage_denial_does_not_break_startup(driver):
    driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {"source": """
        for (const method of ['getItem', 'setItem']) {
            const original = Storage.prototype[method];
            Storage.prototype[method] = function(key, ...args) {
                if (key === 'sec_audit_theme') throw new DOMException('Storage denied', 'SecurityError');
                return original.call(this, key, ...args);
            };
        }
    """})
    driver.get(URL + "/#/modules/port-scanner")
    control = theme_control(driver)
    assert theme(driver) == "technical"
    Select(control).select_by_value("graphite")
    assert theme(driver) == "graphite"
    driver.refresh()
    assert theme_control(driver).get_attribute("value") == "technical"


def viewport(driver, width, height):
    driver.execute_cdp_cmd("Emulation.setDeviceMetricsOverride", {"width": width, "height": height, "deviceScaleFactor": 1, "mobile": False})


def test_manifest_search_scales_without_hiding_general_navigation(driver):
    driver.get(URL + "/#/modules/port-scanner")
    theme_control(driver)
    driver.execute_async_script("""
      const done = arguments[0];
      import('/src/core/moduleRegistry.ts').then(({registry}) => {
        for (let i = 0; i < 22; i++) registry.push({id: `future-${i}`, name: `Future module ${i}`, icon: '◇', route: `/modules/future-${i}`, navGroup: 'modules', navOrder: 100+i, status: 'coming-soon'});
        done();
      });
    """)
    search = driver.find_element(By.CSS_SELECTOR, "[data-testid='module-search']")
    search.send_keys("Future module 21")
    assert len(driver.find_elements(By.CSS_SELECTOR, ".nav [data-group='modules']")) == 1
    assert "Future module 21" in driver.find_element(By.CSS_SELECTOR, ".nav").text
    assert driver.find_element(By.CSS_SELECTOR, "[data-testid='nav-item-settings']").is_displayed()
    search.clear()
    search.send_keys(" ")
    assert driver.execute_script("return document.querySelector('[data-testid=nav-item-settings]').getBoundingClientRect().bottom < innerHeight"), "General navigation stays reachable when all future modules are listed"
    search.clear()
    search.send_keys("not-found")
    assert "Không tìm thấy module" in driver.find_element(By.CSS_SELECTOR, ".nav").text


def test_mobile_navigation_keyboard_escape_and_focus_return(driver):
    viewport(driver, 390, 844)
    driver.get(URL + "/#/modules/port-scanner")
    theme_control(driver)
    toggle = driver.find_element(By.CSS_SELECTOR, "[data-testid='menu-toggle']")
    toggle.send_keys(Keys.ENTER)
    dialog = driver.find_element(By.CSS_SELECTOR, "dialog[open].mobile-navigation")
    assert dialog.is_displayed()
    driver.switch_to.active_element.send_keys(Keys.ESCAPE)
    assert not driver.find_elements(By.CSS_SELECTOR, "dialog[open].mobile-navigation")
    assert driver.switch_to.active_element == toggle


@pytest.mark.parametrize("size", [(390, 844), (1024, 768), (1440, 900)])
def test_themes_keep_panels_and_bound_page_width(driver, selenium_database, size):
    seed_endpoints(selenium_database)
    viewport(driver, *size)
    driver.get(URL + "/#/modules/port-scanner")
    control = theme_control(driver)
    WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.TAG_NAME, "table")))
    original = [p.text for p in driver.find_elements(By.CSS_SELECTOR, "[data-testid='panel-title']")]
    table = driver.find_element(By.TAG_NAME, "table")
    content = table.text
    for value in ("technical", "graphite", "light"):
        Select(control).select_by_value(value)
        assert [p.text for p in driver.find_elements(By.CSS_SELECTOR, "[data-testid='panel-title']")] == original
        assert driver.execute_script("return document.documentElement.scrollWidth <= innerWidth"), value
        assert driver.find_element(By.TAG_NAME, "table") == table
        assert table.text == content
        inventory = driver.find_element(By.ID, "port-inventory").rect
        summary = driver.find_element(By.ID, "port-summary").rect
        if size[0] <= 1150:
            assert inventory["y"] < summary["y"]
        elif value == "technical":
            assert inventory["x"] < summary["x"]
        elif value == "graphite":
            assert summary["y"] < inventory["y"]
        else:
            assert summary["x"] < inventory["x"]
        capture(driver, f"{value}-{size[0]}x{size[1]}")


def test_theme_switch_preserves_filter_evidence_and_review(driver, selenium_database):
    seed_endpoints(selenium_database)
    driver.get(URL + "/#/modules/port-scanner")
    wait = WebDriverWait(driver, 10)
    wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "[data-testid='endpoint-evidence-btn']")))
    search = driver.find_element(By.CSS_SELECTOR, ".datatable-search")
    search.send_keys("C:\\Demo\\demo.exe")
    driver.find_element(By.CSS_SELECTOR, "[data-testid='endpoint-evidence-btn']").click()
    dialog = driver.find_element(By.CSS_SELECTOR, "dialog[open].evidence-drawer")
    original = dialog.find_element(By.CSS_SELECTOR, ".evidence-content").text
    assert "C:\\Demo\\demo.exe" in original and "DEMO\\user" in original
    driver.execute_script("window.__themeRequests=[]; const fetch=window.fetch; window.fetch=(url,...args)=>{if(!String(url).endsWith('/health')) window.__themeRequests.push(String(url)); return fetch(url,...args)}; window.__originalEvidence=document.querySelector('.evidence-content');")
    for value in ("graphite", "light", "technical"):
        Select(dialog.find_element(By.CSS_SELECTOR, "[data-testid='theme-selector']")).select_by_value(value)
        assert dialog.find_element(By.CSS_SELECTOR, ".evidence-content").text == original
        assert driver.execute_script("return document.querySelector('.evidence-content') === window.__originalEvidence")
    assert driver.execute_script("return window.__themeRequests") == []
    driver.switch_to.active_element.send_keys(Keys.ESCAPE)
    assert search.get_attribute("value") == "C:\\Demo\\demo.exe"
    driver.find_element(By.CSS_SELECTOR, "[data-testid='review-endpoint-btn']").click()
    wait.until(EC.text_to_be_present_in_element((By.TAG_NAME, "table"), "Hủy xác nhận"))
    assert driver.find_element(By.CSS_SELECTOR, ".kpi-danger [data-testid='kpi-value']").text == "1"


def seed_firewall(database):
    with sqlite3.connect(database) as connection:
        connection.execute("INSERT INTO scans (id,module_id,status,started_at,finished_at,summary_json,partial_result) VALUES ('theme-firewall','firewall-check','done','2026-10-24 00:00:00','2026-10-24 00:01:00',?,0)", (json.dumps({"total_profiles": 3, "total_rules": 1, "danger": 1, "warning": 1, "safe": 2}),))
        for name in ("Domain", "Private", "Public"):
            detail = {"kind": "profile", "name": name, "active": name == "Private", "enabled": name != "Public", "default_inbound_action": "Block", "default_outbound_action": "Allow", "reasons": ["FIREWALL_DISABLED"] if name == "Public" else [], "guidance": ["Kiểm tra chính sách firewall."]}
            connection.execute("INSERT INTO scan_items (scan_id,module_id,whitelist_key,severity,title,detail_json,is_new) VALUES ('theme-firewall','firewall-check',?,?,?,?,0)", (name, "danger" if name == "Public" else "safe", name, json.dumps(detail)))
        detail = {"kind": "rule", "name": "demo-rule", "profiles": ["Public"], "direction": "Inbound", "action": "Allow", "protocol": "TCP", "local_ports": ["4444"], "remote_ports": ["Any"], "local_addresses": ["Any"], "remote_addresses": ["Any"], "program": "C:\\Demo\\demo.exe", "service": "Demo service", "policy_source": "Local", "reasons": ["BROAD_INBOUND_ALLOW"], "guidance": ["Xác minh phạm vi cho phép."]}
        connection.execute("INSERT INTO scan_items (scan_id,module_id,whitelist_key,severity,title,detail_json,is_new) VALUES ('theme-firewall','firewall-check','demo-rule','warning','Demo rule',?,1)", (json.dumps(detail),))


def test_firewall_evidence_and_history_selection_survive_themes(driver, selenium_database):
    viewport(driver, 1440, 900)
    seed_firewall(selenium_database)
    driver.get(URL + "/#/modules/firewall-check")
    button = WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.CSS_SELECTOR, "[data-testid='firewall-evidence-btn']")))
    profiles = [p.text for p in driver.find_elements(By.CSS_SELECTOR, "[data-testid='firewall-profile']")]
    assert len(profiles) == 3
    button.click()
    dialog = driver.find_element(By.CSS_SELECTOR, "dialog[open].evidence-drawer")
    original = dialog.find_element(By.CSS_SELECTOR, ".evidence-content").text
    for value in ("technical", "graphite", "light"):
        Select(dialog.find_element(By.CSS_SELECTOR, "[data-testid='theme-selector']")).select_by_value(value)
        assert dialog.find_element(By.CSS_SELECTOR, ".evidence-content").text == original
        for text in ("C:\\Demo\\demo.exe", "Demo service", "Local", "4444", "Xác minh phạm vi"):
            assert text in original
        capture(driver, f"{value}-firewall-evidence-1440x900")
    driver.switch_to.active_element.send_keys(Keys.ESCAPE)
    assert [p.text for p in driver.find_elements(By.CSS_SELECTOR, "[data-testid='firewall-profile']")] == profiles
    driver.find_element(By.CSS_SELECTOR, "[data-testid='nav-item-scan-history']").click()
    select = WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.ID, "history-module")))
    Select(select).select_by_value("firewall-check")
    WebDriverWait(driver, 10).until(EC.text_to_be_present_in_element((By.TAG_NAME, "table"), "3 / 1"))
    for value in ("technical", "graphite", "light"):
        Select(theme_control(driver)).select_by_value(value)
        assert select.get_attribute("value") == "firewall-check"
        assert "3 / 1" in driver.find_element(By.TAG_NAME, "table").text
        capture(driver, f"{value}-history-1440x900")


def test_idle_motion_and_reduced_motion_dialog_focus(driver, selenium_database):
    seed_endpoints(selenium_database)
    driver.execute_cdp_cmd("Emulation.setEmulatedMedia", {"features": [{"name": "prefers-reduced-motion", "value": "reduce"}]})
    driver.get(URL + "/#/modules/port-scanner")
    button = WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.CSS_SELECTOR, "[data-testid='endpoint-evidence-btn']")))
    for value in ("technical", "graphite", "light"):
        Select(theme_control(driver)).select_by_value(value)
        assert driver.execute_script("return [...document.querySelectorAll('.radar *, .mp-layout, .btn')].every(e=>getComputedStyle(e).animationName==='none' && getComputedStyle(e).transitionDuration==='0s')")
    button.click()
    dialog = driver.find_element(By.CSS_SELECTOR, "dialog[open]")
    for _ in range(12):
        driver.switch_to.active_element.send_keys(Keys.TAB)
        assert driver.execute_script("return document.querySelector('dialog[open]').contains(document.activeElement)")
    driver.switch_to.active_element.send_keys(Keys.ESCAPE)
    assert driver.switch_to.active_element == button
    assert not dialog.is_displayed()
    driver.execute_cdp_cmd("Emulation.setEmulatedMedia", {"features": [{"name": "prefers-reduced-motion", "value": "no-preference"}]})
    assert driver.execute_script("return [...document.querySelectorAll('.radar *')].every(e=>getComputedStyle(e).animationName==='none')"), "Idle radar must not run ambient loops"


def test_theme_switch_keeps_running_scan_and_socket(driver, selenium_database):
    driver.get(URL + "/#/settings")
    theme_control(driver)
    seed_endpoints(selenium_database, running=True)
    driver.execute_script("window.__socketCount=0; window.WebSocket=class extends WebSocket{constructor(...args){super(...args);window.__socketCount++;}}; window.__requests=[]; const f=window.fetch;window.fetch=(url,...args)=>{if(!String(url).endsWith('/health'))window.__requests.push(String(url));return f(url,...args);};")
    try:
        driver.find_element(By.CSS_SELECTOR, "[data-testid='nav-item-port-scanner']").click()
        WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.CSS_SELECTOR, "[data-testid='progress-bar']")))
        count = driver.execute_script("return window.__socketCount")
        requests = driver.execute_script("return window.__requests.length")
        progress = driver.find_element(By.CSS_SELECTOR, "[data-testid='progress-bar']")
        for value in ("graphite", "light", "technical"):
            Select(theme_control(driver)).select_by_value(value)
            assert driver.find_element(By.CSS_SELECTOR, "[data-testid='progress-bar']") == progress
        assert driver.execute_script("return window.__socketCount") == count
        assert driver.execute_script("return window.__requests.length") == requests
    finally:
        with sqlite3.connect(selenium_database) as connection:
            connection.execute("UPDATE scans SET status='error' WHERE id='seed-v2'")


@pytest.mark.parametrize("state", ["loading", "empty", "error", "partial", "permission"])
def test_content_states_in_every_theme(driver, selenium_database, state):
    viewport(driver, 390, 844)
    if state in ("partial", "permission"):
        seed_endpoints(selenium_database)
        with sqlite3.connect(selenium_database) as connection:
            if state == "partial":
                connection.execute("UPDATE scans SET partial_result=1 WHERE id='seed-v2'")
            else:
                for item_id, raw in connection.execute("SELECT id,detail_json FROM scan_items").fetchall():
                    detail = json.loads(raw)
                    detail["owners"][0].update(exe=None, username=None)
                    detail["owners"][0]["status"].update(exe="access_denied", username="unknown")
                    detail["owners"].append({"pid": 322, "name": "Other owner", "exe": "C:\\Demo\\" + "long-directory\\" * 24 + "demo.exe", "username": "DEMO\\other-user", "status": {"exe": "ok", "username": "ok"}})
                    connection.execute("UPDATE scan_items SET detail_json=? WHERE id=?", (json.dumps(detail), item_id))
    if state in ("loading", "error"):
        driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {"source": """
          const original = window.fetch;
          window.fetch=(url,...args)=>{
            if(String(url).endsWith('/port-scanner/scans/latest')) {
              if(STATE === 'loading') return new Promise(()=>{});
              return Promise.resolve(new Response(JSON.stringify({success:false,error:{code:'TEST_ERROR',message:'Không thể đọc inventory thử nghiệm'}}),{status:500}));
            }
            return original(url,...args);
          };
        """.replace("STATE", json.dumps(state))})
    driver.get(URL + "/#/modules/port-scanner")
    theme_control(driver)
    expected = {"loading": "Đang tải dữ liệu gần nhất", "empty": "Chưa có dữ liệu quét", "error": "Không thể đọc inventory thử nghiệm", "partial": "Inventory chưa đầy đủ", "permission": "Metadata chưa đầy đủ"}[state]
    WebDriverWait(driver, 10).until(EC.text_to_be_present_in_element((By.TAG_NAME, "main"), expected))
    for value in ("technical", "graphite", "light"):
        Select(theme_control(driver)).select_by_value(value)
        assert expected in driver.find_element(By.TAG_NAME, "main").text
        assert driver.execute_script("return document.documentElement.scrollWidth <= innerWidth")
        if state == "error":
            assert driver.find_element(By.CSS_SELECTOR, "[data-testid='retry-btn']").is_enabled()
        if state == "permission":
            driver.find_element(By.CSS_SELECTOR, "[data-testid='endpoint-evidence-btn']").click()
            drawer = driver.find_element(By.CSS_SELECTOR, "dialog[open]")
            assert "Thiếu quyền" in drawer.text and "Chưa xác định" in drawer.text and "Other owner" in drawer.text
            assert driver.execute_script("const d=document.querySelector('dialog[open]');return d.scrollWidth<=d.clientWidth")
            capture(driver, f"{value}-{state}-390x844")
            drawer.find_element(By.CSS_SELECTOR, "[aria-label='Đóng bằng chứng']").click()
        else:
            capture(driver, f"{value}-{state}-390x844")


def test_theme_contrast_and_key_touch_targets(driver):
    driver.get(URL + "/#/modules/port-scanner")
    theme_control(driver)
    records = {}
    for value in ("technical", "graphite", "light"):
        Select(theme_control(driver)).select_by_value(value)
        ratios = driver.execute_script("""
          const css=getComputedStyle(document.documentElement), canvas=document.createElement('canvas');canvas.width=canvas.height=1;
          const ctx=canvas.getContext('2d');
          const luminance=name=>{ctx.clearRect(0,0,1,1);ctx.fillStyle=css.getPropertyValue(name).trim();ctx.fillRect(0,0,1,1);const rgba=ctx.getImageData(0,0,1,1).data;const c=[...rgba].slice(0,3).map(x=>{x/=255;return x<=.04045?x/12.92:((x+.055)/1.055)**2.4});return .2126*c[0]+.7152*c[1]+.0722*c[2]};
          const ratio=(a,b)=>{const x=luminance(a),y=luminance(b);return (Math.max(x,y)+.05)/(Math.min(x,y)+.05)};
          const values={};for(const text of ['--text-primary','--text-secondary','--text-muted'])for(const bg of ['--bg-base','--bg-surface','--bg-elevated'])values[text+'/'+bg]=ratio(text,bg);
          for(const status of ['danger','warning','safe'])values[status]=ratio('--status-'+status,'--status-'+status+'-soft');
          values.action=ratio('--accent-ink','--accent');values.boundary=ratio('--border','--bg-surface');values.focus=ratio('--accent','--bg-surface');return values;
        """)
        for name, ratio in ratios.items():
            assert ratio >= (3 if name in ("boundary", "focus") else 4.5), (value, name, ratio)
        controls = driver.find_elements(By.CSS_SELECTOR, ".topbar button,.topbar select,.module-search-label input")
        assert all(control.rect["height"] >= 44 for control in controls)
        records[value] = ratios
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    (ARTIFACTS / "contrast.json").write_text(json.dumps(records, indent=2), encoding="utf-8")


def test_history_marks_legacy_without_reinterpreting_counts(driver, selenium_database):
    seed_endpoints(selenium_database)
    with sqlite3.connect(selenium_database) as connection:
        connection.execute("UPDATE scans SET summary_json=? WHERE id='seed-v2'", (json.dumps({"total_open": 2, "danger": 0, "warning": 0, "safe": 2}),))
    driver.get(URL + "/#/scan-history")
    WebDriverWait(driver, 10).until(EC.text_to_be_present_in_element((By.TAG_NAME, "table"), "Hoàn tất"))
    table = driver.find_element(By.TAG_NAME, "table")
    assert "Dữ liệu cũ" in table.text
    assert table.find_element(By.CSS_SELECTOR, "tbody tr td:nth-child(6)").text == "2"


def test_all_storage_denied_keeps_settings_and_reports_save_failure(driver):
    driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {"source": """
      for (const method of ['getItem','setItem','removeItem']) {
        Storage.prototype[method] = () => {throw new DOMException('Storage denied','SecurityError')};
      }
    """})
    driver.get(URL + "/#/settings")
    control = theme_control(driver)
    assert theme(driver) == "technical"
    Select(control).select_by_value("graphite")
    token = driver.find_element(By.CSS_SELECTOR, ".settings-input")
    token.clear()
    token.send_keys("test-token")
    driver.find_element(By.CSS_SELECTOR, "button[type='submit']").click()
    WebDriverWait(driver, 10).until(EC.text_to_be_present_in_element((By.TAG_NAME, "main"), "Không lưu được token"))
    assert "Đã lưu" not in driver.find_element(By.CSS_SELECTOR, "button[type='submit']").text
    assert token.get_attribute("value") == "test-token"
    assert theme(driver) == "graphite"
    driver.refresh()
    assert theme_control(driver).get_attribute("value") == "technical"


@pytest.mark.parametrize("failure", ["disconnect", "error"])
def test_live_evidence_closes_before_previous_snapshot_returns(driver, selenium_database, failure):
    seed_endpoints(selenium_database)
    driver.get(URL + "/#/modules/port-scanner")
    wait = WebDriverWait(driver, 10)
    wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "[data-testid='endpoint-evidence-btn']")))
    with sqlite3.connect(selenium_database) as connection:
        key, raw = connection.execute("SELECT whitelist_key,detail_json FROM scan_items WHERE scan_id='seed-v2' ORDER BY id LIMIT 1").fetchone()
        detail = json.loads(raw)
        detail["owners"][0].update(name="Live owner.exe", exe="C:\\Live\\live.exe")
        connection.execute("INSERT INTO scans (id,module_id,status,started_at,partial_result) VALUES ('seed-live','port-scanner','running','2026-10-25 00:00:00',0)")
    driver.execute_script("""
      window.WebSocket=class extends WebSocket {constructor(...args){super(...args);if(this.url.includes('/ws/scan/'))window.__liveSocket=this;}};
      const original=window.fetch;
      window.fetch=(url,init)=>String(url).endsWith('/port-scanner/scan') && init?.method==='POST'
        ? Promise.resolve(new Response(JSON.stringify({success:true,data:{scan_id:'seed-live'},error:null}),{status:200}))
        : original(url,init);
    """)
    try:
        driver.find_element(By.CSS_SELECTOR, "[data-testid='scan-button']").click()
        wait.until(lambda d: d.execute_script("return window.__liveSocket?.readyState===1"))
        driver.execute_script("window.__liveSocket.dispatchEvent(new MessageEvent('message',{data:JSON.stringify({type:'item_found',item:arguments[0]})}));", {"whitelist_key": key, "severity": "warning", "title": "Live endpoint", "detail": detail, "is_new": False})
        wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "[data-testid='endpoint-evidence-btn']"))).click()
        assert "Live owner.exe" in driver.find_element(By.CSS_SELECTOR, "dialog[open]").text
        if failure == "disconnect":
            driver.execute_script("window.__liveSocket.close()")
        else:
            driver.execute_script("window.__liveSocket.dispatchEvent(new MessageEvent('message',{data:JSON.stringify({type:'error',code:'TEST_LIVE_FAILED',message:'Lượt thử nghiệm thất bại'})}));")
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "[data-testid='error-banner']")))
        wait.until(EC.invisibility_of_element_located((By.CSS_SELECTOR, "dialog[open].evidence-drawer")))
        assert driver.find_element(By.CSS_SELECTOR, "[data-testid='retry-btn']").is_enabled()
    finally:
        with sqlite3.connect(selenium_database) as connection:
            connection.execute("UPDATE scans SET status='error' WHERE id='seed-live'")


@pytest.mark.parametrize("module", ["port-scanner", "firewall-check"])
def test_compact_inventory_preserves_sort_choices(driver, selenium_database, module):
    if module == "port-scanner":
        seed_endpoints(selenium_database)
        label, expected = "Giao thức", "UDP"
    else:
        seed_firewall(selenium_database)
        with sqlite3.connect(selenium_database) as connection:
            raw = connection.execute("SELECT detail_json FROM scan_items WHERE whitelist_key='demo-rule'").fetchone()[0]
            detail = json.loads(raw)
            detail.update(name="demo-block", action="Block")
            connection.execute("INSERT INTO scan_items (scan_id,module_id,whitelist_key,severity,title,detail_json,is_new) VALUES ('theme-firewall','firewall-check','demo-block','safe','Block rule',?,0)", (json.dumps(detail),))
        label, expected = "Hành động", "Block"
    driver.get(URL + "/#/modules/" + module)
    WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.TAG_NAME, "table")))
    button = driver.find_element(By.XPATH, f"//th//button[contains(.,'{label}')]")
    button.click()
    button.click()
    assert expected in driver.find_element(By.CSS_SELECTOR, "tbody tr").text
