from typing import Any
from fastapi import APIRouter, HTTPException, Depends

from app.schemas.route_schema import RouteByPlaceRequest, RouteCandidateRequest
from app.services.geocode_service import GeocodeService
from app.services.candidate_route_service import CandidateRouteService
from app.services.accessibility_service import AccessibilityService
from app.services.filter_service import FilterService
from app.services.scoring_service import ScoringService
from app.services.reason_service import ReasonService
from app.services.kakao_service import get_transit_routes, simplify_routes

router = APIRouter(prefix="/routes", tags=["Routes"])


@router.post("/candidates")
async def get_route_candidates(
    request: RouteCandidateRequest,
) -> dict[str, Any]:
    kakao_data = await get_transit_routes(
        origin_x=request.origin_x,
        origin_y=request.origin_y,
        destination_x=request.destination_x,
        destination_y=request.destination_y,
    )
    return simplify_routes(kakao_data)


@router.post("/recommend")
async def recommend_route_by_places(
    request: RouteByPlaceRequest,
    candidate_service: CandidateRouteService = Depends(),
    accessibility_service: AccessibilityService = Depends(),
    filter_service: FilterService = Depends(),
    scoring_service: ScoringService = Depends(),
    reason_service: ReasonService = Depends(),
    geocode_service: GeocodeService = Depends()
) -> dict[str, Any]:
    # 1. 출발지 지오코딩
    _, origin_results = await geocode_service.search_auto(request.origin_name)
    if not origin_results:
        raise HTTPException(status_code=404, detail=f"출발지를 찾을 수 없습니다: {request.origin_name}")

    # 2. 목적지 지오코딩
    _, destination_results = await geocode_service.search_auto(request.destination_name)
    if not destination_results:
        raise HTTPException(status_code=404, detail=f"목적지를 찾을 수 없습니다: {request.destination_name}")

    origin = origin_results[0]
    destination = destination_results[0]

    # LocationPoint 객체의 정확한 속성(longitude, latitude) 접근
    origin_x = getattr(origin, "longitude", 127.111)
    origin_y = getattr(origin, "latitude", 37.394)
    dest_x = getattr(destination, "longitude", 127.128)
    dest_y = getattr(destination, "latitude", 37.413)

    user_type_obj = getattr(request, "user_type", "WHEELCHAIR")
    user_type_val = user_type_obj.value if hasattr(user_type_obj, "value") else str(user_type_obj)

    try:
        # 3. 좌표 기반 후보 경로 동적 생성
        candidate_routes = await candidate_service.get_candidate_routes_from_kakao(
            origin_x=float(origin_x),
            origin_y=float(origin_y),
            destination_x=float(dest_x),
            destination_y=float(dest_y),
            start_name=request.origin_name,
            dest_name=request.destination_name
        )

        # 4. KRIC 역 편의시설 API 실시간 연동
        enriched_routes = await accessibility_service.enrich_routes(candidate_routes)

        # 5. 사용자 유형별 필터링
        filtered_routes = filter_service.filter_routes(enriched_routes, user_type_val)
        if not filtered_routes:
            raise HTTPException(
                status_code=400,
                detail=f"선택하신 사용자 유형({user_type_val})으로 이동 가능한 유효 경로가 없습니다."
            )

        # 6. 점수 계산
        scored_routes = scoring_service.calculate_scores(filtered_routes, user_type_val)

        # 7. 최적 경로 선택
        best_route = max(scored_routes, key=lambda x: x.get("score", 0))

        # 8. 추천 사유 작성
        best_route["reason"] = reason_service.generate_reason(best_route, user_type_val)

        origin_dict = origin.model_dump() if hasattr(origin, 'model_dump') else origin.dict()
        dest_dict = destination.model_dump() if hasattr(destination, 'model_dump') else destination.dict()

        return {
            "origin": origin_dict,
            "destination": dest_dict,
            "recommended_route": best_route,        # 1순위 최적 추천 경로
            "all_candidate_routes": scored_routes   # 전체 후보 경로 목록 (버스, 지하철, 혼합)
        }

    except HTTPException:
        raise
    except Exception as e:
        print(f"[Recommend Error] {e}")
        raise HTTPException(status_code=500, detail="경로 추천 처리 중 오류가 발생했습니다.")