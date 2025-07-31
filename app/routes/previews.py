"""Scroll upload and management routes."""

from pathlib import Path
import re
import uuid as uuid_module

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth.session import get_current_user_from_session
from app.database import get_db
from app.logging_config import get_logger, log_error, log_preview_event, log_request
from app.models.preview import Preview, Subject
from app.upload import HTMLProcessor

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.get("/scroll/{preview_id}", response_class=HTMLResponse)
async def view_scroll(request: Request, preview_id: str, db: AsyncSession = Depends(get_db)):
    """Display a published scroll by its scroll_id.

    Shows the full HTML content of a published research scroll. Only published
    scrolls are accessible to the public.

    """
    log_request(request, extra_data={"preview_id": preview_id})

    result = await db.execute(
        select(Preview)
        .options(selectinload(Preview.subject))
        .where(Preview.preview_id == preview_id, Preview.status == "published")
    )
    preview = result.scalar_one_or_none()

    if not preview:
        get_logger().warning(f"Scroll not found: {preview_id}")
        return templates.TemplateResponse(
            request, "404.html", {"message": "Scroll not found"}, status_code=404
        )

    log_preview_event(
        "view", preview_id, str(preview.user_id), request, extra_data={"title": preview.title}
    )
    
    # Check if HTML content has CSS
    has_css = bool(re.search(r'<style|<link[^>]*stylesheet|style\s*=', preview.html_content, re.IGNORECASE))
    
    # If no CSS detected, inject basic styles
    if not has_css:
        basic_css = """
        <style>
            body {
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Roboto', 'Helvetica Neue', Arial, sans-serif;
                line-height: 1.6;
                max-width: 800px;
                margin: 0 auto;
                padding: 2rem;
                color: #333;
                background: #fff;
            }
            h1, h2, h3, h4, h5, h6 {
                font-family: Georgia, serif;
                color: #222;
                margin: 1.5rem 0 1rem 0;
            }
            h1 { font-size: 2rem; }
            h2 { font-size: 1.5rem; }
            h3 { font-size: 1.25rem; }
            p { margin: 1rem 0; }
            code {
                background: #f5f5f5;
                padding: 0.2rem 0.4rem;
                border-radius: 3px;
                font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', monospace;
                font-size: 0.9em;
            }
            pre {
                background: #f5f5f5;
                padding: 1rem;
                border-radius: 5px;
                overflow-x: auto;
            }
            blockquote {
                border-left: 4px solid #ef4444;
                padding-left: 1rem;
                margin: 1rem 0;
                font-style: italic;
                color: #666;
            }
            
            /* Dark mode */
            @media (prefers-color-scheme: dark) {
                body {
                    background: #1a1a1a;
                    color: #e5e5e5;
                }
                h1, h2, h3, h4, h5, h6 {
                    color: #fff;
                }
                code, pre {
                    background: #2a2a2a;
                    color: #e5e5e5;
                }
                blockquote {
                    color: #ccc;
                }
            }
        </style>
        """
        
        # Inject CSS after <head> tag or at the beginning if no head tag
        if '<head>' in preview.html_content:
            preview.html_content = preview.html_content.replace('<head>', f'<head>{basic_css}', 1)
        else:
            preview.html_content = basic_css + preview.html_content
    
    return templates.TemplateResponse(request, "preview.html", {"preview": preview})


@router.get("/upload", response_class=HTMLResponse)
async def upload_page(request: Request, db: AsyncSession = Depends(get_db)):
    """Display the HTML scroll upload page.

    Shows the upload form for authenticated users to submit their HTML research
    scrolls. Unauthenticated users are redirected to login. Loads available
    academic subjects for categorization.

    """
    log_request(request)
    current_user = await get_current_user_from_session(request, db)

    # Redirect unauthenticated users to login
    if not current_user:
        get_logger().info("Unauthenticated user redirected from upload page to login")
        return RedirectResponse(url="/login", status_code=302)

    log_request(request, user_id=str(current_user.id))

    # Load available subjects
    result = await db.execute(select(Subject).order_by(Subject.name))
    subjects = result.scalars().all()

    return templates.TemplateResponse(
        request, "upload.html", {"current_user": current_user, "subjects": subjects}
    )


