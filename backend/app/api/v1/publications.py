from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Response, status

from app.api.v1.auth import AuthenticatedUser, current_user, require_owner
from app.core.exceptions import AppError, validation_error
from app.schemas.common import success
from app.schemas.project import ProjectCreate
from app.schemas.publication import PublicationCreateRequest
from app.services.auth_service import get_auth_service
from app.services.pattern_service import get_pattern_service
from app.services.project_service import get_project_service
from app.services.publication_service import get_publication_service

router = APIRouter(tags=["publications"])


@router.post("/projects/{project_id}/publications", status_code=status.HTTP_201_CREATED)
def submit_publication(
    project_id: str,
    request: PublicationCreateRequest,
    user: AuthenticatedUser = Depends(current_user),
) -> dict[str, object]:
    require_owner(user, "project", project_id)
    if request.finished_image_id:
        require_owner(user, "image", request.finished_image_id)
    project = get_project_service().get(project_id)
    return success(get_publication_service().submit(user.id, project, request))


@router.get("/publications/mine")
def list_my_publications(user: AuthenticatedUser = Depends(current_user)) -> dict[str, object]:
    return success(get_publication_service().list_for_owner(user.id))


@router.get("/publications/mine/page")
def list_my_publications_page(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=12, ge=1, le=48),
    user: AuthenticatedUser = Depends(current_user),
) -> dict[str, object]:
    return success(get_publication_service().list_for_owner_page(user.id, page, page_size))


@router.get("/publications/favorites/mine")
def list_favorite_publications(user: AuthenticatedUser = Depends(current_user)) -> dict[str, object]:
    return success(get_publication_service().list_favorites(user.id))


@router.get("/publications/favorites/mine/page")
def list_favorite_publications_page(
    query: str | None = Query(default=None, max_length=120),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=12, ge=1, le=48),
    user: AuthenticatedUser = Depends(current_user),
) -> dict[str, object]:
    return success(get_publication_service().list_favorites_page(user.id, page, page_size, query))


@router.get("/publications/favorites/mine/tokens")
def list_favorite_publication_tokens(user: AuthenticatedUser = Depends(current_user)) -> dict[str, object]:
    return success({"items": get_publication_service().favorite_tokens(user.id)})


@router.post("/publications/{publication_id}/resume")
def resume_publication(publication_id: str, user: AuthenticatedUser = Depends(current_user)) -> dict[str, object]:
    """Open the source project or rebuild an idempotent editing project from the publication snapshot."""
    publication = get_publication_service().get_for_owner(user.id, publication_id)
    auth = get_auth_service()
    projects = get_project_service()
    patterns = get_pattern_service()
    owned_project_ids = auth.owned_ids(user.id, "project")

    def editable(project: dict[str, object]) -> bool:
        pattern_id = project.get("pattern_id")
        if not isinstance(pattern_id, str) or not pattern_id:
            return False
        try:
            patterns.get(pattern_id)
        except AppError:
            return False
        return True

    source_project_id = str(publication["project_id"])
    if source_project_id in owned_project_ids:
        try:
            source_project = projects.get(source_project_id)
            if editable(source_project):
                return success(source_project)
        except AppError:
            pass

    for project in projects.list():
        if project["id"] not in owned_project_ids or not editable(project):
            continue
        editor_settings = project.get("editor_settings")
        resume_meta = editor_settings.get("publication_resume", {}) if isinstance(editor_settings, dict) else {}
        if isinstance(resume_meta, dict) and resume_meta.get("source_publication_id") == publication_id:
            return success(project)

    pattern_id = str(publication["pattern_id"])
    try:
        patterns.get(pattern_id)
    except AppError as error:
        raise validation_error(
            "原项目和图纸均已删除，无法继续编辑；发布记录仍会保留用于查看审核说明",
            "PUBLICATION_SOURCE_MISSING",
        ) from error

    auth.claim(user.id, "pattern", pattern_id)
    restored = projects.create(
        ProjectCreate(
            name=f"{str(publication['title'])[:104]} · 继续编辑",
            description=str(publication.get("description") or "从社区发布记录恢复的编辑项目"),
            pattern_id=pattern_id,
            editor_settings={
                "publication_resume": {
                    "source_publication_id": publication_id,
                    "source_project_id": source_project_id,
                }
            },
        )
    )
    auth.claim(user.id, "project", restored["id"])
    return success(restored)


@router.get("/publications")
def list_publications(
    query: str | None = Query(default=None, max_length=120),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=18, ge=1, le=48),
) -> dict[str, object]:
    return success(get_publication_service().list_public(query, page, page_size))


@router.delete("/publications/{publication_id}", status_code=status.HTTP_204_NO_CONTENT)
def withdraw_publication(publication_id: str, user: AuthenticatedUser = Depends(current_user)) -> Response:
    get_publication_service().withdraw(user.id, publication_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete("/publications/{publication_id}/record", status_code=status.HTTP_204_NO_CONTENT)
def delete_publication_record(publication_id: str, user: AuthenticatedUser = Depends(current_user)) -> Response:
    get_publication_service().delete_for_owner(user.id, publication_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/publications/{public_token}/favorite")
def favorite_publication(public_token: str, user: AuthenticatedUser = Depends(current_user)) -> dict[str, object]:
    return success(get_publication_service().favorite(user.id, public_token))


@router.delete("/publications/{public_token}/favorite", status_code=status.HTTP_204_NO_CONTENT)
def unfavorite_publication(public_token: str, user: AuthenticatedUser = Depends(current_user)) -> Response:
    get_publication_service().unfavorite(user.id, public_token)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/publications/{public_token}/remix", status_code=status.HTTP_201_CREATED)
def remix_publication(public_token: str, user: AuthenticatedUser = Depends(current_user)) -> dict[str, object]:
    publication, source_pattern = get_publication_service().remix_source(public_token)
    pattern = get_pattern_service().create_remix(source_pattern, public_token)
    source_name = str(publication["title"]).strip()
    project = get_project_service().create(
        ProjectCreate(
            name=f"{source_name[:110]} · 再创作",
            description=f"基于社区模板《{source_name}》再创作",
            pattern_id=pattern["id"],
            editor_settings={"community_remix": {"source_token": public_token, "source_title": source_name}},
        )
    )
    auth = get_auth_service()
    auth.claim(user.id, "pattern", pattern["id"])
    auth.claim(user.id, "project", project["id"])
    return success({"project": project, "pattern": pattern})


@router.get("/publications/{public_token}")
def get_publication(public_token: str) -> dict[str, object]:
    return success(get_publication_service().get_public(public_token))
