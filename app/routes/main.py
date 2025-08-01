"""Main application routes (landing page, etc.)."""

import csv
from datetime import datetime
import io
import json
import re
import time
from typing import Optional

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.session import get_current_user_from_session
from app.database import get_db
from app.logging_config import get_logger, log_error, log_request
from app.models.preview import Preview, Subject

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.get("/", response_class=HTMLResponse)
async def landing_page(request: Request, db: AsyncSession = Depends(get_db)):
    """Display the application landing page.

    Shows the main homepage of Scroll Press with different content and navigation
    options based on user authentication status. Anonymous users see registration
    prompts while authenticated users see upload options.

    """
    log_request(request)
    current_user = await get_current_user_from_session(request, db)

    if current_user:
        log_request(request, user_id=str(current_user.id))

    # Get subjects with scroll counts
    subjects_result = await db.execute(
        select(Subject.name, func.count(Subject.id).label("scroll_count"))
        .outerjoin(Subject.scrolls)
        .group_by(Subject.id, Subject.name)
        .order_by(Subject.name)
    )
    subjects = subjects_result.all()

    # Get recent published scrolls with subjects
    previews_result = await db.execute(
        select(Preview, Subject.name.label("subject_name"))
        .join(Subject)
        .where(Preview.status == "published")
        .order_by(Preview.created_at.desc())
        .limit(4)
    )
    previews = previews_result.all()

    return templates.TemplateResponse(
        request,
        "index.html",
        {"current_user": current_user, "subjects": subjects, "previews": previews},
    )


@router.get("/health")
async def health_check(request: Request, db: AsyncSession = Depends(get_db)):
    """Health check endpoint for monitoring and load balancers.

    Performs basic application health checks including:
    - Database connectivity
    - Basic application functionality

    Returns:
        dict: Health status with timestamp and component checks
    """
    log_request(request)
    start_time = time.time()

    try:
        # Test database connectivity
        await db.execute(text("SELECT 1"))

        # Test basic model queries
        result = await db.execute(select(func.count(Subject.id)))
        subject_count = result.scalar()

        result = await db.execute(select(func.count(Preview.id)))
        scroll_count = result.scalar()

        response_time = round((time.time() - start_time) * 1000, 2)

        get_logger().info(f"Health check passed - response_time: {response_time}ms")

        return {
            "status": "healthy",
            "timestamp": time.time(),
            "response_time_ms": response_time,
            "components": {"database": "healthy", "models": "healthy"},
            "metrics": {"subject_count": subject_count, "scroll_count": scroll_count},
            "version": "0.1.0",
        }

    except Exception as e:
        response_time = round((time.time() - start_time) * 1000, 2)
        log_error(e, request, context="health_check")

        return {
            "status": "unhealthy",
            "timestamp": time.time(),
            "response_time_ms": response_time,
            "components": {"database": "unhealthy", "models": "unknown"},
            "error": str(e),
            "version": "0.1.0",
        }


@router.get("/about", response_class=HTMLResponse)
async def about_page(request: Request, db: AsyncSession = Depends(get_db)):
    """Display the About page.

    Shows information about Scroll Press, its mission, and features.
    """
    log_request(request)
    current_user = await get_current_user_from_session(request, db)

    if current_user:
        log_request(request, user_id=str(current_user.id))

    return templates.TemplateResponse(request, "about.html", {"current_user": current_user})


@router.get("/contact", response_class=HTMLResponse)
async def contact_page(request: Request, db: AsyncSession = Depends(get_db)):
    """Display the Contact page.

    Shows contact information and ways to get in touch with the Scroll Press team.
    """
    log_request(request)
    current_user = await get_current_user_from_session(request, db)

    if current_user:
        log_request(request, user_id=str(current_user.id))

    return templates.TemplateResponse(request, "contact.html", {"current_user": current_user})


