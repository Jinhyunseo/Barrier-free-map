import os
from typing import Any

import httpx
from dotenv import load_dotenv
from fastapi import HTTPException


load_dotenv()

GYEONGGI_BUS_API_KEY = os.getenv(
    "GYEONGGI_BUS_API_KEY"
)

BUS_ARRIVAL_URL = (
    "https://apis.data.go.kr/"
    "6410000/busarrivalservice/v2/"
    "getBusArrivalListv2"
)


async def get_bus_arrivals(
    station_id: str,
) -> list[dict[str, Any]]:
    """
    GBIS 정류장 ID를 이용해
    해당 정류장의 실시간 버스 도착정보를 조회합니다.
    """

    if not GYEONGGI_BUS_API_KEY:
        raise RuntimeError(
            "GYEONGGI_BUS_API_KEY가 없습니다. "
            "backend/.env 파일을 확인하세요."
        )

    params = {
        "serviceKey": GYEONGGI_BUS_API_KEY,
        "format": "json",
        "stationId": station_id,
    }

    try:
        async with httpx.AsyncClient(
            timeout=20.0
        ) as client:
            response = await client.get(
                BUS_ARRIVAL_URL,
                params=params,
            )

        response.raise_for_status()
        data = response.json()

    except httpx.HTTPStatusError as exc:
        raise HTTPException(
            status_code=exc.response.status_code,
            detail={
                "message": (
                    "경기도 버스 도착정보 API "
                    "호출에 실패했습니다."
                ),
                "response": exc.response.text,
            },
        ) from exc

    except httpx.RequestError as exc:
        raise HTTPException(
            status_code=502,
            detail=(
                "경기도 버스 API 서버에 "
                f"연결하지 못했습니다: {exc}"
            ),
        ) from exc

    except ValueError as exc:
        raise HTTPException(
            status_code=502,
            detail=(
                "경기도 버스 API 응답을 "
                "JSON으로 변환하지 못했습니다."
            ),
        ) from exc

    response_data = data.get(
        "response",
        {},
    )

    header = response_data.get(
        "msgHeader",
        {},
    )

    if header.get("resultCode") != 0:
        raise HTTPException(
            status_code=502,
            detail={
                "message": (
                    "경기도 버스 API가 "
                    "오류를 반환했습니다."
                ),
                "resultCode": header.get(
                    "resultCode"
                ),
                "resultMessage": header.get(
                    "resultMessage"
                ),
            },
        )

    body = response_data.get(
        "msgBody",
        {},
    )

    arrivals = body.get(
        "busArrivalList",
        [],
    )

    if not isinstance(arrivals, list):
        return []

    return arrivals


def _is_low_floor(
    value: Any,
) -> bool:
    """
    GBIS lowPlate 값을 bool로 변환합니다.

    현재 API 응답 기준:
    1 → 저상버스
    0 → 일반버스
    """

    return str(value).strip() == "1"


def _optional_int(
    value: Any,
) -> int | None:
    if value in (
        None,
        "",
    ):
        return None

    try:
        return int(value)

    except (
        TypeError,
        ValueError,
    ):
        return None


def find_route_arrival(
    arrivals: list[dict[str, Any]],
    route_id: str,
) -> dict[str, Any] | None:
    """
    정류장 전체 도착정보에서
    특정 GBIS routeId의 정보를 찾습니다.
    """

    target_route_id = str(
        route_id
    ).strip()

    for arrival in arrivals:

        current_route_id = str(
            arrival.get(
                "routeId",
                "",
            )
        ).strip()

        if current_route_id == target_route_id:
            return arrival

    return None


def extract_low_floor_buses(
    arrival: dict[str, Any],
) -> list[dict[str, Any]]:
    """
    첫 번째/두 번째 도착 예정 차량 중
    저상버스만 추출합니다.
    """

    low_floor_buses = []

    for order in (
        1,
        2,
    ):
        low_plate = arrival.get(
            f"lowPlate{order}"
        )

        if not _is_low_floor(
            low_plate
        ):
            continue

        low_floor_buses.append(
            {
                "arrival_order": order,
                "vehicle_id": arrival.get(
                    f"vehId{order}"
                ),
                "plate_number": arrival.get(
                    f"plateNo{order}"
                ),
                "arrival_minutes": _optional_int(
                    arrival.get(
                        f"predictTime{order}"
                    )
                ),
                "arrival_seconds": _optional_int(
                    arrival.get(
                        f"predictTimeSec{order}"
                    )
                ),
                "remaining_stops": _optional_int(
                    arrival.get(
                        f"locationNo{order}"
                    )
                ),
                "remaining_seats": _optional_int(
                    arrival.get(
                        f"remainSeatCnt{order}"
                    )
                ),
            }
        )

    return low_floor_buses


async def get_low_floor_bus_status(
    station_id: str,
    route_id: str,
    bus_number: str | None = None,
) -> dict[str, Any]:
    """
    특정 정류장 + 노선에 대해
    현재 도착 예정 저상버스가 있는지 확인합니다.
    """

    arrivals = await get_bus_arrivals(
        station_id=station_id
    )

    route_arrival = find_route_arrival(
        arrivals=arrivals,
        route_id=route_id,
    )

    if route_arrival is None:
        return {
            "status": "NO_REALTIME_ARRIVAL",
            "bus_number": bus_number,
            "route_id": route_id,
            "station_id": station_id,
            "low_floor_bus_available": False,
            "next_low_floor_bus": None,
            "low_floor_buses": [],
        }

    low_floor_buses = extract_low_floor_buses(
        route_arrival
    )

    # 가장 빨리 도착하는 저상버스 선택
    buses_with_time = [
        bus
        for bus in low_floor_buses
        if bus["arrival_seconds"] is not None
    ]

    if buses_with_time:
        next_low_floor_bus = min(
            buses_with_time,
            key=lambda bus: bus[
                "arrival_seconds"
            ],
        )

    elif low_floor_buses:
        next_low_floor_bus = low_floor_buses[0]

    else:
        next_low_floor_bus = None

    return {
        "status": (
            "AVAILABLE"
            if low_floor_buses
            else "NO_LOW_FLOOR_BUS"
        ),
        "bus_number": (
            bus_number
            or str(
                route_arrival.get(
                    "routeName",
                    "",
                )
            )
        ),
        "route_id": route_id,
        "station_id": station_id,
        "low_floor_bus_available": bool(
            low_floor_buses
        ),
        "next_low_floor_bus": next_low_floor_bus,
        "low_floor_buses": low_floor_buses,
    }