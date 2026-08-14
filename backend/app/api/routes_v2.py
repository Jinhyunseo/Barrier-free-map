from fastapi import APIRouter, HTTPException

from app.schemas.v2 import RouteSearchRequest, RouteSearchResponse
from app.services.route_orchestrator import RouteOrchestrator

router = APIRouter(prefix="/routes", tags=["Routes v2"])
service = RouteOrchestrator()


@router.post("/search", response_model=RouteSearchResponse)
async def search_routes(request: RouteSearchRequest):
    try:
        return await service.search(
            origin_query=request.origin,
            destination_query=request.destination,
            conditions=request.mobility_conditions,
            preference=request.preference,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"경로 탐색 중 오류가 발생했습니다: {exc}") from exc
