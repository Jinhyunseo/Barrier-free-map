from __future__ import annotations

import json
import os
import re
from collections import defaultdict
from pathlib import Path
from typing import Any
from urllib.parse import unquote

import requests
from dotenv import load_dotenv

from app.data.realtime_facility_mapping import (
    get_realtime_facility_mapping,
)


load_dotenv()


# ==============================================================================
# 1. 기본 설정
# ==============================================================================

API_URL = (
    "https://apis.data.go.kr/"
    "B553664/ElevatorInformationService/"
    "getElevatorListM"
)

SERVICE_KEY = os.getenv(
    "ELEVATOR_SERVICE_KEY",
    "",
)


# facility_status_service.py
# backend/app/services/
#
# parent.parent = backend/app
APP_DIR = (
    Path(__file__)
    .resolve()
    .parent
    .parent
)

REALTIME_DATA_DIR = (
    APP_DIR
    / "data"
    / "realtime"
)


CLASSIFY_FIELDS = [
    "elvtrDivNm",
    "elvtrKindNm",
    "elvtrForm",
    "elvtrSeNm",
]


# ==============================================================================
# 2. 문자열 정규화
# ==============================================================================

def normalize_device_no(
    value: Any,
) -> str:
    """
    elevatorNo를 숫자 7자리 문자열로 통일합니다.
    """

    if value is None:
        return ""

    digits = re.sub(
        r"\D",
        "",
        str(value),
    )

    if not digits:
        return ""

    return digits.zfill(7)


def normalize_station_name(
    value: Any,
) -> str:

    text = str(
        value
        or ""
    ).strip()

    if not text:
        return ""

    if not text.endswith("역"):
        text += "역"

    return text


def normalize_floor(
    value: Any,
) -> str:

    if value is None:
        return ""

    text = (
        str(value)
        .strip()
        .upper()
        .replace(" ", "")
    )

    if text.endswith("F"):
        text = text[:-1]

    return text


def normalize_line_name(
    value: Any,
) -> str:
    """
    노선명 표현 차이를 조금 보정합니다.
    """

    text = (
        str(value or "")
        .strip()
        .replace(" ", "")
    )

    replacements = {
        "수인분당선": "분당선",
        "경의·중앙선": "경의중앙선",
    }

    for before, after in replacements.items():
        text = text.replace(
            before,
            after,
        )

    return text


def normalize_location(
    value: Any,
) -> str:
    """
    상세 위치 문자열 비교용 정규화.

    예:

    (B2) 삼동행 표 내는 곳 내 계단 옆
    (B3) 삼동행 승강장 3-4 출입문 앞

    과

    (B2)삼동행표내는곳내계단옆
    (B3)삼동행승강장3-4출입문앞

    을 동일하게 비교할 수 있도록 합니다.
    """

    if value is None:
        return ""

    text = str(
        value
    ).strip()

    if not text:
        return ""

    text = text.lower()

    # 공백 제거
    text = re.sub(
        r"\s+",
        "",
        text,
    )

    # 쉼표 / > / ↔ 등 표현 차이 제거
    text = re.sub(
        r"[,>↔→←]",
        "",
        text,
    )

    # 일부 흔한 구두점 제거
    text = re.sub(
        r"[._]",
        "",
        text,
    )

    return text


# ==============================================================================
# 3. 시설 종류 판별
# ==============================================================================

def classify_facility(
    item: dict[str, Any],
) -> str:

    text = " ".join(
        str(
            item.get(
                field,
                "",
            )
        )
        for field
        in CLASSIFY_FIELDS
    ).strip()

    if not text:
        text = " ".join(
            str(value)
            for value
            in item.values()
        )

    if (
        "에스컬레이터" in text
        or
        "무빙워크" in text
    ):
        return "ESCALATOR"

    if (
        "휠체어리프트" in text
        or
        "리프트" in text
    ):
        return "WHEELCHAIR_LIFT"

    if (
        "엘리베이터" in text
        or
        "승강기" in text
    ):
        return "ELEVATOR"

    return "OTHER"


# ==============================================================================
# 4. 운행 상태 정규화
# ==============================================================================

