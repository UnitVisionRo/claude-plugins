"""Application entry point.

A root FastAPI app exposes liveness/readiness and mounts two API surfaces as
separate sub-apps, grouped by consumer. Each sub-app carries its own CORS
posture, auth dependency, and OpenAPI schema:

    /rest  -> browser-facing console (admin/GUI). CORS locked to the frontend
              origin(s), credentials allowed -- the session is an httpOnly
              cookie (see routers/rest/deps.py).
    /api   -> server-to-server integrations. CORS open (a browser is never
              the caller); guarded by an API-key header instead.

Run from this directory: ``uv run uvicorn main:app --reload``.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.routing import APIRoute
from sqlalchemy import text

from environment import settings
from lib.database import async_session_factory, engine
from routers.api import router as integrations_router
from routers.rest import router as rest_router

_VERSION = "0.0.0"


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    # The engine is a module-level singleton; dispose its pool on shutdown.
    # (Mounted sub-apps don't reliably receive lifespan events, so manage it here.)
    yield
    await engine.dispose()


def _operation_id(route: APIRoute) -> str:
    """Use the endpoint function's own name as the OpenAPI operationId.

    FastAPI's default mangles the path and method into the id (`login_auth_login_post`), and
    every client generator turns that straight into a method name -- `loginAuthLoginPost()`.
    The function name alone generates `login()`.

    The cost: operation ids must be unique WITHIN a surface, so two routers on the same
    sub-app cannot both define e.g. `list_items`. FastAPI raises at startup if they do, so
    this can never fail silently.
    """
    return route.name


def _make_surface(title: str, *, allow_origins: list[str], allow_all: bool = False) -> FastAPI:
    """Build a surface sub-app with its CORS posture applied."""
    sub = FastAPI(title=title, version=_VERSION, generate_unique_id_function=_operation_id)
    if allow_all:
        # Server-to-server: CORS protects nothing here (the API key is the guard).
        # A wildcard origin cannot carry credentials, which is fine -- auth is a header, not a cookie.
        sub.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_methods=["*"],
            allow_headers=["*"],
            allow_credentials=False,
        )
    else:
        sub.add_middleware(
            CORSMiddleware,
            allow_origins=allow_origins,
            allow_methods=["*"],
            allow_headers=["*"],
            allow_credentials=True,
        )
    return sub


def create_app() -> FastAPI:
    app = FastAPI(title="__APP_NAME__", version=_VERSION, lifespan=lifespan)

    rest_app = _make_surface("__APP_NAME__ -- Console (/rest)", allow_origins=settings.rest_cors_origins)
    rest_app.include_router(rest_router)
    app.mount("/rest", rest_app)

    integrations_app = _make_surface("__APP_NAME__ -- Integrations (/api)", allow_origins=[], allow_all=True)
    integrations_app.include_router(integrations_router)
    app.mount("/api", integrations_app)

    # A mounted sub-app is a separate FastAPI instance with its own `dependency_overrides`;
    # overrides set on the parent do NOT reach it. Tests need a handle on the sub-app to swap
    # the database session, and nothing else exposes one -- hence these.
    app.state.rest_app = rest_app
    app.state.integrations_app = integrations_app

    @app.get("/health", tags=["health"])
    async def health() -> dict[str, str]:
        """Liveness: the app process is up. Does not touch the database."""
        return {"status": "ok"}

    @app.get("/health/db", tags=["health"])
    async def health_db() -> dict[str, str]:
        """Readiness: the database is reachable."""
        async with async_session_factory() as session:
            await session.execute(text("SELECT 1"))
        return {"database": "ok"}

    return app


app = create_app()
