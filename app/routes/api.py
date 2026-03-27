"""Public REST API v1 for AI agent access to scholarly content.

Provides search, metadata, and full-text content endpoints
for programmatic access to published scrolls.
"""

from html.parser import HTMLParser
import re

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.scroll import Scroll, Subject

router = APIRouter(prefix="/api/v1", tags=["api-v1"])

MAX_PER_PAGE = 100
DEFAULT_PER_PAGE = 20


class _HTMLTextExtractor(HTMLParser):
    """Strip HTML tags, returning only text content."""

    def __init__(self):
        super().__init__()
        self._pieces: list[str] = []

    def handle_data(self, data: str):
        self._pieces.append(data)

    def get_text(self) -> str:
        return " ".join(self._pieces).strip()


def _strip_html(html: str) -> str:
    extractor = _HTMLTextExtractor()
    extractor.feed(html)
    return re.sub(r"\s+", " ", extractor.get_text())


def _format_citation(scroll: Scroll, subject_name: str) -> str:
    """Build a simple citation string for attribution."""
    year = scroll.published_at.year if scroll.published_at else scroll.created_at.year
    parts = [
        f"{scroll.authors}.",
        f'"{scroll.title}."',
        f"Scroll Press ({subject_name}),",
        f"v{scroll.version},",
        f"{year}.",
    ]
    if scroll.doi:
        parts.append(f"https://doi.org/{scroll.doi}")
    return " ".join(parts)


def _scroll_summary(scroll: Scroll, subject_name: str) -> dict:
    return {
        "title": scroll.title,
        "authors": scroll.authors,
        "abstract": scroll.abstract,
        "keywords": scroll.keywords or [],
        "subject": subject_name,
        "version": scroll.version,
        "url_hash": scroll.url_hash,
        "doi": scroll.doi,
        "license": scroll.license,
        "created_at": scroll.created_at.isoformat(),
        "published_at": scroll.published_at.isoformat() if scroll.published_at else None,
    }


# --- GET /api/v1/scrolls ---


@router.get("/scrolls")
async def list_scrolls(
    q: str | None = None,
    author: str | None = None,
    subject: str | None = None,
    all_versions: bool = Query(default=False),
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=DEFAULT_PER_PAGE, ge=1, le=MAX_PER_PAGE),
    db: AsyncSession = Depends(get_db),
):
    """Search and list published scrolls with pagination."""
    base = (
        select(Scroll, Subject.name.label("subject_name"))
        .join(Subject)
        .where(Scroll.status == "published")
    )

    if not all_versions:
        # Subquery: max version per scroll_series_id
        latest_version_sq = (
            select(
                Scroll.scroll_series_id,
                func.max(Scroll.version).label("max_version"),
            )
            .where(Scroll.scroll_series_id.isnot(None), Scroll.status == "published")
            .group_by(Scroll.scroll_series_id)
            .subquery()
        )
        # Keep scrolls that are either:
        # 1. Not part of a series (scroll_series_id is NULL), or
        # 2. The latest version in their series
        base = base.outerjoin(
            latest_version_sq,
            Scroll.scroll_series_id == latest_version_sq.c.scroll_series_id,
        ).where(
            (Scroll.scroll_series_id.is_(None))
            | (Scroll.version == latest_version_sq.c.max_version)
        )

    if q:
        pattern = f"%{q}%"
        base = base.where(
            Scroll.title.ilike(pattern)
            | Scroll.abstract.ilike(pattern)
            | Scroll.authors.ilike(pattern)
        )

    if author:
        base = base.where(Scroll.authors.ilike(f"%{author}%"))

    if subject:
        base = base.where(Subject.name == subject)

    count_q = select(func.count()).select_from(base.subquery())
    total = (await db.execute(count_q)).scalar() or 0

    rows = (
        await db.execute(
            base.order_by(Scroll.published_at.desc().nullslast(), Scroll.created_at.desc())
            .offset((page - 1) * per_page)
            .limit(per_page)
        )
    ).all()

    scrolls = [_scroll_summary(row[0], row[1]) for row in rows]

    return {
        "scrolls": scrolls,
        "total": total,
        "page": page,
        "per_page": per_page,
    }


# --- GET /api/v1/scrolls/{url_hash} ---


@router.get("/scrolls/{url_hash}")
async def get_scroll(url_hash: str, db: AsyncSession = Depends(get_db)):
    """Get detailed metadata for a single published scroll."""
    result = await db.execute(
        select(Scroll, Subject.name.label("subject_name"))
        .join(Subject)
        .where(Scroll.url_hash == url_hash, Scroll.status == "published")
    )
    row = result.first()
    if not row:
        raise HTTPException(status_code=404, detail="Scroll not found")

    scroll, subject_name = row[0], row[1]
    data = _scroll_summary(scroll, subject_name)
    data["citation"] = _format_citation(scroll, subject_name)
    data["canonical_url"] = scroll.canonical_url
    data["version_url"] = scroll.version_url

    # Build versions array
    if scroll.scroll_series_id:
        siblings = await db.execute(
            select(Scroll.version, Scroll.url_hash, Scroll.published_at)
            .where(
                Scroll.scroll_series_id == scroll.scroll_series_id,
                Scroll.status == "published",
            )
            .order_by(Scroll.version.desc())
        )
        versions = [
            {
                "version": r.version,
                "url_hash": r.url_hash,
                "published_at": r.published_at.isoformat() if r.published_at else None,
            }
            for r in siblings.all()
        ]
    else:
        versions = [
            {
                "version": scroll.version,
                "url_hash": scroll.url_hash,
                "published_at": scroll.published_at.isoformat() if scroll.published_at else None,
            }
        ]

    data["versions"] = versions
    data["latest_version"] = versions[0]["version"] if versions else scroll.version

    return data


# --- GET /api/v1/scrolls/{url_hash}/content ---


@router.get("/scrolls/{url_hash}/content")
async def get_scroll_content(
    url_hash: str,
    format: str = Query(default="html", pattern="^(html|text)$"),
    db: AsyncSession = Depends(get_db),
):
    """Get full-text content of a published scroll.

    Use format=html for raw HTML, format=text for plain text.
    """
    result = await db.execute(
        select(Scroll, Subject.name.label("subject_name"))
        .join(Subject)
        .where(Scroll.url_hash == url_hash, Scroll.status == "published")
    )
    row = result.first()
    if not row:
        raise HTTPException(status_code=404, detail="Scroll not found")

    scroll, subject_name = row[0], row[1]

    if format == "text":
        content = _strip_html(scroll.html_content)
    else:
        content = scroll.html_content

    return {
        "content": content,
        "format": format,
        "license": scroll.license,
        "citation": _format_citation(scroll, subject_name),
    }


# --- GET /api/v1/subjects ---


@router.get("/subjects")
async def list_subjects(db: AsyncSession = Depends(get_db)):
    """List all subjects that have at least one published scroll, with counts."""
    result = await db.execute(
        select(Subject.name, Subject.description, func.count(Scroll.id).label("scroll_count"))
        .join(Scroll, Subject.id == Scroll.subject_id)
        .where(Scroll.status == "published")
        .group_by(Subject.id, Subject.name, Subject.description)
        .order_by(Subject.name)
    )
    rows = result.all()
    return {
        "subjects": [
            {
                "name": row.name,
                "description": row.description,
                "scroll_count": row.scroll_count,
            }
            for row in rows
        ]
    }
