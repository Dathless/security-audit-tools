# Current implementation note

Status checked against main on 2026-10-24: Port Scanner and Firewall Check are implemented; Startup Programs is [planned](../plans/startup-programs.md). The final pre-merge run recorded 295 passing tests; see the [verification report](reports/firewall-check-nmap-removal.md). The case catalog below also contains proposed cases and is not proof that every case is implemented or has passed.

The Nmap engine is removed. Its unavailable/execution/parser cases below are superseded by psutil-only operation and legacy configuration compatibility. Firewall Check v1 acceptance and failure cases are implemented in `backend/modules/firewall_check/tests/` and `backend/tests/test_selenium_firewall.py`; see [implementation checklist](../plans/completed/firewall-check-nmap-removal-checklist.md) for execution evidence.

# Test Case Specification

## 1. Mục đích

Tài liệu này tổng hợp các test case cần có cho dự án **Security Audit
Tool**, bao gồm:

-   Các test đã tồn tại trong source hiện tại.
-   Các test còn thiếu và được đề xuất bổ sung.
-   Mục tiêu, tiền điều kiện, dữ liệu kiểm thử và kết quả mong đợi.
-   Các tiêu chí kiểm thử về chức năng, API contract, security,
    persistence, realtime, resilience và kiến trúc.
-   Tiêu chí pass/fail và yêu cầu môi trường phục vụ kiểm thử.

Tài liệu được xây dựng dựa trên README của dự án và các test hiện có,
đặc biệt `tests/test_api.py` và
`modules/port_scanner/tests/test_scanner.py`.

------------------------------------------------------------------------

## 2. Phạm vi hệ thống cần kiểm thử

Các thành phần chính:

``` text
Frontend
    │
    ├── REST API ───────────────┐
    │                           │
    └── WebSocket ──────────────┤
                                ▼
                           FastAPI Backend
                                │
              ┌─────────────────┼──────────────────┐
              ▼                 ▼                  ▼
         Auth / API        Scan Executor       Event Bus
                                │                  │
              ┌─────────────────┼──────────────────┘
              ▼                 ▼
         Port Scanner        Scheduler
              │
              ▼
           Storage
              │
              ├── scan_runs
              ├── scan_items
              ├── scan_diff_log
              └── whitelist_entries
```

Phạm vi:

1.  Authentication / local token.
2.  Health API.
3.  Module registry.
4.  Port Scanner.
5.  Scan lifecycle.
6.  Scan persistence và history.
7.  Diffing.
8.  Severity.
9.  Whitelist.
10. REST API.
11. WebSocket / realtime.
12. Event Bus.
13. Scheduler.
14. Nmap/socket fallback.
15. Database integrity.
16. Error handling / resilience.
17. Architecture / module isolation.
18. Frontend integration ở mức E2E nếu có môi trường phù hợp.

------------------------------------------------------------------------

# 3. Quy ước trạng thái Test Case

  Trạng thái   Ý nghĩa
  ------------ ----------------------------------------------------
  `DONE`       Đã có test tương ứng trong source hiện tại
  `PARTIAL`    Có test một phần nhưng chưa bao phủ đầy đủ yêu cầu
  `TODO`       Chưa có test, cần bổ sung
  `OPTIONAL`   Nên có khi mở rộng hệ thống hoặc trước production

Mức ưu tiên:

  Priority   Ý nghĩa
  ---------- -----------------------------------------------------------
  `P0`       Critical --- phải có trước khi xem test suite đạt yêu cầu
  `P1`       High --- nên có trước production
  `P2`       Medium --- nên bổ sung trong quá trình hoàn thiện
  `P3`       Low --- cải thiện chất lượng dài hạn

------------------------------------------------------------------------

# 4. Tiêu chí kiểm thử tổng quát

## 4.1 Functional correctness

Mỗi chức năng phải kiểm tra:

-   Happy path.
-   Invalid input.
-   Missing resource.
-   Duplicate resource.
-   Permission / authentication failure.
-   Dependency failure.
-   Boundary condition.
-   State transition.

## 4.2 API contract

Mỗi API phải kiểm tra tối thiểu:

-   HTTP status code.
-   `success`.
-   `data`.
-   `error.code` khi lỗi.
-   Kiểu dữ liệu của response.
-   Các field bắt buộc.
-   Pagination nếu API hỗ trợ pagination.
-   Authentication requirement.

Response thành công phải tuân theo envelope:

``` json
{
  "success": true,
  "data": {}
}
```

Response lỗi:

``` json
{
  "success": false,
  "data": null,
  "error": {
    "code": "ERROR_CODE"
  }
}
```

## 4.3 Deterministic test

Test không được phụ thuộc vào:

