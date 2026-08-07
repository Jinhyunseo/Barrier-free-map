from __future__ import annotations

from copy import deepcopy
from typing import Any


# ==============================================================================
# 1. 사용자 유형별 접근성 기준 및 가중치
#
# 점수가 낮을수록 사용자에게 더 적합한 경로입니다.
#
# Hard Barrier
# - 조건을 위반하면 해당 경로를 추천 후보에서 제외합니다.
#
# Soft Scoring
# - 이용은 가능하지만 불편한 정도를 점수로 계산합니다.
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
# 2. 공통 유틸리티 함수
# ==============================================================================

def _safe_number(
    value: Any,
    default: float = 0.0,
) -> float:
    """
    int, float 또는 숫자 문자열을 float로 변환합니다.

    None이거나 변환할 수 없는 값이면 default를 반환합니다.
    """

    if value is None:
        return default

    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _normalize_text(value: Any) -> str:
    """
    문자열 비교를 위해 소문자로 변환하고
    앞뒤 공백을 제거합니다.
    """

    if value is None:
        return ""

    return str(value).strip().lower()


def _is_walk_step(step: dict[str, Any]) -> bool:
    """
    카카오 후보 경로의 step이 도보 구간인지 확인합니다.

    현재 카카오 응답의 step_type이 문자열인 경우를 기준으로 하며,
    walk, walking, pedestrian, 도보 등의 값을 지원합니다.
    """

    step_type = _normalize_text(step.get("step_type"))

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


def _route_uses_bus(route: dict[str, Any]) -> bool:
    """
    경로에 버스 이용 구간이 포함되어 있는지 확인합니다.
    """

    route_type = _normalize_text(route.get("route_type"))

    if "bus" in route_type or "버스" in route_type:
        return True

    for vehicle in route.get("vehicles", []):
        if not isinstance(vehicle, dict):
            continue

        vehicle_type = _normalize_text(vehicle.get("type"))
        vehicle_name = _normalize_text(vehicle.get("name"))

        if (
            "bus" in vehicle_type
            or "버스" in vehicle_type
            or "bus" in vehicle_name
            or "버스" in vehicle_name
        ):
            return True

    for step in route.get("steps", []):
        if not isinstance(step, dict):
            continue

        step_type = _normalize_text(step.get("step_type"))

        if "bus" in step_type or "버스" in step_type:
            return True

    return False


def _route_uses_subway(route: dict[str, Any]) -> bool:
    """
    경로에 지하철 이용 구간이 포함되어 있는지 확인합니다.
    """

    route_type = _normalize_text(route.get("route_type"))

    subway_keywords = {
        "subway",
        "metro",
        "rail",
        "지하철",
        "전철",
    }

    if any(keyword in route_type for keyword in subway_keywords):
        return True

    for vehicle in route.get("vehicles", []):
        if not isinstance(vehicle, dict):
            continue

        vehicle_type = _normalize_text(vehicle.get("type"))
        vehicle_name = _normalize_text(vehicle.get("name"))

        if any(
            keyword in vehicle_type or keyword in vehicle_name
            for keyword in subway_keywords
        ):
            return True

    for step in route.get("steps", []):
        if not isinstance(step, dict):
            continue

        step_type = _normalize_text(step.get("step_type"))

        if any(keyword in step_type for keyword in subway_keywords):
            return True

    return False


def calculate_walk_distance(
    route: dict[str, Any],
) -> tuple[int, bool]:
    """
    카카오 후보 경로의 도보 step 거리만 합산합니다.

    반환값:
    - 도보거리(m)
    - 도보 step을 정상적으로 식별했는지 여부

    도보 step을 찾지 못했다고 해서 전체 이동거리를
    보행거리로 간주하지 않습니다.
    """

    walk_distance = 0
    found_walk_step = False

    for step in route.get("steps", []):
        if not isinstance(step, dict):
            continue

        if not _is_walk_step(step):
            continue

        found_walk_step = True

        distance = _safe_number(
            step.get("distance"),
            default=0.0,
        )

        walk_distance += int(round(distance))

    return walk_distance, found_walk_step


