from typing import Any

from fastapi import APIRouter, HTTPException

from app.schemas.route_schema import (
    RouteByPlaceRequest,
    RouteCandidateRequest,
)
from app.services.geocode_service import GeocodeService
from app.services.kakao_service import (
    get_transit_routes,
    simplify_routes,
)


router = APIRouter(
    prefix="/routes",
    tags=["Routes"],
)


@router.post("/candidates")
async def get_route_candidates(
    request: RouteCandidateRequest,
) -> dict[str, Any]:
    kakao_data = await get_transit_routes(
        origin_x=request.origin_x,
        origin_y=request.origin_y,
        destination_x=request.destination_x,
        destination_y=request.destination_y,
    )

    return simplify_routes(kakao_data)


@router.post("/by-places")
async def get_routes_by_places(
    request: RouteByPlaceRequest,
) -> dict[str, Any]:
    geocode_service = GeocodeService()

    _, origin_results = await geocode_service.search_auto(
        request.origin_name
    )

    if not origin_results:
        raise HTTPException(
            status_code=404,
            detail=f"출발지를 찾을 수 없습니다: {request.origin_name}",
        )

    _, destination_results = await geocode_service.search_auto(
        request.destination_name
    )

    if not destination_results:
        raise HTTPException(
            status_code=404,
            detail=f"목적지를 찾을 수 없습니다: {request.destination_name}",
        )

    origin = origin_results[0]
    destination = destination_results[0]

    kakao_data = await get_transit_routes(
        origin_x=origin.longitude,
        origin_y=origin.latitude,
        destination_x=destination.longitude,
        destination_y=destination.latitude,
    )

    routes = simplify_routes(kakao_data)

    return {
        "origin": origin.model_dump(),
        "destination": destination.model_dump(),
        **routes,
    }