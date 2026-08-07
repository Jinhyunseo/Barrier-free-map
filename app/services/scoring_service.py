# app/services/scoring_service.py
from typing import List, Dict, Any

class ScoringService:
    """
    팀 정의 비용(Cost) 함수 및 가중치(Weights) 기반 경로 점수 계산 서비스
    """
    
    # 사용자 유형별 가중치(Weights) 정의
    USER_WEIGHTS: Dict[str, Dict[str, float]] = {
        # 휠체어 이용자: 보행 거리, 환승 패널티가 크고 엘리베이터/저상버스 보너스 비중이 큼
        "WHEELCHAIR": {
            "time_per_min": 1.0,
            "walk_dist_per_m": 0.05,
            "transfer_penalty": 15.0,
            "elevator_bonus": -15.0,   # 엘리베이터 이용 시 비용 15 차감
            "low_bus_bonus": -10.0     # 저상버스 이용 시 비용 10 차감
        },
        # 고령자: 환승 및 보행 부담 감점, 엘리베이터 선호
        "ELDER": {
            "time_per_min": 1.0,
            "walk_dist_per_m": 0.03,
            "transfer_penalty": 10.0,
            "elevator_bonus": -10.0,
            "low_bus_bonus": -5.0
        },
        # 일반 교통약자 / 기본값
        "DEFAULT": {
            "time_per_min": 1.0,
            "walk_dist_per_m": 0.02,
            "transfer_penalty": 8.0,
            "elevator_bonus": -8.0,
            "low_bus_bonus": -5.0
        }
    }

    def _calculate_edge_cost(self, edge: Dict[str, Any], weights: Dict[str, float]) -> float:
        """
        조원님이 정의하신 비용(Cost) 산출 함수
        """
        cost = 0.0
        
        # 1. 기본 소요 시간 및 보행 거리 비용 계산
        cost += edge.get('travel_time_min', 0) * weights['time_per_min']
        cost += edge.get('walk_distance_m', 0) * weights['walk_dist_per_m']
        
        # 2. 특수 조건에 따른 패널티(+) 및 보너스(-) 적용
        if edge.get('is_transfer', False):
            cost += weights['transfer_penalty']     # 환승 부담 패널티 추가
            
        if edge.get('has_elevator', False):
            cost += weights['elevator_bonus']       # 엘리베이터 보너스 (비용 차감)
            
        if edge.get('is_low_floor_bus', False):
            cost += weights['low_bus_bonus']        # 저상버스 보너스 (비용 차감)
            
        # 비용이 0 이하로 떨어지는 것을 방지 (최소 0.1 비용 보장)
        return max(cost, 0.1)

    def calculate_scores(self, routes: List[Dict[str, Any]], user_type: str) -> List[Dict[str, Any]]:
        user_type_str = user_type.upper() if isinstance(user_type, str) else str(user_type).upper()
        
        # 사용자 유형에 맞는 가중치 선택
        if "WHEELCHAIR" in user_type_str:
            weights = self.USER_WEIGHTS["WHEELCHAIR"]
        elif "ELDER" in user_type_str:
            weights = self.USER_WEIGHTS["ELDER"]
        else:
            weights = self.USER_WEIGHTS["DEFAULT"]

        for route in routes:
            access = route.get("accessibility", {})
            
            # 경로 데이터를 조원님의 edge 딕셔너리 포맷에 매핑
            edge = {
                "travel_time_min": route.get("travel_time", 0),
                "walk_distance_m": route.get("walking_distance", 0),
                "is_transfer": route.get("transfer_count", 0) > 0,
                "has_elevator": access.get("elevator", False),
                "is_low_floor_bus": access.get("low_floor_bus", False)
            }
            
            # 1. 조원님 함수로 비용(Cost) 산출
            cost = self._calculate_edge_cost(edge, weights)
            route["cost"] = round(cost, 2)
            
            # 2. 비용(Cost)을 점수(Score)로 변환 (비용이 적을수록 점수가 높음)
            # 기준 최고점(120점)에서 비용을 차감
            final_score = 120.0 - cost
            route["score"] = round(max(0.0, final_score), 2)

        return routes