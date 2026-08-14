# backend/app/data/station_graphs/seongnam.py

STATION_GRAPH_CONFIG = {
    "station_name": "성남역",

    # 1. 층 및 공간 구조
    "layout": {
        "spaces": [
            {
                "line_name": "경강선",
                "floor": "B2",
                "type": "CONCOURSE",  # B2 대합실
            },
            {
                "line_name": "경강선",
                "floor": "B3",
                "type": "PLATFORM",   # B3 승강장
            },
        ],

        # 1~5번 출구 정의
        "exits": [
            {
                "exit_no": str(exit_no),
                "line_name": "경강선",
                "concourse_floor": "B2",
            }
            for exit_no in range(1, 6)
        ],

        # 출구 보행 연결
        "exit_connections": [
            {
                "from_line": "경강선",
                "from_floor": "B2",
                "exit_no": str(exit_no),
                "transport_type": "WALKING",
                "wheelchair_accessible": True,
                "is_bidirectional": True,
                "detail_location": f"{exit_no}번 출구 통로",
            }
            for exit_no in range(1, 6)
        ],

        "transfers": [],
    },

    # 2. 방향별 승강장 키워드 매핑
    "directional_platforms": {
        ("경강선", "B3"): {
            "YEOJU": {
                "label": "여주 방향",
                "keywords": ["여주승강장", "여주행", "경강선역무실"],
            },
            "PANGYO": {
                "label": "판교 방향",
                "keywords": ["판교승강장", "판교행"],
            },
        },
    },

    # 3. 지상 엘리베이터 접근점 정의
    "ground_ev_access": {
        "1_4": {
            "label": "1·4번 출구 사이",
            "nearby_exit_nos": ["1", "4"],
            "keywords": ["1,4번출입구", "1,4번출구", "선큰", "1,4번"],
        },
        "5": {
            "label": "5번 출구 뒤",
            "nearby_exit_nos": ["5"],
            "keywords": ["5번출입구", "5번출구", "5번출입구뒤"],
        },
    },

    # 4. 수동 보정 간선 (지상 EV 수직 이동 + B2 대합실 내부 자유 이동 보장)
    "manual_edges": [
        # (1) 지상 1,4번 선큰 EV <-> B2 대합실 수직 연결
        {
            "id": "SNM_MANUAL_EV_1_4",
            "line_name": "경강선",
            "from_node": "SNM_1F_EV_ACCESS_1_4",
            "to_node": "SNM_경강선_B2_CONCOURSE",
            "transport_type": "ELEVATOR",
            "wheelchair_accessible": True,
            "is_bidirectional": True,
            "from_floor": "1F",
            "to_floor": "B2",
            "detail_location": "1,4번 출구 사이 선큰 엘리베이터 (지상 1F ↔ B2 대합실)",
            "description": "성남역 지상 1,4번 EV ↔ B2 대합실 수직 이동 간선",
        },
        # (2) B2 대합실 내부 수평 보행 이동 보장 (판교방면 EV 접근용)
        {
            "id": "SNM_MANUAL_WALK_B2_INTERNAL",
            "line_name": "경강선",
            "from_node": "SNM_경강선_B2_CONCOURSE",
            "to_node": "SNM_경강선_B3_PLATFORM_PANGYO",
            "transport_type": "ELEVATOR",  # B2 대합실 -> B3 판교승강장 EV 연결 보장
            "wheelchair_accessible": True,
            "is_bidirectional": True,
            "from_floor": "B2",
            "to_floor": "B3",
            "detail_location": "B2 대합실 ↔ 판교방면 승강장 엘리베이터",
            "description": "B2 대합실에서 B3 판교방면 승강장 연결 EV 간선",
        }
    ],
}