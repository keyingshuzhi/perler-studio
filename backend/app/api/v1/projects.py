from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Response, status

from app.api.v1.auth import AuthenticatedUser, current_user, require_owner
from app.schemas.common import success
from app.schemas.project import ProjectCreate, ProjectUpdate
from app.schemas.share import ShareCreateRequest, VersionCreateRequest
from app.services.auth_service import get_auth_service
from app.services.project_service import get_project_service

router = APIRouter(prefix="/projects", tags=["projects"])


@router.get("")
def list_projects(user: AuthenticatedUser = Depends(current_user)) -> dict[str, object]:
    owned_ids = get_auth_service().owned_ids(user.id, "project")
    return success([project for project in get_project_service().list() if project["id"] in owned_ids])


@router.get("/page")
def list_projects_page(
    query: str | None = Query(default=None, max_length=120),
    tag: str | None = Query(default=None, max_length=80),
    favorite: bool = Query(default=False),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=16, ge=1, le=100),
    user: AuthenticatedUser = Depends(current_user),
) -> dict[str, object]:
    owned_ids = get_auth_service().owned_ids(user.id, "project")
    owned = [project for project in get_project_service().list() if project["id"] in owned_ids]

    def metadata(project: dict[str, object]) -> tuple[list[str], bool]:
        settings = project.get("editor_settings")
        raw = settings.get("project_metadata") if isinstance(settings, dict) else None
        tags = raw.get("tags", []) if isinstance(raw, dict) else []
        normalized_tags = [item for item in tags if isinstance(item, str)] if isinstance(tags, list) else []
        return normalized_tags, bool(raw.get("favorite", False)) if isinstance(raw, dict) else False

    normalized_query = (query or "").strip().casefold()
    normalized_tag = (tag or "").strip()
    filtered: list[dict[str, object]] = []
    for project in owned:
        tags, is_favorite = metadata(project)
        haystack = " ".join((str(project.get("name", "")), str(project.get("description") or ""), *tags)).casefold()
        if normalized_query and normalized_query not in haystack:
            continue
        if normalized_tag and normalized_tag not in tags:
            continue
        if favorite and not is_favorite:
            continue
        filtered.append(project)

    available_tags = sorted({item for project in owned for item in metadata(project)[0]})
    start = (page - 1) * page_size
    return success(
        {
            "items": filtered[start : start + page_size],
            "total": len(filtered),
            "page": page,
            "page_size": page_size,
            "library_total": len(owned),
            "favorite_count": sum(1 for project in owned if metadata(project)[1]),
            "tagged_count": sum(1 for project in owned if metadata(project)[0]),
            "available_tags": available_tags,
        }
    )


@router.post("", status_code=status.HTTP_201_CREATED)
def create_project(request: ProjectCreate, user: AuthenticatedUser = Depends(current_user)) -> dict[str, object]:
    if request.pattern_id:
        require_owner(user, "pattern", request.pattern_id)
    project = get_project_service().create(request)
    get_auth_service().claim(user.id, "project", project["id"])
    return success(project)


@router.get("/{project_id}")
def get_project(project_id: str, user: AuthenticatedUser = Depends(current_user)) -> dict[str, object]:
    require_owner(user, "project", project_id)
    return success(get_project_service().get(project_id))


@router.put("/{project_id}")
def update_project(
    project_id: str, request: ProjectUpdate, user: AuthenticatedUser = Depends(current_user)
) -> dict[str, object]:
    require_owner(user, "project", project_id)
    if request.pattern_id:
        require_owner(user, "pattern", request.pattern_id)
    return success(get_project_service().update(project_id, request))


@router.post("/{project_id}/duplicate", status_code=status.HTTP_201_CREATED)
def duplicate_project(project_id: str, user: AuthenticatedUser = Depends(current_user)) -> dict[str, object]:
    require_owner(user, "project", project_id)
    project = get_project_service().duplicate(project_id)
    get_auth_service().claim(user.id, "project", project["id"])
    if project.get("pattern_id"):
        get_auth_service().claim(user.id, "pattern", project["pattern_id"])
    return success(project)


@router.get("/{project_id}/versions")
def list_project_versions(project_id: str, user: AuthenticatedUser = Depends(current_user)) -> dict[str, object]:
    require_owner(user, "project", project_id)
    return success(get_project_service().list_versions(project_id))


@router.post("/{project_id}/versions", status_code=status.HTTP_201_CREATED)
def create_project_version(
    project_id: str, request: VersionCreateRequest, user: AuthenticatedUser = Depends(current_user)
) -> dict[str, object]:
    require_owner(user, "project", project_id)
    version = get_project_service().create_version(project_id, request)
    get_auth_service().claim(user.id, "version", version["id"])
    return success(version)


@router.get("/{project_id}/versions/{version_id}")
def get_project_version(
    project_id: str, version_id: str, user: AuthenticatedUser = Depends(current_user)
) -> dict[str, object]:
    require_owner(user, "project", project_id)
    require_owner(user, "version", version_id)
    return success(get_project_service().get_version(project_id, version_id))


@router.post("/{project_id}/versions/{version_id}/restore")
def restore_project_version(
    project_id: str, version_id: str, user: AuthenticatedUser = Depends(current_user)
) -> dict[str, object]:
    require_owner(user, "project", project_id)
    require_owner(user, "version", version_id)
    project = get_project_service().restore_version(project_id, version_id)
    if project.get("pattern_id"):
        get_auth_service().claim(user.id, "pattern", project["pattern_id"])
    return success(project)


@router.post("/{project_id}/shares", status_code=status.HTTP_201_CREATED)
def create_project_share(
    project_id: str, request: ShareCreateRequest, user: AuthenticatedUser = Depends(current_user)
) -> dict[str, object]:
    require_owner(user, "project", project_id)
    share = get_project_service().create_share(project_id, request)
    get_auth_service().claim(user.id, "share", share["token"])
    return success(share)


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_project(project_id: str, user: AuthenticatedUser = Depends(current_user)) -> Response:
    require_owner(user, "project", project_id)
    get_project_service().delete(project_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
