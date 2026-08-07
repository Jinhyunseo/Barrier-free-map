import math
from typing import List, Dict, Any

class CandidateRouteService:
    """
    출발지와 목적지의 위도/경도 좌표를 기반으로 
    실제 이동 거리를 계산하여 동적 후보 경로 목록을 생성하는 서비스
    """

    def _haversine_distance(self, lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """두 위도/경도 좌표 간의 실제 거리(km) 계산"""
        R = 6371.0  # 지구 반지름 (km)
        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)

        a = (math.sin(dlat / 2) ** 2 +
             math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
             math.sin(dlon / 2) ** 2)
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        return R * c

    async def get_candidate_routes_from_kakao(
        self, 
        origin_x: float, 
        origin_y: float, 
        destination_x: float, 
        destination_y: float,
        start_name: str,
        dest_name: str
    ) -> List[Dict[str, Any]]:
        
        # 1. 두 지점 간의 실제 좌표 거리 계산 (km)
        direct_dist_km = self._haversine_distance(origin_y, origin_x, destination_y, destination_x)
        
        # 실제 대중교통 우회 거리 보정 (직선거리의 약 1.35배)
        approx_road_dist_km = round(max(0.8, direct_dist_km * 1.35), 2)
        
        # 2. 이동 거리에 비례한 예상 소요 시간 및 도보 거리 계산
        base_time = int(approx_road_dist_km * 4.5) + 6  # 소요 시간(분)
        base_walk = int(min(approx_road_dist_km * 110, 900))  # 도보 거리(m)

        # 3. 출발지/목적지 좌표에 따라 다이내믹하게 변하는 3가지 후보 경로 생성
        candidate_list = [
            {
                "id": 1,
                "name": f"{start_name} → {dest_name} 버스 경로",
                "start": start_name,
                "destination": dest_name,
                "distance": approx_road_dist_km,
                "walking_distance": int(base_walk * 0.7),
                "travel_time": base_time,
                "transfer_count": 0 if approx_road_dist_km < 3.5 else 1,
                "required_elevators": 0,
                "transport_type": "BUS"
            },
            {
                "id": 2,
                "name": f"{start_name} → {dest_name} 지하철 경로",
                "start": start_name,
                "destination": dest_name,
                "distance": round(approx_road_dist_km * 1.1, 2),
                "walking_distance": int(base_walk * 1.2),
                "travel_time": max(10, int(base_time * 0.8)),
                "transfer_count": 1 if approx_road_dist_km < 5.5 else 2,
                "required_elevators": 2,
                "transport_type": "SUBWAY"
            },
            {
                "id": 3,
                "name": f"{start_name} → {dest_name} 혼합 경로",
                "start": start_name,
                "destination": dest_name,
                "distance": round(approx_road_dist_km * 1.05, 2),
                "walking_distance": base_walk,
                "travel_time": int(base_time * 0.9),
                "transfer_count": 1,
                "required_elevators": 1,
                "transport_type": "MIXED"
            }
        ]

        return candidate_list