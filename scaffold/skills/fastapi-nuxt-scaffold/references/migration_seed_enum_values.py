"""Destination: api/migrations/versions/<rev>_seed_enum_values.py

Template for the migration that fills the enum lookup tables. Create it with

    uv run alembic revision -m "seed enum values"

and paste this body in, keeping the `revision`/`down_revision` lines Alembic generated.

The values are written as LITERALS, never imported from `lib.enums`. A migration is a
point-in-time fact: importing the live enum would make an old migration silently change
meaning the day someone adds a member, and replaying history would no longer reproduce the
database it originally produced.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic. KEEP the values Alembic generated for you.
revision = "<generated>"
down_revision = "<generated-parent>"
branch_labels = None
depends_on = None

# Literal snapshots of lib/enums.py as of this migration.
ROLES = ("ADMIN", "USER")
TWO_FACTOR_METHODS = ("EMAIL", "TOTP")


def _fill(table_name: str, values: tuple[str, ...]) -> None:
    table = sa.table(table_name, sa.column("name", sa.String))
    op.bulk_insert(table, [{"name": value} for value in values])


def upgrade() -> None:
    _fill("role", ROLES)
    _fill("two_factor_method", TWO_FACTOR_METHODS)


def downgrade() -> None:
    for table_name, values in (("role", ROLES), ("two_factor_method", TWO_FACTOR_METHODS)):
        op.execute(
            sa.text(f"DELETE FROM {table_name} WHERE name IN :values").bindparams(
                sa.bindparam("values", value=tuple(values), expanding=True)
            )
        )
