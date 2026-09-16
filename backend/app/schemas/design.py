from __future__ import annotations

from pydantic import BaseModel, Field


class BlankPatternCreateRequest(BaseModel):
    grid_width: int = Field(ge=1, le=500)
    grid_height: int = Field(ge=1, le=500)
    palette_id: str = Field(default="mard-291", min_length=2, max_length=64)
    bead_size_mm: float = Field(default=5.0, gt=0, le=20)
    waste_rate: float = Field(default=0.05, ge=0, le=1)


class TemplatePatternCreateRequest(BaseModel):
    template_id: str = Field(min_length=2, max_length=64)
    palette_id: str = Field(default="mard-291", min_length=2, max_length=64)
    foreground_code: str | None = Field(default=None, max_length=64)
    accent_code: str | None = Field(default=None, max_length=64)
    bead_size_mm: float = Field(default=5.0, gt=0, le=20)
    waste_rate: float = Field(default=0.05, ge=0, le=1)


class TextPatternCreateRequest(BaseModel):
    text: str = Field(min_length=1, max_length=14)
    style: str = Field(default="keychain", pattern=r"^(keychain|nameplate)$")
    palette_id: str = Field(default="mard-291", min_length=2, max_length=64)
    foreground_code: str | None = Field(default=None, max_length=64)
    accent_code: str | None = Field(default=None, max_length=64)
    bead_size_mm: float = Field(default=5.0, gt=0, le=20)
    waste_rate: float = Field(default=0.05, ge=0, le=1)


class AssemblyPlanRequest(BaseModel):
    board_width: int = Field(default=29, ge=4, le=120)
    board_height: int = Field(default=29, ge=4, le=120)
    overlap: int = Field(default=0, ge=0, le=12)
