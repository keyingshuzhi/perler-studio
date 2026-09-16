from __future__ import annotations

import numpy as np
import pytest
from PIL import Image

from app.core.config import Settings
from app.schemas.palette import PaletteCreate, PaletteUpdate
from app.schemas.pattern import CleanupLevel, DistanceMethod, PatternGenerateRequest, ResizeMode, SamplingMode
from app.services.assembly_service import build_assembly_plan
from app.services.color_matcher import ColorMatcher, _delta_e_2000, rgb_to_lab
from app.services.color_report_service import calculate_color_report
from app.services.conversion_diagnostics import calculate_conversion_diagnostics
from app.services.grid_generator import resize_to_grid
from app.services.image_processor import prepare_conversion_image
from app.services.palette_service import PaletteService
from app.services.pattern_preview import PREVIEW_STYLE, save_pattern_preview
from app.services.pattern_service import PatternService
from app.services.pdf_exporter import _balanced_ranges
from app.services.png_exporter import render_pattern_png
from app.services.production_service import build_production_plan
from app.services.statistics_service import calculate_statistics
from app.services.storage_service import StorageService
from app.services.structure_analyzer import analyze_structure
from app.services.template_service import list_templates, render_template, render_text

PALETTE = {
    "id": "test",
    "colors": [
        {"code": "W", "name_zh": "白", "name_en": "White", "hex": "#FFFFFF", "rgb": [255, 255, 255], "available": True},
        {"code": "K", "name_zh": "黑", "name_en": "Black", "hex": "#000000", "rgb": [0, 0, 0], "available": True},
        {"code": "R", "name_zh": "红", "name_en": "Red", "hex": "#FF0000", "rgb": [255, 0, 0], "available": True},
    ],
}


def test_png_renderer_preserves_complete_cells_and_the_outer_grid_edge() -> None:
    pattern = {"grid_width": 2, "grid_height": 1, "cells": ["R", "K"], "statistics": {"colors": []}}
    options = {
        "cell_size_px": 4,
        "show_grid": True,
        "show_coordinates": False,
        "show_symbols": False,
        "include_legend": False,
        "background": "white",
    }

    gridded = render_pattern_png(pattern, PALETTE, options)
    clean = render_pattern_png(pattern, PALETTE, {**options, "show_grid": False})

    assert gridded.size == (9, 5)
    assert gridded.getpixel((8, 4))[:3] == (115, 115, 115)
    assert gridded.getpixel((3, 3))[:3] == (255, 0, 0)
    assert gridded.getpixel((5, 3))[:3] == (0, 0, 0)
    assert clean.size == (8, 4)
    assert clean.getpixel((3, 3))[:3] == (255, 0, 0)
    assert clean.getpixel((4, 3))[:3] == (0, 0, 0)


def test_display_preview_is_solid_gridless_and_upgrades_an_old_style(tmp_path) -> None:
    settings = Settings(data_dir=tmp_path)
    storage = StorageService(settings)
    pattern = {
        "id": "pat_0123456789ab",
        "grid_width": 2,
        "grid_height": 1,
        "cells": ["R", "K"],
        "statistics": {"colors": []},
    }

    assert save_pattern_preview(pattern, PALETTE, settings, storage)
    preview_path = settings.pattern_dir / "pat_0123456789ab.png"
    with Image.open(preview_path) as preview:
        assert preview.size == (36, 18)
        assert preview.getpixel((17, 17))[:3] == (255, 0, 0)
        assert preview.getpixel((18, 17))[:3] == (0, 0, 0)
    assert pattern["preview_style"] == PREVIEW_STYLE
    assert not save_pattern_preview(pattern, PALETTE, settings, storage, force=False)

    pattern["preview_style"] = "legacy-grid"
    assert save_pattern_preview(pattern, PALETTE, settings, storage, force=False)


def test_contain_grid_keeps_transparent_padding() -> None:
    source = Image.new("RGBA", (4, 2), "red")
    result = resize_to_grid(source, 4, 4, ResizeMode.contain)
    assert result.size == (4, 4)
    assert np.asarray(result)[0, 0, 3] == 0
    assert np.asarray(result)[1, 0, 3] == 255


def test_edge_aware_sampling_uses_an_observed_colour_instead_of_a_blended_edge() -> None:
    pixels = np.full((3, 6, 4), (255, 0, 0, 255), dtype=np.uint8)
    pixels[:2, :2, :3] = (0, 0, 255)
    source = Image.fromarray(pixels, "RGBA")
    result = np.asarray(resize_to_grid(source, 2, 1, ResizeMode.stretch, SamplingMode.edge_aware))
    assert tuple(result[0, 0, :3]) == (255, 0, 0)


