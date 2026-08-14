from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.models import ConditionMaster
from app.schemas.v2 import ConditionResponse

router = APIRouter(prefix="/conditions", tags=["Conditions"])


@router.get("", response_model=list[ConditionResponse])
async def list_conditions(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(ConditionMaster).order_by(ConditionMaster.condition_id))
    return result.scalars().all()
