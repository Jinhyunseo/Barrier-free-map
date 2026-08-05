from sqlalchemy import Column, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship
from app.core.database import Base


class UserType(Base):
    """교통약자 유형 정의 테이블 (User_Type)"""

    __tablename__ = "User_Type"

    user_type_id = Column(Integer, primary_key=True, autoincrement=True)
    type_name = Column(String(50), nullable=False)
    description = Column(Text, nullable=True)

    constraints = relationship("UserConstraint", back_populates="user_type")
    evaluations = relationship("RouteEvaluation", back_populates="user_type")


class ConstraintRule(Base):
    """교통약자 이동 제약 규칙 (Constraint_Rule)"""

    __tablename__ = "Constraint_Rule"

    constraint_id = Column(Integer, primary_key=True, autoincrement=True)
    constraint_name = Column(String(50), nullable=False)
    description = Column(String(255), nullable=True)

    user_constraints = relationship(
        "UserConstraint", back_populates="constraint_rule"
    )


class UserConstraint(Base):
    """사용자 유형별 적용 제약 조건 매핑 (User_Constraint)"""

    __tablename__ = "User_Constraint"

    user_type_id = Column(
        Integer, ForeignKey("User_Type.user_type_id"), primary_key=True
    )
    constraint_id = Column(
        Integer, ForeignKey("Constraint_Rule.constraint_id"), primary_key=True
    )

    user_type = relationship("UserType", back_populates="constraints")
    constraint_rule = relationship(
        "ConstraintRule", back_populates="user_constraints"
    )
