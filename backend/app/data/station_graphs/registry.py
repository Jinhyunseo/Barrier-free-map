from __future__ import annotations

from typing import Any

from .moran import STATION_GRAPH_CONFIG as MORAN_CONFIG
from .yatap import STATION_GRAPH_CONFIG as YATAP_CONFIG
from .seongnam import STATION_GRAPH_CONFIG as SEONGNAM_CONFIG  # 성남역 불러오기
from .pangyo import STATION_GRAPH_CONFIG as PANGYO_CONFIG      # 1. 판교역 불러오기


STATION_GRAPH_CONFIGS: dict[str, dict[str, Any]] = {
    MORAN_CONFIG["station_name"]: MORAN_CONFIG,
    YATAP_CONFIG["station_name"]: YATAP_CONFIG,
    SEONGNAM_CONFIG["station_name"]: SEONGNAM_CONFIG,  # 성남역 등록하기
    PANGYO_CONFIG["station_name"]: PANGYO_CONFIG,      # 2. 판교역 등록하기
}



def get_station_graph_config(
    station_name: str,
) -> dict[str, Any]:

    return STATION_GRAPH_CONFIGS.get(
        station_name,
        {},
    )