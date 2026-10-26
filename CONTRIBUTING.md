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

## Quy trình planner → executor → reviewer

Khi người dùng yêu cầu làm việc với subagent, điều phối các vai trò trong cùng một task/chat. Mặc định chạy tuần tự trên một nhánh: chỉ executor sửa product code và tests; điều phối viên tích hợp và cập nhật tài liệu. Không tạo chat riêng hoặc cho nhiều agent ghi cùng tệp.

| Vai trò | Model / effort mặc định | Trách nhiệm và bàn giao |
|---|---|---|
| Planner | GPT-6.1 Sol / high | Đọc hướng dẫn repo, truy callers và nguyên nhân lỗi; lập phạm vi, contract, rủi ro và tiêu chí kiểm chứng trước khi sửa. |
| Executor | GPT-6.1 Sol / high | Thực hiện kế hoạch nhỏ nhất đủ yêu cầu, thêm regression tests và bàn giao diff cùng kết quả lệnh thực chạy. |
| Reviewer | GPT-6 Astra / high | Review độc lập, chỉ đọc; kiểm tra yêu cầu, diff, callers, tests, bảo mật và các tình huống lỗi/race. Trả finding có vị trí, mức độ, cách tái hiện và điều kiện chấp nhận. |

- Chọn lại model/effort theo độ phức tạp và model khả dụng; ghi lựa chọn thực tế trong bàn giao. Không âm thầm coi model thay thế là model đã yêu cầu.
- Nạp skill đúng vai trò: lập kế hoạch/debug nguyên nhân cho planner; debugging, kiểm thử và skill frontend/backend phù hợp cho executor; review, bảo mật khi liên quan và verification cho reviewer. Điều phối viên nạp Postman API Engineer khi đổi API, chốt contract trước implementation và chọn kiểm chứng phù hợp; tránh setup/publish bên ngoài khi không cần.
- Theo dõi mỗi hạng mục với owner, phạm vi tệp, trạng thái, tiêu chí chấp nhận và bằng chứng trong kế hoạch/báo cáo của task. Không cần thêm hệ thống Kanban cho thay đổi đơn lẻ.
- Tối đa **3 vòng review–fix**: reviewer review → executor sửa finding có bằng chứng → chạy lại kiểm chứng bị ảnh hưởng. Dừng sớm khi reviewer không còn finding cần sửa và các gate đạt. Lần kiểm tra lại sau sửa thuộc vòng đó; không mở vòng sửa thứ tư.
- Nếu hết 3 vòng vẫn còn lỗi, ghi rõ phần tồn đọng, ảnh hưởng và bước tiếp theo; không báo hoàn tất hoặc merge khi gate chưa đạt. Không tính việc nạp skill/đọc mã là một vòng review.
- Gate bàn giao: kiểm chứng theo bảng ở trên, review toàn diff và `git diff --check`; báo phần chưa kiểm chứng. Commit/push/merge vẫn tuân theo quyền hạn và quy tắc của repo.

## Tài liệu và changelog

- Giữ [docs/README.md](docs/README.md) làm điểm điều hướng. Kế hoạch ở `docs/plans/`, bằng chứng kiểm thử ở `docs/testing/reports/`; giữ số liệu lịch sử trong archive.
- Cập nhật [CHANGELOG.md](CHANGELOG.md) phần Unreleased cho thay đổi người dùng/contributor cần biết. Nhóm theo Added, Changed, Fixed, Removed hoặc Security; không ghi mọi commit nhỏ.
- Kế hoạch chỉ được ghi là tài liệu được bổ sung, không được mô tả như tính năng đã phát hành. Chỉ thêm phiên bản/ngày phát hành khi có release thật; không suy ra release từ version trong mã nguồn.

## Dữ liệu local và push

- Không commit config/token thật, `.env` local, database, nội dung scan từ máy thật hoặc log thô. Dùng fixture giả và giữ localhost/token/Origin guards.
- `docs/` bỏ qua tệp mới: thêm từng tài liệu được chọn bằng `git add -f <path>`. Kiểm tra `git diff --cached` trước khi commit; không force-add cả thư mục.
- Dùng push thông thường khi có thể. Khi được cho phép force-push, đọc SHA remote hiện tại và dùng `--force-with-lease=<ref>:<expected-sha>`. Nếu lease thất bại, fetch và review thay đổi mới trước khi quyết định tiếp; không đổi sang `--force` để ghi đè.
- Sau khi push, đối chiếu SHA nhánh remote với commit local và báo rõ nhánh, commit đã công bố cùng những giới hạn kiểm chứng.
