import json
from pathlib import Path

import networkx as nx
from pydantic import ValidationError

from app.schemas.station_graph import StationGraph


# station json 파일들이 저장된 위치
STATION_DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "stations"


def get_station_json_path(station_name: str) -> Path:
    """
    역 이름을 받아 해당 역의 JSON 파일 경로를 반환한다.

    예:
        "yatap" -> app/data/stations/yatap.json
    """

    station_key = station_name.strip().lower()

    if not station_key:
        raise ValueError("station_name이 비어 있습니다.")

    json_path = STATION_DATA_DIR / f"{station_key}.json"

    if not json_path.exists():
        raise FileNotFoundError(
            f"역 그래프 JSON 파일을 찾을 수 없습니다: {json_path}"
        )

    return json_path


def load_station_data(station_name: str) -> StationGraph:
    """
    역 JSON 파일을 읽고 StationGraph(Pydantic) 모델로 검증한다.
    """

    json_path = get_station_json_path(station_name)

    try:
        with json_path.open("r", encoding="utf-8") as file:
            raw_data = json.load(file)

    except json.JSONDecodeError as exc:
        raise ValueError(
            f"{json_path.name}의 JSON 형식이 올바르지 않습니다: {exc}"
        ) from exc

    try:
        station_graph = StationGraph.model_validate(raw_data)

    except ValidationError as exc:
        raise ValueError(
            f"{json_path.name}이 station_graph.py 스키마와 일치하지 않습니다.\n"
            f"{exc}"
        ) from exc

    return station_graph


def validate_graph_integrity(station_graph: StationGraph) -> None:
    """
    그래프의 기본 참조 무결성을 검사한다.

    검사 항목:
    1. node id 중복
    2. edge id 중복
    3. edge source가 실제 node인지
    4. edge target이 실제 node인지
    """

    node_ids = [node.id for node in station_graph.nodes]

    # -------------------------
    # Node ID 중복 검사
    # -------------------------

    if len(node_ids) != len(set(node_ids)):
        duplicates = sorted(
            {
                node_id
                for node_id in node_ids
                if node_ids.count(node_id) > 1
            }
        )

        raise ValueError(
            f"중복된 node id가 존재합니다: {duplicates}"
        )

    node_id_set = set(node_ids)

    # -------------------------
    # Edge ID 중복 검사
    # -------------------------

    edge_ids = [edge.id for edge in station_graph.edges]

    if len(edge_ids) != len(set(edge_ids)):
        duplicates = sorted(
            {
                edge_id
                for edge_id in edge_ids
                if edge_ids.count(edge_id) > 1
            }
        )

        raise ValueError(
            f"중복된 edge id가 존재합니다: {duplicates}"
        )

    # -------------------------
    # Edge source / target 검사
    # -------------------------

    for edge in station_graph.edges:

        if edge.source not in node_id_set:
            raise ValueError(
                f"Edge '{edge.id}'의 source node가 존재하지 않습니다: "
                f"{edge.source}"
            )

        if edge.target not in node_id_set:
            raise ValueError(
                f"Edge '{edge.id}'의 target node가 존재하지 않습니다: "
                f"{edge.target}"
            )


def build_networkx_graph(
    station_graph: StationGraph,
) -> nx.DiGraph:
    """
    StationGraph 데이터를 NetworkX DiGraph로 변환한다.

    현재 EV-only MVP에서는:

    - WALK
    - ELEVATOR

    모두 물리적으로 양방향 이동 가능하다고 가정한다.

    따라서 JSON에는 edge를 한 번만 저장하고,
    NetworkX 그래프에는 정방향/역방향 edge를 모두 생성한다.
    """

    validate_graph_integrity(station_graph)

    graph = nx.DiGraph()

    # ==================================================
    # 1. Node 생성
    # ==================================================

    for node in station_graph.nodes:

        node_data = node.model_dump()

        # id는 NetworkX node key로 사용하므로
        # attribute에서는 제거
        node_data.pop("id", None)

        graph.add_node(
            node.id,
            **node_data,
        )

    # ==================================================
    # 2. Edge 생성
    # ==================================================

    for edge in station_graph.edges:

        edge_data = edge.model_dump()

        source = edge_data.pop("source")
        target = edge_data.pop("target")

        # ----------------------------------------------
        # 정방향
        # source -> target
        # ----------------------------------------------

        graph.add_edge(
            source,
            target,
            **edge_data,
        )

        # ----------------------------------------------
        # 역방향
        # target -> source
        #
        # EV-only MVP에서는 WALK / ELEVATOR 모두
        # 양방향으로 사용한다.
        # ----------------------------------------------

        reverse_edge_data = edge_data.copy()

        # 같은 물리 edge라는 것을 알 수 있도록
        # 원본 edge id는 유지한다.
        graph.add_edge(
            target,
            source,
            **reverse_edge_data,
        )

    return graph


def load_station_graph(station_name: str) -> nx.DiGraph:
    """
    외부 서비스에서 사용하는 메인 함수.

    예:
        graph = load_station_graph("yatap")

    처리 과정:

        yatap.json
            ↓
        Pydantic validation
            ↓
        참조 무결성 검사
            ↓
        NetworkX DiGraph 생성
            ↓
        양방향 edge 생성
    """

    station_data = load_station_data(station_name)

    graph = build_networkx_graph(station_data)

    return graph


def get_graph_summary(graph: nx.DiGraph) -> dict:
    """
    테스트/디버깅용 그래프 요약 정보를 반환한다.
    """

    elevator_edges = []
    walk_edges = []

    for source, target, data in graph.edges(data=True):

        mode = data.get("mode")

        edge_info = {
            "source": source,
            "target": target,
            "edge_id": data.get("id"),
            "facility_id": data.get("facility_id"),
        }

        if mode == "ELEVATOR":
            elevator_edges.append(edge_info)

        elif mode == "WALK":
            walk_edges.append(edge_info)

    return {
        "node_count": graph.number_of_nodes(),
        "edge_count": graph.number_of_edges(),
        "elevator_edge_count": len(elevator_edges),
        "walk_edge_count": len(walk_edges),
        "elevator_edges": elevator_edges,
        "walk_edges": walk_edges,
    }