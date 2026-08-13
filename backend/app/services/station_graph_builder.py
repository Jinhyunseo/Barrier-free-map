from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from app.data.station_metadata import STATION_METADATA
from app.services.station_facility_service import load_facility_json


# ==============================================================================
# 1. 경로 설정
# ==============================================================================

APP_DIR = Path(__file__).resolve().parent.parent

FACILITY_DATA_DIR = (
    APP_DIR
    / "data"
    / "station_facilities"
)

GRAPH_DATA_DIR = (
    APP_DIR
    / "data"
    / "station_graphs"
)

OUTPUT_FILE = (
    GRAPH_DATA_DIR
    / "all_stations_graph.json"
)


# ==============================================================================
# 2. 서비스 내부 역 코드
# ==============================================================================

INTERNAL_STATION_CODES = {
    "가천대역": "GCH",
    "태평역": "TPG",
    "모란역": "MRN",
    "야탑역": "YTP",
    "이매역": "IME",
    "서현역": "SHY",
    "수내역": "SNE",
    "정자역": "JGJ",
    "미금역": "MGM",
    "오리역": "ORI",
    "남위례역": "NWR",
    "산성역": "SSG",
    "남한산성입구역": "NHS",
    "단대오거리역": "DDE",
    "신흥역": "SHN",
    "수진역": "SJN",
    "판교역": "PGY",
    "성남역": "SNM",
}


# ==============================================================================
# 3. 기본 유틸
# ==============================================================================

def normalize_floor(
    ground_type: Any,
    floor_number: Any,
) -> str:
    """
    KRIC 층 정보를 내부 표기 방식으로 변환합니다.

    예:
    지하 + 2 -> B2
    지상 + 1 -> 1F
    """

    try:
        floor = int(
            float(
                floor_number
            )
        )
    except (
        TypeError,
        ValueError,
    ):
        floor = 1

    ground_text = str(
        ground_type or ""
    ).strip()

    if ground_text == "지상":
        return f"{floor}F"

    return f"B{floor}"


def get_floor_depth(
    floor_code: str,
) -> int:
    """
    층 깊이를 비교하기 위한 함수입니다.

    B1 -> 1
    B2 -> 2
    B3 -> 3
    1F -> 0
    """

    if not floor_code:
        return 0

    floor_code = (
        floor_code.upper()
    )

    if floor_code.startswith(
        "B"
    ):
        try:
            return int(
                floor_code[1:]
            )
        except ValueError:
            return 0

    return 0


def normalize_exit_no(
    exit_no: Any,
) -> str | None:

    if exit_no is None:
        return None

    exit_text = str(
        exit_no
    ).strip()

    if not exit_text:
        return None

    match = re.search(
        r"\d+",
        exit_text,
    )

    if not match:
        return None

    return match.group()


def extract_exit_no_from_location(
    detail_location: str,
) -> str | None:

    match = re.search(
        r"(\d+)\s*번\s*출입구",
        detail_location,
    )

    if not match:
        return None

    return match.group(1)


def compact_text(
    text: Any,
) -> str:
    """
    위치 문자열 비교를 쉽게 하기 위해
    모든 공백을 제거합니다.
    """

    return re.sub(
        r"\s+",
        "",
        str(
            text or ""
        ),
    )


def contains_platform_keyword(
    text: str,
) -> bool:
    """
    해당 위치 설명이 승강장 쪽을 의미하는지 확인합니다.
    """

    compact = compact_text(
        text
    )

    return (
        "승강장" in compact
        or "출입문앞" in compact
        or "출입문맞은편" in compact
    )


def contains_concourse_keyword(
    text: str,
) -> bool:
    """
    해당 위치 설명이 대합실/맞이방 쪽을 의미하는지 확인합니다.
    """

    compact = compact_text(
        text
    )

    keywords = (
        "대합실",
        "맞이방",
        "표내는곳",
        "개집표구",
        "개찰구",
        "환승통로",
        "환승표내는곳",
    )

    return any(
        keyword in compact
        for keyword in keywords
    )


def is_transfer_area_text(
    text: Any,
) -> bool:
    """
    상세 위치가 환승 구역/환승 통로를 의미하는지 확인합니다.

    환승 관련 PLATFORM만 같은 층 CONCOURSE와
    WALKING으로 연결하기 위해 사용합니다.
    """

    compact = compact_text(
        text
    )

    keywords = (
        "환승통로",
        "환승표내는곳",
    )

    return any(
        keyword in compact
        for keyword in keywords
    )


def is_ground_connection(
    facility: dict[str, Any],
) -> bool:
    """
    지상 출입구와 연결되는 시설인지 판별합니다.
    """

    from_ground = str(
        facility.get(
            "grndDvNmFr",
            "",
        )
    ).strip()

    to_ground = str(
        facility.get(
            "grndDvNmTo",
            "",
        )
    ).strip()

    if (
        from_ground == "지상"
        or to_ground == "지상"
    ):
        return True

    detail_location = str(
        facility.get(
            "dtlLoc",
            "",
        )
    )

    if (
        "출입구" in detail_location
        and "승강장"
        not in detail_location
    ):
        return True

    return False