@router.get("/terms", response_class=HTMLResponse)
async def terms_page(request: Request, db: AsyncSession = Depends(get_db)):
    """Display the Terms of Service page.

    Shows the legal terms and conditions for using Scroll Press.
    """
    log_request(request)
    current_user = await get_current_user_from_session(request, db)

    if current_user:
        log_request(request, user_id=str(current_user.id))

    return templates.TemplateResponse(request, "terms.html", {"current_user": current_user})


@router.get("/privacy", response_class=HTMLResponse)
async def privacy_page(request: Request, db: AsyncSession = Depends(get_db)):
    """Display the Privacy Policy page.

    Shows information about data collection, processing, and user rights under GDPR.
    """
    log_request(request)
    current_user = await get_current_user_from_session(request, db)

    if current_user:
        log_request(request, user_id=str(current_user.id))

    return templates.TemplateResponse(request, "privacy.html", {"current_user": current_user})


@router.get("/legal", response_class=HTMLResponse)
async def legal_page(request: Request, db: AsyncSession = Depends(get_db)):
    """Display the Impressum/Legal page.

    Shows legal information required by German law (TMG).
    """
    log_request(request)
    current_user = await get_current_user_from_session(request, db)

    if current_user:
        log_request(request, user_id=str(current_user.id))

    return templates.TemplateResponse(request, "legal.html", {"current_user": current_user})


@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request, db: AsyncSession = Depends(get_db)):
    """Display user dashboard with their published papers."""
    log_request(request)
    current_user = await get_current_user_from_session(request, db)

    if not current_user:
        return RedirectResponse(url="/login", status_code=302)

    log_request(request, user_id=str(current_user.id))

    # Get user's published papers with subject names
    published_papers = await db.execute(
        select(Preview, Subject.name.label("subject_name"))
        .join(Subject)
        .where(Preview.user_id == current_user.id, Preview.status == "published")
        .order_by(Preview.created_at.desc())
    )
    papers = published_papers.all()

    return templates.TemplateResponse(
        request, "dashboard.html", {"current_user": current_user, "papers": papers}
    )


def highlight_search_terms(text: str, query: str) -> str:
    """Highlight search terms in text with <mark> tags."""
    if not text or not query:
        return text

    # Split query into individual terms and clean them
    terms = [term.strip() for term in query.split() if term.strip()]

    # Escape HTML in original text first
    import html

    escaped_text = html.escape(text)

    # Highlight each term (case insensitive)
    for term in terms:
        # Escape the term for regex
        escaped_term = re.escape(term)
        pattern = re.compile(f"({escaped_term})", re.IGNORECASE)
        escaped_text = pattern.sub(r"<mark>\1</mark>", escaped_text)

    return escaped_text


