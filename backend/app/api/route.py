from typing import Any

from fastapi import APIRouter, HTTPException

from app.schemas.route_schema import (
    RouteByPlaceRequest,
    RouteCandidateRequest,
)

from app.services.geocode_service import (
    GeocodeService,
)

from app.services.kakao_service import (
    get_transit_routes,
    simplify_routes,
)

from app.services.movement_extraction_service import (
    attach_station_movements,
)

from app.services.recommendation_service import (
    select_best_candidate,
)

from app.services.station_path_service import (
    analyze_station_movement,
    resolve_movement_nodes,
    find_shortest_internal_path,
    extract_required_facilities,
    find_realtime_safe_internal_path,
)

from app.services.facility_status_service import (
    attach_realtime_status_to_facilities,
    summarize_route_facility_status,
)

from app.services.bus_matching_service import (
    match_bus_step_identifiers,
)

from app.services.bus_arrival_service import (
    get_low_floor_bus_status,
)


router = APIRouter(
    prefix="/routes",
    tags=["Routes"],
)


# ==============================================================================
# 1. 좌표 기반 후보 경로 조회
# ==============================================================================

@router.post("/candidates")
async def get_route_candidates(
    request: RouteCandidateRequest,
) -> dict[str, Any]:
    """
    출발지와 목적지 좌표를 직접 입력받아
    카카오 후보 경로 전체를 반환합니다.
    """

    try:
        kakao_data = (
            await get_transit_routes(
                origin_x=request.origin_x,
                origin_y=request.origin_y,
                destination_x=request.destination_x,
                destination_y=request.destination_y,
            )
        )

        return simplify_routes(
            kakao_data
        )

    except Exception as error:
        raise HTTPException(
            status_code=502,
            detail=(
                "카카오 후보 경로 조회 중 "
                f"오류가 발생했습니다: {error}"
            ),
        ) from error


# ==============================================================================
# 2. 장소명 기반 후보 경로 조회
# ==============================================================================

@router.post("/by-places")
async def get_routes_by_places(
    request: RouteByPlaceRequest,
) -> dict[str, Any]:
    """
    출발지·목적지 장소명을 좌표로 변환한 뒤
    카카오 후보 경로 전체를 반환합니다.

    각 후보에는 station_movements도 추가합니다.
    """

    geocode_service = (
        GeocodeService()
    )

    # --------------------------------------------------------------------------
    # 1. 출발지 검색
    # --------------------------------------------------------------------------

    _, origin_results = (
        await geocode_service.search_auto(
            request.origin_name
        )
    )

    if not origin_results:
        raise HTTPException(
            status_code=404,
            detail=(
                "출발지를 찾을 수 없습니다: "
                f"{request.origin_name}"
            ),
        )

    # --------------------------------------------------------------------------
    # 2. 목적지 검색
    # --------------------------------------------------------------------------

    _, destination_results = (
        await geocode_service.search_auto(
            request.destination_name
        )
    )

    if not destination_results:
        raise HTTPException(
            status_code=404,
            detail=(
                "목적지를 찾을 수 없습니다: "
                f"{request.destination_name}"
            ),
        )

    origin = (
        origin_results[0]
    )

    destination = (
        destination_results[0]
    )

    # --------------------------------------------------------------------------
    # 3. 카카오 후보 경로 조회
    # --------------------------------------------------------------------------

    try:
        kakao_data = (
            await get_transit_routes(
                origin_x=origin.longitude,
                origin_y=origin.latitude,
                destination_x=destination.longitude,
                destination_y=destination.latitude,
            )
        )

    except Exception as error:
        raise HTTPException(
            status_code=502,
            detail=(
                "카카오 후보 경로 조회 중 "
                f"오류가 발생했습니다: {error}"
            ),
        ) from error

    # --------------------------------------------------------------------------
    # 4. 응답 단순화
    # --------------------------------------------------------------------------

    simplified_data = (
        simplify_routes(
            kakao_data
        )
    )

    routes = (
        simplified_data.get(
            "routes",
            [],
        )
    )

    if not routes:
        raise HTTPException(
            status_code=404,
            detail=(
                "조회된 후보 경로가 없습니다."
            ),
        )

    # --------------------------------------------------------------------------
    # 5. 승차 / 환승 / 하차 movement 추출
    # --------------------------------------------------------------------------

    routes = (
        attach_station_movements(
            routes
        )
    )

    # --------------------------------------------------------------------------
    # 6. 반환
    # --------------------------------------------------------------------------

    return {
        "origin": (
            origin.model_dump()
        ),

        "destination": (
            destination.model_dump()
        ),

        "mobility_constraints": (
            request.mobility_constraints.model_dump()
        ),

        "route_preference": (
            request.route_preference
        ),

        **simplified_data,

        "routes": (
            routes
        ),
    }


