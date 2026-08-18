import json
import math
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

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
GEOJSON_PATH = os.path.join(DATA_DIR, "성남시_보행망.geojson")


def load_seongnam_walking_network():
    """성남시 보행망 GeoJSON 데이터 로드"""
    if os.path.exists(GEOJSON_PATH):
        try:
            with open(GEOJSON_PATH, "r", encoding="utf-8") as f:
                content = f.read()
                return json.loads(content, strict=False)
        except Exception as e:
            print(f"[경고] GeoJSON 로드 중 오류 발생: {e}")
            return None
    return None


def calculate_distance_meters(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """두 위도/경도 좌표 사이의 실제 직선 거리(m) 계산 (Haversine)"""
    R = 6371000
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = (math.sin(delta_phi / 2) ** 2 +
         math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    return R * c


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
        raise RuntimeError("TMAP_APP_KEY가 없습니다. .env 파일을 확인하세요.")

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
        raw_data = json.loads(response.text, strict=False)
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


def simplify_walking_route(data: dict[str, Any]) -> dict[str, Any]:
    features = data.get("features", [])

    if not features:
        raise HTTPException(
            status_code=502,
            detail="TMAP 보행 경로 결과가 없습니다.",
        )

    path_coordinates = []
    instructions = []
    segments = []

    first_properties = features[0].get("properties", {})
    total_distance = first_properties.get("totalDistance", 0)
    total_time = first_properties.get("totalTime", 0)

    for feature in features:
        geometry = feature.get("geometry", {})
        properties = feature.get("properties", {})
        geometry_type = geometry.get("type")

        if geometry_type == "LineString":
            coordinates = geometry.get("coordinates", [])
            path_coordinates.extend(coordinates)

            segments.append(
                {
                    "distance_meters": properties.get("distance", 0),
                    "duration_seconds": properties.get("time", 0),
                    "road_name": properties.get("name", ""),
                    "description": properties.get("description", ""),
                    "road_type": properties.get("roadType"),
                    "facility_type": properties.get("facilityType"),
                    "coordinates": coordinates,
                }
            )

        elif geometry_type == "Point":
            description = properties.get("description", "")
            if description:
                instructions.append(
                    {
                        "description": description,
                        "turn_type": properties.get("turnType"),
                        "point_type": properties.get("pointType"),
                        "intersection_name": properties.get("intersectionName", ""),
                        "coordinate": geometry.get("coordinates", []),
                    }
                )

    # 💡 [핵심] 경사도 8.0% 이상인 급경사 구간만 선별 감지
    detected_slopes = detect_slopes_on_path(path_coordinates, slope_threshold=8.0)

    # 💡 급경사 여부 플래그 (경로 추천 알고리즘에서 우회할 때 활용)
    has_steep_slope = len(detected_slopes) > 0

    return {
        "type": "WALK",
        "total_distance_meters": total_distance,
        "total_duration_seconds": total_time,
        "total_duration_minutes": round(total_time / 60, 1),
        "path": path_coordinates,
        "instructions": instructions,
        "segments": segments,
        "detected_slopes": detected_slopes,
        "has_steep_slope": has_steep_slope,  # 8% 이상 급경사 포함 여부 (True/False)
    }


def detect_slopes_on_path(
    path_coordinates: list[list[float]], slope_threshold: float = 8.0
) -> list[dict[str, Any]]:
    """경사도 8.0% 이상의 급경사 구간만 정확히 감지"""
    network = load_seongnam_walking_network()
    if not network:
        return []

    detected_slopes = []
    features = network.get("features", [])
    SEARCH_RADIUS_METERS = 80.0  # 경로 주변 80m 이내 보행망 체크

    for feature in features:
        props = feature.get("properties", {})
        geom = feature.get("geometry", {})

        # 1. grade_100m 속성 읽기 (0.08 = 8%)
        raw_grade = props.get("grade_100m") or props.get("grade_local") or props.get("slope_deg") or props.get("slope")
        
        if raw_grade is None:
            continue

        try:
            raw_val = abs(float(raw_grade))
            # 소수점 비율(0.08)을 퍼센트(8.0%)로 변환
            slope_val = raw_val * 100.0 if raw_val < 1.0 else raw_val
        except (ValueError, TypeError):
            continue

        # 💡 [조건] 경사도가 지정한 임계값(8.0%) 이상일 때만 감지
        if slope_val >= slope_threshold:
            geom_type = geom.get("type")
            coords_to_check = []

            if geom_type == "MultiLineString":
                multi_coords = geom.get("coordinates", [])
                for line_coords in multi_coords:
                    for coord in line_coords:
                        if len(coord) >= 2:
                            coords_to_check.append((float(coord[1]), float(coord[0])))
            elif geom_type == "LineString":
                line_coords = geom.get("coordinates", [])
                for coord in line_coords:
                    if len(coord) >= 2:
                        coords_to_check.append((float(coord[1]), float(coord[0])))
            elif geom_type == "Point":
                pt_coords = geom.get("coordinates", [])
                if len(pt_coords) >= 2:
                    coords_to_check.append((float(pt_coords[1]), float(pt_coords[0])))

            is_matched = False
            for s_lat, s_lng in coords_to_check:
                for p_lng, p_lat in path_coordinates:
                    dist = calculate_distance_meters(s_lat, s_lng, float(p_lat), float(p_lng))

                    if dist <= SEARCH_RADIUS_METERS:
                        road_name = props.get("walk_class") or props.get("명칭") or "급경사 구간"
                        detected_slopes.append(
                            {
                                "name": str(road_name),
                                "latitude": round(s_lat, 6),
                                "longitude": round(s_lng, 6),
                                "slope_degree": round(slope_val, 1),
                            }
                        )
                        is_matched = True
                        break

                if is_matched:
                    break

    print(f"🔍 [백엔드 로그] 감지된 8% 이상 급경사로 개수: {len(detected_slopes)}개")
    return detected_slopes