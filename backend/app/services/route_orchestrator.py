from __future__ import annotations

from typing import Any

from app.schemas.v2 import MobilityCondition, PreferenceOption
from app.services.condition_service import condition_exclusion_reasons, preference_sort_key, resolve_legacy_profile
from app.services.geocode_service import GeocodeService
from app.services.kakao_service import get_transit_routes, simplify_routes
from app.services.movement_extraction_service import attach_station_movements
from app.services.recommendation_service import evaluate_candidate_route


class RouteOrchestrator:
    def __init__(self):
        self.geocoder = GeocodeService()

    async def search(
        self,
        origin_query: str,
        destination_query: str,
        conditions: list[MobilityCondition],
        preference: PreferenceOption,
    ) -> dict[str, Any]:
        _, origin_results = await self.geocoder.search_auto(origin_query)
        if not origin_results:
            raise ValueError(f"출발지를 찾을 수 없습니다: {origin_query}")

        _, destination_results = await self.geocoder.search_auto(destination_query)
        if not destination_results:
            raise ValueError(f"목적지를 찾을 수 없습니다: {destination_query}")

        origin = origin_results[0]
        destination = destination_results[0]

        kakao_data = await get_transit_routes(
            origin_x=origin.longitude,
            origin_y=origin.latitude,
            destination_x=destination.longitude,
            destination_y=destination.latitude,
        )
        simplified = simplify_routes(kakao_data)
        routes = attach_station_movements(simplified.get("routes", []))

        # The existing station-path engine is reused through a compatibility profile.
        # The public contract remains condition-based; this adapter can be removed after
        # station_path_service is fully converted to condition sets.
        legacy_profile = resolve_legacy_profile(conditions)
        evaluated: list[dict[str, Any]] = []
        excluded: list[dict[str, Any]] = []

        for route in routes:
            item = evaluate_candidate_route(route, legacy_profile)
            extra_reasons = condition_exclusion_reasons(item, set(conditions))
            reasons = list(dict.fromkeys(item["evaluation"].get("exclusion_reasons", []) + extra_reasons))
            item["evaluation"]["exclusion_reasons"] = reasons
            item["evaluation"]["is_available"] = not reasons

            if reasons:
                excluded.append({
                    "route_id": item.get("route_id"),
                    "route_type": item.get("route_type"),
                    "exclusion_reasons": reasons,
                })
            else:
                evaluated.append(item)

        evaluated.sort(key=lambda r: preference_sort_key(r, preference))
        optimal = evaluated[0] if evaluated else None
        if optimal:
            optimal.setdefault("evaluation", {})["is_recommended"] = True

        return {
            "origin": origin.model_dump(),
            "destination": destination.model_dump(),
            "preference": preference,
            "mobility_conditions": conditions,
            "optimal_route": optimal,
            "alternative_routes": evaluated[1:],
            "excluded_routes": excluded,
            "ai_recommendation_reason": self._build_reason(optimal, conditions, preference),
        }

    @staticmethod
    def _build_reason(route: dict[str, Any] | None, conditions: list[MobilityCondition], preference: PreferenceOption) -> str | None:
        if not route:
            return "선택한 이동 조건을 만족하는 경로를 찾지 못했습니다."
        reasons = route.get("evaluation", {}).get("positive_reasons", [])
        prefix = f"{preference.value} 기준으로 선택한 경로입니다."
        if reasons:
            return prefix + " " + " ".join(reasons[:3])
        return prefix
