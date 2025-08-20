"""Scroll upload and management routes."""

from pathlib import Path
import re
import uuid as uuid_module

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
import sentry_sdk
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth.session import get_current_user_from_session
from app.database import get_db
from app.logging_config import get_logger, log_error, log_preview_event, log_request
from app.models.scroll import Scroll, Subject
from app.templates_config import templates
from app.upload import HTMLProcessor

router = APIRouter()


@router.get("/scroll/{identifier}", response_class=HTMLResponse)
async def view_scroll(request: Request, identifier: str, db: AsyncSession = Depends(get_db)):
    """Display a published scroll by its identifier.

    Shows the full HTML content of a published research scroll. Supports both:
    - Legacy preview_id format (backward compatibility)
    - Content-addressable hash format (new permanent URLs)

    Only published scrolls are accessible to the public.
    """
    sentry_sdk.set_tag("operation", "scroll_view")
    sentry_sdk.set_context("scroll", {"identifier": identifier})
    log_request(request, extra_data={"identifier": identifier})

    # Find scroll by content-addressable hash only (no legacy preview_id support)
    result = await db.execute(
        select(Scroll)
        .options(selectinload(Scroll.subject))
        .where(
            Scroll.url_hash == identifier,
            Scroll.status == "published",
        )
    )
    scroll = result.scalar_one_or_none()

    if not scroll:
        get_logger().warning(f"Scroll not found: {identifier}")
        return templates.TemplateResponse(
            request, "404.html", {"message": "Scroll not found"}, status_code=404
        )

    log_preview_event(
        "view",
        identifier,
        str(scroll.user_id) if scroll.user_id else None,
        request,
        extra_data={"title": scroll.title, "url_hash": scroll.url_hash},
    )

    # Check if HTML content has CSS
    has_css = bool(
        re.search(r"<style|<link[^>]*stylesheet|style\s*=", scroll.html_content, re.IGNORECASE)
    )

    # If no CSS detected, inject basic styles
    if not has_css:
        basic_css = """
        <style>
            /* Base styles for injected scroll content */
            .injected-scroll-content {
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Roboto', 'Helvetica Neue', Arial, sans-serif;
                line-height: 1.6;
                max-width: 800px;
                margin: 0 auto;
                padding: 2rem;
            }
            .injected-scroll-content h1, 
            .injected-scroll-content h2, 
            .injected-scroll-content h3, 
            .injected-scroll-content h4, 
            .injected-scroll-content h5, 
            .injected-scroll-content h6 {
                font-family: Georgia, serif;
                margin: 1.5rem 0 1rem 0;
                font-weight: normal;
            }
            .injected-scroll-content h1 { font-size: 2rem; }
            .injected-scroll-content h2 { font-size: 1.5rem; }
            .injected-scroll-content h3 { font-size: 1.25rem; }
            .injected-scroll-content h4 { font-size: 1.1rem; }
            .injected-scroll-content h5 { font-size: 1rem; }
            .injected-scroll-content h6 { font-size: 0.9rem; }
            .injected-scroll-content p { 
                margin: 1rem 0; 
            }
            .injected-scroll-content code {
                background: var(--gray-bg);
                padding: 0.2rem 0.4rem;
                border-radius: 3px;
                font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', monospace;
                font-size: 0.9em;
            }
            .injected-scroll-content pre {
                background: var(--gray-bg);
                padding: 1rem;
                border-radius: 5px;
                overflow-x: auto;
            }
            .injected-scroll-content blockquote {
                border-left: 4px solid var(--red);
                padding-left: 1rem;
                margin: 1rem 0;
                font-style: italic;
                color: var(--gray);
            }
        </style>
        """

        # Wrap content in a styled container and inject CSS
        wrapped_content = f"""
        {basic_css}
        <div class="injected-scroll-content">
            {scroll.html_content}
        </div>
        """
        scroll.html_content = wrapped_content

    return templates.TemplateResponse(request, "scroll.html", {"scroll": scroll})


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
    get_logger().info("Loading subjects for upload form...")
    try:
        result = await db.execute(select(Subject).order_by(Subject.name))
        subjects = result.scalars().all()
        subject_count = len(subjects)
        get_logger().info(f"Loaded {subject_count} subjects for upload form")

        if subject_count > 0:
            subject_names = [s.name for s in subjects[:3]]  # First 3
            get_logger().info(f"Subject names: {subject_names}")
        else:
            get_logger().warning("⚠️  No subjects found when loading upload form")
            # Create default subjects for testing
            get_logger().info("Creating default subjects for testing...")
            try:
                default_subjects = [
                    Subject(name="Computer Science", description="Computing and algorithms"),
                    Subject(name="Physics", description="Theoretical and experimental physics"),
                    Subject(name="Mathematics", description="Pure and applied mathematics"),
                ]
                for subject in default_subjects:
                    db.add(subject)
                await db.commit()

                # Reload subjects
                result = await db.execute(select(Subject).order_by(Subject.name))
                subjects = result.scalars().all()
                get_logger().info(f"Created {len(default_subjects)} default subjects")
            except Exception as create_error:
                get_logger().error(f"Failed to create default subjects: {create_error}")
                subjects = []

    except Exception as e:
        get_logger().error(f"❌ Failed to load subjects: {e}")
        subjects = []  # Fallback to empty list

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
    license: str = Form(...),
    confirm_rights: str = Form(None),
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
        sentry_sdk.set_tag("operation", "scroll_upload")
        sentry_sdk.set_user({"id": str(current_user.id)})
        sentry_sdk.set_context(
            "upload", {"title": title, "subject_id": subject_id, "license": license}
        )
        # Validate required fields
        if not title or not title.strip():
            raise ValueError("Title is required")
        if not authors or not authors.strip():
            raise ValueError("Authors are required")
        if not abstract or not abstract.strip():
            raise ValueError("Abstract is required")
        if not html_content or not html_content.strip():
            raise ValueError("HTML content is required")
        if not license or license not in ["cc-by-4.0", "arr"]:
            raise ValueError("License must be selected (CC BY 4.0 or All Rights Reserved)")
        if not confirm_rights or confirm_rights.lower() != "true":
            raise ValueError("You must confirm that you have the right to publish this content")

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

        # Validate HTML content for security - REJECT if dangerous content found
        from app.security.html_validator import HTMLValidator

        html_validator = HTMLValidator()
        is_html_safe, html_errors = html_validator.validate(html_content.strip())

        if not is_html_safe:
            # Format errors for user display as bulleted list
            error_messages = []
            for error in html_errors:
                if error.get("line_number"):
                    error_messages.append(f"• Line {error['line_number']}: {error['message']}")
                else:
                    error_messages.append(f"• {error['message']}")

            error_summary = (
                "Your HTML contains content that is not allowed for security reasons:\n\n"
                + "\n".join(error_messages)
            )
            raise ValueError(error_summary)

        # Generate content-addressable storage fields
        from app.storage.content_processing import generate_permanent_url

        url_hash, content_hash, tar_data = await generate_permanent_url(html_content.strip())

        # Create scroll with content-addressable storage
        scroll = Scroll(
            user_id=current_user.id,
            title=title.strip(),
            authors=authors.strip(),
            subject_id=subject.id,
            abstract=abstract.strip(),
            keywords=keyword_list,
            html_content=html_content.strip(),
            license=license,
            content_hash=content_hash,
            url_hash=url_hash,
            status="published",
        )
        scroll.publish()

        db.add(scroll)
        await db.commit()
        await db.refresh(scroll)

        log_preview_event(
            "create",
            str(scroll.id),
            str(current_user.id),
            request,
            extra_data={"title": scroll.title, "status": "published"},
        )

        # If publishing directly, publish the scroll after it's in the database
        if action == "publish":
            # Load the subject relationship before publishing
            result = await db.execute(
                select(Scroll).options(selectinload(Scroll.subject)).where(Scroll.id == scroll.id)
            )
            scroll = result.scalar_one()
            scroll.publish()
            await db.commit()  # Commit the publish changes
            log_preview_event(
                "publish",
                scroll.url_hash,
                str(current_user.id),
                request,
                extra_data={"title": scroll.title},
            )

        # Return success response - just the content for HTMX
        success_message = "Your scroll has been published successfully!"
        preview_url = f"/scroll/{scroll.url_hash}"

        # Return success response using proper template
        return templates.TemplateResponse(
            request,
            "upload_success.html",
            {
                "scroll": scroll,
                "preview_url": preview_url,
                "success_message": success_message,
            },
        )

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
                    "license": license,
                    "confirm_rights": confirm_rights,
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
    license: str = Form(...),
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

        # Validate license
        if not license or license not in ["cc-by-4.0", "arr"]:
            raise HTTPException(
                status_code=422,
                detail="License must be selected (CC BY 4.0 or All Rights Reserved)",
            )

        # Create scroll with enhanced metadata
        scroll = Scroll(
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
            license=license,
            status="published",
        )

        scroll.publish()
        db.add(scroll)
        await db.commit()
        await db.refresh(scroll)

        log_preview_event(
            "create_html",
            str(scroll.id),
            str(current_user.id),
            request,
            extra_data={
                "title": scroll.title,
                "status": "published",
                "file_size": processed_data.get("file_size"),
                "sanitization_count": len(processed_data.get("sanitization_log", [])),
            },
        )

        # If publishing directly, publish the scroll
        if action == "publish":
            scroll.publish()
            await db.commit()
            log_preview_event(
                "publish_html",
                scroll.preview_id,
                str(current_user.id),
                request,
                extra_data={"title": scroll.title},
            )

        # Prepare response
        response_data = {
            "success": True,
            "preview_id": str(scroll.id),
            "preview_public_id": scroll.preview_id if action == "publish" else None,
            "title": scroll.title,
            "status": scroll.status,
            "validation_status": scroll.validation_status,
            "content_metrics": processed_data.get("content_metrics", {}),
            "sanitization_log": processed_data.get("sanitization_log", []),
            "warnings": [e for e in errors if e.get("severity") == "warning"],
            "message": "Scroll published successfully",
        }

        response_data["preview_url"] = f"/scroll/{scroll.preview_id}"

        return JSONResponse(content=response_data)

    except Exception as e:
        log_error(e, request, user_id=str(current_user.id), context="html_upload")
        raise HTTPException(status_code=500, detail=f"Upload processing failed: {str(e)}")

    finally:
        if temp_file_path.exists():
            temp_file_path.unlink()


