from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict


class ReportType(str, Enum):
    BROKEN_ELEVATOR = "BROKEN_ELEVATOR"
    BROKEN_ESCALATOR = "BROKEN_ESCALATOR"
    INSPECTION_ELEVATOR = "INSPECTION_ELEVATOR"
    INSPECTION_ESCALATOR = "INSPECTION_ESCALATOR"
    RESTORED_ELEVATOR = "RESTORED_ELEVATOR"
    RESTORED_ESCALATOR = "RESTORED_ESCALATOR"


class ReportableFacilityResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    facility_id: int
    station_id: int
    station_name: str
    line_name: str | None = None
    facility_type: str
    facility_name: str | None = None
    exit_no: str | None = None
    direction: str | None = None
    detail_location: str | None = None
    status_code: str | None = None
    is_usable: bool | None = None


class ReportCreateResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    report_id: int
    user_id: int
    facility_id: int
    report_type: str
    title: str
    description: str | None = None
    image_url: str
    report_status: str
    ai_verification: str
    ai_confidence_score: float | None = None
    detected_status: str | None = None
    reason: str | None = None
    created_at: datetime


class ReportStatusResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    report_id: int
    report_status: str
    ai_verification_result: str | None = None
    confidence_score: float | None = None
    detected_status: str | None = None
    reason: str | None = None
