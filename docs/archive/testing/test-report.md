# Báo cáo kiểm thử — Security Audit Tool (Backend)

| Mục | Nội dung |
| --- | --- |
| **Dự án** | Security Audit Tool — Backend (FastAPI + Port Scanner module) |
| **Phạm vi** | Toàn bộ test suite backend (`tests/` + `modules/port_scanner/tests/`) |
| **Ngày chạy** | 2026-08-14 |
| **Người thực hiện** | Team phát triển / QA |
| **Trạng thái tổng thể** | **PASSED — 169/169 (100%)** |
| **Thời gian chạy** | ~4.9s (169 tests) |
| **Điều kiện** | Không phụ thuộc Internet / port thật / Nmap binary / DB production |

---

## 1. Tóm tắt điều hành

Test suite backend của Security Audit Tool hiện đạt **169 test pass trên tổng
số 169 (100%)**, bao gồm unit test, integration test, API contract test,
WebSocket realtime test và architecture test. Toàn bộ test chạy nhanh
(~5s), **deterministic** và không phụ thuộc vào hạ tầng bên ngoài — đạt yêu
cầu để chạy trong mỗi commit/PR.

Trong quá trình kiểm thử phát hiện và xử lý **1 test stale** liên quan tới
contract mới của `PortScannerModule._classify` (xem mục 6). Sau khi cập nhật,
toàn bộ suite xanh trở lại.

---

## 2. Mục tiêu kiểm thử

1. Xác nhận **tính đúng đắn chức năng** của từng thành phần: Config, Envelope,
   DB utils, Executor, Scanner, Event Bus, Scheduler, Whitelist, Diffing,
   WebSocket.
2. Đảm bảo **API contract** thống nhất: envelope `{success, data, error}`,
   mã lỗi ổn định, không leak dữ liệu nhạy cảm.
3. Đảm bảo **real-time pipeline** (Executor → Event Bus → WebSocket) đúng thứ
   tự và đủ sự kiện.
4. Đảm bảo **resilience**: scanner lỗi / DB lỗi / subscriber lỗi không làm sập
   toàn bộ hệ thống; transaction rollback đúng.
5. Đảm bảo **kiến trúc**: `core/` không import ngược `modules/`.
6. Đảm bảo **tính deterministic**: không phụ thuộc mạng, port thật, thời gian
   thực, thứ tự chạy.

---

## 3. Phạm vi kiểm thử

### 3.1 In-scope

| Nhóm | Thành phần |
| --- | --- |
| Authentication / Security | Token local, endpoint protection, secret leak, malformed request |
| REST API | Health, Modules, Scan, History, Whitelist, Pagination, Validation |
| Module Registry | Discovery, duplicate ID, failure isolation, architecture isolation |
| Port Scanner | Severity matrix, process edge cases, service/port mismatch, whitelist override, nmap fallback |
| Scan Lifecycle | running → done/error, persistence, summary, partial_result |
| Diffing | appeared/disappeared/is_new, persistence, nhiều lần scan |
| Whitelist | CRUD, override severity, uniqueness, lifecycle |
| WebSocket / Realtime | connect, progress/item_found/done/error, replay, multi-subscriber, global channel |
| Event Bus | pub/sub, wildcard, unsubscribe, failure isolation |
| Scheduler | no-schedule, register job, trigger dispatch |
| Error Handling | ScanError, generic exception, DB failure, concurrent scan, rollback |
| Config | load, defaults, module settings, ensure_local_token |
| DB utilities | now_iso, dt_to_iso, session_scope, create_all |

### 3.2 Out-of-scope

| Hạng mục | Lý do |
| --- | --- |
| E2E Frontend (React) | Cần hạ tầng Playwright/Cypress, ngoài phạm vi `./backend/tests/` |
| Rate limit / lockout (TC-SEC-002) | Hệ thống chưa triển khai tính năng |
| Whitelist cross-module (TC-WL-008) | Hiện chỉ có 1 module duy nhất |
| Scheduler timing thực tế (TC-SCHED-004) | Test timing APScheduler thật vi phạm nguyên tắc deterministic |
| Performance / stress test | Có thể tách thành bộ test riêng |

