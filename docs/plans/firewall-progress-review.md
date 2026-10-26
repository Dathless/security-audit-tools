# Firewall Check: review, sửa lỗi và theo dõi tiến trình

Trạng thái: hoàn tất thay đổi và kiểm chứng trên `codex/firewall-progress-review`, ngày 2026-10-26. [Báo cáo kiểm chứng](../testing/reports/firewall-progress-review.md).

## Mục tiêu và thiết kế

Sửa các lỗi vòng đời quét có bằng chứng; giúp người dùng biết đang làm gì, đã chờ bao lâu và kết quả nào thuộc lượt quét đang theo dõi. Chỉ đọc Windows Firewall, giữ nguyên token/Origin guards và dữ liệu lịch sử.

Tái sử dụng `serialize_scans`, executor, WebSocket và design-system ProgressBar. Collector vẫn là một truy vấn PowerShell có timeout 60 giây: giai đoạn này không biết khối lượng công việc, nên hiển thị indeterminate; đánh giá profiles/rules dùng số lượng thực. Chỉ sự kiện `done` sau persistence mới xác nhận thành công. Không dùng timeout làm ETA hoặc tăng phần trăm theo đồng hồ.

ETA dựa vào thời lượng thành công đã biết và luôn có nhãn ước tính. Khi chưa có mẫu hoặc lâu hơn mẫu, hiển thị đúng giới hạn. Nhật ký thu gọn/mở rộng chứa hoạt động quan sát trong phiên, có giới hạn số dòng, giữ kết thúc/lỗi và nói rõ khoảng trống khi kết nối lại. Không thêm dependency, bảng log hoặc lưu đầu ra PowerShell thô.

Các phương án đã cân nhắc: đếm ngược theo timeout không phản ánh tiến độ; viết lại collector để stream từng cmdlet tăng phạm vi. Chọn tiến độ theo các giai đoạn hiện có và elapsed/ETA minh bạch. Đây là quyết định triển khai của điều phối viên trong phạm vi yêu cầu người dùng.

## Phạm vi và contract

- Backend: firewall manifest bật khóa quét và recovery có sẵn; POST `/api/v1/modules/firewall-check/scan` trả 409 envelope `SCAN_ALREADY_RUNNING` nếu đang quét. Scheduler dùng guard có sẵn.
- Progress WebSocket giữ `{type: "progress", current, total, message}`; `total <= 0` nghĩa là chưa biết tổng. Counts được phát khi công việc thực sự được đánh giá, không phát lại sau cùng. Kết quả/lỗi cuối giữ contract hiện tại.
- Frontend: API helper lấy exact scan ID; hook chặn stale responses/callbacks, tải đúng kết quả khi hoàn tất, đối chiếu HTTP khi mất socket và theo dõi scan đã chạy khi gặp 409. Không hiển thị bằng chứng của snapshot cũ như kết quả mới.
- UI: ProgressBar dùng chung thêm trạng thái indeterminate, elapsed/ETA và nhật ký tùy mở. Giữ accessibility, reduced motion, theme tokens.
- Tests/fixtures: scanner, API, restart/duplicate/retry và Selenium với dữ liệu giả cho các race/tiến trình/lỗi. Không sửa firewall máy thật trong tests mới.
- Tài liệu: CONTRIBUTING quy trình ba vai trò, changelog, mục lục và báo cáo kiểm chứng.

## Phân vai và gate

| Owner | Model / effort | Phạm vi | Trạng thái |
|---|---|---|---|
| Planner | GPT-6.1 Sol / high | Chỉ đọc, phân tích nguyên nhân, callers và kế hoạch | Hoàn tất |
| Executor | GPT-6.1 Sol / high | Product code và tests trong phạm vi trên | Hoàn tất |
| Reviewer | GPT-6 Astra / high | Chỉ đọc toàn diff, kiểm tra yêu cầu, logic, bảo mật và tests | Vòng 1 đạt; không cần vòng sửa product |
| Điều phối viên | Model của chat | Tích hợp, tài liệu, kiểm chứng và bàn giao | Hoàn tất kiểm chứng và tài liệu |

Một nhánh, một product writer, cùng task. Tối đa 3 vòng review–fix; dừng sớm nếu đạt. Các finding sau giới hạn phải ghi rõ, không coi hoàn tất khi còn gate thất bại.

## Checklist

- [x] Đọc hướng dẫn, xác định nguyên nhân và phạm vi; baseline 46 firewall tests đạt.
- [x] Regression tests cho lỗi và tiến trình, implementation tối thiểu.
- [x] Backend full suite; frontend lint/build.
- [x] Selenium cho luồng quét và UI; ảnh minh họa dùng dữ liệu giả.
- [x] Reviewer kiểm tra; vòng 1 không có finding product cần sửa, bổ sung kiểm chứng và xác nhận lại.
- [x] Cập nhật changelog/báo cáo, diff check và ghi giới hạn kiểm chứng.

## Trọng tâm review

Mất socket nhưng backend còn chạy; kết quả HTTP cũ đến sau khi bắt đầu scan mới; terminal event khi chuyển trang/đổi scan; thiếu mẫu ETA hoặc mẫu bị vượt; hàng nghìn rule không làm nhật ký/tần suất cập nhật tăng vô hạn. Kiểm tra 409, restart recovery và không hạ cảnh báo bởi thay đổi tiến trình.
