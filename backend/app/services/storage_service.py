from __future__ import annotations

import json
import os
import re
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from app.core.config import Settings, get_settings
from app.core.exceptions import not_found, validation_error

_SAFE_ID = re.compile(r"^[a-z]+_[0-9a-f]{12,64}$")


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


class StorageService:
    """Filesystem persistence with atomic JSON replacement for the MVP.

    The API stores only generated IDs in paths, never client filenames. This keeps
    the same service boundary when local storage is later replaced by S3/MinIO.
    """

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.settings.ensure_storage_dirs()

    @staticmethod
    def new_id(prefix: str) -> str:
        return f"{prefix}_{uuid4().hex}"

    @staticmethod
    def _validate_id(value: str) -> str:
        if not _SAFE_ID.fullmatch(value):
            raise validation_error("资源标识格式无效", "INVALID_RESOURCE_ID")
        return value

    @staticmethod
    def _write_json(path: Path, data: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                json.dump(data, handle, ensure_ascii=False, separators=(",", ":"))
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp_name, path)
        finally:
            if os.path.exists(temp_name):
                os.unlink(temp_name)

    @staticmethod
    def _read_json(path: Path, resource: str, resource_id: str) -> dict[str, Any]:
        if not path.is_file():
            raise not_found(resource, resource_id)
        try:
            with path.open(encoding="utf-8") as handle:
                return json.load(handle)
        except json.JSONDecodeError as error:
            raise validation_error(f"{resource} 数据损坏", "CORRUPT_STORAGE") from error

    def image_dir(self, image_id: str) -> Path:
        return self.settings.upload_dir / self._validate_id(image_id)

    def image_meta_path(self, image_id: str) -> Path:
        return self.image_dir(image_id) / "metadata.json"

    def save_image_metadata(self, metadata: dict[str, Any]) -> None:
        self._write_json(self.image_meta_path(metadata["image_id"]), metadata)

    def load_image_metadata(self, image_id: str) -> dict[str, Any]:
        return self._read_json(self.image_meta_path(image_id), "image", image_id)

    def pattern_path(self, pattern_id: str) -> Path:
        return self.settings.pattern_dir / f"{self._validate_id(pattern_id)}.json"

    def save_pattern(self, pattern: dict[str, Any]) -> None:
        self._write_json(self.pattern_path(pattern["id"]), pattern)

    def load_pattern(self, pattern_id: str) -> dict[str, Any]:
        return self._read_json(self.pattern_path(pattern_id), "pattern", pattern_id)

    def delete_pattern(self, pattern_id: str) -> None:
        path = self.pattern_path(pattern_id)
        if not path.exists():
            raise not_found("pattern", pattern_id)
        path.unlink()

    def project_path(self, project_id: str) -> Path:
        return self.settings.project_dir / f"{self._validate_id(project_id)}.json"

    def save_project(self, project: dict[str, Any]) -> None:
        self._write_json(self.project_path(project["id"]), project)

    def load_project(self, project_id: str) -> dict[str, Any]:
        return self._read_json(self.project_path(project_id), "project", project_id)

    def delete_project(self, project_id: str) -> None:
        path = self.project_path(project_id)
        if not path.exists():
            raise not_found("project", project_id)
        path.unlink()

    def list_projects(self) -> list[dict[str, Any]]:
        projects: list[dict[str, Any]] = []
        for path in self.settings.project_dir.glob("pro_*.json"):
            try:
                with path.open(encoding="utf-8") as handle:
                    projects.append(json.load(handle))
            except json.JSONDecodeError:
                continue
        return sorted(projects, key=lambda project: project.get("updated_at", ""), reverse=True)

    def export_record_path(self, export_id: str) -> Path:
        return self.settings.export_dir / f"{self._validate_id(export_id)}.json"

    def save_export_record(self, export_record: dict[str, Any]) -> None:
        self._write_json(self.export_record_path(export_record["id"]), export_record)

    def load_export_record(self, export_id: str) -> dict[str, Any]:
        return self._read_json(self.export_record_path(export_id), "export", export_id)

    def task_path(self, task_id: str) -> Path:
        return self.settings.task_dir / f"{self._validate_id(task_id)}.json"

    def save_task(self, task: dict[str, Any]) -> None:
        self._write_json(self.task_path(task["id"]), task)

    def load_task(self, task_id: str) -> dict[str, Any]:
        return self._read_json(self.task_path(task_id), "task", task_id)

    def project_version_path(self, project_id: str, version_id: str) -> Path:
        return self.settings.version_dir / self._validate_id(project_id) / f"{self._validate_id(version_id)}.json"

    def save_project_version(self, version: dict[str, Any]) -> None:
        self._write_json(self.project_version_path(version["project_id"], version["id"]), version)

    def load_project_version(self, project_id: str, version_id: str) -> dict[str, Any]:
        return self._read_json(self.project_version_path(project_id, version_id), "project version", version_id)

    def list_project_versions(self, project_id: str) -> list[dict[str, Any]]:
        directory = self.settings.version_dir / self._validate_id(project_id)
        versions: list[dict[str, Any]] = []
        for path in directory.glob("ver_*.json"):
            try:
                with path.open(encoding="utf-8") as handle:
                    versions.append(json.load(handle))
            except json.JSONDecodeError:
                continue
        return sorted(versions, key=lambda item: item.get("created_at", ""), reverse=True)

    def share_path(self, token: str) -> Path:
        return self.settings.share_dir / f"{self._validate_id(token)}.json"

    def save_share(self, share: dict[str, Any]) -> None:
        self._write_json(self.share_path(share["token"]), share)

    def load_share(self, token: str) -> dict[str, Any]:
        return self._read_json(self.share_path(token), "share", token)

    @staticmethod
    def media_url(path: Path, media_root: Path) -> str:
        return "/media/" + path.resolve().relative_to(media_root.resolve()).as_posix()


def get_storage() -> StorageService:
    return StorageService()
