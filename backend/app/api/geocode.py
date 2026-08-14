from fastapi import APIRouter, Depends, Query
from app.schemas.response import GeocodeResponse
from app.services.geocode_service import GeocodeService

router = APIRouter(prefix="/geocode", tags=["Geocode (좌표 변환)"])


@router.get("", response_model=GeocodeResponse)
async def search_geocode(
    query: str = Query(..., description="검색할 주소 또는 장소명 (예: 서울특별시 서초구 반포대로 58 또는 강남역)"),
    service: GeocodeService = Depends(),
):
    """
    [통합 좌표 변환 API]
    입력된 텍스트가 주소인지 장소명인지 자동 판단하여 좌표(위도, 경도)를 변환합니다.
    (주소 검색을 우선 시도 후, 결과가 없는 경우 장소 검색을 수행)
    """
    search_type, results = await service.search_auto(query)
    return GeocodeResponse(query=query, search_type=search_type, results=results)


@router.get("/address", response_model=GeocodeResponse)
async def search_by_address(
    address: str = Query(..., description="변환할 도로명 주소 또는 지번 주소 (예: 서울특별시 서초구 반포대로 58)"),
    service: GeocodeService = Depends(),
):
    """
    [주소 전용 좌표 변환 API]
    도로명 주소 또는 지번 주소를 직접 입력 받아 위도/경도 좌표로 도출합니다.
    """
    results = await service.search_address(address)
    return GeocodeResponse(query=address, search_type="ADDRESS", results=results)


@router.get("/keyword", response_model=GeocodeResponse)
async def search_by_keyword(
    keyword: str = Query(..., description="변환할 장소명 또는 건물이름 (예: 강남역, 고속터미널)"),
    service: GeocodeService = Depends(),
):
    """
    [장소명/키워드 전용 좌표 변환 API]
    장소명 또는 키워드를 입력 받아 위치 좌표로 변환합니다.
    """
    results = await service.search_keyword(keyword)
    return GeocodeResponse(query=keyword, search_type="KEYWORD", results=results)