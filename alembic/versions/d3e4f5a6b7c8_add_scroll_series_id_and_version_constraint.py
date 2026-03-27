"""Add scroll_series_id and version unique constraint

Revision ID: d3e4f5a6b7c8
Revises: 2a3b4c5d6e7f
Create Date: 2026-03-27

"""

from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy import text

from alembic import op

revision: str = "d3e4f5a6b7c8"
down_revision: Union[str, Sequence[str], None] = "2a3b4c5d6e7f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add scroll_series_id column
    op.add_column(
        "scrolls",
        sa.Column("scroll_series_id", sa.String(36), nullable=True),
    )
    op.create_index("ix_scrolls_scroll_series_id", "scrolls", ["scroll_series_id"])

    # Backfill: each existing scroll becomes v1 of its own series
    conn = op.get_bind()
    if conn.dialect.name == "postgresql":
        conn.execute(
            text(
                "UPDATE scrolls SET scroll_series_id = gen_random_uuid() "
                "WHERE scroll_series_id IS NULL"
            )
        )
    else:
        # SQLite: generate UUIDs in Python
        rows = conn.execute(
            text("SELECT id FROM scrolls WHERE scroll_series_id IS NULL")
        ).fetchall()
        for row in rows:
            import uuid

            conn.execute(
                text("UPDATE scrolls SET scroll_series_id = :sid WHERE id = :id"),
                {"sid": str(uuid.uuid4()), "id": str(row[0])},
            )

    # Drop the old partial unique index on (year, slug) -- superseded by (year, slug, version)
    op.drop_index("uq_scroll_year_slug", table_name="scrolls")

    # Add unique constraint on (publication_year, slug, version)
    op.create_unique_constraint(
        "uq_scroll_year_slug_version",
        "scrolls",
        ["publication_year", "slug", "version"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_scroll_year_slug_version", "scrolls", type_="unique")

    # Restore old partial unique index
    op.create_index(
        "uq_scroll_year_slug",
        "scrolls",
        ["publication_year", "slug"],
        unique=True,
        postgresql_where=text("status = 'published'"),
    )

    op.drop_index("ix_scrolls_scroll_series_id", table_name="scrolls")
    op.drop_column("scrolls", "scroll_series_id")
