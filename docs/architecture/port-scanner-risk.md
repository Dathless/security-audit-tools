# Risky Standard — Port Scanner Risk Assessment

> **Trạng thái 2026-10-24:** tài liệu định hướng đánh giá rủi ro, không phải danh sách tính năng đã triển khai. Port Scanner hiện chỉ phân loại theo risky-port list, listener 0.0.0.0/:: và lỗi quyền đọc tiến trình; whitelist có thể override severity thành safe. Reason codes hiện dùng là PORT_IN_RISKY_LIST, LISTENING_ON_ALL_INTERFACES và PROCESS_IDENTIFICATION_FAILED. Không có fingerprint dịch vụ/version, kiểm tra CVE hoặc suy luận port/process mismatch từ tên executable. Các level mở rộng bên dưới vẫn là đề xuất. Xem [backend](backend.md) và [scanner đang chạy](../../backend/modules/port_scanner/scanner.py).

## 1. Mục tiêu

Nâng cấp module Port Scanner từ mô hình:

- `DANGER`: port nằm trong risky list
- `WARNING`: listener là `0.0.0.0` hoặc không đọc được process name
- `SAFE`: các trường hợp còn lại

thành mô hình đánh giá rủi ro dựa trên **evidence → rule → risk → reason**.

> Nguyên tắc: Port mở không đồng nghĩa với nguy hiểm. `0.0.0.0` là dấu hiệu exposure, không tự động là vulnerability. Không đọc được process cũng không có nghĩa process độc hại.

---

# 2. Risk Level

| Level | Ý nghĩa |
|---|---|
| `SAFE` | Chưa phát hiện dấu hiệu rủi ro từ các rule hiện có |
| `WARNING` | Có dấu hiệu cần kiểm tra thêm nhưng chưa đủ bằng chứng để kết luận nguy hiểm |
| `DANGER` | Có bằng chứng/rule đủ mạnh để đánh dấu rủi ro cao |
| `CRITICAL` | Dành cho phiên bản nâng cao; rủi ro rất cao, thường cần kết hợp nhiều evidence |

### Priority

Khi nhiều điều kiện cùng xảy ra, áp dụng mức cao nhất:

```text
CRITICAL > DANGER > WARNING > SAFE
```

Ví dụ:

```text
4444 + 0.0.0.0 + process unknown
→ DANGER
```

Không được hạ xuống `WARNING` chỉ vì listener/process rule được kiểm tra sau.

---

# 3. Kiến trúc đánh giá

```text
Open Port
   ↓
Listener / Exposure Detection
   ↓
Process Identification
   ↓
Service / Process Analysis
   ↓
Rule Evaluation
   ↓
Risk Level
   ↓
Reasons / Findings
```

Không nên chỉ trả về:

```text
port → danger/safe
```

Nên trả về:

```text
port
protocol
listener
process
risk
reasons
```

---

# 4. LEVEL 1 — Core Rules

Đây là phạm vi bắt buộc nên triển khai trước. Phù hợp với sinh viên Software Engineering.

## 4.1 Risky Port

### Rule

```text
IF port ∈ risky_list
THEN DANGER
```

### Risky list hiện tại

```text
4444
1337
31337
```

Không hard-code trực tiếp trong logic scanner. Nên lưu thành cấu hình/metadata.

Ví dụ:

```json
{
  "4444": {
    "severity": "DANGER",
    "reason": "Known high-risk port"
  },
  "1337": {
    "severity": "DANGER",
    "reason": "Known high-risk port"
  },
  "31337": {
    "severity": "DANGER",
    "reason": "Known high-risk port"
  }
}
```

### Lưu ý

Risky port là **evidence mạnh**, không phải bằng chứng máy đã bị compromise.

---

## 4.2 Listener Scope

### Hiện tại

```text
listener == 0.0.0.0
→ WARNING
```

Giữ rule này ở Level 1.

### Khuyến nghị mở rộng

Phân loại:

```text
127.0.0.1 / localhost → LOCAL_ONLY
private interface      → INTERNAL
0.0.0.0                → ALL_INTERFACES
::                     → ALL_INTERFACES_IPV6
unknown                → UNKNOWN
```

### Risk baseline

