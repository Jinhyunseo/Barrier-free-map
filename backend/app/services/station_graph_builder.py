from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from app.data.station_metadata import STATION_METADATA
from app.data.station_layouts import STATION_LAYOUTS
from app.services.station_facility_service import load_facility_json


# ==============================================================================
# 1. 경로 설정
# ==============================================================================

APP_DIR = Path(__file__).resolve().parent.parent

FACILITY_DATA_DIR = APP_DIR / "data" / "station_facilities"
GRAPH_DATA_DIR = APP_DIR / "data" / "station_graphs"
OUTPUT_FILE = GRAPH_DATA_DIR / "all_stations_graph.json"


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
        floor = int(float(floor_number))
    except (TypeError, ValueError):
        floor = 1

    ground_text = str(ground_type or "").strip()

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

    floor_code = floor_code.upper()

    if floor_code.startswith("B"):
        try:
            return int(floor_code[1:])
        except ValueError:
            return 0

    return 0


def normalize_exit_no(
    exit_no: Any,
) -> str | None:

    if exit_no is None:
        return None

    exit_text = str(exit_no).strip()

    if not exit_text:
        return None

    match = re.search(r"\d+", exit_text)

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
        str(text or ""),
    )


def safe_line_name(
    line_name: str,
) -> str:
    """
    노선명을 노드 ID에 사용할 수 있도록 간단히 정규화합니다.
    """

    return (
        str(line_name or "공통")
        .strip()
        .replace(" ", "_")
        .replace("/", "_")
    )


def contains_platform_keyword(
    text: str,
) -> bool:
    """
    해당 위치 설명이 승강장 쪽을 의미하는지 확인합니다.
    """

    compact = compact_text(text)

    return (
        "승강장" in compact
        or "출입문앞" in compact
        or "출입문맞은편" in compact
    )


def get_directional_platform_key(
    *,
    station_name: str,
    line_name: str,
    floor: str,
    detail_location: str,
) -> str | None:
    """
    검증된 역에서 시설 위치 설명을 실제 진행 방향 플랫폼으로 매핑합니다.

    - 모란역 수인분당선 B2:
      야탑 방향 / 태평 방향
    - 야탑역 수인분당선 B2:
      왕십리·청량리 방면 = 모란 방향
      죽전·고색·인천 방면 = 이매 방향
    """

    if line_name != "수인분당선":
        return None

    if str(floor).strip().upper() != "B2":
        return None

    text = compact_text(detail_location)

    if station_name == "모란역":
        if "야탑" in text:
            return "YATAB"
        if "태평" in text:
            return "TAEPYEONG"

    if station_name == "야탑역":
        if any(
            keyword in text
            for keyword in (
                "왕십리",
                "청량리",
                "모란",
            )
        ):
            return "MORAN"

        if any(
            keyword in text
            for keyword in (
                "죽전",
                "고색",
                "인천",
                "이매",
            )
        ):
            return "IMAE"

    return None


def make_directional_platform_node_id(
    *,
    station_code: str,
    line_name: str,
    floor: str,
    platform_key: str,
) -> str:
    return (
        f"{station_code}_"
        f"{safe_line_name(line_name)}_"
        f"{floor}_PLATFORM_"
        f"{platform_key}"
    )


def get_directional_platform_description(
    platform_key: str,
) -> str:

    names = {
        "YATAB": "야탑 방향",
        "TAEPYEONG": "태평 방향",
        "MORAN": "모란 방향",
        "IMAE": "이매 방향",
    }

    return names.get(
        platform_key,
        platform_key,
    )


def get_directional_platform_keys_for_layout(
    *,
    station_name: str,
    line_name: str,
    floor: str,
) -> tuple[str, ...]:

    key = (
        station_name,
        line_name,
        str(floor).strip().upper(),
    )

    mapping = {
        ("모란역", "수인분당선", "B2"): (
            "YATAB",
            "TAEPYEONG",
        ),
        ("야탑역", "수인분당선", "B2"): (
            "MORAN",
            "IMAE",
        ),
    }

    return mapping.get(
        key,
        (),
    )


def is_unresolved_directional_platform_facility(
    *,
    station_name: str,
    line_name: str,
    from_floor: str,
    to_floor: str,
    detail_location: str,
) -> bool:
    """
    방향별 PLATFORM으로 나눈 층에 연결되는 시설인데
    어느 방향 승강장인지 확정할 수 없으면 True를 반환합니다.

    이런 경우 일반 PLATFORM을 새로 만들어 잘못 연결하지 않고
    원천 데이터가 보강될 때까지 해당 간선을 보류합니다.
    """

    directional_floor = None

    for floor in (
        from_floor,
        to_floor,
    ):
        if get_directional_platform_keys_for_layout(
            station_name=station_name,
            line_name=line_name,
            floor=floor,
        ):
            directional_floor = (
                str(floor)
                .strip()
                .upper()
            )
            break

    if directional_floor is None:
        return False

    return get_directional_platform_key(
        station_name=station_name,
        line_name=line_name,
        floor=directional_floor,
        detail_location=detail_location,
    ) is None


def is_transfer_area_text(
    text: Any,
) -> bool:
    """
    상세 위치가 환승 구역/환승 통로를 의미하는지 확인합니다.
    """

    compact = compact_text(text)

    keywords = (
        "환승통로",
        "환승표내는곳",
        "환승구간",
    )

    return any(
        keyword in compact
        for keyword in keywords
    )


