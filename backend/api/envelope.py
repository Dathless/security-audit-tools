from __future__ import annotations

from typing import Any

from fastapi.encoders import jsonable_encoder


def ok(data: Any = None) -> dict:
    return {"success": True, "data": jsonable_encoder(data), "error": None}


def fail(code: str, message: str) -> dict:
    return {"success": False, "data": None, "error": {"code": code, "message": message}}