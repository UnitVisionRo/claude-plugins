"""Destination: api/schemas/rest.py

Wire models for the browser-facing surface.

Field names are camelCase, matching the root CLAUDE.md's JSON-key rule and the ORM columns
they read from -- so `from_attributes=True` works without a single alias, and the generated
TypeScript needs no renaming layer either.

**Express every constraint you can declaratively** -- `Annotated[str, StringConstraints(...)]`,
`Field(ge=..., max_length=...)`, `EmailStr` -- rather than in a `field_validator`. Declarative
constraints become JSON Schema, and JSON Schema becomes real client-side validation:

    username: Annotated[str, StringConstraints(...)]  ->  v.pipe(v.string(), v.regex(/.../))
    email: EmailStr                                   ->  v.pipe(v.string(), v.email())
    @field_validator(...)                             ->  v.string()          <-- invisible

A `field_validator` runs on the server and nowhere else, so the browser learns nothing about
the rule and the frontend has to re-state it by hand -- which is exactly how the two drift
apart. Keep validators for the two jobs constraints cannot do: normalising input
(`mode="before"`) and comparing fields to each other (`model_validator`).
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, StringConstraints, field_validator, model_validator

from lib.enums import Role, TwoFactorMethod

# At least 8 characters, and at least one of each: lowercase, uppercase, digit, symbol.
# Lookaheads are the one regex feature worth checking here: they are valid in both Python's
# `re` and JavaScript's RegExp, so this pattern survives the trip into the generated client.
PASSWORD_PATTERN = r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[^\w\s]).{8,}$"
PASSWORD_MESSAGE = (
    "Password must be at least 8 characters and include a lowercase letter, "
    "an uppercase letter, a digit and a symbol"
)

# The constraint is what reaches the browser; the message is what a human reads. `Field`'s
# `description` carries the wording into the OpenAPI schema too, so the generated client and
# the API docs both show it.
Password = Annotated[
    str,
    StringConstraints(pattern=PASSWORD_PATTERN),
    Field(description=PASSWORD_MESSAGE),
]
Username = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=3, max_length=125, pattern=r"^[a-zA-Z0-9._-]+$"),
    Field(description="3-125 characters: letters, digits, dot, dash or underscore"),
]
SixDigitCode = Annotated[str, StringConstraints(pattern=r"^\d{6}$")]


class RestModel(BaseModel):
    """Base for every wire model on this surface.

    `regex_engine="python-re"` is required, not cosmetic. Pydantic v2 validates patterns with
    Rust's `regex` crate by default, which has no look-around at all -- so a `StringConstraints`
    pattern containing `(?=...)` fails at import time with "look-around ... is not supported".
    The password rule needs look-ahead (it is how one regex says "contains a digit AND an
    uppercase letter AND ..."), and JavaScript's RegExp supports it, so the pattern is fine
    everywhere except that one engine. Switching to Python's own `re` keeps the constraint
    declarative -- and therefore visible to the generated client -- instead of forcing it back
    into a `field_validator` the browser cannot see.
    """

    model_config = ConfigDict(regex_engine="python-re")


class ORMModel(RestModel):
    model_config = ConfigDict(from_attributes=True, regex_engine="python-re")


class LoginRequest(RestModel):
    """Deliberately unconstrained.

    Applying `Username`/`Password` here would reject a malformed guess with a 422 instead of
    the same "incorrect username or password" everything else gets -- handing an attacker a
    free oracle for the account-name and password rules.
    """

    username: str
    password: str


class LoginResult(RestModel):
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


class SignupRequest(RestModel):
    inviteToken: str
    username: Username
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)]
    password: Password
    confirmPassword: str

    @model_validator(mode="after")
    def passwords_match(self) -> SignupRequest:
        # Cross-field, so it cannot be a constraint and never reaches the client. The frontend
        # re-states this one by hand (`matches()` in utils/validation.ts).
        if self.password != self.confirmPassword:
            raise ValueError("Passwords do not match")
        return self


class InvitedUserResult(RestModel):
    """What the public signup page is allowed to learn from an invite token: enough to greet
    the invitee and prefill the form, and nothing else about the account."""

    email: EmailStr
    name: str | None = None


class InviteRequest(RestModel):
    email: EmailStr
    role: Role = Role.USER
    name: str | None = None


class InviteResult(RestModel):
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


class RecoveryRequest(RestModel):
    """Username or email -- people remember one or the other, rarely reliably both."""

    usernameOrEmail: str


class PasswordResetRequest(RestModel):
    recoveryToken: str
    newPassword: Password
    confirmPassword: str

    @model_validator(mode="after")
    def passwords_match(self) -> PasswordResetRequest:
        if self.newPassword != self.confirmPassword:
            raise ValueError("Passwords do not match")
        return self


class RecoveryTarget(RestModel):
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


class TwoFactorStatus(RestModel):
    """Enrolment state. `method` NULL means two-factor auth is off."""

    method: TwoFactorMethod | None = None
    pendingMethod: TwoFactorMethod | None = None


class TwoFactorSetupRequest(RestModel):
    method: TwoFactorMethod
    currentPassword: str


class TwoFactorSetupResult(RestModel):
    """TOTP enrolment data. Both fields are NULL for the EMAIL method.

    `secret` is returned exactly once, so the user can type it in if they cannot scan the QR.
    """

    otpauthUri: str | None = None
    secret: str | None = None


class TwoFactorCode(RestModel):
    code: SixDigitCode

    @field_validator("code", mode="before")
    @classmethod
    def normalize_code(cls, value: str) -> str:
        """Strip the spaces authenticator apps display ("123 456") BEFORE the pattern runs.

        `mode="before"` is load-bearing: at the default `mode="after"` the `^\\d{6}$`
        constraint would see the raw value and reject a code the user copied verbatim from
        their authenticator.
        """
        return value.strip().replace(" ", "") if isinstance(value, str) else value


class PasswordConfirmation(RestModel):
    currentPassword: str
