from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Any

import numpy as np

from app.core.exceptions import validation_error
from app.schemas.pattern import CleanupLevel, DistanceMethod


def rgb_to_lab(rgb: np.ndarray) -> np.ndarray:
    """Convert an sRGB array in [0, 255] to CIE L*a*b* using D65 white point."""
    rgb = np.asarray(rgb, dtype=np.float64) / 255.0
    linear = np.where(rgb <= 0.04045, rgb / 12.92, ((rgb + 0.055) / 1.055) ** 2.4)
    matrix = np.array(
        [[0.4124564, 0.3575761, 0.1804375], [0.2126729, 0.7151522, 0.0721750], [0.0193339, 0.1191920, 0.9503041]]
    )
    xyz = linear @ matrix.T
    xyz /= np.array([0.95047, 1.0, 1.08883])
    epsilon, kappa = 216 / 24389, 24389 / 27
    fxyz = np.where(xyz > epsilon, np.cbrt(xyz), (kappa * xyz + 16) / 116)
    return np.stack(
        (116 * fxyz[..., 1] - 16, 500 * (fxyz[..., 0] - fxyz[..., 1]), 200 * (fxyz[..., 1] - fxyz[..., 2])), axis=-1
    )


def color_record_lab(color: dict[str, Any]) -> np.ndarray:
    """Return a swatch's measured CIELAB value or its screen-RGB fallback."""
    measured = color.get("measured_lab")
    if measured is None:
        return rgb_to_lab(np.asarray(color["rgb"], dtype=np.float64).reshape(1, 3))[0]
    value = np.asarray(measured, dtype=np.float64)
    if value.shape != (3,) or not np.all(np.isfinite(value)):
        raise ValueError(f"色号 {color.get('code', '')} 的 measured_lab 必须包含三个有限数值")
    return value


def palette_records_lab(colors: list[dict[str, Any]]) -> np.ndarray:
    """Build the candidate LAB matrix while preserving per-swatch fallback."""
    if not colors:
        return np.empty((0, 3), dtype=np.float64)
    return np.stack([color_record_lab(color) for color in colors]).astype(np.float64)


def colorimetry_status(measured_count: int, total_count: int) -> str:
    if total_count <= 0:
        return "not_applicable"
    if measured_count <= 0:
        return "screen_rgb"
    if measured_count >= total_count:
        return "measured_lab"
    return "mixed_lab"


def rgb_to_oklab(rgb: np.ndarray) -> np.ndarray:
    """Convert sRGB values in [0, 255] to the modern perceptual OKLab space."""
    normalized = np.asarray(rgb, dtype=np.float64) / 255.0
    linear = np.where(normalized <= 0.04045, normalized / 12.92, ((normalized + 0.055) / 1.055) ** 2.4)
    lms = (
        linear
        @ np.array(
            [
                [0.4122214708, 0.5363325363, 0.0514459929],
                [0.2119034982, 0.6806995451, 0.1073969566],
                [0.0883024619, 0.2817188376, 0.6299787005],
            ]
        ).T
    )
    lms_root = np.cbrt(lms)
    return (
        lms_root
        @ np.array(
            [
                [0.2104542553, 0.7936177850, -0.0040720468],
                [1.9779984951, -2.4285922050, 0.4505937099],
                [0.0259040371, 0.7827717662, -0.8086757660],
            ]
        ).T
    )


def _delta_e_2000(first: np.ndarray, second: np.ndarray) -> np.ndarray:
    """Vectorised CIEDE2000 distance for arrays shaped (..., 3)."""
    l1, a1, b1 = (first[..., index] for index in range(3))
    l2, a2, b2 = (second[..., index] for index in range(3))
    c1, c2 = np.hypot(a1, b1), np.hypot(a2, b2)
    mean_c = (c1 + c2) / 2
    g = 0.5 * (1 - np.sqrt(mean_c**7 / (mean_c**7 + 25**7)))
    a1p, a2p = (1 + g) * a1, (1 + g) * a2
    c1p, c2p = np.hypot(a1p, b1), np.hypot(a2p, b2)
    h1p = (np.degrees(np.arctan2(b1, a1p)) + 360) % 360
    h2p = (np.degrees(np.arctan2(b2, a2p)) + 360) % 360
    delta_l, delta_c = l2 - l1, c2p - c1p
    delta_h_angle = h2p - h1p
    delta_h_angle = np.where(delta_h_angle > 180, delta_h_angle - 360, delta_h_angle)
    delta_h_angle = np.where(delta_h_angle < -180, delta_h_angle + 360, delta_h_angle)
    delta_h_angle = np.where(c1p * c2p == 0, 0, delta_h_angle)
    delta_h = 2 * np.sqrt(c1p * c2p) * np.sin(np.radians(delta_h_angle / 2))
    mean_l, mean_cp = (l1 + l2) / 2, (c1p + c2p) / 2
    h_sum = h1p + h2p
    mean_hp = np.where(np.abs(h1p - h2p) <= 180, h_sum / 2, np.where(h_sum < 360, (h_sum + 360) / 2, (h_sum - 360) / 2))
    mean_hp = np.where(c1p * c2p == 0, h_sum, mean_hp)
    t = (
        1
        - 0.17 * np.cos(np.radians(mean_hp - 30))
        + 0.24 * np.cos(np.radians(2 * mean_hp))
        + 0.32 * np.cos(np.radians(3 * mean_hp + 6))
        - 0.20 * np.cos(np.radians(4 * mean_hp - 63))
    )
    delta_theta = 30 * np.exp(-(((mean_hp - 275) / 25) ** 2))
    r_c = 2 * np.sqrt(mean_cp**7 / (mean_cp**7 + 25**7))
    s_l = 1 + 0.015 * (mean_l - 50) ** 2 / np.sqrt(20 + (mean_l - 50) ** 2)
    s_c, s_h = 1 + 0.045 * mean_cp, 1 + 0.015 * mean_cp * t
    r_t = -np.sin(np.radians(2 * delta_theta)) * r_c
    return np.sqrt(
        (delta_l / s_l) ** 2 + (delta_c / s_c) ** 2 + (delta_h / s_h) ** 2 + r_t * (delta_c / s_c) * (delta_h / s_h)
    )