def normalize_operation_status(
    raw_status: Any,
) -> str:

    if raw_status is None:
        return "UNKNOWN"

    status = (
        str(raw_status)
        .strip()
        .replace(" ", "")
        .upper()
    )

    if not status:
        return "UNKNOWN"

    available_keywords = [
        "운행중",
        "정상",
        "정상운행",
        "가동중",
    ]

    for keyword in available_keywords:

        if keyword in status:
            return "AVAILABLE"

    unavailable_keywords = [
        "운행정지",
        "운행중지",
        "정지",
        "고장",
        "점검",
        "휴지",
        "폐지",
        "사용중지",
        "사용불가",
    ]

    for keyword in unavailable_keywords:

        if keyword in status:
            return "UNAVAILABLE"

    return "UNKNOWN"


# ==============================================================================
# 5. 역별 저장 JSON 경로
# ==============================================================================

def get_station_json_path(
    station_name: str,
) -> Path:

    station_name = (
        normalize_station_name(
            station_name
        )
    )

    return (
        REALTIME_DATA_DIR
        /
        f"{station_name} 승강기 현황.json"
    )


# ==============================================================================
# 6. 저장된 JSON 읽기
# ==============================================================================

def load_station_facilities_from_json(
    station_name: str,
) -> dict[str, Any]:

    path = get_station_json_path(
        station_name
    )

    if not path.exists():

        return {
            "status": "FILE_NOT_FOUND",
            "station_name": station_name,
            "items": [],
            "updated_at": None,
            "source": "JSON",
            "file_path": str(path),
            "message": (
                "저장된 승강기 현황 JSON이 없습니다."
            ),
        }

    try:

        with open(
            path,
            "r",
            encoding="utf-8",
        ) as file:

            payload = json.load(
                file
            )

    except (
        OSError,
        json.JSONDecodeError,
    ) as error:

        return {
            "status": "JSON_ERROR",
            "station_name": station_name,
            "items": [],
            "updated_at": None,
            "source": "JSON",
            "file_path": str(path),
            "message": str(error),
        }

    items_data = payload.get(
        "items",
        {},
    )

    devices: list[
        dict[str, Any]
    ] = []

    if isinstance(
        items_data,
        dict,
    ):

        for group_items in (
            items_data.values()
        ):

            if not isinstance(
                group_items,
                list,
            ):
                continue

            for item in group_items:

                if isinstance(
                    item,
                    dict,
                ):
                    devices.append(
                        item
                    )

    return {
        "status": "SUCCESS",

        "station_name": (
            station_name
        ),

        "items": devices,

        "total_count": len(
            devices
        ),

        "updated_at": (
            payload.get(
                "updated_at"
            )
        ),

        "source": "JSON",

        "file_path": str(
            path
        ),
    }


# ==============================================================================
# 7. 기존 실시간 API
#
# JSON이 없는 역을 위한 fallback
# ==============================================================================

def fetch_station_facilities(
    station_name: str,
    service_key: str | None = None,
) -> dict[str, Any]:

    key = (
        service_key
        or SERVICE_KEY
    )

    if not key:

        return {
            "status": "API_KEY_MISSING",
            "station_name": station_name,
            "items": [],
            "source": "API",
            "message": (
                "ELEVATOR_SERVICE_KEY가 "
                "설정되어 있지 않습니다."
            ),
        }

    params = {
        "serviceKey": unquote(
            key
        ),
        "numOfRows": "200",
        "pageNo": "1",
        "_type": "json",
        "sido": "경기",
        "sigungu": "성남",
        "buld_nm": station_name,
    }

    try:

        response = requests.get(
            API_URL,
            params=params,
            timeout=10,
        )

        response.raise_for_status()

        data = response.json()

    except (
        requests.exceptions.RequestException
    ) as error:

        return {
            "status": "API_ERROR",
            "station_name": station_name,
            "items": [],
            "source": "API",
            "message": str(error),
        }

    except json.JSONDecodeError as error:

        return {
            "status": "JSON_ERROR",
            "station_name": station_name,
            "items": [],
            "source": "API",
            "message": str(error),
        }

    items = (
        data
        .get(
            "response",
            {},
        )
        .get(
            "body",
            {},
        )
        .get(
            "items",
            {},
        )
        .get(
            "item",
            [],
        )
    )

    if isinstance(
        items,
        dict,
    ):
        items = [
            items
        ]

    if not isinstance(
        items,
        list,
    ):
        items = []

    filtered_items = []

    for item in items:

        if not isinstance(
            item,
            dict,
        ):
            continue

        buld_prpos = item.get(
            "buldPrpos"
        )

        if not buld_prpos:
            continue

        if isinstance(
            buld_prpos,
            str,
        ):

            if (
                "운수시설"
                in buld_prpos
            ):

                filtered_items.append(
                    item
                )

        elif isinstance(
            buld_prpos,
            list,
        ):

            if any(
                "운수시설"
                in str(value)
                for value
                in buld_prpos
            ):

                filtered_items.append(
                    item
                )

    return {
        "status": "SUCCESS",
        "station_name": station_name,
        "items": filtered_items,
        "total_count": len(
            filtered_items
        ),
        "updated_at": None,
        "source": "API",
    }


