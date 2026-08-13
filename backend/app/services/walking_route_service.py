import os
from typing import Any
from urllib.parse import quote

import httpx
from dotenv import load_dotenv
from fastapi import HTTPException

load_dotenv()

TMAP_APP_KEY = os.getenv("TMAP_APP_KEY", "").strip()

TMAP_WALKING_URL = (
    "https://apis.openapi.sk.com/tmap/routes/pedestrian"
)


async def get_walking_route(
    start_x: float,
    start_y: float,
    end_x: float,
    end_y: float,
    start_name: str = "출발지",
    end_name: str = "도착지",
    avoid_stairs: bool = False,
) -> dict[str, Any]:

    if not TMAP_APP_KEY:
        raise RuntimeError(
            "TMAP_APP_KEY가 없습니다. .env 파일을 확인하세요."
        )

    # 계단 회피가 필요한 경우 TMAP의 계단 제외 옵션 사용
    search_option = "30" if avoid_stairs else "0"

    headers = {
        "appKey": TMAP_APP_KEY,
        "Content-Type": "application/json",
    }

    payload = {
        "startX": str(start_x),
        "startY": str(start_y),
        "endX": str(end_x),
        "endY": str(end_y),
        "startName": quote(start_name),
        "endName": quote(end_name),
        "reqCoordType": "WGS84GEO",
        "resCoordType": "WGS84GEO",
        "searchOption": search_option,
    }

    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.post(
                TMAP_WALKING_URL,
                params={"version": "1"},
                headers=headers,
                json=payload,
            )

        response.raise_for_status()

        raw_data = response.json()

        return simplify_walking_route(raw_data)

    except httpx.HTTPStatusError as exc:
        raise HTTPException(
            status_code=exc.response.status_code,
            detail={
                "message": "TMAP 보행 경로 API 호출 실패",
                "tmap_response": exc.response.text,
            },
        ) from exc

    except httpx.RequestError as exc:
        raise HTTPException(
            status_code=502,
            detail=f"TMAP API 서버 연결 실패: {exc}",
        ) from exc


def simplify_walking_route(
    data: dict[str, Any],
) -> dict[str, Any]:

    features = data.get("features", [])

    if not features:
        raise HTTPException(
            status_code=502,
            detail="TMAP 보행 경로 결과가 없습니다.",
        )

    total_distance = 0
    total_time = 0

    path_coordinates = []
    instructions = []
    segments = []

    # 첫 Point에 전체 거리/시간이 들어 있음
    first_properties = features[0].get("properties", {})

    total_distance = first_properties.get(
        "totalDistance",
        0,
    )

    total_time = first_properties.get(
        "totalTime",
        0,
    )

    for feature in features:

        geometry = feature.get("geometry", {})
        properties = feature.get("properties", {})

        geometry_type = geometry.get("type")

        # 실제 지도에 그릴 보행 경로
        if geometry_type == "LineString":

            coordinates = geometry.get(
                "coordinates",
                [],
            )

            path_coordinates.extend(coordinates)

            segments.append(
                {
                    "distance_meters": properties.get(
                        "distance",
                        0,
                    ),
                    "duration_seconds": properties.get(
                        "time",
                        0,
                    ),
                    "road_name": properties.get(
                        "name",
                        "",
                    ),
                    "description": properties.get(
                        "description",
                        "",
                    ),
                    "road_type": properties.get(
                        "roadType",
                    ),
                    "facility_type": properties.get(
                        "facilityType",
                    ),
                    "coordinates": coordinates,
                }
            )

        # 좌회전 / 직진 / 육교 진입 등의 안내
        elif geometry_type == "Point":

            description = properties.get(
                "description",
                "",
            )

            if description:
                instructions.append(
                    {
                        "description": description,
                        "turn_type": properties.get(
                            "turnType",
                        ),
                        "point_type": properties.get(
                            "pointType",
                        ),
                        "intersection_name": properties.get(
                            "intersectionName",
                            "",
                        ),
                        "coordinate": geometry.get(
                            "coordinates",
                            [],
                        ),
                    }
                )

    return {
        "type": "WALK",
        "total_distance_meters": total_distance,
        "total_duration_seconds": total_time,
        "total_duration_minutes": round(
            total_time / 60,
            1,
        ),
        "path": path_coordinates,
        "instructions": instructions,
        "segments": segments,
    }