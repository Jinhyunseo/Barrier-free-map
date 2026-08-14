from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field


class LocationPoint(BaseModel):
    name: str
    latitude: float
    longitude: float
    address: Optional[str] = None
    road_address: Optional[str] = None


class GeocodeResponse(BaseModel):
    query: str
    search_type: str = "KEYWORD"  # KEYWORD 또는 ADDRESS
    results: List[LocationPoint]


class FacilityStatusResponse(BaseModel):
    facility_id: int
    standard_name: str
    facility_type: str
    station_name: str
    status_code: str
    source_updated_at: Optional[datetime] = None


class RouteSegment(BaseModel):
    mode: str  # BUS, SUBWAY, WALK
    route_name: Optional[str] = None  # 버스 번호 또는 지하철 노선명
    start_station: str
    end_station: str
    duration_minutes: int
    distance_meters: int
    is_accessible: bool = True  # 이동 편의성 보장 여부
    accessibility_issues: List[str] = Field(default_factory=list)


class RouteDetail(BaseModel):
    route_id: str
    total_duration_minutes: int
    total_walk_distance_meters: int
    transfer_count: int
    total_score: float
    segments: List[RouteSegment]
    is_filtered_out: bool = False
    filter_reason: Optional[str] = None


class ExcludedRouteInfo(BaseModel):
    route_id: str
    summary: str
    exclusion_reason: str


class RouteSearchResponse(BaseModel):
    """Flutter 앱으로 반환할 최종 추천 경로 결과 스키마"""

    user_type: str
    optimal_route: Optional[RouteDetail] = None
    alternative_routes: List[RouteDetail] = Field(default_factory=list)
    excluded_routes: List[ExcludedRouteInfo] = Field(default_factory=list)
    ai_recommendation_reason: str = Field(
        ..., description="Gemini가 생성한 추천 이유 자연어 설명"
    )