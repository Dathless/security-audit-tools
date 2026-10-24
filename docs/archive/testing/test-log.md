# TestLog.md — Kết quả triển khai Test Suite

Tài liệu ghi nhận kết quả điều chỉnh & bổ sung bộ kiểm thử cho **Security
Audit Tool** dựa trên `docs/testing/test-cases.md`, `docs/testing/unit-test-plan.md` và hiện
trạng mã nguồn trong `./backend/`.

---

## 1. Tóm tắt

- Cập nhật test trong `./backend/tests/` và `./backend/modules/port_scanner/tests/`.
- **Trước:** 78 test pass (7 file).
- **Sau:** **169 test pass** (18 file), chạy lặp lại nhiều lần ổn định
  (không flaky), thời gian chạy ~5s, không phụ thuộc mạng / nmap / port
  thật / DB production.
- **Đã sửa 1 test stale:** `test_config_scanner.py::test_custom_risky_ports_from_config`
  vẫn assert contract cũ (`_classify` trả chuỗi message); contract hiện tại
  của `PortScannerModule._classify` là `(severity, reasons: list[str])`
  (xem mục 5.4).

```
Môi trường kiểm thử:
- Python 3.11, pytest 9.1.1, pytest-asyncio (asyncio_mode = auto)
- FastAPI TestClient (httpx)
- SQLite tạm (tmp_path_factory) — không đụng data/security_audit.db
- psutil / nmap đều bị Fake/Mock
```

---

## 2. Phân bố test theo file

| # | File | Số test | Nhóm phạm vi |
| --- | --- | ---: | --- |
| 1 | `tests/test_api.py` | 25 | TC-AUTH, TC-SEC, TC-HEALTH, TC-MODULE, TC-SCAN, TC-HISTORY, TC-WL, TC-VALID |
| 2 | `tests/test_config.py` | 10 | UT-CONFIG-001..010 |
| 3 | `tests/test_config_scanner.py` | 4 | CL-CS-001..003 + extra |
| 4 | `tests/test_db_utils.py` | 6 | UT-DB-001..006 |
| 5 | `tests/test_envelope.py` | 5 | UT-ENV-001..005 |
| 6 | `tests/test_error_recovery.py` | 8 | CL-ERR-001..008 |
| 7 | `tests/test_event_bus.py` | 11 | TC-EVENT, TC-ERR-003, UT-EV-001..004 |
| 8 | `tests/test_executor_helpers.py` | 10 | UT-EXEC-001..010 |
| 9 | `tests/test_module_pipeline.py` | 5 | CL-MOD-001..005 |
| 10 | `tests/test_realtime_pipeline.py` | 9 | CL-RT-001..009 |
| 11 | `tests/test_registry_architecture.py` | 4 | TC-MODULE-003/004/005 |
| 12 | `tests/test_scan_integration.py` | 16 | TC-SCAN-004, TC-DIFF, TC-WL-007, TC-DB, TC-ERR, CL-DIFF-005..008 |
| 13 | `tests/test_scan_lifecycle.py` | 9 | CL-LC-001..009 |
| 14 | `tests/test_scheduler.py` | 3 | TC-SCHED-001..003 |
| 15 | `tests/test_scheduler_lifecycle.py` | 3 | CL-SCH-001..003 |
| 16 | `tests/test_websocket.py` | 7 | TC-WS-001..009 + global channel |
| 17 | `tests/test_whitelist_lifecycle.py` | 6 | CL-WL-001..006 |
| 18 | `modules/port_scanner/tests/test_scanner.py` | 28 | TC-SCANNER, TC-PERM, TC-WL, TC-NMAP, UT-SC, diff |
| | **Tổng** | **169** | |

> Số test ở bảng trên là số lượng *test function* thu được qua
> `pytest --collect-only` (đã gộp đầy đủ các trường hợp `parametrize`:
> `test_severity_matrix` = 9, `test_diff_fixture_matrix` = 4).

---

## 3. Chi tiết từng Test Case

### 3.1 Authentication / Security

