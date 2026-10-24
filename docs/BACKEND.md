# Current implementation note

Firewall Check v1 is implemented in `modules/firewall_check/`, using a fixed, read-only Windows PowerShell query and the existing ScannerBase/executor/storage/WebSocket pipeline. The four authenticated endpoints and JSON fields are documented in the root README and FastAPI OpenAPI descriptions. `api/scan_results.py` serializes results for both modules. Diff baselines use only completed, full snapshots. Port Scanner now uses psutil only; legacy Nmap configuration is converted without deleting historical data. Earlier future-module references below describe the initial design.

# BACKEND.md — Security Audit Tool

Tài liệu thiết kế chi tiết backend. Đi kèm `DESIGN.md` (thiết kế UI) và `requirements.txt`.

---

## 1. Mục tiêu & ràng buộc thiết kế

- Chạy **local**, phục vụ đúng 1 người dùng (chính chủ máy) — không cần multi-tenant, nhưng vẫn cần auth tối thiểu vì API có thể đọc thông tin nhạy cảm (tiến trình, process path).
- **Module hoá**: thêm chức năng kiểm tra mới (firewall, startup programs...) không được sửa code lõi (routing, scheduler, storage).
- **Real-time**: một lượt quét có thể mất vài giây đến vài chục giây → UI cần thấy tiến trình, không chỉ đợi kết quả cuối.
- **Lưu lịch sử**: mọi lượt quét phải lưu lại để so sánh "cái gì mới xuất hiện" giữa các lần — đây là giá trị cốt lõi của một security tool, không chỉ là snapshot đơn lẻ.

---

## 2. Kiến trúc tổng quan

```
┌─────────────────────────────────────────────────────────┐
│                        FastAPI App                        │
│  ┌───────────────┐   ┌──────────────┐   ┌──────────────┐ │
│  │  REST Routes  │   │  WebSocket   │   │  Scheduler   │ │
│  │ /api/v1/...   │   │  /ws/scan    │   │ (APScheduler)│ │
│  └───────┬───────┘   └──────┬───────┘   └──────┬───────┘ │
│          │                  │                  │         │
│          └──────────┬───────┴──────────┬───────┘         │
│                      ▼                  ▼                 │
│              ┌───────────────┐  ┌───────────────┐         │
│              │ Module Registry│  │  Event Bus    │         │
│              │  (core)        │  │  (core)       │         │
│              └───────┬───────┘  └───────┬───────┘         │
│                      ▼                  ▼                 │
│    ┌─────────────────────────────────────────────────┐   │
│    │                  Modules                          │  │
│    │  port_scanner/   firewall_check/   ...            │  │
│    │  (ScannerBase implementation, mỗi module tự chứa) │  │
│    └─────────────────────┬───────────────────────────┘   │
│                          ▼                                 │
│                  ┌───────────────┐                         │
│                  │  Storage (DB) │  SQLite qua SQLAlchemy   │
│                  └───────────────┘                         │
└─────────────────────────────────────────────────────────┘
```

**Nguyên tắc cốt lõi:** `core/` không bao giờ import ngược từ `modules/`. Chiều phụ thuộc luôn là `modules → core`, không bao giờ ngược lại. Đây là điều kiện bắt buộc để thêm/bớt module không phá vỡ phần lõi.

---

## 3. Module system (backend)

### 3.1 `ScannerBase` — hợp đồng mọi module phải tuân theo

```python
# core/scanner_base.py
from abc import ABC, abstractmethod
from pydantic import BaseModel

class ScanResultItem(BaseModel):
    """1 dòng kết quả, module tự định nghĩa schema con kế thừa từ đây."""
    severity: str          # "safe" | "warning" | "danger"
    title: str
    detail: dict            # payload riêng của module (vd: port, pid, process_name)

class ScanResult(BaseModel):
    module_id: str
    started_at: str
    finished_at: str
    items: list[ScanResultItem]
    summary: dict            # số liệu cho KPI row trên UI

class ScannerBase(ABC):
    module_id: str           # phải trùng với id khai báo trong manifest
    display_name: str

    @abstractmethod
    async def run(self, progress_cb=None) -> ScanResult:
        """
        progress_cb: callback(current: int, total: int, message: str)
        được gọi trong lúc quét để đẩy tiến trình qua WebSocket.
        """
        ...

    def get_whitelist_key(self, item: ScanResultItem) -> str:
        """Sinh khoá định danh để so sánh với whitelist / lần quét trước.
        Mỗi module override theo logic riêng (vd: port_scanner dùng 'port:pid_name')."""
        raise NotImplementedError
```

### 3.2 Module manifest (backend) — song song với manifest frontend

