from __future__ import annotations

from fastapi import APIRouter, Depends, File, UploadFile, status
from PIL import Image

from app.api.v1.auth import AuthenticatedUser, current_user, require_owner
from app.core.config import get_settings
from app.schemas.common import success
from app.schemas.image import ImagePreprocessRequest
from app.services.auth_service import get_auth_service
from app.services.image_processor import decode_image, preprocess_image, save_png
from app.services.image_validator import ImageValidator, safe_filename
from app.services.storage_service import get_storage, utc_now

router = APIRouter(prefix="/images", tags=["images"])


def _image_payload(metadata: dict[str, object]) -> dict[str, object]:
    settings, storage = get_settings(), get_storage()
    payload = {
        "image_id": metadata["image_id"],
        "filename": metadata["filename"],
        "width": metadata["width"],
        "height": metadata["height"],
        "mime_type": metadata["mime_type"],
        "has_alpha": metadata["has_alpha"],
        "preview_url": storage.media_url(settings.storage_dir / str(metadata["preview_path"]), settings.storage_dir),
        "source_url": storage.media_url(settings.storage_dir / str(metadata["storage_path"]), settings.storage_dir),
    }
    if metadata.get("parent_image_id"):
        payload["parent_image_id"] = metadata["parent_image_id"]
    if metadata.get("settings"):
        payload["settings"] = metadata["settings"]
    return payload


def _save_image(
    image_id: str,
    filename: str,
    image: Image.Image,
    parent_image_id: str | None = None,
    settings_data: dict[str, object] | None = None,
) -> dict[str, object]:
    settings, storage = get_settings(), get_storage()
    directory = storage.image_dir(image_id)
    source_path, preview_path = directory / "source.png", directory / "preview.png"
    save_png(image, source_path)
    preview = image.copy()
    preview.thumbnail((1_600, 1_600), Image.Resampling.LANCZOS)
    save_png(preview, preview_path)
    metadata: dict[str, object] = {
        "image_id": image_id,
        "filename": filename,
        "width": image.width,
        "height": image.height,
        "mime_type": "image/png",
        "has_alpha": True,
        "storage_path": str(source_path.relative_to(settings.storage_dir)),
        "preview_path": str(preview_path.relative_to(settings.storage_dir)),
        "parent_image_id": parent_image_id,
        "settings": settings_data or {},
        "created_at": utc_now(),
    }
    storage.save_image_metadata(metadata)
    return metadata


@router.post("/upload", status_code=status.HTTP_201_CREATED)
async def upload_image(
    file: UploadFile = File(...), user: AuthenticatedUser = Depends(current_user)
) -> dict[str, object]:
    settings, storage = get_settings(), get_storage()
    content = await file.read(settings.max_upload_size_mb * 1024 * 1024 + 1)
    verified = ImageValidator(settings).validate(content)
    image_id = storage.new_id("img")
    directory = storage.image_dir(image_id)
    source_path, preview_path = directory / f"source{verified.extension}", directory / "preview.png"
    directory.mkdir(parents=True, exist_ok=True)
    source_path.write_bytes(content)
    image = decode_image(content)
    preview = image.copy()
    preview.thumbnail((1_600, 1_600), Image.Resampling.LANCZOS)
    save_png(preview, preview_path)
    metadata: dict[str, object] = {
        "image_id": image_id,
        "filename": safe_filename(file.filename),
        # The response reflects the EXIF-corrected image that later conversion uses.
        "width": image.width,
        "height": image.height,
        "mime_type": verified.mime_type,
        "has_alpha": verified.has_alpha,
        "storage_path": str(source_path.relative_to(settings.storage_dir)),
        "preview_path": str(preview_path.relative_to(settings.storage_dir)),
        "parent_image_id": None,
        "settings": {},
        "created_at": utc_now(),
    }
    storage.save_image_metadata(metadata)
    get_auth_service().claim(user.id, "image", image_id)
    return success(_image_payload(metadata))


@router.get("/{image_id}")
def get_image(image_id: str, user: AuthenticatedUser = Depends(current_user)) -> dict[str, object]:
    require_owner(user, "image", image_id)
    return success(_image_payload(get_storage().load_image_metadata(image_id)))


@router.post("/preprocess")
def preprocess(request: ImagePreprocessRequest, user: AuthenticatedUser = Depends(current_user)) -> dict[str, object]:
    settings, storage = get_settings(), get_storage()
    require_owner(user, "image", request.image_id)
    original = storage.load_image_metadata(request.image_id)
    source_path = settings.storage_dir / str(original["storage_path"])
    image = decode_image(source_path.read_bytes())
    processed = preprocess_image(image, request)
    metadata = _save_image(
        storage.new_id("img"),
        f"processed-{original['filename']}",
        processed,
        request.image_id,
        request.model_dump(mode="json", exclude={"image_id"}),
    )
    get_auth_service().claim(user.id, "image", str(metadata["image_id"]))
    payload = _image_payload(metadata)
    payload["parent_image_id"] = request.image_id
    payload["settings"] = metadata["settings"]
    return success(payload)
