from __future__ import annotations

import asyncio
import json
import logging
import sys
from pathlib import Path
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.core.database import AsyncSessionLocal
from app.data.station_metadata import get_station_coordinates


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)
logger = logging.getLogger(__name__)


def normalize_text(value: Any) -> str | None:
    if value is None:
        return None
    text_value = str(value).strip()
    return text_value or None


def to_float(value: Any) -> float | None:
    try:
        return float(str(value).strip())
    except (TypeError, ValueError):
        return None


def to_int(value: Any) -> int | None:
    try:
        return int(float(str(value).strip()))
    except (TypeError, ValueError):
        return None


def station_name_from_filename(path: Path) -> str:
    return path.stem.split("_", 1)[0]


def line_name_from_code(line_code: str | None, path: Path) -> str | None:
    mapping = {
        "K1": "수인분당선",
        "K5": "경강선",
        "D1": "신분당선",
    }
    if line_code in mapping:
        return mapping[line_code]

    stem = path.stem
    if "신분당" in stem:
        return "신분당선"
    if "수인분당" in stem:
        return "수인분당선"
    if "경강" in stem:
        return "경강선"
    return None


async def upsert_station(
    db: AsyncSession,
    *,
    station_code: str,
    station_name: str,
    operator_code: str | None,
    line_code: str | None,
    line_name: str | None,
    latitude: float | None,
    longitude: float | None,
) -> int:
    result = await db.execute(
        text(
            """
            SELECT station_id
            FROM `station`
            WHERE station_code = :station_code
              AND COALESCE(line_code, '') = COALESCE(:line_code, '')
            LIMIT 1
            """
        ),
        {"station_code": station_code, "line_code": line_code},
    )
    row = result.mappings().first()

    if row:
        await db.execute(
            text(
                """
                UPDATE `station`
                SET
                    station_name = :station_name,
                    operator_code = :operator_code,
                    line_code = :line_code,
                    line_name = :line_name,
                    latitude = COALESCE(:latitude, latitude),
                    longitude = COALESCE(:longitude, longitude),
                    data_source = 'PUBLIC_JSON'
                WHERE station_id = :station_id
                """
            ),
            {
                "station_id": row["station_id"],
                "station_name": station_name,
                "operator_code": operator_code,
                "line_code": line_code,
                "line_name": line_name,
                "latitude": latitude,
                "longitude": longitude,
            },
        )
        return int(row["station_id"])

    result = await db.execute(
        text(
            """
            INSERT INTO `station` (
                operator_code,
                line_code,
                line_name,
                station_code,
                station_name,
                latitude,
                longitude,
                data_source
            )
            VALUES (
                :operator_code,
                :line_code,
                :line_name,
                :station_code,
                :station_name,
                :latitude,
                :longitude,
                'PUBLIC_JSON'
            )
            """
        ),
        {
            "operator_code": operator_code,
            "line_code": line_code,
            "line_name": line_name,
            "station_code": station_code,
            "station_name": station_name,
            "latitude": latitude,
            "longitude": longitude,
        },
    )
    return int(result.lastrowid)


async def upsert_facility(
    db: AsyncSession,
    *,
    station_id: int,
    facility_code: str,
    facility_type: str,
    facility_name: str,
    exit_no: str | None,
    direction: str | None,
    detail_location: str | None,
    from_floor_name: str | None,
    to_floor_name: str | None,
    from_floor: int | None,
    to_floor: int | None,
    passenger_capacity: int | None,
    weight_capacity_kg: int | None,
) -> int:
    result = await db.execute(
        text(
            """
            SELECT facility_id
            FROM `facility`
            WHERE external_facility_code = :facility_code
            LIMIT 1
            """
        ),
        {"facility_code": facility_code},
    )
    row = result.mappings().first()

    params = {
        "station_id": station_id,
        "facility_code": facility_code,
        "facility_type": facility_type,
        "facility_name": facility_name,
        "exit_no": exit_no,
        "direction": direction,
        "detail_location": detail_location,
        "from_floor_name": from_floor_name,
        "to_floor_name": to_floor_name,
        "from_floor": from_floor,
        "to_floor": to_floor,
        "passenger_capacity": passenger_capacity,
        "weight_capacity_kg": weight_capacity_kg,
    }

    if row:
        await db.execute(
            text(
                """
                UPDATE `facility`
                SET
                    station_id = :station_id,
                    facility_type = :facility_type,
                    facility_name = :facility_name,
                    exit_no = :exit_no,
                    direction = :direction,
                    detail_location = :detail_location,
                    from_floor_name = :from_floor_name,
                    to_floor_name = :to_floor_name,
                    from_floor = :from_floor,
                    to_floor = :to_floor,
                    passenger_capacity = :passenger_capacity,
                    weight_capacity_kg = :weight_capacity_kg,
                    data_source = 'PUBLIC_JSON'
                WHERE facility_id = :facility_id
                """
            ),
            {**params, "facility_id": row["facility_id"]},
        )
        return int(row["facility_id"])

    result = await db.execute(
        text(
            """
            INSERT INTO `facility` (
                station_id,
                facility_type,
                facility_name,
                external_facility_code,
                exit_no,
                direction,
                detail_location,
                from_floor_name,
                to_floor_name,
                from_floor,
                to_floor,
                passenger_capacity,
                weight_capacity_kg,
                data_source
            )
            VALUES (
                :station_id,
                :facility_type,
                :facility_name,
                :facility_code,
                :exit_no,
                :direction,
                :detail_location,
                :from_floor_name,
                :to_floor_name,
                :from_floor,
                :to_floor,
                :passenger_capacity,
                :weight_capacity_kg,
                'PUBLIC_JSON'
            )
            """
        ),
        params,
    )
    return int(result.lastrowid)


