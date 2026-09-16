from __future__ import annotations

from math import ceil
from typing import Any

from app.core.exceptions import validation_error


def _range_labels(total: int, capacity: int, overlap: int) -> list[tuple[int, int]]:
    step = capacity - overlap
    count = max(1, ceil(max(0, total - overlap) / step))
    return [(index * step, min(total, index * step + capacity)) for index in range(count)]


def _row_label(index: int) -> str:
    result = ""
    value = index + 1
    while value:
        value, remainder = divmod(value - 1, 26)
        result = chr(65 + remainder) + result
    return result


def build_assembly_plan(
    pattern: dict[str, Any], board_width: int, board_height: int, overlap: int = 0
) -> dict[str, Any]:
    if overlap >= min(board_width, board_height):
        raise validation_error("重叠格数必须小于底板边长", "INVALID_BOARD_OVERLAP")
    row_ranges = _range_labels(int(pattern["grid_height"]), board_height, overlap)
    column_ranges = _range_labels(int(pattern["grid_width"]), board_width, overlap)
    boards: list[dict[str, Any]] = []
    for row, (start_row, end_row) in enumerate(row_ranges):
        for column, (start_column, end_column) in enumerate(column_ranges):
            board_id = f"{_row_label(row)}{column + 1}"
            boards.append(
                {
                    "id": board_id,
                    "row": row + 1,
                    "column": column + 1,
                    "row_range": [start_row + 1, end_row],
                    "column_range": [start_column + 1, end_column],
                    "grid_width": end_column - start_column,
                    "grid_height": end_row - start_row,
                    "join_right": f"{_row_label(row)}{column + 2}" if column + 1 < len(column_ranges) else None,
                    "join_bottom": f"{_row_label(row + 1)}{column + 1}" if row + 1 < len(row_ranges) else None,
                }
            )
    return {
        "grid_width": pattern["grid_width"],
        "grid_height": pattern["grid_height"],
        "board_width": board_width,
        "board_height": board_height,
        "overlap": overlap,
        "board_rows": len(row_ranges),
        "board_columns": len(column_ranges),
        "board_count": len(boards),
        "boards": boards,
    }
