from __future__ import annotations

import json
import sqlite3
from typing import Any

from app.core.exceptions import AppError, not_found, validation_error
from app.schemas.publication import PublicationCreateRequest, PublicationReviewRequest, PublicationStatus
from app.services.auth_service import AuthService, get_auth_service
from app.services.palette_service import get_palette_service
from app.services.pattern_preview import PREVIEW_STYLE, pattern_preview_is_current, save_pattern_preview
from app.services.storage_service import StorageService, get_storage, utc_now


class PublicationService:
    """Moderated public-project submissions backed by the account database."""

    def __init__(self, auth: AuthService | None = None, storage: StorageService | None = None) -> None:
        self.auth = auth or get_auth_service()
        self.storage = storage or get_storage()
        self.palettes = get_palette_service()
        self._initialize()

    def _initialize(self) -> None:
        with self.auth._connect() as connection:  # noqa: SLF001 - shared local SQLite boundary
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS publications (
                    id TEXT PRIMARY KEY,
                    public_token TEXT NOT NULL UNIQUE,
                    project_id TEXT NOT NULL,
                    pattern_id TEXT NOT NULL,
                    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
                    title TEXT NOT NULL,
                    description TEXT,
                    tags_json TEXT NOT NULL DEFAULT '[]',
                    finished_image_id TEXT,
                    status TEXT NOT NULL CHECK (status IN ('pending', 'approved', 'rejected', 'withdrawn')),
                    submitted_at TEXT NOT NULL,
                    reviewed_at TEXT,
                    reviewer_id TEXT REFERENCES users(id) ON DELETE SET NULL,
                    review_note TEXT,
                    review_checks_json TEXT NOT NULL DEFAULT '[]'
                );
                CREATE INDEX IF NOT EXISTS idx_publications_owner_status
                    ON publications(user_id, status, submitted_at DESC);
                CREATE INDEX IF NOT EXISTS idx_publications_review_queue
                    ON publications(status, submitted_at DESC);
                CREATE UNIQUE INDEX IF NOT EXISTS idx_publications_public_token
                    ON publications(public_token);
                CREATE TABLE IF NOT EXISTS publication_favorites (
                    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    publication_id TEXT NOT NULL REFERENCES publications(id) ON DELETE CASCADE,
                    created_at TEXT NOT NULL,
                    PRIMARY KEY (user_id, publication_id)
                );
                CREATE INDEX IF NOT EXISTS idx_publication_favorites_user
                    ON publication_favorites(user_id, created_at DESC);
                """
            )
            columns = {str(row["name"]) for row in connection.execute("PRAGMA table_info(publications)")}
            if "tags_json" not in columns:
                connection.execute("ALTER TABLE publications ADD COLUMN tags_json TEXT NOT NULL DEFAULT '[]'")
            if "finished_image_id" not in columns:
                connection.execute("ALTER TABLE publications ADD COLUMN finished_image_id TEXT")
            if "review_checks_json" not in columns:
                connection.execute("ALTER TABLE publications ADD COLUMN review_checks_json TEXT NOT NULL DEFAULT '[]'")
            connection.execute("PRAGMA optimize")

    @staticmethod
    def _serialize(row: sqlite3.Row) -> dict[str, Any]:
        try:
            tags = json.loads(str(row["tags_json"] or "[]"))
        except (TypeError, ValueError):
            tags = []
        try:
            review_checks = json.loads(str(row["review_checks_json"] or "[]"))
        except (TypeError, ValueError):
            review_checks = []
        return {
            "id": str(row["id"]),
            "public_token": str(row["public_token"]),
            "project_id": str(row["project_id"]),
            "pattern_id": str(row["pattern_id"]),
            "title": str(row["title"]),
            "description": row["description"],
            "tags": [tag for tag in tags if isinstance(tag, str)],
            "finished_image_id": row["finished_image_id"],
            "status": str(row["status"]),
            "submitted_at": str(row["submitted_at"]),
            "reviewed_at": row["reviewed_at"],
            "review_note": row["review_note"],
            "review_checks": [check for check in review_checks if isinstance(check, str)],
            "author": {
                "id": str(row["user_id"]),
                "display_name": str(row["author_name"] or "已删除用户"),
            },
            "reviewer": (
                {"id": str(row["reviewer_id"]), "display_name": str(row["reviewer_name"] or "管理员")}
                if row["reviewer_id"]
                else None
            ),
        }

    @staticmethod
    def _select_sql(where: str) -> str:
        return f"""
            SELECT publications.*, author.display_name AS author_name, reviewer.display_name AS reviewer_name
            FROM publications
            LEFT JOIN users AS author ON author.id = publications.user_id
            LEFT JOIN users AS reviewer ON reviewer.id = publications.reviewer_id
            {where}
        """

    @staticmethod
    def _admin_filter(status: PublicationStatus | None, query: str | None) -> tuple[str, list[Any]]:
        clauses: list[str] = []
        params: list[Any] = []
        if status:
            clauses.append("publications.status = ?")
            params.append(status.value)

        normalized = (query or "").strip()
        if normalized:
            escaped = normalized.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            needle = f"%{escaped}%"
            searchable_columns = (
                "publications.title",
                "publications.description",
                "publications.tags_json",
                "author.display_name",
                "publications.id",
                "publications.public_token",
                "publications.project_id",
                "publications.pattern_id",
            )
            clauses.append(
                "(" + " OR ".join(f"COALESCE({column}, '') LIKE ? ESCAPE '\\'" for column in searchable_columns) + ")"
            )
            params.extend([needle] * len(searchable_columns))

        return (f"WHERE {' AND '.join(clauses)}" if clauses else ""), params

    def submit(self, user_id: str, project: dict[str, Any], request: PublicationCreateRequest) -> dict[str, Any]:
        pattern_id = project.get("pattern_id")
        if not pattern_id:
            raise validation_error("项目尚未包含图纸，无法提交审核", "PROJECT_WITHOUT_PATTERN")
        fallback_description = str(project.get("description") or "").strip()[:50] or None
        description = request.description if "description" in request.model_fields_set else fallback_description
        with self.auth._connect() as connection:  # noqa: SLF001
            pending = connection.execute(
                "SELECT id FROM publications WHERE project_id = ? AND user_id = ? AND status = ?",
                (project["id"], user_id, PublicationStatus.pending.value),
            ).fetchone()
            if pending:
                raise AppError(409, "PUBLICATION_ALREADY_PENDING", "该项目已有待审核的发布申请")
            publication_id = StorageService.new_id("pub")
            now = utc_now()
            connection.execute(
                """
                INSERT INTO publications (
                    id, public_token, project_id, pattern_id, user_id, title, description, tags_json, finished_image_id,
                    status, submitted_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    publication_id,
                    publication_id,
                    project["id"],
                    pattern_id,
                    user_id,
                    request.title or project["name"],
                    description,
                    json.dumps(request.tags, ensure_ascii=False, separators=(",", ":")),
                    request.finished_image_id,
                    PublicationStatus.pending.value,
                    now,
                ),
            )
        return self.get_for_owner(user_id, publication_id)

    def _finished_photo_preview_url(self, publication: dict[str, Any]) -> str | None:
        base_url = self._finished_photo_private_preview_url(publication)
        return f"{base_url}?publication_token={publication['public_token']}" if base_url else None

    def _finished_photo_private_preview_url(self, publication: dict[str, Any]) -> str | None:
        return self._private_image_preview_url(publication.get("finished_image_id"))

    def _private_image_preview_url(self, image_id: object) -> str | None:
        if not image_id:
            return None
        try:
            image = self.storage.load_image_metadata(str(image_id))
            path = self.storage.settings.storage_dir / str(image["preview_path"])
            if not path.is_file():
                return None
            base_url = self.storage.media_url(path, self.storage.settings.storage_dir)
        except AppError:
            return None
        return base_url

    def _private_pattern_preview_url(self, pattern: dict[str, Any]) -> str:
        if not pattern_preview_is_current(pattern, self.storage.settings) and save_pattern_preview(
            pattern, self.palettes.get(str(pattern["palette_id"])), self.storage.settings, self.storage, force=False
        ):
            self.storage.save_pattern(pattern)
        preview_url = pattern.get("preview_url")
        if not preview_url:
            raise validation_error("图纸预览不可用", "PATTERN_PREVIEW_UNAVAILABLE")
        return str(preview_url)

    def _public_item(self, publication: dict[str, Any], pattern: dict[str, Any]) -> dict[str, Any]:
        return {
            **publication,
            "preview_url": self._public_pattern_preview_url(publication, pattern),
            "finished_photo_preview_url": self._finished_photo_preview_url(publication),
            "grid_width": pattern["grid_width"],
            "grid_height": pattern["grid_height"],
            "statistics": pattern["statistics"],
        }

    def _public_pattern_preview_url(self, publication: dict[str, Any], pattern: dict[str, Any]) -> str:
        preview_url = self._private_pattern_preview_url(pattern)
        return f"{preview_url}?publication_token={publication['public_token']}&preview_style={PREVIEW_STYLE}"

    def _admin_item(self, publication: dict[str, Any]) -> dict[str, Any]:
        result = {
            **publication,
            "finished_photo_preview_url": self._finished_photo_private_preview_url(publication),
            "preview_url": None,
            "grid_width": None,
            "grid_height": None,
            "total_beads": None,
            "used_color_count": None,
            "review_ready": False,
        }
        try:
            pattern = self.storage.load_pattern(publication["pattern_id"])
            statistics = pattern.get("statistics") or {}
            total_beads = int(statistics.get("total_beads") or 0)
            result.update(
                {
                    "preview_url": self._private_pattern_preview_url(pattern),
                    "grid_width": int(pattern["grid_width"]),
                    "grid_height": int(pattern["grid_height"]),
                    "total_beads": total_beads,
                    "used_color_count": int(statistics.get("used_color_count") or 0),
                    "review_ready": total_beads > 0,
                }
            )
        except (AppError, KeyError, OSError, TypeError, ValueError):
            pass
        return result

    def list_for_owner(self, user_id: str) -> list[dict[str, Any]]:
        with self.auth._connect() as connection:  # noqa: SLF001
            rows = connection.execute(
                self._select_sql("WHERE publications.user_id = ? ORDER BY publications.submitted_at DESC"), (user_id,)
            ).fetchall()
        return [self._serialize(row) for row in rows]

    def list_for_owner_page(self, user_id: str, page: int, page_size: int) -> dict[str, Any]:
        with self.auth._connect() as connection:  # noqa: SLF001
            total = int(
                connection.execute("SELECT COUNT(*) FROM publications WHERE user_id = ?", (user_id,)).fetchone()[0]
            )
            rows = connection.execute(
                self._select_sql(
                    "WHERE publications.user_id = ? ORDER BY publications.submitted_at DESC LIMIT ? OFFSET ?"
                ),
                (user_id, page_size, (page - 1) * page_size),
            ).fetchall()
            status_rows = connection.execute(
                "SELECT status, COUNT(*) AS total FROM publications WHERE user_id = ? GROUP BY status", (user_id,)
            ).fetchall()
        return {
            "items": [self._serialize(row) for row in rows],
            "total": total,
            "page": page,
            "page_size": page_size,
            "status_counts": {str(row["status"]): int(row["total"]) for row in status_rows},
        }

    def get_for_owner(self, user_id: str, publication_id: str) -> dict[str, Any]:
        with self.auth._connect() as connection:  # noqa: SLF001
            row = connection.execute(
                self._select_sql("WHERE publications.id = ? AND publications.user_id = ?"), (publication_id, user_id)
            ).fetchone()
        if not row:
            raise not_found("publication", publication_id)
        return self._serialize(row)

    def withdraw(self, user_id: str, publication_id: str) -> dict[str, Any]:
        publication = self.get_for_owner(user_id, publication_id)
        if publication["status"] == PublicationStatus.withdrawn.value:
            return publication
        with self.auth._connect() as connection:  # noqa: SLF001
            connection.execute(
                "UPDATE publications SET status = ?, reviewed_at = NULL, reviewer_id = NULL WHERE id = ?",
                (PublicationStatus.withdrawn.value, publication_id),
            )
        return self.get_for_owner(user_id, publication_id)

    def delete_for_owner(self, user_id: str, publication_id: str) -> None:
        """Permanently remove an owner's publication record without deleting its source project."""
        self.get_for_owner(user_id, publication_id)
        with self.auth._connect() as connection:  # noqa: SLF001
            connection.execute("DELETE FROM publication_favorites WHERE publication_id = ?", (publication_id,))
            connection.execute("DELETE FROM publications WHERE id = ? AND user_id = ?", (publication_id, user_id))

    def withdraw_by_admin(self, reviewer_id: str, publication_id: str, note: str | None = None) -> dict[str, Any]:
        """Take an approved community work off the shelf while retaining its audit trail."""
        publication = self.get_for_admin(publication_id)
        if publication["status"] != PublicationStatus.approved.value:
            raise AppError(409, "PUBLICATION_NOT_PUBLIC", "只能下架已公开的社区作品")
        review_note = (note or "").strip()
        if not review_note:
            raise validation_error("请填写删除原因，创作者将会在个人中心看到该说明", "TAKEDOWN_REASON_REQUIRED")
        with self.auth._connect() as connection:  # noqa: SLF001
            connection.execute(
                """
                UPDATE publications
                SET status = ?, reviewer_id = ?, reviewed_at = ?, review_note = ?
                WHERE id = ?
                """,
                (PublicationStatus.withdrawn.value, reviewer_id, utc_now(), review_note, publication_id),
            )
        return self.get_for_admin(publication_id)

    def list_for_admin(self, status: PublicationStatus | None, query: str | None = None) -> list[dict[str, Any]]:
        where, params = self._admin_filter(status, query)
        with self.auth._connect() as connection:  # noqa: SLF001
            rows = connection.execute(
                self._select_sql(f"{where} ORDER BY publications.submitted_at ASC"), params
            ).fetchall()
        publications = [self._serialize(row) for row in rows]
        return [self._admin_item(publication) for publication in publications]

    def list_for_admin_page(
        self, status: PublicationStatus | None, query: str | None, page: int, page_size: int
    ) -> dict[str, Any]:
        where, params = self._admin_filter(status, query)
        library_where, library_params = self._admin_filter(status, None)
        with self.auth._connect() as connection:  # noqa: SLF001
            total = int(
                connection.execute(
                    f"""
                    SELECT COUNT(*) FROM publications
                    LEFT JOIN users AS author ON author.id = publications.user_id
                    {where}
                    """,
                    params,
                ).fetchone()[0]
            )
            library_total = (
                total
                if not (query or "").strip()
                else int(
                    connection.execute(f"SELECT COUNT(*) FROM publications {library_where}", library_params).fetchone()[
                        0
                    ]
                )
            )
            rows = connection.execute(
                self._select_sql(f"{where} ORDER BY publications.submitted_at ASC LIMIT ? OFFSET ?"),
                [*params, page_size, (page - 1) * page_size],
            ).fetchall()
        items = [self._serialize(row) for row in rows]
        return {
            "items": [self._admin_item(publication) for publication in items],
            "total": total,
            "library_total": library_total,
            "page": page,
            "page_size": page_size,
        }

    def list_public(self, query: str | None, page: int, page_size: int) -> dict[str, Any]:
        normalized = (query or "").strip()
        where = "WHERE publications.status = ?"
        params: list[Any] = [PublicationStatus.approved.value]
        if normalized:
            where += " AND (publications.title LIKE ? OR publications.description LIKE ? OR author.display_name LIKE ?)"
            needle = f"%{normalized}%"
            params.extend((needle, needle, needle))
        with self.auth._connect() as connection:  # noqa: SLF001
            total = int(
                connection.execute(
                    f"""
                    SELECT COUNT(*) FROM publications
                    LEFT JOIN users AS author ON author.id = publications.user_id
                    {where}
                    """,
                    params,
                ).fetchone()[0]
            )
            rows = connection.execute(
                self._select_sql(f"{where} ORDER BY publications.reviewed_at DESC LIMIT ? OFFSET ?"),
                [*params, page_size, (page - 1) * page_size],
            ).fetchall()
        items: list[dict[str, Any]] = []
        for row in rows:
            publication = self._serialize(row)
            try:
                pattern = self.storage.load_pattern(publication["pattern_id"])
            except AppError:
                continue
            items.append(self._public_item(publication, pattern))
        return {"items": items, "total": total, "page": page, "page_size": page_size}

    def review(self, reviewer_id: str, publication_id: str, request: PublicationReviewRequest) -> dict[str, Any]:
        publication = self.get_for_admin(publication_id)
        if publication["status"] != PublicationStatus.pending.value:
            raise AppError(409, "PUBLICATION_NOT_PENDING", "只能审核待审核的发布申请")
        if request.decision == PublicationStatus.approved:
            readiness = self.get_admin_detail(publication_id)["review_readiness"]
            if not readiness["can_approve"]:
                issue = "；".join(readiness["blocking_issues"])
                raise validation_error(f"作品材料不完整，无法通过审核：{issue}", "PUBLICATION_NOT_REVIEWABLE")
        with self.auth._connect() as connection:  # noqa: SLF001
            cursor = connection.execute(
                """
                UPDATE publications
                SET status = ?, review_note = ?, review_checks_json = ?, reviewer_id = ?, reviewed_at = ?
                WHERE id = ? AND status = ?
                """,
                (
                    request.decision.value,
                    request.note,
                    json.dumps([check.value for check in request.checks], ensure_ascii=False, separators=(",", ":")),
                    reviewer_id,
                    utc_now(),
                    publication_id,
                    PublicationStatus.pending.value,
                ),
            )
            if cursor.rowcount != 1:
                raise AppError(409, "PUBLICATION_NOT_PENDING", "作品审核状态已变更，请刷新后重试")
        return self.get_for_admin(publication_id)

    def get_for_admin(self, publication_id: str) -> dict[str, Any]:
        with self.auth._connect() as connection:  # noqa: SLF001
            row = connection.execute(self._select_sql("WHERE publications.id = ?"), (publication_id,)).fetchone()
        if not row:
            raise not_found("publication", publication_id)
        return self._serialize(row)

    def get_admin_detail(self, publication_id: str) -> dict[str, Any]:
        publication = self.get_for_admin(publication_id)
        blocking_issues: list[str] = []
        warnings: list[str] = []
        pattern_detail: dict[str, Any] | None = None
        project_detail: dict[str, Any] | None = None

        try:
            project = self.storage.load_project(publication["project_id"])
            project_detail = {
                "id": project["id"],
                "name": project.get("name"),
                "description": project.get("description"),
                "created_at": project.get("created_at"),
                "updated_at": project.get("updated_at"),
            }
        except (AppError, KeyError, TypeError):
            warnings.append("关联项目已不可用，请重点核对图纸内容")

        try:
            pattern = self.storage.load_pattern(publication["pattern_id"])
            statistics = pattern.get("statistics") or {}
            total_beads = int(statistics.get("total_beads") or 0)
            if total_beads <= 0:
                blocking_issues.append("图纸中没有可见的拼豆单元格")
            preview_url: str | None = None
            try:
                preview_url = self._private_pattern_preview_url(pattern)
            except (AppError, KeyError, OSError, TypeError, ValueError):
                blocking_issues.append("图纸预览生成失败")
            palette_id = str(pattern.get("palette_id") or "")
            palette_name = palette_id
            palette_brand: str | None = None
            try:
                palette = self.palettes.get(palette_id)
                palette_name = str(palette.get("name") or palette_id)
                palette_brand = str(palette.get("brand")) if palette.get("brand") else None
            except AppError:
                warnings.append("图纸使用的色卡已不可用")
            source_image_preview_url = self._private_image_preview_url(pattern.get("image_id"))
            if pattern.get("image_id") and not source_image_preview_url:
                warnings.append("原始参考图资源已不可用")
            pattern_detail = {
                "id": pattern.get("id"),
                "revision": pattern.get("revision"),
                "preview_url": preview_url,
                "source_image_preview_url": source_image_preview_url,
                "grid_width": pattern.get("grid_width"),
                "grid_height": pattern.get("grid_height"),
                "palette_id": palette_id,
                "palette_name": palette_name,
                "palette_brand": palette_brand,
                "statistics": statistics,
                "color_report": pattern.get("color_report"),
                "created_at": pattern.get("created_at"),
                "updated_at": pattern.get("updated_at"),
            }
        except (AppError, KeyError, TypeError, ValueError):
            blocking_issues.append("关联图纸不存在或数据已损坏")

        finished_photo_preview_url = self._finished_photo_private_preview_url(publication)
        if publication.get("finished_image_id") and not finished_photo_preview_url:
            warnings.append("成品实拍资源已不可用")
        elif not publication.get("finished_image_id"):
            warnings.append("创作者未上传成品实拍（可选材料）")
        if not publication.get("description"):
            warnings.append("创作者未填写作品简介")

        return {
            "publication": publication,
            "project": project_detail,
            "pattern": pattern_detail,
            "finished_photo_preview_url": finished_photo_preview_url,
            "review_readiness": {
                "can_approve": not blocking_issues,
                "blocking_issues": blocking_issues,
                "warnings": warnings,
            },
        }

    def get_public(self, public_token: str) -> dict[str, Any]:
        with self.auth._connect() as connection:  # noqa: SLF001
            row = connection.execute(
                self._select_sql("WHERE publications.public_token = ? AND publications.status = ?"),
                (public_token, PublicationStatus.approved.value),
            ).fetchone()
        if not row:
            raise not_found("publication", public_token)
        publication = self._serialize(row)
        pattern = self.storage.load_pattern(publication["pattern_id"])
        return {
            "publication": publication,
            "pattern": {
                "preview_url": self._public_pattern_preview_url(publication, pattern),
                "grid_width": pattern["grid_width"],
                "grid_height": pattern["grid_height"],
                "statistics": pattern["statistics"],
            },
            "finished_photo_preview_url": self._finished_photo_preview_url(publication),
        }

    def _approved_publication(self, public_token: str) -> dict[str, Any]:
        with self.auth._connect() as connection:  # noqa: SLF001
            row = connection.execute(
                self._select_sql("WHERE publications.public_token = ? AND publications.status = ?"),
                (public_token, PublicationStatus.approved.value),
            ).fetchone()
        if not row:
            raise not_found("publication", public_token)
        return self._serialize(row)

    def favorite(self, user_id: str, public_token: str) -> dict[str, Any]:
        publication = self._approved_publication(public_token)
        with self.auth._connect() as connection:  # noqa: SLF001
            connection.execute(
                """
                INSERT INTO publication_favorites (user_id, publication_id, created_at)
                VALUES (?, ?, ?)
                ON CONFLICT(user_id, publication_id) DO NOTHING
                """,
                (user_id, publication["id"], utc_now()),
            )
        return {"public_token": public_token, "favorited": True}

    def unfavorite(self, user_id: str, public_token: str) -> None:
        publication = self._approved_publication(public_token)
        with self.auth._connect() as connection:  # noqa: SLF001
            connection.execute(
                "DELETE FROM publication_favorites WHERE user_id = ? AND publication_id = ?",
                (user_id, publication["id"]),
            )

    def list_favorites(self, user_id: str) -> list[dict[str, Any]]:
        with self.auth._connect() as connection:  # noqa: SLF001
            rows = connection.execute(
                self._select_sql(
                    """
                    JOIN publication_favorites ON publication_favorites.publication_id = publications.id
                    WHERE publication_favorites.user_id = ? AND publications.status = ?
                    ORDER BY publication_favorites.created_at DESC
                    """
                ),
                (user_id, PublicationStatus.approved.value),
            ).fetchall()
        items: list[dict[str, Any]] = []
        for row in rows:
            publication = self._serialize(row)
            try:
                items.append(self._public_item(publication, self.storage.load_pattern(publication["pattern_id"])))
            except AppError:
                continue
        return items

    def list_favorites_page(self, user_id: str, page: int, page_size: int, query: str | None = None) -> dict[str, Any]:
        normalized = (query or "").strip()
        where = "WHERE publication_favorites.user_id = ? AND publications.status = ?"
        params: list[Any] = [user_id, PublicationStatus.approved.value]
        if normalized:
            where += " AND (publications.title LIKE ? OR publications.description LIKE ? OR author.display_name LIKE ?)"
            needle = f"%{normalized}%"
            params.extend((needle, needle, needle))
        join = "JOIN publication_favorites ON publication_favorites.publication_id = publications.id"
        with self.auth._connect() as connection:  # noqa: SLF001
            total = int(
                connection.execute(
                    f"""
                    SELECT COUNT(*) FROM publications
                    {join}
                    LEFT JOIN users AS author ON author.id = publications.user_id
                    {where}
                    """,
                    params,
                ).fetchone()[0]
            )
            rows = connection.execute(
                self._select_sql(
                    f"""
                    {join}
                    {where}
                    ORDER BY publication_favorites.created_at DESC
                    LIMIT ? OFFSET ?
                    """
                ),
                [*params, page_size, (page - 1) * page_size],
            ).fetchall()
        items: list[dict[str, Any]] = []
        for row in rows:
            publication = self._serialize(row)
            try:
                items.append(self._public_item(publication, self.storage.load_pattern(publication["pattern_id"])))
            except AppError:
                continue
        return {"items": items, "total": total, "page": page, "page_size": page_size}

    def favorite_tokens(self, user_id: str) -> list[str]:
        with self.auth._connect() as connection:  # noqa: SLF001
            rows = connection.execute(
                """
                SELECT publications.public_token
                FROM publication_favorites
                JOIN publications ON publications.id = publication_favorites.publication_id
                WHERE publication_favorites.user_id = ? AND publications.status = ?
                """,
                (user_id, PublicationStatus.approved.value),
            ).fetchall()
        return [str(row["public_token"]) for row in rows]

    def remix_source(self, public_token: str) -> tuple[dict[str, Any], dict[str, Any]]:
        publication = self._approved_publication(public_token)
        return publication, self.storage.load_pattern(publication["pattern_id"])

    def allows_pattern_preview(self, public_token: str, pattern_id: str) -> bool:
        with self.auth._connect() as connection:  # noqa: SLF001
            row = connection.execute(
                """
                SELECT 1 FROM publications
                WHERE public_token = ? AND pattern_id = ? AND status = ?
                """,
                (public_token, pattern_id, PublicationStatus.approved.value),
            ).fetchone()
        return bool(row)

    def allows_finished_image(self, public_token: str, image_id: str) -> bool:
        with self.auth._connect() as connection:  # noqa: SLF001
            row = connection.execute(
                """
                SELECT 1 FROM publications
                WHERE public_token = ? AND finished_image_id = ? AND status = ?
                """,
                (public_token, image_id, PublicationStatus.approved.value),
            ).fetchone()
        return bool(row)


def get_publication_service() -> PublicationService:
    return PublicationService()
