from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.models import ConditionMaster, User, UserConditionPreference, UserProfile
from app.schemas.v2 import RegisterRequest, UserProfileUpdate, UserResponse
from app.services.security_service import hash_password

router = APIRouter(prefix="/users", tags=["Users"])


async def _build_user_response(db: AsyncSession, user: User) -> UserResponse:
    profile = await db.scalar(select(UserProfile).where(UserProfile.user_id == user.user_id))
    stmt = select(ConditionMaster.condition_code).join(
        UserConditionPreference,
        UserConditionPreference.condition_id == ConditionMaster.condition_id,
    ).where(UserConditionPreference.user_id == user.user_id)
    result = await db.execute(stmt)
    codes = list(result.scalars().all())

    return UserResponse(
        user_id=user.user_id,
        email=user.email,
        nickname=user.nickname,
        mobility_conditions=codes,
        default_preference=profile.default_preference if profile else "BALANCED",
        max_incline_angle=float(profile.max_incline_angle or 8.3) if profile else 8.3,
        max_step_height_cm=int(profile.max_step_height_cm or 3) if profile else 3,
    )


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(request: RegisterRequest, db: AsyncSession = Depends(get_db)):
    exists = await db.scalar(select(User).where(User.email == request.email))
    if exists:
        raise HTTPException(status_code=409, detail="이미 등록된 이메일입니다.")

    user = User(
        email=request.email,
        password_hash=hash_password(request.password),
        nickname=request.nickname,
    )
    db.add(user)
    await db.flush()

    profile = UserProfile(
        user_id=user.user_id,
        default_preference=request.default_preference.value,
        max_incline_angle=request.max_incline_angle,
        max_step_height_cm=request.max_step_height_cm,
    )
    db.add(profile)

    for code in request.mobility_conditions:
        condition = await db.scalar(
            select(ConditionMaster).where(ConditionMaster.condition_code == code.value)
        )
        if not condition:
            condition = ConditionMaster(
                condition_code=code.value,
                condition_name=code.value,
            )
            db.add(condition)
            await db.flush()
        db.add(UserConditionPreference(user_id=user.user_id, condition_id=condition.condition_id))

    await db.commit()
    await db.refresh(user)
    return await _build_user_response(db, user)


@router.get("/{user_id}/profile", response_model=UserResponse)
async def get_profile(user_id: int, db: AsyncSession = Depends(get_db)):
    user = await db.scalar(select(User).where(User.user_id == user_id))
    if not user:
        raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다.")
    return await _build_user_response(db, user)


@router.put("/{user_id}/profile", response_model=UserResponse)
async def update_profile(user_id: int, request: UserProfileUpdate, db: AsyncSession = Depends(get_db)):
    user = await db.scalar(select(User).where(User.user_id == user_id))
    profile = await db.scalar(select(UserProfile).where(UserProfile.user_id == user_id))
    if not user or not profile:
        raise HTTPException(status_code=404, detail="사용자 프로필을 찾을 수 없습니다.")

    profile = await db.scalar(select(UserProfile).where(UserProfile.user_id == user.user_id))
    profile.default_preference = request.default_preference.value
    profile.max_incline_angle = request.max_incline_angle
    profile.max_step_height_cm = request.max_step_height_cm

    await db.execute(
        UserConditionPreference.__table__.delete().where(
            UserConditionPreference.user_id == user_id
        )
    )

    for code in request.mobility_conditions:
        condition = await db.scalar(
            select(ConditionMaster).where(ConditionMaster.condition_code == code.value)
        )
        if not condition:
            condition = ConditionMaster(condition_code=code.value, condition_name=code.value)
            db.add(condition)
            await db.flush()
        db.add(UserConditionPreference(user_id=user_id, condition_id=condition.condition_id))

    await db.commit()
    await db.refresh(user)
    return await _build_user_response(db, user)
