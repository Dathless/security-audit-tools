# Current implementation note

Status checked against main on 2026-10-24: use the existing backend/module tests as the executable source of truth. The [Firewall/Nmap report](reports/firewall-check-nmap-removal.md) records the completed verification; [Startup Programs](../plans/startup-programs.md) has a separate, unexecuted checklist. Historical estimates and test targets below do not represent current coverage or a new test run.

Nmap execution and `_nmap_ports` are retired. Replace their cases below with legacy `scan_mode: nmap` conversion to psutil and blocked Nmap import. Active tests are `tests/test_config_scanner.py`, `modules/port_scanner/tests/test_scanner.py`, and `modules/firewall_check/tests/`. Firewall coverage includes all risk rules, validated evidence, singleton/empty results, Unicode, unsupported platforms, permissions, timeout, REST/token isolation, pagination, WebSocket/replay, and failed-scan diff recovery. UI acceptance lives in `tests/test_selenium_firewall.py` and the existing Selenium suites. Earlier Nmap-specific entries below are superseded; historical test reports remain unchanged.

# Unit Test Plan — Security Audit Tool (Backend)

## 1. Mục đích

Tài liệu này lên kế hoạch triển khai **unit test** cho backend Security Audit
Tool, bao gồm:

- **Unit test hàm đơn lẻ**: kiểm tra từng function/method biệt lập.
- **Integration test (feature cluster)**: kiểm tra cụm chức năng — nhiều hàm,
  nhiều lớp (API → executor → scanner → DB → event_bus → WebSocket) kết nối
  với nhau hoàn thành 1 luồng nghiệp vụ.

Tài liệu phân tích khoảng trống hiện tại (78 test đã pass) và bổ sung các
test cần thiết, ưu tiên theo mức độ quan trọng.

---

## 2. Tổng quan hiện trạng

### 2.1 File test hiện có

| File | Số test | Phạm vi |
|------|---------|---------|
| `tests/test_api.py` | 25 | Auth, Health, Module list, Scan API, History, Whitelist CRUD, Validation, Security |
| `tests/test_event_bus.py` | 7 | Pub/sub, wildcard `*`/`#`, unsubscribe, failure isolation |
| `tests/test_registry_architecture.py` | 4 | Architecture isolation, discovery failure, duplicate ID |
| `tests/test_scan_integration.py` | 12 | Lifecycle, Diff matrix, Whitelist override, DB rollback, Error, Concurrency |
| `tests/test_scheduler.py` | 3 | No schedule, register job, job triggers dispatch |
| `tests/test_websocket.py` | 7 | Connect, events sequence, replay, multi-subscriber, global channel |
| `modules/port_scanner/tests/test_scanner.py` | 20 | Severity matrix, process edge cases, nmap fallback, whitelist override |
| **Tổng** | **78** | |

### 2.2 Khoảng trống cần bổ sung

| Nhóm | Hiện trạng | Cần thêm |
|------|-----------|----------|
| Config (`core/config.py`) | Chưa có test riêng | Unit test `Config`, `ModuleSettings.from_config`, `ensure_local_token` |
| Envelope (`api/envelope.py`) | Được gián tiếp test qua API | Unit test trực tiếp `ok()`, `fail()` |
| Executor helpers | Được test gián qua integration | Unit test `_mark_failed`, `_previous_scan`, `_keys_of_scan`, `_whitelist_keys` |
| Scanner utilities | `_build_summary`, `_nmap_ports` chưa test trực tiếp | Unit test |
| Database utilities | `now_iso`, `dt_to_iso` chưa test | Unit test |
| Cluster: Whitelist lifecycle | Test lẻ tẻ | Integration test chu trình đầy đủ |
| Cluster: Diff engine | Có fixture matrix | Bổ sung edge cases |
| Cluster: Error recovery | Có cơ bản | Bổ sung phân loại ScanError vs generic |
| Cluster: Config → Scanner | Chưa có | Integration test config ảnh hưởng đến scanner behavior |

---

## 3. Kế hoạch Unit Test — Hàm đơn lẻ

### 3.1 `core/config.py` — Tests cho Config

