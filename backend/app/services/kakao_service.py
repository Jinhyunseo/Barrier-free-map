import os

import httpx
from dotenv import load_dotenv
from fastapi import HTTPException
from typing import Any


load_dotenv()


KAKAO_REST_API_KEY = os.getenv(
    "KAKAO_REST_API_KEY"
)

KAKAO_TRANSIT_URL = (
    "https://dapi.kakao.com/v2/routing/publictraffic"
)


# ==============================================================================
# 1. 카카오 대중교통 경로 조회
# ==============================================================================

async def get_transit_routes(
    origin_x: float,
    origin_y: float,
    destination_x: float,
    destination_y: float,
) -> dict[str, Any]:

    if not KAKAO_REST_API_KEY:
        raise RuntimeError(
            "KAKAO_REST_API_KEY가 없습니다. "
            "backend/.env 파일을 확인하세요."
        )

    headers = {
        "Authorization": (
            f"KakaoAK {KAKAO_REST_API_KEY}"
        ),
    }

    params = {
        "start_x": origin_x,
        "start_y": origin_y,
        "end_x": destination_x,
        "end_y": destination_y,
    }

    try:

        async with httpx.AsyncClient(
            timeout=20.0
        ) as client:

            response = await client.get(
                KAKAO_TRANSIT_URL,
                headers=headers,
                params=params,
            )

        response.raise_for_status()

        return response.json()

    except httpx.HTTPStatusError as exc:

        raise HTTPException(
            status_code=(
                exc.response.status_code
            ),
            detail={
                "message": (
                    "카카오 대중교통 API 호출에 "
                    "실패했습니다."
                ),
                "kakao_response": (
                    exc.response.text
                ),
            },
        ) from exc

    except httpx.RequestError as exc:

        raise HTTPException(
            status_code=502,
            detail=(
                "카카오 API 서버에 "
                "연결하지 못했습니다: "
                f"{str(exc)}"
            ),
        ) from exc


# ==============================================================================
# 2. 환승 정류장 중복 제거
# ==============================================================================

def remove_duplicate_stops(
    stops: list[str],
) -> list[str]:
    """
    순서를 유지하면서 중복된 역/정류장 이름을 제거합니다.

    예:
    ["이매", "이매"]
    -> ["이매"]
    """

    result: list[str] = []

    for stop in stops:

        if stop not in result:
            result.append(
                stop
            )

    return result


# ==============================================================================
# 3. 환승 안내 문구 보정
# ==============================================================================

def normalize_transfer_guidance(
    guidance: Any,
    stops: list[str],
) -> str | None:
    """
    카카오 WALKING 환승 안내가 다음처럼
    중복되는 경우를 보정합니다.

    이매이매역 환승
    정자정자역 환승

    환승 WALKING step의 stop이 동일 역이면
    해당 역 이름을 이용해 새 안내 문구를 만듭니다.
    """

    if guidance is None:
        return None

    text = str(
        guidance
    ).strip()

    if not text:
        return text

    # 환승 안내가 아니면 원본 그대로
    if "환승" not in text:
        return text

    unique_stops = (
        remove_duplicate_stops(
            stops
        )
    )

    # 같은 역 내부 환승인 경우
    # stop 이름으로 안내 문구를 재생성
    if len(unique_stops) == 1:

        station_name = (
            unique_stops[0]
            .strip()
        )

        if station_name:

            if not station_name.endswith(
                "역"
            ):
                station_name = (
                    f"{station_name}역"
                )

            return (
                f"{station_name} 환승"
            )

    return text


# ==============================================================================
# 4. 경로 단순화
# ==============================================================================

