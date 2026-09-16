"""Destination: api/tests/test_auth_flow.py

The whole invite -> signup -> login -> two-factor journey, plus the properties that make it
worth having: the waiting ticket cannot act as a session, a pending invite cannot log in, a
TOTP code cannot be replayed, and wrong codes lock the account.
"""

from __future__ import annotations

import re
import time

import httpx
import pyotp
import sqlalchemy as sa
from pytest import MonkeyPatch
from sqlalchemy.ext.asyncio import AsyncSession

from lib.enums import Role, TwoFactorMethod
from lib.security import ACCESS_TOKEN_COOKIE, REFRESH_TOKEN_COOKIE, TWOFA_PENDING_COOKIE, hash_password
from models.user import User, UserTwoFactor
from services import auth as auth_service

PASSWORD = "Sc4ffold!pass"
NEW_PASSWORD = "Inv1ted!pass"

REST = "/rest"


async def make_admin(db: AsyncSession, username: str = "admin") -> User:
    admin = User(
        username=username,
        email=f"{username}@example.com",
        name="Administrator",
        role=Role.ADMIN,
        passwordHash=hash_password(PASSWORD),
    )
    db.add(admin)
    await db.commit()
    return admin


async def login(client: httpx.AsyncClient, username: str, password: str = PASSWORD) -> httpx.Response:
    return await client.post(f"{REST}/auth/login", json={"username": username, "password": password})


async def test_invite_signup_login_journey(client: httpx.AsyncClient, db: AsyncSession) -> None:
    await make_admin(db)
    assert (await login(client, "admin")).json() == {"twofaRequired": False, "twofaMethod": None}

    # 1. an administrator invites someone
    invite = await client.post(f"{REST}/users/invite", json={"email": "newcomer@example.com", "role": "USER"})
    assert invite.status_code == 201, invite.text
    invite_url = invite.json()["inviteUrl"]
    token = invite_url.rsplit("/", 1)[-1]

    # 2. the link resolves for an anonymous visitor
    lookup = await client.get(f"{REST}/auth/invite/{token}")
    assert lookup.status_code == 200
    assert lookup.json()["email"] == "newcomer@example.com"

    # 3. the invited user cannot log in before accepting -- there is no password yet
    assert (await login(client, "newcomer", PASSWORD)).status_code == 400

    # 4. accepting the invitation
    signup = await client.post(
        f"{REST}/auth/signup",
        json={
            "inviteToken": token,
            "username": "newcomer",
            "name": "New Comer",
            "password": NEW_PASSWORD,
            "confirmPassword": NEW_PASSWORD,
        },
    )
    assert signup.status_code == 200, signup.text

    # 5. the token is consumed -- the emailed link is now dead
    assert (await client.get(f"{REST}/auth/invite/{token}")).status_code == 404

    # 6. and the account works
    result = await login(client, "newcomer", NEW_PASSWORD)
    assert result.status_code == 200
    assert result.json() == {"twofaRequired": False, "twofaMethod": None}

    me = await client.get(f"{REST}/auth/me")
    assert me.status_code == 200
    assert me.json()["username"] == "newcomer"
    assert me.json()["role"] == Role.USER


async def test_signup_rejects_a_weak_password(client: httpx.AsyncClient, db: AsyncSession) -> None:
    await make_admin(db)
    await login(client, "admin")
    invite = await client.post(f"{REST}/users/invite", json={"email": "weak@example.com"})
    token = invite.json()["inviteUrl"].rsplit("/", 1)[-1]

    response = await client.post(
        f"{REST}/auth/signup",
        json={
            "inviteToken": token,
            "username": "weakling",
            "name": "Weak Ling",
            "password": "password",
            "confirmPassword": "password",
        },
    )
    assert response.status_code == 422


async def test_non_admin_cannot_invite(client: httpx.AsyncClient, db: AsyncSession) -> None:
    db.add(User(username="regular", email="regular@example.com", role=Role.USER,
                passwordHash=hash_password(PASSWORD)))
    await db.commit()

    await login(client, "regular")
    response = await client.post(f"{REST}/users/invite", json={"email": "nope@example.com"})
    assert response.status_code == 403


def totp_code(secret: str, step_offset: int = 0) -> str:
    """A TOTP code for the current 30-second step, or a neighbouring one.

    Enrolment spends the step whose code confirmed it, and a spent step can never be replayed
    (see `services.auth.match_totp_timestep`). A test that enrols and then signs in runs both
    inside the same step, so it must ask for the NEXT one -- which is still inside the +/-1
    tolerance window the server accepts. Real users hit this only if they re-authenticate
    within 30 seconds of enrolling.
    """
    return pyotp.TOTP(secret, interval=auth_service.TWOFA_TOTP_INTERVAL).at(
        int(time.time()), counter_offset=step_offset
    )


