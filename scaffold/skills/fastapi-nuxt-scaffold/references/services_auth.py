"""Destination: api/services/auth.py

Session lifecycle and two-factor policy. Everything here takes the request's `AsyncSession`
as a parameter and never commits -- the router decides the transaction boundary.
"""

from __future__ import annotations

import hmac
import time
import uuid
from datetime import timedelta

import pyotp
import sqlalchemy as sa
from fastapi import BackgroundTasks, HTTPException, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from environment import settings
from lib.mail import render_email, send_mail
from lib.security import (
    ACCESS_TOKEN_COOKIE,
    DEVICE_ID_COOKIE,
    REFRESH_TOKEN_COOKIE,
    TWOFA_PENDING_COOKIE,
    create_access_token,
    decrypt_secret,
    fingerprint,
    generate_numeric_code,
    generate_token,
)
from lib.utils import utcnow
from models.user import User, UserSession, UserTwoFactor

# Two-factor policy. Fixed values rather than settings: nobody tunes these per installation,
# and one more knob in `.env` is one more thing to get wrong on a fresh deployment.
TWOFA_PENDING_MINUTES = 10  # window between password and code (ticket lifetime AND code lifetime)
TWOFA_EMAIL_RESEND_SECONDS = 60  # minimum gap between two mailed codes
TWOFA_MAX_FAILED_ATTEMPTS = 5  # wrong codes in a row before a lockout
TWOFA_LOCK_MINUTES = 15  # how long that lockout lasts
TWOFA_TOTP_VALID_WINDOW = 1  # +/-30s of clock tolerance for authenticator codes
TWOFA_TOTP_INTERVAL = 30  # TOTP time step, in seconds

# One message for every rejected code -- wrong, expired, or replayed. Distinguishing them would
# tell an attacker which check failed.
INVALID_CODE_MESSAGE = "Invalid or expired code"


def _set_cookie(response: Response, key: str, value: str, max_age: int) -> None:
    response.set_cookie(
        key=key,
        value=value,
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite=settings.COOKIE_SAMESITE,  # type: ignore[arg-type]
        max_age=max_age,
        path="/",
    )


def set_pending_cookie(response: Response, token: str) -> None:
    """The two-factor waiting ticket, under the same cookie policy as the session cookies."""
    _set_cookie(response, TWOFA_PENDING_COOKIE, token, TWOFA_PENDING_MINUTES * 60)


def clear_session_cookies(response: Response) -> None:
    for cookie in (ACCESS_TOKEN_COOKIE, REFRESH_TOKEN_COOKIE):
        response.delete_cookie(cookie, path="/")


async def issue_session(user: User, request: Request, response: Response, db: AsyncSession) -> None:
    """Set the session cookies and record the login in `user_sessions`.

    Shared by plain login and by two-factor confirmation -- authentication is complete only
    once this has run. Does not commit; the caller owns the transaction.
    """
    device_id = request.cookies.get(DEVICE_ID_COOKIE) or str(uuid.uuid4())
    refresh_token = generate_token()
    now = utcnow()

    existing = await db.scalar(
        sa.select(UserSession).where(
            UserSession.userId == user.id,
            UserSession.deviceId == device_id,
            UserSession.revokedAt.is_(None),
        )
    )
    session_row = existing or UserSession(userId=user.id, deviceId=device_id)
    session_row.tokenHash = fingerprint(refresh_token)
    session_row.ip = request.client.host if request.client else None
    session_row.userAgent = (request.headers.get("user-agent") or "")[:255] or None
    session_row.lastUsedAt = now
    session_row.expiresAt = now + timedelta(days=settings.REFRESH_TOKEN_EXP_DAYS)
    session_row.revokedAt = None
    if existing is None:
        db.add(session_row)

    refresh_max_age = settings.REFRESH_TOKEN_EXP_DAYS * 24 * 60 * 60
    _set_cookie(response, ACCESS_TOKEN_COOKIE, create_access_token(str(user.uuid), device_id),
                settings.ACCESS_TOKEN_EXP_MINUTES * 60)
    _set_cookie(response, REFRESH_TOKEN_COOKIE, refresh_token, refresh_max_age)
    _set_cookie(response, DEVICE_ID_COOKIE, device_id, refresh_max_age)


