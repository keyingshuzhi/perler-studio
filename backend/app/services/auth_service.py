from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import sqlite3
from datetime import UTC, datetime, timedelta
from typing import Any

from app.core.config import Settings, get_settings
from app.core.exceptions import AppError, conflict
from app.schemas.auth import (
    AdminPasswordResetRequest,
    AdminUserCreateRequest,
    AdminUserUpdateRequest,
    ChangePasswordRequest,
    LoginRequest,
    ProfileUpdateRequest,
    RegisterRequest,
    UserRole,
)
from app.services.storage_service import StorageService, utc_now


class AuthService:
    """SQLite-backed accounts, sessions, and ownership metadata.

    Image and export bytes remain in the storage volume; this database is the
    source of truth for account access and the ownership boundary around every
    user-created resource.
    """

    USER_ROLE = UserRole.user.value
    ADMIN_ROLE = UserRole.admin.value
    BUILT_IN_ADMIN_ACCOUNT = "admin"
    BUILT_IN_ADMIN_PASSWORD = "admin"

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.settings.ensure_storage_dirs()
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.settings.database_file, timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id TEXT PRIMARY KEY,
                    email TEXT NOT NULL COLLATE NOCASE UNIQUE,
                    display_name TEXT NOT NULL,
                    password_hash TEXT NOT NULL,
                    role TEXT NOT NULL DEFAULT 'user' CHECK (role IN ('user', 'admin')),
                    is_active INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    deleted_at TEXT
                );
                CREATE TABLE IF NOT EXISTS sessions (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    token_hash TEXT NOT NULL UNIQUE,
                    created_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    last_seen_at TEXT NOT NULL,
                    revoked_at TEXT
                );
                CREATE TABLE IF NOT EXISTS resource_owners (
                    resource_type TEXT NOT NULL,
                    resource_id TEXT NOT NULL,
                    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    created_at TEXT NOT NULL,
                    PRIMARY KEY (resource_type, resource_id)
                );
                CREATE INDEX IF NOT EXISTS idx_sessions_token_hash ON sessions(token_hash);
                CREATE INDEX IF NOT EXISTS idx_sessions_user_id ON sessions(user_id);
                CREATE INDEX IF NOT EXISTS idx_resource_owners_user_type ON resource_owners(user_id, resource_type);
                """
            )
            columns = {str(row["name"]) for row in connection.execute("PRAGMA table_info(users)")}
            if "role" not in columns:
                connection.execute(
                    "ALTER TABLE users ADD COLUMN role TEXT NOT NULL DEFAULT 'user' CHECK (role IN ('user', 'admin'))"
                )
            if "deleted_at" not in columns:
                connection.execute("ALTER TABLE users ADD COLUMN deleted_at TEXT")
            connection.execute("CREATE INDEX IF NOT EXISTS idx_users_role_active ON users(role, is_active)")
            # This account is inserted only once and is never overwritten.
            # Administrators can therefore safely change its password in the
            # UI without a future application restart restoring `admin`.
            built_in_admin = connection.execute(
                "SELECT id FROM users WHERE email = ?", (self.BUILT_IN_ADMIN_ACCOUNT,)
            ).fetchone()
            if not built_in_admin:
                now = utc_now()
                connection.execute(
                    """
                    INSERT INTO users (id, email, display_name, password_hash, role, is_active, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, 1, ?, ?)
                    """,
                    (
                        StorageService.new_id("usr"),
                        self.BUILT_IN_ADMIN_ACCOUNT,
                        "平台管理员",
                        self._hash_password(self.BUILT_IN_ADMIN_PASSWORD),
                        self.ADMIN_ROLE,
                        now,
                        now,
                    ),
                )
            connection.execute("PRAGMA optimize")

    @staticmethod
    def _hash_password(password: str) -> str:
        salt = secrets.token_bytes(16)
        digest = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=2**14, r=8, p=1)
        return (
            "scrypt$16384$8$1$"
            + base64.b64encode(salt).decode("ascii")
            + "$"
            + base64.b64encode(digest).decode("ascii")
        )

    @staticmethod
    def _verify_password(password: str, encoded: str) -> bool:
        try:
            algorithm, n, r, p, salt_b64, digest_b64 = encoded.split("$")
            if algorithm != "scrypt":
                return False
            actual = hashlib.scrypt(
                password.encode("utf-8"),
                salt=base64.b64decode(salt_b64),
                n=int(n),
                r=int(r),
                p=int(p),
            )
            return hmac.compare_digest(actual, base64.b64decode(digest_b64))
        except (ValueError, TypeError, UnicodeError):
            return False

    @staticmethod
    def _token_hash(token: str) -> str:
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    @staticmethod
    def _public_user(row: sqlite3.Row | dict[str, Any]) -> dict[str, str]:
        return {
            "id": str(row["id"]),
            "email": str(row["email"]),
            "display_name": str(row["display_name"]),
            "role": str(row["role"]),
            "created_at": str(row["created_at"]),
        }

    @staticmethod
    def _admin_user(row: sqlite3.Row | dict[str, Any]) -> dict[str, Any]:
        return {
            "id": str(row["id"]),
            "email": str(row["email"]),
            "display_name": str(row["display_name"]),
            "role": str(row["role"]),
            "is_active": bool(row["is_active"]),
            "created_at": str(row["created_at"]),
            "updated_at": str(row["updated_at"]),
            "deleted_at": str(row["deleted_at"]) if row["deleted_at"] else None,
        }

    def _is_initial_admin_email(self, email: str) -> bool:
        normalized = email.strip().lower()
        return any(hmac.compare_digest(normalized, item.strip().lower()) for item in self.settings.initial_admin_emails)

    def _role_for_new_account(self, email: str) -> str:
        return self.ADMIN_ROLE if self._is_initial_admin_email(email) else self.USER_ROLE

    def _issue_session(self, user: sqlite3.Row | dict[str, Any]) -> dict[str, Any]:
        token = secrets.token_urlsafe(48)
        now = datetime.now(UTC)
        expires_at = now + timedelta(days=self.settings.auth_session_days)
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO sessions (id, user_id, token_hash, created_at, expires_at, last_seen_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    StorageService.new_id("ses"),
                    str(user["id"]),
                    self._token_hash(token),
                    now.isoformat(),
                    expires_at.isoformat(),
                    now.isoformat(),
                ),
            )
        return {
            "access_token": token,
            "token_type": "bearer",
            "expires_at": expires_at.isoformat(),
            "user": self._public_user(user),
        }

    def register(self, request: RegisterRequest) -> dict[str, Any]:
        now = utc_now()
        user = {
            "id": StorageService.new_id("usr"),
            "email": request.email,
            "display_name": request.display_name,
            "password_hash": self._hash_password(request.password),
            "role": self._role_for_new_account(request.email),
            "created_at": now,
            "updated_at": now,
        }
        try:
            with self._connect() as connection:
                # The built-in administrator should not prevent the first
                # local creator from adopting pre-account workspace data.
                user_count = int(
                    connection.execute(
                        "SELECT COUNT(*) FROM users WHERE email <> ?", (self.BUILT_IN_ADMIN_ACCOUNT,)
                    ).fetchone()[0]
                )
                connection.execute(
                    """
                    INSERT INTO users (id, email, display_name, password_hash, role, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        user["id"],
                        user["email"],
                        user["display_name"],
                        user["password_hash"],
                        user["role"],
                        now,
                        now,
                    ),
                )
        except sqlite3.IntegrityError as error:
            raise conflict("该邮箱已经注册，请直接登录", "EMAIL_ALREADY_REGISTERED") from error
        if self._should_claim_legacy_data(request.email, user_count):
            self.claim_legacy_workspace(str(user["id"]))
        return self._issue_session(user)

    def login(self, request: LoginRequest) -> dict[str, Any]:
        with self._connect() as connection:
            user = connection.execute(
                "SELECT id, email, display_name, password_hash, role, is_active, created_at FROM users WHERE email = ?",
                (request.account,),
            ).fetchone()
        if (
            not user
            or not bool(user["is_active"])
            or not self._verify_password(request.password, str(user["password_hash"]))
        ):
            raise AppError(401, "INVALID_CREDENTIALS", "账号或密码不正确")
        if self._is_initial_admin_email(str(user["email"])) and user["role"] != self.ADMIN_ROLE:
            with self._connect() as connection:
                connection.execute(
                    "UPDATE users SET role = ?, updated_at = ? WHERE id = ?",
                    (self.ADMIN_ROLE, utc_now(), user["id"]),
                )
            user = {**dict(user), "role": self.ADMIN_ROLE}
        return self._issue_session(user)

    def current_user(self, token: str) -> dict[str, str]:
        token_hash = self._token_hash(token)
        now = datetime.now(UTC)
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT users.id, users.email, users.display_name, users.role, users.created_at,
                       sessions.id AS session_id, sessions.expires_at
                FROM sessions
                JOIN users ON users.id = sessions.user_id
                WHERE sessions.token_hash = ? AND sessions.revoked_at IS NULL AND users.is_active = 1
                """,
                (token_hash,),
            ).fetchone()
            if not row or datetime.fromisoformat(str(row["expires_at"])) <= now:
                if row:
                    connection.execute(
                        "UPDATE sessions SET revoked_at = ? WHERE id = ?", (now.isoformat(), row["session_id"])
                    )
                raise AppError(401, "AUTH_SESSION_EXPIRED", "登录状态已过期，请重新登录")
            connection.execute(
                "UPDATE sessions SET last_seen_at = ? WHERE id = ?", (now.isoformat(), row["session_id"])
            )
        return self._public_user(row)

    def logout(self, token: str) -> None:
        with self._connect() as connection:
            connection.execute(
                "UPDATE sessions SET revoked_at = ? WHERE token_hash = ?", (utc_now(), self._token_hash(token))
            )

    def update_profile(self, user_id: str, request: ProfileUpdateRequest) -> dict[str, str]:
        now = utc_now()
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE users SET display_name = ?, updated_at = ?
                WHERE id = ? AND is_active = 1 AND deleted_at IS NULL
                """,
                (request.display_name, now, user_id),
            )
            user = connection.execute(
                "SELECT id, email, display_name, role, created_at FROM users WHERE id = ?", (user_id,)
            ).fetchone()
        if not user:
            raise AppError(404, "USER_NOT_FOUND", "用户不存在")
        return self._public_user(user)

    def change_own_password(self, user_id: str, request: ChangePasswordRequest) -> None:
        with self._connect() as connection:
            user = connection.execute(
                "SELECT password_hash, is_active, deleted_at FROM users WHERE id = ?", (user_id,)
            ).fetchone()
        if not user or not bool(user["is_active"]) or user["deleted_at"]:
            raise AppError(404, "USER_NOT_FOUND", "用户不存在")
        if not self._verify_password(request.current_password, str(user["password_hash"])):
            raise AppError(401, "CURRENT_PASSWORD_INCORRECT", "当前密码不正确")
        now = utc_now()
        with self._connect() as connection:
            connection.execute(
                "UPDATE users SET password_hash = ?, updated_at = ? WHERE id = ?",
                (self._hash_password(request.new_password), now, user_id),
            )
            connection.execute(
                "UPDATE sessions SET revoked_at = ? WHERE user_id = ? AND revoked_at IS NULL", (now, user_id)
            )

    def require_admin(self, user_id: str) -> None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT role, is_active, deleted_at FROM users WHERE id = ?", (user_id,)
            ).fetchone()
        if not row or not bool(row["is_active"]) or row["deleted_at"] or row["role"] != self.ADMIN_ROLE:
            raise AppError(403, "ADMIN_REQUIRED", "需要管理员权限")

    def list_users(self, query: str | None, page: int, page_size: int) -> dict[str, Any]:
        normalized = (query or "").strip()
        where = ""
        params: list[Any] = []
        if normalized:
            where = "WHERE email LIKE ? OR display_name LIKE ?"
            needle = f"%{normalized}%"
            params.extend((needle, needle))
        with self._connect() as connection:
            total = int(connection.execute(f"SELECT COUNT(*) FROM users {where}", params).fetchone()[0])
            rows = connection.execute(
                f"""
                SELECT id, email, display_name, role, is_active, created_at, updated_at, deleted_at
                FROM users {where}
                ORDER BY created_at DESC
                LIMIT ? OFFSET ?
                """,
                [*params, page_size, (page - 1) * page_size],
            ).fetchall()
        return {
            "items": [self._admin_user(row) for row in rows],
            "total": total,
            "page": page,
            "page_size": page_size,
        }

    def create_user(self, request: AdminUserCreateRequest) -> dict[str, Any]:
        now = utc_now()
        user = {
            "id": StorageService.new_id("usr"),
            "email": request.email,
            "display_name": request.display_name,
            "password_hash": self._hash_password(request.password),
            "role": request.role.value,
            "is_active": int(request.is_active),
            "created_at": now,
            "updated_at": now,
            "deleted_at": None,
        }
        try:
            with self._connect() as connection:
                connection.execute(
                    """
                    INSERT INTO users (id, email, display_name, password_hash, role, is_active, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        user["id"],
                        user["email"],
                        user["display_name"],
                        user["password_hash"],
                        user["role"],
                        user["is_active"],
                        now,
                        now,
                    ),
                )
        except sqlite3.IntegrityError as error:
            raise conflict("该邮箱已经注册", "EMAIL_ALREADY_REGISTERED") from error
        return self._admin_user(user)

    def _load_admin_user(self, user_id: str) -> sqlite3.Row:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT id, email, display_name, role, is_active, created_at, updated_at, deleted_at
                FROM users WHERE id = ?
                """,
                (user_id,),
            ).fetchone()
        if not row:
            raise AppError(404, "USER_NOT_FOUND", "用户不存在")
        return row

    def _ensure_not_last_active_admin(self, target: sqlite3.Row, next_role: str, next_active: bool) -> None:
        is_losing_admin = (
            target["role"] == self.ADMIN_ROLE
            and bool(target["is_active"])
            and (next_role != self.ADMIN_ROLE or not next_active)
        )
        if not is_losing_admin:
            return
        with self._connect() as connection:
            active_admins = int(
                connection.execute(
                    "SELECT COUNT(*) FROM users WHERE role = ? AND is_active = 1 AND deleted_at IS NULL",
                    (self.ADMIN_ROLE,),
                ).fetchone()[0]
            )
        if active_admins <= 1:
            raise AppError(409, "LAST_ADMIN_PROTECTED", "至少需要保留一位启用状态的管理员")

    def update_user(self, actor_id: str, user_id: str, request: AdminUserUpdateRequest) -> dict[str, Any]:
        target = self._load_admin_user(user_id)
        if target["deleted_at"]:
            raise AppError(409, "USER_DELETED", "已删除的用户不能再修改")
        changes = request.model_dump(exclude_none=True)
        next_role = str(changes.get("role", target["role"]))
        next_active = bool(changes.get("is_active", target["is_active"]))
        if actor_id == user_id and (next_role != self.ADMIN_ROLE or not next_active):
            raise AppError(409, "SELF_ADMIN_PROTECTED", "不能取消或停用自己的管理员权限")
        self._ensure_not_last_active_admin(target, next_role, next_active)
        assignments: list[str] = []
        params: list[Any] = []
        for key in ("email", "display_name", "role", "is_active"):
            if key in changes:
                assignments.append(f"{key} = ?")
                value = changes[key]
                if isinstance(value, UserRole):
                    params.append(value.value)
                elif key == "is_active":
                    params.append(int(value))
                else:
                    params.append(value)
        assignments.append("updated_at = ?")
        params.append(utc_now())
        params.append(user_id)
        try:
            with self._connect() as connection:
                connection.execute(f"UPDATE users SET {', '.join(assignments)} WHERE id = ?", params)
                if "is_active" in changes and not bool(changes["is_active"]):
                    connection.execute(
                        "UPDATE sessions SET revoked_at = ? WHERE user_id = ? AND revoked_at IS NULL",
                        (utc_now(), user_id),
                    )
        except sqlite3.IntegrityError as error:
            raise conflict("该邮箱已经注册", "EMAIL_ALREADY_REGISTERED") from error
        return self._admin_user(self._load_admin_user(user_id))

    def reset_user_password(self, user_id: str, request: AdminPasswordResetRequest) -> None:
        target = self._load_admin_user(user_id)
        if target["deleted_at"]:
            raise AppError(409, "USER_DELETED", "已删除的用户不能重置密码")
        now = utc_now()
        with self._connect() as connection:
            connection.execute(
                "UPDATE users SET password_hash = ?, updated_at = ? WHERE id = ?",
                (self._hash_password(request.password), now, user_id),
            )
            connection.execute(
                "UPDATE sessions SET revoked_at = ? WHERE user_id = ? AND revoked_at IS NULL", (now, user_id)
            )

    def delete_user(self, actor_id: str, user_id: str) -> None:
        target = self._load_admin_user(user_id)
        if target["deleted_at"]:
            return
        if actor_id == user_id:
            raise AppError(409, "SELF_DELETE_PROTECTED", "不能删除自己的管理员账户")
        self._ensure_not_last_active_admin(target, self.USER_ROLE, False)
        now = utc_now()
        tombstone_email = f"deleted-{user_id}@perler-studio.invalid"
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE users
                SET email = ?, display_name = '已删除用户', password_hash = ?, role = ?, is_active = 0,
                    deleted_at = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    tombstone_email,
                    self._hash_password(secrets.token_urlsafe(48)),
                    self.USER_ROLE,
                    now,
                    now,
                    user_id,
                ),
            )
            connection.execute(
                "UPDATE sessions SET revoked_at = ? WHERE user_id = ? AND revoked_at IS NULL", (now, user_id)
            )

    def claim(self, user_id: str, resource_type: str, resource_id: str) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT OR IGNORE INTO resource_owners (resource_type, resource_id, user_id, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (resource_type, resource_id, user_id, utc_now()),
            )

    def _should_claim_legacy_data(self, email: str, existing_user_count: int) -> bool:
        configured_owner = (self.settings.legacy_data_owner_email or "").strip().lower()
        if configured_owner:
            return hmac.compare_digest(email, configured_owner)
        return self.settings.app_env.lower() != "production" and existing_user_count == 0

    def claim_legacy_workspace(self, user_id: str) -> None:
        """Attach pre-account filesystem data to the approved initial owner.

        This protects existing local projects created before account ownership existed.
        Production imports only run for the explicitly configured owner email.
        """
        storage_root = self.settings.storage_dir
        project_ids: set[str] = set()
        for path in self.settings.project_dir.glob("pro_*.json"):
            project_id = path.stem
            self.claim(user_id, "project", project_id)
            project_ids.add(project_id)
            try:
                project = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if isinstance(project.get("pattern_id"), str):
                self.claim(user_id, "pattern", project["pattern_id"])

        resource_paths = {
            "pattern": self.settings.pattern_dir.glob("pat_*.json"),
            "export": self.settings.export_dir.glob("exp_*.json"),
            "share": self.settings.share_dir.glob("shr_*.json"),
            "palette": (storage_root / "palettes").glob("*.json"),
        }
        for resource_type, paths in resource_paths.items():
            for path in paths:
                self.claim(user_id, resource_type, path.stem)

        for directory in self.settings.upload_dir.glob("img_*"):
            if directory.is_dir():
                self.claim(user_id, "image", directory.name)
        for project_id in project_ids:
            for path in (self.settings.version_dir / project_id).glob("ver_*.json"):
                self.claim(user_id, "version", path.stem)

    def require_owner(self, user_id: str, resource_type: str, resource_id: str) -> None:
        with self._connect() as connection:
            owner = connection.execute(
                "SELECT user_id FROM resource_owners WHERE resource_type = ? AND resource_id = ?",
                (resource_type, resource_id),
            ).fetchone()
        if not owner or not hmac.compare_digest(str(owner["user_id"]), user_id):
            raise AppError(404, f"{resource_type.upper()}_NOT_FOUND", f"{resource_type} 不存在或无访问权限")

    def owned_ids(self, user_id: str, resource_type: str) -> set[str]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT resource_id FROM resource_owners WHERE user_id = ? AND resource_type = ?",
                (user_id, resource_type),
            ).fetchall()
        return {str(row["resource_id"]) for row in rows}


def get_auth_service() -> AuthService:
    return AuthService()
