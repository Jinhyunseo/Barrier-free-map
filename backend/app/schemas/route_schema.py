from typing import Literal

from pydantic import BaseModel, Field


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


class RouteByPlaceRequest(BaseModel):
    """
    출발지와 목적지의 장소명, 사용자 유형을 입력해
    후보 경로를 조회할 때 사용하는 요청 형식
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
    user_type: Literal[
        "WHEELCHAIR",
        "STROLLER",
        "ELDERLY",
    ] = Field(
        ...,
        description=(
            "사용자 이동 유형: "
            "WHEELCHAIR(휠체어), "
            "STROLLER(유모차), "
            "ELDERLY(노약자)"
        ),
        examples=["WHEELCHAIR"],
    )