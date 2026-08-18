from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from app.data.station_metadata import STATION_METADATA
from app.data.station_layouts import STATION_LAYOUTS
from app.data.station_graphs import get_station_graph_config
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
    return re.sub(
        r"\s+",
        "",
        str(text or ""),
    )


def safe_line_name(
    line_name: str,
) -> str:
    return (
        str(line_name or "공통")
        .strip()
        .replace(" ", "_")
        .replace("/", "_")
    )


def contains_platform_keyword(
    text: str,
) -> bool:
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
    config = get_station_graph_config(station_name)

    directional_platforms = config.get(
        "directional_platforms",
        {},
    )

    platform_config = directional_platforms.get(
        (
            line_name,
            str(floor).strip().upper(),
        ),
        {},
    )

    text = compact_text(detail_location)

    for platform_key, info in platform_config.items():
        for keyword in info.get("keywords", []):
            if compact_text(keyword) in text:
                return platform_key

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
    *,
    station_name: str | None = None,
    line_name: str | None = None,
    floor: str | None = None,
) -> str:
    if station_name and line_name and floor:
        config = get_station_graph_config(station_name)

        info = (
            config
            .get("directional_platforms", {})
            .get(
                (
                    line_name,
                    str(floor).strip().upper(),
                ),
                {},
            )
            .get(platform_key, {})
        )

        label = info.get("label")

        if label:
            return str(label)

    fallback_names = {
        "YATAB": "야탑 방향",
        "TAEPYEONG": "태평 방향",
        "MORAN": "모란 방향",
        "IMAE": "이매 방향",
    }

    return fallback_names.get(
        platform_key,
        platform_key,
    )


def get_directional_platform_keys_for_layout(
    *,
    station_name: str,
    line_name: str,
    floor: str,
) -> tuple[str, ...]:
    config = get_station_graph_config(station_name)

    platform_config = (
        config
        .get("directional_platforms", {})
        .get(
            (
                line_name,
                str(floor).strip().upper(),
            ),
            {},
        )
    )

    return tuple(platform_config.keys())


def is_unresolved_directional_platform_facility(
    *,
    station_name: str,
    line_name: str,
    from_floor: str,
    to_floor: str,
    detail_location: str,
) -> bool:
    directional_floor = None

    for floor in (from_floor, to_floor):
        if get_directional_platform_keys_for_layout(
            station_name=station_name,
            line_name=line_name,
            floor=floor,
        ):
            directional_floor = str(floor).strip().upper()
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
    compact = compact_text(text)

    keywords = (
        "환승통로",
        "환승표내는곳",
        "환승구간",
    )

    return any(keyword in compact for keyword in keywords)


def is_ground_connection(
    facility: dict[str, Any],
) -> bool:
    from_ground = str(facility.get("grndDvNmFr", "")).strip()
    to_ground = str(facility.get("grndDvNmTo", "")).strip()

    if from_ground == "지상" or to_ground == "지상":
        return True

    if from_ground and to_ground:
        return False

    detail_location = str(facility.get("dtlLoc", ""))

    if "출입구" in detail_location and "승강장" not in detail_location:
        return True

    return False


# ==============================================================================
# 4. STATION_LAYOUTS 관련 유틸
# ==============================================================================

def get_station_layout(
    station_name: str,
) -> dict[str, Any] | None:
    """
    역별 개별 설정 파일의 layout을 최우선으로 사용합니다.

    협업 시 station_layouts.py를 여러 명이 함께 수정하지 않도록,
    moran.py / yatap.py / seongnam.py 같은 개별 역 설정의 layout을
    먼저 읽고, 개별 layout이 없는 기존 역에 대해서만
    STATION_LAYOUTS를 fallback으로 사용합니다.
    """

    config = get_station_graph_config(station_name)
    config_layout = config.get("layout")

    if isinstance(config_layout, dict):
        return config_layout

    layout = STATION_LAYOUTS.get(station_name)

    if isinstance(layout, dict):
        return layout

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

        if str(space.get("line_name", "")).strip() != normalized_line:
            continue

        if str(space.get("floor", "")).strip().upper() != normalized_floor:
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
    layout = get_station_layout(station_name)

    if layout:
        exits = layout.get("exits")
        if isinstance(exits, list) and exits:
            return [
                exit_info for exit_info in exits if isinstance(exit_info, dict)
            ]

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

    for exit_info in get_layout_exits(station_name):
        if str(exit_info.get("exit_no", "")).strip() == target:
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
    if has_station_layout(station_name):
        node_id = make_layout_space_node_id(
            station_code=station_code,
            line_name=line_name,
            floor=floor,
            space_type="CONCOURSE",
        )
        node_line_name = line_name
        description = f"{station_name} {line_name} {floor} 대합실"
    else:
        node_id = f"{station_code}_{floor}_CONCOURSE"
        node_line_name = "공통"
        description = f"{station_name} {floor} 대합실/환승 구역"

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
        node_id = f"{station_code}_{floor}_CONCOURSE"

    if node_id in nodes:
        return nodes[node_id]

    node = create_concourse_node(
        station_name=station_name,
        station_code=station_code,
        floor=floor,
        line_name=line_name,
    )

    add_node(nodes, node)
    return node


