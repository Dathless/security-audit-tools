# Tài liệu dự án

Đọc [README dự án](../README.md) để cài đặt và chạy ứng dụng. Thư mục này phân biệt thiết kế, kế hoạch chưa triển khai và bằng chứng kiểm thử; trạng thái thực tế cần đối chiếu với mã nguồn và tests.

## Bắt đầu từ đâu

| Nhu cầu | Tài liệu |
|---|---|
| Hiểu kiến trúc backend | [Backend](architecture/backend.md) |
| Triển khai module tiếp theo | [Startup Programs — thiết kế và checklist](plans/startup-programs.md) |
| Xem phần Firewall Check và bỏ Nmap đã hoàn thành | [Kế hoạch](plans/completed/firewall-check-nmap-removal.md), [checklist](plans/completed/firewall-check-nmap-removal-checklist.md), [bằng chứng kiểm thử](testing/reports/firewall-check-nmap-removal.md) |
| Hiểu UI và design tokens | [Kiến trúc frontend](architecture/frontend.md); [đường dẫn cũ](../frontend/DESIGN.md) giữ liên kết tương thích |

## Tài liệu tham khảo và lịch sử

| Tài liệu | Cách sử dụng |
|---|---|
| [Định hướng đánh giá rủi ro Port Scanner](architecture/port-scanner-risk.md) | Phân biệt các rule hiện có với các level mới được đề xuất |
| [Đề xuất Active Modules](plans/proposals/active-modules.md) | Ý tưởng tham khảo, chưa phải chức năng đã triển khai |
| [Danh mục test case](testing/test-cases.md), [kế hoạch unit test](testing/unit-test-plan.md) | Đối chiếu với test thực thi và báo cáo mới nhất |
| [Kế hoạch sửa Selenium trước đây](archive/selenium-ui-fix-plan.md) | Bối cảnh lỗi cũ, không đại diện cho trạng thái hiện tại |
| [Test log](archive/testing/test-log.md), [báo cáo ngày 2026-08-14](archive/testing/test-report.md) | Bằng chứng lịch sử, giữ nguyên số liệu gốc |

## Cấu trúc

```text
docs/
├── README.md
├── architecture/       # Thiết kế backend, frontend và đánh giá rủi ro
├── plans/
│   ├── startup-programs.md
│   ├── completed/      # Kế hoạch và checklist của phần đã hoàn thành
│   └── proposals/      # Ý tưởng tham khảo, chưa cam kết triển khai
├── testing/
│   ├── test-cases.md
│   ├── unit-test-plan.md
│   └── reports/        # Bằng chứng kiểm thử theo tính năng
├── archive/            # Kế hoạch sửa lỗi, báo cáo và log lịch sử
│   └── testing/
└── screenshots/        # Ảnh minh họa được chọn để chia sẻ
```

## Quy ước cập nhật

- Dùng tên tệp `kebab-case.md`, mô tả rõ nội dung; kế hoạch mới đặt trong `plans/` và có checklist kiểm chứng.
- Giữ một bản kế hoạch cho mỗi tính năng. Khi thiết kế được điều chỉnh, cập nhật bản đó thay vì tạo tài liệu cạnh tranh.
- Kế hoạch đã thực hiện chuyển vào `plans/completed/`; báo cáo kiểm chứng đặt trong `testing/reports/`. Không đánh dấu hoàn thành chỉ vì đã có tài liệu.
- Giữ báo cáo/log cũ trong `archive/` với số liệu gốc. Chúng không đại diện cho kết quả kiểm thử hiện tại.
- Khi di chuyển tệp, sửa cả liên kết Markdown và đường dẫn tham chiếu trong README, hướng dẫn contributor và tài liệu liên quan.
- `docs/` vẫn bị Git bỏ qua cho tệp mới; các tài liệu Markdown được chọn trong mục lục được theo dõi trong Git. Khi thêm tài liệu, chọn từng tệp cần chia sẻ bằng `git add -f <path>`. Log lỗi thô vẫn chỉ có trên máy; không thêm toàn bộ thư mục hoặc log thô.

Hai tài liệu kiến trúc backend/frontend mô tả hệ thống hiện tại. `architecture/port-scanner-risk.md` phân biệt quy tắc đang chạy với ý tưởng mở rộng; `plans/proposals/active-modules.md`, các kế hoạch kiểm thử ban đầu và nội dung `archive/` là tài liệu tham khảo, không xác nhận những đề xuất trong đó đã được triển khai.