# ==============================================================================
# 8. 역 데이터 가져오기
#
# JSON 우선
# JSON 없으면 API
# ==============================================================================

def get_station_facility_data(
    station_name: str,
) -> dict[str, Any]:

    json_result = (
        load_station_facilities_from_json(
            station_name
        )
    )

    if (
        json_result.get(
            "status"
        )
        == "SUCCESS"
    ):
        return json_result

    api_result = (
        fetch_station_facilities(
            station_name
        )
    )

    if (
        api_result.get(
            "status"
        )
        == "SUCCESS"
    ):
        return api_result

    return json_result


# ==============================================================================
# 9. elevatorNo 정확 매칭
# ==============================================================================

def find_device_by_no(
    devices: list[dict[str, Any]],
    device_no: str,
) -> dict[str, Any] | None:

    target = (
        normalize_device_no(
            device_no
        )
    )

    if not target:
        return None

    for device in devices:

        current = (
            normalize_device_no(
                device.get(
                    "elevatorNo"
                )
            )
        )

        if current == target:
            return device

    return None


# ==============================================================================
# 10. 노선 비교
# ==============================================================================

def device_matches_line(
    device: dict[str, Any],
    line_name: str,
) -> bool:

    expected = (
        normalize_line_name(
            line_name
        )
    )

    if not expected:
        return True

    building_name = (
        normalize_line_name(
            device.get(
                "buldNm",
                "",
            )
        )
    )

    if not building_name:
        return True

    return (
        expected
        in building_name
    )


# ==============================================================================
# 11. ★ 상세 위치 기준 1:1 매칭
# ==============================================================================

def find_device_by_detail_location(
    facility: dict[str, Any],
    devices: list[dict[str, Any]],
) -> dict[str, Any] | None:
    """
    내부 그래프의 detail_location과
    저장 JSON의 dtlLoc이 일치하는 실제 장비를 찾습니다.

    우선:
    시설 종류 + 노선 + 상세 위치

    가 모두 일치해야 합니다.
    """

    detail_location = (
        normalize_location(
            facility.get(
                "detail_location"
            )
        )
    )

    if not detail_location:
        return None

    expected_type = (
        str(
            facility.get(
                "facility_type",
                "",
            )
        )
        .strip()
        .upper()
    )

    line_name = str(
        facility.get(
            "line_name",
            "",
        )
    ).strip()

    matches: list[
        dict[str, Any]
    ] = []

    for device in devices:

        # ----------------------------------------------------------
        # 시설 종류
        # ----------------------------------------------------------

        actual_type = (
            classify_facility(
                device
            )
        )

        if (
            expected_type
            and
            actual_type
            != expected_type
        ):
            continue

        # ----------------------------------------------------------
        # 노선
        # ----------------------------------------------------------

        if (
            line_name
            and
            not device_matches_line(
                device,
                line_name,
            )
        ):
            continue

        # ----------------------------------------------------------
        # 상세위치
        # ----------------------------------------------------------

        device_location = (
            normalize_location(
                device.get(
                    "dtlLoc"
                )
            )
        )

        if not device_location:
            continue

        if (
            detail_location
            == device_location
        ):

            matches.append(
                device
            )

    # 상세위치가 같은 장비가 정확히 1대일 때만
    # 진짜 1:1 매칭으로 인정
    if len(matches) == 1:

        return matches[0]

    return None


# ==============================================================================
# 12. 층 구간 비교
# ==============================================================================

def normalize_section(
    value: Any,
) -> tuple[str, str] | None:

    if value is None:
        return None

    text = (
        str(value)
        .strip()
        .upper()
        .replace(" ", "")
    )

    parts = text.split(
        "-"
    )

    if len(parts) != 2:
        return None

    first = normalize_floor(
        parts[0]
    )

    second = normalize_floor(
        parts[1]
    )

    if not first or not second:
        return None

    return (
        first,
        second,
    )


