from typing import List
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.repositories.elevator_repository import ElevatorRepository
from app.schemas.response import FacilityStatusResponse

router = APIRouter(prefix="/facility", tags=["Facility"])


@router.get("/status", response_model=List[FacilityStatusResponse])
def get_facility_status(
    station_name: str = Query(..., description="조회할 역/정류장 명칭 (예: 야탑역)"),
    db: Session = Depends(get_db),
):
    """역/정류장별 승강기 및 편의시설 실시간 상태 조회 API"""
    repo = ElevatorRepository(db)
    facilities = repo.get_facility_by_station(station_name)
    response_list = []

    for f in facilities:
        status_info = repo.get_facility_status(f.facility_id)
        response_list.append(
            FacilityStatusResponse(
                facility_id=f.facility_id,
                standard_name=f.facility_name,
                facility_type=f.facility_type,
                station_name=f.location_station,
                status_code=status_info.status_code if status_info else "NORMAL",
                source_updated_at=status_info.last_updated_at if status_info else None,
            )
        )

    return response_list
