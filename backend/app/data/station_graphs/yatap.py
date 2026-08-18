STATION_GRAPH_CONFIG = {
    "station_name": "야탑역",

    "layout": {
        "spaces": [
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
            {
                "exit_no": str(exit_no),
                "line_name": "수인분당선",
                "concourse_floor": "B1",
            }
            for exit_no in range(1, 5)
        ],
        "transfers": [],
    },

    "directional_platforms": {
        ("수인분당선", "B2"): {
            "MORAN": {
                "label": "모란 방향",
                "keywords": ["왕십리", "청량리", "모란"],
            },
            "IMAE": {
                "label": "이매 방향",
                "keywords": ["죽전", "고색", "인천", "이매"],
            },
        },
    },

    "ground_ev_access": {
        "1_2": {
            "label": "1·2번 출구 사이",
            "nearby_exit_nos": ["1", "2"],
            "keywords": [
                "1,2번출구중간",
                "1,2번출입구중간",
            ],
        },
        "3_4": {
            "label": "3·4번 출구 사이",
            "nearby_exit_nos": ["3", "4"],
            "keywords": [
                "3,4번출구중간",
                "3,4번출입구중간",
            ],
        },
    },

    # KRIC 통합 데이터의 야탑역 ES 목록은 실제 구조 검증 결과 계단.
    "facility_type_overrides": {
        "ESCALATOR": "STAIR",
    },

    # 계단 원천 레코드 10개를 시설 단위로 보존.
    "preserve_facility_records": {
        "STAIR": True,
    },
}
