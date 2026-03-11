import sqlalchemy as sa
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_admin_user
from app.core.security import hash_secret
from app.db.session import get_db
from app.models.user import User
from app.schemas.user import UserCreate, UserRead

router = APIRouter(prefix="/admin/users", tags=["users"])

VALID_ROLES = {"admin", "user"}


@router.get("/", response_model=list[UserRead])
async def list_users(
    _: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(sa.select(User).order_by(User.created_at.desc()))
    return result.scalars().all()


@router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
async def create_user(
    payload: UserCreate,
    _: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    role = payload.role.lower().strip()
    if role not in VALID_ROLES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Role must be either 'admin' or 'user'",
        )

    existing_user = await db.execute(sa.select(User).where(User.username == payload.username))
    if existing_user.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username is already in use",
        )

    user = User(
        username=payload.username,
        full_name=payload.full_name,
        hashed_password=hash_secret(payload.password),
        role=role,
        is_active=payload.is_active,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user