-   Port thực tế đang mở trên máy developer.
-   Process thực tế trên máy.
-   Nmap được cài trên máy test.
-   Trạng thái mạng Internet.
-   Thời gian thực.
-   Database production.
-   Dữ liệu test từ lần chạy trước.

Sử dụng:

-   Fake.
-   Mock.
-   Monkeypatch.
-   Fixture.
-   Temporary database.
-   Controlled test data.

## 4.4 Isolation

Mỗi test phải độc lập:

``` text
Test A
  ↓
setup riêng
  ↓
execute
  ↓
assert
  ↓
cleanup
```

Không được yêu cầu test A chạy trước test B.

## 4.5 Idempotency

Các operation phù hợp phải kiểm tra chạy nhiều lần không tạo dữ liệu
ngoài ý muốn.

Ví dụ:

``` text
POST whitelist cùng key 2 lần
→ không tạo 2 record
```

------------------------------------------------------------------------

# 5. Authentication / Security

## TC-AUTH-001 --- Request không có token

**Status:** `DONE`\
**Priority:** P0

### Mục tiêu

Đảm bảo API không cho phép request khi thiếu `X-Local-Token`.

### Preconditions

-   Backend đang chạy.
-   Token hợp lệ tồn tại.
-   Header `X-Local-Token` bị remove.

### Steps

``` text
GET /api/v1/health
```

### Expected

``` text
HTTP 401
success = false
error.code = INVALID_LOCAL_TOKEN
```

### Kỹ thuật

-   API contract testing.
-   Negative testing.

------------------------------------------------------------------------

## TC-AUTH-002 --- Token hợp lệ

**Status:** `PARTIAL`\
**Priority:** P0

### Mục tiêu

Đảm bảo request có token hợp lệ được chấp nhận.

### Expected

``` text
HTTP 200
success = true
```

### Coverage

Nên kiểm tra ít nhất:

-   `/health`
-   `/modules`
-   `/scan`
-   `/scans`
-   `/scans/latest`
-   `/whitelist`

------------------------------------------------------------------------

## TC-AUTH-003 --- Token sai

**Status:** `TODO`\
**Priority:** P0

### Steps

Gửi:

``` http
X-Local-Token: invalid-token
```

### Expected

``` text
401
INVALID_LOCAL_TOKEN
```

------------------------------------------------------------------------

## TC-AUTH-004 --- Token rỗng

**Status:** `TODO`\
**Priority:** P1

Kiểm tra:

``` http
X-Local-Token:
```

Expected:

``` text
401
```

------------------------------------------------------------------------

## TC-AUTH-005 --- Tất cả protected endpoint đều yêu cầu token

**Status:** `TODO`\
**Priority:** P0

### Mục tiêu

Đảm bảo không có endpoint mới vô tình bỏ qua security dependency.

### Endpoints

``` text
GET    /api/v1/health
GET    /api/v1/modules
POST   /api/v1/modules/{module_id}/scan
GET    /api/v1/modules/{module_id}/scans
GET    /api/v1/modules/{module_id}/scans/{scan_id}
GET    /api/v1/modules/{module_id}/scans/latest
GET    /api/v1/modules/{module_id}/whitelist
POST   /api/v1/modules/{module_id}/whitelist
DELETE /api/v1/modules/{module_id}/whitelist/{id}
```

------------------------------------------------------------------------

# 6. Health API

## TC-HEALTH-001 --- Health bình thường

**Status:** `DONE`\
**Priority:** P0

### Expected

``` text
HTTP 200
success = true
status ∈ {idle, scanning}
```

------------------------------------------------------------------------

## TC-HEALTH-002 --- Health khi đang scan

**Status:** `TODO`\
**Priority:** P1

### Steps

1.  Trigger scan.
2.  Trong lúc scan đang chạy gọi `/health`.

### Expected

``` text
status = scanning
```

------------------------------------------------------------------------

## TC-HEALTH-003 --- Health sau khi scan hoàn thành

**Status:** `TODO`\
**Priority:** P1

Expected:

``` text
status = idle
```

và không còn scan active.

------------------------------------------------------------------------

## TC-HEALTH-004 --- Health response đầy đủ

**Status:** `TODO`\
**Priority:** P1

Kiểm tra các field được contract yêu cầu:

-   status.
-   active scan count.
-   module count.
-   uptime nếu có.

------------------------------------------------------------------------

# 7. Module Registry

## TC-MODULE-001 --- List modules

**Status:** `DONE`\
**Priority:** P0

Test hiện tại kiểm tra:

-   `port-scanner` tồn tại.
-   display name là `Port Scanner`.
-   status là `active`.

------------------------------------------------------------------------

## TC-MODULE-002 --- Module manifest đầy đủ

**Status:** `TODO`\
**Priority:** P1

Mỗi module phải có các metadata bắt buộc:

``` text
id
display_name
version
status
```