| Listener | Baseline |
|---|---|
| `127.0.0.1` | SAFE/LOW |
| Private interface | SAFE/WARNING tùy service |
| `0.0.0.0` | WARNING |
| `::` | WARNING |
| Unknown | WARNING |

`0.0.0.0` không nên tự động trở thành DANGER.

---

## 4.3 Process Identification

### Rule hiện tại

```text
IF process_name cannot be read
THEN WARNING
```

Giữ rule này.

### Reason

```text
PROCESS_IDENTIFICATION_FAILED
```

### Không được làm

```text
process_name == null
→ DANGER
```

Không đọc được process có thể chỉ do permission.

---

## 4.4 Port / Process Mismatch

Thêm rule:

```text
port + process/service
```

thay vì chỉ đánh giá port.

Ví dụ mapping cơ bản:

| Port | Expected service |
|---|---|
| 22 | SSH |
| 80 | HTTP |
| 443 | HTTPS |
| 3306 | MySQL |
| 5432 | PostgreSQL |
| 6379 | Redis |
| 27017 | MongoDB |

Nếu service/process không phù hợp:

```text
→ WARNING
```

Reason:

```text
SERVICE_PORT_MISMATCH
```

Không kết luận malware chỉ dựa trên mismatch.

---

# 5. LEVEL 2 — Service Awareness

Sau khi Level 1 ổn định, thêm nhận diện mức độ nhạy cảm của service.

## 5.1 Service Sensitivity

### Low

```text
HTTP
HTTPS
DNS
```

### Medium

```text
SSH
FTP
SMTP
```

### High

```text
RDP
VNC
Database
Redis
MongoDB
Elasticsearch
Admin panel
```

Mức độ nhạy cảm chỉ là **risk factor**, không phải luôn luôn DANGER.

---

## 5.2 Sensitive Service Exposure

Ví dụ:

```text
0.0.0.0:8080 + HTTP
→ WARNING
```

Nhưng:

```text
0.0.0.0:3306 + MySQL
→ DANGER
```

Trong khi:

```text
127.0.0.1:3306 + MySQL
→ SAFE
```

### Reason

```text
SENSITIVE_SERVICE_EXPOSED
```

hoặc cụ thể:

```text
DATABASE_EXPOSED_ON_ALL_INTERFACES
```

---

## 5.3 Database Exposure

Các service nên nhận diện:

```text
MySQL
PostgreSQL
MongoDB
Redis
Elasticsearch
Memcached
```

Rule cơ bản:

```text
database + all interfaces
→ DANGER
```

database + private interface:

```text
→ WARNING hoặc SAFE tùy context
```

database + localhost:

```text
→ SAFE
```

---

# 6. LEVEL 3 — Process Context

## 6.1 Process Name

Nếu đọc được:

```text
PID
process name
```

thì lưu lại.

Ví dụ:

```text
22 → sshd
80 → nginx
3306 → mysqld
```

---

## 6.2 Process Classification

Phân loại:

```text
KNOWN
UNKNOWN
SUSPICIOUS
```

### Known

Process phù hợp với service.

```text
22 + sshd
→ KNOWN
```

### Unknown

Không xác định được.

```text
22 + unknown
→ WARNING
```

Reason:

```text
UNKNOWN_PROCESS
```

### Suspicious

Tên/path có dấu hiệu bất thường theo rule.

```text
→ WARNING hoặc DANGER
```

Không được kết luận malware chỉ dựa vào tên process.

---

## 6.3 Process Path

Nếu OS/API cho phép đọc executable path:

```text
PID
→ process
→ executable path
```

Ví dụ:

```text
nginx
/usr/sbin/nginx
```

→ bình thường.

Nhưng:

```text
nginx
/tmp/nginx
```

→ WARNING.

Reason:

```text
UNEXPECTED_PROCESS_PATH
```

Đây là rule nâng cao nhưng vẫn có giá trị thực tế.

---

## 6.4 Process Owner

Nếu lấy được user/owner:

```text
process
→ owner
```

Ví dụ web service chạy bằng `root` có thể tạo:

```text
WARNING
```

Reason:

```text
PRIVILEGED_SERVICE_OWNER
```

