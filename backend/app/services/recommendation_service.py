from __future__ import annotations

from copy import deepcopy
from typing import Any

from app.services.movement_extraction_service import (
    attach_station_movements,
)

from app.services.station_facility_service import (
    get_station_facilities,
)

from app.services.station_path_service import (
    find_realtime_safe_internal_path,
    get_station_graph,
)


# ==============================================================================
# 1. 사용자 유형별 설정
# ==============================================================================

USER_CONFIGS: dict[str, dict[str, Any]] = {
    "WHEELCHAIR": {
        "name": "휠체어",
        "max_incline": 8.3,
        "max_curb": 2.0,
        "allow_stairs": False,
        "require_low_floor_bus": True,
        "broken_elevator_is_barrier": True,
        "weights": {
            "time_per_min": 1.0,
            "walk_dist_per_m": 0.08,
            "transfer_penalty": 20.0,
            "elevator_bonus": -8.0,
            "low_floor_bus_bonus": -15.0,
            "unknown_data_penalty": 10.0,
        },
    },

    "STROLLER": {
        "name": "유모차",
        "max_incline": 10.0,
        "max_curb": 5.0,
        "allow_stairs": False,
        "require_low_floor_bus": False,
        "broken_elevator_is_barrier": True,
        "weights": {
            "time_per_min": 1.0,
            "walk_dist_per_m": 0.03,
            "transfer_penalty": 15.0,
            "elevator_bonus": -10.0,
            "low_floor_bus_bonus": -5.0,
            "unknown_data_penalty": 7.0,
        },
    },

    "ELDERLY": {
        "name": "고령자",
        "max_incline": 8.3,
        "max_curb": 3.0,
        "allow_stairs": False,
        "require_low_floor_bus": False,
        "broken_elevator_is_barrier": True,
        "weights": {
            "time_per_min": 1.2,
            "walk_dist_per_m": 0.05,
            "transfer_penalty": 25.0,
            "elevator_bonus": -12.0,
            "low_floor_bus_bonus": -5.0,
            "unknown_data_penalty": 8.0,
        },
    },
}


# ==============================================================================
# 2. 공통 유틸
# ==============================================================================

def _safe_number(
    value: Any,
    default: float = 0.0,
) -> float:
    if value is None:
        return default

    try:
        return float(value)

    except (
        TypeError,
        ValueError,
    ):
        return default


def _normalize_text(
    value: Any,
) -> str:
    if value is None:
        return ""

    return str(
        value
    ).strip().lower()


def _normalize_user_type(
    user_type: str,
) -> str:
    return str(
        user_type
    ).strip().upper()


def _append_unique(
    target: list[str],
    value: str,
) -> None:
    if (
        value
        and value
        not in target
    ):
        target.append(
            value
        )


def _remove_value(
    target: list[str],
    value: str,
) -> None:
    while value in target:
        target.remove(
            value
        )


# ==============================================================================
# 3. 카카오 경로 유형 판단
# ==============================================================================

def _is_walk_step(
    step: dict[str, Any],
) -> bool:
    step_type = _normalize_text(
        step.get(
            "step_type"
        )
    )

    walk_keywords = {
        "walk",
        "walking",
        "pedestrian",
        "foot",
        "도보",
    }

    if step_type in walk_keywords:
        return True

    return any(
        keyword in step_type
        for keyword in walk_keywords
    )


def _route_uses_bus(
    route: dict[str, Any],
) -> bool:
    route_type = _normalize_text(
        route.get(
            "route_type"
        )
    )

    if (
        "bus" in route_type
        or "버스" in route_type
    ):
        return True

    for vehicle in route.get(
        "vehicles",
        [],
    ):
        if not isinstance(
            vehicle,
            dict,
        ):
            continue

        vehicle_type = _normalize_text(
            vehicle.get(
                "type"
            )
        )

        vehicle_name = _normalize_text(
            vehicle.get(
                "name"
            )
        )

        if (
            "bus" in vehicle_type
            or "버스" in vehicle_type
            or "bus" in vehicle_name
            or "버스" in vehicle_name
        ):
            return True

    for step in route.get(
        "steps",
        [],
    ):
        if not isinstance(
            step,
            dict,
        ):
            continue

        step_type = _normalize_text(
            step.get(
                "step_type"
            )
        )

        if (
            "bus" in step_type
            or "버스" in step_type
        ):
            return True

    return False


def _route_uses_subway(
    route: dict[str, Any],
) -> bool:
    route_type = _normalize_text(
        route.get(
            "route_type"
        )
    )

    subway_keywords = {
        "subway",
        "metro",
        "rail",
        "지하철",
        "전철",
    }

    if any(
        keyword in route_type
        for keyword in subway_keywords
    ):
        return True

    for vehicle in route.get(
        "vehicles",
        [],
    ):
        if not isinstance(
            vehicle,
            dict,
        ):
            continue

        vehicle_type = _normalize_text(
            vehicle.get(
                "type"
            )
        )

        vehicle_name = _normalize_text(
            vehicle.get(
                "name"
            )
        )

        if any(
            (
                keyword in vehicle_type
                or keyword in vehicle_name
            )
            for keyword in subway_keywords
        ):
            return True

    for step in route.get(
        "steps",
        [],
    ):
        if not isinstance(
            step,
            dict,
        ):
            continue

        step_type = _normalize_text(
            step.get(
                "step_type"
            )
        )

        if any(
            keyword in step_type
            for keyword in subway_keywords
        ):
            return True

    return False


