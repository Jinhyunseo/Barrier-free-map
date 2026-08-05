import os
import sys

# 프로젝트 루트 경로를 sys.path에 추가하여 모듈 참조 오류 해결
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.router import api_router
from app.core.config import settings
from app.core.database import Base, engine
import app.models  # ORM 모델 등록


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 앱 시작 시 DB 테이블 자동 생성 (개발/프로토타입 환경용)
    Base.metadata.create_all(bind=engine)
    print(f"[{settings.PROJECT_NAME}] Database tables initialized.")
    yield
    print(f"[{settings.PROJECT_NAME}] Shutting down backend...")


app = FastAPI(
    title=settings.PROJECT_NAME,
    description="교통약자 모빌리티 최적 경로 추천 및 AI 설명 백엔드 API",
    version=settings.VERSION,
    lifespan=lifespan,
)

# CORS 미들웨어 등록
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API v1 라우터 연결
app.include_router(api_router)


@app.get("/", tags=["Root"])
async def root():
    return {
        "status": "online",
        "service": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "docs_url": "/docs",
    }


@app.get("/health", tags=["Health Check"])
async def health_check():
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
