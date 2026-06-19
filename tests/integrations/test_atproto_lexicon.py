"""Tests for the Scroll -> pub.aris.scroll record converter.

The converter is a pure function: takes a Scroll-shaped object and a base URL,
returns a dict matching the pub.aris.scroll Lexicon. No DB, no network, no SDK.
This is the testable seam between Press's internal model and atproto's schema.
"""

from datetime import datetime, timezone


class FakeScroll:
    """Minimal Scroll stand-in that mimics the attributes the converter reads.

    Mirrors app.models.scroll.Scroll's public surface without requiring a
    SQLAlchemy session or an actual DB row.
    """

    def __init__(self, **overrides):
        defaults = dict(
            title="Test Scroll",
            authors="Leo Torres, Alice Liddell",
            abstract="An abstract.",
            content_hash="a" * 64,
            url_hash="abcdef123456",
            version=1,
            publication_year=2026,
            slug="test-scroll",
            published_at=datetime(2026, 6, 1, 12, 0, 0, tzinfo=timezone.utc),
            license="cc-by-4.0",
            doi=None,
            keywords=None,
        )
        defaults.update(overrides)
        for k, v in defaults.items():
            setattr(self, k, v)

    @property
    def canonical_url(self):
        if self.publication_year and self.slug:
            return f"/{self.publication_year}/{self.slug}"
        return f"/scroll/{self.url_hash}"


def test_required_fields_present():
    from app.integrations.atproto.lexicon import scroll_to_lexicon_record

    record = scroll_to_lexicon_record(FakeScroll(), base_url="https://scroll.press")

    assert record["title"] == "Test Scroll"
    assert record["abstract"] == "An abstract."
    assert record["canonicalUrl"] == "https://scroll.press/2026/test-scroll"
    assert record["urlHash"] == "abcdef123456"
    assert record["contentHash"] == "a" * 64
    assert record["license"] == "cc-by-4.0"
    assert record["publishedAt"] == "2026-06-01T12:00:00+00:00"


def test_arch_version_always_present():
    """ARCH version is a substrate-trust signal that distinguishes Press
    scrolls from text preprints in downstream surfaces (Semble, Chive).
    Must always be emitted.
    """
    from app.integrations.atproto.lexicon import scroll_to_lexicon_record

    record = scroll_to_lexicon_record(FakeScroll(), base_url="https://scroll.press")
    assert record["arch"] == "1.0"


def test_format_always_present():
    """Format disambiguates Press (interactive HTML) from Chive (text preprints)
    when both appear in the same downstream surface.
    """
    from app.integrations.atproto.lexicon import scroll_to_lexicon_record

    record = scroll_to_lexicon_record(FakeScroll(), base_url="https://scroll.press")
    assert record["format"] == "interactive_html"


def test_authors_split_into_typed_objects():
    from app.integrations.atproto.lexicon import scroll_to_lexicon_record

    scroll = FakeScroll(authors="Leo Torres, Alice Liddell, Sherlock Holmes")
    record = scroll_to_lexicon_record(scroll, base_url="https://scroll.press")
    assert record["authors"] == [
        {"displayName": "Leo Torres"},
        {"displayName": "Alice Liddell"},
        {"displayName": "Sherlock Holmes"},
    ]


def test_single_author():
    from app.integrations.atproto.lexicon import scroll_to_lexicon_record

    scroll = FakeScroll(authors="Leo Torres")
    record = scroll_to_lexicon_record(scroll, base_url="https://scroll.press")
    assert record["authors"] == [{"displayName": "Leo Torres"}]


def test_authors_strip_whitespace():
    from app.integrations.atproto.lexicon import scroll_to_lexicon_record

    scroll = FakeScroll(authors="  Leo Torres ,  Alice Liddell  ")
    record = scroll_to_lexicon_record(scroll, base_url="https://scroll.press")
    assert record["authors"] == [
        {"displayName": "Leo Torres"},
        {"displayName": "Alice Liddell"},
    ]


def test_authors_empty_yields_empty_list():
    """Defensive: published scrolls have authors per the model's NOT NULL,
    but the converter should not crash on degenerate input.
    """
    from app.integrations.atproto.lexicon import scroll_to_lexicon_record

    scroll = FakeScroll(authors="")
    record = scroll_to_lexicon_record(scroll, base_url="https://scroll.press")
    assert record["authors"] == []


