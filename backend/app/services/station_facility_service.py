from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.data.station_metadata import (
    get_station_line_metadata,
)


# ---------------------------------------------------------
# 기본 경로
# ---------------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent.parent

FACILITY_DATA_DIR = (
    BASE_DIR
    / "data"
    / "station_facilities"
)


# ---------------------------------------------------------
# 성남시 전체 역/노선 시설 통합 JSON
# ---------------------------------------------------------

INTEGRATED_FACILITY_FILE = (
    FACILITY_DATA_DIR
    / "Elevator_Escalator_현황_통합.json"
)


# ---------------------------------------------------------
# 기존 개별 JSON 경로 조회
#
# 기존 6개 JSON 파일은 당분간 삭제하지 않고
# 비교/백업용으로 유지합니다.
# ---------------------------------------------------------

def get_facility_file_path(
    station_name: str,
    line_name: str,
) -> Path | None:
    """
    station_metadata.py에 등록된 facility_file을 이용해
    기존 개별 시설 JSON 파일의 경로를 반환합니다.

    현재 메인 로딩은 통합 JSON을 사용하지만,
    기존 데이터 비교 및 fallback 용도로 남겨둡니다.
    """

    line_metadata = get_station_line_metadata(
        station_name=station_name,
        line_name=line_name,
    )

    if not line_metadata:
        return None

    facility_file = line_metadata.get(
        "facility_file"
    )

    if not facility_file:
        return None

    return (
        FACILITY_DATA_DIR
        / facility_file
    )


# ---------------------------------------------------------
# 통합 JSON 로딩
# ---------------------------------------------------------

def _load_integrated_facility_data(
) -> list[dict[str, Any]]:
    """
    Elevator_Escalator_현황_통합.json 전체를 읽습니다.
    """

    if not INTEGRATED_FACILITY_FILE.exists():
        raise FileNotFoundError(
            "통합 시설 JSON 파일을 찾을 수 없습니다: "
            f"{INTEGRATED_FACILITY_FILE}"
        )

    try:
        with INTEGRATED_FACILITY_FILE.open(
            "r",
            encoding="utf-8",
        ) as file:
            raw_data = json.load(file)

    except json.JSONDecodeError as error:
        raise ValueError(
            "통합 시설 JSON 형식이 올바르지 않습니다: "
            f"{INTEGRATED_FACILITY_FILE.name}"
        ) from error

    if not isinstance(
        raw_data,
        list,
    ):
        raise ValueError(
            "통합 시설 JSON의 최상위 구조는 "
            "리스트여야 합니다."
        )

    return [
        item
        for item in raw_data
        if isinstance(
            item,
            dict,
        )
    ]


# ---------------------------------------------------------
# 역 + 노선별 시설 데이터 조회
# ---------------------------------------------------------

def load_facility_json(
    station_name: str,
    line_name: str,
) -> dict[str, Any]:
    """
    통합 시설 JSON에서
    특정 역 + 노선의 시설 데이터를 찾아 반환합니다.

    station_metadata.py의 다음 정보를 사용합니다.

    - operator_code
    - line_code
    - station_code

    위 세 값을 통합 JSON의

    - railOprIsttCd
    - lnCd
    - stinCd

    와 비교합니다.

    예:
    판교역 / 신분당선

    station_metadata:
        operator_code = DX
        line_code = D1
        station_code = 4311

    통합 JSON:
        railOprIsttCd = DX
        lnCd = D1
        stinCd = 4311
    """

    line_metadata = get_station_line_metadata(
        station_name=station_name,
        line_name=line_name,
    )

    if not line_metadata:
        raise ValueError(
            "지원하지 않는 역 또는 노선입니다: "
            f"{station_name} / {line_name}"
        )

    operator_code = str(
        line_metadata.get(
            "operator_code",
            "",
        )
    ).strip()

    line_code = str(
        line_metadata.get(
            "line_code",
            "",
        )
    ).strip()

    station_code = str(
        line_metadata.get(
            "station_code",
            "",
        )
    ).strip()

    if not (
        operator_code
        and line_code
        and station_code
    ):
        raise ValueError(
            "역 메타데이터가 불완전합니다: "
            f"{station_name} / {line_name}"
        )

    integrated_data = (
        _load_integrated_facility_data()
    )

    for station_data in integrated_data:

        data_operator_code = str(
            station_data.get(
                "railOprIsttCd",
                "",
            )
        ).strip()

        data_line_code = str(
            station_data.get(
                "lnCd",
                "",
            )
        ).strip()

        data_station_code = str(
            station_data.get(
                "stinCd",
                "",
            )
        ).strip()

        if (
            data_operator_code == operator_code
            and data_line_code == line_code
            and data_station_code == station_code
        ):
            return station_data

    raise ValueError(
        "통합 시설 JSON에서 해당 역·노선 데이터를 "
        "찾지 못했습니다: "
        f"{station_name} / {line_name} "
        f"(operator={operator_code}, "
        f"line={line_code}, "
        f"station={station_code})"
    )


