import networkx as nx
import pytest

from app.services.graph_loader import load_station_graph


@pytest.fixture(scope="module")
def yatap_graph():
    """
    야탑역 graph.json을 NetworkX 그래프로 로드한다.
    """
    return load_station_graph("yatap")


# ============================================================
# KRIC 공식 이동동선 기반 정방향 4개
# 출입구 -> 승강장
# ============================================================

FORWARD_ROUTES = [
    (
        "EXIT12_TO_MORAN",
        "YTP_EXIT_12",
        "YTP_PLATFORM_MORAN",
        [
            "YTP_EXIT_12",
            "YTP_EXIT_12_EV_G1",
            "YTP_EXIT_12_EV_B1",
            "YTP_MORAN_EV_B1",
            "YTP_MORAN_EV_B2",
            "YTP_PLATFORM_MORAN",
        ],
    ),
    (
        "EXIT12_TO_IMAE",
        "YTP_EXIT_12",
        "YTP_PLATFORM_IMAE",
        [
            "YTP_EXIT_12",
            "YTP_EXIT_12_EV_G1",
            "YTP_EXIT_12_EV_B1",
            "YTP_IMAE_EV_B1",
            "YTP_IMAE_EV_B2",
            "YTP_PLATFORM_IMAE",
        ],
    ),
    (
        "EXIT34_TO_MORAN",
        "YTP_EXIT_34",
        "YTP_PLATFORM_MORAN",
        [
            "YTP_EXIT_34",
            "YTP_EXIT_34_EV_G1",
            "YTP_EXIT_34_EV_B1",
            "YTP_MORAN_EV_B1",
            "YTP_MORAN_EV_B2",
            "YTP_PLATFORM_MORAN",
        ],
    ),
    (
        "EXIT34_TO_IMAE",
        "YTP_EXIT_34",
        "YTP_PLATFORM_IMAE",
        [
            "YTP_EXIT_34",
            "YTP_EXIT_34_EV_G1",
            "YTP_EXIT_34_EV_B1",
            "YTP_IMAE_EV_B1",
            "YTP_IMAE_EV_B2",
            "YTP_PLATFORM_IMAE",
        ],
    ),
]


# ============================================================
# 역방향 4개
# 승강장 -> 출입구
#
# graph_loader가 WALK/ELEVATOR edge를
# 정상적으로 양방향 생성하는지 확인한다.
# ============================================================

REVERSE_ROUTES = [
    (
        "MORAN_TO_EXIT12",
        "YTP_PLATFORM_MORAN",
        "YTP_EXIT_12",
        [
            "YTP_PLATFORM_MORAN",
            "YTP_MORAN_EV_B2",
            "YTP_MORAN_EV_B1",
            "YTP_EXIT_12_EV_B1",
            "YTP_EXIT_12_EV_G1",
            "YTP_EXIT_12",
        ],
    ),
    (
        "IMAE_TO_EXIT12",
        "YTP_PLATFORM_IMAE",
        "YTP_EXIT_12",
        [
            "YTP_PLATFORM_IMAE",
            "YTP_IMAE_EV_B2",
            "YTP_IMAE_EV_B1",
            "YTP_EXIT_12_EV_B1",
            "YTP_EXIT_12_EV_G1",
            "YTP_EXIT_12",
        ],
    ),
    (
        "MORAN_TO_EXIT34",
        "YTP_PLATFORM_MORAN",
        "YTP_EXIT_34",
        [
            "YTP_PLATFORM_MORAN",
            "YTP_MORAN_EV_B2",
            "YTP_MORAN_EV_B1",
            "YTP_EXIT_34_EV_B1",
            "YTP_EXIT_34_EV_G1",
            "YTP_EXIT_34",
        ],
    ),
    (
        "IMAE_TO_EXIT34",
        "YTP_PLATFORM_IMAE",
        "YTP_EXIT_34",
        [
            "YTP_PLATFORM_IMAE",
            "YTP_IMAE_EV_B2",
            "YTP_IMAE_EV_B1",
            "YTP_EXIT_34_EV_B1",
            "YTP_EXIT_34_EV_G1",
            "YTP_EXIT_34",
        ],
    ),
]


