from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field


class SymbolMode(StrEnum):
    color_code = "color_code"
    short_code = "short_code"
    none = "none"


class ExportBase(BaseModel):
    project_id: str | None = Field(default=None, min_length=4, max_length=80)
    pattern_id: str | None = Field(default=None, min_length=4, max_length=80)


class PNGExportRequest(ExportBase):
    cell_size_px: int = Field(default=32, ge=8, le=256)
    show_grid: bool = True
    show_coordinates: bool = True
    show_symbols: bool = True
    symbol_mode: SymbolMode = SymbolMode.color_code
    background: str = Field(default="white", pattern=r"^(white|transparent|#[0-9A-Fa-f]{6})$")
    include_legend: bool = True


class SVGExportRequest(ExportBase):
    cell_size_px: int = Field(default=32, ge=8, le=256)
    show_grid: bool = True
    show_coordinates: bool = True
    show_symbols: bool = True
    symbol_mode: SymbolMode = SymbolMode.color_code
    background: str = Field(default="white", pattern=r"^(white|transparent|#[0-9A-Fa-f]{6})$")
    include_legend: bool = True


class PDFExportRequest(ExportBase):
    paper_size: str = Field(default="A4", pattern=r"^(A4|A3)$")
    orientation: str = Field(default="landscape", pattern=r"^(portrait|landscape)$")
    mode: str = Field(default="multipage", pattern=r"^(single|multipage|guide)$")
    show_grid: bool = True
    show_coordinates: bool = True
    show_symbols: bool = True
    symbol_mode: SymbolMode = SymbolMode.short_code
    include_legend: bool = True
    include_statistics: bool = True
    overlap_cells: int = Field(default=1, ge=0, le=20)
    margin_mm: float = Field(default=10, ge=3, le=40)
    assembly_board_width: int = Field(default=29, ge=4, le=120)
    assembly_board_height: int = Field(default=29, ge=4, le=120)
    assembly_overlap: int = Field(default=0, ge=0, le=12)


class CSVExportRequest(ExportBase):
    include_waste: bool = True


class ProjectExportRequest(ExportBase):
    pass