def get_ground_ev_access_key(
    *,
    station_name: str,
    detail_location: str,
) -> str | None:
    config = get_station_graph_config(station_name)
    access_config = config.get("ground_ev_access", {})
    text = compact_text(detail_location)

    for access_key, info in access_config.items():
        for keyword in info.get("keywords", []):
            if compact_text(keyword) in text:
                return access_key

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
    node_id = f"{station_code}_1F_EV_ACCESS_{access_key}"
    existing = nodes.get(node_id)

    if existing:
        return existing

    config = get_station_graph_config(station_name)
    access_info = config.get("ground_ev_access", {}).get(access_key, {})
    nearby_exit_nos = access_info.get("nearby_exit_nos") or access_key.split("_")

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
        "description": f"{station_name} {'/'.join(nearby_exit_nos)}번 출구 사이 지상 엘리베이터 접근점",
    }

    add_node(nodes, node)
    return node


def create_exit_node(
    station_name: str,
    station_code: str,
    exit_no: str,
    line_name: str = "공통",
) -> dict[str, Any]:
    node_id = f"{station_code}_1F_EXIT_{exit_no}"

    return {
        "id": node_id,
        "station_code": station_code,
        "station_name": station_name,
        "type": "EXIT",
        "floor": "1F",
        "line_name": line_name,
        "exit_no": exit_no,
        "description": f"{station_name} {exit_no}번 출구",
    }


