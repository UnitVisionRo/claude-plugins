"""Destination: api/models/user.py

The three tables the auth flow needs. Split deliberately:

- `users`            -- identity. Read on every authenticated request, so it holds no secrets
                        beyond the password hash.
- `user_sessions`    -- one row per (user, device) refresh token. Lets a user see and revoke
                        their own sessions, and makes logout server-side, not just a cleared cookie.
- `user_two_factor`  -- at most one row per user, created the moment enrolment STARTS. Two-factor
                        auth is *active* only when `method` is non-NULL. Disabling deletes the row;
                        there is no "temporarily off" state. Kept out of `users` so the TOTP secret
                        and the mailed-code hash are not dragged into every session lookup.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Enum, ForeignKey, String, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from lib.enums import Role, TwoFactorMethod
from models.base import CreatedAtMixin, TableBase, UuidMixin


def _enum_column(enum_cls: type[Role] | type[TwoFactorMethod]) -> Enum:
    """The column type for a StrEnum stored as VARCHAR + FK to its lookup table.

    `native_enum=False` / `create_constraint=False`: the lookup table's foreign key is what
    enforces the allowed values, so neither a Postgres ENUM type nor a CHECK is wanted here
    (see `models/base.py` for why the lookup table wins).
    """
    return Enum(enum_cls, native_enum=False, create_constraint=False, length=20)


class User(UuidMixin, CreatedAtMixin, TableBase):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    # Both NULL until the invite is accepted: an invited user exists as a row (so the invite can
    # be tracked and re-sent) but cannot log in, because login requires a username AND a hash.
    username: Mapped[str | None] = mapped_column(String(125), unique=True, index=True)
    passwordHash: Mapped[str | None] = mapped_column(String(255))
    name: Mapped[str | None] = mapped_column(String(255))

    role: Mapped[Role] = mapped_column(_enum_column(Role), ForeignKey("role.name"))

    isBlocked: Mapped[bool] = mapped_column(server_default=text("false"), default=False)

    # HMAC fingerprint of the invite token, never the token itself -- a database dump must not
    # hand anyone a working invite link. Non-NULL means "invited, not yet accepted", which is
    # exactly the condition login refuses.
    inviteTokenHash: Mapped[str | None] = mapped_column(String(64), unique=True, index=True)
    invitedAt: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    invitedById: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id"))

    # Same treatment as the invite token: fingerprint only, single use. `recoveryRequestedAt`
    # is stored rather than leaning on a generic `modifiedAt`, so that unrelated edits to the
    # row cannot quietly extend the lifetime of a password-reset link.
    recoveryTokenHash: Mapped[str | None] = mapped_column(String(64), unique=True, index=True)
    recoveryRequestedAt: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    twoFactor: Mapped[UserTwoFactor | None] = relationship(
        back_populates="user", cascade="all, delete-orphan", uselist=False
    )

    @property
    def isPending(self) -> bool:
        return self.inviteTokenHash is not None


class UserSession(CreatedAtMixin, TableBase):
    """A live refresh token for one browser/device."""

    __tablename__ = "user_sessions"

    userId: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), index=True)
    deviceId: Mapped[str] = mapped_column(String(36), index=True)

    # NULL once the session ends -- the raw token is never stored, only its HMAC fingerprint.
    tokenHash: Mapped[str | None] = mapped_column(String(64), index=True)

    ip: Mapped[str | None] = mapped_column(String(45))
    userAgent: Mapped[str | None] = mapped_column(String(255))

    lastUsedAt: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    expiresAt: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revokedAt: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class UserTwoFactor(TableBase):
    __tablename__ = "user_two_factor"

    userId: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), unique=True)

    method: Mapped[TwoFactorMethod | None] = mapped_column(
        _enum_column(TwoFactorMethod),
        ForeignKey("two_factor_method.name"),
    )
    totpSecret: Mapped[str | None] = mapped_column(String(255), comment="Fernet-encrypted, never plaintext")

    # The method being enrolled. The ACTIVE method above is untouched until a code confirms the
    # pending one, so abandoning a change leaves the account protected exactly as it was.
    pendingMethod: Mapped[TwoFactorMethod | None] = mapped_column(
        _enum_column(TwoFactorMethod),
        ForeignKey("two_factor_method.name"),
    )
    pendingTotpSecret: Mapped[str | None] = mapped_column(String(255), comment="Fernet-encrypted, never plaintext")

    emailCodeHash: Mapped[str | None] = mapped_column(String(64))
    emailCodeExpiresAt: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    emailCodeSentAt: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), comment="Rate-limits resends")

    failedAttempts: Mapped[int] = mapped_column(server_default=text("0"), default=0)
    lockedUntil: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # The last TOTP time-step accepted, so the same 30-second code cannot be replayed.
    lastTotpTimestep: Mapped[int | None] = mapped_column(BigInteger)

    user: Mapped[User] = relationship(back_populates="twoFactor")
