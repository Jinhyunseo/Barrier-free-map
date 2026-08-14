# backend/app/data/station_graphs/pangyo.py

STATION_GRAPH_CONFIG = {
    "station_name": "판교역",

    # 1. 층 및 공간 구조
    "layout": {
        "spaces": [
            # --- 신분당선 ---
            {
                "line_name": "신분당선",
                "floor": "B1",
                "type": "CONCOURSE",  # 신분당선 B1 환승주차장/대합실
            },
            {
                "line_name": "신분당선",
                "floor": "B2",
                "type": "CONCOURSE",  # 신분당선 B2 대합실
            },
            {
                "line_name": "신분당선",
                "floor": "B3",
                "type": "PLATFORM",   # 신분당선 B3 승강장
            },

            # --- 경강선 ---
            {
                "line_name": "경강선",
                "floor": "B2",
                "type": "CONCOURSE",  # 경강선 B2 대합실
            },
            {
                "line_name": "경강선",
                "floor": "B3",
                "type": "CONCOURSE",  # 경강선 B3 환승대합실
            },
            {
                "line_name": "경강선",
                "floor": "B4",
                "type": "PLATFORM",   # 경강선 B4 승강장
            },
        ],

        # 1~4번 출구 정의 (신분당선 B2 대합실 연결)
        "exits": [
            {
                "exit_no": str(exit_no),
                "line_name": "신분당선",
                "concourse_floor": "B2",
            }
            for exit_no in range(1, 5)
        ],

        # 출구 보행 연결
        "exit_connections": [
            {
                "from_line": "신분당선",
                "from_floor": "B2",
                "exit_no": str(exit_no),
                "transport_type": "WALKING",
                "wheelchair_accessible": True,
                "is_bidirectional": True,
                "detail_location": f"{exit_no}번 출구 통로",
            }
            for exit_no in range(1, 5)
        ],

        # 신분당선 <-> 경강선 환승 보행 연결 (B2 대합실 및 B3 환승층)
        "transfers": [
            {
                "from_line": "신분당선",
                "from_floor": "B2",
                "to_line": "경강선",
                "to_floor": "B2",
                "transport_type": "WALKING",
                "wheelchair_accessible": True,
                "is_bidirectional": True,
            },
            {
                "from_line": "신분당선",
                "from_floor": "B3",
                "to_line": "경강선",
                "to_floor": "B3",
                "transport_type": "WALKING",
                "wheelchair_accessible": True,
                "is_bidirectional": True,
            },
        ],
    },

    # 2. 노선별/방향별 승강장 키워드 매핑 (정밀 키워드 적용)
    "directional_platforms": {
        # [신분당선 B3 승강장]
        ("신분당선", "B3"): {
            "GANGNAM": {
                "label": "청계산입구/강남 방향",
                "keywords": ["2-1", "청계산입구방면(상행)승강장"],
            },
            "GWANGGYO": {
                "label": "정자/광교 방향",
                "keywords": ["5-4", "정자방면(하행)승강장"],
            },
        },
        # [경강선 B4 승강장]
        ("경강선", "B4"): {
            "YEOJU": {
                "label": "성남/이매/여주 방향",
                "keywords": ["이매역방향", "이매", "여주", "성남"],
            },
            "TERMINAL": {
                "label": "당역종착 방향",
                "keywords": ["당역종착"],
            },
        },
    },

    # 3. 지상 엘리베이터(EV) 접근 위치 매핑 (1F <-> B2 연결)
    "ground_ev_access": {
        "1": {
            "label": "1번 출구 옆",
            "nearby_exit_nos": ["1", "2"],
            "keywords": ["1번출입구", "1번출구"],
        },
        "3": {
            "label": "3번 출구 옆",
            "nearby_exit_nos": ["3", "4"],
            "keywords": ["3번출입구", "3번출구"],
        },
    },
}