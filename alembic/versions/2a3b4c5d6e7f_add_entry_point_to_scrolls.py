"""Add entry_point to scrolls

Revision ID: 2a3b4c5d6e7f
Revises: 1585147ccb65
Create Date: 2026-03-26

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "2a3b4c5d6e7f"
down_revision: Union[str, Sequence[str], None] = "1585147ccb65"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "scrolls",
        sa.Column("entry_point", sa.String(500), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("scrolls", "entry_point")