@router.get("/search", response_class=HTMLResponse)
async def search_results(
    request: Request, q: Optional[str] = None, db: AsyncSession = Depends(get_db)
):
    """Search for scrolls across titles, authors, abstracts, and content.

    Args:
        request: FastAPI request object
        q: Search query parameter
        db: Database session

    Returns:
        Search results page or redirect to homepage if no query
    """
    log_request(request)
    current_user = await get_current_user_from_session(request, db)

    if current_user:
        log_request(request, user_id=str(current_user.id))

    # Redirect to homepage if no query
    if not q or not q.strip():
        return RedirectResponse(url="/", status_code=302)

    query = q.strip()
    get_logger().info(f"Search query: '{query}'")

    try:
        # Check if we're using PostgreSQL or SQLite for testing
        db_url = str(db.get_bind().url)
        is_postgresql = "postgresql" in db_url
        get_logger().info(f"Using database: {db_url}, PostgreSQL: {is_postgresql}")

        if is_postgresql:
            # Use hybrid approach: full-text search + partial matching for better UX
            # This gives us both semantic matching and partial word matching
            search_sql = text("""
                SELECT p.*, s.name as subject_name,
                    -- Calculate relevance scores
                    CASE WHEN (
                        to_tsvector('english', p.title) @@ plainto_tsquery('english', :query)
                        OR to_tsvector('english', p.authors) @@ plainto_tsquery('english', :query)  
                        OR to_tsvector('english', p.abstract) @@ plainto_tsquery('english', :query)
                        OR to_tsvector('english', COALESCE(p.html_content, '')) @@ plainto_tsquery('english', :query)
                    ) THEN 
                        ts_rank(to_tsvector('english', p.title || ' ' || p.authors || ' ' || p.abstract), plainto_tsquery('english', :query))
                    ELSE 0.1 
                    END as fts_rank
                FROM previews p
                JOIN subjects s ON p.subject_id = s.id
                WHERE p.status = 'published'
                AND (
                    -- Full-text search (higher priority)
                    to_tsvector('english', p.title) @@ plainto_tsquery('english', :query)
                    OR to_tsvector('english', p.authors) @@ plainto_tsquery('english', :query)  
                    OR to_tsvector('english', p.abstract) @@ plainto_tsquery('english', :query)
                    OR to_tsvector('english', COALESCE(p.html_content, '')) @@ plainto_tsquery('english', :query)
                    -- Partial matching (fallback for partial words)
                    OR p.title ILIKE '%' || :query || '%'
                    OR p.authors ILIKE '%' || :query || '%'
                    OR p.abstract ILIKE '%' || :query || '%'
                    OR p.html_content ILIKE '%' || :query || '%'
                )
                ORDER BY fts_rank DESC, p.created_at DESC
                LIMIT 50
            """)

            search_results = await db.execute(search_sql, {"query": query})
            # Convert to the expected format
            results = [(row, row.subject_name) for row in search_results.fetchall()]
        else:
            # Fallback to LIKE queries for SQLite (testing)
            like_pattern = f"%{query}%"
            search_results = await db.execute(
                select(Preview, Subject.name.label("subject_name"))
                .join(Subject)
                .where(
                    Preview.status == "published",
                    or_(
                        Preview.title.ilike(like_pattern),
                        Preview.authors.ilike(like_pattern),
                        Preview.abstract.ilike(like_pattern),
                        Preview.html_content.ilike(like_pattern),
                    ),
                )
                .order_by(Preview.created_at.desc())
                .limit(50)
            )

        if is_postgresql:
            # Results are already processed above
            result_count = len(results)
        else:
            # SQLite results need standard processing
            results = search_results.all()
            result_count = len(results)

        get_logger().info(f"Search for '{query}' returned {result_count} results")

        return templates.TemplateResponse(
            request,
            "search_results.html",
            {
                "current_user": current_user,
                "query": query,
                "results": results,
                "result_count": result_count,
                "highlight_terms": lambda text: highlight_search_terms(text, query),
            },
        )

    except Exception as e:
        log_error(e, request, context="search")
        get_logger().error(f"Search error details: {str(e)}")

        return templates.TemplateResponse(
            request,
            "search_results.html",
            {
                "current_user": current_user,
                "query": query,
                "results": [],
                "result_count": 0,
                "error": "There was an error performing your search. Please try again.",
                "highlight_terms": lambda text: text,
            },
        )