def test_doi_omitted_when_absent():
    """exclude_none semantics: absent optional fields stay out of the record."""
    from app.integrations.atproto.lexicon import scroll_to_lexicon_record

    record = scroll_to_lexicon_record(FakeScroll(doi=None), base_url="https://scroll.press")
    assert "doi" not in record


def test_doi_included_when_present():
    from app.integrations.atproto.lexicon import scroll_to_lexicon_record

    scroll = FakeScroll(doi="10.5281/zenodo.19110499")
    record = scroll_to_lexicon_record(scroll, base_url="https://scroll.press")
    assert record["doi"] == "10.5281/zenodo.19110499"


def test_keywords_omitted_when_absent():
    from app.integrations.atproto.lexicon import scroll_to_lexicon_record

    record = scroll_to_lexicon_record(FakeScroll(keywords=None), base_url="https://scroll.press")
    assert "keywords" not in record


def test_keywords_included_when_present():
    from app.integrations.atproto.lexicon import scroll_to_lexicon_record

    scroll = FakeScroll(keywords=["spectral", "graph theory"])
    record = scroll_to_lexicon_record(scroll, base_url="https://scroll.press")
    assert record["keywords"] == ["spectral", "graph theory"]


def test_version_and_publication_year_emitted():
    from app.integrations.atproto.lexicon import scroll_to_lexicon_record

    scroll = FakeScroll(version=2, publication_year=2026)
    record = scroll_to_lexicon_record(scroll, base_url="https://scroll.press")
    assert record["version"] == 2
    assert record["publicationYear"] == 2026


def test_canonical_url_falls_back_when_no_slug():
    """Press scrolls without slug/publication_year fall back to the
    content-addressable /scroll/{url_hash} URL.
    """
    from app.integrations.atproto.lexicon import scroll_to_lexicon_record

    scroll = FakeScroll(publication_year=None, slug=None)
    record = scroll_to_lexicon_record(scroll, base_url="https://scroll.press")
    assert record["canonicalUrl"] == "https://scroll.press/scroll/abcdef123456"


def test_published_at_serialized_as_iso_8601():
    """atproto datetime format expects ISO 8601 with timezone."""
    from app.integrations.atproto.lexicon import scroll_to_lexicon_record

    scroll = FakeScroll(
        published_at=datetime(2026, 3, 17, 12, 59, 25, 528873, tzinfo=timezone.utc)
    )
    record = scroll_to_lexicon_record(scroll, base_url="https://scroll.press")
    assert record["publishedAt"] == "2026-03-17T12:59:25.528873+00:00"


def test_base_url_trailing_slash_normalized():
    """Trailing slash on base_url should not produce double-slash in canonicalUrl."""
    from app.integrations.atproto.lexicon import scroll_to_lexicon_record

    record = scroll_to_lexicon_record(FakeScroll(), base_url="https://scroll.press/")
    assert record["canonicalUrl"] == "https://scroll.press/2026/test-scroll"


def test_record_validates_against_pydantic_schema():
    """The output dict must round-trip through the typed Pydantic schema."""
    from app.integrations.atproto.lexicon import scroll_to_lexicon_record
    from app.integrations.atproto.schema import PressScrollRecord

    scroll = FakeScroll(doi="10.5281/zenodo.19110499", keywords=["test"])
    record = scroll_to_lexicon_record(scroll, base_url="https://scroll.press")
    parsed = PressScrollRecord.model_validate(record)
    assert parsed.title == scroll.title
    assert parsed.contentHash == scroll.content_hash
    assert parsed.urlHash == scroll.url_hash
    assert parsed.doi == "10.5281/zenodo.19110499"


def test_dollar_type_not_emitted_by_converter():
    """$type is injected by the atproto SDK at createRecord/putRecord time,
    not by the converter. Including it here would cause a duplicate-key issue.
    """
    from app.integrations.atproto.lexicon import scroll_to_lexicon_record

    record = scroll_to_lexicon_record(FakeScroll(), base_url="https://scroll.press")
    assert "$type" not in record


def test_published_at_falls_back_to_created_at_when_null():
    """Some prod scrolls (seed/demo data) carry status='published' but a NULL
    published_at column. The converter must not crash on them: fall back to
    created_at so every published scroll gets a record.
    """
    from app.integrations.atproto.lexicon import scroll_to_lexicon_record

    scroll = FakeScroll(published_at=None)
    scroll.created_at = datetime(2026, 5, 1, 9, 0, 0, tzinfo=timezone.utc)

    record = scroll_to_lexicon_record(scroll, base_url="https://scroll.press")
    assert record["publishedAt"] == "2026-05-01T09:00:00+00:00"