@router.post("/upload-form", response_class=HTMLResponse)
async def upload_form(
    request: Request,
    title: str = Form(...),
    authors: str = Form(...),
    subject_id: str = Form(...),
    abstract: str = Form(...),
    keywords: str = Form(""),
    html_content: str = Form(...),
    action: str = Form("publish"),  # Always publish
    db: AsyncSession = Depends(get_db),
):
    """Process HTML scroll upload form submission.

    Validates and processes the upload of HTML research scrolls with
    direct publishing. Uses HTMX for seamless form submission
    with success/error feedback.

    Args:
        request: The HTTP request object for HTMX responses
        title: The scroll title (required)
        authors: Comma-separated author names (required)
        subject_id: UUID of the academic subject (required)
        abstract: Research abstract/summary (required)
        keywords: Comma-separated keywords (optional)
        html_content: Complete HTML document content (required)
        action: Always "publish" to make public
        db: Database session dependency for scroll operations

    Returns:
        HTMLResponse: Success HTML content or error form with validation messages

    Raises:
        ValueError: For validation errors (missing fields, invalid subject)
        Exception: For database or unexpected errors during upload

    """
    current_user = await get_current_user_from_session(request, db)

    # Redirect unauthenticated users
    if not current_user:
        return RedirectResponse(url="/login", status_code=302)

    log_request(
        request, user_id=str(current_user.id), extra_data={"title": title, "action": action}
    )

    try:
        # Validate required fields
        if not title or not title.strip():
            raise ValueError("Title is required")
        if not authors or not authors.strip():
            raise ValueError("Authors are required")
        if not abstract or not abstract.strip():
            raise ValueError("Abstract is required")
        if not html_content or not html_content.strip():
            raise ValueError("HTML content is required")

        # Find the subject - handle UUID conversion
        try:
            subject_uuid = uuid_module.UUID(subject_id)
            result = await db.execute(select(Subject).where(Subject.id == subject_uuid))
            subject = result.scalar_one_or_none()
            if not subject:
                raise ValueError("Invalid subject selected")
        except (ValueError, TypeError):
            raise ValueError("Invalid subject ID format")

        # Process keywords
        keyword_list = []
        if keywords.strip():
            keyword_list = [kw.strip() for kw in keywords.split(",") if kw.strip()]

        # Create scroll
        preview = Preview(
            user_id=current_user.id,
            title=title.strip(),
            authors=authors.strip(),
            subject_id=subject.id,
            abstract=abstract.strip(),
            keywords=keyword_list,
            html_content=html_content.strip(),
            status="published",
        )
        preview.publish()

        db.add(preview)
        await db.commit()
        await db.refresh(preview)

        log_preview_event(
            "create",
            str(preview.id),
            str(current_user.id),
            request,
            extra_data={"title": preview.title, "status": "published"},
        )

        # If publishing directly, publish the scroll after it's in the database
        if action == "publish":
            # Load the subject relationship before publishing
            result = await db.execute(
                select(Preview)
                .options(selectinload(Preview.subject))
                .where(Preview.id == preview.id)
            )
            preview = result.scalar_one()
            preview.publish()
            await db.commit()  # Commit the publish changes
            log_preview_event(
                "publish",
                preview.preview_id,
                str(current_user.id),
                request,
                extra_data={"title": preview.title},
            )

        # Return success response - just the content for HTMX
        success_message = "Your scroll has been published successfully!"
        preview_url = f"/scroll/{preview.preview_id}"

        # Return just the success content (not full page) for HTMX
        success_html = f"""
        <div class="success-container" style="max-width: 600px; margin: 4rem auto; padding: 3rem; background: #f0fdf4; border: 1px solid #bbf7d0; border-radius: 4px; text-align: center;">
            <h1 style="color: #15803d; margin-bottom: 1rem;">✅ Success!</h1>
            <p style="color: #166534; font-size: 1.1rem; margin-bottom: 2rem;">{success_message}</p>

            <div style="margin-bottom: 2rem;">
                <p><strong>Title:</strong> {preview.title}</p>
                <p><strong>Status:</strong> Published</p>
                <p><strong>Scroll ID:</strong> {preview.preview_id}</p>
            </div>

            <div style="display: flex; gap: 1rem; justify-content: center;">
                <a href="{preview_url}" class="btn btn-primary">View Scroll</a>
                <a href="/upload" class="btn btn-secondary">Upload Another</a>
                <a href="/" class="btn btn-secondary">Go Home</a>
            </div>
        </div>
        """

        return HTMLResponse(content=success_html)

    except Exception as e:
        error_message = str(e) if str(e) else "Upload failed. Please try again."
        log_error(e, request, user_id=str(current_user.id), context="preview_upload")

        # Load subjects for error response
        result = await db.execute(select(Subject).order_by(Subject.name))
        subjects = result.scalars().all()

        # Return form with error
        return templates.TemplateResponse(
            request,
            "upload.html",
            {
                "current_user": current_user,
                "subjects": subjects,
                "error": error_message,
                "form_data": {
                    "title": title,
                    "authors": authors,
                    "subject_id": subject_id,
                    "abstract": abstract,
                    "keywords": keywords,
                    "html_content": html_content,
                },
            },
            status_code=422,
        )


