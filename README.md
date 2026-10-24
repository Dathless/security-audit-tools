<div align="center">

# Security Audit Tool

  <img src="https://img.shields.io/badge/Python-3.11-3776AB?logo=python&logoColor=white" alt="Python">
  <img src="https://img.shields.io/badge/FastAPI-009688?logo=fastapi&logoColor=white" alt="FastAPI">
  <img src="https://img.shields.io/badge/React-19-61DAFB?logo=react&logoColor=black" alt="React">
  <img src="https://img.shields.io/badge/TypeScript-3178C6?logo=typescript&logoColor=white" alt="TypeScript">
  <img src="https://img.shields.io/badge/Vite-646CFF?logo=vite&logoColor=white" alt="Vite">
  <img src="https://img.shields.io/badge/Tailwind_CSS-v4-06B6D4?logo=tailwindcss&logoColor=white" alt="Tailwind CSS">
  <img src="https://img.shields.io/badge/WebSocket-010101?logo=websocket&logoColor=white" alt="WebSocket">
  <img src="https://img.shields.io/badge/SQLite-003B57?logo=sqlite&logoColor=white" alt="SQLite">
</div>

> Công cụ kiểm tra bảo mật cho laptop Windows cá nhân — quét cổng đang mở, đối chiếu whitelist và phát hiện bất thường mới xuất hiện giữa các lần quét theo thời gian thực.

**Security Audit Tool** là ứng dụng **local-first** chạy trên chính chiếc máy cần kiểm tra. Nó quét các cổng đang `LISTEN`, gắn mức độ rủi ro, cho phép đánh dấu "an toàn" (whitelist) và — quan trọng nhất — **so sánh với các lượt quét trước** để cảnh báo những gì *mới xuất hiện* hoặc *biến mất* trên máy của bạn.

Kiến trúc **module hoá hai chiều** (backend + frontend) cho phép thêm một module kiểm tra mới (Firewall Check, Startup Programs, Outbound Connections…) chỉ bằng cách thêm một thư mục, không đụng vào bất kỳ file lõi nào.

---

## Mục lục

