from __future__ import annotations

import io
from typing import TYPE_CHECKING

import numpy as np
from PIL import Image, ImageEnhance, ImageFilter, ImageOps

from app.core.exceptions import validation_error
from app.schemas.image import ImagePreprocessRequest
from app.schemas.pattern import PatternGenerateRequest

if TYPE_CHECKING:
    from pathlib import Path


def decode_image(content: bytes) -> Image.Image:
    """Decode a user image, honour EXIF orientation, and normalize to RGBA."""
    with Image.open(io.BytesIO(content)) as source:
        source.load()
        return ImageOps.exif_transpose(source).convert("RGBA")


def save_png(image: Image.Image, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path, format="PNG", optimize=True)


def _remove_flat_background(image: Image.Image, tolerance: int) -> Image.Image:
    """Remove a near-uniform background estimated from the four corner pixels.

    This intentionally conservative operation is deterministic and cheap; semantic
    background removal remains an optional future worker feature.
    """
    pixels = np.asarray(image).copy()
    height, width = pixels.shape[:2]
    samples = np.array(
        [
            pixels[0, 0, :3],
            pixels[0, width - 1, :3],
            pixels[height - 1, 0, :3],
            pixels[height - 1, width - 1, :3],
        ],
        dtype=np.float32,
    )
    background = samples.mean(axis=0)
    distance = np.sqrt(((pixels[..., :3].astype(np.float32) - background) ** 2).sum(axis=2))
    # Feather the mask, so nearly matching edge pixels do not leave a hard fringe.
    start, end = float(tolerance), float(max(tolerance + 12, 1))
    alpha_factor = np.clip((distance - start) / (end - start), 0.0, 1.0)
    pixels[..., 3] = np.minimum(pixels[..., 3], (alpha_factor * 255).astype(np.uint8))
    return Image.fromarray(pixels, "RGBA")


def preprocess_image(image: Image.Image, request: ImagePreprocessRequest) -> Image.Image:
    result = image.copy().convert("RGBA")
    if request.crop:
        crop = request.crop
        if crop.x + crop.width > result.width or crop.y + crop.height > result.height:
            raise validation_error("裁剪区域超出图片边界", "INVALID_CROP")
        result = result.crop((crop.x, crop.y, crop.x + crop.width, crop.y + crop.height))
    if request.rotate:
        result = result.rotate(-request.rotate, expand=True, resample=Image.Resampling.BICUBIC)
    if request.brightness != 1:
        result = ImageEnhance.Brightness(result).enhance(request.brightness)
    if request.contrast != 1:
        result = ImageEnhance.Contrast(result).enhance(request.contrast)
    if request.saturation != 1:
        result = ImageEnhance.Color(result).enhance(request.saturation)
    if request.sharpen:
        result = result.filter(ImageFilter.UnsharpMask(radius=1.5, percent=int(request.sharpen * 100), threshold=2))
    if request.remove_background:
        result = _remove_flat_background(result, request.background_tolerance)
    return result


def _crop_to_subject(
    image: Image.Image, target_ratio: float, focus_x: float, focus_y: float, zoom: float
) -> tuple[Image.Image, float, float]:
    """Crop to the final aspect ratio around a user-selected focal point.

    The crop remains inside the original image, so moving the focal target never
    creates artificial pixels at the border. The returned focus position is
    expressed in the resulting crop and is reused by background/detail effects.
    """
    source_ratio = image.width / image.height
    if source_ratio > target_ratio:
        crop_height = image.height
        crop_width = crop_height * target_ratio
    else:
        crop_width = image.width
        crop_height = crop_width / target_ratio
    crop_width = max(1, min(image.width, round(crop_width / zoom)))
    crop_height = max(1, min(image.height, round(crop_height / zoom)))
    desired_left = image.width * focus_x - crop_width / 2
    desired_top = image.height * focus_y - crop_height / 2
    left = min(max(0, round(desired_left)), image.width - crop_width)
    top = min(max(0, round(desired_top)), image.height - crop_height)
    focus_in_crop_x = min(1.0, max(0.0, (image.width * focus_x - left) / crop_width))
    focus_in_crop_y = min(1.0, max(0.0, (image.height * focus_y - top) / crop_height))
    return image.crop((left, top, left + crop_width, top + crop_height)), focus_in_crop_x, focus_in_crop_y


def _focus_mask(width: int, height: int, focus_x: float, focus_y: float, radius: float) -> np.ndarray:
    """A soft elliptical focal mask that respects non-square source images."""
    y, x = np.ogrid[:height, :width]
    normalized_x = (x / max(width - 1, 1) - focus_x) / radius
    normalized_y = (y / max(height - 1, 1) - focus_y) / radius
    distance_sq = normalized_x**2 + normalized_y**2
    return np.exp(-2.6 * distance_sq)[..., None]


def prepare_conversion_image(image: Image.Image, request: PatternGenerateRequest) -> Image.Image:
    """Apply conversion-only framing and detail protection before grid sampling.

    This is deliberately heuristic rather than a claimed semantic detector: the
    creator controls the focal point, while the conversion pipeline preserves its
    local contrast/edges and gently suppresses competing background texture.
    """
    result = image.copy().convert("RGBA")
    focus_x, focus_y = request.focus_x, request.focus_y
    if request.subject_crop or request.focus_zoom > 1:
        result, focus_x, focus_y = _crop_to_subject(
            result, request.grid_width / request.grid_height, focus_x, focus_y, request.focus_zoom
        )

    priorities = {str(priority) for priority in request.detail_priorities}
    if request.background_weaken or priorities & {"facial", "text"}:
        original = np.asarray(result, dtype=np.float64)
        mask = _focus_mask(result.width, result.height, focus_x, focus_y, request.focus_radius)
        softened = result.filter(ImageFilter.GaussianBlur(radius=1.4 + request.background_weaken * 3.2))
        softened = ImageEnhance.Color(softened).enhance(1 - request.background_weaken * 0.42)
        background = np.asarray(softened, dtype=np.float64)
        weaken = (1 - mask) * request.background_weaken
        combined = original * (1 - weaken) + background * weaken
        result = Image.fromarray(np.clip(combined, 0, 255).astype(np.uint8), "RGBA")

    # Outlines benefit from a light global pass; face/text choices receive a
    # stronger focal-only pass so distant texture does not become noisy beads.
    if "outline" in priorities:
        result = result.filter(ImageFilter.UnsharpMask(radius=1.1, percent=118, threshold=3))
    if priorities & {"facial", "text"}:
        original = np.asarray(result, dtype=np.float64)
        enhanced = result.filter(ImageFilter.UnsharpMask(radius=1.5, percent=155, threshold=2))
        if "text" in priorities:
            enhanced = ImageEnhance.Contrast(enhanced).enhance(1.12)
        local_mask = _focus_mask(result.width, result.height, focus_x, focus_y, request.focus_radius)
        blended = original * (1 - local_mask * 0.78) + np.asarray(enhanced, dtype=np.float64) * local_mask * 0.78
        result = Image.fromarray(np.clip(blended, 0, 255).astype(np.uint8), "RGBA")
    return result