# ==============================================================================
# 3. 최종 사용자 맞춤 경로 추천
# ==============================================================================

@router.post("/recommend")
async def get_recommended_route(
    request: RouteByPlaceRequest,
) -> dict[str, Any]:
    """
    최종 사용자 맞춤 경로 추천 API.

    처리 과정:

    1. 장소명 → 좌표 변환
    2. 카카오 대중교통 후보 경로 조회
    3. 후보 경로 단순화
    4. station_movements 추출
    5. 역 내부 이동 그래프 탐색
    6. 이동 조건 제약 적용
    7. 실제 EV / ES 실시간 상태 조회
    8. 고장 시설 발견 시 해당 edge 차단
    9. 역 내부 우회 경로 재탐색
    10. Hard Barrier 검사
    11. 경로 선호도 기반 점수 계산
    12. 가장 적합한 경로 추천
    """

    geocode_service = (
        GeocodeService()
    )

    # ==========================================================================
    # 1. 출발지 검색
    # ==========================================================================

    _, origin_results = (
        await geocode_service.search_auto(
            request.origin_name
        )
    )

    if not origin_results:
        raise HTTPException(
            status_code=404,
            detail=(
                "출발지를 찾을 수 없습니다: "
                f"{request.origin_name}"
            ),
        )

    # ==========================================================================
    # 2. 목적지 검색
    # ==========================================================================

    _, destination_results = (
        await geocode_service.search_auto(
            request.destination_name
        )
    )

    if not destination_results:
        raise HTTPException(
            status_code=404,
            detail=(
                "목적지를 찾을 수 없습니다: "
                f"{request.destination_name}"
            ),
        )

    origin = (
        origin_results[0]
    )

    destination = (
        destination_results[0]
    )

    # ==========================================================================
    # 3. 카카오 후보 경로 조회
    # ==========================================================================

    try:
        kakao_data = (
            await get_transit_routes(
                origin_x=origin.longitude,
                origin_y=origin.latitude,
                destination_x=destination.longitude,
                destination_y=destination.latitude,
            )
        )

    except Exception as error:
        raise HTTPException(
            status_code=502,
            detail=(
                "카카오 후보 경로 조회 중 "
                f"오류가 발생했습니다: {error}"
            ),
        ) from error

    # ==========================================================================
    # 4. 카카오 응답 단순화
    # ==========================================================================

    simplified_data = (
        simplify_routes(
            kakao_data
        )
    )

    routes = (
        simplified_data.get(
            "routes",
            [],
        )
    )

    if not routes:
        raise HTTPException(
            status_code=404,
            detail=(
                "조회된 후보 경로가 없습니다."
            ),
        )

    # ==========================================================================
    # 5. station_movements 추출
    # ==========================================================================

    routes = (
        attach_station_movements(
            routes
        )
    )

    # ==========================================================================
    # 6. 최종 추천
    #
    # recommendation_service 내부에서:
    #
    # station_movements
    # → 역 내부 그래프
    # → 이동 조건 제약
    # → 실시간 EV / ES
    # → 고장 시설 우회
    # → Hard Barrier
    # → 경로 선호도 점수
    # → 최종 추천
    #
    # 순으로 처리됩니다.
    # ==========================================================================

    try:
        recommendation_result = (
            await select_best_candidate(
                routes=routes,
                mobility_constraints=(
                    request.mobility_constraints.model_dump()
                ),
                route_preference=(
                    request.route_preference
                ),
            )
        )

    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail=str(
                error
            ),
        ) from error

    except FileNotFoundError as error:
        raise HTTPException(
            status_code=500,
            detail=(
                "경로 추천에 필요한 데이터 파일을 "
                f"찾을 수 없습니다: {error}"
            ),
        ) from error

    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=(
                "추천 경로 계산 중 "
                f"오류가 발생했습니다: {error}"
            ),
        ) from error

    # ==========================================================================
    # 7. 최종 반환
    # ==========================================================================

    return {
        "origin": (
            origin.model_dump()
        ),

        "destination": (
            destination.model_dump()
        ),

        **recommendation_result,
    }


