from __future__ import annotations

from typing import Any

from fastapi import HTTPException, status


class AppError(HTTPException):
    """An API-safe domain exception rendered by the global exception handler."""

    def __init__(self, status_code: int, code: str, message: str, data: Any = None) -> None:
        super().__init__(status_code=status_code, detail={"code": code, "message": message, "data": data})


def not_found(resource: str, resource_id: str) -> AppError:
    return AppError(status.HTTP_404_NOT_FOUND, f"{resource.upper()}_NOT_FOUND", f"{resource} 不存在: {resource_id}")


def validation_error(message: str, code: str = "VALIDATION_ERROR") -> AppError:
    return AppError(status.HTTP_422_UNPROCESSABLE_CONTENT, code, message)


def conflict(message: str, code: str = "REVISION_CONFLICT") -> AppError:
    return AppError(status.HTTP_409_CONFLICT, code, message)
