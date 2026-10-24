from __future__ import annotations

import asyncio
import ipaddress
import json
import logging
import socket
from datetime import datetime
from time import perf_counter

import psutil

from core.config import config
from core.scanner_base import ProgressCallback, ScanError, ScanResult, ScanResultItem, ScannerBase
from storage.db import db
from .evidence import ASSESSMENT_VERSION, IDENTITY_VERSION, complete_identity, endpoint_key

logger = logging.getLogger(__name__)
ANY_IP = {"0.0.0.0", "::"}
REASON_NOTES = {
    "PORT_IN_RISKY_LIST": "Cổng nằm trong danh sách cần chú ý; không phải bằng chứng malware",
    "LISTENING_ON_ALL_INTERFACES": "Bind trên mọi giao diện; chưa xác minh khả năng truy cập từ mạng",
    "NON_LOOPBACK_BIND": "Bind ngoài loopback; cần xem xét phạm vi sử dụng",
    "PROCESS_IDENTITY_UNKNOWN": "Chưa xác định đầy đủ executable/chủ sở hữu tiến trình",
}
GUIDANCE = {
    "PORT_IN_RISKY_LIST": "Đối chiếu ứng dụng và nhu cầu sử dụng cổng này.",
    "LISTENING_ON_ALL_INTERFACES": "Kiểm tra cấu hình bind và chính sách firewall bằng công cụ phù hợp.",
    "NON_LOOPBACK_BIND": "Xác nhận ứng dụng có cần bind vào địa chỉ này hay không.",
    "PROCESS_IDENTITY_UNKNOWN": "Kiểm tra quyền đọc hoặc quét lại nếu tiến trình đã thoát; không tự nâng quyền.",
}