# ==============================================================================
# 4. 보행거리 계산
# ==============================================================================

def calculate_walk_distance(
    route: dict[str, Any],
) -> tuple[int, bool]:
    walk_distance = 0
    found_walk_step = False

    for step in route.get(
        "steps",
        [],
    ):
        if not isinstance(
            step,
            dict,
        ):
            continue

        if not _is_walk_step(
            step
        ):
            continue

        found_walk_step = True

        distance = _safe_number(
            step.get(
                "distance"
            ),
            default=0.0,
        )

        walk_distance += int(
            round(
                distance
            )
        )

    return (
        walk_distance,
        found_walk_step,
    )


# ==============================================================================
# 5. station_movements → 기존 시설 데이터 조회
# ==============================================================================

def _extract_station_line_pairs(
    route: dict[str, Any],
) -> list[dict[str, str]]:
    movements = route.get(
        "station_movements",
        [],
    )

    if not isinstance(
        movements,
        list,
    ):
        return []

    pairs: list[
        dict[str, str]
    ] = []

    seen: set[
        tuple[str, str]
    ] = set()

    for movement in movements:

        if not isinstance(
            movement,
            dict,
        ):
            continue

        movement_type = str(
            movement.get(
                "movement_type",
                "",
            )
        ).strip().upper()

        station_name = movement.get(
            "station_name"
        )

        if not station_name:
            continue

        station_name = str(
            station_name
        ).strip()

        line_names: list[str] = []

        if movement_type in {
            "BOARDING",
            "ALIGHTING",
        }:
            line_name = movement.get(
                "line_name"
            )

            if line_name:
                line_names.append(
                    str(
                        line_name
                    ).strip()
                )

        elif movement_type == "TRANSFER":

            from_line = movement.get(
                "from_line"
            )

            to_line = movement.get(
                "to_line"
            )

            if from_line:
                line_names.append(
                    str(
                        from_line
                    ).strip()
                )

            if to_line:
                line_names.append(
                    str(
                        to_line
                    ).strip()
                )

        for line_name in line_names:

            if not line_name:
                continue

            key = (
                station_name,
                line_name,
            )

            if key in seen:
                continue

            seen.add(
                key
            )

            pairs.append(
                {
                    "station_name": station_name,
                    "line_name": line_name,
                }
            )

    return pairs


def collect_station_facilities(
    route: dict[str, Any],
) -> list[dict[str, Any]]:
    station_line_pairs = (
        _extract_station_line_pairs(
            route
        )
    )

    results: list[
        dict[str, Any]
    ] = []

    for pair in station_line_pairs:

        station_name = pair[
            "station_name"
        ]

        line_name = pair[
            "line_name"
        ]

        facility_data = (
            get_station_facilities(
                station_name=station_name,
                line_name=line_name,
            )
        )

        results.append(
            facility_data
        )

    return results


# ==============================================================================
# 6. 기본 시설 접근성 데이터
# ==============================================================================

def attach_facility_accessibility(
    route: dict[str, Any],
) -> dict[str, Any]:
    analyzed_route = deepcopy(
        route
    )

    existing_accessibility = (
        analyzed_route.get(
            "accessibility"
        )
    )

    if not isinstance(
        existing_accessibility,
        dict,
    ):
        existing_accessibility = {}

    accessibility = deepcopy(
        existing_accessibility
    )

    station_facilities = (
        collect_station_facilities(
            analyzed_route
        )
    )

    successful_facilities = [
        facility
        for facility in station_facilities
        if facility.get(
            "status"
        ) == "SUCCESS"
    ]

    failed_facilities = [
        facility
        for facility in station_facilities
        if facility.get(
            "status"
        ) != "SUCCESS"
    ]

    elevator_count = sum(
        int(
            facility.get(
                "elevator_count",
                0,
            )
            or 0
        )
        for facility
        in successful_facilities
    )

    escalator_count = sum(
        int(
            facility.get(
                "escalator_count",
                0,
            )
            or 0
        )
        for facility
        in successful_facilities
    )

    if _route_uses_subway(
        analyzed_route
    ):
        if not station_facilities:
            has_elevator = None

        elif failed_facilities:
            has_elevator = None

        else:
            has_elevator = all(
                int(
                    facility.get(
                        "elevator_count",
                        0,
                    )
                    or 0
                ) > 0
                for facility
                in successful_facilities
            )

    else:
        has_elevator = None

    unknown_fields = accessibility.get(
        "unknown_fields",
        [],
    )

    if not isinstance(
        unknown_fields,
        list,
    ):
        unknown_fields = []

    unknown_fields = list(
        unknown_fields
    )

    if _route_uses_subway(
        analyzed_route
    ):
        _append_unique(
            unknown_fields,
            "엘리베이터 고장 여부",
        )

    if failed_facilities:
        _append_unique(
            unknown_fields,
            "일부 역사 시설 정보",
        )

    accessibility[
        "has_elevator"
    ] = has_elevator

    accessibility[
        "has_broken_elevator"
    ] = None

    accessibility[
        "broken_elevator_stations"
    ] = []

    accessibility[
        "station_facilities"
    ] = station_facilities

    accessibility[
        "facility_summary"
    ] = {
        "station_line_count": len(
            station_facilities
        ),

        "successful_station_line_count": len(
            successful_facilities
        ),

        "failed_station_line_count": len(
            failed_facilities
        ),

        "total_elevator_count": elevator_count,

        "total_escalator_count": escalator_count,
    }

    accessibility[
        "unknown_fields"
    ] = list(
        dict.fromkeys(
            unknown_fields
        )
    )

    if station_facilities:
        accessibility[
            "status"
        ] = "FACILITY_ANALYZED"

    else:
        accessibility.setdefault(
            "status",
            "UNKNOWN",
        )

    analyzed_route[
        "accessibility"
    ] = accessibility

    return analyzed_route


