# Active Module — Thiết kế chi tiết

> Tài liệu bổ sung cho `Security Audit Tool`. Mô tả nhánh **Active** (chủ động) song song với nhánh **Passive** (thụ động) hiện có, khởi đầu bằng module **Port Process Simulator**, cùng đề xuất mở rộng để nhánh Active trở nên toàn vẹn.

---

## Mục lục

- [1. Passive vs Active — vì sao cần tách nhánh](#1-passive-vs-active--vì-sao-cần-tách-nhánh)
- [2. Module đề xuất: Port Process Simulator](#2-module-đề-xuất-port-process-simulator)
- [3. Kiến trúc: `ActiveServiceBase` + `ActiveServiceManager`](#3-kiến-trúc-activeservicebase--activeservicemanager)
- [4. Cấu trúc thư mục module](#4-cấu-trúc-thư-mục-module)
- [5. Cấu hình (`config.yaml`)](#5-cấu-hình-configyaml)
- [6. Data model](#6-data-model)
- [7. API Reference](#7-api-reference)
- [8. Realtime: Event Bus / WebSocket](#8-realtime-event-bus--websocket)
- [9. Tương tác với module Passive](#9-tương-tác-với-module-passive)
- [10. Độc lập & song song — cơ chế đảm bảo](#10-độc-lập--song-song--cơ-chế-đảm-bảo)
- [11. An toàn & rủi ro](#11-an-toàn--rủi-ro)
- [12. Frontend](#12-frontend)
- [13. Gợi ý mở rộng nhánh Active](#13-gợi-ý-mở-rộng-nhánh-active)
- [14. Lộ trình triển khai đề xuất](#14-lộ-trình-triển-khai-đề-xuất)

---

## 1. Passive vs Active — vì sao cần tách nhánh

Toàn bộ module hiện tại (Port Scanner, và các stub Firewall Check / Process Monitor) đều là **passive**: chỉ *đọc* trạng thái hệ thống tại một thời điểm rồi kết thúc (`ScannerBase.run()` chạy một lần, trả `ScanResult`, xong là hết vòng đời).

Module **active** khác về bản chất trên 3 điểm, nên không thể ép vào `ScannerBase`:

| Tiêu chí | Passive (`ScannerBase`) | Active (đề xuất) |
|---|---|---|
| Vòng đời | Chạy một lần rồi kết thúc (`run()` → `ScanResult`) | Chạy nền liên tục cho tới khi bị dừng (`start()` / `stop()`) |
| Tác động hệ thống | Chỉ đọc (socket, WMI, registry...) | Chủ động tạo trạng thái mới (bind port, spawn process, mở kết nối...) |
| Kết quả | Một `ScanResult` trả về sau khi hoàn tất | Một **stream sự kiện** phát sinh trong lúc service đang chạy (vd có ai đó connect tới cổng giả) |

Vì vậy nhánh Active cần một base class và một manager lifecycle riêng, sống **song song** với `core/scanner_base.py` và `core/executor.py` hiện có, không sửa đổi chúng — giữ đúng nguyên tắc `modules → core`, module mới không đụng file lõi.

---

## 2. Module đề xuất: Port Process Simulator

**Nghiệp vụ**: chủ động bind (lắng nghe thật) trên nhiều cổng TCP/UDP cấu hình được, mỗi cổng có thể gán:

- `process_name` — tên tiến trình giả lập hiển thị khi bị Port Scanner (passive) quét tới (vd `rdp_fake.exe`, `mysql_decoy.exe`).
- `description` — mô tả nghiệp vụ/mục đích của cổng giả (vd "Giả lập RDP để test cảnh báo cổng nguy hiểm").
- `protocol` — `tcp` hoặc `udp`.
- `banner` *(tuỳ chọn)* — chuỗi trả lời khi có kết nối tới, mô phỏng service thật (vd banner SSH/FTP) để test các công cụ dò quét khác ngoài chính tool này.

**Mục đích sử dụng**:

1. Tự kiểm tra (self-check) module Port Scanner: cổng mới xuất hiện có được gắn badge **NEW** đúng không, mức rủi ro (`danger`/`warning`/`safe`) có phân loại đúng theo `known_risky_ports` không.
2. Làm honeypot cá nhân: nếu có kết nối tới một cổng giả lập không ai biết tới ngoài chủ máy, đó là tín hiệu bất thường đáng ngờ.
3. Là "nguồn dữ liệu test" ổn định, lặp lại được cho CI/pytest — không phụ thuộc trạng thái máy thật như các module passive khác.

---

## 3. Kiến trúc: `ActiveServiceBase` + `ActiveServiceManager`

### 3.1 `core/active_service_base.py` *(mới, không sửa `scanner_base.py`)*

```python
class ServiceStatus(str, Enum):
    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    ERROR = "error"

class ActiveServiceBase(ABC):
    @abstractmethod
    async def start(self) -> None: ...
    @abstractmethod
    async def stop(self) -> None: ...
    @abstractmethod
    def status(self) -> ServiceStatus: ...
    @abstractmethod
    def get_config_schema(self) -> dict: ...
    # hook tuỳ chọn: mỗi lần có sự kiện (vd 1 kết nối tới cổng giả)
    async def emit(self, event_type: str, payload: dict) -> None: ...
```

### 3.2 `core/active_service_manager.py` *(mới, song song với `module_registry.py`)*

- Tự phát hiện các module có khai báo `is_active: true` trong manifest (mở rộng `ModuleManifest`, thêm field `service_cls: type[ActiveServiceBase] | None`), tương tự cách `discover_modules()` hiện đang quét `modules/`.
- Giữ một registry `{module_id: ActiveServiceBase instance}` độc lập với registry passive.
- Expose `start(module_id)`, `stop(module_id)`, `stop_all()` (gọi khi app shutdown để đảm bảo dọn socket), `status_all()`.
- `stop_all()` được đăng ký vào FastAPI lifespan/shutdown event trong `main.py` — đây là điểm chạm duy nhất vào file lõi khi thêm cơ chế active, và chỉ cần thêm **một lần** cho toàn bộ nhánh, không phải mỗi module.

### 3.3 Vì sao dùng `asyncio.start_server` thay vì thread/process riêng

Toàn bộ backend đã chạy trên `asyncio` (FastAPI + Starlette WS). Mỗi cổng giả lập chỉ cần là một `asyncio.start_server(...)` task nhẹ, sống trong cùng event loop:

- Không tốn thread/process riêng cho mỗi cổng → nhẹ khi cấu hình hàng chục cổng.
- Không chặn (block) vòng lặp sự kiện chính — request REST, WebSocket scan, scheduler vẫn chạy bình thường song song.
- Dễ `cancel()` từng task riêng lẻ khi `stop()` một module mà không ảnh hưởng module active khác.

---

## 4. Cấu trúc thư mục module

```
backend/modules/port_simulator/
├── manifest.py     # ActiveModuleManifest: id, display_name, version, service_cls, is_active=True
├── service.py       # implement ActiveServiceBase — quản lý N asyncio.start_server theo config
├── routes.py         # REST riêng: start / stop / status / CRUD cổng / lịch sử hits
├── models.py           # bảng riêng: port_simulator_ports, port_simulator_hits
└── tests/                # test start/stop, giả lập kết nối tới cổng, không phụ thuộc máy thật
```

Đúng convention hiện có: thêm thư mục, không sửa `main.py`, `module_registry.py` (trừ 1 lần đăng ký `stop_all()` ở mục 3.2), không sửa `port_scanner/`.

---

## 5. Cấu hình (`config.yaml`)

```yaml
modules:
  port-simulator:
    enabled: false          # mặc định tắt — chủ động opt-in vì đây là module active
    is_active: true
    bind_host: 127.0.0.1    # mặc định chỉ localhost, xem mục 11
    max_ports: 32            # giới hạn số cổng giả lập cùng lúc
    ports:
      - port: 8081
        protocol: tcp
        process_name: "fake_rdp.exe"
        description: "Giả lập RDP để test cảnh báo cổng nguy hiểm"
        banner: null
      - port: 9090
        protocol: tcp
        process_name: "mysql_decoy.exe"
        description: "Giả lập MySQL để test whitelist"
        banner: "5.7.31-log\n"
```

---

## 6. Data model

Thêm 2 bảng riêng cho module (không đụng bảng chung `scans` / `scan_items` vì bản chất dữ liệu khác — không phải một "lượt quét" mà là "một phiên chạy service"):

| Bảng | Mô tả |
|---|---|
| `port_simulator_ports` | Cấu hình từng cổng: `port`, `protocol`, `process_name`, `description`, `banner`, `enabled` |
| `port_simulator_hits` | Log mỗi kết nối tới cổng giả: `port`, `remote_addr`, `protocol`, `timestamp`, `bytes_received` |

Đồng thời đề xuất thêm **1 bảng chung mới** (song song với `scans`, dùng được cho mọi module active tương lai, tương tự vai trò `detail_json` tự do đã dùng cho passive):

| Bảng | Mô tả |
|---|---|
| `active_service_runs` | `id`, `module_id`, `status` (`running`/`stopped`/`error`), `started_at`, `stopped_at`, `config_snapshot_json` — lịch sử mỗi lần start/stop một active service, phục vụ audit "module active nào đã chạy khi nào" |

---

## 7. API Reference

Theo đúng convention `/api/v1/modules/{module_id}/...`, router riêng trong `module.router`:

| Method | Endpoint | Mô tả |
|---|---|---|
| POST | `/api/v1/modules/port-simulator/start` | Khởi động service — bind tất cả cổng đang `enabled` trong config |
| POST | `/api/v1/modules/port-simulator/stop` | Dừng service — đóng toàn bộ socket đang mở |
| GET | `/api/v1/modules/port-simulator/status` | Trạng thái hiện tại + số cổng đang lắng nghe |
| GET | `/api/v1/modules/port-simulator/ports` | Danh sách cổng đã cấu hình |
| POST | `/api/v1/modules/port-simulator/ports` | Thêm cổng giả lập mới (`port`, `process_name`, `description`, `protocol`, `banner?`) |
| DELETE | `/api/v1/modules/port-simulator/ports/{id}` | Gỡ một cổng khỏi cấu hình |
| GET | `/api/v1/modules/port-simulator/hits` | Lịch sử kết nối tới các cổng giả (phân trang) |

---

## 8. Realtime: Event Bus / WebSocket

Tái sử dụng `core/event_bus.py` và kênh `WS /ws/events` **đã có sẵn** cho scan tự động — không cần mở kênh WebSocket riêng cho active module:

```json
{ "type": "active.port-simulator.started", "module_id": "port-simulator", "ports": [8081, 9090] }
```

```json
{ "type": "active.port-simulator.hit", "module_id": "port-simulator", "port": 8081, "remote_addr": "127.0.0.1", "timestamp": "..." }
```

```json
{ "type": "active.port-simulator.stopped", "module_id": "port-simulator" }
```

Nhờ dùng chung topic wildcard pub/sub sẵn có, frontend chỉ cần subscribe thêm prefix `active.*` trên đúng kênh `/ws/events` hiện tại — không phải sửa `web_socket.py`.

---

## 9. Tương tác với module Passive

- Khi Port Simulator đang chạy, Port Scanner (passive) quét máy **sẽ tự nhìn thấy** các cổng giả này đang `LISTEN` — đây chính là mục đích self-check.
- Để tránh gây nhiễu dashboard chính bằng dữ liệu giả lặp lại mỗi lần quét, đề xuất:
  - Gắn `whitelist_key` dạng đặc biệt (vd prefix `sim:`) để Port Scanner có thể *tuỳ chọn* lọc riêng nhóm "cổng do chính công cụ tạo ra" thay vì trộn chung với cổng thật.
  - Hoặc thêm cờ `source: "simulated"` vào `detail_json` của `scan_items` khi Port Scanner phát hiện cổng trùng khớp với cấu hình đang chạy của Port Simulator (so khớp qua service `active_service_manager.status_all()` lúc quét) — không đổi schema bảng chung, tận dụng đúng thiết kế `detail_json` tự do đã có.

---

## 10. Độc lập & song song — cơ chế đảm bảo

| Yêu cầu | Cách đáp ứng |
|---|---|
| **Độc lập** (module active này không phụ thuộc module active khác, khởi động/tắt riêng lẻ) | Mỗi module active có `ActiveServiceBase` instance riêng, `start()`/`stop()` không gọi chéo sang instance khác; `ActiveServiceManager` quản lý theo `module_id`, lỗi ở service này không cancel task của service kia. |
| **Song song** (nhiều module active chạy cùng lúc) | Toàn bộ chạy trên cùng event loop `asyncio` không chặn nhau; mỗi service tự quản `asyncio.TaskGroup`/`set[Task]` riêng cho các cổng của mình. |
| **Dùng chung trong 1 dự án** | Cùng đăng ký qua `ModuleManifest` mở rộng (`is_active`), cùng dùng `Event Bus`, `WS /ws/events`, envelope response, `X-Local-Token` guard, và cùng convention route `/api/v1/modules/{id}/...` như module passive — không tạo hệ thống song song khác biệt về mặt hạ tầng, chỉ khác về lifecycle base class. |
| **Không xung đột cổng vật lý** | `ActiveServiceManager` kiểm tra trùng cổng giữa các module active trước khi `start()`, trả lỗi rõ ràng (`PORT_ALREADY_IN_USE_BY_MODULE`) thay vì để hệ điều hành báo lỗi bind mơ hồ. |

---

## 11. An toàn & rủi ro

> ⚠️ Nhánh Active thay đổi trạng thái thật của máy (mở cổng thật), rủi ro cao hơn passive — cần rào chắn rõ ràng.

- **Mặc định `bind_host: 127.0.0.1`** — chỉ cổng giả lập trên chính máy mới thấy, giống nguyên tắc bind của backend hiện tại.
- Nếu người dùng chủ động đổi sang `0.0.0.0` (để test từ máy khác trong LAN), UI **phải hiện cảnh báo rõ ràng** và log sự kiện `active.*.exposed_externally` — vì lúc đó cổng giả lập là cổng *thật*, mở ra ngoài thật.
- **`max_ports`** giới hạn số cổng cấu hình cùng lúc, tránh vô tình gây cạn tài nguyên (file descriptor) trên máy cá nhân.
- **Graceful shutdown bắt buộc**: `stop_all()` phải chạy khi app tắt (`main.py` lifespan) để không để sót socket mở treo sau khi tắt backend.
- **Không nên bật mặc định** (`enabled: false`) — đây là module người dùng chủ động bật để tự kiểm tra, không phải chạy nền liên tục như port scanner theo lịch.
- Vì bản chất gần với honeypot cá nhân, chỉ nên dùng trên máy cá nhân của chính mình để tự kiểm tra — không dùng để mô phỏng dịch vụ trên hạ tầng không thuộc quyền sở hữu/không có sự cho phép rõ ràng.

---

## 12. Frontend

- `frontend/src/modules/port-simulator/`: copy từ `_template/`, dùng `ModulePageLayout` như các module khác.
- `Page.tsx` gồm:
  - Toggle **Start/Stop** service + `StatusBadge` (Idle / Running (N cổng) / Error).
  - `DataTable` CRUD danh sách cổng cấu hình (port, protocol, process_name, description, banner).
  - Bảng **Hits** cập nhật real-time qua `/ws/events` (giống cách Scan History nhận dữ liệu qua kênh toàn cục hiện tại).
- Sidebar: badge riêng biệt màu khác với badge "cần xem" của passive (vd icon dạng "radar phát" thay vì "kính lúp") để phân biệt trực quan hai nhánh Active/Passive ngay trên sidebar.

---

## 13. Gợi ý mở rộng nhánh Active

Để nhánh Active toàn vẹn, cùng chung `ActiveServiceBase`/`ActiveServiceManager` vừa thiết kế ở trên:

1. **Firewall Rule Tester** — chủ động tạo/xoá rule test trên Windows Firewall (`netsh advfirewall firewall add rule ...`) để kiểm chứng module passive `Firewall Check` (đang là stub trong lộ trình) đọc đúng rule vừa tạo/xoá. Đây là cặp active/passive tương tự Port Simulator ↔ Port Scanner.

2. **Outbound Connection Simulator** — chủ động mở kết nối outbound tới địa chỉ test cấu hình được, để kiểm tra module passive `Outbound Connections` (đã có trong lộ trình) có ghi nhận đúng kết nối và rule firewall chặn outbound có hoạt động không.

3. **Dummy Process Spawner** — spawn một tiến trình con vô hại, đặt tên/tiêu đề tuỳ chỉnh, để kiểm tra `Process Monitor` và `Startup Programs` (đã có trong lộ trình) có phát hiện đúng tiến trình mới xuất hiện.

4. **Detection Coverage Runner** — kịch bản tổ hợp: bật đồng thời nhiều active service (Port Simulator + Dummy Process Spawner + Outbound Simulator), chờ một khoảng thời gian, rồi tự động đối chiếu với kết quả các module passive tương ứng → sinh báo cáo "Detection Coverage Report" (module nào bắt được / bỏ sót bao nhiêu %). Đây là lớp lắp ráp phía trên các active service riêng lẻ, không phải một service mới bind port.

5. **Scheduled Active Test Suite** — tận dụng `APScheduler` đã có sẵn cho passive (`default_schedule`), mở rộng để chạy `Detection Coverage Runner` theo lịch định kỳ (vd mỗi tuần), tự động cảnh báo nếu coverage giảm so với baseline — phát hiện sớm khi một thay đổi hệ thống làm hỏng khả năng phát hiện.

6. **Baseline Recorder & Auto-Restore** — chụp snapshot trạng thái máy (cổng đang mở, rule firewall, danh sách startup) trước khi chạy bất kỳ active test nào, và tự động khôi phục sau khi test xong (đặc biệt quan trọng cho Firewall Rule Tester — đảm bảo không để sót rule test trên máy thật). Nên triển khai như một service dùng chung (`core` hoặc một module `active-baseline`), được các active module khác gọi trước/sau vòng đời `start()/stop()` của chúng.

---

## 14. Lộ trình triển khai đề xuất

- [ ] `core/active_service_base.py` + `core/active_service_manager.py` (hạ tầng dùng chung, một lần cho toàn nhánh)
- [ ] Mở rộng `ModuleManifest` với `is_active` + `service_cls`, `discover_modules()` nhận diện cả hai loại
- [ ] Đăng ký `stop_all()` vào lifespan shutdown của `main.py`
- [ ] Module **Port Process Simulator** (module active đầu tiên, hoàn chỉnh backend + frontend + tests)
- [ ] Bảng chung `active_service_runs`
- [ ] Cờ liên kết `source: "simulated"` trong `detail_json` của Port Scanner khi trùng cấu hình Port Simulator
- [ ] Các module active tiếp theo theo thứ tự ưu tiên: Firewall Rule Tester → Outbound Connection Simulator → Dummy Process Spawner → Detection Coverage Runner → Scheduled Active Test Suite → Baseline Recorder