async def rotate_session(
    raw_token: str,
    device_id: str,
    request: Request,
    response: Response,
    db: AsyncSession,
) -> User:
    """Validate a refresh token, issue a new one in its place, and return the user.

    Rotation on every use: a stolen refresh token is good for one request at most, and the
    legitimate browser's next refresh fails loudly instead of sharing the session silently.
    """
    session_row = await db.scalar(
        sa.select(UserSession).where(
            UserSession.tokenHash == fingerprint(raw_token),
            UserSession.revokedAt.is_(None),
        )
    )
    unauthorized = HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Session expired")

    now = utcnow()
    if (
        session_row is None
        or session_row.deviceId != device_id
        or session_row.expiresAt < now
        or session_row.lastUsedAt < now - timedelta(days=settings.REFRESH_TOKEN_IDLE_DAYS)
    ):
        raise unauthorized

    user = await db.scalar(sa.select(User).where(User.id == session_row.userId, User.isBlocked.is_(False)))
    if user is None:
        raise unauthorized

    new_refresh_token = generate_token()
    session_row.tokenHash = fingerprint(new_refresh_token)
    session_row.lastUsedAt = now
    session_row.expiresAt = now + timedelta(days=settings.REFRESH_TOKEN_EXP_DAYS)

    refresh_max_age = settings.REFRESH_TOKEN_EXP_DAYS * 24 * 60 * 60
    _set_cookie(response, ACCESS_TOKEN_COOKIE, create_access_token(str(user.uuid), device_id),
                settings.ACCESS_TOKEN_EXP_MINUTES * 60)
    _set_cookie(response, REFRESH_TOKEN_COOKIE, new_refresh_token, refresh_max_age)
    return user


async def revoke_session(user_id: int, device_id: str, db: AsyncSession) -> None:
    await db.execute(
        sa.update(UserSession)
        .where(
            UserSession.userId == user_id,
            UserSession.deviceId == device_id,
            UserSession.revokedAt.is_(None),
        )
        .values(revokedAt=utcnow(), tokenHash=None)
    )


async def revoke_other_sessions(user_id: int, keep_device_id: str, db: AsyncSession) -> None:
    """Sign out everywhere except the browser making the request."""
    await db.execute(
        sa.update(UserSession)
        .where(
            UserSession.userId == user_id,
            UserSession.deviceId != keep_device_id,
            UserSession.revokedAt.is_(None),
        )
        .values(revokedAt=utcnow(), tokenHash=None)
    )


async def list_sessions(user_id: int, db: AsyncSession) -> list[UserSession]:
    """Every session still able to refresh itself, newest use first.

    `tokenHash IS NOT NULL` as well as `revokedAt IS NULL`: revocation clears the hash, and a
    row that somehow lost its token cannot be used to refresh either, so showing it as an
    active session would be a lie.
    """
    rows = await db.scalars(
        sa.select(UserSession)
        .where(
            UserSession.userId == user_id,
            UserSession.revokedAt.is_(None),
            UserSession.tokenHash.is_not(None),
        )
        .order_by(UserSession.lastUsedAt.desc())
    )
    return list(rows.all())


# --- two-factor ------------------------------------------------------------------------


def ensure_not_locked(row: UserTwoFactor) -> None:
    """Refuse while the account is in a lockout from repeated wrong codes."""
    if row.lockedUntil and row.lockedUntil > utcnow():
        minutes = max(1, int((row.lockedUntil - utcnow()).total_seconds() // 60) + 1)
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Too many incorrect codes. Try again in {minutes} minutes.",
        )


async def reject_invalid_code(row: UserTwoFactor, db: AsyncSession) -> None:
    """Count the failed attempt, COMMIT it, then raise.

    Committing before the raise is the point: otherwise the exception rolls the transaction
    back, the counter never increases, and the lockout never happens.

    On reaching the threshold the counter resets along with the lock, so once the 15 minutes
    are up the user gets a full set of attempts again.
    """
    row.failedAttempts = (row.failedAttempts or 0) + 1
    if row.failedAttempts >= TWOFA_MAX_FAILED_ATTEMPTS:
        row.lockedUntil = utcnow() + timedelta(minutes=TWOFA_LOCK_MINUTES)
        row.failedAttempts = 0
    await db.commit()
    raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=INVALID_CODE_MESSAGE)


