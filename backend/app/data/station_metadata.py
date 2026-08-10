from __future__ import annotations

from typing import Any


STATION_METADATA: dict[str, dict[str, Any]] = {
    "판교역": {
        "operation_address": "판교역로 160",
        "lines": {
            "경강선": {
                "operator_code": "KR",
                "line_code": "K5",
                "station_code": "K409",
                "facility_file": "pangyo_gyeonggang.json",
            },
            "신분당선": {
                "operator_code": "DX",
                "line_code": "D1",
                "station_code": "4311",
                "facility_file": "pangyo_shinbundang.json",
            },
        },
    },

    "정자역": {
        "operation_address": "성남대로 333",
        "lines": {
            "수인분당선": {
                "operator_code": "KR",
                "line_code": "K1",
                "station_code": "K230",
                "facility_file": "jeongja_suinbundang.json",
            },
            "신분당선": {
                "operator_code": "DX",
                "line_code": "D1",
                "station_code": "4312",
                "facility_file": "jeongja_shinbundang.json",
            },
        },
    },

    "수내역": {
        "operation_address": "성남대로 491",
        "lines": {
            "수인분당선": {
                "operator_code": "KR",
                "line_code": "K1",
                "station_code": "K229",
                "facility_file": "sunae_suinbundang.json",
            },
        },
    },

    "서현역": {
        "operation_address": "성남대로 601",
        "lines": {
            "수인분당선": {
                "operator_code": "KR",
                "line_code": "K1",
                "station_code": "K228",
                "facility_file": "seohyeon_suinbundang.json",
            },
        },
    },

    "이매역": {
        "operation_address": "성남대로 지하 738",
        "lines": {
            "경강선": {
                "operator_code": "KR",
                "line_code": "K5",
                "station_code": "K411",
                "facility_file": "imae_gyeonggang.json",
            },
            "수인분당선": {
                "operator_code": "KR",
                "line_code": "K1",
                "station_code": "K227",
                "facility_file": "imae_suinbundang.json",
            },
        },
    },

    "야탑역": {
        "operation_address": "성남대로 903",
        "lines": {
            "수인분당선": {
                "operator_code": "KR",
                "line_code": "K1",
                "station_code": "K226",
                "facility_file": "yatap_suinbundang.json",
            },
        },
    },
}


def get_station_metadata(
    station_name: str,
) -> dict[str, Any] | None:
    return STATION_METADATA.get(station_name)


def get_station_line_metadata(
    station_name: str,
    line_name: str,
) -> dict[str, str] | None:
    station = STATION_METADATA.get(station_name)

    if not station:
        return None

    return station.get("lines", {}).get(line_name)


def get_operation_address(
    station_name: str,
) -> str | None:
    station = STATION_METADATA.get(station_name)

    if not station:
        return None

    return station.get("operation_address")


def get_supported_lines(
    station_name: str,
) -> list[str]:
    station = STATION_METADATA.get(station_name)

    if not station:
        return []

    return list(
        station.get("lines", {}).keys()
    )


def is_supported_station(
    station_name: str,
) -> bool:
    return station_name in STATION_METADATA