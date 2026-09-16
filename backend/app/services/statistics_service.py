from __future__ import annotations

import math
from collections import Counter
from typing import Any


def calculate_statistics(
    cells: list[str | None],
    grid_width: int,
    grid_height: int,
    palette: dict[str, Any],
    bead_size_mm: float,
    waste_rate: float,
    pegboard_side: int = 29,
) -> dict[str, Any]:
    if len(cells) != grid_width * grid_height:
        raise ValueError("网格数据长度与尺寸不匹配")
    palette_by_code = {color["code"]: color for color in palette["colors"]}
    counts = Counter(code for code in cells if code is not None)
    colors = []
    for code, count in sorted(counts.items(), key=lambda item: (-item[1], item[0])):
        color = palette_by_code.get(code)
        if color is None:
            raise ValueError(f"图纸包含色卡中不存在的色号: {code}")
        colors.append(
            {
                "color_code": code,
                "color_name": color["name_zh"],
                "color_name_en": color.get("name_en"),
                "hex": color["hex"],
                "count": count,
                "count_with_waste": math.ceil(count * (1 + waste_rate)),
                "ratio": round(count / len(cells), 6),
            }
        )
    total_beads = sum(counts.values())
    return {
        "grid_width": grid_width,
        "grid_height": grid_height,
        "bead_size_mm": bead_size_mm,
        "total_cells": len(cells),
        "transparent_cells": len(cells) - total_beads,
        "total_beads": total_beads,
        "total_beads_with_waste": math.ceil(total_beads * (1 + waste_rate)),
        "used_color_count": len(counts),
        "physical_width_mm": round(grid_width * bead_size_mm, 2),
        "physical_height_mm": round(grid_height * bead_size_mm, 2),
        "waste_rate": waste_rate,
        "estimated_pegboards": math.ceil(grid_width / pegboard_side) * math.ceil(grid_height / pegboard_side),
        "colors": colors,
    }
