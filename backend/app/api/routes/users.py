from datetime import datetime, timezone

import sqlalchemy as sa
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_admin_user
from app.core.security import hash_secret
from app.db.session import get_db
from app.models.invitation_key import InvitationKey
from app.models.user import User
from app.schemas.auth import InvitationKeyResponse, InvitationKeyUpdate
from app.schemas.user import UserRead

router = APIRouter(prefix="/admin/users", tags=["users"])

@router.get("/", response_model=list[UserRead])
async def list_users(
    _: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(sa.select(User).order_by(User.created_at.desc()))
    return result.scalars().all()


@router.put("/invitation-key", response_model=InvitationKeyResponse)
async def set_invitation_key(
    payload: InvitationKeyUpdate,
    current_user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    key = payload.invitation_key.strip()
    if not key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invitation key cannot be empty",
        )

    result = await db.execute(
        sa.select(InvitationKey).order_by(InvitationKey.updated_at.desc())
    )
    invitation = result.scalars().first()
    now = datetime.now(timezone.utc)
    if invitation is None:
        invitation = InvitationKey(
            key_hash=hash_secret(key),
            updated_by_id=current_user.id,
            updated_at=now,
        )
        db.add(invitation)
    else:
        invitation.key_hash = hash_secret(key)
        invitation.updated_by_id = current_user.id
        invitation.updated_at = now

    await db.commit()
    await db.refresh(invitation)
    return InvitationKeyResponse(
        updated_at=invitation.updated_at,
        updated_by_id=invitation.updated_by_id,
    )