# ==============================================================================
# 3. 접근성 데이터 읽기
#
# 팀원1의 접근성 API 결과는 각 경로의 accessibility에 들어온다고
# 가정합니다.
#
# 예상 예시:
#
# "accessibility": {
#     "status": "ANALYZED",
#     "has_broken_elevator": False,
#     "broken_elevator_stations": [],
#     "has_elevator": True,
#     "has_stairs": False,
#     "max_incline": 3.2,
#     "max_curb_height": 1.0,
#     "has_low_floor_bus": True,
#     "low_floor_bus_numbers": ["76"],
#     "unknown_fields": [],
#     "unavailable_reasons": []
# }
# ==============================================================================

def get_accessibility_data(
    route: dict[str, Any],
) -> dict[str, Any]:
    """
    route의 accessibility 값을 안전하게 읽습니다.

    값이 없는 항목은 None 또는 빈 리스트로 유지해
    '정보 없음'과 False를 구분합니다.
    """

    accessibility = route.get("accessibility")

    if not isinstance(accessibility, dict):
        accessibility = {}

    max_incline = accessibility.get("max_incline")

    if max_incline is None:
        max_incline = accessibility.get("incline")

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

    if not isinstance(unknown_fields, list):
        unknown_fields = []

    unavailable_reasons = accessibility.get(
        "unavailable_reasons",
        [],
    )

    if not isinstance(unavailable_reasons, list):
        unavailable_reasons = []

    return {
        "status": accessibility.get(
            "status",
            "UNKNOWN",
        ),
        "has_broken_elevator": accessibility.get(
            "has_broken_elevator"
        ),
        "broken_elevator_stations": accessibility.get(
            "broken_elevator_stations",
            [],
        ),
        "has_elevator": accessibility.get(
            "has_elevator"
        ),
        "has_stairs": accessibility.get(
            "has_stairs"
        ),
        "max_incline": max_incline,
        "has_steep_slope": accessibility.get(
            "has_steep_slope"
        ),
        "max_curb_height": max_curb_height,
        "has_low_floor_bus": accessibility.get(
            "has_low_floor_bus"
        ),
        "low_floor_bus_numbers": accessibility.get(
            "low_floor_bus_numbers",
            [],
        ),
        "unknown_fields": unknown_fields,
        "unavailable_reasons": unavailable_reasons,
    }


# ==============================================================================
# 4. Hard Barrier 검사
# ==============================================================================

def check_hard_barriers(
    route: dict[str, Any],
    user_type: str,
) -> list[str]:
    """
    후보 경로가 사용자에게 물리적으로 이용 불가능한지 검사합니다.

    이용 불가능한 조건이 여러 개라면 모든 사유를 반환합니다.
    """

    config = USER_CONFIGS[user_type]
    accessibility = get_accessibility_data(route)

    exclusion_reasons: list[str] = []

    # 접근성 API에서 직접 전달한 이용 불가 사유
    for reason in accessibility["unavailable_reasons"]:
        if reason and reason not in exclusion_reasons:
            exclusion_reasons.append(str(reason))

    # 계단
    has_stairs = accessibility["has_stairs"]

    if (
        has_stairs is True
        and not config["allow_stairs"]
    ):
        exclusion_reasons.append(
            "계단이 포함된 경로입니다."
        )

    # 경사도
    max_incline = accessibility["max_incline"]

    if max_incline is not None:
        incline_value = _safe_number(max_incline)

        if incline_value >= config["max_incline"]:
            exclusion_reasons.append(
                "허용 기준을 초과하는 경사가 "
                f"포함되어 있습니다. "
                f"({incline_value:.1f}% 이상)"
            )

    # 경사도 값 대신 has_steep_slope만 제공된 경우
    elif accessibility["has_steep_slope"] is True:
        exclusion_reasons.append(
            "급경사 구간이 포함되어 있습니다."
        )

    # 보도 턱
    max_curb_height = accessibility[
        "max_curb_height"
    ]

    if max_curb_height is not None:
        curb_value = _safe_number(max_curb_height)

        if curb_value > config["max_curb"]:
            exclusion_reasons.append(
                "허용 기준보다 높은 보도 턱이 "
                f"포함되어 있습니다. "
                f"({curb_value:.1f}cm)"
            )

    # 고장 난 엘리베이터
    if (
        config["broken_elevator_is_barrier"]
        and accessibility[
            "has_broken_elevator"
        ] is True
    ):
        broken_stations = accessibility.get(
            "broken_elevator_stations",
            [],
        )

        if broken_stations:
            station_text = ", ".join(
                str(station)
                for station in broken_stations
            )

            exclusion_reasons.append(
                "이용 동선에 엘리베이터가 고장 난 "
                f"역이 포함되어 있습니다: {station_text}"
            )
        else:
            exclusion_reasons.append(
                "이용 동선에 고장 난 엘리베이터가 "
                "포함되어 있습니다."
            )

    # 휠체어가 버스를 이용하는 경우 저상버스 필수
    if (
        config["require_low_floor_bus"]
        and _route_uses_bus(route)
        and accessibility[
            "has_low_floor_bus"
        ] is False
    ):
        exclusion_reasons.append(
            "휠체어 이용이 가능한 저상버스가 "
            "확인되지 않은 경로입니다."
        )

    # 중복 사유 제거
    return list(dict.fromkeys(exclusion_reasons))


