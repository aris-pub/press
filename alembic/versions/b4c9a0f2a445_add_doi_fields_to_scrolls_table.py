"""Add DOI fields to scrolls table

Revision ID: b4c9a0f2a445
Revises: ffb0fc228185
Create Date: 2026-01-14 13:08:29.145503

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b4c9a0f2a445"
down_revision: Union[str, Sequence[str], None] = "ffb0fc228185"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add DOI tracking fields to scrolls table."""
    # Add DOI field (nullable, will be populated after publication)
    op.add_column("scrolls", sa.Column("doi", sa.String(length=100), nullable=True))

    # Add DOI status field (pending, minted, failed, null for pre-existing scrolls)
    op.add_column("scrolls", sa.Column("doi_status", sa.String(length=20), nullable=True))

    # Add CHECK constraint to ensure only valid doi_status values
    op.create_check_constraint(
        "ck_scrolls_doi_status_valid",
        "scrolls",
        "doi_status IN ('pending', 'minted', 'failed') OR doi_status IS NULL",
    )

    # Add DOI minted timestamp
    op.add_column("scrolls", sa.Column("doi_minted_at", sa.DateTime(timezone=True), nullable=True))

    # Add Zenodo deposit ID for reference
    op.add_column("scrolls", sa.Column("zenodo_deposit_id", sa.Integer(), nullable=True))

    # Add index on DOI for lookups
    op.create_index(op.f("ix_scrolls_doi"), "scrolls", ["doi"], unique=True)


def downgrade() -> None:
    """Remove DOI tracking fields."""
    op.drop_index(op.f("ix_scrolls_doi"), table_name="scrolls")
    op.drop_constraint("ck_scrolls_doi_status_valid", "scrolls", type_="check")
    op.drop_column("scrolls", "zenodo_deposit_id")
    op.drop_column("scrolls", "doi_minted_at")
    op.drop_column("scrolls", "doi_status")
    op.drop_column("scrolls", "doi")
