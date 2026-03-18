"""Add slug and publication_year to scrolls

Revision ID: a1b2c3d4e5f6
Revises: 39ba54fcd32b
Create Date: 2026-03-18

"""

from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy import text

from alembic import op

revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, Sequence[str], None] = "39ba54fcd32b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def slugify_title(title: str) -> str:
    """Inline slug generation for migration backfill (no app imports)."""
    import re
    import unicodedata

    stop_words = frozenset(
        {"the", "a", "an", "of", "for", "in", "on", "with", "and", "or", "to", "is", "by"}
    )
    normalized = unicodedata.normalize("NFKD", title)
    ascii_only = normalized.encode("ascii", "ignore").decode("ascii")
    lowered = ascii_only.lower().replace("'", "").replace("\u2019", "")
    words = re.findall(r"[a-z0-9]+", lowered)
    words = [w for w in words if w not in stop_words]
    slug = "-".join(words)
    if len(slug) <= 60:
        return slug
    truncated = slug[:60]
    last_hyphen = truncated.rfind("-")
    if last_hyphen > 0:
        truncated = truncated[:last_hyphen]
    return truncated


def upgrade() -> None:
    op.add_column("scrolls", sa.Column("slug", sa.String(60), nullable=True))
    op.add_column("scrolls", sa.Column("publication_year", sa.Integer(), nullable=True))

    # Backfill existing published scrolls
    conn = op.get_bind()
    rows = conn.execute(
        text("SELECT id, title, published_at FROM scrolls WHERE status = 'published' AND published_at IS NOT NULL")
    ).fetchall()

    seen: dict[tuple[int, str], int] = {}
    for row in rows:
        scroll_id, title, published_at = row
        year = published_at.year
        base_slug = slugify_title(title)
        candidate = base_slug
        key = (year, candidate)
        if key in seen:
            seen[key] += 1
            candidate = f"{base_slug}-{seen[key]}"
        else:
            seen[key] = 1

        conn.execute(
            text("UPDATE scrolls SET slug = :slug, publication_year = :year WHERE id = :id"),
            {"slug": candidate, "year": year, "id": str(scroll_id)},
        )

    # Partial unique index: only published scrolls must have unique (year, slug)
    op.create_index(
        "uq_scroll_year_slug",
        "scrolls",
        ["publication_year", "slug"],
        unique=True,
        postgresql_where=text("status = 'published'"),
    )


def downgrade() -> None:
    op.drop_index("uq_scroll_year_slug", table_name="scrolls")
    op.drop_column("scrolls", "publication_year")
    op.drop_column("scrolls", "slug")
