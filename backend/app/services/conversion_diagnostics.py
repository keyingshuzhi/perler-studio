from __future__ import annotations

from typing import Any

import numpy as np

from app.services.color_matcher import _delta_e_2000, color_record_lab, colorimetry_status, rgb_to_lab


def calculate_conversion_diagnostics(
    rgba: np.ndarray,
    cells: list[str | None],
    palette: dict[str, Any],
    hotspot_limit: int = 48,
) -> dict[str, Any]:
    """Return compact, cell-addressable CIEDE2000 diagnostics for a conversion.

    ``cell_delta_e_00_tenths`` is intentionally integer-packed to keep real-time
    preview responses practical. A value of 73 means ΔE00 7.3; transparent cells
    remain zero. The named hotspots retain their exact display value and provide
    a quick path to the cells most worth correcting in the editor.
    """
    flattened = np.asarray(rgba, dtype=np.uint8).reshape(-1, 4)
    values = np.zeros(len(cells), dtype=np.uint16)
    visible_indices = np.asarray(
        [index for index, code in enumerate(cells) if code is not None and flattened[index, 3] > 5], dtype=np.int32
    )
    if not len(visible_indices):
        return {
            "metric": "CIEDE2000",
            "quality_basis": "not_applicable",
            "measured_evaluated_cell_count": 0,
            "measured_evaluated_percent": 0.0,
            "average_delta_e_00": 0.0,
            "p95_delta_e_00": 0.0,
            "maximum_delta_e_00": 0.0,
            "cell_delta_e_00_tenths": values.tolist(),
            "hotspots": [],
        }

    color_by_code = {str(color["code"]): color for color in palette["colors"]}
    source_rgb = flattened[visible_indices, :3].astype(np.float64)
    matched_colors = [color_by_code[str(cells[index])] for index in visible_indices]
    matched_lab = np.stack([color_record_lab(color) for color in matched_colors])
    measured_count = sum(color.get("measured_lab") is not None for color in matched_colors)
    delta_e = _delta_e_2000(rgb_to_lab(source_rgb), matched_lab)
    values[visible_indices] = np.clip(np.rint(delta_e * 10), 0, np.iinfo(np.uint16).max).astype(np.uint16)
    width = int(rgba.shape[1])
    order = np.argsort(delta_e)[::-1][:hotspot_limit]
    hotspots = [
        {
            "index": int(visible_indices[position]),
            "row": int(visible_indices[position] // width) + 1,
            "column": int(visible_indices[position] % width) + 1,
            "color_code": cells[int(visible_indices[position])],
            "delta_e_00": round(float(delta_e[position]), 2),
        }
        for position in order
        if delta_e[position] > 0
    ]
    return {
        "metric": "CIEDE2000",
        "quality_basis": colorimetry_status(measured_count, len(matched_colors)),
        "measured_evaluated_cell_count": measured_count,
        "measured_evaluated_percent": round(measured_count / len(matched_colors) * 100, 1),
        "average_delta_e_00": round(float(np.mean(delta_e)), 2),
        "p95_delta_e_00": round(float(np.quantile(delta_e, 0.95)), 2),
        "maximum_delta_e_00": round(float(np.max(delta_e)), 2),
        "cell_delta_e_00_tenths": values.tolist(),
        "hotspots": hotspots,
    }
