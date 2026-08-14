from __future__ import annotations

from typing import Any


REALTIME_FACILITY_MAPPING: dict[str, dict[str, Any]] = {

    # ==========================================================================
    # 정자역 - 수인분당선 ELEVATOR
    # ==========================================================================

    # 2번 출구
    "JGJ_01_EV_001": {
        "station_name": "정자역",
        "line_name": "수인분당선",
        "facility_type": "ELEVATOR",
        "device_no": "2056151",
        "mapping_status": "CONFIRMED",
    },

    # 4번 출구
    "JGJ_01_EV_002": {
        "station_name": "정자역",
        "line_name": "수인분당선",
        "facility_type": "ELEVATOR",
        "device_no": "2056152",
        "mapping_status": "CONFIRMED",
    },

    # 미금 방향(하행) B2 ↔ B1
    "JGJ_01_EV_003": {
        "station_name": "정자역",
        "line_name": "수인분당선",
        "facility_type": "ELEVATOR",
        "device_no": "2050987",
        "mapping_status": "CONFIRMED",
    },

    # 수내 방향(상행) B2 ↔ B1
    "JGJ_01_EV_004": {
        "station_name": "정자역",
        "line_name": "수인분당선",
        "facility_type": "ELEVATOR",
        "device_no": "2050986",
        "mapping_status": "CONFIRMED",
    },


    # ==========================================================================
    # 정자역 - 수인분당선 ESCALATOR
    # ==========================================================================

    # 미금 방향 B2 → B1
    "JGJ_01_ES_009": {
        "station_name": "정자역",
        "line_name": "수인분당선",
        "facility_type": "ESCALATOR",
        "device_no": "3807412",
        "mapping_status": "CONFIRMED",
    },

    # 미금 방향 B1 → B2
    "JGJ_01_ES_010": {
        "station_name": "정자역",
        "line_name": "수인분당선",
        "facility_type": "ESCALATOR",
        "device_no": "3807411",
        "mapping_status": "CONFIRMED",
    },

    # 수내 방향 B2 → B1
    "JGJ_01_ES_011": {
        "station_name": "정자역",
        "line_name": "수인분당선",
        "facility_type": "ESCALATOR",
        "device_no": "3807410",
        "mapping_status": "CONFIRMED",
    },

    # 수내 방향 B1 → B2
    "JGJ_01_ES_012": {
        "station_name": "정자역",
        "line_name": "수인분당선",
        "facility_type": "ESCALATOR",
        "device_no": "3807409",
        "mapping_status": "CONFIRMED",
    },


    # ==========================================================================
    # 정자역 - 신분당선 ELEVATOR
    # ==========================================================================

    # 6번 출구
    "JGJ_02_EV_001": {
        "station_name": "정자역",
        "line_name": "신분당선",
        "facility_type": "ELEVATOR",
        "device_no": "2051672",
        "mapping_status": "CONFIRMED",
    },

    # 미금 방향 환승 연결
    "JGJ_02_EV_002": {
        "station_name": "정자역",
        "line_name": "신분당선",
        "facility_type": "ELEVATOR",
        "device_no": "2051675",
        "mapping_status": "CONFIRMED",
    },

    # 수내 방향 환승 연결
    "JGJ_02_EV_003": {
        "station_name": "정자역",
        "line_name": "신분당선",
        "facility_type": "ELEVATOR",
        "device_no": "2051676",
        "mapping_status": "CONFIRMED",
    },

    # 판교 방향 B3 ↔ B2
    "JGJ_02_EV_004": {
        "station_name": "정자역",
        "line_name": "신분당선",
        "facility_type": "ELEVATOR",
        "device_no": "2051674",
        "mapping_status": "CONFIRMED",
    },

    # 미금 방향 B3 ↔ B2
    "JGJ_02_EV_005": {
        "station_name": "정자역",
        "line_name": "신분당선",
        "facility_type": "ELEVATOR",
        "device_no": "2051673",
        "mapping_status": "CONFIRMED",
    },
}


def get_realtime_facility_mapping(
    edge_id: str,
) -> dict[str, Any] | None:
    """
    내부 그래프 edge_id에 대응하는
    실시간 장비 매핑 정보를 반환합니다.
    """

    return REALTIME_FACILITY_MAPPING.get(
        edge_id
    )


def get_realtime_device_no(
    edge_id: str,
) -> str | None:
    """
    edge_id에 대응하는 실시간 API 장비번호를 반환합니다.
    """

    mapping = (
        get_realtime_facility_mapping(
            edge_id
        )
    )

    if not mapping:
        return None

    device_no = mapping.get(
        "device_no"
    )

    if not device_no:
        return None

    return str(
        device_no
    )