# ---------------------------------------------------------
# 엘리베이터 조회
# ---------------------------------------------------------

def get_station_elevators(
    station_name: str,
    line_name: str,
) -> list[dict[str, Any]]:
    """
    해당 역·노선의 엘리베이터 목록을 반환합니다.
    """

    station_data = load_facility_json(
        station_name=station_name,
        line_name=line_name,
    )

    elevators = station_data.get(
        "elevators",
        [],
    )

    if not isinstance(
        elevators,
        list,
    ):
        return []

    return [
        elevator
        for elevator in elevators
        if isinstance(
            elevator,
            dict,
        )
    ]


# ---------------------------------------------------------
# 에스컬레이터 조회
# ---------------------------------------------------------

def get_station_escalators(
    station_name: str,
    line_name: str,
) -> list[dict[str, Any]]:
    """
    해당 역·노선의 에스컬레이터 목록을 반환합니다.
    """

    station_data = load_facility_json(
        station_name=station_name,
        line_name=line_name,
    )

    escalators = station_data.get(
        "escalators",
        [],
    )

    if not isinstance(
        escalators,
        list,
    ):
        return []

    return [
        escalator
        for escalator in escalators
        if isinstance(
            escalator,
            dict,
        )
    ]


# ---------------------------------------------------------
# 엘리베이터 데이터 정규화
# ---------------------------------------------------------

def normalize_elevator(
    elevator: dict[str, Any],
) -> dict[str, Any]:
    """
    KRIC 형식의 엘리베이터 데이터를
    우리 서비스 내부 형식으로 변환합니다.

    실시간 운행 상태는 여기서 판단하지 않습니다.

    실제 운행중 / 고장 / 점검 여부는
    facility_status_service의 실시간 API 로직에서
    별도로 반영합니다.
    """

    return {
        "facility_type": (
            "ELEVATOR"
        ),

        "operator_code": elevator.get(
            "railOprIsttCd"
        ),

        "line_code": elevator.get(
            "lnCd"
        ),

        "station_code": elevator.get(
            "stinCd"
        ),

        "exit_no": elevator.get(
            "exitNo"
        ),

        "detail_location": elevator.get(
            "dtlLoc"
        ),

        "from_ground_type": elevator.get(
            "grndDvNmFr"
        ),

        "from_floor": elevator.get(
            "runStinFlorFr"
        ),

        "to_ground_type": elevator.get(
            "grndDvNmTo"
        ),

        "to_floor": elevator.get(
            "runStinFlorTo"
        ),

        "capacity_persons": elevator.get(
            "rglnPsno"
        ),

        "capacity_weight_kg": elevator.get(
            "rglnWgt"
        ),

        # -------------------------------------------------
        # 정적 시설 데이터 단계에서는
        # 실시간 상태를 판단하지 않습니다.
        # -------------------------------------------------

        "operation_status": (
            "UNKNOWN"
        ),

        "is_operating": None,
    }


