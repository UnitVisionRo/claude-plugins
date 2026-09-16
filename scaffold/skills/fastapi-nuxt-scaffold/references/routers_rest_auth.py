"""Destination: api/routers/rest/auth.py

The browser-facing authentication flow.

Login is two-phase whenever the account has two-factor auth enabled. Phase one verifies the
password and issues nothing but a short-lived, audience-scoped waiting ticket; phase two
verifies the code and only then sets the session cookies. Nothing in between counts as a
session -- `get_current_user` rejects the waiting ticket, and the two-factor endpoints reject
a session token.
"""

from __future__ import annotations

from typing import Annotated

import sqlalchemy as sa
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

import schemas.rest as s
from lib.database import get_session
from lib.enums import TwoFactorMethod
from lib.security import (
    DEVICE_ID_COOKIE,
    JWT_2FA_AUDIENCE,
    REFRESH_TOKEN_COOKIE,
    TWOFA_PENDING_COOKIE,
    create_twofa_pending_token,
    decode_token,
    encrypt_secret,
    hash_password,
    verify_password,
)
from models.user import User, UserTwoFactor
from routers.rest.deps import CurrentUser
from services import auth as auth_service
from services.invites import find_user_by_invite_token
from services.recovery import consume_recovery, find_by_recovery_token, request_recovery

router = APIRouter(prefix="/auth", tags=["auth"])

DbSession = Annotated[AsyncSession, Depends(get_session)]

# One message for both a missing user and a wrong password: anything else is a username oracle.
_BAD_CREDENTIALS = HTTPException(status.HTTP_400_BAD_REQUEST, detail="Incorrect username or password")


async def _load_pending_user(request: Request, db: AsyncSession) -> User:
    """Resolve the user behind the two-factor waiting ticket, re-reading them from the database.

    Up to ten minutes can pass between the password and the code, so nothing about the user is
    carried over from phase one -- they may have been blocked in the meantime.
    """
    expired = HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Verification expired. Please sign in again.")
    token = request.cookies.get(TWOFA_PENDING_COOKIE)
    claims = decode_token(token, JWT_2FA_AUDIENCE) if token else None
    if claims is None:
        raise expired

    user = await db.scalar(sa.select(User).where(User.uuid == claims["sub"]))
    if user is None:
        raise expired
    if user.isBlocked:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="This account is blocked")
    return user


async def _load_twofa(user_id: int, db: AsyncSession) -> UserTwoFactor | None:
    return await db.scalar(sa.select(UserTwoFactor).where(UserTwoFactor.userId == user_id))


@router.post("/login")
async def login(
    body: s.LoginRequest,
    request: Request,
    response: Response,
    background_tasks: BackgroundTasks,
    db: DbSession,
) -> s.LoginResult:
    user = await db.scalar(sa.select(User).where(User.username == body.username))

    # `inviteTokenHash is not None` means the invite was never accepted, so there is no password
    # to check. Refused with the same message as a wrong password -- a pending invite is not
    # something an anonymous caller gets to probe for.
    if user is None or user.inviteTokenHash is not None or not verify_password(user.passwordHash, body.password):
        raise _BAD_CREDENTIALS

    if user.isBlocked:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="This account is blocked")

    twofa = await _load_twofa(user.id, db)
    if twofa is None or twofa.method is None:
        await auth_service.issue_session(user, request, response, db)
        await db.commit()
        return s.LoginResult(twofaRequired=False)

    # Locked out from repeated wrong codes: refuse here, before issuing a ticket or sending a
    # code. Otherwise every correct password would keep mailing codes to a locked account.
    auth_service.ensure_not_locked(twofa)

    # Whoever was signed in in this browser is signed out now: their account must not stay open
    # while a different login waits for its code.
    auth_service.clear_session_cookies(response)

    auth_service.set_pending_cookie(
        response, create_twofa_pending_token(str(user.uuid), auth_service.TWOFA_PENDING_MINUTES)
    )

    if twofa.method == TwoFactorMethod.EMAIL:
        await auth_service.send_email_code(user, twofa, background_tasks)

    await db.commit()
    return s.LoginResult(twofaRequired=True, twofaMethod=twofa.method)


@router.post("/2fa/verify")
async def verify_two_factor(
    body: s.TwoFactorCode,
    request: Request,
    response: Response,
    db: DbSession,
) -> None:
    """Phase two of login: no session yet, the caller is identified by the waiting ticket."""
    user = await _load_pending_user(request, db)
    row = await _load_twofa(user.id, db)
    if row is None or row.method is None:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail="Two-factor authentication is no longer enabled for this account. Please sign in again.",
        )

    auth_service.ensure_not_locked(row)

    if row.method == TwoFactorMethod.TOTP:
        matched_step = auth_service.match_totp_timestep(row.totpSecret, body.code, row.lastTotpTimestep)
        if matched_step is None:
            await auth_service.reject_invalid_code(row, db)
        row.lastTotpTimestep = matched_step
    elif not auth_service.email_code_matches(row, body.code):
        await auth_service.reject_invalid_code(row, db)

    auth_service.clear_code_state(row)
    response.delete_cookie(TWOFA_PENDING_COOKIE, path="/")
    await auth_service.issue_session(user, request, response, db)
    await db.commit()