async def enrol_totp(client: httpx.AsyncClient) -> str:
    """Walk the real enrolment endpoints and return the plaintext TOTP secret."""
    setup = await client.post(f"{REST}/auth/2fa/setup", json={"method": "TOTP", "currentPassword": PASSWORD})
    assert setup.status_code == 200, setup.text
    secret = setup.json()["secret"]
    assert secret and setup.json()["otpauthUri"].startswith("otpauth://totp/")

    confirm = await client.post(f"{REST}/auth/2fa/confirm", json={"code": totp_code(secret)})
    assert confirm.status_code == 200, confirm.text
    return secret


async def test_totp_setup_then_two_phase_login(client: httpx.AsyncClient, db: AsyncSession) -> None:
    await make_admin(db)
    await login(client, "admin")
    secret = await enrol_totp(client)

    assert (await client.get(f"{REST}/auth/2fa")).json()["method"] == TwoFactorMethod.TOTP

    client.cookies.clear()

    # Phase one: the password alone no longer produces a session.
    result = await login(client, "admin")
    assert result.json() == {"twofaRequired": True, "twofaMethod": "TOTP"}
    assert ACCESS_TOKEN_COOKIE not in client.cookies
    assert TWOFA_PENDING_COOKIE in client.cookies

    # The waiting ticket is not a session.
    assert (await client.get(f"{REST}/auth/me")).status_code == 401

    # Phase two.
    verify = await client.post(f"{REST}/auth/2fa/verify", json={"code": totp_code(secret, 1)})
    assert verify.status_code == 200, verify.text
    assert (await client.get(f"{REST}/auth/me")).status_code == 200


async def test_a_code_copied_with_its_space_is_accepted(client: httpx.AsyncClient, db: AsyncSession) -> None:
    """Authenticator apps render the code as "123 456", and people paste exactly that.

    Normalisation therefore has to run BEFORE the `^\\d{6}$` constraint (`mode="before"` in
    `schemas/rest.py`); at the default `mode="after"` the constraint sees the raw value and
    rejects a code that is entirely correct.
    """
    await make_admin(db)
    await login(client, "admin")
    secret = await enrol_totp(client)
    client.cookies.clear()

    await login(client, "admin")
    code = totp_code(secret, 1)
    spaced = f"{code[:3]} {code[3:]}"
    assert (await client.post(f"{REST}/auth/2fa/verify", json={"code": spaced})).status_code == 200
    assert (await client.get(f"{REST}/auth/me")).status_code == 200


async def test_totp_code_cannot_be_replayed(client: httpx.AsyncClient, db: AsyncSession) -> None:
    await make_admin(db)
    await login(client, "admin")
    secret = await enrol_totp(client)

    code = totp_code(secret, 1)
    client.cookies.clear()
    await login(client, "admin")
    assert (await client.post(f"{REST}/auth/2fa/verify", json={"code": code})).status_code == 200

    client.cookies.clear()
    await login(client, "admin")
    # Same code, same 30-second step: refused, because the step was already spent.
    replay = await client.post(f"{REST}/auth/2fa/verify", json={"code": code})
    assert replay.status_code == 400
    assert replay.json()["detail"] == auth_service.INVALID_CODE_MESSAGE


async def test_wrong_codes_lock_the_account(client: httpx.AsyncClient, db: AsyncSession) -> None:
    await make_admin(db)
    await login(client, "admin")
    secret = await enrol_totp(client)
    client.cookies.clear()

    await login(client, "admin")
    for _ in range(auth_service.TWOFA_MAX_FAILED_ATTEMPTS):
        assert (await client.post(f"{REST}/auth/2fa/verify", json={"code": "000000"})).status_code == 400

    # Even the correct code is refused while the lockout holds.
    locked = await client.post(f"{REST}/auth/2fa/verify", json={"code": totp_code(secret, 1)})
    assert locked.status_code == 429

    row = await db.scalar(sa.select(UserTwoFactor))
    assert row is not None and row.lockedUntil is not None


