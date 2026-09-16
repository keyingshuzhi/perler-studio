from __future__ import annotations

from typing import TypedDict


class GridPreset(TypedDict):
    id: str
    name_zh: str
    name_en: str
    grid_width: int
    grid_height: int
    use_case: str
    recommended_max_colors: int
    recommended_bead_size_mm: float


class PegboardTemplate(TypedDict):
    id: str
    name_zh: str
    board_width: int
    board_height: int
    usable_holes: int
    bead_size_mm: float
    layout_kind: str
    description: str


GRID_PRESETS: tuple[GridPreset, ...] = (
    {
        "id": "phone_charm_mini",
        "name_zh": "手机挂件（迷你豆）",
        "name_en": "Phone charm",
        "grid_width": 16,
        "grid_height": 16,
        "use_case": "手机挂件、小吊饰",
        "recommended_max_colors": 24,
        "recommended_bead_size_mm": 2.6,
    },
    {
        "id": "keychain_midi",
        "name_zh": "钥匙扣（中号豆）",
        "name_en": "Keychain",
        "grid_width": 12,
        "grid_height": 12,
        "use_case": "钥匙扣、包挂",
        "recommended_max_colors": 32,
        "recommended_bead_size_mm": 5.0,
    },
    {
        "id": "badge_midi",
        "name_zh": "徽章／胸针",
        "name_en": "Badge",
        "grid_width": 14,
        "grid_height": 14,
        "use_case": "胸针、徽章、小摆件",
        "recommended_max_colors": 40,
        "recommended_bead_size_mm": 5.0,
    },
    {
        "id": "coaster_midi",
        "name_zh": "杯垫",
        "name_en": "Coaster",
        "grid_width": 29,
        "grid_height": 29,
        "use_case": "标准中号豆杯垫",
        "recommended_max_colors": 64,
        "recommended_bead_size_mm": 5.0,
    },
    {
        "id": "portrait_small",
        "name_zh": "小幅头像",
        "name_en": "Small portrait",
        "grid_width": 48,
        "grid_height": 48,
        "use_case": "人物头像、宠物头像",
        "recommended_max_colors": 96,
        "recommended_bead_size_mm": 5.0,
    },
    {
        "id": "frame_square",
        "name_zh": "方形相框",
        "name_en": "Square frame",
        "grid_width": 64,
        "grid_height": 64,
        "use_case": "装框作品、桌面摆台",
        "recommended_max_colors": 120,
        "recommended_bead_size_mm": 5.0,
    },
    {
        "id": "poster_landscape",
        "name_zh": "横版海报",
        "name_en": "Landscape poster",
        "grid_width": 112,
        "grid_height": 84,
        "use_case": "风景、横版角色图",
        "recommended_max_colors": 160,
        "recommended_bead_size_mm": 5.0,
    },
    {
        "id": "wall_art",
        "name_zh": "墙面大作",
        "name_en": "Wall art",
        "grid_width": 160,
        "grid_height": 120,
        "use_case": "拼板墙饰、大尺寸作品",
        "recommended_max_colors": 220,
        "recommended_bead_size_mm": 5.0,
    },
)


# These are the rectangular, grid-aligned boards that the current editor and
# exporters can map one-to-one. Decorative/irregular boards intentionally stay
# out of this registry until their exact hole maps are modelled.
PEGBOARD_TEMPLATES: tuple[PegboardTemplate, ...] = (
    {
        "id": "midi-square-29",
        "name_zh": "中号方形底板 29 × 29",
        "board_width": 29,
        "board_height": 29,
        "usable_holes": 841,
        "bead_size_mm": 5.0,
        "layout_kind": "rectangular",
        "description": "标准中号方形底板，坐标从左上角 1,1 开始。",
    },
    {
        "id": "midi-square-30",
        "name_zh": "中号方形底板 30 × 30",
        "board_width": 30,
        "board_height": 30,
        "usable_holes": 900,
        "bead_size_mm": 5.0,
        "layout_kind": "rectangular",
        "description": "30 格方形底板，适合与同规格底板拼接。",
    },
    {
        "id": "midi-square-60",
        "name_zh": "中号大方形底板 60 × 60",
        "board_width": 60,
        "board_height": 60,
        "usable_holes": 3600,
        "bead_size_mm": 5.0,
        "layout_kind": "rectangular",
        "description": "大尺寸方形底板，适合减少大型壁画的拼接数量。",
    },
)


def list_grid_presets() -> list[dict[str, object]]:
    bead_sizes = (2.6, 5.0)
    payload: list[dict[str, object]] = []
    for preset in GRID_PRESETS:
        dimensions = {
            str(size): {
                "width_mm": round(preset["grid_width"] * size, 1),
                "height_mm": round(preset["grid_height"] * size, 1),
                "width_in": round(preset["grid_width"] * size / 25.4, 2),
                "height_in": round(preset["grid_height"] * size / 25.4, 2),
            }
            for size in bead_sizes
        }
        payload.append({**preset, "dimensions": dimensions})
    return payload


def list_pegboard_templates() -> list[dict[str, object]]:
    return [dict(template) for template in PEGBOARD_TEMPLATES]


def get_pegboard_template(template_id: str) -> dict[str, object]:
    for template in PEGBOARD_TEMPLATES:
        if template["id"] == template_id:
            return dict(template)
    raise KeyError(template_id)