def get_or_create_exit_node(
    *,
    station_name: str,
    station_code: str,
    exit_no: str,
    nodes: dict[str, dict[str, Any]],
    fallback_line_name: str = "공통",
) -> dict[str, Any]:
    node_id = f"{station_code}_1F_EXIT_{exit_no}"

    layout_exit = find_layout_exit(
        station_name=station_name,
        exit_no=exit_no,
    )

    if layout_exit:
        line_name = str(layout_exit.get("line_name", fallback_line_name)).strip() or fallback_line_name
    else:
        line_name = fallback_line_name

    existing = nodes.get(node_id)

    if existing:
        if layout_exit and existing.get("line_name") == "공통":
            existing["line_name"] = line_name
        return existing

    node = create_exit_node(
        station_name=station_name,
        station_code=station_code,
        exit_no=exit_no,
        line_name=line_name,
    )

    add_node(nodes, node)
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

        line_name = str(space.get("line_name", "")).strip()
        floor = str(space.get("floor", "")).strip().upper()
        space_type = str(space.get("type", "")).strip().upper()

        if not line_name or not floor:
            continue

        try:
            line_index = line_names.index(line_name) + 1
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
            platform_keys = get_directional_platform_keys_for_layout(
                station_name=station_name,
                line_name=line_name,
                floor=floor,
            )

            if platform_keys:
                for platform_key in platform_keys:
                    get_or_create_platform_node(
                        station_name=station_name,
                        station_code=station_code,
                        line_name=line_name,
                        line_index=line_index,
                        facility_type="LAYOUT",
                        facility_index=0,
                        floor=floor,
                        detail_location=get_directional_platform_description(
                            platform_key,
                            station_name=station_name,
                            line_name=line_name,
                            floor=floor,
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
    for exit_info in get_layout_exits(station_name):
        exit_no = str(exit_info.get("exit_no", "")).strip()

        if not exit_no:
            continue

        line_name = str(exit_info.get("line_name", "공통")).strip() or "공통"

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
    layout = get_station_layout(station_name)

    if not layout:
        return

    connections = layout.get("exit_connections", [])

    if not isinstance(connections, list):
        return

    connection_index = 1

    for connection in connections:
        if not isinstance(connection, dict):
            continue

        from_line = str(connection.get("from_line", "")).strip()
        from_floor = str(connection.get("from_floor", "")).strip().upper()
        exit_no = str(connection.get("exit_no", "")).strip()

        if not (from_line and from_floor and exit_no):
            continue

        from_space = find_layout_space(
            station_name=station_name,
            line_name=from_line,
            floor=from_floor,
        )

        if not from_space:
            continue

        from_type = str(from_space.get("type", "")).strip().upper()

        from_node_id = make_layout_space_node_id(
            station_code=station_code,
            line_name=from_line,
            floor=from_floor,
            space_type=from_type,
        )

        exit_node_id = f"{station_code}_1F_EXIT_{exit_no}"

        if from_node_id not in nodes or exit_node_id not in nodes:
            continue

        transport_type = str(connection.get("transport_type", "WALKING")).strip().upper()

        already_exists = any(
            {
                str(edge.get("from_node", "")),
                str(edge.get("to_node", "")),
            }
            == {
                from_node_id,
                exit_node_id,
            }
            and str(edge.get("transport_type", "")).upper() == transport_type
            for edge in edges
        )

        if already_exists:
            continue

        edge_id = f"{station_code}_LAYOUT_EXIT_{connection_index:03d}"
        connection_index += 1

        edges.append(
            {
                "id": edge_id,
                "station_name": station_name,
                "line_name": from_line,
                "from_node": from_node_id,
                "to_node": exit_node_id,
                "transport_type": transport_type,
                "wheelchair_accessible": bool(connection.get("wheelchair_accessible", False)),
                "is_bidirectional": bool(connection.get("is_bidirectional", True)),
                "from_floor": from_floor,
                "to_floor": "1F",
                "exit_no": exit_no,
                "detail_location": str(connection.get("detail_location", f"{exit_no}번 출구")),
                "direction": connection.get("direction"),
                "direction_name": connection.get("direction_name"),
                "operator_code": None,
                "line_code": None,
                "kric_station_code": None,
                "description": f"{station_name} {from_line} {from_floor} → {exit_no}번 출구 {transport_type} 연결",
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
    platform_nodes = [
        node for node in list(nodes.values())
        if node.get("type") == "PLATFORM" and is_transfer_area_text(node.get("detail_location", ""))
    ]

    walking_index = 1

    for platform_node in platform_nodes:
        floor = str(platform_node.get("floor", "")).strip()
        line_name = str(platform_node.get("line_name", "공통")).strip()

        if not floor:
            continue

        concourse_node = get_or_create_concourse_node(
            station_name=station_name,
            station_code=station_code,
            floor=floor,
            line_name=line_name,
            nodes=nodes,
        )

        platform_node_id = str(platform_node.get("id", "")).strip()
        concourse_node_id = str(concourse_node.get("id", "")).strip()

        if not platform_node_id or not concourse_node_id or platform_node_id == concourse_node_id:
            continue

        already_exists = any(
            str(edge.get("transport_type", "")).upper() == "WALKING"
            and {str(edge.get("from_node", "")), str(edge.get("to_node", ""))} == {platform_node_id, concourse_node_id}
            for edge in edges
        )

        if already_exists:
            continue

        while True:
            edge_id = f"{station_code}_WALK_TRANSFER_{walking_index:03d}"
            walking_index += 1
            if not any(edge.get("id") == edge_id for edge in edges):
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
                "detail_location": platform_node.get("detail_location", ""),
                "direction": None,
                "direction_name": None,
                "operator_code": None,
                "line_code": None,
                "kric_station_code": None,
                "description": f"{station_name} {floor} 환승구역 내부 보행 연결",
            }
        )


def add_layout_transfer_edges(
    *,
    station_name: str,
    station_code: str,
    nodes: dict[str, dict[str, Any]],
    edges: list[dict[str, Any]],
) -> None:
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

        from_line = str(transfer.get("from_line", "")).strip()
        from_floor = str(transfer.get("from_floor", "")).strip().upper()
        to_line = str(transfer.get("to_line", "")).strip()
        to_floor = str(transfer.get("to_floor", "")).strip().upper()
        transport_type = str(transfer.get("transport_type", "WALKING")).strip().upper()

        if not (from_line and from_floor and to_line and to_floor):
            continue

        from_space = find_layout_space(station_name=station_name, line_name=from_line, floor=from_floor)
        to_space = find_layout_space(station_name=station_name, line_name=to_line, floor=to_floor)

        if not from_space or not to_space:
            continue

        from_type = str(from_space.get("type", "")).strip().upper()
        to_type = str(to_space.get("type", "")).strip().upper()

        from_node_id = make_layout_space_node_id(station_code=station_code, line_name=from_line, floor=from_floor, space_type=from_type)
        to_node_id = make_layout_space_node_id(station_code=station_code, line_name=to_line, floor=to_floor, space_type=to_type)

        if from_node_id not in nodes or to_node_id not in nodes or from_node_id == to_node_id:
            continue

        already_exists = any(
            str(edge.get("transport_type", "")).upper() == transport_type
            and {str(edge.get("from_node", "")), str(edge.get("to_node", ""))} == {from_node_id, to_node_id}
            for edge in edges
        )

        if already_exists:
            continue

        while True:
            edge_id = f"{station_code}_WALK_LAYOUT_TRANSFER_{transfer_index:03d}"
            transfer_index += 1
            if not any(edge.get("id") == edge_id for edge in edges):
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
                "detail_location": f"{station_name} {from_line} {from_floor} ↔ {to_line} {to_floor} 환승",
                "direction": None,
                "direction_name": None,
                "operator_code": None,
                "line_code": None,
                "kric_station_code": None,
                "description": f"{station_name} {from_line} ↔ {to_line} 환승 보행 연결",
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
    if station_name != "이매역" or has_station_layout(station_name):
        return

    b2_concourse_id = f"{station_code}_B2_CONCOURSE"
    b2_concourse = nodes.get(b2_concourse_id)

    if not b2_concourse:
        return

    target_platforms: list[dict[str, Any]] = []

    for node in nodes.values():
        if node.get("type") != "PLATFORM":
            continue
        if str(node.get("line_name", "")).strip() != "수인분당선":
            continue
        if str(node.get("floor", "")).strip().upper() != "B2":
            continue

        detail_location = compact_text(node.get("detail_location", ""))

        if any(keyword in detail_location for keyword in ("야탑", "서현", "왕십리", "청량리", "죽전", "고색", "인천")):
            target_platforms.append(node)

    walking_index = 1

    for platform_node in target_platforms:
        platform_node_id = str(platform_node.get("id", "")).strip()
        if not platform_node_id:
            continue

        already_exists = any(
            str(edge.get("transport_type", "")).upper() == "WALKING"
            and {str(edge.get("from_node", "")), str(edge.get("to_node", ""))} == {b2_concourse_id, platform_node_id}
            for edge in edges
        )

        if already_exists:
            continue

        while True:
            edge_id = f"{station_code}_WALK_IMAE_TRANSFER_{walking_index:03d}"
            walking_index += 1
            if not any(edge.get("id") == edge_id for edge in edges):
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
                "detail_location": platform_node.get("detail_location", ""),
                "direction": None,
                "direction_name": None,
                "operator_code": None,
                "line_code": None,
                "kric_station_code": None,
                "description": "이매역 B2 환승구간 ↔ 수인분당선 B2 승강장 보행 연결",
            }
        )


