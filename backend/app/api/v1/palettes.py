from __future__ import annotations

from fastapi import APIRouter, Depends, Response, status

from app.api.v1.auth import AuthenticatedUser, current_user, require_owner
from app.schemas.common import success
from app.schemas.palette import PaletteCreate, PaletteUpdate
from app.services.auth_service import get_auth_service
from app.services.palette_service import get_palette_service

router = APIRouter(prefix="/palettes", tags=["palettes"])


@router.get("")
def list_palettes(user: AuthenticatedUser = Depends(current_user)) -> dict[str, object]:
    owned_ids = get_auth_service().owned_ids(user.id, "palette")
    return success(
        [palette for palette in get_palette_service().list() if palette["is_system"] or palette["id"] in owned_ids]
    )


@router.get("/{palette_id}")
def get_palette(palette_id: str, user: AuthenticatedUser = Depends(current_user)) -> dict[str, object]:
    palette = get_palette_service().get(palette_id)
    if not palette["is_system"]:
        require_owner(user, "palette", palette_id)
    return success(palette)


@router.post("", status_code=status.HTTP_201_CREATED)
def create_palette(request: PaletteCreate, user: AuthenticatedUser = Depends(current_user)) -> dict[str, object]:
    palette = get_palette_service().create(request)
    get_auth_service().claim(user.id, "palette", palette["id"])
    return success(palette)


@router.put("/{palette_id}")
def update_palette(
    palette_id: str, request: PaletteUpdate, user: AuthenticatedUser = Depends(current_user)
) -> dict[str, object]:
    require_owner(user, "palette", palette_id)
    return success(get_palette_service().update(palette_id, request))


@router.delete("/{palette_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_palette(palette_id: str, user: AuthenticatedUser = Depends(current_user)) -> Response:
    require_owner(user, "palette", palette_id)
    get_palette_service().delete(palette_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