# ==============================================================================
# 4. 시설 JSON 읽기
# ==============================================================================

def load_facility_file(
    file_name: str,
) -> dict[str, Any]:

    file_path = (
        FACILITY_DATA_DIR
        / file_name
    )

    if not file_path.exists():
        raise FileNotFoundError(
            "시설 JSON 파일이 없습니다: "
            f"{file_path}"
        )

    with file_path.open(
        "r",
        encoding="utf-8",
    ) as file:
        raw_data = json.load(
            file
        )

    if isinstance(
        raw_data,
        list,
    ):

        if not raw_data:
            raise ValueError(
                "시설 JSON이 비어 있습니다: "
                f"{file_name}"
            )

        station_data = (
            raw_data[0]
        )

    elif isinstance(
        raw_data,
        dict,
    ):
        station_data = (
            raw_data
        )

    else:
        raise ValueError(
            "지원하지 않는 JSON 구조입니다: "
            f"{file_name}"
        )

    if not isinstance(
        station_data,
        dict,
    ):
        raise ValueError(
            "시설 데이터가 객체가 아닙니다: "
            f"{file_name}"
        )

    return station_data


# ==============================================================================
# 5. 노드 관리
# ==============================================================================

def add_node(
    nodes: dict[
        str,
        dict[str, Any],
    ],
    node: dict[str, Any],
) -> None:

    node_id = node[
        "id"
    ]

    if node_id not in nodes:
        nodes[
            node_id
        ] = node


def create_concourse_node(
    station_name: str,
    station_code: str,
    floor: str,
) -> dict[str, Any]:
    """
    층별 대합실 노드 생성.

    예:
    JGJ_B1_CONCOURSE
    JGJ_B2_CONCOURSE
    """

    node_id = (
        f"{station_code}_"
        f"{floor}_CONCOURSE"
    )

    return {
        "id": node_id,
        "station_code": (
            station_code
        ),
        "station_name": (
            station_name
        ),
        "type": "CONCOURSE",
        "floor": floor,
        "line_name": "공통",
        "description": (
            f"{station_name} "
            f"{floor} 대합실/환승 구역"
        ),
    }


def get_or_create_concourse_node(
    *,
    station_name: str,
    station_code: str,
    floor: str,
    nodes: dict[
        str,
        dict[str, Any],
    ],
) -> dict[str, Any]:

    node_id = (
        f"{station_code}_"
        f"{floor}_CONCOURSE"
    )

    if node_id in nodes:
        return nodes[
            node_id
        ]

    node = (
        create_concourse_node(
            station_name=station_name,
            station_code=station_code,
            floor=floor,
        )
    )

    add_node(
        nodes,
        node,
    )

    return node


def create_exit_node(
    station_name: str,
    station_code: str,
    exit_no: str,
) -> dict[str, Any]:

    node_id = (
        f"{station_code}"
        f"_1F_EXIT_"
        f"{exit_no}"
    )

    return {
        "id": node_id,
        "station_code": (
            station_code
        ),
        "station_name": (
            station_name
        ),
        "type": "EXIT",
        "floor": "1F",
        "line_name": "공통",
        "exit_no": (
            exit_no
        ),
        "description": (
            f"{station_name} "
            f"{exit_no}번 출구"
        ),
    }


def create_platform_node(
    *,
    station_name: str,
    station_code: str,
    line_name: str,
    line_index: int,
    facility_type: str,
    facility_index: int,
    floor: str,
    detail_location: str,
) -> dict[str, Any]:

    node_id = (
        f"{station_code}"
        f"_LINE_{line_index:02d}"
        f"_{floor}"
        f"_{facility_type}"
        f"_PLATFORM_"
        f"{facility_index:03d}"
    )

    return {
        "id": node_id,
        "station_code": (
            station_code
        ),
        "station_name": (
            station_name
        ),
        "type": "PLATFORM",
        "floor": floor,
        "line_name": (
            line_name
        ),
        "detail_location": (
            detail_location
        ),
        "description": (
            f"{station_name} "
            f"{line_name} "
            f"{floor} 승강장/인접 통로 "
            f"({detail_location})"
        ),
    }


# ==============================================================================
# 6. 환승통로형 PLATFORM ↔ CONCOURSE 보행 연결
# ==============================================================================

