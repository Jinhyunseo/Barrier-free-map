from typing import Any

from fastapi import APIRouter

from app.schemas.route_schema import RouteCandidateRequest
from app.services.kakao_service import (
    get_transit_routes,
    simplify_routes,
)


router = APIRouter(
    prefix="/routes",
    tags=["Routes"],
)


@router.post("/candidates")
async def get_route_candidates(
    request: RouteCandidateRequest,
) -> dict[str, Any]:
    # 1. 카카오에서 원본 후보 경로를 받아오기
    kakao_data = await get_transit_routes(
        origin_x=request.origin_x,
        origin_y=request.origin_y,
        destination_x=request.destination_x,
        destination_y=request.destination_y,
    )

    # 2. 복잡한 원본 JSON을 간단한 형태로 바꿔서 반환
    return simplify_routes(kakao_data)