def _distances(
    rgb: np.ndarray,
    candidates_rgb: np.ndarray,
    method: DistanceMethod,
    candidates_lab: np.ndarray | None = None,
    candidates_oklab: np.ndarray | None = None,
) -> np.ndarray:
    first_rgb, second_rgb = rgb[:, None, :], candidates_rgb[None, :, :]
    if method == DistanceMethod.rgb:
        return np.linalg.norm(first_rgb - second_rgb, axis=-1)
    first_lab = rgb_to_lab(first_rgb)
    second_lab = (candidates_lab if candidates_lab is not None else rgb_to_lab(candidates_rgb))[None, :, :]
    if method == DistanceMethod.cie76:
        return np.linalg.norm(first_lab - second_lab, axis=-1)
    if method == DistanceMethod.cie94:
        delta_l = first_lab[..., 0] - second_lab[..., 0]
        c1 = np.hypot(first_lab[..., 1], first_lab[..., 2])
        c2 = np.hypot(second_lab[..., 1], second_lab[..., 2])
        delta_c = c1 - c2
        delta_a = first_lab[..., 1] - second_lab[..., 1]
        delta_b = first_lab[..., 2] - second_lab[..., 2]
        delta_h_sq = np.maximum(0, delta_a**2 + delta_b**2 - delta_c**2)
        return np.sqrt(delta_l**2 + (delta_c / (1 + 0.045 * c1)) ** 2 + delta_h_sq / (1 + 0.015 * c1) ** 2)
    ciede2000 = _delta_e_2000(first_lab, second_lab)
    if method == DistanceMethod.ciede2000:
        return ciede2000

    # CIEDE2000 is excellent in isolation but can still rank a palette swatch
    # with a visibly different lightness or saturation above an RGB-nearer one.
    # Combining it with OKLab and explicit lightness/chroma preservation gives
    # the constrained bead palette a more faithful on-screen approximation.
    first_oklab = rgb_to_oklab(first_rgb)
    second_oklab = (candidates_oklab if candidates_oklab is not None else rgb_to_oklab(candidates_rgb))[None, :, :]
    oklab_distance = np.linalg.norm(first_oklab - second_oklab, axis=-1) * 100.0
    lightness_delta = np.abs(first_lab[..., 0] - second_lab[..., 0])
    chroma_delta = np.abs(
        np.hypot(first_lab[..., 1], first_lab[..., 2]) - np.hypot(second_lab[..., 1], second_lab[..., 2])
    )
    return np.sqrt(
        ciede2000**2 + (0.33 * oklab_distance) ** 2 + (0.27 * lightness_delta) ** 2 + (0.10 * chroma_delta) ** 2
    )


def _paired_distances(
    first_rgb: np.ndarray,
    second_rgb: np.ndarray,
    method: DistanceMethod,
    first_lab: np.ndarray | None = None,
    second_lab: np.ndarray | None = None,
    first_oklab: np.ndarray | None = None,
    second_oklab: np.ndarray | None = None,
) -> np.ndarray:
    """Return colour distances for aligned RGB pairs instead of a cross matrix."""
    first_rgb = np.asarray(first_rgb, dtype=np.float64)
    second_rgb = np.asarray(second_rgb, dtype=np.float64)
    if method == DistanceMethod.rgb:
        return np.linalg.norm(first_rgb - second_rgb, axis=-1)

    first_lab = rgb_to_lab(first_rgb) if first_lab is None else first_lab
    second_lab = rgb_to_lab(second_rgb) if second_lab is None else second_lab
    if method == DistanceMethod.cie76:
        return np.linalg.norm(first_lab - second_lab, axis=-1)
    if method == DistanceMethod.cie94:
        delta_l = first_lab[..., 0] - second_lab[..., 0]
        c1 = np.hypot(first_lab[..., 1], first_lab[..., 2])
        c2 = np.hypot(second_lab[..., 1], second_lab[..., 2])
        delta_c = c1 - c2
        delta_a = first_lab[..., 1] - second_lab[..., 1]
        delta_b = first_lab[..., 2] - second_lab[..., 2]
        delta_h_sq = np.maximum(0, delta_a**2 + delta_b**2 - delta_c**2)
        return np.sqrt(delta_l**2 + (delta_c / (1 + 0.045 * c1)) ** 2 + delta_h_sq / (1 + 0.015 * c1) ** 2)

    ciede2000 = _delta_e_2000(first_lab, second_lab)
    if method == DistanceMethod.ciede2000:
        return ciede2000

    first_oklab = rgb_to_oklab(first_rgb) if first_oklab is None else first_oklab
    second_oklab = rgb_to_oklab(second_rgb) if second_oklab is None else second_oklab
    oklab_distance = np.linalg.norm(first_oklab - second_oklab, axis=-1) * 100.0
    lightness_delta = np.abs(first_lab[..., 0] - second_lab[..., 0])
    chroma_delta = np.abs(
        np.hypot(first_lab[..., 1], first_lab[..., 2]) - np.hypot(second_lab[..., 1], second_lab[..., 2])
    )
    return np.sqrt(
        ciede2000**2 + (0.33 * oklab_distance) ** 2 + (0.27 * lightness_delta) ** 2 + (0.10 * chroma_delta) ** 2
    )


@dataclass(frozen=True)
class MatchResult:
    cells: list[str | None]
    matched_rgb: np.ndarray
    selected_color_count: int
    cleanup_adjusted_cell_count: int = 0


