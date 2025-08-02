"""Add content-addressable storage fields to scrolls

Revision ID: f7ed1e1bdfde
Revises: 23c7a3d4442f
Create Date: 2025-08-02 16:52:35.186420

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f7ed1e1bdfde"
down_revision: Union[str, Sequence[str], None] = "23c7a3d4442f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Add columns as nullable first
    op.add_column("scrolls", sa.Column("content_hash", sa.String(length=64), nullable=True))
    op.add_column("scrolls", sa.Column("url_hash", sa.String(length=20), nullable=True))

    # For existing scrolls, we'll generate hashes based on their content when accessed
    # This is acceptable since the content-addressable storage is for new uploads
    # Legacy scrolls will continue to use preview_id for access

    # Create unique constraints (will only apply to non-null values)
    op.create_unique_constraint("uq_scrolls_url_hash", "scrolls", ["url_hash"])
    op.create_unique_constraint("uq_scrolls_content_hash", "scrolls", ["content_hash"])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint("uq_scrolls_content_hash", "scrolls", type_="unique")
    op.drop_constraint("uq_scrolls_url_hash", "scrolls", type_="unique")
    op.drop_column("scrolls", "url_hash")
    op.drop_column("scrolls", "content_hash")
