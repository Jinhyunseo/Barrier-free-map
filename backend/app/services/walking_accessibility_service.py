from typing import Any


STAIR_KEYWORDS = {
    "계단",
    "stairs",
    "stair",
}

OVERPASS_KEYWORDS = {
    "육교",
    "보도육교",
    "overpass",
}


def analyze_walking_accessibility(
    walking_route: dict[str, Any] | None,
) -> dict[str, Any]:
    """
    TMAP 보행 경로의 instructions / segments를 분석해서
    보행 접근성 요소를 추출합니다.
    """

    if not walking_route:
        return {
            "status": "UNKNOWN",
            "has_stairs": None,
            "has_overpass": None,
            "detected_barriers": [],
        }

    detected_barriers: list[str] = []

    has_stairs = False
    has_overpass = False

    # 안내 문구 분석
    instructions = walking_route.get(
        "instructions",
        [],
    )

    if not isinstance(
        instructions,
        list,
    ):
        instructions = []

    for instruction in instructions:
        if not isinstance(
            instruction,
            dict,
        ):
            continue

        description = str(
            instruction.get(
                "description",
                "",
            )
        ).lower()

        if any(
            keyword in description
            for keyword in STAIR_KEYWORDS
        ):
            has_stairs = True

            if "계단" not in detected_barriers:
                detected_barriers.append(
                    "계단"
                )

        if any(
            keyword in description
            for keyword in OVERPASS_KEYWORDS
        ):
            has_overpass = True

            if "육교" not in detected_barriers:
                detected_barriers.append(
                    "육교"
                )

    # segment 정보도 함께 확인
    segments = walking_route.get(
        "segments",
        [],
    )

    if not isinstance(
        segments,
        list,
    ):
        segments = []

    for segment in segments:
        if not isinstance(
            segment,
            dict,
        ):
            continue

        description = str(
            segment.get(
                "description",
                "",
            )
        ).lower()

        road_name = str(
            segment.get(
                "road_name",
                "",
            )
        ).lower()

        combined_text = (
            f"{description} {road_name}"
        )

        if any(
            keyword in combined_text
            for keyword in STAIR_KEYWORDS
        ):
            has_stairs = True

            if "계단" not in detected_barriers:
                detected_barriers.append(
                    "계단"
                )

        if any(
            keyword in combined_text
            for keyword in OVERPASS_KEYWORDS
        ):
            has_overpass = True

            if "육교" not in detected_barriers:
                detected_barriers.append(
                    "육교"
                )

    return {
        "status": "ANALYZED",
        "has_stairs": has_stairs,
        "has_overpass": has_overpass,
        "detected_barriers": (
            detected_barriers
        ),
    }


def attach_walking_accessibility(
    route: dict[str, Any],
) -> dict[str, Any]:
    """
    walking_access의 first_mile / last_mile을 각각 분석해서
    route에 walking_accessibility를 추가합니다.
    """

    walking_access = route.get(
        "walking_access",
        {},
    )

    if not isinstance(
        walking_access,
        dict,
    ):
        walking_access = {}

    first_mile = walking_access.get(
        "first_mile"
    )

    last_mile = walking_access.get(
        "last_mile"
    )

    first_result = (
        analyze_walking_accessibility(
            first_mile
        )
    )

    last_result = (
        analyze_walking_accessibility(
            last_mile
        )
    )

    has_stairs = any(
        value is True
        for value in [
            first_result.get(
                "has_stairs"
            ),
            last_result.get(
                "has_stairs"
            ),
        ]
    )

    has_overpass = any(
        value is True
        for value in [
            first_result.get(
                "has_overpass"
            ),
            last_result.get(
                "has_overpass"
            ),
        ]
    )

    detected_barriers = list(
        dict.fromkeys(
            (
                first_result.get(
                    "detected_barriers",
                    [],
                )
                +
                last_result.get(
                    "detected_barriers",
                    [],
                )
            )
        )
    )

    route[
        "walking_accessibility"
    ] = {
        "first_mile": (
            first_result
        ),
        "last_mile": (
            last_result
        ),
        "has_stairs": (
            has_stairs
        ),
        "has_overpass": (
            has_overpass
        ),
        "detected_barriers": (
            detected_barriers
        ),
    }

    return route