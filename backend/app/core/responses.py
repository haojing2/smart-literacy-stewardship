from __future__ import annotations

from typing import Any
from uuid import uuid4


def success_response(data: Any) -> dict[str, Any]:
    return {
        "code": 0,
        "message": "success",
        "data": data,
        "requestId": str(uuid4()),
    }


def error_response(code: Any, message: str) -> dict[str, Any]:
    return {
        "code": code,
        "message": message,
        "data": None,
        "requestId": str(uuid4()),
    }
