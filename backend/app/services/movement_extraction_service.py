from __future__ import annotations

import re
from copy import deepcopy
from typing import Any


# ==============================================================================
# 1. 서비스에서 사용하는 철도 노선 순서
#
# station_movements의 정확한 진행 방향을 계산하기 위해 사용합니다.
#
# 전체 수도권 노선을 모두 넣는 것이 아니라
# 현재 서비스 범위에서 방향 판별에 필요한 인접 역까지만 포함합니다.
# ==============================================================================

LINE_STATION_ORDERS: dict[str, list[str]] = {
    "신분당선": [
        "청계산입구역",
        "판교역",
        "정자역",
        "미금역",
    ],

    "수인분당선": [
        "미금역",
        "정자역",
        "수내역",
        "서현역",
        "이매역",
        "야탑역",
        "모란역",
    ],

    "경강선": [
        "판교역",
        "성남역",
        "이매역",
        "삼동역",
    ],
}


# ==============================================================================
# 2. 역 이름 정규화
# ==============================================================================

def normalize_station_name(
    name: str | None,
) -> str | None:
    """
    역 이름을 서비스 내부 표준 형태로 정리합니다.

    예:
    판교(판교테크노밸리) -> 판교역
    정자 -> 정자역
    """

    if not name:
        return None

    normalized = str(
        name
    ).strip()

    # 괄호와 괄호 안 부가 설명 제거
    normalized = re.sub(
        r"\([^)]*\)",
        "",
        normalized,
    ).strip()

    if not normalized:
        return None

    if not normalized.endswith(
        "역"
    ):
        normalized = (
            f"{normalized}역"
        )

    return normalized


# ==============================================================================
# 3. 지하철 step 노선명 추출
# ==============================================================================

def get_step_line_name(
    step: dict[str, Any],
) -> str | None:
    """
    지하철 step에서 노선명을 추출합니다.
    """

    vehicles = step.get(
        "vehicles",
        [],
    )

    if isinstance(
        vehicles,
        list,
    ):

        for vehicle in vehicles:

            if not isinstance(
                vehicle,
                dict,
            ):
                continue

            name = vehicle.get(
                "name"
            )

            if name:
                return str(
                    name
                ).strip()

    # vehicles에 노선명이 없으면
    # guidance에서 보조 추출
    guidance = str(
        step.get(
            "guidance",
            "",
        )
    ).strip()

    match = re.match(
        r"(.+?)\s*\(",
        guidance,
    )

    if match:
        return (
            match.group(1)
            .strip()
        )

    return None


# ==============================================================================
# 4. step의 정차역 정규화
# ==============================================================================

def get_normalized_stops(
    step: dict[str, Any],
) -> list[str]:
    """
    지하철 step의 stops를
    서비스 내부 역명 형태로 변환합니다.
    """

    raw_stops = step.get(
        "stops",
        [],
    )

    if not isinstance(
        raw_stops,
        list,
    ):
        return []

    normalized_stops: list[str] = []

    for stop in raw_stops:

        normalized = (
            normalize_station_name(
                str(stop)
                if stop is not None
                else None
            )
        )

        if normalized:
            normalized_stops.append(
                normalized
            )

    return normalized_stops


# ==============================================================================
# 5. 후보 경로에서 지하철 구간만 추출
# ==============================================================================

def get_subway_steps(
    route: dict[str, Any],
) -> list[dict[str, Any]]:
    """
    후보 경로에서 지하철 구간만
    순서대로 반환합니다.
    """

    subway_steps: list[
        dict[str, Any]
    ] = []

    for step in route.get(
        "steps",
        [],
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
        ).strip().upper()

        if step_type == "SUBWAY":
            subway_steps.append(
                step
            )

    return subway_steps


# ==============================================================================
# 6. 환승 WALKING step 검색
# ==============================================================================