| TC | Trạng thái | Test / Ghi chú |
| --- | --- | --- |
| TC-AUTH-001 | DONE | `test_health_requires_token` — thiếu `X-Local-Token` → 401 `INVALID_LOCAL_TOKEN` |
| TC-AUTH-002 | DONE | `test_auth_valid_token_all_endpoints` — token hợp lệ trên toàn bộ protected endpoint |
| TC-AUTH-003 | DONE | `test_auth_invalid_token` — token sai → 401 |
| TC-AUTH-004 | DONE | `test_auth_empty_token` — token rỗng → 401 |
| TC-AUTH-005 | DONE | `test_auth_all_protected_endpoints_require_token` — parametrize theo danh sách endpoint |
| TC-SEC-001 | DONE | `test_no_secret_leak_in_responses` — không leak token / stack trace |
| TC-SEC-002 | **SKIP** | Hệ thống chưa có rate limit/lockout nên không có gì để test |
| TC-SEC-003 | DONE | `test_malformed_request_no_crash` — không crash, không leak SQL/stack trace |

### 3.2 Health

| TC | Trạng thái | Test / Ghi chú |
| --- | --- | --- |
| TC-HEALTH-001 | DONE | `test_health_ok` |
| TC-HEALTH-002 | DONE | `test_health_while_scanning` — chèn record `status=running` rồi gọi `/health` → `scanning` |
| TC-HEALTH-003 | DONE | `test_health_idle_after_scan_completed` — sau scan xong → `idle` |
| TC-HEALTH-004 | DONE | `test_health_response_contract` — status/running_scans/registered_modules/uptime_seconds |

### 3.3 Module Registry & Architecture

| TC | Trạng thái | Test / Ghi chú |
| --- | --- | --- |
| TC-MODULE-001 | DONE | `test_list_modules` |
| TC-MODULE-002 | DONE | `test_modules_manifest_complete` — id/display_name/version/status/enabled/has_scan/last_scan + id unique |
| TC-MODULE-003 | DONE | `test_module_registry_no_duplicate_ids` — 2 module trùng ID → registry không crash, ID không lặp |
| TC-MODULE-004 | DONE | `test_module_discovery_failure_isolation` — module lỗi khi discovery không làm sập registry |
| TC-MODULE-005 | DONE | `test_core_does_not_import_modules` + `test_module_registry_only_uses_modules_namespace` — **nới lỏng 1 chút**: `core/module_registry.py` được phép đọc namespace `modules`; các file core khác cấm import ngược |
| CL-MOD-001 | DONE | `test_module_discovered_at_startup` — `discover_modules()` chứa `port-scanner` |
| CL-MOD-002 | DONE | `test_module_router_included_in_app` — route `/api/v1/modules/port-scanner/scan` tồn tại |
| CL-MOD-003 | DONE | `test_get_modules_returns_port_scanner` — GET `/modules` trả đúng `display_name` |
| CL-MOD-004 | DONE | `test_module_manifest_has_required_fields` — id/display_name/version/scanner_cls |
| CL-MOD-005 | DONE | `test_module_enabled_reflects_config` — `enabled` phản ánh cấu hình |

### 3.4 Scan API & Lifecycle

| TC | Trạng thái | Test / Ghi chú |
| --- | --- | --- |
| TC-SCAN-001 | DONE | `test_scan_endpoint_returns_scan_id` — POST scan trả `scan_id` ngay |
| TC-SCAN-002 | DONE | `test_scan_dispatch_failure_uses_error_envelope` — 500, error envelope, không leak stack trace |
| TC-SCAN-003 | DONE | `test_scan_unknown_module` — **ghi chú lệch contract**: module lạ không có route → FastAPI trả `404 HTTP_ERROR` (tài liệu ghi `MODULE_NOT_FOUND`). Test khóa hành vi thực tế. |
| TC-SCAN-004 | DONE | `test_scan_lifecycle` — running → done, result persist, truy vấn lại được |
| CL-LC-001 | DONE | `test_scan_creates_running_record` — record `status=running` ngay sau khi tạo |
| CL-LC-002 | DONE | `test_scan_completes_to_done` — scan xong → `status=done`, `summary_json` có |
| CL-LC-003 | DONE | `test_scan_items_persist` — item có đủ severity/title/detail_json/whitelist_key |
| CL-LC-004 | DONE | `test_scan_summary_correct` — 4444(danger) + 80(safe) → summary đúng |
| CL-LC-005 | DONE | `test_query_history_after_scan` — GET `/scans` chứa scan vừa chạy |
| CL-LC-006 | DONE | `test_query_latest_scan` — GET `/scans/latest` trả scan đó |
| CL-LC-007 | DONE | `test_query_scan_detail` — GET `/scans/{id}` có items array |
| CL-LC-008 | DONE | `test_partial_result_on_permission_denied` — `deny_net=True` → `partial_result=True` |
| CL-LC-009 | DONE | `test_started_at_before_finished_at` — timestamp hợp lệ |