async def test_email_code_login(
    client: httpx.AsyncClient,
    db: AsyncSession,
    monkeypatch: MonkeyPatch,
) -> None:
    """The EMAIL method end-to-end, reading the code out of a captured email."""
    sent: list[tuple[str, str, str]] = []

    async def capture(to: str, subject: str, html_body: str) -> None:
        sent.append((to, subject, html_body))

    # The code is rendered into the email body and stored only as a digest, so capturing the
    # mail is the only way to learn it -- which is exactly the property under test.
    monkeypatch.setattr("lib.mail.send_mail", capture)
    monkeypatch.setattr("services.auth.send_mail", capture)

    await make_admin(db)
    await login(client, "admin")

    setup = await client.post(f"{REST}/auth/2fa/setup", json={"method": "EMAIL", "currentPassword": PASSWORD})
    assert setup.status_code == 200
    assert setup.json() == {"otpauthUri": None, "secret": None}

    code = _extract_code(sent[-1][2])
    assert (await client.post(f"{REST}/auth/2fa/confirm", json={"code": code})).status_code == 200

    client.cookies.clear()
    result = await login(client, "admin")
    assert result.json() == {"twofaRequired": True, "twofaMethod": "EMAIL"}

    login_code = _extract_code(sent[-1][2])
    assert (await client.post(f"{REST}/auth/2fa/verify", json={"code": login_code})).status_code == 200
    assert (await client.get(f"{REST}/auth/me")).status_code == 200


async def test_email_code_resend_is_rate_limited(
    client: httpx.AsyncClient,
    db: AsyncSession,
    monkeypatch: MonkeyPatch,
) -> None:
    sent: list[str] = []

    async def capture(to: str, subject: str, html_body: str) -> None:
        sent.append(html_body)

    monkeypatch.setattr("services.auth.send_mail", capture)

    await make_admin(db)
    await login(client, "admin")
    await client.post(f"{REST}/auth/2fa/setup", json={"method": "EMAIL", "currentPassword": PASSWORD})
    await client.post(f"{REST}/auth/2fa/confirm", json={"code": _extract_code(sent[-1])})

    client.cookies.clear()
    await login(client, "admin")
    assert (await client.post(f"{REST}/auth/2fa/resend")).status_code == 429


async def test_disable_two_factor_requires_the_password(client: httpx.AsyncClient, db: AsyncSession) -> None:
    await make_admin(db)
    await login(client, "admin")
    await enrol_totp(client)

    wrong = await client.post(f"{REST}/auth/2fa/disable", json={"currentPassword": "not-the-password"})
    assert wrong.status_code == 400

    right = await client.post(f"{REST}/auth/2fa/disable", json={"currentPassword": PASSWORD})
    assert right.status_code == 200
    assert (await client.get(f"{REST}/auth/2fa")).json()["method"] is None


async def test_logout_revokes_the_session(client: httpx.AsyncClient, db: AsyncSession) -> None:
    await make_admin(db)
    await login(client, "admin")
    assert (await client.get(f"{REST}/auth/me")).status_code == 200

    assert (await client.post(f"{REST}/auth/logout")).status_code == 200
    assert (await client.get(f"{REST}/auth/me")).status_code == 401
    # The refresh cookie is gone too, so the session cannot be resurrected.
    assert (await client.post(f"{REST}/auth/refresh")).status_code == 401


async def test_refresh_rotates_the_token_and_keeps_the_session(client: httpx.AsyncClient, db: AsyncSession) -> None:
    """The happy path the frontend depends on when an access token expires mid-session."""
    await make_admin(db)
    await login(client, "admin")
    first_refresh = client.cookies[REFRESH_TOKEN_COOKIE]

    assert (await client.post(f"{REST}/auth/refresh")).status_code == 200
    second_refresh = client.cookies[REFRESH_TOKEN_COOKIE]

    # Rotated, not reissued: a stolen refresh token is good for one use at most.
    assert second_refresh != first_refresh
    assert (await client.get(f"{REST}/auth/me")).status_code == 200

    # The superseded token is dead even though the session it belonged to is still alive.
    client.cookies.set(REFRESH_TOKEN_COOKIE, first_refresh)
    assert (await client.post(f"{REST}/auth/refresh")).status_code == 401


async def test_refresh_fails_once_the_session_is_revoked(client: httpx.AsyncClient, db: AsyncSession) -> None:
    await make_admin(db)
    await login(client, "admin")
    await client.post(f"{REST}/auth/logout")
    assert (await client.post(f"{REST}/auth/refresh")).status_code == 401


async def test_blocked_user_cannot_log_in(client: httpx.AsyncClient, db: AsyncSession) -> None:
    admin = await make_admin(db)
    admin.isBlocked = True
    await db.commit()

    assert (await login(client, "admin")).status_code == 403


def _extract_code(html_body: str) -> str:
    match = re.search(r">(\d{6})<", html_body)
    assert match, f"no six-digit code in the email body: {html_body[:400]}"
    return match.group(1)
