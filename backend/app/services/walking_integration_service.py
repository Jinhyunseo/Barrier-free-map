import math
from copy import deepcopy
from typing import Any

from app.services.walking_route_service import (
    get_walking_route,
)


# ==============================================================================
# TMAP 최소 보행 요청 거리
# ==============================================================================

TMAP_MIN_WALK_DISTANCE_METERS = 100.0

# TMAP 보행 API를 적용할 최대 후보 수
TMAP_MAX_CANDIDATE_ROUTES = 3


# ==============================================================================
# TMAP 호출 전 후보 경로 1차 선별
# ==============================================================================

def _safe_number(
    value: Any,
    default: float = 0.0,
) -> float:
    try:
        if value is None:
            return default

        return float(value)

    except (
        TypeError,
        ValueError,
    ):
        return default


def _get_internal_walk_distance(
    route: dict[str, Any],
) -> float:
    """
    TMAP 적용 전에는 first-mile / last-mile 실제 보행거리를 모르므로,
    카카오 후보 경로 내부 WALKING step의 거리만 합산합니다.
    """

    total = 0.0

    steps = route.get(
        "steps",
        [],
    )

    if not isinstance(
        steps,
        list,
    ):
        return total

    for step in steps:

        if not isinstance(
            step,
            dict,
        ):
            continue

        step_type = str(
            step.get(
                "step_type",
                "",
            )
        ).strip().upper()

        if step_type not in {
            "WALK",
            "WALKING",
        }:
            continue

        total += _safe_number(
            step.get(
                "distance"
            ),
            0.0,
        )

    return total


def _select_preliminary_routes(
    routes: list[dict[str, Any]],
    route_preference: str = "BALANCED",
    limit: int = TMAP_MAX_CANDIDATE_ROUTES,
) -> list[dict[str, Any]]:
    """
    TMAP 보행 API 호출 전에 카카오 후보 경로를 1차 선별합니다.

    FASTEST:
        전체 이동시간 우선

    MIN_WALKING:
        카카오 경로 내부 도보거리 우선

    MIN_TRANSFER:
        환승 횟수 우선

    BALANCED:
        시간 + 도보거리 + 환승 횟수를 함께 고려

    주의:
    이 단계는 TMAP 실제 보행 접근 경로를 붙이기 전의
    '1차 후보 압축' 단계입니다.
    """

    if not isinstance(
        routes,
        list,
    ):
        return []

    if limit <= 0:
        return []

    if len(routes) <= limit:
        return [
            deepcopy(route)
            for route in routes
        ]

    preference = str(
        route_preference
        or "BALANCED"
    ).strip().upper()

    def route_key(
        route: dict[str, Any],
    ) -> tuple:
        time_minutes = _safe_number(
            route.get(
                "total_time_minutes"
            ),
            default=float("inf"),
        )

        if (
            time_minutes == float("inf")
        ):
            total_time_seconds = _safe_number(
                route.get(
                    "total_time_seconds"
                ),
                default=float("inf"),
            )

            if (
                total_time_seconds
                != float("inf")
            ):
                time_minutes = (
                    total_time_seconds
                    / 60.0
                )

        transfer_count = _safe_number(
            route.get(
                "transfer_count"
            ),
            default=float("inf"),
        )

        walk_distance = (
            _get_internal_walk_distance(
                route
            )
        )

        if preference == "FASTEST":
            return (
                time_minutes,
                walk_distance,
                transfer_count,
            )

        if preference == "MIN_WALKING":
            return (
                walk_distance,
                time_minutes,
                transfer_count,
            )

        if preference == "MIN_TRANSFER":
            return (
                transfer_count,
                time_minutes,
                walk_distance,
            )

        # BALANCED
        balanced_score = (
            time_minutes
            + walk_distance * 0.035
            + transfer_count * 12.0
        )

        return (
            balanced_score,
            time_minutes,
            walk_distance,
            transfer_count,
        )

    selected = sorted(
        routes,
        key=route_key,
    )[:limit]

    return [
        deepcopy(route)
        for route in selected
    ]


# ==============================================================================
# 좌표 거리 계산
# ==============================================================================

def _haversine_distance_m(
    lon1: float,
    lat1: float,
    lon2: float,
    lat2: float,
) -> float:
    """
    두 WGS84 좌표 사이의 직선거리를
    미터 단위로 계산합니다.
    """

    earth_radius_m = 6371000.0

    lat1_rad = math.radians(
        lat1
    )

    lat2_rad = math.radians(
        lat2
    )

    delta_lat = math.radians(
        lat2 - lat1
    )

    delta_lon = math.radians(
        lon2 - lon1
    )

    a = (
        math.sin(
            delta_lat / 2
        ) ** 2
        +
        math.cos(
            lat1_rad
        )
        * math.cos(
            lat2_rad
        )
        * math.sin(
            delta_lon / 2
        ) ** 2
    )

    c = 2 * math.atan2(
        math.sqrt(a),
        math.sqrt(1 - a),
    )

    return (
        earth_radius_m
        * c
    )


