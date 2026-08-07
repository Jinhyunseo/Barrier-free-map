from __future__ import annotations

import re
from copy import deepcopy
from typing import Any


def normalize_station_name(name: str | None) -> str | None:
    """
    역 이름을 서비스 내부 표준 형태로 정리합니다.

    예:
    - 판교(판교테크노밸리) -> 판교역
    - 정자 -> 정자역
    """

    if not name:
        return None

    normalized = name.strip()

    # 괄호와 괄호 안 부가 설명 제거
    normalized = re.sub(r"\([^)]*\)", "", normalized).strip()

    if not normalized:
        return None

    if not normalized.endswith("역"):
        normalized = f"{normalized}역"

    return normalized


def get_step_line_name(step: dict[str, Any]) -> str | None:
    """
    지하철 step에서 노선명을 추출합니다.
    """

    vehicles = step.get("vehicles", [])

    if isinstance(vehicles, list):
        for vehicle in vehicles:
            if not isinstance(vehicle, dict):
                continue

            name = vehicle.get("name")

            if name:
                return str(name).strip()

    # vehicles에 노선명이 없을 경우 guidance에서 보조 추출
    guidance = str(step.get("guidance", "")).strip()

    match = re.match(r"(.+?)\s*\(", guidance)

    if match:
        return match.group(1).strip()

    return None


def get_subway_steps(
    route: dict[str, Any],
) -> list[dict[str, Any]]:
    """
    후보 경로에서 지하철 구간만 순서대로 반환합니다.
    """

    subway_steps: list[dict[str, Any]] = []

    for step in route.get("steps", []):
        if not isinstance(step, dict):
            continue

        step_type = str(
            step.get("step_type", "")
        ).strip().upper()

        if step_type == "SUBWAY":
            subway_steps.append(step)

    return subway_steps


def get_transfer_walk_step(
    route: dict[str, Any],
    previous_subway_step_id: int | None,
    next_subway_step_id: int | None,
) -> dict[str, Any] | None:
    """
    두 지하철 구간 사이에 있는 환승 도보 step을 찾습니다.
    """

    if (
        previous_subway_step_id is None
        or next_subway_step_id is None
    ):
        return None

    for step in route.get("steps", []):
        if not isinstance(step, dict):
            continue

        step_id = step.get("step_id")

        if not isinstance(step_id, int):
            continue

        if not (
            previous_subway_step_id
            < step_id
            < next_subway_step_id
        ):
            continue

        step_type = str(
            step.get("step_type", "")
        ).strip().upper()

        guidance = str(
            step.get("guidance", "")
        ).strip()

        if (
            step_type == "WALKING"
            and "환승" in guidance
        ):
            return step

    return None


def extract_station_movements(
    route: dict[str, Any],
) -> list[dict[str, Any]]:
    """
    카카오 후보 경로 하나에서 다음 정보를 추출합니다.

    - 최초 승차역
    - 환승역
    - 최종 하차역
    - 이용 노선
    - 이전 역 / 다음 역
    - 환승 도보거리와 시간
    """

    subway_steps = get_subway_steps(route)

    if not subway_steps:
        return []

    movements: list[dict[str, Any]] = []

    # ------------------------------------------------------------------
    # 1. 최초 승차
    # ------------------------------------------------------------------
    first_step = subway_steps[0]
    first_stops = first_step.get("stops", [])

    if isinstance(first_stops, list) and first_stops:
        boarding_station = normalize_station_name(
            first_stops[0]
        )

        next_station = (
            normalize_station_name(first_stops[1])
            if len(first_stops) >= 2
            else None
        )

        movements.append(
            {
                "movement_type": "BOARDING",
                "station_name": boarding_station,
                "line_name": get_step_line_name(
                    first_step
                ),
                "previous_station": None,
                "next_station": next_station,
                "step_id": first_step.get("step_id"),
            }
        )

    # ------------------------------------------------------------------
    # 2. 환승
    # ------------------------------------------------------------------
    for index in range(len(subway_steps) - 1):
        previous_step = subway_steps[index]
        next_step = subway_steps[index + 1]

        previous_stops = previous_step.get(
            "stops",
            [],
        )
        next_stops = next_step.get(
            "stops",
            [],
        )

        if (
            not isinstance(previous_stops, list)
            or not previous_stops
            or not isinstance(next_stops, list)
            or not next_stops
        ):
            continue

        transfer_station_from = normalize_station_name(
            previous_stops[-1]
        )
        transfer_station_to = normalize_station_name(
            next_stops[0]
        )

        # 두 구간의 연결 역이 같을 때 환승으로 판단
        if transfer_station_from != transfer_station_to:
            continue

        previous_station = (
            normalize_station_name(
                previous_stops[-2]
            )
            if len(previous_stops) >= 2
            else None
        )

        next_station = (
            normalize_station_name(next_stops[1])
            if len(next_stops) >= 2
            else None
        )

        transfer_walk_step = get_transfer_walk_step(
            route=route,
            previous_subway_step_id=previous_step.get(
                "step_id"
            ),
            next_subway_step_id=next_step.get(
                "step_id"
            ),
        )

        movements.append(
            {
                "movement_type": "TRANSFER",
                "station_name": transfer_station_from,
                "from_line": get_step_line_name(
                    previous_step
                ),
                "to_line": get_step_line_name(
                    next_step
                ),
                "previous_station": previous_station,
                "next_station": next_station,
                "walk_distance_meters": (
                    transfer_walk_step.get(
                        "distance"
                    )
                    if transfer_walk_step
                    else None
                ),
                "walk_time_seconds": (
                    transfer_walk_step.get("time")
                    if transfer_walk_step
                    else None
                ),
                "walk_guidance": (
                    transfer_walk_step.get(
                        "guidance"
                    )
                    if transfer_walk_step
                    else None
                ),
                "from_step_id": previous_step.get(
                    "step_id"
                ),
                "to_step_id": next_step.get(
                    "step_id"
                ),
            }
        )

    # ------------------------------------------------------------------
    # 3. 최종 하차
    # ------------------------------------------------------------------
    last_step = subway_steps[-1]
    last_stops = last_step.get("stops", [])

    if isinstance(last_stops, list) and last_stops:
        alighting_station = normalize_station_name(
            last_stops[-1]
        )

        previous_station = (
            normalize_station_name(
                last_stops[-2]
            )
            if len(last_stops) >= 2
            else None
        )

        movements.append(
            {
                "movement_type": "ALIGHTING",
                "station_name": alighting_station,
                "line_name": get_step_line_name(
                    last_step
                ),
                "previous_station": previous_station,
                "next_station": None,
                "step_id": last_step.get("step_id"),
            }
        )

    return movements


def attach_station_movements(
    routes: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    모든 후보 경로에 station_movements 필드를 추가합니다.
    """

    analyzed_routes: list[dict[str, Any]] = []

    for route in routes:
        copied_route = deepcopy(route)

        copied_route["station_movements"] = (
            extract_station_movements(copied_route)
        )

        analyzed_routes.append(copied_route)

    return analyzed_routes