def test_adaptive_sampling_uses_linear_light_for_a_smooth_cell() -> None:
    pixels = np.zeros((3, 3, 4), dtype=np.uint8)
    pixels[..., 3] = 255
    pixels[..., :3] = np.array([[0, 10, 20], [10, 20, 30], [20, 30, 40]], dtype=np.uint8)[..., None]
    source = Image.fromarray(pixels, "RGBA")
    adaptive = np.asarray(resize_to_grid(source, 1, 1, ResizeMode.stretch, SamplingMode.adaptive))
    edge_aware = np.asarray(resize_to_grid(source, 1, 1, ResizeMode.stretch, SamplingMode.edge_aware))
    assert tuple(adaptive[0, 0, :3]) == (22, 22, 22)
    assert tuple(edge_aware[0, 0, :3]) == (20, 20, 20)


def test_adaptive_sampling_preserves_a_centred_high_contrast_detail() -> None:
    pixels = np.full((3, 3, 4), (255, 255, 255, 255), dtype=np.uint8)
    pixels[1, 1, :3] = (0, 0, 0)
    source = Image.fromarray(pixels, "RGBA")

    result = np.asarray(resize_to_grid(source, 1, 1, ResizeMode.stretch, SamplingMode.adaptive))

    assert tuple(result[0, 0, :3]) == (0, 0, 0)
    assert result[0, 0, 3] == 255


def test_color_matching_honours_disabled_and_transparency() -> None:
    rgba = np.array([[[255, 0, 0, 255], [255, 255, 255, 0]]], dtype=np.uint8)
    result = ColorMatcher().match(
        rgba, PALETTE, DistanceMethod.ciede2000, disabled_colors=["K"], transparent_background=True
    )
    assert result.cells == ["R", None]


def test_perceptual_matching_prefers_measured_lab_while_rgb_mode_keeps_screen_semantics() -> None:
    source_rgb = np.asarray([[255, 0, 0]], dtype=np.float64)
    source_lab = rgb_to_lab(source_rgb)[0].tolist()
    blue_lab = rgb_to_lab(np.asarray([[0, 0, 255]], dtype=np.float64))[0].tolist()
    palette = {
        "id": "measured-match",
        "colors": [
            {"code": "SCREEN", "rgb": [255, 0, 0], "measured_lab": blue_lab, "available": True},
            {"code": "PHYSICAL", "rgb": [0, 0, 255], "measured_lab": source_lab, "available": True},
        ],
    }
    rgba = np.asarray([[[255, 0, 0, 255]]], dtype=np.uint8)

    perceptual = ColorMatcher().match(
        rgba,
        palette,
        DistanceMethod.ciede2000,
        cleanup_level=CleanupLevel.off,
    )
    screen_rgb = ColorMatcher().match(
        rgba,
        palette,
        DistanceMethod.rgb,
        cleanup_level=CleanupLevel.off,
    )

    assert perceptual.cells == ["PHYSICAL"]
    assert screen_rgb.cells == ["SCREEN"]


def test_balanced_palette_selection_preserves_a_small_distinct_region() -> None:
    palette = {
        "id": "balanced",
        "colors": [
            {"code": "R", "rgb": [255, 0, 0], "available": True},
            {"code": "RD", "rgb": [240, 0, 0], "available": True},
            {"code": "B", "rgb": [0, 0, 255], "available": True},
        ],
    }
    pixels = np.array([[[255, 0, 0, 255]] * 100 + [[240, 0, 0, 255]] * 10 + [[0, 0, 255, 255]] * 5], dtype=np.uint8)
    result = ColorMatcher().match(
        pixels, palette, DistanceMethod.ciede2000, max_colors=2, cleanup_level=CleanupLevel.off
    )
    assert set(result.cells) == {"R", "B"}


def test_quality_palette_one_swap_revisits_greedy_choices_and_preserves_forced_colours() -> None:
    distances = np.asarray(
        [
            [0.0, 1.0, 8.0],
            [8.0, 7.0, 0.0],
        ],
        dtype=np.float64,
    )
    candidates = np.asarray([0, 1, 2], dtype=np.int32)
    weights = np.ones(2, dtype=np.float64)

    refined = ColorMatcher._refine_quality_palette(
        distances,
        candidates,
        [0, 1],
        set(),
        weights,
        weights,
    )
    forced = ColorMatcher._refine_quality_palette(
        distances,
        candidates,
        [0, 1],
        {1},
        weights,
        weights,
    )
    before_p95 = float(np.quantile(np.min(distances[:, [0, 1]], axis=1), 0.95))
    refined_p95 = float(np.quantile(np.min(distances[:, refined], axis=1), 0.95))

    assert set(refined) == {0, 2}
    assert refined_p95 < before_p95
    assert 1 in forced


