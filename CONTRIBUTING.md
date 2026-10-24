# Contributing

Tài liệu này quy định cách đóng góp và review cho Security Audit Tool. Đọc [README](README.md) để chạy dự án, [AGENTS.md](AGENTS.md) để biết cấu trúc và style, và [mục lục tài liệu](docs/README.md) trước khi sửa thiết kế.

## Phạm vi và nhánh làm việc

- Tạo nhánh ngắn hạn từ main, dùng tên `codex/<muc-dich>`, ví dụ `codex/startup-programs`.
- Mỗi thay đổi giải quyết một mục tiêu rõ ràng. Tách sửa lỗi, refactor và thay đổi quy trình khi chúng có thể review độc lập.
- Ưu tiên helper, design-system và dependency đang có. Module mới đăng ký qua manifest; core không import trực tiếp module cụ thể.
- Tạo PR vào main theo mặc định. Thay đổi trực tiếp hoặc viết lại lịch sử nhánh đã chia sẻ cần được người duy trì cho phép rõ ràng; yêu cầu đó không cho phép bỏ qua branch protection.

## Commit messages

Dùng Conventional Commits, subject tiếng Anh ở thể mệnh lệnh, không có dấu chấm cuối và tối đa 72 ký tự:

```text
type(scope): short imperative description

Explain why the change is needed and any compatibility impact.
Record checks actually run and relevant limitations.
```

- Type: `feat`, `fix`, `docs`, `refactor`, `test`, `perf`, `build`, `ci`, `chore`, `style`, `revert`.
- Scope là tùy chọn; dùng tên quen thuộc như `api`, `ui`, `storage`, `port-scanner` hoặc `firewall-check` khi nó giúp làm rõ phạm vi. Các commit hiện có thường bỏ scope.
- Thay đổi nhỏ có thể chỉ cần subject. Thêm body khi cần giải thích lý do, tương thích hoặc bằng chứng kiểm thử; tránh subject chung chung như “update” hay “fix stuff”.
- Thay đổi phá vỡ tương thích dùng `!` và footer `BREAKING CHANGE:` nêu cách chuyển đổi. Chỉ liên kết issue có thật; không sửa thông điệp commit đã công bố nếu chưa được cho phép.

Ví dụ: `docs: organize project guides and startup plan`, `fix(api): preserve legacy scan fields`.

## Kiểm chứng trước khi gửi

| Loại thay đổi | Kiểm chứng cần thiết |
|---|---|
| Logic backend, collector, persistence hoặc API | Từ backend chạy `python -m pytest`; thêm test cho hành vi và lỗi mới, mock quan sát OS/network |
| UI hoặc TypeScript | Từ frontend chạy `pnpm lint` và `pnpm build` |
| Luồng người dùng, WebSocket, navigation hoặc trạng thái quét | Từ backend chạy `python -m pytest --selenium` trong môi trường có browser phù hợp |
| Chỉ tài liệu/comment | Kiểm tra liên kết và đường dẫn bị ảnh hưởng; chạy `git diff --check` và `git diff --cached --check`; ghi rõ nếu không chạy application tests |

Đọc kết quả thực tế trước khi báo đạt. Số liệu trong báo cáo lịch sử không thay cho lần chạy mới. Tính năng chưa triển khai phải giữ trạng thái planned/coming-soon.

## Pull request và review

- Mô tả vấn đề, hành vi sau thay đổi, phạm vi và ảnh hưởng bảo mật/tương thích; liên kết issue nếu có.
- Liệt kê lệnh đã chạy, kết quả và phần chưa kiểm chứng. Có ảnh minh họa với thay đổi UI nhìn thấy được, dùng dữ liệu giả đã chọn để chia sẻ.
- Review diff hoàn chỉnh, bao gồm callers, fixture và tài liệu liên quan. Sửa các vấn đề có bằng chứng và kiểm tra lại trước khi merge.
- Không đánh dấu checklist đạt bằng suy đoán. Quy định ở đây được kiểm tra khi review; enforcement tự động chỉ có hiệu lực khi được cấu hình riêng.

## Tài liệu và changelog

- Giữ [docs/README.md](docs/README.md) làm điểm điều hướng. Kế hoạch ở `docs/plans/`, bằng chứng kiểm thử ở `docs/testing/reports/`; giữ số liệu lịch sử trong archive.
- Cập nhật [CHANGELOG.md](CHANGELOG.md) phần Unreleased cho thay đổi người dùng/contributor cần biết. Nhóm theo Added, Changed, Fixed, Removed hoặc Security; không ghi mọi commit nhỏ.
- Kế hoạch chỉ được ghi là tài liệu được bổ sung, không được mô tả như tính năng đã phát hành. Chỉ thêm phiên bản/ngày phát hành khi có release thật; không suy ra release từ version trong mã nguồn.

## Dữ liệu local và push

- Không commit config/token thật, `.env` local, database, nội dung scan từ máy thật hoặc log thô. Dùng fixture giả và giữ localhost/token/Origin guards.
- `docs/` bỏ qua tệp mới: thêm từng tài liệu được chọn bằng `git add -f <path>`. Kiểm tra `git diff --cached` trước khi commit; không force-add cả thư mục.
- Dùng push thông thường khi có thể. Khi được cho phép force-push, đọc SHA remote hiện tại và dùng `--force-with-lease=<ref>:<expected-sha>`. Nếu lease thất bại, fetch và review thay đổi mới trước khi quyết định tiếp; không đổi sang `--force` để ghi đè.
- Sau khi push, đối chiếu SHA nhánh remote với commit local và báo rõ nhánh, commit đã công bố cùng những giới hạn kiểm chứng.