# ==============================================================================
# 6-2. 역별 수동 검증 간선
# ==============================================================================

def add_station_config_manual_edges(
    *,
    station_name: str,
    station_code: str,
    nodes: dict[str, dict[str, Any]],
    edges: list[dict[str, Any]],
) -> None:
    """
    각 역의 STATION_GRAPH_CONFIG["manual_edges"]를 그래프에 추가합니다.
    같은 두 노드 사이에 실제 시설이 여러 개 있어도 edge id가 다르면 모두 보존합니다.
    """
    station_config = get_station_graph_config(station_name)
    manual_edges = station_config.get("manual_edges", [])

    if not isinstance(manual_edges, list):
        return

    existing_edge_ids = {
        str(edge.get("id", "")).strip()
        for edge in edges
        if str(edge.get("id", "")).strip()
    }

    for manual_index, manual_edge in enumerate(manual_edges, start=1):
        if not isinstance(manual_edge, dict):
            continue

        from_node_id = str(manual_edge.get("from_node", "")).strip()
        to_node_id = str(manual_edge.get("to_node", "")).strip()

        if not from_node_id or not to_node_id:
            print(f"⚠️ {station_name} manual edge {manual_index}: from_node / to_node 누락")
            continue

        if from_node_id not in nodes:
            print(f"⚠️ {station_name} manual edge {manual_index}: from_node 없음 -> {from_node_id}")
            continue

        if to_node_id not in nodes:
            print(f"⚠️ {station_name} manual edge {manual_index}: to_node 없음 -> {to_node_id}")
            continue

        edge_id = str(manual_edge.get("id", "")).strip()
        if not edge_id:
            edge_id = f"{station_code}_MANUAL_{manual_index:03d}"

        if edge_id in existing_edge_ids:
            continue

        transport_type = str(
            manual_edge.get("transport_type", "WALKING")
        ).strip().upper()

        from_node = nodes[from_node_id]
        to_node = nodes[to_node_id]

        default_accessible = transport_type in {"WALKING", "ELEVATOR"}

        edges.append(
            {
                "id": edge_id,
                "station_name": station_name,
                "line_name": manual_edge.get("line_name"),
                "from_node": from_node_id,
                "to_node": to_node_id,
                "transport_type": transport_type,
                "wheelchair_accessible": bool(
                    manual_edge.get("wheelchair_accessible", default_accessible)
                ),
                "is_bidirectional": bool(
                    manual_edge.get("is_bidirectional", True)
                ),
                "from_floor": str(
                    manual_edge.get("from_floor", from_node.get("floor", "")) or ""
                ).strip().upper(),
                "to_floor": str(
                    manual_edge.get("to_floor", to_node.get("floor", "")) or ""
                ).strip().upper(),
                "exit_no": manual_edge.get("exit_no"),
                "detail_location": str(manual_edge.get("detail_location", "")),
                "direction": manual_edge.get("direction"),
                "direction_name": manual_edge.get("direction_name"),
                "operator_code": manual_edge.get("operator_code"),
                "line_code": manual_edge.get("line_code"),
                "kric_station_code": manual_edge.get("kric_station_code"),
                "verification_status": manual_edge.get(
                    "verification_status", "VERIFIED"
                ),
                "source": manual_edge.get("source", "STATION_CONFIG"),
                "description": str(
                    manual_edge.get(
                        "description",
                        f"{station_name} {from_node_id} ↔ {to_node_id} {transport_type}",
                    )
                ),
            }
        )

        existing_edge_ids.add(edge_id)



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
) -> tuple[dict[str, Any], dict[str, Any]]:
    if has_station_layout(station_name):
        from_layout_node = get_or_create_layout_space_node(
            station_name=station_name, station_code=station_code, line_name=line_name,
            line_index=line_index, facility_type=facility_type, facility_index=facility_index,
            floor=from_floor, detail_location=detail_location, nodes=nodes,
        )
        to_layout_node = get_or_create_layout_space_node(
            station_name=station_name, station_code=station_code, line_name=line_name,
            line_index=line_index, facility_type=facility_type, facility_index=facility_index,
            floor=to_floor, detail_location=detail_location, nodes=nodes,
        )

        if from_layout_node is not None and to_layout_node is not None:
            return (from_layout_node, to_layout_node)

    from_depth = get_floor_depth(from_floor)
    to_depth = get_floor_depth(to_floor)

    if contains_platform_keyword(detail_location):
        if from_depth > to_depth:
            platform_floor = from_floor
            concourse_floor = to_floor
            platform_is_from = True
        elif to_depth > from_depth:
            platform_floor = to_floor
            concourse_floor = from_floor
            platform_is_from = False
        else:
            platform_floor = from_floor
            concourse_floor = to_floor
            platform_is_from = True

        platform_node = get_or_create_platform_node(
            station_name=station_name, station_code=station_code, line_name=line_name,
            line_index=line_index, facility_type=facility_type, facility_index=facility_index,
            floor=platform_floor, detail_location=detail_location, nodes=nodes,
        )

        concourse_node = get_or_create_concourse_node(
            station_name=station_name, station_code=station_code, floor=concourse_floor,
            line_name=line_name, nodes=nodes,
        )

        if platform_is_from:
            return (platform_node, concourse_node)

        return (concourse_node, platform_node)

    from_node = get_or_create_concourse_node(
        station_name=station_name, station_code=station_code, floor=from_floor,
        line_name=line_name, nodes=nodes,
    )

    to_node = get_or_create_concourse_node(
        station_name=station_name, station_code=station_code, floor=to_floor,
        line_name=line_name, nodes=nodes,
    )

    return (from_node, to_node)


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
    detail_location = str(elevator.get("dtlLoc", "")).strip()

    from_floor = normalize_floor(
        elevator.get("grndDvNmFr"),
        elevator.get("runStinFlorFr"),
    )

    to_floor = normalize_floor(
        elevator.get("grndDvNmTo"),
        elevator.get("runStinFlorTo"),
    )

    if is_unresolved_directional_platform_facility(
        station_name=station_name,
        line_name=line_name,
        from_floor=from_floor,
        to_floor=to_floor,
        detail_location=detail_location,
    ):
        return

    exit_no = normalize_exit_no(elevator.get("exitNo"))

    if not exit_no:
        exit_no = extract_exit_no_from_location(detail_location)

    edge_id = f"{station_code}_{line_index:02d}_EV_{facility_index:03d}"

    if is_ground_connection(elevator):
        if not exit_no:
            exit_no = f"UNKNOWN_{line_index:02d}_{facility_index:03d}"

        access_key = get_ground_ev_access_key(
            station_name=station_name,
            detail_location=detail_location,
        )

        if access_key:
            ground_node = get_or_create_accessible_entrance_node(
                station_name=station_name,
                station_code=station_code,
                line_name=line_name,
                access_key=access_key,
                detail_location=detail_location,
                nodes=nodes,
            )
            exit_no = None
        else:
            ground_node = get_or_create_exit_node(
                station_name=station_name,
                station_code=station_code,
                exit_no=exit_no,
                nodes=nodes,
                fallback_line_name=line_name,
            )

        if str(elevator.get("grndDvNmFr", "")).strip() == "지하":
            underground_floor = from_floor
            underground_is_from = True
        else:
            underground_floor = to_floor
            underground_is_from = False

        underground_node = get_or_create_layout_space_node(
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

        if underground_node is None:
            underground_node = get_or_create_concourse_node(
                station_name=station_name,
                station_code=station_code,
                floor=underground_floor,
                line_name=line_name,
                nodes=nodes,
            )

        if underground_is_from:
            from_node = underground_node
            to_node = ground_node
        else:
            from_node = ground_node
            to_node = underground_node

    else:
        from_node, to_node = determine_internal_endpoints(
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
            "operator_code": elevator.get("railOprIsttCd"),
            "line_code": elevator.get("lnCd"),
            "kric_station_code": elevator.get("stinCd"),
            "capacity_persons": elevator.get("rglnPsno"),
            "capacity_weight_kg": elevator.get("rglnWgt"),
            "description": f"{line_name} 엘리베이터 ({detail_location})",
        }
    )