```python
# modules/port_scanner/manifest.py
from core.module_registry import ModuleManifest
from .scanner import PortScannerModule

manifest = ModuleManifest(
    id="port-scanner",
    display_name="Port Scanner",
    version="0.1.0",
    scanner_cls=PortScannerModule,
    router=None,              # optional: router riêng nếu module cần endpoint đặc thù
    default_schedule=None,    # cron string nếu muốn tự động chạy định kỳ
)
```

### 3.3 Registry tự động quét module

```python
# core/module_registry.py
import importlib, pkgutil
import modules

def discover_modules() -> dict[str, ModuleManifest]:
    found = {}
    for _, name, ispkg in pkgutil.iter_modules(modules.__path__):
        if not ispkg:
            continue
        mod = importlib.import_module(f"modules.{name}.manifest")
        found[mod.manifest.id] = mod.manifest
    return found
```

Registry chạy 1 lần khi app khởi động (`main.py` gọi `discover_modules()`), kết quả dùng để:
- Sinh route `/api/v1/modules` (danh sách module cho sidebar bên frontend).
- Đăng ký router riêng của module (nếu có) vào app FastAPI qua `app.include_router(...)`.
- Đăng ký `default_schedule` vào APScheduler nếu module khai báo lịch chạy tự động.

**Kết quả:** thêm module mới = thêm thư mục `modules/ten_module/` với `manifest.py` + `scanner.py` implement `ScannerBase` → không sửa `main.py`, không sửa `module_registry.py`.

---

## 4. API design

Base path: `/api/v1`. Toàn bộ response bọc trong envelope thống nhất:

```json
{
  "success": true,
  "data": { ... },
  "error": null
}
```

Khi lỗi:
```json
{
  "success": false,
  "data": null,
  "error": { "code": "SCAN_PERMISSION_DENIED", "message": "Cần quyền Administrator để đọc toàn bộ tiến trình." }
}
```

### 4.1 Module & hệ thống

| Method | Endpoint | Mô tả |
|---|---|---|
| GET | `/api/v1/modules` | Danh sách module đã đăng ký (id, tên, trạng thái, có scan gần nhất không) — nguồn dữ liệu cho sidebar |
| GET | `/api/v1/health` | Health check, dùng cho UI hiện trạng "Idle/Scanning" ở sidebar footer |

### 4.2 Port Scanner module

| Method | Endpoint | Mô tả |
|---|---|---|
| POST | `/api/v1/modules/port-scanner/scan` | Bắt đầu 1 lượt quét mới (async — trả `scan_id` ngay, kết quả đẩy qua WebSocket) |
| GET | `/api/v1/modules/port-scanner/scans` | Lịch sử các lượt quét (phân trang) |
| GET | `/api/v1/modules/port-scanner/scans/{scan_id}` | Chi tiết 1 lượt quét (toàn bộ port + trạng thái) |
| GET | `/api/v1/modules/port-scanner/scans/latest` | Kết quả lượt quét gần nhất — dùng để render dashboard khi mới load trang |
| GET | `/api/v1/modules/port-scanner/whitelist` | Danh sách whitelist hiện tại |
| POST | `/api/v1/modules/port-scanner/whitelist` | Thêm 1 mục vào whitelist (đánh dấu "an toàn") |
| DELETE | `/api/v1/modules/port-scanner/whitelist/{id}` | Gỡ khỏi whitelist |

**Thiết kế endpoint theo pattern chung `/api/v1/modules/{module_id}/...`** — mọi module tương lai (firewall-check, startup-programs) đi theo đúng convention này, tách route theo `module.router` riêng (mục 3.2), không dồn hết vào 1 file `routes.py` khổng lồ.

### 4.3 WebSocket

`WS /ws/scan/{scan_id}`

Server đẩy các message dạng:

```json
{ "type": "progress", "current": 340, "total": 1024, "message": "Đang kiểm tra cổng 8080..." }
{ "type": "item_found", "item": { "severity": "danger", "title": "Port 4444", "detail": {...} } }
{ "type": "done", "scan_id": "abc123", "summary": { "total_open": 27, "danger": 3, "warning": 2, "safe": 22 } }
{ "type": "error", "code": "SCAN_PERMISSION_DENIED", "message": "..." }
```

Frontend subscribe ngay sau khi gọi `POST .../scan` nhận được `scan_id`. Thiết kế này cho phép **mọi module dùng chung 1 kênh WebSocket theo `scan_id`**, không cần mở endpoint WS riêng cho từng module.

---

## 5. Luồng hoạt động (sequence)

### 5.1 Luồng quét thủ công (người dùng bấm "Quét ngay")