def get_transfer_walk_step(
    route: dict[str, Any],
    previous_subway_step_id: int | None,
    next_subway_step_id: int | None,
) -> dict[str, Any] | None:
    """
    두 지하철 구간 사이에 있는
    환승 도보 step을 찾습니다.
    """

    if (
        previous_subway_step_id
        is None
        or next_subway_step_id
        is None
    ):
        return None

    for step in route.get(
        "steps",
        [],
    ):

        if not isinstance(
            step,
            dict,
        ):
            continue

        step_id = step.get(
            "step_id"
        )

        if not isinstance(
            step_id,
            int,
        ):
            continue

        if not (
            previous_subway_step_id
            < step_id
            < next_subway_step_id
        ):
            continue

        step_type = str(
            step.get(
                "step_type",
                "",
            )
        ).strip().upper()

        guidance = str(
            step.get(
                "guidance",
                "",
            )
        ).strip()

        if (
            step_type
            == "WALKING"
            and "환승"
            in guidance
        ):
            return step

    return None


# ==============================================================================
# 7. 노선 진행 방향 판별
# ==============================================================================

def get_step_direction_sign(
    step: dict[str, Any],
) -> int | None:
    """
    해당 지하철 step이 노선 순서상
    어느 방향으로 이동하는지 계산합니다.

    반환:
    +1 : LINE_STATION_ORDERS의 정방향
    -1 : LINE_STATION_ORDERS의 역방향
    None : 판단 불가

    예:
    신분당선
    판교 -> 정자

    노선 순서:
    청계산입구 -> 판교 -> 정자 -> 미금

    따라서 +1
    """

    line_name = (
        get_step_line_name(
            step
        )
    )

    if not line_name:
        return None

    station_order = (
        LINE_STATION_ORDERS.get(
            line_name
        )
    )

    if not station_order:
        return None

    stops = (
        get_normalized_stops(
            step
        )
    )

    if len(stops) < 2:
        return None

    # 노선 메타데이터에 존재하는
    # 연속된 두 역을 찾습니다.
    for index in range(
        len(stops) - 1
    ):

        first_station = (
            stops[index]
        )

        second_station = (
            stops[index + 1]
        )

        if (
            first_station
            not in station_order
            or second_station
            not in station_order
        ):
            continue

        first_index = (
            station_order.index(
                first_station
            )
        )

        second_index = (
            station_order.index(
                second_station
            )
        )

        if second_index > first_index:
            return 1

        if second_index < first_index:
            return -1

    return None


# ==============================================================================
# 8. 특정 역에서 열차가 계속 진행할 다음 역 계산
# ==============================================================================

def get_direction_station_at(
    step: dict[str, Any],
    station_name: str | None,
) -> str | None:
    """
    열차가 해당 역을 지나 계속 운행한다고 가정했을 때
    다음 역을 반환합니다.

    이것을 플랫폼 방향 판별 기준으로 사용합니다.

    예:
    step:
    판교 -> 정자

    station_name:
    정자역

    신분당선 순서:
    청계산입구 -> 판교 -> 정자 -> 미금

    반환:
    미금역
    """

    if not station_name:
        return None

    normalized_station = (
        normalize_station_name(
            station_name
        )
    )

    if not normalized_station:
        return None

    line_name = (
        get_step_line_name(
            step
        )
    )

    if not line_name:
        return None

    station_order = (
        LINE_STATION_ORDERS.get(
            line_name
        )
    )

    if not station_order:
        return None

    if (
        normalized_station
        not in station_order
    ):
        return None

    direction_sign = (
        get_step_direction_sign(
            step
        )
    )

    if direction_sign is None:
        return None

    current_index = (
        station_order.index(
            normalized_station
        )
    )

    next_index = (
        current_index
        + direction_sign
    )

    if (
        next_index < 0
        or next_index
        >= len(
            station_order
        )
    ):
        return None

    return station_order[
        next_index
    ]


# ==============================================================================
# 9. 승차 구간 진행 방향 계산
# ==============================================================================

def get_boarding_direction_station(
    step: dict[str, Any],
) -> str | None:
    """
    최초 승차 시 어떤 방향 승강장을 이용해야 하는지 반환합니다.

    첫 번째 다음 정차역을 우선 사용합니다.

    예:
    정자 -> 수내 -> 서현 ...

    반환:
    수내역
    """

    stops = (
        get_normalized_stops(
            step
        )
    )

    if len(stops) >= 2:
        return stops[1]

    if stops:
        return (
            get_direction_station_at(
                step,
                stops[0],
            )
        )

    return None


