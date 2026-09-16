from __future__ import annotations

from math import ceil
from pathlib import Path
from typing import Any

from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import A3, A4, landscape, portrait
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.pdfgen import canvas

from app.core.exceptions import validation_error
from app.services.assembly_service import build_assembly_plan

_HEADER_HEIGHT = 42.0
_FOOTER_HEIGHT = 26.0
_COORDINATE_GUTTER = 19.0
_MAX_CELL_SIZE = 18.0


def _register_font() -> str:
    name = "STSong-Light"
    try:
        pdfmetrics.getFont(name)
    except KeyError:
        pdfmetrics.registerFont(UnicodeCIDFont(name))
    return name


def _balanced_ranges(total: int, capacity: int, overlap: int) -> list[tuple[int, int]]:
    """Split a dimension into similarly sized, overlapping print sections.

    Filling every page to its maximum capacity makes the final page a narrow,
    mostly blank strip. Instead we first determine the smallest required page
    count, then distribute cells (including the requested overlap) evenly.
    """
    if total <= capacity:
        return [(0, total)]
    overlap = min(max(0, overlap), max(0, capacity - 1))
    step = max(1, capacity - overlap)
    page_count = ceil((total - overlap) / step)
    distributed_cells = total + overlap * (page_count - 1)
    base, remainder = divmod(distributed_cells, page_count)
    ranges: list[tuple[int, int]] = []
    start = 0
    for index in range(page_count):
        length = base + (1 if index < remainder else 0)
        end = min(total, start + length)
        ranges.append((start, end))
        start = end - overlap
    return ranges


def _symbol(code: str, mode: str) -> str:
    return code if mode == "color_code" else code.rsplit("-", 1)[-1]


def _minimum_symbol_cell_size(palette: dict[str, Any], mode: str) -> float:
    """Return a print-safe cell size for the selected in-cell label."""
    longest_label = max((len(_symbol(color["code"], mode)) for color in palette["colors"]), default=1)
    if longest_label > 5:
        return 16.0
    if longest_label > 3:
        return 13.5
    return 11.5


def _dark(hex_color: str) -> bool:
    red, green, blue = (int(hex_color[index : index + 2], 16) for index in (1, 3, 5))
    return (red * 299 + green * 587 + blue * 114) / 1000 < 148


def _fit_text(text: str, font: str, size: float, max_width: float) -> str:
    if pdfmetrics.stringWidth(text, font, size) <= max_width:
        return text
    ellipsis = "…"
    trimmed = text
    while trimmed and pdfmetrics.stringWidth(trimmed + ellipsis, font, size) > max_width:
        trimmed = trimmed[:-1]
    return (trimmed or text[:1]) + ellipsis


def _draw_header(
    document: canvas.Canvas,
    title: str,
    font: str,
    page_width: float,
    page_height: float,
    margin: float,
    page_number: int,
    total_pages: int,
    section: str,
) -> None:
    top = page_height - margin
    document.setFillColor(HexColor("#F5F3FF"))
    document.roundRect(margin, top - 31, page_width - margin * 2, 31, 7, stroke=0, fill=1)
    document.setFillColor(HexColor("#211C48"))
    document.setFont(font, 14)
    document.drawString(margin + 11, top - 13, _fit_text(title, font, 14, page_width - margin * 2 - 210))
    document.setFont(font, 7.5)
    document.setFillColor(HexColor("#645B8B"))
    document.drawString(margin + 11, top - 24, section)
    document.setFillColor(HexColor("#E8E3FF"))
    document.roundRect(page_width - margin - 92, top - 24, 81, 15, 7.5, stroke=0, fill=1)
    document.setFillColor(HexColor("#4E3CB5"))
    document.setFont(font, 7)
    document.drawCentredString(page_width - margin - 51.5, top - 18.5, f"第 {page_number} / {total_pages} 页")