@router.post("/upload")
async def upload_content_addressable(
    request: Request,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    """
    Upload HTML content with content-addressable storage.

    MVP implementation that accepts single HTML files and returns permanent URLs
    based on cryptographic hashes of the content.

    Args:
        request: HTTP request object
        file: Uploaded HTML file (enforced UTF-8 encoding)
        db: Database session

    Returns:
        JSONResponse with permanent URL and content hash

    Raises:
        HTTPException: For validation errors, encoding issues, or processing failures
    """
    from app.storage.content_processing import (
        generate_permanent_url,
        validate_utf8_content,
    )

    log_request(request, extra_data={"filename": file.filename})

    try:
        # Validate file type
        if not file.filename or not file.filename.lower().endswith(".html"):
            raise HTTPException(status_code=422, detail="Only HTML files are accepted")

        # Read file content
        content_bytes = await file.read()

        # Enforce UTF-8 validation
        if not validate_utf8_content(content_bytes):
            raise HTTPException(status_code=422, detail="File content must be UTF-8 encoded")

        # Convert to string and validate size (5MB limit)
        content_str = content_bytes.decode("utf-8")
        if len(content_bytes) > 5 * 1024 * 1024:  # 5MB
            raise HTTPException(status_code=422, detail="File size cannot exceed 5MB")

        # Validate content is not empty
        if not content_str.strip():
            raise HTTPException(status_code=422, detail="File content cannot be empty")

        # Generate permanent URL using content-addressable storage
        url_hash, content_hash, tar_data = await generate_permanent_url(content_str)

        # Check if content already exists
        result = await db.execute(select(Scroll).where(Scroll.content_hash == content_hash))
        existing_scroll = result.scalar_one_or_none()

        if existing_scroll:
            # Content already exists, return existing URL
            return JSONResponse(
                content={
                    "success": True,
                    "permanent_url": f"/scroll/{existing_scroll.url_hash}",
                    "url_hash": existing_scroll.url_hash,
                    "content_hash": content_hash,
                    "exists": True,
                    "message": "Content already exists with permanent URL",
                }
            )

        # Create new scroll with content-addressable storage
        scroll = Scroll(
            content_hash=content_hash,
            url_hash=url_hash,
            title=f"Content {url_hash[:8]}",  # Temporary title for MVP
            authors="Anonymous",  # Default for MVP
            abstract="Content uploaded via content-addressable storage",  # Default for MVP
            html_content=content_str,
            content_type="html",
            original_filename=file.filename,
            file_size=len(content_bytes),
            license="arr",  # Default license for MVP
            status="published",
            # Set a default subject for MVP - we'll need to handle this properly
            subject_id=(await db.execute(select(Subject).limit(1))).scalar_one().id,
        )

        db.add(scroll)
        await db.commit()
        await db.refresh(scroll)

        log_preview_event(
            "create_content_addressable",
            url_hash,
            None,  # No user for MVP
            request,
            extra_data={
                "content_hash": content_hash,
                "file_size": len(content_bytes),
                "filename": file.filename,
            },
        )

        return JSONResponse(
            content={
                "success": True,
                "permanent_url": f"/scroll/{url_hash}",
                "url_hash": url_hash,
                "content_hash": content_hash,
                "exists": False,
                "message": "Content uploaded successfully with permanent URL",
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        log_error(e, request, context="content_addressable_upload")
        raise HTTPException(status_code=500, detail=f"Upload processing failed: {str(e)}")


@router.get("/scroll/{identifier}/raw")
async def get_raw_content(request: Request, identifier: str, db: AsyncSession = Depends(get_db)):
    """
    Serve raw tar content for content-addressable stored scrolls.

    Returns the uncompressed tar archive of the original content.
    For MVP with HTML-only content, this recreates the tar from stored HTML.

    Args:
        request: HTTP request object
        identifier: Content hash or legacy preview_id
        db: Database session

    Returns:
        Raw tar content as application/x-tar

    Raises:
        HTTPException: If scroll not found or not content-addressable
    """
    from fastapi.responses import Response

    from app.storage.content_processing import process_html_content

    log_request(request, extra_data={"identifier": identifier, "endpoint": "raw"})

    # Find scroll by content-addressable hash only (no legacy preview_id support)
    result = await db.execute(
        select(Scroll).where(
            Scroll.url_hash == identifier,
            Scroll.status == "published",
        )
    )
    scroll = result.scalar_one_or_none()

    if not scroll:
        raise HTTPException(status_code=404, detail="Scroll not found")

    # For content-addressable scrolls, regenerate tar from stored content
    if scroll.url_hash:
        try:
            # Process the stored HTML content to create tar
            normalized_content, tar_data = process_html_content(scroll.html_content)

            log_preview_event(
                "view_raw",
                identifier,
                str(scroll.user_id) if scroll.user_id else None,
                request,
                extra_data={"content_hash": scroll.content_hash},
            )

            return Response(
                content=tar_data,
                media_type="application/x-tar",
                headers={
                    "Content-Disposition": f"attachment; filename=content-{scroll.url_hash}.tar",
                    "Content-Length": str(len(tar_data)),
                },
            )

        except Exception as e:
            log_error(e, request, context="raw_content_generation")
            raise HTTPException(status_code=500, detail="Failed to generate raw content")
    else:
        # Legacy scroll without content-addressable storage
        raise HTTPException(status_code=422, detail="Raw content not available for legacy scrolls")
