from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, EmailStr, Field


class MobilityCondition(str, Enum):
    AVOID_STAIRS = "AVOID_STAIRS"
    PREFER_ELEVATOR = "PREFER_ELEVATOR"
    AVOID_STEEP_INCLINE = "AVOID_STEEP_INCLINE"
    NEED_LOW_BUS = "NEED_LOW_BUS"
    AVOID_OBSTACLE_STEP = "AVOID_OBSTACLE_STEP"
    AVOID_GENERAL_BUS = "AVOID_GENERAL_BUS"


class PreferenceOption(str, Enum):
    BALANCED = "BALANCED"
    TIME_FIRST = "TIME_FIRST"
    MIN_WALK = "MIN_WALK"
    MIN_TRANSFER = "MIN_TRANSFER"


class ConditionResponse(BaseModel):
    condition_id: int
    condition_code: str
    condition_name: str
    description: str | None = None

    model_config = {"from_attributes": True}


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    nickname: str
    mobility_conditions: list[MobilityCondition] = Field(default_factory=list)
    default_preference: PreferenceOption = PreferenceOption.BALANCED
    max_incline_angle: float = 8.3
    max_step_height_cm: int = 3


class UserProfileUpdate(BaseModel):
    mobility_conditions: list[MobilityCondition] = Field(default_factory=list)
    default_preference: PreferenceOption = PreferenceOption.BALANCED
    max_incline_angle: float = 8.3
    max_step_height_cm: int = 3


class UserResponse(BaseModel):
    user_id: int
    email: EmailStr
    nickname: str
    mobility_conditions: list[str] = Field(default_factory=list)
    default_preference: str = "BALANCED"
    max_incline_angle: float = 8.3
    max_step_height_cm: int = 3


class RouteSearchRequest(BaseModel):
    origin: str
    destination: str
    mobility_conditions: list[MobilityCondition] = Field(default_factory=list)
    preference: PreferenceOption = PreferenceOption.BALANCED


class RouteSearchResponse(BaseModel):
    origin: dict[str, Any]
    destination: dict[str, Any]
    preference: PreferenceOption
    mobility_conditions: list[MobilityCondition]
    optimal_route: dict[str, Any] | None = None
    alternative_routes: list[dict[str, Any]] = Field(default_factory=list)
    excluded_routes: list[dict[str, Any]] = Field(default_factory=list)
    ai_recommendation_reason: str | None = None
