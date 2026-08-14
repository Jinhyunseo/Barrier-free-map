"""
현재 프로젝트의 DB는 seongnam_nav_db_v2.sql을 기준으로 생성합니다.

기존 Base.metadata.create_all()은 과거 ORM 모델까지 함께 생성할 수 있어
2차 프로토타입 DB를 오염시킬 수 있으므로 이 스크립트에서는 실행하지 않습니다.
대신 현재 필수 테이블 존재 여부를 검증합니다.
"""

import asyncio

from sqlalchemy import text

from app.core.database import engine


REQUIRED_TABLES = {
    "user",
    "station",
    "facility",
    "facility_status",
    "facility_status_history",
    "bus_stop",
    "user_report",
    "ai_verification",
}


async def main() -> None:
    async with engine.connect() as conn:
        result = await conn.execute(text("SHOW TABLES"))
        existing = {str(row[0]).lower() for row in result.fetchall()}

    missing = REQUIRED_TABLES - existing
    if missing:
        print("필수 테이블이 없습니다:")
        for name in sorted(missing):
            print(f" - {name}")
        print("MySQL Workbench에서 seongnam_nav_db_v2.sql을 먼저 실행하세요.")
        raise SystemExit(1)

    print("DB 필수 테이블 검증 완료.")


if __name__ == "__main__":
    asyncio.run(main())
