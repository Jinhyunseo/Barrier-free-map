from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.data.station_metadata import get_station_coordinates
from app.schemas.report import (
    ReportableFacilityResponse,
    ReportCreateResponse,
    ReportStatusResponse,
    ReportType,
)
from app.services.gemini_service import gemini_service

logger = logging.getLogger(__name__)

# main.py에서 /api/v2를 붙이므로 여기서는 /reports만 사용합니다.
router = APIRouter(prefix="/reports", tags=["User Reports"])

BASE_DIR = Path(__file__).resolve().parents[2]
UPLOAD_DIR = BASE_DIR / "static" / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp"}


def normalize_report_type(value: str) -> str:
    return value.strip().upper()


def get_expected_status(report_type: str) -> str:
    value = normalize_report_type(report_type)
    if value.startswith("BROKEN_") or value == "BROKEN":
        return "BROKEN"
    if value.startswith("INSPECTION_") or value == "INSPECTION":
        return "INSPECTION"
    if value.startswith("RESTORED_") or value == "RESTORED":
        return "NORMAL"
    return "UNKNOWN"


def get_expected_facility_type(report_type: str) -> str | None:
    value = normalize_report_type(report_type)
    if value.endswith("_ELEVATOR"):
        return "ELEVATOR"
    if value.endswith("_ESCALATOR"):
        return "ESCALATOR"
    return None


def is_report_approved(
    *,
    place_match: bool,
    facility_match: bool,
    state_match: bool,
    confidence_score: float,
) -> bool:
    return (
        place_match
        and facility_match
        and state_match
        and confidence_score >= settings.AI_CONFIDENCE_THRESHOLD
    )


