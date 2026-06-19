"""Pure converter: Scroll model -> pub.aris.scroll record dict.

No DB, no SDK, no network. Reads only the attributes documented on Scroll's
public surface. Output is a dict ready to hand to the atproto SDK's
createRecord/putRecord call, validated through the typed PressScrollRecord.
"""

from app.integrations.atproto.schema import Author, PressScrollRecord


def _split_author_names(authors: str) -> list[str]:
    """Split Press's comma-separated authors field into clean display names.

    Press stores authors as a free-form string ("Alice Smith, Bob Jones");
    the Lexicon needs them as typed objects. v1: no ORCID per-author yet.
    """
    if not authors:
        return []
    return [name.strip() for name in authors.split(",") if name.strip()]


def scroll_to_lexicon_record(scroll, base_url: str) -> dict:
    """Convert a Scroll-shaped object into a pub.aris.scroll record dict.

    The Scroll's `canonical_url` property returns a relative path
    (e.g. /2026/glee); this function joins it with base_url to produce the
    public canonical URL the record points at.
    """
    base = base_url.rstrip("/")
    canonical = f"{base}{scroll.canonical_url}"

    record = PressScrollRecord(
        title=scroll.title,
        authors=[Author(displayName=name) for name in _split_author_names(scroll.authors)],
        abstract=scroll.abstract,
        canonicalUrl=canonical,
        urlHash=scroll.url_hash,
        contentHash=scroll.content_hash,
        publishedAt=scroll.published_at.isoformat(),
        license=scroll.license,
        doi=scroll.doi or None,
        version=scroll.version,
        publicationYear=scroll.publication_year,
        keywords=list(scroll.keywords) if scroll.keywords else None,
    )

    # by_alias=True surfaces `format` instead of `content_format`.
    # exclude_none keeps absent optional fields out of the wire record.
    return record.model_dump(by_alias=True, exclude_none=True)