def match_totp_timestep(encrypted_secret: str | None, code: str, last_timestep: int | None) -> int | None:
    """Return the time step that matched, or None if the code is refused.

    `pyotp.TOTP.verify()` only returns a bool, so it cannot say WHICH step matched. Without
    that, replay protection would have to record the current step, leaving the previous step's
    code reusable -- hence walking the window explicitly.

    A step already accepted (or older) is refused, which is what stops replay.
    """
    # `\d` in the schema validator also matches non-ASCII digits, and `hmac.compare_digest`
    # raises TypeError on non-ASCII strings. Refuse those like any other wrong code.
    if not code.isascii():
        return None

    secret = decrypt_secret(encrypted_secret) if encrypted_secret else None
    if not secret:
        return None

    totp = pyotp.TOTP(secret, interval=TWOFA_TOTP_INTERVAL)
    now_ts = int(time.time())
    current_step = now_ts // TWOFA_TOTP_INTERVAL

    for offset in range(-TWOFA_TOTP_VALID_WINDOW, TWOFA_TOTP_VALID_WINDOW + 1):
        if hmac.compare_digest(totp.at(now_ts, counter_offset=offset), code):
            matched_step = current_step + offset
            if last_timestep is not None and matched_step <= last_timestep:
                return None
            return matched_step

    return None


def email_code_matches(row: UserTwoFactor, code: str) -> bool:
    """Constant-time comparison against the stored digest, plus the expiry check."""
    if not row.emailCodeHash or not row.emailCodeExpiresAt:
        return False
    if row.emailCodeExpiresAt < utcnow():
        return False
    return hmac.compare_digest(row.emailCodeHash, fingerprint(code))


def clear_code_state(row: UserTwoFactor) -> None:
    """Wipe every single-use artefact after a code is accepted."""
    row.failedAttempts = 0
    row.lockedUntil = None
    row.emailCodeHash = None
    row.emailCodeExpiresAt = None
    row.emailCodeSentAt = None


async def send_email_code(user: User, row: UserTwoFactor, background_tasks: BackgroundTasks) -> None:
    """Generate a fresh six-digit code, store its digest, and mail it.

    Any previous code stops working the moment this runs. Does not commit.
    """
    code = generate_numeric_code()
    now = utcnow()
    row.emailCodeHash = fingerprint(code)
    row.emailCodeExpiresAt = now + timedelta(minutes=TWOFA_PENDING_MINUTES)
    row.emailCodeSentAt = now

    body = await render_email(
        "twofa_code.html",
        {"code": code, "userName": user.name, "expiryMinutes": TWOFA_PENDING_MINUTES},
    )
    background_tasks.add_task(send_mail, user.email, "Your verification code", body)


def check_resend_allowed(row: UserTwoFactor) -> None:
    if not row.emailCodeSentAt:
        return
    elapsed = (utcnow() - row.emailCodeSentAt).total_seconds()
    if elapsed < TWOFA_EMAIL_RESEND_SECONDS:
        wait = int(TWOFA_EMAIL_RESEND_SECONDS - elapsed) + 1
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"A code was just sent. Try again in {wait} seconds.",
        )


def totp_provisioning_uri(secret: str, account: str) -> str:
    return pyotp.TOTP(secret, interval=TWOFA_TOTP_INTERVAL).provisioning_uri(
        name=account, issuer_name=settings.APP_NAME
    )


def new_totp_secret() -> str:
    return pyotp.random_base32()

