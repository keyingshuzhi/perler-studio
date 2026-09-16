from __future__ import annotations

from dataclasses import dataclass

from fastapi import APIRouter, Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.exceptions import AppError
from app.schemas.auth import ChangePasswordRequest, LoginRequest, ProfileUpdateRequest, RegisterRequest
from app.schemas.common import success
from app.services.auth_service import get_auth_service

router = APIRouter(prefix="/auth", tags=["auth"])
_bearer = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class AuthenticatedUser:
    id: str
    email: str
    display_name: str
    role: str
    created_at: str
    token: str


def current_user(credentials: HTTPAuthorizationCredentials | None = Depends(_bearer)) -> AuthenticatedUser:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise AppError(401, "AUTH_REQUIRED", "请先登录后再继续")
    user = get_auth_service().current_user(credentials.credentials)
    return AuthenticatedUser(**user, token=credentials.credentials)


def require_owner(user: AuthenticatedUser, resource_type: str, resource_id: str) -> None:
    get_auth_service().require_owner(user.id, resource_type, resource_id)


def require_admin(user: AuthenticatedUser = Depends(current_user)) -> AuthenticatedUser:
    get_auth_service().require_admin(user.id)
    return user


@router.post("/register", status_code=201)
def register(request: RegisterRequest) -> dict[str, object]:
    return success(get_auth_service().register(request))


@router.post("/login")
def login(request: LoginRequest) -> dict[str, object]:
    return success(get_auth_service().login(request))


@router.get("/me")
def get_me(user: AuthenticatedUser = Depends(current_user)) -> dict[str, object]:
    return success(
        {
            "id": user.id,
            "email": user.email,
            "display_name": user.display_name,
            "role": user.role,
            "created_at": user.created_at,
        }
    )


@router.patch("/me")
def update_me(request: ProfileUpdateRequest, user: AuthenticatedUser = Depends(current_user)) -> dict[str, object]:
    return success(get_auth_service().update_profile(user.id, request))


@router.put("/me/password", status_code=204)
def change_my_password(request: ChangePasswordRequest, user: AuthenticatedUser = Depends(current_user)) -> None:
    get_auth_service().change_own_password(user.id, request)


@router.post("/logout", status_code=204)
def logout(user: AuthenticatedUser = Depends(current_user)) -> None:
    get_auth_service().logout(user.token)
