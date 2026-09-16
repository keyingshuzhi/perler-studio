from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Any

from app.core.config import Settings
from app.services.image_processor import save_png
from app.services.png_exporter import render_pattern_png
from app.services.storage_service import StorageService

PREVIEW_STYLE = "solid-gridless-v1"


def pattern_preview_is_current(pattern: dict[str, Any], settings: Settings) -> bool:
    preview_path = settings.pattern_dir / f"{pattern['id']}.png"
    return pattern.get("preview_style") == PREVIEW_STYLE and preview_path.is_file()


def save_pattern_preview(
    pattern: dict[str, Any],
    palette: dict[str, Any],
    settings: Settings,
    storage: StorageService,
    *,
    force: bool = True,
) -> bool:
    """Write the clean display preview shared by project and community pages.

    Exported production files retain their own grid/symbol options. This preview
    intentionally uses a solid background without guide lines so cards can scale
    every orientation cleanly without dense lines swallowing small cells.
    """
    preview_path = settings.pattern_dir / f"{pattern['id']}.png"
    if not force and pattern_preview_is_current(pattern, settings):
        return False

    preview = render_pattern_png(
        pattern,
        palette,
        {
            "cell_size_px": max(8, min(18, 1_800 // max(int(pattern["grid_width"]), int(pattern["grid_height"])))),
            "show_grid": False,
            "show_coordinates": False,
            "show_symbols": False,
            "include_legend": False,
            "background": "white",
        },
    )
    preview_path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{preview_path.stem}.", suffix=".png", dir=preview_path.parent
    )
    os.close(descriptor)
    temporary_path = Path(temporary_name)
    try:
        save_png(preview, temporary_path)
        os.replace(temporary_path, preview_path)
    finally:
        if temporary_path.exists():
            temporary_path.unlink()

    pattern["preview_url"] = storage.media_url(preview_path, settings.storage_dir)
    pattern["preview_style"] = PREVIEW_STYLE
    return True
