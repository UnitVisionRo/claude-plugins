"""Destination: api/scripts/seed.py

Create the first administrator. Run from `api/`:

    uv run python -m scripts.seed

Idempotent: re-running reports the existing admin instead of creating a second one, and never
resets a password that is already in use. Pass `--reset-password` to issue a new one.

The password is random and printed ONCE, to stdout. It is never written to a file, never
stored in plaintext, and cannot be recovered afterwards -- copy it now or re-run with
`--reset-password`. A fixed default password ("admin/admin") is how a scaffold becomes the
hole in a production deployment.

Enum lookup rows are NOT seeded here -- they are inserted by the `seed_enum_values` migration,
because their contents are part of the schema at a point in time (see `models/enum_tables.py`).
"""

from __future__ import annotations

import argparse
import asyncio
import secrets
import string
import sys

import sqlalchemy as sa
from pydantic import EmailStr, TypeAdapter, ValidationError

from lib.database import make_session
from lib.enums import Role
from lib.security import hash_password
from models.user import User

ADMIN_USERNAME = "admin"
# `.test`, `.localhost` and bare hostnames are refused by `EmailStr`, which every response
# model containing an email runs through. An admin seeded with one of those is created fine
# and then 500s the first time `/auth/me` serializes it -- so the address is validated here,
# before the row exists, and the default is an RFC 2606 example domain.
DEFAULT_ADMIN_EMAIL = "admin@example.com"

_email_validator: TypeAdapter[EmailStr] = TypeAdapter(EmailStr)


def generate_password(length: int = 20) -> str:
    """A random password that satisfies `schemas.rest`'s own complexity rule by construction."""
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*-_=+"
    while True:
        password = "".join(secrets.choice(alphabet) for _ in range(length))
        if (
            any(character.islower() for character in password)
            and any(character.isupper() for character in password)
            and any(character.isdigit() for character in password)
            and any(character in "!@#$%^&*-_=+" for character in password)
        ):
            return password


async def seed_admin(email: str, reset_password: bool) -> None:
    async with make_session() as db:
        admin = await db.scalar(sa.select(User).where(User.username == ADMIN_USERNAME))

        if admin is not None and admin.email != email:
            # Keep the address in sync when one is given explicitly. Without this there is no
            # way to correct a typo in the admin's email short of editing the database by hand,
            # and that address is what password recovery and 2FA codes are sent to.
            print(f"Updating administrator email: {admin.email} -> {email}")
            admin.email = email
            await db.commit()

        if admin is not None and not reset_password:
            print(f"Administrator {ADMIN_USERNAME!r} already exists (email: {admin.email}). Password unchanged.")
            print("Re-run with --reset-password to issue a new one.")
            return

        password = generate_password()

        if admin is None:
            admin = User(username=ADMIN_USERNAME, email=email, name="Administrator", role=Role.ADMIN)
            db.add(admin)
            action = "created"
        else:
            action = "password reset for"

        admin.passwordHash = hash_password(password)
        # An admin created here has no invitation to accept -- it is already a usable account.
        admin.inviteTokenHash = None
        admin.isBlocked = False
        await db.commit()

    print(f"Administrator {action}:")
    print(f"  username: {ADMIN_USERNAME}")
    print(f"  email:    {admin.email}")
    print(f"  password: {password}")
    print("\nThis password is shown once and is not stored anywhere in plaintext. Save it now.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed the first administrator account.")
    parser.add_argument("--email", default=DEFAULT_ADMIN_EMAIL, help="Email for the admin account")
    parser.add_argument("--reset-password", action="store_true", help="Issue a new password for an existing admin")
    args = parser.parse_args()

    try:
        _email_validator.validate_python(args.email)
    except ValidationError:
        print(f"{args.email!r} is not an address this app can serialize. Use a real domain.", file=sys.stderr)
        raise SystemExit(2) from None

    try:
        asyncio.run(seed_admin(args.email, args.reset_password))
    except Exception as error:  # noqa: BLE001 -- a CLI should report, not traceback
        print(f"Seeding failed: {error}", file=sys.stderr)
        raise SystemExit(1) from error


if __name__ == "__main__":
    main()
