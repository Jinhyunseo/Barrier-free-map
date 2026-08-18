from __future__ import annotations

import asyncio
import json
import logging
import os
from typing import Any

from pydantic import BaseModel

try:
    from google import genai
    from google.genai import types as genai_types
except ImportError:  # pragma: no cover - SDK가 설치되지 않은 환경 방어
    genai = None
    genai_types = None

logger = logging.getLogger(__name__)

# ==============================================================================
# 1. 모델 및 기본 설정
# ==============================================================================

# 💡 응답 속도가 가장 빠르고 안정적인 표준 모델 적용
GEMINI_MODEL_NAME = "gemini-3.5-flash-lite"
GEMINI_FALLBACK_MODEL_NAME = "gemini-3.5-flash"

# 💡 단일 요청 타임아웃을 15초로 설정
GEMINI_TIMEOUT_SECONDS = 15.0

FALLBACK_RECOMMEND_REASON = "이동시간, 도보 거리, 환승 횟수를 종합적으로 고려하여 이 경로를 추천드립니다."
FALLBACK_SLOPE_WARNING = "이 경로에는 급경사 구간이 포함되어 있어요. 천천히, 안전에 유의하며 이동해주세요."


class RouteAiText(BaseModel):
    """Gemini에게 강제할 JSON 응답 스키마."""

    recommend_reason: str
    slope_warning: str | None = None


# ==============================================================================
# 2. 클라이언트 초기화 (지연 초기화 + 실패 시 None 반환)
# ==============================================================================

_client: "genai.Client | None" = None
_client_init_attempted = False


def _get_client() -> "genai.Client | None":
    """GEMINI_API_KEY가 없거나 클라이언트 생성에 실패하면 None을 반환한다."""
    global _client, _client_init_attempted

    if _client is not None:
        return _client
    if _client_init_attempted:
        return None
    _client_init_attempted = True

    if genai is None:
        logger.warning("google-genai 패키지가 설치되어 있지 않아 AI 문구 생성을 건너뜁니다.")
        return None

    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        logger.warning(".env에 GEMINI_API_KEY가 없어 AI 문구 생성을 건너뜁니다. Fallback 문구를 사용합니다.")
        return None

    try:
        _client = genai.Client(api_key=api_key)
    except Exception:
        logger.exception("Gemini 클라이언트 초기화에 실패했습니다.")
        _client = None

    return _client


# ==============================================================================
# 3. 시스템 프롬프트
# ==============================================================================

SYSTEM_INSTRUCTION = """\
당신은 교통약자를 위한 배리어프리 길안내 서비스의 안내 문구 작성 담당자입니다.
사용자는 아래 5가지 개별 이동조건 중 하나 이상을 선택했을 수 있습니다. 각 조건의 의미는 다음과 같습니다.

- avoid_stairs: 계단 이용이 어려운 사용자입니다. 계단이 없는 경로인지가 중요합니다.
- require_elevator: 엘리베이터가 반드시 필요한 사용자입니다. 역 내부 이동 시 엘리베이터 이용 가능 여부가 중요합니다.
- avoid_escalator: 에스컬레이터 이용이 어려운 사용자입니다. 에스컬레이터를 타지 않아도 되는지가 중요합니다.
- avoid_steep_slope: 급경사(8% 이상 경사로)를 피하고 싶은 사용자입니다.
- require_low_floor_bus: 저상버스가 반드시 필요한 사용자입니다. 버스 구간이 있다면 저상버스 확인 여부가 중요합니다.

당신의 임무는 입력으로 주어지는 [경로 정보] JSON만 근거로 삼아 아래 두 문구를 작성하는 것입니다. 입력에 없는 사실을 지어내지 마세요.

1. recommend_reason (사이드바에 표시될 "이 경로를 추천하는 이유")
   - 선택된 이동조건과 실제로 관련된 경로의 장점을 중심으로, 이용자가 안심할 수 있도록 안내합니다.
   - 1~2문장, 최대 60자 내외의 간결한 존댓말.

2. slope_warning (급경사 피하기 옵션을 켰는데도 경로에 급경사가 포함된 경우에만 표시되는 경고 팝업 문구)
   - 입력의 "slope_warning_needed" 값이 true일 때만 작성하고, false이면 반드시 null을 반환합니다.
   - 다정하고 안심시키는 톤으로 실제 최대 경사도 수치를 자연스럽게 포함합니다. 최대 80자 내외.

반드시 아래 JSON 스키마로만 응답하세요.
{"recommend_reason": string, "slope_warning": string | null}
"""


