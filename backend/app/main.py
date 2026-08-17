from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.conditions import router as conditions_router
from app.api.geocode import router as geocode_router
from app.api.reports import router as reports_router
from app.api.routes_v2 import router as routes_router
from app.api.users_v2 import router as users_router
from app.core.config import settings

# ============================================================
# FastAPI Application
# ============================================================

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="성남시 배리어프리 길안내 2차 프로토타입 백엔드 API",
)

# frontend/map.html을 Live Server(예: 127.0.0.1:5500)로 실행해도
# FastAPI API 및 사진 업로드 요청을 허용합니다.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:8000",
        "http://localhost:8000",
    ],
    allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# Static Files
# ============================================================

# backend/static/
BASE_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = BASE_DIR / "static"

# 업로드 폴더가 없으면 생성
STATIC_DIR.mkdir(parents=True, exist_ok=True)

app.mount(
    "/static",
    StaticFiles(directory=str(STATIC_DIR)),
    name="static",
)


# ============================================================
# API Routers
# ============================================================

API_PREFIX = "/api/v2"

app.include_router(
    conditions_router,
    prefix=API_PREFIX,
)

app.include_router(
    users_router,
    prefix=API_PREFIX,
)

app.include_router(
    routes_router,
    prefix=API_PREFIX,
)

app.include_router(
    reports_router,
    prefix=API_PREFIX,
)

app.include_router(
    geocode_router,
    prefix=API_PREFIX,
)


# ============================================================
# System
# ============================================================


@app.get(
    "/",
    tags=["System"],
)
async def root():
    return {
        "message": "성남시 배리어프리 길안내 API",
        "version": settings.VERSION,
        "docs": "/docs",
    }


@app.get(
    "/health",
    tags=["System"],
)
async def health():
    return {
        "status": "ok",
        "version": settings.VERSION,
    }
