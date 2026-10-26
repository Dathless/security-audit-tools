"""Firewall lifecycle/UI regressions using synthetic HTTP and socket observations."""
from pathlib import Path

import pytest
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait


SCRIPT = r"""(() => {
  const response = data => new Response(JSON.stringify({success:true, data, error:null}), {status:200});
  const scan = (id, status='done', seconds=20) => ({id, module_id:'firewall-check', status,
    started_at:new Date(Date.now()-seconds*1000).toISOString(),
    finished_at:status==='running' ? null : new Date().toISOString(), partial_result:false,
    summary:{total_profiles:1,total_rules:0,danger:0,warning:0,safe:1},
    items:[{id:11,title:'Synthetic '+id,severity:'safe',is_new:false,whitelist_key:'profile:Public',
      detail:{kind:'profile',name:'Public',enabled:true,active:true,default_inbound_action:'Block',
        default_outbound_action:'Allow',reasons:[],guidance:[]}}]});
  const f = window.__fw = {scan, latest:scan('previous'), exact:scan('new','running',0),
    history:[scan('previous')], posts:0, reads:[], sockets:[], holdLatest:false, holdExact:false};
  const nativeFetch = window.fetch.bind(window);
  window.fetch = async (url, init) => {
    const path = String(url);
    if (!path.includes('/modules/firewall-check/')) return nativeFetch(url, init);
    if (path.endsWith('/scan')) {
      f.posts++;
      if (f.holdPost) return new Promise((resolve,reject) => {
        f.resolvePost=() => resolve(response({scan_id:f.exact.id})); f.rejectPost=reject;
      });
      if (f.conflict) {f.latest=f.exact; return new Response(JSON.stringify({success:false,data:null,
        error:{code:'SCAN_ALREADY_RUNNING',message:'already running'}}), {status:409});}
      return response({scan_id:f.exact.id});
    }
    if (path.endsWith('/scans/latest')) {
      if (f.holdLatest) return new Promise(resolve => f.resolveLatest = data => resolve(response(data)));
      return response(f.latest);
    }
    if (path.includes('/scans?')) return response({items:f.history,page:1,page_size:20,total:f.history.length});
    f.reads.push(path.split('/').pop());
    if (f.failExact) throw new Error('synthetic offline');
    if (f.holdExact) return new Promise(resolve => f.resolveExact = data => resolve(response(data)));
    return response(f.exact);
  };
  const NativeSocket = window.WebSocket;
  window.WebSocket = class {
    constructor(url, protocols) {
      if (!url.includes('/ws/scan/')) return new NativeSocket(url, protocols);
      this.url = url; this.readyState = 1; f.sockets.push(this);
    }
    close() {this.readyState=3;}
    emit(message) {this.onmessage?.({data:JSON.stringify(message)});}
    disconnect() {this.onclose?.();}
  };
})();
"""


@pytest.fixture
def firewall_ui(driver):
    def open_page(setup=""):
        driver.implicitly_wait(0)
        driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {"source": SCRIPT + setup})
        driver.get("http://127.0.0.1:5173/#/modules/firewall-check")
        wait = WebDriverWait(driver, 12)
        wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "[data-testid='scan-button']")))
        return wait
    return open_page


def click_scan(driver):
    driver.find_element(By.CSS_SELECTOR, "[data-testid='scan-button']").click()


