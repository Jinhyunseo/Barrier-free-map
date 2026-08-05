from fastapi import APIRouter, Depends
from app.schemas.request import RouteSearchRequest
from app.schemas.response import RouteSearchResponse
from app.services.geocode_service import GeocodeService
from app.services.recommendation_service import RecommendationService
from app.services.route_service import RouteService
from app.services.score_service import ScoreService

router = APIRouter(prefix="/route", tags=["Route Recommendation"])


@router.post("/recommend", response_model=RouteSearchResponse)
async def recommend_route(
    req: RouteSearchRequest,
    geocode_service: GeocodeService = Depends(),
    route_service: RouteService = Depends(),
    score_service: ScoreService = Depends(),
    recommendation_service: RecommendationService = Depends(),
):
    """
    [전체 동작 흐름 9단계 통합]
    1. 사용자 입력 (출발지, 목적지, 사용자 유형)
    2. 좌표 확인/변환
    3. 외부 카카오 대중교통 API 통해 15개 후보 경로 수집
    4. 경로 정보 추출 및 매핑
    5. 제약 조건 필터링
    6. 가중치 점수 계산
    7. 최적 경로 및 대안 경로 선정
    8. Gemini AI 기반 추천 이유 및 제외 사유 자연어 생성
    9. 결과 반환
    """
    # 후보 경로 수집
    candidate_routes = await route_service.fetch_candidate_routes(
        origin_lat=req.origin_lat,
        origin_lng=req.origin_lng,
        dest_lat=req.destination_lat,
        dest_lng=req.destination_lng,
    )

    # 경로 제약 필터링 및 점수 산출
    valid_routes, excluded_routes = score_service.process_routes(
        candidate_routes, user_type=req.user_type
    )

    # 최적 경로 및 대안 경로 분리
    optimal_route = valid_routes[0] if valid_routes else None
    alternative_routes = valid_routes[1:] if len(valid_routes) > 1 else []

    # Gemini 추천 이유 설명 생성
    ai_reason = await recommendation_service.generate_explanation(
        user_type=req.user_type,
        optimal_route=optimal_route,
        excluded_routes=excluded_routes,
    )

    return RouteSearchResponse(
        user_type=req.user_type,
        optimal_route=optimal_route,
        alternative_routes=alternative_routes,
        excluded_routes=excluded_routes,
        ai_recommendation_reason=ai_reason,
    )