def is_ground_connection(
    facility: dict[str, Any],
) -> bool:
    """
    시설이 실제 지상층과 연결되는지 판별합니다.

    중요:
    기존에는 dtlLoc에 '출입구'가 있다는 이유만으로
    B2 ↔ B1 같은 역사 내부 시설까지 1F EXIT에 연결될 수 있었습니다.

    이제 KRIC의 grndDvNmFr / grndDvNmTo 값을 우선합니다.
    두 값이 명시되어 있고 모두 '지하'라면 내부 시설로 처리합니다.
    텍스트 판별은 지상/지하 정보가 비어 있을 때만 fallback으로 사용합니다.
    """

    from_ground = str(
        facility.get("grndDvNmFr", "")
    ).strip()

    to_ground = str(
        facility.get("grndDvNmTo", "")
    ).strip()

    if (
        from_ground == "지상"
        or to_ground == "지상"
    ):
        return True

    # 양쪽 정보가 모두 존재하면서 지상이 아니라면
    # 출입구 번호가 텍스트에 있어도 역사 내부 시설입니다.
    if from_ground and to_ground:
        return False

    detail_location = str(
        facility.get("dtlLoc", "")
    )

    if (
        "출입구" in detail_location
        and "승강장" not in detail_location
    ):
        return True

    return False


# ==============================================================================
# 4. STATION_LAYOUTS 관련 유틸
# ==============================================================================

def get_station_layout(
    station_name: str,
) -> dict[str, Any] | None:

    layout = STATION_LAYOUTS.get(
        station_name
    )

    if isinstance(
        layout,
        dict,
    ):
        return layout

    # ------------------------------------------------------------------
    # 야탑역 실제 구조도 기반 fallback
    #
    # B1: 수인분당선 맞이방
    # B2: 상대식 승강장(모란 방향 / 이매 방향)
    # 출구: 1~4번
    #
    # 추후 station_layouts.py에 야탑역을 옮겨 적으면
    # 이 fallback은 제거해도 됩니다.
    # ------------------------------------------------------------------
    if station_name == "야탑역":
        return {
            "spaces": [
                {
                    "line_name": "수인분당선",
                    "floor": "B1",
                    "type": "CONCOURSE",
                },
                {
                    "line_name": "수인분당선",
                    "floor": "B2",
                    "type": "PLATFORM",
                },
            ],
            "exits": [
                {
                    "exit_no": str(exit_no),
                    "line_name": "수인분당선",
                    "concourse_floor": "B1",
                }
                for exit_no
                in range(1, 5)
            ],
            "transfers": [],
        }

    return None


def has_station_layout(
    station_name: str,
) -> bool:

    return get_station_layout(station_name) is not None


def find_layout_space(
    *,
    station_name: str,
    line_name: str,
    floor: str,
) -> dict[str, Any] | None:
    """
    STATION_LAYOUTS에서 특정 노선/층의 실제 공간 정보를 찾습니다.

    현재 프로토타입에서는 한 노선·한 층당 핵심 공간 하나를
    PLATFORM 또는 CONCOURSE로 정의하는 구조를 사용합니다.
    """

    layout = get_station_layout(station_name)

    if not layout:
        return None

    spaces = layout.get("spaces", [])

    if not isinstance(spaces, list):
        return None

    normalized_line = str(line_name).strip()
    normalized_floor = str(floor).strip().upper()

    for space in spaces:

        if not isinstance(space, dict):
            continue

        if (
            str(space.get("line_name", "")).strip()
            != normalized_line
        ):
            continue

        if (
            str(space.get("floor", "")).strip().upper()
            != normalized_floor
        ):
            continue

        return space

    return None


def make_layout_space_node_id(
    *,
    station_code: str,
    line_name: str,
    floor: str,
    space_type: str,
) -> str:

    return (
        f"{station_code}_"
        f"{safe_line_name(line_name)}_"
        f"{floor}_"
        f"{space_type}"
    )


def get_layout_exits(
    station_name: str,
) -> list[dict[str, Any]]:
    """
    STATION_LAYOUTS에 정의된 출구 목록을 반환합니다.

    모란역은 사용자가 제공한 실제 역사 구조도 기준으로
    1~8번 출구가 수인분당선 측,
    9~12번 출구가 8호선 측에 배치되어 있음을 임시 fallback으로 사용합니다.

    추후 station_layouts.py에 exits를 직접 정의하면
    그 값을 최우선으로 사용합니다.
    """

    layout = get_station_layout(station_name)

    if layout:
        exits = layout.get("exits")

        if isinstance(exits, list) and exits:
            return [
                exit_info
                for exit_info in exits
                if isinstance(exit_info, dict)
            ]

    # 모란역 구조도 기반 임시 fallback
    if station_name == "모란역":
        result: list[dict[str, Any]] = []

        for exit_no in range(1, 9):
            result.append(
                {
                    "exit_no": str(exit_no),
                    "line_name": "수인분당선",
                    "concourse_floor": "B1",
                }
            )

        for exit_no in range(9, 13):
            result.append(
                {
                    "exit_no": str(exit_no),
                    "line_name": "8호선",
                    "concourse_floor": "B1",
                }
            )

        return result

    return []


def find_layout_exit(
    *,
    station_name: str,
    exit_no: str | None,
) -> dict[str, Any] | None:

    if not exit_no:
        return None

    target = str(exit_no).strip()

    for exit_info in get_layout_exits(
        station_name
    ):

        if (
            str(
                exit_info.get(
                    "exit_no",
                    "",
                )
            ).strip()
            == target
        ):
            return exit_info

    return None


# ==============================================================================
# 5. 노드 관리
# ==============================================================================

def add_node(
    nodes: dict[str, dict[str, Any]],
    node: dict[str, Any],
) -> None:

    node_id = node["id"]

    if node_id not in nodes:
        nodes[node_id] = node


def create_concourse_node(
    station_name: str,
    station_code: str,
    floor: str,
    line_name: str = "공통",
) -> dict[str, Any]:
    """
    대합실 노드 생성.

    STATION_LAYOUTS가 정의된 역에서는 노선별 노드를 생성합니다.
      예: MRN_8호선_B1_CONCOURSE

    아직 STATION_LAYOUTS가 없는 역은 기존 호환성을 위해
    공용 층별 노드를 유지할 수 있습니다.
      예: YTP_B1_CONCOURSE
    """

    if has_station_layout(station_name):

        node_id = make_layout_space_node_id(
            station_code=station_code,
            line_name=line_name,
            floor=floor,
            space_type="CONCOURSE",
        )

        node_line_name = line_name

        description = (
            f"{station_name} "
            f"{line_name} "
            f"{floor} 대합실"
        )

    else:

        node_id = (
            f"{station_code}_"
            f"{floor}_CONCOURSE"
        )

        node_line_name = "공통"

        description = (
            f"{station_name} "
            f"{floor} 대합실/환승 구역"
        )

    return {
        "id": node_id,
        "station_code": station_code,
        "station_name": station_name,
        "type": "CONCOURSE",
        "floor": floor,
        "line_name": node_line_name,
        "description": description,
    }


