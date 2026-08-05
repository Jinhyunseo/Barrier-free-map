from datetime import datetime
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Numeric,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import relationship
from app.core.database import Base


class Route(Base):
    """후보 경로 마스터 테이블 (Route)"""

    __tablename__ = "Route"

    route_id = Column(Integer, primary_key=True, autoincrement=True)
    route_name = Column(String(100), nullable=False)
    origin_name = Column(String(100), nullable=False)
    destination_name = Column(String(100), nullable=False)
    total_duration = Column(Integer, nullable=False)
    total_walk_distance = Column(Integer, nullable=False)
    transfer_count = Column(Integer, nullable=False, default=0)
    elevator_use_count = Column(Integer, nullable=False, default=0)
    has_low_floor_bus = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    segments = relationship("RouteSegment", back_populates="route")
    evaluations = relationship("RouteEvaluation", back_populates="route")


class RouteSegment(Base):
    """경로별 세부 이동 구간 (Route_Segment)"""

    __tablename__ = "Route_Segment"

    segment_id = Column(Integer, primary_key=True, autoincrement=True)
    route_id = Column(Integer, ForeignKey("Route.route_id"), nullable=False)
    sequence = Column(Integer, nullable=False)
    transport_id = Column(
        Integer, ForeignKey("Transportation.transport_id"), nullable=False
    )
    start_node = Column(String(100), nullable=False)
    end_node = Column(String(100), nullable=False)
    walk_distance = Column(Integer, nullable=False, default=0)
    duration = Column(Integer, nullable=False)
    has_stairs = Column(Boolean, nullable=False, default=False)

    route = relationship("Route", back_populates="segments")
    transportation = relationship("Transportation", back_populates="segments")
    segment_facilities = relationship(
        "SegmentFacility", back_populates="segment"
    )


class RouteEvaluation(Base):
    """사용자 맞춤 경로 평가 및 AI 추천 결과 (Route_Evaluation)"""

    __tablename__ = "Route_Evaluation"

    evaluation_id = Column(Integer, primary_key=True, autoincrement=True)
    route_id = Column(Integer, ForeignKey("Route.route_id"), nullable=False)
    user_type_id = Column(
        Integer, ForeignKey("User_Type.user_type_id"), nullable=False
    )
    is_filtered_out = Column(Boolean, nullable=False, default=False)
    filter_reason = Column(String(255), nullable=True)
    calculated_score = Column(Numeric(10, 2), nullable=True)
    ai_recommend_reason = Column(Text, nullable=True)
    evaluated_at = Column(DateTime, default=datetime.utcnow)

    route = relationship("Route", back_populates="evaluations")
    user_type = relationship("UserType", back_populates="evaluations")