def simplify_routes(
    kakao_data: dict[str, Any],
) -> dict[str, Any]:
    """
    카카오에서 받은 복잡한 경로 JSON을
    우리 서비스에서 사용하기 쉬운 형태로 바꿉니다.
    """

    simplified_routes = []

    # --------------------------------------------------------------------------
    # 카카오가 반환한 경로들을 하나씩 확인
    # --------------------------------------------------------------------------

    for route_number, route in enumerate(
        kakao_data.get(
            "routes",
            [],
        ),
        start=1,
    ):

        route_properties = (
            route.get(
                "properties",
                {},
            )
        )

        vehicles = []
        stops = []
        path = []
        steps = []

        # ----------------------------------------------------------------------
        # 하나의 경로 안에 있는 이동 구간 확인
        # ----------------------------------------------------------------------

        for step_number, step in enumerate(
            route.get(
                "steps",
                [],
            ),
            start=1,
        ):

            step_properties = (
                step.get(
                    "properties",
                    {},
                )
            )

            step_vehicles = []
            step_stops = []

            # ------------------------------------------------------------------
            # 버스 번호 또는 지하철 노선 추출
            # ------------------------------------------------------------------

            for vehicle in (
                step_properties.get(
                    "vehicles",
                    [],
                )
            ):

                vehicle_data = {
                    "name": (
                        vehicle.get(
                            "name"
                        )
                    ),
                    "type": (
                        vehicle.get(
                            "type"
                        )
                    ),
                }

                step_vehicles.append(
                    vehicle_data
                )

                # 경로 전체 노선 목록에는 중복 없이 추가
                if (
                    vehicle_data
                    not in vehicles
                ):
                    vehicles.append(
                        vehicle_data
                    )

            # ------------------------------------------------------------------
            # 정류장 또는 역 이름 추출
            # ------------------------------------------------------------------

            for stop in (
                step_properties.get(
                    "stops",
                    [],
                )
            ):

                if not isinstance(
                    stop,
                    dict,
                ):
                    continue

                stop_name = (
                    stop.get(
                        "name"
                    )
                )

                if stop_name:

                    stop_name = str(
                        stop_name
                    ).strip()

                    if stop_name:
                        step_stops.append(
                            stop_name
                        )

                        # 전체 경로 stops에는 중복 없이 추가
                        if (
                            stop_name
                            not in stops
                        ):
                            stops.append(
                                stop_name
                            )

            # ------------------------------------------------------------------
            # step 타입
            # ------------------------------------------------------------------

            step_type = (
                step_properties.get(
                    "type"
                )
            )

            normalized_step_type = (
                str(
                    step_type
                    or ""
                )
                .strip()
                .upper()
            )

            # ------------------------------------------------------------------
            # WALKING 환승 step 보정
            # ------------------------------------------------------------------

            step_guidance = (
                step_properties.get(
                    "guidance"
                )
            )

            if (
                normalized_step_type
                == "WALKING"
                and
                "환승"
                in str(
                    step_guidance
                    or ""
                )
            ):

                # ["이매", "이매"] -> ["이매"]
                step_stops = (
                    remove_duplicate_stops(
                        step_stops
                    )
                )

                # 이매이매역 환승 -> 이매역 환승
                step_guidance = (
                    normalize_transfer_guidance(
                        guidance=(
                            step_guidance
                        ),
                        stops=(
                            step_stops
                        ),
                    )
                )

            # ------------------------------------------------------------------
            # 지도 경로선 좌표
            # ------------------------------------------------------------------

            step_path = (
                step.get(
                    "path",
                    {},
                )
                .get(
                    "points",
                    [],
                )
            )

            if not isinstance(
                step_path,
                list,
            ):
                step_path = []

            path.extend(
                step_path
            )

            # ------------------------------------------------------------------
            # 구간별 정보 저장
            # ------------------------------------------------------------------

            steps.append(
                {
                    "step_id": (
                        step_number
                    ),

                    "step_type": (
                        step_type
                    ),

                    "guidance": (
                        step_guidance
                    ),

                    "distance": (
                        step_properties.get(
                            "distance"
                        )
                    ),

                    "time": (
                        step_properties.get(
                            "time"
                        )
                    ),

                    "vehicles": (
                        step_vehicles
                    ),

                    "stops": (
                        step_stops
                    ),

                    "path": (
                        step_path
                    ),
                }
            )

        # ----------------------------------------------------------------------
        # 경로 하나 저장
        # ----------------------------------------------------------------------

        simplified_routes.append(
            {
                "route_id": (
                    route_number
                ),

                "route_type": (
                    route_properties.get(
                        "type"
                    )
                ),

                "total_time_seconds": (
                    route_properties.get(
                        "totalTime"
                    )
                ),

                "total_time_minutes": (
                    seconds_to_minutes(
                        route_properties.get(
                            "totalTime"
                        )
                    )
                ),

                "total_distance_meters": (
                    route_properties.get(
                        "totalDistance"
                    )
                ),

                "transfer_count": (
                    route_properties.get(
                        "transfers"
                    )
                ),

                "fare": (
                    route_properties.get(
                        "fare",
                        {},
                    ).get(
                        "value"
                    )
                ),

                "vehicles": (
                    vehicles
                ),

                "stops": (
                    stops
                ),

                "steps": (
                    steps
                ),

                "path": (
                    path
                ),

                # --------------------------------------------------------------
                # 접근성 데이터
                # --------------------------------------------------------------

                "accessibility": {
                    "status": "UNKNOWN",

                    "has_broken_elevator": (
                        None
                    ),

                    "has_steep_slope": (
                        None
                    ),

                    "has_stairs": (
                        None
                    ),

                    "has_low_floor_bus": (
                        None
                    ),

                    "unavailable_reasons": (
                        []
                    ),
                },

                # --------------------------------------------------------------
                # 추천 알고리즘 결과
                # --------------------------------------------------------------

                "evaluation": {
                    "is_available": None,
                    "score": None,
                    "is_recommended": False,
                },

                # AI 추천 설명
                "recommendation_reason": (
                    None
                ),
            }
        )

    original_properties = (
        kakao_data.get(
            "properties",
            {},
        )
    )

    return {
        "status": (
            kakao_data.get(
                "status"
            )
        ),

        "total": (
            len(
                simplified_routes
            )
        ),

        "route_count": {
            "bus": (
                original_properties.get(
                    "bus",
                    0,
                )
            ),

            "subway": (
                original_properties.get(
                    "subway",
                    0,
                )
            ),

            "bus_and_subway": (
                original_properties.get(
                    "busAndSubway",
                    0,
                )
            ),
        },

        "routes": (
            simplified_routes
        ),
    }


# ==============================================================================
# 5. 초 → 분
# ==============================================================================

def seconds_to_minutes(
    seconds: int | None,
) -> int | None:
    """
    초 단위 시간을 분 단위로 바꿉니다.

    1초라도 남으면 다음 분으로 올림 처리합니다.

    예:
    1246초 → 21분
    """

    if seconds is None:
        return None

    return (
        seconds
        + 59
    ) // 60