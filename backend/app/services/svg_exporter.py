from __future__ import annotations

from html import escape
from pathlib import Path
from typing import Any, TextIO

from app.core.exceptions import validation_error

_MAX_SVG_CELLS = 250_000


def _escape(value: object) -> str:
    return escape(str(value), quote=True)


def _is_dark(hex_color: str) -> bool:
    red, green, blue = (int(hex_color[index : index + 2], 16) for index in (1, 3, 5))
    return (red * 299 + green * 587 + blue * 114) / 1000 < 148


def _symbol(code: str, mode: str) -> str:
    return code if mode == "color_code" else code.rsplit("-", 1)[-1]


def _write_grid_lines(handle: TextIO, x: int, y: int, width: int, height: int, cell_size: int) -> None:
    commands = [f"M{x + offset * cell_size} {y}V{y + height * cell_size}" for offset in range(width + 1)]
    commands.extend(f"M{x} {y + offset * cell_size}H{x + width * cell_size}" for offset in range(height + 1))
    handle.write(f'<path d="{" ".join(commands)}" fill="none" stroke="#737373" stroke-width="1"/>\n')


def export_svg(pattern: dict[str, Any], palette: dict[str, Any], options: dict[str, Any], destination: Path) -> None:
    """Export a self-contained, scalable SVG pattern without rasterisation."""
    width, height = int(pattern["grid_width"]), int(pattern["grid_height"])
    if width * height > _MAX_SVG_CELLS:
        raise validation_error("当前 SVG 网格过大，请将图纸控制在 250,000 格以内", "SVG_TOO_LARGE")

    cell_size = int(options.get("cell_size_px", 32))
    show_grid = bool(options.get("show_grid", True))
    show_coordinates = bool(options.get("show_coordinates", True))
    symbol_mode = str(options.get("symbol_mode", "color_code"))
    show_symbols = bool(options.get("show_symbols", True)) and symbol_mode != "none"
    include_legend = bool(options.get("include_legend", True))
    coordinate_offset = 30 if show_coordinates else 0
    colors = {color["code"]: color for color in palette["colors"]}
    statistics = pattern["statistics"]
    legend_width = 250 if include_legend else 0
    grid_width_px, grid_height_px = width * cell_size, height * cell_size
    legend_height = 56 + len(statistics["colors"]) * 22 if include_legend else 0
    canvas_width = coordinate_offset + grid_width_px + legend_width
    canvas_height = max(coordinate_offset + grid_height_px, legend_height)
    background = str(options.get("background", "white"))
    symbol_font_size = max(7, min(18, cell_size * (0.21 if symbol_mode == "color_code" else 0.3)))

    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write('<?xml version="1.0" encoding="UTF-8"?>\n')
        handle.write(
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{canvas_width}" height="{canvas_height}" '
            f'viewBox="0 0 {canvas_width} {canvas_height}" role="img" aria-labelledby="title desc">\n'
        )
        handle.write(f'<title id="title">Perler Studio 图纸 {_escape(pattern["id"])}</title>\n')
        handle.write(f'<desc id="desc">{width} × {height} 拼豆图纸，{statistics["total_beads"]} 颗拼豆。</desc>\n')
        if background != "transparent":
            handle.write(f'<rect width="100%" height="100%" fill="{_escape(background)}"/>\n')
        handle.write('<g shape-rendering="crispEdges">\n')
        for index, code in enumerate(pattern["cells"]):
            if code is None:
                continue
            color = colors.get(code)
            if color is None:
                raise validation_error(f"图纸引用了不存在的色号: {code}", "UNKNOWN_PATTERN_COLOR")
            row, column = divmod(index, width)
            x, y = coordinate_offset + column * cell_size, coordinate_offset + row * cell_size
            handle.write(
                f'<rect class="cell" data-code="{_escape(code)}" x="{x}" y="{y}" width="{cell_size}" '
                f'height="{cell_size}" fill="{_escape(color["hex"])}"/>\n'
            )
        if show_grid:
            _write_grid_lines(handle, coordinate_offset, coordinate_offset, width, height, cell_size)
        handle.write("</g>\n")

        if show_symbols:
            handle.write(
                f'<g text-anchor="middle" dominant-baseline="central" font-family="Arial, sans-serif" '
                f'font-size="{symbol_font_size:.2f}" font-weight="600">\n'
            )
            for index, code in enumerate(pattern["cells"]):
                if code is None:
                    continue
                color = colors[code]
                row, column = divmod(index, width)
                x = coordinate_offset + (column + 0.5) * cell_size
                y = coordinate_offset + (row + 0.5) * cell_size
                text_color = "#FFFFFF" if _is_dark(color["hex"]) else "#1D1D1D"
                label = _escape(_symbol(code, symbol_mode))
                handle.write(f'<text x="{x:.2f}" y="{y:.2f}" fill="{text_color}">{label}</text>\n')
            handle.write("</g>\n")

        if show_coordinates:
            handle.write('<g fill="#262626" font-family="Arial, sans-serif" font-size="11" text-anchor="middle">\n')
            for column in range(width):
                x = coordinate_offset + (column + 0.5) * cell_size
                handle.write(f'<text x="{x:.2f}" y="18">{column + 1}</text>\n')
            handle.write('<g text-anchor="end" dominant-baseline="central">\n')
            for row in range(height):
                y = coordinate_offset + (row + 0.5) * cell_size
                handle.write(f'<text x="{coordinate_offset - 6}" y="{y:.2f}">{row + 1}</text>\n')
            handle.write("</g></g>\n")

        if include_legend:
            legend_x = coordinate_offset + grid_width_px + 18
            handle.write('<g font-family="Arial, sans-serif" fill="#222222">\n')
            handle.write(f'<text x="{legend_x}" y="24" font-size="16" font-weight="700">材料清单</text>\n')
            legend_summary = f"{width} × {height} · {statistics['total_beads']} 颗"
            handle.write(f'<text x="{legend_x}" y="43" font-size="11">{legend_summary}</text>\n')
            for index, item in enumerate(statistics["colors"]):
                y = 62 + index * 22
                color_hex = _escape(item["hex"])
                legend_label = _escape(f"{item['color_code']} × {item['count']}")
                handle.write(
                    f'<rect x="{legend_x}" y="{y}" width="14" height="14" fill="{color_hex}" stroke="#777"/>\n'
                )
                handle.write(f'<text x="{legend_x + 22}" y="{y + 11}" font-size="12">{legend_label}</text>\n')
            handle.write("</g>\n")
        handle.write("</svg>\n")
