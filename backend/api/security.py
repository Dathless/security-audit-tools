from __future__ import annotations

from fastapi import Header, HTTPException

from core.config import config


class ApiError(HTTPException):
    """Lỗi API bọc đúng envelope chuẩn: {'success': False, 'error': {code, message}}."""

    def __init__(self, code: str, message: str, status_code: int = 400) -> None:
        self.code = code
        super().__init__(status_code=status_code, detail={"code": code, "message": message})


def require_local_token(x_local_token: str | None = Header(default=None)) -> None:
    """Kiểm tra token nội bộ (chống localhost CSRF — mục 9 BACKEND.md).

    Bỏ qua khi config chưa bật require_local_token (dùng cho dev/test).
    """
    if not config.settings.app.require_local_token:
        return
    token = config.settings.app.local_token.strip()
    if not token:
        return
    incoming = (x_local_token or "").strip()
    if not incoming or incoming != token:
        raise ApiError(
            "INVALID_LOCAL_TOKEN",
            "Token nội bộ (X-Local-Token) không hợp lệ hoặc thiếu.",
            status_code=401,
        )