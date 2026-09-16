from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class ApiEnvelope(BaseModel):
    success: bool = True
    data: Any = None
    message: str | None = None
    code: str | None = None


def success(data: Any = None, message: str | None = None) -> dict[str, Any]:
    return {"success": True, "data": data, "message": message, "code": None}