def test_tail_aware_quality_selection_is_deterministic() -> None:
    palette = {
        "id": "tail-deterministic",
        "colors": [
            {"code": f"C{index}", "rgb": rgb, "available": True}
            for index, rgb in enumerate(([25, 35, 45], [75, 85, 95], [125, 135, 145], [175, 185, 195], [225, 215, 205]))
        ],
    }
    rows = [[value, min(255, value + 12), max(0, value - 8), 255] for value in range(20, 240, 3)]
    rgba = np.asarray([rows], dtype=np.uint8)

    first = ColorMatcher().match(
        rgba,
        palette,
        DistanceMethod.ciede2000,
        max_colors=3,
        cleanup_level=CleanupLevel.off,
    )
    second = ColorMatcher().match(
        rgba,
        palette,
        DistanceMethod.ciede2000,
        max_colors=3,
        cleanup_level=CleanupLevel.off,
    )

    assert first.cells == second.cells


def test_light_cleanup_preserves_a_distinct_isolated_source_colour() -> None:
    palette = {
        "id": "cleanup",
        "colors": [
            {"code": "R", "rgb": [255, 0, 0], "available": True},
            {"code": "RD", "rgb": [240, 0, 0], "available": True},
        ],
    }
    rgba = np.full((3, 3, 4), (255, 0, 0, 255), dtype=np.uint8)
    rgba[1, 1, :3] = (240, 0, 0)
    result = ColorMatcher().match(rgba, palette, DistanceMethod.ciede2000, cleanup_level=CleanupLevel.light)
    assert result.cells[4] == "RD"


def test_light_cleanup_only_merges_visually_indistinguishable_noise() -> None:
    palette = {
        "id": "near-cleanup",
        "colors": [
            {"code": "R", "rgb": [255, 0, 0], "available": True},
            {"code": "RD", "rgb": [254, 0, 0], "available": True},
        ],
    }
    rgba = np.full((3, 3, 4), (255, 0, 0, 255), dtype=np.uint8)
    rgba[1, 1, :3] = (254, 0, 0)
    result = ColorMatcher().match(rgba, palette, DistanceMethod.ciede2000, cleanup_level=CleanupLevel.light)
    assert result.cells == ["R"] * 9


def test_medium_cleanup_merges_a_small_connected_near_colour_island() -> None:
    palette = {
        "id": "region-cleanup",
        "colors": [
            {"code": "R", "rgb": [255, 0, 0], "available": True},
            {"code": "RD", "rgb": [250, 4, 0], "available": True},
        ],
    }
    rgba = np.full((5, 5, 4), (255, 0, 0, 255), dtype=np.uint8)
    rgba[2, 2:4, :3] = (250, 4, 0)

    result = ColorMatcher().match(rgba, palette, DistanceMethod.ciede2000, cleanup_level=CleanupLevel.medium)

    assert result.cells == ["R"] * 25


def test_medium_cleanup_preserves_a_high_contrast_small_detail() -> None:
    rgba = np.full((5, 5, 4), (255, 0, 0, 255), dtype=np.uint8)
    rgba[2, 2:4, :3] = (0, 0, 0)

    result = ColorMatcher().match(rgba, PALETTE, DistanceMethod.ciede2000, cleanup_level=CleanupLevel.medium)

    assert result.cells[12:14] == ["K", "K"]


def test_ciede2000_matches_reference_pair() -> None:
    # First published Sharma et al. CIEDE2000 reference pair.
    first = np.array([[[50.0, 2.6772, -79.7751]]])
    second = np.array([[[50.0, 0.0, -82.7485]]])
    assert _delta_e_2000(first, second)[0, 0] == pytest.approx(2.0425, abs=0.0001)


def test_fidelity_metric_preserves_a_rgb_nearer_palette_swatch() -> None:
    palette = {
        "id": "fidelity",
        "colors": [
            {"code": "CIE", "rgb": [134, 110, 223], "available": True},
            {"code": "FIDELITY", "rgb": [132, 135, 195], "available": True},
        ],
    }
    rgba = np.array([[[160, 124, 203, 255]]], dtype=np.uint8)
    matcher = ColorMatcher()
    ciede = matcher.match(rgba, palette, DistanceMethod.ciede2000, cleanup_level=CleanupLevel.off)
    fidelity = matcher.match(rgba, palette, DistanceMethod.fidelity, cleanup_level=CleanupLevel.off)
    assert ciede.cells == ["CIE"]
    assert fidelity.cells == ["FIDELITY"]


