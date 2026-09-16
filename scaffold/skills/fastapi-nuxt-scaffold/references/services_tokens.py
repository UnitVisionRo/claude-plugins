"""Destination: api/services/tokens.py

Issuing the single-use, emailed tokens (invitations, password resets).

Both live in a UNIQUE column on `users` and are stored as HMAC fingerprints, never in the
clear -- a database dump must not hand anyone a working link. The retry loop is about that
UNIQUE constraint rather than about collisions being likely: with 48 random bytes a clash is
not going to happen, but losing that race would surface as an IntegrityError at commit time,
which is not something a caller could do anything useful with.
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import InstrumentedAttribute

from lib.security import fingerprint, generate_token
from models.user import User


async def issue_unique_token(db: AsyncSession, column: InstrumentedAttribute[str | None]) -> tuple[str, str]:
    """Return `(raw_token, fingerprint)` for a token no other row holds in `column`.

    The raw token is returned to the caller once, to be put in a link and then forgotten; only
    the fingerprint is ever stored.
    """
    for _ in range(5):
        candidate = generate_token()
        candidate_fingerprint = fingerprint(candidate)
        taken = await db.scalar(sa.select(sa.func.count()).select_from(User).where(column == candidate_fingerprint))
        if not taken:
            return candidate, candidate_fingerprint

    raise RuntimeError(f"Could not generate a unique token for {column.key}")
