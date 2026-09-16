from __future__ import annotations

import math
from datetime import date
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator


class PaletteCalibration(BaseModel):
    """Provenance for physical CIELAB measurements used by the matcher.

    Image colours are converted to CIELAB with a D65 white point and the 2°
    standard observer. Accepting a different reference without chromatic
    adaptation would make the resulting Delta E values look precise while being
    scientifically incomparable, so stage four deliberately supports this one
    reference condition first.
    """

    color_space: Literal["CIELAB"] = "CIELAB"
    illuminant: Literal["D65"] = "D65"
    observer: Literal["2_degree"] = "2_degree"
    source: str = Field(min_length=1, max_length=200)
    instrument: str | None = Field(default=None, max_length=120)
    measurement_geometry: str | None = Field(default=None, max_length=80)
    measured_at: date | None = None
    notes: str | None = Field(default=None, max_length=500)


class PaletteColor(BaseModel):
    code: str = Field(min_length=1, max_length=64)
    name_zh: str = Field(min_length=1, max_length=100)
    name_en: str | None = Field(default=None, max_length=100)
    hex: str = Field(pattern=r"^#[0-9A-Fa-f]{6}$")
    rgb: list[int] = Field(min_length=3, max_length=3)
    measured_lab: list[float] | None = Field(default=None, min_length=3, max_length=3)
    category: str | None = Field(default=None, max_length=64)
    available: bool = True

    @field_validator("rgb")
    @classmethod
    def rgb_range(cls, value: list[int]) -> list[int]:
        if any(component < 0 or component > 255 for component in value):
            raise ValueError("rgb 分量必须在 0 到 255 之间")
        return value

    @field_validator("measured_lab")
    @classmethod
    def measured_lab_range(cls, value: list[float] | None) -> list[float] | None:
        if value is None:
            return value
        if not all(math.isfinite(component) for component in value):
            raise ValueError("实体 LAB 分量必须是有限数值")
        lightness, a_axis, b_axis = value
        if not 0 <= lightness <= 100:
            raise ValueError("实体 LAB 的 L* 必须在 0 到 100 之间")
        if not -160 <= a_axis <= 160 or not -160 <= b_axis <= 160:
            raise ValueError("实体 LAB 的 a*、b* 必须在 -160 到 160 之间")
        return value


class PaletteCreate(BaseModel):
    id: str = Field(pattern=r"^[a-z0-9][a-z0-9_-]{1,62}$")
    name: str = Field(min_length=1, max_length=100)
    brand: str = Field(min_length=1, max_length=100)
    calibration: PaletteCalibration | None = None
    colors: list[PaletteColor] = Field(min_length=1, max_length=500)

    @model_validator(mode="after")
    def calibration_matches_measurements(self) -> PaletteCreate:
        has_measurements = any(color.measured_lab is not None for color in self.colors)
        if has_measurements and self.calibration is None:
            raise ValueError("包含实体 LAB 的色卡必须提供 calibration 测量来源")
        if self.calibration is not None and not has_measurements:
            raise ValueError("calibration 需要至少一个带 measured_lab 的色号")
        return self


class PaletteUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    brand: str | None = Field(default=None, min_length=1, max_length=100)
    calibration: PaletteCalibration | None = None
    colors: list[PaletteColor] | None = Field(default=None, min_length=1, max_length=500)