class ColorMatcher:
    """Maps grid pixels to available palette codes using a selectable colour metric."""

    @staticmethod
    def _representative_pixels(
        pixels: np.ndarray,
        importance_weights: np.ndarray | None = None,
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Build deterministic objective and population colour summaries.

        Exact source colours are retained while the grid contains at most 4,096
        unique values. More complex photographs are reduced to a 16 x 16 x 16
        RGB histogram whose entries store the actual mean source colour. Unlike a
        fixed spatial stride, this retains the population of every colour family
        and gives quality thresholds a stable meaning on both small and large grids.
        """
        integer_pixels = np.asarray(pixels, dtype=np.uint16)
        importance = (
            np.ones(len(integer_pixels), dtype=np.float64)
            if importance_weights is None
            else np.asarray(importance_weights, dtype=np.float64).reshape(-1)
        )
        if len(importance) != len(integer_pixels):
            raise ValueError("结构权重数量必须与可见源像素数量一致")
        unique, inverse, counts = np.unique(integer_pixels, axis=0, return_inverse=True, return_counts=True)
        if len(unique) <= 4_096:
            objective_weights = np.bincount(inverse, weights=importance, minlength=len(unique))
            return unique.astype(np.float64), objective_weights, counts.astype(np.float64)

        buckets = integer_pixels // 16
        keys = buckets[:, 0] * 256 + buckets[:, 1] * 16 + buckets[:, 2]
        bucket_counts = np.bincount(keys, minlength=4_096)
        objective_weights = np.bincount(keys, weights=importance, minlength=4_096)
        active = np.flatnonzero(bucket_counts)
        sums = np.stack(
            [np.bincount(keys, weights=integer_pixels[:, channel], minlength=4_096) for channel in range(3)],
            axis=1,
        )
        representatives = sums[active] / bucket_counts[active, None]
        return (
            representatives,
            objective_weights[active].astype(np.float64),
            bucket_counts[active].astype(np.float64),
        )

    @staticmethod
    def _weighted_quantile(values: np.ndarray, weights: np.ndarray, quantile: float) -> float:
        order = np.argsort(values)
        ordered_values, ordered_weights = values[order], weights[order]
        threshold = float(ordered_weights.sum()) * quantile
        position = int(np.searchsorted(np.cumsum(ordered_weights), threshold, side="left"))
        return float(ordered_values[min(position, len(ordered_values) - 1)])

    @classmethod
    def _population_p95_delta_e(
        cls,
        pixels: np.ndarray,
        palette_rgb: np.ndarray,
        palette_lab: np.ndarray,
    ) -> float:
        """Verify an automatic stop against every distinct source colour."""
        unique, counts = np.unique(np.asarray(pixels, dtype=np.uint8), axis=0, return_counts=True)
        minimum_distances: list[np.ndarray] = []
        for start in range(0, len(unique), 2_048):
            distances = _distances(
                unique[start : start + 2_048],
                palette_rgb,
                DistanceMethod.ciede2000,
                palette_lab,
            )
            minimum_distances.append(np.min(distances, axis=1))
        return cls._weighted_quantile(np.concatenate(minimum_distances), counts.astype(np.float64), 0.95)

    def _nearest(
        self,
        pixels: np.ndarray,
        candidates_rgb: np.ndarray,
        method: DistanceMethod,
        candidates_lab: np.ndarray | None = None,
    ) -> np.ndarray:
        if not len(pixels):
            return np.empty(0, dtype=np.int32)

        # Grid pixels are integer RGB values, so duplicates are common after
        # resize/crop. Match each unique source colour once, then restore the
        # original order. This materially reduces work for flat illustrations.
        unique_pixels, inverse = np.unique(pixels, axis=0, return_inverse=True)
        if method != DistanceMethod.rgb and candidates_lab is None:
            candidates_lab = rgb_to_lab(candidates_rgb)
        candidates_oklab = rgb_to_oklab(candidates_rgb) if method == DistanceMethod.fidelity else None
        chunk_size = (
            1_024 if method == DistanceMethod.fidelity else 2_048 if method == DistanceMethod.ciede2000 else 8_192
        )
        chunks: list[np.ndarray] = []
        for start in range(0, len(unique_pixels), chunk_size):
            distance = _distances(
                unique_pixels[start : start + chunk_size], candidates_rgb, method, candidates_lab, candidates_oklab
            )
            chunks.append(np.argmin(distance, axis=1))
        unique_matches = np.concatenate(chunks)
        return unique_matches[inverse]

    @staticmethod
    def _select_balanced_palette(
        frequencies: np.ndarray,
        candidate_indices: np.ndarray,
        all_lab: np.ndarray,
        forced: list[int],
        max_colors: int,
    ) -> np.ndarray:
        """Choose frequent but perceptually distinct colours for a capped palette.

        A pure frequency ranking tends to select several nearly identical shades
        while dropping small, high-contrast details. Greedy weighted farthest-point
        selection keeps common colours while reserving slots for distinct regions.
        """
        selected = list(dict.fromkeys(forced))
        active = [index for index in candidate_indices.tolist() if frequencies[index] > 0 and index not in selected]
        if not selected and active:
            selected.append(max(active, key=lambda index: int(frequencies[index])))
            active.remove(selected[0])
        while active and len(selected) < max_colors:
            if not selected:
                selected.append(max(active, key=lambda index: int(frequencies[index])))
                active.remove(selected[-1])
                continue
            remaining = np.asarray(active, dtype=np.int32)
            selected_array = np.asarray(selected)
            distances = np.linalg.norm(all_lab[remaining, None, :] - all_lab[selected_array][None, :, :], axis=-1)
            min_distances = np.min(distances, axis=1)
            scores = np.sqrt(frequencies[remaining]) * np.maximum(min_distances, 0.1)
            selected_index = int(remaining[int(np.argmax(scores))])
            selected.append(selected_index)
            active.remove(selected_index)
        return np.asarray(selected, dtype=np.int32)

    @staticmethod
    def _select_fidelity_palette(
        pixels: np.ndarray,
        candidate_indices: np.ndarray,
        all_rgb: np.ndarray,
        all_lab: np.ndarray,
        forced: list[int],
        max_colors: int,
    ) -> np.ndarray:
        """Greedily minimise global perceptual error for a restricted palette.

        Colour-count limits are a major source of visible colour drift. The old
        frequency/diversity selector could reserve several slots for rare but
        distant colours even when their aggregate error was high. Here every
        added swatch must produce the largest measured error reduction across a
        representative sample of the actual source pixels. The final assignment
        is still calculated on every grid cell, not merely the sample.
        """
        selected = list(dict.fromkeys(forced))
        if len(selected) >= max_colors:
            return np.asarray(selected, dtype=np.int32)

        # Sampling bounds work for very large grids while retaining spatially
        # distributed image colours. There is deliberately no random component,
        # so repeated generation is stable.
        step = max(1, int(np.ceil(len(pixels) / 2_048)))
        sample = pixels[::step]
        pool = np.asarray([index for index in candidate_indices if index not in selected], dtype=np.int32)
        if not len(pool):
            return np.asarray(selected, dtype=np.int32)
        distances = _distances(
            sample,
            all_rgb[pool],
            DistanceMethod.fidelity,
            all_lab[pool],
            rgb_to_oklab(all_rgb[pool]),
        )
        if selected:
            selected_distances = _distances(
                sample,
                all_rgb[np.asarray(selected)],
                DistanceMethod.fidelity,
                all_lab[np.asarray(selected)],
                rgb_to_oklab(all_rgb[np.asarray(selected)]),
            )
            current_error = np.min(selected_distances, axis=1)
        else:
            first_position = int(np.argmin(distances.sum(axis=0)))
            selected.append(int(pool[first_position]))
            current_error = distances[:, first_position]
            keep = np.arange(len(pool)) != first_position
            pool, distances = pool[keep], distances[:, keep]

        while len(pool) and len(selected) < max_colors:
            resulting_error = np.minimum(current_error[:, None], distances)
            improvement = (current_error[:, None] - resulting_error).sum(axis=0)
            position = int(np.argmax(improvement))
            selected.append(int(pool[position]))
            current_error = resulting_error[:, position]
            keep = np.arange(len(pool)) != position
            pool, distances = pool[keep], distances[:, keep]
        return np.asarray(selected, dtype=np.int32)

    @classmethod
    def _tail_objective_weights(
        cls,
        current_error: np.ndarray,
        objective_weights: np.ndarray,
        population_weights: np.ndarray,
    ) -> np.ndarray:
        """Reweight the upper error tail without discarding mean fidelity.

        A hard P95 objective is discontinuous: improving the cell currently at
        the percentile boundary can simply expose its neighbour. This CVaR-like
        ramp starts at P90, reaches a strong multiplier at P95 and continues
        above it, so the optimiser lowers the whole tail instead of chasing one
        order statistic. Structure weights remain part of the base objective.
        """
        p90 = cls._weighted_quantile(current_error, population_weights, 0.90)
        p95 = cls._weighted_quantile(current_error, population_weights, 0.95)
        scale = max(p95 - p90, 1.0)
        ramp = np.clip((current_error - p90) / scale, 0.0, 2.0)
        tail_multiplier = 1.0 + 2.5 * ramp + 2.5 * (current_error >= p95)
        return objective_weights * tail_multiplier

    @classmethod
    def _refine_quality_palette(
        cls,
        distances: np.ndarray,
        candidate_indices: np.ndarray,
        selected: list[int],
        forced: set[int],
        objective_weights: np.ndarray,
        population_weights: np.ndarray,
    ) -> list[int]:
        """Jointly refine palette membership and its nearest-label assignment.

        Greedy addition cannot revisit an early swatch after later colours make
        it redundant. Deterministic one-swap search removes one non-locked
        swatch, inserts one unused real candidate and immediately recomputes the
        best label for every representative source colour. Only swaps that do
        not worsen P95 and improve the tail-weighted objective are accepted.
        """
        if len(selected) <= len(forced) or len(selected) >= len(candidate_indices):
            return selected

        position_by_index = {int(index): position for position, index in enumerate(candidate_indices)}
        selected_positions = [position_by_index[index] for index in selected]
        maximum_passes = 2
        candidates_per_removal = 8

        for _ in range(maximum_passes):
            current_error = np.min(distances[:, selected_positions], axis=1)
            current_p95 = cls._weighted_quantile(current_error, population_weights, 0.95)
            tail_weights = cls._tail_objective_weights(
                current_error,
                objective_weights,
                population_weights,
            )
            current_score = float(np.sum(current_error**2 * tail_weights))
            relative_importance = objective_weights / np.maximum(population_weights, 1e-9)
            protected = relative_importance >= 2.0
            current_protected_score = float(np.sum(current_error[protected] ** 2 * objective_weights[protected]))
            selected_set = set(selected_positions)
            unused_positions = np.asarray(
                [position for position in range(len(candidate_indices)) if position not in selected_set],
                dtype=np.int32,
            )
            if not len(unused_positions):
                break

            best_swap: tuple[tuple[float, float, int, int], int, int] | None = None
            for slot, palette_index in enumerate(selected):
                if palette_index in forced:
                    continue
                retained = selected_positions[:slot] + selected_positions[slot + 1 :]
                base_error = (
                    np.min(distances[:, retained], axis=1)
                    if retained
                    else np.full(len(distances), np.inf, dtype=np.float64)
                )
                resulting_error = np.minimum(
                    base_error[:, None],
                    distances[:, unused_positions],
                )
                scores = np.sum(resulting_error**2 * tail_weights[:, None], axis=0)
                shortlist = np.argsort(scores, kind="stable")[:candidates_per_removal]
                for local_position in shortlist:
                    score = float(scores[local_position])
                    if score + 1e-9 >= current_score:
                        continue
                    candidate_position = int(unused_positions[local_position])
                    candidate_error = resulting_error[:, local_position]
                    candidate_p95 = cls._weighted_quantile(candidate_error, population_weights, 0.95)
                    if candidate_p95 > current_p95 + 1e-9:
                        continue
                    if protected.any():
                        candidate_protected_score = float(
                            np.sum(candidate_error[protected] ** 2 * objective_weights[protected])
                        )
                        if candidate_protected_score > current_protected_score + 1e-9:
                            continue
                    candidate_index = int(candidate_indices[candidate_position])
                    key = (candidate_p95, score, slot, candidate_index)
                    if best_swap is None or key < best_swap[0]:
                        best_swap = (key, slot, candidate_position)

            if best_swap is None:
                break
            _, slot, candidate_position = best_swap
            selected[slot] = int(candidate_indices[candidate_position])
            selected_positions[slot] = candidate_position

        return selected

    @classmethod
    def _select_quality_palette(
        cls,
        pixels: np.ndarray,
        candidate_indices: np.ndarray,
        all_rgb: np.ndarray,
        all_lab: np.ndarray,
        forced: list[int],
        max_colors: int,
        target_p95_delta_e_00: float | None,
        importance_weights: np.ndarray | None = None,
    ) -> np.ndarray:
        """Select real palette swatches against the same ΔE00 used by QA.

        The previous automatic limit estimated a colour count from grid size and
        content complexity before considering the actual palette gamut. This
        selector instead adds the swatch that produces the greatest weighted
        error reduction. Optional structure weights give focal and small-detail
        regions more influence, while the stop decision still uses the unweighted
        source population so P95 retains its original quality meaning.
        """
        selected = list(dict.fromkeys(forced))
        max_colors = max(len(selected), min(max_colors, len(candidate_indices)))
        if len(selected) >= max_colors:
            return np.asarray(selected, dtype=np.int32)

        representatives, objective_weights, population_weights = cls._representative_pixels(
            pixels,
            importance_weights,
        )
        distances = _distances(
            representatives,
            all_rgb[candidate_indices],
            DistanceMethod.ciede2000,
            all_lab[candidate_indices],
        )
        position_by_index = {int(index): position for position, index in enumerate(candidate_indices)}
        selected_positions = [position_by_index[index] for index in selected]
        if selected_positions:
            current_error = np.min(distances[:, selected_positions], axis=1)
        else:
            first_position = int(np.argmin((distances**2 * objective_weights[:, None]).sum(axis=0)))
            selected.append(int(candidate_indices[first_position]))
            selected_positions.append(first_position)
            current_error = distances[:, first_position]

        minimum_colors = min(max_colors, max(len(selected), min(8, len(representatives))))
        while len(selected) < max_colors:
            selected_set = set(selected_positions)
            remaining_positions = np.asarray(
                [position for position in range(len(candidate_indices)) if position not in selected_set],
                dtype=np.int32,
            )
            if not len(remaining_positions):
                break
            resulting_error = np.minimum(
                current_error[:, None],
                distances[:, remaining_positions],
            )
            tail_weights = cls._tail_objective_weights(
                current_error,
                objective_weights,
                population_weights,
            )
            improvement = ((current_error[:, None] ** 2 - resulting_error**2) * tail_weights[:, None]).sum(axis=0)
            local_position = int(np.argmax(improvement))
            selected_position = int(remaining_positions[local_position])
            selected.append(int(candidate_indices[selected_position]))
            selected_positions.append(selected_position)
            current_error = resulting_error[:, local_position]

            if len(selected) < minimum_colors or target_p95_delta_e_00 is None:
                continue
            p95 = cls._weighted_quantile(current_error, population_weights, 0.95)
            if (
                p95 <= target_p95_delta_e_00
                and cls._population_p95_delta_e(
                    pixels,
                    all_rgb[np.asarray(selected, dtype=np.int32)],
                    all_lab[np.asarray(selected, dtype=np.int32)],
                )
                <= target_p95_delta_e_00
            ):
                break
        before_refinement = list(selected)
        selected = cls._refine_quality_palette(
            distances,
            candidate_indices,
            selected,
            set(forced),
            objective_weights,
            population_weights,
        )
        if selected != before_refinement:
            before_p95 = cls._population_p95_delta_e(
                pixels,
                all_rgb[np.asarray(before_refinement, dtype=np.int32)],
                all_lab[np.asarray(before_refinement, dtype=np.int32)],
            )
            refined_p95 = cls._population_p95_delta_e(
                pixels,
                all_rgb[np.asarray(selected, dtype=np.int32)],
                all_lab[np.asarray(selected, dtype=np.int32)],
            )
            if refined_p95 > before_p95 + 1e-9:
                selected = before_refinement
        return np.asarray(selected, dtype=np.int32)

    @staticmethod
    def _cleanup_components(
        matched_palette_indices: np.ndarray,
        rgba: np.ndarray,
        visible: np.ndarray,
        all_rgb: np.ndarray,
        all_lab: np.ndarray,
        locked: set[str],
        codes: list[str],
        level: CleanupLevel,
        method: DistanceMethod,
    ) -> np.ndarray:
        if level == CleanupLevel.off or rgba.ndim != 3:
            return matched_palette_indices

        height, width = rgba.shape[:2]
        full_indices = np.full(height * width, -1, dtype=np.int32)
        full_indices[visible] = matched_palette_indices
        grid = full_indices.reshape(height, width)
        locked_indices = {index for index, code in enumerate(codes) if code in locked}
        # The light compatibility mode only removes an unambiguous isolated
        # cell. Medium cleanup is handled by the edge-aware spatial optimiser
        # below, which evaluates the complete local energy instead of using a
        # component-size rule.
        if level == CleanupLevel.light:
            maximum_component_size, minimum_boundary_support, tolerance, passes = 1, 7, 1.75, 1
        else:
            grid_scale = 1 + int(round(np.sqrt(max(1, height * width)) / 24))
            maximum_component_size = max(2, min(5, grid_scale))
            minimum_boundary_support, tolerance, passes = 2, 4.5, 2

        connected_offsets = ((-1, 0), (1, 0), (0, -1), (0, 1))
        boundary_offsets = (
            (-1, -1),
            (-1, 0),
            (-1, 1),
            (0, -1),
            (0, 1),
            (1, -1),
            (1, 0),
            (1, 1),
        )

        for _ in range(passes):
            updated = grid.copy()
            visited = np.zeros((height, width), dtype=bool)
            changed = False
            for row in range(height):
                for column in range(width):
                    current = int(grid[row, column])
                    if current < 0 or visited[row, column]:
                        continue

                    component: list[tuple[int, int]] = []
                    component_too_large = False
                    queue = deque([(row, column)])
                    visited[row, column] = True
                    while queue:
                        current_row, current_column = queue.popleft()
                        if not component_too_large:
                            component.append((current_row, current_column))
                            if len(component) > maximum_component_size:
                                component.clear()
                                component_too_large = True
                        for row_offset, column_offset in connected_offsets:
                            next_row, next_column = current_row + row_offset, current_column + column_offset
                            if not (0 <= next_row < height and 0 <= next_column < width):
                                continue
                            if visited[next_row, next_column] or int(grid[next_row, next_column]) != current:
                                continue
                            visited[next_row, next_column] = True
                            queue.append((next_row, next_column))

                    if current in locked_indices or component_too_large:
                        continue

                    boundary_counts: dict[int, int] = {}
                    for current_row, current_column in component:
                        for row_offset, column_offset in boundary_offsets:
                            next_row, next_column = current_row + row_offset, current_column + column_offset
                            if not (0 <= next_row < height and 0 <= next_column < width):
                                continue
                            neighbour = int(grid[next_row, next_column])
                            if neighbour >= 0 and neighbour != current:
                                boundary_counts[neighbour] = boundary_counts.get(neighbour, 0) + 1
                    candidates = [
                        index for index, support in boundary_counts.items() if support >= minimum_boundary_support
                    ]
                    if not candidates:
                        continue

                    source = np.asarray(
                        [rgba[current_row, current_column, :3] for current_row, current_column in component],
                        dtype=np.float64,
                    )
                    candidate_array = np.asarray(candidates, dtype=np.int32)
                    current_error = float(_distances(source, all_rgb[[current]], method, all_lab[[current]]).mean())
                    replacement_errors = _distances(
                        source,
                        all_rgb[candidate_array],
                        method,
                        all_lab[candidate_array],
                    ).mean(axis=0)
                    # When two candidates are perceptually equivalent, prefer
                    # the one forming the stronger surrounding region.
                    support_bonus = (
                        np.asarray([np.log1p(boundary_counts[index]) for index in candidates], dtype=np.float64) * 0.08
                    )
                    winner_position = int(np.argmin(replacement_errors - support_bonus))
                    winner = int(candidate_array[winner_position])
                    replacement_error = float(replacement_errors[winner_position])
                    if replacement_error <= current_error + tolerance:
                        for current_row, current_column in component:
                            updated[current_row, current_column] = winner
                        changed = True
            grid = updated
            if not changed:
                break
        return grid.reshape(-1)[visible]

    @staticmethod
    def _spatial_regularize(
        matched_palette_indices: np.ndarray,
        rgba: np.ndarray,
        visible: np.ndarray,
        all_rgb: np.ndarray,
        all_lab: np.ndarray,
        locked: set[str],
        codes: list[str],
        method: DistanceMethod,
        importance_map: np.ndarray | None = None,
    ) -> np.ndarray:
        """Minimise an edge-aware data-plus-smoothness energy on the bead grid.

        Every editable cell may keep its current swatch or adopt one of its four
        neighbours. The data term is the selected perceptual colour distance to
        the sampled source cell. The pairwise Potts term favours continuous colour
        regions only where neighbouring source pixels are perceptually similar;
        its weight rapidly approaches zero across a real source edge. Red/black
        updates make each pass deterministic and avoid synchronous oscillation.
        """
        if rgba.ndim != 3 or not len(matched_palette_indices):
            return matched_palette_indices

        height, width = rgba.shape[:2]
        full_indices = np.full(height * width, -1, dtype=np.int32)
        full_indices[visible] = matched_palette_indices
        grid = full_indices.reshape(height, width)
        locked_indices = {index for index, code in enumerate(codes) if code in locked}
        raw_importance = (
            np.ones(height * width, dtype=np.float32)
            if importance_map is None
            else np.asarray(importance_map, dtype=np.float32).reshape(-1)
        )
        if len(raw_importance) != height * width:
            raise ValueError("结构权重尺寸必须与目标网格一致")
        importance_grid = np.clip(raw_importance.reshape(height, width), 0.25, 8.0)

        source_rgb = rgba[..., :3]
        source_lab = rgb_to_lab(source_rgb).astype(np.float32)
        source_oklab = rgb_to_oklab(source_rgb) if method == DistanceMethod.fidelity else None
        palette_oklab = rgb_to_oklab(all_rgb) if method == DistanceMethod.fidelity else None

        horizontal_delta = _delta_e_2000(source_lab[:, :-1], source_lab[:, 1:])
        vertical_delta = _delta_e_2000(source_lab[:-1, :], source_lab[1:, :])
        edge_sigma = 4.0
        horizontal_weight = np.exp(-((horizontal_delta / edge_sigma) ** 2)).astype(np.float32)
        vertical_weight = np.exp(-((vertical_delta / edge_sigma) ** 2)).astype(np.float32)
        horizontal_weight *= visible.reshape(height, width)[:, :-1] & visible.reshape(height, width)[:, 1:]
        vertical_weight *= visible.reshape(height, width)[:-1, :] & visible.reshape(height, width)[1:, :]
        if importance_map is not None:
            horizontal_protection = np.maximum(importance_grid[:, :-1], importance_grid[:, 1:])
            vertical_protection = np.maximum(importance_grid[:-1, :], importance_grid[1:, :])
            horizontal_weight /= np.maximum(horizontal_protection, 1.0)
            vertical_weight /= np.maximum(vertical_protection, 1.0)

        grid_flat = grid.reshape(-1)
        source_rgb_flat = source_rgb.reshape(-1, 3)
        source_lab_flat = source_lab.reshape(-1, 3)
        source_oklab_flat = source_oklab.reshape(-1, 3) if source_oklab is not None else None
        importance_flat = importance_grid.reshape(-1)
        visible_grid = visible.reshape(height, width)
        checkerboard = np.bitwise_xor(
            (np.arange(height, dtype=np.uint8) & 1)[:, None],
            (np.arange(width, dtype=np.uint8) & 1)[None, :],
        )
        smoothness_strength = 7.5
        maximum_passes = 3
        chunk_size = 65_536

        def data_energy(positions: np.ndarray, proposals: np.ndarray) -> np.ndarray:
            energy = np.full(len(positions), np.inf, dtype=np.float64)
            valid = proposals >= 0
            valid_positions = np.flatnonzero(valid)
            for start in range(0, len(valid_positions), chunk_size):
                local = valid_positions[start : start + chunk_size]
                source_positions = positions[local]
                labels = proposals[local]
                distances = _paired_distances(
                    source_rgb_flat[source_positions],
                    all_rgb[labels],
                    method,
                    source_lab_flat[source_positions],
                    all_lab[labels],
                    source_oklab_flat[source_positions] if source_oklab_flat is not None else None,
                    palette_oklab[labels] if palette_oklab is not None else None,
                )
                energy[local] = distances**2 * importance_flat[source_positions]
            return energy

        def local_energy(
            positions: np.ndarray,
            proposals: np.ndarray,
            adjacent_labels: tuple[np.ndarray, ...],
            adjacent_weights: tuple[np.ndarray, ...],
        ) -> np.ndarray:
            energy = data_energy(positions, proposals)
            valid = proposals >= 0
            for neighbours, weights in zip(adjacent_labels, adjacent_weights, strict=True):
                connected = valid & (neighbours >= 0)
                energy[connected] += (
                    smoothness_strength * weights[connected] * (proposals[connected] != neighbours[connected])
                )
            return energy

        for _ in range(maximum_passes):
            pass_changes = 0
            for parity in (0, 1):
                editable = visible_grid & (checkerboard == parity)
                if locked_indices:
                    editable &= ~np.isin(grid, tuple(locked_indices))
                positions = np.flatnonzero(editable.reshape(-1))
                if not len(positions):
                    continue

                rows, columns = np.divmod(positions, width)
                adjacent_labels_list: list[np.ndarray] = []
                adjacent_weights_list: list[np.ndarray] = []
                for row_offset, column_offset in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                    neighbour_rows = rows + row_offset
                    neighbour_columns = columns + column_offset
                    inside = (
                        (neighbour_rows >= 0)
                        & (neighbour_rows < height)
                        & (neighbour_columns >= 0)
                        & (neighbour_columns < width)
                    )
                    neighbour_labels = np.full(len(positions), -1, dtype=np.int32)
                    neighbour_weights = np.zeros(len(positions), dtype=np.float32)
                    neighbour_positions = neighbour_rows[inside] * width + neighbour_columns[inside]
                    neighbour_labels[inside] = grid_flat[neighbour_positions]
                    if row_offset == -1:
                        neighbour_weights[inside] = vertical_weight[rows[inside] - 1, columns[inside]]
                    elif row_offset == 1:
                        neighbour_weights[inside] = vertical_weight[rows[inside], columns[inside]]
                    elif column_offset == -1:
                        neighbour_weights[inside] = horizontal_weight[rows[inside], columns[inside] - 1]
                    else:
                        neighbour_weights[inside] = horizontal_weight[rows[inside], columns[inside]]
                    adjacent_labels_list.append(neighbour_labels)
                    adjacent_weights_list.append(neighbour_weights)

                adjacent_labels = tuple(adjacent_labels_list)
                adjacent_weights = tuple(adjacent_weights_list)
                current = grid_flat[positions].copy()
                best_labels = current.copy()
                best_energy = local_energy(positions, current, adjacent_labels, adjacent_weights)
                for proposal in adjacent_labels:
                    proposal_energy = local_energy(positions, proposal, adjacent_labels, adjacent_weights)
                    improves = proposal_energy + 1e-9 < best_energy
                    best_labels[improves] = proposal[improves]
                    best_energy[improves] = proposal_energy[improves]

                changed = best_labels != current
                if np.any(changed):
                    grid_flat[positions[changed]] = best_labels[changed]
                    pass_changes += int(np.count_nonzero(changed))
            if not pass_changes:
                break

        # A pixel-wise ICM move can be trapped by the temporary boundary that
        # appears when only one cell of a small island changes. Evaluate compact
        # connected islands as a single proposal with a stronger edge-weighted
        # region prior, so the island can change atomically without relaxing
        # protection across real source edges.
        connected_offsets = ((-1, 0), (1, 0), (0, -1), (0, 1))
        maximum_component_size = 8
        component_smoothness_strength = 18.0
        for _ in range(2):
            visited = np.zeros((height, width), dtype=bool)
            component_changes = 0
            for row in range(height):
                for column in range(width):
                    current = int(grid[row, column])
                    if current < 0 or visited[row, column]:
                        continue
                    component: list[tuple[int, int]] = []
                    too_large = False
                    queue = deque([(row, column)])
                    visited[row, column] = True
                    while queue:
                        current_row, current_column = queue.popleft()
                        if not too_large:
                            component.append((current_row, current_column))
                            if len(component) > maximum_component_size:
                                component.clear()
                                too_large = True
                        for row_offset, column_offset in connected_offsets:
                            next_row, next_column = current_row + row_offset, current_column + column_offset
                            if not (0 <= next_row < height and 0 <= next_column < width):
                                continue
                            if visited[next_row, next_column] or int(grid[next_row, next_column]) != current:
                                continue
                            visited[next_row, next_column] = True
                            queue.append((next_row, next_column))

                    if too_large or current in locked_indices:
                        continue

                    boundary_labels: list[int] = []
                    boundary_weights: list[float] = []
                    component_coordinates = set(component)
                    for current_row, current_column in component:
                        for row_offset, column_offset in connected_offsets:
                            next_row, next_column = current_row + row_offset, current_column + column_offset
                            if not (0 <= next_row < height and 0 <= next_column < width):
                                continue
                            if (next_row, next_column) in component_coordinates:
                                continue
                            neighbour = int(grid[next_row, next_column])
                            if neighbour < 0:
                                continue
                            if row_offset == -1:
                                weight = vertical_weight[current_row - 1, current_column]
                            elif row_offset == 1:
                                weight = vertical_weight[current_row, current_column]
                            elif column_offset == -1:
                                weight = horizontal_weight[current_row, current_column - 1]
                            else:
                                weight = horizontal_weight[current_row, current_column]
                            boundary_labels.append(neighbour)
                            boundary_weights.append(float(weight))
                    if not boundary_labels:
                        continue

                    positions = np.asarray(
                        [current_row * width + current_column for current_row, current_column in component],
                        dtype=np.int64,
                    )
                    current_proposal = np.full(len(positions), current, dtype=np.int32)
                    current_energy = float(data_energy(positions, current_proposal).sum())
                    boundary_array = np.asarray(boundary_labels, dtype=np.int32)
                    weight_array = np.asarray(boundary_weights, dtype=np.float64)
                    current_energy += component_smoothness_strength * float(
                        weight_array[current != boundary_array].sum()
                    )
                    best_label = current
                    best_energy = current_energy
                    for candidate in sorted(set(boundary_labels)):
                        proposal = np.full(len(positions), candidate, dtype=np.int32)
                        candidate_energy = float(data_energy(positions, proposal).sum())
                        candidate_energy += component_smoothness_strength * float(
                            weight_array[candidate != boundary_array].sum()
                        )
                        if candidate_energy + 1e-9 < best_energy:
                            best_label = candidate
                            best_energy = candidate_energy
                    if best_label != current:
                        for current_row, current_column in component:
                            grid[current_row, current_column] = best_label
                        component_changes += len(component)
            if not component_changes:
                break
        return grid_flat[visible]

    def _cleanup_isolated(
        self,
        matched_palette_indices: np.ndarray,
        rgba: np.ndarray,
        visible: np.ndarray,
        all_rgb: np.ndarray,
        all_lab: np.ndarray,
        locked: set[str],
        codes: list[str],
        level: CleanupLevel,
        method: DistanceMethod,
        importance_map: np.ndarray | None = None,
    ) -> np.ndarray:
        if level == CleanupLevel.off:
            return matched_palette_indices
        if level == CleanupLevel.light:
            return self._cleanup_components(
                matched_palette_indices,
                rgba,
                visible,
                all_rgb,
                all_lab,
                locked,
                codes,
                level,
                method,
            )
        return self._spatial_regularize(
            matched_palette_indices,
            rgba,
            visible,
            all_rgb,
            all_lab,
            locked,
            codes,
            method,
            importance_map,
        )

    def match(
        self,
        rgba: np.ndarray,
        palette: dict[str, Any],
        method: DistanceMethod,
        disabled_colors: list[str] | None = None,
        locked_colors: list[str] | None = None,
        max_colors: int | None = None,
        minimum_color_count: int = 0,
        transparent_background: bool = True,
        cleanup_level: CleanupLevel = CleanupLevel.light,
        auto_color_limit: bool = False,
        target_p95_delta_e_00: float = 6.0,
        importance_map: np.ndarray | None = None,
    ) -> MatchResult:
        color_records = [color for color in palette["colors"] if color.get("available", True)]
        disabled = set(disabled_colors or [])
        locked = set(locked_colors or [])
        codes = [color["code"] for color in color_records]
        unknown_locks = locked - set(codes)
        if unknown_locks:
            raise validation_error(
                f"锁定色号不存在或不可用: {', '.join(sorted(unknown_locks))}", "INVALID_LOCKED_COLOR"
            )
        candidate_indices = np.array(
            [index for index, code in enumerate(codes) if code not in disabled], dtype=np.int32
        )
        if not len(candidate_indices):
            raise validation_error("禁用色号后没有可用颜色", "EMPTY_PALETTE")

        flattened = rgba.reshape(-1, 4)
        visible = flattened[:, 3] > 5 if transparent_background else np.ones(len(flattened), dtype=bool)
        source_rgb = flattened[visible, :3].astype(np.float64)
        visible_importance = None
        if importance_map is not None:
            flattened_importance = np.asarray(importance_map, dtype=np.float64).reshape(-1)
            if len(flattened_importance) != len(flattened):
                raise ValueError("结构权重尺寸必须与目标网格一致")
            visible_importance = flattened_importance[visible]
        selection_importance = None if visible_importance is None else np.clip(visible_importance**3, 0.1, 64.0)
        all_rgb = np.asarray([color["rgb"] for color in color_records], dtype=np.float64)
        all_lab = palette_records_lab(color_records)
        if not len(source_rgb):
            return MatchResult([None] * len(flattened), np.empty((0, 3)), 0)

        should_select = bool(max_colors) and (auto_color_limit or int(max_colors) < len(candidate_indices))
        if should_select:
            ceiling = min(int(max_colors or len(candidate_indices)), len(candidate_indices))
            forced = [index for index, code in enumerate(codes) if code in locked and code not in disabled]
            if auto_color_limit or method == DistanceMethod.ciede2000:
                selected = self._select_quality_palette(
                    source_rgb,
                    candidate_indices,
                    all_rgb,
                    all_lab,
                    forced,
                    ceiling,
                    target_p95_delta_e_00 if auto_color_limit else None,
                    selection_importance,
                )
            elif method == DistanceMethod.fidelity:
                selected = self._select_fidelity_palette(
                    source_rgb,
                    candidate_indices,
                    all_rgb,
                    all_lab,
                    forced,
                    ceiling,
                )
            else:
                initial = self._nearest(
                    source_rgb,
                    all_rgb[candidate_indices],
                    method,
                    all_lab[candidate_indices],
                )
                initial_palette_indices = candidate_indices[initial]
                frequencies = np.bincount(initial_palette_indices, minlength=len(codes))
                diversity_lab = rgb_to_lab(all_rgb) if method == DistanceMethod.rgb else all_lab
                selected = self._select_balanced_palette(
                    frequencies,
                    candidate_indices,
                    diversity_lab,
                    forced,
                    ceiling,
                )
            if not len(selected):
                selected = candidate_indices[:1]
            matched_palette_indices = selected[self._nearest(source_rgb, all_rgb[selected], method, all_lab[selected])]
        else:
            selected = candidate_indices
            matched_palette_indices = selected[self._nearest(source_rgb, all_rgb[selected], method, all_lab[selected])]

        if minimum_color_count > 1:
            frequencies = np.bincount(matched_palette_indices, minlength=len(codes))
            rare = {
                index
                for index, count in enumerate(frequencies)
                if 0 < count < minimum_color_count and codes[index] not in locked
            }
            retained = [
                index
                for index, count in enumerate(frequencies)
                if count >= minimum_color_count or codes[index] in locked
            ]
            if not retained:
                retained = [int(np.argmax(frequencies))]
            if rare:
                mask = np.isin(matched_palette_indices, list(rare))
                matched_palette_indices[mask] = np.asarray(retained)[
                    self._nearest(source_rgb[mask], all_rgb[retained], method, all_lab[retained])
                ]

        before_cleanup = matched_palette_indices.copy()
        matched_palette_indices = self._cleanup_isolated(
            matched_palette_indices,
            rgba,
            visible,
            all_rgb,
            all_lab,
            locked,
            codes,
            cleanup_level,
            method,
            importance_map,
        )
        cleanup_adjusted_cell_count = int(np.count_nonzero(matched_palette_indices != before_cleanup))

        cells: list[str | None] = [None] * len(flattened)
        for index, palette_index in zip(np.flatnonzero(visible), matched_palette_indices, strict=True):
            cells[int(index)] = codes[int(palette_index)]
        used_palette_count = int(len(np.unique(matched_palette_indices)))
        return MatchResult(
            cells,
            all_rgb[matched_palette_indices],
            used_palette_count,
            cleanup_adjusted_cell_count,
        )
