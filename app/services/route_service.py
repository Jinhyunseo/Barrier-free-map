from typing import List
from app.schemas.response import RouteDetail, RouteSegment


class RouteService:
    """카카오 대중교통 경로 API 호출 및 15개 후보 경로 조회/파싱 서비스"""

    async def fetch_candidate_routes(
        self,
        origin_lat: float,
        origin_lng: float,
        dest_lat: float,
        dest_lng: float,
    ) -> List[RouteDetail]:
        """
        카카오 대중교통 API를 호출하여 후보 경로(최대 15개) 수집 및 정규화
        (프로토타입 가동을 위해 핵심 세그먼트 데이터 생성 모의 로직 제공)
        """
        candidate_routes = []

        # 후보 경로 1: 지하철 중심 (승강기 이용 가능)
        candidate_routes.append(
            RouteDetail(
                route_id="route_1",
                total_duration_minutes=35,
                total_walk_distance_meters=300,
                transfer_count=1,
                total_score=0.0,
                segments=[
                    RouteSegment(
                        mode="SUBWAY",
                        route_name="2호선",
                        start_station="강남역",
                        end_station="교대역",
                        duration_minutes=5,
                        distance_meters=1200,
                    ),
                    RouteSegment(
                        mode="SUBWAY",
                        route_name="3호선",
                        start_station="교대역",
                        end_station="고속터미널역",
                        duration_minutes=10,
                        distance_meters=2500,
                    ),
                    RouteSegment(
                        mode="WALK",
                        start_station="고속터미널역",
                        end_station="목적지",
                        duration_minutes=5,
                        distance_meters=300,
                    ),
                ],
            )
        )

        # 후보 경로 2: 버스 노선 포함 (계단 경유 또는 저상버스 여부 체크 대상)
        candidate_routes.append(
            RouteDetail(
                route_id="route_2",
                total_duration_minutes=40,
                total_walk_distance_meters=450,
                transfer_count=0,
                total_score=0.0,
                segments=[
                    RouteSegment(
                        mode="BUS",
                        route_name="146번",
                        start_station="강남역정류장",
                        end_station="고속터미널정류장",
                        duration_minutes=30,
                        distance_meters=4000,
                        is_accessible=True,
                    ),
                    RouteSegment(
                        mode="WALK",
                        start_station="고속터미널정류장",
                        end_station="목적지",
                        duration_minutes=10,
                        distance_meters=450,
                    ),
                ],
            )
        )

        # 후보 경로 3: 계단만 통과 가능하거나 승강기 고장 구간 포함 경로 (필터링 테스트용)
        candidate_routes.append(
            RouteDetail(
                route_id="route_3",
                total_duration_minutes=25,
                total_walk_distance_meters=600,
                transfer_count=1,
                total_score=0.0,
                segments=[
                    RouteSegment(
                        mode="SUBWAY",
                        route_name="9호선",
                        start_station="신논현역",
                        end_station="고속터미널역",
                        duration_minutes=15,
                        distance_meters=3000,
                        is_accessible=False,
                        accessibility_issues=["승강기 고장/점검 중"],
                    ),
                    RouteSegment(
                        mode="WALK",
                        start_station="고속터미널역",
                        end_station="목적지",
                        duration_minutes=10,
                        distance_meters=600,
                        accessibility_issues=["긴 계단 구간 통과 필요"],
                    ),
                ],
            )
        )

        return candidate_routes