# ==============================================================================
# 4. Few-shot 예시 & Payload 변환
# ==============================================================================

def _example_turn(user_payload: dict[str, Any], model_payload: dict[str, Any]) -> list["genai_types.Content"]:
    return [
        genai_types.Content(
            role="user",
            parts=[genai_types.Part.from_text(text=_dumps(user_payload))],
        ),
        genai_types.Content(
            role="model",
            parts=[genai_types.Part.from_text(text=_dumps(model_payload))],
        ),
    ]


def _dumps(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False)


def _build_few_shot_examples() -> list["genai_types.Content"]:
    examples: list["genai_types.Content"] = []

    examples += _example_turn(
        user_payload={
            "mobility_constraints": {
                "avoid_stairs": True,
                "require_elevator": True,
                "avoid_escalator": False,
                "avoid_steep_slope": False,
                "require_low_floor_bus": False,
            },
            "route_preference": "BALANCED",
            "total_time_minutes": 24,
            "total_walk_distance_meters": 320,
            "transfer_count": 1,
            "has_elevator": True,
            "has_stairs": False,
            "has_low_floor_bus": None,
            "has_steep_slope": False,
            "slope_warning_needed": False,
            "max_slope_percent": None,
            "slope_spot_count": 0,
        },
        model_payload={
            "recommend_reason": "환승역에서 엘리베이터로 이동할 수 있고 계단 구간이 없어 편안하게 이용하실 수 있어요.",
            "slope_warning": None,
        },
    )

    examples += _example_turn(
        user_payload={
            "mobility_constraints": {
                "avoid_stairs": False,
                "require_elevator": False,
                "avoid_escalator": False,
                "avoid_steep_slope": True,
                "require_low_floor_bus": False,
            },
            "route_preference": "MIN_WALKING",
            "total_time_minutes": 12,
            "total_walk_distance_meters": 1000,
            "transfer_count": 0,
            "has_elevator": None,
            "has_stairs": None,
            "has_low_floor_bus": None,
            "has_steep_slope": True,
            "slope_warning_needed": True,
            "max_slope_percent": 23.7,
            "slope_spot_count": 3,
        },
        model_payload={
            "recommend_reason": "도보 거리가 가장 짧고 환승 없이 바로 이동할 수 있는 경로예요.",
            "slope_warning": "이 근처는 지형상 완만한 길을 찾기 어려워요. 경사가 있는 구간(최대 23.7%)이 포함되어 있으니, 난간이나 벽을 짚으며 천천히 이동해주세요.",
        },
    )

    return examples


def _build_route_payload(
    route: dict[str, Any],
    mobility_constraints: dict[str, bool],
    route_preference: str,
    slope_warning_needed: bool,
    max_slope_percent: float | None,
    slope_spot_count: int,
) -> dict[str, Any]:
    accessibility = route.get("accessibility", {}) or {}

    return {
        "mobility_constraints": mobility_constraints,
        "route_preference": route_preference,
        "total_time_minutes": route.get("total_travel_time_minutes") or route.get("total_time_minutes"),
        "total_walk_distance_meters": route.get("total_walk_distance_meters"),
        "transfer_count": route.get("transfer_count"),
        "has_elevator": accessibility.get("has_elevator"),
        "has_stairs": accessibility.get("has_stairs"),
        "has_low_floor_bus": accessibility.get("has_low_floor_bus"),
        "low_floor_bus_numbers": accessibility.get("low_floor_bus_numbers") or [],
        "has_steep_slope": bool(slope_spot_count > 0),
        "slope_warning_needed": slope_warning_needed,
        "max_slope_percent": max_slope_percent,
        "slope_spot_count": slope_spot_count,
    }


