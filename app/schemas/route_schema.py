from pydantic import BaseModel, Field


class RouteCandidateRequest(BaseModel):
    """좌표를 직접 입력해 후보 경로를 조회할 때 사용하는 요청 형식"""

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
        examples=[127.12711],
    )
    destination_y: float = Field(
        ...,
        description="목적지 위도",
        examples=[37.41311],
    )


class RouteByPlaceRequest(BaseModel):
    """출발지와 목적지의 장소명을 입력해 후보 경로를 조회할 때 사용하는 요청 형식"""

    origin_name: str = Field(
        ...,
        description="출발지 장소명",
        examples=["현대백화점 판교점"],
    )
    destination_name: str = Field(
        ...,
        description="목적지 장소명",
        examples=["성남종합버스터미널"],
    )
    user_type: str = Field(
        default="WHEELCHAIR",
        description="교통약자 유형 (WHEELCHAIR, BLIND, ELDER 등)"
        )