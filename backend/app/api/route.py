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

        "user_type": (
            request.user_type
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
    6. 사용자 유형 제약 적용
    7. 실제 EV / ES 실시간 상태 조회
    8. 고장 시설 발견 시 해당 edge 차단
    9. 역 내부 우회 경로 재탐색
    10. Hard Barrier 검사
    11. 사용자별 불편 점수 계산
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
    # → 사용자 유형 제약
    # → 실시간 EV / ES
    # → 고장 시설 우회
    # → Hard Barrier
    # → Soft Score
    # → 최종 추천
    #
    # 순으로 처리됩니다.
    # ==========================================================================

    try:
        recommendation_result = (
            select_best_candidate(
                routes=routes,
                user_type=request.user_type,
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
    movement: dict[str, Any],
) -> dict[str, Any]:
    """
    station_movement 하나의
    기본 역 내부 경로를 테스트합니다.

    실시간 상태는 반영하지 않습니다.
    """

    return (
        analyze_station_movement(
            movement
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
    사용자 유형 제약을 반영해 BFS를 수행합니다.
    """

    movement = (
        payload.get(
            "movement"
        )
    )

    blocked_edge_ids = (
        payload.get(
            "blocked_edge_ids",
            [],
        )
    )

    user_type = (
        payload.get(
            "user_type"
        )
    )

    # --------------------------------------------------------------------------
    # 입력 검증
    # --------------------------------------------------------------------------

    if not isinstance(
        movement,
        dict,
    ):
        raise HTTPException(
            status_code=400,
            detail=(
                "movement는 "
                "객체(dict) 형태여야 합니다."
            ),
        )

    if not isinstance(
        blocked_edge_ids,
        list,
    ):
        raise HTTPException(
            status_code=400,
            detail=(
                "blocked_edge_ids는 "
                "list 형태여야 합니다."
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

    # --------------------------------------------------------------------------
    # 시작 / 종료 노드 결정
    # --------------------------------------------------------------------------

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

            "user_type": (
                user_type
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

    # --------------------------------------------------------------------------
    # BFS
    # --------------------------------------------------------------------------

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

            user_type=(
                str(
                    user_type
                )
                if user_type
                else None
            ),
        )
    )

    # --------------------------------------------------------------------------
    # EV / ES 추출
    # --------------------------------------------------------------------------

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

        "user_type": (
            user_type
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
# 7. 사용자 유형 + 실시간 EV/ES 기반 내부 경로 디버그
# ==============================================================================

@router.post(
    "/debug/realtime-safe-path"
)
async def debug_realtime_safe_path(
    payload: dict[str, Any],
) -> dict[str, Any]:
    """
    사용자 유형과 실제 EV / ES 운행 상태를 반영하여
    역 내부 안전 경로를 계산합니다.

    운행 불가 시설이 발견되면 해당 edge를 차단하고
    자동으로 BFS를 다시 수행합니다.
    """

    movement = (
        payload.get(
            "movement"
        )
    )

    user_type = (
        payload.get(
            "user_type"
        )
    )

    if not isinstance(
        movement,
        dict,
    ):
        raise HTTPException(
            status_code=400,
            detail=(
                "movement는 "
                "객체(dict) 형태여야 합니다."
            ),
        )

    try:
        result = (
            find_realtime_safe_internal_path(
                movement=movement,

                user_type=(
                    str(
                        user_type
                    )
                    if user_type
                    else None
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