def get_or_create_concourse_node(
    *,
    station_name: str,
    station_code: str,
    floor: str,
    line_name: str = "공통",
    nodes: dict[str, dict[str, Any]],
) -> dict[str, Any]:

    if has_station_layout(station_name):

        node_id = make_layout_space_node_id(
            station_code=station_code,
            line_name=line_name,
            floor=floor,
            space_type="CONCOURSE",
        )

    else:

        node_id = (
            f"{station_code}_"
            f"{floor}_CONCOURSE"
        )

    if node_id in nodes:
        return nodes[node_id]

    node = create_concourse_node(
        station_name=station_name,
        station_code=station_code,
        floor=floor,
        line_name=line_name,
    )

    add_node(
        nodes,
        node,
    )

    return node


def get_ground_ev_access_key(
    *,
    station_name: str,
    detail_location: str,
) -> str | None:
    """
    구조도/원천 위치 설명에서 지상 EV 접근 지점을 식별합니다.
    """

    if station_name != "야탑역":
        return None

    text = compact_text(
        detail_location
    )

    if (
        "1,2번출구중간" in text
        or "1,2번출입구중간" in text
    ):
        return "1_2"

    if (
        "3,4번출구중간" in text
        or "3,4번출입구중간" in text
    ):
        return "3_4"

    return None


def get_or_create_accessible_entrance_node(
    *,
    station_name: str,
    station_code: str,
    line_name: str,
    access_key: str,
    detail_location: str,
    nodes: dict[str, dict[str, Any]],
) -> dict[str, Any]:

    node_id = (
        f"{station_code}_"
        f"1F_EV_ACCESS_"
        f"{access_key}"
    )

    existing = nodes.get(
        node_id
    )

    if existing:
        return existing

    nearby_exit_nos = (
        access_key
        .split("_")
    )

    node = {
        "id": node_id,
        "station_code": station_code,
        "station_name": station_name,
        "type": "ACCESSIBLE_ENTRANCE",
        "floor": "1F",
        "line_name": line_name,
        "access_type": "ELEVATOR",
        "wheelchair_accessible": True,
        "nearby_exit_nos": nearby_exit_nos,
        "detail_location": detail_location,
        "description": (
            f"{station_name} "
            f"{'/'.join(nearby_exit_nos)}번 출구 사이 "
            f"지상 엘리베이터 접근점"
        ),
    }

    add_node(
        nodes,
        node,
    )

    return node


def create_exit_node(
    station_name: str,
    station_code: str,
    exit_no: str,
    line_name: str = "공통",
) -> dict[str, Any]:

    node_id = (
        f"{station_code}"
        f"_1F_EXIT_"
        f"{exit_no}"
    )

    return {
        "id": node_id,
        "station_code": station_code,
        "station_name": station_name,
        "type": "EXIT",
        "floor": "1F",
        "line_name": line_name,
        "exit_no": exit_no,
        "description": (
            f"{station_name} "
            f"{exit_no}번 출구"
        ),
    }


def get_or_create_exit_node(
    *,
    station_name: str,
    station_code: str,
    exit_no: str,
    nodes: dict[str, dict[str, Any]],
    fallback_line_name: str = "공통",
) -> dict[str, Any]:
    """
    실제 layout의 출구 소속 노선을 우선 반영해 EXIT 노드를 생성합니다.
    """

    node_id = (
        f"{station_code}"
        f"_1F_EXIT_"
        f"{exit_no}"
    )

    layout_exit = find_layout_exit(
        station_name=station_name,
        exit_no=exit_no,
    )

    if layout_exit:
        line_name = str(
            layout_exit.get(
                "line_name",
                fallback_line_name,
            )
        ).strip() or fallback_line_name
    else:
        line_name = fallback_line_name

    existing = nodes.get(node_id)

    if existing:
        # 기존에 공통으로 만들어진 노드가 있으면
        # layout의 실제 노선 정보로 보완합니다.
        if (
            layout_exit
            and existing.get("line_name") == "공통"
        ):
            existing["line_name"] = line_name

        return existing

    node = create_exit_node(
        station_name=station_name,
        station_code=station_code,
        exit_no=exit_no,
        line_name=line_name,
    )

    add_node(
        nodes,
        node,
    )

    return node


def create_platform_node(
    *, station_name: str, station_code: str, line_name: str, line_index: int,
    facility_type: str, facility_index: int, floor: str, detail_location: str,
    platform_key: str | None = None,
) -> dict[str, Any]:
    if has_station_layout(station_name):
        resolved_key = platform_key or get_directional_platform_key(
            station_name=station_name, line_name=line_name, floor=floor,
            detail_location=detail_location,
        )
        if resolved_key:
            node_id = make_directional_platform_node_id(
                station_code=station_code, line_name=line_name, floor=floor,
                platform_key=resolved_key,
            )
            direction_label = get_directional_platform_description(resolved_key)
            description = f"{station_name} {line_name} {floor} {direction_label} 승강장"
        else:
            node_id = make_layout_space_node_id(
                station_code=station_code, line_name=line_name, floor=floor,
                space_type="PLATFORM",
            )
            direction_label = None
            description = f"{station_name} {line_name} {floor} 승강장"
    else:
        resolved_key = None
        direction_label = None
        node_id = f"{station_code}_LINE_{line_index:02d}_{floor}_{facility_type}_PLATFORM_{facility_index:03d}"
        description = f"{station_name} {line_name} {floor} 승강장/인접 통로 ({detail_location})"

    return {
        "id": node_id, "station_code": station_code, "station_name": station_name,
        "type": "PLATFORM", "floor": floor, "line_name": line_name,
        "platform_key": resolved_key, "direction_name": direction_label,
        "detail_location": detail_location, "description": description,
    }


