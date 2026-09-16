"""Destination: api/schemas/rest.py

Wire models for the browser-facing surface.

Field names are camelCase, matching the root CLAUDE.md's JSON-key rule and the ORM columns
they read from -- so `from_attributes=True` works without a single alias, and the generated
TypeScript needs no renaming layer either.
"""

from __future__ import annotations

import re
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, field_validator, model_validator

from lib.enums import Role, TwoFactorMethod

# At least 8 characters, and at least one of each: lowercase, uppercase, digit, symbol.
_PASSWORD_PATTERN = re.compile(r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[^\w\s]).{8,}$")
_USERNAME_PATTERN = re.compile(r"^[a-zA-Z0-9._-]{3,125}$")


def _validate_password(value: str) -> str:
    if not _PASSWORD_PATTERN.match(value):
        raise ValueError(
            "Password must be at least 8 characters and include a lowercase letter, "
            "an uppercase letter, a digit and a symbol"
        )
    return value


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResult(BaseModel):
    """The result of `POST /rest/auth/login`.

    `twofaRequired=False` means the session cookies are already set. `twofaRequired=True`
    means NO session was issued -- a code must still be confirmed at `/auth/2fa/verify`.
    """

    twofaRequired: bool
    twofaMethod: TwoFactorMethod | None = None


class CurrentUserResult(ORMModel):
    uuid: UUID
    email: EmailStr
    username: str | None = None
    name: str | None = None
    role: Role
    createdAt: datetime


class SignupRequest(BaseModel):
    inviteToken: str
    username: str
    name: str
    password: str
    confirmPassword: str

    @field_validator("username")
    @classmethod
    def validate_username(cls, value: str) -> str:
        value = value.strip()
        if not _USERNAME_PATTERN.match(value):
            raise ValueError("Username must be 3-125 characters, letters, digits, dot, dash or underscore only")
        return value

    @field_validator("password")
    @classmethod
    def validate_password(cls, value: str) -> str:
        return _validate_password(value)

    @model_validator(mode="after")
    def passwords_match(self) -> SignupRequest:
        if self.password != self.confirmPassword:
            raise ValueError("Passwords do not match")
        return self


class InvitedUserResult(BaseModel):
    """What the public signup page is allowed to learn from an invite token: enough to greet
    the invitee and prefill the form, and nothing else about the account."""

    email: EmailStr
    name: str | None = None


class InviteRequest(BaseModel):
    email: EmailStr
    role: Role = Role.USER
    name: str | None = None


class InviteResult(BaseModel):
    """The invite link is returned as well as mailed.

    Deliberate: email delivery is best-effort (`lib/mail.py`), so an admin needs a way to hand
    the link over directly -- and it is the only way the flow works before SMTP is configured.
    """

    inviteUrl: str


class UserListItem(ORMModel):
    uuid: UUID
    email: EmailStr
    username: str | None = None
    name: str | None = None
    role: Role
    isBlocked: bool
    isPending: bool
    createdAt: datetime


class RecoveryRequest(BaseModel):
    """Username or email -- people remember one or the other, rarely reliably both."""

    usernameOrEmail: str


class PasswordResetRequest(BaseModel):
    recoveryToken: str
    newPassword: str
    confirmPassword: str

    @field_validator("newPassword")
    @classmethod
    def validate_password(cls, value: str) -> str:
        return _validate_password(value)

    @model_validator(mode="after")
    def passwords_match(self) -> PasswordResetRequest:
        if self.newPassword != self.confirmPassword:
            raise ValueError("Passwords do not match")
        return self


class RecoveryTarget(BaseModel):
    """Which account a reset link belongs to, so the page can say so before asking.

    Safe to return for a valid token: holding one already proves the holder received the mail
    sent to that address, so naming the account tells them nothing they did not have. Showing
    it is the point -- somebody with two accounts needs to know which one they are changing.
    """

    username: str | None = None
    email: EmailStr


class ActiveSession(ORMModel):
    """One signed-in browser. `deviceId` is an opaque per-browser id, not a device fingerprint."""

    deviceId: str
    userAgent: str | None = None
    ip: str | None = None
    createdAt: datetime
    lastUsedAt: datetime
    isCurrent: bool = False


class TwoFactorStatus(BaseModel):
    """Enrolment state. `method` NULL means two-factor auth is off."""

    method: TwoFactorMethod | None = None
    pendingMethod: TwoFactorMethod | None = None


class TwoFactorSetupRequest(BaseModel):
    method: TwoFactorMethod
    currentPassword: str


class TwoFactorSetupResult(BaseModel):
    """TOTP enrolment data. Both fields are NULL for the EMAIL method.

    `secret` is returned exactly once, so the user can type it in if they cannot scan the QR.
    """

    otpauthUri: str | None = None
    secret: str | None = None


class TwoFactorCode(BaseModel):
    code: str

    @field_validator("code")
    @classmethod
    def normalize_code(cls, value: str) -> str:
        # Authenticator apps display the code with a space in the middle ("123 456").
        value = value.strip().replace(" ", "")
        if not re.fullmatch(r"\d{6}", value):
            raise ValueError("The code must be exactly 6 digits")
        return value


class PasswordConfirmation(BaseModel):
    currentPassword: str