```
User (UI)          FastAPI              PortScannerModule        DB            WebSocket
   │  POST /scan       │                       │                  │                │
   │──────────────────>│                       │                  │                │
   │                    │ tạo scan_id, lưu      │                  │                │
   │                    │ record status=running │─────────────────>│                │
   │                    │──────────────────────>│                  │                │
   │  { scan_id }       │                       │                  │                │
   │<──────────────────│                       │                  │                │
   │  WS connect /ws/scan/{scan_id}                                                 │
   │────────────────────────────────────────────────────────────────────────────────>│
   │                    │  await module.run(progress_cb)                             │
   │                    │                       │  psutil.net_connections()          │
   │                    │                       │  với mỗi port: đối chiếu whitelist  │
   │                    │                       │──progress_cb()─────────────────────>│ (progress msg)
   │                    │                       │──progress_cb() (item_found)─────────>│
   │                    │                       │  ... lặp đến khi xong               │
   │                    │  ghi ScanResult vào DB │                  │                │
   │                    │──────────────────────────────────────────>│                │
   │                    │  so sánh với lượt trước → đánh dấu "new"  │                │
   │                    │  broadcast "done" + summary                                │
   │                    │────────────────────────────────────────────────────────────>│
   │  UI cập nhật KPI, bảng, radar map từ message "done"                              │
```

### 5.2 Luồng quét tự động (scheduler)

APScheduler gọi thẳng `module.run()` theo cron đã cấu hình trong `config.yaml`, **không qua** REST endpoint — vì đây là tiến trình nội bộ, không có request HTTP. Kết quả vẫn ghi DB và **broadcast qua WebSocket tới mọi client đang mở** (nếu có ai đang mở UI, họ thấy cập nhật realtime dù không phải người bấm nút quét) qua `event_bus`.

### 5.3 So sánh & phát hiện bất thường (diffing logic)

Đây là phần logic quan trọng nhất về mặt bảo mật, nằm trong `core/`, dùng chung cho mọi module (không riêng port scanner):

1. Sau khi `module.run()` trả `ScanResult`, với mỗi `item` gọi `module.get_whitelist_key(item)` để sinh khoá định danh.
2. So khoá này với bảng `whitelist_entries` (đã được người dùng xác nhận an toàn trước đó) → nếu có, `severity` override thành `safe`.
3. So với `ScanResult` liền trước của cùng module → khoá nào **chưa từng xuất hiện** → gắn cờ `is_new = true` (hiển thị badge "NEW" trên UI).
4. Khoá nào nằm trong lượt trước nhưng **biến mất** ở lượt này → ghi vào `scan_diff_log` (hữu ích để biết "cổng X đã bị đóng lại lúc nào", phục vụ điều tra sau này).

---

## 6. Database schema

Dùng SQLite qua SQLAlchemy 2.0 (đủ cho 1 người dùng, không cần server DB riêng). Schema chia 2 nhóm: bảng **chung** (mọi module dùng) và bảng **riêng module** (namespace theo `module_id`).

### 6.1 Bảng chung (`core` tables)

```sql
-- Mỗi lượt quét, thuộc về 1 module
CREATE TABLE scans (
    id            TEXT PRIMARY KEY,   -- uuid
    module_id     TEXT NOT NULL,
    status        TEXT NOT NULL,      -- running | done | error
    started_at    DATETIME NOT NULL,
    finished_at   DATETIME,
    summary_json  TEXT,               -- JSON: {total_open, danger, warning, safe,...}
    error_message TEXT
);

-- Từng kết quả trong 1 lượt quét
CREATE TABLE scan_items (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    scan_id       TEXT NOT NULL REFERENCES scans(id),
    module_id     TEXT NOT NULL,
    whitelist_key TEXT NOT NULL,      -- khoá định danh, module tự sinh
    severity      TEXT NOT NULL,      -- safe | warning | danger
    title         TEXT NOT NULL,
    detail_json   TEXT NOT NULL,      -- payload riêng của module
    is_new        BOOLEAN DEFAULT 0
);

-- Whitelist, dùng chung cho mọi module (namespace theo module_id)
CREATE TABLE whitelist_entries (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    module_id     TEXT NOT NULL,
    whitelist_key TEXT NOT NULL,
    label         TEXT,               -- ghi chú người dùng tự đặt
    created_at    DATETIME NOT NULL,
    UNIQUE(module_id, whitelist_key)
);

-- Log những mục biến mất giữa 2 lần quét (điều tra lịch sử)
CREATE TABLE scan_diff_log (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    module_id     TEXT NOT NULL,
    whitelist_key TEXT NOT NULL,
    change_type   TEXT NOT NULL,      -- appeared | disappeared
    scan_id       TEXT NOT NULL REFERENCES scans(id),
    created_at    DATETIME NOT NULL
);
```

