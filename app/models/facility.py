from datetime import datetime
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
)
from sqlalchemy.orm import relationship
from app.core.database import Base


class Facility(Base):
    """이동 편의시설 및 장애 요소 마스터 (Facility)"""

    __tablename__ = "Facility"

    facility_id = Column(Integer, primary_key=True, autoincrement=True)
    facility_name = Column(String(100), nullable=False)
    facility_type = Column(String(30), nullable=False)  # ELEVATOR, STAIRS, ESCALATOR, RAMP
    location_station = Column(String(100), nullable=False)
    api_facility_code = Column(String(100), nullable=True)

    statuses = relationship("FacilityStatus", back_populates="facility")
    segment_facilities = relationship("SegmentFacility", back_populates="facility")


class FacilityStatus(Base):
    """시설 실시간 운영 및 점검 상태 정보 (Facility_Status)"""

    __tablename__ = "Facility_Status"

    status_id = Column(Integer, primary_key=True, autoincrement=True)
    facility_id = Column(
        Integer, ForeignKey("Facility.facility_id"), nullable=False
    )
    status_code = Column(String(20), nullable=False, default="NORMAL")  # NORMAL, BROKEN, INSPECTION
    is_usable_wheelchair = Column(Boolean, nullable=False, default=True)
    last_updated_at = Column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    facility = relationship("Facility", back_populates="statuses")


class Transportation(Base):
    """교통수단 정보 (Transportation)"""

    __tablename__ = "Transportation"

    transport_id = Column(Integer, primary_key=True, autoincrement=True)
    transport_type = Column(String(30), nullable=False)  # SUBWAY, LOW_BUS, BUS, WALK
    line_number = Column(String(50), nullable=True)
    is_low_floor = Column(Boolean, nullable=False, default=False)

    segments = relationship("RouteSegment", back_populates="transportation")


class SegmentFacility(Base):
    """이동 구간별 포함 편의시설 매핑 (Segment_Facility)"""

    __tablename__ = "Segment_Facility"

    segment_id = Column(
        Integer, ForeignKey("Route_Segment.segment_id"), primary_key=True
    )
    facility_id = Column(
        Integer, ForeignKey("Facility.facility_id"), primary_key=True
    )
    is_essential = Column(Boolean, nullable=False, default=True)

    segment = relationship("RouteSegment", back_populates="segment_facilities")
    facility = relationship("Facility", back_populates="segment_facilities")
