from fastapi import APIRouter
from app.api.facility import router as facility_router
from app.api.geocode import router as geocode_router
from app.api.route import router as route_router

api_router = APIRouter(prefix="/api/v1")

api_router.include_router(geocode_router)
api_router.include_router(facility_router)
api_router.include_router(route_router)
