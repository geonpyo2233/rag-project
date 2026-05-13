from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def _timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def success_response(data: dict[str, Any]) -> dict[str, Any]:
    return {
        "success": True,
        "timestamp": _timestamp(),
        "data": data,
    }


def error_response(message: str, **extra: Any) -> dict[str, Any]:
    return {
        "success": False,
        "timestamp": _timestamp(),
        "message": message,
        **extra,
    }