def add_transfer_walking_edges(
    *,
    station_name: str,
    station_code: str,
    nodes: dict[
        str,
        dict[str, Any],
    ],
    edges: list[
        dict[str, Any]
    ],
) -> None:
    """
    같은 층의 환승통로형 PLATFORM 노드와
    CONCOURSE 노드를 WALKING edge로 연결합니다.

    대상:

    - 상세 위치에 '환승통로'
    - 상세 위치에 '환승표내는곳'

    이 포함된 PLATFORM.

    모든 PLATFORM을 무조건 CONCOURSE에 연결하면
    실제 승강장에서 대합실로 바로 이동하는 잘못된
    지름길이 생길 수 있으므로 환승 관련 노드만 연결합니다.

    WALKING은 같은 층의 일반 내부 통로로 간주하여
    wheelchair_accessible=True,
    is_bidirectional=True로 설정합니다.
    """

    platform_nodes = [
        node
        for node in list(
            nodes.values()
        )
        if (
            node.get(
                "type"
            )
            == "PLATFORM"
        )
        and is_transfer_area_text(
            node.get(
                "detail_location",
                "",
            )
        )
    ]

    walking_index = 1

    for platform_node in (
        platform_nodes
    ):

        floor = str(
            platform_node.get(
                "floor",
                "",
            )
        ).strip()

        if not floor:
            continue

        concourse_node = (
            get_or_create_concourse_node(
                station_name=station_name,
                station_code=station_code,
                floor=floor,
                nodes=nodes,
            )
        )

        platform_node_id = str(
            platform_node.get(
                "id",
                "",
            )
        ).strip()

        concourse_node_id = str(
            concourse_node.get(
                "id",
                "",
            )
        ).strip()

        if (
            not platform_node_id
            or not concourse_node_id
        ):
            continue

        if (
            platform_node_id
            == concourse_node_id
        ):
            continue

        # ----------------------------------------------------------------------
        # 동일 두 노드를 연결하는 WALKING edge 중복 방지
        # ----------------------------------------------------------------------

        already_exists = any(
            str(
                edge.get(
                    "transport_type",
                    "",
                )
            ).upper()
            == "WALKING"
            and {
                str(
                    edge.get(
                        "from_node",
                        "",
                    )
                ),
                str(
                    edge.get(
                        "to_node",
                        "",
                    )
                ),
            }
            == {
                platform_node_id,
                concourse_node_id,
            }
            for edge in edges
        )

        if already_exists:
            continue

        # ----------------------------------------------------------------------
        # edge id 중복 방지
        # ----------------------------------------------------------------------

        while True:

            edge_id = (
                f"{station_code}"
                f"_WALK_TRANSFER_"
                f"{walking_index:03d}"
            )

            walking_index += 1

            if not any(
                edge.get(
                    "id"
                )
                == edge_id
                for edge in edges
            ):
                break

        edges.append(
            {
                "id": (
                    edge_id
                ),

                "station_name": (
                    station_name
                ),

                "line_name": (
                    platform_node.get(
                        "line_name"
                    )
                ),

                "from_node": (
                    platform_node_id
                ),

                "to_node": (
                    concourse_node_id
                ),

                "transport_type": (
                    "WALKING"
                ),

                "wheelchair_accessible": (
                    True
                ),

                "is_bidirectional": (
                    True
                ),

                "from_floor": (
                    floor
                ),

                "to_floor": (
                    floor
                ),

                "exit_no": (
                    None
                ),

                "detail_location": (
                    platform_node.get(
                        "detail_location",
                        "",
                    )
                ),

                "direction": (
                    None
                ),

                "direction_name": (
                    None
                ),

                "operator_code": (
                    None
                ),

                "line_code": (
                    None
                ),

                "kric_station_code": (
                    None
                ),

                "description": (
                    f"{station_name} "
                    f"{floor} 환승구역 "
                    f"내부 보행 연결"
                ),
            }
        )


# ==============================================================================
# 6-1. 이매역 B2 환승 보행 연결 보정
# ==============================================================================