@router.post("", response_model=ReportCreateResponse, status_code=201)
async def create_report(
    user_id: int = Form(..., description="제보 사용자 ID", examples=[1]),
    facility_id: int = Form(..., description="제보 대상 시설 ID", examples=[21]),
    report_type: ReportType = Form(..., description="제보 유형"),
    title: str = Form(..., description="제보 제목"),
    description: str | None = Form(None, description="제보 설명"),
    latitude: float | None = Form(
        None,
        description="촬영 위도. 미입력 시 시설/역 좌표를 사용합니다.",
    ),
    longitude: float | None = Form(
        None,
        description="촬영 경도. 미입력 시 시설/역 좌표를 사용합니다.",
    ),
    image: UploadFile = File(..., description="현장 사진"),
    db: AsyncSession = Depends(get_db),
):
    if image.content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(
            status_code=400,
            detail="JPEG, PNG, WEBP 이미지만 업로드할 수 있습니다.",
        )

    image_bytes = await image.read()
    if not image_bytes:
        raise HTTPException(status_code=400, detail="빈 이미지 파일입니다.")
    if len(image_bytes) > settings.MAX_IMAGE_SIZE:
        raise HTTPException(status_code=400, detail="이미지 크기는 최대 10MB입니다.")

    canonical_report_type = normalize_report_type(report_type.value)

    # 1) 사용자 확인
    result = await db.execute(
        text("""
            SELECT user_id, email, nickname
            FROM `user`
            WHERE user_id = :user_id
            LIMIT 1
            """),
        {"user_id": user_id},
    )
    user = result.mappings().first()
    if not user:
        raise HTTPException(status_code=404, detail="존재하지 않는 사용자입니다.")

    # 2) 시설 + 역사 정보 확인
    result = await db.execute(
        text("""
            SELECT
                f.facility_id,
                f.station_id,
                f.facility_type,
                f.facility_name,
                f.external_facility_code,
                f.exit_no,
                f.direction,
                f.detail_location,
                f.latitude AS facility_latitude,
                f.longitude AS facility_longitude,
                s.station_name,
                s.line_code,
                s.line_name,
                s.station_code,
                s.latitude AS station_latitude,
                s.longitude AS station_longitude
            FROM `facility` AS f
            INNER JOIN `station` AS s
                ON s.station_id = f.station_id
            WHERE f.facility_id = :facility_id
            LIMIT 1
            """),
        {"facility_id": facility_id},
    )
    facility = result.mappings().first()
    if not facility:
        raise HTTPException(status_code=404, detail="존재하지 않는 시설입니다.")

    expected_facility_type = get_expected_facility_type(canonical_report_type)
    if (
        expected_facility_type is not None
        and facility["facility_type"] != expected_facility_type
    ):
        raise HTTPException(
            status_code=400,
            detail=(
                f"report_type은 {expected_facility_type} 제보인데 "
                f"facility_id={facility_id}의 유형은 {facility['facility_type']}입니다."
            ),
        )

    # 3) 촬영 좌표 결정
    # 우선순위: 사용자가 입력한 촬영 좌표 > 시설 DB 좌표 > 역 DB 좌표
    #          > 프로젝트에 미리 저장된 역 대표 좌표
    report_latitude = latitude
    report_longitude = longitude

    if report_latitude is None:
        report_latitude = facility["facility_latitude"]
    if report_longitude is None:
        report_longitude = facility["facility_longitude"]
    if report_latitude is None:
        report_latitude = facility["station_latitude"]
    if report_longitude is None:
        report_longitude = facility["station_longitude"]

    # 기존 DB에 station/facility 좌표가 NULL로 적재되어 있어도
    # Swagger에서 latitude/longitude를 공란으로 두고 테스트할 수 있도록
    # station_metadata.py의 사전 저장 좌표를 마지막 fallback으로 사용합니다.
    if report_latitude is None or report_longitude is None:
        fallback_coordinates = get_station_coordinates(
            station_name=facility["station_name"],
            station_code=facility["station_code"],
            line_code=facility["line_code"],
        )
        if fallback_coordinates is not None:
            fallback_latitude, fallback_longitude = fallback_coordinates
            if report_latitude is None:
                report_latitude = fallback_latitude
            if report_longitude is None:
                report_longitude = fallback_longitude

            # 기존 DB의 station 좌표가 비어 있다면 이번 요청에서 함께 보정합니다.
            # 이후 요청부터는 station 테이블의 좌표를 바로 사용할 수 있습니다.
            await db.execute(
                text(
                    """
                    UPDATE `station`
                    SET
                        latitude = COALESCE(latitude, :latitude),
                        longitude = COALESCE(longitude, :longitude)
                    WHERE station_id = :station_id
                    """
                ),
                {
                    "station_id": facility["station_id"],
                    "latitude": fallback_latitude,
                    "longitude": fallback_longitude,
                },
            )

    if report_latitude is None or report_longitude is None:
        raise HTTPException(
            status_code=400,
            detail=(
                "촬영 좌표를 찾을 수 없습니다. latitude/longitude를 입력하거나 "
                "해당 역의 좌표를 station_metadata.py에 등록해주세요."
            ),
        )

    # 4) 이미지 저장
    extension = {
        "image/jpeg": ".jpg",
        "image/png": ".png",
        "image/webp": ".webp",
    }[image.content_type]
    filename = f"{uuid.uuid4()}{extension}"
    file_path = UPLOAD_DIR / filename

    try:
        file_path.write_bytes(image_bytes)
    except OSError as exc:
        logger.exception("이미지 저장 실패")
        raise HTTPException(
            status_code=500, detail="이미지 저장에 실패했습니다."
        ) from exc

    image_url = f"/static/uploads/{filename}"

    # 5) user_report를 먼저 저장/COMMIT
    try:
        result = await db.execute(
            text("""
                INSERT INTO `user_report` (
                    user_id,
                    facility_id,
                    bus_stop_id,
                    report_type,
                    title,
                    description,
                    image_url,
                    latitude,
                    longitude,
                    report_status
                )
                VALUES (
                    :user_id,
                    :facility_id,
                    NULL,
                    :report_type,
                    :title,
                    :description,
                    :image_url,
                    :latitude,
                    :longitude,
                    'PENDING'
                )
                """),
            {
                "user_id": user_id,
                "facility_id": facility_id,
                "report_type": canonical_report_type,
                "title": title,
                "description": description,
                "image_url": image_url,
                "latitude": float(report_latitude),
                "longitude": float(report_longitude),
            },
        )
        report_id = int(result.lastrowid)
        await db.commit()
    except Exception as exc:
        await db.rollback()
        file_path.unlink(missing_ok=True)
        logger.exception("user_report 저장 실패")
        raise HTTPException(
            status_code=500, detail="제보 저장에 실패했습니다."
        ) from exc

    # 6) Gemini 이미지 검증
    try:
        ai_result = await gemini_service.verify_facility_image(
            image_bytes=image_bytes,
            mime_type=image.content_type,
            station_name=facility["station_name"],
            line_name=facility["line_name"],
            facility_type=facility["facility_type"],
            facility_name=facility["facility_name"],
            exit_no=facility["exit_no"],
            detail_location=facility["detail_location"],
            report_type=canonical_report_type,
            report_title=title,
            report_description=description,
        )
    except Exception as exc:
        logger.exception("Gemini 이미지 검증 실패 | report_id=%s", report_id)
        await db.execute(
            text("""
                UPDATE `user_report`
                SET report_status = 'ERROR'
                WHERE report_id = :report_id
                """),
            {"report_id": report_id},
        )
        await db.commit()
        raise HTTPException(
            status_code=502,
            detail=(
                "제보는 저장되었지만 Gemini 이미지 검증에 실패했습니다. "
                f"report_id={report_id}"
            ),
        ) from exc

    # ========================================================
    # 개발 테스트 전용 강제 APPROVED
    # AI_TEST_FORCE_APPROVE와 DEBUG가 TRUE 일때
    # ========================================================

    logger.warning(
        "AI_TEST_FORCE_APPROVE 현재 설정값 = %s",
        settings.AI_TEST_FORCE_APPROVE,
    )

    if settings.AI_TEST_FORCE_APPROVE and settings.DEBUG:

        expected_test_status = get_expected_status(report_type)

        if expected_test_status == "UNKNOWN":
            expected_test_status = "BROKEN"

        ai_result = ai_result.model_copy(
            update={
                "place_match": True,
                "facility_match": True,
                "state_match": True,
                "detected_status": expected_test_status,
                "confidence_score": 99.0,
                "reason": (
                    "[TEST MODE] "
                    "시설 상태 및 상태 변경 이력 저장 테스트를 위한 "
                    "강제 승인 결과입니다."
                ),
            }
        )

    logger.warning(
        "AI_TEST_FORCE_APPROVE 적용 완료 | "
        "report_id=%s | "
        "detected_status=%s | "
        "confidence=%s",
        report_id,
        ai_result.detected_status,
        ai_result.confidence_score,
    )

    # 7) 서버 측에서도 사용자 제보 상태와 Gemini detected_status를 다시 비교
    expected_status = get_expected_status(canonical_report_type)
    if expected_status == "UNKNOWN":
        state_match = ai_result.state_match
    else:
        state_match = ai_result.detected_status == expected_status

    approved = is_report_approved(
        place_match=ai_result.place_match,
        facility_match=ai_result.facility_match,
        state_match=state_match,
        confidence_score=ai_result.confidence_score,
    )
    verification_result = "APPROVED" if approved else "REJECTED"

    # 8) AI 결과 + 현재 상태 + 상태 이력을 한 transaction으로 저장
    try:
        raw_response = ai_result.model_dump()
        raw_response["state_match"] = state_match
        raw_response["expected_status"] = expected_status

        await db.execute(
            text("""
                INSERT INTO `ai_verification` (
                    report_id,
                    place_match,
                    facility_match,
                    state_match,
                    confidence_score,
                    verification_result,
                    reason,
                    model_name,
                    raw_response,
                    verified_at
                )
                VALUES (
                    :report_id,
                    :place_match,
                    :facility_match,
                    :state_match,
                    :confidence_score,
                    :verification_result,
                    :reason,
                    :model_name,
                    CAST(:raw_response AS JSON),
                    CURRENT_TIMESTAMP
                )
                """),
            {
                "report_id": report_id,
                "place_match": int(ai_result.place_match),
                "facility_match": int(ai_result.facility_match),
                "state_match": int(state_match),
                "confidence_score": ai_result.confidence_score,
                "verification_result": verification_result,
                "reason": ai_result.reason,
                "model_name": settings.GEMINI_MODEL,
                "raw_response": json.dumps(raw_response, ensure_ascii=False),
            },
        )

        await db.execute(
            text("""
                UPDATE `user_report`
                SET report_status = :report_status
                WHERE report_id = :report_id
                """),
            {
                "report_status": verification_result,
                "report_id": report_id,
            },
        )

        if approved:
            new_status = ai_result.detected_status
            result = await db.execute(
                text("""
                    SELECT status_id, status_code
                    FROM `facility_status`
                    WHERE facility_id = :facility_id
                    LIMIT 1
                    """),
                {"facility_id": facility_id},
            )
            current_status = result.mappings().first()

            if current_status:
                previous_status = current_status["status_code"]
                await db.execute(
                    text("""
                        UPDATE `facility_status`
                        SET
                            status_code = :status_code,
                            is_usable = :is_usable,
                            is_usable_wheelchair = :is_usable_wheelchair,
                            source_type = 'USER_REPORT',
                            source_report_id = :source_report_id,
                            last_updated_at = CURRENT_TIMESTAMP
                        WHERE facility_id = :facility_id
                        """),
                    {
                        "status_code": new_status,
                        "is_usable": int(new_status == "NORMAL"),
                        "is_usable_wheelchair": int(
                            new_status == "NORMAL"
                            and facility["facility_type"] == "ELEVATOR"
                        ),
                        "source_report_id": report_id,
                        "facility_id": facility_id,
                    },
                )
            else:
                previous_status = None
                await db.execute(
                    text("""
                        INSERT INTO `facility_status` (
                            facility_id,
                            status_code,
                            is_usable,
                            is_usable_wheelchair,
                            source_type,
                            source_report_id
                        )
                        VALUES (
                            :facility_id,
                            :status_code,
                            :is_usable,
                            :is_usable_wheelchair,
                            'USER_REPORT',
                            :source_report_id
                        )
                        """),
                    {
                        "facility_id": facility_id,
                        "status_code": new_status,
                        "is_usable": int(new_status == "NORMAL"),
                        "is_usable_wheelchair": int(
                            new_status == "NORMAL"
                            and facility["facility_type"] == "ELEVATOR"
                        ),
                        "source_report_id": report_id,
                    },
                )

            if previous_status != new_status:
                await db.execute(
                    text("""
                        INSERT INTO `facility_status_history` (
                            facility_id,
                            previous_status,
                            new_status,
                            source_type,
                            report_id,
                            confidence_score
                        )
                        VALUES (
                            :facility_id,
                            :previous_status,
                            :new_status,
                            'USER_REPORT',
                            :report_id,
                            :confidence_score
                        )
                        """),
                    {
                        "facility_id": facility_id,
                        "previous_status": previous_status,
                        "new_status": new_status,
                        "report_id": report_id,
                        "confidence_score": ai_result.confidence_score,
                    },
                )

        await db.commit()

    except Exception as exc:
        await db.rollback()
        logger.exception("AI 검증 결과 DB 저장 실패 | report_id=%s", report_id)
        await db.execute(
            text("""
                UPDATE `user_report`
                SET report_status = 'ERROR'
                WHERE report_id = :report_id
                """),
            {"report_id": report_id},
        )
        await db.commit()
        raise HTTPException(
            status_code=500,
            detail=f"AI 검증 결과 저장에 실패했습니다. report_id={report_id}",
        ) from exc

    return ReportCreateResponse(
        report_id=report_id,
        user_id=user_id,
        facility_id=facility_id,
        report_type=canonical_report_type,
        title=title,
        description=description,
        image_url=image_url,
        report_status=verification_result,
        ai_verification=verification_result,
        ai_confidence_score=ai_result.confidence_score,
        detected_status=ai_result.detected_status,
        reason=ai_result.reason,
        created_at=datetime.now(),
    )


