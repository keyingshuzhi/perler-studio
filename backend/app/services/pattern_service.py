from __future__ import annotations

from typing import Any

import numpy as np

from app.core.config import Settings, get_settings
from app.core.exceptions import conflict, validation_error
from app.schemas.design import BlankPatternCreateRequest, TemplatePatternCreateRequest, TextPatternCreateRequest
from app.schemas.pattern import InventoryMode, PatternGenerateRequest, PatternPatchRequest
from app.services.color_matcher import ColorMatcher
from app.services.color_report_service import calculate_color_report
from app.services.conversion_diagnostics import calculate_conversion_diagnostics
from app.services.grid_generator import resize_to_grid
from app.services.image_processor import decode_image, prepare_conversion_image
from app.services.palette_service import PaletteService, get_palette_service
from app.services.pattern_preview import save_pattern_preview
from app.services.statistics_service import calculate_statistics
from app.services.storage_service import StorageService, get_storage, utc_now
from app.services.structure_analyzer import analyze_structure
from app.services.template_service import render_template, render_text


class PatternService:
    def __init__(
        self,
        settings: Settings | None = None,
        storage: StorageService | None = None,
        palettes: PaletteService | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.storage = storage or get_storage()
        self.palettes = palettes or get_palette_service()
        self.matcher = ColorMatcher()

    @staticmethod
    def _eligible_palette_codes(palette: dict[str, Any], include_special_colors: bool) -> set[str]:
        """Return production-safe candidates, keeping effect colours opt-in."""
        return {
            str(color["code"])
            for color in palette["colors"]
            if color.get("available", True) and (include_special_colors or color.get("effect", "standard") != "special")
        }

    @staticmethod
    def _color_ceiling(request: PatternGenerateRequest, palette_capacity: int) -> int:
        """Resolve the maximum search size; the matcher chooses the actual count.

        Automatic mode no longer guesses a final count from grid dimensions. The
        preset and creator value are only safety/production ceilings; the matcher
        grows a working palette until the requested P95 ΔE00 is reached.
        """
        preset_caps = {
            "portrait": 40,
            "illustration": 36,
            "pixel_art": 32,
            "landscape": 56,
            "custom": 48,
        }
        preset_cap = preset_caps[request.conversion_preset.value]
        configured_cap = request.max_colors or (preset_cap if request.auto_color_limit else palette_capacity)
        ceiling = (
            min(configured_cap, preset_cap, palette_capacity)
            if request.auto_color_limit
            else min(configured_cap, palette_capacity)
        )
        return max(1, min(palette_capacity, max(ceiling, len(set(request.locked_colors)))))

    def _grid_for_conversion(self, request: PatternGenerateRequest) -> np.ndarray:
        """Produce the processed source grid shared by preview, generation and edits."""
        if request.grid_width > self.settings.max_grid_width or request.grid_height > self.settings.max_grid_height:
            raise validation_error("目标网格超出服务限制", "GRID_SIZE_EXCEEDED")
        image_meta = self.storage.load_image_metadata(request.image_id)
        source_path = self.settings.storage_dir / image_meta["storage_path"]
        if not source_path.is_file():
            raise validation_error("原始图片文件不存在", "IMAGE_SOURCE_MISSING")
        image = prepare_conversion_image(decode_image(source_path.read_bytes()), request)
        try:
            grid = resize_to_grid(
                image, request.grid_width, request.grid_height, request.resize_mode, request.sampling_mode
            )
        except ValueError as error:
            raise validation_error(str(error), "INVALID_RESIZE_MODE") from error
        return np.asarray(grid)

    def _convert(
        self, request: PatternGenerateRequest
    ) -> tuple[np.ndarray, Any, dict[str, Any], dict[str, Any], dict[str, Any]]:
        """Run the single conversion pipeline used by preview and final generation."""
        grid = self._grid_for_conversion(request)
        palette = self.palettes.get(request.palette_id)
        palette_codes = {str(color["code"]) for color in palette["colors"] if color.get("available", True)}
        eligible_codes = self._eligible_palette_codes(palette, request.include_special_colors)
        unknown_locked_codes = set(request.locked_colors) - palette_codes
        if unknown_locked_codes:
            raise validation_error(
                f"锁定色号不存在或不可用: {', '.join(sorted(unknown_locked_codes))}",
                "INVALID_LOCKED_COLOR",
            )
        inventory_codes = {item.color_code for item in request.inventory}
        unknown_inventory_codes = inventory_codes - palette_codes
        if unknown_inventory_codes:
            raise validation_error(
                f"库存色号不存在或不可用: {', '.join(sorted(unknown_inventory_codes))}", "INVALID_INVENTORY_COLOR"
            )
        disabled_colors = set(request.disabled_colors) | (palette_codes - eligible_codes)
        excluded_locks = set(request.locked_colors) - eligible_codes
        if excluded_locks:
            raise validation_error(
                f"锁定的特殊色需要先启用扩展／特殊色: {', '.join(sorted(excluded_locks))}",
                "SPECIAL_COLOR_NOT_ENABLED",
            )
        if request.inventory_mode == InventoryMode.only:
            owned_codes = {item.color_code for item in request.inventory if item.quantity > 0}
            disabled_colors |= eligible_codes - owned_codes
        candidate_capacity = len(eligible_codes - disabled_colors)
        if not candidate_capacity:
            raise validation_error("当前色卡、库存和特殊色设置下没有可用颜色", "EMPTY_PALETTE")
        effective_color_ceiling = self._color_ceiling(request, candidate_capacity)
        structure = analyze_structure(grid, request)
        matching = self.matcher.match(
            grid,
            palette,
            request.distance_method,
            sorted(disabled_colors),
            request.locked_colors,
            effective_color_ceiling,
            request.minimum_color_count,
            request.transparent_background,
            request.cleanup_level,
            request.auto_color_limit,
            request.target_p95_delta_e_00,
            importance_map=structure.importance if structure.enabled else None,
        )
        statistics = calculate_statistics(
            matching.cells, request.grid_width, request.grid_height, palette, request.bead_size_mm, request.waste_rate
        )
        color_report = calculate_color_report(
            grid,
            matching.cells,
            palette,
            statistics,
            request.inventory,
            matching.selected_color_count,
            matching_metric=request.distance_method.value,
            target_p95_delta_e_00=request.target_p95_delta_e_00 if request.auto_color_limit else None,
            eligible_color_codes=eligible_codes - disabled_colors,
            special_colors_enabled=request.include_special_colors,
            cleanup_adjusted_cell_count=matching.cleanup_adjusted_cell_count,
            structure_aware_enabled=structure.enabled,
            structure_importance=structure.importance if structure.enabled else None,
            structure_protected_mask=structure.protected_mask if structure.enabled else None,
        )
        return grid, matching, palette, statistics, color_report

    def _build_pattern(
        self,
        request: PatternGenerateRequest,
        pattern_id: str,
        revision: int,
        created_at: str,
        updated_at: str,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        _grid, matching, palette, statistics, color_report = self._convert(request)
        pattern = {
            "id": pattern_id,
            "revision": revision,
            "image_id": request.image_id,
            "palette_id": request.palette_id,
            "grid_width": request.grid_width,
            "grid_height": request.grid_height,
            "cells": matching.cells,
            "settings": request.model_dump(
                mode="json",
                exclude={"image_id", "grid_width", "grid_height", "palette_id", "bead_size_mm", "waste_rate"},
            ),
            "statistics": statistics,
            "color_report": color_report,
            "created_at": created_at,
            "updated_at": updated_at,
        }
        return pattern, palette

    def preview(self, request: PatternGenerateRequest) -> dict[str, Any]:
        """Generate a conversion result without writing a pattern or media file."""
        grid, matching, palette, statistics, color_report = self._convert(request)
        return {
            "image_id": request.image_id,
            "palette_id": request.palette_id,
            "grid_width": request.grid_width,
            "grid_height": request.grid_height,
            "cells": matching.cells,
            "settings": request.model_dump(
                mode="json",
                exclude={"image_id", "grid_width", "grid_height", "palette_id", "bead_size_mm", "waste_rate"},
            ),
            "statistics": statistics,
            "color_report": color_report,
            "diagnostics": calculate_conversion_diagnostics(grid, matching.cells, palette),
        }

    def _save_preview(self, pattern: dict[str, Any], palette: dict[str, Any]) -> None:
        save_pattern_preview(pattern, palette, self.settings, self.storage)

    def generate(self, request: PatternGenerateRequest) -> dict[str, Any]:
        pattern_id, now = self.storage.new_id("pat"), utc_now()
        pattern, palette = self._build_pattern(request, pattern_id, revision=1, created_at=now, updated_at=now)
        self._save_preview(pattern, palette)
        self.storage.save_pattern(pattern)
        return pattern

    def _create_design_pattern(
        self,
        palette_id: str,
        grid_width: int,
        grid_height: int,
        cells: list[str | None],
        bead_size_mm: float,
        waste_rate: float,
        settings: dict[str, Any],
    ) -> dict[str, Any]:
        palette = self.palettes.get(palette_id)
        allowed_codes = {color["code"] for color in palette["colors"] if color.get("available", True)}
        unknown = {code for code in cells if code is not None} - allowed_codes
        if unknown:
            raise validation_error(f"设计中存在当前色卡没有的色号: {', '.join(sorted(unknown))}", "INVALID_COLOR_CODE")
        pattern_id, now = self.storage.new_id("pat"), utc_now()
        statistics = calculate_statistics(cells, grid_width, grid_height, palette, bead_size_mm, waste_rate)
        pattern = {
            "id": pattern_id,
            "revision": 1,
            "image_id": "",
            "palette_id": palette_id,
            "grid_width": grid_width,
            "grid_height": grid_height,
            "cells": cells,
            "settings": {"source_kind": "design", **settings},
            "statistics": statistics,
            "color_report": calculate_color_report(
                np.zeros((grid_height, grid_width, 4), dtype=np.uint8),
                cells,
                palette,
                statistics,
                reference_available=False,
            ),
            "created_at": now,
            "updated_at": now,
        }
        self._save_preview(pattern, palette)
        self.storage.save_pattern(pattern)
        return pattern

    def create_blank(self, request: BlankPatternCreateRequest) -> dict[str, Any]:
        return self._create_design_pattern(
            request.palette_id,
            request.grid_width,
            request.grid_height,
            [None] * (request.grid_width * request.grid_height),
            request.bead_size_mm,
            request.waste_rate,
            {"design_kind": "blank"},
        )

    def create_template(self, request: TemplatePatternCreateRequest) -> dict[str, Any]:
        palette = self.palettes.get(request.palette_id)
        available = [color["code"] for color in palette["colors"] if color.get("available", True)]
        if not available:
            raise validation_error("当前色卡没有可用颜色", "EMPTY_PALETTE")
        foreground = request.foreground_code or available[0]
        accent = request.accent_code or foreground
        width, height, cells = render_template(request.template_id, foreground, accent)
        return self._create_design_pattern(
            request.palette_id,
            width,
            height,
            cells,
            request.bead_size_mm,
            request.waste_rate,
            {"design_kind": "template", "template_id": request.template_id},
        )

    def create_text(self, request: TextPatternCreateRequest) -> dict[str, Any]:
        palette = self.palettes.get(request.palette_id)
        available = [color["code"] for color in palette["colors"] if color.get("available", True)]
        if not available:
            raise validation_error("当前色卡没有可用颜色", "EMPTY_PALETTE")
        foreground = request.foreground_code or available[0]
        accent = request.accent_code or foreground
        width, height, cells, normalized = render_text(request.text, request.style, foreground, accent)
        return self._create_design_pattern(
            request.palette_id,
            width,
            height,
            cells,
            request.bead_size_mm,
            request.waste_rate,
            {"design_kind": "text", "text": normalized, "text_style": request.style},
        )

    def create_remix(self, source: dict[str, Any], source_token: str) -> dict[str, Any]:
        """Copy an approved community pattern into a new editable design pattern."""
        return self._create_design_pattern(
            str(source["palette_id"]),
            int(source["grid_width"]),
            int(source["grid_height"]),
            list(source["cells"]),
            float(source["statistics"]["bead_size_mm"]),
            float(source["statistics"]["waste_rate"]),
            {"design_kind": "community_remix", "remix_source_token": source_token},
        )

    def regenerate(self, pattern_id: str, request: PatternGenerateRequest) -> dict[str, Any]:
        """Rebuild a pattern in place so its owning project remains intact."""
        current = self.storage.load_pattern(pattern_id)
        now = utc_now()
        pattern, palette = self._build_pattern(
            request,
            pattern_id,
            revision=int(current["revision"]) + 1,
            created_at=str(current["created_at"]),
            updated_at=now,
        )
        self._save_preview(pattern, palette)
        self.storage.save_pattern(pattern)
        return pattern

    def get(self, pattern_id: str) -> dict[str, Any]:
        return self.storage.load_pattern(pattern_id)

    def patch(self, pattern_id: str, request: PatternPatchRequest) -> dict[str, Any]:
        pattern = self.storage.load_pattern(pattern_id)
        if request.base_revision is not None and request.base_revision != pattern["revision"]:
            raise conflict("图纸已被更新，请刷新后再保存", "PATTERN_REVISION_CONFLICT")
        palette = self.palettes.get(pattern["palette_id"])
        allowed_codes = {color["code"] for color in palette["colors"] if color.get("available", True)}
        seen_indices: set[int] = set()
        cells = list(pattern["cells"])
        for change in request.changes:
            if change.index >= len(cells):
                raise validation_error(f"单元格索引超出范围: {change.index}", "INVALID_CELL_INDEX")
            if change.index in seen_indices:
                raise validation_error(f"单元格索引重复: {change.index}", "DUPLICATE_CELL_INDEX")
            seen_indices.add(change.index)
            if "before" in change.model_fields_set and cells[change.index] != change.before:
                raise conflict("图纸单元格已被其他修改覆盖，请刷新后重试", "CELL_CONFLICT")
            if change.after is not None and change.after not in allowed_codes:
                raise validation_error(f"色号不存在或不可用: {change.after}", "INVALID_COLOR_CODE")
            cells[change.index] = change.after
        pattern["cells"] = cells
        pattern["revision"] += 1
        pattern["updated_at"] = utc_now()
        pattern["statistics"] = calculate_statistics(
            cells,
            pattern["grid_width"],
            pattern["grid_height"],
            palette,
            pattern["statistics"]["bead_size_mm"],
            pattern["statistics"]["waste_rate"],
        )
        if pattern.get("image_id"):
            settings = dict(pattern.get("settings", {}))
            conversion_request = PatternGenerateRequest.model_validate(
                {
                    **settings,
                    "image_id": pattern["image_id"],
                    "grid_width": pattern["grid_width"],
                    "grid_height": pattern["grid_height"],
                    "palette_id": pattern["palette_id"],
                    "bead_size_mm": pattern["statistics"]["bead_size_mm"],
                    "waste_rate": pattern["statistics"]["waste_rate"],
                }
            )
            grid = self._grid_for_conversion(conversion_request)
            eligible_codes = self._eligible_palette_codes(
                palette,
                conversion_request.include_special_colors,
            )
            eligible_codes -= set(conversion_request.disabled_colors)
            if conversion_request.inventory_mode == InventoryMode.only:
                owned_codes = {item.color_code for item in conversion_request.inventory if item.quantity > 0}
                eligible_codes &= owned_codes
            structure = analyze_structure(grid, conversion_request)
            pattern["color_report"] = calculate_color_report(
                grid,
                cells,
                palette,
                pattern["statistics"],
                settings.get("inventory", []),
                settings.get("max_colors"),
                matching_metric=conversion_request.distance_method.value,
                target_p95_delta_e_00=conversion_request.target_p95_delta_e_00
                if conversion_request.auto_color_limit
                else None,
                eligible_color_codes=eligible_codes,
                special_colors_enabled=conversion_request.include_special_colors,
                structure_aware_enabled=structure.enabled,
                structure_importance=structure.importance if structure.enabled else None,
                structure_protected_mask=structure.protected_mask if structure.enabled else None,
            )
        elif pattern.get("settings", {}).get("source_kind") == "design":
            pattern["color_report"] = calculate_color_report(
                np.zeros((pattern["grid_height"], pattern["grid_width"], 4), dtype=np.uint8),
                cells,
                palette,
                pattern["statistics"],
                pattern.get("settings", {}).get("inventory", []),
                reference_available=False,
            )
        self._save_preview(pattern, palette)
        self.storage.save_pattern(pattern)
        return pattern

    def delete(self, pattern_id: str) -> None:
        self.storage.load_pattern(pattern_id)
        self.storage.delete_pattern(pattern_id)
        preview_path = self.settings.pattern_dir / f"{pattern_id}.png"
        if preview_path.exists():
            preview_path.unlink()


def get_pattern_service() -> PatternService:
    return PatternService()