# ==============================================================================
# 5. 정보 미확인 항목 계산
# ==============================================================================

def find_unknown_fields(
    route: dict[str, Any],
) -> list[str]:
    """
    경로 평가에 필요하지만 확인되지 않은 접근성 정보를 반환합니다.

    정보가 없다는 이유만으로 경로를 즉시 제외하지 않고,
    점수에 불확실성 패널티를 적용합니다.
    """

    accessibility = get_accessibility_data(route)

    unknown_fields: list[str] = list(
        accessibility["unknown_fields"]
    )

    # 모든 경로에서 필요한 정보
    if accessibility["has_stairs"] is None:
        unknown_fields.append("계단 여부")

    if (
        accessibility["max_incline"] is None
        and accessibility["has_steep_slope"] is None
    ):
        unknown_fields.append("경사도")

    if accessibility["max_curb_height"] is None:
        unknown_fields.append("보도 턱 높이")

    # 버스 경로에서 필요한 정보
    if (
        _route_uses_bus(route)
        and accessibility[
            "has_low_floor_bus"
        ] is None
    ):
        unknown_fields.append("저상버스 여부")

    # 지하철 경로에서 필요한 정보
    if _route_uses_subway(route):
        if accessibility["has_elevator"] is None:
            unknown_fields.append("엘리베이터 설치 여부")

        if (
            accessibility[
                "has_broken_elevator"
            ] is None
        ):
            unknown_fields.append(
                "엘리베이터 고장 여부"
            )

    return list(dict.fromkeys(unknown_fields))


# ==============================================================================
# 6. 후보 경로 점수 계산
# ==============================================================================

