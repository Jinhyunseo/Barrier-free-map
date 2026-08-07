# app/services/accessibility_service.py
from typing import List, Dict, Any
from app.services.kric_station_service import KricStationService

class AccessibilityService:
    """
    후보 경로 목록에 KRIC API 역 편의시설 실시간 데이터를 주입하는 서비스
    """
    def __init__(self):
        self.kric_service = KricStationService()

    async def enrich_routes(self, routes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        enriched_list = []

        for route in routes:
            r = dict(route)
            transport_type = r.get("transport_type", "BUS")
            start_name = r.get("start", "")
            dest_name = r.get("destination", "")
            route_name = r.get("name", "")

            # 검색 대상 문구 합성 (출발지 + 목적지 + 경로명)
            search_text = f"{start_name} {dest_name} {route_name}"

            # 기본 접근성 정보
            access = {
                "stairs": False,
                "elevator": True,
                "elevator_status": "NORMAL",
                "low_floor_bus": True,
                "wheelchair_possible": True,
                "visual_guidance": True,
                "voice_guidance": True,
                "elevator_location": "버스 전용 경로 (지하철 승강기 해당 없음)",
                "movement_path": "도보 및 저상버스 이동 동선"
            }

            # 지하철이 포함된 경로(SUBWAY, MIXED)의 경우 KRIC 역 편의시설 API 연동
            if transport_type in ["SUBWAY", "MIXED"]:
                kric_info = await self.kric_service.get_station_accessibility(route_name)
                
                access["elevator"] = kric_info.get("has_elevator", True)
                access["elevator_status"] = kric_info.get("elevator_status", "NORMAL")
                access["wheelchair_possible"] = kric_info.get("wheelchair_possible", True)
                access["voice_guidance"] = kric_info.get("has_voice_guidance", True)
                access["stairs"] = not kric_info.get("has_elevator", True)

                # 승강기 위치 및 이동 경로 정보 반영
                access["elevator_location"] = kric_info.get("elevator_location", "역 내 승강기 위치 정보 확인 필요")
                access["movement_path"] = kric_info.get("movement_path", "엘리베이터 동선 이용 가능")

            r["accessibility"] = access
            enriched_list.append(r)

        return enriched_list