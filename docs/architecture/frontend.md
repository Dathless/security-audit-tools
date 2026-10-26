# Kiến trúc frontend — Security Audit Tool

UI Console dùng React 19, TypeScript và Vite. Thiết kế ba theme được duyệt ngày 2026-10-24; tiến độ và bằng chứng nằm trong [checklist](../plans/ui-console-redesign.md) và [báo cáo kiểm chứng](../testing/reports/ui-console-redesign.md). Xem thêm [backend](backend.md) và [mục lục](../README.md).

## Cấu trúc và luồng dữ liệu

- `src/app/AppShell.tsx`: sidebar, tìm module, menu modal trên màn nhỏ, breadcrumb, theme và hành động quét của module hiện tại. Health polling 5 giây và WebSocket toàn cục đồng bộ trạng thái.
- `src/core/moduleRegistry.ts`: phát hiện `modules/*/manifest.ts` bằng `import.meta.glob`, sắp theo `navOrder`; không liệt kê module trong shell.
- `src/core/router.ts`: hash route; `scanRegistry.ts` đăng ký hành động quét khi trang module mount.
- `src/core/theme.ts`: catalog ba theme, xác thực preference và subscription độc lập với scan store.
- `src/design-system/`: tokens, layout và linh kiện dùng chung. `src/modules/`: pages, hooks và trình bày bằng chứng chuyên biệt.
- `src/modules/api.ts` và `core/types/api.ts`: API client/types hiện có. Theme không thay đổi contract, token, collector, risk hoặc review.

REST gửi `X-Local-Token`; WebSocket dùng subprotocol `sec-audit` và `token.<encodeURIComponent(token)>`, không đặt token trong URL. Backend vẫn chỉ bind localhost. Port Scanner/Firewall hooks giữ xử lý ngắt kết nối, phục hồi scan running và tải đúng scan hoàn tất.

## Theme và trạng thái

| ID | Tên | Palette | Port Scanner trên màn rộng |
|---|---|---|---|
| `technical` | Technical Console — mặc định | Neutral dark / amber | Inventory trái, summary phải |
| `graphite` | Graphite Studio | Graphite / teal | Summary phía trên inventory |
| `light` | Light Precision | Warm white / deep blue | Summary trái, inventory phải |

Ba theme dùng **cùng cây React, panel, dữ liệu và hành động**. Root `data-theme` đổi tokens và grid areas; không có page/component riêng theo theme. Dưới 1150px Port Scanner xếp inventory trước summary trong mọi theme. Điều hướng chuyển sang native dialog dưới hoặc bằng 960px.

`initializeTheme()` chạy trước `createRoot`. Chỉ ID hợp lệ được lưu trong `localStorage.sec_audit_theme`; preference không hợp lệ hoặc storage bị chặn dùng Technical. Khi storage bị chặn, vẫn đổi theme được trong phiên hiện tại. Shell và Settings dùng cùng `ThemeSelector`; modal bằng chứng có selector riêng để không phải đóng bằng chứng. Đổi theme không gọi API, mở socket hoặc remount module; query, sort, lựa chọn, review và scan đang chạy được giữ nguyên.

Token vẫn ưu tiên env rồi localStorage. Client bắt lỗi đọc storage để Settings và shell không crash khi không có env token; backend vẫn từ chối request thiếu token. Nếu ghi storage thất bại, Settings giữ giá trị đang nhập và báo chưa lưu được, không tạo kho token khác hoặc báo thành công giả.

## Tokens và typography

Tokens nằm tại `design-system/tokens/index.css`: primitives → semantic surfaces/text/action/risk → component aliases. Module phải dùng biến ngữ nghĩa, không thêm palette riêng.

| Token | Technical | Graphite | Light |
|---|---|---|---|
| `--bg-base` | `#10120f` | `#13191d` | `#f3f4f0` |
| `--bg-surface` | `#171a16` | `#1b2328` | `#ffffff` |
| `--text-primary` | `#edf0e8` | `#edf3f5` | `#1e2d37` |
| `--accent` | `#edbf66` | `#81d6c3` | `#245a80` |

Action/selection accent tách khỏi severity đỏ/cam/xanh lá. Mọi risk đi kèm nhãn; xác nhận review dùng trạng thái trung tính và không đổi severity/KPI. Màu `safe` có nghĩa không phát hiện theo tiêu chí hiện tại, không phải chứng nhận an toàn.

Dùng font có sẵn trên máy: Bahnschrift/Segoe UI cho tiêu đề và giao diện; Cascadia/Consolas/ui-monospace cho dữ liệu kỹ thuật. Không tải Google Fonts. Body 14px, bảng 13px, dữ liệu mono và metadata 12px; KPI dùng tabular numbers. Tên theme, nhãn và nội dung thống nhất giữa các palette.

## Layout và linh kiện

`ModulePageLayout` cung cấp header → metric strip → banner/content. `PanelGrid` là lưới hai cột chung, nhận thêm class cho layout module; `Panel` nhận `id` ổn định. Không hardcode số lượng module trong shell; điều hướng tìm kiếm và cuộn được, giữ nhóm General và health status.

