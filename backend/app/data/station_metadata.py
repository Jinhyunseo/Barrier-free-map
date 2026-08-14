from __future__ import annotations

from typing import Any


STATION_METADATA: dict[str, dict[str, Any]] = {
    "판교역": {
        "latitude": 37.3947611,
        "longitude": 127.1111361,
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
        "latitude": 37.3662800,
        "longitude": 127.1081200,
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
        "latitude": 37.3785528,
        "longitude": 127.1142750,
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
        "latitude": 37.3851167,
        "longitude": 127.1232944,
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
        "latitude": 37.3957300,
        "longitude": 127.1283700,
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
        "latitude": 37.4111390,
        "longitude": 127.1287220,
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


def get_station_coordinates(
    *,
    station_name: str | None = None,
    station_code: str | None = None,
    line_code: str | None = None,
) -> tuple[float, float] | None:
    """프로젝트에 미리 저장된 역 대표 좌표를 반환합니다.

    station_name이 정확히 일치하면 우선 사용하고, 이름이 없거나 파일명 인코딩 등으로
    일치하지 않는 경우 station_code/line_code로 다시 찾습니다.
    반환 순서는 (latitude, longitude) 입니다.
    """

    if station_name:
        station = STATION_METADATA.get(station_name)
        if station:
            latitude = station.get("latitude")
            longitude = station.get("longitude")
            if latitude is not None and longitude is not None:
                return float(latitude), float(longitude)

    if station_code:
        for station in STATION_METADATA.values():
            for line in station.get("lines", {}).values():
                if line.get("station_code") != station_code:
                    continue
                if line_code and line.get("line_code") != line_code:
                    continue

                latitude = station.get("latitude")
                longitude = station.get("longitude")
                if latitude is not None and longitude is not None:
                    return float(latitude), float(longitude)

    return None
