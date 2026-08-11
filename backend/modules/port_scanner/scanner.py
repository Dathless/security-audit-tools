from __future__ import annotations

import asyncio
import json
import logging
import shutil
import socket
from datetime import datetime

import psutil

from core.config import config
from core.scanner_base import ProgressCallback, ScanResult, ScanResultItem, ScannerBase
from storage.db import db

logger = logging.getLogger(__name__)

ANY_IP = {"0.0.0.0", "::"}


class PortScannerModule(ScannerBase):
    module_id = "port-scanner"
    display_name = "Port Scanner"

    def __init__(self) -> None:
        settings = config.module("port-scanner")
        self.scan_mode = str(settings.get("scan_mode", "socket"))
        self.known_risky_ports = {
            int(p) for p in (settings.get("known_risky_ports", []) or [4444, 1337, 31337])
        }

    async def run(self, progress_cb: ProgressCallback | None = None) -> ScanResult:
        started_at = datetime.utcnow()

        entries = await self._collect(progress_cb)

        items: list[ScanResultItem] = []
        total = len(entries) or 1
        for idx, entry in enumerate(entries, start=1):
            severity, note = self._classify(entry)
            detail = {
                "port": entry["port"],
                "ip": entry["ip"],
                "pid": entry["pid"],
                "process_name": entry["process_name"],
                "protocol": entry["protocol"],
                "note": note,
                "permission_denied": entry["permission_denied"],
            }
            items.append(
                ScanResultItem(
                    severity=severity,
                    title=f"Port {entry['port']}",
                    detail=detail,
                )
            )
            if progress_cb:
                await progress_cb(idx, total, f"Đang kiểm tra cổng {entry['port']}...")

        finished_at = datetime.utcnow()
        summary = _build_summary(items)
        partial_result = any(e["permission_denied"] for e in entries)

        self._record_config()
        logger.info(
            "Port scanner: mode=%s ports=%d (danger=%d warning=%d safe=%d)",
            self.scan_mode,
            len(items),
            summary["danger"],
            summary["warning"],
            summary["safe"],
        )

        return ScanResult(
            module_id=self.module_id,
            started_at=started_at.strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
            finished_at=finished_at.strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
            items=items,
            summary=summary,
            partial_result=partial_result,
        )

    # ------------------------------------------------------------------ collect
    async def _collect(self, progress_cb) -> list[dict]:
        if self.scan_mode == "nmap" and shutil.which("nmap"):
            try:
                return await asyncio.to_thread(self._scan_nmap)
            except Exception:  # noqa: BLE001
                logger.exception("Nmap quét lỗi — fallback về chế độ socket")
        if progress_cb:
            await progress_cb(0, 1, "Đang đọc danh sách kết nối (chế độ socket)...")
        try:
            return await asyncio.to_thread(self._scan_socket)
        except (psutil.AccessDenied, PermissionError):
            logger.warning("Thiếu quyền đọc danh sách kết nối — trả kết quả rỗng kèm cảnh báo")
            return [
                {
                    "port": 0,
                    "ip": "",
                    "pid": None,
                    "process_name": "",
                    "protocol": "",
                    "permission_denied": True,
                }
            ]

    def _scan_socket(self) -> list[dict]:
        conns = psutil.net_connections(kind="inet")
        entries: list[dict] = []
        for conn in conns:
            if not conn.laddr:
                continue
            is_udp = conn.type == socket.SOCK_DGRAM
            if not is_udp and conn.status != psutil.CONN_LISTEN:
                continue
            ip, port = conn.laddr
            process_name, denied = self._process_name(conn.pid)
            protocol = "udp" if is_udp else "tcp"
            entries.append(
                {
                    "port": int(port),
                    "ip": ip,
                    "pid": conn.pid,
                    "process_name": process_name,
                    "protocol": protocol,
                    "permission_denied": denied,
                }
            )
        entries.sort(key=lambda e: e["port"])
        return entries

    def _scan_nmap(self) -> list[dict]:
        import nmap

        host = "127.0.0.1"
        ports = _nmap_ports(self.known_risky_ports)
        scanner = nmap.PortScanner()
        scanner.scan(hosts=host, ports=ports, arguments="-sT -Pn --open -T4")
        host_data = scanner["scan"].get(host, {}) or {}
        entries: list[dict] = []
        for port_str, info in host_data.get("tcp", {}).items():
            if info.get("state") != "open":
                continue
            entries.append(
                {
                    "port": int(port_str),
                    "ip": host,
                    "pid": None,
                    "process_name": "",
                    "protocol": "tcp",
                    "permission_denied": False,
                }
            )
        return entries

    @staticmethod
    def _process_name(pid: int | None) -> tuple[str, bool]:
        if not pid:
            return "", False
        try:
            return psutil.Process(pid).name(), False
        except (psutil.AccessDenied, PermissionError):
            return "", True
        except (psutil.NoSuchProcess, psutil.ZombieProcess):
            return "", False

    # ----------------------------------------------------------------- classify
    def _classify(self, entry: dict) -> tuple[str, str]:
        port = entry["port"]
        if port in self.known_risky_ports:
            return "danger", "Nằm trong danh sách cổng rủi ro đã biết"
        if entry["ip"] in ANY_IP:
            return "warning", "Đang lắng nghe trên mọi giao diện (0.0.0.0/::)"
        if entry["permission_denied"]:
            return "warning", "Cần quyền Administrator để lấy tên tiến trình"
        return "safe", "Port mở thông thường (loopback/nội bộ)"

    # ----------------------------------------------------------------- snapshot
    def _record_config(self) -> None:
        from .models import PortScannerConfig

        with db.session() as s:
            row = s.get(PortScannerConfig, self.module_id)
            if row is None:
                row = PortScannerConfig(id=self.module_id, scan_mode=self.scan_mode)
            row.scan_mode = self.scan_mode
            row.known_risky_ports_json = json.dumps(sorted(self.known_risky_ports))
            s.add(row)
            s.commit()

    def get_whitelist_key(self, item: ScanResultItem) -> str:
        detail = item.detail
        port = detail.get("port")
        process_name = detail.get("process_name") or ""
        if process_name:
            return f"{port}:{process_name}"
        return str(port)


def _nmap_ports(risky: set[int]) -> str:
    ranges = "1-1024"
    extra = [p for p in risky if p > 1024]
    if extra:
        return f"{ranges},{','.join(str(p) for p in sorted(extra))}"
    return ranges


def _build_summary(items: list[ScanResultItem]) -> dict:
    counter = {"danger": 0, "warning": 0, "safe": 0}
    for item in items:
        counter[item.severity] = counter.get(item.severity, 0) + 1
    return {
        "total_open": len(items),
        "danger": counter["danger"],
        "warning": counter["warning"],
        "safe": counter["safe"],
    }