def _draw_footer(
    document: canvas.Canvas,
    pattern: dict[str, Any],
    font: str,
    page_width: float,
    margin: float,
    section: str,
) -> None:
    statistics = pattern["statistics"]
    document.setStrokeColor(HexColor("#DDD9EB"))
    document.setLineWidth(0.55)
    document.line(margin, margin + 12, page_width - margin, margin + 12)
    document.setFillColor(HexColor("#5F6680"))
    document.setFont(font, 7)
    physical_size = f"{statistics['physical_width_mm']} × {statistics['physical_height_mm']} mm"
    document.drawString(
        margin,
        margin + 2,
        f"成品 {physical_size} - {statistics['total_beads']} 颗",
    )
    document.drawRightString(page_width - margin, margin + 2, section)


def _draw_preview(
    document: canvas.Canvas,
    pattern: dict[str, Any],
    colors: dict[str, dict[str, Any]],
    x: float,
    y: float,
    size: float,
) -> None:
    width, height = int(pattern["grid_width"]), int(pattern["grid_height"])
    cell = min(size / width, size / height)
    draw_width, draw_height = width * cell, height * cell
    origin_x = x + (size - draw_width) / 2
    origin_y = y + (size - draw_height) / 2
    document.setFillColor(HexColor("#FFFFFF"))
    document.roundRect(x, y, size, size, 8, stroke=0, fill=1)
    for row in range(height):
        for column in range(width):
            code = pattern["cells"][row * width + column]
            if code is None:
                continue
            document.setFillColor(HexColor(colors[code]["hex"]))
            document.rect(origin_x + column * cell, origin_y + (height - row - 1) * cell, cell, cell, stroke=0, fill=1)
    document.setStrokeColor(HexColor("#DCD7EA"))
    document.roundRect(x, y, size, size, 8, stroke=1, fill=0)


