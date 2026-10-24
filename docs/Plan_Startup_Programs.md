# Startup Programs v1 Implementation Plan

> **For agentic workers:** dùng `superpowers:executing-plans` hoặc `superpowers:subagent-driven-development` khi được yêu cầu triển khai. Theo dõi từng bước bằng checkbox; viết test lỗi trước, sửa rồi kiểm chứng test đạt.
>
> Đây là đề xuất chức năng tiếp theo. Tài liệu này bao gồm thiết kế; chưa triển khai Startup Programs.

**Goal:** giúp người dùng thấy những mục được đăng ký tự chạy khi đăng nhập Windows và phát hiện mục mới giữa các snapshot.

**Architecture:** thêm module `startup-programs` theo ScannerBase → executor → SQLite → REST/WebSocket đang có. Đọc Registry và hai thư mục Startup bằng thư viện chuẩn Python/Windows API, hiển thị bằng design-system hiện tại.

**Tech Stack:** Python 3.11+, `winreg`, `ctypes`, `pathlib`/`os`, Pydantic, FastAPI, SQLite, React/TypeScript; không thêm dependency.

**Spec:** phần [Thiết kế](#thiết-kế) trong chính tài liệu này.

## Vì sao chọn chức năng này

| Ý tưởng | Giá trị | Lựa chọn |
|---|---|---|
| Startup Programs | Thấy các mục đăng ký tự chạy và thay đổi về persistence, bổ sung cho kiểm tra mạng hiện có | Ưu tiên tiếp theo; đã có placeholder frontend |
| Active Connections | Thấy tiến trình và các đầu kết nối hiện tại; tái sử dụng psutil | Sau Startup; cần mô tả chính xác vì một snapshot không chứng minh chiều kết nối |
| Đối chiếu cổng với firewall | Giải thích quan hệ giữa listener và rule | Giai đoạn sau; phải xử lý nhiều điều kiện và độ ưu tiên rule trước khi kết luận |

## Thiết kế

### Phạm vi và ý nghĩa dữ liệu

- Bản đầu phục vụ Windows 10/11 x64, trong ngữ cảnh tài khoản đang chạy backend. Nền tảng/kiến trúc chưa hỗ trợ trả lỗi rõ ràng.
- Đọc `Software\Microsoft\Windows\CurrentVersion\Run` và `RunOnce` ở HKCU (view dùng chung) và HKLM (cả view 32/64 bit); dùng flag WOW64, không ghép đường dẫn `Wow6432Node` thủ công.
- Liệt kê file ngay trong `FOLDERID_Startup` và `FOLDERID_CommonStartup`. Xác định đường dẫn bằng `SHGetKnownFolderPath` với `KF_FLAG_DONT_VERIFY`; không tạo thư mục còn thiếu và không quét đệ quy.
- Tổng phạm vi là tám nguồn: hai HKCU, bốn HKLM và hai thư mục. Registry key/thư mục không tồn tại là nguồn rỗng hợp lệ; thiếu quyền hoặc lỗi đọc không phải nguồn rỗng.
- Chỉ đọc. Không thực thi command, mở shortcut, sửa/xóa Registry, disable mục startup hoặc tải thông tin ra dịch vụ ngoài.
- V1 không đọc Scheduled Tasks, Services, WMI persistence hoặc trạng thái `StartupApproved`. Trạng thái hiệu lực là `unknown`: một mục có đăng ký không đồng nghĩa nó đang được bật, đã chạy hoặc đang chạy.
- Giữ `.lnk` dưới dạng file shortcut với đường dẫn nguồn, không tự giải mã hoặc chạy target. Không tách executable hay đoán đường dẫn từ command line trong v1.

### Dữ liệu, định danh và đánh giá

- Một item tương ứng một Registry value hoặc một file trong Startup. `detail` gồm `kind`, `name`, `scope` (`user`/`machine`), `source`, `registry_view`, `command` hoặc `path`, `value_type`, `effective_status: unknown`, `reasons`, `guidance`.
- Chỉ `REG_SZ`/`REG_EXPAND_SZ` được đưa vào trường command. Kiểu khác giữ `value_type`, đặt command null và sinh cảnh báo, không serialize trực tiếp byte buffer. Giữ command gốc chưa mở rộng biến môi trường trong v1.
- Giữ nguyên tên và command gốc; coi chúng là dữ liệu không tin cậy. React render dưới dạng text. Không đưa command vào shell, URL hành động hoặc HTML thô.
- Khóa identity là JSON tuple: Registry `[registry,hive,view,key,value_name]`; folder `[folder,source,filename]`. Không dùng PID, timestamp hay command làm identity. Không gộp hai nguồn HKLM khác view.
- `warning` cho Registry value rỗng/sai kiểu chuỗi; file Startup có đuôi `.bat`, `.cmd`, `.ps1`, `.vbs`, `.js`, `.wsf` cũng cần xem xét thủ công. Lý do giải thích đây là cấu hình bất thường hoặc khả năng chạy script, không kết luận là malware.
- Các mục còn lại dùng `safe` với nhãn “Không phát hiện theo tiêu chí v1”. Mục mới chỉ có badge NEW; không tự tăng severity vì mới xuất hiện. V1 không sinh `danger`.
- Summary: `total_entries`, `total_sources`, `danger`, `warning`, `safe`. Không đổi các summary cũ của Port Scanner/Firewall Check.
- Một nguồn không đọc được làm toàn bộ lượt scan `error`, kèm mã `SCAN_PERMISSION_DENIED` hoặc `STARTUP_READ_FAILED` và tên nguồn. Không lưu một snapshot thiếu làm mốc diff. Bảng lịch sử vẫn giữ các lần thành công trước.
- Key biến mất/thêm mới được executor ghi nhận bằng identity hiện có. Thay command trong cùng value được thể hiện ở snapshot mới; diff từng thuộc tính chưa thuộc v1.

### API và giao diện

- Thêm bốn endpoint dưới `/api/v1/modules/startup-programs`: `POST /scan`, `GET /scans/latest`, `GET /scans/{scan_id}`, `GET /scans`.
- Giữ envelope, token, phân trang 1/20 và tối đa 100, lỗi khác module trả 404. Dùng `api/scan_results.py` và hai WebSocket đã có auth/Origin guard. Không tạo bảng riêng hoặc whitelist endpoint.
- Bật manifest frontend `startup-programs`; tạo backend `modules/startup_programs/`, không dùng nhầm stub `process_monitor`.
- Trang có KPI tổng mục/cảnh báo/mục không có phát hiện; bảng tên, nguồn, phạm vi, command/đường dẫn, đánh giá và NEW. Có tìm kiếm, hướng dẫn, progress, retry và nhãn “Trạng thái hiệu lực: chưa xác định”.
- Thêm lựa chọn Startup Programs vào Scan History, hiển thị số mục và mở đúng module. Mặc định lịch sử vẫn là Port Scanner.
- Dùng vòng đời quét đã kiểm chứng: trích hook Firewall Check thành `core/useModuleScan.ts` để dùng chung cho Firewall và Startup. Interface là `useModuleScan(moduleId, startRequest, latestRequest)`, trả data/loading/scanning/progress/error/startScan. Port Scanner giữ hook whitelist riêng.

## Global Constraints

- Không thêm dependency runtime hoặc migration database; giữ API của hai module đang hoạt động.
- Quyền và lỗi dữ liệu phải được xử lý trước khi phân loại; không trả kết quả an toàn cho nguồn không đọc được.
- Không tự nâng quyền, thay chính sách Windows hay tự động khắc phục startup.
- Không commit fixture lấy nguyên trạng từ máy thật: command có thể chứa dữ liệu riêng tư.

## Review Focus

1. Thiếu quyền một nguồn không được biến thành snapshot trống và sinh diff mất mục giả.
2. Unicode, dấu nháy và ký tự shell trong command chỉ được hiển thị, không được thực thi.
3. HKLM 32/64 bit không được bỏ sót; HKCU dùng chung không được đếm hai lần.
4. `.lnk`, folder bị chuyển vị trí hoặc source không tồn tại không được bị hiểu là target bị mất.
5. Mất WS, rời trang hoặc nhận phản hồi cũ phải không làm khóa nút quét hay trộn dữ liệu lịch sử.

## Checklist triển khai

### Task 1 — Collector và phân loại

**Files:** tạo `backend/modules/startup_programs/scanner.py`, `collector.py`, `tests/test_scanner.py`.

**Interfaces:** collector trả danh sách observation theo schema trên; scanner triển khai `run(progress_cb) -> ScanResult` và `get_whitelist_key(item) -> str`.

- [ ] Viết test lỗi cho đủ tám nguồn, nguồn rỗng, denied/error, Unicode, value sai kiểu, script file và identity ổn định.
- [ ] Chạy `pytest modules/startup_programs/tests/test_scanner.py -q`; xác nhận lỗi do chức năng chưa có.
- [ ] Triển khai `winreg` chỉ sau platform guard, mở key với quyền đọc trong context manager. Dùng Windows Known Folder API qua `ctypes`, khai báo kiểu trả về và giải phóng bộ nhớ bằng `CoTaskMemFree`.
- [ ] Enum từng nguồn một lần; không thực thi command, resolve shortcut hoặc đi vào thư mục con. Giữ `.lnk`/command là dữ liệu thô.
- [ ] Chạy lại test: tất cả đạt, gồm assertion không có lời gọi tạo process hoặc ghi Registry.

### Task 2 — API và lưu lịch sử

**Files:** thêm `manifest.py`, `routes.py`, `tests/test_api.py` trong module; cập nhật cấu hình mẫu README và fixture module.

**Interfaces:** bốn endpoint, summary và detail đã chốt; dùng serializer và executor hiện có.

- [ ] Viết/chạy test lỗi cho auth, latest-null, start/done/error, phân trang, cách ly module, WebSocket/replay và quét lại sau lỗi quyền.
- [ ] Đăng ký manifest, viết router theo Firewall Check; thêm section cấu hình `startup-programs` enabled, lịch mặc định null.
- [ ] Kiểm chứng thêm/mất item và mốc completed/full; snapshot lỗi không tạo log mất mục.
- [ ] Cập nhật README/OpenAPI với ví dụ item Registry và file, lỗi quyền và giới hạn effective_status.
- [ ] Chạy toàn bộ backend; các module cũ tiếp tục đạt.

### Task 3 — UI và hook dùng chung

**Files:** `frontend/src/modules/startup-programs/`, `core/useModuleScan.ts`, API/types và Scan History; Firewall hook trở thành wrapper mỏng.

**Interfaces:** thêm `startStartupScan`, `fetchLatestStartupScan`, `fetchStartupScans` vào client; thêm `total_entries`/`total_sources` dạng optional vào summary chung.

- [ ] Viết Selenium test lỗi cho navigation, scan, nguồn hiển thị, tìm kiếm, NEW, hướng dẫn và chọn lịch sử.
- [ ] Trích hook theo interface ở thiết kế; giữ xử lý WS close/error, stale callback và đồng bộ health.
- [ ] Xây page bằng ModulePageLayout, Panel, DataTable, StatusBadge, ErrorBanner và ProgressBar. Dùng label rõ ràng và điều khiển được bằng bàn phím.
- [ ] Kích hoạt manifest và lựa chọn lịch sử; không tạo dashboard/biểu đồ riêng.
- [ ] Chạy lint/build và các test mất WS/rời trang của cả Firewall lẫn Startup.

### Task 4 — Xác minh và bàn giao

- [ ] Chạy toàn bộ `pytest --selenium`, dùng SQLite tạm và dữ liệu độc lập từng test; không chấp nhận test chỉ pass nhờ dữ liệu test trước.
- [ ] Đo line coverage collector/phân loại và API, mục tiêu tối thiểu 80%, bao phủ toàn bộ nhánh trust-boundary mới bằng test.
- [ ] Đối chiếu một snapshot chỉ đọc trên Windows thật với Registry và hai Startup folder; không tạo/xóa mục startup để làm thử nghiệm.
- [ ] Kiểm tra diff, dữ liệu nhạy cảm, không có thao tác ghi hệ thống và không có regression ở Port Scanner/Firewall Check.
- [ ] Lưu bằng chứng test cùng các giới hạn chưa kiểm chứng. Chỉ commit hoặc push khi được yêu cầu.

## Tiêu chí chấp nhận

Người dùng có thể đọc các nguồn đã chốt, biết mục nào mới xuất hiện hoặc biến mất, xem đầy đủ nguồn gốc và lý do cảnh báo, tải lịch sử theo module và phục hồi sau lỗi/kết nối gián đoạn. Ứng dụng không khẳng định đã kiểm kê mọi cơ chế persistence hay xác nhận mục thực sự đã chạy.

## Nguồn tham khảo

- [Microsoft: Run and RunOnce Registry Keys](https://learn.microsoft.com/en-us/windows/win32/setupapi/run-and-runonce-registry-keys)
- [Microsoft: Registry Keys Affected by WOW64](https://learn.microsoft.com/en-us/windows/win32/winprog64/shared-registry-keys)
- [Microsoft: KNOWNFOLDERID](https://learn.microsoft.com/en-us/windows/win32/shell/knownfolderid)
- [Microsoft: SHGetKnownFolderPath](https://learn.microsoft.com/en-us/windows/win32/api/shlobj_core/nf-shlobj_core-shgetknownfolderpath)
