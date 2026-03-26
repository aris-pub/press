"""Add storage_type to scrolls

Revision ID: 1585147ccb65
Revises: a1b2c3d4e5f6
Create Date: 2026-03-26

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "1585147ccb65"
down_revision: Union[str, Sequence[str], None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "scrolls",
        sa.Column("storage_type", sa.String(20), nullable=False, server_default="inline"),
    )


def downgrade() -> None:
    op.drop_column("scrolls", "storage_type")