Nếu contract có thêm field thì phải validate tương ứng.

------------------------------------------------------------------------

## TC-MODULE-003 --- Duplicate module ID

**Status:** `TODO`\
**Priority:** P1

Module registry không được chứa hai module cùng ID.

------------------------------------------------------------------------

## TC-MODULE-004 --- Module discovery failure

**Status:** `TODO`\
**Priority:** P1

Mô phỏng module lỗi khi discovery.

Expected:

-   Backend không crash toàn bộ.
-   Module lỗi được đánh dấu phù hợp hoặc bỏ qua theo contract.
-   Module hợp lệ khác vẫn hoạt động.

------------------------------------------------------------------------

## TC-MODULE-005 --- Architecture module isolation

**Status:** `TODO`\
**Priority:** P2

Kiểm tra `core/` không import ngược `modules/` nếu đây là invariant kiến
trúc.

Đây là **architecture test**.

------------------------------------------------------------------------

# 8. Scan API

## TC-SCAN-001 --- POST scan trả scan_id

**Status:** `DONE`\
**Priority:** P0

### Kỹ thuật

Monkeypatch `dispatch_scan()` để không chạy scan thật.

### Expected

``` text
HTTP 200
success = true
data.scan_id tồn tại
```

------------------------------------------------------------------------

## TC-SCAN-002 --- Dispatch scan failure

**Status:** `TODO`\
**Priority:** P0

Mock:

``` text
dispatch_scan()
→ raise exception
```

### Expected

-   API không trả stack trace nội bộ.
-   Response dùng error envelope.
-   Error code ổn định.

------------------------------------------------------------------------

## TC-SCAN-003 --- Scan module không tồn tại

**Status:** `TODO`\
**Priority:** P1

Ví dụ:

``` text
POST /api/v1/modules/unknown/scan
```

Expected:

``` text
404
MODULE_NOT_FOUND
```

------------------------------------------------------------------------

## TC-SCAN-004 --- Scan lifecycle

**Status:** `TODO`\
**Priority:** P0

Workflow:

``` text
POST scan
    ↓
scan_id
    ↓
executor
    ↓
scanner
    ↓
DB persistence
    ↓
done
```

Expected:

-   scan record được tạo.
-   trạng thái chuyển đúng.
-   result được persist.
-   scan có thể truy vấn lại.

------------------------------------------------------------------------

# 9. Scan Persistence / History

## TC-HISTORY-001 --- History rỗng

**Status:** `DONE`\
**Priority:** P0

Expected:

``` text
total = 0
items = []
```

------------------------------------------------------------------------

## TC-HISTORY-002 --- Scan → history

**Status:** `DONE`\
**Priority:** P0

Test hiện tại chạy scan thật ở mức integration với `FakePsutil`, sau đó
truy vấn history.

------------------------------------------------------------------------

## TC-HISTORY-003 --- Scan detail

**Status:** `DONE`\
**Priority:** P0

Kiểm tra scan đã tạo có thể lấy detail.

------------------------------------------------------------------------

## TC-HISTORY-004 --- Latest scan

**Status:** `DONE`\
**Priority:** P0

Kiểm tra scan mới nhất được trả đúng.

------------------------------------------------------------------------

## TC-HISTORY-005 --- Latest scan khi chưa có scan

**Status:** `TODO`\
**Priority:** P1

Cần thống nhất contract:

``` text
200 + data=null
```

hoặc:

``` text
404
```

Sau đó viết test cố định behavior.

------------------------------------------------------------------------

## TC-HISTORY-006 --- Scan detail không tồn tại

**Status:** `TODO`\
**Priority:** P1

Expected:

``` text
404
SCAN_NOT_FOUND
```

------------------------------------------------------------------------

## TC-HISTORY-007 --- Pagination

**Status:** `TODO`\
**Priority:** P1

Kiểm tra:

``` text
page=1
page_size=10
```

và boundary:

``` text
page=0
page_size=0
page_size quá lớn
page vượt quá tổng số trang
```

------------------------------------------------------------------------

# 10. Port Scanner

## TC-SCANER-001 --- Discover active connection

**Status:** `DONE`\
**Priority:** P0

Sử dụng fake `psutil` để tạo connection xác định.

------------------------------------------------------------------------

## TC-SCANNER-002 --- Process không tồn tại

**Status:** `DONE/PARTIAL`\
**Priority:** P0

Test hiện tại mô phỏng:

``` python
Process(pid)
→ NoSuchProcess
```

Nhưng cần assert rõ behavior cuối cùng:

-   scan không crash.
-   item vẫn được trả.
-   process metadata được đánh dấu thiếu.
-   severity/partial result đúng theo contract.

------------------------------------------------------------------------

## TC-SCANNER-003 --- Localhost safe

**Status:** `DONE` hoặc `TODO` tùy coverage trong `test_scanner.py`\
**Priority:** P0