# ==============================================================================
# 9. 에스컬레이터 변환 (단방향/양방향 올바른 생성 로직 수정)
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

    detail_location = str(escalator.get("dtlLoc", "")).strip()

    from_floor = normalize_floor(
        escalator.get("grndDvNmFr"),
        escalator.get("runStinFlorFr"),
    )

    to_floor = normalize_floor(
        escalator.get("grndDvNmTo"),
        escalator.get("runStinFlorTo"),
    )

    if is_unresolved_directional_platform_facility(
        station_name=station_name,
        line_name=line_name,
        from_floor=from_floor,
        to_floor=to_floor,
        detail_location=detail_location,
    ):
        return

    direction_name = str(escalator.get("updnDvNm", "")).strip()

    if direction_name == "상행":
        direction = "UP"
    elif direction_name == "하행":
        direction = "DOWN"
    else:
        direction = "UNKNOWN"

    exit_no = normalize_exit_no(escalator.get("exitNo"))

    if not exit_no:
        exit_no = extract_exit_no_from_location(detail_location)

    station_config = get_station_graph_config(station_name)

    effective_transport_type = (
        station_config
        .get("facility_type_overrides", {})
        .get("ESCALATOR", "ESCALATOR")
    )

    is_stair_override = (effective_transport_type == "STAIR")

    edge_type_code = "STAIR" if is_stair_override else "ES"

    edge_id = f"{station_code}_{line_index:02d}_{edge_type_code}_{facility_index:03d}"

    if is_ground_connection(escalator):
        if not exit_no:
            exit_no = f"UNKNOWN_{line_index:02d}_{facility_index:03d}"

        exit_node = get_or_create_exit_node(
            station_name=station_name,
            station_code=station_code,
            exit_no=exit_no,
            nodes=nodes,
            fallback_line_name=line_name,
        )

        if str(escalator.get("grndDvNmFr", "")).strip() == "지하":
            underground_floor = from_floor
            underground_is_lower = True
        else:
            underground_floor = to_floor
            underground_is_lower = False

        underground_node = get_or_create_layout_space_node(
            station_name=station_name,
            station_code=station_code,
            line_name=line_name,
            line_index=line_index,
            facility_type="STAIR" if is_stair_override else "ES",
            facility_index=facility_index,
            floor=underground_floor,
            detail_location=detail_location,
            nodes=nodes,
        )

        if underground_node is None:
            underground_node = get_or_create_concourse_node(
                station_name=station_name,
                station_code=station_code,
                floor=underground_floor,
                line_name=line_name,
                nodes=nodes,
            )

        lower_node = underground_node if underground_is_lower else exit_node
        upper_node = exit_node if underground_is_lower else underground_node

    else:
        node1, node2 = determine_internal_endpoints(
            station_name=station_name,
            station_code=station_code,
            line_name=line_name,
            line_index=line_index,
            facility_type="STAIR" if is_stair_override else "ES",
            facility_index=facility_index,
            from_floor=from_floor,
            to_floor=to_floor,
            detail_location=detail_location,
            nodes=nodes,
        )

        depth1 = get_floor_depth(from_floor)
        depth2 = get_floor_depth(to_floor)

        if depth1 >= depth2:
            lower_node = node1
            upper_node = node2
        else:
            lower_node = node2
            upper_node = node1

    if lower_node["id"] == upper_node["id"]:
        return

    # 🎯 방향(상행/하행/미지정)에 따른 단방향/양방향 간선 결정
    if is_stair_override or direction == "UNKNOWN":
        is_bidirectional = True
        from_node = lower_node
        to_node = upper_node
    elif direction == "UP":
        is_bidirectional = False
        from_node = lower_node  # 아래층 -> 위층
        to_node = upper_node
    elif direction == "DOWN":
        is_bidirectional = False
        from_node = upper_node  # 위층 -> 아래층
        to_node = lower_node

    if is_stair_override:
        preserve_stair_records = bool(
            station_config
            .get("preserve_facility_records", {})
            .get("STAIR", False)
        )

        if not preserve_stair_records:
            already_exists = any(
                str(edge.get("transport_type", "")).upper() == "STAIR"
                and {
                    str(edge.get("from_node", "")),
                    str(edge.get("to_node", "")),
                }
                == {
                    from_node["id"],
                    to_node["id"],
                }
                and str(edge.get("exit_no", "")) == str(exit_no or "")
                for edge in edges
            )

            if already_exists:
                return

    edges.append(
        {
            "id": edge_id,
            "station_name": station_name,
            "line_name": line_name,
            "from_node": from_node["id"],
            "to_node": to_node["id"],
            "transport_type": "STAIR" if is_stair_override else "ESCALATOR",
            "wheelchair_accessible": False,
            "is_bidirectional": is_bidirectional,
            "direction": None if is_stair_override else direction,
            "direction_name": None if is_stair_override else direction_name,
            "from_floor": from_floor,
            "to_floor": to_floor,
            "exit_no": exit_no,
            "detail_location": detail_location,
            "operator_code": escalator.get("railOprIsttCd"),
            "line_code": escalator.get("lnCd"),
            "kric_station_code": escalator.get("stinCd"),
            "description": f"{line_name} {'계단' if is_stair_override else '에스컬레이터'} ({detail_location})",
        }
    )