# ==============================================================================
# 10. 하차/환승 도착 플랫폼 방향 계산
# ==============================================================================

def get_arrival_direction_station(
    step: dict[str, Any],
) -> str | None:
    """
    지하철 구간의 마지막 역에 도착했을 때
    해당 열차가 계속 진행할 방향의 다음 역을 반환합니다.

    환승/하차 플랫폼을 정확하게 고르기 위해 사용합니다.

    예:
    신분당선:
    판교 -> 정자

    반환:
    미금역
    """

    stops = (
        get_normalized_stops(
            step
        )
    )

    if not stops:
        return None

    arrival_station = (
        stops[-1]
    )

    return get_direction_station_at(
        step,
        arrival_station,
    )


# ==============================================================================
# 11. station_movements 추출
# ==============================================================================

def extract_station_movements(
    route: dict[str, Any],
) -> list[dict[str, Any]]:
    """
    카카오 후보 경로 하나에서
    역 내부 이동에 필요한 정보를 추출합니다.

    생성 정보:
    - 최초 승차역
    - 환승역
    - 최종 하차역
    - 이용 노선
    - 이전 역 / 다음 역
    - 탑승 진행 방향
    - 도착 진행 방향
    - 환승 후 진행 방향
    - 환승 도보거리 / 시간
    """

    subway_steps = (
        get_subway_steps(
            route
        )
    )

    if not subway_steps:
        return []

    movements: list[
        dict[str, Any]
    ] = []

    # ------------------------------------------------------------------
    # 1. 최초 승차
    # ------------------------------------------------------------------

    first_step = (
        subway_steps[0]
    )

    first_stops = (
        get_normalized_stops(
            first_step
        )
    )

    if first_stops:

        boarding_station = (
            first_stops[0]
        )

        next_station = (
            first_stops[1]
            if len(
                first_stops
            ) >= 2
            else None
        )

        departure_direction_station = (
            get_boarding_direction_station(
                first_step
            )
        )

        movements.append(
            {
                "movement_type": (
                    "BOARDING"
                ),

                "station_name": (
                    boarding_station
                ),

                "line_name": (
                    get_step_line_name(
                        first_step
                    )
                ),

                "previous_station": (
                    None
                ),

                "next_station": (
                    next_station
                ),

                # 정확한 탑승 승강장 방향 기준
                "departure_direction_station": (
                    departure_direction_station
                ),

                "direction_source": (
                    "KAKAO_STOPS"
                ),

                "step_id": (
                    first_step.get(
                        "step_id"
                    )
                ),
            }
        )

    # ------------------------------------------------------------------
    # 2. 환승
    # ------------------------------------------------------------------

    for index in range(
        len(
            subway_steps
        ) - 1
    ):

        previous_step = (
            subway_steps[index]
        )

        next_step = (
            subway_steps[
                index + 1
            ]
        )

        previous_stops = (
            get_normalized_stops(
                previous_step
            )
        )

        next_stops = (
            get_normalized_stops(
                next_step
            )
        )

        if (
            not previous_stops
            or not next_stops
        ):
            continue

        transfer_station_from = (
            previous_stops[-1]
        )

        transfer_station_to = (
            next_stops[0]
        )

        # 이전 지하철 구간의 마지막 역과
        # 다음 지하철 구간의 첫 역이 같아야 환승
        if (
            transfer_station_from
            != transfer_station_to
        ):
            continue

        previous_station = (
            previous_stops[-2]
            if len(
                previous_stops
            ) >= 2
            else None
        )

        next_station = (
            next_stops[1]
            if len(
                next_stops
            ) >= 2
            else None
        )

        # --------------------------------------------------------------
        # 핵심:
        # 이전 노선에서 도착한 플랫폼의 진행 방향
        # --------------------------------------------------------------

        arrival_direction_station = (
            get_arrival_direction_station(
                previous_step
            )
        )

        # --------------------------------------------------------------
        # 환승 후 새 노선의 탑승 방향
        # --------------------------------------------------------------

        departure_direction_station = (
            get_boarding_direction_station(
                next_step
            )
        )

        transfer_walk_step = (
            get_transfer_walk_step(
                route=route,
                previous_subway_step_id=(
                    previous_step.get(
                        "step_id"
                    )
                ),
                next_subway_step_id=(
                    next_step.get(
                        "step_id"
                    )
                ),
            )
        )

        movements.append(
            {
                "movement_type": (
                    "TRANSFER"
                ),

                "station_name": (
                    transfer_station_from
                ),

                "from_line": (
                    get_step_line_name(
                        previous_step
                    )
                ),

                "to_line": (
                    get_step_line_name(
                        next_step
                    )
                ),

                "previous_station": (
                    previous_station
                ),

                "next_station": (
                    next_station
                ),

                # 이전 노선에서 도착한
                # 실제 플랫폼 방향 기준
                "arrival_direction_station": (
                    arrival_direction_station
                ),

                # 환승 후 새 노선에서 출발할
                # 실제 플랫폼 방향 기준
                "departure_direction_station": (
                    departure_direction_station
                ),

                "arrival_direction_source": (
                    "LINE_TOPOLOGY"
                    if arrival_direction_station
                    else "UNKNOWN"
                ),

                "departure_direction_source": (
                    "KAKAO_STOPS"
                    if departure_direction_station
                    else "UNKNOWN"
                ),

                "walk_distance_meters": (
                    transfer_walk_step.get(
                        "distance"
                    )
                    if transfer_walk_step
                    else None
                ),

                "walk_time_seconds": (
                    transfer_walk_step.get(
                        "time"
                    )
                    if transfer_walk_step
                    else None
                ),

                # 카카오 환승 WALKING guidance가
                # "이매이매역 환승"처럼 중복되는 경우가 있으므로
                # 이미 확정한 환승역 이름으로 안내 문구를 생성합니다.
                "walk_guidance": (
                    f"{transfer_station_from} 환승"
                    if transfer_walk_step
                    else None
                ),

                "from_step_id": (
                    previous_step.get(
                        "step_id"
                    )
                ),

                "to_step_id": (
                    next_step.get(
                        "step_id"
                    )
                ),
            }
        )

    # ------------------------------------------------------------------
    # 3. 최종 하차
    # ------------------------------------------------------------------

    last_step = (
        subway_steps[-1]
    )

    last_stops = (
        get_normalized_stops(
            last_step
        )
    )

    if last_stops:

        alighting_station = (
            last_stops[-1]
        )

        previous_station = (
            last_stops[-2]
            if len(
                last_stops
            ) >= 2
            else None
        )

        arrival_direction_station = (
            get_arrival_direction_station(
                last_step
            )
        )

        movements.append(
            {
                "movement_type": (
                    "ALIGHTING"
                ),

                "station_name": (
                    alighting_station
                ),

                "line_name": (
                    get_step_line_name(
                        last_step
                    )
                ),

                "previous_station": (
                    previous_station
                ),

                "next_station": (
                    None
                ),

                # 하차한 승강장의 진행 방향
                "arrival_direction_station": (
                    arrival_direction_station
                ),

                "arrival_direction_source": (
                    "LINE_TOPOLOGY"
                    if arrival_direction_station
                    else "UNKNOWN"
                ),

                "step_id": (
                    last_step.get(
                        "step_id"
                    )
                ),
            }
        )

    return movements


# ==============================================================================
# 12. 모든 후보 경로에 station_movements 추가
# ==============================================================================

def attach_station_movements(
    routes: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    모든 후보 경로에
    station_movements 필드를 추가합니다.
    """

    analyzed_routes: list[
        dict[str, Any]
    ] = []

    for route in routes:

        copied_route = deepcopy(
            route
        )

        copied_route[
            "station_movements"
        ] = (
            extract_station_movements(
                copied_route
            )
        )

        analyzed_routes.append(
            copied_route
        )

    return analyzed_routes