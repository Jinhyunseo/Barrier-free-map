from pydantic import BaseModel, EmailStr, Field, ConfigDict
from typing import List, Optional
from datetime import datetime
from enum import Enum

# --- Enums ---
class PreferenceOptionEnum(str, Enum):
    BALANCED = "BALANCED"
    TIME_FIRST = "TIME_FIRST"
    MIN_WALK = "MIN_WALK"
    MIN_TRANSFER = "MIN_TRANSFER"

class ConditionCodeEnum(str, Enum):
    AVOID_STAIRS = "AVOID_STAIRS"
    PREFER_ELEVATOR = "PREFER_ELEVATOR"
    AVOID_STEEP_INCLINE = "AVOID_STEEP_INCLINE"
    NEED_LOW_BUS = "NEED_LOW_BUS"
    AVOID_OBSTACLE_STEP = "AVOID_OBSTACLE_STEP"

# --- User & Profile ---
class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8)
    nickname: str
    selected_condition_ids: List[int] = Field(default_factory=list, description="다중 선택된 이동 조건 ID 목록 [F-01]")

class UserProfileResponse(BaseModel):
    default_preference: PreferenceOptionEnum
    max_incline_angle: float
    max_step_height_cm: int

    model_config = ConfigDict(from_attributes=True)

class UserResponse(BaseModel):
    user_id: int
    email: EmailStr
    nickname: str
    profile: Optional[UserProfileResponse] = None

    model_config = ConfigDict(from_attributes=True)

# --- Route Search Request & Response ---
class RouteSearchRequest(BaseModel):
    origin_name: str = Field(..., example="판교역")
    destination_name: str = Field(..., example="성남종합버스터미널")
    mobility_conditions: List[ConditionCodeEnum] = Field(
        ..., description="이동 조건 다중 선택 (Multi-select) [F-01]"
    )
    preference_option: PreferenceOptionEnum = Field(
        default=PreferenceOptionEnum.BALANCED, description="경로 선호도 옵션 (Single-select) [F-03]"
    )

class RouteSegmentResponse(BaseModel):
    sequence: int
    transport_type: str
    line_number: Optional[str] = None
    start_node: str
    end_node: str
    walk_distance: int
    duration: int
    has_stairs: bool
    has_steep_incline: bool
    has_obstacle_step: bool

    model_config = ConfigDict(from_attributes=True)

class RouteSearchResponse(BaseModel):
    route_id: int
    route_name: str
    total_duration: int
    total_walk_distance: int
    transfer_count: int
    elevator_use_count: int
    has_low_floor_bus: bool
    transfer_difficulty_score: float
    ai_recommend_reason: Optional[str] = None
    segments: List[RouteSegmentResponse] = []

    model_config = ConfigDict(from_attributes=True)

# --- User Report ---
class UserReportCreate(BaseModel):
    report_type: str = Field(..., example="BROKEN_ELEVATOR")
    title: str
    description: Optional[str] = None
    image_url: Optional[str] = None
    latitude: float
    longitude: float

class UserReportResponse(BaseModel):
    report_id: int
    user_id: int
    title: str
    ai_verification_status: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)