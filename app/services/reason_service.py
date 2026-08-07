from typing import List

class ReasonService:
    """
    추천 경로에 대한 추천 사유 생성
    """
    def generate_reason(self, route: dict, user_type: str) -> str:
        reasons: List[str] = []
        user_type_str = user_type.upper() if isinstance(user_type, str) else str(user_type).upper()
        access = route.get("accessibility", {})

        if route.get("transfer_count", 0) == 0:
            reasons.append("환승이 필요하지 않습니다.")
        elif route.get("transfer_count", 0) == 1:
            reasons.append("환승이 1회로 적은 편입니다.")

        if route.get("walking_distance", 0) <= 300:
            reasons.append("도보 이동 거리가 매우 짧습니다.")

        if access.get("elevator", False) and access.get("elevator_status") == "NORMAL":
            reasons.append("엘리베이터를 이용할 수 있습니다.")

        if "WHEELCHAIR" in user_type_str:
            reasons.append("휠체어 이용자를 고려하여 접근 가능한 경로를 선택했습니다.")
            if route.get("required_elevators", 0) <= 1:
                reasons.append("엘리베이터 이용 횟수가 적습니다.")

        unique_reasons = list(dict.fromkeys(reasons))
        return " ".join(unique_reasons)