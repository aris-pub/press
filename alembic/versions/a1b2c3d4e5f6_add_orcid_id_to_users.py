"""Add orcid_id column to users

Revision ID: a1b2c3d4e5f6
Revises: d3a7b8c1e2f4
Create Date: 2026-03-28

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, Sequence[str], None] = "d3a7b8c1e2f4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("orcid_id", sa.String(20), nullable=True),
    )
    op.create_index("ix_users_orcid_id", "users", ["orcid_id"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_users_orcid_id", table_name="users")
    op.drop_column("users", "orcid_id")
