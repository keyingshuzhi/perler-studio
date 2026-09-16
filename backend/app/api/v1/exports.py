from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse

from app.api.v1.auth import AuthenticatedUser, current_user, require_owner
from app.schemas.common import success
from app.schemas.export import (
    CSVExportRequest,
    PDFExportRequest,
    PNGExportRequest,
    ProjectExportRequest,
    SVGExportRequest,
)
from app.services.auth_service import get_auth_service
from app.services.export_service import get_export_service

router = APIRouter(prefix="/exports", tags=["exports"])


def _require_export_target(
    user: AuthenticatedUser,
    request: PNGExportRequest | PDFExportRequest | SVGExportRequest | CSVExportRequest | ProjectExportRequest,
) -> None:
    if request.pattern_id:
        require_owner(user, "pattern", request.pattern_id)
    elif request.project_id:
        require_owner(user, "project", request.project_id)


def _claim_export(user: AuthenticatedUser, export: dict[str, object]) -> dict[str, object]:
    get_auth_service().claim(user.id, "export", str(export["id"]))
    return success(export)


@router.post("/png")
def export_png(request: PNGExportRequest, user: AuthenticatedUser = Depends(current_user)) -> dict[str, object]:
    _require_export_target(user, request)
    return _claim_export(user, get_export_service().png(request))


@router.post("/pdf")
def export_pdf(request: PDFExportRequest, user: AuthenticatedUser = Depends(current_user)) -> dict[str, object]:
    _require_export_target(user, request)
    return _claim_export(user, get_export_service().pdf(request))


@router.post("/svg")
def export_svg(request: SVGExportRequest, user: AuthenticatedUser = Depends(current_user)) -> dict[str, object]:
    _require_export_target(user, request)
    return _claim_export(user, get_export_service().svg(request))


@router.post("/csv")
def export_csv(request: CSVExportRequest, user: AuthenticatedUser = Depends(current_user)) -> dict[str, object]:
    _require_export_target(user, request)
    return _claim_export(user, get_export_service().csv(request))


@router.post("/project")
def export_project(request: ProjectExportRequest, user: AuthenticatedUser = Depends(current_user)) -> dict[str, object]:
    _require_export_target(user, request)
    return _claim_export(user, get_export_service().project_json(request))


@router.get("/{export_id}/download")
def download_export(export_id: str, user: AuthenticatedUser = Depends(current_user)) -> FileResponse:
    require_owner(user, "export", export_id)
    service = get_export_service()
    path = service.file_path(export_id)
    return FileResponse(path, filename=path.name, media_type="application/octet-stream")


@router.get("/{export_id}")
def get_export(export_id: str, user: AuthenticatedUser = Depends(current_user)) -> dict[str, object]:
    require_owner(user, "export", export_id)
    return success(get_export_service().get(export_id))
