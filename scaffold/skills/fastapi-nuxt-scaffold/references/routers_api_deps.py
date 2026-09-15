"""Auth dependency for the /api (integrations) surface.

Minimal placeholder: checks a header against a static set of keys from
settings. No scoping, rotation, or revocation -- add a DB-backed ApiKey model
when you actually need per-integration keys; this just proves the
per-surface-auth-dependency shape.
"""

from __future__ import annotations

from fastapi import Header, HTTPException, status

from environment import settings


async def verify_api_key(x_api_key: str = Header(...)) -> None:
    if x_api_key not in settings.api_keys:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Invalid API key")
