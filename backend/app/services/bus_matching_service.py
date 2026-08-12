from __future__ import annotations

import json
import math
import re
from functools import lru_cache
from pathlib import Path
from typing import Any


BASE_DIR = Path(__file__).resolve().parent.parent

BUS_STATION_DATA_PATH = (
    BASE_DIR
    / "data"
    / "성남시_버스정류장_GBIS번호_추가.json"
)

BUS_ROUTE_DATA_PATH = (
    BASE_DIR
    / "data"
    / "경기도_성남시_버스노선_현황_노선ID추가.json"
)


# ==============================================================================
# 1. 공통 유틸
# ==============================================================================

def _normalize_text(
    value: Any,
) -> str:
    """
    이름 매칭용 문자열 정규화.
    공백 차이를 제거하고 소문자로 비교합니다.
    """

    if value is None:
        return ""

    return (
        str(value)
        .strip()
        .replace(" ", "")
        .lower()
    )


def _normalize_bus_number(
    value: Any,
) -> str:
    """
    버스 번호 비교용 정규화.
    예:
    ' 55 ' -> '55'
    """

    return _normalize_text(
        value
    )


def _safe_float(
    value: Any,
) -> float | None:
    try:
        return float(
            str(value).strip()
        )
    except (
        TypeError,
        ValueError,
    ):
        return None


def _haversine_distance_m(
    lon1: float,
    lat1: float,
    lon2: float,
    lat2: float,
) -> float:
    """
    두 WGS84 좌표 사이의 대략적인 직선거리(m).
    """

    earth_radius_m = 6_371_000.0

    phi1 = math.radians(
        lat1
    )
    phi2 = math.radians(
        lat2
    )

    delta_phi = math.radians(
        lat2 - lat1
    )
    delta_lambda = math.radians(
        lon2 - lon1
    )

    a = (
        math.sin(
            delta_phi / 2
        ) ** 2
        + math.cos(
            phi1
        )
        * math.cos(
            phi2
        )
        * math.sin(
            delta_lambda / 2
        ) ** 2
    )

    c = 2 * math.atan2(
        math.sqrt(
            a
        ),
        math.sqrt(
            1 - a
        ),
    )

    return (
        earth_radius_m
        * c
    )


# ==============================================================================
# 2. 정적 JSON 로드
# ==============================================================================

@lru_cache(
    maxsize=1
)
def load_bus_stations() -> list[
    dict[str, Any]
]:
    if not BUS_STATION_DATA_PATH.exists():
        raise FileNotFoundError(
            "버스 정류장 JSON을 찾을 수 없습니다: "
            f"{BUS_STATION_DATA_PATH}"
        )

    with BUS_STATION_DATA_PATH.open(
        "r",
        encoding="utf-8",
    ) as file:
        data = json.load(
            file
        )

    if not isinstance(
        data,
        list,
    ):
        raise ValueError(
            "버스 정류장 JSON 최상위 값은 list여야 합니다."
        )

    return [
        item
        for item in data
        if isinstance(
            item,
            dict,
        )
    ]


@lru_cache(
    maxsize=1
)
def load_bus_routes() -> list[
    dict[str, Any]
]:
    if not BUS_ROUTE_DATA_PATH.exists():
        raise FileNotFoundError(
            "버스 노선 JSON을 찾을 수 없습니다: "
            f"{BUS_ROUTE_DATA_PATH}"
        )

    with BUS_ROUTE_DATA_PATH.open(
        "r",
        encoding="utf-8",
    ) as file:
        data = json.load(
            file
        )

    if not isinstance(
        data,
        list,
    ):
        raise ValueError(
            "버스 노선 JSON 최상위 값은 list여야 합니다."
        )

    return [
        item
        for item in data
        if isinstance(
            item,
            dict,
        )
    ]


# ==============================================================================
# 3. 정류장 경유 노선번호 파싱
# ==============================================================================