# ============================================================
# 정방향 테스트
# ============================================================

@pytest.mark.parametrize(
    "route_name,start,end,expected_path",
    FORWARD_ROUTES,
    ids=[route[0] for route in FORWARD_ROUTES],
)
def test_yatap_forward_routes(
    yatap_graph,
    route_name,
    start,
    end,
    expected_path,
):
    """
    KRIC 공식 이동동선 4개가
    야탑역 그래프에서 정확하게 재현되는지 확인한다.
    """

    assert nx.has_path(
        yatap_graph,
        start,
        end,
    ), f"{route_name}: 경로가 존재하지 않습니다."

    actual_path = nx.shortest_path(
        yatap_graph,
        start,
        end,
    )

    assert actual_path == expected_path, (
        f"{route_name}: 예상 경로와 실제 경로가 다릅니다.\n"
        f"expected={expected_path}\n"
        f"actual={actual_path}"
    )


# ============================================================
# 역방향 테스트
# ============================================================

@pytest.mark.parametrize(
    "route_name,start,end,expected_path",
    REVERSE_ROUTES,
    ids=[route[0] for route in REVERSE_ROUTES],
)
def test_yatap_reverse_routes(
    yatap_graph,
    route_name,
    start,
    end,
    expected_path,
):
    """
    graph_loader의 양방향 edge 생성이 정상적으로 작동하여
    승강장 -> 출입구 경로도 정확히 만들어지는지 확인한다.
    """

    assert nx.has_path(
        yatap_graph,
        start,
        end,
    ), f"{route_name}: 역방향 경로가 존재하지 않습니다."

    actual_path = nx.shortest_path(
        yatap_graph,
        start,
        end,
    )

    assert actual_path == expected_path, (
        f"{route_name}: 예상 역방향 경로와 실제 경로가 다릅니다.\n"
        f"expected={expected_path}\n"
        f"actual={actual_path}"
    )


# ============================================================
# facility_id 테스트
# ============================================================

EXPECTED_ELEVATORS = {
    "YTP_EV_EXIT12": "2050607",
    "YTP_EV_EXIT34": "2050608",
    "YTP_EV_MORAN": "2050606",
    "YTP_EV_IMAE": "2050605",
}


def test_yatap_elevator_facility_ids(yatap_graph):
    """
    실제 야탑역 엘리베이터 facility_id가
    올바른 ELEVATOR edge에 보존되어 있는지 확인한다.
    """

    found = {}

    for _, _, data in yatap_graph.edges(data=True):

        if data.get("mode") != "ELEVATOR":
            continue

        edge_id = data.get("id")
        facility_id = data.get("facility_id")

        found[edge_id] = facility_id

    assert found == EXPECTED_ELEVATORS


# ============================================================
# 그래프 기본 구조 테스트
# ============================================================

def test_yatap_graph_structure(yatap_graph):
    """
    야탑역 EV-only 그래프의 기본 구조가
    의도한 상태로 유지되는지 확인한다.
    """

    assert yatap_graph.number_of_nodes() == 12
    assert yatap_graph.number_of_edges() == 24

    elevator_edges = [
        (u, v)
        for u, v, data in yatap_graph.edges(data=True)
        if data.get("mode") == "ELEVATOR"
    ]

    walk_edges = [
        (u, v)
        for u, v, data in yatap_graph.edges(data=True)
        if data.get("mode") == "WALK"
    ]

    # JSON의 EV 4개가 양방향으로 생성됨
    assert len(elevator_edges) == 8

    # JSON의 WALK 8개가 양방향으로 생성됨
    assert len(walk_edges) == 16