from __future__ import annotations

from typing import Iterable

from app.schemas.v2 import MobilityCondition, PreferenceOption


# Legacy station-path engine currently needs one of these three profiles.
# The public API no longer exposes a user type; this is a temporary compatibility layer.
def resolve_legacy_profile(conditions: Iterable[MobilityCondition]) -> str:
    conditions = set(conditions)
    if MobilityCondition.NEED_LOW_BUS in conditions or MobilityCondition.AVOID_STAIRS in conditions:
        return "WHEELCHAIR"
    if MobilityCondition.PREFER_ELEVATOR in conditions:
        return "ELDERLY"
    return "STROLLER"


def condition_exclusion_reasons(route: dict, conditions: set[MobilityCondition]) -> list[str]:
    accessibility = route.get("accessibility") or {}
    reasons: list[str] = []

    if MobilityCondition.AVOID_STAIRS in conditions and accessibility.get("has_stairs") is True:
        reasons.append("계단 제외 조건을 만족하지 않습니다.")

    if MobilityCondition.AVOID_STEEP_INCLINE in conditions:
        if accessibility.get("has_steep_slope") is True:
            reasons.append("급경사 제외 조건을 만족하지 않습니다.")
        incline = accessibility.get("max_incline")
        if incline is not None:
            try:
                if float(incline) > 8.3:
                    reasons.append(f"허용 경사도(8.3%)를 초과합니다: {float(incline):.1f}%")
            except (TypeError, ValueError):
                pass

    if MobilityCondition.AVOID_OBSTACLE_STEP in conditions:
        curb = accessibility.get("max_curb_height")
        if curb is not None:
            try:
                if float(curb) > 3.0:
                    reasons.append(f"허용 보도 턱(3cm)을 초과합니다: {float(curb):.1f}cm")
            except (TypeError, ValueError):
                pass

    if MobilityCondition.NEED_LOW_BUS in conditions:
        has_bus = any(
            "bus" in str(step.get("step_type", "")).lower() or "버스" in str(step.get("step_type", ""))
            for step in route.get("steps", [])
            if isinstance(step, dict)
        )
        if has_bus and accessibility.get("has_low_floor_bus") is not True:
            reasons.append("저상버스 이용이 확인되지 않은 경로입니다.")

    if MobilityCondition.AVOID_GENERAL_BUS in conditions:
        if any(
            "bus" in str(step.get("step_type", "")).lower() and "low" not in str(step.get("step_type", "")).lower()
            for step in route.get("steps", [])
            if isinstance(step, dict)
        ):
            if accessibility.get("has_low_floor_bus") is not True:
                reasons.append("일반 버스가 포함된 경로입니다.")

    return list(dict.fromkeys(reasons))


def preference_sort_key(route: dict, preference: PreferenceOption):
    evaluation = route.get("evaluation") or {}
    accessibility = route.get("accessibility") or {}
    score = evaluation.get("score")

    def num(value, default=10**9):
        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    if preference == PreferenceOption.TIME_FIRST:
        return (num(route.get("total_time_minutes")), num(score))
    if preference == PreferenceOption.MIN_WALK:
        return (num(route.get("total_walk_distance_meters")), num(score))
    if preference == PreferenceOption.MIN_TRANSFER:
        return (num(route.get("transfer_count")), num(score))

    # Balanced: legacy accessibility score is the base, with elevator preference as a bonus.
    bonus = 0
    if accessibility.get("has_elevator") is True:
        bonus -= 10
    return (num(score) + bonus, num(route.get("total_time_minutes")))
