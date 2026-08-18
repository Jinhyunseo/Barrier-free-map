from __future__ import annotations

from typing import Iterable, Optional

import networkx as nx


class PathNotFoundError(Exception):
    """
    이용 가능한 역사 내부 경로를 찾지 못했을 때 사용한다.
    """
    pass


def apply_confirmed_edges_only(
    graph: nx.DiGraph,
) -> nx.DiGraph:
    """
    공식적으로 확인된(CONFIRMED) edge만 남긴
    새로운 그래프를 반환한다.

    INFERRED / UNKNOWN / confidence 누락 edge는
    실제 경로 탐색에 사용하지 않는다.

    원본 graph는 수정하지 않는다.
    """

    safe_graph = graph.copy()

    edges_to_remove = []

    for source, target, data in safe_graph.edges(data=True):
        if data.get("confidence") != "CONFIRMED":
            edges_to_remove.append((source, target))

    safe_graph.remove_edges_from(edges_to_remove)

    return safe_graph


def apply_blocked_facilities(
    graph: nx.DiGraph,
    blocked_facility_ids: Optional[Iterable[str]] = None,
) -> nx.DiGraph:
    """
    고장/점검 중인 엘리베이터 facility_id를 받아
    해당 ELEVATOR edge를 제거한 새로운 그래프를 반환한다.

    원본 graph는 수정하지 않는다.

    예:
        blocked_facility_ids = ["2050606"]

    → facility_id가 2050606인 ELEVATOR edge를
      정방향/역방향 모두 제거한다.
    """

    safe_graph = graph.copy()

    blocked_ids = {
        str(facility_id)
        for facility_id in (blocked_facility_ids or [])
        if facility_id is not None
    }

    if not blocked_ids:
        return safe_graph

    edges_to_remove = []

    for source, target, data in safe_graph.edges(data=True):
        if data.get("mode") != "ELEVATOR":
            continue

        facility_id = data.get("facility_id")

        if facility_id is not None and str(facility_id) in blocked_ids:
            edges_to_remove.append((source, target))

    safe_graph.remove_edges_from(edges_to_remove)

    return safe_graph


def build_safe_graph(
    graph: nx.DiGraph,
    blocked_facility_ids: Optional[Iterable[str]] = None,
) -> nx.DiGraph:
    """
    실제 경로 탐색에 사용할 안전한 그래프를 생성한다.

    처리 순서:
        1. CONFIRMED edge만 유지
        2. 고장/점검 중인 ELEVATOR edge 제거

    원본 graph는 수정하지 않는다.
    """

    safe_graph = apply_confirmed_edges_only(graph)

    safe_graph = apply_blocked_facilities(
        safe_graph,
        blocked_facility_ids,
    )

    return safe_graph


def validate_path_nodes(
    graph: nx.DiGraph,
    start_node: str,
    end_node: str,
) -> None:
    """
    출발/도착 node가 그래프에 실제로 존재하는지 확인한다.
    """

    if start_node not in graph:
        raise ValueError(
            f"출발 node가 그래프에 존재하지 않습니다: {start_node}"
        )

    if end_node not in graph:
        raise ValueError(
            f"도착 node가 그래프에 존재하지 않습니다: {end_node}"
        )


def find_internal_path(
    graph: nx.DiGraph,
    start_node: str,
    end_node: str,
    blocked_facility_ids: Optional[Iterable[str]] = None,
) -> list[str]:
    """
    역사 내부 경로를 탐색한다.

    현재 MVP에서는 시간/거리 가중치를 사용하지 않으므로
    NetworkX shortest_path의 기본 hop 수 기준으로 탐색한다.

    처리 순서:
        1. start/end node 존재 여부 확인
        2. CONFIRMED edge만 유지
        3. 고장난 EV edge 제거
        4. 이용 가능한 경로 탐색
        5. 없으면 PathNotFoundError 발생
    """

    validate_path_nodes(
        graph,
        start_node,
        end_node,
    )

    safe_graph = build_safe_graph(
        graph,
        blocked_facility_ids,
    )

    try:
        return nx.shortest_path(
            safe_graph,
            source=start_node,
            target=end_node,
        )

    except nx.NetworkXNoPath as exc:
        raise PathNotFoundError(
            f"이용 가능한 역사 내부 경로가 없습니다: "
            f"{start_node} -> {end_node}"
        ) from exc


def get_path_edges(
    graph: nx.DiGraph,
    node_path: list[str],
) -> list[dict]:
    """
    node 경로를 실제 edge 정보 배열로 변환한다.
    """

    if len(node_path) < 2:
        return []

    result = []

    for index in range(len(node_path) - 1):
        source = node_path[index]
        target = node_path[index + 1]

        if not graph.has_edge(source, target):
            raise ValueError(
                f"node_path에 존재하지만 실제 graph edge가 없습니다: "
                f"{source} -> {target}"
            )

        edge_data = graph.get_edge_data(
            source,
            target,
        ).copy()

        result.append(
            {
                "source": source,
                "target": target,
                **edge_data,
            }
        )

    return result


def get_path_steps(
    graph: nx.DiGraph,
    node_path: list[str],
) -> list[dict]:
    """
    Flutter/API 응답에서 사용하기 좋은 단계별 안내 정보를 만든다.

    각 edge의 instruction을 그대로 사용한다.
    """

    edge_path = get_path_edges(
        graph,
        node_path,
    )

    steps = []

    for index, edge in enumerate(edge_path, start=1):
        target_node = graph.nodes[edge["target"]]

        steps.append(
            {
                "step": index,
                "source": edge["source"],
                "target": edge["target"],
                "target_name": target_node.get("name"),
                "floor": target_node.get("floor"),
                "mode": edge.get("mode"),
                "facility_id": edge.get("facility_id"),
                "instruction": edge.get("instruction"),
            }
        )

    return steps


def find_internal_route(
    graph: nx.DiGraph,
    start_node: str,
    end_node: str,
    blocked_facility_ids: Optional[Iterable[str]] = None,
) -> dict:
    """
    서비스에서 가장 편하게 사용할 메인 함수.

    성공 시:
    {
        "status": "SUCCESS",
        "start_node": ...,
        "end_node": ...,
        "node_path": [...],
        "edge_path": [...],
        "steps": [...]
    }

    경로가 없으면:
    {
        "status": "PATH_NOT_FOUND",
        ...
    }
    """

    try:
        node_path = find_internal_path(
            graph=graph,
            start_node=start_node,
            end_node=end_node,
            blocked_facility_ids=blocked_facility_ids,
        )

    except PathNotFoundError:
        return {
            "status": "PATH_NOT_FOUND",
            "start_node": start_node,
            "end_node": end_node,
            "node_path": [],
            "edge_path": [],
            "steps": [],
        }

    # find_internal_path와 동일한 안전 조건이 적용된
    # 그래프에서 edge/step 정보를 생성한다.
    safe_graph = build_safe_graph(
        graph,
        blocked_facility_ids,
    )

    edge_path = get_path_edges(
        safe_graph,
        node_path,
    )

    steps = get_path_steps(
        safe_graph,
        node_path,
    )

    return {
        "status": "SUCCESS",
        "start_node": start_node,
        "end_node": end_node,
        "node_path": node_path,
        "edge_path": edge_path,
        "steps": steps,
    }