def _draw_summary_page(
    document: canvas.Canvas,
    pattern: dict[str, Any],
    colors: dict[str, dict[str, Any]],
    font: str,
    title: str,
    page_width: float,
    page_height: float,
    margin: float,
    page_number: int,
    total_pages: int,
    chart_page_count: int,
) -> None:
    _draw_header(document, title, font, page_width, page_height, margin, page_number, total_pages, "制作总览")
    statistics = pattern["statistics"]
    preview_size = min(235.0, page_height - margin * 2 - _HEADER_HEIGHT - _FOOTER_HEIGHT - 8)
    preview_x, preview_y = margin, page_height - margin - _HEADER_HEIGHT - preview_size
    _draw_preview(document, pattern, colors, preview_x, preview_y, preview_size)
    right_x = preview_x + preview_size + 24
    right_width = page_width - margin - right_x
    document.setFillColor(HexColor("#1E2843"))
    document.setFont(font, 16)
    document.drawString(right_x, page_height - margin - _HEADER_HEIGHT - 7, "拼豆制作说明")
    document.setFillColor(HexColor("#6A728B"))
    document.setFont(font, 8)
    document.drawString(
        right_x, page_height - margin - _HEADER_HEIGHT - 22, "按图纸分页编号逐页拼装；相邻页面保留边缘重叠格便于衔接。"
    )

    cards = [
        ("网格", f"{statistics['grid_width']} × {statistics['grid_height']} 格"),
        ("成品尺寸", f"{statistics['physical_width_mm']} × {statistics['physical_height_mm']} mm"),
        ("拼豆总数", f"{statistics['total_beads']:,} 颗"),
        ("使用颜色", f"{statistics['used_color_count']} 色 - 图纸 {chart_page_count} 页"),
    ]
    card_width = (right_width - 10) / 2
    card_top = page_height - margin - _HEADER_HEIGHT - 49
    for index, (label, value) in enumerate(cards):
        x = right_x + (index % 2) * (card_width + 10)
        y = card_top - (index // 2) * 56
        document.setFillColor(HexColor("#F5F3FF"))
        document.roundRect(x, y - 44, card_width, 44, 7, stroke=0, fill=1)
        document.setFillColor(HexColor("#7467BE"))
        document.setFont(font, 7)
        document.drawString(x + 9, y - 13, label)
        document.setFillColor(HexColor("#2A3452"))
        document.setFont(font, 10)
        document.drawString(x + 9, y - 29, _fit_text(value, font, 10, card_width - 18))

    instructions_y = card_top - 132
    document.setFillColor(HexColor("#1E2843"))
    document.setFont(font, 10)
    document.drawString(right_x, instructions_y, "使用建议")
    document.setFillColor(HexColor("#65708B"))
    document.setFont(font, 8)
    instructions = [
        "1. 先准备材料清单中的拼豆数量（已包含设定损耗）。",
        "2. 按每页行列范围拼装，先完成轮廓与高对比区域。",
        "3. 仅在同色块内部连续铺放；跨页时使用重叠行列核对。",
    ]
    for index, instruction in enumerate(instructions):
        document.drawString(right_x, instructions_y - 17 - index * 16, instruction)
    _draw_footer(document, pattern, font, page_width, margin, "总览")
    document.showPage()


def _draw_material_pages(
    document: canvas.Canvas,
    pattern: dict[str, Any],
    font: str,
    title: str,
    page_width: float,
    page_height: float,
    margin: float,
    first_page_number: int,
    total_pages: int,
) -> int:
    materials = sorted(pattern["statistics"]["colors"], key=lambda item: str(item["color_code"]))
    if not materials:
        return 0
    columns, rows_per_column = 3, 22
    per_page = columns * rows_per_column
    page_count = ceil(len(materials) / per_page)
    content_width = page_width - margin * 2
    base_page_count, page_remainder = divmod(len(materials), page_count)
    material_start = 0
    for page_offset in range(page_count):
        page_number = first_page_number + page_offset
        page_item_count = base_page_count + (1 if page_offset < page_remainder else 0)
        page_materials = materials[material_start : material_start + page_item_count]
        material_start += page_item_count
        used_columns = min(columns, len(page_materials))
        column_width = (content_width - (used_columns - 1) * 10) / used_columns
        base_column_count, column_remainder = divmod(len(page_materials), used_columns)
        _draw_header(document, title, font, page_width, page_height, margin, page_number, total_pages, "完整材料清单")
        document.setFillColor(HexColor("#66708A"))
        document.setFont(font, 8)
        document.drawString(
            margin, page_height - margin - _HEADER_HEIGHT - 6, "色号、名称和数量；数量已按当前损耗率计算。"
        )
        material_index = 0
        for column in range(used_columns):
            x = margin + column * (column_width + 10)
            top = page_height - margin - _HEADER_HEIGHT - 26
            document.setFillColor(HexColor("#F5F3FF"))
            document.roundRect(x, top - 17, column_width, 17, 5, stroke=0, fill=1)
            document.setFillColor(HexColor("#51458F"))
            document.setFont(font, 7)
            document.drawString(x + 7, top - 11, "色号 / 名称")
            document.drawRightString(x + column_width - 7, top - 11, "准备数量")
            column_item_count = base_column_count + (1 if column < column_remainder else 0)
            for row in range(column_item_count):
                item = page_materials[material_index]
                material_index += 1
                y = top - 27 - row * 17
                document.setStrokeColor(HexColor("#E8E5EF"))
                document.line(x, y - 5, x + column_width, y - 5)
                document.setFillColor(HexColor(item["hex"]))
                document.rect(x + 2, y, 8, 8, stroke=1, fill=1)
                document.setFillColor(HexColor("#33405E"))
                document.setFont("Helvetica-Bold", 7)
                document.drawString(x + 15, y + 1, str(item["color_code"]))
                document.setFont(font, 6.5)
                name = str(item.get("color_name") or "")
                document.drawString(x + 47, y + 1, _fit_text(name, font, 6.5, column_width - 107))
                document.setFont(font, 7)
                quantity = item.get("count_with_waste", item["count"])
                document.drawRightString(x + column_width - 2, y + 1, f"{quantity} 颗")
        _draw_footer(document, pattern, font, page_width, margin, "材料清单")
        document.showPage()
    return page_count


def _draw_chart_page(
    document: canvas.Canvas,
    pattern: dict[str, Any],
    colors: dict[str, dict[str, Any]],
    font: str,
    title: str,
    page_width: float,
    page_height: float,
    margin: float,
    page_number: int,
    total_pages: int,
    row_range: tuple[int, int],
    column_range: tuple[int, int],
    cell_size: float,
    show_grid: bool,
    show_coordinates: bool,
    show_symbols: bool,
    symbol_mode: str,
) -> None:
    start_row, end_row = row_range
    start_column, end_column = column_range
    grid_width = int(pattern["grid_width"])
    row_count, column_count = end_row - start_row, end_column - start_column
    available_width = page_width - margin * 2 - (0 if not show_coordinates else _COORDINATE_GUTTER)
    available_height = page_height - margin * 2 - _HEADER_HEIGHT - _FOOTER_HEIGHT
    draw_width, draw_height = column_count * cell_size, row_count * cell_size
    origin_x = margin + (_COORDINATE_GUTTER if show_coordinates else 0) + (available_width - draw_width) / 2
    origin_y = page_height - margin - _HEADER_HEIGHT - (available_height - draw_height) / 2
    section = f"行 {start_row + 1}-{end_row} - 列 {start_column + 1}-{end_column}"
    _draw_header(document, title, font, page_width, page_height, margin, page_number, total_pages, section)

    for row in range(start_row, end_row):
        for column in range(start_column, end_column):
            code = pattern["cells"][row * grid_width + column]
            if code is None:
                continue
            x = origin_x + (column - start_column) * cell_size
            y = origin_y - (row - start_row + 1) * cell_size
            document.setFillColor(HexColor(colors[code]["hex"]))
            document.rect(x, y, cell_size, cell_size, stroke=0, fill=1)

    if show_grid:
        document.setStrokeColor(HexColor("#7D8090"))
        document.setLineWidth(0.28 if cell_size >= 12 else 0.22)
        for offset in range(column_count + 1):
            x = origin_x + offset * cell_size
            document.line(x, origin_y, x, origin_y - draw_height)
        for offset in range(row_count + 1):
            y = origin_y - offset * cell_size
            document.line(origin_x, y, origin_x + draw_width, y)

    if show_symbols:
        for row in range(start_row, end_row):
            for column in range(start_column, end_column):
                code = pattern["cells"][row * grid_width + column]
                if code is None:
                    continue
                label = _symbol(code, symbol_mode)
                x = origin_x + (column - start_column) * cell_size
                y = origin_y - (row - start_row + 1) * cell_size
                font_size = min(8.2, max(5.6, cell_size * (0.42 if len(label) <= 3 else 0.30)))
                document.setFillColor(HexColor("#FFFFFF") if _dark(colors[code]["hex"]) else HexColor("#1B2134"))
                document.setFont("Helvetica-Bold", font_size)
                document.drawCentredString(x + cell_size / 2, y + (cell_size - font_size) / 2 + 0.55, label)

    if show_coordinates:
        document.setFillColor(HexColor("#4F5872"))
        document.setFont("Helvetica", min(7.0, max(5.2, cell_size * 0.46)))
        for column in range(start_column, end_column):
            document.drawCentredString(
                origin_x + (column - start_column + 0.5) * cell_size, origin_y + 5.5, str(column + 1)
            )
        for row in range(start_row, end_row):
            document.drawRightString(origin_x - 4.5, origin_y - (row - start_row + 0.67) * cell_size, str(row + 1))
    _draw_footer(document, pattern, font, page_width, margin, section)
    document.showPage()


def _assembly_order(boards: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[int, list[dict[str, Any]]] = {}
    for board in boards:
        grouped.setdefault(int(board["row"]), []).append(board)
    ordered: list[dict[str, Any]] = []
    for row in sorted(grouped):
        sequence = sorted(grouped[row], key=lambda board: int(board["column"]))
        ordered.extend(sequence if row % 2 else list(reversed(sequence)))
    return ordered


def _draw_assembly_pages(
    document: canvas.Canvas,
    pattern: dict[str, Any],
    font: str,
    title: str,
    page_width: float,
    page_height: float,
    margin: float,
    first_page_number: int,
    total_pages: int,
    board_width: int,
    board_height: int,
    overlap: int,
) -> int:
    """Add physical board layout, installation sequence and coordinate ranges."""
    plan = build_assembly_plan(pattern, board_width, board_height, overlap)
    ordered = _assembly_order(plan["boards"])
    page_count = max(1, ceil(len(ordered) / 24))
    for page_offset in range(page_count):
        page_number = first_page_number + page_offset
        _draw_header(
            document, title, font, page_width, page_height, margin, page_number, total_pages, "底板布局与装配说明"
        )
        top = page_height - margin - _HEADER_HEIGHT - 14
        document.setFillColor(HexColor("#1E2843"))
        document.setFont(font, 10)
        document.drawString(margin, top, f"{board_width} × {board_height} 方形底板 · 共 {plan['board_count']} 块")
        document.setFillColor(HexColor("#65708B"))
        document.setFont(font, 7.5)
        document.drawString(
            margin,
            top - 13,
            f"按蛇形顺序装配；每块保留原图坐标。{' 相邻边重叠 ' + str(overlap) + ' 格用于校准。' if overlap else ''}",
        )

        map_top = top - 29
        map_height = min(104.0, page_height * 0.17)
        map_width = min(300.0, page_width - margin * 2)
        cell = min(map_width / plan["board_columns"], map_height / plan["board_rows"])
        draw_height = cell * plan["board_rows"]
        map_x = margin
        map_y = map_top - draw_height
        sequence_number = {board["id"]: index for index, board in enumerate(ordered, start=1)}
        for board in plan["boards"]:
            x = map_x + (int(board["column"]) - 1) * cell
            y = map_y + (plan["board_rows"] - int(board["row"])) * cell
            document.setFillColor(HexColor("#F5F3FF"))
            document.roundRect(x + 1, y + 1, cell - 2, cell - 2, min(4, cell / 6), stroke=0, fill=1)
            document.setStrokeColor(HexColor("#CFC5F1"))
            document.roundRect(x + 1, y + 1, cell - 2, cell - 2, min(4, cell / 6), stroke=1, fill=0)
            document.setFillColor(HexColor("#5041A5"))
            document.setFont("Helvetica-Bold", min(8, max(4.8, cell * 0.22)))
            document.drawCentredString(x + cell / 2, y + cell / 2 + 1, str(board["id"]))
            document.setFillColor(HexColor("#7569BA"))
            document.setFont("Helvetica", min(5.8, max(3.8, cell * 0.15)))
            document.drawCentredString(x + cell / 2, y + cell / 2 - cell * 0.20, str(sequence_number[board["id"]]))

        chunk = ordered[page_offset * 24 : (page_offset + 1) * 24]
        list_top = map_y - 20
        document.setFillColor(HexColor("#1E2843"))
        document.setFont(font, 9)
        document.drawString(margin, list_top, "安装顺序与坐标范围")
        column_width = (page_width - margin * 2 - 12) / 2
        for index, board in enumerate(chunk):
            column, row = divmod(index, 12)
            x = margin + column * (column_width + 12)
            y = list_top - 17 - row * 17
            document.setStrokeColor(HexColor("#E8E5EF"))
            document.line(x, y - 4, x + column_width, y - 4)
            ordinal = page_offset * 24 + index + 1
            document.setFillColor(HexColor("#5C4CC0"))
            document.setFont("Helvetica-Bold", 7)
            document.drawString(x, y, f"{ordinal:02d}  {board['id']}")
            document.setFillColor(HexColor("#58647A"))
            document.setFont(font, 6.8)
            coordinate_range = (
                f"行 {board['row_range'][0]}–{board['row_range'][1]} · "
                f"列 {board['column_range'][0]}–{board['column_range'][1]}"
            )
            document.drawString(x + 43, y, coordinate_range)
        _draw_footer(document, pattern, font, page_width, margin, "底板装配")
        document.showPage()
    return page_count


def export_pdf(pattern: dict[str, Any], palette: dict[str, Any], options: dict[str, Any], destination: Path) -> None:
    page_size = A4 if options.get("paper_size", "A4") == "A4" else A3
    page_size = landscape(page_size) if options.get("orientation", "landscape") == "landscape" else portrait(page_size)
    page_width, page_height = page_size
    margin = float(options.get("margin_mm", 10)) * mm
    grid_width, grid_height = int(pattern["grid_width"]), int(pattern["grid_height"])
    symbol_mode = str(options.get("symbol_mode", "short_code"))
    show_symbols = bool(options.get("show_symbols", True)) and symbol_mode != "none"
    show_coordinates = bool(options.get("show_coordinates", True))
    show_grid = bool(options.get("show_grid", True))
    is_guide = options.get("mode", "multipage") == "guide"
    is_multipage = options.get("mode", "multipage") == "multipage" or is_guide
    minimum_cell_size = _minimum_symbol_cell_size(palette, symbol_mode) if show_symbols else 7.0
    coordinate_gutter = _COORDINATE_GUTTER if show_coordinates else 0
    available_width = page_width - margin * 2 - coordinate_gutter
    available_height = page_height - margin * 2 - _HEADER_HEIGHT - _FOOTER_HEIGHT
    if available_width <= 0 or available_height <= 0:
        raise validation_error("页边距过大，无法容纳图纸内容", "PDF_MARGIN_TOO_LARGE")

    if not is_multipage:
        cell_size = min(available_width / grid_width, available_height / grid_height)
        if cell_size < minimum_cell_size:
            message = "单页纸张无法容纳可读的格内色号，请改用多页导出或关闭色号"
            raise validation_error(message, "PDF_SINGLE_PAGE_TOO_DENSE")
        column_ranges, row_ranges = [(0, grid_width)], [(0, grid_height)]
    else:
        cells_x = max(1, int(available_width // minimum_cell_size))
        cells_y = max(1, int(available_height // minimum_cell_size))
        overlap = int(options.get("overlap_cells", 1))
        column_ranges = _balanced_ranges(grid_width, cells_x, overlap)
        row_ranges = _balanced_ranges(grid_height, cells_y, overlap)
        widest = max(end - start for start, end in column_ranges)
        tallest = max(end - start for start, end in row_ranges)
        cell_size = min(_MAX_CELL_SIZE, available_width / widest, available_height / tallest)

    chart_sections = [(row_range, column_range) for row_range in row_ranges for column_range in column_ranges]
    if len(chart_sections) > 500:
        raise validation_error("分页数量过多，请增大单元格容量或缩小图纸", "PDF_TOO_MANY_PAGES")
    include_statistics = bool(options.get("include_statistics", True)) and is_multipage
    include_legend = bool(options.get("include_legend", True)) and is_multipage
    materials = pattern["statistics"]["colors"]
    legend_page_count = ceil(len(materials) / 66) if include_legend else 0
    summary_page_count = 1 if include_statistics else 0
    assembly_plan = (
        build_assembly_plan(
            pattern,
            int(options.get("assembly_board_width", 29)),
            int(options.get("assembly_board_height", 29)),
            int(options.get("assembly_overlap", 0)),
        )
        if is_guide
        else None
    )
    assembly_page_count = max(1, ceil(len(assembly_plan["boards"]) / 24)) if assembly_plan else 0
    total_pages = summary_page_count + assembly_page_count + legend_page_count + len(chart_sections)
    destination.parent.mkdir(parents=True, exist_ok=True)
    document = canvas.Canvas(str(destination), pagesize=page_size, pageCompression=1)
    document.setTitle(str(options.get("title") or "Perler Studio 图纸"))
    document.setAuthor("Perler Studio")
    font = _register_font()
    colors = {color["code"]: color for color in palette["colors"]}
    title = str(options.get("title") or f"图纸 {pattern['id'][-8:]}")
    page_number = 1

    if include_statistics:
        _draw_summary_page(
            document,
            pattern,
            colors,
            font,
            title,
            page_width,
            page_height,
            margin,
            page_number,
            total_pages,
            len(chart_sections),
        )
        page_number += 1
    if is_guide:
        page_number += _draw_assembly_pages(
            document,
            pattern,
            font,
            title,
            page_width,
            page_height,
            margin,
            page_number,
            total_pages,
            int(options.get("assembly_board_width", 29)),
            int(options.get("assembly_board_height", 29)),
            int(options.get("assembly_overlap", 0)),
        )
    if include_legend:
        page_number += _draw_material_pages(
            document,
            pattern,
            font,
            title,
            page_width,
            page_height,
            margin,
            page_number,
            total_pages,
        )
    for row_range, column_range in chart_sections:
        _draw_chart_page(
            document,
            pattern,
            colors,
            font,
            title,
            page_width,
            page_height,
            margin,
            page_number,
            total_pages,
            row_range,
            column_range,
            cell_size,
            show_grid,
            show_coordinates,
            show_symbols,
            symbol_mode,
        )
        page_number += 1
    document.save()
