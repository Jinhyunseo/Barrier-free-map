from pydantic import BaseModel, Field


class RouteCandidateRequest(BaseModel):
    origin_x: float = Field(
        ...,
        description="출발지 경도",
        examples=[127.111990],
    )
    origin_y: float = Field(
        ...,
        description="출발지 위도",
        examples=[37.392800],
    )
    destination_x: float = Field(
        ...,
        description="도착지 경도",
        examples=[127.127110],
    )
    destination_y: float = Field(
        ...,
        description="도착지 위도",
        examples=[37.413110],
    )