Ví dụ:

``` text
127.0.0.1:8080
```

Expected severity theo rule.

------------------------------------------------------------------------

## TC-SCANNER-004 --- Wildcard bind warning

**Status:** `DONE` hoặc `TODO` tùy coverage trong `test_scanner.py`\
**Priority:** P0

Ví dụ:

``` text
0.0.0.0:8080
::
```

Expected:

``` text
warning
```

nếu port không thuộc risky-port set.

------------------------------------------------------------------------

## TC-SCANNER-005 --- Risky port danger

**Status:** `DONE` hoặc `TODO` tùy coverage trong `test_scanner.py`\
**Priority:** P0

Ví dụ risky port:

``` text
22
23
3389
```

Danh sách thực tế phải lấy từ source/config của project.

Expected:

``` text
severity = danger
```

------------------------------------------------------------------------

## TC-SCANNER-006 --- Severity boundary / parameterized tests

**Status:** `TODO/PARTIAL`\
**Priority:** P0

Dùng `pytest.mark.parametrize` cho ma trận:

``` text
IP type
×
port type
×
process metadata available/unavailable
×
whitelist state
```

Mục tiêu là tránh bỏ sót combination.

------------------------------------------------------------------------

# 11. Whitelist

## TC-WL-001 --- List empty whitelist

**Status:** `DONE`\
**Priority:** P0

------------------------------------------------------------------------

## TC-WL-002 --- Create whitelist

**Status:** `DONE`\
**Priority:** P0

------------------------------------------------------------------------

## TC-WL-003 --- Read whitelist

**Status:** `DONE`\
**Priority:** P0

------------------------------------------------------------------------

## TC-WL-004 --- Delete whitelist

**Status:** `DONE`\
**Priority:** P0

------------------------------------------------------------------------

## TC-WL-005 --- Duplicate whitelist

**Status:** `DONE`\
**Priority:** P0

Expected không tạo duplicate.

------------------------------------------------------------------------

## TC-WL-006 --- Delete nonexistent whitelist

**Status:** `DONE`\
**Priority:** P0

Expected:

``` text
404
WHITELIST_NOT_FOUND
```

------------------------------------------------------------------------

## TC-WL-007 --- Whitelist override severity

**Status:** `DONE` hoặc `TODO` tùy coverage của `test_scanner.py`\
**Priority:** P0

Workflow:

``` text
risky port
    ↓
danger
    ↓
whitelist
    ↓
scan lại
    ↓
safe
```

Đây là business-critical test.

------------------------------------------------------------------------

## TC-WL-008 --- Same key khác module

**Status:** `TODO`\
**Priority:** P1

Nếu uniqueness là:

``` text
(module_id, whitelist_key)
```

thì:

``` text
module A + key X
module B + key X
```

phải được phép.

------------------------------------------------------------------------

# 12. Diffing

## TC-DIFF-001 --- First scan

**Status:** `DONE` hoặc `PARTIAL` tùy coverage trong `test_scanner.py`\
**Priority:** P0

Xác định behavior của scan đầu tiên.

------------------------------------------------------------------------

## TC-DIFF-002 --- Identical consecutive scans

**Status:** `TODO`\
**Priority:** P0

``` text
Scan #1: 22, 80
Scan #2: 22, 80
```

Expected:

``` text
NEW = none
DISAPPEARED = none
```

------------------------------------------------------------------------

## TC-DIFF-003 --- New item

**Status:** `DONE` hoặc `TODO` tùy coverage trong `test_scanner.py`\
**Priority:** P0

``` text
Scan #1: 80
Scan #2: 80, 443
```

Expected:

``` text
443 = NEW
```

------------------------------------------------------------------------

## TC-DIFF-004 --- Disappeared item

**Status:** `DONE` hoặc `TODO` tùy coverage trong `test_scanner.py`\
**Priority:** P0

``` text
Scan #1: 80, 443
Scan #2: 80
```

Expected:

``` text
443 = DISAPPEARED
```

------------------------------------------------------------------------

## TC-DIFF-005 --- Persist diff log

**Status:** `TODO`\
**Priority:** P1

Kiểm tra `scan_diff_log` thực sự lưu:

``` text
appeared
disappeared
```

đúng scan và đúng item.

------------------------------------------------------------------------

# 13. WebSocket / Realtime

Đây là nhóm ưu tiên cao vì WebSocket là một phần quan trọng của scan
lifecycle.

## TC-WS-001 --- Connect scan WebSocket

**Status:** `TODO`\
**Priority:** P0

Connect:

``` text
/ws/scan/{scan_id}
```

Expected connection thành công với scan hợp lệ.

------------------------------------------------------------------------

## TC-WS-002 --- Invalid scan_id

**Status:** `TODO`\
**Priority:** P1

