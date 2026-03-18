"""Slug generation utilities for human-readable scroll URLs."""

import re
import unicodedata

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

STOP_WORDS = frozenset(
    {"the", "a", "an", "of", "for", "in", "on", "with", "and", "or", "to", "is", "by"}
)

MAX_SLUG_LENGTH = 60


def slugify_title(title: str) -> str:
    """Convert a title into a URL-friendly slug.

    NFKD-normalizes, lowercases, extracts alphanumeric words,
    removes stop words, joins with hyphens, and truncates to
    60 characters on a word boundary.
    """
    normalized = unicodedata.normalize("NFKD", title)
    ascii_only = normalized.encode("ascii", "ignore").decode("ascii")
    lowered = ascii_only.lower()
    # Strip apostrophes so contractions stay as one word
    lowered = lowered.replace("'", "").replace("\u2019", "")

    words = re.findall(r"[a-z0-9]+", lowered)
    words = [w for w in words if w not in STOP_WORDS]

    slug = "-".join(words)

    if len(slug) <= MAX_SLUG_LENGTH:
        return slug

    # Truncate on word boundary
    truncated = slug[:MAX_SLUG_LENGTH]
    last_hyphen = truncated.rfind("-")
    if last_hyphen > 0:
        truncated = truncated[:last_hyphen]
    return truncated


async def generate_unique_slug(db: AsyncSession, title: str, year: int) -> str:
    """Generate a slug unique within (publication_year, slug) pairs.

    Checks the scroll table for collisions and appends -2, -3, etc.
    """
    from app.models.scroll import Scroll

    base_slug = slugify_title(title)
    candidate = base_slug
    suffix = 2

    while True:
        result = await db.execute(
            select(Scroll.id).where(
                Scroll.publication_year == year,
                Scroll.slug == candidate,
            )
        )
        if result.first() is None:
            return candidate
        candidate = f"{base_slug}-{suffix}"
        suffix += 1
