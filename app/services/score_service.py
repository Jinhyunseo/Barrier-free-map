from typing import List, Tuple
from app.schemas.response import ExcludedRouteInfo, RouteDetail
from app.utils.calculator import calculate_route_score


class ScoreService:
    """경로 필터링 (제약조건 적용) 및 점수 계산, 최적/대안 경로 분류 서비스"""

    def process_routes(
        self, routes: List[RouteDetail], user_type: str
    ) -> Tuple[List[RouteDetail], List[ExcludedRouteInfo]]:
        valid_routes: List[RouteDetail] = []
        excluded_routes: List[ExcludedRouteInfo] = []

        for route in routes:
            filter_reason = None

            # 휠체어 이용자 제약조건 검사
            if user_type.upper() == "WHEELCHAIR":
                for seg in route.segments:
                    if not seg.is_accessible:
                        filter_reason = f"이용 불가 구간 포함 ({', '.join(seg.accessibility_issues)})"
                        break

            if filter_reason:
                route.is_filtered_out = True
                route.filter_reason = filter_reason
                excluded_routes.append(
                    ExcludedRouteInfo(
                        route_id=route.route_id,
                        summary=f"소요시간: {route.total_duration_minutes}분, 환승: {route.transfer_count}회",
                        exclusion_reason=filter_reason,
                    )
                )
            else:
                # 점수 계산
                elevator_count = sum(
                    1 for s in route.segments if s.mode == "SUBWAY"
                )
                score = calculate_route_score(
                    duration_minutes=route.total_duration_minutes,
                    walk_distance_meters=route.total_walk_distance_meters,
                    transfer_count=route.transfer_count,
                    elevator_count=elevator_count,
                )
                route.total_score = score
                valid_routes.append(route)

        # 점수가 가장 낮은 순서로 정렬 (점수가 작을수록 최적)
        valid_routes.sort(key=lambda r: r.total_score)

        return valid_routes, excluded_routes