---

## 4. Chiến lược & phương pháp kiểm thử

| Lớp | Kỹ thuật | Số test |
| --- | --- | --- |
| **Unit test** | Test hàm đơn lẻ, không khởi động app | 75 |
| **API contract test** | TestClient, assert status/envelope/error code | 25 |
| **Integration test (feature cluster)** | Chạy thật executor + DB SQLite tạm | 46 |
| **WebSocket / Realtime test** | TestClient portal chạy scan trên đúng event loop | 16 |
| **Architecture test** | Đọc AST/text nguồn, kiểm tra import | 4 |
| **Nmap / fallback test** | Mock module `nmap` + `shutil.which` | 3 |

### 4.1 Nguyên tắc chống flaky

- Toàn bộ dữ liệu test đi qua **Fake/Mock**: `FakePsutil`, `FakeConn`,
  `FakeProcess` (trong `backend/helpers.py`), mock `nmap`, mock
  `AsyncIOScheduler.start`.
- Mỗi test dùng **DB SQLite tạm** (fixture `tmp_path_factory` + `clean_db`),
  không đụng DB production/development.
- WebSocket test chạy scan qua `client.portal.call(...)` trên đúng event loop
  của app → nhận event **deterministic**, không chờ real time.
- Scheduler test patch `AsyncIOScheduler.start` để không chạy event loop thật.
- Mỗi case diff chạy trên DB sạch riêng (`clean_db`) để không nhiễu case trước.

### 4.2 Cấu trúc test infrastructure

| Thành phần | Vai trò |
| --- | --- |
| `backend/conftest.py` | Fixtures `clean_db`, `client`, `client_no_raise`, `patch_psutil`, `port_manifest`, `event_collector` |
| `backend/helpers.py` | `FakeConn`, `FakeProcess`, `FakePsutil`, `fake_conn`, `fake_process` dùng chung |
| `backend/pytest.ini` | `asyncio_mode = auto`, `testpaths = tests modules` |

---

## 5. Môi trường kiểm thử

```text
OS              : win32
Python          : 3.11.15
pytest          : 9.1.1
pluggy          : 1.6.0
plugins         : anyio-4.14.2, pytest-asyncio 1.4.0 (asyncio_mode = auto)
HTTP client     : FastAPI TestClient (httpx)
Database        : SQLite tạm (tmp_path_factory)
External deps   : psutil / nmap đều bị Fake/Mock
```

---

## 6. Kết quả thực thi

### 6.1 Tổng quan

```text
169 passed, 0 failed, 0 skipped, 0 errors, 1 warning in 4.89s
```

> 1 warning: `StarletteDeprecationWarning` (TestClient dùng `httpx` cũ,
> khuyến nghị dùng `httpx2`) — không ảnh hưởng tính đúng đắn của kết quả.

### 6.2 Kết quả theo file

| # | File | Test | Pass | Fail | Skip |
| ---: | --- | ---: | ---: | ---: | ---: |
| 1 | `tests/test_api.py` | 25 | 25 | 0 | 0 |
| 2 | `tests/test_config.py` | 10 | 10 | 0 | 0 |
| 3 | `tests/test_config_scanner.py` | 4 | 4 | 0 | 0 |
| 4 | `tests/test_db_utils.py` | 6 | 6 | 0 | 0 |
| 5 | `tests/test_envelope.py` | 5 | 5 | 0 | 0 |
| 6 | `tests/test_error_recovery.py` | 8 | 8 | 0 | 0 |
| 7 | `tests/test_event_bus.py` | 11 | 11 | 0 | 0 |
| 8 | `tests/test_executor_helpers.py` | 10 | 10 | 0 | 0 |
| 9 | `tests/test_module_pipeline.py` | 5 | 5 | 0 | 0 |
| 10 | `tests/test_realtime_pipeline.py` | 9 | 9 | 0 | 0 |
| 11 | `tests/test_registry_architecture.py` | 4 | 4 | 0 | 0 |
| 12 | `tests/test_scan_integration.py` | 16 | 16 | 0 | 0 |
| 13 | `tests/test_scan_lifecycle.py` | 9 | 9 | 0 | 0 |
| 14 | `tests/test_scheduler.py` | 3 | 3 | 0 | 0 |
| 15 | `tests/test_scheduler_lifecycle.py` | 3 | 3 | 0 | 0 |
| 16 | `tests/test_websocket.py` | 7 | 7 | 0 | 0 |
| 17 | `tests/test_whitelist_lifecycle.py` | 6 | 6 | 0 | 0 |
| 18 | `modules/port_scanner/tests/test_scanner.py` | 28 | 28 | 0 | 0 |
| | **Tổng** | **169** | **169** | **0** | **0** |

