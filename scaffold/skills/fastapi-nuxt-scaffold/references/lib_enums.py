"""Shared `StrEnum`s. Every enum in the app is defined here, never inline in a model or schema.

Each one is backed by a lookup table registered in `models/enum_tables.py` (see
`models/base.py` for why). Adding a member means adding a row, which means a migration --
`migrations/versions/*_seed_enum_values.py` shows the shape.
"""

from enum import StrEnum


class Role(StrEnum):
    """What a user is allowed to do.

    Deliberately flat: one role per user, checked with `require_admin`. A real permission
    model (many roles, scopes, per-resource grants) is domain modelling that belongs to the
    app being built, not to the scaffold -- but the enum table means adding a role later is
    an INSERT plus a migration, not an `ALTER TYPE`.
    """

    ADMIN = "ADMIN"
    USER = "USER"


class TwoFactorMethod(StrEnum):
    """How a user receives the second-factor code.

    EMAIL -- a six-digit code mailed on every login.
    TOTP  -- an authenticator app (Microsoft/Google Authenticator, 1Password, ...).
    """

    EMAIL = "EMAIL"
    TOTP = "TOTP"