def test_generate_defaults_use_the_same_ciede2000_metric_as_quality_reporting() -> None:
    request = PatternGenerateRequest(image_id="image_1234", grid_width=32, grid_height=32)
    assert request.sampling_mode == SamplingMode.adaptive
    assert request.distance_method == DistanceMethod.ciede2000
    assert request.auto_color_limit is True
    assert request.target_p95_delta_e_00 == 6
    assert request.include_special_colors is False
    assert request.cleanup_level == CleanupLevel.medium
    assert request.structure_aware is True


def test_automatic_colour_ceiling_is_only_a_production_cap() -> None:
    request = PatternGenerateRequest(
        image_id="image_1234",
        grid_width=64,
        grid_height=64,
        max_colors=291,
    )

    ceiling = PatternService._color_ceiling(request, palette_capacity=221)

    assert ceiling == 48


def test_quality_driven_palette_stops_after_reaching_the_p95_target() -> None:
    palette = {
        "id": "quality-target",
        "colors": [
            {"code": "K", "rgb": [0, 0, 0], "available": True},
            {"code": "W", "rgb": [255, 255, 255], "available": True},
            *[{"code": f"G{value}", "rgb": [value, value, value], "available": True} for value in range(20, 220, 20)],
        ],
    }
    rgba = np.array([[[0, 0, 0, 255], [255, 255, 255, 255]]] * 8, dtype=np.uint8)

    result = ColorMatcher().match(
        rgba,
        palette,
        DistanceMethod.ciede2000,
        max_colors=len(palette["colors"]),
        cleanup_level=CleanupLevel.off,
        auto_color_limit=True,
        target_p95_delta_e_00=0.5,
    )

    assert result.selected_color_count == 2
    assert set(result.cells) == {"K", "W"}


def test_structure_analysis_prioritizes_focal_detail_and_skips_pixel_art() -> None:
    rgba = np.full((9, 9, 4), (100, 100, 100, 255), dtype=np.uint8)
    rgba[4, 4] = (125, 105, 105, 255)
    portrait = PatternGenerateRequest(
        image_id="image_1234",
        grid_width=9,
        grid_height=9,
        conversion_preset="portrait",
        detail_priorities=["facial", "outline"],
        focus_x=0.5,
        focus_y=0.5,
    )

    analysis = analyze_structure(rgba, portrait)

    assert analysis.enabled is True
    assert analysis.importance[4, 4] > analysis.importance[0, 0]
    assert analysis.protected_mask[4, 4]

    pixel_art = portrait.model_copy(update={"conversion_preset": "pixel_art"})
    pixel_analysis = analyze_structure(rgba, pixel_art)
    assert pixel_analysis.enabled is False
    assert np.all(pixel_analysis.importance == 1)


def test_structure_weight_reserves_a_palette_slot_for_a_small_detail() -> None:
    background_colours = ([70, 70, 70], [100, 100, 100], [130, 130, 130], [160, 160, 160])
    detail = [90, 105, 120]
    palette_values = [
        [65, 65, 65],
        [95, 95, 95],
        [125, 125, 125],
        [155, 155, 155],
        detail,
    ]
    palette = {
        "id": "structure-budget",
        "colors": [{"code": f"C{index}", "rgb": rgb, "available": True} for index, rgb in enumerate(palette_values)],
    }
    rows = [rgb for background in background_colours for rgb in [background] * 25]
    rows.append(detail)
    rgba = np.asarray([[rgb + [255] for rgb in rows]], dtype=np.uint8)
    importance = np.ones((1, len(rows)), dtype=np.float64)
    importance[0, -1] = 4
    matcher = ColorMatcher()

    plain = matcher.match(
        rgba,
        palette,
        DistanceMethod.ciede2000,
        max_colors=2,
        cleanup_level=CleanupLevel.off,
    )
    structured = matcher.match(
        rgba,
        palette,
        DistanceMethod.ciede2000,
        max_colors=2,
        cleanup_level=CleanupLevel.off,
        importance_map=importance,
    )

    assert plain.cells[-1] != "C4"
    assert structured.cells[-1] == "C4"