| Thành phần | Hợp đồng chính |
|---|---|
| `ThemeSelector` | `compact?`; nhãn và ID select riêng, dùng theme store |
| `Panel` | `title`, `subtitle?`, `actions?`, `children`, `id?` |
| `DataTable<T>` | `columns`, `rows`, `rowKey`, `renderColumn?`, `searchText?`, `maxHeight?` |
| `EvidenceDrawer` | `open`, `title`, `onClose`, `children`, `actions?`; native dialog |
| `ProgressBar` | `current`, `total`, `message?`; giá trị và nhãn ARIA, fill scaleX |
| `Button` / `StatusBadge` | Biến thể hành động/severity với token chung |

DataTable giữ sort/filter nội bộ, search ID riêng cho từng bảng và vùng cuộn có tên/focus bàn phím. `searchText` bổ sung dữ liệu tìm kiếm không cần nhồi mọi thuộc tính vào cột. Filter không có kết quả hiển thị hướng dẫn đổi/xóa lọc. Chỉ bảng kỹ thuật cuộn ngang; trang không tràn viewport.

EvidenceDrawer dùng `showModal()`/`close()`, Escape, vòng Tab/Shift+Tab và trả focus về nút đã mở. Helper `dialogFocus.ts` cũng dùng cho menu mobile. Theme selector trong modal giữ nguyên bằng chứng đang mở. Header có một hành động quét chính; action phục hồi lỗi giữ ở đúng trạng thái.

Bằng chứng Port trong scan đang chạy được gắn nhãn tạm. Khi scan lỗi hoặc mất kết nối, drawer đóng và để lộ lỗi/nút tải lại; không tra lại cùng endpoint key trong snapshot cũ rồi thay owner/risk trong modal. Bảng giữ sorting cổng/giao thức; Firewall giữ sorting chiều và hành động riêng.

## Nội dung module

- **Port Scanner:** một dòng mỗi endpoint; mức rủi ro, cổng/giao thức/bind, owner chính/số lượng, review và thay đổi. Drawer giữ mọi owner, executable/user, thời điểm tạo, trạng thái từng trường, lý do/guidance và trước/sau. Tìm kiếm vẫn thấy full path/user/bind. Panel `port-inventory` và `port-summary` có mặt trong mọi theme. Metadata thiếu không suy luận an toàn; legacy giữ đánh giá cũ; partial ghi rõ không kết luận endpoint biến mất.
- **Firewall Check:** ba profiles, KPI và rules; drawer giữ tên rule, profile, chiều/action, local/remote ports/addresses, program/service/policy source, reasons/guidance. Chỉ đọc cấu hình, không tuyên bố reachability hoặc hiệu lực tổng hợp.
- **Scan History:** filter Port Scanner/Firewall, thời gian/trạng thái/counts và mở module; theme giữ filter đang chọn. Hiện API lấy trang đầu 50 records, chưa có điều khiển phân trang lịch sử.
- **Settings:** Appearance, token local, module backend, review phân trang/hủy và whitelist legacy xem/xóa. Theme không thay đổi token/review hoặc quét.
- **Startup Programs / Outbound Connections:** vẫn coming-soon. [Kế hoạch Startup Programs](../plans/startup-programs.md) chưa phải chức năng đang chạy.

## Motion và accessibility

Dùng CSS, không thêm dependency: duration/easing/distance tokens theo theme, chuyển trang/disclosure nhỏ, hover/press/focus và progress dùng transform. Radar chỉ chạy khi scan; không có idle sweep/blink. Không animate từng dòng khi live inventory về.

`prefers-reduced-motion: reduce` tắt transition/animation, sweep và press transform; nội dung/giá trị progress vẫn có mặt. Kiểm tra contrast từng palette: text ≥4.5:1; control boundary/focus ≥3:1. Control chính ≥44px. Menu/drawer có nhãn, focus rõ và Escape; skip link chuyển focus vào main mà không thay hash route.

## Thêm module và kiểm chứng

1. Thêm `modules/<module-id>/manifest.ts` với `id`, `name`, `route`, `navGroup`, `navOrder`, `status`, `Page` nếu hoạt động.
2. Dùng ModulePageLayout và linh kiện chung; dữ liệu đặc thù ở module. Đăng ký scan handler theo mẫu module đang có.
3. Dùng semantic tokens, stable panel IDs và cùng nội dung ở cả ba theme; chỉ CSS thay vị trí/trang trí.
4. Kiểm tra 390x844, 1024x768, 1440x900, long values, keyboard, reduced motion và mọi trạng thái liên quan. Không thêm API/virtualization khi chưa có nhu cầu đo được.

Chạy `pnpm lint`, `pnpm build` trong frontend; từ backend chạy `python -m pytest` và `python -m pytest --selenium`. `tests/test_selenium_themes.py` dùng fixture database/browser hiện có, kiểm tra parity/state/persistence/motion/contrast và lưu captures bằng dữ liệu giả. Không dùng token hoặc thông tin host thật trong ảnh tài liệu.
