# Kiểm chứng UI Console Redesign

Trạng thái: **hoàn tất triển khai trên nhánh `codex/ui-console-redesign` ngày 2026-10-25**. Review độc lập đã được xử lý và toàn bộ 372 tests đạt sau lượt sửa. Lần chạy trước bị gián đoạn không được tính là đạt. Theo yêu cầu khi tiếp tục, chỉ hoàn tất UI; Startup Programs vẫn chưa triển khai. Người dùng cho phép commit, push và tích hợp qua PR vào main ngày 2026-10-26; các kiểm tra bàn giao được ghi riêng bên dưới.

## Kiểm tra bàn giao ngày 2026-10-26

- Review lại theo thiết kế: không có phát hiện cần sửa. Review theo quy định repo: sửa một lỗi tài liệu, giữ các mục changelog cũ dưới `Changed` và đặt mục `Fixed` mới sau đó.
- Backend riêng: `python -m pytest -q -m "not selenium"` — **271 đạt**, 101 Selenium được tách sang nhóm browser, một warning Starlette/httpx có sẵn, 35.24 giây.
- Selenium hồi quy: `python -m pytest -q --selenium --ignore=tests/test_selenium_themes.py -m selenium --basetemp .pytest_cache/publish-core-clean` — **77 đạt**, 271 backend được tách riêng, 511.21 giây.
- Theme: `python -m pytest tests/test_selenium_themes.py -q --selenium --basetemp .pytest_cache/publish-themes-clean` — **24 đạt**, 118.92 giây. Như vậy đủ **372 tests** qua ba nhóm chạy hoàn chỉnh; không có test trong phạm vi bị bỏ qua.
- Storage không có env token: `python -m pytest tests/test_selenium_themes.py -q --selenium --selenium-no-env-token -k all_storage_denied --basetemp .pytest_cache/publish-no-env-clean` — **1 đạt**, 23 case không thuộc cấu hình bổ sung được deselect, 7.40 giây.
- Frontend `pnpm lint` và `pnpm build`: đạt; bundle gồm 67 modules. Checker bằng chứng đạt; tám tài liệu liên quan không có liên kết local bị hỏng.
- Lượt gộp mới kết thúc sau 185 dấu đạt nhưng thiếu tổng kết; không tính là đạt. Lượt browser tiếp theo gặp setup lỗi và để lại Vite fixture trên cổng 5173; không tính là đạt. Dọn đúng tiến trình fixture sau khi xác minh command line rồi chạy browser riêng với cổng sạch.
- Chỉ chia sẻ mã nguồn, tài liệu được chọn và ảnh từ dữ liệu giả. Kiểm tra staged paths không có config, database, log hoặc mẫu GitHub/private-key secret; đây không phải chứng nhận quét toàn bộ bí mật.

## Phạm vi

Technical Console mặc định, Graphite Studio và Light Precision dùng cùng shell, panel, dữ liệu và hành động; khác palette/grid/motion. Port Scanner và Firewall có bảng gọn và ngăn bằng chứng đầy đủ. History/Settings/coming-soon dùng chung tokens. Không sửa backend, API contract, auth guards hoặc scan hooks; API client chỉ bổ sung fallback khi không đọc được storage. Không thêm dependency.

[Thiết kế](../../plans/ui-console-redesign-design.md), [checklist và execution ledger](../../plans/ui-console-redesign.md), [kiến trúc hiện tại](../../architecture/frontend.md). Prototype là tài liệu thiết kế; ảnh bên dưới là ứng dụng thật với database/browser fixture.

## Bằng chứng đã chạy