@router.post("/upload/html")
async def upload_html_paper(
    request: Request,
    file: UploadFile = File(...),
    title: str = Form(...),
    authors: str = Form(...),
    subject_id: str = Form(...),
    abstract: str = Form(...),
    keywords: str = Form(""),
    action: str = Form("publish"),
    db: AsyncSession = Depends(get_db),
):
    """Upload HTML source with enhanced security and sanitization.

    Processes uploaded HTML files through comprehensive security validation,
    sanitization, and content checks before storing in the database.

    Args:
        request: The HTTP request object
        file: The uploaded HTML file
        title: The scroll title (required)
        authors: Comma-separated author names (required)
        subject_id: UUID of the academic subject (required)
        abstract: Research abstract/summary (required)
        keywords: Comma-separated keywords (optional)
        action: Always "publish" to make public
        db: Database session dependency

    Returns:
        JSONResponse: Processing results with sanitized content and metadata

    Raises:
        HTTPException: For authentication, validation, or processing errors
    """
    current_user = await get_current_user_from_session(request, db)

    # Redirect unauthenticated users
    if not current_user:
        raise HTTPException(status_code=401, detail="Authentication required")

    log_request(
        request,
        user_id=str(current_user.id),
        extra_data={"filename": file.filename, "action": action},
    )

    # Temporary file handling
    temp_dir = Path("/tmp/press_uploads")
    temp_dir.mkdir(exist_ok=True)
    temp_file_path = temp_dir / f"{uuid_module.uuid4()}_{file.filename}"

    try:
        # Save uploaded file temporarily
        content = await file.read()
        with open(temp_file_path, "wb") as f:
            f.write(content)

        # Process HTML upload
        processor = HTMLProcessor()
        success, processed_data, errors = await processor.process_html_upload(
            str(temp_file_path), file.filename, str(current_user.id)
        )

        if not success:
            log_error(
                Exception("HTML processing failed"),
                request,
                user_id=str(current_user.id),
                context="html_upload",
                extra_data={"errors": errors},
            )
            return JSONResponse(
                status_code=422,
                content={
                    "success": False,
                    "errors": errors,
                    "message": "HTML processing failed due to validation errors",
                },
            )

        # Validate subject
        try:
            subject_uuid = uuid_module.UUID(subject_id)
            result = await db.execute(select(Subject).where(Subject.id == subject_uuid))
            subject = result.scalar_one_or_none()
            if not subject:
                raise ValueError("Invalid subject selected")
        except (ValueError, TypeError):
            raise HTTPException(status_code=422, detail="Invalid subject ID format")

        # Process keywords
        keyword_list = []
        if keywords.strip():
            keyword_list = [kw.strip() for kw in keywords.split(",") if kw.strip()]

        # Create scroll with enhanced metadata
        preview = Preview(
            user_id=current_user.id,
            title=title.strip(),
            authors=authors.strip(),
            subject_id=subject.id,
            abstract=abstract.strip(),
            keywords=keyword_list,
            html_content=processed_data["html_content"],
            content_type=processed_data.get("content_type", "html"),
            original_filename=processed_data.get("original_filename"),
            file_size=processed_data.get("file_size"),
            external_resources=processed_data.get("external_resources"),
            validation_status=processed_data.get("validation_status", "approved"),
            sanitization_log=processed_data.get("sanitization_log"),
            status="published",
        )

        preview.publish()
        db.add(preview)
        await db.commit()
        await db.refresh(preview)

        log_preview_event(
            "create_html",
            str(preview.id),
            str(current_user.id),
            request,
            extra_data={
                "title": preview.title,
                "status": "published",
                "file_size": processed_data.get("file_size"),
                "sanitization_count": len(processed_data.get("sanitization_log", [])),
            },
        )

        # If publishing directly, publish the scroll
        if action == "publish":
            preview.publish()
            await db.commit()
            log_preview_event(
                "publish_html",
                preview.preview_id,
                str(current_user.id),
                request,
                extra_data={"title": preview.title},
            )

        # Prepare response
        response_data = {
            "success": True,
            "preview_id": str(preview.id),
            "preview_public_id": preview.preview_id if action == "publish" else None,
            "title": preview.title,
            "status": preview.status,
            "validation_status": preview.validation_status,
            "content_metrics": processed_data.get("content_metrics", {}),
            "sanitization_log": processed_data.get("sanitization_log", []),
            "warnings": [e for e in errors if e.get("severity") == "warning"],
            "message": "Scroll published successfully",
        }

        response_data["preview_url"] = f"/scroll/{preview.preview_id}"

        return JSONResponse(content=response_data)

    except Exception as e:
        log_error(e, request, user_id=str(current_user.id), context="html_upload")
        raise HTTPException(status_code=500, detail=f"Upload processing failed: {str(e)}")

    finally:
        if temp_file_path.exists():
            temp_file_path.unlink()
