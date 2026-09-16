"""Destination: api/services/invites.py

Issuing and mailing invitations.

An invited user is a real `users` row from the moment the invite is created -- that is what
makes an invite listable, re-sendable, and revocable, and what reserves the email address. It
just cannot log in yet: `inviteTokenHash` is non-NULL and there is no password hash.
"""

from __future__ import annotations

import sqlalchemy as sa
from fastapi import BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession

from environment import settings
from lib.mail import render_email, send_mail
from lib.security import fingerprint
from lib.utils import utcnow
from models.user import User
from services.tokens import issue_unique_token


async def issue_invite_token(db: AsyncSession) -> tuple[str, str]:
    """Return `(raw_token, fingerprint)` for a token no other pending invite is using."""
    return await issue_unique_token(db, User.inviteTokenHash)


def invite_url(raw_token: str) -> str:
    return f"{settings.FRONTEND_BASE_URL.rstrip('/')}/signup/{raw_token}"


async def send_invite_email(user: User, raw_token: str, background_tasks: BackgroundTasks) -> str:
    """Queue the invitation email and return the link.

    The link is returned, not just mailed, so an admin can copy it out of the UI -- which is
    also the only way the flow is usable before SMTP is configured. `lib.mail.send_mail` never
    raises, so a dead mail server cannot fail the invite.
    """
    url = invite_url(raw_token)
    body = await render_email("user_invite.html", {"inviteUrl": url})
    background_tasks.add_task(send_mail, user.email, f"You have been invited to {settings.APP_NAME}", body)
    return url


async def find_user_by_invite_token(raw_token: str, db: AsyncSession) -> User | None:
    return await db.scalar(sa.select(User).where(User.inviteTokenHash == fingerprint(raw_token)))


def mark_invited(user: User, token_fingerprint: str, invited_by_id: int | None) -> None:
    user.inviteTokenHash = token_fingerprint
    user.invitedAt = utcnow()
    user.invitedById = invited_by_id