async def ensure_initial_status(
    db: AsyncSession,
    facility_id: int,
    facility_type: str,
) -> None:
    result = await db.execute(
        text(
            """
            SELECT status_id
            FROM `facility_status`
            WHERE facility_id = :facility_id
            LIMIT 1
            """
        ),
        {"facility_id": facility_id},
    )
    if result.mappings().first():
        return

    await db.execute(
        text(
            """
            INSERT INTO `facility_status` (
                facility_id,
                status_code,
                is_usable,
                is_usable_wheelchair,
                source_type
            )
            VALUES (
                :facility_id,
                'NORMAL',
                1,
                :wheelchair,
                'INITIAL_DATA'
            )
            """
        ),
        {
            "facility_id": facility_id,
            "wheelchair": int(facility_type == "ELEVATOR"),
        },
    )


async def seed_subway_data(db: AsyncSession, files: list[Path]) -> None:
    for path in files:
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            stations = raw if isinstance(raw, list) else [raw]

            for station in stations:
                if not isinstance(station, dict):
                    continue

                station_code = normalize_text(station.get("stinCd"))
                if not station_code:
                    continue

                station_name = (
                    normalize_text(station.get("stinNm"))
                    or station_name_from_filename(path)
                )
                operator_code = normalize_text(station.get("railOprIsttCd"))
                line_code = normalize_text(station.get("lnCd"))
                line_name = line_name_from_code(line_code, path)

                station_coordinates = get_station_coordinates(
                    station_name=station_name,
                    station_code=station_code,
                    line_code=line_code,
                )
                station_latitude = (
                    station_coordinates[0] if station_coordinates else None
                )
                station_longitude = (
                    station_coordinates[1] if station_coordinates else None
                )

                station_id = await upsert_station(
                    db,
                    station_code=station_code,
                    station_name=station_name,
                    operator_code=operator_code,
                    line_code=line_code,
                    line_name=line_name,
                    latitude=station_latitude,
                    longitude=station_longitude,
                )

                for idx, item in enumerate(station.get("elevators") or [], start=1):
                    if not isinstance(item, dict):
                        continue
                    exit_no = normalize_text(item.get("exitNo"))
                    code = f"ELEV_{station_code}_{exit_no or '0'}_{idx}"
                    facility_id = await upsert_facility(
                        db,
                        station_id=station_id,
                        facility_code=code,
                        facility_type="ELEVATOR",
                        facility_name=f"[{station_name}] 엘리베이터 {idx}",
                        exit_no=exit_no,
                        direction=None,
                        detail_location=normalize_text(item.get("dtlLoc")),
                        from_floor_name=normalize_text(item.get("grndDvNmFr")),
                        to_floor_name=normalize_text(item.get("grndDvNmTo")),
                        from_floor=to_int(item.get("runStinFlorFr")),
                        to_floor=to_int(item.get("runStinFlorTo")),
                        passenger_capacity=to_int(item.get("rglnPsno")),
                        weight_capacity_kg=to_int(item.get("rglnWgt")),
                    )
                    await ensure_initial_status(db, facility_id, "ELEVATOR")

                for idx, item in enumerate(station.get("escalators") or [], start=1):
                    if not isinstance(item, dict):
                        continue
                    exit_no = normalize_text(item.get("exitNo"))
                    code = f"ESCA_{station_code}_{exit_no or '0'}_{idx}"
                    facility_id = await upsert_facility(
                        db,
                        station_id=station_id,
                        facility_code=code,
                        facility_type="ESCALATOR",
                        facility_name=f"[{station_name}] 에스컬레이터 {idx}",
                        exit_no=exit_no,
                        direction=normalize_text(item.get("updnDvNm")),
                        detail_location=normalize_text(item.get("dtlLoc")),
                        from_floor_name=normalize_text(item.get("grndDvNmFr")),
                        to_floor_name=normalize_text(item.get("grndDvNmTo")),
                        from_floor=to_int(item.get("runStinFlorFr")),
                        to_floor=to_int(item.get("runStinFlorTo")),
                        passenger_capacity=None,
                        weight_capacity_kg=None,
                    )
                    await ensure_initial_status(db, facility_id, "ESCALATOR")

            await db.commit()
            logger.info("지하철 적재 완료: %s", path.name)
        except Exception:
            await db.rollback()
            logger.exception("지하철 파일 처리 실패: %s", path.name)


