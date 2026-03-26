"""Add archive_manifest column to scrolls

Revision ID: d3a7b8c1e2f4
Revises: ffb0fc228185
Create Date: 2026-03-26 12:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d3a7b8c1e2f4"
down_revision: Union[str, None] = "ffb0fc228185"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("scrolls", sa.Column("archive_manifest", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("scrolls", "archive_manifest")