**File mới:** `tests/test_config.py`

| ID | Test case | Hàm cần test | Mô tả | Priority |
|----|-----------|--------------|-------|----------|
| UT-CONFIG-001 | `Config` load từ file YAML | `Config.__init__` | Tạo file YAML tạm, truyền path → Config đọc đúng giá trị | P1 |
| UT-CONFIG-002 | `Config` với file không tồn tại | `Config.__init__` | Path không có file → dùng default values, không crash | P1 |
| UT-CONFIG-003 | `Config.module()` unknown module | `Config.module` |传入 module_id không tồn tại → trả `ModuleSettings(enabled=False)` | P1 |
| UT-CONFIG-004 | `Config.module()` known module | `Config.module` |传入 module_id có trong config → trả đúng settings | P1 |
| UT-CONFIG-005 | `ensure_local_token` khi chưa có token | `Config.ensure_local_token` | Token rỗng → generate token mới, persist vào file | P0 |
| UT-CONFIG-006 | `ensure_local_token` khi đã có token | `Config.ensure_local_token` | Token đã tồn tại → trả token đó, không ghi đè | P0 |
| UT-CONFIG-007 | `ModuleSettings.from_config` đầy đủ | `ModuleSettings.from_config` | Dict có `enabled`, `schedule`, extra keys → parse đúng | P1 |
| UT-CONFIG-008 | `ModuleSettings.from_config` rỗng | `ModuleSettings.from_config` | Dict rỗng/None → default `enabled=True`, `schedule=None` | P1 |
| UT-CONFIG-009 | `ModuleSettings.get()` key tồn tại | `ModuleSettings.get` | `get("scan_mode", "socket")` → trả giá trị từ extra | P2 |
| UT-CONFIG-010 | `ModuleSettings.get()` key không tồn tại | `ModuleSettings.get` | Key không có → trả default | P2 |

### 3.2 `api/envelope.py` — Tests cho Envelope

**File mới:** `tests/test_envelope.py`

| ID | Test case | Hàm cần test | Mô tả | Priority |
|----|-----------|--------------|-------|----------|
| UT-ENV-001 | `ok()` với dict | `ok` | `ok({"key": "val"})` → `{success: true, data: {...}, error: null}` | P1 |
| UT-ENV-002 | `ok()` với list | `ok` | `ok([1,2,3])` → data là list | P2 |
| UT-ENV-003 | `ok()` với None | `ok` | `ok(None)` → `data: null` | P2 |
| UT-ENV-004 | `fail()` tạo error envelope | `fail` | `fail("CODE", "msg")` → `{success: false, data: null, error: {code, message}}` | P1 |
| UT-ENV-005 | `fail()` error code đúng | `fail` | Kiểm tra `error.code` = giá trị truyền vào | P1 |

### 3.3 `storage/db.py` — Tests cho DB utilities

**File mới:** `tests/test_db_utils.py`

| ID | Test case | Hàm cần test | Mô tả | Priority |
|----|-----------|--------------|-------|----------|
| UT-DB-001 | `now_iso()` format | `now_iso` | Kết quả match pattern `%Y-%m-%dT%H:%M:%S.%fZ` | P2 |
| UT-DB-002 | `dt_to_iso()` với datetime | `dt_to_iso` | Truyền datetime → trả ISO string đúng format | P2 |
| UT-DB-003 | `dt_to_iso()` với None | `dt_to_iso` | Truyền None → trả None | P2 |
| UT-DB-004 | `Database.session_scope` commit | `Database.session_scope` | Operation thành công → data persist | P1 |
| UT-DB-005 | `Database.session_scope` rollback on error | `Database.session_scope` | Exception giữa chừng → rollback, data không persist | P1 |
| UT-DB-006 | `Database.create_all` tạo bảng | `Database.create_all` | Gọi create_all → tất cả bảng tồn tại | P1 |

### 3.4 `core/executor.py` — Tests cho executor helpers

**File mới:** `tests/test_executor_helpers.py`

