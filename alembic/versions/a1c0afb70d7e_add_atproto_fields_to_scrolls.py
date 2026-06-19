"""Add atproto fields to scrolls

Adds the columns the atproto publisher needs to track per-scroll publishing
state: the at:// URI the record was created at, its CID for drift detection,
the publish status (pending/published/failed), and the timestamp of the last
successful publish. Mirrors the pattern doi_* uses.

Revision ID: a1c0afb70d7e
Revises: 596bb368fc0d
Create Date: 2026-06-19

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "a1c0afb70d7e"
down_revision: Union[str, Sequence[str], None] = "596bb368fc0d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
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


def downgrade() -> None:
    op.drop_index("ix_scrolls_atproto_uri", table_name="scrolls")
    op.drop_column("scrolls", "atproto_published_at")
    op.drop_column("scrolls", "atproto_status")
    op.drop_column("scrolls", "atproto_cid")
    op.drop_column("scrolls", "atproto_uri")
