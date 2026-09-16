from fastapi import APIRouter

from app.core.presets import list_grid_presets, list_pegboard_templates
from app.schemas.common import success
from app.services.template_service import list_templates

router = APIRouter(prefix="/presets", tags=["presets"])


@router.get("/grids")
def list_presets() -> dict[str, object]:
    """Return production-size grid presets with mini and midi bead dimensions."""
    return success({"items": list_grid_presets()})


@router.get("/templates")
def list_design_templates() -> dict[str, object]:
    return success({"items": list_templates()})


@router.get("/boards")
def list_pegboards() -> dict[str, object]:
    """Return grid-aligned physical pegboard templates with their true hole counts."""
    return success({"items": list_pegboard_templates()})
