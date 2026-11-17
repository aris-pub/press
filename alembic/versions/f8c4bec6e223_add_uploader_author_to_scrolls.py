"""add uploader_author to scrolls

Revision ID: f8c4bec6e223
Revises: c7e1a9f3b204
Create Date: 2026-11-17 22:05:40.201632

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f8c4bec6e223"
down_revision: Union[str, Sequence[str], None] = "c7e1a9f3b204"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Which name in the author list belongs to the uploader. Null for papers posted
    # before the upload form asked; those fall back to matching the account name.
    op.add_column("scrolls", sa.Column("uploader_author", sa.String(length=200), nullable=True))


def downgrade() -> None:
    op.drop_column("scrolls", "uploader_author")