| ID | Test case | Hàm cần test | Mô tả | Priority |
|----|-----------|--------------|-------|----------|
| UT-EXEC-001 | `_mark_failed` cập nhật status | `_mark_failed` | Scan record tồn tại → status = "error", error_message set | P0 |
| UT-EXEC-002 | `_mark_failed` scan không tồn tại | `_mark_failed` | Scan record không có → không crash, không exception | P1 |
| UT-EXEC-003 | `_previous_scan` trả scan liền trước | `_previous_scan` | Có 2 scan → trả scan cũ hơn (không tính scan hiện tại) | P0 |
| UT-EXEC-004 | `_previous_scan` không có scan trước | `_previous_scan` | Scan đầu tiên → trả None | P0 |
| UT-EXEC-005 | `_previous_scan` exclude scan_id hiện tại | `_previous_scan` |传入 exclude_scan_id → scan đó bị loại khỏi kết quả | P1 |
| UT-EXEC-006 | `_keys_of_scan` trả đúng keys | `_keys_of_scan` | Scan có 3 items → trả set 3 whitelist_key | P0 |
| UT-EXEC-007 | `_keys_of_scan` scan rỗng | `_keys_of_scan` | Scan không có items → trả set rỗng | P1 |
| UT-EXEC-008 | `_whitelist_keys` trả đúng keys | `_whitelist_keys` | Có 2 entries → trả set 2 key | P0 |
| UT-EXEC-009 | `_whitelist_keys` whitelist rỗng | `_whitelist_keys` | Không có entry → trả set rỗng | P1 |
| UT-EXEC-010 | `_whitelist_keys` phân biệt module | `_whitelist_keys` | Module A có key X, Module B có key X → query module A chỉ trả key X của A | P1 |

### 3.5 `modules/port_scanner/scanner.py` — Tests cho utilities

**File:** `modules/port_scanner/tests/test_scanner.py` (bổ sung)

| ID | Test case | Hàm cần test | Mô tả | Priority |
|----|-----------|--------------|-------|----------|
| UT-SC-001 | `_build_summary` đúng counts | `_build_summary` | List items có 3 danger, 2 warning, 5 safe → summary đúng | P1 |
| UT-SC-002 | `_build_summary` list rỗng | `_build_summary` | Items rỗng → `{total_open:0, danger:0, warning:0, safe:0}` | P1 |
| UT-SC-003 | `_nmap_ports` với risky ports > 1024 | `_nmap_ports` | risky = {4444, 8080} → output chứa `1-1024,4444,8080` | P1 |
| UT-SC-004 | `_nmap_ports` không có risky > 1024 | `_nmap_ports` | risky = {} hoặc all ≤ 1024 → output = `1-1024` | P2 |
| UT-SC-005 | `_build_summary` mix severities | `_build_summary` | Items hỗn hợp → count chính xác từng loại | P1 |

### 3.6 `core/event_bus.py` — Tests cho `_match` (bổ sung)

**File:** `tests/test_event_bus.py` (bổ sung)

| ID | Test case | Hàm cần test | Mô tả | Priority |
|----|-----------|--------------|-------|----------|
| UT-EV-001 | `_match` exact match | `_match` | `"scan.abc.progress"` match `"scan.abc.progress"` | P1 |
| UT-EV-002 | `_match` `*` sai số segment | `_match` | `"scan.progress"` không match `"scan.abc.progress"` (2 segment vs 3) | P1 |
| UT-EV-003 | `_match` `#` cuối | `_match` | `"scan.#"` match `"scan.abc.progress"` | P1 |
| UT-EV-004 | `_match` không match | `_match` | `"scan.abc.progress"` không match `"scan.abc.error"` | P1 |

---

## 4. Kế hoạch Integration Test — Feature Clusters

Đây là phần quan trọng nhất: kiểm tra cụm chức năng nhiều hàm, nhiều lớp
làm việc cùng nhau.

### 4.1 Cluster: Whitelist Lifecycle (Toàn chu trình)

**File mới:** `tests/test_whitelist_lifecycle.py`

**Luồng kiểm tra:** Tạo whitelist → Scan → Severity override → Xoá whitelist
→ Scan lại → Severity khôi phục