def test_spatial_cleanup_merges_a_near_colour_speckle_in_a_flat_region() -> None:
    palette = {
        "id": "spatial-flat",
        "colors": [
            {"code": "A", "rgb": [100, 100, 100], "available": True},
            {"code": "B", "rgb": [112, 112, 112], "available": True},
        ],
    }
    rgba = np.full((5, 5, 4), (100, 100, 100, 255), dtype=np.uint8)
    rgba[2, 2] = (107, 107, 107, 255)
    matcher = ColorMatcher()

    unregularized = matcher.match(
        rgba,
        palette,
        DistanceMethod.ciede2000,
        cleanup_level=CleanupLevel.off,
    )
    regularized = matcher.match(
        rgba,
        palette,
        DistanceMethod.ciede2000,
        cleanup_level=CleanupLevel.medium,
    )

    assert unregularized.cells[12] == "B"
    assert set(regularized.cells) == {"A"}
    assert regularized.cleanup_adjusted_cell_count == 1


def test_structure_weight_protects_a_moderate_detail_from_spatial_merging() -> None:
    palette = {
        "id": "structure-spatial",
        "colors": [
            {"code": "A", "rgb": [100, 100, 100], "available": True},
            {"code": "B", "rgb": [112, 112, 112], "available": True},
        ],
    }
    rgba = np.full((5, 5, 4), (100, 100, 100, 255), dtype=np.uint8)
    rgba[2, 2] = (107, 107, 107, 255)
    importance = np.ones((5, 5), dtype=np.float64)
    importance[2, 2] = 4
    matcher = ColorMatcher()

    plain = matcher.match(
        rgba,
        palette,
        DistanceMethod.ciede2000,
        cleanup_level=CleanupLevel.medium,
    )
    structured = matcher.match(
        rgba,
        palette,
        DistanceMethod.ciede2000,
        cleanup_level=CleanupLevel.medium,
        importance_map=importance,
    )

    assert plain.cells[12] == "A"
    assert structured.cells[12] == "B"


def test_spatial_cleanup_preserves_a_high_contrast_single_cell_detail() -> None:
    palette = {
        "id": "spatial-edge",
        "colors": [
            {"code": "A", "rgb": [100, 100, 100], "available": True},
            {"code": "B", "rgb": [200, 200, 200], "available": True},
        ],
    }
    rgba = np.full((5, 5, 4), (100, 100, 100, 255), dtype=np.uint8)
    rgba[2, 2] = (200, 200, 200, 255)

    result = ColorMatcher().match(
        rgba,
        palette,
        DistanceMethod.ciede2000,
        cleanup_level=CleanupLevel.medium,
    )

    assert result.cells[12] == "B"
    assert result.cleanup_adjusted_cell_count == 0


def test_spatial_cleanup_never_replaces_a_locked_colour_cell() -> None:
    palette = {
        "id": "spatial-locked",
        "colors": [
            {"code": "A", "rgb": [100, 100, 100], "available": True},
            {"code": "B", "rgb": [112, 112, 112], "available": True},
        ],
    }
    rgba = np.full((5, 5, 4), (100, 100, 100, 255), dtype=np.uint8)
    rgba[2, 2] = (107, 107, 107, 255)

    result = ColorMatcher().match(
        rgba,
        palette,
        DistanceMethod.ciede2000,
        locked_colors=["B"],
        cleanup_level=CleanupLevel.medium,
    )

    assert result.cells[12] == "B"
    assert result.cleanup_adjusted_cell_count == 0


def test_special_effect_colours_are_opt_in_conversion_candidates() -> None:
    palette = {
        "colors": [
            {"code": "S", "rgb": [10, 10, 10], "available": True, "effect": "standard"},
            {"code": "X", "rgb": [20, 20, 20], "available": True, "effect": "special"},
        ]
    }

    assert PatternService._eligible_palette_codes(palette, include_special_colors=False) == {"S"}
    assert PatternService._eligible_palette_codes(palette, include_special_colors=True) == {"S", "X"}


def test_subject_framing_uses_focal_point_and_preserves_target_aspect() -> None:
    pixels = np.full((20, 40, 4), (20, 20, 20, 255), dtype=np.uint8)
    pixels[:, 28:, :3] = (240, 20, 20)
    source = Image.fromarray(pixels, "RGBA")
    request = PatternGenerateRequest(
        image_id="image_1234",
        grid_width=10,
        grid_height=10,
        subject_crop=True,
        focus_x=0.85,
        focus_y=0.5,
        focus_zoom=1.5,
        background_weaken=0.5,
        detail_priorities=["facial", "outline"],
    )

    result = prepare_conversion_image(source, request)

    assert result.size == (13, 13)
    assert np.asarray(result)[6, 6, 0] > 100