def attach_facility_accessibility_to_routes(
    routes: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    return [
        attach_facility_accessibility(
            route
        )
        for route in routes
    ]


# ==============================================================================
# 7. 실시간 역 내부 동선 분석
# ==============================================================================

def _station_graph_exists(
    station_name: str,
) -> bool:
    try:
        graph = get_station_graph(
            station_name
        )

    except (
        FileNotFoundError,
        ValueError,
    ):
        return False

    return isinstance(
        graph,
        dict,
    )


def attach_realtime_internal_accessibility(
    route: dict[str, Any],
    user_type: str,
) -> dict[str, Any]:
    analyzed_route = deepcopy(
        route
    )

    accessibility = analyzed_route.get(
        "accessibility",
        {},
    )

    if not isinstance(
        accessibility,
        dict,
    ):
        accessibility = {}

    accessibility = deepcopy(
        accessibility
    )

    movements = analyzed_route.get(
        "station_movements",
        [],
    )

    if not isinstance(
        movements,
        list,
    ):
        movements = []

    internal_paths: list[
        dict[str, Any]
    ] = []

    analyzed_movement_count = 0
    unknown_movement_count = 0
    unavailable_movement_count = 0

    required_facilities: list[
        dict[str, Any]
    ] = []

    blocked_facility_ids: list[str] = []
    broken_or_blocked_stations: list[str] = []
    unknown_realtime_facilities: list[str] = []

    unavailable_reasons = accessibility.get(
        "unavailable_reasons",
        [],
    )

    if not isinstance(
        unavailable_reasons,
        list,
    ):
        unavailable_reasons = []

    unavailable_reasons = list(
        unavailable_reasons
    )

    unknown_fields = accessibility.get(
        "unknown_fields",
        [],
    )

    if not isinstance(
        unknown_fields,
        list,
    ):
        unknown_fields = []

    unknown_fields = list(
        unknown_fields
    )

    for movement in movements:

        if not isinstance(
            movement,
            dict,
        ):
            continue

        station_name = str(
            movement.get(
                "station_name",
                "",
            )
        ).strip()

        if not station_name:
            continue

        if not _station_graph_exists(
            station_name
        ):
            unknown_movement_count += 1

            internal_paths.append(
                {
                    "status": "GRAPH_NOT_AVAILABLE",
                    "station_name": station_name,
                    "movement": movement,
                    "message": (
                        "해당 역의 내부 이동 그래프가 "
                        "구축되지 않았습니다."
                    ),
                }
            )

            _append_unique(
                unknown_fields,
                f"{station_name} 내부 이동 동선",
            )

            continue

        try:
            result = (
                find_realtime_safe_internal_path(
                    movement=movement,
                    user_type=user_type,
                )
            )

        except Exception as error:
            unknown_movement_count += 1

            internal_paths.append(
                {
                    "status": "ANALYSIS_ERROR",
                    "station_name": station_name,
                    "movement": movement,
                    "message": str(
                        error
                    ),
                }
            )

            _append_unique(
                unknown_fields,
                f"{station_name} 내부 이동 동선",
            )

            continue

        internal_paths.append(
            result
        )

        status = str(
            result.get(
                "status",
                "UNKNOWN",
            )
        ).upper()

        if status == "SUCCESS":

            analyzed_movement_count += 1

            facilities = result.get(
                "required_facilities",
                [],
            )

            if isinstance(
                facilities,
                list,
            ):
                required_facilities.extend(
                    facility
                    for facility in facilities
                    if isinstance(
                        facility,
                        dict,
                    )
                )

            blocked_ids = result.get(
                "blocked_edge_ids",
                [],
            )

            if isinstance(
                blocked_ids,
                list,
            ):
                for edge_id in blocked_ids:

                    edge_text = str(
                        edge_id
                    ).strip()

                    if (
                        edge_text
                        and edge_text
                        not in blocked_facility_ids
                    ):
                        blocked_facility_ids.append(
                            edge_text
                        )

                if (
                    blocked_ids
                    and station_name
                    not in broken_or_blocked_stations
                ):
                    broken_or_blocked_stations.append(
                        station_name
                    )

            if result.get(
                "has_unknown_facility_status"
            ) is True:

                _append_unique(
                    unknown_fields,
                    f"{station_name} 일부 승강설비 실시간 상태",
                )

        elif status in {
            "REALTIME_PATH_NOT_FOUND",
            "PATH_NOT_FOUND",
            "MAX_RETRY_EXCEEDED",
        }:

            unavailable_movement_count += 1

            reason = (
                f"{station_name}에서 "
                "사용자 유형에 맞는 이용 가능한 "
                "역 내부 이동 동선을 찾지 못했습니다."
            )

            _append_unique(
                unavailable_reasons,
                reason,
            )

            blocked_ids = result.get(
                "blocked_edge_ids",
                [],
            )

            if isinstance(
                blocked_ids,
                list,
            ):

                for edge_id in blocked_ids:

                    edge_text = str(
                        edge_id
                    ).strip()

                    if (
                        edge_text
                        and edge_text
                        not in blocked_facility_ids
                    ):
                        blocked_facility_ids.append(
                            edge_text
                        )

                if (
                    blocked_ids
                    and station_name
                    not in broken_or_blocked_stations
                ):
                    broken_or_blocked_stations.append(
                        station_name
                    )

        else:

            unknown_movement_count += 1

            _append_unique(
                unknown_fields,
                f"{station_name} 내부 이동 동선",
            )

    elevator_facilities = [
        facility
        for facility in required_facilities
        if str(
            facility.get(
                "facility_type",
                "",
            )
        ).upper()
        == "ELEVATOR"
    ]

    escalator_facilities = [
        facility
        for facility in required_facilities
        if str(
            facility.get(
                "facility_type",
                "",
            )
        ).upper()
        == "ESCALATOR"
    ]

    for facility in required_facilities:

        realtime = facility.get(
            "realtime",
            {},
        )

        if not isinstance(
            realtime,
            dict,
        ):
            realtime = {}

        realtime_status = str(
            realtime.get(
                "realtime_status",
                "UNKNOWN",
            )
        ).upper()

        if realtime_status == "UNKNOWN":

            edge_id = str(
                facility.get(
                    "edge_id",
                    "",
                )
            ).strip()

            if (
                edge_id
                and edge_id
                not in unknown_realtime_facilities
            ):
                unknown_realtime_facilities.append(
                    edge_id
                )

    if analyzed_movement_count > 0:

        if elevator_facilities:
            accessibility[
                "has_elevator"
            ] = True

        elif _route_uses_subway(
            analyzed_route
        ):
            accessibility.setdefault(
                "has_elevator",
                None,
            )

    if unavailable_movement_count > 0:

        if blocked_facility_ids:
            accessibility[
                "has_broken_elevator"
            ] = True

        else:
            accessibility[
                "has_broken_elevator"
            ] = None

    elif unknown_realtime_facilities:

        accessibility[
            "has_broken_elevator"
        ] = None

    elif analyzed_movement_count > 0:

        accessibility[
            "has_broken_elevator"
        ] = False

    if (
        analyzed_movement_count > 0
        and not unknown_realtime_facilities
        and unavailable_movement_count == 0
    ):
        _remove_value(
            unknown_fields,
            "엘리베이터 고장 여부",
        )

    if unavailable_movement_count > 0:
        internal_path_available: bool | None = False

    elif (
        analyzed_movement_count > 0
        and unknown_movement_count == 0
    ):
        internal_path_available = True

    else:
        internal_path_available = None

    accessibility[
        "internal_path_available"
    ] = internal_path_available

    accessibility[
        "internal_paths"
    ] = internal_paths

    accessibility[
        "required_facilities"
    ] = required_facilities

    accessibility[
        "required_facility_count"
    ] = len(
        required_facilities
    )

    accessibility[
        "required_elevator_count"
    ] = len(
        elevator_facilities
    )

    accessibility[
        "required_escalator_count"
    ] = len(
        escalator_facilities
    )

    accessibility[
        "blocked_facility_ids"
    ] = blocked_facility_ids

    accessibility[
        "rerouted_due_to_facility_failure"
    ] = bool(
        blocked_facility_ids
        and unavailable_movement_count == 0
    )

    accessibility[
        "broken_elevator_stations"
    ] = (
        broken_or_blocked_stations
        if accessibility.get(
            "has_broken_elevator"
        ) is True
        else []
    )

    accessibility[
        "facility_failure_detected_stations"
    ] = broken_or_blocked_stations

    accessibility[
        "unknown_realtime_facilities"
    ] = unknown_realtime_facilities

    accessibility[
        "analyzed_internal_movement_count"
    ] = analyzed_movement_count

    accessibility[
        "unknown_internal_movement_count"
    ] = unknown_movement_count

    accessibility[
        "unavailable_internal_movement_count"
    ] = unavailable_movement_count

    accessibility[
        "unknown_fields"
    ] = list(
        dict.fromkeys(
            unknown_fields
        )
    )

    accessibility[
        "unavailable_reasons"
    ] = list(
        dict.fromkeys(
            unavailable_reasons
        )
    )

    if unavailable_movement_count > 0:

        accessibility[
            "status"
        ] = "INTERNAL_PATH_UNAVAILABLE"

    elif (
        analyzed_movement_count > 0
        and unknown_movement_count == 0
        and not unknown_realtime_facilities
    ):

        accessibility[
            "status"
        ] = "REALTIME_ANALYZED"

    elif analyzed_movement_count > 0:

        accessibility[
            "status"
        ] = "PARTIALLY_REALTIME_ANALYZED"

    else:
        accessibility.setdefault(
            "status",
            "UNKNOWN",
        )

    analyzed_route[
        "accessibility"
    ] = accessibility

    return analyzed_route


# ==============================================================================
# 8. 접근성 데이터 읽기
# ==============================================================================

def get_accessibility_data(
    route: dict[str, Any],
) -> dict[str, Any]:
    accessibility = route.get(
        "accessibility"
    )

    if not isinstance(
        accessibility,
        dict,
    ):
        accessibility = {}

    max_incline = accessibility.get(
        "max_incline"
    )

    if max_incline is None:
        max_incline = accessibility.get(
            "incline"
        )

    max_curb_height = accessibility.get(
        "max_curb_height"
    )

    if max_curb_height is None:
        max_curb_height = accessibility.get(
            "curb_height"
        )

    unknown_fields = accessibility.get(
        "unknown_fields",
        [],
    )

    if not isinstance(
        unknown_fields,
        list,
    ):
        unknown_fields = []

    unavailable_reasons = accessibility.get(
        "unavailable_reasons",
        [],
    )

    if not isinstance(
        unavailable_reasons,
        list,
    ):
        unavailable_reasons = []

    return {
        "status": accessibility.get(
            "status",
            "UNKNOWN",
        ),

        "internal_path_available": (
            accessibility.get(
                "internal_path_available"
            )
        ),

        "internal_paths": (
            accessibility.get(
                "internal_paths",
                [],
            )
        ),

        "required_facilities": (
            accessibility.get(
                "required_facilities",
                [],
            )
        ),

        "required_facility_count": (
            accessibility.get(
                "required_facility_count",
                0,
            )
        ),

        "required_elevator_count": (
            accessibility.get(
                "required_elevator_count",
                0,
            )
        ),

        "required_escalator_count": (
            accessibility.get(
                "required_escalator_count",
                0,
            )
        ),

        "blocked_facility_ids": (
            accessibility.get(
                "blocked_facility_ids",
                [],
            )
        ),

        "rerouted_due_to_facility_failure": (
            accessibility.get(
                "rerouted_due_to_facility_failure",
                False,
            )
        ),

        "has_broken_elevator": (
            accessibility.get(
                "has_broken_elevator"
            )
        ),

        "broken_elevator_stations": (
            accessibility.get(
                "broken_elevator_stations",
                [],
            )
        ),

        "has_elevator": (
            accessibility.get(
                "has_elevator"
            )
        ),

        "has_stairs": (
            accessibility.get(
                "has_stairs"
            )
        ),

        "max_incline": max_incline,

        "has_steep_slope": (
            accessibility.get(
                "has_steep_slope"
            )
        ),

        "max_curb_height": (
            max_curb_height
        ),

        "has_low_floor_bus": (
            accessibility.get(
                "has_low_floor_bus"
            )
        ),

        "low_floor_bus_numbers": (
            accessibility.get(
                "low_floor_bus_numbers",
                [],
            )
        ),

        "station_facilities": (
            accessibility.get(
                "station_facilities",
                [],
            )
        ),

        "facility_summary": (
            accessibility.get(
                "facility_summary",
                {},
            )
        ),

        "unknown_fields": (
            unknown_fields
        ),

        "unavailable_reasons": (
            unavailable_reasons
        ),
    }


# ==============================================================================
# 9. Hard Barrier 검사
# ==============================================================================

def check_hard_barriers(
    route: dict[str, Any],
    user_type: str,
) -> list[str]:
    config = USER_CONFIGS[
        user_type
    ]

    accessibility = (
        get_accessibility_data(
            route
        )
    )

    exclusion_reasons: list[
        str
    ] = []

    for reason in accessibility[
        "unavailable_reasons"
    ]:
        if (
            reason
            and reason
            not in exclusion_reasons
        ):
            exclusion_reasons.append(
                str(
                    reason
                )
            )

    # --------------------------------------------------------------------------
    # 역 내부 경로 자체가 이용 불가능
    # --------------------------------------------------------------------------

    if (
        accessibility[
            "internal_path_available"
        ] is False
    ):
        _append_unique(
            exclusion_reasons,
            (
                "역 내부에서 사용자 유형에 맞는 "
                "이동 동선을 확보할 수 없습니다."
            ),
        )

    # --------------------------------------------------------------------------
    # 계단
    # --------------------------------------------------------------------------

    has_stairs = accessibility[
        "has_stairs"
    ]

    if (
        has_stairs is True
        and not config[
            "allow_stairs"
        ]
    ):
        _append_unique(
            exclusion_reasons,
            "계단이 포함된 경로입니다.",
        )

    # --------------------------------------------------------------------------
    # 경사도
    # --------------------------------------------------------------------------

    max_incline = accessibility[
        "max_incline"
    ]

    if max_incline is not None:

        incline_value = (
            _safe_number(
                max_incline
            )
        )

        if (
            incline_value
            >= config[
                "max_incline"
            ]
        ):
            _append_unique(
                exclusion_reasons,
                (
                    "허용 기준을 초과하는 경사가 "
                    "포함되어 있습니다. "
                    f"({incline_value:.1f}% 이상)"
                ),
            )

    elif (
        accessibility[
            "has_steep_slope"
        ] is True
    ):
        _append_unique(
            exclusion_reasons,
            "급경사 구간이 포함되어 있습니다.",
        )

    # --------------------------------------------------------------------------
    # 보도 턱
    # --------------------------------------------------------------------------

    max_curb_height = (
        accessibility[
            "max_curb_height"
        ]
    )

    if max_curb_height is not None:

        curb_value = (
            _safe_number(
                max_curb_height
            )
        )

        if (
            curb_value
            > config[
                "max_curb"
            ]
        ):
            _append_unique(
                exclusion_reasons,
                (
                    "허용 기준보다 높은 보도 턱이 "
                    "포함되어 있습니다. "
                    f"({curb_value:.1f}cm)"
                ),
            )

    # --------------------------------------------------------------------------
    # 우회 불가능한 승강기 고장
    # --------------------------------------------------------------------------

    if (
        config[
            "broken_elevator_is_barrier"
        ]
        and accessibility[
            "has_broken_elevator"
        ] is True
    ):

        broken_stations = (
            accessibility.get(
                "broken_elevator_stations",
                [],
            )
        )

        if broken_stations:

            station_text = ", ".join(
                str(
                    station
                )
                for station
                in broken_stations
            )

            _append_unique(
                exclusion_reasons,
                (
                    "이용 동선의 승강기 고장으로 "
                    "대체 내부 경로를 확보하지 못했습니다: "
                    f"{station_text}"
                ),
            )

        else:
            _append_unique(
                exclusion_reasons,
                (
                    "이용 동선의 승강기 고장으로 "
                    "안전한 이동 경로를 확보하지 못했습니다."
                ),
            )

    # --------------------------------------------------------------------------
    # ★ 휠체어 + 버스 → 저상버스가 '확인된 경우에만' 허용
    #
    # 이전:
    # has_low_floor_bus is False → 제외
    #
    # 수정:
    # has_low_floor_bus is not True → 제외
    #
    # 따라서 None(미확인)도 휠체어 사용자에게는 제외됩니다.
    # --------------------------------------------------------------------------

    if (
        config[
            "require_low_floor_bus"
        ]
        and _route_uses_bus(
            route
        )
        and accessibility[
            "has_low_floor_bus"
        ] is not True
    ):
        _append_unique(
            exclusion_reasons,
            (
                "휠체어 이용이 가능한 저상버스로 "
                "확인되지 않은 경로입니다."
            ),
        )

    return list(
        dict.fromkeys(
            exclusion_reasons
        )
    )


# ==============================================================================
# 10. 정보 미확인 항목
# ==============================================================================

def find_unknown_fields(
    route: dict[str, Any],
) -> list[str]:
    accessibility = (
        get_accessibility_data(
            route
        )
    )

    unknown_fields: list[
        str
    ] = list(
        accessibility[
            "unknown_fields"
        ]
    )

    if (
        accessibility[
            "has_stairs"
        ] is None
    ):
        _append_unique(
            unknown_fields,
            "계단 여부",
        )

    if (
        accessibility[
            "max_incline"
        ] is None
        and accessibility[
            "has_steep_slope"
        ] is None
    ):
        _append_unique(
            unknown_fields,
            "경사도",
        )

    if (
        accessibility[
            "max_curb_height"
        ] is None
    ):
        _append_unique(
            unknown_fields,
            "보도 턱 높이",
        )

    if (
        _route_uses_bus(
            route
        )
        and accessibility[
            "has_low_floor_bus"
        ] is None
    ):
        _append_unique(
            unknown_fields,
            "저상버스 여부",
        )

    if _route_uses_subway(
        route
    ):

        if (
            accessibility[
                "has_elevator"
            ] is None
        ):
            _append_unique(
                unknown_fields,
                "엘리베이터 설치 여부",
            )

        if (
            accessibility[
                "has_broken_elevator"
            ] is None
        ):
            _append_unique(
                unknown_fields,
                "엘리베이터 고장 여부",
            )

    return list(
        dict.fromkeys(
            unknown_fields
        )
    )


# ==============================================================================
# 11. 후보 경로 점수 계산
# ==============================================================================

def calculate_route_score(
    route: dict[str, Any],
    user_type: str,
) -> tuple[
    float,
    list[str],
    list[str],
]:
    config = USER_CONFIGS[
        user_type
    ]

    weights = config[
        "weights"
    ]

    accessibility = (
        get_accessibility_data(
            route
        )
    )

    score = 0.0

    positive_reasons: list[
        str
    ] = []

    total_time_minutes = (
        _safe_number(
            route.get(
                "total_time_minutes"
            ),
            default=0.0,
        )
    )

    score += (
        total_time_minutes
        * weights[
            "time_per_min"
        ]
    )

    (
        walk_distance,
        found_walk_step,
    ) = calculate_walk_distance(
        route
    )

    score += (
        walk_distance
        * weights[
            "walk_dist_per_m"
        ]
    )

    if (
        walk_distance <= 300
        and found_walk_step
    ):
        positive_reasons.append(
            "보행 구간이 비교적 짧습니다."
        )

    transfer_count = int(
        _safe_number(
            route.get(
                "transfer_count"
            ),
            default=0.0,
        )
    )

    score += (
        transfer_count
        * weights[
            "transfer_penalty"
        ]
    )

    if transfer_count == 0:
        positive_reasons.append(
            "환승 없이 이동할 수 있습니다."
        )

    elif transfer_count == 1:
        positive_reasons.append(
            "환승 횟수가 1회로 비교적 적습니다."
        )

    if (
        accessibility[
            "has_elevator"
        ] is True
    ):
        score += (
            weights[
                "elevator_bonus"
            ]
        )

        positive_reasons.append(
            "실제 이용 동선에서 엘리베이터를 "
            "사용할 수 있습니다."
        )

    if (
        accessibility[
            "rerouted_due_to_facility_failure"
        ] is True
    ):
        positive_reasons.append(
            "운행 불가 승강설비를 피해 "
            "대체 역사 내부 동선을 찾았습니다."
        )

    if (
        _route_uses_bus(
            route
        )
        and accessibility[
            "has_low_floor_bus"
        ] is True
    ):

        score += (
            weights[
                "low_floor_bus_bonus"
            ]
        )

        low_floor_bus_numbers = (
            accessibility.get(
                "low_floor_bus_numbers",
                [],
            )
        )

        if low_floor_bus_numbers:

            bus_text = ", ".join(
                str(
                    number
                )
                for number
                in low_floor_bus_numbers
            )

            positive_reasons.append(
                f"저상버스({bus_text})를 "
                "이용할 수 있습니다."
            )

        else:
            positive_reasons.append(
                "저상버스를 이용할 수 있습니다."
            )

    if (
        accessibility[
            "has_stairs"
        ] is False
    ):
        positive_reasons.append(
            "계단이 없는 경로로 확인되었습니다."
        )

    max_incline = accessibility[
        "max_incline"
    ]

    if max_incline is not None:

        incline_value = (
            _safe_number(
                max_incline
            )
        )

        if (
            incline_value
            < config[
                "max_incline"
            ]
        ):
            positive_reasons.append(
                (
                    "사용자 유형의 허용 기준 이내인 "
                    f"경사도입니다. "
                    f"({incline_value:.1f}%)"
                )
            )

    max_curb_height = (
        accessibility[
            "max_curb_height"
        ]
    )

    if max_curb_height is not None:

        curb_value = (
            _safe_number(
                max_curb_height
            )
        )

        if (
            curb_value
            <= config[
                "max_curb"
            ]
        ):
            positive_reasons.append(
                (
                    "보도 턱 높이가 사용자 기준 "
                    "이내입니다."
                )
            )

    unknown_fields = (
        find_unknown_fields(
            route
        )
    )

    score += (
        len(
            unknown_fields
        )
        * weights[
            "unknown_data_penalty"
        ]
    )

    final_score = max(
        round(
            score,
            2,
        ),
        0.1,
    )

    return (
        final_score,

        list(
            dict.fromkeys(
                positive_reasons
            )
        ),

        unknown_fields,
    )


# ==============================================================================
# 12. 후보 경로 하나 평가
# ==============================================================================

def evaluate_candidate_route(
    route: dict[str, Any],
    user_type: str,
) -> dict[str, Any]:
    user_type = (
        _normalize_user_type(
            user_type
        )
    )

    if user_type not in USER_CONFIGS:

        supported_types = ", ".join(
            USER_CONFIGS.keys()
        )

        raise ValueError(
            f"지원하지 않는 사용자 유형입니다: "
            f"{user_type}. "
            f"지원 유형: {supported_types}"
        )

    evaluated_route = (
        attach_facility_accessibility(
            route
        )
    )

    evaluated_route = (
        attach_realtime_internal_accessibility(
            route=evaluated_route,
            user_type=user_type,
        )
    )

    exclusion_reasons = (
        check_hard_barriers(
            evaluated_route,
            user_type,
        )
    )

    is_available = (
        len(
            exclusion_reasons
        )
        == 0
    )

    if is_available:

        (
            score,
            positive_reasons,
            unknown_fields,
        ) = calculate_route_score(
            evaluated_route,
            user_type,
        )

    else:

        score = None
        positive_reasons = []

        unknown_fields = (
            find_unknown_fields(
                evaluated_route
            )
        )

    evaluated_route[
        "evaluation"
    ] = {
        "is_available": (
            is_available
        ),

        "score": score,

        "is_recommended": False,

        "positive_reasons": (
            positive_reasons
        ),

        "exclusion_reasons": (
            exclusion_reasons
        ),

        "unknown_fields": (
            unknown_fields
        ),

        "has_unknown_accessibility_data": (
            bool(
                unknown_fields
            )
        ),
    }

    walk_distance, _ = (
        calculate_walk_distance(
            evaluated_route
        )
    )

    evaluated_route[
        "total_walk_distance_meters"
    ] = walk_distance

    return evaluated_route


# ==============================================================================
# 13. 모든 후보 경로 평가
# ==============================================================================

def evaluate_all_candidates(
    routes: list[dict[str, Any]],
    user_type: str,
) -> list[dict[str, Any]]:
    user_type = (
        _normalize_user_type(
            user_type
        )
    )

    routes_copy = [
        deepcopy(
            route
        )
        for route in routes
    ]

    needs_movement_attachment = any(
        not isinstance(
            route.get(
                "station_movements"
            ),
            list,
        )
        for route in routes_copy
    )

    if needs_movement_attachment:

        routes_with_movements = (
            attach_station_movements(
                routes_copy
            )
        )

    else:

        routes_with_movements = (
            routes_copy
        )

    return [
        evaluate_candidate_route(
            route=route,
            user_type=user_type,
        )
        for route
        in routes_with_movements
    ]


# ==============================================================================
# 14. 최적 후보 경로 선택
# ==============================================================================

def select_best_candidate(
    routes: list[dict[str, Any]],
    user_type: str,
) -> dict[str, Any]:
    user_type = (
        _normalize_user_type(
            user_type
        )
    )

    if user_type not in USER_CONFIGS:

        supported_types = ", ".join(
            USER_CONFIGS.keys()
        )

        raise ValueError(
            f"지원하지 않는 사용자 유형입니다: "
            f"{user_type}. "
            f"지원 유형: {supported_types}"
        )

    evaluated_routes = (
        evaluate_all_candidates(
            routes=routes,
            user_type=user_type,
        )
    )

    available_routes = [
        route
        for route
        in evaluated_routes
        if route[
            "evaluation"
        ][
            "is_available"
        ]
    ]

    excluded_routes = [
        {
            "route_id": (
                route.get(
                    "route_id"
                )
            ),

            "route_type": (
                route.get(
                    "route_type"
                )
            ),

            "exclusion_reasons": (
                route[
                    "evaluation"
                ][
                    "exclusion_reasons"
                ]
            ),

            "unknown_fields": (
                route[
                    "evaluation"
                ][
                    "unknown_fields"
                ]
            ),

            "accessibility_status": (
                route.get(
                    "accessibility",
                    {},
                ).get(
                    "status",
                    "UNKNOWN",
                )
            ),
        }

        for route
        in evaluated_routes

        if not route[
            "evaluation"
        ][
            "is_available"
        ]
    ]

    if not available_routes:

        return {
            "user_type": user_type,

            "user_type_name": (
                USER_CONFIGS[
                    user_type
                ][
                    "name"
                ]
            ),

            "recommended_route": None,

            "alternative_routes": [],

            "excluded_routes": (
                excluded_routes
            ),

            "message": (
                "해당 사용자 유형으로 "
                "안전하게 이용할 수 있는 "
                "경로를 찾지 못했습니다."
            ),

            "summary": {
                "total_candidate_count": (
                    len(
                        evaluated_routes
                    )
                ),

                "available_route_count": 0,

                "excluded_route_count": (
                    len(
                        excluded_routes
                    )
                ),
            },
        }

    available_routes.sort(
        key=lambda route: (
            _safe_number(
                route[
                    "evaluation"
                ].get(
                    "score"
                ),
                default=float(
                    "inf"
                ),
            ),

            _safe_number(
                route.get(
                    "total_time_minutes"
                ),
                default=float(
                    "inf"
                ),
            ),

            _safe_number(
                route.get(
                    "transfer_count"
                ),
                default=float(
                    "inf"
                ),
            ),

            _safe_number(
                route.get(
                    "total_distance_meters"
                ),
                default=float(
                    "inf"
                ),
            ),
        )
    )

    recommended_route = (
        available_routes[
            0
        ]
    )

    recommended_route[
        "evaluation"
    ][
        "is_recommended"
    ] = True

    alternative_routes = (
        available_routes[
            1:
        ]
    )

    return {
        "user_type": user_type,

        "user_type_name": (
            USER_CONFIGS[
                user_type
            ][
                "name"
            ]
        ),

        "recommended_route": (
            recommended_route
        ),

        "alternative_routes": (
            alternative_routes
        ),

        "excluded_routes": (
            excluded_routes
        ),

        "summary": {
            "total_candidate_count": (
                len(
                    evaluated_routes
                )
            ),

            "available_route_count": (
                len(
                    available_routes
                )
            ),

            "excluded_route_count": (
                len(
                    excluded_routes
                )
            ),
        },
    }