| ID | Test case | Mô tả | Priority |
|----|-----------|-------|----------|
| CL-WL-001 | Whitelist override danger → safe | Tạo whitelist key `4444:proc` → Scan thấy port 4444 → severity = safe (không phải danger) | P0 |
| CL-WL-002 | Whitelist override warning → safe | Tạo whitelist key cho port bind 0.0.0.0 → Scan → severity = safe | P0 |
| CL-WL-003 | Remove whitelist khôi phục severity | Whitelist exist → scan = safe → remove whitelist → scan lại = danger/warning gốc | P0 |
| CL-WL-004 | Whitelist không ảnh hưởng item khác | Whitelist key `80:nginx` → port 4444 vẫn giữ severity gốc | P1 |
| CL-WL-005 | Whitelist persists qua 3 lần scan | Scan #1 (danger) → whitelist → Scan #2 (safe) → Scan #3 (vẫn safe) | P1 |
| CL-WL-006 | Whitelist ID không duplicate | Thêm cùng key 2 lần qua API → chỉ 1 record, HTTP 400 | P1 |

**Kỹ thuật:** Dùng `FakePsutil` với connections xác định, chạy `execute_scan`
thật qua executor, query DB để assert severity.

### 4.2 Cluster: Diff Engine (Xuất hiện / Biến mất)

**File:** `tests/test_scan_integration.py` (bổ sung)

| ID | Test case | Mô tả | Priority |
|----|-----------|-------|----------|
| CL-DIFF-001 | Scan đầu tiên: mọi item là `appeared` | Không có scan trước → `scan_diff_log` chứa tất cả keys với `change_type=appeared` | P0 |
| CL-DIFF-002 | Scan giống hệt: không diff log | Scan #1 = {80, 443} → Scan #2 = {80, 443} → `scan_diff_log` rỗng | P0 |
| CL-DIFF-003 | Port mới xuất hiện | Scan #1 = {80} → Scan #2 = {80, 443} → 443 có diff log `appeared` | P0 |
| CL-DIFF-004 | Port biến mất | Scan #1 = {80, 443} → Scan #2 = {80} → 443 có diff log `disappeared` | P0 |
| CL-DIFF-005 | Mix xuất hiện + biến mất | Scan #1 = {80, 443} → Scan #2 = {80, 8080} → 443 disappeared, 8080 appeared | P0 |
| CL-DIFF-006 | `is_new` flag đúng trên items | Scan #2 có port mới → `is_new=True` cho port đó, `is_new=False` cho port cũ | P0 |
| CL-DIFF-007 | Diff log có scan_id đúng | Diff log entry có `scan_id` = scan hiện tại (không phải scan trước) | P1 |
| CL-DIFF-008 | Diff qua 3 lần scan | Scan #1 = {80} → #2 = {80, 443} → #3 = {80} → log có appeared (scan#2) + disappeared (scan#3) | P1 |

### 4.3 Cluster: Scan Lifecycle End-to-End

**File:** `tests/test_scan_lifecycle.py` (mới)

**Luồng:** POST /scan → executor chạy → DB persist → query lại API

| ID | Test case | Mô tả | Priority |
|----|-----------|-------|----------|
| CL-LC-001 | Scan tạo record `status=running` ngay | POST scan → query DB ngay → status = "running" | P0 |
| CL-LC-002 | Scan hoàn thành → `status=done` | Chờ executor xong → query DB → status = "done", summary_json có | P0 |
| CL-LC-003 | Scan items persist đúng | Scan xong → query `scan_items` → mỗi item có `severity`, `title`, `detail_json`, `whitelist_key` | P0 |
| CL-LC-004 | Scan summary đúng | Port 4444(danger) + 80(safe) → summary `{danger:1, warning:0, safe:1, total_open:2}` | P0 |
| CL-LC-005 | Query history sau scan | Scan xong → GET `/scans` → list chứa scan đó | P0 |
| CL-LC-006 | Query latest scan | Scan xong → GET `/scans/latest` → trả scan đó | P0 |
| CL-LC-007 | Query scan detail | Scan xong → GET `/scans/{id}` → có items array | P0 |
| CL-LC-008 | `partial_result` đúng khi permission denied | `FakePsutil(deny_net=True)` → scan xong → `partial_result=True` | P0 |
| CL-LC-009 | `started_at` < `finished_at` | Scan xong → timestamp hợp lệ | P1 |

