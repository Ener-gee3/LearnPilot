from typing import Any


def ok(data: Any, message: str = "ok") -> dict:
    return {"success": True, "message": message, "data": data, "error": None}


def err(code: str, message: str, details: Any = None) -> dict:
    return {"success": False, "message": message, "data": None, "error": {"code": code, "details": details}}