### 3.5 Scan Persistence / History

| TC | Trạng thái | Test / Ghi chú |
| --- | --- | --- |
| TC-HISTORY-001 | DONE | `test_scan_history_empty_ok` — total=0, items=[] |
| TC-HISTORY-002 | DONE | `test_scan_and_read_history` — scan → history |
| TC-HISTORY-003 | DONE | `test_scan_and_read_history` — scan detail |
| TC-HISTORY-004 | DONE | `test_scan_and_read_history` — latest scan |
| TC-HISTORY-005 | DONE | `test_latest_scan_empty_returns_null` — contract: `200 + data=null` |
| TC-HISTORY-006 | DONE | `test_scan_detail_not_found` — `404 SCAN_NOT_FOUND` |
| TC-HISTORY-007 | DONE | `test_scan_history_pagination` — default, page=2&size=2, quá trang, page=0/size=0, size>100 |

### 3.6 Port Scanner (unit)

| TC | Trạng thái | Test / Ghi chú |
| --- | --- | --- |
| TC-SCANNER-001 | DONE | `test_run_returns_empty_result` + `test_run_classify_severities` — fake psutil connections |
| TC-SCANNER-002 | DONE | `test_process_does_not_exist_still_returns_item` — PID không tồn tại → item vẫn trả, metadata trống, không crash |
| TC-SCANNER-003 | DONE | `test_severity_matrix` (127.0.0.1 → safe) |
| TC-SCANNER-004 | DONE | `test_severity_matrix` (0.0.0.0 / :: → warning) |
| TC-SCANNER-005 | DONE | `test_severity_matrix` (risky ports **lấy từ config**: 4444/1337/31337 → danger) |
| TC-SCANNER-006 | DONE | `test_severity_matrix` — `pytest.mark.parametrize` 9 tổ hợp IP type × port type × process metadata |
| TC-SCANNER-007 | DONE | `test_service_port_mismatch` — port 22 + process sai → warning + `SERVICE_PORT_MISMATCH` |
| TC-SCANNER-008 | DONE | `test_service_port_match_no_mismatch` — port 22 + sshd → không mismatch |
| TC-SCANNER-009 | DONE | `test_risky_port_takes_priority_over_mismatch` — risky port + mismatch → danger (ưu tiên risky) |
| TC-PERM-001 | DONE | `test_run_reports_partial_permission_denied` + `test_net_connections_access_denied_returns_partial` — không đọc được connection → partial_result + warning |
| TC-PERM-002 | DONE | `test_severity_matrix` (có process metadata) + `test_whitelist_key_with_process_name` |

### 3.7 Whitelist

| TC | Trạng thái | Test / Ghi chú |
| --- | --- | --- |
| TC-WL-001..005 | DONE | `test_whitelist_crud` — CRUD + không tạo duplicate qua API |
| TC-WL-006 | DONE | `test_whitelist_delete_not_found` — `404 WHITELIST_NOT_FOUND` |
| TC-WL-007 | DONE | `test_whitelist_overrides_severity` (module test) + `test_whitelist_override_severity_via_api` (tạo whitelist qua API rồi scan lại) |
| TC-WL-008 | **SKIP** | Hệ thống hiện chỉ có 1 module (`port-scanner`) nên không thể kiểm tra uniqueness khác module cho `(module_id, whitelist_key)` |
| CL-WL-001 | DONE | `test_whitelist_override_danger_to_safe` — whitelist key `4444:proc` → severity=safe |
| CL-WL-002 | DONE | `test_whitelist_override_warning_to_safe` — whitelist port bind 0.0.0.0 → safe |
| CL-WL-003 | DONE | `test_remove_whitelist_restores_severity` — xoá whitelist → scan lại = danger gốc |
| CL-WL-004 | DONE | `test_whitelist_does_not_affect_other_items` — whitelist key này không ảnh hưởng item khác |
| CL-WL-005 | DONE | `test_whitelist_persists_across_scans` — danger → whitelist → safe → scan lần 3 vẫn safe |
| CL-WL-006 | DONE | `test_whitelist_duplicate_via_api` — thêm cùng key 2 lần → 1 record, `created=false` |

### 3.8 Diffing