def test_conversion_diagnostics_exposes_cell_heatmap_and_ranked_hotspots() -> None:
    rgba = np.array([[[255, 0, 0, 255], [0, 255, 0, 255]]], dtype=np.uint8)
    palette = {
        "id": "diagnostics",
        "colors": [
            {"code": "R", "rgb": [255, 0, 0]},
            {"code": "B", "rgb": [0, 0, 255]},
        ],
    }

    diagnostics = calculate_conversion_diagnostics(rgba, ["R", "B"], palette)

    assert diagnostics["cell_delta_e_00_tenths"][0] == 0
    assert diagnostics["cell_delta_e_00_tenths"][1] > 0
    assert diagnostics["hotspots"][0]["column"] == 2


def test_diagnostics_and_report_evaluate_the_physical_lab_value_instead_of_preview_rgb() -> None:
    red_lab = rgb_to_lab(np.asarray([[255, 0, 0]], dtype=np.float64))[0].tolist()
    palette = {
        "id": "measured-report",
        "calibration": {
            "color_space": "CIELAB",
            "illuminant": "D65",
            "observer": "2_degree",
            "source": "test instrument",
        },
        "colors": [
            {
                "code": "B",
                "name_zh": "屏幕蓝、实物红",
                "hex": "#0000FF",
                "rgb": [0, 0, 255],
                "measured_lab": red_lab,
                "available": True,
            },
            {
                "code": "K",
                "name_zh": "黑",
                "hex": "#000000",
                "rgb": [0, 0, 0],
                "available": True,
            },
        ],
    }
    rgba = np.asarray([[[255, 0, 0, 255]]], dtype=np.uint8)
    cells = ["B"]
    statistics = calculate_statistics(cells, 1, 1, palette, bead_size_mm=5, waste_rate=0)

    diagnostics = calculate_conversion_diagnostics(rgba, cells, palette)
    report = calculate_color_report(
        rgba,
        cells,
        palette,
        statistics,
        matching_metric="ciede2000",
        eligible_color_codes={"B", "K"},
    )

    assert diagnostics["average_delta_e_00"] == 0
    assert diagnostics["quality_basis"] == "measured_lab"
    assert diagnostics["measured_evaluated_percent"] == 100
    assert report["average_delta_e_00"] == 0
    assert report["quality_basis"] == "measured_lab"
    assert report["matching_color_basis"] == "mixed_lab"
    assert report["palette_measurement_coverage_percent"] == 50
    assert report["calibration"]["source"] == "test instrument"


def test_pdf_page_ranges_are_balanced_instead_of_leaving_a_thin_final_strip() -> None:
    ranges = _balanced_ranges(total=100, capacity=69, overlap=1)
    assert ranges == [(0, 51), (50, 100)]


def test_statistics_are_derived_from_cells() -> None:
    result = calculate_statistics(["W", "W", None, "K"], 2, 2, PALETTE, bead_size_mm=5, waste_rate=0.05)
    assert result["total_beads"] == 3
    assert result["transparent_cells"] == 1
    assert result["physical_width_mm"] == 10
    assert result["colors"][0]["count_with_waste"] == 3


def test_color_report_exposes_perceptual_quality_inventory_shortage_and_substitution() -> None:
    palette = {
        "id": "report",
        "colors": [
            {"code": "R", "name_zh": "红", "hex": "#FF0000", "rgb": [255, 0, 0], "available": True},
            {"code": "B", "name_zh": "蓝", "hex": "#0000FF", "rgb": [0, 0, 255], "available": True},
        ],
    }
    rgba = np.full((2, 2, 4), (255, 0, 0, 255), dtype=np.uint8)
    statistics = calculate_statistics(["R"] * 4, 2, 2, palette, bead_size_mm=5, waste_rate=0.25)
    report = calculate_color_report(
        rgba,
        ["R"] * 4,
        palette,
        statistics,
        inventory=[{"color_code": "B", "quantity": 20}],
        selected_color_limit=24,
        matching_metric="ciede2000",
        target_p95_delta_e_00=0.5,
        eligible_color_codes={"R", "B"},
    )
    assert report["average_delta_e_00"] == 0
    assert report["quality_label"] == "优秀"
    assert report["matching_metric"] == "ciede2000"
    assert report["target_p95_delta_e_00"] == 0.5
    assert report["target_met"] is True
    assert report["oracle_p95_delta_e_00"] == 0
    assert report["p95_oracle_gap"] == 0
    assert report["oracle_target_reachable"] is True
    assert report["cleanup_adjusted_cell_count"] == 0
    assert report["cleanup_adjusted_percent"] == 0
    assert report["inventory"]["coverage_percent"] == 0
    assert report["inventory"]["missing_colors"][0]["shortage_quantity"] == 5
    assert report["substitutions"][0]["to_color_code"] == "B"