# ==============================================================================
# 4. 기본 역 내부 경로 디버그
# ==============================================================================

@router.post("/debug/path")
async def debug_station_path(
    payload: dict[str, Any],
) -> dict[str, Any]:
    """
    station_movement 하나의 기본 역 내부 경로를 테스트합니다.

    payload 예시:
    {
        "movement": {...},
        "mobility_constraints": {
            "avoid_stairs": true,
            "require_elevator": true,
            "avoid_escalator": false,
            "avoid_steep_slope": false
        }
    }

    실시간 상태는 반영하지 않습니다.
    """

    movement = payload.get(
        "movement"
    )

    mobility_constraints = payload.get(
        "mobility_constraints",
        {},
    )

    if not isinstance(
        movement,
        dict,
    ):
        raise HTTPException(
            status_code=400,
            detail=(
                "movement는 객체(dict) 형태여야 합니다."
            ),
        )

    if not isinstance(
        mobility_constraints,
        dict,
    ):
        raise HTTPException(
            status_code=400,
            detail=(
                "mobility_constraints는 "
                "객체(dict) 형태여야 합니다."
            ),
        )

    return (
        analyze_station_movement(
            movement=movement,
            mobility_constraints=(
                mobility_constraints
            ),
        )
    )


# ==============================================================================
# 5. 실시간 시설 상태 디버그
# ==============================================================================

@router.post(
    "/debug/facility-status"
)
async def debug_facility_status(
    payload: dict[str, Any],
) -> dict[str, Any]:
    """
    required_facilities에
    실제 EV / ES 실시간 운행 상태를 붙입니다.
    """

    required_facilities = (
        payload.get(
            "required_facilities",
            [],
        )
    )

    if not isinstance(
        required_facilities,
        list,
    ):
        raise HTTPException(
            status_code=400,
            detail=(
                "required_facilities는 "
                "list 형태여야 합니다."
            ),
        )

    facilities_with_status = (
        attach_realtime_status_to_facilities(
            required_facilities
        )
    )

    summary = (
        summarize_route_facility_status(
            facilities_with_status
        )
    )

    return {
        "required_facilities": (
            facilities_with_status
        ),

        "facility_status_summary": (
            summary
        ),
    }


# ==============================================================================
# 6. 특정 시설 강제 차단 디버그
# ==============================================================================

@router.post(
    "/debug/path-with-blocked-facilities"
)
async def debug_path_with_blocked_facilities(
    payload: dict[str, Any],
) -> dict[str, Any]:
    """
    특정 EV / ES를 강제로 차단하고
    이동 조건을 반영해 BFS를 수행합니다.
    """

    movement = payload.get(
        "movement"
    )

    blocked_edge_ids = payload.get(
        "blocked_edge_ids",
        [],
    )

    mobility_constraints = payload.get(
        "mobility_constraints",
        {},
    )

    if not isinstance(
        movement,
        dict,
    ):
        raise HTTPException(
            status_code=400,
            detail=(
                "movement는 객체(dict) 형태여야 합니다."
            ),
        )

    if not isinstance(
        blocked_edge_ids,
        list,
    ):
        raise HTTPException(
            status_code=400,
            detail=(
                "blocked_edge_ids는 list 형태여야 합니다."
            ),
        )

    if not isinstance(
        mobility_constraints,
        dict,
    ):
        raise HTTPException(
            status_code=400,
            detail=(
                "mobility_constraints는 "
                "객체(dict) 형태여야 합니다."
            ),
        )

    blocked_set = {
        str(
            edge_id
        ).strip()
        for edge_id
        in blocked_edge_ids
        if str(
            edge_id
        ).strip()
    }

    resolved = (
        resolve_movement_nodes(
            movement
        )
    )

    if (
        resolved.get(
            "status"
        )
        != "SUCCESS"
    ):
        return {
            "status": (
                resolved.get(
                    "status",
                    "ERROR",
                )
            ),
            "mobility_constraints": (
                mobility_constraints
            ),
            "movement": (
                movement
            ),
            "blocked_edge_ids": (
                sorted(
                    blocked_set
                )
            ),
            "node_resolution": (
                resolved
            ),
        }

    station_name = str(
        resolved[
            "station_name"
        ]
    )

    start_node = (
        resolved[
            "start_node"
        ]
    )

    end_node = (
        resolved[
            "end_node"
        ]
    )

    internal_path = (
        find_shortest_internal_path(
            station_name=station_name,
            start_node_id=str(
                start_node[
                    "id"
                ]
            ),
            end_node_id=str(
                end_node[
                    "id"
                ]
            ),
            blocked_edge_ids=(
                blocked_set
            ),
            mobility_constraints=(
                mobility_constraints
            ),
        )
    )

    required_facilities = (
        extract_required_facilities(
            internal_path
        )
    )

    return {
        "status": (
            internal_path.get(
                "status"
            )
        ),
        "mobility_constraints": (
            mobility_constraints
        ),
        "movement": (
            movement
        ),
        "blocked_edge_ids": (
            sorted(
                blocked_set
            )
        ),
        "node_resolution": (
            resolved
        ),
        "start_node": (
            start_node
        ),
        "end_node": (
            end_node
        ),
        "node_path": (
            internal_path.get(
                "node_path",
                [],
            )
        ),
        "edge_count": (
            internal_path.get(
                "edge_count",
                0,
            )
        ),
        "required_facility_count": (
            len(
                required_facilities
            )
        ),
        "required_facilities": (
            required_facilities
        ),
    }