def parse_station_bus_numbers(
    station: dict[str, Any],
) -> set[str]:
    """
    정류장 JSON의
    '시내버스_경유노선번호' 문자열에서
    버스 번호만 추출합니다.

    예:
    '55(시내),341(시내),66(마을)'
    ->
    {'55', '341', '66'}
    """

    raw = station.get(
        "시내버스_경유노선번호",
        "",
    )

    if not raw:
        return set()

    result: set[str] = set()

    for token in str(
        raw
    ).split(","):

        token = token.strip()

        if not token:
            continue

        # '(시내)', '(마을)', '(서울)' 등 뒤 설명 제거
        bus_number = re.sub(
            r"\([^)]*\)",
            "",
            token,
        ).strip()

        normalized = (
            _normalize_bus_number(
                bus_number
            )
        )

        if normalized:
            result.add(
                normalized
            )

    return result


# ==============================================================================
# 4. 버스 번호 -> GBIS routeId
# ==============================================================================

def find_route_by_bus_number(
    bus_number: str,
) -> dict[str, Any] | None:
    """
    버스 번호를 정적 노선 JSON의 '노선명'과 정확히 매칭합니다.

    데이터에 노선이 없으면 None을 반환합니다.
    이는 오류가 아니라 '정적 데이터에서 미매칭' 상태입니다.
    """

    target = (
        _normalize_bus_number(
            bus_number
        )
    )

    if not target:
        return None

    for route in load_bus_routes():

        route_name = (
            _normalize_bus_number(
                route.get(
                    "노선명"
                )
            )
        )

        if (
            route_name
            == target
        ):
            return route

    return None


def get_route_id(
    bus_number: str,
) -> str | None:
    route = (
        find_route_by_bus_number(
            bus_number
        )
    )

    if not route:
        return None

    route_id = route.get(
        "노선ID"
    )

    if route_id is None:
        return None

    route_id_text = str(
        route_id
    ).strip()

    return (
        route_id_text
        or None
    )


# ==============================================================================
# 5. 정류장명 -> GBIS stationId 후보 검색
# ==============================================================================

def find_station_candidates(
    stop_name: str,
    bus_numbers: list[str] | None = None,
) -> list[dict[str, Any]]:
    """
    정류장명으로 후보를 찾습니다.

    같은 이름의 정류장이 양방향에 2개 이상 있을 수 있으므로,
    버스 번호 정보가 있으면 해당 노선이 실제 경유하는
    정류장만 우선 남깁니다.
    """

    target_name = (
        _normalize_text(
            stop_name
        )
    )

    if not target_name:
        return []

    candidates = [
        station
        for station
        in load_bus_stations()
        if _normalize_text(
            station.get(
                "정류장명"
            )
        )
        == target_name
    ]

    if (
        not candidates
        or not bus_numbers
    ):
        return candidates

    normalized_bus_numbers = {
        _normalize_bus_number(
            number
        )
        for number
        in bus_numbers
        if _normalize_bus_number(
            number
        )
    }

    route_filtered = []

    for station in candidates:

        station_bus_numbers = (
            parse_station_bus_numbers(
                station
            )
        )

        if (
            normalized_bus_numbers
            & station_bus_numbers
        ):
            route_filtered.append(
                station
            )

    # 버스 번호 필터 결과가 하나라도 있으면 그 결과를 사용.
    # 없으면 정류장명 후보 자체를 반환하여 좌표 매칭 기회를 남김.
    return (
        route_filtered
        if route_filtered
        else candidates
    )