class PortScannerModule(ScannerBase):
    module_id = "port-scanner"
    display_name = "Port Scanner"

    def __init__(self) -> None:
        settings = config.module(self.module_id)
        self.scan_mode = "socket"
        if settings.get("scan_mode") == "nmap":
            logger.warning("scan_mode=nmap đã ngừng hỗ trợ; chuyển sang psutil (socket).")
        ports = settings.get("known_risky_ports", [4444, 1337, 31337])
        if not isinstance(ports, list) or any(type(port) is not int or not 1 <= port <= 65535 for port in ports):
            raise ScanError("SCAN_CONFIG_INVALID", "known_risky_ports phải là danh sách số nguyên từ 1 đến 65535.")
        self.known_risky_ports = set(ports)
        self._inventory_partial = False
        self._timings: dict = {}

    async def run(self, progress_cb: ProgressCallback | None = None) -> ScanResult:
        started_at = datetime.utcnow()
        entries = await self._collect(progress_cb)
        items = []
        for index, entry in enumerate(entries, 1):
            severity, reasons = self._classify(entry)
            detail = dict(entry)
            detail.update(identity_version=IDENTITY_VERSION, assessment_version=ASSESSMENT_VERSION,
                          ip=entry["listener"], reasons=reasons,
                          note=REASON_NOTES[reasons[0]] if reasons else "Không phát hiện theo tiêu chí hiện tại",
                          guidance=[GUIDANCE[reason] for reason in reasons])
            items.append(ScanResultItem(severity=severity, title=f"{entry['protocol'].upper()} {entry['listener']}:{entry['port']}", detail=detail))
            if progress_cb and (index == 1 or index % 50 == 0 or index == len(entries)):
                await progress_cb(index, len(entries), f"Đang đánh giá endpoint {index}/{len(entries)}…")
        summary = _build_summary(items)
        summary.update(identity_version=IDENTITY_VERSION, assessment_version=ASSESSMENT_VERSION, **self._timings)
        self._record_config()
        return ScanResult(module_id=self.module_id, started_at=started_at.isoformat() + "Z",
                          finished_at=datetime.utcnow().isoformat() + "Z", items=items,
                          summary=summary, partial_result=self._inventory_partial)

    async def _collect(self, progress_cb) -> list[dict]:
        if progress_cb:
            await progress_cb(0, 1, "Đang đọc inventory TCP LISTEN và UDP bind…")
        try:
            return await asyncio.to_thread(self._scan_socket)
        except (psutil.AccessDenied, PermissionError) as exc:
            raise ScanError("SCAN_PERMISSION_DENIED", "Không có quyền đọc inventory socket; không tạo kết quả cổng giả.") from exc

    def _scan_socket(self) -> list[dict]:
        started = perf_counter()
        conns = psutil.net_connections(kind="inet")
        inventory_done = perf_counter()
        cache: dict[int | None, dict] = {}
        endpoints: dict[str, dict] = {}
        self._inventory_partial = False
        for conn in conns:
            if conn.type not in (socket.SOCK_STREAM, socket.SOCK_DGRAM):
                continue
            if conn.type == socket.SOCK_STREAM and conn.status != psutil.CONN_LISTEN:
                continue
            if not conn.laddr:
                self._inventory_partial = True
                continue
            try:
                address, port = conn.laddr
                parsed = ipaddress.ip_address(address)
                if conn.family not in (socket.AF_INET, socket.AF_INET6) or parsed.version != (4 if conn.family == socket.AF_INET else 6):
                    raise ValueError("family/address mismatch")
                if type(port) is not int or not 1 <= port <= 65535:
                    raise ValueError("invalid port")
            except (ValueError, TypeError):
                self._inventory_partial = True
                continue
            if conn.pid not in cache:
                cache[conn.pid] = self._process_metadata(conn.pid)
            owner = cache[conn.pid]
            detail = {"protocol": "udp" if conn.type == socket.SOCK_DGRAM else "tcp",
                      "family": f"ipv{parsed.version}", "listener": str(parsed), "port": port,
                      "socket_status": "bound" if conn.type == socket.SOCK_DGRAM else "listening",
                      "exposure": "wildcard" if parsed.is_unspecified else "loopback" if parsed.is_loopback else "specific",
                      "owners": []}
            key = endpoint_key(detail)
            entry = endpoints.setdefault(key, detail)
            if owner not in entry["owners"]:
                entry["owners"].append(owner)
        for entry in endpoints.values():
            entry["owners"].sort(key=lambda owner: (owner["pid"] is None, owner["pid"] or 0))
            first = entry["owners"][0]
            entry.update(pid=first["pid"], process_name=first["name"] or "",
                         permission_denied=any("access_denied" in owner["status"].values() for owner in entry["owners"]))
        self._timings = {"inventory_ms": round((inventory_done - started) * 1000, 3),
                         "metadata_ms": round((perf_counter() - inventory_done) * 1000, 3)}
        return sorted(endpoints.values(), key=lambda entry: (entry["port"], entry["protocol"], entry["family"], entry["listener"]))

    @staticmethod
    def _process_metadata(pid: int | None) -> dict:
        owner = {"pid": pid, "name": None, "exe": None, "username": None, "create_time": None, "status": {}}
        fields = ("name", "exe", "username", "create_time")
        try:
            if pid is None:
                raise psutil.NoSuchProcess(-1)
            process = psutil.Process(pid)
            with process.oneshot():
                for field in fields:
                    try:
                        value = getattr(process, field)()
                        owner[field] = value
                        owner["status"][field] = "ok" if value is not None and value != "" else "unknown"
                    except (psutil.AccessDenied, PermissionError):
                        owner["status"][field] = "access_denied"
                    except (psutil.NoSuchProcess, psutil.ZombieProcess):
                        owner["status"][field] = "gone"
        except (psutil.AccessDenied, PermissionError):
            owner["status"] = dict.fromkeys(fields, "access_denied")
        except (psutil.NoSuchProcess, psutil.ZombieProcess):
            owner["status"] = dict.fromkeys(fields, "unknown" if pid is None else "gone")
        return owner

    @staticmethod
    def _process_name(pid: int | None) -> tuple[str, bool]:
        owner = PortScannerModule._process_metadata(pid)
        return owner["name"] or "", "access_denied" in owner["status"].values()

    def _classify(self, entry: dict) -> tuple[str, list[str]]:
        address = ipaddress.ip_address(entry.get("listener", entry.get("ip")))
        risky = entry["port"] in self.known_risky_ports
        outside = not address.is_loopback
        reasons = []
        if risky:
            reasons.append("PORT_IN_RISKY_LIST")
        if outside:
            reasons.append("LISTENING_ON_ALL_INTERFACES" if address.is_unspecified else "NON_LOOPBACK_BIND")
        if not complete_identity(entry):
            reasons.append("PROCESS_IDENTITY_UNKNOWN")
        return "danger" if risky and outside else "warning" if reasons else "safe", reasons

    def _record_config(self) -> None:
        from .models import PortScannerConfig
        with db.session() as session:
            row = session.get(PortScannerConfig, self.module_id) or PortScannerConfig(id=self.module_id, scan_mode=self.scan_mode)
            row.scan_mode = self.scan_mode
            row.known_risky_ports_json = json.dumps(sorted(self.known_risky_ports))
            row.updated_at = datetime.utcnow()
            session.add(row)
            session.commit()

    def get_whitelist_key(self, item: ScanResultItem) -> str:
        return endpoint_key(item.detail)

    def on_persist(self, session, scan_id, result, previous) -> None:
        from .reviews import persist_snapshot
        persist_snapshot(session, scan_id, result, previous)


def _build_summary(items: list[ScanResultItem]) -> dict:
    summary = {"total_open": len(items), "total_endpoints": len(items), "danger": 0, "warning": 0, "safe": 0,
               "unique_ports": len({item.detail.get("port") for item in items}),
               "unique_processes": len({(owner["pid"], owner.get("create_time")) for item in items for owner in item.detail.get("owners", []) if owner["pid"] is not None}),
               "tcp_listeners": sum(item.detail.get("protocol") == "tcp" for item in items),
               "udp_bindings": sum(item.detail.get("protocol") == "udp" for item in items),
               "metadata_incomplete_count": sum(not complete_identity(item.detail) for item in items)}
    for item in items:
        summary[item.severity] += 1
    return summary