@router.post("/2fa/resend")
async def resend_two_factor_code(request: Request, background_tasks: BackgroundTasks, db: DbSession) -> None:
    """Re-send the login code by email. The previous code stops working."""
    user = await _load_pending_user(request, db)
    row = await _load_twofa(user.id, db)
    if row is None or row.method != TwoFactorMethod.EMAIL:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail="Codes are only re-sent for email-based two-factor authentication.",
        )

    auth_service.ensure_not_locked(row)
    auth_service.check_resend_allowed(row)
    await auth_service.send_email_code(user, row, background_tasks)
    await db.commit()


@router.post("/refresh")
async def refresh_session(request: Request, response: Response, db: DbSession) -> None:
    """Exchange the refresh cookie for a new access token, rotating the refresh token."""
    refresh_token = request.cookies.get(REFRESH_TOKEN_COOKIE)
    device_id = request.cookies.get(DEVICE_ID_COOKIE)
    if not refresh_token or not device_id:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Session expired")

    await auth_service.rotate_session(refresh_token, device_id, request, response, db)
    await db.commit()


@router.post("/logout")
async def logout(request: Request, response: Response, current_user: CurrentUser, db: DbSession) -> None:
    device_id = request.cookies.get(DEVICE_ID_COOKIE)
    if device_id:
        await auth_service.revoke_session(current_user.id, device_id, db)
        await db.commit()
    auth_service.clear_session_cookies(response)


@router.get("/me")
async def get_me(current_user: CurrentUser) -> s.CurrentUserResult:
    return s.CurrentUserResult.model_validate(current_user)


@router.get("/invite/{token}")
async def get_invite(token: str, db: DbSession) -> s.InvitedUserResult:
    """Public: what the signup page needs to render an invite link it was just handed."""
    user = await find_user_by_invite_token(token, db)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="This invitation is invalid or has already been used")
    return s.InvitedUserResult(email=user.email, name=user.name)


@router.post("/signup")
async def signup(body: s.SignupRequest, db: DbSession) -> None:
    """Accept an invitation: choose a username and password, consuming the token."""
    user = await find_user_by_invite_token(body.inviteToken, db)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="This invitation is invalid or has already been used")

    taken = await db.scalar(
        sa.select(sa.func.count()).select_from(User).where(User.username == body.username, User.id != user.id)
    )
    if taken:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="That username is already taken")

    user.username = body.username
    user.name = body.name
    user.passwordHash = hash_password(body.password)
    # Consuming the token is what turns the row into a real account: it is now allowed to log
    # in, and the link in the invitation email stops working.
    user.inviteTokenHash = None
    await db.commit()


# --- password recovery ------------------------------------------------------------------


@router.post("/recovery")
async def request_password_recovery(
    body: s.RecoveryRequest,
    background_tasks: BackgroundTasks,
    db: DbSession,
) -> None:
    """Email a reset link. Always succeeds, whether or not the account exists.

    Deliberately indiscriminate: a 404 for an unknown username would make this an
    account-enumeration oracle that needs no credentials to query.
    """
    await request_recovery(body.usernameOrEmail, db, background_tasks)
    await db.commit()


@router.get("/recovery/{token}")
async def check_recovery_token(token: str, db: DbSession) -> s.RecoveryTarget:
    """Whether a reset link is still good, and whose account it is.

    Checked before the form is shown, so an expired link says so immediately instead of after
    the user has chosen and typed a password twice.
    """
    user = await find_by_recovery_token(token, db)
    if user is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            detail="This reset link is invalid, expired, or has already been used",
        )
    return s.RecoveryTarget(username=user.username, email=user.email)


@router.post("/password-reset")
async def reset_password(body: s.PasswordResetRequest, response: Response, db: DbSession) -> None:
    """Set a new password from a reset link, ending every existing session."""
    user = await find_by_recovery_token(body.recoveryToken, db)
    if user is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            detail="This reset link is invalid, expired, or has already been used",
        )

    await consume_recovery(user, body.newPassword, db)
    # Every session is gone, including this browser's if it happened to have one.
    auth_service.clear_session_cookies(response)
    await db.commit()


# --- sessions ---------------------------------------------------------------------------


