from typing import List

class FilterService:
    """
    사용자 유형(WHEELCHAIR 등)에 따라 이용 불가능한 경로 제거
    """
    def filter_routes(self, routes: List[dict], user_type: str) -> List[dict]:
        result = []
        user_type_str = user_type.upper() if isinstance(user_type, str) else str(user_type).upper()

        for route in routes:
            access = route.get("accessibility", {})

            if "WHEELCHAIR" in user_type_str:
                if access.get("stairs", False) or not access.get("wheelchair_possible", False):
                    continue
                if access.get("elevator", False) and access.get("elevator_status") != "NORMAL":
                    continue

            elif "ELDER" in user_type_str:
                if access.get("elevator", False) and access.get("elevator_status") == "MAINTENANCE":
                    continue

            elif "BLIND" in user_type_str:
                if not access.get("voice_guidance", False):
                    continue

            result.append(route)
        return result