def add_imae_transfer_walking_edges(
    *,
    station_name: str,
    station_code: str,
    nodes: dict[str, dict[str, Any]],
    edges: list[dict[str, Any]],
) -> None:
    """
    이매역 경강선 B3 승강장 -> B2 환승구간 -> 수인분당선 B2 승강장
    동선을 그래프에 명시적으로 연결합니다.

    현재 원천 데이터에는 경강선 쪽에
    '왕십리행환승구간', '수원인천행환승구간' 표현이 존재하지만,
    일반 그래프 생성 로직은 이를 별도 B2 환승 공간으로 모델링하지 않아
    B2 -> B1 -> B2 우회가 발생할 수 있습니다.

    프로토타입 단계에서는 이매역의 수인분당선 B2 PLATFORM 노드 중
    방향이 명확한 노드들을 B2 CONCOURSE와 WALKING으로 연결해
    실제 환승구간을 보정합니다.
    """

    if station_name != "이매역":
        return

    b2_concourse_id = (
        f"{station_code}_B2_CONCOURSE"
    )

    b2_concourse = nodes.get(
        b2_concourse_id
    )

    if not b2_concourse:
        return

    # 수인분당선 B2 승강장 중 실제 열차 승강장 후보
    target_platforms: list[
        dict[str, Any]
    ] = []

    for node in nodes.values():

        if (
            node.get("type")
            != "PLATFORM"
        ):
            continue

        if (
            str(
                node.get(
                    "line_name",
                    "",
                )
            ).strip()
            != "수인분당선"
        ):
            continue

        if (
            str(
                node.get(
                    "floor",
                    "",
                )
            ).strip().upper()
            != "B2"
        ):
            continue

        detail_location = (
            compact_text(
                node.get(
                    "detail_location",
                    "",
                )
            )
        )

        # 이매역 수인분당선의 실제 승강장 방향 표현
        if any(
            keyword in detail_location
            for keyword in (
                "야탑",
                "서현",
                "왕십리",
                "청량리",
                "죽전",
                "고색",
                "인천",
            )
        ):
            target_platforms.append(
                node
            )

    walking_index = 1

    for platform_node in target_platforms:

        platform_node_id = str(
            platform_node.get(
                "id",
                "",
            )
        ).strip()

        if not platform_node_id:
            continue

        # 이미 B2 CONCOURSE와 WALKING으로 연결돼 있으면 중복 방지
        already_exists = any(
            str(
                edge.get(
                    "transport_type",
                    "",
                )
            ).upper()
            == "WALKING"
            and {
                str(
                    edge.get(
                        "from_node",
                        "",
                    )
                ),
                str(
                    edge.get(
                        "to_node",
                        "",
                    )
                ),
            }
            == {
                b2_concourse_id,
                platform_node_id,
            }
            for edge in edges
        )

        if already_exists:
            continue

        while True:

            edge_id = (
                f"{station_code}"
                f"_WALK_IMAE_TRANSFER_"
                f"{walking_index:03d}"
            )

            walking_index += 1

            if not any(
                edge.get("id")
                == edge_id
                for edge in edges
            ):
                break

        edges.append(
            {
                "id": edge_id,
                "station_name": station_name,
                "line_name": "수인분당선",
                "from_node": b2_concourse_id,
                "to_node": platform_node_id,
                "transport_type": "WALKING",
                "wheelchair_accessible": True,
                "is_bidirectional": True,
                "from_floor": "B2",
                "to_floor": "B2",
                "exit_no": None,
                "detail_location": (
                    platform_node.get(
                        "detail_location",
                        "",
                    )
                ),
                "direction": None,
                "direction_name": None,
                "operator_code": None,
                "line_code": None,
                "kric_station_code": None,
                "description": (
                    "이매역 B2 환승구간 "
                    "↔ 수인분당선 B2 승강장 "
                    "보행 연결"
                ),
            }
        )
def add_moran_transfer_walking_edges(
    *,
    station_name: str,
    station_code: str,
    nodes: dict[str, dict[str, Any]],
    edges: list[dict[str, Any]],
) -> None:
    """
    모란역 8호선 ↔ 수인분당선 환승 동선을
    B1 대합실을 기준으로 명시적으로 연결합니다.

    모란역 시설 데이터 구조:
    - 8호선: B3 승강장 -> B1/B2 대합실
    - 수인분당선: B2 승강장 -> B1 맞이방

    원천 시설 데이터에는 실제 환승역임에도
    '환승통로'라는 명시적인 표현이 없어
    일반 환승 WALKING edge 생성 로직에서
    환승 연결이 생성되지 않을 수 있습니다.

    따라서 두 노선의 B1 대합실 공간을
    WALKING edge로 연결합니다.
    """

    if station_name != "모란역":
        return

    # ---------------------------------------------------------
    # 모란역 B1 CONCOURSE 후보 탐색
    # ---------------------------------------------------------

    b1_concourses: list[
        dict[str, Any]
    ] = []

    for node in nodes.values():

        if (
            node.get("type")
            != "CONCOURSE"
        ):
            continue

        if (
            str(
                node.get(
                    "floor",
                    "",
                )
            ).strip().upper()
            != "B1"
        ):
            continue

        b1_concourses.append(
            node
        )

    if not b1_concourses:
        return

    # ---------------------------------------------------------
    # 8호선 / 수인분당선과 연결되어 있는
    # B1 CONCOURSE를 각각 찾습니다.
    # ---------------------------------------------------------

    line_concourses: dict[
        str,
        set[str],
    ] = {
        "8호선": set(),
        "수인분당선": set(),
    }

    for edge in edges:

        line_name = str(
            edge.get(
                "line_name",
                "",
            )
        ).strip()

        if line_name not in line_concourses:
            continue

        from_node = str(
            edge.get(
                "from_node",
                "",
            )
        ).strip()

        to_node = str(
            edge.get(
                "to_node",
                "",
            )
        ).strip()

        for concourse in b1_concourses:

            concourse_id = str(
                concourse.get(
                    "id",
                    "",
                )
            ).strip()

            if not concourse_id:
                continue

            if (
                from_node == concourse_id
                or to_node == concourse_id
            ):
                line_concourses[
                    line_name
                ].add(
                    concourse_id
                )

    line8_concourses = list(
        line_concourses["8호선"]
    )

    suin_concourses = list(
        line_concourses["수인분당선"]
    )

    if (
        not line8_concourses
        or not suin_concourses
    ):
        return

    # ---------------------------------------------------------
    # 두 노선 B1 대합실 연결
    # ---------------------------------------------------------

    walking_index = 1

    for line8_concourse_id in (
        line8_concourses
    ):

        for suin_concourse_id in (
            suin_concourses
        ):

            # 동일 노드라면 이미 공용 공간이므로
            # 별도의 edge가 필요하지 않습니다.
            if (
                line8_concourse_id
                == suin_concourse_id
            ):
                continue

            # 이미 WALKING 연결이 있으면 중복 생성 방지
            already_exists = any(
                str(
                    edge.get(
                        "transport_type",
                        "",
                    )
                ).upper()
                == "WALKING"
                and {
                    str(
                        edge.get(
                            "from_node",
                            "",
                        )
                    ),
                    str(
                        edge.get(
                            "to_node",
                            "",
                        )
                    ),
                }
                == {
                    line8_concourse_id,
                    suin_concourse_id,
                }
                for edge in edges
            )

            if already_exists:
                continue

            while True:

                edge_id = (
                    f"{station_code}"
                    f"_WALK_MORAN_TRANSFER_"
                    f"{walking_index:03d}"
                )

                walking_index += 1

                if not any(
                    edge.get("id")
                    == edge_id
                    for edge in edges
                ):
                    break

            edges.append(
                {
                    "id": edge_id,

                    "station_name": (
                        station_name
                    ),

                    # 두 노선을 연결하는 공용 환승 통로이므로
                    # 특정 노선으로 지정하지 않습니다.
                    "line_name": None,

                    "from_node": (
                        line8_concourse_id
                    ),

                    "to_node": (
                        suin_concourse_id
                    ),

                    "transport_type": (
                        "WALKING"
                    ),

                    "wheelchair_accessible": (
                        True
                    ),

                    "is_bidirectional": True,

                    "from_floor": "B1",
                    "to_floor": "B1",

                    "exit_no": None,

                    "detail_location": (
                        "모란역 8호선 ↔ "
                        "수인분당선 환승 통로"
                    ),

                    "direction": None,
                    "direction_name": None,

                    "operator_code": None,
                    "line_code": None,
                    "kric_station_code": None,

                    "description": (
                        "모란역 B1 대합실 "
                        "8호선 ↔ 수인분당선 "
                        "환승 보행 연결"
                    ),
                }
            )