def get_or_create_platform_node(
    *, station_name: str, station_code: str, line_name: str, line_index: int,
    facility_type: str, facility_index: int, floor: str, detail_location: str,
    nodes: dict[str, dict[str, Any]], platform_key: str | None = None,
) -> dict[str, Any]:
    node = create_platform_node(
        station_name=station_name, station_code=station_code, line_name=line_name,
        line_index=line_index, facility_type=facility_type,
        facility_index=facility_index, floor=floor,
        detail_location=detail_location, platform_key=platform_key,
    )
    existing = nodes.get(node["id"])
    if existing:
        if detail_location and detail_location != "STATION_LAYOUTS":
            existing["detail_location"] = detail_location
        return existing
    add_node(nodes, node)
    return node


def get_or_create_layout_space_node(
    *, station_name: str, station_code: str, line_name: str, line_index: int,
    facility_type: str, facility_index: int, floor: str, detail_location: str,
    nodes: dict[str, dict[str, Any]],
) -> dict[str, Any] | None:
    space = find_layout_space(station_name=station_name, line_name=line_name, floor=floor)
    if not space:
        return None
    space_type = str(space.get("type", "")).strip().upper()
    if space_type == "PLATFORM":
        platform_key = get_directional_platform_key(
            station_name=station_name, line_name=line_name, floor=floor,
            detail_location=detail_location,
        )
        return get_or_create_platform_node(
            station_name=station_name, station_code=station_code, line_name=line_name,
            line_index=line_index, facility_type=facility_type,
            facility_index=facility_index, floor=floor,
            detail_location=detail_location, nodes=nodes, platform_key=platform_key,
        )
    if space_type == "CONCOURSE":
        return get_or_create_concourse_node(
            station_name=station_name, station_code=station_code, floor=floor,
            line_name=line_name, nodes=nodes,
        )
    return None


def preload_layout_nodes(
    *,
    station_name: str,
    station_code: str,
    station_metadata: dict[str, Any],
    nodes: dict[str, dict[str, Any]],
) -> None:
    """
    실제 역사 기본 뼈대를 먼저 생성합니다.

    EV/ES 데이터가 특정 승강장을 명시하지 않더라도
    STATION_LAYOUTS에 정의된 PLATFORM/CONCOURSE가
    그래프에 반드시 존재하도록 합니다.
    """

    layout = get_station_layout(station_name)

    if not layout:
        return

    spaces = layout.get("spaces", [])

    if not isinstance(spaces, list):
        return

    lines = station_metadata.get("lines", {})

    line_names = list(lines.keys())

    for space in spaces:

        if not isinstance(space, dict):
            continue

        line_name = str(
            space.get("line_name", "")
        ).strip()

        floor = str(
            space.get("floor", "")
        ).strip().upper()

        space_type = str(
            space.get("type", "")
        ).strip().upper()

        if not line_name or not floor:
            continue

        try:
            line_index = (
                line_names.index(line_name) + 1
            )
        except ValueError:
            line_index = 0

        if space_type == "CONCOURSE":

            get_or_create_concourse_node(
                station_name=station_name,
                station_code=station_code,
                floor=floor,
                line_name=line_name,
                nodes=nodes,
            )

        elif space_type == "PLATFORM":

            platform_keys = (
                get_directional_platform_keys_for_layout(
                    station_name=station_name,
                    line_name=line_name,
                    floor=floor,
                )
            )

            if platform_keys:

                for platform_key in (
                    platform_keys
                ):

                    get_or_create_platform_node(
                        station_name=station_name,
                        station_code=station_code,
                        line_name=line_name,
                        line_index=line_index,
                        facility_type="LAYOUT",
                        facility_index=0,
                        floor=floor,
                        detail_location=(
                            get_directional_platform_description(
                                platform_key
                            )
                        ),
                        nodes=nodes,
                        platform_key=platform_key,
                    )

            else:

                get_or_create_platform_node(
                    station_name=station_name,
                    station_code=station_code,
                    line_name=line_name,
                    line_index=line_index,
                    facility_type="LAYOUT",
                    facility_index=0,
                    floor=floor,
                    detail_location="STATION_LAYOUTS",
                    nodes=nodes,
                )


def preload_layout_exits(
    *,
    station_name: str,
    station_code: str,
    nodes: dict[str, dict[str, Any]],
) -> None:
    """
    실제 역사 구조도에 존재하는 출구를 시설 유무와 관계없이 선생성합니다.

    중요:
    출구 노드를 만든다고 해서 CONCOURSE와 자동 WALKING 연결하지 않습니다.
    그렇게 하면 계단/엘리베이터 같은 실제 수직 이동 제약을 우회할 수 있기 때문입니다.
    """

    for exit_info in get_layout_exits(
        station_name
    ):

        exit_no = str(
            exit_info.get(
                "exit_no",
                "",
            )
        ).strip()

        if not exit_no:
            continue

        line_name = str(
            exit_info.get(
                "line_name",
                "공통",
            )
        ).strip() or "공통"

        get_or_create_exit_node(
            station_name=station_name,
            station_code=station_code,
            exit_no=exit_no,
            nodes=nodes,
            fallback_line_name=line_name,
        )


