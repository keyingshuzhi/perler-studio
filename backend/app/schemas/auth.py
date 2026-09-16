from __future__ import annotations

import re
from enum import StrEnum

from pydantic import AliasChoices, BaseModel, Field, field_validator, model_validator


class UserRole(StrEnum):
    user = "user"
    admin = "admin"


class RegisterRequest(BaseModel):
    email: str = Field(min_length=5, max_length=254)
    password: str = Field(min_length=8, max_length=128)
    display_name: str = Field(min_length=1, max_length=80)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        normalized = value.strip().lower()
        if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", normalized):
            raise ValueError("请输入有效的邮箱地址")
        return normalized

    @field_validator("display_name")
    @classmethod
    def normalize_display_name(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("请输入显示名称")
        return normalized


class LoginRequest(BaseModel):
    # Keep `email` as a backwards-compatible request alias.  A built-in
    # administrator uses the short account name `admin`, while registered
    # creators continue to sign in with their email address.
    account: str = Field(
        min_length=1,
        max_length=254,
        validation_alias=AliasChoices("account", "email"),
    )
    password: str = Field(min_length=1, max_length=128)

    @field_validator("account")
    @classmethod
    def normalize_account(cls, value: str) -> str:
        normalized = value.strip().lower()
        if not normalized:
            raise ValueError("请输入账号或邮箱")
        return normalized


class UserResponse(BaseModel):
    id: str
    email: str
    display_name: str
    role: UserRole
    created_at: str


class SessionResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_at: str
    user: UserResponse


class AdminUserCreateRequest(RegisterRequest):
    role: UserRole = UserRole.user
    is_active: bool = True


class AdminUserUpdateRequest(BaseModel):
    email: str | None = Field(default=None, min_length=5, max_length=254)
    display_name: str | None = Field(default=None, min_length=1, max_length=80)
    role: UserRole | None = None
    is_active: bool | None = None

    @field_validator("email")
    @classmethod
    def normalize_optional_email(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip().lower()
        if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", normalized):
            raise ValueError("请输入有效的邮箱地址")
        return normalized

    @field_validator("display_name")
    @classmethod
    def normalize_optional_display_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            raise ValueError("请输入显示名称")
        return normalized

    @model_validator(mode="after")
    def require_a_change(self) -> AdminUserUpdateRequest:
        if not self.model_dump(exclude_none=True):
            raise ValueError("请至少提供一项需要更新的用户信息")
        return self


class AdminPasswordResetRequest(BaseModel):
    password: str = Field(min_length=8, max_length=128)


class ProfileUpdateRequest(BaseModel):
    display_name: str = Field(min_length=1, max_length=80)

    @field_validator("display_name")
    @classmethod
    def normalize_display_name(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("请输入显示名称")
        return normalized


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=8, max_length=128)
