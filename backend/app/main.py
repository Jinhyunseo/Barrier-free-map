from fastapi import FastAPI

from app.api.geocode import router as geocode_router
from app.api.route import router as route_router


app = FastAPI(
    title="Barrier-Free Navigation API",
    description="교통약자 맞춤형 경로 추천 서비스 백엔드",
    version="0.1.0",
)

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
