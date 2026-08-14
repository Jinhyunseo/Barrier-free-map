from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.orm import relationship

from app.core.database import Base


# ============================================================
# 2차 프로토타입 핵심 테이블
# ============================================================


class User(Base):
    __tablename__ = "user"

    user_id = Column(Integer, primary_key=True, autoincrement=True)
    email = Column(String(100), nullable=False, unique=True, index=True)
    password_hash = Column(String(255), nullable=False)
    nickname = Column(String(50), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    # 아래 3개 프로필/조건 테이블은 다른 팀 기능과의 호환용입니다.
    profile = relationship(
        "UserProfile",
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan",
    )
    condition_preferences = relationship(
        "UserConditionPreference",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    reports = relationship(
        "UserReport",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    evaluations = relationship("RouteEvaluation", back_populates="user")


class Station(Base):
    __tablename__ = "station"

    station_id = Column(Integer, primary_key=True, autoincrement=True)
    operator_code = Column(String(30), nullable=True)
    line_code = Column(String(30), nullable=True)
    line_name = Column(String(100), nullable=True)
    station_code = Column(String(50), nullable=False, index=True)
    station_name = Column(String(100), nullable=False, index=True)
    latitude = Column(Numeric(10, 7), nullable=True)
    longitude = Column(Numeric(11, 7), nullable=True)
    data_source = Column(String(50), nullable=False, default="PUBLIC_JSON")
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    facilities = relationship(
        "Facility",
        back_populates="station",
        cascade="all, delete-orphan",
    )


class Facility(Base):
    __tablename__ = "facility"

    facility_id = Column(Integer, primary_key=True, autoincrement=True)
    station_id = Column(
        Integer,
        ForeignKey("station.station_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    facility_type = Column(String(30), nullable=False, index=True)
    facility_name = Column(String(100), nullable=True)
    external_facility_code = Column(String(100), nullable=True, index=True)
    exit_no = Column(String(20), nullable=True)
    direction = Column(String(30), nullable=True)
    detail_location = Column(Text, nullable=True)
    from_floor_name = Column(String(30), nullable=True)
    to_floor_name = Column(String(30), nullable=True)
    from_floor = Column(Numeric(5, 2), nullable=True)
    to_floor = Column(Numeric(5, 2), nullable=True)
    passenger_capacity = Column(Integer, nullable=True)
    weight_capacity_kg = Column(Integer, nullable=True)
    latitude = Column(Numeric(10, 7), nullable=True)
    longitude = Column(Numeric(11, 7), nullable=True)
    data_source = Column(String(50), nullable=False, default="PUBLIC_JSON")
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    station = relationship("Station", back_populates="facilities")
    current_status = relationship(
        "FacilityStatus",
        back_populates="facility",
        uselist=False,
        cascade="all, delete-orphan",
    )
    status_history = relationship(
        "FacilityStatusHistory",
        back_populates="facility",
        cascade="all, delete-orphan",
    )
    reports = relationship("UserReport", back_populates="facility")
    segment_facilities = relationship(
        "SegmentFacility",
        back_populates="facility",
        cascade="all, delete-orphan",
    )


class FacilityStatus(Base):
    __tablename__ = "facility_status"

    status_id = Column(Integer, primary_key=True, autoincrement=True)
    facility_id = Column(
        Integer,
        ForeignKey("facility.facility_id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    status_code = Column(String(30), nullable=False, default="NORMAL")
    is_usable = Column(Boolean, nullable=False, default=True)
    is_usable_wheelchair = Column(Boolean, nullable=False, default=True)
    source_type = Column(String(30), nullable=False, default="INITIAL_DATA")
    source_report_id = Column(Integer, nullable=True)
    last_updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    facility = relationship("Facility", back_populates="current_status")


class FacilityStatusHistory(Base):
    __tablename__ = "facility_status_history"

    history_id = Column(Integer, primary_key=True, autoincrement=True)
    facility_id = Column(
        Integer,
        ForeignKey("facility.facility_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    previous_status = Column(String(30), nullable=True)
    new_status = Column(String(30), nullable=False)
    source_type = Column(String(30), nullable=False)
    report_id = Column(Integer, nullable=True, index=True)
    confidence_score = Column(Numeric(5, 2), nullable=True)
    changed_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    facility = relationship("Facility", back_populates="status_history")


class BusStop(Base):
    __tablename__ = "bus_stop"

    bus_stop_id = Column(Integer, primary_key=True, autoincrement=True)
    stop_code = Column(String(30), nullable=False, unique=True, index=True)
    stop_name = Column(String(150), nullable=False, index=True)
    detail_location = Column(String(255), nullable=True)
    latitude = Column(Numeric(10, 7), nullable=False)
    longitude = Column(Numeric(11, 7), nullable=False)
    district = Column(String(50), nullable=True)
    administrative_dong = Column(String(100), nullable=True)
    stop_installation_type = Column(String(50), nullable=True)
    central_lane = Column(String(1), nullable=True)
    chair_type = Column(String(50), nullable=True)
    bit_type = Column(String(100), nullable=True)
    air_cleaner_installed = Column(String(1), nullable=True)
    heating_cooling_installed = Column(String(1), nullable=True)
    windshield_installed = Column(String(1), nullable=True)
    fine_dust_sensor_installed = Column(String(1), nullable=True)
    emergency_bell_installed = Column(String(1), nullable=True)
    wifi_installed = Column(String(1), nullable=True)
    red_zone = Column(String(1), nullable=True)
    city_bus_routes = Column(Text, nullable=True)
    intercity_bus_routes = Column(Text, nullable=True)
    data_source = Column(String(50), nullable=False, default="PUBLIC_JSON")
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    reports = relationship("UserReport", back_populates="bus_stop")


class UserReport(Base):
    __tablename__ = "user_report"

    report_id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(
        Integer,
        ForeignKey("user.user_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    facility_id = Column(
        Integer,
        ForeignKey("facility.facility_id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    bus_stop_id = Column(
        Integer,
        ForeignKey("bus_stop.bus_stop_id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    report_type = Column(String(30), nullable=False)
    title = Column(String(150), nullable=False)
    description = Column(Text, nullable=True)
    image_url = Column(String(500), nullable=True)
    latitude = Column(Numeric(10, 7), nullable=False)
    longitude = Column(Numeric(11, 7), nullable=False)
    report_status = Column(String(20), nullable=False, default="PENDING")
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    user = relationship("User", back_populates="reports")
    facility = relationship("Facility", back_populates="reports")
    bus_stop = relationship("BusStop", back_populates="reports")
    ai_verification = relationship(
        "AIVerification",
        back_populates="report",
        uselist=False,
        cascade="all, delete-orphan",
    )


class AIVerification(Base):
    __tablename__ = "ai_verification"

    verification_id = Column(Integer, primary_key=True, autoincrement=True)
    report_id = Column(
        Integer,
        ForeignKey("user_report.report_id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    place_match = Column(Boolean, nullable=False, default=False)
    facility_match = Column(Boolean, nullable=False, default=False)
    state_match = Column(Boolean, nullable=False, default=False)
    confidence_score = Column(Numeric(5, 2), nullable=True)
    verification_result = Column(String(20), nullable=False, default="PENDING")
    reason = Column(Text, nullable=True)
    model_name = Column(String(100), nullable=True)
    raw_response = Column(Text, nullable=True)
    verified_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    report = relationship("UserReport", back_populates="ai_verification")


# ============================================================
# 다른 팀 기능과의 호환을 위한 기존 모델
# 현재 seongnam_nav_db_v2.sql의 F-09 핵심 스키마에는 포함되지 않습니다.
# ============================================================


class UserProfile(Base):
    __tablename__ = "user_profile"

    profile_id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(
        Integer,
        ForeignKey("user.user_id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    default_preference = Column(String(30), nullable=False, default="BALANCED")
    max_incline_angle = Column(Numeric(4, 1), default=8.0)
    max_step_height_cm = Column(Integer, default=3)

    user = relationship("User", back_populates="profile")


class ConditionMaster(Base):
    __tablename__ = "condition_master"

    condition_id = Column(Integer, primary_key=True, autoincrement=True)
    condition_code = Column(String(50), nullable=False, unique=True)
    condition_name = Column(String(100), nullable=False)
    description = Column(String(255), nullable=True)

    user_preferences = relationship(
        "UserConditionPreference",
        back_populates="condition",
    )


class UserConditionPreference(Base):
    __tablename__ = "user_condition_preference"

    user_id = Column(
        Integer,
        ForeignKey("user.user_id", ondelete="CASCADE"),
        primary_key=True,
    )
    condition_id = Column(
        Integer,
        ForeignKey("condition_master.condition_id", ondelete="CASCADE"),
        primary_key=True,
    )

    user = relationship("User", back_populates="condition_preferences")
    condition = relationship("ConditionMaster", back_populates="user_preferences")


class Transportation(Base):
    __tablename__ = "transportation"

    transport_id = Column(Integer, primary_key=True, autoincrement=True)
    transport_type = Column(String(30), nullable=False)
    line_number = Column(String(50), nullable=True)
    is_low_floor = Column(Boolean, nullable=False, default=False)
    has_wheelchair_lift = Column(Boolean, nullable=False, default=False)

    segments = relationship("RouteSegment", back_populates="transportation")


class Route(Base):
    __tablename__ = "route"

    route_id = Column(Integer, primary_key=True, autoincrement=True)
    route_name = Column(String(100), nullable=False)
    origin_name = Column(String(100), nullable=False)
    destination_name = Column(String(100), nullable=False)
    total_duration = Column(Integer, nullable=False)
    total_walk_distance = Column(Integer, nullable=False)
    transfer_count = Column(Integer, nullable=False, default=0)
    elevator_use_count = Column(Integer, nullable=False, default=0)
    has_low_floor_bus = Column(Boolean, nullable=False, default=False)
    transfer_difficulty_score = Column(Numeric(5, 2), default=0.00)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    segments = relationship(
        "RouteSegment",
        back_populates="route",
        cascade="all, delete-orphan",
    )
    evaluations = relationship(
        "RouteEvaluation",
        back_populates="route",
        cascade="all, delete-orphan",
    )


class RouteSegment(Base):
    __tablename__ = "route_segment"

    segment_id = Column(Integer, primary_key=True, autoincrement=True)
    route_id = Column(
        Integer,
        ForeignKey("route.route_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    sequence = Column(Integer, nullable=False)
    transport_id = Column(
        Integer,
        ForeignKey("transportation.transport_id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    start_node = Column(String(100), nullable=False)
    end_node = Column(String(100), nullable=False)
    walk_distance = Column(Integer, nullable=False, default=0)
    duration = Column(Integer, nullable=False)
    has_stairs = Column(Boolean, nullable=False, default=False)
    has_steep_incline = Column(Boolean, nullable=False, default=False)
    has_obstacle_step = Column(Boolean, nullable=False, default=False)

    route = relationship("Route", back_populates="segments")
    transportation = relationship("Transportation", back_populates="segments")
    segment_facilities = relationship(
        "SegmentFacility",
        back_populates="segment",
        cascade="all, delete-orphan",
    )


class SegmentFacility(Base):
    __tablename__ = "segment_facility"

    segment_id = Column(
        Integer,
        ForeignKey("route_segment.segment_id", ondelete="CASCADE"),
        primary_key=True,
    )
    facility_id = Column(
        Integer,
        ForeignKey("facility.facility_id", ondelete="CASCADE"),
        primary_key=True,
    )
    is_essential = Column(Boolean, nullable=False, default=True)

    segment = relationship("RouteSegment", back_populates="segment_facilities")
    facility = relationship("Facility", back_populates="segment_facilities")


class RouteEvaluation(Base):
    __tablename__ = "route_evaluation"

    evaluation_id = Column(Integer, primary_key=True, autoincrement=True)
    route_id = Column(
        Integer,
        ForeignKey("route.route_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id = Column(
        Integer,
        ForeignKey("user.user_id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    preference_option = Column(String(30), nullable=False, default="BALANCED")
    is_filtered_out = Column(Boolean, nullable=False, default=False)
    filter_reason = Column(String(255), nullable=True)
    calculated_score = Column(Numeric(10, 2), nullable=True)
    ai_recommend_reason = Column(Text, nullable=True)
    evaluated_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    route = relationship("Route", back_populates="evaluations")
    user = relationship("User", back_populates="evaluations")
