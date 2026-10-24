# Startup Programs v1 Implementation Plan

> **For agentic workers:** dùng `superpowers:executing-plans` khi được yêu cầu triển khai. Theo dõi checklist; viết test thất bại trước, triển khai tối thiểu rồi kiểm chứng.
>
> **Trạng thái:** đã định hình thiết kế ngày 2026-10-24; chưa triển khai. Tài liệu này thay thế đề xuất ban đầu chỉ so sánh identity, bổ sung các lựa chọn đã chốt: nhật ký riêng, thay đổi lệnh Registry và dấu vân tay nội dung tệp.

**Goal:** kiểm kê những mục đăng ký tự chạy khi đăng nhập Windows, lưu nhật ký thêm/xóa/sửa với bằng chứng trước và sau.

**Architecture:** thêm module `startup-programs` theo ScannerBase → executor → SQLite → REST/WebSocket hiện có. Collector PowerShell chỉ đọc; snapshot và nhật ký được lưu trong cùng transaction, UI dùng design-system hiện tại.

**Tech Stack:** Python 3.11+, Windows PowerShell/.NET, Pydantic, FastAPI, SQLAlchemy/SQLite, React/TypeScript; không thêm dependency runtime.

**Spec:** phần [Thiết kế](#thiết-kế) trong tài liệu này. Xem thêm [backend](../architecture/backend.md) và [frontend](../architecture/frontend.md).

## Global Constraints

- Windows 10/11 x64, tài khoản đang chạy backend, một backend process trên một SQLite database.
- Chỉ đọc; không thực thi command, sửa Registry, disable startup, tự nâng quyền hoặc gửi dữ liệu ra dịch vụ ngoài.
- Không thêm Scheduled Tasks, Services, WMI persistence hoặc kiểm tra StartupApproved trong v1.
- Giữ API và lịch sử của Port Scanner/Firewall Check; core không import trực tiếp module cụ thể.
- Lịch Startup mặc định tắt. Không đưa command lấy từ máy thật, token hoặc database vào fixture/tài liệu chia sẻ.

## Thiết kế

### Collector và phân loại

- Đọc tám nguồn: HKCU Run/RunOnce dùng view chung; HKLM Run/RunOnce ở cả view 32/64 bit; Startup của người dùng và Common Startup.
- Dùng PowerShell có sẵn: RegistryKey với quyền đọc, không mở rộng biến môi trường; GetFolderPath với DoNotVerify để xác định Startup/CommonStartup mà không tạo thư mục; SHA-256 cho từng tệp trực tiếp trong hai thư mục.
- Giữ `.lnk` như tệp thường: không resolve target, không thực thi hoặc quét đệ quy. Timeout collector 60 giây và dừng process khi hết hạn.
- Mỗi nguồn phải có trạng thái rõ ràng, kể cả nguồn rỗng. Key/thư mục không tồn tại là rỗng hợp lệ; thiếu quyền, lỗi đọc/băm, reparse point ở nguồn hoặc tệp, nguồn bị bỏ sót hoặc phát hiện tệp thay đổi trong lúc đọc làm cả lượt quét `error`. Không tạo snapshot mốc từ dữ liệu thiếu.
- Collector kiểm tra metadata trước/sau khi băm để phát hiện thay đổi quan sát được; đây là quá trình quan sát trong một khoảng thời gian, không phải snapshot nguyên tử của Windows.
- `detail` gồm kind, name, scope, source, registry_view, command/path, value_type, sha256 cho tệp, effective_status, reasons và guidance. Command giữ nguyên chuỗi gốc; chỉ REG_SZ/REG_EXPAND_SZ được đưa vào command. Kiểu khác có command null và cảnh báo.
- Identity Registry là JSON tuple `[registry,hive,view,key,value_name]`; identity tệp là `[folder,source,filename]`. Giữ nguyên tên, không casefold hoặc dùng command/hash/timestamp làm identity.
- Cảnh báo cho command rỗng/kiểu không hỗ trợ và các tệp `.bat`, `.cmd`, `.ps1`, `.vbs`, `.js`, `.wsf` cần xem xét. Không suy luận malware; v1 không tự sinh danger. Các mục còn lại mang nhãn “Không phát hiện theo tiêu chí v1”.
- Thay đổi là thông tin, không tự nâng severity. `effective_status: unknown`: có đăng ký không chứng minh mục đang bật, đã chạy hoặc đang chạy.

### Snapshot, context và nhật ký

- Tái sử dụng Scan/ScanItem; thêm bảng nhật ký module với context_id (SID), scan_id, baseline_scan_id, entry_key, event_type, before_json, after_json và created_at. Khởi tạo bảng mới qua metadata.create_all hiện có; không sửa schema bảng cũ hoặc thêm framework migration.
- Nhật ký có bốn loại `initial`, `added`, `modified`, `removed`. Lần thành công đầu tiên ghi initial; không trình bày thành cảnh báo thêm mới.
- So sánh cùng identity: Registry theo command/value_type; tệp theo path/SHA-256. Chỉ đổi thời gian tệp không tạo modified. Đổi tên được thể hiện là xóa và thêm.
- Chỉ dùng snapshot done, đầy đủ, cùng SID làm mốc. Chốt baseline_scan_id khi tiếp nhận scan, trước khi thu thập; không chọn lại mốc khi lưu. Lưu SID và mốc trong metadata của Scan cho cả running/error và snapshot rỗng.
- Bổ sung điểm mở rộng tối thiểu trong pipeline chung để chuẩn bị context và lưu journal trong cùng transaction với snapshot/summary; mặc định không tác động module cũ. Lỗi ở bất kỳ bước lưu nào phải rollback, không để lại items hoặc sự kiện dở dang.
- Chỉ một Startup scan hoạt động tại một thời điểm: REST trùng trả 409; scheduler bỏ qua lượt trùng. Khi khởi động backend, đánh dấu lượt Startup running bị bỏ dở là error trước khi chạy scheduler.
- Journal lưu bản sao dữ liệu trước/sau để xem bằng chứng mà không phải tính lại diff từ các snapshot khi đọc. Không lưu nội dung tệp; chỉ lưu hash và metadata cần thiết.
- Summary giữ danger/warning/safe và thêm total_entries, total_sources, context_id, baseline_scan_id cùng initial_count, added_count, modified_count, removed_count.

### API và giao diện

Các endpoint dự kiến dưới `/api/v1/modules/startup-programs` (chưa tồn tại trong ứng dụng):

| Method | Path | Hành vi |
|---|---|---|
| POST | `/scan` | Tiếp nhận scan, trả scan_id; 409 nếu đang có Startup scan |
| GET | `/scans/latest` | Scan gần nhất của context hiện tại hoặc null |
| GET | `/scans/{scan_id}` | Chi tiết; khác module/context hoặc không tồn tại trả 404 |
| GET | `/scans` | Lịch sử cùng context, phân trang |
| GET | `/changes` | Journal cùng context, tùy chọn lọc scan_id, phân trang |

- Giữ envelope, X-Local-Token, auth/Origin guard và hai WebSocket hiện có. Phân trang mặc định page=1/page_size=20, tối đa 100.
- Danh sách module, latest, history và changes dùng cùng context hiện tại; không hiển thị kết quả tài khoản khác như kết quả hiện tại.
- Bật manifest frontend Startup Programs. Trang có KPI, bảng kiểm kê tìm kiếm được, nguồn/phạm vi, command/path và lý do cảnh báo; nhật ký có trước/sau và nhãn “Ban đầu”, “Đã thêm”, “Đã sửa”, “Đã xóa”.
- Thêm module vào Scan History. Dùng layout, bảng, badge, progress và error/retry hiện có; chỉ hiển thị kết quả hoàn tất sau khi transaction thành công.
- Tái sử dụng vòng đời quét Firewall; nếu trích hook dùng chung, giữ xử lý mất WebSocket, callback cũ, rời trang và đồng bộ busy state. Không thay hook whitelist riêng của Port Scanner.
- Render command/tên/đường dẫn như text không tin cậy; không tạo HTML thô, shell action hoặc liên kết thực thi. Không có whitelist hay endpoint thay đổi cấu hình startup.

## Review Focus

1. Một nguồn lỗi hoặc băm thất bại không được tạo sự kiện xóa giả.
2. Scan rỗng, đổi SID, quét trùng và restart không được chọn sai mốc hoặc trộn lịch sử.
3. Unicode, dấu nháy và ký tự shell phải được bảo toàn như dữ liệu, không thực thi.
4. Metadata thay đổi khi băm và reparse point phải được phát hiện; shortcut không bị hiểu thành executable target.
5. Rollback hoặc mất WebSocket không được để UI coi dữ liệu tạm là kết quả hoàn tất.

## Checklist triển khai

- [ ] Viết test thất bại rồi triển khai collector đủ tám nguồn: rỗng, lỗi quyền, kiểu Registry, Unicode, timeout, reparse point và thay đổi tệp khi đọc.
- [ ] Kiểm chứng diff cho đổi command/value_type, đổi nội dung tệp, chỉ đổi thời gian, đổi tên, thêm/xóa và initial.
- [ ] Triển khai context, baseline, admission guard và lưu transaction; kiểm thử scan lỗi/rỗng, đổi SID, REST 409, scheduler bỏ qua và restart.
- [ ] Thêm model journal và cập nhật fixture dọn database; kiểm thử rollback toàn bộ và bằng chứng trước/sau không phụ thuộc việc tính lại diff.
- [ ] Đăng ký manifest/backend router; thêm API tests cho auth, envelope, phân trang, 404, cách ly context và WebSocket done/error/replay. Cập nhật README/OpenAPI theo chức năng thực sự được triển khai.
- [ ] Làm UI kiểm kê, nhật ký và Scan History; kiểm thử tìm kiếm, trước/sau, nhãn initial, retry, mất WebSocket và rời trang.
- [ ] Từ backend chạy `python -m pytest`; chạy đầy đủ `python -m pytest --selenium` trong môi trường có trình duyệt. Từ frontend chạy `pnpm lint` và `pnpm build`. Port Scanner và Firewall Check tiếp tục đạt.
- [ ] Đối chiếu một lượt chỉ đọc trên Windows thật; không tạo/xóa mục Startup để thử nghiệm. Review diff, dữ liệu nhạy cảm và ghi lại kết quả cùng giới hạn chưa kiểm chứng.
- [ ] Khi hoàn tất, cập nhật tài liệu hệ thống và chuyển kế hoạch vào completed. Chỉ commit/push khi được yêu cầu.

## Tiêu chí chấp nhận và giới hạn

Người dùng kiểm kê được tám nguồn đã chốt, thấy nhật ký ban đầu/thêm/sửa/xóa với dữ liệu trước/sau và lịch sử nhất quán theo context. Nguồn lỗi không sinh kết quả an toàn hoặc diff giả; các module hiện có không hồi quy.

Hash `.lnk` chỉ phát hiện thay đổi chính shortcut, không phát hiện nội dung chương trình đích thay đổi. Không coi việc không có phát hiện là chứng nhận an toàn, và không tuyên bố kiểm kê mọi cơ chế persistence. Các test trong checklist chưa được chạy cho Startup Programs vì module chưa triển khai.

## Nguồn tham khảo

- [Microsoft: Run and RunOnce Registry Keys](https://learn.microsoft.com/en-us/windows/win32/setupapi/run-and-runonce-registry-keys)
- [Microsoft: Registry Keys Affected by WOW64](https://learn.microsoft.com/en-us/windows/win32/winprog64/shared-registry-keys)
- [Microsoft: RegistryKey.GetValue](https://learn.microsoft.com/en-us/dotnet/api/microsoft.win32.registrykey.getvalue)
- [Microsoft: Environment.GetFolderPath](https://learn.microsoft.com/en-us/dotnet/api/system.environment.getfolderpath)
- [Microsoft: Get-FileHash](https://learn.microsoft.com/en-us/powershell/module/microsoft.powershell.utility/get-filehash)