def same_floor_section(
    from_floor: Any,
    to_floor: Any,
    section_value: Any,
) -> bool:

    section = (
        normalize_section(
            section_value
        )
    )

    if not section:
        return False

    expected_from = (
        normalize_floor(
            from_floor
        )
    )

    expected_to = (
        normalize_floor(
            to_floor
        )
    )

    if (
        not expected_from
        or
        not expected_to
    ):
        return False

    actual_from, actual_to = (
        section
    )

    return (
        (
            expected_from
            == actual_from
            and
            expected_to
            == actual_to
        )
        or
        (
            expected_from
            == actual_to
            and
            expected_to
            == actual_from
        )
    )


# ==============================================================================
# 13. 구간 fallback 장비 검색
# ==============================================================================

def find_segment_devices(
    facility: dict[str, Any],
    devices: list[dict[str, Any]],
) -> list[dict[str, Any]]:

    expected_type = (
        str(
            facility.get(
                "facility_type",
                "",
            )
        )
        .upper()
    )

    line_name = str(
        facility.get(
            "line_name",
            "",
        )
    ).strip()

    from_floor = (
        facility.get(
            "actual_from_floor"
        )
        or
        facility.get(
            "edge_from_floor"
        )
    )

    to_floor = (
        facility.get(
            "actual_to_floor"
        )
        or
        facility.get(
            "edge_to_floor"
        )
    )

    candidates = []

    for device in devices:

        actual_type = (
            classify_facility(
                device
            )
        )

        if (
            expected_type
            and
            actual_type
            != expected_type
        ):
            continue

        if (
            line_name
            and
            not device_matches_line(
                device,
                line_name,
            )
        ):
            continue

        if not same_floor_section(
            from_floor,
            to_floor,
            device.get(
                "shuttleSection"
            ),
        ):
            continue

        candidates.append(
            device
        )

    return candidates


# ==============================================================================
# 14. 실제 장비 상태 결과 생성
# ==============================================================================

def build_device_status(
    device: dict[str, Any],
    facility: dict[str, Any],
    match_method: str,
    mapping_status: str,
    data_source: str,
    updated_at: Any,
) -> dict[str, Any]:

    raw_status = (
        device.get(
            "elvtrStts"
        )
    )

    realtime_status = (
        normalize_operation_status(
            raw_status
        )
    )

    expected_type = (
        str(
            facility.get(
                "facility_type",
                "",
            )
        )
        .upper()
    )

    actual_type = (
        classify_facility(
            device
        )
    )

    return {
        "realtime_status": (
            realtime_status
        ),

        "mapping_status": (
            mapping_status
        ),

        "match_method": (
            match_method
        ),

        "data_source": (
            data_source
        ),

        "updated_at": (
            updated_at
        ),

        "device_no": str(
            device.get(
                "elevatorNo",
                "",
            )
        ),

        "facility_type": (
            expected_type
        ),

        "api_facility_type": (
            actual_type
        ),

        "facility_type_matched": (
            (
                not expected_type
            )
            or
            (
                expected_type
                == actual_type
            )
        ),

        "raw_status": (
            raw_status
        ),

        "installation_place": (
            device.get(
                "dtlLoc"
            )
            or
            device.get(
                "installationPlace"
            )
        ),

        "shuttle_section": (
            device.get(
                "shuttleSection"
            )
        ),

        "exit_no": (
            device.get(
                "locationExitNo"
            )
        ),

        "pause_date": (
            device.get(
                "pauseAblDe"
            )
        ),

        "pause_reason": (
            device.get(
                "pauseAbleResn"
            )
        ),
    }


# ==============================================================================
# 15. 구간 fallback 상태
# ==============================================================================