def test_color_report_separates_algorithm_headroom_from_palette_gamut_limit() -> None:
    source = np.asarray([[[0, 255, 0, 255]]], dtype=np.uint8)
    palette_with_exact_colour = {
        "id": "oracle-reachable",
        "colors": [
            {"code": "R", "name_zh": "红", "hex": "#FF0000", "rgb": [255, 0, 0], "available": True},
            {"code": "G", "name_zh": "绿", "hex": "#00FF00", "rgb": [0, 255, 0], "available": True},
        ],
    }
    red_cells = ["R"]
    statistics = calculate_statistics(
        red_cells,
        1,
        1,
        palette_with_exact_colour,
        bead_size_mm=5,
        waste_rate=0,
    )

    reachable = calculate_color_report(
        source,
        red_cells,
        palette_with_exact_colour,
        statistics,
        target_p95_delta_e_00=1,
        eligible_color_codes={"R", "G"},
    )
    gamut_limited = calculate_color_report(
        source,
        red_cells,
        {"id": "oracle-limited", "colors": palette_with_exact_colour["colors"][:1]},
        calculate_statistics(
            red_cells,
            1,
            1,
            {"id": "oracle-limited", "colors": palette_with_exact_colour["colors"][:1]},
            bead_size_mm=5,
            waste_rate=0,
        ),
        target_p95_delta_e_00=1,
        eligible_color_codes={"R"},
    )

    assert reachable["target_met"] is False
    assert reachable["oracle_p95_delta_e_00"] == 0
    assert reachable["p95_oracle_gap"] == reachable["p95_delta_e_00"]
    assert reachable["oracle_target_reachable"] is True
    assert gamut_limited["oracle_p95_delta_e_00"] > 1
    assert gamut_limited["p95_oracle_gap"] == 0
    assert gamut_limited["oracle_target_reachable"] is False


def test_color_report_preserves_zero_selected_colours_for_an_empty_grid() -> None:
    palette = {
        "id": "empty-report",
        "colors": [
            {"code": "K", "name_zh": "黑", "hex": "#000000", "rgb": [0, 0, 0], "available": True},
        ],
    }
    rgba = np.zeros((1, 1, 4), dtype=np.uint8)
    statistics = calculate_statistics([None], 1, 1, palette, bead_size_mm=5, waste_rate=0)

    report = calculate_color_report(
        rgba,
        [None],
        palette,
        statistics,
        selected_color_limit=0,
        eligible_color_codes={"K"},
    )

    assert report["selected_color_limit"] == 0
    assert report["used_color_count"] == 0


def test_color_report_skips_oracle_for_an_original_design_without_reference_image() -> None:
    palette = {
        "id": "original-report",
        "colors": [
            {"code": "K", "name_zh": "黑", "hex": "#000000", "rgb": [0, 0, 0], "available": True},
        ],
    }
    cells = ["K"]
    statistics = calculate_statistics(cells, 1, 1, palette, bead_size_mm=5, waste_rate=0)

    report = calculate_color_report(
        np.zeros((1, 1, 4), dtype=np.uint8),
        cells,
        palette,
        statistics,
        reference_available=False,
    )

    assert report["quality_label"] == "原创设计"
    assert report["evaluated_cells"] == 0
    assert report["oracle_p95_delta_e_00"] is None


def test_production_plan_uses_saved_grid_inventory_and_physical_board_layout() -> None:
    palette = {
        "id": "production",
        "colors": [
            {"code": "A1", "name_zh": "A", "hex": "#FF0000", "rgb": [255, 0, 0], "available": True},
            {"code": "B1", "name_zh": "B", "hex": "#0000FF", "rgb": [0, 0, 255], "available": True},
        ],
    }
    cells = ["A1", "B1", "A1", None]
    pattern = {
        "grid_width": 2,
        "grid_height": 2,
        "cells": cells,
        "statistics": calculate_statistics(cells, 2, 2, palette, bead_size_mm=5, waste_rate=0),
        "settings": {"inventory": [{"color_code": "A1", "quantity": 1}, {"color_code": "B1", "quantity": 0}]},
    }

    plan = build_production_plan(pattern, strategy="color", beads_per_hour=120)

    assert plan["board_template"]["usable_holes"] == 841
    assert plan["assembly"]["boards"][0]["bead_count"] == 3
    assert plan["make_steps"][0]["bead_count"] == 2
    assert {item["color_code"] for item in plan["materials"]["shortages"]} == {"A1", "B1"}