def select_best_station_candidate(
    stop_name: str,
    bus_numbers: list[str] | None = None,
    reference_lon: float | None = None,
    reference_lat: float | None = None,
) -> dict[str, Any] | None:
    """
    정류장 후보가 여러 개일 때 다음 기준으로 선택합니다.

    1. 정류장명 정확 매칭
    2. 해당 버스가 실제 경유하는 정류장 우선
    3. 카카오 BUS step 시작 좌표와 가장 가까운 정류장 선택

    reference 좌표가 없다면 후보가 1개일 때만 확정합니다.
    후보가 여러 개면 임의 선택하지 않고 None을 반환합니다.
    """

    candidates = (
        find_station_candidates(
            stop_name=stop_name,
            bus_numbers=(
                bus_numbers
                or []
            ),
        )
    )

    if not candidates:
        return None

    if len(
        candidates
    ) == 1:
        return candidates[
            0
        ]

    if (
        reference_lon is None
        or reference_lat is None
    ):
        return None

    ranked: list[
        tuple[
            float,
            dict[str, Any],
        ]
    ] = []

    for station in candidates:

        station_lat = (
            _safe_float(
                station.get(
                    "위도"
                )
            )
        )

        station_lon = (
            _safe_float(
                station.get(
                    "경도"
                )
            )
        )

        if (
            station_lat is None
            or station_lon is None
        ):
            continue

        distance_m = (
            _haversine_distance_m(
                lon1=reference_lon,
                lat1=reference_lat,
                lon2=station_lon,
                lat2=station_lat,
            )
        )

        ranked.append(
            (
                distance_m,
                station,
            )
        )

    if not ranked:
        return None

    ranked.sort(
        key=lambda item: (
            item[
                0
            ]
        )
    )

    return ranked[
        0
    ][
        1
    ]


def get_station_id(
    stop_name: str,
    bus_numbers: list[str] | None = None,
    reference_lon: float | None = None,
    reference_lat: float | None = None,
) -> str | None:
    station = (
        select_best_station_candidate(
            stop_name=stop_name,
            bus_numbers=bus_numbers,
            reference_lon=reference_lon,
            reference_lat=reference_lat,
        )
    )

    if not station:
        return None

    station_id = station.get(
        "정류장번호"
    )

    if station_id is None:
        return None

    station_id_text = str(
        station_id
    ).strip()

    return (
        station_id_text
        or None
    )


# ==============================================================================
# 6. 카카오 BUS step -> routeId + stationId
# ==============================================================================

def extract_bus_numbers_from_step(
    step: dict[str, Any],
) -> list[str]:
    vehicles = step.get(
        "vehicles",
        [],
    )

    if not isinstance(
        vehicles,
        list,
    ):
        return []

    result: list[str] = []

    for vehicle in vehicles:

        if not isinstance(
            vehicle,
            dict,
        ):
            continue

        name = str(
            vehicle.get(
                "name",
                "",
            )
        ).strip()

        if (
            name
            and name
            not in result
        ):
            result.append(
                name
            )

    return result


def _get_step_reference_point(
    step: dict[str, Any],
) -> tuple[
    float | None,
    float | None,
]:
    """
    카카오 BUS step path의 첫 좌표를 승차 정류장 근처 기준점으로 사용합니다.

    path 좌표 순서:
    [longitude, latitude]
    """

    path = step.get(
        "path",
        [],
    )

    if (
        not isinstance(
            path,
            list,
        )
        or not path
    ):
        return (
            None,
            None,
        )

    first_point = path[
        0
    ]

    if (
        not isinstance(
            first_point,
            list,
        )
        or len(
            first_point
        ) < 2
    ):
        return (
            None,
            None,
        )

    longitude = (
        _safe_float(
            first_point[
                0
            ]
        )
    )

    latitude = (
        _safe_float(
            first_point[
                1
            ]
        )
    )

    return (
        longitude,
        latitude,
    )