async def upsert_bus_stop(db: AsyncSession, item: dict[str, Any]) -> None:
    stop_code = normalize_text(item.get("정류장번호(ID)"))
    stop_name = normalize_text(item.get("정류장명"))
    latitude = to_float(item.get("위도"))
    longitude = to_float(item.get("경도"))

    if not stop_code or not stop_name or latitude is None or longitude is None:
        return

    values = {
        "stop_code": stop_code,
        "stop_name": stop_name,
        "detail_location": normalize_text(item.get("상세위치")),
        "latitude": latitude,
        "longitude": longitude,
        "district": normalize_text(item.get("시군구")),
        "administrative_dong": normalize_text(item.get("행정동")),
        "stop_installation_type": normalize_text(item.get("정류장설치유형")),
        "central_lane": normalize_text(item.get("중앙차로여부")),
        "chair_type": normalize_text(item.get("의자설치유형")),
        "bit_type": normalize_text(item.get("버스정보안내단말기(BIT) 유형")),
        "air_cleaner_installed": normalize_text(item.get("공기청정기설치여부")),
        "heating_cooling_installed": normalize_text(item.get("냉온풍기설치여부")),
        "windshield_installed": normalize_text(item.get("바람막이설치여부")),
        "fine_dust_sensor_installed": normalize_text(
            item.get("미세먼지 측정센서 설치여부")
        ),
        "emergency_bell_installed": normalize_text(item.get("안전비상벨설치여부")),
        "wifi_installed": normalize_text(item.get("와이파이설치여부")),
        "red_zone": normalize_text(item.get("레드존여부")),
        "city_bus_routes": normalize_text(item.get("시내버스_경유노선번호")),
        "intercity_bus_routes": normalize_text(item.get("시외버스_경유노선번호")),
    }

    result = await db.execute(
        text(
            """
            SELECT bus_stop_id
            FROM `bus_stop`
            WHERE stop_code = :stop_code
            LIMIT 1
            """
        ),
        {"stop_code": stop_code},
    )
    row = result.mappings().first()

    if row:
        await db.execute(
            text(
                """
                UPDATE `bus_stop`
                SET
                    stop_name = :stop_name,
                    detail_location = :detail_location,
                    latitude = :latitude,
                    longitude = :longitude,
                    district = :district,
                    administrative_dong = :administrative_dong,
                    stop_installation_type = :stop_installation_type,
                    central_lane = :central_lane,
                    chair_type = :chair_type,
                    bit_type = :bit_type,
                    air_cleaner_installed = :air_cleaner_installed,
                    heating_cooling_installed = :heating_cooling_installed,
                    windshield_installed = :windshield_installed,
                    fine_dust_sensor_installed = :fine_dust_sensor_installed,
                    emergency_bell_installed = :emergency_bell_installed,
                    wifi_installed = :wifi_installed,
                    red_zone = :red_zone,
                    city_bus_routes = :city_bus_routes,
                    intercity_bus_routes = :intercity_bus_routes,
                    data_source = 'PUBLIC_JSON'
                WHERE bus_stop_id = :bus_stop_id
                """
            ),
            {**values, "bus_stop_id": row["bus_stop_id"]},
        )
        return

    await db.execute(
        text(
            """
            INSERT INTO `bus_stop` (
                stop_code, stop_name, detail_location,
                latitude, longitude, district, administrative_dong,
                stop_installation_type, central_lane, chair_type, bit_type,
                air_cleaner_installed, heating_cooling_installed,
                windshield_installed, fine_dust_sensor_installed,
                emergency_bell_installed, wifi_installed, red_zone,
                city_bus_routes, intercity_bus_routes, data_source
            )
            VALUES (
                :stop_code, :stop_name, :detail_location,
                :latitude, :longitude, :district, :administrative_dong,
                :stop_installation_type, :central_lane, :chair_type, :bit_type,
                :air_cleaner_installed, :heating_cooling_installed,
                :windshield_installed, :fine_dust_sensor_installed,
                :emergency_bell_installed, :wifi_installed, :red_zone,
                :city_bus_routes, :intercity_bus_routes, 'PUBLIC_JSON'
            )
            """
        ),
        values,
    )


async def seed_bus_data(db: AsyncSession, files: list[Path]) -> None:
    for path in files:
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            items = raw.get("data", []) if isinstance(raw, dict) else raw
            if not isinstance(items, list):
                continue

            for item in items:
                if isinstance(item, dict):
                    await upsert_bus_stop(db, item)

            await db.commit()
            logger.info("버스정류장 적재 완료: %s | %d건", path.name, len(items))
        except Exception:
            await db.rollback()
            logger.exception("버스정류장 파일 처리 실패: %s", path.name)


async def main() -> None:
    base_dir = PROJECT_ROOT / "facility-info"
    subway_files = sorted((base_dir / "subway").glob("*.json"))
    bus_files = sorted((base_dir / "bus").glob("*.json"))

    logger.info(
        "DB seeding 시작 | subway=%d | bus=%d",
        len(subway_files),
        len(bus_files),
    )

    async with AsyncSessionLocal() as db:
        await seed_subway_data(db, subway_files)
        await seed_bus_data(db, bus_files)


if __name__ == "__main__":
    asyncio.run(main())
