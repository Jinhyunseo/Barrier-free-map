from typing import Any

from fastapi import APIRouter, HTTPException

from app.schemas.route_schema import (
    RouteByPlaceRequest,
    RouteCandidateRequest,
)
from app.services.geocode_service import GeocodeService
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
    """
    출발지와 목적지의 좌표를 직접 입력받아
    카카오 대중교통 후보 경로를 반환합니다.
    """

    kakao_data = await get_transit_routes(
        origin_x=request.origin_x,
        origin_y=request.origin_y,
        destination_x=request.destination_x,
        destination_y=request.destination_y,
    )

    return simplify_routes(kakao_data)


@router.post("/by-places")
async def get_routes_by_places(
    request: RouteByPlaceRequest,
) -> dict[str, Any]:
    """
    출발지·목적지 장소명과 사용자 유형을 입력받아
    장소를 좌표로 변환한 뒤 후보 경로를 반환합니다.

    현재 단계에서는 사용자 유형을 함께 받아 반환만 하며,
    이후 사용자 맞춤형 추천 알고리즘에 전달할 예정입니다.
    """

    geocode_service = GeocodeService()

    # 1. 출발지 장소명 검색
    _, origin_results = await geocode_service.search_auto(
        request.origin_name
    )

    if not origin_results:
        raise HTTPException(
            status_code=404,
            detail=f"출발지를 찾을 수 없습니다: {request.origin_name}",
        )

    # 2. 목적지 장소명 검색
    _, destination_results = await geocode_service.search_auto(
        request.destination_name
    )

    if not destination_results:
        raise HTTPException(
            status_code=404,
            detail=f"목적지를 찾을 수 없습니다: {request.destination_name}",
        )

    # 현재는 각 검색 결과의 첫 번째 장소를 사용
    origin = origin_results[0]
    destination = destination_results[0]

    # 3. 좌표를 이용해 카카오 후보 경로 조회
    kakao_data = await get_transit_routes(
        origin_x=origin.longitude,
        origin_y=origin.latitude,
        destination_x=destination.longitude,
        destination_y=destination.latitude,
    )

    # 4. 복잡한 카카오 응답을 우리 서비스 형식으로 정리
    routes = simplify_routes(kakao_data)

    # 5. 출발지·목적지·사용자 유형과 후보 경로 반환
    return {
        "origin": origin.model_dump(),
        "destination": destination.model_dump(),
        "user_type": request.user_type,
        **routes,
    }