# DESIGN.md — Security Audit Tool

> Hiện tại Firewall Check đã hoạt động và dùng chung layout, design tokens và component bên dưới. Startup Programs và Outbound Connections vẫn là placeholder. Các phần mô tả module chỉ có Port Scanner phản ánh thiết kế ban đầu.

Tài liệu thiết kế giao diện cho công cụ kiểm tra bảo mật laptop Windows cá nhân.
Xem bản mockup trực quan tại `dashboard-mockup.html` (đi kèm cùng tài liệu này).

---

## 1. Nguyên tắc thiết kế

1. **Trạng thái là dữ liệu, không phải trang trí.** Đây là công cụ bảo mật — màu đỏ/vàng/xanh biểu thị mức độ rủi ro thật. Mọi màu trạng thái dùng thống nhất một bảng token duy nhất (`status-danger`, `status-warning`, `status-safe`) xuyên suốt toàn bộ ứng dụng, không để module nào tự chế màu riêng.
2. **Mỗi module là một "trang" độc lập, tuân theo một hợp đồng bố cục chung** (page header → KPI row → panel chính), để người dùng dùng module mới mà không phải học lại cách đọc giao diện.
3. **Không có màn hình nào coi UI chỉ có 1 module.** Sidebar, routing và trạng thái rỗng đều được thiết kế cho N module ngay từ đầu, kể cả khi hiện tại chỉ có Port Scanner.
4. **Dữ liệu kỹ thuật (port, PID, IP, timestamp) luôn dùng font mono** để dễ scan bằng mắt và căn cột chuẩn — đây là chi tiết nhỏ nhưng quan trọng với một dashboard nhiều số liệu.

---

## 2. Design tokens

### 2.1 Màu sắc

| Token | Hex | Vai trò |
|---|---|---|
| `--bg-base` | `#0B0E14` | Nền toàn ứng dụng (near-black, ánh navy) |
| `--bg-surface` | `#121722` | Nền sidebar, card, panel |
| `--bg-elevated` | `#1A2130` | Hover state, phần tử nổi lên |
| `--border` / `--border-soft` | `#242C3D` / `#1C2332` | Viền, đường chia |
| `--text-primary` | `#E7EAF2` | Chữ chính |
| `--text-secondary` | `#8B93A7` | Chữ phụ, mô tả |
| `--text-muted` | `#525B71` | Label, timestamp, chữ mờ |
| `--accent` | `#3DA9FC` | Màu thương hiệu — dùng cho nút chính, link, nav active, focus ring. **Không** dùng để biểu thị trạng thái bảo mật. |
| `--status-danger` | `#FF5A5F` | Cổng/mục bất thường, cần xử lý ngay |
| `--status-warning` | `#FFB020` | Mới phát hiện / cần xem xét |
| `--status-safe` | `#2ECC8F` | Đã xác nhận an toàn / whitelist |
| `--status-info` | `#8B93A7` | Trung tính, thông tin tham khảo |

Nguyên tắc quan trọng: **`--accent` (xanh dương) và `--status-*` là hai hệ màu tách biệt.** Xanh dương = "đây là UI, có thể bấm được". Đỏ/vàng/xanh lá = "đây là đánh giá rủi ro". Trộn hai hệ này sẽ khiến người dùng đọc nhầm mức độ nguy hiểm.

### 2.2 Typography

| Vai trò | Font | Dùng cho |
|---|---|---|
| Display | `Space Grotesk` (500/600/700) | Tên module, tiêu đề trang, tên brand |
| Body / UI | `Inter` (400/500/600) | Toàn bộ text giao diện, nút, label |
| Mono | `JetBrains Mono` (400/500/600) | Port, PID, IP, path, timestamp, mọi dữ liệu kỹ thuật trong bảng |