def match_bus_step_identifiers(
    step: dict[str, Any],
) -> dict[str, Any]:
    """
    카카오가 단순화한 BUS step 하나에서
    GBIS stationId와 routeId들을 매칭합니다.

    routeId가 정적 노선 JSON에 없는 노선은 None으로 남깁니다.
    이후 버스 도착정보 API 응답에서 routeId를 보완할 수 있습니다.
    """

    step_type = str(
        step.get(
            "step_type",
            "",
        )
    ).strip().upper()

    if step_type != "BUS":
        return {
            "status": (
                "NOT_BUS_STEP"
            ),
            "station_id": None,
            "boarding_stop_name": None,
            "routes": [],
        }

    bus_numbers = (
        extract_bus_numbers_from_step(
            step
        )
    )

    stops = step.get(
        "stops",
        [],
    )

    if not isinstance(
        stops,
        list,
    ):
        stops = []

    boarding_stop_name = (
        str(
            stops[
                0
            ]
        ).strip()
        if stops
        else ""
    )

    (
        reference_lon,
        reference_lat,
    ) = (
        _get_step_reference_point(
            step
        )
    )

    station = (
        select_best_station_candidate(
            stop_name=(
                boarding_stop_name
            ),
            bus_numbers=(
                bus_numbers
            ),
            reference_lon=(
                reference_lon
            ),
            reference_lat=(
                reference_lat
            ),
        )
    )

    station_id = None

    if station:
        raw_station_id = (
            station.get(
                "정류장번호"
            )
        )

        if raw_station_id is not None:
            station_id = str(
                raw_station_id
            ).strip() or None

    route_matches: list[
        dict[str, Any]
    ] = []

    for bus_number in (
        bus_numbers
    ):

        route = (
            find_route_by_bus_number(
                bus_number
            )
        )

        route_id = None

        if route:
            raw_route_id = (
                route.get(
                    "노선ID"
                )
            )

            if raw_route_id is not None:
                route_id = str(
                    raw_route_id
                ).strip() or None

        route_matches.append(
            {
                "bus_number": (
                    bus_number
                ),
                "route_id": (
                    route_id
                ),
                "route_match_status": (
                    "MATCHED"
                    if route_id
                    else "NOT_FOUND_IN_STATIC_DATA"
                ),
            }
        )

    route_id_count = sum(
        1
        for item
        in route_matches
        if item.get(
            "route_id"
        )
    )

    if (
        station_id
        and route_matches
        and route_id_count
        == len(
            route_matches
        )
    ):
        status = (
            "MATCHED"
        )

    elif (
        station_id
        or route_id_count > 0
    ):
        status = (
            "PARTIAL"
        )

    else:
        status = (
            "UNMATCHED"
        )

    return {
        "status": status,
        "boarding_stop_name": (
            boarding_stop_name
        ),
        "station_id": (
            station_id
        ),
        "station_match": (
            {
                "station_name": (
                    station.get(
                        "정류장명"
                    )
                ),
                "station_id": (
                    station_id
                ),
                "mobile_short_number": (
                    station.get(
                        "모바일단축번호"
                    )
                ),
                "latitude": (
                    _safe_float(
                        station.get(
                            "위도"
                        )
                    )
                ),
                "longitude": (
                    _safe_float(
                        station.get(
                            "경도"
                        )
                    )
                ),
                "detail_location": (
                    station.get(
                        "상세위치"
                    )
                ),
            }
            if station
            else None
        ),
        "routes": (
            route_matches
        ),
    }


def attach_bus_identifiers_to_route(
    route: dict[str, Any],
) -> dict[str, Any]:
    """
    경로의 모든 BUS step에 GBIS 식별자 매칭 결과를 붙입니다.
    """

    steps = route.get(
        "steps",
        [],
    )

    if not isinstance(
        steps,
        list,
    ):
        return route

    bus_matches: list[
        dict[str, Any]
    ] = []

    for step in steps:

        if not isinstance(
            step,
            dict,
        ):
            continue

        if str(
            step.get(
                "step_type",
                "",
            )
        ).upper() != "BUS":
            continue

        match_result = (
            match_bus_step_identifiers(
                step
            )
        )

        bus_matches.append(
            {
                "step_id": (
                    step.get(
                        "step_id"
                    )
                ),
                **match_result,
            }
        )

    route[
        "bus_identifier_matches"
    ] = bus_matches

    return route
