from typing import List, Optional
from sqlalchemy.orm import Session
from app.models.facility import Facility, FacilityStatus


class ElevatorRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_facility_by_station(
        self, station_name: str, facility_type: str = "ELEVATOR"
    ) -> List[Facility]:
        """역/정류장 명칭 기반 시설물 정적 정보 조회"""
        return (
            self.db.query(Facility)
            .filter(
                Facility.location_station.like(f"%{station_name}%"),
                Facility.facility_type == facility_type,
            )
            .all()
        )

    def get_facility_status(
        self, facility_id: int
    ) -> Optional[FacilityStatus]:
        """시설물 최근 상태 조회"""
        return (
            self.db.query(FacilityStatus)
            .filter(FacilityStatus.facility_id == facility_id)
            .order_by(FacilityStatus.last_updated_at.desc())
            .first()
        )
