from __future__ import annotations

from typing import Any


STATION_LAYOUTS: dict[str, dict[str, Any]] = {
    "모란역": {
        "spaces": [
            # --------------------------------------------------
            # 8호선
            # --------------------------------------------------
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

            # --------------------------------------------------
            # 수인분당선
            # --------------------------------------------------
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

        # ------------------------------------------------------
        # 노선 간 환승
        # ------------------------------------------------------
        "transfers": [
            {
                "from_line": "8호선",
                "from_floor": "B1",
                "to_line": "수인분당선",
                "to_floor": "B1",
                "transport_type": "WALKING",
            },
        ],
    },
}