Không kết luận vulnerability chỉ từ điều kiện này.

---

# 7. LEVEL 4 — Service & Version

## 7.1 Service Fingerprinting

Nếu có thể xác định:

```text
port
→ protocol
→ service
→ version
```

ví dụ:

```text
3306
→ MySQL
→ version X
```

thì risk engine có thêm evidence.

---

## 7.2 Version Vulnerability

Bước tiếp theo:

```text
service
+
version
↓
CVE lookup
↓
CVSS
↓
Risk
```

Ví dụ:

```text
Known critical vulnerability
→ DANGER / CRITICAL
```

Không cần tự xây CVE database ở phiên bản đầu. Có thể tích hợp nguồn vulnerability phù hợp sau.

---

# 8. LEVEL 5 — Exposure & Security Posture

## 8.1 Authentication

Phân biệt:

```text
authentication required
anonymous access
unknown
```

Ví dụ:

```text
Public + anonymous sensitive service
→ DANGER
```

---

## 8.2 Encryption

Đánh giá:

```text
TLS supported?
Plaintext?
Weak/legacy protocol?
```

Ví dụ:

```text
Sensitive HTTP-only service
→ WARNING/DANGER
```

---

## 8.3 Admin Interface

Nếu HTTP service có dấu hiệu là management/admin interface:

```text
public exposure + admin interface
→ DANGER/WARNING
```

Không cần đăng nhập hoặc brute-force.

---

# 9. LEVEL 6 — Enterprise Context

Các rule sau chỉ nên triển khai khi core scanner đã ổn định.

## 9.1 Asset Criticality

Mỗi asset có thể có:

```text
LOW
MEDIUM
HIGH
CRITICAL
```

Cùng một service nhưng asset khác nhau có risk khác nhau.

Ví dụ:

```text
3306 + development
→ WARNING
```

```text
3306 + production database
→ DANGER
```

---

## 9.2 Network Context

Phân biệt:

```text
localhost
LAN
VPN
internal subnet
Internet-facing
```

Risk tăng theo mức exposure.

---

## 9.3 Attack Surface Score

Không chỉ đánh giá từng port, mà đánh giá tổng thể asset.

Ví dụ:

```text
0–2 exposed services → LOW
3–5 → MEDIUM
6+ → HIGH
```

Đây là score hỗ trợ, không thay thế finding cụ thể.

---

# 10. Rule Evaluation Order

Nên triển khai rule theo thứ tự:

```text
1. Risky Port
2. Critical / Highly Sensitive Service Exposure
3. Known Vulnerable Service
4. Suspicious Process
5. Service/Port Mismatch
6. Sensitive Service Exposure
7. All Interfaces
8. Process Identification Failure
9. Other warnings
10. SAFE
```

Pseudo-code:

```text
if risky_port:
    DANGER

elif critical_service_exposure:
    DANGER

elif known_critical_vulnerability:
    CRITICAL

elif suspicious_process:
    WARNING

elif service_port_mismatch:
    WARNING

elif sensitive_service_exposed:
    DANGER

elif listener_is_all_interfaces:
    WARNING

elif process_unknown:
    WARNING

else:
    SAFE
```

Khi hệ thống có `CRITICAL`, nên ưu tiên:

```text
CRITICAL > DANGER > WARNING > SAFE
```

---

# 11. Finding Data Model

Không nên lưu chỉ:

```text
port
status
```

Nên lưu:

```json
{
  "port": 3306,
  "protocol": "TCP",
  "listener": "0.0.0.0",
  "process": "mysqld",
  "status": "DANGER",
  "reasons": [
    "DATABASE_EXPOSED_ON_ALL_INTERFACES"
  ]
}
```

Ví dụ risky port:

```json
{
  "port": 4444,
  "protocol": "TCP",
  "listener": "0.0.0.0",
  "process": null,
  "status": "DANGER",
  "reasons": [
    "PORT_IN_RISKY_LIST",
    "LISTENING_ON_ALL_INTERFACES",
    "PROCESS_IDENTIFICATION_FAILED"
  ]
}
```

Ví dụ safe:

```json
{
  "port": 8080,
  "protocol": "TCP",
  "listener": "127.0.0.1",
  "process": "myapp",
  "status": "SAFE",
  "reasons": []
}
```