Expected behavior phải được xác định:

``` text
close/error
```

hoặc response phù hợp.

------------------------------------------------------------------------

## TC-WS-003 --- Progress event

**Status:** `TODO`\
**Priority:** P0

Expected event:

``` json
{
  "type": "progress",
  "scan_id": "...",
  "progress": 50
}
```

Validate schema và range của progress.

------------------------------------------------------------------------

## TC-WS-004 --- Item found event

**Status:** `TODO`\
**Priority:** P0

Expected:

``` text
type = item_found
```

Payload phải chứa item hợp lệ.

------------------------------------------------------------------------

## TC-WS-005 --- Done event

**Status:** `TODO`\
**Priority:** P0

Expected:

``` text
type = done
scan_id đúng
summary tồn tại
```

------------------------------------------------------------------------

## TC-WS-006 --- Error event

**Status:** `TODO`\
**Priority:** P0

Mô phỏng scanner failure.

Expected:

``` text
type = error
code ổn định
```

------------------------------------------------------------------------

## TC-WS-007 --- Event order

**Status:** `TODO`\
**Priority:** P0

Kiểm tra:

``` text
progress
→ item_found
→ done
```

Không được:

``` text
done
→ item_found
```

------------------------------------------------------------------------

## TC-WS-008 --- Replay sau khi scan hoàn thành

**Status:** `TODO`\
**Priority:** P0

Workflow:

``` text
scan hoàn thành
    ↓
client connect WS muộn
    ↓
nhận state cuối
```

Expected:

``` text
replay = true
```

------------------------------------------------------------------------

## TC-WS-009 --- Multiple subscribers

**Status:** `TODO`\
**Priority:** P1

Hai client cùng subscribe một scan.

Expected:

``` text
client A nhận event
client B nhận event
```

Không mất event do subscriber khác.

------------------------------------------------------------------------

# 14. Event Bus

## TC-EVENT-001 --- Publish/subscribe

**Status:** `TODO`\
**Priority:** P1

``` text
subscribe(topic)
publish(topic,event)
→ callback nhận event
```

------------------------------------------------------------------------

## TC-EVENT-002 --- Multiple subscribers

**Status:** `TODO`\
**Priority:** P1

Một event phải tới tất cả subscriber hợp lệ.

------------------------------------------------------------------------

## TC-EVENT-003 --- Unsubscribe

**Status:** `TODO`\
**Priority:** P1

Sau unsubscribe:

``` text
publish
→ callback không được gọi
```

------------------------------------------------------------------------

## TC-EVENT-004 --- Wildcard topic

**Status:** `TODO`\
**Priority:** P1

Nếu event bus hỗ trợ wildcard:

``` text
scan.*
```

phải nhận:

``` text
scan.progress
scan.item_found
scan.done
```

------------------------------------------------------------------------

# 15. Scheduler

## TC-SCHED-001 --- Scheduler disabled / no schedule

**Status:** `TODO`\
**Priority:** P1

Không tạo job khi không cấu hình schedule.

------------------------------------------------------------------------

## TC-SCHED-002 --- Register scheduled scan

**Status:** `TODO`\
**Priority:** P1

Cấu hình schedule hợp lệ.

Expected:

``` text
job được register
```

------------------------------------------------------------------------

## TC-SCHED-003 --- Scheduled job triggers scan

**Status:** `TODO`\
**Priority:** P1

Mock clock/job.

Expected:

``` text
job execute
→ dispatch_scan()
```

Không chờ real time.

------------------------------------------------------------------------

## TC-SCHED-004 --- Scheduler error isolation

**Status:** `TODO`\
**Priority:** P1

Một scheduled scan lỗi không được làm scheduler chết hoàn toàn.

------------------------------------------------------------------------

# 16. Nmap / Socket fallback

## TC-NMAP-001 --- Socket scan

**Status:** `TODO/PARTIAL`\
**Priority:** P1

Scan mode socket hoạt động bình thường.

------------------------------------------------------------------------

## TC-NMAP-002 --- Nmap scan

**Status:** `TODO`\
**Priority:** P1

Mock Nmap và kiểm tra parser/executor.

------------------------------------------------------------------------

## TC-NMAP-003 --- Nmap unavailable

**Status:** `TODO`\
**Priority:** P0

Mô phỏng:

``` text
Nmap không cài
```

Expected:

``` text
fallback → socket
scan vẫn thành công
```

------------------------------------------------------------------------

## TC-NMAP-004 --- Nmap execution failure

**Status:** `TODO`\
**Priority:** P1

Nmap binary tồn tại nhưng command fail.

Expected fallback/error theo contract.

------------------------------------------------------------------------

# 17. Partial Result / Permission

## TC-PERM-001 --- Process permission denied

**Status:** `TODO/PARTIAL`\
**Priority:** P0