def calculate_route_score(
    route: dict[str, Any],
    user_type: str,
) -> tuple[float, list[str], list[str]]:
    """
    후보 경로 하나의 불편 점수를 계산합니다.

    반환:
    - 점수
    - 추천 근거
    - 정보 미확인 항목

    점수가 낮을수록 좋은 경로입니다.
    """

    config = USER_CONFIGS[user_type]
    weights = config["weights"]
    accessibility = get_accessibility_data(route)

    score = 0.0
    positive_reasons: list[str] = []

    # ------------------------------------------------------------------
    # 1. 총 소요시간
    # ------------------------------------------------------------------
    total_time_minutes = _safe_number(
        route.get("total_time_minutes"),
        default=0.0,
    )

    score += (
        total_time_minutes
        * weights["time_per_min"]
    )

    # ------------------------------------------------------------------
    # 2. 보행거리
    # ------------------------------------------------------------------
    walk_distance, found_walk_step = (
        calculate_walk_distance(route)
    )

    score += (
        walk_distance
        * weights["walk_dist_per_m"]
    )

    if walk_distance <= 300 and found_walk_step:
        positive_reasons.append(
            "보행 구간이 비교적 짧습니다."
        )

    # ------------------------------------------------------------------
    # 3. 환승 횟수
    # ------------------------------------------------------------------
    transfer_count = int(
        _safe_number(
            route.get("transfer_count"),
            default=0.0,
        )
    )

    score += (
        transfer_count
        * weights["transfer_penalty"]
    )

    if transfer_count == 0:
        positive_reasons.append(
            "환승 없이 이동할 수 있습니다."
        )
    elif transfer_count == 1:
        positive_reasons.append(
            "환승 횟수가 1회로 비교적 적습니다."
        )

    # ------------------------------------------------------------------
    # 4. 엘리베이터
    # ------------------------------------------------------------------
    if accessibility["has_elevator"] is True:
        score += weights["elevator_bonus"]

        positive_reasons.append(
            "엘리베이터를 이용할 수 있는 "
            "동선입니다."
        )

    # ------------------------------------------------------------------
    # 5. 저상버스
    # ------------------------------------------------------------------
    if (
        _route_uses_bus(route)
        and accessibility[
            "has_low_floor_bus"
        ] is True
    ):
        score += weights["low_floor_bus_bonus"]

        low_floor_bus_numbers = accessibility.get(
            "low_floor_bus_numbers",
            [],
        )

        if low_floor_bus_numbers:
            bus_text = ", ".join(
                str(number)
                for number in low_floor_bus_numbers
            )

            positive_reasons.append(
                f"저상버스({bus_text})를 이용할 수 "
                "있습니다."
            )
        else:
            positive_reasons.append(
                "저상버스를 이용할 수 있습니다."
            )

    # ------------------------------------------------------------------
    # 6. 계단·경사·턱이 안전하다고 확인된 경우
    # ------------------------------------------------------------------
    if accessibility["has_stairs"] is False:
        positive_reasons.append(
            "계단이 없는 경로로 확인되었습니다."
        )

    max_incline = accessibility["max_incline"]

    if max_incline is not None:
        incline_value = _safe_number(max_incline)

        if incline_value < config["max_incline"]:
            positive_reasons.append(
                "사용자 유형의 허용 기준 이내인 "
                f"경사도입니다. ({incline_value:.1f}%)"
            )

    max_curb_height = accessibility[
        "max_curb_height"
    ]

    if max_curb_height is not None:
        curb_value = _safe_number(max_curb_height)

        if curb_value <= config["max_curb"]:
            positive_reasons.append(
                "보도 턱 높이가 사용자 기준 이내입니다."
            )

    # ------------------------------------------------------------------
    # 7. 정보 미확인 패널티
    # ------------------------------------------------------------------
    unknown_fields = find_unknown_fields(route)

    score += (
        len(unknown_fields)
        * weights["unknown_data_penalty"]
    )

    # 점수가 음수가 되는 것을 방지
    final_score = max(round(score, 2), 0.1)

    return (
        final_score,
        list(dict.fromkeys(positive_reasons)),
        unknown_fields,
    )


# ==============================================================================
# 7. 후보 경로 하나 평가
# ==============================================================================

