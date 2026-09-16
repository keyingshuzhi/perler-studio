from __future__ import annotations

from typing import Any

from app.core.exceptions import validation_error
from app.schemas.project import ProjectCreate, ProjectUpdate
from app.schemas.share import ShareCommentRequest, ShareConfirmationRequest, ShareCreateRequest, VersionCreateRequest
from app.services.palette_service import get_palette_service
from app.services.pattern_preview import save_pattern_preview
from app.services.storage_service import StorageService, get_storage, utc_now


class ProjectService:
    def __init__(self, storage: StorageService | None = None) -> None:
        self.storage = storage or get_storage()

    def create(self, request: ProjectCreate) -> dict[str, Any]:
        if request.pattern_id:
            self.storage.load_pattern(request.pattern_id)
        project_id, now = self.storage.new_id("pro"), utc_now()
        project = {
            "id": project_id,
            "name": request.name,
            "description": request.description,
            "pattern_id": request.pattern_id,
            "editor_settings": request.editor_settings,
            "created_at": now,
            "updated_at": now,
        }
        self.storage.save_project(project)
        return project

    def list(self) -> list[dict[str, Any]]:
        return self.storage.list_projects()

    def get(self, project_id: str) -> dict[str, Any]:
        return self.storage.load_project(project_id)

    def update(self, project_id: str, request: ProjectUpdate) -> dict[str, Any]:
        project = self.storage.load_project(project_id)
        changes = request.model_dump(exclude_none=True)
        if "pattern_id" in changes:
            self.storage.load_pattern(changes["pattern_id"])
        project.update(changes)
        project["updated_at"] = utc_now()
        self.storage.save_project(project)
        return project

    def duplicate(self, project_id: str) -> dict[str, Any]:
        source = self.storage.load_project(project_id)
        new_id, now = self.storage.new_id("pro"), utc_now()
        pattern_id = source.get("pattern_id")
        if pattern_id:
            source_pattern = self.storage.load_pattern(pattern_id)
            new_pattern_id = self.storage.new_id("pat")
            cloned_pattern = {
                **source_pattern,
                "id": new_pattern_id,
                "revision": 1,
                "cells": list(source_pattern["cells"]),
                "created_at": now,
                "updated_at": now,
            }
            palette = get_palette_service().get(cloned_pattern["palette_id"])
            save_pattern_preview(cloned_pattern, palette, self.storage.settings, self.storage)
            self.storage.save_pattern(cloned_pattern)
            pattern_id = new_pattern_id
        copy = {
            **source,
            "id": new_id,
            "name": f"{source['name']}（副本）",
            "pattern_id": pattern_id,
            "created_at": now,
            "updated_at": now,
        }
        self.storage.save_project(copy)
        return copy

    def _save_pattern_preview(self, pattern: dict[str, Any]) -> None:
        palette = get_palette_service().get(pattern["palette_id"])
        save_pattern_preview(pattern, palette, self.storage.settings, self.storage)

    def create_version(self, project_id: str, request: VersionCreateRequest) -> dict[str, Any]:
        project = self.storage.load_project(project_id)
        now = utc_now()
        pattern_id = project.get("pattern_id")
        pattern = self.storage.load_pattern(pattern_id) if pattern_id else None
        if request.automatic and pattern:
            latest = next(iter(self.storage.list_project_versions(project_id)), None)
            if latest and latest.get("pattern_revision") == pattern.get("revision"):
                return self._version_summary(latest)
        version_timestamp = now[:16].replace("T", " ")
        default_label = f"自动保存 {version_timestamp}" if request.automatic else f"版本 {version_timestamp}"
        version = {
            "id": self.storage.new_id("ver"),
            "project_id": project_id,
            "label": request.label or default_label,
            "automatic": request.automatic,
            "pattern": pattern,
            "pattern_revision": pattern.get("revision") if pattern else None,
            "created_at": now,
        }
        self.storage.save_project_version(version)
        return self._version_summary(version)

    @staticmethod
    def _version_summary(version: dict[str, Any]) -> dict[str, Any]:
        pattern = version.get("pattern") or {}
        return {
            "id": version["id"],
            "project_id": version["project_id"],
            "label": version["label"],
            "pattern_revision": version.get("pattern_revision"),
            "automatic": bool(version.get("automatic", False)),
            "preview_url": pattern.get("preview_url"),
            "created_at": version["created_at"],
        }

    def list_versions(self, project_id: str) -> list[dict[str, Any]]:
        self.storage.load_project(project_id)
        return [self._version_summary(version) for version in self.storage.list_project_versions(project_id)]

    def get_version(self, project_id: str, version_id: str) -> dict[str, Any]:
        """Return an immutable snapshot for owner-side comparison only."""
        self.storage.load_project(project_id)
        version = self.storage.load_project_version(project_id, version_id)
        return {**self._version_summary(version), "pattern": version.get("pattern")}

    def restore_version(self, project_id: str, version_id: str) -> dict[str, Any]:
        project = self.storage.load_project(project_id)
        version = self.storage.load_project_version(project_id, version_id)
        snapshot = version.get("pattern")
        if not snapshot:
            raise validation_error("该版本不包含可恢复的图纸", "VERSION_WITHOUT_PATTERN")
        if project.get("pattern_id"):
            current = self.storage.load_pattern(project["pattern_id"])
            pattern_id = current["id"]
            revision = int(current["revision"]) + 1
            created_at = current["created_at"]
        else:
            pattern_id, revision, created_at = self.storage.new_id("pat"), 1, utc_now()
        restored = {
            **snapshot,
            "id": pattern_id,
            "revision": revision,
            "cells": list(snapshot["cells"]),
            "created_at": created_at,
            "updated_at": utc_now(),
        }
        self._save_pattern_preview(restored)
        self.storage.save_pattern(restored)
        project["pattern_id"] = pattern_id
        project["updated_at"] = utc_now()
        self.storage.save_project(project)
        return project

    def create_share(self, project_id: str, request: ShareCreateRequest) -> dict[str, Any]:
        project = self.storage.load_project(project_id)
        if not project.get("pattern_id"):
            raise validation_error("项目尚未包含图纸，无法创建分享", "PROJECT_WITHOUT_PATTERN")
        token, now = self.storage.new_id("shr"), utc_now()
        share = {
            "token": token,
            "project_id": project_id,
            "title": request.title or project["name"],
            "created_at": now,
            "confirmation": None,
            "comments": [],
        }
        self.storage.save_share(share)
        return share

    def get_share(self, token: str) -> dict[str, Any]:
        share = self.storage.load_share(token)
        project = self.storage.load_project(share["project_id"])
        pattern = self.storage.load_pattern(project["pattern_id"]) if project.get("pattern_id") else None
        return {
            "share": {**share, "comments": share.get("comments", [])},
            "project": {"id": project["id"], "name": project["name"], "description": project.get("description")},
            "pattern": (
                {
                    "preview_url": f"{pattern['preview_url']}?share_token={token}",
                    "grid_width": pattern["grid_width"],
                    "grid_height": pattern["grid_height"],
                    "statistics": pattern["statistics"],
                }
                if pattern
                else None
            ),
        }

    def confirm_share(self, token: str, request: ShareConfirmationRequest) -> dict[str, Any]:
        share = self.storage.load_share(token)
        share["confirmation"] = {**request.model_dump(mode="json"), "confirmed_at": utc_now()}
        self.storage.save_share(share)
        return self.get_share(token)

    def add_share_comment(self, token: str, request: ShareCommentRequest) -> dict[str, Any]:
        """Persist a client note, optionally anchored to a pattern cell.

        Shares are deliberately public/read-only.  The comment exposes only an
        address (row/column), never the underlying editable cell data.
        """
        share = self.storage.load_share(token)
        project = self.storage.load_project(share["project_id"])
        pattern = self.storage.load_pattern(project["pattern_id"]) if project.get("pattern_id") else None
        cell_index = request.cell_index
        comment: dict[str, Any] = {
            "id": self.storage.new_id("cmt"),
            "message": request.message.strip(),
            "created_at": utc_now(),
            "author_label": "客户",
        }
        if not comment["message"]:
            raise validation_error("留言不能为空", "EMPTY_SHARE_COMMENT")
        if cell_index is not None:
            if not pattern or cell_index >= pattern["grid_width"] * pattern["grid_height"]:
                raise validation_error("留言坐标不在图纸范围内", "INVALID_SHARE_COMMENT_CELL")
            comment.update(
                {
                    "cell_index": cell_index,
                    "row": cell_index // pattern["grid_width"] + 1,
                    "column": cell_index % pattern["grid_width"] + 1,
                }
            )
        share.setdefault("comments", []).append(comment)
        self.storage.save_share(share)
        return self.get_share(token)

    def delete(self, project_id: str) -> None:
        self.storage.delete_project(project_id)


def get_project_service() -> ProjectService:
    return ProjectService()
