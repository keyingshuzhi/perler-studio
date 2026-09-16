from __future__ import annotations

from collections.abc import Iterable
from typing import Any

import numpy as np

from app.schemas.pattern import DistanceMethod
from app.services.color_matcher import (
    _delta_e_2000,
    _distances,
    color_record_lab,
    colorimetry_status,
    palette_records_lab,
    rgb_to_lab,
)


def _quality(delta_e: float) -> tuple[str, str]:
    if delta_e <= 1.5:
        return "优秀", "平均色差极低，适合保留细腻的明暗与肤色过渡。"
    if delta_e <= 3:
        return "良好", "大多数颜色接近原图；重点区域仍建议在编辑器中与原图对照。"
    if delta_e <= 6:
        return "可制作", "整体可读，但局部色相或明度会出现可见差异。"
    return "建议精修", "色差较明显，建议提高色阶、切换色卡或在编辑器中修正重点区域。"


def _difference_label(delta_e: float) -> str:
    if delta_e <= 2:
        return "几乎无可见差异"
    if delta_e <= 5:
        return "可接受替代"
    if delta_e <= 10:
        return "存在可见差异"
    return "色差较大，建议谨慎替换"


def _inventory_map(inventory: Iterable[Any]) -> dict[str, int]:
    result: dict[str, int] = {}
    for item in inventory:
        if isinstance(item, dict):
            code, quantity = item.get("color_code"), item.get("quantity")
        else:
            code, quantity = getattr(item, "color_code", None), getattr(item, "quantity", None)
        if isinstance(code, str) and isinstance(quantity, int) and quantity > 0:
            result[code] = quantity
    return result


def _oracle_quality(
    source_rgb: np.ndarray,
    candidate_colors: list[dict[str, Any]],
) -> tuple[float, float] | None:
    """Return the unconstrained per-cell CIEDE2000 lower bound.

    The oracle may use every eligible real swatch independently for every cell.
    It ignores colour-count and spatial-cleanup constraints, so no production
    algorithm using the same one-bead-per-cell palette can have a lower colour
    error. Unique source colours keep the diagnostic practical on large grids.
    """
    if not len(source_rgb) or not candidate_colors:
        return None
    unique, inverse = np.unique(np.asarray(source_rgb, dtype=np.uint8), axis=0, return_inverse=True)
    candidate_rgb = np.asarray([color["rgb"] for color in candidate_colors], dtype=np.float64)
    candidate_lab = palette_records_lab(candidate_colors)
    minimum_distances: list[np.ndarray] = []
    for start in range(0, len(unique), 2_048):
        distances = _distances(
            unique[start : start + 2_048],
            candidate_rgb,
            DistanceMethod.ciede2000,
            candidate_lab,
        )
        minimum_distances.append(np.min(distances, axis=1))
    minimum = np.concatenate(minimum_distances)
    per_cell_minimum = minimum[inverse]
    return float(np.mean(per_cell_minimum)), float(np.quantile(per_cell_minimum, 0.95))


def _nearest_inventory_alternative(
    required_color: dict[str, Any], candidates: list[dict[str, Any]], available: dict[str, int]
) -> dict[str, Any] | None:
    if not candidates:
        return None
    source_lab = color_record_lab(required_color).reshape(1, 3)
    candidate_lab = palette_records_lab(candidates)
    distances = _delta_e_2000(source_lab, candidate_lab)
    index = int(np.argmin(distances))
    candidate = candidates[index]
    delta_e = float(distances[index])
    return {
        "from_color_code": required_color["code"],
        "to_color_code": candidate["code"],
        "to_color_name": candidate["name_zh"],
        "to_hex": candidate["hex"],
        "available_quantity": available[candidate["code"]],
        "delta_e_00": round(delta_e, 2),
        "assessment": _difference_label(delta_e),
    }


