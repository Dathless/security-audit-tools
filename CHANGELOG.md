# Changelog

Ghi lại thay đổi đáng chú ý cho người dùng và contributor. Mục Unreleased chưa phải một release được gắn tag. Quy tắc cập nhật nằm trong [CONTRIBUTING.md](CONTRIBUTING.md#tài-liệu-và-changelog).

## Unreleased

### Added

- Firewall Check: thanh tiến trình phân biệt lúc đọc cấu hình chưa biết tổng và lúc đánh giá profiles/rules; thời gian đã chạy, ETA tham chiếu lượt thành công trước đó và nhật ký có thể mở/thu gọn. Nhật ký chỉ chứa hoạt động quan sát trong phiên; thiếu mẫu ETA hoặc vượt mẫu được báo rõ.

- UI Console với ba theme Technical Console (mặc định), Graphite Studio và Light Precision; lưu lựa chọn local, bảo toàn filter/bằng chứng/scan khi đổi. Điều hướng manifest có tìm kiếm, menu mobile và ngăn bằng chứng dùng chung cho endpoint/rule.

- Port Scanner 0.2.0: endpoint identity v2, nhiều owner và metadata có trạng thái, mọi risk reasons/guidance, review có fingerprint/expiry và bằng chứng trước/sau. API `/reviews` hỗ trợ tạo idempotent, phân trang và hủy; bảng riêng được tạo bổ sung, không sửa snapshot lịch sử.
- Khóa Port scan trong một backend process (REST trùng 409, scheduler bỏ lượt), xử lý constructor/restart, phục hồi WebSocket và chạy tiếp scan đang có trên giao diện.
- Hướng dẫn đóng góp: phạm vi commit/PR, Conventional Commits, kiểm thử theo loại thay đổi, bảo vệ dữ liệu local và quy tắc force-with-lease.
- [Thiết kế Startup Programs](docs/plans/startup-programs.md): kiểm kê Run/RunOnce và Startup folders, dự kiến lưu nhật ký trước/sau và SHA-256 của tệp. Module chưa được triển khai.

### Changed

- Hướng dẫn contributor bổ sung quy trình planner → executor → reviewer trong cùng task, phân công model/effort và skill, yêu cầu bằng chứng và giới hạn tối đa 3 vòng review–fix.

- Dựng lại shell, metric strip, bảng và panel bằng semantic tokens chung; ba theme chỉ đổi palette/layout/motion. Giữ toàn bộ owner, trạng thái metadata, reasons/guidance và trước/sau trong bằng chứng; risk/review và API không đổi. Motion tôn trọng reduced motion, radar không chạy lúc idle, bỏ tải Google Fonts.

- **Breaking:** POST Port Scanner `/whitelist` trả `410 WHITELIST_REPLACED_BY_REVIEW`; dùng `{scan_id,item_id,note?}` với `/reviews`. GET/DELETE whitelist legacy giữ lại. Xác nhận không hạ severity/reasons/KPI; snapshot legacy giữ nguyên và không được review bằng contract mới.
- Risky-port chỉ loopback là warning; ngoài loopback kết hợp risky-port là danger (ưu tiên cao). IPv4/IPv6, TCP/UDP và bind address không dùng chung identity. Scan v2 đầu là initial; partial không tạo removal hoặc baseline. Lỗi toàn bộ inventory là error, không còn “port 0”.
- Collector cache PID trong scan, dùng oneshot; một truy vấn inventory và tối đa một Process cho mỗi PID. [Báo cáo nâng cấp](docs/testing/reports/port-scanner-upgrade.md) ghi số đo fixture và kiểm chứng, không cam kết SLA trên máy thật.
- Tổ chức tài liệu thành architecture, plans, testing và archive; thêm [mục lục](docs/README.md) và đưa các tài liệu Markdown đã chọn vào Git.
- Đồng bộ README và tài liệu hệ thống với Port Scanner dùng psutil, Firewall Check đang hoạt động và giới hạn scheduler hiện tại.
- Chọn một [tài liệu frontend chính](docs/architecture/frontend.md); giữ frontend/DESIGN.md làm liên kết chuyển tiếp và sửa đường dẫn tham chiếu trong comment/docstring.

### Fixed

- Firewall Check chặn quét trùng (REST trả `409 SCAN_ALREADY_RUNNING`, scheduler bỏ lượt), phục hồi trạng thái bị gián đoạn khi backend restart và đối chiếu đúng scan ID khi mất kết nối/hoàn tất. Bỏ phản hồi/callback cũ để tránh ghi đè lượt đang theo dõi; progress được phát khi từng mục thực sự được đánh giá.

- UI vẫn mở được khi trình duyệt chặn localStorage và không có token từ env; Settings báo rõ khi token chưa lưu được, giữ nguyên kiểm tra xác thực. Bằng chứng tạm đóng khi scan lỗi/mất kết nối để không bị thay âm thầm bằng snapshot cũ; giữ lựa chọn sắp xếp giao thức và hành động trong bảng gọn.

## 2026-10-24 — Mốc tích hợp PR #1

Đây là mốc lịch sử được xác nhận bởi [PR #1](https://github.com/Dathless/security-audit-tools/pull/1) và merge commit [bc7675c](https://github.com/Dathless/security-audit-tools/commit/bc7675c098b5f4b60f893e7aa88af745ad167e7a), không phải release được gắn tag.

### Added

- Firewall Check chỉ đọc Windows profiles và enabled rules từ ActiveStore, giải thích cảnh báo, có dashboard, API và lịch sử theo module.
- Cơ chế phục hồi UI khi mất WebSocket và đồng bộ trạng thái đang quét khi chuyển trang.

### Changed

- Port Scanner kiểm kê TCP LISTEN/UDP bằng psutil; cấu hình scan_mode nmap cũ chuyển sang socket, giữ dữ liệu lịch sử và các trường API tương thích.
- Diff dùng snapshot thành công và đầy đủ làm mốc; kiểm thử browser được cô lập dữ liệu.

### Removed

- Nhánh thực thi Nmap và dependency python-nmap; không cần cài Nmap binary để dùng Port Scanner.

### Security

- Hai kênh WebSocket kiểm tra local token và browser Origin trước khi accept; browser truyền token bằng subprotocol, không đặt trong URL.

Bằng chứng tại thời điểm tích hợp: 295 tests đạt, gồm browser tests; frontend lint/build đạt. Xem [báo cáo kiểm chứng](docs/testing/reports/firewall-check-nmap-removal.md). Đây là số liệu lịch sử, không phải lần chạy mới cho thay đổi tài liệu.
