from typing import Optional
from pydantic import BaseModel, Field


class GeocodeRequest(BaseModel):
    """장소명 → 좌표 변환 요청 스키마"""

    query: str = Field(..., description="검색할 장소명 또는 주소")


class RouteSearchRequest(BaseModel):
    """최적 경로 추천 요청 스키마 (Flutter 앱 -> FastAPI 백엔드)"""

    origin_name: str = Field(..., description="출발지 명칭")
    origin_lat: float = Field(..., description="출발지 위도")
    origin_lng: float = Field(..., description="출발지 경도")

    destination_name: str = Field(..., description="목적지 명칭")
    destination_lat: float = Field(..., description="목적지 위도")
    destination_lng: float = Field(..., description="목적지 경도")

    user_type: str = Field(
        ...,
        description="사용자 유형 (WHEELCHAIR: 휠체어, ELDERLY: 노약자, STROLLER: 유모차, GENERAL: 일반)",
    )

    max_transfers: Optional[int] = Field(
        default=None, description="최대 환승 횟수 제약"
    )
