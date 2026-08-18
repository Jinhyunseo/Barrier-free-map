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

from app.services.bus_matching_service import (
    match_bus_step_identifiers,
)

from app.services.bus_arrival_service import (
    get_low_floor_bus_status,
)
from app.services.walking_accessibility_service import (
    attach_walking_accessibility,
)

from app.services.gemini_recommendation_service import (
    generate_route_ai_text,
)

# ==============================================================================
# 1. 2차 프로토타입 추천 설정
# ==============================================================================

DEFAULT_MOBILITY_CONSTRAINTS: dict[str, bool] = {
    "avoid_stairs": False,
    "require_elevator": False,
    "avoid_escalator": False,
    "avoid_steep_slope": False,
    "require_low_floor_bus": False,
}


SUPPORTED_ROUTE_PREFERENCES = {
    "BALANCED",
    "FASTEST",
    "MIN_WALKING",
    "MIN_TRANSFER",
}


PREFERENCE_WEIGHTS: dict[str, dict[str, float]] = {
    "BALANCED": {
        "time_per_min": 1.0,
        "walk_dist_per_m": 0.035,
        "transfer_penalty": 12.0,
        "unknown_data_penalty": 8.0,
    },
    "FASTEST": {
        "time_per_min": 1.0,
        "walk_dist_per_m": 0.005,
        "transfer_penalty": 2.0,
        "unknown_data_penalty": 8.0,
    },
    "MIN_WALKING": {
        "time_per_min": 0.25,
        "walk_dist_per_m": 0.10,
        "transfer_penalty": 5.0,
        "unknown_data_penalty": 8.0,
    },
    "MIN_TRANSFER": {
        "time_per_min": 0.35,
        "walk_dist_per_m": 0.01,
        "transfer_penalty": 35.0,
        "unknown_data_penalty": 8.0,
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
    except (TypeError, ValueError):
        return default


def _normalize_text(
    value: Any,
) -> str:
    if value is None:
        return ""

    return str(value).strip().lower()


def normalize_mobility_constraints(
    mobility_constraints: dict[str, Any] | None,
) -> dict[str, bool]:
    normalized = dict(DEFAULT_MOBILITY_CONSTRAINTS)

    if not isinstance(mobility_constraints, dict):
        return normalized

    for key in normalized:
        normalized[key] = bool(mobility_constraints.get(key, False))

    return normalized


def normalize_route_preference(
    route_preference: str | None,
) -> str:
    value = str(route_preference or "BALANCED").strip().upper()

    if value not in SUPPORTED_ROUTE_PREFERENCES:
        supported = ", ".join(sorted(SUPPORTED_ROUTE_PREFERENCES))
        raise ValueError(f"지원하지 않는 경로 선호도입니다: {value}. 지원 값: {supported}")

    return value


def _append_unique(
    target: list[str],
    value: str,
) -> None:
    if value and value not in target:
        target.append(value)


def _remove_value(
    target: list[str],
    value: str,
) -> None:
    while value in target:
        target.remove(value)


def _get_all_detected_slopes(route: dict[str, Any]) -> list[dict[str, Any]]:
    slopes: list[dict[str, Any]] = []

    top_level = route.get("detected_slopes", [])
    if isinstance(top_level, list):
        slopes.extend(s for s in top_level if isinstance(s, dict))

    walking_access = route.get("walking_access", {})
    if isinstance(walking_access, dict):
        for leg_key in ("first_mile", "last_mile"):
            leg = walking_access.get(leg_key, {})
            if not isinstance(leg, dict):
                continue
            leg_slopes = leg.get("detected_slopes", [])
            if isinstance(leg_slopes, list):
                slopes.extend(s for s in leg_slopes if isinstance(s, dict))

    return slopes


# ==============================================================================
# 3. 카카오 경로 유형 판단
# ==============================================================================

def _is_walk_step(step: dict[str, Any]) -> bool:
    step_type = _normalize_text(step.get("step_type"))
    walk_keywords = {"walk", "walking", "pedestrian", "foot", "도보"}

    if step_type in walk_keywords:
        return True

    return any(keyword in step_type for keyword in walk_keywords)


def _route_uses_bus(route: dict[str, Any]) -> bool:
    route_type = _normalize_text(route.get("route_type"))
    if "bus" in route_type or "버스" in route_type:
        return True

    for vehicle in route.get("vehicles", []):
        if not isinstance(vehicle, dict):
            continue
        vehicle_type = _normalize_text(vehicle.get("type"))
        vehicle_name = _normalize_text(vehicle.get("name"))
        if "bus" in vehicle_type or "버스" in vehicle_type or "bus" in vehicle_name or "버스" in vehicle_name:
            return True

    for step in route.get("steps", []):
        if not isinstance(step, dict):
            continue
        step_type = _normalize_text(step.get("step_type"))
        if "bus" in step_type or "버스" in step_type:
            return True

    return False


def _route_uses_subway(route: dict[str, Any]) -> bool:
    route_type = _normalize_text(route.get("route_type"))
    subway_keywords = {"subway", "metro", "rail", "지하철", "전철"}

    if any(keyword in route_type for keyword in subway_keywords):
        return True

    for vehicle in route.get("vehicles", []):
        if not isinstance(vehicle, dict):
            continue
        vehicle_type = _normalize_text(vehicle.get("type"))
        vehicle_name = _normalize_text(vehicle.get("name"))
        if any((keyword in vehicle_type or keyword in vehicle_name) for keyword in subway_keywords):
            return True

    for step in route.get("steps", []):
        if not isinstance(step, dict):
            continue
        step_type = _normalize_text(step.get("step_type"))
        if any(keyword in step_type for keyword in subway_keywords):
            return True

    return False


# ==============================================================================
# 4. 보행거리 및 시간 계산
# ==============================================================================

def calculate_walk_distance(route: dict[str, Any]) -> tuple[int, bool]:
    walk_distance = 0
    found_walk_step = False

    for step in route.get("steps", []):
        if not isinstance(step, dict) or not _is_walk_step(step):
            continue
        found_walk_step = True
        distance = _safe_number(step.get("distance"), default=0.0)
        walk_distance += int(round(distance))

    access_walk_distance = _safe_number(route.get("access_walk_distance_meters"), default=0.0)
    if access_walk_distance > 0:
        found_walk_step = True
        walk_distance += int(round(access_walk_distance))

    return walk_distance, found_walk_step


def calculate_total_travel_time(route: dict[str, Any]) -> tuple[int, float]:
    total_time_seconds = int(round(_safe_number(route.get("total_time_seconds"), default=0.0)))

    if total_time_seconds <= 0:
        total_time_minutes = _safe_number(route.get("total_time_minutes"), default=0.0)
        total_time_seconds = int(round(total_time_minutes * 60))

    total_time_minutes = round(total_time_seconds / 60, 1)
    return total_time_seconds, total_time_minutes


# ==============================================================================
# 5. 역사 시설 및 기본 접근성 데이터
# ==============================================================================

def _extract_station_line_pairs(route: dict[str, Any]) -> list[dict[str, str]]:
    movements = route.get("station_movements", [])
    if not isinstance(movements, list):
        return []

    pairs = []
    seen = set()

    for movement in movements:
        if not isinstance(movement, dict):
            continue
        movement_type = str(movement.get("movement_type", "")).strip().upper()
        station_name = movement.get("station_name")
        if not station_name:
            continue

        station_name = str(station_name).strip()
        line_names = []

        if movement_type in {"BOARDING", "ALIGHTING"}:
            line_name = movement.get("line_name")
            if line_name:
                line_names.append(str(line_name).strip())
        elif movement_type == "TRANSFER":
            from_line = movement.get("from_line")
            to_line = movement.get("to_line")
            if from_line:
                line_names.append(str(from_line).strip())
            if to_line:
                line_names.append(str(to_line).strip())

        for line_name in line_names:
            if not line_name:
                continue
            key = (station_name, line_name)
            if key in seen:
                continue
            seen.add(key)
            pairs.append({"station_name": station_name, "line_name": line_name})

    return pairs


def collect_station_facilities(route: dict[str, Any]) -> list[dict[str, Any]]:
    station_line_pairs = _extract_station_line_pairs(route)
    results = []
    for pair in station_line_pairs:
        facility_data = get_station_facilities(
            station_name=pair["station_name"],
            line_name=pair["line_name"],
        )
        results.append(facility_data)
    return results


def attach_facility_accessibility(route: dict[str, Any]) -> dict[str, Any]:
    analyzed_route = deepcopy(route)
    existing_accessibility = analyzed_route.get("accessibility")
    if not isinstance(existing_accessibility, dict):
        existing_accessibility = {}

    accessibility = deepcopy(existing_accessibility)
    station_facilities = collect_station_facilities(analyzed_route)

    successful_facilities = [f for f in station_facilities if f.get("status") == "SUCCESS"]
    failed_facilities = [f for f in station_facilities if f.get("status") != "SUCCESS"]

    elevator_count = sum(int(f.get("elevator_count", 0) or 0) for f in successful_facilities)
    escalator_count = sum(int(f.get("escalator_count", 0) or 0) for f in successful_facilities)

    if _route_uses_subway(analyzed_route):
        if not station_facilities or failed_facilities:
            has_elevator = None
        else:
            has_elevator = all(int(f.get("elevator_count", 0) or 0) > 0 for f in successful_facilities)
    else:
        has_elevator = None

    unknown_fields = accessibility.get("unknown_fields", [])
    if not isinstance(unknown_fields, list):
        unknown_fields = []
    unknown_fields = list(unknown_fields)

    if _route_uses_subway(analyzed_route):
        _append_unique(unknown_fields, "엘리베이터 고장 여부")
    if failed_facilities:
        _append_unique(unknown_fields, "일부 역사 시설 정보")

    accessibility["has_elevator"] = has_elevator
    accessibility["has_broken_elevator"] = None
    accessibility["broken_elevator_stations"] = []
    accessibility["station_facilities"] = station_facilities
    accessibility["facility_summary"] = {
        "station_line_count": len(station_facilities),
        "successful_station_line_count": len(successful_facilities),
        "failed_station_line_count": len(failed_facilities),
        "total_elevator_count": elevator_count,
        "total_escalator_count": escalator_count,
    }
    accessibility["unknown_fields"] = list(dict.fromkeys(unknown_fields))
    accessibility["status"] = "FACILITY_ANALYZED" if station_facilities else accessibility.get("status", "UNKNOWN")

    analyzed_route["accessibility"] = accessibility
    return analyzed_route


def attach_facility_accessibility_to_routes(routes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [attach_facility_accessibility(route) for route in routes]


# ==============================================================================
# 7. 실시간 역 내부 동선 및 버스 접근성 분석
# ==============================================================================

def _station_graph_exists(station_name: str) -> bool:
    try:
        graph = get_station_graph(station_name)
    except (FileNotFoundError, ValueError):
        return False
    return isinstance(graph, dict)


def attach_realtime_internal_accessibility(
    route: dict[str, Any],
    mobility_constraints: dict[str, Any] | None,
) -> dict[str, Any]:
    constraints = normalize_mobility_constraints(mobility_constraints)
    analyzed_route = deepcopy(route)

    accessibility = analyzed_route.get("accessibility", {})
    if not isinstance(accessibility, dict):
        accessibility = {}
    accessibility = deepcopy(accessibility)

    movements = analyzed_route.get("station_movements", [])
    if not isinstance(movements, list):
        movements = []

    internal_paths = []
    analyzed_movement_count = 0
    unknown_movement_count = 0
    unavailable_movement_count = 0

    required_facilities = []
    blocked_facility_ids = []
    broken_or_blocked_stations = []
    unknown_realtime_facilities = []

    unavailable_reasons = list(accessibility.get("unavailable_reasons", []))
    unknown_fields = list(accessibility.get("unknown_fields", []))

    for movement in movements:
        if not isinstance(movement, dict):
            continue
        station_name = str(movement.get("station_name", "")).strip()
        if not station_name:
            continue

        if not _station_graph_exists(station_name):
            unknown_movement_count += 1
            internal_paths.append({
                "status": "GRAPH_NOT_AVAILABLE",
                "station_name": station_name,
                "movement": movement,
                "message": "해당 역의 내부 이동 그래프가 구축되지 않았습니다.",
            })
            _append_unique(unknown_fields, f"{station_name} 내부 이동 동선")
            continue

        try:
            result = find_realtime_safe_internal_path(
                movement=movement,
                mobility_constraints=constraints,
            )
        except Exception as error:
            unknown_movement_count += 1
            internal_paths.append({
                "status": "ANALYSIS_ERROR",
                "station_name": station_name,
                "movement": movement,
                "message": str(error),
            })
            _append_unique(unknown_fields, f"{station_name} 내부 이동 동선")
            continue

        internal_paths.append(result)
        status = str(result.get("status", "UNKNOWN")).upper()

        if status == "SUCCESS":
            analyzed_movement_count += 1
            facilities = result.get("required_facilities", [])
            if isinstance(facilities, list):
                required_facilities.extend([f for f in facilities if isinstance(f, dict)])

            blocked_ids = result.get("blocked_edge_ids", [])
            if isinstance(blocked_ids, list):
                for edge_id in blocked_ids:
                    edge_text = str(edge_id).strip()
                    if edge_text and edge_text not in blocked_facility_ids:
                        blocked_facility_ids.append(edge_text)
                if blocked_ids and station_name not in broken_or_blocked_stations:
                    broken_or_blocked_stations.append(station_name)

            if result.get("has_unknown_facility_status") is True:
                _append_unique(unknown_fields, f"{station_name} 일부 승강설비 실시간 상태")

        elif status in {"REALTIME_PATH_NOT_FOUND", "PATH_NOT_FOUND", "MAX_RETRY_EXCEEDED"}:
            unavailable_movement_count += 1
            _append_unique(unavailable_reasons, f"{station_name}에서 선택한 이동 조건을 만족하는 역 내부 이동 동선을 찾지 못했습니다.")

    elevator_facilities = [f for f in required_facilities if str(f.get("facility_type", "")).upper() == "ELEVATOR"]
    escalator_facilities = [f for f in required_facilities if str(f.get("facility_type", "")).upper() == "ESCALATOR"]

    if analyzed_movement_count > 0:
        if elevator_facilities:
            accessibility["has_elevator"] = True
        elif _route_uses_subway(analyzed_route):
            accessibility.setdefault("has_elevator", None)

    if unavailable_movement_count > 0:
        accessibility["has_broken_elevator"] = True if blocked_facility_ids else None
    elif analyzed_movement_count > 0 and not unknown_realtime_facilities:
        accessibility["has_broken_elevator"] = False

    internal_path_available = False if unavailable_movement_count > 0 else (True if (analyzed_movement_count > 0 and unknown_movement_count == 0) else None)

    accessibility["internal_path_available"] = internal_path_available
    accessibility["internal_paths"] = internal_paths
    accessibility["required_facilities"] = required_facilities
    accessibility["required_facility_count"] = len(required_facilities)
    accessibility["required_elevator_count"] = len(elevator_facilities)
    accessibility["required_escalator_count"] = len(escalator_facilities)
    accessibility["blocked_facility_ids"] = blocked_facility_ids
    accessibility["rerouted_due_to_facility_failure"] = bool(blocked_facility_ids and unavailable_movement_count == 0)
    accessibility["broken_elevator_stations"] = broken_or_blocked_stations if accessibility.get("has_broken_elevator") is True else []
    accessibility["mobility_constraints"] = constraints
    accessibility["unknown_fields"] = list(dict.fromkeys(unknown_fields))
    accessibility["unavailable_reasons"] = list(dict.fromkeys(unavailable_reasons))

    if unavailable_movement_count > 0:
        accessibility["status"] = "INTERNAL_PATH_UNAVAILABLE"
    elif analyzed_movement_count > 0 and unknown_movement_count == 0 and not unknown_realtime_facilities:
        accessibility["status"] = "REALTIME_ANALYZED"
    elif analyzed_movement_count > 0:
        accessibility["status"] = "PARTIALLY_REALTIME_ANALYZED"

    analyzed_route["accessibility"] = accessibility
    return analyzed_route


async def attach_realtime_bus_accessibility(route: dict[str, Any]) -> dict[str, Any]:
    analyzed_route = deepcopy(route)
    accessibility = deepcopy(analyzed_route.get("accessibility", {}))
    steps = analyzed_route.get("steps", [])
    unknown_fields = list(accessibility.get("unknown_fields", []))

    bus_results = []
    low_floor_bus_numbers = []
    bus_step_count = 0
    available_step_count = 0
    unavailable_step_count = 0
    unknown_step_count = 0

    for step in steps:
        if not isinstance(step, dict) or str(step.get("step_type", "")).strip().upper() != "BUS":
            continue

        bus_step_count += 1
        try:
            identifier_result = match_bus_step_identifiers(step)
        except Exception as error:
            unknown_step_count += 1
            bus_results.append({
                "step_id": step.get("step_id"),
                "status": "IDENTIFIER_MATCH_ERROR",
                "message": str(error),
                "station_id": None,
                "routes": [],
            })
            continue

        station_id = identifier_result.get("station_id")
        route_matches = identifier_result.get("routes", [])

        step_result = {
            "step_id": step.get("step_id"),
            "boarding_stop_name": identifier_result.get("boarding_stop_name"),
            "station_id": station_id,
            "station_match": identifier_result.get("station_match"),
            "routes": [],
        }

        if not station_id:
            unknown_step_count += 1
            step_result["status"] = "STATION_ID_NOT_FOUND"
            bus_results.append(step_result)
            continue

        step_available = False
        step_confirmed_no_low_floor = False
        step_unknown = False

        for route_match in route_matches:
            if not isinstance(route_match, dict):
                continue
            bus_number = str(route_match.get("bus_number", "")).strip()
            route_id = route_match.get("route_id")

            route_result = {
                "bus_number": bus_number,
                "route_id": route_id,
                "route_match_status": route_match.get("route_match_status"),
                "realtime": None,
            }

            if not route_id:
                step_unknown = True
                route_result["realtime"] = {"status": "ROUTE_ID_NOT_FOUND", "low_floor_bus_available": None}
                step_result["routes"].append(route_result)
                continue

            try:
                realtime = await get_low_floor_bus_status(
                    station_id=str(station_id),
                    route_id=str(route_id),
                    bus_number=bus_number or None,
                )
            except Exception as error:
                step_unknown = True
                route_result["realtime"] = {"status": "API_ERROR", "message": str(error), "low_floor_bus_available": None}
                step_result["routes"].append(route_result)
                continue

            route_result["realtime"] = realtime
            realtime_status = str(realtime.get("status", "UNKNOWN")).upper()
            low_floor_available = realtime.get("low_floor_bus_available")

            if realtime_status == "AVAILABLE" and low_floor_available is True:
                step_available = True
                if bus_number and bus_number not in low_floor_bus_numbers:
                    low_floor_bus_numbers.append(bus_number)
            elif realtime_status == "NO_LOW_FLOOR_BUS" and low_floor_available is False:
                step_confirmed_no_low_floor = True
            else:
                step_unknown = True

            step_result["routes"].append(route_result)

        if step_available:
            available_step_count += 1
            step_result["status"] = "LOW_FLOOR_AVAILABLE"
        elif step_confirmed_no_low_floor and not step_unknown:
            unavailable_step_count += 1
            step_result["status"] = "LOW_FLOOR_NOT_AVAILABLE"
        else:
            unknown_step_count += 1
            step_result["status"] = "LOW_FLOOR_UNKNOWN"

        bus_results.append(step_result)

    has_low_floor_bus = True if (bus_step_count > 0 and available_step_count == bus_step_count) else (False if unavailable_step_count > 0 else None)

    accessibility["has_low_floor_bus"] = has_low_floor_bus
    accessibility["low_floor_bus_numbers"] = low_floor_bus_numbers
    accessibility["bus_accessibility"] = bus_results
    accessibility["bus_step_count"] = bus_step_count

    if bus_step_count > 0 and has_low_floor_bus is None:
        _append_unique(unknown_fields, "저상버스 여부")
    elif bus_step_count > 0:
        _remove_value(unknown_fields, "저상버스 여부")

    accessibility["unknown_fields"] = list(dict.fromkeys(unknown_fields))
    analyzed_route["accessibility"] = accessibility
    return analyzed_route


# ==============================================================================
# 8. 접근성 데이터 읽기
# ==============================================================================

def get_accessibility_data(route: dict[str, Any]) -> dict[str, Any]:
    accessibility = route.get("accessibility")
    if not isinstance(accessibility, dict):
        accessibility = {}

    walking_accessibility = route.get("walking_accessibility", {})
    if not isinstance(walking_accessibility, dict):
        walking_accessibility = {}

    max_incline = accessibility.get("max_incline") or accessibility.get("incline")
    max_curb_height = accessibility.get("max_curb_height") or accessibility.get("curb_height")

    has_steep_slope = accessibility.get("has_steep_slope")
    if has_steep_slope is None:
        has_steep_slope = walking_accessibility.get("has_steep_slope")

    unknown_fields = list(accessibility.get("unknown_fields", []))
    unavailable_reasons = list(accessibility.get("unavailable_reasons", []))

    return {
        "status": accessibility.get("status", "UNKNOWN"),
        "internal_path_available": accessibility.get("internal_path_available"),
        "internal_paths": accessibility.get("internal_paths", []),
        "required_facilities": accessibility.get("required_facilities", []),
        "required_facility_count": accessibility.get("required_facility_count", 0),
        "required_elevator_count": accessibility.get("required_elevator_count", 0),
        "required_escalator_count": accessibility.get("required_escalator_count", 0),
        "blocked_facility_ids": accessibility.get("blocked_facility_ids", []),
        "rerouted_due_to_facility_failure": accessibility.get("rerouted_due_to_facility_failure", False),
        "has_broken_elevator": accessibility.get("has_broken_elevator"),
        "broken_elevator_stations": accessibility.get("broken_elevator_stations", []),
        "has_elevator": accessibility.get("has_elevator"),
        "has_stairs": accessibility.get("has_stairs"),
        "max_incline": max_incline,
        "has_steep_slope": has_steep_slope,
        "max_curb_height": max_curb_height,
        "has_low_floor_bus": accessibility.get("has_low_floor_bus"),
        "low_floor_bus_numbers": accessibility.get("low_floor_bus_numbers", []),
        "station_facilities": accessibility.get("station_facilities", []),
        "facility_summary": accessibility.get("facility_summary", {}),
        "unknown_fields": unknown_fields,
        "unavailable_reasons": unavailable_reasons,
    }


# ==============================================================================
# 9. Hard Barrier 검사
# ==============================================================================

def check_hard_barriers(
    route: dict[str, Any],
    mobility_constraints: dict[str, Any] | None,
) -> list[str]:
    constraints = normalize_mobility_constraints(mobility_constraints)
    accessibility = get_accessibility_data(route)
    exclusion_reasons = []

    for reason in accessibility["unavailable_reasons"]:
        if reason and reason not in exclusion_reasons:
            exclusion_reasons.append(str(reason))

    if accessibility["internal_path_available"] is False:
        _append_unique(exclusion_reasons, "선택한 이동 조건으로 이용 가능한 역 내부 이동 동선을 확보할 수 없습니다.")

    if constraints["avoid_stairs"] and accessibility["has_stairs"] is True:
        _append_unique(exclusion_reasons, "계단이 포함된 경로입니다.")

    walking_accessibility = route.get("walking_accessibility", {})
    if not isinstance(walking_accessibility, dict):
        walking_accessibility = {}

    if constraints["avoid_stairs"] and walking_accessibility.get("has_stairs") is True:
        _append_unique(exclusion_reasons, "보행 구간에 계단이 포함되어 있습니다.")

    if constraints["require_elevator"] and _route_uses_subway(route):
        if accessibility["internal_path_available"] is True and accessibility["has_elevator"] is False:
            _append_unique(exclusion_reasons, "필수 엘리베이터를 이용할 수 없는 경로입니다.")

    if constraints["avoid_escalator"]:
        required_facilities = accessibility["required_facilities"]
        if isinstance(required_facilities, list):
            uses_escalator = any(
                str(f.get("facility_type", "")).upper() == "ESCALATOR"
                for f in required_facilities if isinstance(f, dict)
            )
            if uses_escalator:
                _append_unique(exclusion_reasons, "에스컬레이터 이용이 필요한 경로입니다.")

    if constraints["require_low_floor_bus"] and _route_uses_bus(route) and accessibility["has_low_floor_bus"] is False:
        _append_unique(exclusion_reasons, "현재 도착 예정 차량 중 저상버스를 확인할 수 없는 버스 구간이 있습니다.")

    if accessibility["has_broken_elevator"] is True and accessibility["internal_path_available"] is False:
        broken_stations = accessibility.get("broken_elevator_stations", [])
        if broken_stations:
            station_text = ", ".join(str(s) for s in broken_stations)
            _append_unique(exclusion_reasons, f"승강설비 고장으로 대체 내부 경로를 확보하지 못했습니다: {station_text}")
        else:
            _append_unique(exclusion_reasons, "승강설비 고장으로 안전한 대체 이동 경로를 확보하지 못했습니다.")

    return list(dict.fromkeys(exclusion_reasons))


# ==============================================================================
# 10. 정보 미확인 항목 및 경로 점수 계산
# ==============================================================================

def find_unknown_fields(route: dict[str, Any]) -> list[str]:
    accessibility = get_accessibility_data(route)
    unknown_fields = list(accessibility["unknown_fields"])

    if accessibility["has_stairs"] is None:
        _append_unique(unknown_fields, "계단 여부")
    if accessibility["max_incline"] is None and accessibility["has_steep_slope"] is None:
        _append_unique(unknown_fields, "경사도")
    if accessibility["max_curb_height"] is None:
        _append_unique(unknown_fields, "보도 턱 높이")

    if _route_uses_subway(route):
        if accessibility["has_elevator"] is None:
            _append_unique(unknown_fields, "엘리베이터 설치 여부")
        if accessibility["has_broken_elevator"] is None:
            _append_unique(unknown_fields, "엘리베이터 고장 여부")

    return list(dict.fromkeys(unknown_fields))


def calculate_route_score(
    route: dict[str, Any],
    route_preference: str,
    mobility_constraints: dict[str, bool] | None = None,
) -> tuple[float, list[str], list[str]]:
    preference = normalize_route_preference(route_preference)
    weights = PREFERENCE_WEIGHTS[preference]
    accessibility = get_accessibility_data(route)
    constraints = normalize_mobility_constraints(mobility_constraints)

    score = 0.0
    positive_reasons = []

    _, total_time_minutes = calculate_total_travel_time(route)
    score += total_time_minutes * weights["time_per_min"]

    walk_distance, found_walk_step = calculate_walk_distance(route)
    score += walk_distance * weights["walk_dist_per_m"]

    transfer_count = int(_safe_number(route.get("transfer_count"), default=0.0))
    score += transfer_count * weights["transfer_penalty"]

    detected_slopes = _get_all_detected_slopes(route)
    has_steep_slope = accessibility["has_steep_slope"] is True or len(detected_slopes) > 0

    if constraints.get("avoid_steep_slope"):
        if has_steep_slope:
            max_slope_val = max([_safe_number(s.get("slope_degree"), default=8.0) for s in detected_slopes] or [8.0])
            score += 50.0 + (max_slope_val * 2.0)
        else:
            positive_reasons.append("급경사 구간을 회피하는 평탄한 경로입니다.")

    if preference == "FASTEST":
        positive_reasons.append("접근 가능한 후보 중 이동시간을 우선하여 평가했습니다.")
    elif preference == "MIN_WALKING":
        positive_reasons.append("접근 가능한 후보 중 도보 거리를 우선하여 평가했습니다.")
    elif preference == "MIN_TRANSFER":
        positive_reasons.append("접근 가능한 후보 중 환승 횟수를 우선하여 평가했습니다.")
    else:
        positive_reasons.append("이동시간, 도보 거리, 환승 횟수를 균형 있게 평가했습니다.")

    if walk_distance <= 300 and found_walk_step:
        positive_reasons.append("보행 구간이 비교적 짧습니다.")
    if transfer_count == 0:
        positive_reasons.append("환승 없이 이동할 수 있습니다.")
    elif transfer_count == 1:
        positive_reasons.append("환승 횟수가 1회로 비교적 적습니다.")

    if accessibility["has_elevator"] is True:
        positive_reasons.append("실제 역 내부 이동 동선에서 엘리베이터를 이용할 수 있습니다.")
    if accessibility["rerouted_due_to_facility_failure"] is True:
        positive_reasons.append("운행 불가 승강설비를 피해 대체 역사 내부 동선을 찾았습니다.")

    if _route_uses_bus(route) and accessibility["has_low_floor_bus"] is True:
        low_floor_bus_numbers = accessibility.get("low_floor_bus_numbers", [])
        if low_floor_bus_numbers:
            bus_text = ", ".join(str(n) for n in low_floor_bus_numbers)
            positive_reasons.append(f"저상버스({bus_text})를 이용할 수 있습니다.")
        else:
            positive_reasons.append("저상버스를 이용할 수 있습니다.")

    if accessibility["has_stairs"] is False:
        positive_reasons.append("계단이 없는 경로로 확인되었습니다.")
    if not has_steep_slope:
        positive_reasons.append("급경사 구간이 없는 경로로 확인되었습니다.")

    unknown_fields = find_unknown_fields(route)
    score += len(unknown_fields) * weights["unknown_data_penalty"]

    final_score = max(round(score, 2), 0.1)
    return final_score, list(dict.fromkeys(positive_reasons)), unknown_fields


# ==============================================================================
# 11. 후보 경로 평가 및 선택
# ==============================================================================

async def evaluate_candidate_route(
    route: dict[str, Any],
    mobility_constraints: dict[str, Any] | None,
    route_preference: str,
) -> dict[str, Any]:
    constraints = normalize_mobility_constraints(mobility_constraints)
    preference = normalize_route_preference(route_preference)

    evaluated_route = attach_facility_accessibility(route)
    evaluated_route = attach_realtime_internal_accessibility(
        route=evaluated_route,
        mobility_constraints=constraints,
    )

    if constraints["require_low_floor_bus"] and _route_uses_bus(evaluated_route):
        evaluated_route = await attach_realtime_bus_accessibility(evaluated_route)

    evaluated_route = attach_walking_accessibility(evaluated_route)

    total_travel_time_seconds, total_travel_time_minutes = calculate_total_travel_time(evaluated_route)
    evaluated_route["total_travel_time_seconds"] = total_travel_time_seconds
    evaluated_route["total_travel_time_minutes"] = total_travel_time_minutes

    exclusion_reasons = check_hard_barriers(evaluated_route, constraints)
    is_available = (len(exclusion_reasons) == 0)

    if is_available:
        score, positive_reasons, unknown_fields = calculate_route_score(evaluated_route, preference, constraints)
    else:
        score = None
        positive_reasons = []
        unknown_fields = find_unknown_fields(evaluated_route)

    evaluated_route["evaluation"] = {
        "is_available": is_available,
        "score": score,
        "is_recommended": False,
        "route_preference": preference,
        "mobility_constraints": constraints,
        "positive_reasons": positive_reasons,
        "exclusion_reasons": exclusion_reasons,
        "unknown_fields": unknown_fields,
        "has_unknown_accessibility_data": bool(unknown_fields),
    }

    walk_distance, _ = calculate_walk_distance(evaluated_route)
    evaluated_route["total_walk_distance_meters"] = walk_distance

    return evaluated_route


async def evaluate_all_candidates(
    routes: list[dict[str, Any]],
    mobility_constraints: dict[str, Any] | None,
    route_preference: str = "BALANCED",
) -> list[dict[str, Any]]:
    evaluated_routes = []
    for route in routes:
        evaluated = await evaluate_candidate_route(
            route=route,
            mobility_constraints=mobility_constraints,
            route_preference=route_preference,
        )
        evaluated_routes.append(evaluated)
    return evaluated_routes


async def select_best_candidate(
    routes: list[dict[str, Any]],
    mobility_constraints: dict[str, Any] | None,
    route_preference: str = "BALANCED",
) -> dict[str, Any]:
    constraints = normalize_mobility_constraints(mobility_constraints)
    preference = normalize_route_preference(route_preference)

    # 1. 모든 후보 경로 평가
    evaluated_routes = await evaluate_all_candidates(
        routes=routes,
        mobility_constraints=constraints,
        route_preference=preference,
    )

    available_routes = [
        r for r in evaluated_routes
        if isinstance(r.get("evaluation"), dict) and r["evaluation"].get("is_available", True)
    ]
    excluded_routes = [
        r for r in evaluated_routes
        if not (isinstance(r.get("evaluation"), dict) and r["evaluation"].get("is_available", True))
    ]

    if not available_routes:
        return {
            "mobility_constraints": constraints,
            "route_preference": preference,
            "recommended_route": None,
            "alternative_routes": [],
            "excluded_routes": excluded_routes,
            "detected_slopes": [],
            "has_steep_warning": False,
            "ai_reason": None,
            "slope_warning_message": None,
            "message": "선택한 이동 조건으로 이용 가능한 경로를 찾지 못했습니다.",
            "summary": {
                "total_candidate_count": len(evaluated_routes),
                "available_route_count": 0,
                "excluded_route_count": len(excluded_routes),
            },
        }

    # 2. '급경사 피하기' 옵션 활성화 여부 확인
    avoid_slope = constraints.get("avoid_steep_slope", False)

    # 3. 안전한 정렬 키 함수
    def get_sort_key(r: dict[str, Any]):
        eval_info = r.get("evaluation") if isinstance(r.get("evaluation"), dict) else {}
        score = _safe_number(eval_info.get("score"), default=9999.0)
        total_time = _safe_number(r.get("total_travel_time_minutes") or r.get("total_time_minutes"), default=9999.0)

        if avoid_slope:
            # 급경사 피하기 ON: 경사 개수가 0개인 경로가 1위로 최우선 정렬
            slopes = _get_all_detected_slopes(r)
            slope_count = len(slopes)
            return (slope_count, score, total_time)
        else:
            # 급경사 피하기 OFF: 평가 점수 및 소요 시간순 정렬
            return (score, total_time)

    available_routes.sort(key=get_sort_key)

    # 최적 추천 경로 선정
    recommended_route = available_routes[0]
    if isinstance(recommended_route.get("evaluation"), dict):
        recommended_route["evaluation"]["is_recommended"] = True

    alternative_routes = available_routes[1:]

    # 4. 경사 정보 안전 수집 및 급경사 경고 판단
    rec_slopes = _get_all_detected_slopes(recommended_route)
    recommended_route["detected_slopes"] = rec_slopes

    has_steep = len(rec_slopes) > 0
    slope_warning_needed = bool(avoid_slope and has_steep)

    max_slope_val = None
    count_val = len(rec_slopes)
    if slope_warning_needed and rec_slopes:
        slope_degrees = [
            _safe_number(s.get("slope_degree"), default=8.0)
            for s in rec_slopes if isinstance(s, dict)
        ]
        max_slope_val = max(slope_degrees) if slope_degrees else 8.0

    # 5. Gemini AI 문구 생성
    ai_text = await generate_route_ai_text(
        route=recommended_route,
        mobility_constraints=constraints,
        route_preference=preference,
        slope_warning_needed=slope_warning_needed,
        max_slope_percent=max_slope_val,
        slope_spot_count=count_val,
    )

    ai_reason = ai_text.get("recommend_reason")
    slope_warning_message = ai_text.get("slope_warning")

    recommended_route["ai_reason"] = ai_reason
    if ai_reason and isinstance(recommended_route.get("evaluation"), dict):
        recommended_route["evaluation"]["positive_reasons"] = [ai_reason]

    # 6. 반환값에 summary 객체 포함
    return {
        "mobility_constraints": constraints,
        "route_preference": preference,
        "recommended_route": recommended_route,
        "alternative_routes": alternative_routes,
        "excluded_routes": excluded_routes,
        "detected_slopes": rec_slopes,
        "has_steep_warning": bool(slope_warning_needed and slope_warning_message),
        "ai_reason": ai_reason,
        "slope_warning_message": slope_warning_message,
        "summary": {
            "total_candidate_count": len(evaluated_routes),
            "available_route_count": len(available_routes),
            "excluded_route_count": len(excluded_routes),
        },
    }