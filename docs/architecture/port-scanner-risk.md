# Port Scanner — kiểm kê, đánh giá và review

Trạng thái: endpoint identity v2, assessment v2, module 0.2.0. Xem [kế hoạch và checklist](../plans/port-scanner-upgrade.md), [backend](backend.md) và [bằng chứng kiểm thử](../testing/reports/port-scanner-upgrade.md).

## Phạm vi kiểm kê

Collector chỉ đọc `psutil.net_connections(kind="inet")` một lần: TCP `LISTEN` và UDP đang bind. UDP không được diễn giải thành dịch vụ đang lắng nghe. Một dòng là `(protocol, family, scoped bind address, port)`, giữ đủ `owners[]`; PID/tên tiến trình không thuộc identity endpoint.

Metadata gồm tên, executable path, username và create time, với trạng thái từng trường `ok`, `unknown`, `access_denied`, `gone`. Cache PID chỉ tồn tại trong một lượt quét; `Process.oneshot()` gom đọc thuộc tính theo [tài liệu psutil 7.2.2](https://github.com/giampaolo/psutil/blob/v7.2.2/docs/index.rst). Không đọc được inventory toàn bộ tạo scan `error`, không có mục giả port 0. Metadata thiếu không đồng nghĩa inventory endpoint thiếu; inventory partial không tạo removal và không làm baseline.

## Rule đang chạy

Mọi rule đều được đánh giá, giữ đầy đủ reason codes và guidance; severity là mức cao nhất.

| Bằng chứng | Severity |
|---|---|
| Loopback, owner xác định, không có dấu hiệu khác | `safe`: không có phát hiện theo tiêu chí hiện tại |
| Cổng trong `known_risky_ports`, chỉ bind loopback | `warning` |
| Wildcard hoặc địa chỉ không phải loopback | `warning` |
| Cổng trong danh sách cần chú ý + ngoài loopback | `danger`: ưu tiên xem xét cao |
| Thiếu executable/user của ít nhất một owner | `warning`, không suy luận malware |

Reason codes: `PORT_IN_RISKY_LIST`, `LISTENING_ON_ALL_INTERFACES`, `NON_LOOPBACK_BIND`, `PROCESS_IDENTITY_UNKNOWN`. Cấu hình risky ports chỉ nhận danh sách số nguyên `1..65535`; `[]` nghĩa là không cấu hình cổng cần chú ý.

Bind address không chứng minh truy cập được từ LAN/Internet. Tên/path executable không chứng minh dịch vụ, phiên bản, chữ ký hoặc lỗ hổng. Không có port/process mismatch rule chỉ dựa vào tên.

## Review độc lập với risk

Xác nhận đã xem không đổi severity, reasons hay KPI rủi ro. Fingerprint gồm identity endpoint, tập executable/user đã sắp xếp và loại trùng, assessment version, severity và reasons; bỏ PID/thời gian quan sát/cấu hình không ảnh hưởng kết quả.

- Đủ identity mọi owner và inventory đầy đủ: review dùng xuyên scan khi bằng chứng còn khớp.
- Thiếu metadata/partial: chỉ xác nhận scan hiện tại; review lâu dài bị tạm ngưng áp dụng.
- Quan sát owner/risk đổi hoặc endpoint biến mất trong inventory đầy đủ: review hết hiệu lực. Partial chỉ chặn expiry do vắng mặt, không bỏ qua thay đổi đã quan sát. A → B → A phải xác nhận lại.
- Snapshot và expiry được ghi cùng transaction qua `ScannerBase.on_persist`; rollback không để lại review expiry đơn lẻ.

API review chỉ nhận item của snapshot mới nhất đã hoàn tất; target bị thay thế trả `409`. POST whitelist cũ trả `410`; GET/DELETE giữ phục vụ chuyển đổi, không tự tạo review hoặc hạ risk.

## Lịch sử và giới hạn

Baseline chỉ dùng scan done, đầy đủ, cùng identity version. Scan v2 đầu tiên là “Ban đầu”; về sau phân biệt thêm/đổi/không đổi và lưu bằng chứng trước/sau cho mục đổi. Snapshot cũ giữ nguyên, được gắn `legacy`; không suy diễn risk của các dòng safe cũ.

V1 chạy một backend process trên SQLite. Chưa có active probe, quét đích mạng, Windows Services, xác minh executable/chữ ký, CVE hoặc đối chiếu firewall. Path/user không phát hiện nội dung binary bị thay tại cùng đường dẫn. Các ý tưởng này cần thiết kế và bằng chứng riêng trước khi bổ sung rule.
