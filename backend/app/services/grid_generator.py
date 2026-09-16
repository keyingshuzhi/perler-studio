from __future__ import annotations

import numpy as np
from PIL import Image

from app.schemas.pattern import ResizeMode, SamplingMode

_OVERSAMPLE = 3


def _resample_method(source: Image.Image, target_size: tuple[int, int]) -> Image.Resampling:
    """Use area-like reduction to avoid LANCZOS halos around hard edges."""
    if target_size[0] < source.width or target_size[1] < source.height:
        return Image.Resampling.BOX
    return Image.Resampling.BICUBIC


def _fit_to_canvas(image: Image.Image, width: int, height: int, mode: ResizeMode, scale: int = 1) -> Image.Image:
    target_size = (width * scale, height * scale)
    source = image.convert("RGBA")
    if mode == ResizeMode.stretch:
        return source.resize(target_size, _resample_method(source, target_size))

    resize_scale = (
        max(target_size[0] / source.width, target_size[1] / source.height)
        if mode == ResizeMode.cover
        else min(target_size[0] / source.width, target_size[1] / source.height)
    )
    resized_size = (max(1, round(source.width * resize_scale)), max(1, round(source.height * resize_scale)))
    resized = source.resize(resized_size, _resample_method(source, resized_size))
    if mode == ResizeMode.cover:
        left = max(0, (resized.width - target_size[0]) // 2)
        top = max(0, (resized.height - target_size[1]) // 2)
        return resized.crop((left, top, left + target_size[0], top + target_size[1]))

    canvas = Image.new("RGBA", target_size, (0, 0, 0, 0))
    canvas.alpha_composite(resized, ((target_size[0] - resized.width) // 2, (target_size[1] - resized.height) // 2))
    return canvas


def _edge_aware_reduce(image: Image.Image, width: int, height: int) -> Image.Image:
    """Select a colour medoid from each 3 × 3 sub-grid instead of averaging it.

    Averaging across an outline creates colours that are absent from the source and
    often absent from a bead palette. Selecting the in-cell medoid preserves the
    dominant side of an edge and greatly reduces one-cell colour fringes.
    """
    pixels = np.asarray(image, dtype=np.float64)
    samples = pixels.reshape(height, _OVERSAMPLE, width, _OVERSAMPLE, 4).transpose(0, 2, 1, 3, 4)
    samples = samples.reshape(height, width, _OVERSAMPLE * _OVERSAMPLE, 4)
    alpha = samples[..., 3]
    visible = alpha > 5
    weights = alpha[..., None] / 255.0
    weight_sum = weights.sum(axis=2, keepdims=True)
    mean_rgb = np.divide(
        (samples[..., :3] * weights).sum(axis=2, keepdims=True),
        weight_sum,
        out=np.zeros((height, width, 1, 3), dtype=np.float64),
        where=weight_sum > 0,
    )
    distances = ((samples[..., :3] - mean_rgb) ** 2).sum(axis=-1)
    distances[~visible] = np.inf
    selected = np.argmin(distances, axis=2)
    selected_samples = samples[np.arange(height)[:, None], np.arange(width)[None, :], selected]
    coverage = visible.mean(axis=2)
    selected_samples[..., 3] = np.where(coverage >= 0.5, selected_samples[..., 3], 0)
    return Image.fromarray(np.clip(selected_samples, 0, 255).astype(np.uint8), "RGBA")


def _srgb_to_linear(rgb: np.ndarray) -> np.ndarray:
    normalized = np.asarray(rgb, dtype=np.float64) / 255.0
    return np.where(normalized <= 0.04045, normalized / 12.92, ((normalized + 0.055) / 1.055) ** 2.4)


def _linear_to_srgb(linear: np.ndarray) -> np.ndarray:
    clipped = np.clip(linear, 0.0, 1.0)
    return np.where(clipped <= 0.0031308, clipped * 12.92, 1.055 * clipped ** (1 / 2.4) - 0.055) * 255.0


def _adaptive_reduce(image: Image.Image, width: int, height: int) -> Image.Image:
    """Preserve smooth-region colour while retaining hard edges.

    A grid cell in a photograph usually contains a continuous colour transition,
    for which choosing one observed sub-pixel makes the result needlessly darker
    or more saturated. At a high-contrast boundary, averaging creates a third
    colour that is not present in the image or physical palette. This reducer
    measures the perceptual spread in each 3 × 3 sub-grid: it uses an
    alpha-aware *linear-light* mean for smooth regions and a perceptual medoid
    when a cell straddles a real edge.
    """
    pixels = np.asarray(image, dtype=np.float64)
    samples = pixels.reshape(height, _OVERSAMPLE, width, _OVERSAMPLE, 4).transpose(0, 2, 1, 3, 4)
    samples = samples.reshape(height, width, _OVERSAMPLE * _OVERSAMPLE, 4)
    alpha = samples[..., 3]
    visible = alpha > 5
    weights = alpha / 255.0
    weight_sum = weights.sum(axis=2, keepdims=True)
    linear_samples = _srgb_to_linear(samples[..., :3])
    mean_linear = np.divide(
        (linear_samples * weights[..., None]).sum(axis=2),
        weight_sum,
        out=np.zeros((height, width, 3), dtype=np.float64),
        where=weight_sum > 0,
    )
    smooth_rgb = _linear_to_srgb(mean_linear)

    # RGB distances are only used to classify edge strength. The relatively
    # conservative threshold keeps gradients smooth and reserves medoids for
    # outlines/colour blocks with an obvious discontinuity.
    distances_to_mean = np.linalg.norm(samples[..., :3] - smooth_rgb[..., None, :], axis=-1)
    medoid_distances = distances_to_mean.copy()
    medoid_distances[~visible] = np.inf
    medoid = np.argmin(medoid_distances, axis=2)
    medoid_rgb = samples[np.arange(height)[:, None], np.arange(width)[None, :], medoid, :3]
    weighted_variance = np.divide(
        (np.where(visible, distances_to_mean**2, 0.0) * weights).sum(axis=2),
        weight_sum[..., 0],
        out=np.zeros((height, width), dtype=np.float64),
        where=weight_sum[..., 0] > 0,
    )
    # At least one substantial, hard colour transition must be present before
    # choosing a source sample. This avoids turning subtle photograph gradients
    # into a patchwork of arbitrary sub-samples.
    edge = np.sqrt(weighted_variance) >= 34.0
    # At a genuine edge, a conventional medoid favours the majority colour in
    # the 3 × 3 cell. That can erase a one-pixel outline, eye, or fine feature
    # even when it passes through the centre of the final bead cell. The centre
    # sample keeps the geometry aligned to the output grid; the medoid remains
    # the safe fallback where that centre is transparent.
    centre_index = (_OVERSAMPLE * _OVERSAMPLE) // 2
    centre_visible = visible[..., centre_index]
    centre_rgb = samples[..., centre_index, :3]
    edge_rgb = np.where(centre_visible[..., None], centre_rgb, medoid_rgb)
    rgb = np.where(edge[..., None], edge_rgb, smooth_rgb)
    coverage = visible.mean(axis=2)
    # Preserve a centred, thin opaque feature instead of discarding it merely
    # because it covers fewer than half of the oversampled cell.
    output_alpha = np.where((coverage >= 0.5) | centre_visible, 255, 0)
    result = np.concatenate((rgb, output_alpha[..., None]), axis=-1)
    return Image.fromarray(np.clip(result, 0, 255).astype(np.uint8), "RGBA")


def resize_to_grid(
    image: Image.Image,
    width: int,
    height: int,
    mode: ResizeMode,
    sampling_mode: SamplingMode = SamplingMode.adaptive,
) -> Image.Image:
    """Return one RGBA source colour per target grid cell.

    ``adaptive`` is the production default. It renders an oversampled image and
    uses a linear-light average in smooth regions while preserving hard edges.
    ``edge_aware`` remains available for graphic pixel art and ``smooth`` keeps
    the former single-pass resize for backwards-compatible output.
    """
    if mode == ResizeMode.pixel:
        if image.size != (width, height):
            raise ValueError("pixel 模式要求原始图片尺寸与目标网格完全一致")
        return image.convert("RGBA")
    if sampling_mode == SamplingMode.smooth:
        return _fit_to_canvas(image, width, height, mode)
    fitted = _fit_to_canvas(image, width, height, mode, scale=_OVERSAMPLE)
    if sampling_mode == SamplingMode.edge_aware:
        return _edge_aware_reduce(fitted, width, height)
    return _adaptive_reduce(fitted, width, height)
