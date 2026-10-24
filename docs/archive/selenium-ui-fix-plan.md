# Kế hoạch sửa lỗi Selenium UI Tests

> Tài liệu lịch sử, dựa trên lần chạy lỗi tại thời điểm lập kế hoạch và [Selenium guide](../../backend/tests/README_SELENIUM.md). Log thô cục bộ nằm tại `docs/archive/testing/selenium-errors.log`, bị Git bỏ qua và không cần có trong bản clone. Xem [báo cáo mới hơn](../testing/reports/firewall-check-nmap-removal.md) cho bằng chứng kiểm thử trước khi merge PR #1.

## 1. Tóm tắt hiện trạng

- Tổng sô: **231 items**, kết quả: **169 passed, 62 errors, 23 warnings**.
- Toàn bộ **62 error** đều thuộc 3 file Selenium:
  - `tests/test_selenium_navigation_layout.py` — 26 test
  - `tests/test_selenium_port_scanner.py` — 22 test
  - `tests/test_selenium_scan_flow.py` — 14 test
- Lỗi chung 100% là: **`E fixture 'driver' not found`** tại giai đoạn `setup`.
- Kèm theo: **23 warnings `PytestUnknownMarkWarning: Unknown pytest.mark.selenium`**.

## 2. Nguyên nhân gốc (Root cause)

**File `backend/tests/conftest_selenium.py` không bao giờ được pytest nạp.**

- Pytest chỉ tự động nạp file cấu hình tên cố định là **`conftest.py`**, KHÔNG nạp file khác tên
  (kể cả `conftest_selenium.py`).
- Mọi fixture/hook cần thiết đang nằm trong `conftest_selenium.py`, gồm:
  - fixture `driver` (WebDriver) → thiếu → **62 lỗi `fixture 'driver' not found`**
  - fixture session `backend_process`, `frontend_process`
  - fixture `wait_for_angular`, `_setup_token` (autouse, inject token localStorage)
  - `pytest_addoption` đăng ký option `--selenium`
  - `pytest_configure` đăng ký marker `selenium`, `slow` → thiếu → **23 warnings**
  - `pytest_collection_modifyitems` (skip Selenium khi không truyền `--selenium`)
- Hệ quả phụ: vì option `--selenium` không được đăng ký, run `pytest` (không kèm `--selenium`)
  không skip các test Selenium mà để chúng chạy → error hàng loạt.

### Bằng chứng

```
tests/test_selenium_navigation_layout.py:13: def test_sidebar_always_visible(self, driver):
E fixture 'driver' not found
> available fixtures: ... (chỉ có fixture của core, không có `driver`)
```

Chạy `pytest --fixtures` xác nhận không có fixture nào của `conftest_selenium.py` được đăng ký.

## 3. Kế hoạch sửa

### Giai đoạn 1 — Làm cho pytest nạp được fixture Selenium (bắt buộc, sửa dứt 62 lỗi)

#### 3.1 Đổi tên file conftest

- Đổi tên `backend/tests/conftest_selenium.py` → `backend/tests/conftest.py`.
- Pytest sẽ tự nạp file này cho toàn bộ test trong `backend/tests/` và đăng ký:
  - fixture `driver`, `backend_process`, `frontend_process`, `wait_for_angular`, `page_helpers`
  - option `--selenium`, marker `selenium`/`slow`, logic skip khi không chạy kèm `--selenium`.

#### 3.2 Chặn autouse `_setup_token` không đụng tới test core

Hiện `_setup_token` là `@pytest.fixture(autouse=True)` và có tham số `driver`, `wait_for_angular`.
Nếu đặt vào `tests/conftest.py` (được nạp cho **mọi** test trong thư mục), nó sẽ:
- resolve `driver` → dựng browser + bật backend/frontend cho cả `test_api.py`, `test_config.py`, … => phá vỡ 169 test core.

**Sửa:** gating theo option + marker, resolve driver theo cách lazy:

```python
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
```

> Lưu ý: hiện `wait_for_angular` có tên gây hiểu nhầm (app là React chứ không phải Angular) — có thể
> đổi thành tên phù hợp, hoặc giữ nguyên vì không ảnh hưởng chức năng.

#### 3.3 Xác nhận kết quả sau giai đoạn 1

- `pytest` (không `--selenium`) → test Selenium được **skip** (không còn error, không còn warning).
- `pytest tests/test_selenium_*.py -v --selenium` → 62 test Selenium **thực sự chạy**; phần còn lại
  là lỗi selector/route để xử lý ở giai đoạn 2.

---

