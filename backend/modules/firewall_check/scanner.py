from __future__ import annotations

import asyncio
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, StrictBool, ValidationError, field_validator

from core.scanner_base import ProgressCallback, ScanError, ScanResult, ScanResultItem, ScannerBase

ProfileName = Literal["Domain", "Private", "Public"]
Action = Literal["Allow", "Block", "NotConfigured"]


class FirewallProfile(BaseModel):
    name: ProfileName
    enabled: StrictBool
    default_inbound_action: Action
    default_outbound_action: Action


class FirewallRule(BaseModel):
    name: str = Field(min_length=1)
    display_name: str
    profiles: list[Literal["Domain", "Private", "Public", "Any"]] = Field(min_length=1)
    direction: Literal["Inbound", "Outbound"]
    action: Literal["Allow", "Block"]
    protocol: str = Field(min_length=1)
    local_ports: list[str] = Field(min_length=1)
    remote_ports: list[str] = Field(min_length=1)
    local_addresses: list[str] = Field(min_length=1)
    remote_addresses: list[str] = Field(min_length=1)
    program: str = Field(min_length=1)
    service: str = Field(min_length=1)
    policy_source: str


class FirewallSnapshot(BaseModel):
    profiles: list[FirewallProfile]
    active_profiles: list[ProfileName]
    rules: list[FirewallRule]

    @field_validator("profiles", "active_profiles", "rules", mode="before")
    @classmethod
    def singleton_to_list(cls, value):
        return [value] if isinstance(value, (dict, str)) else value


GUIDANCE = {
    "FIREWALL_DISABLED": "Mở Windows Security → Firewall & network protection và kiểm tra việc bật firewall cho profile này.",
    "DEFAULT_INBOUND_ALLOW": "Mở Windows Defender Firewall with Advanced Security → Properties và xem lại chính sách Inbound connections.",
    "POLICY_UNDETERMINED": "Kiểm tra chính sách hiệu lực trong Windows Firewall hoặc Group Policy; chưa đủ dữ liệu để kết luận.",
    "BROAD_INBOUND_ALLOW": "Tìm rule theo tên trong Windows Firewall → Inbound Rules; xem lại Profiles, Scope, Protocols and Ports, chương trình và dịch vụ trước khi sửa.",
}


class FirewallCheckModule(ScannerBase):
    module_id = "firewall-check"
    display_name = "Firewall Check"

    async def run(self, progress_cb: ProgressCallback | None = None) -> ScanResult:
        started_at = datetime.utcnow()
        if progress_cb:
            await progress_cb(0, 1, "Đang đọc cấu hình Windows Firewall…")
        snapshot = await asyncio.to_thread(self._collect)
        items = []
        for profile in snapshot.profiles:
            detail = profile.model_dump()
            detail.update(kind="profile", active=profile.name in snapshot.active_profiles)
            reasons = []
            if not profile.enabled:
                reasons.append("FIREWALL_DISABLED")
            if profile.default_inbound_action == "Allow":
                reasons.append("DEFAULT_INBOUND_ALLOW")
            if "NotConfigured" in (profile.default_inbound_action, profile.default_outbound_action):
                reasons.append("POLICY_UNDETERMINED")
            severity = "safe"
            if reasons:
                severity = "danger" if detail["active"] and any(r != "POLICY_UNDETERMINED" for r in reasons) else "warning"
            items.append(self._item(profile.name, detail, severity, reasons))

        for rule in snapshot.rules:
            detail = rule.model_dump()
            detail["kind"] = "rule"
            broad = (
                rule.direction == "Inbound" and rule.action == "Allow"
                and bool({"Any", "Public"} & set(rule.profiles))
                and rule.protocol.lower() in {"tcp", "udp", "any", "6", "17", "256"}
                and bool({"Any", "*", "0-65535", "1-65535"} & set(rule.local_ports))
                and bool({"Any", "*", "0.0.0.0/0", "::/0", "0.0.0.0-255.255.255.255"} & set(rule.remote_addresses))
            )
            items.append(self._item(rule.display_name or rule.name, detail, "warning" if broad else "safe", ["BROAD_INBOUND_ALLOW"] if broad else []))

        summary = {"total_profiles": len(snapshot.profiles), "total_rules": len(snapshot.rules), "danger": 0, "warning": 0, "safe": 0}
        for index, item in enumerate(items, 1):
            summary[item.severity] += 1
            if progress_cb:
                await progress_cb(index, len(items), f"Đang đánh giá {item.title}…")
        return ScanResult(
            module_id=self.module_id,
            started_at=started_at.strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
            finished_at=datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
            items=items, summary=summary,
        )

    @staticmethod
    def _item(title: str, detail: dict, severity: str, reasons: list[str]) -> ScanResultItem:
        detail["reasons"] = reasons
        detail["guidance"] = [GUIDANCE[reason] for reason in reasons]
        return ScanResultItem(title=title, severity=severity, detail=detail)

    @staticmethod
    def _collect() -> FirewallSnapshot:
        if sys.platform != "win32":
            raise ScanError("UNSUPPORTED_PLATFORM", "Firewall Check chỉ hỗ trợ Windows.")
        try:
            result = subprocess.run(
                ["powershell.exe", "-NoProfile", "-NonInteractive", "-WindowStyle", "Hidden", "-Command", Path(__file__).with_name("collect.ps1").read_text(encoding="utf-8")],
                capture_output=True, text=True, encoding="utf-8", check=True, timeout=60,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
        except subprocess.TimeoutExpired as exc:
            raise ScanError("FIREWALL_TIMEOUT", "Đọc Windows Firewall quá 60 giây. Hãy thử lại.") from exc
        except PermissionError as exc:
            raise ScanError("SCAN_PERMISSION_DENIED", "Không có quyền đọc Windows Firewall. Hãy thử chạy backend với quyền Administrator.") from exc
        except FileNotFoundError as exc:
            raise ScanError("FIREWALL_UNAVAILABLE", "Không tìm thấy Windows PowerShell.") from exc
        except subprocess.CalledProcessError as exc:
            error = exc.stderr or ""
            if "FIREWALL_PERMISSION_DENIED" in error:
                raise ScanError("SCAN_PERMISSION_DENIED", "Không có quyền đọc Windows Firewall. Hãy thử chạy backend với quyền Administrator.") from exc
            if "FIREWALL_UNAVAILABLE" in error:
                raise ScanError("FIREWALL_UNAVAILABLE", "Windows thiếu các lệnh NetSecurity cần thiết.") from exc
            raise ScanError("FIREWALL_QUERY_FAILED", "Không đọc được đầy đủ Windows Firewall. Kiểm tra quyền, dịch vụ firewall và thử lại.") from exc
        try:
            snapshot = FirewallSnapshot.model_validate(json.loads(result.stdout.lstrip("\ufeff")))
            if len(snapshot.profiles) != 3 or {p.name for p in snapshot.profiles} != {"Domain", "Private", "Public"}:
                raise ValueError("Incomplete profiles")
            if len({r.name for r in snapshot.rules}) != len(snapshot.rules):
                raise ValueError("Duplicate rule IDs")
            return snapshot
        except (ValidationError, ValueError, TypeError) as exc:
            raise ScanError("FIREWALL_INVALID_DATA", "Dữ liệu Windows Firewall không đầy đủ hoặc không hợp lệ. Hãy thử lại.") from exc

    def get_whitelist_key(self, item: ScanResultItem) -> str:
        return f"{item.detail['kind']}:{item.detail['name']}"