# ==============================================================================
# 7. 시설의 두 끝점 판단
# ==============================================================================

def determine_internal_endpoints(
    *,
    station_name: str,
    station_code: str,
    line_name: str,
    line_index: int,
    facility_type: str,
    facility_index: int,
    from_floor: str,
    to_floor: str,
    detail_location: str,
    nodes: dict[
        str,
        dict[str, Any],
    ],
) -> tuple[
    dict[str, Any],
    dict[str, Any],
]:
    """
    지하 내부 EV/ES의 양 끝 노드를 생성합니다.

    현재 KRIC 데이터에는 각 끝점의 공간 유형이 별도 필드로
    제공되지 않으므로 상세 위치 + 층 깊이를 이용합니다.

    일반적인 구조:
    승강장(더 깊은 층) ↔ 대합실(더 얕은 층)

    승강장 표현이 있는 데이터에서는 더 깊은 쪽을 PLATFORM,
    얕은 쪽을 CONCOURSE로 구성합니다.
    """

    from_depth = (
        get_floor_depth(
            from_floor
        )
    )

    to_depth = (
        get_floor_depth(
            to_floor
        )
    )

    # --------------------------------------------------------------------------
    # 승강장 연결 시설
    # --------------------------------------------------------------------------

    if contains_platform_keyword(
        detail_location
    ):

        if from_depth > to_depth:

            platform_floor = (
                from_floor
            )

            concourse_floor = (
                to_floor
            )

            platform_is_from = (
                True
            )

        elif to_depth > from_depth:

            platform_floor = (
                to_floor
            )

            concourse_floor = (
                from_floor
            )

            platform_is_from = (
                False
            )

        else:

            # 같은 층으로 들어오는 예외 데이터
            # 우선 from을 PLATFORM 쪽으로 둡니다.

            platform_floor = (
                from_floor
            )

            concourse_floor = (
                to_floor
            )

            platform_is_from = (
                True
            )

        platform_node = (
            create_platform_node(
                station_name=station_name,
                station_code=station_code,
                line_name=line_name,
                line_index=line_index,
                facility_type=facility_type,
                facility_index=facility_index,
                floor=platform_floor,
                detail_location=detail_location,
            )
        )

        add_node(
            nodes,
            platform_node,
        )

        concourse_node = (
            get_or_create_concourse_node(
                station_name=station_name,
                station_code=station_code,
                floor=concourse_floor,
                nodes=nodes,
            )
        )

        if platform_is_from:
            return (
                platform_node,
                concourse_node,
            )

        return (
            concourse_node,
            platform_node,
        )

    # --------------------------------------------------------------------------
    # 승강장 표현이 없는 지하 시설
    #
    # 대합실 ↔ 대합실 층간 연결로 처리
    # --------------------------------------------------------------------------

    from_node = (
        get_or_create_concourse_node(
            station_name=station_name,
            station_code=station_code,
            floor=from_floor,
            nodes=nodes,
        )
    )

    to_node = (
        get_or_create_concourse_node(
            station_name=station_name,
            station_code=station_code,
            floor=to_floor,
            nodes=nodes,
        )
    )

    return (
        from_node,
        to_node,
    )