**Vì sao `detail_json` là JSON tự do thay vì cột cứng:** mỗi module có payload khác nhau hoàn toàn (port scanner cần `port/pid/process_name`, firewall check cần `rule_name/direction/action`). Nếu cố định schema cột, mỗi module mới sẽ cần migration đổi bảng chung → vi phạm nguyên tắc "module không đụng core". Đánh đổi là mất khả năng query SQL trực tiếp trên field riêng — chấp nhận được vì khối lượng dữ liệu nhỏ (dùng cá nhân), lọc/so sánh xử lý ở tầng Python.

### 6.2 Model riêng module (ví dụ port_scanner)

Nếu module cần bảng riêng ngoài `detail_json` (ví dụ bảng cấu hình riêng), đặt trong `modules/port_scanner/models.py`, migration riêng qua Alembic, **có prefix tên bảng theo module** (`port_scanner_config`) để tránh đụng namespace.

---

## 7. Cấu hình (`config.yaml`)

```yaml
app:
  host: 127.0.0.1        # chỉ bind localhost — không expose ra mạng ngoài mặc định
  port: 8000
  log_level: info

database:
  url: sqlite:///./data/security_audit.db

modules:
  port-scanner:
    enabled: true
    schedule: null        # ví dụ "0 */6 * * *" nếu muốn tự quét mỗi 6h
    known_risky_ports: [4444, 1337, 31337]
  firewall-check:
    enabled: false          # module chưa triển khai, nằm sẵn để bật lên khi code xong
```

Mỗi module đọc đúng section `modules.<module_id>` của mình qua `pydantic-settings`, không đọc config của module khác.

---

## 8. Xử lý lỗi & permission

- Đọc toàn bộ `psutil.net_connections()` với thông tin process đầy đủ trên Windows **cần quyền Administrator** — nếu thiếu quyền, `psutil` trả `AccessDenied` cho một số tiến trình. Backend xử lý: vẫn trả kết quả các port đọc được, đồng thời gắn cờ `partial_result: true` + thông báo rõ trong response để UI hiện banner cảnh báo (đúng theo `EmptyState`/error banner đã mô tả trong `DESIGN.md`).
- Port Scanner chỉ dùng psutil. `scan_mode: nmap` từ cấu hình cũ được chuyển sang `socket` với cảnh báo log; giữ cột database cũ để tránh migration.
- Mọi exception trong `module.run()` được bọc bởi executor chung ở `core/` (không phải từng module tự try/except riêng lẻ), đảm bảo 1 module lỗi không làm sập cả app, và luôn trả về đúng envelope lỗi chuẩn ở mục 4.

---

## 9. Bảo mật cho chính backend

- Mặc định chỉ bind `127.0.0.1` — không truy cập được từ máy khác trong mạng LAN trừ khi người dùng chủ động đổi `host` trong config.
- Vì UI có thể hiển thị đường dẫn thực thi, PID, thông tin tiến trình nhạy cảm, khuyến nghị thêm 1 token đơn giản (local API key sinh ngẫu nhiên lúc cài đặt, lưu trong `config.yaml`, FE gửi qua header `X-Local-Token`) — tránh trường hợp có trang web độc hại nào đó gọi `fetch('http://127.0.0.1:8000/...')` từ trình duyệt (CSRF kiểu localhost).
- CORS: chỉ cho phép origin của chính frontend (`http://127.0.0.1:5173` lúc dev, hoặc origin của bundle production).

---

## 10. Testing

- `pytest` + `httpx.AsyncClient` để test REST endpoint qua `TestClient` của FastAPI.
- Mock `psutil.net_connections()` để test logic diffing/whitelist mà không phụ thuộc trạng thái máy thật lúc CI chạy.
- Mỗi module bắt buộc có `tests/test_scanner.py` riêng trong thư mục module — pattern test cũng "đi theo module" như code, tránh 1 file test khổng lồ dùng chung.

---

## 11. Checklist thêm module backend mới

1. Tạo `modules/ten_module/` gồm `manifest.py`, `scanner.py` (implement `ScannerBase`), `models.py` (nếu cần bảng riêng), `tests/`.
2. Implement `run()` trả về `ScanResult` đúng schema chung.
3. Implement `get_whitelist_key()` theo logic riêng của dữ liệu module đó.
4. Thêm section `modules.<id>` vào `config.yaml`.
5. Không cần sửa `main.py`, `module_registry.py`, hay bảng `scans`/`scan_items` — registry và storage tự nhận diện module mới qua `module_id`.

---

## 12. Ghi chú phạm vi

Tài liệu này đã thiết kế đầy đủ tầng lõi (core) và chi tiết hoá module **Port Scanner**. Các module tương lai (Firewall Check, Startup Programs, Outbound Connections) chỉ cần tuân theo `ScannerBase` + convention ở mục 11, chưa cần thiết kế logic `run()` chi tiết cho từng module đó ở giai đoạn này.