def evaluate_candidate_route(
    route: dict[str, Any],
    user_type: str,
) -> dict[str, Any]:
    """
    카카오 후보 경로 하나를 평가합니다.

    기존 경로 데이터를 유지하면서 evaluation 필드에
    이용 가능 여부, 점수, 추천 근거, 제외 이유 등을 추가합니다.
    """

    if user_type not in USER_CONFIGS:
        supported_types = ", ".join(
            USER_CONFIGS.keys()
        )

        raise ValueError(
            f"지원하지 않는 사용자 유형입니다: "
            f"{user_type}. "
            f"지원 유형: {supported_types}"
        )

    evaluated_route = deepcopy(route)

    exclusion_reasons = check_hard_barriers(
        route,
        user_type,
    )

    is_available = len(exclusion_reasons) == 0

    if is_available:
        (
            score,
            positive_reasons,
            unknown_fields,
        ) = calculate_route_score(
            route,
            user_type,
        )
    else:
        score = None
        positive_reasons = []
        unknown_fields = find_unknown_fields(route)

    evaluated_route["evaluation"] = {
        "is_available": is_available,
        "score": score,
        "is_recommended": False,
        "positive_reasons": positive_reasons,
        "exclusion_reasons": exclusion_reasons,
        "unknown_fields": unknown_fields,
        "has_unknown_accessibility_data": bool(
            unknown_fields
        ),
    }

    # Flutter가 바로 사용할 수 있도록 보행거리도 추가
    walk_distance, _ = calculate_walk_distance(route)

    evaluated_route[
        "total_walk_distance_meters"
    ] = walk_distance

    return evaluated_route


# ==============================================================================
# 8. 모든 후보 경로 평가
# ==============================================================================

def evaluate_all_candidates(
    routes: list[dict[str, Any]],
    user_type: str,
) -> list[dict[str, Any]]:
    """
    카카오 후보 경로 전체를 평가합니다.
    """

    return [
        evaluate_candidate_route(
            route=route,
            user_type=user_type,
        )
        for route in routes
    ]


# ==============================================================================
# 9. 최적 후보 경로 선택
# ==============================================================================

def select_best_candidate(
    routes: list[dict[str, Any]],
    user_type: str,
) -> dict[str, Any]:
    """
    카카오 후보 경로들을 사용자 유형에 따라 평가한 뒤
    최적 경로 하나를 선택합니다.

    선택 우선순위:
    1. 불편 점수가 낮은 경로
    2. 총 소요시간이 짧은 경로
    3. 환승 횟수가 적은 경로
    4. 총 이동거리가 짧은 경로
    """

    evaluated_routes = evaluate_all_candidates(
        routes=routes,
        user_type=user_type,
    )

    available_routes = [
        route
        for route in evaluated_routes
        if route["evaluation"]["is_available"]
    ]

    excluded_routes = [
        {
            "route_id": route.get("route_id"),
            "route_type": route.get("route_type"),
            "exclusion_reasons": route[
                "evaluation"
            ]["exclusion_reasons"],
            "unknown_fields": route[
                "evaluation"
            ]["unknown_fields"],
        }
        for route in evaluated_routes
        if not route["evaluation"]["is_available"]
    ]

    if not available_routes:
        return {
            "user_type": user_type,
            "user_type_name": USER_CONFIGS[
                user_type
            ]["name"],
            "recommended_route": None,
            "alternative_routes": [],
            "excluded_routes": excluded_routes,
            "message": (
                "해당 사용자 유형으로 안전하게 이용할 수 "
                "있는 경로를 찾지 못했습니다."
            ),
        }

    available_routes.sort(
        key=lambda route: (
            _safe_number(
                route["evaluation"].get("score"),
                default=float("inf"),
            ),
            _safe_number(
                route.get("total_time_minutes"),
                default=float("inf"),
            ),
            _safe_number(
                route.get("transfer_count"),
                default=float("inf"),
            ),
            _safe_number(
                route.get(
                    "total_distance_meters"
                ),
                default=float("inf"),
            ),
        )
    )

    recommended_route = available_routes[0]
    recommended_route["evaluation"][
        "is_recommended"
    ] = True

    # 추천 경로를 제외한 이용 가능한 후보
    alternative_routes = available_routes[1:]

    return {
        "user_type": user_type,
        "user_type_name": USER_CONFIGS[
            user_type
        ]["name"],
        "recommended_route": recommended_route,
        "alternative_routes": alternative_routes,
        "excluded_routes": excluded_routes,
        "summary": {
            "total_candidate_count": len(
                evaluated_routes
            ),
            "available_route_count": len(
                available_routes
            ),
            "excluded_route_count": len(
                excluded_routes
            ),
        },
    }