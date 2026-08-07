from typing import Dict, Any, List
from app.services.candidate_route_service import CandidateRouteService
from app.services.accessibility_service import AccessibilityService
from app.services.filter_service import FilterService
from app.services.scoring_service import ScoringService
from app.services.reason_service import ReasonService


class RecommendService:
    def __init__(self):
        self.candidate_service = CandidateRouteService()
        self.accessibility_service = AccessibilityService()
        self.filter_service = FilterService()
        self.scoring_service = ScoringService()
        self.reason_service = ReasonService()

    async def recommend_best_route(
        self,
        start: str,
        destination: str,
        origin_x: float,
        origin_y: float,
        destination_x: float,
        destination_y: float,
        user_type: Any = "WHEELCHAIR"
    ) -> Dict[str, Any]:
        
        # user_type 값 추출 (Enum 또는 문자열 대응)
        user_type_val = user_type.value if hasattr(user_type, "value") else str(user_type)

        # 1. 좌표 기반 후보 경로 동적 조회 (비동기)
        candidates = await self.candidate_service.get_candidate_routes_from_kakao(
            origin_x=origin_x,
            origin_y=origin_y,
            destination_x=destination_x,
            destination_y=destination_y,
            start_name=start,
            dest_name=destination
        )

        # 2. KRIC API 기반 역 이동경로 및 승강기 위치 정보 연동
        enriched_routes = await self.accessibility_service.enrich_routes(candidates)

        # 3. 휠체어/교통약자 필터링
        filtered_routes = self.filter_service.filter_routes(enriched_routes, user_type_val)

        if not filtered_routes:
            raise ValueError(f"선택하신 사용자 유형({user_type_val})으로 이동 가능한 경로가 없습니다.")

        # 4. 점수 계산
        scored_routes = self.scoring_service.calculate_scores(filtered_routes, user_type_val)

        # 5. 최적 경로 1개 선택 (딕셔너리 키 접근)
        best_route = max(scored_routes, key=lambda r: r.get("score", 0) if isinstance(r, dict) else getattr(r, 'score', 0))

        # 6. 추천 사유 생성 및 추가
        best_route["reason"] = self.reason_service.generate_reason(best_route, user_type_val)

        return best_route