@pytest.mark.selenium
def test_firewall_unknown_progress_time_log_and_exact_completion(driver, firewall_ui):
    driver.execute_cdp_cmd("Emulation.setEmulatedMedia", {"features": [{"name": "prefers-reduced-motion", "value": "reduce"}]})
    wait = firewall_ui()
    wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "[data-testid='firewall-results']")))
    click_scan(driver)
    bar = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "[data-testid='progress-bar']")))
    assert bar.get_attribute("aria-valuenow") is None
    assert "0/0" not in bar.text and "0/1" not in bar.text
    assert driver.execute_script("return getComputedStyle(document.querySelector('.progress-fill')).animationName") == "none"
    timing = driver.find_element(By.CSS_SELECTOR, "[data-testid='firewall-timing']")
    assert "ước tính" in timing.text.lower()
    wait.until(lambda d: "1 giây" in d.find_element(By.CSS_SELECTOR, "[data-testid='firewall-timing']").text)
    driver.execute_script("__fw.sockets.at(-1).emit({type:'progress',current:1,total:4,message:'Đã đánh giá profile Domain.'});")
    wait.until(lambda d: d.find_element(By.CSS_SELECTOR, "[data-testid='progress-bar']").get_attribute("aria-valuenow") == "1")
    details = driver.find_element(By.CSS_SELECTOR, "[data-testid='firewall-log']")
    details.find_element(By.TAG_NAME, "summary").click()
    wait.until(lambda _: "Domain" in details.text)
    driver.set_window_size(1366, 1000)
    screenshot = Path(__file__).resolve().parents[1] / "logs" / "firewall-progress-synthetic.png"
    driver.save_screenshot(str(screenshot))
    driver.execute_script("__fw.sockets.at(-1).emit({type:'progress',current:4,total:4,message:'Đã đánh giá rule cuối.'});")
    assert not driver.find_elements(By.CSS_SELECTOR, "[data-testid='firewall-results']")
    driver.execute_script("for(let i=1;i<=150;i++) __fw.sockets.at(-1).emit({type:'progress',current:i,total:150,message:'Synthetic milestone '+i});")
    wait.until(lambda d: len(d.find_elements(By.CSS_SELECTOR, "[data-testid='firewall-log'] li")) == 100)
    assert "Synthetic milestone 150" in details.text
    driver.execute_script("__fw.exact=__fw.scan('new'); __fw.latest=__fw.scan('unrelated'); __fw.sockets.at(-1).emit({type:'done',scan_id:'new',summary:{}});")
    wait.until(lambda d: "Synthetic new" in d.find_element(By.CSS_SELECTOR, "[data-testid='firewall-results']").text)
    assert driver.execute_script("return __fw.reads.includes('new')")
    assert "Hoàn tất" in driver.find_element(By.CSS_SELECTOR, "[data-testid='firewall-log']").text
    entries = driver.find_elements(By.CSS_SELECTOR, "[data-testid='firewall-log'] li")
    assert len(entries) == 100 and "kết quả đã được lưu" in entries[-1].text


@pytest.mark.selenium
def test_firewall_stale_initial_load_cannot_replace_started_scan(driver, firewall_ui):
    wait = firewall_ui("__fw.holdLatest=true;")
    wait.until(lambda d: d.execute_script("return !!__fw.resolveLatest"))
    click_scan(driver)
    wait.until(lambda d: d.execute_script("return __fw.sockets.length === 1"))
    driver.execute_script("__fw.resolveLatest({...__fw.scan('old-error','error'),error_message:'stale failure'});")
    wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "[data-testid='progress-bar']")))
    assert not driver.find_elements(By.CSS_SELECTOR, "[data-testid='error-banner']")
    driver.execute_script("__fw.exact=__fw.scan('new'); __fw.sockets[0].emit({type:'done',scan_id:'new',summary:{}});")
    wait.until(lambda d: "Synthetic new" in d.find_element(By.CSS_SELECTOR, "[data-testid='firewall-results']").text)


@pytest.mark.selenium
def test_firewall_disconnect_keeps_guard_until_exact_terminal_and_retry(driver, firewall_ui):
    wait = firewall_ui()
    wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "[data-testid='firewall-results']")))
    click_scan(driver)
    wait.until(lambda d: d.execute_script("return __fw.sockets.length === 1"))
    driver.execute_script("__fw.oldCallback=__fw.sockets[0].onmessage; __fw.sockets[0].disconnect();")
    wait.until(lambda d: d.execute_script("return __fw.reads.length > 0"))
    click_scan(driver)
    assert driver.execute_script("return __fw.posts") == 1
    assert driver.find_elements(By.CSS_SELECTOR, "[data-testid='progress-bar']")
    driver.execute_script("__fw.exact={...__fw.scan('new','error'),error_message:'synthetic denied'};")
    wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "[data-testid='error-banner']")))
    assert "synthetic denied" in driver.find_element(By.CSS_SELECTOR, "[data-testid='error-banner']").text
    assert not driver.find_elements(By.CSS_SELECTOR, "[data-testid='firewall-results']")
    driver.execute_script("__fw.exact=__fw.scan('retry','running',0);")
    click_scan(driver)
    wait.until(lambda d: d.execute_script("return __fw.sockets.length === 2"))
    driver.execute_script("__fw.oldCallback?.({data:JSON.stringify({type:'error',code:'OLD',message:'stale socket error'})});")
    assert not driver.find_elements(By.CSS_SELECTOR, "[data-testid='error-banner']")
    assert driver.execute_script("return __fw.posts") == 2


