"""Destination: api/tests/test_recovery_and_sessions.py

Password recovery and the active-session list.

The properties under test are mostly the negative ones -- a reset link that must not be
reusable, an endpoint that must not reveal whether an account exists, a revoked browser that
must not be able to refresh itself. Those are the parts that look fine by hand.
"""

from __future__ import annotations

import re
from datetime import timedelta

import httpx
import pytest
from pytest import MonkeyPatch
from sqlalchemy.ext.asyncio import AsyncSession

from environment import settings
from lib.enums import Role
from lib.security import (
    ACCESS_TOKEN_COOKIE,
    DEVICE_ID_COOKIE,
    REFRESH_TOKEN_COOKIE,
    hash_password,
    verify_password,
)
from lib.utils import utcnow
from models.user import User

PASSWORD = "Sc4ffold!pass"
NEW_PASSWORD = "Rec0vered!pass"
REST = "/rest"


@pytest.fixture
def mailbox(monkeypatch: MonkeyPatch) -> list[str]:
    """Capture outgoing email bodies -- the reset token only exists inside one."""
    sent: list[str] = []

    async def capture(to: str, subject: str, html_body: str) -> None:
        sent.append(html_body)

    monkeypatch.setattr("services.recovery.send_mail", capture)
    return sent


async def make_user(db: AsyncSession, username: str = "person", email: str = "person@example.com") -> User:
    user = User(username=username, email=email, name="A Person", role=Role.USER,
                passwordHash=hash_password(PASSWORD))
    db.add(user)
    await db.commit()
    return user


async def login(client: httpx.AsyncClient, username: str = "person", password: str = PASSWORD) -> httpx.Response:
    return await client.post(f"{REST}/auth/login", json={"username": username, "password": password})


def reset_token(html_body: str) -> str:
    match = re.search(r"/password-reset/([A-Za-z0-9_-]+)", html_body)
    assert match, f"no reset link in the email body: {html_body[:400]}"
    return match.group(1)


# --- password recovery -------------------------------------------------------------------


async def test_recovery_by_username_then_reset(client: httpx.AsyncClient, db: AsyncSession, mailbox: list[str]) -> None:
    user = await make_user(db)

    assert (await client.post(f"{REST}/auth/recovery", json={"usernameOrEmail": "person"})).status_code == 200
    token = reset_token(mailbox[-1])

    # The page checks the link before asking for a password, and learns whose account it is
    # so it can show that -- someone with two accounts needs to know which one they are changing.
    check = await client.get(f"{REST}/auth/recovery/{token}")
    assert check.status_code == 200
    assert check.json() == {"username": "person", "email": "person@example.com"}

    reset = await client.post(
        f"{REST}/auth/password-reset",
        json={"recoveryToken": token, "newPassword": NEW_PASSWORD, "confirmPassword": NEW_PASSWORD},
    )
    assert reset.status_code == 200, reset.text

    await db.refresh(user)
    assert verify_password(user.passwordHash, NEW_PASSWORD)
    assert user.recoveryTokenHash is None

    assert (await login(client, password=NEW_PASSWORD)).status_code == 200
    assert (await login(client, password=PASSWORD)).status_code == 400


async def test_recovery_by_email_is_case_insensitive(
    client: httpx.AsyncClient,
    db: AsyncSession,
    mailbox: list[str],
) -> None:
    await make_user(db)
    response = await client.post(f"{REST}/auth/recovery", json={"usernameOrEmail": "PERSON@Example.COM"})
    assert response.status_code == 200
    assert len(mailbox) == 1


async def test_recovery_reveals_nothing_about_unknown_accounts(
    client: httpx.AsyncClient,
    db: AsyncSession,
    mailbox: list[str],
) -> None:
    """The whole point: identical answer for a real and an imaginary account, and no email."""
    await make_user(db)
    known = await client.post(f"{REST}/auth/recovery", json={"usernameOrEmail": "person"})
    unknown = await client.post(f"{REST}/auth/recovery", json={"usernameOrEmail": "nobody"})

    assert known.status_code == unknown.status_code == 200
    assert known.text == unknown.text
    assert len(mailbox) == 1  # only the real account was mailed