# ---------------------------------------------------------
# 에스컬레이터 데이터 정규화
# ---------------------------------------------------------

def normalize_escalator(
    escalator: dict[str, Any],
) -> dict[str, Any]:
    """
    KRIC 형식의 에스컬레이터 데이터를
    우리 서비스 내부 형식으로 변환합니다.
    """

    up_down = escalator.get(
        "updnDvNm"
    )

    if up_down == "상행":
        direction = "UP"

    elif up_down == "하행":
        direction = "DOWN"

    else:
        direction = "UNKNOWN"

    return {
        "facility_type": (
            "ESCALATOR"
        ),

        "operator_code": escalator.get(
            "railOprIsttCd"
        ),

        "line_code": escalator.get(
            "lnCd"
        ),

        "station_code": escalator.get(
            "stinCd"
        ),

        "exit_no": escalator.get(
            "exitNo"
        ),

        "detail_location": escalator.get(
            "dtlLoc"
        ),

        "from_ground_type": escalator.get(
            "grndDvNmFr"
        ),

        "from_floor": escalator.get(
            "runStinFlorFr"
        ),

        "to_ground_type": escalator.get(
            "grndDvNmTo"
        ),

        "to_floor": escalator.get(
            "runStinFlorTo"
        ),

        "direction": direction,

        "direction_name": up_down,

        # -------------------------------------------------
        # 실시간 상태는 별도 API에서 처리
        # -------------------------------------------------

        "operation_status": (
            "UNKNOWN"
        ),

        "is_operating": None,
    }


# ---------------------------------------------------------
# 역 전체 시설 조회
# ---------------------------------------------------------

def get_station_facilities(
    station_name: str,
    line_name: str,
) -> dict[str, Any]:
    """
    해당 역·노선의 엘리베이터와
    에스컬레이터를 함께 반환합니다.

    현재 메인 데이터 소스는

    Elevator_Escalator_현황_통합.json

    입니다.

    예:
    get_station_facilities(
        "정자역",
        "신분당선",
    )
    """

    line_metadata = get_station_line_metadata(
        station_name=station_name,
        line_name=line_name,
    )

    if not line_metadata:
        return {
            "station_name": station_name,
            "line_name": line_name,

            "status": "UNSUPPORTED",

            "message": (
                "현재 지원하지 않는 역 또는 "
                "노선입니다."
            ),

            "elevator_count": 0,
            "escalator_count": 0,
            "facility_count": 0,

            "elevators": [],
            "escalators": [],
            "facilities": [],
        }

    try:
        raw_elevators = (
            get_station_elevators(
                station_name=station_name,
                line_name=line_name,
            )
        )

        raw_escalators = (
            get_station_escalators(
                station_name=station_name,
                line_name=line_name,
            )
        )

    except (
        FileNotFoundError,
        ValueError,
    ) as error:

        return {
            "station_name": station_name,
            "line_name": line_name,

            "status": "ERROR",

            "message": str(error),

            "elevator_count": 0,
            "escalator_count": 0,
            "facility_count": 0,

            "elevators": [],
            "escalators": [],
            "facilities": [],
        }

    elevators = [
        normalize_elevator(
            elevator
        )
        for elevator in raw_elevators
    ]

    escalators = [
        normalize_escalator(
            escalator
        )
        for escalator in raw_escalators
    ]

    facilities = (
        elevators
        + escalators
    )

    return {
        "station_name": station_name,
        "line_name": line_name,

        "status": "SUCCESS",

        "operator_code": line_metadata.get(
            "operator_code"
        ),

        "line_code": line_metadata.get(
            "line_code"
        ),

        "station_code": line_metadata.get(
            "station_code"
        ),

        "elevator_count": len(
            elevators
        ),

        "escalator_count": len(
            escalators
        ),

        "facility_count": len(
            facilities
        ),

        "elevators": elevators,

        "escalators": escalators,

        "facilities": facilities,
    }