# ==============================================================================
# 10. 역 하나의 그래프 생성
# ==============================================================================

def build_station_graph(
    station_name: str,
    station_metadata: dict[str, Any],
) -> dict[str, Any]:
    station_code = INTERNAL_STATION_CODES[station_name]

    nodes: dict[str, dict[str, Any]] = {}
    edges: list[dict[str, Any]] = []
    source_files: list[str] = []

    lines = station_metadata.get("lines", {})

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

    for line_index, (line_name, line_metadata) in enumerate(lines.items(), start=1):
        try:
            station_data = load_facility_json(
                station_name=station_name,
                line_name=line_name,
            )
        except (FileNotFoundError, ValueError) as error:
            print(f"⚠️ {station_name} / {line_name} 시설 데이터 로드 실패: {error}")
            continue

        integrated_source = "Elevator_Escalator_현황_통합.json"

        if integrated_source not in source_files:
            source_files.append(integrated_source)

        elevators = station_data.get("elevators", [])
        escalators = station_data.get("escalators", [])

        if not isinstance(elevators, list):
            elevators = []
        if not isinstance(escalators, list):
            escalators = []

        for facility_index, elevator in enumerate(elevators, start=1):
            if not isinstance(elevator, dict):
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

        for facility_index, escalator in enumerate(escalators, start=1):
            if not isinstance(escalator, dict):
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

    if has_station_layout(station_name):
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

        add_station_config_manual_edges(
            station_name=station_name,
            station_code=station_code,
            nodes=nodes,
            edges=edges,
        )
    else:
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
        "nodes": list(nodes.values()),
        "edges": edges,
    }


