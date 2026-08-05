from typing import List, Optional
import httpx
from app.core.config import settings
from app.schemas.response import ExcludedRouteInfo, RouteDetail


class RecommendationService:
    """Gemini API를 호출하여 최적 경로 추천 이유 및 제외 사유 설명 자연어 생성 서비스"""

    def __init__(self):
        self.gemini_api_key = settings.GEMINI_API_KEY

    async def generate_explanation(
        self,
        user_type: str,
        optimal_route: Optional[RouteDetail],
        excluded_routes: List[ExcludedRouteInfo],
    ) -> str:
        if not optimal_route:
            return "현재 조건에서 이용 가능한 안전한 경로를 찾지 못했습니다. 출발지와 목적지를 확인해 주세요."

        user_type_desc = {
            "WHEELCHAIR": "휠체어 이용자",
            "ELDERLY": "노약자",
            "STROLLER": "유모차 동반자",
            "GENERAL": "일반 사용자",
        }.get(user_type.upper(), user_type)

        prompt = (
            f"사용자 유형: {user_type_desc}\n"
            f"선정된 최적 경로: 소요시간 {optimal_route.total_duration_minutes}분, "
            f"도보 거리 {optimal_route.total_walk_distance_meters}m, 환승 {optimal_route.transfer_count}회.\n"
            f"제외된 경로 및 사유: {', '.join([f'{r.route_id}({r.exclusion_reason})' for r in excluded_routes])}\n\n"
            f"위 정보를 바탕으로 사용자에게 최적 경로를 추천하는 친절하고 자애로운 설명 문장 2~3줄을 작성해 주세요."
        )

        # Gemini API 키가 설정되어 있는 경우 비동기 HTTP 호출
        if self.gemini_api_key:
            try:
                url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={self.gemini_api_key}"
                payload = {"contents": [{"parts": [{"text": prompt}]}]}
                async with httpx.AsyncClient() as client:
                    resp = await client.post(url, json=payload, timeout=10.0)
                    if resp.status_code == 200:
                        data = resp.json()
                        candidates = data.get("candidates", [])
                        if candidates:
                            parts = candidates[0].get("content", {}).get("parts", [])
                            if parts:
                                return parts[0].get("text", "").strip()
            except Exception as e:
                print(f"Gemini API 호출 중 예외 발생: {e}")

        # 기본 생성 문구 (Mock 데이터)
        return (
            f"{user_type_desc}를 위해 이동 편의성이 보장된 최적 경로를 추천합니다. "
            f"승강기 고장 구간 및 긴 계단 통과 구간을 제외하여 "
            f"소요시간 {optimal_route.total_duration_minutes}분 만에 안전하게 이동하실 수 있습니다."
        )
