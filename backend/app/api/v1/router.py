from fastapi import APIRouter

from app.api.v1 import admin, auth, exports, images, palettes, patterns, presets, projects, publications, shares, tasks

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(admin.router)
api_router.include_router(images.router)
api_router.include_router(patterns.router)
api_router.include_router(palettes.router)
api_router.include_router(projects.router)
api_router.include_router(publications.router)
api_router.include_router(shares.router)
api_router.include_router(exports.router)
api_router.include_router(tasks.router)
api_router.include_router(presets.router)