| Kiểm tra | Kết quả |
|---|---|
| Theme preference RED → GREEN | 3 thiếu hành vi trước triển khai → 3 đạt; invalid/denied storage fallback Technical |
| Shared shell RED → GREEN | 2 thiếu search/menu → 8 đạt gồm 3 viewport |
| Port evidence và upgrade regression | 18 đạt, 132.23 giây; review raw risk, delayed responses, reconnect/running |
| Firewall/theme/motion | 16 đạt, 142.37 giây; không remount/socket lại khi đổi theme |
| Rendered states/contrast | RED: 8 đạt, 1 contrast fail; sửa border → 18 đạt, 85.01 giây |
| Fixed General / masked token / legacy history | RED đã tái hiện → 3 đạt, 16.82 giây; legacy chờ dữ liệu xong trước assertion |
| Backend `python -m pytest -q` | 271 đạt, 95 Selenium bỏ qua theo mặc định, 28.94 giây; trước test legacy mới |
| Frontend `pnpm lint` / `pnpm build` | Đạt sau toàn bộ sửa mã nguồn; build 67 modules, không thêm dependency |
| Full backend + Selenium `python -m pytest -q --selenium` | **372 đạt** (271 backend + 101 Selenium), 1 warning có sẵn, **559.15 giây**; fixture Windows selector, không có setup error hoặc test bị bỏ qua |
| Full attempt với Windows default loop | 305 đạt, 1 assertion border lỗi, 66 setup errors; backend dừng accept do IOCP WinError 64, 336.34 giây; không tính là đạt |
| Review độc lập | Hoàn tất chỉ đọc; 0 Critical, 2 Important và sorting được nâng từ Minor lên Important; sửa trong một lượt, không có re-review |
| Regression cho review và compatibility | RED: 5 case review và 2 case compatibility fail → GREEN 7 đạt, 37.69 giây |
| Toàn bộ storage bị chặn, không có env token | RED crash khi khởi động → GREEN 1 đạt, 6.42 giây; backend vẫn kiểm tra token |
| Không có env token — fixture cuối | **1 đạt, 6.33 giây**, chạy lại riêng bằng `--selenium-no-env-token -k all_storage_denied` |
| Fixture Windows + kiểm tra border | **5 đạt, 50.66 giây**, gồm mọi luồng Firewall thật |
| Tài liệu và rendered evidence | Local links/diff checks đạt; checker xác nhận 33 ảnh cho 3 theme/viewport/state/page, ảnh từ fixture giả và token đã che |

Log thô ở `backend/.pytest_cache/ui-*.log`, không đưa vào Git. Một cảnh báo deprecation Starlette/httpx có sẵn không phải lỗi test. Không nâng dependency trong task giao diện.

## Rendered review

Viewport đo bằng Chrome CDP, không suy ra từ kích thước cửa sổ: **390x844, 1024x768, 1440x900**. Ba theme giữ cùng DOM table, nội dung/panel và counts. Màn hẹp inventory đứng trước radar; màn rộng Technical inventory trái, Light inventory phải, Graphite summary strip ở trên. Bảng cuộn ngang cục bộ khi cần; trang và drawer không tràn ngang.

[Technical desktop](ui-console-assets/technical-1440x900.png), [Graphite desktop](ui-console-assets/graphite-1440x900.png), [Light desktop](ui-console-assets/light-1440x900.png), [Technical mobile](ui-console-assets/technical-390x844.png), [Graphite tablet](ui-console-assets/graphite-1024x768.png), [Light tablet](ui-console-assets/light-1024x768.png).

Đã xem lại ảnh sau lượt sửa cuối: [Settings Technical](ui-console-assets/technical-settings-1440x900.png), [History Graphite](ui-console-assets/graphite-history-1440x900.png), [bằng chứng Firewall Light](ui-console-assets/light-firewall-evidence-1440x900.png). Mỗi trang này cũng có captures ở hai theme còn lại; controls, dữ liệu và chức năng giữ nguyên.

Đã quan sát thực tế và sửa Graphite summary quá cao, mobile toolbar dư khoảng trống và control border contrast thấp. Radar idle không animation; progress vẫn có số và thông báo khi reduced motion. Native dialogs có vòng Tab/Shift+Tab, Escape và trả focus; selector trong modal giữ nguyên bằng chứng đang mở. Điều hướng thử bằng 22 manifest giả, General/status luôn có vùng riêng.