def add_layout_exit_connections(
    *,
    station_name: str,
    station_code: str,
    nodes: dict[str, dict[str, Any]],
    edges: list[dict[str, Any]],
) -> None:
    """
    station_layouts.py에 exit_connections가 명시된 경우에만
    실제 출구 접근 간선을 추가합니다.

    예시 스키마:
    {
        "from_line": "수인분당선",
        "from_floor": "B1",
        "exit_no": "1",
        "transport_type": "STAIR",
        "wheelchair_accessible": False,
        "is_bidirectional": True,
    }

    구조도만으로 접근수단을 확정할 수 없는 출구에는
    임의의 WALKING edge를 생성하지 않습니다.
    """

    layout = get_station_layout(station_name)

    if not layout:
        return

    connections = layout.get(
        "exit_connections",
        [],
    )

    if not isinstance(
        connections,
        list,
    ):
        return

    connection_index = 1

    for connection in connections:

        if not isinstance(
            connection,
            dict,
        ):
            continue

        from_line = str(
            connection.get(
                "from_line",
                "",
            )
        ).strip()

        from_floor = str(
            connection.get(
                "from_floor",
                "",
            )
        ).strip().upper()

        exit_no = str(
            connection.get(
                "exit_no",
                "",
            )
        ).strip()

        if not (
            from_line
            and from_floor
            and exit_no
        ):
            continue

        from_space = find_layout_space(
            station_name=station_name,
            line_name=from_line,
            floor=from_floor,
        )

        if not from_space:
            continue

        from_type = str(
            from_space.get(
                "type",
                "",
            )
        ).strip().upper()

        from_node_id = (
            make_layout_space_node_id(
                station_code=station_code,
                line_name=from_line,
                floor=from_floor,
                space_type=from_type,
            )
        )

        exit_node_id = (
            f"{station_code}"
            f"_1F_EXIT_"
            f"{exit_no}"
        )

        if (
            from_node_id not in nodes
            or exit_node_id not in nodes
        ):
            continue

        transport_type = str(
            connection.get(
                "transport_type",
                "WALKING",
            )
        ).strip().upper()

        already_exists = any(
            {
                str(edge.get("from_node", "")),
                str(edge.get("to_node", "")),
            }
            == {
                from_node_id,
                exit_node_id,
            }
            and str(
                edge.get(
                    "transport_type",
                    "",
                )
            ).upper()
            == transport_type
            for edge in edges
        )

        if already_exists:
            continue

        edge_id = (
            f"{station_code}"
            f"_LAYOUT_EXIT_"
            f"{connection_index:03d}"
        )

        connection_index += 1

        edges.append(
            {
                "id": edge_id,
                "station_name": station_name,
                "line_name": from_line,
                "from_node": from_node_id,
                "to_node": exit_node_id,
                "transport_type": transport_type,
                "wheelchair_accessible": bool(
                    connection.get(
                        "wheelchair_accessible",
                        False,
                    )
                ),
                "is_bidirectional": bool(
                    connection.get(
                        "is_bidirectional",
                        True,
                    )
                ),
                "from_floor": from_floor,
                "to_floor": "1F",
                "exit_no": exit_no,
                "detail_location": str(
                    connection.get(
                        "detail_location",
                        f"{exit_no}번 출구",
                    )
                ),
                "direction": connection.get(
                    "direction"
                ),
                "direction_name": connection.get(
                    "direction_name"
                ),
                "operator_code": None,
                "line_code": None,
                "kric_station_code": None,
                "description": (
                    f"{station_name} "
                    f"{from_line} {from_floor} "
                    f"→ {exit_no}번 출구 "
                    f"{transport_type} 연결"
                ),
            }
        )



# ==============================================================================
# 6. 환승 보행 연결
# ==============================================================================

def add_transfer_walking_edges(
    *,
    station_name: str,
    station_code: str,
    nodes: dict[str, dict[str, Any]],
    edges: list[dict[str, Any]],
) -> None:
    """
    기존 원천 데이터의 '환승통로', '환승표내는곳', '환승구간'
    표현을 기반으로 PLATFORM ↔ CONCOURSE 보행 연결을 추가합니다.

    STATION_LAYOUTS가 없는 역에 대한 기존 fallback 기능입니다.
    """

    platform_nodes = [
        node
        for node in list(nodes.values())
        if (
            node.get("type") == "PLATFORM"
            and is_transfer_area_text(
                node.get(
                    "detail_location",
                    "",
                )
            )
        )
    ]

    walking_index = 1

    for platform_node in platform_nodes:

        floor = str(
            platform_node.get("floor", "")
        ).strip()

        line_name = str(
            platform_node.get(
                "line_name",
                "공통",
            )
        ).strip()

        if not floor:
            continue

        concourse_node = get_or_create_concourse_node(
            station_name=station_name,
            station_code=station_code,
            floor=floor,
            line_name=line_name,
            nodes=nodes,
        )

        platform_node_id = str(
            platform_node.get("id", "")
        ).strip()

        concourse_node_id = str(
            concourse_node.get("id", "")
        ).strip()

        if (
            not platform_node_id
            or not concourse_node_id
            or platform_node_id == concourse_node_id
        ):
            continue

        already_exists = any(
            str(
                edge.get(
                    "transport_type",
                    "",
                )
            ).upper()
            == "WALKING"
            and {
                str(edge.get("from_node", "")),
                str(edge.get("to_node", "")),
            }
            == {
                platform_node_id,
                concourse_node_id,
            }
            for edge in edges
        )

        if already_exists:
            continue

        while True:

            edge_id = (
                f"{station_code}"
                f"_WALK_TRANSFER_"
                f"{walking_index:03d}"
            )

            walking_index += 1

            if not any(
                edge.get("id") == edge_id
                for edge in edges
            ):
                break

        edges.append(
            {
                "id": edge_id,
                "station_name": station_name,
                "line_name": line_name,
                "from_node": platform_node_id,
                "to_node": concourse_node_id,
                "transport_type": "WALKING",
                "wheelchair_accessible": True,
                "is_bidirectional": True,
                "from_floor": floor,
                "to_floor": floor,
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
                    f"{station_name} "
                    f"{floor} 환승구역 내부 보행 연결"
                ),
            }
        )


