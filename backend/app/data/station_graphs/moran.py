# backend/app/data/station_graphs/moran.py
#
# 모란역 실제 역사 구조도 + KRIC 시설 데이터 + 직접 검증 내용을
# 기준으로 작성한 역별 그래프 설정입니다.
#
# 원칙:
# - 구조도에서 확인한 물리 구조를 우선합니다.
# - KRIC의 EV/ES 데이터는 builder가 자동으로 시설 간선으로 변환합니다.
# - KRIC에 없는 계단/환승 연결은 manual_edges로 보강합니다.
# - 수인분당선 B2는 진행 방향별 승강장 노드로 분리합니다.

STATION_GRAPH_CONFIG = {
    "station_name": "모란역",

    # ==================================================================
    # 1. 물리 공간 / 출구
    # ==================================================================
    "layout": {
        "spaces": [
            # 8호선
            {
                "line_name": "8호선",
                "floor": "B1",
                "type": "CONCOURSE",
            },
            {
                "line_name": "8호선",
                "floor": "B2",
                "type": "CONCOURSE",
            },
            {
                "line_name": "8호선",
                "floor": "B3",
                "type": "PLATFORM",
            },

            # 수인분당선
            {
                "line_name": "수인분당선",
                "floor": "B1",
                "type": "CONCOURSE",
            },
            {
                "line_name": "수인분당선",
                "floor": "B2",
                "type": "PLATFORM",
            },
        ],

        "exits": [
            # 수인분당선 측 1~8번
            *[
                {
                    "exit_no": str(exit_no),
                    "line_name": "수인분당선",
                    "concourse_floor": "B1",
                }
                for exit_no in range(1, 9)
            ],

            # 8호선 측 9~12번
            *[
                {
                    "exit_no": str(exit_no),
                    "line_name": "8호선",
                    "concourse_floor": "B1",
                }
                for exit_no in range(9, 13)
            ],
        ],

        # 구조도에서 확정한 지상 ↔ B1 연결.
        # ES는 KRIC에서도 생성되지만 동일 연결은 layout 추가 과정에서
        # 중복 방지되므로 실제 구조 명세를 여기에도 남깁니다.
        "exit_connections": [
            # 수인분당선 1~8
            {
                "from_line": "수인분당선",
                "from_floor": "B1",
                "exit_no": "1",
                "transport_type": "STAIR",
                "wheelchair_accessible": False,
                "is_bidirectional": True,
                "detail_location": "1번 출구 ↔ 수인분당선 B1 계단",
            },
            {
                "from_line": "수인분당선",
                "from_floor": "B1",
                "exit_no": "2",
                "transport_type": "ESCALATOR",
                "wheelchair_accessible": False,
                "is_bidirectional": True,
                "detail_location": "2번 출구 ↔ 수인분당선 B1 에스컬레이터",
            },
            {
                "from_line": "수인분당선",
                "from_floor": "B1",
                "exit_no": "3",
                "transport_type": "STAIR",
                "wheelchair_accessible": False,
                "is_bidirectional": True,
                "detail_location": "3번 출구 ↔ 수인분당선 B1 계단",
            },
            {
                "from_line": "수인분당선",
                "from_floor": "B1",
                "exit_no": "4",
                "transport_type": "ESCALATOR",
                "wheelchair_accessible": False,
                "is_bidirectional": True,
                "detail_location": "4번 출구 ↔ 수인분당선 B1 에스컬레이터",
            },
            {
                "from_line": "수인분당선",
                "from_floor": "B1",
                "exit_no": "5",
                "transport_type": "ESCALATOR",
                "wheelchair_accessible": False,
                "is_bidirectional": True,
                "detail_location": "5번 출구 ↔ 수인분당선 B1 에스컬레이터",
            },
            {
                "from_line": "수인분당선",
                "from_floor": "B1",
                "exit_no": "6",
                "transport_type": "STAIR",
                "wheelchair_accessible": False,
                "is_bidirectional": True,
                "detail_location": "6번 출구 ↔ 수인분당선 B1 계단",
            },
            {
                "from_line": "수인분당선",
                "from_floor": "B1",
                "exit_no": "7",
                "transport_type": "ESCALATOR",
                "wheelchair_accessible": False,
                "is_bidirectional": True,
                "detail_location": "7번 출구 ↔ 수인분당선 B1 에스컬레이터",
            },
            {
                "from_line": "수인분당선",
                "from_floor": "B1",
                "exit_no": "8",
                "transport_type": "STAIR",
                "wheelchair_accessible": False,
                "is_bidirectional": True,
                "detail_location": "8번 출구 ↔ 수인분당선 B1 계단",
            },

            # 8호선 9~12
            {
                "from_line": "8호선",
                "from_floor": "B1",
                "exit_no": "9",
                "transport_type": "STAIR",
                "wheelchair_accessible": False,
                "is_bidirectional": True,
                "detail_location": "9번 출구 ↔ 8호선 B1 계단",
            },
            {
                "from_line": "8호선",
                "from_floor": "B1",
                "exit_no": "10",
                "transport_type": "STAIR",
                "wheelchair_accessible": False,
                "is_bidirectional": True,
                "detail_location": "10번 출구 ↔ 8호선 B1 계단",
            },
            {
                "from_line": "8호선",
                "from_floor": "B1",
                "exit_no": "11",
                "transport_type": "STAIR",
                "wheelchair_accessible": False,
                "is_bidirectional": True,
                "detail_location": "11번 출구 ↔ 8호선 B1 계단",
            },
            {
                "from_line": "8호선",
                "from_floor": "B1",
                "exit_no": "12",
                "transport_type": "STAIR",
                "wheelchair_accessible": False,
                "is_bidirectional": True,
                "detail_location": "12번 출구 ↔ 8호선 B1 계단",
            },
        ],

        # 복잡한 환승 구조는 아래 manual_edges에서 방향별로 명시합니다.
        "transfers": [],
    },

    # ==================================================================
    # 2. 수인분당선 방향별 승강장
    # ==================================================================
    "directional_platforms": {
        ("수인분당선", "B2"): {
            "YATAB": {
                "label": "야탑 방향",
                "keywords": [
                    "야탑역방향",
                    "야탑역 방향",
                    "야탑 방향",
                    "야탑",
                ],
            },
            "TAEPYEONG": {
                "label": "태평 방향",
                "keywords": [
                    "태평역방향",
                    "태평역 방향",
                    "태평 방향",
                    "태평",
                ],
            },
        },
    },

    # 11번 출구 EV는 KRIC에 exitNo=11이 명시되어 있어
    # 별도의 ACCESSIBLE_ENTRANCE 보정이 필요하지 않습니다.
    "ground_ev_access": {},

    # ==================================================================
    # 3. 구조도 검증 수동 간선
    # ==================================================================
    #
    # KRIC에 없는 계단과 환승 연결을 실제 구조도에 맞춰 추가합니다.
    # 같은 두 노드를 연결하더라도 위치가 다른 계단은 별도 edge입니다.
    #
    "manual_edges": [
        # --------------------------------------------------------------
        # 수인분당선 B1 ↔ B2 야탑 방향: 계단 3개
        # --------------------------------------------------------------
        {
            "id": "MRN_K1_STAIR_YATAB_01",
            "line_name": "수인분당선",
            "from_node": "MRN_수인분당선_B1_CONCOURSE",
            "to_node": "MRN_수인분당선_B2_PLATFORM_YATAB",
            "transport_type": "STAIR",
            "wheelchair_accessible": False,
            "is_bidirectional": True,
            "detail_location": "B1 3번 출구 방향 ↔ B2 야탑 방향 승강장",
            "description": "모란역 수인분당선 야탑 방향 3번 출구 측 계단",
            "source": "STATION_MAP_VERIFIED",
        },
        {
            "id": "MRN_K1_STAIR_YATAB_02",
            "line_name": "수인분당선",
            "from_node": "MRN_수인분당선_B1_CONCOURSE",
            "to_node": "MRN_수인분당선_B2_PLATFORM_YATAB",
            "transport_type": "STAIR",
            "wheelchair_accessible": False,
            "is_bidirectional": True,
            "detail_location": "B1 1·2번 출구 방향 ↔ B2 야탑 방향 승강장 계단 1",
            "description": "모란역 수인분당선 야탑 방향 1·2번 출구 측 계단 1",
            "source": "STATION_MAP_VERIFIED",
        },
        {
            "id": "MRN_K1_STAIR_YATAB_03",
            "line_name": "수인분당선",
            "from_node": "MRN_수인분당선_B1_CONCOURSE",
            "to_node": "MRN_수인분당선_B2_PLATFORM_YATAB",
            "transport_type": "STAIR",
            "wheelchair_accessible": False,
            "is_bidirectional": True,
            "detail_location": "B1 1·2번 출구 방향 ↔ B2 야탑 방향 승강장 계단 2",
            "description": "모란역 수인분당선 야탑 방향 1·2번 출구 측 계단 2",
            "source": "STATION_MAP_VERIFIED",
        },

        # --------------------------------------------------------------
        # KRIC 방향 판별 누락 보강: B1 → B2 하행 에스컬레이터 2개
        # --------------------------------------------------------------
        # 원천 KRIC 레코드의 B1 측 dtlLoc에는 "야탑"/"태평" 키워드가 없어
        # builder가 방향별 승강장을 판별하지 못하므로 역별 설정에서 보강합니다.
        {
            "id": "MRN_K1_ES_YATAB_DOWN",
            "line_name": "수인분당선",
            "from_node": "MRN_수인분당선_B1_CONCOURSE",
            "to_node": "MRN_수인분당선_B2_PLATFORM_YATAB",
            "transport_type": "ESCALATOR",
            "wheelchair_accessible": False,
            "is_bidirectional": False,
            "direction": "DOWN",
            "direction_name": "하행",
            "detail_location": "(B1) 3번/4번 출입구 방향 표내는 곳",
            "description": "모란역 수인분당선 B1 → B2 야탑 방향 하행 에스컬레이터",
            "operator_code": "KR",
            "line_code": "K1",
            "kric_station_code": "K225",
            "verification_status": "VERIFIED",
            "source": "KRIC_DIRECTION_PATCH",
        },
        {
            "id": "MRN_K1_ES_TAEPYEONG_DOWN",
            "line_name": "수인분당선",
            "from_node": "MRN_수인분당선_B1_CONCOURSE",
            "to_node": "MRN_수인분당선_B2_PLATFORM_TAEPYEONG",
            "transport_type": "ESCALATOR",
            "wheelchair_accessible": False,
            "is_bidirectional": False,
            "direction": "DOWN",
            "direction_name": "하행",
            "detail_location": "(B1) 5번/6번 출입구 방향 표내는 곳",
            "description": "모란역 수인분당선 B1 → B2 태평 방향 하행 에스컬레이터",
            "operator_code": "KR",
            "line_code": "K1",
            "kric_station_code": "K225",
            "verification_status": "VERIFIED",
            "source": "KRIC_DIRECTION_PATCH",
        },

        # --------------------------------------------------------------
        # 수인분당선 B1 ↔ B2 태평 방향: 일반 접근 계단 3개
        # --------------------------------------------------------------
        {
            "id": "MRN_K1_STAIR_TAEPYEONG_01",
            "line_name": "수인분당선",
            "from_node": "MRN_수인분당선_B1_CONCOURSE",
            "to_node": "MRN_수인분당선_B2_PLATFORM_TAEPYEONG",
            "transport_type": "STAIR",
            "wheelchair_accessible": False,
            "is_bidirectional": True,
            "detail_location": "B1 6번 출구 방향 ↔ B2 태평 방향 승강장",
            "description": "모란역 수인분당선 태평 방향 6번 출구 측 계단",
            "source": "STATION_MAP_VERIFIED",
        },
        {
            "id": "MRN_K1_STAIR_TAEPYEONG_02",
            "line_name": "수인분당선",
            "from_node": "MRN_수인분당선_B1_CONCOURSE",
            "to_node": "MRN_수인분당선_B2_PLATFORM_TAEPYEONG",
            "transport_type": "STAIR",
            "wheelchair_accessible": False,
            "is_bidirectional": True,
            "detail_location": "B1 7·8번 출구 방향 ↔ B2 태평 방향 승강장 계단 1",
            "description": "모란역 수인분당선 태평 방향 7·8번 출구 측 계단 1",
            "source": "STATION_MAP_VERIFIED",
        },
        {
            "id": "MRN_K1_STAIR_TAEPYEONG_03",
            "line_name": "수인분당선",
            "from_node": "MRN_수인분당선_B1_CONCOURSE",
            "to_node": "MRN_수인분당선_B2_PLATFORM_TAEPYEONG",
            "transport_type": "STAIR",
            "wheelchair_accessible": False,
            "is_bidirectional": True,
            "detail_location": "B1 7·8번 출구 방향 ↔ B2 태평 방향 승강장 계단 2",
            "description": "모란역 수인분당선 태평 방향 7·8번 출구 측 계단 2",
            "source": "STATION_MAP_VERIFIED",
        },


        # --------------------------------------------------------------
        # 8호선 일반 계단 연결
        # --------------------------------------------------------------
        # 구조도상 B2 대합실과 B3 승강장 사이 일반 계단 연결은
        # 확실하므로 위상 연결 1개를 둡니다.
        # 정확한 물리 계단 개수까지 검증되면 같은 형식으로 추가 가능합니다.
        {
            "id": "MRN_LINE8_STAIR_B2_B3_TOPOLOGY",
            "line_name": "8호선",
            "from_node": "MRN_8호선_B2_CONCOURSE",
            "to_node": "MRN_8호선_B3_PLATFORM",
            "transport_type": "STAIR",
            "wheelchair_accessible": False,
            "is_bidirectional": True,
            "detail_location": "8호선 B2 대합실 ↔ B3 승강장 일반 계단",
            "description": "모란역 8호선 B2↔B3 계단 연결",
            "verification_status": "TOPOLOGY_VERIFIED_COUNT_PENDING",
            "source": "STATION_MAP",
        },

        # --------------------------------------------------------------
        # 환승 동선
        # --------------------------------------------------------------
        # 구조도상 8호선 승강장 끝 환승 동선에서 수인분당선으로 연결.
        {
            "id": "MRN_TRANSFER_LINE8_TO_K1_YATAB",
            "line_name": None,
            "from_node": "MRN_8호선_B3_PLATFORM",
            "to_node": "MRN_수인분당선_B2_PLATFORM_YATAB",
            "transport_type": "WALKING",
            "wheelchair_accessible": True,
            "is_bidirectional": True,
            "detail_location": "8호선 승강장 끝 환승통로 ↔ 수인분당선 야탑 방향",
            "description": "모란역 8호선 ↔ 수인분당선 야탑 방향 환승 보행 연결",
            "verification_status": "TOPOLOGY_VERIFIED",
            "source": "STATION_MAP",
        },

        # 태평 방향은 환승 측 계단이 존재하므로 별도 계단 연결로 표현.
        {
            "id": "MRN_TRANSFER_LINE8_TO_K1_TAEPYEONG",
            "line_name": None,
            "from_node": "MRN_8호선_B3_PLATFORM",
            "to_node": "MRN_수인분당선_B2_PLATFORM_TAEPYEONG",
            "transport_type": "STAIR",
            "wheelchair_accessible": False,
            "is_bidirectional": True,
            "detail_location": "8호선 환승 측 ↔ 수인분당선 태평 방향 승강장",
            "description": "모란역 8호선 ↔ 수인분당선 태평 방향 환승 계단",
            "verification_status": "TOPOLOGY_VERIFIED",
            "source": "STATION_MAP_VERIFIED",
        },
    ],
}
