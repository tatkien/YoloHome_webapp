from datetime import datetime, timezone

import sqlalchemy as sa
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_admin_user
from app.core.security import hash_secret
from app.db.db_utils import reset_sequence_to_min_gap
from app.db.session import get_db
from app.models.invitation_key import InvitationKey
from app.models.user import User
from app.schemas.auth import InvitationKeyResponse, InvitationKeyUpdate
from app.schemas.user import UserRead

router = APIRouter(prefix="/admin/users", tags=["users"])


async def _get_user_or_404(db: AsyncSession, user_id: int) -> User:
    result = await db.execute(sa.select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user

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


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: int,
    current_user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete a user account.

    Auth: JWT required. Admin only.

    Raises:
        403: Attempt to delete the last active admin or your own account.
        404: User not found.
    """
    target_user = await _get_user_or_404(db, user_id)

    if target_user.role == "admin" and target_user.is_active:
        active_admin_count = await db.scalar(
            sa.select(sa.func.count())
            .select_from(User)
            .where(User.role == "admin", User.is_active.is_(True))
        )
        if (active_admin_count or 0) <= 1:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cannot delete the last active admin",
            )

    if target_user.id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot delete your own account",
        )

    await db.delete(target_user)
    await db.commit()