def add_layout_transfer_edges(
    *,
    station_name: str,
    station_code: str,
    nodes: dict[str, dict[str, Any]],
    edges: list[dict[str, Any]],
) -> None:
    """
    STATION_LAYOUTS에 명시한 실제 환승 연결을 WALKING edge로 생성합니다.

    예:
    모란역 8호선 B1 CONCOURSE
        ↔
    모란역 수인분당선 B1 CONCOURSE
    """

    layout = get_station_layout(station_name)

    if not layout:
        return

    transfers = layout.get("transfers", [])

    if not isinstance(transfers, list):
        return

    transfer_index = 1

    for transfer in transfers:

        if not isinstance(transfer, dict):
            continue

        from_line = str(
            transfer.get("from_line", "")
        ).strip()

        from_floor = str(
            transfer.get("from_floor", "")
        ).strip().upper()

        to_line = str(
            transfer.get("to_line", "")
        ).strip()

        to_floor = str(
            transfer.get("to_floor", "")
        ).strip().upper()

        transport_type = str(
            transfer.get(
                "transport_type",
                "WALKING",
            )
        ).strip().upper()

        if not (
            from_line
            and from_floor
            and to_line
            and to_floor
        ):
            continue

        from_space = find_layout_space(
            station_name=station_name,
            line_name=from_line,
            floor=from_floor,
        )

        to_space = find_layout_space(
            station_name=station_name,
            line_name=to_line,
            floor=to_floor,
        )

        if not from_space or not to_space:
            continue

        from_type = str(
            from_space.get("type", "")
        ).strip().upper()

        to_type = str(
            to_space.get("type", "")
        ).strip().upper()

        from_node_id = make_layout_space_node_id(
            station_code=station_code,
            line_name=from_line,
            floor=from_floor,
            space_type=from_type,
        )

        to_node_id = make_layout_space_node_id(
            station_code=station_code,
            line_name=to_line,
            floor=to_floor,
            space_type=to_type,
        )

        if (
            from_node_id not in nodes
            or to_node_id not in nodes
        ):
            continue

        if from_node_id == to_node_id:
            continue

        already_exists = any(
            str(
                edge.get(
                    "transport_type",
                    "",
                )
            ).upper()
            == transport_type
            and {
                str(edge.get("from_node", "")),
                str(edge.get("to_node", "")),
            }
            == {
                from_node_id,
                to_node_id,
            }
            for edge in edges
        )

        if already_exists:
            continue

        while True:

            edge_id = (
                f"{station_code}"
                f"_WALK_LAYOUT_TRANSFER_"
                f"{transfer_index:03d}"
            )

            transfer_index += 1

            if not any(
                edge.get("id") == edge_id
                for edge in edges
            ):
                break

        edges.append(
            {
                "id": edge_id,
                "station_name": station_name,
                "line_name": None,
                "from_node": from_node_id,
                "to_node": to_node_id,
                "transport_type": transport_type,
                "wheelchair_accessible": True,
                "is_bidirectional": True,
                "from_floor": from_floor,
                "to_floor": to_floor,
                "exit_no": None,
                "detail_location": (
                    f"{station_name} "
                    f"{from_line} {from_floor} ↔ "
                    f"{to_line} {to_floor} 환승"
                ),
                "direction": None,
                "direction_name": None,
                "operator_code": None,
                "line_code": None,
                "kric_station_code": None,
                "description": (
                    f"{station_name} "
                    f"{from_line} ↔ {to_line} "
                    f"환승 보행 연결"
                ),
            }
        )


# ==============================================================================
# 6-1. 이매역 기존 환승 보정
# ==============================================================================