# ==============================================================================
# 11. 전체 역 그래프 생성
# ==============================================================================

def build_all_station_graphs() -> dict[str, dict[str, Any]]:
    all_graphs: dict[str, dict[str, Any]] = {}

    for station_name, station_metadata in STATION_METADATA.items():
        if station_name not in INTERNAL_STATION_CODES:
            continue

        graph = build_station_graph(
            station_name=station_name,
            station_metadata=station_metadata,
        )

        all_graphs[station_name] = graph

    return all_graphs


# ==============================================================================
# 12. JSON 저장
# ==============================================================================

def save_all_station_graphs(
    graphs: dict[str, dict[str, Any]],
) -> Path:
    GRAPH_DATA_DIR.mkdir(parents=True, exist_ok=True)

    with OUTPUT_FILE.open("w", encoding="utf-8") as file:
        json.dump(
            graphs,
            file,
            ensure_ascii=False,
            indent=2,
        )

    return OUTPUT_FILE


def build_and_save_all_station_graphs() -> Path:
    graphs = build_all_station_graphs()
    output_path = save_all_station_graphs(graphs)

    print("\n======================================")
    print("층별 역 내부 이동 그래프 생성 완료")
    print("======================================")

    for station_name, graph in graphs.items():
        concourse_count = sum(1 for node in graph["nodes"] if node.get("type") == "CONCOURSE")
        platform_count = sum(1 for node in graph["nodes"] if node.get("type") == "PLATFORM")
        walking_count = sum(1 for edge in graph["edges"] if edge.get("transport_type") == "WALKING")
        exit_count = sum(1 for node in graph["nodes"] if node.get("type") == "EXIT")
        accessible_entrance_count = sum(
            1
            for node in graph["nodes"]
            if node.get("type") == "ACCESSIBLE_ENTRANCE"
        )

        ground_elevator_count = sum(
            1
            for edge in graph["edges"]
            if edge.get("transport_type") == "ELEVATOR"
            and (
                (
                    str(edge.get("from_floor", "")).upper().endswith("F")
                    and not str(edge.get("from_floor", "")).upper().startswith("B")
                )
                or
                (
                    str(edge.get("to_floor", "")).upper().endswith("F")
                    and not str(edge.get("to_floor", "")).upper().startswith("B")
                )
            )
        )

        stair_count = sum(1 for edge in graph["edges"] if edge.get("transport_type") == "STAIR")
        escalator_count = sum(1 for edge in graph["edges"] if edge.get("transport_type") == "ESCALATOR")

        connected_exit_ids = {
            node_id
            for edge in graph["edges"]
            for node_id in (str(edge.get("from_node", "")), str(edge.get("to_node", "")))
            if "_1F_EXIT_" in node_id
        }

        connected_exit_count = len(connected_exit_ids)
        layout_mark = " [LAYOUT]" if has_station_layout(station_name) else ""

        print(
            f"{station_name}{layout_mark}: "
            f"노드 {graph['total_nodes']}개 / "
            f"간선 {graph['total_edges']}개 / "
            f"대합실 {concourse_count}개 / "
            f"승강장 {platform_count}개 / "
            f"출구 {exit_count}개 "
            f"(연결 {connected_exit_count}개) / "
            f"지상 EV접근점 {accessible_entrance_count}개 / "
            f"지상 연결 EV {ground_elevator_count}개 / "
            f"계단 {stair_count}개 / "
            f"에스컬레이터 {escalator_count}개 / "
            f"환승 보행간선 {walking_count}개"
        )

    print("--------------------------------------")
    print(f"저장 위치: {output_path}")

    return output_path


# ==============================================================================
# 13. 직접 실행
# ==============================================================================

if __name__ == "__main__":
    build_and_save_all_station_graphs()
