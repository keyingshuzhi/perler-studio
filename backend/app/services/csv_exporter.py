from __future__ import annotations

import csv
from pathlib import Path
from typing import Any


def export_statistics_csv(pattern: dict[str, Any], destination: Path, include_waste: bool = True) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    fields = ["color_code", "color_name", "color_name_en", "hex", "count", "ratio"]
    if include_waste:
        fields.append("count_with_waste")
    with destination.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for color in pattern["statistics"]["colors"]:
            writer.writerow({field: color.get(field) for field in fields})
