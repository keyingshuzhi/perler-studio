from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from PIL import Image, ImageFilter

from app.schemas.pattern import ConversionPreset, PatternGenerateRequest
from app.services.color_matcher import _delta_e_2000, rgb_to_lab


@dataclass(frozen=True)
class StructureAnalysis:
    """Per-cell importance used by palette selection and spatial regularisation."""

    enabled: bool
    importance: np.ndarray
    protected_mask: np.ndarray

    @property
    def protected_cell_count(self) -> int:
        return int(np.count_nonzero(self.protected_mask))


def _elliptical_focus(
    height: int,
    width: int,
    focus_x: float,
    focus_y: float,
    radius: float,
) -> np.ndarray:
    rows, columns = np.ogrid[:height, :width]
    normalized_x = (columns / max(width - 1, 1) - focus_x) / max(radius, 0.05)
    normalized_y = (rows / max(height - 1, 1) - focus_y) / max(radius, 0.05)
    return np.exp(-2.6 * (normalized_x**2 + normalized_y**2))


def _local_edge_strength(lab: np.ndarray, visible: np.ndarray) -> np.ndarray:
    strength = np.zeros(visible.shape, dtype=np.float32)
    horizontal_visible = visible[:, :-1] & visible[:, 1:]
    horizontal = _delta_e_2000(lab[:, :-1], lab[:, 1:])
    horizontal = np.where(horizontal_visible, horizontal, 0).astype(np.float32)
    strength[:, :-1] = np.maximum(strength[:, :-1], horizontal)
    strength[:, 1:] = np.maximum(strength[:, 1:], horizontal)

    vertical_visible = visible[:-1, :] & visible[1:, :]
    vertical = _delta_e_2000(lab[:-1, :], lab[1:, :])
    vertical = np.where(vertical_visible, vertical, 0).astype(np.float32)
    strength[:-1, :] = np.maximum(strength[:-1, :], vertical)
    strength[1:, :] = np.maximum(strength[1:, :], vertical)
    return strength


def _rarity_score(lab: np.ndarray, visible: np.ndarray) -> np.ndarray:
    """Estimate whether a structural colour family occupies a small area."""
    quantized_l = np.clip((lab[..., 0] / 10).astype(np.int32), 0, 10)
    quantized_a = np.clip(((lab[..., 1] + 128) / 16).astype(np.int32), 0, 15)
    quantized_b = np.clip(((lab[..., 2] + 128) / 16).astype(np.int32), 0, 15)
    keys = quantized_l * 256 + quantized_a * 16 + quantized_b
    visible_keys = keys[visible]
    score = np.zeros(visible.shape, dtype=np.float32)
    if not len(visible_keys):
        return score
    counts = np.bincount(visible_keys, minlength=11 * 256)
    family_counts = counts[visible_keys]
    rarity = np.sqrt(len(visible_keys) / np.maximum(family_counts * 8, 1))
    score[visible] = np.clip(rarity, 0, 3).astype(np.float32)
    return score


def analyze_structure(rgba: np.ndarray, request: PatternGenerateRequest) -> StructureAnalysis:
    """Create a deterministic multi-scale structure map from the sampled source.

    This is not semantic AI segmentation. It combines perceptual edges, local
    contrast, colour-family rarity, the selected content preset, and the creator's
    focal region. The resulting normalized weights let small meaningful regions
    compete for palette slots without letting a large background dominate every
    global error decision.
    """
    height, width = rgba.shape[:2]
    visible = np.asarray(rgba[..., 3]) > 5
    enabled = request.structure_aware and request.conversion_preset != ConversionPreset.pixel_art
    if not enabled or not np.any(visible):
        return StructureAnalysis(False, np.ones((height, width), dtype=np.float32), np.zeros_like(visible))

    rgb = np.asarray(rgba[..., :3], dtype=np.uint8)
    lab = rgb_to_lab(rgb).astype(np.float32)
    edge_strength = _local_edge_strength(lab, visible)
    blurred_rgb = np.asarray(
        Image.fromarray(rgb, "RGB").filter(ImageFilter.BoxBlur(radius=2)),
        dtype=np.uint8,
    )
    local_contrast = _delta_e_2000(lab, rgb_to_lab(blurred_rgb)).astype(np.float32)
    edge_score = np.clip((edge_strength - 1.5) / 9.0, 0, 1)
    contrast_score = np.clip((local_contrast - 1.0) / 10.0, 0, 1)
    detail_score = np.maximum(edge_score, contrast_score * 0.82)

    focus_x = 0.5 if request.subject_crop or request.focus_zoom > 1 else request.focus_x
    focus_y = 0.5 if request.subject_crop or request.focus_zoom > 1 else request.focus_y
    focus = _elliptical_focus(height, width, focus_x, focus_y, request.focus_radius).astype(np.float32)
    preset = request.conversion_preset
    if preset == ConversionPreset.portrait:
        importance = 0.58 + 1.25 * focus + detail_score * (0.28 + 1.45 * focus)
    elif preset == ConversionPreset.illustration:
        importance = 0.88 + 0.92 * detail_score
    elif preset == ConversionPreset.landscape:
        importance = 0.9 + 0.48 * detail_score + 0.18 * focus
    else:
        importance = 0.94 + 0.64 * detail_score

    priorities = {str(priority) for priority in request.detail_priorities}
    if priorities & {"facial", "text"}:
        importance += 1.2 * focus * (0.35 + 0.65 * detail_score)
    if "outline" in priorities:
        importance += 0.62 * detail_score

    importance += 0.34 * detail_score * _rarity_score(lab, visible)
    importance = np.where(visible, importance, 1.0).astype(np.float32)
    visible_mean = float(importance[visible].mean())
    importance[visible] = np.clip(importance[visible] / max(visible_mean, 1e-6), 0.35, 4.5)
    # Clipping can move the mean slightly; one final normalization keeps the
    # overall data-term scale stable between enabled and disabled conversions.
    normalized_mean = float(importance[visible].mean())
    importance[visible] /= max(normalized_mean, 1e-6)
    protected = visible & (importance >= 1.35)
    return StructureAnalysis(True, importance, protected)
