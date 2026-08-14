import asyncio
from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.models.models import ConditionMaster

CONDITIONS = [
    ("AVOID_STAIRS", "계단 제외", "계단이 포함된 이동 구간을 제외합니다."),
    ("PREFER_ELEVATOR", "엘리베이터 경유", "가능하면 엘리베이터를 사용하는 경로를 우선합니다."),
    ("AVOID_STEEP_INCLINE", "급경사 제외", "허용 경사도를 초과하는 구간을 제외합니다."),
    ("NEED_LOW_BUS", "저상버스 필요", "버스 이용 시 저상버스 확인 경로를 우선/필수로 적용합니다."),
    ("AVOID_OBSTACLE_STEP", "보도 턱 제외", "허용 높이를 초과하는 보도 턱 구간을 제외합니다."),
    ("AVOID_GENERAL_BUS", "일반 버스 제외", "일반 버스가 포함된 경로를 제외합니다."),
]


async def main():
    async with AsyncSessionLocal() as db:
        for code, name, description in CONDITIONS:
            item = await db.scalar(select(ConditionMaster).where(ConditionMaster.condition_code == code))
            if item:
                item.condition_name = name
                item.description = description
            else:
                db.add(ConditionMaster(condition_code=code, condition_name=name, description=description))
        await db.commit()
        print(f"seeded {len(CONDITIONS)} mobility conditions")


if __name__ == "__main__":
    asyncio.run(main())
