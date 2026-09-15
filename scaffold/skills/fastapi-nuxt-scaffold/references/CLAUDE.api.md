# api/ -- backend

Scoped guidance for the backend. Application-wide contracts live in the root `../CLAUDE.md`.

## Stack
FastAPI (async) + SQLAlchemy 2.0 async (`asyncpg`) + Alembic + PostgreSQL + Pydantic v2
(`from_attributes=True` on response models).

## Project layout
Run everything from `api/` -- it is the import root (`from lib.database import ...`).

- `main.py` -- `create_app()` mounts the `/rest` and `/api` sub-apps, exposes `/health`
  (liveness) + `/health/db` (readiness).
- `environment.py` -- `settings` (pydantic-settings), single source of config.
- `routers/<surface>/` -- one package per surface (`rest`, `api`): `__init__.py` exports
  `router`, `deps.py` holds that surface's auth dependency.
- `lib/` -- general-purpose utilities & FastAPI dependencies: `database.py` (engine,
  `async_session_factory`, `get_session`), `enums.py` (shared `StrEnum`s).
- `models/` -- `base.py` defines `Base`/`TableBase` (BIGINT PK, `AsyncAttrs`) and `BaseEnum`
  (enum lookup tables); `enum_tables.py` registers `StrEnum -> table`. Import every model in
  `models/__init__.py` so Alembic autogenerate sees it.
- `schemas/` -- Pydantic wire models, one module per surface.
- `services/` -- reusable business logic; functions take the request `AsyncSession` as a
  parameter (never open their own).
- `migrations/` -- Alembic (async `env.py`; URL + metadata come from `lib.database` / `models`).

## Database PKs
Auto-incrementing BIGINT primary key (`id`, always the first column) on every real table.
Never expose the DB PK to the frontend or an integration -- a table that needs a public
identifier gets a separate indexed `uuid` (v4, to avoid timestamp leakage) column instead.

## Enums
Always `StrEnum` (not `IntEnum`), key = value (e.g. `ACTIVE = "ACTIVE"`). Defined once in
`lib/enums.py` -- never inline in a model or schema module. Stored as a lookup table + FK
(`models/base.py`'s `BaseEnum` + `models/enum_tables.py`), not a native Postgres enum or a
bare CHECK: discoverable (`SELECT * FROM some_enum;`), easy to extend (insert a row, no
`ALTER TYPE`), DB-enforced via the FK.

## Async SQLAlchemy -- the rules
- One `AsyncSession` per request, provided by a FastAPI dependency and passed explicitly into
  service functions. Don't open new sessions inside services.
- Never `lazy=None` (it aliases `noload` -- the relationship never loads). Default to
  `lazy="select"`; use `lazy="raise_on_sql"` where a load must be explicit.
- Eager-load (`selectinload()`/`joinedload()`) to the depth a response model traverses, then
  return the ORM instance and let FastAPI serialize it. Never rely on lazy loading during
  serialization -- Pydantic reads attributes synchronously; async lazy access raises
  `MissingGreenlet`.
- Topping up a relationship on an instance you already hold: `await instance.awaitable_attrs.<rel>`.
  Don't re-`select()` the same row with `selectinload()` to top it up -- if it's already in the
  identity map, the eager option is a no-op.
- Use `session.scalar(select(...))` / `session.scalars(select(...))`, not
  `execute(...).scalar_one_or_none()` / `.scalars()` -- except keep `scalar_one()` /
  `scalar_one_or_none()` where you deliberately want the "exactly one" / "fail on ambiguity"
  assertion.

## Running & verifying
```bash
uv sync
uv run uvicorn main:app --reload
uv run pytest
uv run ruff check . && uv run ruff format --check . && uv run mypy .
uv run alembic revision --autogenerate -m "<msg>"   # review before applying
uv run alembic upgrade head
```
