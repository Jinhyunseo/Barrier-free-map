import networkx as nx
import pytest

from app.services.graph_loader import load_station_graph


@pytest.fixture(scope="module")
def seohyeon_graph():
    """
    서현역 graph.json을 NetworkX 그래프로 로드한다.
    """
    return load_station_graph("seohyeon")


# ============================================================
# 정방향 공식 경로
# ============================================================

FORWARD_ROUTES = [
    (
        "EXIT1_TO_IMAE",
        "SHN_EXIT_1",
        "SHN_PLATFORM_IMAE",
        [
            "SHN_EXIT_1",
            "SHN_EXIT1_EV_G1",
            "SHN_EXIT1_EV_B1",
            "SHN_IMAE_EV_B1",
            "SHN_IMAE_EV_B2",
            "SHN_PLATFORM_IMAE",
        ],
    ),
    (
        "EXIT1_TO_SUNAE",
        "SHN_EXIT_1",
        "SHN_PLATFORM_SUNAE",
        [
            "SHN_EXIT_1",
            "SHN_EXIT1_EV_G1",
            "SHN_EXIT1_EV_B1",
            "SHN_SUNAE_EV_B1",
            "SHN_SUNAE_EV_B2",
            "SHN_PLATFORM_SUNAE",
        ],
    ),
]


# ============================================================
# 역방향
# ============================================================

REVERSE_ROUTES = [
    (
        "IMAE_TO_EXIT1",
        "SHN_PLATFORM_IMAE",
        "SHN_EXIT_1",
        [
            "SHN_PLATFORM_IMAE",
            "SHN_IMAE_EV_B2",
            "SHN_IMAE_EV_B1",
            "SHN_EXIT1_EV_B1",
            "SHN_EXIT1_EV_G1",
            "SHN_EXIT_1",
        ],
    ),
    (
        "SUNAE_TO_EXIT1",
        "SHN_PLATFORM_SUNAE",
        "SHN_EXIT_1",
        [
            "SHN_PLATFORM_SUNAE",
            "SHN_SUNAE_EV_B2",
            "SHN_SUNAE_EV_B1",
            "SHN_EXIT1_EV_B1",
            "SHN_EXIT1_EV_G1",
            "SHN_EXIT_1",
        ],
    ),
]


@pytest.mark.parametrize(
    "route_name,start,end,expected_path",
    FORWARD_ROUTES,
    ids=[route[0] for route in FORWARD_ROUTES],
)
def test_seohyeon_forward_routes(
    seohyeon_graph,
    route_name,
    start,
    end,
    expected_path,
):
    assert nx.has_path(
        seohyeon_graph,
        start,
        end,
    ), f"{route_name}: 경로가 존재하지 않습니다."

    actual_path = nx.shortest_path(
        seohyeon_graph,
        start,
        end,
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
def test_seohyeon_reverse_routes(
    seohyeon_graph,
    route_name,
    start,
    end,
    expected_path,
):
    assert nx.has_path(
        seohyeon_graph,
        start,
        end,
    ), f"{route_name}: 역방향 경로가 존재하지 않습니다."

    actual_path = nx.shortest_path(
        seohyeon_graph,
        start,
        end,
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
    "SHN_EV_EXIT1": "2115488",
    "SHN_EV_IMAE": "2050935",
    "SHN_EV_SUNAE": "2050936",
}


def test_seohyeon_elevator_facility_ids(seohyeon_graph):
    found = {}

    for _, _, data in seohyeon_graph.edges(data=True):
        if data.get("mode") != "ELEVATOR":
            continue

        edge_id = data.get("id")
        facility_id = data.get("facility_id")

        found[edge_id] = facility_id

    assert found == EXPECTED_ELEVATORS


# ============================================================
# 기본 그래프 구조 검사
# ============================================================

def test_seohyeon_graph_structure(seohyeon_graph):
    # node 9개
    assert seohyeon_graph.number_of_nodes() == 9

    # 원본 edge 8개가 graph_loader에서 양방향 생성
    assert seohyeon_graph.number_of_edges() == 16

    elevator_edges = [
        (u, v)
        for u, v, data in seohyeon_graph.edges(data=True)
        if data.get("mode") == "ELEVATOR"
    ]

    walk_edges = [
        (u, v)
        for u, v, data in seohyeon_graph.edges(data=True)
        if data.get("mode") == "WALK"
    ]

    # EV 원본 3개 → 양방향 6개
    assert len(elevator_edges) == 6

    # WALK 원본 5개 → 양방향 10개
    assert len(walk_edges) == 10