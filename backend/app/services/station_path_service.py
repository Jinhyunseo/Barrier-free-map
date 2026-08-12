from __future__ import annotations

import json
from collections import deque
from pathlib import Path
from typing import Any

from app.services.facility_status_service import (
    attach_realtime_status_to_facilities,
)


# ==============================================================================
# 1. 그래프 JSON 경로
# ==============================================================================

APP_DIR = Path(__file__).resolve().parent.parent

GRAPH_FILE = (
    APP_DIR
    / "data"
    / "station_graphs"
    / "all_stations_graph.json"
)


# ==============================================================================
# 2. 실제 열차 승강장 층 메타데이터
# ==============================================================================
#
# all_stations_graph.json의 PLATFORM 노드 중에는
# 실제 열차 승강장뿐 아니라 환승통로/승강설비 연결 위치가
# PLATFORM 타입으로 생성된 경우도 있습니다.
#
# 따라서 실제 열차가 정차하는 층을 명시해
# 플랫폼 선택 시 잘못된 노드를 고르는 것을 방지합니다.
#
# 검증이 끝난 역부터 추가합니다.
# ==============================================================================

TRAIN_PLATFORM_FLOORS: dict[
    tuple[str, str],
    str,
] = {
    ("정자역", "수인분당선"): "B2",
    ("정자역", "신분당선"): "B3",
}


# ==============================================================================
# 3. 이동 조건 정규화
# ==============================================================================

DEFAULT_MOBILITY_CONSTRAINTS: dict[str, bool] = {
    "avoid_stairs": False,
    "require_elevator": False,
    "avoid_escalator": False,
    "avoid_steep_slope": False,
    "require_low_floor_bus": False,
}


def normalize_mobility_constraints(
    mobility_constraints: dict[str, Any] | None,
) -> dict[str, bool]:
    """2차 프로토타입 이동 조건을 내부 비교용 dict로 정규화합니다."""
    normalized = dict(DEFAULT_MOBILITY_CONSTRAINTS)
    if not isinstance(mobility_constraints, dict):
        return normalized
    for key in normalized:
        normalized[key] = bool(mobility_constraints.get(key, False))
    return normalized


