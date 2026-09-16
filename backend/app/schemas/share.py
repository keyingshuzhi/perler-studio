from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field


class VersionCreateRequest(BaseModel):
    label: str | None = Field(default=None, max_length=120)
    automatic: bool = False


class ShareCreateRequest(BaseModel):
    title: str | None = Field(default=None, max_length=120)


class ConfirmationDecision(StrEnum):
    approved = "approved"
    changes_requested = "changes_requested"


class ShareConfirmationRequest(BaseModel):
    decision: ConfirmationDecision
    comment: str | None = Field(default=None, max_length=2_000)


class ShareCommentRequest(BaseModel):
    """A client comment attached to an optional zero-based grid cell."""

    message: str = Field(min_length=1, max_length=2_000)
    cell_index: int | None = Field(default=None, ge=0)