# ==============================================================================
# 8. 엘리베이터 변환
# ==============================================================================

def add_elevator_to_graph(
    *,
    station_name: str,
    station_code: str,
    line_name: str,
    line_index: int,
    facility_index: int,
    elevator: dict[str, Any],
    nodes: dict[
        str,
        dict[str, Any],
    ],
    edges: list[
        dict[str, Any]
    ],
) -> None:

    detail_location = str(
        elevator.get(
            "dtlLoc",
            "",
        )
    ).strip()

    from_floor = normalize_floor(
        elevator.get(
            "grndDvNmFr"
        ),
        elevator.get(
            "runStinFlorFr"
        ),
    )

    to_floor = normalize_floor(
        elevator.get(
            "grndDvNmTo"
        ),
        elevator.get(
            "runStinFlorTo"
        ),
    )

    exit_no = normalize_exit_no(
        elevator.get(
            "exitNo"
        )
    )

    if not exit_no:

        exit_no = (
            extract_exit_no_from_location(
                detail_location
            )
        )

    edge_id = (
        f"{station_code}"
        f"_{line_index:02d}"
        f"_EV_"
        f"{facility_index:03d}"
    )

    # --------------------------------------------------------------------------
    # 지상 출입구 연결
    # --------------------------------------------------------------------------

    if is_ground_connection(
        elevator
    ):

        if not exit_no:

            exit_no = (
                f"UNKNOWN_"
                f"{line_index:02d}_"
                f"{facility_index:03d}"
            )

        exit_node = (
            create_exit_node(
                station_name=station_name,
                station_code=station_code,
                exit_no=exit_no,
            )
        )

        add_node(
            nodes,
            exit_node,
        )

        if (
            str(
                elevator.get(
                    "grndDvNmFr",
                    "",
                )
            ).strip()
            == "지하"
        ):

            underground_floor = (
                from_floor
            )

            underground_is_from = (
                True
            )

        else:

            underground_floor = (
                to_floor
            )

            underground_is_from = (
                False
            )

        concourse_node = (
            get_or_create_concourse_node(
                station_name=station_name,
                station_code=station_code,
                floor=underground_floor,
                nodes=nodes,
            )
        )

        if underground_is_from:

            from_node = (
                concourse_node
            )

            to_node = (
                exit_node
            )

        else:

            from_node = (
                exit_node
            )

            to_node = (
                concourse_node
            )

    # --------------------------------------------------------------------------
    # 역사 내부
    # --------------------------------------------------------------------------

    else:

        (
            from_node,
            to_node,
        ) = determine_internal_endpoints(
            station_name=station_name,
            station_code=station_code,
            line_name=line_name,
            line_index=line_index,
            facility_type="EV",
            facility_index=facility_index,
            from_floor=from_floor,
            to_floor=to_floor,
            detail_location=detail_location,
            nodes=nodes,
        )

    edges.append(
        {
            "id": (
                edge_id
            ),

            "station_name": (
                station_name
            ),

            "line_name": (
                line_name
            ),

            "from_node": (
                from_node["id"]
            ),

            "to_node": (
                to_node["id"]
            ),

            "transport_type": (
                "ELEVATOR"
            ),

            "wheelchair_accessible": (
                True
            ),

            "is_bidirectional": (
                True
            ),

            "from_floor": (
                from_floor
            ),

            "to_floor": (
                to_floor
            ),

            "exit_no": (
                exit_no
            ),

            "detail_location": (
                detail_location
            ),

            "operator_code": (
                elevator.get(
                    "railOprIsttCd"
                )
            ),

            "line_code": (
                elevator.get(
                    "lnCd"
                )
            ),

            "kric_station_code": (
                elevator.get(
                    "stinCd"
                )
            ),

            "capacity_persons": (
                elevator.get(
                    "rglnPsno"
                )
            ),

            "capacity_weight_kg": (
                elevator.get(
                    "rglnWgt"
                )
            ),

            "description": (
                f"{line_name} "
                f"엘리베이터 "
                f"({detail_location})"
            ),
        }
    )


# ==============================================================================
# 9. 에스컬레이터 변환
# ==============================================================================

