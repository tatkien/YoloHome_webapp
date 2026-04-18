import sqlalchemy as sa
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.config import settings
from app.core.security import create_access_token, hash_secret, verify_secret
from app.db.db_utils import reset_sequence_to_min_gap
from app.db.session import get_db
from app.models.invitation_key import InvitationKey
from app.models.user import User
from app.schemas.auth import LoginRequest, RegistrationRequest, TokenResponse
from app.schemas.user import UserRead

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
async def login(payload: LoginRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(sa.select(User).where(User.username == payload.username))
    user = result.scalar_one_or_none()
    if user is None or not verify_secret(payload.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive",
        )

    return TokenResponse(
        access_token=create_access_token(user.id, user.role),
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user=UserRead.model_validate(user),
    )


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(payload: RegistrationRequest, db: AsyncSession = Depends(get_db)):
    registration_code = payload.registration_code.strip()
    if not registration_code:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Registration code cannot be empty",
        )

    existing_user = await db.execute(sa.select(User).where(User.username == payload.username))
    if existing_user.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username is already in use",
        )

    admin_count = await db.scalar(
        sa.select(sa.func.count()).select_from(User).where(User.role == "admin")
    )

    if admin_count == 0:
        if not settings.SETUP_CODE:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Setup code is not configured",
            )
        if registration_code != settings.SETUP_CODE:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid setup code",
            )
        role = "admin"
    else:
        result = await db.execute(
            sa.select(InvitationKey).order_by(InvitationKey.updated_at.desc())
        )
        invitation = result.scalars().first()
        if invitation is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invitation key is not configured",
            )
        if not verify_secret(registration_code, invitation.key_hash):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid invitation key",
            )
        role = "user"

    user = User(
        username=payload.username,
        full_name=payload.full_name,
        hashed_password=hash_secret(payload.password),
        role=role,
        is_active=True,
    )
    # Keep sequence aligned with current gaps right before INSERT.
    await reset_sequence_to_min_gap(db, "users", "users_id_seq")
    db.add(user)
    await db.commit()
    await db.refresh(user)

    return TokenResponse(
        access_token=create_access_token(user.id, user.role),
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user=UserRead.model_validate(user),
    )


@router.get("/me", response_model=UserRead)
async def read_current_user(current_user: User = Depends(get_current_user)):
    return current_user