| TC | Trạng thái | Test / Ghi chú |
| --- | --- | --- |
| TC-DIFF-001 | DONE | `test_diff_fixture_matrix` (scan đầu tiên → mọi item là appeared) |
| TC-DIFF-002 | DONE | `test_diff_identical_consecutive_scans` — 2 scan giống hệt → không appeared/disappeared |
| TC-DIFF-003 | DONE | `test_diff_fixture_matrix` Case B (80 → 80,443: 443 = appeared) |
| TC-DIFF-004 | DONE | `test_diff_fixture_matrix` Case C (80,443 → 80: 443 = disappeared) |
| TC-DIFF-005 | DONE | `test_diff_fixture_matrix` (persistence `scan_diff_log` đúng scan & đúng key) |
| CL-DIFF-005 | DONE | `test_diff_mix_appeared_and_disappeared` — {80,443} → {80,8080}: 443 disappeared, 8080 appeared |
| CL-DIFF-006 | DONE | `test_diff_is_new_flag` — port mới → `is_new=True`, port cũ → `is_new=False` |
| CL-DIFF-007 | DONE | `test_diff_log_scan_id_is_current` — diff log gắn với scan hiện tại |
| CL-DIFF-008 | DONE | `test_diff_across_three_scans` — {80} → {80,443} → {80}: appeared(#2) + disappeared(#3) |

### 3.9 WebSocket / Realtime

> Kỹ thuật: dùng `TestClient` portal (`client.portal.call(...)`) để chạy
> `execute_scan` trên đúng event loop của app → WS nhận event deterministic,
> không chờ real time.

| TC | Trạng thái | Test / Ghi chú |
| --- | --- | --- |
| TC-WS-001 | DONE | `test_ws_connect_valid_scan` |
| TC-WS-002 | DONE | `test_ws_invalid_scan_id_connection_accepted` — hành vi thực tế: connection vẫn accept, không lỗi, không replay |
| TC-WS-003 | DONE | `test_ws_progress_item_done_events` — **schema thực tế là** `{type, current, total, message}` (tài liệu ví dụ có `progress: 50`/`scan_id`; schema thật đang là current/total) |
| TC-WS-004 | DONE | `test_ws_progress_item_done_events` (item_found có severity/title/detail/is_new) |
| TC-WS-005 | DONE | `test_ws_progress_item_done_events` (done có scan_id/summary/partial_result) |
| TC-WS-006 | DONE | `test_ws_error_event` — scanner failure → `{type:error, code}` ổn định |
| TC-WS-007 | DONE | `test_ws_progress_item_done_events` (assert thứ tự: done luôn sau item_found) |
| TC-WS-008 | DONE | `test_ws_replay_after_done` — connect muộn → nhận done + `replay:true` |
| TC-WS-009 | DONE | `test_ws_multiple_subscribers` — 2 client cùng nhận event |
| (ngoài tài liệu) | DONE | `test_ws_global_events_channel` — kênh `/ws/events` nhận done của scan bất kỳ |
| CL-RT-001 | DONE | `test_progress_events_reach_ws_client` — WS nhận `{type:progress}` |
| CL-RT-002 | DONE | `test_item_found_events_reach_ws_client` — WS nhận `{type:item_found, item}` |
| CL-RT-003 | DONE | `test_done_event_reaches_ws_client` — WS nhận `{type:done, scan_id, summary}` |
| CL-RT-004 | DONE | `test_error_event_reaches_ws_client` — scanner fail → WS nhận `{type:error, code}` |
| CL-RT-005 | DONE | `test_event_order_progress_item_done` — progress → item_found → done |
| CL-RT-006 | DONE | `test_late_client_receives_replay` — client connect muộn → done + `replay:true` |
| CL-RT-007 | DONE | `test_two_clients_both_receive_events` — 2 WS cùng scan → cùng nhận events |
| CL-RT-008 | DONE | `test_global_channel_receives_done` — `/ws/events` nhận done từ scan bất kỳ |
| CL-RT-009 | DONE | `test_progress_message_format` — progress event có đủ `current`/`total`/`message` |

### 3.10 Event Bus

| TC | Trạng thái | Test / Ghi chú |
| --- | --- | --- |
| TC-EVENT-001 | DONE | `test_publish_subscribe` |
| TC-EVENT-002 | DONE | `test_multiple_subscribers` |
| TC-EVENT-003 | DONE | `test_unsubscribe` |
| TC-EVENT-004 | DONE | `test_wildcard_segment`, `test_wildcard_hash`, `test_match_unit` |
| UT-EV-001 | DONE | `test_match_exact` — exact match |
| UT-EV-002 | DONE | `test_match_star_wrong_segment_count` — `*` chỉ khớp đúng 1 segment |
| UT-EV-003 | DONE | `test_match_hash_tail` — `#` khớp mọi segment còn lại |
| UT-EV-004 | DONE | `test_match_no_match_different_topic` — topic khác → không khớp |

### 3.11 Scheduler

| TC | Trạng thái | Test / Ghi chú |
| --- | --- | --- |
| TC-SCHED-001 | DONE | `test_scheduler_no_schedule_no_jobs` |
| TC-SCHED-002 | DONE | `test_scheduler_registers_scheduled_job` (patch `AsyncIOScheduler.start` → không chạy loop thật) |
| TC-SCHED-003 | DONE | `test_scheduler_job_triggers_dispatch` — gọi job wrapper, assert `dispatch_scan` được gọi |
| TC-SCHED-004 | **SKIP** | Error isolation của scheduled scan do executor đảm bảo (TC-ERR-001, TC-DB-005); test timing thực tế của APScheduler sẽ vi phạm nguyên tắc deterministic |
| CL-SCH-001 | DONE | `test_scheduler_no_schedule_no_jobs` — không job khi `default_schedule=None` |
| CL-SCH-002 | DONE | `test_scheduler_has_job_when_schedule_set` — job id `scan-<module>` được đăng ký |
| CL-SCH-003 | DONE | `test_scheduled_job_triggers_dispatch` — mock trigger → `dispatch_scan` được gọi |

### 3.12 Nmap / Socket fallback

| TC | Trạng thái | Test / Ghi chú |
| --- | --- | --- |
| TC-NMAP-001 | DONE | Socket scan được cover bởi `test_run_classify_severities` |
| TC-NMAP-002 | DONE | `test_nmap_scan_parses_open_ports` — mock module `nmap`, parse đúng port open |
| TC-NMAP-003 | DONE | `test_nmap_unavailable_falls_back_to_socket` — `shutil.which` → None → fallback socket |
| TC-NMAP-004 | DONE | `test_nmap_execution_failure_falls_back_to_socket` — nmap tồn tại nhưng scan fail → fallback socket |

### 3.13 Database / Persistence

| TC | Trạng thái | Test / Ghi chú |
| --- | --- | --- |
| TC-DB-001 | DONE | `test_scan_lifecycle`, `test_scan_and_read_history` |
| TC-DB-002 | DONE | `test_scan_lifecycle` (item được lưu đúng scan) |
| TC-DB-003 | DONE | `test_diff_fixture_matrix` (appeared/disappeared được lưu) |
| TC-DB-004 | DONE | `test_whitelist_db_uniqueness` — `IntegrityError` khi vi phạm `UNIQUE(module_id, whitelist_key)` |
| TC-DB-005 | DONE | `test_transaction_rollback_on_persist_failure` — lỗi giữa lúc persist → rollback, không item mồ côi, scan → error |
| UT-DB-001 | DONE | `test_now_iso_format` — match `%Y-%m-%dT%H:%M:%S.%fZ` |
| UT-DB-002 | DONE | `test_dt_to_iso_with_datetime` |
| UT-DB-003 | DONE | `test_dt_to_iso_with_none` → None |
| UT-DB-004 | DONE | `test_database_session_scope_commit` — operation thành công → persist |
| UT-DB-005 | DONE | `test_database_session_scope_rollback_on_error` — exception → rollback |
| UT-DB-006 | DONE | `test_database_create_all_creates_tables` — scans/scan_items/whitelist_entries/scan_diff_log |

### 3.14 Error Handling / Resilience

| TC | Trạng thái | Test / Ghi chú |
| --- | --- | --- |
| TC-ERR-001 | DONE | `test_scanner_exception_error_state` + `test_ws_error_event` — scan → error, WS nhận error event, DB nhất quán |
| TC-ERR-002 | DONE | `test_db_unavailable_error_envelope` — DB fail → `500 INTERNAL_ERROR`, không leak stack trace |
| TC-ERR-003 | DONE | `test_subscriber_failure_isolation` — subscriber throw → subscriber khác vẫn nhận |
| TC-ERR-004 | DONE | `test_concurrent_scans_allowed` — **business rule đã xác định: cho phép chạy song song**; 2 dispatch → 2 scan_id, cả 2 đều done |
| CL-ERR-001 | DONE | `test_scan_error_sets_error_state` — `ScanError` → DB `status=error`, error_message |
| CL-ERR-002 | DONE | `test_generic_exception_sets_scan_failed` — `RuntimeError` → `status=error` |
| CL-ERR-003 | DONE | `test_scan_error_publishes_ws_event` — ScanError → event `{type:error, code}` |
| CL-ERR-004 | DONE | `test_generic_exception_publishes_scan_failed` — RuntimeError → event `code=SCAN_FAILED` |
| CL-ERR-005 | DONE | `test_error_scan_no_items_in_db` — scanner fail → `scan_items` rỗng |
| CL-ERR-006 | DONE | `test_error_scan_no_summary` — scanner fail → `summary_json=None` |
| CL-ERR-007 | DONE | `test_error_scan_status_error` — lỗi DB giữa lúc persist → không half-written, status error/running |
| CL-ERR-008 | DONE | `test_error_scan_does_not_crash_app` — `execute_scan` không để exception thoát ra ngoài |

### 3.15 Input Validation

| TC | Trạng thái | Test / Ghi chú |
| --- | --- | --- |
| TC-VALID-001 | DONE | Gộp vào `test_scan_unknown_module` (module_id không tồn tại → 404) |
| TC-VALID-002 | DONE | `test_whitelist_validation` — thiếu field/blank → 400/422; sai kiểu → 422 |
| TC-VALID-003 | DONE | `test_pagination_validation` + `test_scan_history_pagination` — page<1, size<1, size>100 được clamp (200, không 422) |

### 3.16 Unit test — Config (`core/config.py`)

| ID | Trạng thái | Test / Ghi chú |
| --- | --- | --- |
| UT-CONFIG-001 | DONE | `test_config_load_from_yaml` — Config đọc đúng giá trị từ file YAML tạm |
| UT-CONFIG-002 | DONE | `test_config_missing_file_uses_defaults` — file không tồn tại → default, không crash |
| UT-CONFIG-003 | DONE | `test_config_module_unknown_returns_disabled` — module lạ → `ModuleSettings(enabled=False)` |
| UT-CONFIG-004 | DONE | `test_config_module_known` — module có trong config → trả đúng settings |
| UT-CONFIG-005 | DONE | `test_ensure_local_token_generates_when_empty` — token rỗng → generate + persist |
| UT-CONFIG-006 | DONE | `test_ensure_local_token_existing` — token có sẵn → không ghi đè |
| UT-CONFIG-007 | DONE | `test_module_settings_from_config_full` — parse enabled/schedule/extra |
| UT-CONFIG-008 | DONE | `test_module_settings_from_config_empty` — None/{} → default |
| UT-CONFIG-009 | DONE | `test_module_settings_get_existing_key` — `get("scan_mode")` |
| UT-CONFIG-010 | DONE | `test_module_settings_get_missing_key` — key không có → default |

### 3.17 Unit test — Envelope (`api/envelope.py`)

| ID | Trạng thái | Test / Ghi chú |
| --- | --- | --- |
| UT-ENV-001 | DONE | `test_ok_with_dict` |
| UT-ENV-002 | DONE | `test_ok_with_list` |
| UT-ENV-003 | DONE | `test_ok_with_none` — data=null |
| UT-ENV-004 | DONE | `test_fail_creates_error_envelope` — `{success:false, data:null, error:{code,message}}` |
| UT-ENV-005 | DONE | `test_fail_error_code_exact` — error.code đúng giá trị truyền vào |

### 3.18 Unit test — Executor helpers (`core/executor.py`)

| ID | Trạng thái | Test / Ghi chú |
| --- | --- | --- |
| UT-EXEC-001 | DONE | `test_mark_failed_updates_status` — status=error, error_message set, finished_at |
| UT-EXEC-002 | DONE | `test_mark_failed_scan_not_found` — không crash |
| UT-EXEC-003 | DONE | `test_previous_scan_returns_predecessor` |
| UT-EXEC-004 | DONE | `test_previous_scan_first_scan_returns_none` |
| UT-EXEC-005 | DONE | `test_previous_scan_excludes_current` |
| UT-EXEC-006 | DONE | `test_keys_of_scan_returns_keys` |
| UT-EXEC-007 | DONE | `test_keys_of_scan_empty` |
| UT-EXEC-008 | DONE | `test_whitelist_keys_returns_keys` |
| UT-EXEC-009 | DONE | `test_whitelist_keys_empty` |
| UT-EXEC-010 | DONE | `test_whitelist_keys_per_module` — query module A không trả key của module B |

### 3.19 Unit test — Scanner utilities

| ID | Trạng thái | Test / Ghi chú |
| --- | --- | --- |
| UT-SC-001 | DONE | `test_build_summary_correct_counts` — 3 danger/2 warning/5 safe |
| UT-SC-002 | DONE | `test_build_summary_empty` — all 0 |
| UT-SC-003 | DONE | `test_nmap_ports_with_risky_above_1024` — output chứa `1-1024,4444,8080` |
| UT-SC-004 | DONE | `test_nmap_ports_no_risky_above_1024` — output = `1-1024` |
| UT-SC-005 | DONE | `test_build_summary_mix_severities` |

### 3.20 Config → Scanner behavior

| ID | Trạng thái | Test / Ghi chú |
| --- | --- | --- |
| CL-CS-001 | DONE | `test_custom_risky_ports_from_config` — config `[22, 8080]` → 22/8080 danger, 4444 safe |
| CL-CS-002 | DONE | `test_default_risky_ports` — không config → default [4444, 1337, 31337] |
| CL-CS-003 | DONE | `test_socket_mode_default` — `scan_mode` mặc định = `socket` |
| (extra) | DONE | `test_module_settings_custom_risky_ports` — `ModuleSettings.get("known_risky_ports")` |

### 3.21 Frontend / E2E

| TC | Trạng thái | Ghi chú |
| --- | --- | --- |
| TC-E2E-001..004 | **SKIP** | Cần môi trường frontend E2E (React + Playwright/Cypress) — ngoài phạm vi `./backend/tests/`; không thay thế bằng integration test |

---

## 4. Các test vẫn còn SKIP / chưa làm

| TC | Lý do |
| --- | --- |
| TC-WL-008 | Chỉ có 1 module (port-scanner), không có cặp module để kiểm tra key trùng tên ở module khác |
| TC-SCHED-004 | Error isolation do executor đảm bảo; test timing APScheduler thật vi phạm determinism |
| TC-SEC-002 | Chưa có rate limit / lockout trong hệ thống |
| TC-E2E-001..004 | Cần hạ tầng E2E frontend, ngoài phạm vi `./backend/tests/` |

---

## 5. Ghi chú lệch contract & phát hiện khi viết test

1. **TC-SCAN-003 / TC-VALID-001** — `POST /api/v1/modules/unknown/scan` trả
   `404 HTTP_ERROR` (không có route cho module lạ), trong khi tài liệu mô tả
   `404 MODULE_NOT_FOUND`. Test khóa hành vi hiện tại; nếu muốn contract
   `MODULE_NOT_FOUND`, cần thêm route wildcard `/{module_id}/scan` chung.
2. **TC-WS-003** — event `progress` thực tế có dạng `{type, current, total,
   message}`; ví dụ trong tài liệu dùng `{progress: 50}` + `scan_id`. Schema
   hiện tại không chứa `scan_id` và dùng `current/total` thay vì `progress`.
3. **TC-ERR-001** — `error_message` lưu message (không kèm `code`); `code`
   chỉ xuất hiện trong event WebSocket. Không phải lỗi, chỉ là điểm cần biết.
4. **Test stale đã sửa (mục 1)** — `test_config_scanner.py::test_custom_risky_ports_from_config`
   assert contract cũ của `_classify` (trả `(severity, message_str)`). Contract
   hiện tại trả `(severity, reasons: list[str])` theo `scanner.py` (mã
   `PORT_IN_RISKY_LIST` / `SERVICE_PORT_MISMATCH` / ...). Test đã được cập nhật
   để khóa đúng contract hiện hành.

---

## 6. Kết quả chạy

```text
$ pytest
169 passed, 1 warning in ~4.9s
```

- Chạy lại nhiều lần liên tiếp → ổn định, không flaky.
- Không phụ thuộc: Internet, port thật đang mở, Nmap cài trên máy, DB
  production/development, thời gian thực.
- Mọi test dùng DB SQLite tạm trong `tmp_path_factory`.
- 1 warning duy nhất: `StarletteDeprecationWarning` (FastAPI TestClient dùng
  `httpx` cũ) — không ảnh hưởng kết quả.