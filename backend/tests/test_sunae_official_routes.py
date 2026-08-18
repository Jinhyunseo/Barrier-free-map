import networkx as nx
import pytest

from app.services.graph_loader import load_station_graph


@pytest.fixture(scope="module")
def sunae_graph():
    """
    수내역 graph.json을 NetworkX 그래프로 로드한다.
    """
    return load_station_graph("sunae")


# ============================================================
# 정방향 공식 경로
# ============================================================

FORWARD_ROUTES = [
    (
        "EXIT1_TO_JEONGJA",
        "SNA_EXIT_1",
        "SNA_PLATFORM_JEONGJA",
        [
            "SNA_EXIT_1",
            "SNA_EXIT1_EV_G1",
            "SNA_EXIT1_EV_B1",
            "SNA_JEONGJA_EV_B1",
            "SNA_JEONGJA_EV_B2",
            "SNA_PLATFORM_JEONGJA",
        ],
    ),
    (
        "EXIT1_TO_SEOHYEON",
        "SNA_EXIT_1",
        "SNA_PLATFORM_SEOHYEON",
        [
            "SNA_EXIT_1",
            "SNA_EXIT1_EV_G1",
            "SNA_EXIT1_EV_B1",
            "SNA_SEOHYEON_EV_B1",
            "SNA_SEOHYEON_EV_B2",
            "SNA_PLATFORM_SEOHYEON",
        ],
    ),
]


# ============================================================
# 역방향 공식 경로
# ============================================================

REVERSE_ROUTES = [
    (
        "JEONGJA_TO_EXIT1",
        "SNA_PLATFORM_JEONGJA",
        "SNA_EXIT_1",
        [
            "SNA_PLATFORM_JEONGJA",
            "SNA_JEONGJA_EV_B2",
            "SNA_JEONGJA_EV_B1",
            "SNA_EXIT1_EV_B1",
            "SNA_EXIT1_EV_G1",
            "SNA_EXIT_1",
        ],
    ),
    (
        "SEOHYEON_TO_EXIT1",
        "SNA_PLATFORM_SEOHYEON",
        "SNA_EXIT_1",
        [
            "SNA_PLATFORM_SEOHYEON",
            "SNA_SEOHYEON_EV_B2",
            "SNA_SEOHYEON_EV_B1",
            "SNA_EXIT1_EV_B1",
            "SNA_EXIT1_EV_G1",
            "SNA_EXIT_1",
        ],
    ),
]


@pytest.mark.parametrize(
    "route_name,start,end,expected_path",
    FORWARD_ROUTES,
    ids=[route[0] for route in FORWARD_ROUTES],
)
def test_sunae_forward_routes(
    sunae_graph,
    route_name,
    start,
    end,
    expected_path,
):
    assert nx.has_path(
        sunae_graph,
        start,
        end,
    ), f"{route_name}: 경로가 존재하지 않습니다."

    actual_path = nx.shortest_path(
        sunae_graph,
        source=start,
        target=end,
    )

    assert actual_path == expected_path, (
        f"{route_name}: 예상 경로와 실제 경로가 다릅니다.\n"
        f"expected={expected_path}\n"
        f"actual={actual_path}"
    )


@pytest.mark.parametrize(
    "route_name,start,end,expected_path",
    REVERSE_ROUTES,
    ids=[route[0] for route in REVERSE_ROUTES],
)
def test_sunae_reverse_routes(
    sunae_graph,
    route_name,
    start,
    end,
    expected_path,
):
    assert nx.has_path(
        sunae_graph,
        start,
        end,
    ), f"{route_name}: 역방향 경로가 존재하지 않습니다."

    actual_path = nx.shortest_path(
        sunae_graph,
        source=start,
        target=end,
    )

    assert actual_path == expected_path, (
        f"{route_name}: 예상 역방향 경로와 실제 경로가 다릅니다.\n"
        f"expected={expected_path}\n"
        f"actual={actual_path}"
    )


# ============================================================
# facility_id 검사
# ============================================================

EXPECTED_ELEVATORS = {
    "SNA_EV_EXIT1": "2126115",
    "SNA_EV_JEONGJA": "2050938",
    "SNA_EV_SEOHYEON": "2050937",
}


def test_sunae_elevator_facility_ids(sunae_graph):
    found = {}

    for _, _, data in sunae_graph.edges(data=True):
        if data.get("mode") != "ELEVATOR":
            continue

        edge_id = data.get("id")
        facility_id = data.get("facility_id")

        found[edge_id] = facility_id

    assert found == EXPECTED_ELEVATORS


# ============================================================
# 기본 그래프 구조 검사
# ============================================================

def test_sunae_graph_structure(sunae_graph):
    # node 9개
    assert sunae_graph.number_of_nodes() == 9

    # 원본 edge 8개 × 양방향
    assert sunae_graph.number_of_edges() == 16

    elevator_edges = [
        (u, v)
        for u, v, data in sunae_graph.edges(data=True)
        if data.get("mode") == "ELEVATOR"
    ]

    walk_edges = [
        (u, v)
        for u, v, data in sunae_graph.edges(data=True)
        if data.get("mode") == "WALK"
    ]

    # ELEVATOR 원본 3개 × 양방향
    assert len(elevator_edges) == 6

    # WALK 원본 5개 × 양방향
    assert len(walk_edges) == 10