@router.get("/facilities", response_model=list[ReportableFacilityResponse])
async def get_reportable_facilities(
    station_name: list[str] = Query(
        default=[],
        description="추천 경로에서 지나가는 역명. 동일 파라미터를 여러 번 전달할 수 있습니다.",
    ),
    db: AsyncSession = Depends(get_db),
):
    """
    추천 경로에 포함된 역의 엘리베이터/에스컬레이터를 DB facility_id와 함께 반환합니다.

    프론트엔드는 경로 추천이 완료된 뒤 이 API를 호출해 사용자가 제보할 실제 시설을
    선택하게 합니다. 역명은 '야탑'과 '야탑역'을 동일하게 취급합니다.
    """
    normalized_names: list[str] = []
    for raw_name in station_name:
        name = str(raw_name or "").strip()
        if not name:
            continue
        if name.endswith("역"):
            name = name[:-1].strip()
        if name and name not in normalized_names:
            normalized_names.append(name)

    if not normalized_names:
        return []

    station_filters: list[str] = []
    params: dict[str, str] = {}
    for index, name in enumerate(normalized_names):
        key = f"station_{index}"
        station_filters.append(
            f"REPLACE(TRIM(s.station_name), '역', '') = :{key}"
        )
        params[key] = name

    result = await db.execute(
        text(
            f"""
            SELECT
                f.facility_id,
                f.station_id,
                s.station_name,
                s.line_name,
                f.facility_type,
                f.facility_name,
                f.exit_no,
                f.direction,
                f.detail_location,
                fs.status_code,
                fs.is_usable
            FROM `facility` AS f
            INNER JOIN `station` AS s
                ON s.station_id = f.station_id
            LEFT JOIN `facility_status` AS fs
                ON fs.facility_id = f.facility_id
            WHERE f.facility_type IN ('ELEVATOR', 'ESCALATOR')
              AND ({' OR '.join(station_filters)})
            ORDER BY
                s.station_name,
                CASE f.facility_type
                    WHEN 'ELEVATOR' THEN 1
                    WHEN 'ESCALATOR' THEN 2
                    ELSE 3
                END,
                f.exit_no,
                f.facility_id
            """
        ),
        params,
    )

    facilities = result.mappings().all()
    return [
        ReportableFacilityResponse(
            facility_id=row["facility_id"],
            station_id=row["station_id"],
            station_name=row["station_name"],
            line_name=row["line_name"],
            facility_type=row["facility_type"],
            facility_name=row["facility_name"],
            exit_no=row["exit_no"],
            direction=row["direction"],
            detail_location=row["detail_location"],
            status_code=row["status_code"],
            is_usable=(
                bool(row["is_usable"])
                if row["is_usable"] is not None
                else None
            ),
        )
        for row in facilities
    ]


@router.get("/{report_id}", response_model=ReportStatusResponse)
async def get_report(
    report_id: int,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        text("""
            SELECT
                ur.report_id,
                ur.report_status,
                av.verification_result,
                av.confidence_score,
                av.reason,
                JSON_UNQUOTE(
                    JSON_EXTRACT(av.raw_response, '$.detected_status')
                ) AS detected_status
            FROM `user_report` AS ur
            LEFT JOIN `ai_verification` AS av
                ON av.report_id = ur.report_id
            WHERE ur.report_id = :report_id
            LIMIT 1
            """),
        {"report_id": report_id},
    )
    report = result.mappings().first()

    if not report:
        raise HTTPException(status_code=404, detail="존재하지 않는 제보입니다.")

    return ReportStatusResponse(
        report_id=report["report_id"],
        report_status=report["report_status"],
        ai_verification_result=report["verification_result"],
        confidence_score=(
            float(report["confidence_score"])
            if report["confidence_score"] is not None
            else None
        ),
        detected_status=report["detected_status"],
        reason=report["reason"],
    )