# ==============================================================================
# 짧은 보행 구간 생성
# ==============================================================================

def _create_short_walk(
    start_x: float,
    start_y: float,
    end_x: float,
    end_y: float,
    distance_meters: float,
) -> dict[str, Any]:
    """
    TMAP이 요청을 허용하지 않을 정도로
    가까운 거리의 보행 구간을 직접 생성합니다.

    주의:
    실제 도로망이 아니라 좌표 간 직선거리를 기반으로 한
    짧은 접근 구간입니다.
    """

    distance = max(
        0,
        int(
            round(
                distance_meters
            )
        ),
    )

    # 약 4km/h 수준의 보행 속도
    walking_speed_mps = 1.1

    duration_seconds = (
        int(
            round(
                distance
                / walking_speed_mps
            )
        )
        if distance > 0
        else 0
    )

    return {
        "type": "WALK",
        "source": "LOCAL_SHORT_WALK",
        "total_distance_meters": (
            distance
        ),
        "total_duration_seconds": (
            duration_seconds
        ),
        "total_duration_minutes": (
            round(
                duration_seconds / 60,
                1,
            )
        ),
        "path": [
            [
                start_x,
                start_y,
            ],
            [
                end_x,
                end_y,
            ],
        ],
        "instructions": [
            {
                "description": (
                    f"약 {distance}m 도보 이동"
                ),
                "turn_type": None,
                "point_type": None,
                "intersection_name": "",
                "coordinate": [
                    end_x,
                    end_y,
                ],
            }
        ],
        "segments": [],
    }


# ==============================================================================
# 첫 대중교통 좌표
# ==============================================================================

def _get_first_transit_coordinate(
    route: dict[str, Any],
) -> tuple[float, float] | None:
    """
    첫 번째 버스/지하철 구간의
    시작 좌표를 찾습니다.
    """

    steps = route.get(
        "steps",
        [],
    )

    if not isinstance(
        steps,
        list,
    ):
        return None

    for step in steps:

        if not isinstance(
            step,
            dict,
        ):
            continue

        step_type = str(
            step.get(
                "step_type",
                "",
            )
        ).upper()

        if step_type not in {
            "BUS",
            "SUBWAY",
        }:
            continue

        path = step.get(
            "path",
            [],
        )

        if (
            isinstance(
                path,
                list,
            )
            and path
            and isinstance(
                path[0],
                list,
            )
            and len(
                path[0]
            ) >= 2
        ):
            return (
                float(
                    path[0][0]
                ),
                float(
                    path[0][1]
                ),
            )

    return None


# ==============================================================================
# 마지막 대중교통 좌표
# ==============================================================================

def _get_last_transit_coordinate(
    route: dict[str, Any],
) -> tuple[float, float] | None:
    """
    마지막 버스/지하철 구간의
    종료 좌표를 찾습니다.
    """

    steps = route.get(
        "steps",
        [],
    )

    if not isinstance(
        steps,
        list,
    ):
        return None

    for step in reversed(
        steps
    ):

        if not isinstance(
            step,
            dict,
        ):
            continue

        step_type = str(
            step.get(
                "step_type",
                "",
            )
        ).upper()

        if step_type not in {
            "BUS",
            "SUBWAY",
        }:
            continue

        path = step.get(
            "path",
            [],
        )

        if (
            isinstance(
                path,
                list,
            )
            and path
            and isinstance(
                path[-1],
                list,
            )
            and len(
                path[-1]
            ) >= 2
        ):
            return (
                float(
                    path[-1][0]
                ),
                float(
                    path[-1][1]
                ),
            )

    return None


# ==============================================================================
# 후보 경로 하나에 first-mile / last-mile 붙이기
# ==============================================================================

