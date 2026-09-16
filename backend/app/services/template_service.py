from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.core.exceptions import validation_error


@dataclass(frozen=True)
class TemplateDefinition:
    id: str
    name_zh: str
    category: str
    description: str
    rows: tuple[str, ...]

    @property
    def width(self) -> int:
        return len(self.rows[0])

    @property
    def height(self) -> int:
        return len(self.rows)


TEMPLATES: tuple[TemplateDefinition, ...] = (
    TemplateDefinition(
        "heart-charm",
        "心形挂件",
        "挂件",
        "适合钥匙扣、包挂和告白小礼物。",
        (
            "....AA....",
            ".AAAAAAAA.",
            "AAAAAAAAAA",
            "AAAAAAAAAA",
            ".AAAAAAAA.",
            "..AAAAAA..",
            "...AAAA...",
            "....AA....",
        ),
    ),
    TemplateDefinition(
        "star-charm",
        "星星挂件",
        "挂件",
        "带高光的五角星小吊饰。",
        (
            ".....B.....",
            "....BBB....",
            "AAAAAAAAAAA",
            ".AAAAAAAAA.",
            "..AAAAAAA..",
            "..AA...AA..",
            ".AA.....AA.",
        ),
    ),
    TemplateDefinition(
        "smile-badge",
        "笑脸徽章",
        "徽章",
        "16 格圆角徽章，适合胸针和磁贴。",
        (
            "....AAAAAAAA....",
            ".AAAAAAAAAAAAAA.",
            ".AAAAAAAAAAAAAA.",
            "AAAAAAAAAAAAAAAA",
            "AAAAAAAAAAAAAAAA",
            "AAAAAAAAAAAAAAAA",
            "AAAA..AAAA..AAAA",
            "AAAA..AAAA..AAAA",
            "AAAAAAAAAAAAAAAA",
            "AAA..BBBBBB..AAA",
            "AAAA.BBBBBB.AAAA",
            "AAAAAAAAAAAAAAAA",
            "AAAAAAAAAAAAAAAA",
            ".AAAAAAAAAAAAAA.",
            ".AAAAAAAAAAAAAA.",
            "....AAAAAAAA....",
        ),
    ),
    TemplateDefinition(
        "flower-coaster",
        "花朵杯垫",
        "杯垫",
        "双色花朵中心，适合从 29×29 底板开始扩展。",
        (
            "....AA....",
            "...AAAA...",
            "..AABBAA..",
            ".AABBBBAA.",
            "AABBBBBBAA",
            ".AABBBBAA.",
            "..AABBAA..",
            "...AAAA...",
            "....AA....",
        ),
    ),
)


_FONT: dict[str, tuple[str, ...]] = {
    "A": ("010", "101", "111", "101", "101"),
    "B": ("110", "101", "110", "101", "110"),
    "C": ("011", "100", "100", "100", "011"),
    "D": ("110", "101", "101", "101", "110"),
    "E": ("111", "100", "110", "100", "111"),
    "F": ("111", "100", "110", "100", "100"),
    "G": ("011", "100", "101", "101", "011"),
    "H": ("101", "101", "111", "101", "101"),
    "I": ("111", "010", "010", "010", "111"),
    "J": ("001", "001", "001", "101", "010"),
    "K": ("101", "101", "110", "101", "101"),
    "L": ("100", "100", "100", "100", "111"),
    "M": ("101", "111", "111", "101", "101"),
    "N": ("101", "111", "111", "111", "101"),
    "O": ("010", "101", "101", "101", "010"),
    "P": ("110", "101", "110", "100", "100"),
    "Q": ("010", "101", "101", "011", "001"),
    "R": ("110", "101", "110", "101", "101"),
    "S": ("011", "100", "010", "001", "110"),
    "T": ("111", "010", "010", "010", "010"),
    "U": ("101", "101", "101", "101", "111"),
    "V": ("101", "101", "101", "101", "010"),
    "W": ("101", "101", "111", "111", "101"),
    "X": ("101", "101", "010", "101", "101"),
    "Y": ("101", "101", "010", "010", "010"),
    "Z": ("111", "001", "010", "100", "111"),
    "0": ("111", "101", "101", "101", "111"),
    "1": ("010", "110", "010", "010", "111"),
    "2": ("110", "001", "111", "100", "111"),
    "3": ("110", "001", "011", "001", "110"),
    "4": ("101", "101", "111", "001", "001"),
    "5": ("111", "100", "110", "001", "110"),
    "6": ("011", "100", "111", "101", "111"),
    "7": ("111", "001", "010", "010", "010"),
    "8": ("111", "101", "111", "101", "111"),
    "9": ("111", "101", "111", "001", "110"),
    "!": ("010", "010", "010", "000", "010"),
    "?": ("110", "001", "010", "000", "010"),
    "-": ("000", "000", "111", "000", "000"),
    " ": ("000", "000", "000", "000", "000"),
}


def list_templates() -> list[dict[str, Any]]:
    return [
        {
            "id": template.id,
            "name_zh": template.name_zh,
            "category": template.category,
            "description": template.description,
            "grid_width": template.width,
            "grid_height": template.height,
            "preview": list(template.rows),
        }
        for template in TEMPLATES
    ]


def render_template(template_id: str, foreground: str, accent: str) -> tuple[int, int, list[str | None]]:
    template = next((item for item in TEMPLATES if item.id == template_id), None)
    if template is None:
        raise validation_error("未找到该创作模板", "TEMPLATE_NOT_FOUND")
    cells = [
        foreground if symbol == "A" else accent if symbol == "B" else None for row in template.rows for symbol in row
    ]
    return template.width, template.height, cells


def render_text(text: str, style: str, foreground: str, accent: str) -> tuple[int, int, list[str | None], str]:
    normalized = text.upper().replace("♥", "?")
    glyphs = [_FONT.get(character, _FONT["?"]) for character in normalized]
    text_width = sum(3 for _ in glyphs) + max(0, len(glyphs) - 1)
    width = max(8, text_width + 4)
    height = 11 if style == "keychain" else 9
    cells: list[str | None] = [None] * (width * height)
    text_top = 4 if style == "keychain" else 2
    left = (width - text_width) // 2

    if style == "keychain":
        center = width // 2
        for row, columns in (
            (0, (center - 1, center, center + 1)),
            (1, (center - 1, center + 1)),
            (2, (center - 1, center, center + 1)),
        ):
            for column in columns:
                cells[row * width + column] = accent
    else:
        for column in range(1, width - 1):
            cells[column] = accent
            cells[(height - 1) * width + column] = accent
        for row in range(1, height - 1):
            cells[row * width] = accent
            cells[row * width + width - 1] = accent

    cursor = left
    for glyph in glyphs:
        for row, pixels in enumerate(glyph):
            for column, filled in enumerate(pixels):
                if filled == "1":
                    cells[(text_top + row) * width + cursor + column] = foreground
        cursor += 4
    return width, height, cells, normalized