### 4.4 Cluster: Error Recovery (Lỗi Scanner)

**File:** `tests/test_error_recovery.py` (mới)

| ID | Test case | Mô tả | Priority |
|----|-----------|-------|----------|
| CL-ERR-001 | Scanner raise `ScanError` → error state | Scanner ném `ScanError("CODE", "msg")` → DB status="error", error_message="msg" | P0 |
| CL-ERR-002 | Scanner raise generic exception → `SCAN_FAILED` | Scanner ném `RuntimeError("boom")` → DB status="error", error_message chứa "boom" | P0 |
| CL-ERR-003 | ScanError → WebSocket error event | ScanError → event_bus publish `{type:error, code:"CODE"}` | P0 |
| CL-ERR-004 | Generic exception → WS error event code = `SCAN_FAILED` | RuntimeError → event có `code="SCAN_FAILED"` | P0 |
| CL-ERR-005 | Error scan không có items trong DB | Scanner fail → `scan_items` rỗng (không persist item nào) | P1 |
| CL-ERR-006 | Error scan không có summary | Scanner fail → `summary_json` = None | P1 |
| CL-ERR-007 | Lỗi DB khi persist → rollback | Mock DB session.commit() raise → scan status vẫn "running" hoặc "error", không half-written | P1 |
| CL-ERR-008 | Scanner fail không crash app | Gọi `execute_scan` với scanner lỗi → không có exception thoát ra ngoài | P0 |

### 4.5 Cluster: Realtime Pipeline (Executor → EventBus → WebSocket)

**File:** `tests/test_realtime_pipeline.py` (mới)

| ID | Test case | Mô tả | Priority |
|----|-----------|-------|----------|
| CL-RT-001 | Progress events arrives at WS client | `execute_scan` chạy → WS client nhận `{type:progress}` với `current`/`total` tăng dần | P0 |
| CL-RT-002 | Item found events arrive at WS client | Scanner tìm thấy port → WS client nhận `{type:item_found, item:{severity, title, ...}}` | P0 |
| CL-RT-003 | Done event arrives at WS client | Scan xong → WS client nhận `{type:done, scan_id, summary}` | P0 |
| CL-RT-004 | Error event arrives at WS client | Scanner fail → WS client nhận `{type:error, code, message}` | P0 |
| CL-RT-005 | Event order: progress → item → done | Thu thập events từ WS → assert thứ tự đúng | P0 |
| CL-RT-006 | Late client receives replay | Scan done rồi → client connect WS → nhận done event với `replay:true` | P0 |
| CL-RT-007 | Two clients both receive events | 2 WS connections cùng scan → cả 2 nhận cùng events | P1 |
| CL-RT-008 | Global channel receives done | `/ws/events` → nhận done từ scan bất kỳ | P1 |
| CL-RT-009 | Progress message format | Assert `progress` event có `current`, `total`, `message` (không thiếu field) | P1 |

### 4.6 Cluster: Module Discovery → Registration → API

**File:** `tests/test_module_pipeline.py` (mới)

| ID | Test case | Mô tả | Priority |
|----|-----------|-------|----------|
| CL-MOD-001 | Module discovered at startup | `discover_modules()` trả dict chứa `port-scanner` | P0 |
| CL-MOD-002 | Module router included in app | App có endpoint `/api/v1/modules/port-scanner/scan` | P0 |
| CL-MOD-003 | GET /modules trả module đã discover | GET `/api/v1/modules` → list chứa `port-scanner` với `display_name` đúng | P0 |
| CL-MOD-004 | Module manifest có đủ fields | Mỗi manifest trong registry có `id`, `display_name`, `version`, `scanner_cls` | P1 |
| CL-MOD-005 | Module enabled/disabled reflect config | Config `enabled: true` → module appear trong list; `enabled: false` → không appear | P1 |

