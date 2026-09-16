from __future__ import annotations

from pydantic import BaseModel, Field


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=2_000)
    pattern_id: str | None = Field(default=None, min_length=4, max_length=80)
    editor_settings: dict[str, object] = Field(default_factory=dict)


class ProjectUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=2_000)
    pattern_id: str | None = Field(default=None, min_length=4, max_length=80)
    editor_settings: dict[str, object] | None = None
