from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.data.station_metadata import (
    get_station_line_metadata,
)


# ---------------------------------------------------------
# 시설 JSON 파일이 저장된 폴더
#
# 현재 파일:
# backend/app/services/station_facility_service.py
#
# 시설 데이터:
# backend/app/data/station_facilities/*.json
# ---------------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent.parent

FACILITY_DATA_DIR = (
    BASE_DIR
    / "data"
    / "station_facilities"
)


def get_facility_file_path(
    station_name: str,
    line_name: str,
) -> Path | None:
    """
    역명 + 노선명을 이용해 해당 시설 JSON 파일의
    전체 경로를 반환합니다.

    예:
    정자역 + 신분당선
    -> backend/app/data/station_facilities/
       jeongja_shinbundang.json
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

    return FACILITY_DATA_DIR / facility_file


def load_facility_json(
    station_name: str,
    line_name: str,
) -> dict[str, Any]:
    """
    해당 역·노선의 시설 JSON 파일을 읽습니다.

    JSON 파일은 현재 다음 구조입니다.

    [
        {
            "railOprIsttCd": "...",
            "lnCd": "...",
            "stinCd": "...",
            "elevators": [...],
            "escalators": [...]
        }
    ]

    따라서 리스트의 첫 번째 객체를 반환합니다.
    """

    file_path = get_facility_file_path(
        station_name=station_name,
        line_name=line_name,
    )

    if file_path is None:
        raise ValueError(
            f"지원하지 않는 역 또는 노선입니다: "
            f"{station_name} / {line_name}"
        )

    if not file_path.exists():
        raise FileNotFoundError(
            f"시설 JSON 파일을 찾을 수 없습니다: "
            f"{file_path}"
        )

    try:
        with file_path.open(
            "r",
            encoding="utf-8",
        ) as file:
            raw_data = json.load(file)

    except json.JSONDecodeError as error:
        raise ValueError(
            f"시설 JSON 형식이 올바르지 않습니다: "
            f"{file_path.name}"
        ) from error

    # 현재 JSON은 [ { ... } ] 구조
    if isinstance(raw_data, list):

        if not raw_data:
            raise ValueError(
                f"시설 JSON 데이터가 비어 있습니다: "
                f"{file_path.name}"
            )

        station_data = raw_data[0]

    elif isinstance(raw_data, dict):
        # 추후 JSON 구조가 객체 형태로 바뀌더라도
        # 대응할 수 있도록 처리
        station_data = raw_data

    else:
        raise ValueError(
            f"지원하지 않는 JSON 구조입니다: "
            f"{file_path.name}"
        )

    if not isinstance(station_data, dict):
        raise ValueError(
            f"시설 데이터가 객체 형태가 아닙니다: "
            f"{file_path.name}"
        )

    return station_data


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

    if not isinstance(elevators, list):
        return []

    return [
        elevator
        for elevator in elevators
        if isinstance(elevator, dict)
    ]


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

    if not isinstance(escalators, list):
        return []

    return [
        escalator
        for escalator in escalators
        if isinstance(escalator, dict)
    ]


def normalize_elevator(
    elevator: dict[str, Any],
) -> dict[str, Any]:
    """
    KRIC 형식의 엘리베이터 데이터를
    우리 서비스 내부 형식으로 변환합니다.
    """

    return {
        "facility_type": "ELEVATOR",

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

        # 실시간 운행정보는 아직 연결하지 않았으므로
        # 미확인 상태로 둡니다.
        "operation_status": "UNKNOWN",

        "is_operating": None,
    }


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
        "facility_type": "ESCALATOR",

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

        # 실시간 운행정보는 아직 연결하지 않았으므로
        # 미확인 상태로 둡니다.
        "operation_status": "UNKNOWN",

        "is_operating": None,
    }


def get_station_facilities(
    station_name: str,
    line_name: str,
) -> dict[str, Any]:
    """
    해당 역·노선의 엘리베이터와
    에스컬레이터를 함께 반환합니다.

    이 함수가 외부에서 주로 사용할 메인 함수입니다.

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
        raw_elevators = get_station_elevators(
            station_name=station_name,
            line_name=line_name,
        )

        raw_escalators = get_station_escalators(
            station_name=station_name,
            line_name=line_name,
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
        normalize_elevator(elevator)
        for elevator in raw_elevators
    ]

    escalators = [
        normalize_escalator(escalator)
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