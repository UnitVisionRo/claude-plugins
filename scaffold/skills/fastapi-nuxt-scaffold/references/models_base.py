"""Declarative bases.

`Base` / `TableBase` back real tables: every table gets an auto-incrementing
BIGINT primary key named `id`, always the first column (never expose it
outside the process -- give externally-visible tables a separate unique
`uuid` (v4) column instead).

`BaseEnum` is a SEPARATE declarative base (sharing `Base.metadata`) for enum
lookup tables: no surrogate `id` -- the table is keyed by its own `name`
column, which holds the canonical enum value and is what other tables' FKs
point at. This makes enums discoverable (`SELECT * FROM some_enum;`), easy to
extend (add a value = insert a row, no `ALTER TYPE`), and DB-enforced via the
FK -- while staying human-readable (no int-surrogate join). Prefer this over
a native Postgres enum (rigid: `ALTER TYPE` can't remove/reorder values) or a
bare CHECK constraint (not discoverable at the column).

Usage once you have a real enum:

    # lib/enums.py
    class Status(StrEnum):
        ACTIVE = "ACTIVE"
        ARCHIVED = "ARCHIVED"

    # models/enum_tables.py
    class StatusTable(BaseEnum):
        __tablename__ = "status"

    ENUM_TABLES: dict[type, type] = {Status: StatusTable}

    # consuming column, in some other model
    status: Mapped[Status] = mapped_column(
        Enum(Status, native_enum=False, create_constraint=False, length=20),
        ForeignKey("status.name"),
    )
"""

from uuid import UUID, uuid4
from datetime import datetime

from sqlalchemy import BigInteger, CheckConstraint, DateTime, Uuid
from sqlalchemy.ext.asyncio import AsyncAttrs
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from lib.utils import utcnow

class Base(AsyncAttrs, DeclarativeBase):
    pass


class TableBase(Base):
    __abstract__ = True

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True, sort_order=-100)


class BaseEnum(AsyncAttrs, DeclarativeBase):
    metadata = Base.metadata

    __abstract__ = True

    name: Mapped[str] = mapped_column(primary_key=True)

    __table_args__ = (CheckConstraint("name = upper(name) AND name !~ '[^A-Z0-9_]'", name="ck_screaming_snake_case"),)


class UuidMixin:
    """uuid4 public identifier for externally visible tables (never expose `id`)."""

    uuid: Mapped[UUID] = mapped_column(Uuid, unique=True, nullable=False, default=uuid4, sort_order=-90)


class CreatedAtMixin:
    createdAt: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow, sort_order=90)