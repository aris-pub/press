"""Preview upload and management routes."""

from pathlib import Path
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


@router.get("/preview/{preview_id}", response_class=HTMLResponse)
async def view_preview(request: Request, preview_id: str, db: AsyncSession = Depends(get_db)):
    """Display a published preview by its preview_id.

    Shows the full HTML content of a published research scroll. Only published
    previews are accessible to the public.

    """
    log_request(request, extra_data={"preview_id": preview_id})

    result = await db.execute(
        select(Preview)
        .options(selectinload(Preview.subject))
        .where(Preview.preview_id == preview_id, Preview.status == "published")
    )
    preview = result.scalar_one_or_none()

    if not preview:
        get_logger().warning(f"Preview not found: {preview_id}")
        return templates.TemplateResponse(
            request, "404.html", {"message": "Preview not found"}, status_code=404
        )

    log_preview_event(
        "view", preview_id, str(preview.user_id), request, extra_data={"title": preview.title}
    )
    return templates.TemplateResponse(request, "preview.html", {"preview": preview})


@router.get("/upload", response_class=HTMLResponse)
async def upload_page(request: Request, db: AsyncSession = Depends(get_db)):
    """Display the HTML preview upload page.

    Shows the upload form for authenticated users to submit their HTML research
    previews. Unauthenticated users are redirected to login. Loads available
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
    action: str = Form("draft"),  # "draft" or "publish"
    db: AsyncSession = Depends(get_db),
):
    """Process HTML preview upload form submission.

    Validates and processes the upload of HTML research scrolls. Supports both
    draft saving and direct publishing. Uses HTMX for seamless form submission
    with success/error feedback.

    Args:
        request: The HTTP request object for HTMX responses
        title: The preview title (required)
        authors: Comma-separated author names (required)
        subject_id: UUID of the academic subject (required)
        abstract: Research abstract/summary (required)
        keywords: Comma-separated keywords (optional)
        html_content: Complete HTML document content (required)
        action: Either "draft" to save or "publish" to make public
        db: Database session dependency for preview operations

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

        # Create preview
        preview = Preview(
            user_id=current_user.id,
            title=title.strip(),
            authors=authors.strip(),
            subject_id=subject.id,
            abstract=abstract.strip(),
            keywords=keyword_list,
            html_content=html_content.strip(),
            status="draft",
        )

        db.add(preview)
        await db.commit()
        await db.refresh(preview)

        log_preview_event(
            "create",
            str(preview.id),
            str(current_user.id),
            request,
            extra_data={"title": preview.title, "status": "draft"},
        )

        # If publishing directly, publish the preview after it's in the database
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
        if action == "publish":
            success_message = "Your preview has been published successfully!"
            preview_url = f"/preview/{preview.preview_id}"
        else:
            success_message = f"Draft '{preview.title}' has been saved successfully!"
            preview_url = f"/preview/{preview.id}/edit"

        # Return just the success content (not full page) for HTMX
        success_html = f"""
        <div class="success-container" style="max-width: 600px; margin: 4rem auto; padding: 3rem; background: #f0fdf4; border: 1px solid #bbf7d0; border-radius: 4px; text-align: center;">
            <h1 style="color: #15803d; margin-bottom: 1rem;">✅ Success!</h1>
            <p style="color: #166534; font-size: 1.1rem; margin-bottom: 2rem;">{success_message}</p>

            <div style="margin-bottom: 2rem;">
                <p><strong>Title:</strong> {preview.title}</p>
                <p><strong>Status:</strong> {"Published" if action == "publish" else "Draft"}</p>
                {"<p><strong>Preview ID:</strong> " + preview.preview_id + "</p>" if action == "publish" else ""}
            </div>

            <div style="display: flex; gap: 1rem; justify-content: center;">
                <a href="{preview_url}" class="btn btn-primary">View Preview</a>
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


@router.post("/preview/{preview_id}/publish", response_class=HTMLResponse)
async def publish_preview(request: Request, preview_id: str, db: AsyncSession = Depends(get_db)):
    """Publish a draft preview to make it publicly accessible.

    Converts a draft preview to published status, generating a unique preview ID
    and making it discoverable. Only the preview owner can publish their drafts.

    Args:
        request: The HTTP request object for template responses
        preview_id: UUID string of the draft preview to publish
        db: Database session dependency for preview operations

    Returns:
        HTMLResponse: Success page with preview details or error page

    Raises:
        ValueError: For invalid preview ID, access denied, or non-draft previews
        Exception: For database or unexpected errors during publishing

    """
    current_user = await get_current_user_from_session(request, db)

    # Redirect unauthenticated users
    if not current_user:
        return RedirectResponse(url="/login", status_code=302)

    log_request(request, user_id=str(current_user.id), extra_data={"preview_id": preview_id})

    try:
        # Find the preview and verify ownership
        preview_uuid = uuid_module.UUID(preview_id)
        result = await db.execute(
            select(Preview).where(Preview.id == preview_uuid, Preview.user_id == current_user.id)
        )
        preview = result.scalar_one_or_none()

        if not preview:
            raise ValueError("Preview not found or access denied")

        if preview.status != "draft":
            raise ValueError("Only draft previews can be published")

        # Publish the preview
        preview.publish()
        await db.commit()
        await db.refresh(preview)

        log_preview_event(
            "publish",
            preview.preview_id,
            str(current_user.id),
            request,
            extra_data={"title": preview.title},
        )

        return templates.TemplateResponse(
            request,
            "upload_success.html",
            {
                "current_user": current_user,
                "preview": preview,
                "success_message": f"Preview '{preview.title}' has been published successfully!",
                "preview_url": f"/preview/{preview.preview_id}",
                "is_published": True,
            },
        )

    except Exception as e:
        error_message = str(e) if str(e) else "Failed to publish preview."
        log_error(e, request, user_id=str(current_user.id), context="preview_publish")

        # Return error response (could be improved with a proper error template)
        return templates.TemplateResponse(
            request,
            "upload_success.html",
            {
                "current_user": current_user,
                "error": error_message,
                "success_message": "Error occurred while publishing",
                "is_published": False,
            },
            status_code=400,
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
    action: str = Form("draft"),
    db: AsyncSession = Depends(get_db),
):
    """Upload HTML source with enhanced security and sanitization.

    Processes uploaded HTML files through comprehensive security validation,
    sanitization, and content checks before storing in the database.

    Args:
        request: The HTTP request object
        file: The uploaded HTML file
        title: The preview title (required)
        authors: Comma-separated author names (required)
        subject_id: UUID of the academic subject (required)
        abstract: Research abstract/summary (required)
        keywords: Comma-separated keywords (optional)
        action: Either "draft" to save or "publish" to make public
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

        # Create preview with enhanced metadata
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
            status="draft",
        )

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
                "status": "draft",
                "file_size": processed_data.get("file_size"),
                "sanitization_count": len(processed_data.get("sanitization_log", [])),
            },
        )

        # If publishing directly, publish the preview
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
            "message": f"Preview {'published' if action == 'publish' else 'saved as draft'} successfully",
        }

        if action == "publish":
            response_data["preview_url"] = f"/preview/{preview.preview_id}"

        return JSONResponse(content=response_data)

    except Exception as e:
        log_error(e, request, user_id=str(current_user.id), context="html_upload")
        raise HTTPException(status_code=500, detail=f"Upload processing failed: {str(e)}")

    finally:
        if temp_file_path.exists():
            temp_file_path.unlink()
