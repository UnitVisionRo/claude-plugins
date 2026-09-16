"""Destination: api/routers/rest/deps.py

The auth dependencies for the browser-facing surface.

Authentication is a signed, httpOnly cookie, not an `Authorization` header: the console is a
browser app, and a token readable by JavaScript is a token an XSS can exfiltrate. The cost is
that CSRF becomes the browser's job, which `SameSite` handles -- see `COOKIE_SAMESITE`.

The user is loaded from the database on every request, joined against their session so that
revoking a session takes effect immediately. No process-level cache: a cache would have to be
invalidated on block, on role change, and on logout across every worker, and would hand back
detached ORM instances that explode the first time something touches a relationship. One
indexed lookup per request is not the bottleneck worth that.
"""

from __future__ import annotations

from typing import Annotated

import sqlalchemy as sa
from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from lib.database import get_session
from lib.enums import Role
from lib.security import ACCESS_TOKEN_COOKIE, JWT_AUDIENCE, decode_token
from models.user import User, UserSession

_UNAUTHENTICATED = HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Authentication required")


async def get_current_user(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_session)],
) -> User:
    token = request.cookies.get(ACCESS_TOKEN_COOKIE)
    if not token:
        raise _UNAUTHENTICATED

    claims = decode_token(token, JWT_AUDIENCE)
    if claims is None:
        raise _UNAUTHENTICATED

    # Joined rather than looked up separately: a signature that is merely still *valid* is not
    # enough. The session behind it must also still exist, or "sign that other browser out"
    # (and logout, and a password reset) would not take effect until the access token happened
    # to expire -- up to ACCESS_TOKEN_EXP_MINUTES later.
    user = await db.scalar(
        sa.select(User)
        .join(UserSession, UserSession.userId == User.id)
        .where(
            User.uuid == claims["sub"],
            UserSession.deviceId == claims.get("did"),
            UserSession.revokedAt.is_(None),
            UserSession.tokenHash.is_not(None),
        )
    )
    if user is None or user.inviteTokenHash is not None:
        raise _UNAUTHENTICATED
    if user.isBlocked:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="This account is blocked")

    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


async def require_admin(current_user: CurrentUser) -> User:
    if current_user.role != Role.ADMIN:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Administrator access required")
    return current_user


AdminUser = Annotated[User, Depends(require_admin)]