### 4.7 Cluster: Config → Scanner Behavior

**File:** `tests/test_config_scanner.py` (mới)

| ID | Test case | Mô tả | Priority |
|----|-----------|-------|----------|
| CL-CS-001 | Custom risky ports từ config | Config `known_risky_ports: [22, 8080]` → scanner classify 22 = danger, 4444 = safe | P0 |
| CL-CS-002 | Default risky ports khi config rỗng | Config không có `known_risky_ports` → dùng default [4444, 1337, 31337] | P1 |
| CL-CS-003 | Socket mode | Config `scan_mode: socket` → scanner dùng `_scan_socket` | P1 |
| CL-CS-004 | Nmap mode khi nmap available | Config `scan_mode: nmap` + nmap cài → scanner dùng `_scan_nmap` | P2 |

### 4.8 Cluster: Scheduler → Scan → Completion

**File:** `tests/test_scheduler_lifecycle.py` (mới)

| ID | Test case | Mô tả | Priority |
|----|-----------|-------|----------|
| CL-SCH-001 | Scheduler không có job khi schedule=None | Module không có default_schedule → APScheduler không có job | P1 |
| CL-SCH-002 | Scheduler có job khi schedule set | Module có `default_schedule="* * * * *"` → job registered trong APScheduler | P1 |
| CL-SCH-003 | Scheduled job gọi dispatch_scan | Mock APScheduler trigger job → `dispatch_scan` được gọi với manifest đúng | P1 |

---

## 5. Matrix phân bổ theo Priority

### 5.1 P0 — Phải có trước khi review test suite

| Nhóm | Số test P0 | File |
|------|-----------|------|
| Config `ensure_local_token` | 2 | `tests/test_config.py` |
| Executor helpers (`_mark_failed`, `_previous_scan`, `_keys_of_scan`, `_whitelist_keys`) | 4 | `tests/test_executor_helpers.py` |
| Cluster: Whitelist lifecycle | 3 | `tests/test_whitelist_lifecycle.py` |
| Cluster: Diff engine | 5 | `tests/test_scan_integration.py` |
| Cluster: Scan lifecycle E2E | 7 | `tests/test_scan_lifecycle.py` |
| Cluster: Error recovery | 4 | `tests/test_error_recovery.py` |
| Cluster: Realtime pipeline | 5 | `tests/test_realtime_pipeline.py` |
| Cluster: Module discovery → API | 3 | `tests/test_module_pipeline.py` |
| Cluster: Config → Scanner | 1 | `tests/test_config_scanner.py` |
| **Tổng P0** | **34** | |

### 5.2 P1 — Nên có trước production

| Nhóm | Số test P1 | File |
|------|-----------|------|
| Config (tổng hợp) | 6 | `tests/test_config.py` |
| Envelope | 4 | `tests/test_envelope.py` |
| DB utilities | 5 | `tests/test_db_utils.py` |
| Executor helpers (edge cases) | 6 | `tests/test_executor_helpers.py` |
| Scanner utilities | 5 | `modules/port_scanner/tests/test_scanner.py` |
| EventBus `_match` (edge cases) | 4 | `tests/test_event_bus.py` |
| Cluster: Whitelist lifecycle (edge) | 3 | `tests/test_whitelist_lifecycle.py` |
| Cluster: Diff engine (edge) | 3 | `tests/test_scan_integration.py` |
| Cluster: Scan lifecycle (edge) | 1 | `tests/test_scan_lifecycle.py` |
| Cluster: Error recovery (edge) | 3 | `tests/test_error_recovery.py` |
| Cluster: Realtime pipeline (edge) | 3 | `tests/test_realtime_pipeline.py` |
| Cluster: Module pipeline (edge) | 2 | `tests/test_module_pipeline.py` |
| Cluster: Config → Scanner (edge) | 1 | `tests/test_config_scanner.py` |
| Cluster: Scheduler lifecycle | 3 | `tests/test_scheduler_lifecycle.py` |
| **Tổng P1** | **54** | |

### 5.3 P2 — Cải thiện dài hạn