### 6.3 Kết quả theo nhóm chức năng

| Nhóm | Test | Pass | Đánh giá |
| --- | ---: | ---: | --- |
| Authentication / Security | 7 | 7 | Đạt — toàn bộ protected endpoint được kiểm tra |
| Health | 4 | 4 | Đạt — idle/scanning + contract |
| Module Registry & Architecture | 11 | 11 | Đạt — discovery, isolation, duplicate, kiến trúc |
| Scan API & Lifecycle | 13 | 13 | Đạt — API + lifecycle E2E |
| Scan History / Persistence | 5 | 5 | Đạt — history/detail/latest/pagination |
| Port Scanner (unit) | 18 | 18 | Đạt — severity matrix, process, mismatch, priority |
| Whitelist | 11 | 11 | Đạt — CRUD, override, uniqueness, lifecycle |
| Diffing | 10 | 10 | Đạt — fixture matrix + edge cases |
| WebSocket / Realtime | 16 | 16 | Đạt — đủ events, order, replay, multi-subscriber |
| Event Bus | 11 | 11 | Đạt — pub/sub, wildcard, isolation |
| Scheduler | 6 | 6 | Đạt — job registration & trigger |
| Nmap / Fallback | 3 | 3 | Đạt — fallback socket không crash |
| Error Handling / Resilience | 12 | 12 | Đạt — error state, rollback, concurrent |
| Input Validation | 2 | 2 | Đạt — 400/422, clamp pagination |
| Config | 10 | 10 | Đạt — load, defaults, module settings, token |
| Envelope | 5 | 5 | Đạt — ok()/fail() |
| DB utilities | 6 | 6 | Đạt — iso, session_scope, create_all |
| Executor helpers | 10 | 10 | Đạt — mark_failed, previous_scan, keys |
| Config → Scanner | 4 | 4 | Đạt — risky ports & scan_mode |
| Scanner utilities | 5 | 5 | Đạt — summary, nmap ports |
| **Tổng** | **169** | **169** | **100% PASS** |

---

## 7. Phát hiện trong quá trình kiểm thử

| # | Loại | Mô tả | Mức độ | Xử lý |
| --- | --- | --- | --- | --- |
| 1 | **Test stale** | `test_config_scanner.py::test_custom_risky_ports_from_config` assert contract cũ của `PortScannerModule._classify` (trả chuỗi message) trong khi contract hiện tại trả `(severity, reasons: list[str])` | Trung bình | **Đã sửa**: cập nhật assert theo `["PORT_IN_RISKY_LIST"]` / `[]` — đúng contract trong `scanner.py` |
| 2 | **Lệch contract** | `POST /api/v1/modules/unknown/scan` trả `404 HTTP_ERROR`, tài liệu mô tả `MODULE_NOT_FOUND` | Thấp | Test khóa hành vi hiện tại; cần quyết định có thêm route wildcard hay cập nhật tài liệu |
| 3 | **Lệch schema** | Event `progress` thực tế là `{type, current, total, message}` — tài liệu ví dụ `{progress: 50}` | Thấp | Đã test đúng schema thực tế; cần đồng bộ tài liệu API |
| 4 | **Lệch contract** | `error_message` lưu message không kèm code; code chỉ xuất hiện trong WS event | Thông tin | Không phải bug |

