from __future__ import annotations

from fastapi import APIRouter, Depends, Response, status

from app.api.v1.auth import AuthenticatedUser, current_user, require_owner
from app.core.exceptions import validation_error
from app.schemas.common import success
from app.schemas.design import (
    AssemblyPlanRequest,
    BlankPatternCreateRequest,
    TemplatePatternCreateRequest,
    TextPatternCreateRequest,
)
from app.schemas.pattern import PatternGenerateRequest, PatternPatchRequest
from app.services.assembly_service import build_assembly_plan
from app.services.auth_service import get_auth_service
from app.services.pattern_service import get_pattern_service
from app.services.production_service import build_production_plan

router = APIRouter(prefix="/patterns", tags=["patterns"])


@router.post("/blank", status_code=status.HTTP_201_CREATED)
def create_blank_pattern(
    request: BlankPatternCreateRequest, user: AuthenticatedUser = Depends(current_user)
) -> dict[str, object]:
    pattern = get_pattern_service().create_blank(request)
    get_auth_service().claim(user.id, "pattern", pattern["id"])
    return success(pattern)


@router.post("/template", status_code=status.HTTP_201_CREATED)
def create_template_pattern(
    request: TemplatePatternCreateRequest, user: AuthenticatedUser = Depends(current_user)
) -> dict[str, object]:
    pattern = get_pattern_service().create_template(request)
    get_auth_service().claim(user.id, "pattern", pattern["id"])
    return success(pattern)


@router.post("/text", status_code=status.HTTP_201_CREATED)
def create_text_pattern(
    request: TextPatternCreateRequest, user: AuthenticatedUser = Depends(current_user)
) -> dict[str, object]:
    pattern = get_pattern_service().create_text(request)
    get_auth_service().claim(user.id, "pattern", pattern["id"])
    return success(pattern)


@router.post("/generate", status_code=status.HTTP_201_CREATED)
def generate_pattern(
    request: PatternGenerateRequest, user: AuthenticatedUser = Depends(current_user)
) -> dict[str, object]:
    require_owner(user, "image", request.image_id)
    pattern = get_pattern_service().generate(request)
    get_auth_service().claim(user.id, "pattern", pattern["id"])
    return success(pattern)


@router.post("/preview")
def preview_pattern(
    request: PatternGenerateRequest, user: AuthenticatedUser = Depends(current_user)
) -> dict[str, object]:
    """Preview an image conversion without creating a project or persistent pattern."""
    require_owner(user, "image", request.image_id)
    return success(get_pattern_service().preview(request))


@router.post("/{pattern_id}/regenerate")
def regenerate_pattern(
    pattern_id: str, request: PatternGenerateRequest, user: AuthenticatedUser = Depends(current_user)
) -> dict[str, object]:
    require_owner(user, "pattern", pattern_id)
    require_owner(user, "image", request.image_id)
    return success(get_pattern_service().regenerate(pattern_id, request))


@router.get("/{pattern_id}")
def get_pattern(pattern_id: str, user: AuthenticatedUser = Depends(current_user)) -> dict[str, object]:
    require_owner(user, "pattern", pattern_id)
    return success(get_pattern_service().get(pattern_id))


@router.get("/{pattern_id}/assembly-plan")
def get_assembly_plan(
    pattern_id: str,
    board_width: int = 29,
    board_height: int = 29,
    overlap: int = 0,
    user: AuthenticatedUser = Depends(current_user),
) -> dict[str, object]:
    require_owner(user, "pattern", pattern_id)
    request = AssemblyPlanRequest(board_width=board_width, board_height=board_height, overlap=overlap)
    pattern = get_pattern_service().get(pattern_id)
    return success(build_assembly_plan(pattern, request.board_width, request.board_height, request.overlap))


@router.get("/{pattern_id}/production-plan")
def get_production_plan(
    pattern_id: str,
    board_template_id: str = "midi-square-29",
    overlap: int = 0,
    strategy: str = "color",
    beads_per_hour: int = 360,
    user: AuthenticatedUser = Depends(current_user),
) -> dict[str, object]:
    require_owner(user, "pattern", pattern_id)
    if not 0 <= overlap <= 12:
        raise validation_error("底板重叠格必须在 0–12 之间", "INVALID_BOARD_OVERLAP")
    pattern = get_pattern_service().get(pattern_id)
    return success(build_production_plan(pattern, board_template_id, overlap, strategy, beads_per_hour))


@router.put("/{pattern_id}")
def update_pattern(
    pattern_id: str, request: PatternPatchRequest, user: AuthenticatedUser = Depends(current_user)
) -> dict[str, object]:
    require_owner(user, "pattern", pattern_id)
    return success(get_pattern_service().patch(pattern_id, request))


@router.delete("/{pattern_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_pattern(pattern_id: str, user: AuthenticatedUser = Depends(current_user)) -> Response:
    require_owner(user, "pattern", pattern_id)
    get_pattern_service().delete(pattern_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
