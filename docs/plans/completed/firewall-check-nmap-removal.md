# Kế hoạch: Bỏ Nmap và triển khai Firewall Check v1

## Mục tiêu

Thực hiện theo thứ tự: loại bỏ phụ thuộc Nmap, sau đó bổ sung Firewall Check cho máy Windows hiện tại.

Port Scanner tiếp tục kiểm kê TCP/UDP, PID và tiến trình bằng `psutil`. Firewall Check chỉ đọc trạng thái và các rule đang bật, giải thích cảnh báo và hướng dẫn kiểm tra thủ công.

## 1. Đơn giản hóa Port Scanner

- Xóa nhánh quét Nmap, hàm tạo danh sách cổng cho Nmap, import liên quan và dependency `python-nmap`. Dùng collector `psutil` hiện có.
- Giữ nguyên API, dữ liệu kết quả, phân loại rủi ro, whitelist, lịch sử, radar và xử lý thiếu quyền.
- Bỏ lựa chọn `scan_mode` khỏi cấu hình mẫu. Cấu hình cũ ghi `nmap` vẫn chạy bằng `psutil`, kèm thông báo chuyển đổi trong log.
- Giữ cột `scan_mode` trong database để tránh migration; các lần ghi cấu hình tiếp theo lưu `socket`. Không xóa lịch sử cũ.
- Thay test Nmap bằng test tương thích cấu hình cũ; cập nhật tài liệu sử dụng và kế hoạch kiểm thử. Giữ nguyên các báo cáo kiểm thử lịch sử.

**Tiêu chí hoàn thành:** ứng dụng quét được khi không có thư viện Python lẫn binary Nmap; không bổ sung engine quét hoặc dependency thay thế.

## 2. Firewall Check: dữ liệu và đánh giá

Tạo module theo `ScannerBase` và cơ chế đăng ký hiện có.

- Đọc ba profile **Domain, Private, Public**, trạng thái bật/tắt và chính sách inbound/outbound mặc định.
- Dùng `Get-NetConnectionProfile` xác định profile của các kết nối hiện tại; hỗ trợ nhiều adapter cùng lúc.
- Đọc các rule đang bật từ `ActiveStore`, gồm tên/định danh, profile, chiều kết nối, hành động, giao thức, cổng, địa chỉ, chương trình và dịch vụ. Lấy điều kiện từ các filter tương ứng theo [tài liệu Microsoft](https://learn.microsoft.com/en-us/powershell/module/netsecurity/get-netfirewallrule?view=windowsserver2025-ps).
- Gọi Windows PowerShell bằng script cố định, chạy ẩn, không tương tác, trả JSON; timeout 60 giây. Không ghép dữ liệu người dùng vào câu lệnh.
- Thiếu quyền, thiếu cmdlet, timeout hoặc dữ liệu bắt buộc không hợp lệ phải kết thúc lượt quét bằng lỗi rõ ràng; không trả danh sách rỗng như một kết quả an toàn.

Quy tắc đánh giá v1:

| Điều kiện | Kết quả |
|---|---|
| Profile đang sử dụng bị tắt, hoặc mặc định inbound là Allow | `danger` |
| Điều kiện trên xảy ra ở profile chưa sử dụng | `warning` |
| Rule inbound Allow áp dụng Public/Any, cho phép mọi địa chỉ nguồn và mọi cổng đối với TCP/UDP/Any | `warning` |
| Giá trị chính sách chưa xác định, như `NotConfigured` | `warning`, ghi rõ chưa kết luận được |
| Không khớp điều kiện cảnh báo | `safe`, hiển thị “Không phát hiện theo tiêu chí v1” |

Mỗi mục giữ đầy đủ bằng chứng, lý do và hướng dẫn kiểm tra trong Windows Firewall. Rule rộng chỉ là dấu hiệu cần xem xét; không suy ra khả năng truy cập thực tế, không coi outbound Allow mặc định là bất thường.

## 3. API, lưu trữ và giao diện

- Thêm bốn endpoint dưới `/api/v1/modules/firewall-check`: `POST /scan`, `GET /scans/latest`, `GET /scans/{scan_id}`, `GET /scans`. Dùng envelope, token và phân trang như Port Scanner.
- Tái sử dụng bảng scan/item và WebSocket hiện có. Chi tiết kết quả phân biệt `profile` và `rule`; summary gồm `total_profiles`, `total_rules`, `danger`, `warning`, `safe`. Không thêm bảng riêng.
- Tách phần tuần tự hóa kết quả đang có thành helper dùng chung cho hai module; không xây framework router mới.
- Dùng định danh profile/rule ổn định cho so sánh xuất hiện/biến mất. Chọn lượt quét hoàn tất, đầy đủ gần nhất làm mốc, tránh đánh dấu mọi mục là mới sau một lượt lỗi. V1 chưa bổ sung lịch sử thay đổi từng thuộc tính của rule.
- Kích hoạt trang Firewall Check: trạng thái ba profile, bảng rule có tìm kiếm, lý do cảnh báo, hướng dẫn, tiến trình và lỗi. Dùng các component hiện có; không có nút sửa firewall hoặc whitelist.
- Mở rộng kiểu summary phía frontend để hỗ trợ số lượng riêng từng module, giữ tương thích dữ liệu Port Scanner cũ.
- Scan History có bộ chọn Port Scanner/Firewall Check, mặc định Port Scanner; tải lịch sử theo module, hiển thị số lượng và mở đúng module.
- Cập nhật tài liệu API hiện có và mô tả OpenAPI từ backend. Không thêm workspace hay collection Postman cho phạm vi này.

## 4. Kiểm thử và trình tự bàn giao

**Đợt 1 — bỏ Nmap:**

- Kiểm tra TCP LISTEN, UDP, IPv4/IPv6, PID, tiến trình biến mất và thiếu quyền.
- Kiểm tra cấu hình cũ `scan_mode: nmap`, whitelist, diff và đọc lịch sử cũ.
- Xác nhận không còn import hoặc gọi executable Nmap trong mã chạy.

**Đợt 2 — Firewall Check:**

- Test dữ liệu PowerShell giả lập: nhiều profile hoạt động, không có kết nối, không có rule, Unicode, mảng một/nhiều phần tử, timeout, thiếu quyền và JSON lỗi.
- Test toàn bộ bảng đánh giá; rule Block, outbound và rule giới hạn địa chỉ/cổng không bị gắn nhầm cảnh báo “quá rộng”.
- Test API/token, phân trang, tách dữ liệu giữa module, WebSocket, lưu kết quả và quét lại sau lỗi.
- Cập nhật Selenium cho Firewall Check đã hoạt động, luồng quét và chuyển lịch sử; chạy lint/build frontend và kiểm thử backend liên quan.
- Đối chiếu một lượt đọc thực tế với Windows Firewall, không thay đổi cấu hình máy.

Giữ các chỉnh sửa chưa commit hiện có. Mặc định quét thủ công, không thêm lịch tự động hoặc dependency mới.

**Giới hạn:** v1 đánh giá cấu hình tại máy, chưa kiểm chứng truy cập từ Internet hay tính hiệu lực tổng hợp của mọi rule.
