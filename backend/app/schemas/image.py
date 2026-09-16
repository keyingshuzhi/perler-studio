from __future__ import annotations

from pydantic import BaseModel, Field


class Crop(BaseModel):
    x: int = Field(ge=0)
    y: int = Field(ge=0)
    width: int = Field(gt=0)
    height: int = Field(gt=0)


class ImagePreprocessRequest(BaseModel):
    image_id: str = Field(min_length=4, max_length=80)
    crop: Crop | None = None
    rotate: int = Field(default=0, ge=-360, le=360)
    brightness: float = Field(default=1.0, ge=0, le=3)
    contrast: float = Field(default=1.0, ge=0, le=3)
    saturation: float = Field(default=1.0, ge=0, le=3)
    sharpen: float = Field(default=0.0, ge=0, le=3)
    remove_background: bool = False
    background_tolerance: int = Field(default=24, ge=0, le=255)


class ImageInfo(BaseModel):
    image_id: str
    filename: str
    width: int
    height: int
    mime_type: str
    has_alpha: bool
    preview_url: str
    source_url: str


class ImagePreprocessResponse(ImageInfo):
    parent_image_id: str
    settings: dict[str, object]
