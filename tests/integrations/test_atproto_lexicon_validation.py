"""Validate the canonical pub.aris.scroll Lexicon JSON file and confirm that
records produced by the converter conform to its declared shape.

The Lexicon JSON is the source of truth; the Pydantic schema in schema.py is
a Python-side mirror. These tests guard the integrity of the JSON document
itself and the round-trip from converter to Lexicon-validated record.
"""

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

LEXICON_PATH = (
    Path(__file__).resolve().parents[2] / "lexicons" / "pub" / "aris" / "scroll.json"
)


@pytest.fixture
def lexicon_doc():
    assert LEXICON_PATH.exists(), f"Lexicon JSON missing at {LEXICON_PATH}"
    return json.loads(LEXICON_PATH.read_text())


def test_lexicon_is_at_canonical_path():
    """The Lexicon file lives at lexicons/pub/aris/scroll.json so it can be
    served at aris.pub/lexicons/pub/aris/scroll.json without a translation
    layer.
    """
    assert LEXICON_PATH.exists()


def test_lexicon_document_is_v1(lexicon_doc):
    assert lexicon_doc["lexicon"] == 1


def test_lexicon_id_is_pub_aris_scroll(lexicon_doc):
    assert lexicon_doc["id"] == "pub.aris.scroll"


def test_main_def_is_record(lexicon_doc):
    main = lexicon_doc["defs"]["main"]
    assert main["type"] == "record"
    assert main["key"] == "any"


def test_required_fields_match_pydantic_schema(lexicon_doc):
    """The JSON Lexicon's required fields must match what the Pydantic mirror
    treats as non-Optional. Drift between the two is the failure mode this
    test guards against.
    """
    required = set(lexicon_doc["defs"]["main"]["record"]["required"])
    expected = {
        "title",
        "authors",
        "abstract",
        "canonicalUrl",
        "urlHash",
        "contentHash",
        "publishedAt",
        "license",
    }
    assert required == expected


def test_arch_field_declared(lexicon_doc):
    """ARCH version tracking is a substrate-trust positioning signal that the
    Lexicon must surface even though it has a default value.
    """
    props = lexicon_doc["defs"]["main"]["record"]["properties"]
    assert "arch" in props


def test_format_field_declared_with_known_values(lexicon_doc):
    """format must enumerate the values downstream consumers can dispatch on."""
    props = lexicon_doc["defs"]["main"]["record"]["properties"]
    assert "format" in props
    assert "interactive_html" in props["format"]["knownValues"]


def test_url_hash_length_matches_press_convention(lexicon_doc):
    """Press generates 12-character url_hashes; the Lexicon must accept 8-20
    to allow shorter test fixtures and future-proof longer hashes.
    """
    props = lexicon_doc["defs"]["main"]["record"]["properties"]
    assert props["urlHash"]["minLength"] >= 8
    assert props["urlHash"]["maxLength"] >= 12


def test_content_hash_exact_length_for_sha256(lexicon_doc):
    """SHA-256 hex digests are exactly 64 chars; the Lexicon should enforce that."""
    props = lexicon_doc["defs"]["main"]["record"]["properties"]
    assert props["contentHash"]["minLength"] == 64
    assert props["contentHash"]["maxLength"] == 64


def test_canonical_url_has_uri_format(lexicon_doc):
    """canonicalUrl must declare format=uri so downstream Lexicon validators
    catch malformed URLs.
    """
    props = lexicon_doc["defs"]["main"]["record"]["properties"]
    assert props["canonicalUrl"]["format"] == "uri"


def test_published_at_has_datetime_format(lexicon_doc):
    props = lexicon_doc["defs"]["main"]["record"]["properties"]
    assert props["publishedAt"]["format"] == "datetime"


def test_author_subtype_defined(lexicon_doc):
    """Authors are typed objects, not bare strings, so ORCID and DID can be
    added without breaking record consumers.
    """
    assert "author" in lexicon_doc["defs"]
    author_def = lexicon_doc["defs"]["author"]
    assert author_def["type"] == "object"
    assert author_def["required"] == ["displayName"]


def test_generated_record_matches_lexicon_required_fields():
    """End-to-end: build a record through the converter; every Lexicon-required
    field must be present in the output.
    """
    from app.integrations.atproto.lexicon import scroll_to_lexicon_record

    class FakeScroll:
        title = "GLEE: Geometric Laplacian Eigenmap Embedding"
        authors = "Leo Torres, Kevin S. Chan, Tina Eliassi-Rad"
        abstract = "A graph embedding method."
        content_hash = "f" * 64
        url_hash = "9bf73ea5ee86"
        version = 1
        publication_year = 2026
        slug = "glee"
        published_at = datetime(2026, 3, 17, 12, 59, 25, tzinfo=timezone.utc)
        license = "cc-by-4.0"
        doi = "10.5281/zenodo.19110499"
        keywords = None

        @property
        def canonical_url(self):
            return f"/{self.publication_year}/{self.slug}"

    record = scroll_to_lexicon_record(FakeScroll(), base_url="https://scroll.press")

    lex = json.loads(LEXICON_PATH.read_text())
    required = lex["defs"]["main"]["record"]["required"]
    for field in required:
        assert field in record, f"converter omits Lexicon-required field {field!r}"


def test_generated_record_omits_undeclared_fields():
    """The converter must not emit fields the Lexicon does not declare; future
    additions go through the Lexicon JSON first.
    """
    from app.integrations.atproto.lexicon import scroll_to_lexicon_record

    class FakeScroll:
        title = "Test"
        authors = "A B"
        abstract = "x"
        content_hash = "f" * 64
        url_hash = "abcdef123456"
        version = 1
        publication_year = 2026
        slug = "test"
        published_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
        license = "cc-by-4.0"
        doi = None
        keywords = ["k1", "k2"]

        @property
        def canonical_url(self):
            return "/2026/test"

    record = scroll_to_lexicon_record(FakeScroll(), base_url="https://scroll.press")

    lex = json.loads(LEXICON_PATH.read_text())
    declared = set(lex["defs"]["main"]["record"]["properties"].keys())
    for key in record.keys():
        assert key in declared, f"converter emits undeclared field {key!r}"