Không phát hiện **lỗi chức năng (functional bug)** nào trong phạm vi kiểm thử.

---

## 8. Phân tích độ phủ & rủi ro còn lại

### 8.1 Độ phủ chiến lược

| Layer | Trạng thái | Nhận xét |
| --- | --- | --- |
| Core business logic | ✅ Bao phủ | Config, executor helpers, event bus, scanner base |
| Scanner (severity/diff/whitelist) | ✅ Bao phủ | Ma trận 9 tổ hợp + edge cases |
| API routes | ✅ Bao phủ | Contract test toàn bộ endpoint chính |
| Error paths | ✅ Bao phủ | ScanError/generic/DB failure/subscriber failure |
| WebSocket protocol | ✅ Bao phủ | Đủ events, order, replay, multi-subscriber |

### 8.2 Rủi ro còn lại

| Rủi ro | Ảnh hưởng tiềm tàng | Đề xuất |
| --- | --- | --- |
| E2E frontend chưa có | Luồng UI (bấm scan → realtime → kết quả) chưa được xác nhận tự động | Bổ sung Playwright khi có yêu cầu |
| Chỉ 1 module (port-scanner) | Whitelist cross-module, scheduler nhiều module chưa được test | Kiểm thử khi thêm module mới |
| Chưa đo line/branch coverage | Không biết chính xác % dòng/branch | Chạy `pytest --cov` trước production |
| Windows-only hiện tại | Hành vi psutil/nmap trên Linux/macOS chưa được xác nhận | Chạy CI matrix cross-platform |

---

## 9. Đánh giá chất lượng

| Tiêu chí | Kết quả |
| --- | --- |
| Pass rate | **100%** (169/169) |
| Determinism | ✅ Không flaky, chạy lặp nhiều lần ổn định |
| Isolation | ✅ Mỗi test DB SQLite tạm riêng, không đụng dữ liệu thật |
| Thời gian chạy | ✅ ~5s — phù hợp chạy trong mỗi commit/PR |
| Không phụ thuộc external | ✅ Không Internet, không port thật, không Nmap binary |
| Không leak secret | ✅ Test xác nhận response không chứa token/stack trace |

---

## 10. Kết luận

Test suite backend **đạt yêu cầu cho mức phát hành (release-ready)** ở phạm vi
backend:

- Toàn bộ **P0/P1 test bắt buộc** theo `docs/testing/test-cases.md` đã được triển khai
  và pass (xem `docs/archive/testing/test-log.md` để theo dõi từng test case).
- Hạ tầng kiểm thử chung (`helpers.py`, fixtures trong `conftest.py`) đã chuẩn
  hoá, dễ mở rộng cho module tương lai.
- 1 test stale được phát hiện và sửa; không có lỗi chức năng nào được ghi nhận.

---

## 11. Khuyến nghị

1. **Tích hợp CI** — chạy `pytest` trong mỗi commit/PR (GitHub Actions) để giữ
   suite xanh liên tục.
2. **Đo coverage** — chạy `pytest --cov` trước production, mục tiêu: core logic
   ≥ 90%, diffing/whitelist ≥ 95%, error paths ≥ 80%.
3. **Đồng bộ tài liệu API** — cập nhật mô tả cho `404 HTTP_ERROR` (scan module
   lạ) và schema `progress {current, total, message}`.
4. **Cross-platform matrix** — thêm Linux/macOS vào CI vì scanner phụ thuộc
   API process/network của OS.
5. **Bổ sung E2E frontend** khi có yêu cầu, không thay thế unit/integration
   test hiện có.
6. **Kiểm thử module mới** ngay khi thêm module thứ hai để phủ whitelist
   cross-module và scheduler multi-module.

---

*Tài liệu được sinh từ kết quả thực thi pytest ngày 2026-08-14, kết hợp phân
tích mã nguồn test trong `backend/tests/` và `backend/modules/port_scanner/tests/`.*