def build_segment_fallback_status(
    facility: dict[str, Any],
    candidates: list[dict[str, Any]],
    data_source: str,
    updated_at: Any,
) -> dict[str, Any]:

    if not candidates:

        return {
            "realtime_status": (
                "UNKNOWN"
            ),

            "mapping_status": (
                "SEGMENT_NOT_FOUND"
            ),

            "match_method": (
                "STATION_LINE_FLOOR"
            ),

            "data_source": (
                data_source
            ),

            "updated_at": (
                updated_at
            ),

            "device_no": None,

            "raw_status": None,

            "message": (
                "동일 역·노선·시설종류·"
                "층 구간의 장비를 찾지 못했습니다."
            ),
        }

    available = []
    unavailable = []
    unknown = []

    for device in candidates:

        status = (
            normalize_operation_status(
                device.get(
                    "elvtrStts"
                )
            )
        )

        if status == "AVAILABLE":

            available.append(
                device
            )

        elif status == "UNAVAILABLE":

            unavailable.append(
                device
            )

        else:

            unknown.append(
                device
            )

    if available:

        representative = (
            available[0]
        )

        realtime_status = (
            "AVAILABLE"
        )

    elif (
        unavailable
        and
        not unknown
    ):

        representative = (
            unavailable[0]
        )

        realtime_status = (
            "UNAVAILABLE"
        )

    else:

        representative = (
            candidates[0]
        )

        realtime_status = (
            "UNKNOWN"
        )

    return {
        "realtime_status": (
            realtime_status
        ),

        "mapping_status": (
            "SEGMENT_FALLBACK"
        ),

        "match_method": (
            "STATION_LINE_FLOOR"
        ),

        "data_source": (
            data_source
        ),

        "updated_at": (
            updated_at
        ),

        "device_no": str(
            representative.get(
                "elevatorNo",
                "",
            )
        ),

        "facility_type": (
            facility.get(
                "facility_type"
            )
        ),

        "raw_status": (
            representative.get(
                "elvtrStts"
            )
        ),

        "matched_device_count": (
            len(candidates)
        ),

        "available_device_count": (
            len(available)
        ),

        "unavailable_device_count": (
            len(unavailable)
        ),

        "unknown_device_count": (
            len(unknown)
        ),

        "shuttle_section": (
            representative.get(
                "shuttleSection"
            )
        ),

        "message": (
            "정확한 장비 1:1 매칭 실패로 "
            "역·노선·시설종류·층 구간을 "
            "이용한 fallback 결과입니다."
        ),
    }


# ==============================================================================
# 16. 시설 하나의 실시간 상태
#
# 우선순위
#
# 1. edge_id → device_no 기존 확정 매핑
# 2. detail_location → dtlLoc 1:1 매핑
# 3. 역 + 노선 + 시설종류 + 층 구간 fallback
# ==============================================================================

def get_facility_realtime_status(
    facility: dict[str, Any],
    station_devices: list[dict[str, Any]],
    data_source: str = "UNKNOWN",
    updated_at: Any = None,
) -> dict[str, Any]:

    edge_id = str(
        facility.get(
            "edge_id",
            "",
        )
    ).strip()

    # --------------------------------------------------------------------------
    # 1순위
    # 기존 edge_id → device_no 확정 매핑
    # --------------------------------------------------------------------------

    mapping = None

    if edge_id:

        mapping = (
            get_realtime_facility_mapping(
                edge_id
            )
        )

    if mapping:

        device_no = (
            mapping.get(
                "device_no"
            )
        )

        if device_no:

            device = (
                find_device_by_no(
                    station_devices,
                    str(device_no),
                )
            )

            if device:

                return (
                    build_device_status(
                        device=device,

                        facility=facility,

                        match_method=(
                            "DEVICE_NO"
                        ),

                        mapping_status=(
                            "CONFIRMED"
                        ),

                        data_source=(
                            data_source
                        ),

                        updated_at=(
                            updated_at
                        ),
                    )
                )

    # --------------------------------------------------------------------------
    # 2순위
    # 상세 위치 기반 1:1 매칭
    # --------------------------------------------------------------------------

    location_device = (
        find_device_by_detail_location(
            facility,
            station_devices,
        )
    )

    if location_device:

        return (
            build_device_status(
                device=(
                    location_device
                ),

                facility=(
                    facility
                ),

                match_method=(
                    "DETAIL_LOCATION"
                ),

                mapping_status=(
                    "CONFIRMED"
                ),

                data_source=(
                    data_source
                ),

                updated_at=(
                    updated_at
                ),
            )
        )

    # --------------------------------------------------------------------------
    # 3순위
    # 기존 구간 fallback
    # --------------------------------------------------------------------------

    candidates = (
        find_segment_devices(
            facility,
            station_devices,
        )
    )

    return (
        build_segment_fallback_status(
            facility=facility,

            candidates=candidates,

            data_source=(
                data_source
            ),

            updated_at=(
                updated_at
            ),
        )
    )


# ==============================================================================
# 17. required_facilities 전체에 상태 추가
# ==============================================================================