@pytest.mark.selenium
def test_firewall_recovery_discloses_log_gaps_and_exceeded_estimate(driver, firewall_ui):
    wait = firewall_ui("__fw.latest=__fw.scan('new','running',40);")
    wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "[data-testid='progress-bar']")))
    wait.until(lambda d: "lâu hơn" in d.find_element(By.CSS_SELECTOR, "[data-testid='firewall-timing']").text.lower())
    details = driver.find_element(By.CSS_SELECTOR, "[data-testid='firewall-log']")
    details.find_element(By.TAG_NAME, "summary").click()
    assert "trước" in details.text.lower()


@pytest.mark.selenium
def test_firewall_conflict_recovers_existing_scan_without_fake_eta(driver, firewall_ui):
    wait = firewall_ui("__fw.latest=null; __fw.history=[]; __fw.conflict=true;")
    wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "[data-testid='empty-state']")))
    click_scan(driver)
    wait.until(lambda d: d.execute_script("return __fw.sockets.length === 1"))
    assert "Chưa đủ dữ liệu" in driver.find_element(By.CSS_SELECTOR, "[data-testid='firewall-timing']").text
    assert not driver.find_elements(By.CSS_SELECTOR, "[data-testid='error-banner']")
    click_scan(driver)
    assert driver.execute_script("return __fw.posts") == 1
    driver.execute_script("__fw.exact=__fw.scan('new'); __fw.sockets[0].disconnect();")
    wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "[data-testid='firewall-results']")))


@pytest.mark.selenium
def test_firewall_stale_reconciliation_cannot_overwrite_retry(driver, firewall_ui):
    wait = firewall_ui()
    wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "[data-testid='firewall-results']")))
    click_scan(driver)
    wait.until(lambda d: d.execute_script("return __fw.sockets.length === 1"))
    driver.execute_script("__fw.holdExact=true; __fw.oldCallback=__fw.sockets[0].onmessage; __fw.sockets[0].disconnect();")
    wait.until(lambda d: d.execute_script("return !!__fw.resolveExact"))
    driver.execute_script("__fw.oldCallback({data:JSON.stringify({type:'error',code:'DENIED',message:'denied'})});")
    wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "[data-testid='error-banner']")))
    driver.execute_script("__fw.holdExact=false; __fw.exact=__fw.scan('retry','running',0);")
    click_scan(driver)
    wait.until(lambda d: d.execute_script("return __fw.sockets.length === 2"))
    driver.execute_script("__fw.resolveExact(__fw.scan('new'));")
    assert driver.find_elements(By.CSS_SELECTOR, "[data-testid='progress-bar']")
    assert not driver.find_elements(By.CSS_SELECTOR, "[data-testid='firewall-results']")
    driver.execute_script("__fw.exact=__fw.scan('retry'); __fw.sockets[1].emit({type:'done',scan_id:'retry',summary:{}});")
    wait.until(lambda d: "Synthetic retry" in d.find_element(By.CSS_SELECTOR, "[data-testid='firewall-results']").text)


@pytest.mark.selenium
@pytest.mark.parametrize("outcome", ["success", "failure"])
def test_firewall_unmounted_post_preserves_other_module_busy_state(driver, firewall_ui, outcome):
    wait = firewall_ui()
    wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "[data-testid='firewall-results']")))
    driver.execute_script("__fw.holdPost=true;")
    click_scan(driver)
    wait.until(lambda d: d.execute_script("return !!__fw.rejectPost"))
    driver.find_element(By.CSS_SELECTOR, "[data-testid='nav-item-settings']").click()
    wait.until(EC.url_contains("/settings"))
    state = driver.execute_async_script("""
      const outcome=arguments[0];
      const done=arguments[arguments.length-1];
      import('/src/core/appStore.ts').then(store => {
        store.setScanningNow(true);
        if(outcome==='success') __fw.resolvePost();
        else __fw.rejectPost(new Error('late post failure'));
        setTimeout(() => done({busy:store.appStore.get().scanningNow,sockets:__fw.sockets.length}), 50);
      });
    """, outcome)
    assert state == {"busy": True, "sockets": 0}


@pytest.mark.selenium
def test_firewall_http_outage_keeps_guard_then_recovers(driver, firewall_ui):
    wait = firewall_ui()
    wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "[data-testid='firewall-results']")))
    click_scan(driver)
    wait.until(lambda d: d.execute_script("return __fw.sockets.length === 1"))
    driver.execute_script("__fw.failExact=true; __fw.sockets[0].disconnect();")
    wait.until(lambda d: "Chưa liên lạc" in d.find_element(By.CSS_SELECTOR, ".firewall-progress").text)
    click_scan(driver)
    assert driver.execute_script("return __fw.posts") == 1
    driver.execute_script("__fw.failExact=false; __fw.exact=__fw.scan('new');")
    wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "[data-testid='firewall-results']")))