Type scale gợi ý:
- Page title: 17px / 600 / Space Grotesk
- Panel title: 14px / 600 / Space Grotesk
- Body: 13–14px / 400–500 / Inter
- Data trong bảng: 12.5px / Mono
- Label/caption: 11–11.5px, uppercase, letter-spacing 0.05em, `--text-muted`

### 2.3 Spacing & bo góc

- Đơn vị cơ sở: 2px, dùng bội số 4/6/8/10/14/16/20/28 cho padding/margin.
- `--radius-sm: 6px` — badge, nút, nav item
- `--radius-md: 10px` — KPI card
- `--radius-lg: 16px` — panel lớn

---

## 3. Kiến trúc thông tin & bố cục

```
┌──────────┬───────────────────────────────────────────────┐
│          │  Topbar: breadcrumb + tên module + [Quét ngay] │
│ Sidebar  ├───────────────────────────────────────────────┤
│          │  Page header (mô tả ngắn module)               │
│ - Modules│  ┌────────┬────────┬────────┬────────┐         │
│ - General│  │  KPI   │  KPI   │  KPI   │  KPI   │         │
│          │  └────────┴────────┴────────┴────────┘         │
│          │  ┌───────────────┬─────────────────────┐       │
│          │  │  Panel phụ    │   Panel chính        │       │
│          │  │ (visualization│   (bảng dữ liệu /    │       │
│          │  │  hoặc summary)│    nội dung chi tiết) │      │
│          │  └───────────────┴─────────────────────┘       │
└──────────┴───────────────────────────────────────────────┘
```

**Sidebar** chia 2 nhóm cố định:
- **Modules** — danh sách sinh tự động từ module registry (mục 4). Module chưa cài đặt xong hiển thị ở trạng thái `disabled` kèm nhãn "soon", không ẩn đi — để người dùng luôn thấy được lộ trình mở rộng của chính họ.
- **General** — các mục không thuộc riêng module nào: Scan History (lịch sử tổng hợp mọi module), Settings.

**Topbar** luôn có 3 phần cố định bất kể module nào đang mở: breadcrumb + tên module (trái), hành động toàn cục như "Quét ngay" (phải). Đây là điểm neo giúp giao diện nhất quán khi chuyển module.

**Content area** theo đúng 1 khuôn cho mọi module: Page header → KPI row (tối đa 4 chỉ số) → Panels (1 panel phụ trực quan hoá + 1 panel chính chi tiết). Module không bắt buộc dùng đủ mọi phần, nhưng **không được tự bịa layout khác** — xem hợp đồng ở mục 5.

---

## 4. Cơ chế mở rộng (phần quan trọng nhất)

Mục tiêu: **thêm module mới = thêm 1 thư mục + 1 file manifest, không sửa bất kỳ file lõi nào** (sidebar, router, layout).

### 4.1 Module manifest (frontend)

Mỗi module khai báo 1 file `manifest.ts` duy nhất:

```ts
// modules/port-scanner/manifest.ts
export const manifest: ModuleManifest = {
  id: "port-scanner",
  name: "Port Scanner",
  icon: "▣",                     // icon token, không phải ảnh cứng
  route: "/modules/port-scanner",
  navGroup: "modules",
  navOrder: 1,
  status: "active",              // "active" | "coming-soon"
  Page: PortScannerPage,         // component chính, tuân thủ layout contract
  badge: () => useOpenPortsCount, // hook trả về số hiển thị trên sidebar (optional)
};
```

### 4.2 Registry tự động

`core/moduleRegistry.ts` dùng `import.meta.glob` (Vite) để tự quét mọi `modules/*/manifest.ts`, không cần liệt kê thủ công:

```ts
const modules = import.meta.glob("../modules/*/manifest.ts", { eager: true });
export const registry = Object.values(modules)
  .map(m => m.manifest)
  .sort((a, b) => a.navOrder - b.navOrder);
```