async def test_a_pending_invitee_gets_no_reset_link(
    client: httpx.AsyncClient,
    db: AsyncSession,
    mailbox: list[str],
) -> None:
    """They have no password yet; a second kind of link would be a way around the invitation."""
    db.add(User(email="invited@example.com", role=Role.USER, inviteTokenHash="x" * 64))
    await db.commit()

    response = await client.post(f"{REST}/auth/recovery", json={"usernameOrEmail": "invited@example.com"})
    assert response.status_code == 200
    assert mailbox == []


async def test_a_reset_token_works_once(client: httpx.AsyncClient, db: AsyncSession, mailbox: list[str]) -> None:
    await make_user(db)
    await client.post(f"{REST}/auth/recovery", json={"usernameOrEmail": "person"})
    token = reset_token(mailbox[-1])

    body = {"recoveryToken": token, "newPassword": NEW_PASSWORD, "confirmPassword": NEW_PASSWORD}
    assert (await client.post(f"{REST}/auth/password-reset", json=body)).status_code == 200
    assert (await client.post(f"{REST}/auth/password-reset", json=body)).status_code == 404


async def test_an_expired_reset_token_is_refused(
    client: httpx.AsyncClient,
    db: AsyncSession,
    mailbox: list[str],
) -> None:
    user = await make_user(db)
    await client.post(f"{REST}/auth/recovery", json={"usernameOrEmail": "person"})
    token = reset_token(mailbox[-1])

    user.recoveryRequestedAt = utcnow() - timedelta(minutes=settings.RECOVERY_TOKEN_EXP_MINUTES + 1)
    await db.commit()

    assert (await client.get(f"{REST}/auth/recovery/{token}")).status_code == 404
    response = await client.post(
        f"{REST}/auth/password-reset",
        json={"recoveryToken": token, "newPassword": NEW_PASSWORD, "confirmPassword": NEW_PASSWORD},
    )
    assert response.status_code == 404


async def test_reset_rejects_a_weak_password(client: httpx.AsyncClient, db: AsyncSession, mailbox: list[str]) -> None:
    await make_user(db)
    await client.post(f"{REST}/auth/recovery", json={"usernameOrEmail": "person"})
    token = reset_token(mailbox[-1])

    response = await client.post(
        f"{REST}/auth/password-reset",
        json={"recoveryToken": token, "newPassword": "password", "confirmPassword": "password"},
    )
    assert response.status_code == 422


async def test_reset_signs_every_session_out(client: httpx.AsyncClient, db: AsyncSession, mailbox: list[str]) -> None:
    """A reset is often prompted by someone else knowing the password."""
    await make_user(db)
    await login(client)
    assert (await client.get(f"{REST}/auth/me")).status_code == 200

    await client.post(f"{REST}/auth/recovery", json={"usernameOrEmail": "person"})
    token = reset_token(mailbox[-1])
    await client.post(
        f"{REST}/auth/password-reset",
        json={"recoveryToken": token, "newPassword": NEW_PASSWORD, "confirmPassword": NEW_PASSWORD},
    )

    assert (await client.get(f"{REST}/auth/me")).status_code == 401
    assert (await client.post(f"{REST}/auth/refresh")).status_code == 401


# --- sessions ----------------------------------------------------------------------------


async def test_sessions_list_marks_the_current_browser(client: httpx.AsyncClient, db: AsyncSession) -> None:
    await make_user(db)
    await login(client)

    sessions = (await client.get(f"{REST}/auth/sessions")).json()
    assert len(sessions) == 1
    assert sessions[0]["isCurrent"] is True
    assert sessions[0]["deviceId"] == client.cookies[DEVICE_ID_COOKIE]


async def test_revoking_another_browser_kills_its_refresh(
    client: httpx.AsyncClient,
    second_client: httpx.AsyncClient,
    db: AsyncSession,
) -> None:
    """Two browsers, one signed out remotely -- the revoked one must not be able to refresh."""
    await make_user(db)
    await login(client)
    first_device = client.cookies[DEVICE_ID_COOKIE]

    await login(second_client)
    second_device = second_client.cookies[DEVICE_ID_COOKIE]
    assert second_device != first_device
    assert len((await client.get(f"{REST}/auth/sessions")).json()) == 2

    assert (await client.request("DELETE", f"{REST}/auth/sessions/{second_device}")).status_code == 204

    # The revoked browser still holds its cookies, but they are worth nothing now.
    assert (await second_client.post(f"{REST}/auth/refresh")).status_code == 401

    remaining = (await client.get(f"{REST}/auth/sessions")).json()
    assert [row["deviceId"] for row in remaining] == [first_device]