---

# 12. Reason Codes

Nên chuẩn hóa reason code ngay từ đầu.

| Code | Ý nghĩa | Level |
|---|---|---|
| `PORT_IN_RISKY_LIST` | Port nằm trong risky list | DANGER |
| `LISTENING_ON_ALL_INTERFACES` | Bind `0.0.0.0` hoặc `::` | WARNING |
| `PROCESS_IDENTIFICATION_FAILED` | Không đọc được process | WARNING |
| `UNKNOWN_PROCESS` | Không xác định được process | WARNING |
| `SERVICE_PORT_MISMATCH` | Service không phù hợp port | WARNING |
| `SENSITIVE_SERVICE_EXPOSED` | Service nhạy cảm đang exposed | WARNING/DANGER |
| `DATABASE_EXPOSED_ON_ALL_INTERFACES` | Database bind mọi interface | DANGER |
| `SUSPICIOUS_PROCESS` | Process có dấu hiệu bất thường | WARNING/DANGER |
| `UNEXPECTED_PROCESS_PATH` | Executable path bất thường | WARNING |
| `PRIVILEGED_SERVICE_OWNER` | Service chạy với quyền cao | WARNING |
| `KNOWN_VULNERABILITY` | Service/version có vulnerability | DANGER |
| `CRITICAL_VULNERABILITY` | Vulnerability nghiêm trọng | CRITICAL |
| `ADMIN_INTERFACE_EXPOSED` | Management interface exposed | DANGER/WARNING |
| `PLAINTEXT_SERVICE` | Service không mã hóa | WARNING |

---

# 13. Recommended Implementation Roadmap

## Phase 1 — Bắt buộc

Triển khai:

- Risky port
- Listener scope
- Process identification
- Process/service mismatch
- Reason codes
- Priority-based evaluation

**Mục tiêu:** thay thế `if/else` hiện tại nhưng không làm hệ thống quá phức tạp.

---

## Phase 2 — Khuyến nghị

Thêm:

- Service sensitivity
- Database detection
- `::` IPv6
- Process classification
- Process path
- Process owner

**Mục tiêu:** chuyển từ port scanner sang basic security exposure scanner.

---

## Phase 3 — Advanced

Thêm:

- Service fingerprint
- Version detection
- CVE/CVSS
- TLS analysis
- Authentication indicators
- Admin interface detection

**Mục tiêu:** vulnerability/exposure assessment.

---

## Phase 4 — Enterprise

Chỉ thực hiện khi cần:

- Asset criticality
- Network context
- Attack surface score
- Continuous monitoring
- Historical risk
- False-positive management
- Centralized dashboard
- Policy/compliance mapping
- SIEM integration

---

# 14. Khuyến nghị phạm vi cho sinh viên SE

Không nên cố triển khai toàn bộ Phase 1–4 cùng lúc.

### Mức tối thiểu tốt

```text
Risky Port
+
Listener Scope
+
Process Identification
+
Service/Port Mismatch
+
Reason Codes
```

### Mức tốt

```text
Mức tối thiểu
+
Service Sensitivity
+
Database Exposure
+
Process Path
+
Process Owner
```

### Mức rất tốt

```text
Mức tốt
+
Service Fingerprinting
+
Version Detection
+
CVE/CVSS
```

Enterprise features nên xem là **future roadmap**, không phải yêu cầu bắt buộc.

---

# 15. Nguyên tắc thiết kế cuối cùng

Module phải đi theo mô hình:

```text
DETECTION
    ↓
EVIDENCE
    ↓
RULE
    ↓
RISK LEVEL
    ↓
REASON
```

Không nên:

```text
PORT
 ↓
DANGER / SAFE
```

Ba nguyên tắc phải giữ:

1. **Port mở ≠ nguy hiểm.**
2. **`0.0.0.0` ≠ vulnerability; nó là exposure indicator.**
3. **Không xác định được process ≠ process độc hại.**

Mục tiêu của module là:

> **Phát hiện dấu hiệu rủi ro và cung cấp lý do có thể kiểm chứng, không tự khẳng định hệ thống đã bị tấn công.**