@router.get("/sessions")
async def list_sessions(request: Request, current_user: CurrentUser, db: DbSession) -> list[s.ActiveSession]:
    """Every browser currently signed in as this user."""
    current_device_id = request.cookies.get(DEVICE_ID_COOKIE)
    return [
        s.ActiveSession(
            deviceId=row.deviceId,
            userAgent=row.userAgent,
            ip=row.ip,
            createdAt=row.createdAt,
            lastUsedAt=row.lastUsedAt,
            isCurrent=row.deviceId == current_device_id,
        )
        for row in await auth_service.list_sessions(current_user.id, db)
    ]


@router.delete("/sessions/{device_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_session(
    device_id: str,
    request: Request,
    current_user: CurrentUser,
    db: DbSession,
) -> None:
    """Sign one other browser out, or all of them with `device_id="all"`.

    Never the current one: ending your own session is `POST /auth/logout`, which also clears
    this browser's cookies. Revoking it here would leave the caller holding cookies for a
    session that no longer exists, which reads as a confusing bug rather than a sign-out.
    """
    current_device_id = request.cookies.get(DEVICE_ID_COOKIE)
    if not current_device_id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="No device id on this request")

    if device_id == "all":
        await auth_service.revoke_other_sessions(current_user.id, current_device_id, db)
    elif device_id == current_device_id:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail="Use sign out to end the current session",
        )
    else:
        await auth_service.revoke_session(current_user.id, device_id, db)

    await db.commit()


# --- two-factor self-service ------------------------------------------------------------


@router.get("/2fa")
async def get_two_factor_status(current_user: CurrentUser, db: DbSession) -> s.TwoFactorStatus:
    """Own enrolment state. Never exposes a secret."""
    row = await _load_twofa(current_user.id, db)
    if row is None:
        return s.TwoFactorStatus()
    return s.TwoFactorStatus(method=row.method, pendingMethod=row.pendingMethod)


@router.post("/2fa/setup")
async def setup_two_factor(
    body: s.TwoFactorSetupRequest,
    current_user: CurrentUser,
    background_tasks: BackgroundTasks,
    db: DbSession,
) -> s.TwoFactorSetupResult:
    """Begin enrolment, or a change of method.

    The active method is left alone until a code confirms the pending one, so abandoning this
    halfway leaves the account protected exactly as it was.
    """
    if not verify_password(current_user.passwordHash, body.currentPassword):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Current password is incorrect")

    row = await _load_twofa(current_user.id, db)
    if row is None:
        row = UserTwoFactor(userId=current_user.id, failedAttempts=0)
        db.add(row)

    row.pendingMethod = body.method
    row.pendingTotpSecret = None
    row.failedAttempts = 0
    row.lockedUntil = None

    if body.method == TwoFactorMethod.TOTP:
        secret = auth_service.new_totp_secret()
        row.pendingTotpSecret = encrypt_secret(secret)
        uri = auth_service.totp_provisioning_uri(secret, current_user.username or current_user.email)
        await db.commit()
        return s.TwoFactorSetupResult(otpauthUri=uri, secret=secret)

    await auth_service.send_email_code(current_user, row, background_tasks)
    await db.commit()
    return s.TwoFactorSetupResult()


@router.post("/2fa/confirm")
async def confirm_two_factor(body: s.TwoFactorCode, current_user: CurrentUser, db: DbSession) -> None:
    """Confirm the pending method's code and promote it to the active method."""
    row = await _load_twofa(current_user.id, db)
    if row is None or row.pendingMethod is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="There is no pending setup. Start again.")

    auth_service.ensure_not_locked(row)

    if row.pendingMethod == TwoFactorMethod.TOTP:
        matched_step = auth_service.match_totp_timestep(row.pendingTotpSecret, body.code, row.lastTotpTimestep)
        if matched_step is None:
            await auth_service.reject_invalid_code(row, db)
        row.lastTotpTimestep = matched_step
        row.totpSecret = row.pendingTotpSecret
    else:
        if not auth_service.email_code_matches(row, body.code):
            await auth_service.reject_invalid_code(row, db)
        row.totpSecret = None
        row.lastTotpTimestep = None

    row.method = row.pendingMethod
    row.pendingMethod = None
    row.pendingTotpSecret = None
    auth_service.clear_code_state(row)
    await db.commit()


@router.post("/2fa/disable")
async def disable_two_factor(body: s.PasswordConfirmation, current_user: CurrentUser, db: DbSession) -> None:
    """Turn two-factor auth off: the row is deleted, there is no disabled-but-remembered state."""
    if not verify_password(current_user.passwordHash, body.currentPassword):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Current password is incorrect")

    row = await _load_twofa(current_user.id, db)
    if row is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Two-factor authentication is not enabled")

    await db.delete(row)
    await db.commit()