async def test_revoke_all_keeps_the_current_browser(
    client: httpx.AsyncClient,
    second_client: httpx.AsyncClient,
    db: AsyncSession,
) -> None:
    await make_user(db)
    await login(client)
    first_device = client.cookies[DEVICE_ID_COOKIE]

    await login(second_client)
    assert (await client.request("DELETE", f"{REST}/auth/sessions/all")).status_code == 204
    assert (await second_client.post(f"{REST}/auth/refresh")).status_code == 401

    sessions = (await client.get(f"{REST}/auth/sessions")).json()
    assert [row["deviceId"] for row in sessions] == [first_device]
    assert (await client.get(f"{REST}/auth/me")).status_code == 200


async def test_revoking_a_session_invalidates_its_access_token_at_once(
    client: httpx.AsyncClient,
    second_client: httpx.AsyncClient,
    db: AsyncSession,
) -> None:
    """The point of the feature: not "in up to 30 minutes", but now.

    The revoked browser still holds an access token whose signature and expiry are both still
    perfectly valid. It must stop working anyway, because the session it was issued for is
    gone -- which is why the token carries a `did` claim and `get_current_user` joins on it.
    """
    await make_user(db)
    await login(client)
    await login(second_client)
    second_device = second_client.cookies[DEVICE_ID_COOKIE]

    assert (await second_client.get(f"{REST}/auth/me")).status_code == 200
    await client.request("DELETE", f"{REST}/auth/sessions/{second_device}")

    # Same unexpired cookie, sent again -- now refused.
    assert (await second_client.get(f"{REST}/auth/me")).status_code == 401


async def test_logout_invalidates_the_access_token_server_side(
    client: httpx.AsyncClient,
    db: AsyncSession,
) -> None:
    """Logout clears cookies, but a copied token must die too -- not just the browser's copy."""
    await make_user(db)
    await login(client)
    stolen_access = client.cookies[ACCESS_TOKEN_COOKIE]
    device = client.cookies[DEVICE_ID_COOKIE]

    await client.post(f"{REST}/auth/logout")

    client.cookies.set(ACCESS_TOKEN_COOKIE, stolen_access)
    client.cookies.set(DEVICE_ID_COOKIE, device)
    assert (await client.get(f"{REST}/auth/me")).status_code == 401


async def test_the_current_session_cannot_be_revoked_here(client: httpx.AsyncClient, db: AsyncSession) -> None:
    """Ending your own session is `logout`, which also clears this browser's cookies."""
    await make_user(db)
    await login(client)
    device_id = client.cookies[DEVICE_ID_COOKIE]

    response = await client.request("DELETE", f"{REST}/auth/sessions/{device_id}")
    assert response.status_code == 400
    assert (await client.get(f"{REST}/auth/me")).status_code == 200


async def test_logout_removes_the_session_from_the_list(client: httpx.AsyncClient, db: AsyncSession) -> None:
    await make_user(db)
    await login(client)
    await client.post(f"{REST}/auth/logout")

    # Signing back in must not resurrect the old row as a second live session.
    await login(client)
    sessions = (await client.get(f"{REST}/auth/sessions")).json()
    assert len(sessions) == 1


async def test_sessions_require_authentication(client: httpx.AsyncClient) -> None:
    assert (await client.get(f"{REST}/auth/sessions")).status_code == 401
    assert (await client.request("DELETE", f"{REST}/auth/sessions/all")).status_code == 401


async def test_refresh_cookie_alone_is_not_a_session(client: httpx.AsyncClient, db: AsyncSession) -> None:
    """Sanity check on the cookie split: the refresh token is not an access token."""
    await make_user(db)
    await login(client)
    refresh = client.cookies[REFRESH_TOKEN_COOKIE]
    device = client.cookies[DEVICE_ID_COOKIE]

    client.cookies.clear()
    client.cookies.set(REFRESH_TOKEN_COOKIE, refresh)
    client.cookies.set(DEVICE_ID_COOKIE, device)

    assert (await client.get(f"{REST}/auth/me")).status_code == 401
    assert (await client.post(f"{REST}/auth/refresh")).status_code == 200
    assert (await client.get(f"{REST}/auth/me")).status_code == 200
