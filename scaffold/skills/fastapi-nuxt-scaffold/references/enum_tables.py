"""StrEnum -> lookup-table registry.

Add a concrete `BaseEnum` subclass per enum (see `models/base.py` docstring),
plus its `StrEnum` in `lib/enums.py`, then extend `ENUM_TABLES` below. A
migration seeds the table with the SAME literal values (a migration is an
immutable point-in-time fact -- never import the live enum into one). Tests
seed from the live `StrEnum` via `seed_enum_tables()` after `create_all`.
"""

from __future__ import annotations

from enum import Enum

from sqlalchemy.ext.asyncio import AsyncSession

from models.base import BaseEnum

ENUM_TABLES: dict[type[Enum], type[BaseEnum]] = {}


async def seed_enum_tables(session: AsyncSession) -> None:
    for enum_cls, table_cls in ENUM_TABLES.items():
        for member in enum_cls:
            await session.merge(table_cls(name=member.value))
    await session.commit()
