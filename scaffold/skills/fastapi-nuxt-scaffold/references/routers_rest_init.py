"""Destination: api/routers/rest/__init__.py

The browser-facing surface. Authentication is per-router, not surface-wide: `/auth/login`,
`/auth/signup` and the invite lookup must stay reachable without a session, so the dependency
lives on the routes and routers that need it (`routers/rest/deps.py`), not on this router.
"""

from fastapi import APIRouter

from routers.rest.auth import router as auth_router
from routers.rest.users import router as users_router

router = APIRouter()
router.include_router(auth_router)
router.include_router(users_router)