Mọi trạng thái được seed/intercept có kiểm soát: [loading](ui-console-assets/technical-loading-390x844.png), [empty](ui-console-assets/graphite-empty-390x844.png), [error](ui-console-assets/light-error-390x844.png), [partial](ui-console-assets/technical-partial-390x844.png), [permission và long path/multi-owner](ui-console-assets/light-permission-390x844.png). Mỗi trạng thái đều có ảnh cho cả ba theme. Đây là dữ liệu giả C:\Demo và người dùng DEMO, không phải kiểm kê host thật.

Contrast từ CSS render thực tế, [số đo](ui-console-assets/contrast.json): text/risk tối thiểu **4.985:1**, control boundary tối thiểu **3.464:1**, focus tối thiểu **7.371:1**. Nút/select/search chính cao ít nhất 44px. [Evidence JSON](ui-console-evidence.json) được checker frontend-design-direction xác nhận tính đầy đủ; checker không thay thế kiểm tra hình ảnh hoặc chứng nhận accessibility.

## Quyết định triển khai và giới hạn

- Review không có mục declined-to-judge. Không hoãn phát hiện Minor: mất sorting được xử lý là lỗi chức năng, khôi phục cột sortable giao thức/action; các lỗi storage/live evidence cũng có RED→GREEN và full regression 372/372 sau lượt sửa.
- Khi Storage bị chặn, không tự tạo kho credential thay thế. API client trả token rỗng khi không đọc được; Settings báo thất bại khi không ghi được. Người dùng cần cho phép storage để lưu token nếu không có env token; xác thực vẫn được giữ nguyên.

- Tái sử dụng checkout sạch trên nhánh riêng, các dependency Windows và fixture hiện có; không thêm worktree hoặc package. Khi bàn giao Git, chọn từng tài liệu và ảnh fixture có chủ đích; không đưa token, database hoặc log thô vào commit.
- Dùng CSS/native dialog và motion tokens thay thư viện motion; đủ cho transition giới hạn, reduced motion và scan progress hiện tại. Chưa cần spring/exit orchestration phức tạp.
- Theme store độc lập scan state; một cây component, CSS đổi vị trí. SearchText và toolbar là hai slot nhỏ bổ sung vào DataTable hiện có để vừa gọn vừa tìm được full evidence. Không dùng page fork hoặc invisible columns.
- Thu gọn Graphite summary/mobile toolbar sau xem ảnh thật; bỏ font request ngoài vì dùng system fonts. Typography có thể khác nhẹ giữa OS.
- Dùng plan/checklist/ledger và pytest logs trực tiếp thay các shell wrapper của skill trên Windows. Review bao gồm diff working tree/file mới vì chưa commit.
- Giữ lịch sử lấy 50 records/trang đầu như trước; không thêm pagination UI/virtualization hoặc API mới. Nếu inventory lớn gây chậm trên máy thật, cần đo riêng trước khi nâng cấp.
- Hiện kiểm chứng Chrome/Windows; chưa chạy Firefox/Safari hoặc assistive screen reader thực tế. Contrast được kiểm tra theo cặp token chính, không phải audit WCAG toàn diện của mọi pixel.
- Full run ban đầu làm Windows Proactor ngừng accept sau nhiều lần Chrome đóng socket (`WinError 64`), kéo theo 66 setup errors. Fixture Windows chuyển riêng sang Uvicorn `asyncio:SelectorEventLoop`; Firewall dùng subprocess đồng bộ trong worker thread nên không cần Proactor. Không đổi runtime production: kết quả browser sau điều chỉnh không chứng minh độ bền của default Windows event loop dưới connection churn. Cần xử lý runtime đó riêng nếu gặp ở môi trường sử dụng.
- Trạng thái tích hợp remote phải đối chiếu PR và SHA trên GitHub; không suy ra từ kết quả kiểm thử local.
