# Changelog

Ghi lại thay đổi đáng chú ý cho người dùng và contributor. Mục Unreleased chưa phải một release được gắn tag. Quy tắc cập nhật nằm trong [CONTRIBUTING.md](CONTRIBUTING.md#tài-liệu-và-changelog).

## Unreleased

### Added

- Hướng dẫn đóng góp: phạm vi commit/PR, Conventional Commits, kiểm thử theo loại thay đổi, bảo vệ dữ liệu local và quy tắc force-with-lease.
- [Thiết kế Startup Programs](docs/plans/startup-programs.md): kiểm kê Run/RunOnce và Startup folders, dự kiến lưu nhật ký trước/sau và SHA-256 của tệp. Module chưa được triển khai.

### Changed

- Tổ chức tài liệu thành architecture, plans, testing và archive; thêm [mục lục](docs/README.md) và đưa các tài liệu Markdown đã chọn vào Git.
- Đồng bộ README và tài liệu hệ thống với Port Scanner dùng psutil, Firewall Check đang hoạt động và giới hạn scheduler hiện tại.
- Chọn một [tài liệu frontend chính](docs/architecture/frontend.md); giữ frontend/DESIGN.md làm liên kết chuyển tiếp và sửa đường dẫn tham chiếu trong comment/docstring.

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
