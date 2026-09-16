"""Destination: api/services/recovery.py

Password recovery: "I forgot my password, email me a way back in".

Two rules shape everything here:

1. **The endpoint must never reveal whether an account exists.** `request_recovery` returns
   the same way for a known username, an unknown one, and one that has not accepted its
   invitation yet. An endpoint that 404s on unknown users is a free account-enumeration oracle,
   reachable without any credentials at all.
2. **A reset link is a live credential sitting in an inbox.** So it is single-use, expires in
   `RECOVERY_TOKEN_EXP_MINUTES`, is stored only as a fingerprint, and -- when used -- takes
   every existing session with it (`consume_recovery`). Someone resetting a password is often
   doing it *because* they think somebody else has the old one.
"""

from __future__ import annotations

from datetime import timedelta

import sqlalchemy as sa
from fastapi import BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession

from environment import settings
from lib.mail import render_email, send_mail
from lib.security import fingerprint, hash_password
from lib.utils import utcnow
from models.user import User, UserSession
from services.tokens import issue_unique_token


def recovery_url(raw_token: str) -> str:
    return f"{settings.FRONTEND_BASE_URL.rstrip('/')}/password-reset/{raw_token}"


async def request_recovery(username_or_email: str, db: AsyncSession, background_tasks: BackgroundTasks) -> None:
    """Mail a reset link if -- and only if -- the address belongs to a usable account.

    Returns normally either way; see rule 1 above. Does not commit.
    """
    needle = username_or_email.strip()
    user = await db.scalar(
        sa.select(User).where(
            sa.or_(User.username == needle, sa.func.lower(User.email) == needle.lower()),
            # A pending invitee has no password to reset -- they already have a link, and
            # letting this issue a second kind of link would be a way around the invitation.
            User.inviteTokenHash.is_(None),
            User.isBlocked.is_(False),
        )
    )
    if user is None:
        return

    raw_token, token_fingerprint = await issue_unique_token(db, User.recoveryTokenHash)
    user.recoveryTokenHash = token_fingerprint
    user.recoveryRequestedAt = utcnow()

    body = await render_email(
        "password_reset.html",
        {
            "resetUrl": recovery_url(raw_token),
            "userName": user.name,
            "expiryMinutes": settings.RECOVERY_TOKEN_EXP_MINUTES,
        },
    )
    background_tasks.add_task(send_mail, user.email, f"Reset your {settings.APP_NAME} password", body)


async def find_by_recovery_token(raw_token: str, db: AsyncSession) -> User | None:
    """The user a reset token belongs to, or None if it is unknown, expired, or spent."""
    user = await db.scalar(sa.select(User).where(User.recoveryTokenHash == fingerprint(raw_token)))
    if user is None or user.isBlocked or user.recoveryRequestedAt is None:
        return None

    if utcnow() - user.recoveryRequestedAt > timedelta(minutes=settings.RECOVERY_TOKEN_EXP_MINUTES):
        return None

    return user


async def consume_recovery(user: User, new_password: str, db: AsyncSession) -> None:
    """Set the new password, burn the token, and end every existing session.

    Signing the old sessions out is the point of the last step: if the reset was prompted by
    someone else knowing the password, leaving their session alive would defeat the reset.
    Does not commit.
    """
    user.passwordHash = hash_password(new_password)
    user.recoveryTokenHash = None
    user.recoveryRequestedAt = None

    await db.execute(
        sa.update(UserSession)
        .where(UserSession.userId == user.id, UserSession.revokedAt.is_(None))
        .values(revokedAt=utcnow(), tokenHash=None)
    )
