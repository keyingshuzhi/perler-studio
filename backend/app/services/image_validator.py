from __future__ import annotations

import io
import re
from dataclasses import dataclass

from PIL import Image, UnidentifiedImageError

from app.core.config import Settings, get_settings
from app.core.exceptions import AppError

_FORMAT_INFO = {
    "PNG": (".png", "image/png"),
    "JPEG": (".jpg", "image/jpeg"),
    "WEBP": (".webp", "image/webp"),
}


@dataclass(frozen=True)
class ValidatedImage:
    extension: str
    mime_type: str
    width: int
    height: int
    has_alpha: bool


def safe_filename(name: str | None) -> str:
    candidate = (name or "image").replace("\\", "/").split("/")[-1]
    candidate = re.sub(r"[^A-Za-z0-9._-]", "_", candidate).strip("._")
    return candidate[:120] or "image"


class ImageValidator:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    def validate(self, content: bytes) -> ValidatedImage:
        max_bytes = self.settings.max_upload_size_mb * 1024 * 1024
        if not content:
            raise AppError(422, "EMPTY_UPLOAD", "上传文件为空")
        if len(content) > max_bytes:
            raise AppError(413, "UPLOAD_FILE_TOO_LARGE", f"上传文件超过 {self.settings.max_upload_size_mb} MB 限制")
        try:
            with Image.open(io.BytesIO(content)) as image:
                image.verify()
            with Image.open(io.BytesIO(content)) as image:
                image.load()
                if image.format not in _FORMAT_INFO:
                    raise AppError(415, "UNSUPPORTED_IMAGE_TYPE", "仅支持 PNG、JPG/JPEG 和 WebP 图片")
                width, height = image.size
                if width * height > self.settings.max_image_pixels:
                    raise AppError(413, "IMAGE_PIXEL_LIMIT_EXCEEDED", "图片像素总量超过限制")
                if max(width, height) > 10_000:
                    raise AppError(413, "IMAGE_DIMENSION_LIMIT_EXCEEDED", "图片边长超过 10000 像素限制")
                extension, mime_type = _FORMAT_INFO[image.format]
                has_alpha = "A" in image.getbands() or image.info.get("transparency") is not None
        except (UnidentifiedImageError, OSError, SyntaxError) as error:
            raise AppError(422, "INVALID_IMAGE", "无法识别或读取上传的图片") from error
        return ValidatedImage(extension, mime_type, width, height, has_alpha)