def add_imae_transfer_walking_edges(
    *,
    station_name: str,
    station_code: str,
    nodes: dict[str, dict[str, Any]],
    edges: list[dict[str, Any]],
) -> None:
    """
    아직 이매역 STATION_LAYOUTS가 정의되지 않은 동안
    기존 B2 환승 보정 로직을 유지합니다.

    추후 이매역 layout을 추가하면 이 함수는 제거할 수 있습니다.
    """

    if station_name != "이매역":
        return

    # layout 기반으로 전환된 경우 별도 예외 보정은 하지 않습니다.
    if has_station_layout(station_name):
        return

    b2_concourse_id = (
        f"{station_code}_B2_CONCOURSE"
    )

    b2_concourse = nodes.get(
        b2_concourse_id
    )

    if not b2_concourse:
        return

    target_platforms: list[
        dict[str, Any]
    ] = []

    for node in nodes.values():

        if node.get("type") != "PLATFORM":
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

        detail_location = compact_text(
            node.get(
                "detail_location",
                "",
            )
        )

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

        already_exists = any(
            str(
                edge.get(
                    "transport_type",
                    "",
                )
            ).upper()
            == "WALKING"
            and {
                str(edge.get("from_node", "")),
                str(edge.get("to_node", "")),
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
                edge.get("id") == edge_id
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
    nodes: dict[str, dict[str, Any]],
) -> tuple[
    dict[str, Any],
    dict[str, Any],
]:
    """
    역사 내부 EV/ES의 양 끝 노드를 결정합니다.

    우선순위:
    1. STATION_LAYOUTS에 정의된 실제 공간 구조
    2. 기존 dtlLoc + 층 깊이 추론 로직

    따라서 모란역처럼 dtlLoc에 '승강장'이라는 단어가 없어도
    B3 = 8호선 PLATFORM이라는 실제 구조를 정확히 적용할 수 있습니다.
    """

    # --------------------------------------------------------------------------
    # 1. 실제 layout 우선
    # --------------------------------------------------------------------------

    if has_station_layout(station_name):

        from_layout_node = (
            get_or_create_layout_space_node(
                station_name=station_name,
                station_code=station_code,
                line_name=line_name,
                line_index=line_index,
                facility_type=facility_type,
                facility_index=facility_index,
                floor=from_floor,
                detail_location=detail_location,
                nodes=nodes,
            )
        )

        to_layout_node = (
            get_or_create_layout_space_node(
                station_name=station_name,
                station_code=station_code,
                line_name=line_name,
                line_index=line_index,
                facility_type=facility_type,
                facility_index=facility_index,
                floor=to_floor,
                detail_location=detail_location,
                nodes=nodes,
            )
        )

        if (
            from_layout_node is not None
            and to_layout_node is not None
        ):
            return (
                from_layout_node,
                to_layout_node,
            )

    # --------------------------------------------------------------------------
    # 2. 기존 fallback 추론
    # --------------------------------------------------------------------------

    from_depth = get_floor_depth(
        from_floor
    )

    to_depth = get_floor_depth(
        to_floor
    )

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

            platform_is_from = True

        elif to_depth > from_depth:

            platform_floor = (
                to_floor
            )

            concourse_floor = (
                from_floor
            )

            platform_is_from = False

        else:

            platform_floor = (
                from_floor
            )

            concourse_floor = (
                to_floor
            )

            platform_is_from = True

        platform_node = (
            get_or_create_platform_node(
                station_name=station_name,
                station_code=station_code,
                line_name=line_name,
                line_index=line_index,
                facility_type=facility_type,
                facility_index=facility_index,
                floor=platform_floor,
                detail_location=detail_location,
                nodes=nodes,
            )
        )

        concourse_node = (
            get_or_create_concourse_node(
                station_name=station_name,
                station_code=station_code,
                floor=concourse_floor,
                line_name=line_name,
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

    # 승강장 표현이 없는 경우 대합실 ↔ 대합실 fallback
    from_node = (
        get_or_create_concourse_node(
            station_name=station_name,
            station_code=station_code,
            floor=from_floor,
            line_name=line_name,
            nodes=nodes,
        )
    )

    to_node = (
        get_or_create_concourse_node(
            station_name=station_name,
            station_code=station_code,
            floor=to_floor,
            line_name=line_name,
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
    nodes: dict[str, dict[str, Any]],
    edges: list[dict[str, Any]],
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

    if is_unresolved_directional_platform_facility(
        station_name=station_name,
        line_name=line_name,
        from_floor=from_floor,
        to_floor=to_floor,
        detail_location=detail_location,
    ):
        return

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

        access_key = (
            get_ground_ev_access_key(
                station_name=station_name,
                detail_location=detail_location,
            )
        )

        if access_key:

            ground_node = (
                get_or_create_accessible_entrance_node(
                    station_name=station_name,
                    station_code=station_code,
                    line_name=line_name,
                    access_key=access_key,
                    detail_location=detail_location,
                    nodes=nodes,
                )
            )

            # 야탑역의 1·2 / 3·4번 사이 EV는 특정 한 출구가 아니므로
            # UNKNOWN EXIT 노드를 만들지 않습니다.
            exit_no = None

        else:

            ground_node = (
                get_or_create_exit_node(
                    station_name=station_name,
                    station_code=station_code,
                    exit_no=exit_no,
                    nodes=nodes,
                    fallback_line_name=line_name,
                )
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

            underground_is_from = True

        else:

            underground_floor = (
                to_floor
            )

            underground_is_from = False

        # layout이 있는 역이면 해당 노선/층의 실제 공간을 우선 사용
        underground_node = (
            get_or_create_layout_space_node(
                station_name=station_name,
                station_code=station_code,
                line_name=line_name,
                line_index=line_index,
                facility_type="EV",
                facility_index=facility_index,
                floor=underground_floor,
                detail_location=detail_location,
                nodes=nodes,
            )
        )

        if underground_node is None:

            underground_node = (
                get_or_create_concourse_node(
                    station_name=station_name,
                    station_code=station_code,
                    floor=underground_floor,
                    line_name=line_name,
                    nodes=nodes,
                )
            )

        if underground_is_from:

            from_node = (
                underground_node
            )

            to_node = (
                ground_node
            )

        else:

            from_node = (
                ground_node
            )

            to_node = (
                underground_node
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
            "id": edge_id,
            "station_name": station_name,
            "line_name": line_name,
            "from_node": from_node["id"],
            "to_node": to_node["id"],
            "transport_type": "ELEVATOR",
            "wheelchair_accessible": True,
            "is_bidirectional": True,
            "from_floor": from_floor,
            "to_floor": to_floor,
            "exit_no": exit_no,
            "detail_location": detail_location,
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
    nodes: dict[str, dict[str, Any]],
    edges: list[dict[str, Any]],
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

    if is_unresolved_directional_platform_facility(
        station_name=station_name,
        line_name=line_name,
        from_floor=from_floor,
        to_floor=to_floor,
        detail_location=detail_location,
    ):
        return

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

    # 야탑역의 통합 데이터에서 이 목록은 ES로 들어왔지만,
    # 실제 구조 확인 결과 모두 계단입니다.
    is_yatap_stair = (
        station_name == "야탑역"
    )

    edge_type_code = (
        "STAIR"
        if is_yatap_stair
        else "ES"
    )

    edge_id = (
        f"{station_code}"
        f"_{line_index:02d}"
        f"_{edge_type_code}_"
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
            get_or_create_exit_node(
                station_name=station_name,
                station_code=station_code,
                exit_no=exit_no,
                nodes=nodes,
                fallback_line_name=line_name,
            )
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

            underground_is_from = True

        else:

            underground_floor = (
                to_floor
            )

            underground_is_from = False

        underground_node = (
            get_or_create_layout_space_node(
                station_name=station_name,
                station_code=station_code,
                line_name=line_name,
                line_index=line_index,
                facility_type=(
                    "STAIR"
                    if is_yatap_stair
                    else "ES"
                ),
                facility_index=facility_index,
                floor=underground_floor,
                detail_location=detail_location,
                nodes=nodes,
            )
        )

        if underground_node is None:

            underground_node = (
                get_or_create_concourse_node(
                    station_name=station_name,
                    station_code=station_code,
                    floor=underground_floor,
                    line_name=line_name,
                    nodes=nodes,
                )
            )

        if underground_is_from:

            from_node = (
                underground_node
            )

            to_node = (
                exit_node
            )

        else:

            from_node = (
                exit_node
            )

            to_node = (
                underground_node
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
            facility_type=(
                    "STAIR"
                    if is_yatap_stair
                    else "ES"
                ),
            facility_index=facility_index,
            from_floor=from_floor,
            to_floor=to_floor,
            detail_location=detail_location,
            nodes=nodes,
        )

    # 야탑역 계단은 원천 시설 레코드 10개를 각각 보존합니다.
    # 같은 B1 안의 서로 다른 높이/중간층이 현재 CONCOURSE 하나로 합쳐져
    # from_node == to_node가 되는 경우에는 self-loop로 버리지 않고,
    # 해당 계단 구간 자체를 나타내는 보조 노드를 만들어 기록합니다.
    if (
        is_yatap_stair
        and from_node["id"]
        == to_node["id"]
    ):

        stair_segment_id = (
            f"{station_code}_"
            f"STAIR_SEGMENT_"
            f"{facility_index:03d}"
        )

        stair_segment_node = {
            "id": stair_segment_id,
            "station_code": station_code,
            "station_name": station_name,
            "type": "STAIR_SEGMENT",
            "floor": from_floor,
            "line_name": line_name,
            "detail_location": detail_location,
            "wheelchair_accessible": False,
            "description": (
                f"{station_name} "
                f"계단 구간 "
                f"({detail_location})"
            ),
        }

        add_node(
            nodes,
            stair_segment_node,
        )

        to_node = stair_segment_node

    # 야탑역은 10개의 계단 원천 레코드를 시설 단위로 모두 유지합니다.
    # 상/하행처럼 보이는 기록도 임의로 합치지 않습니다.
    edges.append(
        {
            "id": edge_id,
            "station_name": station_name,
            "line_name": line_name,
            "from_node": from_node["id"],
            "to_node": to_node["id"],
            "transport_type": (
                "STAIR"
                if is_yatap_stair
                else "ESCALATOR"
            ),
            "wheelchair_accessible": False,
            "is_bidirectional": (
                True
                if is_yatap_stair
                else False
            ),
            "direction": (
                None
                if is_yatap_stair
                else direction
            ),
            "direction_name": (
                None
                if is_yatap_stair
                else direction_name
            ),
            "from_floor": from_floor,
            "to_floor": to_floor,
            "exit_no": exit_no,
            "detail_location": detail_location,
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
                f"{'계단' if is_yatap_stair else '에스컬레이터'} "
                f"({detail_location})"
            ),
        }
    )


# ==============================================================================
# 10. 역 하나의 그래프 생성
# ==============================================================================

def build_station_graph(
    station_name: str,
    station_metadata: dict[str, Any],
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
    # 실제 구조가 정의된 역은 시설보다 먼저 뼈대 노드 생성
    # --------------------------------------------------------------------------

    preload_layout_nodes(
        station_name=station_name,
        station_code=station_code,
        station_metadata=station_metadata,
        nodes=nodes,
    )

    preload_layout_exits(
        station_name=station_name,
        station_code=station_code,
        nodes=nodes,
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

        elevators = station_data.get(
            "elevators",
            [],
        )

        escalators = station_data.get(
            "escalators",
            [],
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
    # 환승 연결
    # --------------------------------------------------------------------------

    if has_station_layout(station_name):

        # 실제 구조가 정의된 역은 명시적 layout 환승을 사용합니다.
        add_layout_transfer_edges(
            station_name=station_name,
            station_code=station_code,
            nodes=nodes,
            edges=edges,
        )

        add_layout_exit_connections(
            station_name=station_name,
            station_code=station_code,
            nodes=nodes,
            edges=edges,
        )

    else:

        # 아직 layout이 없는 역은 기존 환승 추론을 유지합니다.
        add_transfer_walking_edges(
            station_name=station_name,
            station_code=station_code,
            nodes=nodes,
            edges=edges,
        )

        add_imae_transfer_walking_edges(
            station_name=station_name,
            station_code=station_code,
            nodes=nodes,
            edges=edges,
        )

    return {
        "station_id": station_code,
        "station_name": station_name,
        "source_files": source_files,
        "total_nodes": len(nodes),
        "total_edges": len(edges),
        "nodes": list(
            nodes.values()
        ),
        "edges": edges,
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

        graph = build_station_graph(
            station_name=station_name,
            station_metadata=station_metadata,
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

        platform_count = sum(
            1
            for node
            in graph[
                "nodes"
            ]
            if node.get(
                "type"
            )
            == "PLATFORM"
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

        exit_count = sum(
            1
            for node
            in graph[
                "nodes"
            ]
            if node.get(
                "type"
            )
            == "EXIT"
        )

        accessible_entrance_count = sum(
            1
            for node
            in graph[
                "nodes"
            ]
            if node.get(
                "type"
            )
            == "ACCESSIBLE_ENTRANCE"
        )

        stair_count = sum(
            1
            for edge
            in graph[
                "edges"
            ]
            if edge.get(
                "transport_type"
            )
            == "STAIR"
        )

        escalator_count = sum(
            1
            for edge
            in graph[
                "edges"
            ]
            if edge.get(
                "transport_type"
            )
            == "ESCALATOR"
        )

        connected_exit_ids = {
            node_id
            for edge in graph["edges"]
            for node_id in (
                str(edge.get("from_node", "")),
                str(edge.get("to_node", "")),
            )
            if "_1F_EXIT_" in node_id
        }

        connected_exit_count = len(
            connected_exit_ids
        )

        layout_mark = (
            " [LAYOUT]"
            if has_station_layout(
                station_name
            )
            else ""
        )

        print(
            f"{station_name}{layout_mark}: "
            f"노드 {graph['total_nodes']}개 / "
            f"간선 {graph['total_edges']}개 / "
            f"대합실 {concourse_count}개 / "
            f"승강장 {platform_count}개 / "
            f"출구 {exit_count}개 "
            f"(연결 {connected_exit_count}개) / "
            f"지상 EV접근점 {accessible_entrance_count}개 / "
            f"계단 {stair_count}개 / "
            f"에스컬레이터 {escalator_count}개 / "
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