Mô phỏng không đọc được process metadata.

Expected:

-   Scan không crash.
-   Item vẫn được trả.
-   `partial_result` đúng.
-   Severity đúng theo rule.

------------------------------------------------------------------------

## TC-PERM-002 --- Administrator/full permission

**Status:** `TODO`\
**Priority:** P1

Mô phỏng đầy đủ process metadata.

Expected:

``` text
process_name
pid
user
```

được xử lý đúng nếu scanner hỗ trợ các field này.

------------------------------------------------------------------------

# 18. Database / Persistence

## TC-DB-001 --- Scan record persistence

**Status:** `DONE/PARTIAL`\
**Priority:** P0

Scan hoàn thành phải tạo record.

------------------------------------------------------------------------

## TC-DB-002 --- Scan items persistence

**Status:** `DONE/PARTIAL`\
**Priority:** P0

Các item phát hiện phải được lưu đúng scan.

------------------------------------------------------------------------

## TC-DB-003 --- Diff log persistence

**Status:** `TODO`\
**Priority:** P1

Kiểm tra appeared/disappeared được lưu.

------------------------------------------------------------------------

## TC-DB-004 --- Whitelist uniqueness

**Status:** `DONE` ở mức API, `TODO` ở mức DB constraint nếu chưa có\
**Priority:** P1

Database phải đảm bảo uniqueness:

``` text
(module_id, whitelist_key)
```

------------------------------------------------------------------------

## TC-DB-005 --- Transaction rollback

**Status:** `TODO`\
**Priority:** P1

Mô phỏng lỗi giữa lúc persist scan.

Expected:

-   Không để DB ở trạng thái half-written.
-   Transaction rollback đúng.
-   Không tạo scan record mồ côi.

------------------------------------------------------------------------

# 19. Error Handling / Resilience

## TC-ERR-001 --- Scanner exception

**Status:** `TODO`\
**Priority:** P0

Scanner raise exception.

Expected:

``` text
scan → error state
WebSocket → error event
DB → trạng thái nhất quán
API → không crash process
```

------------------------------------------------------------------------

## TC-ERR-002 --- Database unavailable

**Status:** `TODO`\
**Priority:** P1

Mô phỏng DB failure.

Expected error rõ ràng, không leak stack trace.

------------------------------------------------------------------------

## TC-ERR-003 --- Event Bus subscriber failure

**Status:** `TODO`\
**Priority:** P1

Một subscriber throw exception.

Expected các subscriber khác vẫn nhận event nếu design yêu cầu
isolation.

------------------------------------------------------------------------

## TC-ERR-004 --- Concurrent scan

**Status:** `TODO`\
**Priority:** P1

Trigger hai scan gần như đồng thời.

Cần xác định business rule:

-   Cho phép chạy song song, hoặc
-   Từ chối scan thứ hai.

Sau đó test đúng rule.

------------------------------------------------------------------------

# 20. API Input Validation

## TC-VALID-001 --- Invalid module_id

**Status:** `TODO`\
**Priority:** P1

------------------------------------------------------------------------

## TC-VALID-002 --- Invalid whitelist payload

**Status:** `TODO`\
**Priority:** P1

Test:

-   thiếu field.
-   field rỗng.
-   field sai kiểu.
-   field quá dài.
-   ký tự không hợp lệ nếu có constraint.

Expected:

``` text
422
```

hoặc error contract tương ứng.

------------------------------------------------------------------------

## TC-VALID-003 --- Invalid pagination

**Status:** `TODO`\
**Priority:** P1

Boundary:

``` text
page < 1
page_size < 1
page_size > max
```

------------------------------------------------------------------------

# 21. Frontend / E2E

Nếu project có frontend React, nên có lớp E2E riêng.

## TC-E2E-001 --- Dashboard load

**Status:** `TODO`\
**Priority:** P1

Expected:

-   API được gọi.
-   Loading state.
-   Data state.
-   Empty state.

------------------------------------------------------------------------

## TC-E2E-002 --- Start scan

**Status:** `TODO`\
**Priority:** P0

Workflow:

``` text
Click Scan
→ loading
→ progress
→ result
```

------------------------------------------------------------------------

## TC-E2E-003 --- WebSocket disconnect

**Status:** `TODO`\
**Priority:** P1

Mô phỏng WS disconnect.

Expected UI:

``` text
reconnecting / disconnected
```

theo thiết kế.

------------------------------------------------------------------------

## TC-E2E-004 --- Empty history

**Status:** `TODO`\
**Priority:** P1

Fresh database.

Expected empty-state UI thay vì error.

------------------------------------------------------------------------

# 22. Security Test bổ sung

## TC-SEC-001 --- Không leak secret

**Status:** `TODO`\
**Priority:** P0

Response/log không được chứa:

-   local token.
-   DB credentials nếu có.
-   stack trace nhạy cảm.
-   environment secrets.

------------------------------------------------------------------------

## TC-SEC-002 --- Invalid token brute-force behavior

**Status:** `OPTIONAL`\
**Priority:** P2

Nếu có rate limit/lockout thì phải test.

------------------------------------------------------------------------

## TC-SEC-003 --- Malformed request

**Status:** `TODO`\
**Priority:** P1

Gửi payload không hợp lệ và đảm bảo:

-   không crash.
-   không SQL error leak.
-   không stack trace leak.

------------------------------------------------------------------------

# 23. Test kỹ thuật nên sử dụng

## Unit Test

Dùng cho:

-   severity calculation.
-   diffing.
-   whitelist rule.
-   parser.
-   event bus.
-   scheduler logic.
-   utility functions.

Công cụ:

``` text
pytest
pytest.mark.parametrize
Mock
MagicMock
monkeypatch
```

------------------------------------------------------------------------

## Component / Integration Test

Dùng cho:

``` text
FastAPI
+
scanner
+
executor
+
DB
```

Đây là lớp quan trọng nhất sau unit test.

------------------------------------------------------------------------

## API Contract Test

Validate:

``` text
status code
response envelope
error code
schema
authentication
```

------------------------------------------------------------------------

## WebSocket Integration Test

Test:

``` text
connect
subscribe
receive
ordering
replay
error
disconnect
```

------------------------------------------------------------------------

## E2E Test

Dùng hạn chế cho:

``` text
React
→ REST
→ WebSocket
→ backend
→ DB
```

Không nên dùng E2E để thay thế unit/integration test.

------------------------------------------------------------------------

# 24. Test Data Requirements

## Scanner fixture

Nên có fixture chuẩn:

``` text
127.0.0.1:8080
127.0.0.1:443
0.0.0.0:8080
0.0.0.0:22
:::8080
```

và process:

``` text
PID tồn tại
PID không tồn tại
permission denied
```

## Diff fixture

### Case A

``` text
Scan 1 = {80, 443}
Scan 2 = {80, 443}
```

### Case B

``` text
Scan 1 = {80}
Scan 2 = {80, 443}
```

### Case C

``` text
Scan 1 = {80, 443}
Scan 2 = {80}
```

### Case D

``` text
Scan 1 = {}
Scan 2 = {80}
```

------------------------------------------------------------------------

# 25. Yêu cầu môi trường kiểm thử

## Backend

Cần:

``` text
Python 3.11+
pytest
pytest-asyncio
FastAPI TestClient
```

## Database

Test phải sử dụng:

``` text
temporary SQLite database
```

hoặc database riêng cho test.

Không dùng database production/development.

## Network

Unit/integration test scanner:

-   Không được yêu cầu Internet.
-   Không được yêu cầu port thực tế đang mở.
-   Không được phụ thuộc network của developer.

Dùng Fake/Mock.

## Nmap

Nmap là optional dependency.

Test fallback phải chạy được kể cả khi Nmap **không được cài**.

## OS

Vì scanner có behavior phụ thuộc process/network API, nên cần xác định
rõ:

``` text
Windows
Linux
```

và chạy platform-specific test khi cần.

------------------------------------------------------------------------

# 26. Quy tắc Mock / Fake

## Được mock

-   `psutil`.
-   Nmap binary/executor.
-   Scheduler clock.
-   Event Bus khi test API layer.
-   Database khi test thuần route nếu cần.

## Không nên mock

Trong integration test:

``` text
API
→ executor
→ scanner
→ storage
```

Nên để các layer chính chạy thật để phát hiện lỗi integration.

------------------------------------------------------------------------

# 27. Definition of Done cho Test Suite

Test suite được xem là đạt yêu cầu khi:

### P0

-   [ ] Authentication được test trên toàn bộ protected endpoints.
-   [ ] Health API.
-   [ ] Module registry.
-   [ ] Scan lifecycle.
-   [ ] Scan persistence.
-   [ ] Scanner severity.
-   [ ] Whitelist override.
-   [ ] Diffing.
-   [ ] WebSocket progress/item/done/error.
-   [ ] WebSocket replay.
-   [ ] Scanner failure.
-   [ ] Nmap fallback.
-   [ ] Permission/partial result.
-   [ ] Không leak sensitive information.

### P1

-   [ ] Pagination.
-   [ ] Event Bus.
-   [ ] Scheduler.
-   [ ] DB transaction rollback.
-   [ ] Concurrent scan behavior.
-   [ ] Input validation.
-   [ ] Multiple WebSocket subscribers.
-   [ ] Frontend critical flows.

### P2

-   [ ] Architecture tests.
-   [ ] Performance tests.
-   [ ] Stress/concurrency tests nâng cao.
-   [ ] Cross-platform matrix.