- [Security Audit Tool](#security-audit-tool)
  - [Mục lục](#mục-lục)
  - [Tính năng](#tính-năng)
    - [Module Port Scanner (đang hoạt động)](#module-port-scanner-đang-hoạt-động)
    - [Ứng dụng tổng thể](#ứng-dụng-tổng-thể)
  - [Kiến trúc tổng quan](#kiến-trúc-tổng-quan)
    - [Luồng một lượt quét](#luồng-một-lượt-quét)
  - [Công nghệ sử dụng](#công-nghệ-sử-dụng)
  - [Cấu trúc dự án](#cấu-trúc-dự-án)
  - [Yêu cầu môi trường](#yêu-cầu-môi-trường)
  - [Cài đặt \& chạy](#cài-đặt--chạy)
    - [1. Backend](#1-backend)
    - [2. Frontend](#2-frontend)
    - [3. Mở trình duyệt](#3-mở-trình-duyệt)
    - [Build production frontend](#build-production-frontend)
  - [Cấu hình](#cấu-hình)
  - [API Reference](#api-reference)
    - [Hệ thống](#hệ-thống)
    - [Port Scanner](#port-scanner)
  - [WebSocket Protocol](#websocket-protocol)
    - [`WS /ws/scan/{scan_id}`](#ws-wsscanscan_id)
    - [`WS /ws/events`](#ws-wsevents)
  - [Hệ thống module — cách thêm module mới](#hệ-thống-module--cách-thêm-module-mới)
    - [Backend](#backend)
    - [Frontend](#frontend)
  - [Cơ sở dữ liệu](#cơ-sở-dữ-liệu)
    - [Bảng chung (mọi module dùng)](#bảng-chung-mọi-module-dùng)
    - [Bảng riêng module (ví dụ)](#bảng-riêng-module-ví-dụ)
  - [Bảo mật](#bảo-mật)
  - [Kiểm thử](#kiểm-thử)
    - [Backend (`pytest`)](#backend-pytest)
    - [Frontend (`ESLint` + `tsc`)](#frontend-eslint--tsc)
  - [Lộ trình](#lộ-trình)
  - [Tài liệu tham khảo](#tài-liệu-tham-khảo)
  - [Giấy phép](#giấy-phép)

---

## Tính năng

### Module Port Scanner (đang hoạt động)

- **Quét cổng đang lắng nghe** trên máy bằng `psutil`, không cần cài Nmap.
- **Phân loại rủi ro tự động**:
  - 🔴 `danger` — cổng nằm trong danh sách cổng rủi ro đã biết (mặc định `4444`, `1337`, `31337`, có thể tuỳ chỉnh).
  - 🟡 `warning` — đang lắng nghe trên mọi giao diện (`0.0.0.0` / `::`), hoặc không đọc được tên tiến trình do thiếu quyền.
  - 🟢 `safe` — cổng mở thông thường (loopback / nội bộ).
- **Whitelist**: đánh dấu một cổng/tiến trình là "an toàn" ngay từ bảng dữ liệu; các lần quét sau sẽ tự hạ mức rủi ro về `safe`.
- **Diffing lịch sử**: so sánh với lượt quét liền trước, gắn badge **NEW** cho mục mới xuất hiện và ghi log những mục đã biến mất (`scan_diff_log`).
- **Real-time**: tiến trình quét, từng cổng phát hiện và kết quả cuối đều đẩy qua WebSocket — không phải đợi kết quả sau vài chục giây.

### Ứng dụng tổng thể

- **Dashboard tối (dark theme)** với radar quét cổng trực quan — một chấm tương ứng một cổng, màu theo mức rủi ro.
- **KPI row**: tổng cổng mở / nguy hiểm / cảnh báo / an toàn.
- **Sidebar sinh tự động từ registry** module, kèm badge đỏ đếm số mục cần xem và trạng thái backend (Idle / Đang quét / Offline).
- **Scan History** — lịch sử tổng hợp các lượt quét.
- **Settings** — cấu hình token nội bộ, xem danh sách module backend.
- **Quét tự động theo lịch** (APScheduler) nếu module khai báo `default_schedule` — kết quả broadcast tới mọi client đang mở qua kênh WebSocket toàn cục.

---

## Kiến trúc tổng quan

```
┌──────────────────────────────────────────────────────────────┐
│                        FastAPI App                            │
│  ┌───────────────┐   ┌──────────────┐   ┌──────────────────┐  │
│  │  REST Routes  │   │  WebSocket   │   │   Scheduler      │  │
│  │  /api/v1/...  │   │ /ws/scan/id  │   │  (APScheduler)   │  │
│  └───────┬───────┘   └──────┬───────┘   └────────┬─────────┘  │
│          │                  │                    │            │
│          └──────────┬───────┴─────────┬──────────┘            │
│                     ▼                 ▼                       │
│             ┌───────────────┐   ┌──────────────┐              │
│             │Module Registry│   │  Event Bus   │              │
│             │   (core)      │   │   (core)     │              │
│             └───────┬───────┘   └──────┬───────┘              │
│                     ▼                  ▼                      │
│     ┌──────────────────────────────────────────────┐          │
│     │                 Modules                        │         │
│     │  port_scanner/   firewall_check/  ...          │         │
│     │  (ScannerBase implementation)                  │         │
│     └────────────────────┬─────────────────────────┘          │
│                          ▼                                   │
│                  ┌──────────────┐                             │
│                  │ Storage (DB) │  SQLite / SQLAlchemy        │
│                  └──────────────┘                             │
└──────────────────────────────────────────────────────────────┘
```

**Nguyên tắc cốt lõi (backend):** `core/` không bao giờ import ngược từ `modules/`. Chiều phụ thuộc luôn là `modules → core`. Nhờ đó thêm/bớt module không phá vỡ phần lõi.

**Nguyên tắc cốt lõi (frontend):** mọi module Page chỉ "lấp slot" vào layout dùng chung (`ModulePageLayout`) và bắt buộc dùng token/component trong `design-system/`. Không có file trung tâm liệt kê cứng tên module.

### Luồng một lượt quét

```
Người dùng bấm "Quét ngay"
      │
      ▼
POST /api/v1/modules/port-scanner/scan   →   trả về scan_id ngay lập tức
      │
      ▼
Frontend mở WebSocket  /ws/scan/{scan_id}  ←───  server đẩy:
      │                                        • progress (340/1024 cổng)
      │                                        • item_found (từng cổng)
      │                                        • done (summary + so sánh lượt trước)
      ▼
Kết quả được lưu DB → so sánh diffing → UI cập nhật KPI + bảng + radar
```

---

## Công nghệ sử dụng

| Tầng | Công nghệ |
|---|---|
| Backend | Python 3.11 · FastAPI · Uvicorn · SQLAlchemy 2.0 · SQLite |
| Real-time | WebSocket (Starlette) + Event Bus nội bộ (pub/sub) |
| Lập lịch | APScheduler (AsyncIOScheduler) |
| Quét hệ thống | `psutil` · Windows PowerShell / NetSecurity |
| Cấu hình | YAML + Pydantic Settings |
| Frontend | React 19 · TypeScript · Vite · Tailwind CSS v4 |
| Quản lý gói frontend | pnpm |
| Kiểm thử | pytest · pytest-asyncio · FastAPI TestClient · ESLint |

---

## Cấu trúc dự án

```
Security-Audit-Tools/
├── backend/                      # FastAPI backend
│   ├── main.py                   # Entrypoint — tạo app, registry, scheduler, error handlers
│   ├── config.yaml               # Cấu hình ứng dụng (tự sinh local_token lần chạy đầu)
│   ├── conftest.py               # Fixture test (DB SQLite tạm, token test)
│   ├── pytest.ini
│   ├── api/                      # REST routes, WebSocket, security, envelope
│   │   ├── routes.py             #   GET /modules, GET /health
│   │   ├── web_socket.py         #   WS /ws/scan/{id}, WS /ws/events
│   │   ├── security.py           #   X-Local-Token guard (chống localhost CSRF)
│   │   └── envelope.py           #   { success, data, error } thống nhất
│   ├── core/                     # Lõi — KHÔNG import ngược từ modules
│   │   ├── scanner_base.py       #   ScannerBase + ScanResult + ScanError
│   │   ├── module_registry.py    #   ModuleManifest + discover_modules()
│   │   ├── executor.py           #   Vòng đời scan: chạy → whitelist → diffing → lưu → broadcast
│   │   ├── event_bus.py          #   Pub/sub nội bộ (topic wildcard)
│   │   ├── scheduler.py          #   Bọc APScheduler
│   │   └── config.py             #   Load config.yaml, sinh local_token
│   ├── modules/                  # Các module kiểm tra
│   │   ├── port_scanner/         #   ✅ Đang hoạt động
│   │   │   ├── manifest.py       #     khai báo module
│   │   │   ├── scanner.py        #     implement ScannerBase (psutil)
│   │   │   ├── routes.py         #     REST riêng của module
│   │   │   ├── models.py         #     bảng riêng: port_scanner_config
│   │   │   └── tests/            #     test đi theo module
│   │   ├── firewall_check/       #   Windows Firewall profiles + rules
│   │   └── process_monitor/      #   ⏳ stub (chưa triển khai)
│   ├── storage/                  # SQLAlchemy models + Database singleton
│   │   ├── db.py                 #   Scan, ScanItem, WhitelistEntry, ScanDiffLog
│   │   └── migrations/           #   Alembic (dành cho bảng riêng module)
│   └── tests/                    # test REST API
│
├── frontend/                     # React + Vite + TS
│   ├── package.json              # scripts: dev / build / lint / preview
│   ├── vite.config.ts
│   ├── .env                      # VITE_LOCAL_TOKEN (bản mẫu)
│   └── src/
│       ├── main.tsx              # Bootstrap React
│       ├── core/                 # Registry, router, store
│       │   ├── moduleRegistry.ts #   import.meta.glob quét modules/*/manifest.ts
│       │   ├── router.ts         #   hash router tối giản (không react-router)
│       │   ├── appStore.ts       #   store mini (health, badges)
│       │   ├── scanRegistry.ts   #   đăng ký handler "Quét ngay" theo module
│       │   └── types/            #   moduleManifest.ts, api.ts
│       ├── design-system/        # Bộ linh kiện dùng chung — core team mới được sửa
│       │   ├── tokens/index.css  #   NGUỒN duy nhất của màu/type/radius
│       │   ├── components/       #   Button, DataTable, KpiCard, StatusBadge, ...
│       │   └── layouts/          #   ModulePageLayout (hợp đồng layout)
│       ├── app/                  # AppShell (sidebar + topbar) + các trang General
│       │   └── pages/            #   ComingSoon, ScanHistory, Settings
│       └── modules/              # Các module
│           ├── _template/        #   mẫu để copy khi thêm module mới
│           ├── port-scanner/     #   ✅ PortScannerPage + RadarMap + usePortScanner
│           ├── firewall-check/   #   Windows Firewall dashboard
│           ├── startup-programs/ #   ⏳ coming-soon
│           └── outbound-connections/  # ⏳ coming-soon
│
├── docs/
│   ├── BACKEND.md                # Thiết kế chi tiết backend
│   └── (DESIGN.md nằm trong frontend/)  # Thiết kế UI/UX + design tokens
├── data/                         # SQLite DB sinh lúc chạy (git-ignored)
├── requirements.txt              # Python dependencies (bản khóa phiên bản)
└── README.md
```

---

## Yêu cầu môi trường

- **Hệ điều hành**: Windows (mục tiêu chính) — về lý thuyết chạy được trên macOS/Linux nơi `psutil` hỗ trợ.
- **Python** 3.11+ (phát triển trên 3.11).
- **Node.js** 20+ và **pnpm** (phát triển trên Node 24 / pnpm 10).
- **Windows PowerShell / NetSecurity** có sẵn trên Windows cho Firewall Check. Port Scanner không cần Nmap.

---

## Cài đặt & chạy

### 1. Backend

```bash
# Từ thư mục gốc của dự án
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # Linux/macOS

pip install -r requirements.txt

cd backend
uvicorn main:app --host 127.0.0.1 --port 8000
```

Backend chạy tại `http://127.0.0.1:8000`.

> **Ghi chú về quyền:** để đọc được **toàn bộ** tên tiến trình của các cổng đang mở trên Windows, hãy chạy backend với **quyền Administrator**. Nếu không, kết quả vẫn trả về đầy đủ số cổng nhưng một số tiến trình bị đánh dấu *"cần admin"* và UI hiện banner cảnh báo `partial_result`.

> **Lần chạy đầu tiên:** backend tự sinh `local_token` ngẫu nhiên và ghi vào `backend/config.yaml → app.local_token`. Copy token này vào Settings của frontend (hoặc file `.env`).

### 2. Frontend

```bash
cd frontend
pnpm install
pnpm dev
```

Frontend chạy tại `http://127.0.0.1:5173` (đã nằm trong `allowed_origins` mặc định của backend).

### 3. Mở trình duyệt

Truy cập `http://127.0.0.1:5173` → mở **Settings**, dán `local_token` → lưu → vào module **Port Scanner** và bấm **Quét ngay**.

### Build production frontend

```bash
cd frontend
pnpm build     # tsc -b && vite build → dist/
pnpm preview   # xem thử bản build
```

---

## Cấu hình

### Firewall Check v1

Module `firewall-check` đọc ba profile Domain/Private/Public, xác định profile đang sử dụng và kiểm kê các rule đang bật từ Windows `ActiveStore`. Dữ liệu cổng, địa chỉ, chương trình và dịch vụ được lấy từ filter của từng rule. Chạy backend với quyền Administrator nếu Windows báo thiếu quyền đọc.

- Profile đang dùng bị tắt hoặc mặc định inbound Allow: `danger`; profile chưa dùng có cùng cấu hình: `warning`.
- Rule inbound Allow trên Public/Any, mọi nguồn và mọi cổng TCP/UDP/Any: `warning`. Outbound Allow mặc định không bị coi là bất thường.
- Policy `NotConfigured`: chưa đủ dữ liệu kết luận, hiển thị `warning`. Nhãn không có phát hiện chỉ áp dụng tiêu chí v1.
- Chỉ đọc cấu hình, có hướng dẫn kiểm tra thủ công; chưa kiểm chứng truy cập từ Internet hoặc tính hiệu lực tổng hợp của mọi rule.
- Scan History cho phép chọn Port Scanner hoặc Firewall Check. Các lượt scan lỗi/thiếu dữ liệu không được dùng làm mốc diff cho lượt tiếp theo.

API dùng `X-Local-Token`, envelope và WebSocket như Port Scanner:

Hai kênh WebSocket `/ws/scan/{scan_id}` và `/ws/events` kiểm tra token trước khi accept. Browser gửi subprotocols `sec-audit` và `token.<encodeURIComponent(localToken)>`; server chọn `sec-audit`. Client ngoài browser có thể dùng header `X-Local-Token`. Origin của browser phải thuộc `allowed_origins`. Token không nằm trong URL; client WebSocket cũ cần cập nhật handshake.

| Method | Đường dẫn | Kết quả |
|---|---|---|
| POST | `/api/v1/modules/firewall-check/scan` | `{scan_id}`; chạy nền, chỉ đọc Windows |
| GET | `/api/v1/modules/firewall-check/scans/latest` | Scan gần nhất hoặc `null` |
| GET | `/api/v1/modules/firewall-check/scans/{scan_id}` | Scan của module; không tồn tại/khác module trả 404 |
| GET | `/api/v1/modules/firewall-check/scans` | `{items,page,page_size,total}`; mặc định 1/20, tối đa 100 mục/trang |

Scan giữ cấu trúc `id/status/started_at/finished_at/summary/partial_result/error_message/items`. Summary firewall là `{total_profiles,total_rules,danger,warning,safe}`; Port Scanner vẫn trả `total_open`. Mỗi item có `detail.kind` là `profile` hoặc `rule`, `reasons` và `guidance`. Rule giữ định danh ổn định, profile, chiều/hành động, giao thức, cổng và địa chỉ hai đầu, chương trình, dịch vụ và nguồn policy. V1 đánh dấu xuất hiện/biến mất theo định danh, chưa lưu diff từng thuộc tính.

Lỗi collector được lưu thành lượt scan `error` và phát sự kiện lỗi: `UNSUPPORTED_PLATFORM`, `SCAN_PERMISSION_DENIED`, `FIREWALL_UNAVAILABLE`, `FIREWALL_TIMEOUT`, `FIREWALL_QUERY_FAILED`, `FIREWALL_INVALID_DATA`. Timeout là 60 giây; dữ liệu không hợp lệ không được biến thành kết quả an toàn. Không có endpoint sửa firewall hoặc whitelist firewall.

Port Scanner dùng `psutil` và không cần Nmap. Cấu hình cũ `scan_mode: nmap` được chuyển sang `socket` kèm cảnh báo log; giữ cột database cũ và dữ liệu lịch sử.

Kết quả mới giữ `ip` và `note` cho client cũ, đồng thời cung cấp `listener` và `reasons`. Giao diện vẫn đọc được snapshot cũ chỉ có `ip/note`, không cần quét lại. Tên executable không đủ để suy ra dịch vụ đang dùng giao thức nào, nên không gắn cảnh báo chỉ vì tên tiến trình khác tên dịch vụ thường gắn với cổng.

Tất cả cấu hình nằm trong `backend/config.yaml`:

```yaml
app:
  host: 127.0.0.1        # chỉ bind localhost — không expose ra mạng ngoài
  port: 8000
  log_level: info
  local_token: <tự sinh> # token nội bộ chống localhost CSRF
  require_local_token: true
  allowed_origins:
    - http://127.0.0.1:5173
    - http://localhost:5173

database:
  url: sqlite:///./data/security_audit.db

modules:
  port-scanner:
    enabled: true
    schedule: null             # ví dụ "0 */6 * * *" để tự quét mỗi 6 giờ
    known_risky_ports: [4444, 1337, 31337]
    max_ports: 1024
  firewall-check:
    enabled: true              # kiểm tra firewall, chỉ đọc
  process-monitor:
    enabled: false
```

Mỗi module đọc đúng section `modules.<module_id>` của mình (phần còn lại nằm trong `extra`), không đọc cấu hình của module khác.

---

## API Reference

Base path: `/api/v1`. Mọi response bọc trong envelope thống nhất:

```json
{ "success": true, "data": { ... }, "error": null }
```

```json
{ "success": false, "data": null, "error": { "code": "INVALID_LOCAL_TOKEN", "message": "..." } }
```

Tất cả endpoint (trừ chưa bật `require_local_token`) yêu cầu header `X-Local-Token`.

### Hệ thống

| Method | Endpoint | Mô tả |
|---|---|---|
| GET | `/api/v1/modules` | Danh sách module đã đăng ký (id, tên, version, `has_scan`, `last_scan`) — nguồn cho sidebar |
| GET | `/api/v1/health` | Trạng thái `idle`/`scanning`, số scan đang chạy, số module, uptime |

### Port Scanner

| Method | Endpoint | Mô tả |
|---|---|---|
| POST | `/api/v1/modules/port-scanner/scan` | Bắt đầu lượt quét mới — trả `scan_id` ngay, kết quả đẩy qua WebSocket |
| GET | `/api/v1/modules/port-scanner/scans` | Lịch sử lượt quét (phân trang: `page`, `page_size`) |
| GET | `/api/v1/modules/port-scanner/scans/{scan_id}` | Chi tiết một lượt quét (toàn bộ port + trạng thái) |
| GET | `/api/v1/modules/port-scanner/scans/latest` | Kết quả lượt quét gần nhất — render dashboard khi tải trang |
| GET | `/api/v1/modules/port-scanner/whitelist` | Danh sách whitelist hiện tại |
| POST | `/api/v1/modules/port-scanner/whitelist` | Thêm mục whitelist (`{ whitelist_key, label? }`) |
| DELETE | `/api/v1/modules/port-scanner/whitelist/{id}` | Gỡ khỏi whitelist |

**Convention:** mọi module tương lai đi theo pattern `/api/v1/modules/{module_id}/...`, route nằm trong `module.router` riêng — không dồn vào một file `routes.py` chung.

---

## WebSocket Protocol

### `WS /ws/scan/{scan_id}`

Server đẩy các message sau (mọi module dùng chung một kênh theo `scan_id`):

```json
{ "type": "progress", "current": 340, "total": 1024, "message": "Đang kiểm tra cổng 8080..." }
```

```json
{ "type": "item_found", "item": { "severity": "danger", "title": "Port 4444", "detail": { "port": 4444, "pid": 1234, "process_name": "x.exe" } } }
```

```json
{ "type": "done", "scan_id": "abc123", "summary": { "total_open": 27, "danger": 3, "warning": 2, "safe": 22 }, "partial_result": false }
```

```json
{ "type": "error", "code": "SCAN_PERMISSION_DENIED", "message": "..." }
```

Nếu client subscribe **muộn** (scan đã xong/lỗi), server gửi lại trạng thái cuối kèm `replay: true`.

### `WS /ws/events`

Kênh toàn cục — mọi client đang mở nhận được sự kiện của **scan tự động** (scheduler) dù không phải người bấm nút quét.

---

## Hệ thống module — cách thêm module mới

Thiết kế cốt lõi của dự án: **thêm module mới không đụng vào file lõi nào** ở cả backend lẫn frontend.

### Backend

1. Tạo `backend/modules/ten-module/` gồm:
   - `manifest.py` — khai báo `ModuleManifest` (id, display_name, version, `scanner_cls`, `router?`, `default_schedule?`).
   - `scanner.py` — implement `ScannerBase`: `async def run(progress_cb) -> ScanResult` + `get_whitelist_key(item)`.
   - `models.py` *(tuỳ chọn)* — bảng riêng, đặt tên có prefix module (vd `ten_module_xxx`).
   - `tests/` — test đi theo module (mô phỏng `psutil`, không phụ thuộc máy thật).
2. Thêm section `modules.<id>` vào `config.yaml`.
3. **Xong.** `core/module_registry.discover_modules()` tự quét thư mục khi app khởi động — không cần sửa `main.py` hay `module_registry.py`.

### Frontend

1. Copy `frontend/src/modules/_template/` → `frontend/src/modules/ten-module/`.
2. Sửa `manifest.ts`: `id`, `name`, `icon`, `route`, `navOrder`, `status`.
3. Viết `Page.tsx` dùng `ModulePageLayout` + các component có sẵn trong `design-system/`.
4. Nếu cần trực quan hoá riêng (như `RadarMap`), đặt trong `modules/ten-module/components/`.
5. **Xong.** `core/moduleRegistry.ts` dùng `import.meta.glob` tự quét — sidebar, router và layout tự có route mới.

> Module `status: "coming-soon"` chỉ cần khai báo manifest, tự hiển thị dạng disabled trong sidebar — có thể lên kế hoạch UI trước khi backend xong.

---

## Cơ sở dữ liệu

SQLite qua SQLAlchemy 2.0 (đủ cho một người dùng, không cần server DB riêng). File DB mặc định tại `data/security_audit.db`.

### Bảng chung (mọi module dùng)

| Bảng | Mô tả |
|---|---|
| `scans` | Mỗi lượt quét — `id` (uuid), `module_id`, `status` (`running`/`done`/`error`), thời gian, `summary_json`, `partial_result` |
| `scan_items` | Từng kết quả trong một lượt — `whitelist_key`, `severity`, `title`, `detail_json` (JSON tự do), `is_new` |
| `whitelist_entries` | Mục "an toàn" đã xác nhận — unique theo `(module_id, whitelist_key)` |
| `scan_diff_log` | Nhật ký mục xuất hiện/biến mất giữa các lượt (`appeared`/`disappeared`) — phục vụ điều tra lịch sử |

### Bảng riêng module (ví dụ)

`port_scanner_config` — snapshot cấu hình module đang dùng (`scan_mode`, `known_risky_ports`) để đối chiếu kết quả lịch sử.

> **Vì sao `detail_json` là JSON tự do?** Mỗi module có payload khác nhau hoàn toàn (port scanner cần `port/pid/process_name`, firewall cần `rule_name/direction/action`...). Nếu cố định cột schema, mỗi module mới cần migration đổi bảng chung — phá vỡ nguyên tắc "module không đụng core". Với dữ liệu cá nhân dung lượng nhỏ, đánh đổi này chấp nhận được.

---

## Bảo mật

Dự án là công cụ bảo mật nên chính backend cũng được bảo vệ:

- **Chỉ bind `127.0.0.1`** mặc định — không thể truy cập từ máy khác trong mạng LAN trừ khi chủ động đổi `host`.
- **Local API token** (`X-Local-Token`) — sinh ngẫu nhiên lúc chạy lần đầu, chống tấn công **CSRF kiểu localhost** (trang web độc hại gọi `fetch('http://127.0.0.1:8000/...')` từ trình duyệt).
- **CORS hạn chế** — chỉ cho phép origin của chính frontend (`http://127.0.0.1:5173` lúc dev).
- **Không lộ secret**: `backend/config.yaml` và `data/` đã có trong `.gitignore`; token lưu trong `.env` frontend cũng bị ignore.

> ⚠️ Không nên tắt `require_local_token` ở môi trường thật. Cờ này chỉ dành cho dev/test.

---

## Kiểm thử

### Backend (`pytest`)

```bash
cd backend
pytest
```

- `conftest.py` cấu hình DB SQLite tạm + token test cố định.
- `tests/test_api.py` — REST endpoints, auth, CRUD whitelist, luồng scan → history.
- `modules/port_scanner/tests/test_scanner.py` — phân loại severity, `partial_result`, **diffing (new/disappeared)**, **whitelist override severity** — tất cả mô phỏng `psutil`, không phụ thuộc trạng thái máy thật.

### Frontend (`ESLint` + `tsc`)

```bash
cd frontend
pnpm lint
pnpm build    # chạy tsc -b trước khi vite build → check type
```

---

## Lộ trình

- [x] **Port Scanner** — kiểm kê TCP/UDP bằng psutil, whitelist, diffing, real-time, radar map, scan history, settings.
- [x] **Firewall Check** — profile đang dùng, trạng thái/policy, rule đang bật, giải thích cảnh báo và lịch sử.
- [ ] **Startup Programs** — liệt kê và đánh giá chương trình tự khởi động cùng Windows.
- [ ] **Outbound Connections** — theo dõi kết nối ra ngoài đang hoạt động.
- [ ] **Process Monitor** — theo dõi tiến trình.
- [ ] Xác thực bằng token hoàn thiện hơn, xuất báo cáo (reports).

Các module chưa triển khai đã có sẵn vị trí trong sidebar (trạng thái `coming-soon`) để luôn thấy được lộ trình mở rộng.

---

## Tài liệu tham khảo

| Tài liệu | Nội dung |
|---|---|
| [`docs/BACKEND.md`](docs/BACKEND.md) | Thiết kế chi tiết backend: module system, API, luồng hoạt động, DB schema, xử lý lỗi |
| [`frontend/DESIGN.md`](frontend/DESIGN.md) | Thiết kế UI/UX: design tokens, layout contract, cơ chế mở rộng, states |

---

## Giấy phép

Một dự án cá nhân — chưa công bố giấy phép cụ thể. Vui lòng liên hệ chủ dự án nếu muốn sử dụng, fork hoặc đóng góp.
