from __future__ import annotations

from collections import Counter
from math import ceil
from typing import Any

from app.core.exceptions import validation_error
from app.core.presets import get_pegboard_template
from app.services.assembly_service import build_assembly_plan

_STRATEGIES = {"color", "region", "rows", "columns"}


def _board_counter(pattern: dict[str, Any], board: dict[str, Any]) -> Counter[str]:
    width = int(pattern["grid_width"])
    start_row, end_row = (int(value) - 1 for value in board["row_range"])
    start_column, end_column = (int(value) - 1 for value in board["column_range"])
    return Counter(
        code
        for row in range(start_row, end_row + 1)
        for column in range(start_column, end_column + 1)
        if (code := pattern["cells"][row * width + column]) is not None
    )


def _assembly_order(boards: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[int, list[dict[str, Any]]] = {}
    for board in boards:
        grouped.setdefault(int(board["row"]), []).append(board)
    ordered: list[dict[str, Any]] = []
    for row in sorted(grouped):
        row_boards = sorted(grouped[row], key=lambda board: int(board["column"]))
        ordered.extend(row_boards if row % 2 else list(reversed(row_boards)))
    return ordered


def _range_count(pattern: dict[str, Any], row_start: int, row_end: int, column_start: int, column_end: int) -> int:
    width = int(pattern["grid_width"])
    return sum(
        pattern["cells"][row * width + column] is not None
        for row in range(row_start, row_end)
        for column in range(column_start, column_end)
    )


def _make_steps(
    pattern: dict[str, Any], boards: list[dict[str, Any]], strategy: str, beads_per_hour: int
) -> list[dict[str, Any]]:
    ordered_boards = _assembly_order(boards)
    board_counts = {board["id"]: Counter(board["color_counts"]) for board in boards}
    steps: list[dict[str, Any]] = []
    if strategy == "color":
        for color in pattern["statistics"]["colors"]:
            code = str(color["color_code"])
            target_boards = [board["id"] for board in ordered_boards if board_counts[board["id"]].get(code, 0)]
            count = int(color["count"])
            steps.append(
                {
                    "id": f"color:{code}",
                    "title": f"铺放 {code}",
                    "instruction": f"在 {', '.join(target_boards)} 中完成所有 {code} 色拼豆。",
                    "bead_count": count,
                    "targets": target_boards,
                }
            )
    elif strategy == "region":
        for board in ordered_boards:
            steps.append(
                {
                    "id": f"board:{board['id']}",
                    "title": f"完成底板 {board['id']}",
                    "instruction": (
                        f"按坐标完成行 {board['row_range'][0]}–{board['row_range'][1]}、"
                        f"列 {board['column_range'][0]}–{board['column_range'][1]}。"
                    ),
                    "bead_count": board["bead_count"],
                    "targets": [board["id"]],
                }
            )
    else:
        by_rows = strategy == "rows"
        total = int(pattern["grid_height"] if by_rows else pattern["grid_width"])
        other_total = int(pattern["grid_width"] if by_rows else pattern["grid_height"])
        for start in range(0, total, 5):
            end = min(total, start + 5)
            count = _range_count(
                pattern,
                start if by_rows else 0,
                end if by_rows else other_total,
                0 if by_rows else start,
                other_total if by_rows else end,
            )
            label = "行" if by_rows else "列"
            steps.append(
                {
                    "id": f"{strategy}:{start + 1}-{end}",
                    "title": f"完成第 {start + 1}–{end} {label}",
                    "instruction": (
                        f"从 {'左到右' if by_rows else '上到下'}连续铺放，完成第 {start + 1}–{end} {label}后核对坐标。"
                    ),
                    "bead_count": count,
                    "targets": [],
                }
            )
    for ordinal, step in enumerate(steps, start=1):
        step["ordinal"] = ordinal
        count = int(step["bead_count"])
        step["estimated_minutes"] = max(1, ceil(count / beads_per_hour * 60)) if count else 0
    return steps


def _missing_materials(pattern: dict[str, Any]) -> dict[str, Any]:
    inventory = pattern.get("settings", {}).get("inventory", [])
    if not isinstance(inventory, list) or not inventory:
        return {"tracked": False, "shortages": [], "coverage_percent": None}
    available = {
        str(item.get("color_code")): int(item.get("quantity", 0)) for item in inventory if isinstance(item, dict)
    }
    required = pattern["statistics"]["colors"]
    shortages = [
        {
            "color_code": item["color_code"],
            "required_quantity": int(item.get("count_with_waste", item["count"])),
            "available_quantity": available.get(str(item["color_code"]), 0),
            "shortage_quantity": max(
                0, int(item.get("count_with_waste", item["count"])) - available.get(str(item["color_code"]), 0)
            ),
        }
        for item in required
    ]
    missing = [item for item in shortages if item["shortage_quantity"]]
    required_total = sum(item["required_quantity"] for item in shortages)
    covered = sum(min(item["required_quantity"], item["available_quantity"]) for item in shortages)
    return {
        "tracked": True,
        "shortages": missing,
        "coverage_percent": round(covered / required_total * 100, 1) if required_total else 100.0,
    }


def build_production_plan(
    pattern: dict[str, Any],
    board_template_id: str = "midi-square-29",
    overlap: int = 0,
    strategy: str = "color",
    beads_per_hour: int = 360,
) -> dict[str, Any]:
    """Build a physical making plan from the exact saved grid and stock snapshot."""
    if strategy not in _STRATEGIES:
        raise validation_error("制作步骤类型无效", "INVALID_PRODUCTION_STRATEGY")
    if not 30 <= beads_per_hour <= 3_000:
        raise validation_error("制作速度应在每小时 30–3000 颗之间", "INVALID_PRODUCTION_SPEED")
    try:
        template = get_pegboard_template(board_template_id)
    except KeyError as error:
        raise validation_error("未找到该底板模板", "PEGBOARD_TEMPLATE_NOT_FOUND") from error
    assembly = build_assembly_plan(pattern, int(template["board_width"]), int(template["board_height"]), overlap)
    boards = []
    for source_board in assembly["boards"]:
        counts = _board_counter(pattern, source_board)
        boards.append(
            {
                **source_board,
                "bead_count": sum(counts.values()),
                "used_color_count": len(counts),
                "color_counts": dict(sorted(counts.items())),
            }
        )
    install_steps = [
        {
            "ordinal": index,
            "id": f"install:{board['id']}",
            "board_id": board["id"],
            "title": f"拼接 {board['id']}",
            "instruction": (
                f"放置 {board['id']}；右侧连接 {board['join_right'] or '无'}，下侧连接 {board['join_bottom'] or '无'}。"
            ),
            "bead_count": board["bead_count"],
        }
        for index, board in enumerate(_assembly_order(boards), start=1)
    ]
    make_steps = _make_steps(pattern, boards, strategy, beads_per_hour)
    total_beads = int(pattern["statistics"]["total_beads"])
    return {
        "board_template": template,
        "assembly": {**assembly, "boards": boards, "installation_steps": install_steps},
        "strategy": strategy,
        "beads_per_hour": beads_per_hour,
        "estimated_minutes": max(1, ceil(total_beads / beads_per_hour * 60)) if total_beads else 0,
        "make_steps": make_steps,
        "materials": _missing_materials(pattern),
    }
