from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Awaitable, Callable, Optional

from pydantic import BaseModel, Field

ProgressCallback = Callable[[int, int, str], Awaitable[None]]


class ScanResultItem(BaseModel):
    """1 dòng kết quả — module tự định nghĩa schema con kế thừa từ đây."""

    severity: str
    title: str
    detail: dict = Field(default_factory=dict)


class ScanResult(BaseModel):
    module_id: str
    started_at: str
    finished_at: str
    items: list[ScanResultItem] = Field(default_factory=list)
    summary: dict = Field(default_factory=dict)
    partial_result: bool = False


class ScanError(Exception):
    """Lỗi có mã lỗi chuẩn, được executor bọc lại thành envelope.

    code khớp với error.code trả ra cho frontend (vd: SCAN_PERMISSION_DENIED).
    """

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class ScannerBase(ABC):
    module_id: str = ""
    display_name: str = ""

    @abstractmethod
    async def run(self, progress_cb: Optional[ProgressCallback] = None) -> ScanResult:
        """progress_cb(current, total, message): đẩy tiến trình qua WebSocket."""
        raise NotImplementedError

    def get_whitelist_key(self, item: ScanResultItem) -> str:
        raise NotImplementedError

    def on_persist(self, session, scan_id: str, result: ScanResult, previous) -> None:
        """Module-owned changes committed atomically with the scan snapshot."""