@router.post("/export-data")
async def export_data(
    request: Request,
    format: str = Form(...),
    include_content: bool = Form(False),
    db: AsyncSession = Depends(get_db),
):
    """Export user's published papers in various formats."""
    log_request(request)
    current_user = await get_current_user_from_session(request, db)

    if not current_user:
        return RedirectResponse(url="/login", status_code=302)

    log_request(request, user_id=str(current_user.id))

    # Validate format
    valid_formats = ["csv", "json", "bibtex"]
    if format not in valid_formats:
        raise HTTPException(status_code=400, detail="Invalid format specified")

    # Validate content inclusion
    if include_content and format != "json":
        error_msg = f"{format.upper()} format does not support HTML content inclusion"
        raise HTTPException(status_code=400, detail=error_msg)

    # Get user's published papers with subject names
    published_papers = await db.execute(
        select(Preview, Subject.name.label("subject_name"))
        .join(Subject)
        .where(Preview.user_id == current_user.id, Preview.status == "published")
        .order_by(Preview.created_at.desc())
    )
    papers = published_papers.all()

    # Generate timestamp for filename
    timestamp = datetime.now().strftime("%Y-%m-%d")
    content_suffix = "full" if include_content else "metadata"
    filename = f"press_export_{format}_{content_suffix}_{timestamp}.{format}"

    if format == "csv":
        return _export_csv(papers, filename)
    elif format == "json":
        return _export_json(papers, include_content, filename)
    elif format == "bibtex":
        return _export_bibtex(papers, filename)


def _export_csv(papers, filename):
    """Export papers as CSV format."""
    output = io.StringIO()
    writer = csv.writer(output)

    # Write header
    headers = [
        "title",
        "authors",
        "abstract",
        "keywords",
        "subject",
        "version",
        "published_date",
        "scroll_id",
    ]
    writer.writerow(headers)

    # Write data rows
    for paper_row in papers:
        paper = paper_row[0]
        subject_name = paper_row[1]

        # Convert keywords list to comma-separated string
        keywords_str = ", ".join(paper.keywords) if paper.keywords else ""

        # Format published date
        published_date = (
            paper.published_at.strftime("%Y-%m-%d %H:%M:%S") if paper.published_at else ""
        )

        row = [
            paper.title,
            paper.authors,
            paper.abstract,
            keywords_str,
            subject_name,
            paper.version,
            published_date,
            paper.preview_id,
        ]
        writer.writerow(row)

    csv_content = output.getvalue()
    output.close()

    return Response(
        content=csv_content,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def _export_json(papers, include_content, filename):
    """Export papers as JSON format."""
    data = []

    for paper_row in papers:
        paper = paper_row[0]
        subject_name = paper_row[1]

        # Base metadata
        paper_data = {
            "title": paper.title,
            "authors": paper.authors,
            "abstract": paper.abstract,
            "keywords": paper.keywords,
            "subject": subject_name,
            "version": paper.version,
            "published_date": paper.published_at.isoformat() if paper.published_at else None,
            "scroll_id": paper.preview_id,
            "created_at": paper.created_at.isoformat(),
            "updated_at": paper.updated_at.isoformat(),
        }

        # Include HTML content if requested
        if include_content:
            paper_data["html_content"] = paper.html_content

        data.append(paper_data)

    json_content = json.dumps(data, indent=2, ensure_ascii=False)

    return Response(
        content=json_content,
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def _export_bibtex(papers, filename):
    """Export papers as BibTeX format."""
    bibtex_entries = []

    for paper_row in papers:
        paper = paper_row[0]
        subject_name = paper_row[1]

        # Generate BibTeX key from title and year
        title_words = re.sub(r"[^\w\s]", "", paper.title).split()[:3]
        key_base = "".join(word.capitalize() for word in title_words)
        year = paper.published_at.year if paper.published_at else datetime.now().year
        bibtex_key = f"{key_base}{year}"

        # Format authors for BibTeX (replace commas with 'and')
        authors_bibtex = paper.authors.replace(",", " and")

        # Create BibTeX entry
        entry = f"""@misc{{{bibtex_key},
  title={{{{ {paper.title} }}}},
  author={{{{ {authors_bibtex} }}}},
  year={{{year}}},
  note={{{{ Scroll Press preprint, {subject_name} }}}},
  url={{{{ https://press.example.com/scroll/{paper.preview_id} }}}}
}}"""

        bibtex_entries.append(entry)

    bibtex_content = "\n\n".join(bibtex_entries)

    return Response(
        content=bibtex_content,
        media_type="text/plain; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
