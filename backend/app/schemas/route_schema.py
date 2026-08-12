from typing import Literal

from pydantic import BaseModel, Field


# =========================================================
# 2차 프로토타입 - 이동 조건
# =========================================================

class MobilityConstraints(BaseModel):
    """
    사용자가 이동할 때 필요한 접근성 조건.

    여러 조건을 동시에 선택할 수 있으므로
    각각 boolean 값으로 관리한다.
    """

    avoid_stairs: bool = Field(
        default=False,
        description="계단 이용이 어려워 계단이 포함된 경로를 피함",
        examples=[True],
    )

    require_elevator: bool = Field(
        default=False,
        description="역사 내부 이동 시 엘리베이터 이용이 필수",
        examples=[True],
    )

    avoid_escalator: bool = Field(
        default=False,
        description="에스컬레이터 이용이 어려워 해당 이동을 피함",
        examples=[False],
    )

    avoid_steep_slope: bool = Field(
        default=False,
        description="급경사가 포함된 보행 경로를 피함",
        examples=[True],
    )

    require_low_floor_bus: bool = Field(
        default=False,
        description="버스 이용 시 저상버스가 필요한 경우",
        examples=[True],
    )


# =========================================================
# 좌표 기반 경로 요청
# =========================================================

class RouteCandidateRequest(BaseModel):
    """
    출발지와 목적지의 좌표를 직접 입력해
    후보 경로를 조회할 때 사용하는 요청 형식
    """

    origin_x: float = Field(
        ...,
        description="출발지 경도",
        examples=[127.11204751299005],
    )

    origin_y: float = Field(
        ...,
        description="출발지 위도",
        examples=[37.39279718014944],
    )

    destination_x: float = Field(
        ...,
        description="목적지 경도",
        examples=[127.12741533321095],
    )

    destination_y: float = Field(
        ...,
        description="목적지 위도",
        examples=[37.41312485775141],
    )


# =========================================================
# 장소명 기반 맞춤 경로 요청
# =========================================================

class RouteByPlaceRequest(BaseModel):
    """
    출발지와 목적지의 장소명,
    사용자의 이동 조건과 경로 선호도를 입력해
    맞춤형 접근성 경로를 조회할 때 사용하는 요청 형식
    """

    origin_name: str = Field(
        ...,
        description="출발지 주소 또는 장소명",
        examples=["현대백화점 판교점"],
    )

    destination_name: str = Field(
        ...,
        description="목적지 주소 또는 장소명",
        examples=["성남종합버스터미널"],
    )

    mobility_constraints: MobilityConstraints = Field(
        default_factory=MobilityConstraints,
        description="사용자가 이동할 때 필요한 접근성 조건",
    )

    route_preference: Literal[
        "BALANCED",
        "FASTEST",
        "MIN_WALKING",
        "MIN_TRANSFER",
    ] = Field(
        default="BALANCED",
        description=(
            "경로 추천 우선순위: "
            "BALANCED(추천), "
            "FASTEST(최단 시간), "
            "MIN_WALKING(최소 도보), "
            "MIN_TRANSFER(최소 환승)"
        ),
        examples=["BALANCED"],
    )