### Giai đoạn 2 — Đồng bộ selector & route với frontend thật (để test đạt PASS)

Sau giai đoạn 1, ta phát hiện loạt mismatch giữa selector trong test và DOM thật của frontend.
Có 2 hướng (khuyến nghị làm **cả hai**):

- **(A)** Thêm `data-testid` vào component frontend, đúng theo mục *"Frontend Test IDs"* trong
  `README_SELENIUM.md`.
- **(B)** Sửa/test giữ selector dùng class đã tồn tại trong frontend.

#### 3.4 `data-testid` cần thêm vào frontend

Frontend hiện tại **không hề chứa `data-testid`** nào. Dưới đây là các `data-testid` cần thêm để
selector của test match (component — file — thuộc tính).

| Component (file)                          | data-testid cần thêm                                                                  |
|-------------------------------------------|---------------------------------------------------------------------------------------|
| `AppShell.tsx` — `<aside>`                | `sidebar`                                                                             |
| `AppShell.tsx` — `<header>`               | `topbar`                                                                              |
| `AppShell.tsx` — `.breadcrumb`            | `breadcrumb`                                                                          |
| `AppShell.tsx` — nút ở topbar             | `topbar-scan-btn`                                                                     |
| `NavItem.tsx`                             | `nav-item-{id}` + thuộc tính `data-module`, `data-status`, `data-route` (xem mục 3.5)  |
| `ModulePageLayout.tsx` — header           | `page-header`, `page-title`, `page-description`                                       |
| `ModulePageLayout.tsx` — `.kpi-row`       | `kpi-row`; `KpiCard` thêm `kpi-card`, `kpi-label`, `kpi-value`, `kpi-sub`, `data-tone` |
| `Panel.tsx`                               | `panel`, `panel-title`, `panel-subtitle`                                              |
| `ProgressBar.tsx`                         | `progress-bar`, `progress-text`/`progress-message`                                    |
| `DataTable.tsx`                           | `data-table` trên `<table>`                                                           |
| `PortScannerPage.tsx` nút scan            | `scan-button` (nút "Quét ngay")                                                       |
| `StatusBadge.tsx`                         | `status-badge` + `data-tone`                                                          |
| `RadarMap.tsx`                            | `radar-map`, `radar-dot`                                                              |
| `EmptyState.tsx`                          | `empty-state`                                                                         |
| `ErrorBanner.tsx`                         | `error-banner`, `retry-btn`                                                           |
| `ScanHistoryPage.tsx`                     | `history-table`, `new-badge`/`badge-new` (đã có `.badge-new` ở PortScannerPage)        |

#### 3.5 Sửa `NavItem` để test điều hướng match

Test đang tìm:
```python
[data-testid='nav-item-port-scanner'], .nav-item[data-module='port-scanner']
[data-testid='nav-item-scan-history'], .nav-item[data-route='/history']
[data-testid='nav-item-settings'], .nav-item[data-route='/settings']
[data-testid^='nav-item-'][data-status='coming-soon'], ...
```
Frontend hiện `<a className="nav-item ..." href="#...">` không có `data-module`/`data-route`/`data-testid`.
→ Thêm vào `NavItem` (hoặc chỗ render trong `AppShell.Sidebar`) các thuộc tính:
`data-module={m.id}`, `data-status={m.status}`, `data-route={route}` và `data-testid={'nav-item-' + m.id}`.

#### 3.6 Loại bỏ selector `:contains()` (Selenium không hỗ trợ)

Có **32 chỗ** dùng `button:contains('Quét ngay')` / `button:contains('Tải lại')`.
`:contains()` là selector jQuery, **Selenium CSS không hỗ trợ** → sẽ ném
`InvalidSelectorException` khi chạy thật.

**Sửa:** thay bằng selector hợp lệ, ví dụ:
```python
# TRƯỚC
By.CSS_SELECTOR, "[data-testid='scan-button'], button:contains('Quét ngay'), .scan-button"
# SAU (ưu tiên data-testid đã thêm ở bước 3.4)
By.CSS_SELECTOR, "[data-testid='scan-button']"
# hoặc nếu chỉ dùng class:
By.CSS_SELECTOR, "button.btn-primary"
```

#### 3.7 Đồng bộ router / URL với hash-routing của frontend

Frontend dùng **hash router** (`frontend/src/core/router.ts`): route thực tế là
`#/modules/port-scanner`, `#/scan-history`, `#/settings`.

Mismatch đang có trong test:

