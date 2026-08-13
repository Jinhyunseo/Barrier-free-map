from __future__ import annotations

from typing import Any


# ==============================================================================
# 성남시 역사 메타데이터
#
# 통합 시설 JSON:
# Elevator_Escalator_현황_통합.json
#
# 시설 데이터 조회 시 아래 3개 값을 이용합니다.
#
# operator_code -> railOprIsttCd
# line_code     -> lnCd
# station_code  -> stinCd
#
# facility_file은 더 이상 사용하지 않습니다.
# ==============================================================================

STATION_METADATA: dict[
    str,
    dict[str, Any],
] = {

    # ==========================================================================
    # 수인분당선
    # ==========================================================================

    "가천대역": {
        "operation_address": None,
        "lines": {
            "수인분당선": {
                "operator_code": "KR",
                "line_code": "K1",
                "station_code": "K223",
            },
        },
    },

    "태평역": {
        "operation_address": None,
        "lines": {
            "수인분당선": {
                "operator_code": "KR",
                "line_code": "K1",
                "station_code": "K224",
            },
        },
    },

    "모란역": {
        "operation_address": None,
        "lines": {
            "수인분당선": {
                "operator_code": "KR",
                "line_code": "K1",
                "station_code": "K225",
            },

            "8호선": {
                "operator_code": "S1",
                "line_code": "8",
                "station_code": "2827",
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
            },
        },
    },

    "이매역": {
        "operation_address": "성남대로 지하 738",
        "lines": {
            "수인분당선": {
                "operator_code": "KR",
                "line_code": "K1",
                "station_code": "K227",
            },

            "경강선": {
                "operator_code": "KR",
                "line_code": "K5",
                "station_code": "K411",
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
            },

            "신분당선": {
                "operator_code": "DX",
                "line_code": "D1",
                "station_code": "4312",
            },
        },
    },

    "미금역": {
        "operation_address": None,
        "lines": {
            "수인분당선": {
                "operator_code": "KR",
                "line_code": "K1",
                "station_code": "K231",
            },

            "신분당선": {
                "operator_code": "DX",
                "line_code": "D1",
                "station_code": "D13",
            },
        },
    },

    "오리역": {
        "operation_address": None,
        "lines": {
            "수인분당선": {
                "operator_code": "KR",
                "line_code": "K1",
                "station_code": "K232",
            },
        },
    },

    # ==========================================================================
    # 8호선
    # ==========================================================================

    "남위례역": {
        "operation_address": None,
        "lines": {
            "8호선": {
                "operator_code": "S1",
                "line_code": "8",
                "station_code": "2828",
            },
        },
    },

    "산성역": {
        "operation_address": None,
        "lines": {
            "8호선": {
                "operator_code": "S1",
                "line_code": "8",
                "station_code": "2822",
            },
        },
    },

    "남한산성입구역": {
        "operation_address": None,
        "lines": {
            "8호선": {
                "operator_code": "S1",
                "line_code": "8",
                "station_code": "2823",
            },
        },
    },

    "단대오거리역": {
        "operation_address": None,
        "lines": {
            "8호선": {
                "operator_code": "S1",
                "line_code": "8",
                "station_code": "2824",
            },
        },
    },

    "신흥역": {
        "operation_address": None,
        "lines": {
            "8호선": {
                "operator_code": "S1",
                "line_code": "8",
                "station_code": "2825",
            },
        },
    },

    "수진역": {
        "operation_address": None,
        "lines": {
            "8호선": {
                "operator_code": "S1",
                "line_code": "8",
                "station_code": "2826",
            },
        },
    },

    # ==========================================================================
    # 판교역
    # ==========================================================================

    "판교역": {
        "operation_address": "판교역로 160",
        "lines": {
            "경강선": {
                "operator_code": "KR",
                "line_code": "K5",
                "station_code": "K409",
            },

            "신분당선": {
                "operator_code": "DX",
                "line_code": "D1",
                "station_code": "4311",
            },
        },
    },

    # ==========================================================================
    # 성남역
    # ==========================================================================

    "성남역": {
        "operation_address": None,
        "lines": {
            "경강선": {
                "operator_code": "KR",
                "line_code": "K5",
                "station_code": "K410",
            },

            "GTX-A": {
                "operator_code": "GX",
                "line_code": "A",
                "station_code": "X109",
            },
        },
    },
}


# ==============================================================================
# 역 전체 메타데이터 조회
# ==============================================================================

def get_station_metadata(
    station_name: str,
) -> dict[str, Any] | None:
    """
    역 이름으로 전체 메타데이터를 반환합니다.
    """

    return STATION_METADATA.get(
        station_name
    )


# ==============================================================================
# 역 + 노선 메타데이터 조회
# ==============================================================================

def get_station_line_metadata(
    station_name: str,
    line_name: str,
) -> dict[str, str] | None:
    """
    역 이름 + 노선 이름으로
    operator / line / station code를 반환합니다.
    """

    station = STATION_METADATA.get(
        station_name
    )

    if not station:
        return None

    lines = station.get(
        "lines",
        {},
    )

    if not isinstance(
        lines,
        dict,
    ):
        return None

    line_metadata = lines.get(
        line_name
    )

    if not isinstance(
        line_metadata,
        dict,
    ):
        return None

    return line_metadata


# ==============================================================================
# 운영 주소 조회
# ==============================================================================

def get_operation_address(
    station_name: str,
) -> str | None:
    """
    역 운영 주소를 반환합니다.

    아직 주소가 등록되지 않은 역은
    None을 반환합니다.
    """

    station = STATION_METADATA.get(
        station_name
    )

    if not station:
        return None

    operation_address = station.get(
        "operation_address"
    )

    if not operation_address:
        return None

    return str(
        operation_address
    )


# ==============================================================================
# 지원 노선 조회
# ==============================================================================

def get_supported_lines(
    station_name: str,
) -> list[str]:
    """
    해당 역에서 지원하는 노선 목록을 반환합니다.
    """

    station = STATION_METADATA.get(
        station_name
    )

    if not station:
        return []

    lines = station.get(
        "lines",
        {},
    )

    if not isinstance(
        lines,
        dict,
    ):
        return []

    return list(
        lines.keys()
    )


# ==============================================================================
# 지원 역 여부
# ==============================================================================

def is_supported_station(
    station_name: str,
) -> bool:
    """
    해당 역이 현재 내부 접근성 분석 대상인지 확인합니다.
    """

    return (
        station_name
        in STATION_METADATA
    )


# ==============================================================================
# 전체 지원 역 목록
# ==============================================================================

def get_supported_stations(
) -> list[str]:
    """
    현재 등록된 전체 지원 역 목록을 반환합니다.
    """

    return list(
        STATION_METADATA.keys()
    )