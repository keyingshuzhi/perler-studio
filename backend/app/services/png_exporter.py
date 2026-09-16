from __future__ import annotations

from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont

from app.core.exceptions import validation_error


def _text_color(hex_color: str) -> str:
    red, green, blue = (int(hex_color[index : index + 2], 16) for index in (1, 3, 5))
    return "#FFFFFF" if (red * 299 + green * 587 + blue * 114) / 1000 < 148 else "#1B1B1B"


def _symbol(code: str, mode: str) -> str:
    return code if mode == "color_code" else code.rsplit("-", 1)[-1]


def render_pattern_png(pattern: dict[str, Any], palette: dict[str, Any], options: dict[str, Any]) -> Image.Image:
    width, height = pattern["grid_width"], pattern["grid_height"]
    cell_size = int(options.get("cell_size_px", 32))
    show_grid = bool(options.get("show_grid", True))
    show_coordinates = bool(options.get("show_coordinates", True))
    show_symbols = bool(options.get("show_symbols", True)) and options.get("symbol_mode", "color_code") != "none"
    include_legend = bool(options.get("include_legend", True))
    background = options.get("background", "white")
    grid_offset = 28 if show_coordinates else 0
    grid_width_px, grid_height_px = width * cell_size, height * cell_size
    grid_edge = 1 if show_grid else 0
    legend_width = 260 if include_legend else 0
    final_width = grid_offset + grid_width_px + grid_edge + legend_width
    final_height = grid_offset + grid_height_px + grid_edge
    if max(final_width, final_height) > 16_000 or final_width * final_height > 120_000_000:
        raise validation_error("当前 PNG 导出尺寸过大，请减小单元格尺寸或网格范围", "PNG_TOO_LARGE")
    transparent = background == "transparent"
    canvas = Image.new("RGBA", (final_width, final_height), (255, 255, 255, 0) if transparent else background)
    draw = ImageDraw.Draw(canvas)
    colors = {color["code"]: color for color in palette["colors"]}
    font = ImageFont.load_default()
    text_font = (
        ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial Unicode.ttf", max(8, cell_size // 5))
        if Path("/System/Library/Fonts/Supplemental/Arial Unicode.ttf").is_file()
        else font
    )
    cells = pattern["cells"]
    for index, code in enumerate(cells):
        if code is None:
            continue
        row, column = divmod(index, width)
        x, y = grid_offset + column * cell_size, grid_offset + row * cell_size
        color = colors[code]
        draw.rectangle((x, y, x + cell_size - 1, y + cell_size - 1), fill=color["hex"])
        if show_symbols and cell_size >= 22:
            label = _symbol(code, options.get("symbol_mode", "color_code"))
            bounds = draw.textbbox((0, 0), label, font=text_font)
            draw.text(
                (x + (cell_size - (bounds[2] - bounds[0])) / 2, y + (cell_size - (bounds[3] - bounds[1])) / 2),
                label,
                fill=_text_color(color["hex"]),
                font=text_font,
            )
    if show_grid:
        for column in range(width + 1):
            x = grid_offset + column * cell_size
            draw.line((x, grid_offset, x, grid_offset + grid_height_px), fill="#737373", width=1)
        for row in range(height + 1):
            y = grid_offset + row * cell_size
            draw.line((grid_offset, y, grid_offset + grid_width_px, y), fill="#737373", width=1)
    if show_coordinates:
        for column in range(width):
            draw.text((grid_offset + column * cell_size + 2, 4), str(column + 1), fill="#222222", font=font)
        for row in range(height):
            draw.text((3, grid_offset + row * cell_size + 2), str(row + 1), fill="#222222", font=font)
    if include_legend:
        x = grid_offset + grid_width_px + 16
        draw.text((x, 14), "Color legend", fill="#111111", font=text_font)
        y = 42
        for item in pattern["statistics"]["colors"]:
            draw.rectangle((x, y, x + 16, y + 16), fill=item["hex"], outline="#777777")
            draw.text((x + 24, y + 2), f"{item['color_code']}  × {item['count']}", fill="#222222", font=font)
            y += 22
            if y > final_height - 20:
                break
    return canvas


def export_png(pattern: dict[str, Any], palette: dict[str, Any], options: dict[str, Any], destination: Path) -> None:
    image = render_pattern_png(pattern, palette, options)
    destination.parent.mkdir(parents=True, exist_ok=True)
    image.save(destination, format="PNG", optimize=True)
