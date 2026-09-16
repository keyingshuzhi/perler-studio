from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field, model_validator


class ResizeMode(StrEnum):
    stretch = "stretch"
    contain = "contain"
    cover = "cover"
    pixel = "pixel"


class DistanceMethod(StrEnum):
    fidelity = "fidelity"
    rgb = "rgb"
    cie76 = "cie76"
    cie94 = "cie94"
    ciede2000 = "ciede2000"


class SamplingMode(StrEnum):
    adaptive = "adaptive"
    edge_aware = "edge_aware"
    smooth = "smooth"


class CleanupLevel(StrEnum):
    off = "off"
    light = "light"
    medium = "medium"


class InventoryMode(StrEnum):
    report = "report"
    only = "only"


class ConversionPreset(StrEnum):
    custom = "custom"
    portrait = "portrait"
    illustration = "illustration"
    pixel_art = "pixel_art"
    landscape = "landscape"


class DetailPriority(StrEnum):
    facial = "facial"
    text = "text"
    outline = "outline"


class InventoryItem(BaseModel):
    color_code: str = Field(min_length=1, max_length=64)
    quantity: int = Field(ge=0, le=1_000_000)


class PatternGenerateRequest(BaseModel):
    image_id: str = Field(min_length=4, max_length=80)
    grid_width: int = Field(ge=1, le=2_000)
    grid_height: int = Field(ge=1, le=2_000)
    resize_mode: ResizeMode = ResizeMode.contain
    sampling_mode: SamplingMode = SamplingMode.adaptive
    palette_id: str = "mard-291"
    distance_method: DistanceMethod = DistanceMethod.ciede2000
    max_colors: int | None = Field(default=None, ge=1, le=500)
    auto_color_limit: bool = True
    target_p95_delta_e_00: float = Field(default=6.0, ge=0.5, le=30)
    include_special_colors: bool = False
    minimum_color_count: int = Field(default=0, ge=0, le=100_000)
    cleanup_level: CleanupLevel = CleanupLevel.medium
    structure_aware: bool = True
    transparent_background: bool = True
    disabled_colors: list[str] = Field(default_factory=list, max_length=500)
    locked_colors: list[str] = Field(default_factory=list, max_length=500)
    inventory: list[InventoryItem] = Field(default_factory=list, max_length=500)
    inventory_mode: InventoryMode = InventoryMode.report
    bead_size_mm: float = Field(default=5.0, gt=0, le=20)
    waste_rate: float = Field(default=0.05, ge=0, le=1)
    conversion_preset: ConversionPreset = ConversionPreset.custom
    subject_crop: bool = False
    focus_x: float = Field(default=0.5, ge=0, le=1)
    focus_y: float = Field(default=0.5, ge=0, le=1)
    focus_zoom: float = Field(default=1.0, ge=1, le=3)
    focus_radius: float = Field(default=0.38, gt=0.05, le=1)
    background_weaken: float = Field(default=0.0, ge=0, le=1)
    detail_priorities: list[DetailPriority] = Field(default_factory=list, max_length=3)

    @model_validator(mode="after")
    def unique_color_rules(self) -> PatternGenerateRequest:
        overlap = set(self.disabled_colors) & set(self.locked_colors)
        if overlap:
            raise ValueError(f"色号不能同时禁用和锁定: {', '.join(sorted(overlap))}")
        inventory_codes = [item.color_code for item in self.inventory]
        if len(inventory_codes) != len(set(inventory_codes)):
            raise ValueError("库存中不能重复添加同一色号")
        if self.inventory_mode == InventoryMode.only and not any(item.quantity > 0 for item in self.inventory):
            raise ValueError("严格库存模式需要至少添加一种有库存的颜色")
        if len(self.detail_priorities) != len(set(self.detail_priorities)):
            raise ValueError("关键细节保护不能重复选择")
        return self


class CellChange(BaseModel):
    index: int = Field(ge=0)
    before: str | None = Field(default=None, max_length=64)
    after: str | None = Field(default=None, max_length=64)


class PatternPatchRequest(BaseModel):
    changes: list[CellChange] = Field(min_length=1, max_length=100_000)
    base_revision: int | None = Field(default=None, ge=1)


class PatternResponse(BaseModel):
    id: str
    revision: int
    image_id: str
    palette_id: str
    grid_width: int
    grid_height: int
    cells: list[str | None]
    settings: dict[str, object]
    statistics: dict[str, object]
    color_report: dict[str, object] | None = None
    preview_url: str
    created_at: str
    updated_at: str