def _normalize_floor_value(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip().upper().replace(" ", "")


def _edge_changes_floor(edge: dict[str, Any]) -> bool:
    from_floor = _normalize_floor_value(edge.get("from_floor"))
    to_floor = _normalize_floor_value(edge.get("to_floor"))
    if not from_floor or not to_floor:
        return False
    return from_floor != to_floor

# ==============================================================================
# 4. 전체 그래프 로드
# ==============================================================================

def load_all_station_graphs() -> dict[str, Any]:
    """
    all_stations_graph.json 전체를 읽어 반환합니다.
    """

    if not GRAPH_FILE.exists():
        raise FileNotFoundError(
            "역 내부 이동 그래프 파일을 찾을 수 없습니다: "
            f"{GRAPH_FILE}"
        )

    try:
        with GRAPH_FILE.open(
            "r",
            encoding="utf-8",
        ) as file:
            data = json.load(file)

    except json.JSONDecodeError as error:
        raise ValueError(
            "all_stations_graph.json 형식이 올바르지 않습니다."
        ) from error

    if not isinstance(
        data,
        dict,
    ):
        raise ValueError(
            "역 내부 이동 그래프의 최상위 구조가 "
            "객체(dict)가 아닙니다."
        )

    return data


# ==============================================================================
# 5. 특정 역 그래프 조회
# ==============================================================================

def get_station_graph(
    station_name: str,
) -> dict[str, Any] | None:
    """
    특정 역의 내부 이동 그래프를 반환합니다.
    """

    graphs = (
        load_all_station_graphs()
    )

    graph = graphs.get(
        station_name
    )

    if not isinstance(
        graph,
        dict,
    ):
        return None

    return graph


# ==============================================================================
# 6. 특정 역 노드 조회
# ==============================================================================

def get_station_nodes(
    station_name: str,
) -> list[dict[str, Any]]:
    """
    특정 역의 노드 목록을 반환합니다.
    """

    graph = get_station_graph(
        station_name
    )

    if not graph:
        return []

    nodes = graph.get(
        "nodes",
        [],
    )

    if not isinstance(
        nodes,
        list,
    ):
        return []

    return [
        node
        for node in nodes
        if isinstance(
            node,
            dict,
        )
    ]


# ==============================================================================
# 7. 특정 역 간선 조회
# ==============================================================================

def get_station_edges(
    station_name: str,
) -> list[dict[str, Any]]:
    """
    특정 역의 간선 목록을 반환합니다.
    """

    graph = get_station_graph(
        station_name
    )

    if not graph:
        return []

    edges = graph.get(
        "edges",
        [],
    )

    if not isinstance(
        edges,
        list,
    ):
        return []

    return [
        edge
        for edge in edges
        if isinstance(
            edge,
            dict,
        )
    ]


# ==============================================================================
# 8. 그래프 요약
# ==============================================================================

def get_station_graph_summary(
    station_name: str,
) -> dict[str, Any]:
    """
    그래프 정상 로딩 여부를 확인하기 위한
    요약 정보를 반환합니다.
    """

    graph = get_station_graph(
        station_name
    )

    if not graph:
        return {
            "station_name": station_name,
            "status": "NOT_FOUND",
            "node_count": 0,
            "edge_count": 0,
            "concourse_count": 0,
        }

    nodes = get_station_nodes(
        station_name
    )

    edges = get_station_edges(
        station_name
    )

    concourse_count = sum(
        1
        for node in nodes
        if str(
            node.get(
                "type",
                "",
            )
        ).upper() == "CONCOURSE"
    )

    return {
        "station_name": station_name,
        "status": "SUCCESS",
        "station_id": graph.get(
            "station_id"
        ),
        "node_count": len(
            nodes
        ),
        "edge_count": len(
            edges
        ),
        "concourse_count": (
            concourse_count
        ),
    }


# ==============================================================================
# 9. 노드 검색 유틸
# ==============================================================================

def get_nodes_by_type(
    station_name: str,
    node_type: str,
) -> list[dict[str, Any]]:
    """
    특정 역에서 원하는 타입의 노드만 반환합니다.
    """

    nodes = get_station_nodes(
        station_name
    )

    target_type = (
        node_type
        .strip()
        .upper()
    )

    return [
        node
        for node in nodes
        if str(
            node.get(
                "type",
                "",
            )
        ).strip().upper() == target_type
    ]


def get_concourse_nodes(
    station_name: str,
) -> list[dict[str, Any]]:
    """
    특정 역의 모든 대합실 노드를 반환합니다.
    """

    return get_nodes_by_type(
        station_name,
        "CONCOURSE",
    )


def get_concourse_node_by_floor(
    station_name: str,
    floor: str,
) -> dict[str, Any] | None:
    """
    특정 층의 대합실 노드를 반환합니다.
    """

    concourse_nodes = (
        get_concourse_nodes(
            station_name
        )
    )

    target_floor = (
        str(floor)
        .strip()
        .upper()
    )

    for node in concourse_nodes:

        node_floor = str(
            node.get(
                "floor",
                "",
            )
        ).strip().upper()

        if node_floor == target_floor:
            return node

    return None


def get_exit_nodes(
    station_name: str,
) -> list[dict[str, Any]]:
    """
    특정 역의 출구 노드를 반환합니다.
    """

    return get_nodes_by_type(
        station_name,
        "EXIT",
    )


def get_platform_nodes(
    station_name: str,
    line_name: str | None = None,
) -> list[dict[str, Any]]:
    """
    특정 역의 PLATFORM 노드를 반환합니다.

    line_name이 입력되면
    해당 노선의 PLATFORM만 반환합니다.
    """

    nodes = get_nodes_by_type(
        station_name,
        "PLATFORM",
    )

    if not line_name:
        return nodes

    target_line = str(
        line_name
    ).strip()

    return [
        node
        for node in nodes
        if str(
            node.get(
                "line_name",
                "",
            )
        ).strip() == target_line
    ]


# ==============================================================================
# 10. 플랫폼 검색 문자열 정규화
# ==============================================================================

def normalize_direction_keyword(
    station_name: str | None,
) -> str:
    """
    방향 비교용 역 이름을 정규화합니다.

    예:
    수내역 -> 수내
    """

    if not station_name:
        return ""

    return (
        str(station_name)
        .replace(
            "역",
            "",
        )
        .replace(
            " ",
            "",
        )
        .strip()
    )


def get_platform_search_text(
    node: dict[str, Any],
) -> str:
    """
    플랫폼 방향 검색에 사용할 문자열을 만듭니다.
    """

    detail_location = str(
        node.get(
            "detail_location",
            "",
        )
    )

    description = str(
        node.get(
            "description",
            "",
        )
    )

    return (
        detail_location
        + " "
        + description
    ).replace(
        " ",
        ""
    )


# ==============================================================================
# 11. 플랫폼의 엘리베이터 연결 여부
# ==============================================================================

def platform_has_elevator_connection(
    station_name: str,
    platform_node_id: str,
) -> bool:
    """
    PLATFORM 노드에 엘리베이터 edge가
    직접 연결되어 있는지 확인합니다.
    """

    edges = get_station_edges(
        station_name
    )

    for edge in edges:

        transport_type = str(
            edge.get(
                "transport_type",
                "",
            )
        ).upper()

        if transport_type != "ELEVATOR":
            continue

        from_node = str(
            edge.get(
                "from_node",
                "",
            )
        )

        to_node = str(
            edge.get(
                "to_node",
                "",
            )
        )

        if platform_node_id in {
            from_node,
            to_node,
        }:
            return True

    return False


# ==============================================================================
# 12. 실제 열차 승강장 찾기
# ==============================================================================

def find_platform_node(
    station_name: str,
    line_name: str,
    direction_station: str | None,
) -> dict[str, Any] | None:
    """
    역 + 노선 + 진행 방향을 이용하여
    실제 열차 승강장 PLATFORM을 찾습니다.

    선택 순서:

    1. 역/노선 PLATFORM 조회
    2. 실제 열차 승강장 층 필터링
    3. 방향 역 이름으로 후보 검색
    4. 동일 방향 후보가 여러 개면 EV 연결 노드 우선
    """

    platform_nodes = (
        get_platform_nodes(
            station_name,
            line_name,
        )
    )

    if not platform_nodes:
        return None

    # --------------------------------------------------------------------------
    # 실제 열차 승강장 층 필터링
    # --------------------------------------------------------------------------

    train_platform_floor = (
        TRAIN_PLATFORM_FLOORS.get(
            (
                station_name,
                line_name,
            )
        )
    )

    if train_platform_floor:

        floor_matching_nodes = [
            node
            for node in platform_nodes
            if str(
                node.get(
                    "floor",
                    "",
                )
            ).strip().upper()
            == train_platform_floor.upper()
        ]

        if floor_matching_nodes:
            platform_nodes = (
                floor_matching_nodes
            )

    # --------------------------------------------------------------------------
    # 방향 정보가 없는 경우
    # --------------------------------------------------------------------------

    if not direction_station:

        for node in platform_nodes:

            node_id = str(
                node.get(
                    "id",
                    "",
                )
            )

            if platform_has_elevator_connection(
                station_name,
                node_id,
            ):
                return node

        return platform_nodes[0]

    direction_keyword = (
        normalize_direction_keyword(
            direction_station
        )
    )

    matching_nodes: list[
        dict[str, Any]
    ] = []

    for node in platform_nodes:

        search_text = (
            get_platform_search_text(
                node
            )
        )

        if (
            direction_keyword
            and direction_keyword
            in search_text
        ):
            matching_nodes.append(
                node
            )

    if not matching_nodes:
        return None

    # --------------------------------------------------------------------------
    # 같은 방향 후보가 여러 개인 경우
    # EV 연결 승강장 우선
    # --------------------------------------------------------------------------

    for node in matching_nodes:

        node_id = str(
            node.get(
                "id",
                "",
            )
        )

        if platform_has_elevator_connection(
            station_name,
            node_id,
        ):
            return node

    return matching_nodes[0]


# ==============================================================================
# 13. PLATFORM과 연결된 대합실 찾기
# ==============================================================================

def find_connected_concourses(
    station_name: str,
    platform_node_id: str,
) -> list[dict[str, Any]]:
    """
    PLATFORM과 직접 연결된
    CONCOURSE 노드를 반환합니다.
    """

    edges = get_station_edges(
        station_name
    )

    nodes = get_station_nodes(
        station_name
    )

    node_map = {
        str(
            node.get(
                "id"
            )
        ): node
        for node in nodes
        if node.get(
            "id"
        )
    }

    concourses: list[
        dict[str, Any]
    ] = []

    seen: set[str] = set()

    for edge in edges:

        from_node = str(
            edge.get(
                "from_node",
                "",
            )
        )

        to_node = str(
            edge.get(
                "to_node",
                "",
            )
        )

        connected_node_id: str | None = (
            None
        )

        if from_node == platform_node_id:
            connected_node_id = (
                to_node
            )

        elif to_node == platform_node_id:
            connected_node_id = (
                from_node
            )

        if not connected_node_id:
            continue

        connected_node = (
            node_map.get(
                connected_node_id
            )
        )

        if not connected_node:
            continue

        if str(
            connected_node.get(
                "type",
                "",
            )
        ).upper() != "CONCOURSE":
            continue

        node_id = str(
            connected_node.get(
                "id"
            )
        )

        if node_id in seen:
            continue

        seen.add(
            node_id
        )

        concourses.append(
            connected_node
        )

    return concourses


def find_connected_concourse(
    station_name: str,
    platform_node_id: str,
) -> dict[str, Any] | None:
    """
    PLATFORM과 연결된 대합실 하나를 반환합니다.

    여러 개라면 엘리베이터 연결 대합실을 우선합니다.
    """

    concourses = (
        find_connected_concourses(
            station_name,
            platform_node_id,
        )
    )

    if not concourses:
        return None

    edges = get_station_edges(
        station_name
    )

    for concourse in concourses:

        concourse_id = str(
            concourse.get(
                "id",
                "",
            )
        )

        for edge in edges:

            transport_type = str(
                edge.get(
                    "transport_type",
                    "",
                )
            ).upper()

            if transport_type != "ELEVATOR":
                continue

            from_node = str(
                edge.get(
                    "from_node",
                    "",
                )
            )

            to_node = str(
                edge.get(
                    "to_node",
                    "",
                )
            )

            if {
                from_node,
                to_node,
            } == {
                platform_node_id,
                concourse_id,
            }:
                return concourse

    return concourses[0]


# ==============================================================================
# 14. movement → 시작/도착 노드 결정
# ==============================================================================

def resolve_movement_nodes(
    movement: dict[str, Any],
) -> dict[str, Any]:
    """
    movement에 따라 역 내부 시작/종료 노드를 결정합니다.
    """

    movement_type = str(
        movement.get(
            "movement_type",
            "",
        )
    ).strip().upper()

    station_name = movement.get(
        "station_name"
    )

    if not station_name:
        return {
            "status": "ERROR",
            "message": (
                "station_name이 없습니다."
            ),
        }

    station_name = str(
        station_name
    ).strip()

    # ==========================================================================
    # BOARDING
    # ==========================================================================

    if movement_type == "BOARDING":

        line_name = movement.get(
            "line_name"
        )

        direction_station = (
            movement.get(
                "departure_direction_station"
            )
        )

        if not line_name:
            return {
                "status": "ERROR",
                "station_name": station_name,
                "movement_type": movement_type,
                "message": (
                    "탑승 노선 정보가 없습니다."
                ),
            }

        platform = (
            find_platform_node(
                station_name=station_name,
                line_name=str(
                    line_name
                ),
                direction_station=(
                    str(
                        direction_station
                    )
                    if direction_station
                    else None
                ),
            )
        )

        if not platform:
            return {
                "status": (
                    "PLATFORM_NOT_FOUND"
                ),
                "station_name": station_name,
                "movement_type": movement_type,
                "line_name": line_name,
                "direction_station": (
                    direction_station
                ),
                "message": (
                    "탑승 방향에 맞는 "
                    "승강장을 찾지 못했습니다."
                ),
            }

        concourse = (
            find_connected_concourse(
                station_name=station_name,
                platform_node_id=str(
                    platform[
                        "id"
                    ]
                ),
            )
        )

        if not concourse:
            return {
                "status": (
                    "CONCOURSE_NOT_FOUND"
                ),
                "station_name": station_name,
                "movement_type": movement_type,
                "message": (
                    "탑승 승강장과 연결된 "
                    "대합실을 찾지 못했습니다."
                ),
            }

        return {
            "status": "SUCCESS",
            "station_name": station_name,
            "movement_type": movement_type,
            "direction_station": (
                direction_station
            ),
            "direction_source": (
                movement.get(
                    "direction_source"
                )
            ),
            "start_node": concourse,
            "end_node": platform,
        }

    # ==========================================================================
    # ALIGHTING
    # ==========================================================================

    if movement_type == "ALIGHTING":

        line_name = movement.get(
            "line_name"
        )

        direction_station = (
            movement.get(
                "arrival_direction_station"
            )
        )

        if not line_name:
            return {
                "status": "ERROR",
                "station_name": station_name,
                "movement_type": movement_type,
                "message": (
                    "하차 노선 정보가 없습니다."
                ),
            }

        platform = (
            find_platform_node(
                station_name=station_name,
                line_name=str(
                    line_name
                ),
                direction_station=(
                    str(
                        direction_station
                    )
                    if direction_station
                    else None
                ),
            )
        )

        if not platform:
            return {
                "status": (
                    "PLATFORM_NOT_FOUND"
                ),
                "station_name": station_name,
                "movement_type": movement_type,
                "line_name": line_name,
                "direction_station": (
                    direction_station
                ),
                "message": (
                    "하차 방향에 맞는 "
                    "승강장을 찾지 못했습니다."
                ),
            }

        concourse = (
            find_connected_concourse(
                station_name=station_name,
                platform_node_id=str(
                    platform[
                        "id"
                    ]
                ),
            )
        )

        if not concourse:
            return {
                "status": (
                    "CONCOURSE_NOT_FOUND"
                ),
                "station_name": station_name,
                "movement_type": movement_type,
                "message": (
                    "하차 승강장과 연결된 "
                    "대합실을 찾지 못했습니다."
                ),
            }

        return {
            "status": "SUCCESS",
            "station_name": station_name,
            "movement_type": movement_type,
            "direction_station": (
                direction_station
            ),
            "direction_source": (
                movement.get(
                    "arrival_direction_source"
                )
            ),
            "start_node": platform,
            "end_node": concourse,
        }

    # ==========================================================================
    # TRANSFER
    # ==========================================================================

    if movement_type == "TRANSFER":

        from_line = movement.get(
            "from_line"
        )

        to_line = movement.get(
            "to_line"
        )

        arrival_direction_station = (
            movement.get(
                "arrival_direction_station"
            )
        )

        departure_direction_station = (
            movement.get(
                "departure_direction_station"
            )
        )

        if (
            not from_line
            or not to_line
        ):
            return {
                "status": "ERROR",
                "station_name": station_name,
                "movement_type": movement_type,
                "message": (
                    "환승 노선 정보가 부족합니다."
                ),
            }

        from_platform = (
            find_platform_node(
                station_name=station_name,
                line_name=str(
                    from_line
                ),
                direction_station=(
                    str(
                        arrival_direction_station
                    )
                    if arrival_direction_station
                    else None
                ),
            )
        )

        to_platform = (
            find_platform_node(
                station_name=station_name,
                line_name=str(
                    to_line
                ),
                direction_station=(
                    str(
                        departure_direction_station
                    )
                    if departure_direction_station
                    else None
                ),
            )
        )

        if not from_platform:
            return {
                "status": (
                    "PLATFORM_NOT_FOUND"
                ),
                "station_name": station_name,
                "movement_type": movement_type,
                "line_name": from_line,
                "direction_station": (
                    arrival_direction_station
                ),
                "message": (
                    "환승 시작 승강장을 "
                    "찾지 못했습니다."
                ),
            }

        if not to_platform:
            return {
                "status": (
                    "PLATFORM_NOT_FOUND"
                ),
                "station_name": station_name,
                "movement_type": movement_type,
                "line_name": to_line,
                "direction_station": (
                    departure_direction_station
                ),
                "message": (
                    "환승 후 탑승 승강장을 "
                    "찾지 못했습니다."
                ),
            }

        return {
            "status": "SUCCESS",
            "station_name": station_name,
            "movement_type": movement_type,

            "arrival_direction_station": (
                arrival_direction_station
            ),

            "departure_direction_station": (
                departure_direction_station
            ),

            "arrival_direction_source": (
                movement.get(
                    "arrival_direction_source"
                )
            ),

            "departure_direction_source": (
                movement.get(
                    "departure_direction_source"
                )
            ),

            "start_node": (
                from_platform
            ),

            "end_node": (
                to_platform
            ),
        }

    return {
        "status": (
            "UNSUPPORTED_MOVEMENT"
        ),
        "station_name": station_name,
        "movement_type": movement_type,
    }


# ==============================================================================
# 15. 이동 조건별 edge 사용 가능 여부
# ==============================================================================

def is_edge_allowed_for_constraints(
    edge: dict[str, Any],
    mobility_constraints: dict[str, Any] | None,
) -> bool:
    """
    사용자가 선택한 이동 조건에 따라 edge 사용 가능 여부를 판단합니다.

    - avoid_stairs=True: 계단 edge 제외
    - avoid_escalator=True: 에스컬레이터/무빙워크 edge 제외
    - require_elevator=True: 층간 이동은 엘리베이터만 허용
    - avoid_steep_slope=True: 명시적으로 급경사인 edge 제외

    같은 층 WALKING edge는 require_elevator=True여도 허용합니다.
    """
    constraints = normalize_mobility_constraints(mobility_constraints)
    transport_type = str(edge.get("transport_type", "")).strip().upper()

    if constraints["avoid_stairs"] and transport_type in {"STAIR", "STAIRS"}:
        return False

    if constraints["avoid_escalator"] and transport_type in {
        "ESCALATOR", "MOVING_WALK", "MOVINGWALK"
    }:
        return False

    if (
        constraints["require_elevator"]
        and _edge_changes_floor(edge)
        and transport_type != "ELEVATOR"
    ):
        return False

    if constraints["avoid_steep_slope"] and edge.get("has_steep_slope") is True:
        return False

    return True

# ==============================================================================
# 16. BFS 인접 목록
# ==============================================================================

def build_adjacency_list(
    station_name: str,
    blocked_edge_ids: set[str] | None = None,
    mobility_constraints: dict[str, Any] | None = None,
) -> dict[str, list[dict[str, Any]]]:
    """이동 조건과 고장 시설 차단 목록을 반영한 BFS 인접 목록을 만듭니다."""
    edges = get_station_edges(station_name)
    blocked_edge_ids = blocked_edge_ids or set()
    adjacency: dict[str, list[dict[str, Any]]] = {}

    for edge in edges:
        edge_id = str(edge.get("id", "")).strip()
        if edge_id and edge_id in blocked_edge_ids:
            continue
        if not is_edge_allowed_for_constraints(edge, mobility_constraints):
            continue

        from_node = edge.get("from_node")
        to_node = edge.get("to_node")
        if not from_node or not to_node:
            continue
        from_node = str(from_node)
        to_node = str(to_node)

        adjacency.setdefault(from_node, []).append({
            "next_node": to_node,
            "edge": edge,
            "traversal_from_node": from_node,
            "traversal_to_node": to_node,
            "reverse_traversal": False,
        })

        if edge.get("is_bidirectional") is True:
            adjacency.setdefault(to_node, []).append({
                "next_node": from_node,
                "edge": edge,
                "traversal_from_node": to_node,
                "traversal_to_node": from_node,
                "reverse_traversal": True,
            })

    return adjacency

# ==============================================================================
# 17. BFS 최단 경로
# ==============================================================================

def find_shortest_internal_path(
    station_name: str,
    start_node_id: str,
    end_node_id: str,
    blocked_edge_ids: set[str] | None = None,
    mobility_constraints: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """BFS로 이동 조건과 고장 시설 차단을 반영한 역 내부 최단 경로를 찾습니다."""
    constraints = normalize_mobility_constraints(mobility_constraints)

    if start_node_id == end_node_id:
        return {
            "status": "SUCCESS",
            "station_name": station_name,
            "mobility_constraints": constraints,
            "node_path": [start_node_id],
            "edge_path": [],
            "traversal_path": [],
            "edge_count": 0,
        }

    adjacency = build_adjacency_list(
        station_name=station_name,
        blocked_edge_ids=blocked_edge_ids,
        mobility_constraints=constraints,
    )

    queue = deque([(start_node_id, [start_node_id], [], [])])
    visited = {start_node_id}

    while queue:
        current_node, node_path, edge_path, traversal_path = queue.popleft()
        for connection in adjacency.get(current_node, []):
            next_node = connection["next_node"]
            if next_node in visited:
                continue
            edge = connection["edge"]
            next_node_path = node_path + [next_node]
            next_edge_path = edge_path + [edge]
            next_traversal_path = traversal_path + [{
                "edge": edge,
                "traversal_from_node": connection["traversal_from_node"],
                "traversal_to_node": connection["traversal_to_node"],
                "reverse_traversal": connection["reverse_traversal"],
            }]

            if next_node == end_node_id:
                return {
                    "status": "SUCCESS",
                    "station_name": station_name,
                    "mobility_constraints": constraints,
                    "node_path": next_node_path,
                    "edge_path": next_edge_path,
                    "traversal_path": next_traversal_path,
                    "edge_count": len(next_edge_path),
                }

            visited.add(next_node)
            queue.append((next_node, next_node_path, next_edge_path, next_traversal_path))

    return {
        "status": "PATH_NOT_FOUND",
        "station_name": station_name,
        "mobility_constraints": constraints,
        "start_node_id": start_node_id,
        "end_node_id": end_node_id,
        "node_path": [],
        "edge_path": [],
        "traversal_path": [],
        "edge_count": 0,
    }

# ==============================================================================
# 18. 기본 movement 내부 경로
# ==============================================================================

def find_movement_internal_path(
    movement: dict[str, Any],
    mobility_constraints: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """실시간 상태 전의 기본 역 내부 경로를 이동 조건을 반영해 계산합니다."""
    constraints = normalize_mobility_constraints(mobility_constraints)
    resolved = resolve_movement_nodes(movement)

    if resolved.get("status") != "SUCCESS":
        return {
            "status": resolved.get("status", "ERROR"),
            "movement": movement,
            "mobility_constraints": constraints,
            "node_resolution": resolved,
            "node_path": [],
            "edge_path": [],
            "traversal_path": [],
            "edge_count": 0,
        }

    station_name = str(resolved["station_name"])
    start_node = resolved["start_node"]
    end_node = resolved["end_node"]

    result = find_shortest_internal_path(
        station_name=station_name,
        start_node_id=str(start_node["id"]),
        end_node_id=str(end_node["id"]),
        mobility_constraints=constraints,
    )
    result["movement"] = movement
    result["node_resolution"] = resolved
    result["start_node"] = start_node
    result["end_node"] = end_node
    return result

# ==============================================================================
# 19. 실제 이용 EV / ES 추출
# ==============================================================================

def extract_required_facilities(
    internal_path: dict[str, Any],
) -> list[dict[str, Any]]:
    """
    BFS 경로에서 실제 이용하는
    ELEVATOR / ESCALATOR를 추출합니다.
    """

    traversal_path = (
        internal_path.get(
            "traversal_path",
            [],
        )
    )

    if not isinstance(
        traversal_path,
        list,
    ):
        return []

    station_name = str(
        internal_path.get(
            "station_name",
            "",
        )
    )

    nodes = get_station_nodes(
        station_name
    )

    node_map = {
        str(
            node.get(
                "id"
            )
        ): node
        for node in nodes
        if node.get(
            "id"
        )
    }

    required_facilities: list[
        dict[str, Any]
    ] = []

    for traversal in traversal_path:

        if not isinstance(
            traversal,
            dict,
        ):
            continue

        edge = traversal.get(
            "edge"
        )

        if not isinstance(
            edge,
            dict,
        ):
            continue

        transport_type = str(
            edge.get(
                "transport_type",
                "",
            )
        ).upper()

        if transport_type not in {
            "ELEVATOR",
            "ESCALATOR",
        }:
            continue

        actual_from_node_id = str(
            traversal.get(
                "traversal_from_node",
                "",
            )
        )

        actual_to_node_id = str(
            traversal.get(
                "traversal_to_node",
                "",
            )
        )

        actual_from_node = (
            node_map.get(
                actual_from_node_id,
                {},
            )
        )

        actual_to_node = (
            node_map.get(
                actual_to_node_id,
                {},
            )
        )

        required_facilities.append(
            {
                "edge_id": (
                    edge.get(
                        "id"
                    )
                ),

                "facility_type": (
                    transport_type
                ),

                "station_name": (
                    edge.get(
                        "station_name"
                    )
                ),

                "line_name": (
                    edge.get(
                        "line_name"
                    )
                ),

                "actual_from_node": (
                    actual_from_node_id
                ),

                "actual_to_node": (
                    actual_to_node_id
                ),

                "actual_from_floor": (
                    actual_from_node.get(
                        "floor"
                    )
                ),

                "actual_to_floor": (
                    actual_to_node.get(
                        "floor"
                    )
                ),

                "reverse_traversal": (
                    traversal.get(
                        "reverse_traversal",
                        False,
                    )
                ),

                "edge_from_node": (
                    edge.get(
                        "from_node"
                    )
                ),

                "edge_to_node": (
                    edge.get(
                        "to_node"
                    )
                ),

                "edge_from_floor": (
                    edge.get(
                        "from_floor"
                    )
                ),

                "edge_to_floor": (
                    edge.get(
                        "to_floor"
                    )
                ),

                "exit_no": (
                    edge.get(
                        "exit_no"
                    )
                ),

                "detail_location": (
                    edge.get(
                        "detail_location"
                    )
                ),

                "direction": (
                    edge.get(
                        "direction"
                    )
                ),

                "direction_name": (
                    edge.get(
                        "direction_name"
                    )
                ),

                "wheelchair_accessible": (
                    edge.get(
                        "wheelchair_accessible"
                    )
                ),

                "is_bidirectional": (
                    edge.get(
                        "is_bidirectional"
                    )
                ),

                "operator_code": (
                    edge.get(
                        "operator_code"
                    )
                ),

                "line_code": (
                    edge.get(
                        "line_code"
                    )
                ),

                "kric_station_code": (
                    edge.get(
                        "kric_station_code"
                    )
                ),
            }
        )

    return required_facilities


# ==============================================================================
# 20. 실시간 상태 + 사용자 유형 기반 우회 BFS
# ==============================================================================

def find_realtime_safe_internal_path(
    movement: dict[str, Any],
    mobility_constraints: dict[str, Any] | None = None,
    max_retry: int = 10,
) -> dict[str, Any]:
    """
    이동 조건 + 실시간 EV/ES 상태를 반영해 현재 이용 가능한 내부 동선을 찾습니다.
    고장 시설은 해당 edge만 차단하고 BFS를 다시 수행합니다.
    """
    constraints = normalize_mobility_constraints(mobility_constraints)
    resolved = resolve_movement_nodes(movement)

    if resolved.get("status") != "SUCCESS":
        return {
            "status": resolved.get("status", "ERROR"),
            "movement": movement,
            "mobility_constraints": constraints,
            "node_resolution": resolved,
            "start_node": None,
            "end_node": None,
            "node_path": [],
            "edge_path": [],
            "traversal_path": [],
            "edge_count": 0,
            "required_facilities": [],
            "required_facility_count": 0,
            "blocked_edge_ids": [],
            "attempt_count": 0,
        }

    station_name = str(resolved["station_name"])
    start_node = resolved["start_node"]
    end_node = resolved["end_node"]
    blocked_edge_ids: set[str] = set()

    for attempt in range(1, max_retry + 1):
        internal_path = find_shortest_internal_path(
            station_name=station_name,
            start_node_id=str(start_node["id"]),
            end_node_id=str(end_node["id"]),
            blocked_edge_ids=blocked_edge_ids,
            mobility_constraints=constraints,
        )

        if internal_path.get("status") != "SUCCESS":
            return {
                "status": "REALTIME_PATH_NOT_FOUND",
                "movement": movement,
                "mobility_constraints": constraints,
                "node_resolution": resolved,
                "start_node": start_node,
                "end_node": end_node,
                "node_path": [],
                "edge_path": [],
                "traversal_path": [],
                "edge_count": 0,
                "required_facilities": [],
                "required_facility_count": 0,
                "blocked_edge_ids": sorted(blocked_edge_ids),
                "attempt_count": attempt,
            }

        required_facilities = extract_required_facilities(internal_path)
        facilities_with_status = attach_realtime_status_to_facilities(required_facilities)

        unavailable_edge_ids: set[str] = set()
        for facility in facilities_with_status:
            realtime = facility.get("realtime", {})
            if not isinstance(realtime, dict):
                continue
            realtime_status = str(realtime.get("realtime_status", "UNKNOWN")).upper()
            edge_id = facility.get("edge_id")
            if realtime_status == "UNAVAILABLE" and edge_id:
                unavailable_edge_ids.add(str(edge_id))

        if not unavailable_edge_ids:
            unknown_count = sum(
                1
                for facility in facilities_with_status
                if str(
                    facility.get("realtime", {}).get("realtime_status", "UNKNOWN")
                ).upper() == "UNKNOWN"
            )
            return {
                "status": "SUCCESS",
                "movement": movement,
                "mobility_constraints": constraints,
                "node_resolution": resolved,
                "start_node": start_node,
                "end_node": end_node,
                "node_path": internal_path.get("node_path", []),
                "edge_path": internal_path.get("edge_path", []),
                "traversal_path": internal_path.get("traversal_path", []),
                "edge_count": internal_path.get("edge_count", 0),
                "required_facilities": facilities_with_status,
                "required_facility_count": len(facilities_with_status),
                "blocked_edge_ids": sorted(blocked_edge_ids),
                "attempt_count": attempt,
                "has_unknown_facility_status": unknown_count > 0,
                "unknown_facility_count": unknown_count,
            }

        newly_blocked = unavailable_edge_ids - blocked_edge_ids
        if not newly_blocked:
            return {
                "status": "REALTIME_PATH_NOT_FOUND",
                "movement": movement,
                "mobility_constraints": constraints,
                "node_resolution": resolved,
                "start_node": start_node,
                "end_node": end_node,
                "node_path": internal_path.get("node_path", []),
                "edge_path": internal_path.get("edge_path", []),
                "traversal_path": internal_path.get("traversal_path", []),
                "edge_count": internal_path.get("edge_count", 0),
                "required_facilities": facilities_with_status,
                "required_facility_count": len(facilities_with_status),
                "blocked_edge_ids": sorted(blocked_edge_ids),
                "attempt_count": attempt,
            }

        blocked_edge_ids.update(newly_blocked)

    return {
        "status": "MAX_RETRY_EXCEEDED",
        "movement": movement,
        "mobility_constraints": constraints,
        "node_resolution": resolved,
        "start_node": start_node,
        "end_node": end_node,
        "node_path": [],
        "edge_path": [],
        "traversal_path": [],
        "edge_count": 0,
        "required_facilities": [],
        "required_facility_count": 0,
        "blocked_edge_ids": sorted(blocked_edge_ids),
        "attempt_count": max_retry,
    }

# ==============================================================================
# 21. 기본 movement 분석
# ==============================================================================

def analyze_station_movement(
    movement: dict[str, Any],
    mobility_constraints: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """실시간 상태 전의 기본 역 내부 동선을 이동 조건을 반영해 분석합니다."""
    constraints = normalize_mobility_constraints(mobility_constraints)
    internal_path = find_movement_internal_path(
        movement=movement,
        mobility_constraints=constraints,
    )
    required_facilities = extract_required_facilities(internal_path)
    return {
        "status": internal_path.get("status"),
        "movement": movement,
        "mobility_constraints": constraints,
        "node_resolution": internal_path.get("node_resolution"),
        "start_node": internal_path.get("start_node"),
        "end_node": internal_path.get("end_node"),
        "node_path": internal_path.get("node_path", []),
        "edge_count": internal_path.get("edge_count", 0),
        "required_facility_count": len(required_facilities),
        "required_facilities": required_facilities,
    }

