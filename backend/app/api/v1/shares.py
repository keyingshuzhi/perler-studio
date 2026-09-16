from fastapi import APIRouter

from app.schemas.common import success
from app.schemas.share import ShareCommentRequest, ShareConfirmationRequest
from app.services.project_service import get_project_service

router = APIRouter(prefix="/shares", tags=["shares"])


@router.get("/{token}")
def get_share(token: str) -> dict[str, object]:
    return success(get_project_service().get_share(token))


@router.post("/{token}/confirmation")
def confirm_share(token: str, request: ShareConfirmationRequest) -> dict[str, object]:
    return success(get_project_service().confirm_share(token, request))


@router.post("/{token}/comments")
def add_share_comment(token: str, request: ShareCommentRequest) -> dict[str, object]:
    return success(get_project_service().add_share_comment(token, request))
