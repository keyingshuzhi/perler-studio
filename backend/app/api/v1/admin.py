from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Response, status

from app.api.v1.auth import AuthenticatedUser, require_admin
from app.schemas.auth import AdminPasswordResetRequest, AdminUserCreateRequest, AdminUserUpdateRequest
from app.schemas.common import success
from app.schemas.publication import PublicationReviewRequest, PublicationStatus
from app.services.auth_service import get_auth_service
from app.services.publication_service import get_publication_service

router = APIRouter(prefix="/admin", tags=["administration"])


@router.get("/users")
def list_users(
    query: str | None = Query(default=None, max_length=120),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=30, ge=1, le=100),
    _: AuthenticatedUser = Depends(require_admin),
) -> dict[str, object]:
    return success(get_auth_service().list_users(query, page, page_size))


@router.post("/users", status_code=status.HTTP_201_CREATED)
def create_user(request: AdminUserCreateRequest, _: AuthenticatedUser = Depends(require_admin)) -> dict[str, object]:
    return success(get_auth_service().create_user(request))


@router.patch("/users/{user_id}")
def update_user(
    user_id: str, request: AdminUserUpdateRequest, admin: AuthenticatedUser = Depends(require_admin)
) -> dict[str, object]:
    return success(get_auth_service().update_user(admin.id, user_id, request))


@router.put("/users/{user_id}/password", status_code=status.HTTP_204_NO_CONTENT)
def reset_user_password(
    user_id: str, request: AdminPasswordResetRequest, _: AuthenticatedUser = Depends(require_admin)
) -> Response:
    get_auth_service().reset_user_password(user_id, request)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(user_id: str, admin: AuthenticatedUser = Depends(require_admin)) -> Response:
    get_auth_service().delete_user(admin.id, user_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/publications")
def list_publications_for_review(
    publication_status: PublicationStatus | None = Query(default=PublicationStatus.pending, alias="status"),
    query: str | None = Query(default=None, max_length=120),
    _: AuthenticatedUser = Depends(require_admin),
) -> dict[str, object]:
    return success(get_publication_service().list_for_admin(publication_status, query))


@router.get("/publications/page")
def list_publications_for_review_page(
    publication_status: PublicationStatus | None = Query(default=PublicationStatus.pending, alias="status"),
    query: str | None = Query(default=None, max_length=120),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    _: AuthenticatedUser = Depends(require_admin),
) -> dict[str, object]:
    return success(get_publication_service().list_for_admin_page(publication_status, query, page, page_size))


@router.get("/publications/{publication_id}")
def get_publication_for_review(
    publication_id: str,
    _: AuthenticatedUser = Depends(require_admin),
) -> dict[str, object]:
    return success(get_publication_service().get_admin_detail(publication_id))


@router.post("/publications/{publication_id}/review")
def review_publication(
    publication_id: str,
    request: PublicationReviewRequest,
    admin: AuthenticatedUser = Depends(require_admin),
) -> dict[str, object]:
    return success(get_publication_service().review(admin.id, publication_id, request))


@router.delete("/publications/{publication_id}", status_code=status.HTTP_204_NO_CONTENT)
def withdraw_publication(
    publication_id: str,
    note: str = Query(min_length=1, max_length=2_000),
    admin: AuthenticatedUser = Depends(require_admin),
) -> Response:
    get_publication_service().withdraw_by_admin(admin.id, publication_id, note)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