# ==============================================================================
# 7. 이동 조건 + 실시간 EV/ES 기반 내부 경로 디버그
# ==============================================================================

@router.post(
    "/debug/realtime-safe-path"
)
async def debug_realtime_safe_path(
    payload: dict[str, Any],
) -> dict[str, Any]:
    """
    이동 조건과 실제 EV / ES 운행 상태를 반영하여
    역 내부 안전 경로를 계산합니다.

    운행 불가 시설이 발견되면 해당 edge를 차단하고
    자동으로 BFS를 다시 수행합니다.
    """

    movement = payload.get(
        "movement"
    )

    mobility_constraints = payload.get(
        "mobility_constraints",
        {},
    )

    if not isinstance(
        movement,
        dict,
    ):
        raise HTTPException(
            status_code=400,
            detail=(
                "movement는 객체(dict) 형태여야 합니다."
            ),
        )

    if not isinstance(
        mobility_constraints,
        dict,
    ):
        raise HTTPException(
            status_code=400,
            detail=(
                "mobility_constraints는 "
                "객체(dict) 형태여야 합니다."
            ),
        )

    try:
        result = (
            find_realtime_safe_internal_path(
                movement=movement,
                mobility_constraints=(
                    mobility_constraints
                ),
            )
        )

    except FileNotFoundError as error:
        raise HTTPException(
            status_code=500,
            detail=(
                "역 내부 그래프 파일을 "
                f"찾을 수 없습니다: {error}"
            ),
        ) from error

    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail=str(
                error
            ),
        ) from error

    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=(
                "실시간 역 내부 경로 계산 중 "
                f"오류가 발생했습니다: {error}"
            ),
        ) from error

    return result

# ==============================================================================
# 버스 GBIS 식별자 매칭 디버그
# ==============================================================================

@router.post(
    "/debug/bus-identifiers"
)
async def debug_bus_identifiers(
    payload: dict[str, Any],
) -> dict[str, Any]:
    """
    카카오 BUS step을 이용하여

    - 버스번호 -> GBIS routeId
    - 승차 정류장 -> GBIS stationId

    매칭 결과를 확인합니다.
    """

    step = payload.get("step")

    if not isinstance(step, dict):
        raise HTTPException(
            status_code=400,
            detail="step은 객체(dict) 형태여야 합니다.",
        )

    step_type = str(
        step.get("step_type", "")
    ).upper()

    if step_type != "BUS":
        raise HTTPException(
            status_code=400,
            detail="BUS step만 테스트할 수 있습니다.",
        )

    try:
        result = match_bus_step_identifiers(
            step
        )

    except FileNotFoundError as error:
        raise HTTPException(
            status_code=500,
            detail=str(error),
        ) from error

    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail=str(error),
        ) from error

    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=(
                "버스 식별자 매칭 중 "
                f"오류가 발생했습니다: {error}"
            ),
        ) from error

    return result

# ==============================================================================
# 실시간 저상버스 도착정보 디버그
# ==============================================================================

@router.get(
    "/debug/bus-arrival"
)
async def debug_bus_arrival(
    station_id: str,
    route_id: str,
    bus_number: str | None = None,
):
    """
    GBIS stationId와 routeId를 이용해
    해당 노선의 실시간 저상버스 도착정보를 확인합니다.
    """

    result = await get_low_floor_bus_status(
        station_id=station_id,
        route_id=route_id,
        bus_number=bus_number,
    )

    return result