------------------------------------------------------------------------

# 28. Tiêu chí chất lượng

## Functional

Mục tiêu:

``` text
P0 test pass rate = 100%
P1 test pass rate = 100% trước production
```

## Regression

Mỗi bug production phải có:

``` text
bug
 ↓
regression test
 ↓
fix
 ↓
test pass
```

## Determinism

Không chấp nhận test:

-   flaky.
-   phụ thuộc network ngoài.
-   phụ thuộc thời gian thực.
-   phụ thuộc thứ tự chạy test.

## Performance

Test suite unit/integration thông thường nên chạy nhanh để có thể chạy
trong mỗi commit/PR.

Các test E2E/stress có thể tách riêng.

------------------------------------------------------------------------

# 29. Coverage mục tiêu

Coverage không nên chỉ nhìn vào % dòng code.

Mục tiêu đề xuất:

  Layer                       Target
  ------------------------- --------
  Core business logic          ≥ 90%
  Scanner                      ≥ 90%
  API routes                   ≥ 85%
  Error paths                  ≥ 80%
  Event Bus                    ≥ 90%
  Diffing                      ≥ 95%
  Whitelist rules              ≥ 95%
  WebSocket protocol           ≥ 85%
  Frontend critical logic      ≥ 80%

Quan trọng hơn line coverage là **branch coverage** đối với:

``` text
severity
diffing
permission
fallback
error handling
whitelist
```

------------------------------------------------------------------------

# 30. Ma trận ưu tiên triển khai

  Nhóm                       Đã có                 Cần bổ sung Priority
  ------------------ ------------- --------------------------- ----------
  Auth                          Có           Một số edge cases P0
  Health                        Có            State transition P1
  Module registry               Có           Failure/invariant P1
  Scan API                      Có          Failure/validation P0
  Scan persistence              Có                 Transaction P0
  Scanner                       Có                 Edge matrix P0
  Severity             Có một phần                 Full matrix P0
  Whitelist                     Có        Integration override P0
  Diffing              Có một phần   Integration + persistence P0
  WebSocket                Chưa có           Toàn bộ lifecycle P0
  Event Bus                Chưa có               Core behavior P1
  Scheduler                Chưa có               Job lifecycle P1
  Nmap                     Chưa/ít                    Fallback P0
  Permission              Một phần              Partial result P0
  DB                      Một phần          Integrity/rollback P1
  Input validation              Ít              Boundary cases P1
  Frontend E2E             Chưa có              Critical flows P1
  Architecture             Chưa có          Import constraints P2

------------------------------------------------------------------------

# 31. Bộ test tối thiểu trước Production

Nếu cần một checklist ngắn gọn để quyết định "đã đủ test để release
chưa", tối thiểu phải pass:

``` text
[ ] Auth: valid / invalid / missing token
[ ] Health: idle / scanning
[ ] Module discovery
[ ] Scan start
[ ] Scan success
[ ] Scan failure
[ ] Scan persistence
[ ] Scan history
[ ] Latest scan
[ ] Scanner severity
[ ] Permission denied / partial result
[ ] Whitelist CRUD
[ ] Whitelist severity override
[ ] Diff: new
[ ] Diff: disappeared
[ ] Diff: unchanged
[ ] WebSocket progress
[ ] WebSocket item_found
[ ] WebSocket done
[ ] WebSocket error
[ ] WebSocket replay
[ ] Nmap unavailable → socket fallback
[ ] Invalid input
[ ] Missing resource
[ ] DB rollback
[ ] No sensitive data leakage
```

------------------------------------------------------------------------

# 32. Kết luận

Test hiện tại đã có nền tốt, đặc biệt:

``` text
Fake psutil
Monkeypatch
API contract assertions
Integration scan
CRUD workflow
Negative testing
```

Nhưng để phản ánh đầy đủ kiến trúc và giá trị của Security Audit Tool,
test suite cần mở rộng mạnh ở:

``` text
                CURRENT
                   │
                   ▼
        REST API + Scanner
                   │
                   │
             cần mở rộng
                   ▼
 ┌─────────────────────────────────┐
 │ WebSocket                       │
 │ Event Bus                       │
 │ Diff persistence                │
 │ Severity matrix                 │
 │ Whitelist integration           │
 │ Permission / partial result     │
 │ Nmap fallback                   │
 │ Scheduler                       │
 │ Error / transaction handling    │
 └─────────────────────────────────┘
```

Ưu tiên triển khai theo thứ tự:

``` text
1. WebSocket lifecycle + replay
2. Scanner severity / permission matrix
3. Diff integration
4. Whitelist integration
5. Nmap fallback
6. Scan error handling
7. Event Bus
8. Scheduler
9. DB transaction/integrity
10. Frontend E2E
```
