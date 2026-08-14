from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Literal

from google import genai
from google.genai import types
from pydantic import BaseModel, Field, ValidationError

from app.core.config import settings

logger = logging.getLogger(__name__)


class GeminiVerificationResult(BaseModel):
    place_match: bool = Field(
        description="사진에서 제보 대상 역/장소와 일치한다고 볼 수 있는 근거가 있는지 여부"
    )
    facility_match: bool = Field(
        description="사진 속 시설 유형이 제보 대상 시설과 일치하는지 여부"
    )
    state_match: bool = Field(
        description="사진에서 확인되는 상태가 사용자의 제보 상태와 일치하는지 여부"
    )
    detected_status: Literal[
        "NORMAL",
        "BROKEN",
        "INSPECTION",
        "UNKNOWN",
    ]
    confidence_score: float = Field(ge=0, le=100)
    reason: str = Field(
        max_length=160,
        description="판단 근거를 한국어 160자 이내로 간결하게 작성",
    )


class GeminiService:
    def __init__(self) -> None:
        self.model_name = settings.GEMINI_MODEL
        self._client: genai.Client | None = None
        self.max_attempts = 3

    @property
    def client(self) -> genai.Client:
        if not settings.GEMINI_API_KEY:
            raise RuntimeError(
                "GEMINI_API_KEY가 없습니다. backend/.env 파일을 확인하세요."
            )
        if self._client is None:
            self._client = genai.Client(api_key=settings.GEMINI_API_KEY)
        return self._client

    @staticmethod
    def _raw_text(response: Any) -> str:
        text = getattr(response, "text", None)
        return str(text).strip() if text else ""

    @staticmethod
    def _finish_reason(response: Any) -> str | None:
        candidates = getattr(response, "candidates", None) or []
        if not candidates:
            return None
        value = getattr(candidates[0], "finish_reason", None)
        return str(value) if value is not None else None

    @staticmethod
    def _parse_response(response: Any) -> GeminiVerificationResult:
        # response_json_schema를 사용한 경우 SDK가 parsed를 제공할 수 있습니다.
        parsed = getattr(response, "parsed", None)
        if isinstance(parsed, GeminiVerificationResult):
            return parsed
        if isinstance(parsed, dict):
            return GeminiVerificationResult.model_validate(parsed)

        raw = GeminiService._raw_text(response)
        if not raw:
            raise ValueError("Gemini가 빈 응답을 반환했습니다.")

        if raw.startswith("```"):
            lines = raw.splitlines()
            if lines and lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            raw = "\n".join(lines).strip()

        try:
            return GeminiVerificationResult.model_validate_json(raw)
        except ValidationError as exc:
            logger.error("Gemini JSON 파싱 실패 | raw=%r", raw[:1000])
            raise ValueError("Gemini 응답이 완전한 JSON 형식이 아닙니다.") from exc

    @staticmethod
    def _build_prompt(
        *,
        station_name: str,
        line_name: str | None,
        facility_type: str,
        facility_name: str | None,
        exit_no: str | None,
        detail_location: str | None,
        report_type: str,
        report_title: str,
        report_description: str | None,
    ) -> str:
        return f"""
		당신은 성남시 교통약자 길안내 서비스의 시설 현장 제보 사진 검증 AI입니다.

		[DB 기준 정보]
		역명: {station_name}
		노선: {line_name or '정보 없음'}
		시설 유형: {facility_type}
		시설명: {facility_name or '정보 없음'}
		출구 번호: {exit_no or '정보 없음'}
		상세 위치: {detail_location or '정보 없음'}

		[사용자 제보]
		제보 유형: {report_type}
		제목: {report_title}
		설명: {report_description or '없음'}

		다음 기준에 따라 판단하세요.

		사용자가 현장에서 일반 스마트폰으로 촬영한 사진이라는 점을 고려하세요.
		사진 한 장에 역명, 출구번호, 시설명, 상태 정보가 모두 포함되어 있을 필요는 없습니다.
		확실한 모순이 없다면 사진에서 확인 가능한 정보를 중심으로 판단하세요.

		1. place_match
		역명판, 출구번호, 안내판 등 명확한 위치 정보가 DB 정보와 일치하면 true입니다.

		다만 역명이나 출구번호가 사진에 보이지 않더라도 그것만으로 false로 판단하지 마세요.
		사진 속 시설 형태, 주변 역사 환경, 시설 안내표지 등으로 해당 장소일 가능성이
		합리적으로 인정되고 DB 정보와 모순되는 요소가 없다면 true로 판단할 수 있습니다.

		다른 역명이나 다른 장소임을 명확하게 확인할 수 있는 경우에는 false로 판단하세요.

		2. facility_match
		사진의 주요 대상이 제보한 시설 유형과 일치하면 true입니다.
		시설 전체가 촬영되지 않아도 엘리베이터 문, 버튼, 안내표지 등
		시설 유형을 식별할 수 있는 충분한 특징이 있으면 true입니다.

		3. state_match
		사진이 사용자가 제보한 상태를 합리적으로 뒷받침하면 true입니다.
		"고장", "점검중", "운행중지" 등의 문구뿐만 아니라
		차단봉, 접근금지 표시, 정지 상태 등 시각적 정황도 고려하세요.

		state_match가 true이고 사용자의 제보가 BROKEN이면
		detected_status도 가능한 경우 BROKEN으로 반환하세요.

		상태를 전혀 판단할 수 없는 경우에만 UNKNOWN을 사용하세요.

		사진만으로 상태를 전혀 판단할 수 없는 경우에만 false로 판단하세요.
		""".strip()

    async def verify_facility_image(
        self,
        *,
        image_bytes: bytes,
        mime_type: str,
        station_name: str,
        line_name: str | None,
        facility_type: str,
        facility_name: str | None,
        exit_no: str | None,
        detail_location: str | None,
        report_type: str,
        report_title: str,
        report_description: str | None,
    ) -> GeminiVerificationResult:
        if not image_bytes:
            raise ValueError("이미지 데이터가 없습니다.")

        prompt = self._build_prompt(
            station_name=station_name,
            line_name=line_name,
            facility_type=facility_type,
            facility_name=facility_name,
            exit_no=exit_no,
            detail_location=detail_location,
            report_type=report_type,
            report_title=report_title,
            report_description=report_description,
        )

        image_part = types.Part.from_bytes(
            data=image_bytes,
            mime_type=mime_type,
        )

        # Gemini 3.5 Flash는 기본 thinking level이 medium입니다.
        # 이 작업은 분류/검증에 가까우므로 minimal로 낮춰 응답 잘림과 지연을 줄입니다.
        config = types.GenerateContentConfig(
            temperature=0.0,
            max_output_tokens=4096,
            thinking_config=types.ThinkingConfig(thinking_level="minimal"),
            response_mime_type="application/json",
            response_json_schema=GeminiVerificationResult.model_json_schema(),
        )

        last_error: Exception | None = None

        for attempt in range(1, self.max_attempts + 1):
            try:
                response = await self.client.aio.models.generate_content(
                    model=self.model_name,
                    contents=[prompt, image_part],
                    config=config,
                )

                logger.info(
                    "Gemini 응답 | attempt=%d | finish_reason=%s | length=%d",
                    attempt,
                    self._finish_reason(response),
                    len(self._raw_text(response)),
                )

                result = self._parse_response(response)
                return result

            except Exception as exc:
                last_error = exc
                logger.warning(
                    "Gemini verification attempt %d/%d failed: %s",
                    attempt,
                    self.max_attempts,
                    exc,
                )
                if attempt < self.max_attempts:
                    await asyncio.sleep(attempt)

        raise RuntimeError("Gemini 이미지 검증에 실패했습니다.") from last_error


gemini_service = GeminiService()
