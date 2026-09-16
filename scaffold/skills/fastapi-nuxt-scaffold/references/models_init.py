"""Destination: api/models/__init__.py

Import every model module so Alembic autogenerate sees the whole metadata. Add new modules here.
"""

from models import base, enum_tables, user  # noqa: F401