| Nhóm | Số test P2 | File |
|------|-----------|------|
| Config (extra keys) | 2 | `tests/test_config.py` |
| Envelope (None/list) | 2 | `tests/test_envelope.py` |
| Scanner utilities (edge) | 1 | `modules/port_scanner/tests/test_scanner.py` |
| Cluster: Config → Scanner (nmap) | 1 | `tests/test_config_scanner.py` |
| **Tổng P2** | **6** | |

---

## 6. Tổng kết

| Phân loại | Số test hiện tại | Cần thêm | Tổng sau |
|-----------|-----------------|---------|---------|
| Unit test hàm đơn lẻ | 0 (chưa có file riêng) | 40 | 40 |
| Integration test cluster | 78 (một phần) | 54 | 132 |
| **Tổng** | **78** | **94** | **172** |

---

## 7. File test mới cần tạo

| File | Nội dung chính |
|------|---------------|
| `tests/test_config.py` | Config load, module lookup, ensure_local_token |
| `tests/test_envelope.py` | `ok()`, `fail()` |
| `tests/test_db_utils.py` | `now_iso`, `dt_to_iso`, `session_scope` |
| `tests/test_executor_helpers.py` | `_mark_failed`, `_previous_scan`, `_keys_of_scan`, `_whitelist_keys` |
| `tests/test_whitelist_lifecycle.py` | Chu trình whitelist đầy đủ |
| `tests/test_scan_lifecycle.py` | E2E scan lifecycle qua API + executor |
| `tests/test_error_recovery.py` | ScanError, generic exception, DB failure |
| `tests/test_realtime_pipeline.py` | Executor → EventBus → WebSocket |
| `tests/test_module_pipeline.py` | Discovery → Registration → API |
| `tests/test_config_scanner.py` | Config ảnh hưởng behavior scanner |
| `tests/test_scheduler_lifecycle.py` | Scheduler → scan completion |

---

## 8. File test hiện có cần bổ sung

| File | Bổ sung |
|------|---------|
| `tests/test_scan_integration.py` | Diff edge cases (CL-DIFF-005..008) |
| `tests/test_event_bus.py` | `_match` edge cases |
| `modules/port_scanner/tests/test_scanner.py` | `_build_summary`, `_nmap_ports` |

---

## 9. Kỹ thuật mock/fake được sử dụng

| Thành phần | Kỹ thuật |
|------------|---------|
| `psutil.net_connections()` | `FakePsutil` từ `helpers.py` (đã có) |
| `psutil.Process(pid)` | `FakeProcess` từ `helpers.py` (đã có) |
| `nmap` module | `monkeypatch` / `unittest.mock.patch` |
| `shutil.which("nmap")` | `monkeypatch` trả `None` hoặc path giả |
| DB engine | SQLite trong `tmp_path_factory` (đã có trong `conftest.py`) |
| `asyncio.create_task` | Chạy `await execute_scan(...)` trực tiếp trong test (thay vì dispatch nền) |
| `event_bus` | Dùng `event_collector` fixture để thu events |
| `dispatch_scan` | Mock khi test API layer; gọi thật khi test integration |
| APScheduler | Mock `AsyncIOScheduler.start` và `add_job` |
| FastAPI TestClient | `httpx.AsyncClient` qua `TestClient` (đã có) |

---

## 10. Môi trường chạy test

```
Python 3.11+
pytest + pytest-asyncio (asyncio_mode = auto)
SQLite temporary (tmp_path_factory)
Fake/Mock psutil, nmap
Không cần: Internet, port thật, Nmap binary, DB production
Thời gian chạy mục tiêu: < 10s cho toàn suite
```

---

## 11. Definition of Done

Test suite được xem là đạt yêu cầu khi:

- [ ] Tất cả P0 test pass (34 test mới)
- [ ] Tất cả P1 test pass (54 test mới)
- [ ] Không có test flaky
- [ ] Không phụ thuộc external resources
- [ ] Coverage core business logic ≥ 90%
- [ ] Coverage diffing/whitelist rules ≥ 95%
- [ ] Coverage error paths ≥ 80%
