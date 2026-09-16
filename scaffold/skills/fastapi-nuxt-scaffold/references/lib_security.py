"""Destination: api/lib/security.py

Cryptographic primitives for the auth flow. Everything here is pure: no database, no request,
no FastAPI. The policy that uses them lives in `services/auth.py`.

Three distinct uses of `settings.TOKEN_KEY`, deliberately kept apart:

- **JWT signing** (HS512) -- the access token and the two-factor waiting ticket.
- **HMAC fingerprints** -- refresh and invite tokens are stored as a keyed digest, so a
  database dump yields no usable token. A keyed HMAC, not a bare SHA-256: without the key an
  attacker cannot even build a rainbow table of candidate tokens.
- **Fernet encryption** -- TOTP secrets must be *recoverable* to verify a code, so they are
  encrypted (reversible), not hashed. Passwords are the opposite case and use Argon2.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
from datetime import timedelta
from typing import Any

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import Argon2Error
from cryptography.fernet import Fernet, InvalidToken

from environment import settings
from lib.utils import utcnow

_password_hasher = PasswordHasher()

JWT_ALGORITHM = "HS512"
JWT_ISSUER = "__APP_NAME__"

# Two audiences over the same signing key. The waiting ticket issued after a correct password
# can never be used as a session (`get_current_user` demands JWT_AUDIENCE), and a session token
# can never be replayed at the two-factor endpoints. Both directions are covered by tests.
JWT_AUDIENCE = "session"
JWT_2FA_AUDIENCE = "2fa-pending"

ACCESS_TOKEN_COOKIE = "access_token"
REFRESH_TOKEN_COOKIE = "refresh_token"
DEVICE_ID_COOKIE = "device_id"
TWOFA_PENDING_COOKIE = "twofa_pending"


def hash_password(password: str) -> str:
    return _password_hasher.hash(password)


def verify_password(password_hash: str | None, password: str) -> bool:
    """Constant-ish-time password check that never raises on a bad hash or a mismatch."""
    if not password_hash:
        return False
    try:
        return _password_hasher.verify(password_hash, password)
    except Argon2Error:
        return False


def generate_token() -> str:
    """A raw, URL-safe bearer token (refresh token, invite token). Shown once, stored hashed."""
    return secrets.token_urlsafe(48)


def fingerprint(raw_token: str) -> str:
    """Keyed HMAC-SHA256 digest of a raw token -- what actually goes in the database."""
    return hmac.new(settings.TOKEN_KEY.encode("utf-8"), raw_token.encode("utf-8"), hashlib.sha256).hexdigest()


def generate_numeric_code(digits: int = 6) -> str:
    """A uniformly random numeric code, zero-padded (`secrets`, never `random`)."""
    return f"{secrets.randbelow(10**digits):0{digits}d}"


def _fernet() -> Fernet:
    """The Fernet key, derived deterministically from `settings.TOKEN_KEY`.

    Fernet wants 32 base64url-encoded bytes and `TOKEN_KEY` is free-form text, hence SHA-256.
    Rotating `TOKEN_KEY` makes stored TOTP secrets undecryptable and users must re-enrol --
    consistent with that rotation already invalidating every JWT.
    """
    return Fernet(base64.urlsafe_b64encode(hashlib.sha256(settings.TOKEN_KEY.encode("utf-8")).digest()))


def encrypt_secret(raw: str) -> str:
    return _fernet().encrypt(raw.encode("utf-8")).decode("ascii")


def decrypt_secret(encrypted: str) -> str | None:
    """Decrypt a stored TOTP secret, or None if it is unreadable (e.g. `TOKEN_KEY` was rotated)."""
    try:
        return _fernet().decrypt(encrypted.encode("ascii")).decode("utf-8")
    except (InvalidToken, ValueError):
        return None


def create_access_token(user_uuid: str, device_id: str, expires_minutes: int | None = None) -> str:
    """A session token, bound to the device whose session issued it.

    The `did` claim is what lets `get_current_user` check the session is still alive. Without
    it, revoking a session would only take away the ability to REFRESH -- the access token
    already in that browser would keep working until it expired, so "sign this other device
    out" would quietly mean "in up to ACCESS_TOKEN_EXP_MINUTES from now".
    """
    minutes = settings.ACCESS_TOKEN_EXP_MINUTES if expires_minutes is None else expires_minutes
    return _encode(user_uuid, JWT_AUDIENCE, timedelta(minutes=minutes), device_id=device_id)


def create_twofa_pending_token(user_uuid: str, expires_minutes: int) -> str:
    """The waiting ticket between a correct password and a correct code.

    Same machinery as the access token but a different audience, so it is not a session. No
    session cookie is issued until the code is confirmed.
    """
    return _encode(user_uuid, JWT_2FA_AUDIENCE, timedelta(minutes=expires_minutes))


def _encode(subject: str, audience: str, lifetime: timedelta, device_id: str | None = None) -> str:
    claims: dict[str, Any] = {
        "sub": subject,
        "iss": JWT_ISSUER,
        "aud": audience,
        # Aware UTC throughout (root CLAUDE.md). A naive `datetime.now()` here would hand out
        # tokens living an extra timezone-offset's worth of time.
        "iat": utcnow(),
        "exp": utcnow() + lifetime,
    }
    if device_id is not None:
        claims["did"] = device_id
    return jwt.encode(claims, settings.TOKEN_KEY, algorithm=JWT_ALGORITHM)


def decode_token(token: str, audience: str) -> dict[str, Any] | None:
    """Return a valid token's claims, or None. Never raises."""
    try:
        claims: dict[str, Any] = jwt.decode(
            token,
            settings.TOKEN_KEY,
            algorithms=[JWT_ALGORITHM],
            issuer=JWT_ISSUER,
            audience=audience,
        )
    except jwt.PyJWTError:
        return None
    return claims if isinstance(claims.get("sub"), str) else None