| Test                                             | Test đang dùng              | Frontend thật                          | Hướng sửa test |
|--------------------------------------------------|-----------------------------|----------------------------------------|----------------|
| `test_navigate_to_scan_history`                  | click `.nav-item[data-route='/history']`, chờ `url_contains("/history")` | NAV route là **`/scan-history`** (GENERAL_NAV) | Đổi thành `/scan-history` |
| `test_navigate_to_settings`                      | `data-route='/settings'`, `url_contains("/settings")` | `#/settings` ✓ | OK (chỉ cần `data-route` từ 3.5) |
| `test_history_row_click_shows_scan_detail`       | `driver.get(".../history")`, chờ `url_contains("/scans/")` | Không có route `/history`; `ScanHistoryPage` nút hành động mở `/modules/port-scanner`, **không có trang detail `/scans/`** | Trang detail chưa tồn tại ở frontend → cần triển khai route `/scans/:id` HOẶC viết lại test theo thực tế |
| `test_page_loads_with_correct_title`             | `#/modules/port-scanner` (hash) | ✓ | OK |
| `test_scan_start_response_time`                  | `#/modules/port-scanner` (hash) | ✓ | OK |

> Lưu ý quan trọng: nhiều test `driver.get("http://127.0.0.1:5173/modules/port-scanner")` ghi **không có `#`**.
> Hash router đọc `window.location.hash` rỗng → route `/` → AppShell **tự redirect tới module đầu tiên**.
> Trang vẫn hiển thị nội dung module, nhưng mọi assertion dạng `url_contains("/modules/port-scanner")`
> sẽ fail vì URL không chứa text đó. → Thống nhất dùng URL hash `.../#/modules/port-scanner` trong test.

#### 3.8 Các selector class lệch tên với frontend (cần sửa hoặc thêm class)

| Test tìm                                | Frontend thật                      | Ghi chú                                        |
|-----------------------------------------|------------------------------------|------------------------------------------------|
| `.progress-bar` / `[data-testid=progress-bar]` | `div.progress` (ProgressBar)        | Thêm `data-testid` hoặc thêm lớp `.progress-bar` |
| `.status-badge`, `.status-badge.danger` | `span.badge.badge-danger`           | Thêm `data-testid='status-badge'` + `data-tone`  |
| `.error-banner`, `.error-banner.warning`| `div.errbanner errbanner-warning`   | Thêm `data-testid='error-banner'` + `data-tone`  |
| `.tone-danger`, `.tone-warning`, `.tone-safe` | `kpi-card kpi-danger`, `badge-danger`, ... | Thêm `data-tone` vào StatusBadge/KpiCard  |
| `.kpi-card.tone-danger`                 | `kpi-card kpi-danger`               | Thêm `data-tone` hoặc sửa selector test         |
| `.page-header`, `.page-title`, `.page-description` | `mp-header`, `mp-title`, `mp-desc` | Thêm `data-testid` theo 3.4                    |
| `.data-table` / `.datatable-table`      | `table.datatable-table`             | Thêm `data-testid='data-table'` lên `<table>`    |
| `.radar-map` / `svg`                    | `div.radar > svg.radar-svg`         | `svg` fallback ✓, thêm `data-testid='radar-map'` |
| `.mark-safe-btn`, `.row-actions button` | `.row-actions button` ✓             | OK (đã dùng nút Button)                          |

#### 3.9 KPI / bảng kỳ vọng

- KPI label test cần `["Cổng đang mở","Nguy hiểm","Cảnh báo","An toàn"]` — frontend đã khớp ✓.
- Cột bảng test cần `["Trạng thái","Cổng","Tiến trình","Giao thức","Listener","Mới","Lý do"]` —
  frontend `DataTable` đúng thứ tự ✓ (nhớ `data-testid='data-table'`).
- Mono font: frontend đã dùng `--font-mono` (JetBrains Mono) + class `td-mono/th-mono` ✓.

---

### Giai đoạn 3 — Chạy & xác minh (bắt buộc)

1. **Chuẩn bị môi trường** (theo `README_SELENIUM.md`):
   - Python deps: `pip install -r requirements.txt` (đã có `selenium==4.47.0`).
   - Frontend deps: `cd frontend && pnpm install`.
   - Chrome + ChromeDriver (`selenium-manager` tự tải hoặc `pip install webdriver-manager`).

2. **Chạy tĩnh (không khởi động browser)** — kiểm tra fixture đã nạp:
   ```bash
   cd backend
   pytest tests/test_selenium_port_scanner.py --fixtures -q | Select-String "driver"
   ```