def add_escalator_to_graph(
    *,
    station_name: str,
    station_code: str,
    line_name: str,
    line_index: int,
    facility_index: int,
    escalator: dict[str, Any],
    nodes: dict[
        str,
        dict[str, Any],
    ],
    edges: list[
        dict[str, Any]
    ],
) -> None:

    detail_location = str(
        escalator.get(
            "dtlLoc",
            "",
        )
    ).strip()

    from_floor = normalize_floor(
        escalator.get(
            "grndDvNmFr"
        ),
        escalator.get(
            "runStinFlorFr"
        ),
    )

    to_floor = normalize_floor(
        escalator.get(
            "grndDvNmTo"
        ),
        escalator.get(
            "runStinFlorTo"
        ),
    )

    direction_name = str(
        escalator.get(
            "updnDvNm",
            "",
        )
    ).strip()

    if direction_name == "상행":
        direction = "UP"

    elif direction_name == "하행":
        direction = "DOWN"

    else:
        direction = "UNKNOWN"

    exit_no = normalize_exit_no(
        escalator.get(
            "exitNo"
        )
    )

    if not exit_no:

        exit_no = (
            extract_exit_no_from_location(
                detail_location
            )
        )

    edge_id = (
        f"{station_code}"
        f"_{line_index:02d}"
        f"_ES_"
        f"{facility_index:03d}"
    )

    # --------------------------------------------------------------------------
    # 지상 출입구 연결
    # --------------------------------------------------------------------------

    if is_ground_connection(
        escalator
    ):

        if not exit_no:

            exit_no = (
                f"UNKNOWN_"
                f"{line_index:02d}_"
                f"{facility_index:03d}"
            )

        exit_node = (
            create_exit_node(
                station_name=station_name,
                station_code=station_code,
                exit_no=exit_no,
            )
        )

        add_node(
            nodes,
            exit_node,
        )

        if (
            str(
                escalator.get(
                    "grndDvNmFr",
                    "",
                )
            ).strip()
            == "지하"
        ):

            underground_floor = (
                from_floor
            )

            underground_is_from = (
                True
            )

        else:

            underground_floor = (
                to_floor
            )

            underground_is_from = (
                False
            )

        concourse_node = (
            get_or_create_concourse_node(
                station_name=station_name,
                station_code=station_code,
                floor=underground_floor,
                nodes=nodes,
            )
        )

        if underground_is_from:

            from_node = (
                concourse_node
            )

            to_node = (
                exit_node
            )

        else:

            from_node = (
                exit_node
            )

            to_node = (
                concourse_node
            )

    # --------------------------------------------------------------------------
    # 역사 내부
    # --------------------------------------------------------------------------

    else:

        (
            from_node,
            to_node,
        ) = determine_internal_endpoints(
            station_name=station_name,
            station_code=station_code,
            line_name=line_name,
            line_index=line_index,
            facility_type="ES",
            facility_index=facility_index,
            from_floor=from_floor,
            to_floor=to_floor,
            detail_location=detail_location,
            nodes=nodes,
        )

    edges.append(
        {
            "id": (
                edge_id
            ),

            "station_name": (
                station_name
            ),

            "line_name": (
                line_name
            ),

            "from_node": (
                from_node["id"]
            ),

            "to_node": (
                to_node["id"]
            ),

            "transport_type": (
                "ESCALATOR"
            ),

            "wheelchair_accessible": (
                False
            ),

            # 에스컬레이터는 운행 방향을 따라야 하므로 단방향
            "is_bidirectional": (
                False
            ),

            "direction": (
                direction
            ),

            "direction_name": (
                direction_name
            ),

            "from_floor": (
                from_floor
            ),

            "to_floor": (
                to_floor
            ),

            "exit_no": (
                exit_no
            ),

            "detail_location": (
                detail_location
            ),

            "operator_code": (
                escalator.get(
                    "railOprIsttCd"
                )
            ),

            "line_code": (
                escalator.get(
                    "lnCd"
                )
            ),

            "kric_station_code": (
                escalator.get(
                    "stinCd"
                )
            ),

            "description": (
                f"{line_name} "
                f"에스컬레이터 "
                f"({detail_location})"
            ),
        }
    )


# ==============================================================================
# 10. 역 하나의 그래프 생성
# ==============================================================================

