from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import PurePosixPath

from fastapi import FastAPI, Query, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.v1.router import api_router
from app.core.config import Settings, get_settings
from app.schemas.common import success
from app.services.auth_service import AuthService
from app.services.publication_service import PublicationService
from app.services.storage_service import StorageService

logger = logging.getLogger("perler_studio")


def create_app(settings: Settings | None = None) -> FastAPI:
    runtime = settings or get_settings()
    runtime.ensure_storage_dirs()
    AuthService(runtime)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        runtime.ensure_storage_dirs()
        yield

    app = FastAPI(
        title=runtime.app_name,
        version=runtime.app_version,
        debug=runtime.app_debug,
        description="专业拼豆图纸生成、编辑、统计与导出 API",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=runtime.cors_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type", "Authorization", "If-Match"],
    )

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        if isinstance(exc.detail, dict) and "code" in exc.detail:
            return JSONResponse(
                status_code=exc.status_code,
                content={
                    "success": False,
                    "data": exc.detail.get("data"),
                    "message": exc.detail.get("message"),
                    "code": exc.detail["code"],
                },
            )
        return JSONResponse(
            status_code=exc.status_code,
            content={"success": False, "data": None, "message": str(exc.detail), "code": "HTTP_ERROR"},
        )

    @app.exception_handler(RequestValidationError)
    async def request_validation_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content=jsonable_encoder(
                {"success": False, "data": exc.errors(), "message": "请求参数校验失败", "code": "VALIDATION_ERROR"}
            ),
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(_: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled API error", exc_info=exc)
        return JSONResponse(
            status_code=500,
            content={"success": False, "data": None, "message": "服务器内部错误", "code": "INTERNAL_ERROR"},
        )

    app.include_router(api_router, prefix=runtime.api_v1_prefix)

    @app.get("/media/{asset_path:path}", include_in_schema=False)
    def serve_media(
        asset_path: str,
        request: Request,
        access_token: str | None = Query(default=None),
        share_token: str | None = Query(default=None),
        publication_token: str | None = Query(default=None),
    ) -> FileResponse:
        """Serve private user media only to its owner, with a share-preview exception."""
        relative = PurePosixPath(asset_path)
        if relative.is_absolute() or ".." in relative.parts:
            raise StarletteHTTPException(status_code=404, detail="文件不存在")
        parts = relative.parts
        if len(parts) >= 2 and parts[0] == "uploads":
            resource_type, resource_id = "image", parts[1]
        elif len(parts) == 2 and parts[0] == "patterns" and parts[1].endswith(".png"):
            resource_type, resource_id = "pattern", parts[1][:-4]
        elif len(parts) == 2 and parts[0] == "exports":
            resource_type, resource_id = "export", parts[1].split(".", 1)[0]
        else:
            raise StarletteHTTPException(status_code=404, detail="文件不存在")

        storage = StorageService(runtime)
        if share_token and resource_type == "pattern":
            share = storage.load_share(share_token)
            project = storage.load_project(str(share["project_id"]))
            if project.get("pattern_id") != resource_id:
                raise StarletteHTTPException(status_code=404, detail="文件不存在")
        elif publication_token and resource_type == "pattern":
            publication_service = PublicationService(AuthService(runtime), storage)
            if not publication_service.allows_pattern_preview(publication_token, resource_id):
                raise StarletteHTTPException(status_code=404, detail="文件不存在")
        elif publication_token and resource_type == "image":
            publication_service = PublicationService(AuthService(runtime), storage)
            if not publication_service.allows_finished_image(publication_token, resource_id):
                raise StarletteHTTPException(status_code=404, detail="文件不存在")
        else:
            authorization = request.headers.get("authorization", "")
            bearer_token = authorization[7:] if authorization.lower().startswith("bearer ") else None
            token = access_token or bearer_token
            if not token:
                raise StarletteHTTPException(status_code=401, detail="请先登录后再继续")
            user = AuthService(runtime).current_user(token)
            if user["role"] != AuthService.ADMIN_ROLE:
                AuthService(runtime).require_owner(user["id"], resource_type, resource_id)

        path = (runtime.storage_dir / relative).resolve()
        if runtime.storage_dir.resolve() not in path.parents or not path.is_file():
            raise StarletteHTTPException(status_code=404, detail="文件不存在")
        return FileResponse(path)

    @app.get("/health", tags=["system"])
    def health() -> dict[str, object]:
        return success({"status": "ok", "version": runtime.app_version, "environment": runtime.app_env})

    return app


app = create_app()
