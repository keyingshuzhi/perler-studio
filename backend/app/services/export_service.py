from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.core.config import Settings, get_settings
from app.core.exceptions import validation_error
from app.schemas.export import (
    CSVExportRequest,
    PDFExportRequest,
    PNGExportRequest,
    ProjectExportRequest,
    SVGExportRequest,
)
from app.services.csv_exporter import export_statistics_csv
from app.services.palette_service import PaletteService, get_palette_service
from app.services.pdf_exporter import export_pdf
from app.services.png_exporter import export_png
from app.services.project_service import ProjectService, get_project_service
from app.services.storage_service import StorageService, get_storage, utc_now
from app.services.svg_exporter import export_svg


class ExportService:
    """Synchronous export adapter; the record format is Celery-ready for V1 tasks."""

    def __init__(
        self,
        settings: Settings | None = None,
        storage: StorageService | None = None,
        palettes: PaletteService | None = None,
        projects: ProjectService | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.storage = storage or get_storage()
        self.palettes = palettes or get_palette_service()
        self.projects = projects or get_project_service()

    def _resolve_pattern(self, request: Any) -> tuple[dict[str, Any], dict[str, Any] | None]:
        if request.pattern_id:
            return self.storage.load_pattern(request.pattern_id), None
        if request.project_id:
            project = self.projects.get(request.project_id)
            if not project.get("pattern_id"):
                raise validation_error("项目尚未关联图纸，无法导出", "PROJECT_HAS_NO_PATTERN")
            return self.storage.load_pattern(project["pattern_id"]), project
        raise validation_error("必须指定 project_id 或 pattern_id", "EXPORT_TARGET_REQUIRED")

    def _record(
        self, kind: str, suffix: str, pattern: dict[str, Any], project: dict[str, Any] | None, settings: dict[str, Any]
    ) -> tuple[dict[str, Any], Path]:
        export_id, now = self.storage.new_id("exp"), utc_now()
        destination = self.settings.export_dir / f"{export_id}.{suffix}"
        record = {
            "id": export_id,
            "project_id": project["id"] if project else None,
            "pattern_id": pattern["id"],
            "export_type": kind,
            "status": "running",
            "settings": settings,
            "file_path": str(destination.relative_to(self.settings.storage_dir)),
            "file_size": None,
            "file_url": None,
            "error_message": None,
            "created_at": now,
            "completed_at": None,
        }
        self.storage.save_export_record(record)
        return record, destination

    def _finish(self, record: dict[str, Any], destination: Path) -> dict[str, Any]:
        record.update(
            {
                "status": "success",
                "file_size": destination.stat().st_size,
                "file_url": self.storage.media_url(destination, self.settings.storage_dir),
                "completed_at": utc_now(),
            }
        )
        self.storage.save_export_record(record)
        return record

    def png(self, request: PNGExportRequest) -> dict[str, Any]:
        pattern, project = self._resolve_pattern(request)
        palette = self.palettes.get(pattern["palette_id"])
        options = request.model_dump(exclude={"project_id", "pattern_id"}, mode="json")
        record, destination = self._record("png", "png", pattern, project, options)
        try:
            export_png(pattern, palette, options, destination)
        except Exception as error:
            record.update({"status": "failed", "error_message": str(error), "completed_at": utc_now()})
            self.storage.save_export_record(record)
            raise
        return self._finish(record, destination)

    def pdf(self, request: PDFExportRequest) -> dict[str, Any]:
        pattern, project = self._resolve_pattern(request)
        palette = self.palettes.get(pattern["palette_id"])
        options = request.model_dump(exclude={"project_id", "pattern_id"}, mode="json")
        record, destination = self._record("pdf", "pdf", pattern, project, options)
        try:
            export_pdf(
                pattern,
                palette,
                {**options, "title": project["name"] if project else "Perler Studio 图纸"},
                destination,
            )
        except Exception as error:
            record.update({"status": "failed", "error_message": str(error), "completed_at": utc_now()})
            self.storage.save_export_record(record)
            raise
        return self._finish(record, destination)

    def svg(self, request: SVGExportRequest) -> dict[str, Any]:
        pattern, project = self._resolve_pattern(request)
        palette = self.palettes.get(pattern["palette_id"])
        options = request.model_dump(exclude={"project_id", "pattern_id"}, mode="json")
        record, destination = self._record("svg", "svg", pattern, project, options)
        try:
            export_svg(pattern, palette, options, destination)
        except Exception as error:
            record.update({"status": "failed", "error_message": str(error), "completed_at": utc_now()})
            self.storage.save_export_record(record)
            raise
        return self._finish(record, destination)

    def csv(self, request: CSVExportRequest) -> dict[str, Any]:
        pattern, project = self._resolve_pattern(request)
        options = request.model_dump(exclude={"project_id", "pattern_id"}, mode="json")
        record, destination = self._record("csv", "csv", pattern, project, options)
        export_statistics_csv(pattern, destination, options["include_waste"])
        return self._finish(record, destination)

    def project_json(self, request: ProjectExportRequest) -> dict[str, Any]:
        pattern, project = self._resolve_pattern(request)
        record, destination = self._record("project", "json", pattern, project, {})
        with destination.open("w", encoding="utf-8") as handle:
            json.dump(
                {"format": "perler-studio-project", "version": 1, "project": project, "pattern": pattern},
                handle,
                ensure_ascii=False,
                separators=(",", ":"),
            )
        return self._finish(record, destination)

    def get(self, export_id: str) -> dict[str, Any]:
        return self.storage.load_export_record(export_id)

    def file_path(self, export_id: str) -> Path:
        record = self.get(export_id)
        if record["status"] != "success":
            raise validation_error("导出文件尚未生成", "EXPORT_NOT_READY")
        path = (self.settings.storage_dir / record["file_path"]).resolve()
        if self.settings.export_dir.resolve() not in path.parents or not path.is_file():
            raise validation_error("导出文件不存在", "EXPORT_FILE_MISSING")
        return path


def get_export_service() -> ExportService:
    return ExportService()