def build_station_graph(
    station_name: str,
    station_metadata: dict[
        str,
        Any,
    ],
) -> dict[str, Any]:

    station_code = (
        INTERNAL_STATION_CODES[
            station_name
        ]
    )

    nodes: dict[
        str,
        dict[str, Any],
    ] = {}

    edges: list[
        dict[str, Any]
    ] = []

    source_files: list[
        str
    ] = []

    lines = station_metadata.get(
        "lines",
        {},
    )

    # --------------------------------------------------------------------------
    # 노선별 통합 시설 JSON 처리
    # --------------------------------------------------------------------------

    for line_index, (
        line_name,
        line_metadata,
    ) in enumerate(
        lines.items(),
        start=1,
    ):

        try:
            station_data = load_facility_json(
                station_name=station_name,
                line_name=line_name,
            )

        except (
            FileNotFoundError,
            ValueError,
        ) as error:
            print(
                f"⚠️ {station_name} / "
                f"{line_name} 시설 데이터 로드 실패: "
                f"{error}"
            )
            continue

        integrated_source = (
            "Elevator_Escalator_현황_통합.json"
        )

        if integrated_source not in source_files:
            source_files.append(
                integrated_source
            )

        elevators = (
            station_data.get(
                "elevators",
                [],
            )
        )

        escalators = (
            station_data.get(
                "escalators",
                [],
            )
        )

        if not isinstance(
            elevators,
            list,
        ):
            elevators = []

        if not isinstance(
            escalators,
            list,
        ):
            escalators = []

        # ----------------------------------------------------------------------
        # 엘리베이터
        # ----------------------------------------------------------------------

        for (
            facility_index,
            elevator,
        ) in enumerate(
            elevators,
            start=1,
        ):

            if not isinstance(
                elevator,
                dict,
            ):
                continue

            add_elevator_to_graph(
                station_name=station_name,
                station_code=station_code,
                line_name=line_name,
                line_index=line_index,
                facility_index=facility_index,
                elevator=elevator,
                nodes=nodes,
                edges=edges,
            )

        # ----------------------------------------------------------------------
        # 에스컬레이터
        # ----------------------------------------------------------------------

        for (
            facility_index,
            escalator,
        ) in enumerate(
            escalators,
            start=1,
        ):

            if not isinstance(
                escalator,
                dict,
            ):
                continue

            add_escalator_to_graph(
                station_name=station_name,
                station_code=station_code,
                line_name=line_name,
                line_index=line_index,
                facility_index=facility_index,
                escalator=escalator,
                nodes=nodes,
                edges=edges,
            )

    # --------------------------------------------------------------------------
    # 모든 EV/ES 생성이 끝난 뒤
    # 환승통로형 PLATFORM ↔ 같은 층 CONCOURSE 연결
    # --------------------------------------------------------------------------

    add_transfer_walking_edges(
        station_name=station_name,
        station_code=station_code,
        nodes=nodes,
        edges=edges,
    )

    # 이매역은 B2 환승구간을 별도 공간으로 모델링하지 못하는
    # 원천 데이터 구조를 보정하기 위해 명시적 보행 연결을 추가합니다.
    add_imae_transfer_walking_edges(
        station_name=station_name,
        station_code=station_code,
        nodes=nodes,
        edges=edges,
    )

    return {
        "station_id": (
            station_code
        ),

        "station_name": (
            station_name
        ),

        "source_files": (
            source_files
        ),

        "total_nodes": len(
            nodes
        ),

        "total_edges": len(
            edges
        ),

        "nodes": list(
            nodes.values()
        ),

        "edges": (
            edges
        ),
    }


# ==============================================================================
# 11. 전체 역 그래프 생성
# ==============================================================================

def build_all_station_graphs(
) -> dict[
    str,
    dict[str, Any],
]:

    all_graphs: dict[
        str,
        dict[str, Any],
    ] = {}

    for (
        station_name,
        station_metadata,
    ) in STATION_METADATA.items():

        if (
            station_name
            not in INTERNAL_STATION_CODES
        ):
            continue

        graph = (
            build_station_graph(
                station_name=station_name,
                station_metadata=station_metadata,
            )
        )

        all_graphs[
            station_name
        ] = graph

    return all_graphs


# ==============================================================================
# 12. JSON 저장
# ==============================================================================

def save_all_station_graphs(
    graphs: dict[
        str,
        dict[str, Any],
    ],
) -> Path:

    GRAPH_DATA_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    with OUTPUT_FILE.open(
        "w",
        encoding="utf-8",
    ) as file:

        json.dump(
            graphs,
            file,
            ensure_ascii=False,
            indent=2,
        )

    return OUTPUT_FILE


def build_and_save_all_station_graphs(
) -> Path:

    graphs = (
        build_all_station_graphs()
    )

    output_path = (
        save_all_station_graphs(
            graphs
        )
    )

    print(
        "\n"
        "======================================"
    )

    print(
        "층별 역 내부 이동 그래프 생성 완료"
    )

    print(
        "======================================"
    )

    for (
        station_name,
        graph,
    ) in graphs.items():

        concourse_count = sum(
            1
            for node
            in graph[
                "nodes"
            ]
            if node.get(
                "type"
            )
            == "CONCOURSE"
        )

        walking_count = sum(
            1
            for edge
            in graph[
                "edges"
            ]
            if edge.get(
                "transport_type"
            )
            == "WALKING"
        )

        print(
            f"{station_name}: "
            f"노드 {graph['total_nodes']}개 / "
            f"간선 {graph['total_edges']}개 / "
            f"대합실 {concourse_count}개 / "
            f"환승 보행간선 {walking_count}개"
        )

    print(
        "--------------------------------------"
    )

    print(
        f"저장 위치: "
        f"{output_path}"
    )

    return output_path


# ==============================================================================
# 13. 직접 실행
# ==============================================================================

if __name__ == "__main__":
    build_and_save_all_station_graphs()