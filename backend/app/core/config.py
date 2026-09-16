from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings. All paths are resolved from the backend directory."""

    app_name: str = "Perler Studio API"
    app_env: str = "development"
    app_debug: bool = False
    app_version: str = "0.3.1"
    api_v1_prefix: str = "/api/v1"
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:5173"])

    data_dir: Path = Path("../data")
    max_upload_size_mb: int = Field(default=20, ge=1, le=100)
    max_image_pixels: int = Field(default=50_000_000, ge=1_000_000)
    max_grid_width: int = Field(default=500, ge=1, le=2_000)
    max_grid_height: int = Field(default=500, ge=1, le=2_000)
    default_palette: str = "mard-291"
    default_distance_method: str = "ciede2000"
    default_bead_size_mm: float = Field(default=5.0, gt=0, le=20)
    default_waste_rate: float = Field(default=0.05, ge=0, le=1)
    database_path: Path | None = None
    auth_secret: str = "perler-studio-development-secret-change-before-production"
    auth_session_days: int = Field(default=30, ge=1, le=365)
    legacy_data_owner_email: str | None = None
    # Bootstrap only: matching addresses receive the administrator role when
    # they register (or next log in). Remove them once setup is complete.
    initial_admin_emails: list[str] = Field(default_factory=list)

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore", enable_decoding=False)

    @field_validator("cors_origins", mode="before")
    @classmethod
    def split_cors_origins(cls, value: object) -> object:
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value

    @field_validator("initial_admin_emails", mode="before")
    @classmethod
    def split_initial_admin_emails(cls, value: object) -> object:
        if isinstance(value, str):
            return [item.strip().lower() for item in value.split(",") if item.strip()]
        return value

    @model_validator(mode="after")
    def require_a_real_production_auth_secret(self) -> Settings:
        if (
            self.app_env.lower() == "production"
            and self.auth_secret == "perler-studio-development-secret-change-before-production"
        ):
            raise ValueError("生产环境必须设置独立的 AUTH_SECRET")
        return self

    @property
    def backend_dir(self) -> Path:
        return Path(__file__).resolve().parents[2]

    def resolve_path(self, path: Path) -> Path:
        return path if path.is_absolute() else (self.backend_dir / path).resolve()

    @property
    def storage_dir(self) -> Path:
        return self.resolve_path(self.data_dir)

    @property
    def database_file(self) -> Path:
        return self.resolve_path(self.database_path or self.data_dir / "perler-studio.db")

    @property
    def upload_dir(self) -> Path:
        return self.storage_dir / "uploads"

    @property
    def pattern_dir(self) -> Path:
        return self.storage_dir / "patterns"

    @property
    def project_dir(self) -> Path:
        return self.storage_dir / "projects"

    @property
    def export_dir(self) -> Path:
        return self.storage_dir / "exports"

    @property
    def task_dir(self) -> Path:
        return self.storage_dir / "tasks"

    @property
    def version_dir(self) -> Path:
        return self.storage_dir / "versions"

    @property
    def share_dir(self) -> Path:
        return self.storage_dir / "shares"

    def ensure_storage_dirs(self) -> None:
        self.database_file.parent.mkdir(parents=True, exist_ok=True)
        for directory in (
            self.upload_dir,
            self.pattern_dir,
            self.project_dir,
            self.export_dir,
            self.task_dir,
            self.version_dir,
            self.share_dir,
        ):
            directory.mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    return Settings()
