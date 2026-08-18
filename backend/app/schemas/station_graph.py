from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field


# ============================================================
# Node / Edge Type
# ============================================================

# 현재 MVP에서는 역사 내부를
# EXIT / ELEVATOR / PLATFORM만으로 표현한다.
NodeType = Literal[
    "EXIT",
    "ELEVATOR",
    "PLATFORM",
]


# 현재 MVP에서는
# 도보 이동과 엘리베이터 이동만 사용한다.
EdgeMode = Literal[
    "WALK",
    "ELEVATOR",
]


# 개별 edge의 검증 상태
Confidence = Literal[
    "CONFIRMED",
    "INFERRED",
    "UNKNOWN",
]


# ============================================================
# Station Node
# ============================================================

class StationNode(BaseModel):
    """
    역사 내부 그래프의 node.

    예:
    - 출입구
    - 엘리베이터의 층별 승하차 지점
    - 방향별 승강장
    """

    # 그래프에서 사용하는 고유 ID
    id: str

    # 사용자에게 표시할 이름
    name: str

    # 해당 node가 위치한 층
    # 예: G1, B1, B2, B3
    floor: str

    # EXIT / ELEVATOR / PLATFORM
    type: NodeType

    # 추후 Kakao Map 실외 경로와 연결할 때 사용.
    # 현재 좌표를 모르면 None.
    lat: Optional[float] = None
    lng: Optional[float] = None


# ============================================================
# Station Edge
# ============================================================

class StationEdge(BaseModel):
    """
    두 node 사이의 실제 이동 연결.

    현재 MVP에서는:
    - WALK
    - ELEVATOR

    두 종류만 사용한다.
    """

    # edge 고유 ID
    id: str

    # 출발 node ID
    source: str

    # 도착 node ID
    target: str

    # WALK / ELEVATOR
    mode: EdgeMode

    # 실제 KRIC 엘리베이터 시설 ID.
    #
    # ELEVATOR edge:
    #   실제 elevator_no 저장
    #
    # WALK edge:
    #   None
    facility_id: Optional[str] = None

    # Flutter/API에서 사용자에게 보여줄
    # 단계별 이동 안내 문구
    instruction: Optional[str] = None

    # 해당 edge의 검증 상태
    #
    # 실제 routing에서는 CONFIRMED만 사용한다.
    confidence: Confidence = "CONFIRMED"

    # 해당 연결의 데이터 출처
    #
    # 예:
    # KRIC_ACCESSIBLE_ROUTE
    provenance_source: str

    # ========================================================
    # KRIC 공식 이동동선 ID
    # ========================================================
    #
    # 이 edge가 어떤 KRIC 공식 경로에 포함되어 있는지 저장한다.
    #
    # 여러 공식 경로가 같은 물리 구간을 공유할 수 있으므로
    # list 형태로 관리한다.
    #
    # 예:
    #
    # 1·2번 출구 → 모란방면
    # 1·2번 출구 → 이매방면
    #
    # 두 경로가 같은 출구 EV를 사용한다면:
    #
    # route_ids = [
    #     "YTP_ROUTE_EXIT12_MORAN",
    #     "YTP_ROUTE_EXIT12_IMAE",
    # ]
    #
    # path_finder는 이 값을 기준으로
    # 서로 다른 공식 이동동선의 edge가 임의로 조합되는 것을 막는다.
    route_ids: list[str] = Field(default_factory=list)


# ============================================================
# Station Graph
# ============================================================

class StationGraph(BaseModel):
    """
    역 하나의 전체 정적 그래프 데이터.

    app/data/stations/{station}.json 파일 하나가
    이 모델 하나에 대응한다.
    """

    # 역 코드
    # 예: YTP, MRN
    station_code: str

    # 역 이름
    # 예: 야탑역, 모란역
    station_name: str

    # 노선 정보
    #
    # 비환승역:
    # SUIN_BUNDANG
    #
    # 환승역의 경우 현재는 문자열로 복수 노선을 표현할 수 있다.
    # 예:
    # LINE8+SUIN_BUNDANG
    line: str

    # 역사 내부 node 목록
    nodes: list[StationNode]

    # 역사 내부 edge 목록
    edges: list[StationEdge]