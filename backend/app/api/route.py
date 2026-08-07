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
from app.services.movement_extraction_service import (
    attach_station_movements,
)
from app.services.recommendation_service import (
    select_best_candidate,
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
    출발지와 목적지 좌표를 직접 입력받아
    카카오 후보 경로 전체를 반환합니다.
    """

    try:
        kakao_data = await get_transit_routes(
            origin_x=request.origin_x,
            origin_y=request.origin_y,
            destination_x=request.destination_x,
            destination_y=request.destination_y,
        )

        return simplify_routes(kakao_data)

    except Exception as error:
        raise HTTPException(
            status_code=502,
            detail=f"카카오 후보 경로 조회 중 오류가 발생했습니다: {error}",
        ) from error


@router.post("/by-places")
async def get_routes_by_places(
    request: RouteByPlaceRequest,
) -> dict[str, Any]:
    """
    출발지·목적지 장소명을 좌표로 변환한 뒤
    카카오 후보 경로 전체를 반환합니다.

    후보 경로별 승차·환승·하차 정보도
    station_movements 필드에 추가합니다.
    """

    geocode_service = GeocodeService()

    # 1. 출발지 검색
    _, origin_results = await geocode_service.search_auto(
        request.origin_name
    )

    if not origin_results:
        raise HTTPException(
            status_code=404,
            detail=(
                "출발지를 찾을 수 없습니다: "
                f"{request.origin_name}"
            ),
        )

    # 2. 목적지 검색
    _, destination_results = await geocode_service.search_auto(
        request.destination_name
    )

    if not destination_results:
        raise HTTPException(
            status_code=404,
            detail=(
                "목적지를 찾을 수 없습니다: "
                f"{request.destination_name}"
            ),
        )

    # 현재는 검색 결과 중 첫 번째 장소를 사용
    origin = origin_results[0]
    destination = destination_results[0]

    # 3. 카카오 후보 경로 조회
    try:
        kakao_data = await get_transit_routes(
            origin_x=origin.longitude,
            origin_y=origin.latitude,
            destination_x=destination.longitude,
            destination_y=destination.latitude,
        )
    except Exception as error:
        raise HTTPException(
            status_code=502,
            detail=f"카카오 후보 경로 조회 중 오류가 발생했습니다: {error}",
        ) from error

    # 4. 카카오 응답 단순화
    simplified_data = simplify_routes(kakao_data)
    routes = simplified_data.get("routes", [])

    if not routes:
        raise HTTPException(
            status_code=404,
            detail="조회된 후보 경로가 없습니다.",
        )

    # 5. 후보 경로별 승차·환승·하차 정보 추출
    routes = attach_station_movements(routes)

    # 6. 후보 경로 전체 반환
    return {
        "origin": origin.model_dump(),
        "destination": destination.model_dump(),
        "user_type": request.user_type,
        **simplified_data,
        "routes": routes,
    }


@router.post("/recommend")
async def get_recommended_route(
    request: RouteByPlaceRequest,
) -> dict[str, Any]:
    """
    출발지·목적지·사용자 유형을 입력받아
    사용자에게 가장 적합한 경로를 추천합니다.

    처리 과정:
    1. 장소명을 좌표로 변환
    2. 카카오 후보 경로 조회
    3. 후보 경로 단순화
    4. 승차·환승·하차 정보 추출
    5. 사용자 유형별 후보 경로 평가
    6. 최적 경로 선택
    """

    geocode_service = GeocodeService()

    # 1. 출발지 검색
    _, origin_results = await geocode_service.search_auto(
        request.origin_name
    )

    if not origin_results:
        raise HTTPException(
            status_code=404,
            detail=(
                "출발지를 찾을 수 없습니다: "
                f"{request.origin_name}"
            ),
        )

    # 2. 목적지 검색
    _, destination_results = await geocode_service.search_auto(
        request.destination_name
    )

    if not destination_results:
        raise HTTPException(
            status_code=404,
            detail=(
                "목적지를 찾을 수 없습니다: "
                f"{request.destination_name}"
            ),
        )

    origin = origin_results[0]
    destination = destination_results[0]

    # 3. 카카오 후보 경로 조회
    try:
        kakao_data = await get_transit_routes(
            origin_x=origin.longitude,
            origin_y=origin.latitude,
            destination_x=destination.longitude,
            destination_y=destination.latitude,
        )
    except Exception as error:
        raise HTTPException(
            status_code=502,
            detail=f"카카오 후보 경로 조회 중 오류가 발생했습니다: {error}",
        ) from error

    # 4. 카카오 응답 단순화
    simplified_data = simplify_routes(kakao_data)
    routes = simplified_data.get("routes", [])

    if not routes:
        raise HTTPException(
            status_code=404,
            detail="조회된 후보 경로가 없습니다.",
        )

    # 5. 각 후보 경로에서 승차역·환승역·하차역 추출
    routes = attach_station_movements(routes)

    # ----------------------------------------------------------
    # 추후 역사 내부 시설 데이터 연결 위치
    #
    # 예:
    #
    # routes = await attach_required_station_facilities(routes)
    #
    # 위 함수에서 station_movements를 이용해
    # 실제 필요한 엘리베이터·에스컬레이터·계단을 찾고,
    # 각 route의 accessibility에 데이터를 추가하게 됩니다.
    # ----------------------------------------------------------

    # 6. 사용자 유형별 최적 경로 선택
    try:
        recommendation_result = select_best_candidate(
            routes=routes,
            user_type=request.user_type,
        )
    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail=str(error),
        ) from error
    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=f"추천 경로 계산 중 오류가 발생했습니다: {error}",
        ) from error

    # 7. 추천 결과 반환
    return {
        "origin": origin.model_dump(),
        "destination": destination.model_dump(),
        **recommendation_result,
    }