def test_templates_text_and_assembly_plan_are_grid_safe() -> None:
    template = next(item for item in list_templates() if item["id"] == "heart-charm")
    width, height, cells = render_template("heart-charm", "A1", "B1")
    assert (width, height) == (template["grid_width"], template["grid_height"])
    assert len(cells) == width * height
    text_width, text_height, text_cells, normalized = render_text("AB-1", "keychain", "A1", "B1")
    assert normalized == "AB-1"
    assert len(text_cells) == text_width * text_height
    plan = build_assembly_plan({"grid_width": width, "grid_height": height}, board_width=4, board_height=4, overlap=1)
    assert plan["board_count"] > 1
    assert plan["boards"][0]["id"] == "A1"


def test_mard_291_palette_is_complete_and_uses_unique_manufacturer_codes() -> None:
    palette = PaletteService().get("mard-291")
    assert len(palette["colors"]) == 291
    assert len({color["code"] for color in palette["colors"]}) == 291
    assert palette["colors"][0]["code"] == "A1"
    assert palette["colors"][-1]["code"] == "ZG8"
    assert sum(color["effect"] == "special" for color in palette["colors"]) == 70
    assert len(PatternService._eligible_palette_codes(palette, include_special_colors=False)) == 221
    assert palette["colorimetry_status"] == "screen_rgb"
    assert palette["measured_color_count"] == 0


def test_custom_palette_persists_calibration_and_reports_partial_coverage(tmp_path) -> None:
    request = PaletteCreate.model_validate(
        {
            "id": "measured-custom",
            "name": "实体测色测试",
            "brand": "Test",
            "calibration": {
                "source": "current inventory sample set",
                "instrument": "test spectrophotometer",
                "measurement_geometry": "d/8 SCI",
                "measured_at": "2026-08-31",
            },
            "colors": [
                {
                    "code": "R1",
                    "name_zh": "红",
                    "hex": "#FF0000",
                    "rgb": [255, 0, 0],
                    "measured_lab": [53.24, 80.09, 67.2],
                },
                {
                    "code": "B1",
                    "name_zh": "蓝",
                    "hex": "#0000FF",
                    "rgb": [0, 0, 255],
                },
            ],
        }
    )
    service = PaletteService(Settings(data_dir=tmp_path, database_path=tmp_path / "studio.db"))

    palette = service.create(request)
    summary = next(item for item in service.list() if item["id"] == request.id)

    assert palette["colorimetry_status"] == "mixed_lab"
    assert palette["measured_color_count"] == 1
    assert palette["measurement_coverage_percent"] == 50
    assert palette["calibration"]["illuminant"] == "D65"
    assert palette["calibration"]["observer"] == "2_degree"
    assert summary["colorimetry_status"] == "mixed_lab"
    assert summary["measurement_coverage_percent"] == 50

    downgraded = service.update(
        request.id,
        PaletteUpdate.model_validate(
            {
                "calibration": None,
                "colors": [
                    {
                        "code": "R1",
                        "name_zh": "红",
                        "hex": "#FF0000",
                        "rgb": [255, 0, 0],
                    },
                    {
                        "code": "B1",
                        "name_zh": "蓝",
                        "hex": "#0000FF",
                        "rgb": [0, 0, 255],
                    },
                ],
            }
        ),
    )
    assert downgraded["colorimetry_status"] == "screen_rgb"
    assert "calibration" not in downgraded


def test_measured_palette_requires_calibration_provenance() -> None:
    with pytest.raises(ValueError, match="calibration"):
        PaletteCreate.model_validate(
            {
                "id": "missing-calibration",
                "name": "缺少来源",
                "brand": "Test",
                "colors": [
                    {
                        "code": "R1",
                        "name_zh": "红",
                        "hex": "#FF0000",
                        "rgb": [255, 0, 0],
                        "measured_lab": [53.24, 80.09, 67.2],
                    }
                ],
            }
        )


def test_mard_working_systems_have_exact_tier_sizes_and_real_mard_codes() -> None:
    service = PaletteService()
    full_codes = {color["code"] for color in service.get("mard-291")["colors"]}
    tiers = (24, 48, 72, 96, 120, 144, 168, 192, 221, 264, 291)

    for tier in tiers:
        palette = service.get(f"mard-{tier}")
        assert palette["color_tier"] == tier
        assert len(palette["colors"]) == tier
        assert {color["code"] for color in palette["colors"]} <= full_codes

    summaries = {palette["id"]: palette for palette in service.list()}
    assert {f"mard-{tier}" for tier in tiers} <= summaries.keys()
    assert "mard" not in summaries
