import os

import httpx
from dotenv import load_dotenv
from fastapi import HTTPException
from typing import Any


load_dotenv()

KAKAO_REST_API_KEY = os.getenv("KAKAO_REST_API_KEY")

KAKAO_TRANSIT_URL = "https://dapi.kakao.com/v2/local/search/keyword.json"


async def get_transit_routes(
    origin_x: float,
    origin_y: float,
    destination_x: float,
    destination_y: float,
) -> dict[str, Any]:
    if not KAKAO_REST_API_KEY:
        raise RuntimeError(
            "KAKAO_REST_API_KEY가 없습니다. backend/.env 파일을 확인하세요."
        )

    headers = {
        "Authorization": f"KakaoAK {KAKAO_REST_API_KEY}",
    }

    params = {
        "start_x": origin_x,
        "start_y": origin_y,
        "end_x": destination_x,
        "end_y": destination_y,
    }

    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.get(
                KAKAO_TRANSIT_URL,
                headers=headers,
                params=params,
            )

        response.raise_for_status()
        return response.json()

    except httpx.HTTPStatusError as exc:
        raise HTTPException(
            status_code=exc.response.status_code,
            detail={
                "message": "카카오 대중교통 API 호출에 실패했습니다.",
                "kakao_response": exc.response.text,
            },
        ) from exc

    except httpx.RequestError as exc:
        raise HTTPException(
            status_code=502,
            detail=f"카카오 API 서버에 연결하지 못했습니다: {str(exc)}",
        ) from exc

def simplify_routes(kakao_data: dict[str, Any]) -> dict[str, Any]:
    """
    카카오에서 받은 복잡한 경로 JSON을
    우리 서비스에서 사용하기 쉬운 형태로 바꿉니다.
    """

    simplified_routes = []

    # 카카오가 반환한 경로들을 하나씩 확인
    for route_number, route in enumerate(
        kakao_data.get("routes", []),
        start=1,
    ):
        route_properties = route.get("properties", {})

        vehicles = []
        stops = []
        path = []
        steps = []

        # 하나의 경로 안에 있는 이동 구간을 하나씩 확인
        for step_number, step in enumerate(
            route.get("steps", []),
            start=1,
        ):
            step_properties = step.get("properties", {})

            step_vehicles = []
            step_stops = []

            # 버스 번호 또는 지하철 노선 추출
            for vehicle in step_properties.get("vehicles", []):
                vehicle_data = {
                    "name": vehicle.get("name"),
                    "type": vehicle.get("type"),
                }

                step_vehicles.append(vehicle_data)

                # 경로 전체 노선 목록에는 중복 없이 추가
                if vehicle_data not in vehicles:
                    vehicles.append(vehicle_data)

            # 정류장 또는 역 이름 추출
            for stop in step_properties.get("stops", []):
                stop_name = stop.get("name")

                if stop_name:
                    step_stops.append(stop_name)

                    # 경로 전체 정류장 목록에는 중복 없이 추가
                    if stop_name not in stops:
                        stops.append(stop_name)

            # 지도에 경로선을 그릴 좌표 추출
            step_path = step.get("path", {}).get("points", [])
            path.extend(step_path)

            # 구간별 정보 저장
            steps.append(
                {
                    "step_id": step_number,
                    "step_type": step_properties.get("type"),
                    "guidance": step_properties.get("guidance"),
                    "distance": step_properties.get("distance"),
                    "time": step_properties.get("time"),
                    "vehicles": step_vehicles,
                    "stops": step_stops,
                    "path": step_path,
                }
            )

        # 경로 하나의 정보를 정리해서 저장
        simplified_routes.append(
            {
                "route_id": route_number,
                "route_type": route_properties.get("type"),
                "total_time_seconds": route_properties.get("totalTime"),
                "total_time_minutes": seconds_to_minutes(
                    route_properties.get("totalTime")
                ),
                "total_distance_meters": route_properties.get(
                    "totalDistance"
                ),
                "transfer_count": route_properties.get("transfers"),
                "fare": route_properties.get("fare", {}).get("value"),
                "vehicles": vehicles,
                "stops": stops,
                "steps": steps,
                "path": path,

                # 나중에 접근성 데이터를 붙일 공간
                "accessibility": {
                    "status": "UNKNOWN",
                    "has_broken_elevator": None,
                    "has_steep_slope": None,
                    "has_stairs": None,
                    "has_low_floor_bus": None,
                    "unavailable_reasons": [],
                },

                # 나중에 추천 알고리즘 결과를 붙일 공간
                "evaluation": {
                    "is_available": None,
                    "score": None,
                    "is_recommended": False,
                },

                # 나중에 AI가 생성할 추천 설명
                "recommendation_reason": None,
            }
        )

    original_properties = kakao_data.get("properties", {})

    return {
        "status": kakao_data.get("status"),
        "total": len(simplified_routes),
        "route_count": {
            "bus": original_properties.get("bus", 0),
            "subway": original_properties.get("subway", 0),
            "bus_and_subway": original_properties.get(
                "busAndSubway",
                0,
            ),
        },
        "routes": simplified_routes,
    }


def seconds_to_minutes(seconds: int | None) -> int | None:
    """
    초 단위 시간을 분 단위로 바꿉니다.
    1초라도 남으면 다음 분으로 올림 처리합니다.
    예: 1246초 → 21분
    """

    if seconds is None:
        return None

    return (seconds + 59) // 60