def calculate_color_report(
    rgba: np.ndarray,
    cells: list[str | None],
    palette: dict[str, Any],
    statistics: dict[str, Any],
    inventory: Iterable[Any] = (),
    selected_color_limit: int | None = None,
    *,
    matching_metric: str | None = None,
    target_p95_delta_e_00: float | None = None,
    eligible_color_codes: set[str] | None = None,
    special_colors_enabled: bool = False,
    cleanup_adjusted_cell_count: int = 0,
    structure_aware_enabled: bool = False,
    structure_importance: np.ndarray | None = None,
    structure_protected_mask: np.ndarray | None = None,
    reference_available: bool = True,
) -> dict[str, Any]:
    """Summarise perceptual conversion error and material availability.

    The quality score always uses CIEDE2000 so it remains comparable when a
    project is generated with the blended "fidelity" matcher. Inventory advice
    is advisory: the recommended replacement is never silently applied.
    """
    palette_by_code = {color["code"]: color for color in palette["colors"]}
    flattened = np.asarray(rgba).reshape(-1, 4)
    evaluated_indices: list[int] = []
    source_rows: list[np.ndarray] = []
    matched_lab_rows: list[np.ndarray] = []
    measured_evaluated_cells = 0
    for index, code in enumerate(cells if reference_available else []):
        if code is None:
            continue
        color = palette_by_code.get(code)
        if color is None or index >= len(flattened):
            continue
        evaluated_indices.append(index)
        source_rows.append(flattened[index, :3])
        matched_lab_rows.append(color_record_lab(color))
        measured_evaluated_cells += color.get("measured_lab") is not None

    if source_rows:
        differences = _delta_e_2000(
            rgb_to_lab(np.asarray(source_rows, dtype=np.float64)),
            np.asarray(matched_lab_rows, dtype=np.float64),
        )
        average_delta_e = float(np.mean(differences))
        p95_delta_e = float(np.quantile(differences, 0.95))
        maximum_delta_e = float(np.max(differences))
    else:
        average_delta_e = p95_delta_e = maximum_delta_e = 0.0
    quality_label, quality_note = (
        _quality(average_delta_e)
        if source_rows
        else (
            "原创设计",
            "此图纸没有参考原图；色差指标会在你从图片生成图纸时提供。",
        )
    )

    structure_weighted_average: float | None = None
    structure_protected_average: float | None = None
    structure_protected_p95: float | None = None
    structure_protected_count = 0
    if structure_aware_enabled and source_rows and structure_importance is not None:
        importance = np.asarray(structure_importance, dtype=np.float64).reshape(-1)
        if len(importance) != len(flattened):
            raise ValueError("结构权重尺寸必须与色差报告网格一致")
        evaluated_importance = importance[np.asarray(evaluated_indices, dtype=np.int64)]
        structure_weighted_average = float(np.average(differences, weights=np.maximum(evaluated_importance, 1e-6)))
        if structure_protected_mask is not None:
            protected = np.asarray(structure_protected_mask, dtype=bool).reshape(-1)
            if len(protected) != len(flattened):
                raise ValueError("结构保护遮罩尺寸必须与色差报告网格一致")
            evaluated_protected = protected[np.asarray(evaluated_indices, dtype=np.int64)]
            structure_protected_count = int(np.count_nonzero(evaluated_protected))
            if structure_protected_count:
                structure_protected_average = float(np.mean(differences[evaluated_protected]))
                structure_protected_p95 = float(np.quantile(differences[evaluated_protected], 0.95))

    eligible_codes = (
        {code for code, color in palette_by_code.items() if color.get("available", True)}
        if eligible_color_codes is None
        else eligible_color_codes
    )
    palette_measured_color_count = sum(color.get("measured_lab") is not None for color in palette_by_code.values())
    eligible_colors = [color for code, color in palette_by_code.items() if code in eligible_codes]
    eligible_measured_color_count = sum(color.get("measured_lab") is not None for color in eligible_colors)
    oracle = _oracle_quality(np.asarray(source_rows, dtype=np.float64), eligible_colors)
    if oracle is None:
        oracle_average_delta_e = oracle_p95_delta_e = p95_oracle_gap = None
        oracle_target_reachable = None
    else:
        oracle_average_delta_e, oracle_p95_delta_e = oracle
        p95_oracle_gap = max(0.0, p95_delta_e - oracle_p95_delta_e)
        oracle_target_reachable = (
            oracle_p95_delta_e <= target_p95_delta_e_00 if target_p95_delta_e_00 is not None else None
        )
    quality_basis = colorimetry_status(measured_evaluated_cells, len(source_rows))
    matching_color_basis = (
        "screen_rgb"
        if matching_metric == "rgb"
        else colorimetry_status(eligible_measured_color_count, len(eligible_colors))
    )
    available = _inventory_map(inventory)
    used_colors = list(statistics.get("colors", []))
    required_beads = sum(int(color.get("count_with_waste", color.get("count", 0))) for color in used_colors)
    covered_beads = 0
    missing_colors: list[dict[str, Any]] = []
    candidates = [
        color for code, color in palette_by_code.items() if code in eligible_codes and available.get(code, 0) > 0
    ]
    substitutions: list[dict[str, Any]] = []
    for item in used_colors:
        code = str(item["color_code"])
        required = int(item.get("count_with_waste", item.get("count", 0)))
        owned = available.get(code, 0)
        covered_beads += min(required, owned)
        shortage = max(0, required - owned)
        if shortage:
            color = palette_by_code[code]
            missing = {
                "color_code": code,
                "color_name": color["name_zh"],
                "hex": color["hex"],
                "required_quantity": required,
                "available_quantity": owned,
                "shortage_quantity": shortage,
            }
            missing_colors.append(missing)
            alternatives = [candidate for candidate in candidates if candidate["code"] != code]
            suggestion = _nearest_inventory_alternative(color, alternatives, available)
            if suggestion:
                substitutions.append(suggestion | {"shortage_quantity": shortage})

    inventory_enabled = bool(available)
    return {
        "metric": "CIEDE2000",
        "matching_metric": matching_metric,
        "quality_basis": quality_basis,
        "matching_color_basis": matching_color_basis,
        "measured_evaluated_cell_count": measured_evaluated_cells,
        "measured_evaluated_percent": round(measured_evaluated_cells / len(source_rows) * 100, 1)
        if source_rows
        else 0.0,
        "palette_measured_color_count": palette_measured_color_count,
        "palette_measurement_coverage_percent": round(
            palette_measured_color_count / len(palette_by_code) * 100,
            1,
        ),
        "calibration": palette.get("calibration"),
        "average_delta_e_00": round(average_delta_e, 2),
        "p95_delta_e_00": round(p95_delta_e, 2),
        "maximum_delta_e_00": round(maximum_delta_e, 2),
        "oracle_average_delta_e_00": round(oracle_average_delta_e, 2) if oracle_average_delta_e is not None else None,
        "oracle_p95_delta_e_00": round(oracle_p95_delta_e, 2) if oracle_p95_delta_e is not None else None,
        "p95_oracle_gap": round(p95_oracle_gap, 2) if p95_oracle_gap is not None else None,
        "oracle_target_reachable": oracle_target_reachable,
        "oracle_palette_color_count": len(eligible_colors),
        "target_p95_delta_e_00": round(target_p95_delta_e_00, 2) if target_p95_delta_e_00 is not None else None,
        "target_met": p95_delta_e <= target_p95_delta_e_00 if target_p95_delta_e_00 is not None else None,
        "quality_label": quality_label,
        "quality_note": quality_note,
        "evaluated_cells": len(source_rows),
        "palette_color_count": len(palette_by_code),
        "eligible_palette_color_count": len(eligible_codes),
        "special_colors_enabled": special_colors_enabled,
        "cleanup_adjusted_cell_count": cleanup_adjusted_cell_count,
        "cleanup_adjusted_percent": round(cleanup_adjusted_cell_count / len(source_rows) * 100, 2)
        if source_rows
        else 0.0,
        "structure_aware_enabled": structure_aware_enabled,
        "structure_protected_cell_count": structure_protected_count,
        "structure_protected_percent": round(structure_protected_count / len(source_rows) * 100, 2)
        if source_rows
        else 0.0,
        "structure_weighted_average_delta_e_00": round(structure_weighted_average, 2)
        if structure_weighted_average is not None
        else None,
        "structure_protected_average_delta_e_00": round(structure_protected_average, 2)
        if structure_protected_average is not None
        else None,
        "structure_protected_p95_delta_e_00": round(structure_protected_p95, 2)
        if structure_protected_p95 is not None
        else None,
        "selected_color_limit": min(
            len(eligible_codes) if selected_color_limit is None else selected_color_limit,
            len(eligible_codes),
        ),
        "used_color_count": int(statistics.get("used_color_count", 0)),
        "inventory": {
            "enabled": inventory_enabled,
            "owned_color_count": len(available),
            "required_beads": required_beads,
            "covered_beads": covered_beads,
            "coverage_percent": round(covered_beads / required_beads * 100, 1) if required_beads else 100.0,
            "missing_colors": missing_colors,
        },
        "substitutions": substitutions,
    }
