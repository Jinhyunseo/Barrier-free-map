from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.geocode import router as geocode_router
from app.api.route import router as route_router


app = FastAPI(
    title="Barrier-Free Navigation API",
    description="교통약자 맞춤형 경로 추천 서비스 백엔드",
    version="0.1.0",
)


# Flutter Web이 FastAPI에 요청할 수 있도록 허용
app.add_middleware(
    CORSMiddleware,

    # 개발 단계에서는 모든 주소의 요청을 허용
    allow_origins=["*"],

    # allow_origins=["*"]일 때는 False로 설정
    allow_credentials=False,

    # GET, POST 등 모든 HTTP 요청 방식 허용
    allow_methods=["*"],

    # 모든 요청 헤더 허용
    allow_headers=["*"],
)


# API 라우터 연결
app.include_router(route_router)
app.include_router(geocode_router)


@app.get("/")
async def root() -> dict[str, str]:
    return {
        "message": "Barrier-Free Navigation API is running!"
    }


@app.get("/health")
async def health_check() -> dict[str, str]:
    return {
        "status": "ok"
    }