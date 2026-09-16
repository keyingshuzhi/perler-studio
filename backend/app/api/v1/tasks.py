from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.v1.auth import AuthenticatedUser, current_user, require_owner
from app.schemas.common import success
from app.services.storage_service import get_storage

router = APIRouter(prefix="/tasks", tags=["tasks"])


@router.get("/{task_id}")
def get_task(task_id: str, user: AuthenticatedUser = Depends(current_user)) -> dict[str, object]:
    """Expose the stable task contract used when Celery is enabled in deployment."""
    require_owner(user, "task", task_id)
    return success(get_storage().load_task(task_id))