# ==============================================================================
# 5. 메인 함수
# ==============================================================================

async def generate_route_ai_text(
    route: dict[str, Any],
    mobility_constraints: dict[str, bool],
    route_preference: str,
    slope_warning_needed: bool,
    max_slope_percent: float | None,
    slope_spot_count: int,
) -> dict[str, str | None]:

    fallback = {
        "recommend_reason": FALLBACK_RECOMMEND_REASON,
        "slope_warning": FALLBACK_SLOPE_WARNING if slope_warning_needed else None,
    }

    client = _get_client()
    if client is None:
        return fallback

    try:
        payload = _build_route_payload(
            route=route,
            mobility_constraints=mobility_constraints,
            route_preference=route_preference,
            slope_warning_needed=slope_warning_needed,
            max_slope_percent=max_slope_percent,
            slope_spot_count=slope_spot_count,
        )

        contents = _build_few_shot_examples() + [
            genai_types.Content(
                role="user",
                parts=[genai_types.Part.from_text(text=_dumps(payload))],
            )
        ]

        config = genai_types.GenerateContentConfig(
            system_instruction=SYSTEM_INSTRUCTION,
            response_mime_type="application/json",
            response_schema=RouteAiText,
            temperature=0.3,
            max_output_tokens=300,
            http_options=genai_types.HttpOptions(timeout=int(GEMINI_TIMEOUT_SECONDS * 1000)),
        )

        response = None
        # 1차 경량 모델 시도 -> 실패 시 2차 표준 모델 순차 시도
        for model_name in [GEMINI_MODEL_NAME, GEMINI_FALLBACK_MODEL_NAME]:
            try:
                response = await client.aio.models.generate_content(
                    model=model_name,
                    contents=contents,
                    config=config,
                )
                if response:
                    break
            except Exception as req_err:
                logger.warning("모델 [%s] 호출 지연/오류: %s. 다음 모델 시도.", model_name, req_err)
                continue

        if not response:
            return fallback

        recommend_reason = None
        slope_warning = None

        # SDK 자동 파싱 객체(response.parsed) 우선 읽기
        if hasattr(response, "parsed") and response.parsed is not None:
            recommend_reason = getattr(response.parsed, "recommend_reason", None)
            slope_warning = getattr(response.parsed, "slope_warning", None)

        # response.text 수동 파싱
        raw_text = getattr(response, "text", None)
        if recommend_reason is None and isinstance(raw_text, str) and raw_text.strip():
            try:
                cleaned_text = raw_text.strip().replace("```json", "").replace("```", "").strip()
                data = json.loads(cleaned_text)
                if isinstance(data, dict):
                    recommend_reason = data.get("recommend_reason")
                    slope_warning = data.get("slope_warning")
            except Exception:
                pass

        recommend_reason = (recommend_reason or "").strip() or FALLBACK_RECOMMEND_REASON

        if slope_warning_needed:
            slope_warning = (slope_warning or "").strip() if slope_warning else FALLBACK_SLOPE_WARNING
        else:
            slope_warning = None

        return {
            "recommend_reason": recommend_reason,
            "slope_warning": slope_warning,
        }

    except Exception as e:
        print(f"\n==========================================")
        print(f"🚨 [Gemini API 호출 실패 에러 원인]: {e}")
        print(f"==========================================\n")
        logger.exception("Gemini AI 문구 생성 중 예외 발생, Fallback 문구 사용")
        return fallback