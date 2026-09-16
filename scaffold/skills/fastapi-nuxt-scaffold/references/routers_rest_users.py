"""Destination: api/routers/rest/users.py

User administration: inviting people, listing them, and the one two-factor operation an
administrator is allowed to perform on someone else's account.

Users are addressed by `uuid` in every path. The BIGINT primary key never leaves the process
(root CLAUDE.md), and a sequential id in a URL would also let anyone count the user table.
"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

import sqlalchemy as sa
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

import schemas.rest as s
from lib.database import get_session
from models.user import User, UserTwoFactor
from routers.rest.deps import AdminUser
from services.invites import issue_invite_token, mark_invited, send_invite_email

router = APIRouter(prefix="/users", tags=["users"])

DbSession = Annotated[AsyncSession, Depends(get_session)]


@router.get("")
async def list_users(admin: AdminUser, db: DbSession) -> list[s.UserListItem]:
    users = (await db.scalars(sa.select(User).order_by(User.createdAt.desc()))).all()
    return [s.UserListItem.model_validate(user) for user in users]


@router.post("/invite", status_code=status.HTTP_201_CREATED)
async def invite_user(
    body: s.InviteRequest,
    admin: AdminUser,
    background_tasks: BackgroundTasks,
    db: DbSession,
) -> s.InviteResult:
    """Create a pending user and mail them an invitation link.

    The invited row reserves the email address immediately, which is why a duplicate email is
    a 409 rather than a second invitation.
    """
    raw_token, token_fingerprint = await issue_invite_token(db)

    user = User(email=body.email, name=body.name, role=body.role)
    mark_invited(user, token_fingerprint, admin.id)
    db.add(user)

    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, detail="A user with that email address already exists") from None

    url = await send_invite_email(user, raw_token, background_tasks)
    await db.commit()
    return s.InviteResult(inviteUrl=url)


@router.post("/{user_uuid}/invite/resend")
async def resend_invite(
    user_uuid: UUID,
    admin: AdminUser,
    background_tasks: BackgroundTasks,
    db: DbSession,
) -> s.InviteResult:
    """Issue a FRESH token and mail it again. Any previous link stops working."""
    user = await db.scalar(sa.select(User).where(User.uuid == user_uuid))
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="User not found")
    if user.inviteTokenHash is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="This user has already accepted their invitation")

    raw_token, token_fingerprint = await issue_invite_token(db)
    mark_invited(user, token_fingerprint, user.invitedById or admin.id)

    url = await send_invite_email(user, raw_token, background_tasks)
    await db.commit()
    return s.InviteResult(inviteUrl=url)


@router.get("/check-username")
async def check_username(db: DbSession, username: str = Query(..., min_length=1)) -> bool:
    """True when the username is free. Public -- the signup form needs it before any session exists.

    This does leak whether a username exists, which is the unavoidable cost of telling someone
    their chosen name is taken. It is why login refuses with one message for both a bad username
    and a bad password: knowing a name exists must not get an attacker any further.
    """
    taken = await db.scalar(sa.select(sa.func.count()).select_from(User).where(User.username == username))
    return not taken


@router.delete("/{user_uuid}/2fa", status_code=status.HTTP_204_NO_CONTENT)
async def admin_reset_two_factor(user_uuid: UUID, admin: AdminUser, db: DbSession) -> None:
    """Reset two-factor auth for a user who lost their phone.

    The only recovery path -- there are no backup codes. Afterwards the user signs in with
    their password alone and can enrol again.
    """
    user = await db.scalar(sa.select(User).where(User.uuid == user_uuid))
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="User not found")

    row = await db.scalar(sa.select(UserTwoFactor).where(UserTwoFactor.userId == user.id))
    if row is not None:
        await db.delete(row)
        await db.commit()
