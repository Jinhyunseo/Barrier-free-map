from typing import List, Optional
from sqlalchemy.orm import Session
from app.models.facility import Transportation
from app.models.user import UserConstraint


class RouteRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_user_constraints(self, user_type_id: int) -> List[UserConstraint]:
        """사용자 유형별 제약 조건 목록 조회"""
        return (
            self.db.query(UserConstraint)
            .filter(UserConstraint.user_type_id == user_type_id)
            .all()
        )

    def is_bus_low_floor(self, line_number: str) -> Optional[bool]:
        """노선번호 기준 저상버스 운행 여부 조회"""
        trans_info = (
            self.db.query(Transportation)
            .filter(
                Transportation.line_number == line_number,
                Transportation.transport_type.in_(["LOW_BUS", "BUS"]),
            )
            .first()
        )
        return trans_info.is_low_floor if trans_info else None