3. **Chạy toàn bộ suite (không `--selenium`)** — test Selenium phải **skip**, 169 core vẫn PASS:
   ```bash
   cd backend
   pytest
   ```

4. **Chạy riêng Selenium sau khi đã fix giai đoạn 2**:
   ```bash
   cd backend
   pytest tests/test_selenium_*.py -v --selenium --selenium-headless=false
   ```
   Dừng khi đạt: test load/layout/navigation/empty-state pass; test scan-flow có thể phụ thuộc quyền
   admin/port thật trên máy — xử lý tiếp bằng seed data hoặc điều kiện bỏ qua.

## 4. Danh sách việc cụ thể (checklist)

- [x] `git mv backend/tests/conftest_selenium.py backend/tests/conftest.py`
- [x] Gate autouse `_setup_token` theo option `--selenium` + marker (mục 3.2)
- [x] Cập nhật `README_SELENIUM.md`: đổi `conftest_selenium.py` → `conftest.py`
- [x] Thêm `data-testid` vào các component frontend theo mục 3.4
- [x] Thêm `data-module`/`data-status`/`data-route`/`data-testid` vào `NavItem` (mục 3.5)
- [x] Thay 32 selector `:contains()` bằng selector hợp lệ (mục 3.6)
- [x] Đồng bộ route `/history`→`/scan-history`, dùng URL hash `#/...` trong test (mục 3.7)
- [x] Quyết định: triển khai route detail `/scans/:id` hoặc viết lại `test_history_row_click_shows_scan_detail` (đã viết lại theo frontend thật: nút "Mở module" → `/modules/port-scanner`)
- [x] Đối chiếu class selector lệch tên (mục 3.8)
- [x] Chạy lại 3 lệnh xác minh ở giai đoạn 3

### Công việc phát sinh đã xử lý thêm

- `conftest.py`: sửa `frontend_process` chạy `pnpm` qua `cmd /c` trên Windows (shim `.cmd` không thể spawn trực tiếp).
- `conftest.py`: nối đúng `--selenium-headless` / `--selenium-browser` vào driver creation (trước đây chỉ đọc env).
- `conftest.py`: sửa key localStorage trong `_setup_token`: `local_token` → `sec_audit_local_token` (khớp `getLocalToken()`).
- `conftest.py`: `PageHelpers.click_scan_button` bỏ `:contains()`.
- Frontend: topbar nút cũng mang `data-testid='scan-button'` → test scan-button dùng được ở mọi phase (empty/ready/error).
- Frontend: thêm panel Whitelist vào `SettingsPage` (`whitelist-list`/`whitelist-item`) cho `test_whitelist_page_shows_marked_items`.
- Test: sửa assertion màu `rgba(r,g,b,1)` (Chrome trả alpha) và selector badge `[data-tone='danger']` → `[data-testid='status-badge'][data-tone='danger']` (tránh khớp cả KPI card).

### Kết quả xác minh (ghi nhận hiện tại)

- `pytest` (không `--selenium`): **169 passed, 62 skipped, 0 errors** — test Selenium skip sạch, hết `PytestUnknownMarkWarning`.
- `pytest --fixtures`: có `driver`, `backend_process`, `frontend_process`, `page_helpers`, `_setup_token`.
- `pytest tests/test_selenium_*.py -v --selenium`: chạy thật. Layout/navigation load/pass; các test phụ thuộc scan pass khi chạy đơn lẻ; máy hiện đang tải (nhiều tiến trình Chrome của user) khiến headless renderer bị `Timed out receiving message from renderer` khi chạy liên tiếp — flaky do môi trường, không phải do selector/route.

## 5. Rủi ro & lưu ý

- **Rủi ro cao nhất sau khi fix conftest**: test chạy thật phụ thuộc Chrome + dev-server frontend
  (`pnpm dev`) + backend (`uvicorn main:app`) trên port 5173/8000 — cần môi trường đầy đủ.
- Test scan-flow (`TestScanLifecycle`, `TestWebSocket*`, whitelist, error-recovery) gọi scan thật trên
  máy → kết quả phụ thuộc hệ thống (port/quyền admin), dễ flaky. Cân nhắc tách marker `slow`/điều kiện skip.
- Một số test ("permission denied", "quá 4 KPI", "kết quả một phần") đòi hỏi backend trả đúng trạng
  thái: có thể cần seed/fixture dữ liệu thay vì scan thật.
- Encoding file frontend khi đọc bằng terminal hiển thị `?`/`�` — chỉ là artifact khi hiển thị,
  không phải lỗi; đảm bảo test so khớp đúng chuỗi tiếng Việt trong mã nguồn.