async def attach_walking_access(
    route: dict[str, Any],
    origin_x: float,
    origin_y: float,
    destination_x: float,
    destination_y: float,
    origin_name: str,
    destination_name: str,
    avoid_stairs: bool = False,
) -> dict[str, Any]:
    """
    대중교통 후보 경로 앞뒤에
    실제 보행 접근 경로를 붙입니다.

    출발지
        ↓
    첫 승차 지점

    마지막 하차 지점
        ↓
    목적지
    """

    result = deepcopy(
        route
    )

    first_transit = (
        _get_first_transit_coordinate(
            result
        )
    )

    last_transit = (
        _get_last_transit_coordinate(
            result
        )
    )

    first_mile_walk = None
    last_mile_walk = None

    # --------------------------------------------------------------------------
    # 출발지 -> 첫 승차지점
    # --------------------------------------------------------------------------

    if first_transit:

        first_x, first_y = (
            first_transit
        )

        first_direct_distance = (
            _haversine_distance_m(
                origin_x,
                origin_y,
                first_x,
                first_y,
            )
        )

        if (
            first_direct_distance
            < TMAP_MIN_WALK_DISTANCE_METERS
        ):
            first_mile_walk = (
                _create_short_walk(
                    start_x=origin_x,
                    start_y=origin_y,
                    end_x=first_x,
                    end_y=first_y,
                    distance_meters=(
                        first_direct_distance
                    ),
                )
            )

        else:
            first_mile_walk = (
                await get_walking_route(
                    start_x=origin_x,
                    start_y=origin_y,
                    end_x=first_x,
                    end_y=first_y,
                    start_name=origin_name,
                    end_name="첫 승차 지점",
                    avoid_stairs=(
                        avoid_stairs
                    ),
                )
            )

    # --------------------------------------------------------------------------
    # 마지막 하차지점 -> 목적지
    # --------------------------------------------------------------------------

    if last_transit:

        last_x, last_y = (
            last_transit
        )

        last_direct_distance = (
            _haversine_distance_m(
                last_x,
                last_y,
                destination_x,
                destination_y,
            )
        )

        if (
            last_direct_distance
            < TMAP_MIN_WALK_DISTANCE_METERS
        ):
            last_mile_walk = (
                _create_short_walk(
                    start_x=last_x,
                    start_y=last_y,
                    end_x=destination_x,
                    end_y=destination_y,
                    distance_meters=(
                        last_direct_distance
                    ),
                )
            )

        else:
            last_mile_walk = (
                await get_walking_route(
                    start_x=last_x,
                    start_y=last_y,
                    end_x=destination_x,
                    end_y=destination_y,
                    start_name=(
                        "마지막 하차 지점"
                    ),
                    end_name=(
                        destination_name
                    ),
                    avoid_stairs=(
                        avoid_stairs
                    ),
                )
            )

    # --------------------------------------------------------------------------
    # walking_access 저장
    # --------------------------------------------------------------------------

    result[
        "walking_access"
    ] = {
        "first_mile": (
            first_mile_walk
        ),
        "last_mile": (
            last_mile_walk
        ),
    }

    # --------------------------------------------------------------------------
    # 보행 거리 합산
    # --------------------------------------------------------------------------

    first_distance = (
        first_mile_walk.get(
            "total_distance_meters",
            0,
        )
        if first_mile_walk
        else 0
    )

    last_distance = (
        last_mile_walk.get(
            "total_distance_meters",
            0,
        )
        if last_mile_walk
        else 0
    )

    # --------------------------------------------------------------------------
    # 보행 시간 합산
    # --------------------------------------------------------------------------

    first_time = (
        first_mile_walk.get(
            "total_duration_seconds",
            0,
        )
        if first_mile_walk
        else 0
    )

    last_time = (
        last_mile_walk.get(
            "total_duration_seconds",
            0,
        )
        if last_mile_walk
        else 0
    )

    result[
        "access_walk_distance_meters"
    ] = int(
        first_distance
        + last_distance
    )

    result[
        "access_walk_time_seconds"
    ] = int(
        first_time
        + last_time
    )

    return result


# ==============================================================================
# 모든 후보 경로에 보행 접근 경로 붙이기
# ==============================================================================

async def attach_walking_access_to_routes(
    routes: list[
        dict[str, Any]
    ],
    origin_x: float,
    origin_y: float,
    destination_x: float,
    destination_y: float,
    origin_name: str,
    destination_name: str,
    avoid_stairs: bool = False,
    route_preference: str = "BALANCED",
) -> list[dict[str, Any]]:
    """
    카카오 후보 경로를 선호도 기준으로 최대 3개까지 1차 선별한 뒤,
    선택된 후보에만 first-mile / last-mile TMAP 보행 접근 구간을 붙입니다.

    이렇게 해서 경로 검색 1회당 TMAP 호출을
    최대 약 6회(first-mile + last-mile × 3개 후보)로 제한합니다.
    """

    selected_routes = (
        _select_preliminary_routes(
            routes=routes,
            route_preference=(
                route_preference
            ),
            limit=(
                TMAP_MAX_CANDIDATE_ROUTES
            ),
        )
    )

    results: list[
        dict[str, Any]
    ] = []

    for route in selected_routes:

        enriched_route = (
            await attach_walking_access(
                route=route,
                origin_x=origin_x,
                origin_y=origin_y,
                destination_x=(
                    destination_x
                ),
                destination_y=(
                    destination_y
                ),
                origin_name=(
                    origin_name
                ),
                destination_name=(
                    destination_name
                ),
                avoid_stairs=(
                    avoid_stairs
                ),
            )
        )

        results.append(
            enriched_route
        )

    return results