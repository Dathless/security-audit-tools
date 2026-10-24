from __future__ import annotations

import asyncio
import json
import logging
import socket
from datetime import datetime

import psutil

from core.config import config
from core.scanner_base import ProgressCallback, ScanResult, ScanResultItem, ScannerBase
from storage.db import db

logger = logging.getLogger(__name__)

ANY_IP = {"0.0.0.0", "::"}

REASON_NOTES = {
    "PORT_IN_RISKY_LIST": "Nằm trong danh sách cổng rủi ro đã biết",
    "LISTENING_ON_ALL_INTERFACES": "Đang lắng nghe trên mọi giao diện (0.0.0.0/::)",
    "PROCESS_IDENTIFICATION_FAILED": "Cần quyền Administrator để lấy tên tiến trình",
}


class PortScannerModule(ScannerBase):
    module_id = "port-scanner"
    display_name = "Port Scanner"

    def __init__(self) -> None:
        settings = config.module("port-scanner")
        self.scan_mode = "socket"
        if settings.get("scan_mode") == "nmap":
            logger.warning("scan_mode=nmap đã ngừng hỗ trợ; chuyển sang psutil (socket).")
        self.known_risky_ports = {
            int(p) for p in (settings.get("known_risky_ports", []) or [4444, 1337, 31337])
        }

    async def run(self, progress_cb: ProgressCallback | None = None) -> ScanResult:
        started_at = datetime.utcnow()

        entries = await self._collect(progress_cb)

        items: list[ScanResultItem] = []
        total = len(entries) or 1
        for idx, entry in enumerate(entries, start=1):
            severity, reasons = self._classify(entry)
            detail = {
                "port": entry["port"],
                "listener": entry["ip"],
                "ip": entry["ip"],
                "pid": entry["pid"],
                "process_name": entry["process_name"],
                "protocol": entry["protocol"],
                "reasons": reasons,
                # Preserve the pre-reason-code API fields for existing clients.
                "note": REASON_NOTES[reasons[0]] if reasons else "Port mở thông thường (loopback/nội bộ)",
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
    def _classify(self, entry: dict) -> tuple[str, list[str]]:
        """Evaluate risky ports, listener scope and process metadata permissions."""
        reasons: list[str] = []
        port = entry["port"]

        # Rule 4.1 — Risky Port
        if port in self.known_risky_ports:
            reasons.append("PORT_IN_RISKY_LIST")
            return "danger", reasons

        # Rule 4.2 — Listener Scope
        if entry["ip"] in ANY_IP:
            reasons.append("LISTENING_ON_ALL_INTERFACES")
            return "warning", reasons

        # Rule 4.3 — Process Identification
        if entry["permission_denied"]:
            reasons.append("PROCESS_IDENTIFICATION_FAILED")
            return "warning", reasons

        return "safe", reasons

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
