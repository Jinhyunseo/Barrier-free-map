from typing import Dict, Any


def calculate_route_score(
    duration_minutes: int,
    walk_distance_meters: int,
    transfer_count: int,
    elevator_count: int,
    slope_penalty: float = 0.0,
    stair_penalty: float = 0.0,
    uncertainty_penalty: float = 0.0,
    weights: Dict[str, float] = None,
) -> float:
    """
    설계도 명세 기반 경로 점수 산출 공식:
    경로 점수 = (이동시간(분) × 시간 가중치)
                + (보행거리(m) × 보행 가중치)
                + (환승 횟수 × 환승 가중치)
                + (승강기 이용 횟수 × 승강기 가중치)
                + 경사 패널티 + 계단 패널티 + 접근성 불확실성 패널티

    ※ 점수가 낮을수록 최적의 경로입니다.
    """
    if weights is None:
        weights = {
            "time": 1.0,
            "walk": 0.05,
            "transfer": 10.0,
            "elevator": -2.0,  # 휠체어/노약자는 승강기가 있으면 점수 차감(선호)
        }

    score = (
        (duration_minutes * weights.get("time", 1.0))
        + (walk_distance_meters * weights.get("walk", 0.05))
        + (transfer_count * weights.get("transfer", 10.0))
        + (elevator_count * weights.get("elevator", -2.0))
        + slope_penalty
        + stair_penalty
        + uncertainty_penalty
    )

    return round(score, 2)