- **Sidebar** render bằng cách `registry.filter(m => m.navGroup === "modules")` → không còn hardcode danh sách nav.
- **Router** sinh route bằng cách map qua `registry` → route mới tự có khi thêm manifest.
- Module có `status: "coming-soon"` tự động render ở dạng `disabled` trong sidebar mà không cần code riêng.

### 4.3 Hợp đồng layout mà mọi module Page phải theo

Để tránh mỗi module "tự vẽ" một kiểu khác nhau, `Page` component của module **không tự dựng khung trang**, mà nhận vào một layout component dùng chung:

```tsx
<ModulePageLayout
  title="Port Scanner"
  description="Quét toàn bộ cổng đang LISTEN..."
  actions={<Button>Quét ngay</Button>}
  kpis={[{label:"Tổng cổng mở", value:27}, ...]}
>
  <PanelGrid>
    <Panel title="Radar cổng"><RadarMap data={...}/></Panel>
    <Panel title="Chi tiết cổng"><PortTable rows={...}/></Panel>
  </PanelGrid>
</ModulePageLayout>
```

`ModulePageLayout`, `Panel`, `PanelGrid`, `KpiCard`, `StatusBadge`, `DataTable` sống trong `design-system/components/` — đây là **bộ linh kiện dùng chung, chỉ core team (bạn) sửa**, module chỉ được *dùng* chứ không *sửa*. Nhờ vậy module mới không thể phá vỡ giao diện chung, và giao diện chung nâng cấp thì mọi module tự động hưởng lợi mà không phải sửa từng module.

### 4.4 Vì sao cách này tránh xung đột

- Không có file "trung tâm" nào liệt kê cứng tên module → không có merge conflict khi 2 module được thêm cùng lúc.
- Style của module mới **bắt buộc dùng token trong `design-system/tokens/`**, không được định nghĩa màu/font riêng → không lệch theme.
- Component dùng chung (`Panel`, `KpiCard`,...) đảm bảo mọi module "trông giống nhau" dù người viết là ai hoặc viết lúc nào.
- Module ở trạng thái `coming-soon` không cần code Page thật, chỉ cần khai báo manifest → có thể lên kế hoạch UI trước khi code backend xong.

### 4.5 Quy trình thêm module mới (checklist thực tế)

1. Copy `modules/_template/` → `modules/ten-module-moi/`.
2. Sửa `manifest.ts`: id, name, icon, route.
3. Viết `Page.tsx` dùng `ModulePageLayout` + các component có sẵn trong design-system.
4. Nếu cần trực quan hoá riêng (như radar map), đặt trong `modules/ten-module-moi/components/`, không đưa vào `design-system/` trừ khi module thứ 2 cũng cần dùng lại (lúc đó mới "nâng cấp" nó lên thành component dùng chung).
5. Xong — không đụng `AppShell.tsx`, `router.ts`, hay `moduleRegistry.ts`.

---

## 5. Thư viện component (trong `design-system/components/`)

| Component | Mô tả | Props chính |
|---|---|---|
| `AppShell` | Khung sidebar + topbar cố định, bọc toàn app | — (core, không đụng) |
| `ModulePageLayout` | Khung 1 trang module: header, KPI row, slot nội dung | `title, description, actions, kpis, children` |
| `Panel` | Khối nội dung bo góc lớn, có title + subtitle | `title, subtitle, children` |
| `PanelGrid` | Grid 2 cột (380px / 1fr) cho panel phụ + panel chính, tự chuyển 1 cột ở màn hẹp | `children` |
| `KpiCard` | Thẻ chỉ số: label + số lớn (mono) + ghi chú, có biến thể màu theo `status` | `label, value, sub, tone` |
| `StatusBadge` | Nhãn tròn nhỏ: chấm màu + text, dùng `status-*` token | `tone: danger\|warning\|safe`, `label` |
| `DataTable` | Bảng dữ liệu, cột mono cho số liệu kỹ thuật, hover row | `columns, rows` |
| `NavItem` | Mục trong sidebar, hỗ trợ trạng thái active/disabled + badge số | `icon, label, active, disabled, badge` |
| `EmptyState` | Khi module chưa có dữ liệu quét (xem mục 7) | `title, description, action` |