def attach_realtime_status_to_facilities(
    required_facilities: list[
        dict[str, Any]
    ],
) -> list[dict[str, Any]]:

    if not required_facilities:
        return []

    facilities_by_station: dict[
        str,
        list[dict[str, Any]],
    ] = defaultdict(
        list
    )

    for facility in (
        required_facilities
    ):

        station_name = str(
            facility.get(
                "station_name",
                "",
            )
        ).strip()

        if not station_name:
            continue

        facilities_by_station[
            station_name
        ].append(
            facility
        )

    # --------------------------------------------------------------------------
    # 역별 JSON/API 결과 캐시
    # --------------------------------------------------------------------------

    station_cache: dict[
        str,
        dict[str, Any],
    ] = {}

    for station_name in (
        facilities_by_station
    ):

        station_cache[
            station_name
        ] = (
            get_station_facility_data(
                station_name
            )
        )

    result = []

    for facility in (
        required_facilities
    ):

        copied = dict(
            facility
        )

        edge_id = str(
            facility.get(
                "edge_id",
                "",
            )
        ).strip()

        station_name = str(
            facility.get(
                "station_name",
                "",
            )
        ).strip()

        if not edge_id:

            realtime_info = {
                "realtime_status": (
                    "UNKNOWN"
                ),

                "mapping_status": (
                    "INVALID_EDGE"
                ),

                "device_no": None,

                "raw_status": None,

                "message": (
                    "edge_id가 없습니다."
                ),
            }

        elif not station_name:

            realtime_info = {
                "realtime_status": (
                    "UNKNOWN"
                ),

                "mapping_status": (
                    "INVALID_STATION"
                ),

                "device_no": None,

                "raw_status": None,

                "message": (
                    "station_name이 없습니다."
                ),
            }

        else:

            station_result = (
                station_cache.get(
                    station_name,
                    {},
                )
            )

            station_status = (
                station_result.get(
                    "status"
                )
            )

            if (
                station_status
                != "SUCCESS"
            ):

                realtime_info = {
                    "realtime_status": (
                        "UNKNOWN"
                    ),

                    "mapping_status": (
                        "DATA_NOT_AVAILABLE"
                    ),

                    "device_no": None,

                    "raw_status": None,

                    "data_source": (
                        station_result.get(
                            "source"
                        )
                    ),

                    "updated_at": (
                        station_result.get(
                            "updated_at"
                        )
                    ),

                    "message": (
                        station_result.get(
                            "message",
                            (
                                "승강기 운행정보를 "
                                "불러오지 못했습니다."
                            ),
                        )
                    ),
                }

            else:

                realtime_info = (
                    get_facility_realtime_status(
                        facility=(
                            facility
                        ),

                        station_devices=(
                            station_result.get(
                                "items",
                                [],
                            )
                        ),

                        data_source=(
                            station_result.get(
                                "source",
                                "UNKNOWN",
                            )
                        ),

                        updated_at=(
                            station_result.get(
                                "updated_at"
                            )
                        ),
                    )
                )

        copied[
            "realtime"
        ] = (
            realtime_info
        )

        result.append(
            copied
        )

    return result


# ==============================================================================
# 18. 전체 경로 시설 상태 요약
# ==============================================================================

def summarize_route_facility_status(
    facilities: list[
        dict[str, Any]
    ],
) -> dict[str, Any]:

    if not facilities:

        return {
            "status": "AVAILABLE",
            "total_facility_count": 0,
            "available_count": 0,
            "unavailable_count": 0,
            "unknown_count": 0,
        }

    available_count = 0
    unavailable_count = 0
    unknown_count = 0

    for facility in facilities:

        realtime = (
            facility.get(
                "realtime",
                {},
            )
        )

        if not isinstance(
            realtime,
            dict,
        ):

            realtime = {}

        status = (
            realtime.get(
                "realtime_status",
                "UNKNOWN",
            )
        )

        if status == "AVAILABLE":

            available_count += 1

        elif status == "UNAVAILABLE":

            unavailable_count += 1

        else:

            unknown_count += 1

    if unavailable_count > 0:

        route_status = (
            "UNAVAILABLE"
        )

    elif unknown_count > 0:

        route_status = (
            "UNKNOWN"
        )

    else:

        route_status = (
            "AVAILABLE"
        )

    return {
        "status": (
            route_status
        ),

        "total_facility_count": (
            len(facilities)
        ),

        "available_count": (
            available_count
        ),

        "unavailable_count": (
            unavailable_count
        ),

        "unknown_count": (
            unknown_count
        ),
    }