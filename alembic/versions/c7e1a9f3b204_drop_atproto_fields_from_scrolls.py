"""Drop atproto fields from scrolls

The in-app atproto publisher was removed in favor of a standalone bot that
holds no per-scroll state, so these columns are no longer written or read.
Reverses a1c0afb70d7e.

Revision ID: c7e1a9f3b204
Revises: a1c0afb70d7e
Create Date: 2026-10-13

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "c7e1a9f3b204"
down_revision: Union[str, Sequence[str], None] = "a1c0afb70d7e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_index("ix_scrolls_atproto_uri", table_name="scrolls")
    op.drop_column("scrolls", "atproto_published_at")
    op.drop_column("scrolls", "atproto_status")
    op.drop_column("scrolls", "atproto_cid")
    op.drop_column("scrolls", "atproto_uri")


def downgrade() -> None:
    op.add_column("scrolls", sa.Column("atproto_uri", sa.String(length=300), nullable=True))
    op.add_column("scrolls", sa.Column("atproto_cid", sa.String(length=100), nullable=True))
    op.add_column("scrolls", sa.Column("atproto_status", sa.String(length=20), nullable=True))
    op.add_column(
        "scrolls",
        sa.Column("atproto_published_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_scrolls_atproto_uri",
        "scrolls",
        ["atproto_uri"],
        unique=True,
    )