---

## 6. Điểm nhấn thiết kế (signature element)

**Radar cổng** trong panel phụ của Port Scanner: các vòng tròn đồng tâm biểu thị dải cổng (well-known 0–1023 ở tâm → dynamic 49152–65535 ở rìa), mỗi cổng đang mở là 1 chấm đặt theo góc tương ứng với số hiệu cổng, màu theo trạng thái, chấm cảnh báo/nguy hiểm có hiệu ứng nhấp nháy nhẹ để thu hút mắt về nơi cần chú ý trước. Đây vừa là điểm nhận diện trực quan riêng của công cụ, vừa mã hoá đúng thông tin thật (không phải trang trí thuần tuý) — ẩn dụ "radar quét" phù hợp với đúng bản chất của port scanning. Các module tương lai (firewall, outbound connections) có thể có visualization riêng của mình trong đúng vị trí "panel phụ" này mà không phá layout chung.

---

## 7. Trạng thái giao diện (states)

Mọi module cần xử lý tối thiểu các trạng thái sau bằng component dùng chung, không tự chế:

- **Loading (đang quét):** KPI row hiện skeleton mono-space, panel chính hiện progress dạng "đã quét 340/1024 cổng" thay vì spinner mơ hồ — vì đây là tool kỹ thuật, con số tiến trình hữu ích hơn hiệu ứng.
- **Empty (chưa quét lần nào):** dùng `EmptyState` — tiêu đề rõ ("Chưa có dữ liệu quét"), 1 câu giải thích, và nút hành động chính ("Quét ngay") — không để trắng trang.
- **Error (quét lỗi, ví dụ thiếu quyền admin):** hiện banner đỏ nhạt (`status-danger-soft`) ngay dưới topbar, nói rõ nguyên nhân + cách khắc phục (vd: "Cần chạy với quyền Administrator để đọc toàn bộ tiến trình"), không chỉ báo "Đã có lỗi xảy ra".
- **Bất thường mới phát hiện:** không chỉ đổi màu badge, mà nav item của module đó ở sidebar cũng hiện `nav-badge` màu đỏ đếm số mục cần xem — để người dùng thấy ngay từ sidebar mà không cần mở từng module.

---

## 8. Responsive & khả năng tiếp cận

- Breakpoint chính ở 960px: dưới ngưỡng này, `PanelGrid` chuyển từ 2 cột sang 1 cột, sidebar có thể thu gọn thành icon-only (giữ nguyên thứ tự nav).
- Toàn bộ màu trạng thái đạt tỷ lệ tương phản ≥ 4.5:1 trên nền `--bg-surface`.
- Mọi phần tử tương tác (nav item, nút, hàng bảng) có `:focus-visible` outline dùng `--accent`, không phụ thuộc màu sắc đơn thuần — trạng thái nguy hiểm luôn có kèm text ("Bất thường"/"An toàn"), không chỉ dựa vào màu, để không loại trừ người dùng mù màu.
- Dữ liệu bảng hỗ trợ sort/filter qua bàn phím (component `DataTable` cần điều này ngay từ v1, vì đây là công cụ để "đọc số liệu nhanh").

---

## 9. Giới hạn phạm vi hiện tại

Bản thiết kế này chỉ hiện thực chi tiết cho module **Port Scanner**. Các module khác (Firewall Check, Startup Programs, Outbound Connections) đã có chỗ đứng trong sidebar và trong registry (trạng thái `coming-soon`) nhưng chưa thiết kế Page chi tiết — sẽ thiết kế riêng khi bắt đầu triển khai từng module, dùng đúng bộ token và component đã định nghĩa ở trên.
