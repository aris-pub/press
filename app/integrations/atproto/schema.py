"""Pydantic schema mirroring the pub.aris.scroll Lexicon.

This is the typed contract the converter writes into and the SDK reads out of.
The canonical schema is the JSON Lexicon at lexicons/pub/aris/scroll.json; this
Pydantic mirror is the type-checkable Python view of the same shape.
"""

from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


class Author(BaseModel):
    """One author of a scroll. displayName is required, ORCID and DID optional."""

    displayName: str = Field(max_length=200)
    orcid: Optional[str] = Field(default=None, max_length=30)
    did: Optional[str] = Field(default=None, max_length=100)


class PressScrollRecord(BaseModel):
    """A pub.aris.scroll record. Maps 1:1 to the Lexicon's main record def.

    The record points at a Press scroll; the scroll content itself remains on
    Press's content-addressable storage. urlHash + contentHash are the load-bearing
    identifiers anchoring the record to a specific immutable artifact.
    """

    # Required
    title: str = Field(max_length=500)
    authors: List[Author]
    abstract: str = Field(max_length=10000)
    canonicalUrl: str = Field(max_length=500)
    urlHash: str = Field(min_length=8, max_length=20)
    contentHash: str = Field(min_length=64, max_length=64)
    publishedAt: str
    license: str = Field(max_length=50)

    # Substrate-trust signals (always emitted, per CRXO position)
    arch: str = Field(default="1.0", max_length=10)
    # `format` collides with a Python builtin name; alias preserves the JSON key.
    content_format: str = Field(
        default="interactive_html", max_length=50, serialization_alias="format"
    )

    # Optional
    doi: Optional[str] = Field(default=None, max_length=200)
    version: int = Field(default=1, ge=1)
    publicationYear: Optional[int] = Field(default=None, ge=1900, le=2200)
    keywords: Optional[List[str]] = None

    model_config = ConfigDict(populate_by_name=True)
