"""Scroll upload and management routes."""

import asyncio
import os
from pathlib import Path
import uuid as uuid_module

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
import sentry_sdk
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth.session import get_current_user_from_session
from app.config import get_base_url
from app.database import get_db
from app.integrations.doi_service import mint_doi_safe
from app.logging_config import get_logger, log_error, log_preview_event, log_request
from app.models.scroll import Scroll, Subject
from app.templates_config import templates
from app.upload import HTMLProcessor

router = APIRouter()


@router.get("/preview/{url_hash}", response_class=HTMLResponse)
async def view_preview(request: Request, url_hash: str, db: AsyncSession = Depends(get_db)):
    """Display preview of scroll before publishing.

    Only the owner can view their preview. Shows the scroll exactly as it would
    appear when published, with options to confirm publication or cancel.
    """
    current_user = await get_current_user_from_session(request, db)

    if not current_user:
        return RedirectResponse(url="/login", status_code=302)

    log_request(request, user_id=str(current_user.id), extra_data={"url_hash": url_hash})

    # Find preview scroll by url_hash
    result = await db.execute(
        select(Scroll)
        .options(selectinload(Scroll.subject))
        .where(
            Scroll.url_hash == url_hash,
            Scroll.status == "preview",
        )
    )
    scroll = result.scalar_one_or_none()

    if not scroll:
        get_logger().warning(f"Preview not found: {url_hash}")
        return templates.TemplateResponse(
            request, "404.html", {"message": "Preview not found"}, status_code=404
        )

    # Verify ownership
    if scroll.user_id != current_user.id:
        get_logger().warning(
            f"User {current_user.id} attempted to view preview {url_hash} owned by {scroll.user_id}"
        )
        return templates.TemplateResponse(
            request, "404.html", {"message": "Preview not found"}, status_code=404
        )

    # Get CSRF token for forms
    from app.auth.csrf import get_csrf_token

    session_id = request.cookies.get("session_id")
    csrf_token = await get_csrf_token(session_id)

    return templates.TemplateResponse(
        request,
        "preview.html",
        {"scroll": scroll, "current_user": current_user, "csrf_token": csrf_token},
    )


@router.post("/preview/{url_hash}/confirm", response_class=HTMLResponse)
async def confirm_preview(request: Request, url_hash: str, db: AsyncSession = Depends(get_db)):
    """Confirm and publish a preview scroll.

    Publishes the scroll, sets published timestamp, and initiates DOI minting.
    Only the owner can confirm their preview.
    """
    current_user = await get_current_user_from_session(request, db)

    if not current_user:
        return RedirectResponse(url="/login", status_code=302)

    log_request(
        request,
        user_id=str(current_user.id),
        extra_data={"url_hash": url_hash, "action": "confirm"},
    )

    # Find preview scroll
    result = await db.execute(
        select(Scroll)
        .options(selectinload(Scroll.subject))
        .where(
            Scroll.url_hash == url_hash,
            Scroll.status == "preview",
        )
    )
    scroll = result.scalar_one_or_none()

    if not scroll:
        raise HTTPException(status_code=404, detail="Preview not found")

    # Verify ownership
    if scroll.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to publish this preview")

    # Publish the scroll
    scroll.publish()
    await db.commit()

    log_preview_event(
        "publish",
        scroll.url_hash,
        str(current_user.id),
        request,
        extra_data={"title": scroll.title, "doi_status": "pending"},
    )

    # Start background task for DOI minting
    asyncio.create_task(mint_doi_safe(str(scroll.id)))

    # Redirect to published scroll
    return RedirectResponse(url=f"/scroll/{scroll.url_hash}", status_code=303)


@router.post("/preview/{url_hash}/cancel", response_class=HTMLResponse)
async def cancel_preview(request: Request, url_hash: str, db: AsyncSession = Depends(get_db)):
    """Cancel and delete a preview scroll.

    Removes the preview from the database. Only the owner can cancel their preview.
    """
    current_user = await get_current_user_from_session(request, db)

    if not current_user:
        return RedirectResponse(url="/login", status_code=302)

    log_request(
        request,
        user_id=str(current_user.id),
        extra_data={"url_hash": url_hash, "action": "cancel"},
    )

    # Find preview scroll
    result = await db.execute(
        select(Scroll).where(
            Scroll.url_hash == url_hash,
            Scroll.status == "preview",
        )
    )
    scroll = result.scalar_one_or_none()

    if not scroll:
        raise HTTPException(status_code=404, detail="Preview not found")

    # Verify ownership
    if scroll.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to cancel this preview")

    # Delete the preview
    await db.delete(scroll)
    await db.commit()

    log_preview_event(
        "cancel_preview",
        url_hash,
        str(current_user.id),
        request,
        extra_data={"title": scroll.title},
    )

    # Redirect to upload page
    return RedirectResponse(url="/upload", status_code=303)


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

    return templates.TemplateResponse(
        request, "scroll.html", {"scroll": scroll, "base_url": get_base_url()}
    )


@router.get("/scroll/{url_hash}/paper")
async def get_paper_html(
    request: Request,
    url_hash: str,
    db: AsyncSession = Depends(get_db),
):
    """Serve paper HTML for iframe embedding.

    Returns raw HTML content of a published paper for iframe rendering.
    For preview scrolls, only the owner can view.
    This route provides complete CSS/JS isolation from the parent Press page.

    Security headers:
    - X-Frame-Options: SAMEORIGIN (prevent external embedding)
    - frame-ancestors 'self' (CSP equivalent)
    """
    sentry_sdk.set_tag("operation", "paper_view")
    sentry_sdk.set_context("paper", {"url_hash": url_hash})

    # Find scroll by content-addressable hash (published or preview)
    result = await db.execute(select(Scroll).where(Scroll.url_hash == url_hash))
    scroll = result.scalar_one_or_none()

    if not scroll:
        raise HTTPException(status_code=404, detail="Paper not found")

    # If preview, verify ownership
    if scroll.status == "preview":
        current_user = await get_current_user_from_session(request, db)
        if not current_user or scroll.user_id != current_user.id:
            raise HTTPException(status_code=404, detail="Paper not found")

    # Set security headers for iframe embedding
    headers = {
        "X-Frame-Options": "SAMEORIGIN",
        "Content-Security-Policy": (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' data: https://cdn.jsdelivr.net https://cdnjs.cloudflare.com https://cdn.plot.ly https://unpkg.com; "
            "style-src 'self' 'unsafe-inline' data: https://cdn.jsdelivr.net https://cdnjs.cloudflare.com https://fonts.googleapis.com; "
            "img-src 'self' data: https:; "
            "font-src 'self' data: https://cdn.jsdelivr.net https://cdnjs.cloudflare.com https://fonts.gstatic.com; "
            "frame-ancestors 'self';"
        ),
    }

    return Response(
        content=scroll.html_content,
        media_type="text/html",
        headers=headers,
    )


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

    # Clean up any abandoned previews from this user
    # (User closed window/lost session without confirming or canceling)
    try:
        abandoned_previews = await db.execute(
            select(Scroll).where(Scroll.user_id == current_user.id, Scroll.status == "preview")
        )
        abandoned = abandoned_previews.scalars().all()
        if abandoned:
            for preview in abandoned:
                await db.delete(preview)
            await db.commit()
            get_logger().info(
                f"Cleaned up {len(abandoned)} abandoned preview(s) for user {current_user.id}"
            )
    except Exception as e:
        get_logger().error(f"Failed to clean up abandoned previews: {e}")
        await db.rollback()

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

    # Get CSRF token for form
    from app.auth.csrf import get_csrf_token

    session_id = request.cookies.get("session_id")
    csrf_token = await get_csrf_token(session_id)

    return templates.TemplateResponse(
        request,
        "upload.html",
        {"current_user": current_user, "subjects": subjects, "csrf_token": csrf_token},
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
        # PROFILING: Track memory usage
        import os

        import psutil

        process = psutil.Process(os.getpid())
        mem_start = process.memory_info().rss / 1024 / 1024
        print(f"[MEMORY PROFILE] Upload start: {mem_start:.1f} MB")

        sentry_sdk.set_tag("operation", "scroll_upload")
        sentry_sdk.set_user({"id": str(current_user.id)})
        sentry_sdk.set_context(
            "upload", {"title": title, "subject_id": subject_id, "license": license}
        )
        # Strip inputs once to avoid creating multiple copies in memory
        html_content = html_content.strip() if html_content else ""
        title = title.strip() if title else ""
        authors = authors.strip() if authors else ""
        abstract = abstract.strip() if abstract else ""

        # Validate required fields
        if not title:
            raise ValueError("Title is required")
        if not authors:
            raise ValueError("Authors are required")
        if not abstract:
            raise ValueError("Abstract is required")
        if not html_content:
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
        is_html_safe, html_errors = html_validator.validate(html_content)

        # PROFILING: Memory after validation
        mem_after_validation = process.memory_info().rss / 1024 / 1024
        print(
            f"[MEMORY PROFILE] After validation: {mem_after_validation:.1f} MB (delta: {mem_after_validation - mem_start:.1f} MB)"
        )

        if not is_html_safe:
            # Group and summarize errors for better readability
            from collections import defaultdict
            import re

            grouped_errors = defaultdict(list)
            for error in html_errors:
                grouped_errors[error.get("type", "other")].append(error)

            error_parts = []

            # Forbidden tags - show unique tags with counts
            if "forbidden_tag" in grouped_errors:
                tag_counts = defaultdict(int)
                for err in grouped_errors["forbidden_tag"]:
                    # Extract tag name from message like "Forbidden tag <input> is not allowed"
                    match = re.search(r"<(\w+)>", err["message"])
                    if match:
                        tag_counts[match.group(1)] += 1

                tag_list = ", ".join(
                    f"<{tag}>" + (f" ({count}x)" if count > 1 else "")
                    for tag, count in sorted(tag_counts.items())
                )
                error_parts.append(f"Forbidden tags found: {tag_list}")

            # Forbidden attributes - show unique attributes with examples
            if "forbidden_attribute" in grouped_errors:
                attr_examples = {}
                for err in grouped_errors["forbidden_attribute"]:
                    # Extract attribute name from message
                    match = re.search(r"'(\w+)'", err["message"])
                    if match:
                        attr_name = match.group(1)
                        if attr_name not in attr_examples:
                            attr_examples[attr_name] = err.get("line_number")

                attr_list = ", ".join(
                    f"'{attr}'" + (f" (line {line})" if line else "")
                    for attr, line in sorted(attr_examples.items())
                )
                error_parts.append(
                    f"Forbidden attributes found: {attr_list}. Remove event handlers and use JavaScript instead."
                )

            # Dangerous CSS - show brief summary
            if "dangerous_css" in grouped_errors or "css_expression" in grouped_errors:
                css_errors = grouped_errors["dangerous_css"] + grouped_errors.get(
                    "css_expression", []
                )
                example_line = css_errors[0].get("line_number")
                line_info = f" (line {example_line})" if example_line else ""
                error_parts.append(
                    f"Dangerous CSS properties found{line_info}. Remove CSS with JavaScript or executable code."
                )

            # External resources - group by type and show resource names
            external_scripts = []
            external_stylesheets = []
            if "external_script" in grouped_errors:
                for err in grouped_errors["external_script"]:
                    # Extract URL from message
                    match = re.search(r"'([^']+)'", err["message"])
                    if match:
                        url = match.group(1)
                        # Extract just the library name from CDN URL
                        lib_name = url.split("/")[-1] if "/" in url else url
                        external_scripts.append(lib_name)

            if "external_stylesheet" in grouped_errors:
                for err in grouped_errors["external_stylesheet"]:
                    match = re.search(r"'([^']+)'", err["message"])
                    if match:
                        url = match.group(1)
                        lib_name = url.split("/")[-1] if "/" in url else url
                        external_stylesheets.append(lib_name)

            if external_scripts or external_stylesheets:
                resources = []
                if external_scripts:
                    resources.append(f"scripts: {', '.join(external_scripts[:3])}")
                if external_stylesheets:
                    resources.append(f"stylesheets: {', '.join(external_stylesheets[:3])}")

                error_parts.append(
                    f"External resources must be embedded: {'; '.join(resources)}. "
                    f"Download and inline these resources. (MathJax/KaTeX CDNs are allowed)"
                )

            # Meta tags
            if "forbidden_meta" in grouped_errors or "dangerous_meta" in grouped_errors:
                meta_count = len(grouped_errors.get("forbidden_meta", [])) + len(
                    grouped_errors.get("dangerous_meta", [])
                )
                error_parts.append(
                    f"Forbidden meta tags found ({meta_count}). Only standard meta tags like author, description, viewport are allowed."
                )

            # JavaScript URLs and dangerous protocols
            if "javascript_url" in grouped_errors or "dangerous_protocol" in grouped_errors:
                error_parts.append(
                    "JavaScript or dangerous URLs found. Remove javascript:, vbscript:, or data:text/html URLs."
                )

            # Format final message with HTML for better rendering
            if error_parts:
                import html

                # HTML-escape the error parts to prevent tag names from rendering as actual HTML
                escaped_parts = [html.escape(part) for part in error_parts]
                error_items = "".join(f"<li>{part}</li>" for part in escaped_parts)
                error_summary = (
                    f"<strong>Your HTML contains security issues that must be fixed:</strong>"
                    f"<ul style='margin-top: 0.5rem; margin-bottom: 0;'>{error_items}</ul>"
                )
            else:
                # Fallback if we can't parse errors
                error_summary = (
                    f"Your HTML contains {len(html_errors)} security issues. "
                    "Please review your HTML for forbidden tags, attributes, or external resources."
                )

            raise ValueError(error_summary)

        # Generate content-addressable storage fields
        from app.storage.content_processing import generate_permanent_url

        url_hash, content_hash, tar_data = await generate_permanent_url(html_content)

        # PROFILING: Memory after generate_permanent_url
        mem_after_url_gen = process.memory_info().rss / 1024 / 1024
        print(
            f"[MEMORY PROFILE] After generate_permanent_url: {mem_after_url_gen:.1f} MB (delta: {mem_after_url_gen - mem_after_validation:.1f} MB)"
        )

        # Check if content already exists (published or preview)
        existing_scroll = await db.execute(select(Scroll).where(Scroll.url_hash == url_hash))
        existing = existing_scroll.scalar_one_or_none()
        if existing:
            if existing.status == "published":
                raise ValueError(
                    "This content has already been published. Each scroll must have unique content."
                )
            else:
                # There's an abandoned preview with the same content
                raise ValueError(
                    "A preview with identical content already exists. Please cancel or confirm the existing preview before uploading again, or modify your content to make it unique."
                )

        # Create scroll with preview status (not yet published)
        scroll = Scroll(
            user_id=current_user.id,
            title=title,
            authors=authors,
            subject_id=subject.id,
            abstract=abstract,
            keywords=keyword_list,
            html_content=html_content,
            license=license,
            content_hash=content_hash,
            url_hash=url_hash,
            status="preview",
        )

        db.add(scroll)

        # PROFILING: Memory before commit
        mem_before_commit = process.memory_info().rss / 1024 / 1024
        print(
            f"[MEMORY PROFILE] Before DB commit: {mem_before_commit:.1f} MB (delta: {mem_before_commit - mem_after_url_gen:.1f} MB)"
        )
        print(f"[MEMORY PROFILE] TOTAL increase: {mem_before_commit - mem_start:.1f} MB")

        await db.commit()
        await db.refresh(scroll)

        # Load the subject relationship for preview display
        result = await db.execute(
            select(Scroll).options(selectinload(Scroll.subject)).where(Scroll.id == scroll.id)
        )
        scroll = result.scalar_one()

        log_preview_event(
            "create_preview",
            str(scroll.id),
            str(current_user.id),
            request,
            extra_data={"title": scroll.title, "status": "preview", "url_hash": scroll.url_hash},
        )

        # Get CSRF token for preview page forms
        from app.auth.csrf import get_csrf_token

        session_id = request.cookies.get("session_id")
        csrf_token = await get_csrf_token(session_id)

        # Return preview page for user to review before publishing
        return templates.TemplateResponse(
            request,
            "preview.html",
            {
                "scroll": scroll,
                "current_user": current_user,
                "csrf_token": csrf_token,
            },
        )

    except Exception as e:
        error_message = str(e) if str(e) else "Upload failed. Please try again."
        # Store user attributes before rollback to avoid lazy-load issues
        user_id_value = current_user.id if current_user else None
        user_id = str(user_id_value) if user_id_value else None
        user_display_name = current_user.display_name if current_user else None
        user_email = current_user.email if current_user else None

        # Rollback the session to clear any pending transactions
        await db.rollback()

        log_error(e, request, user_id=user_id, context="preview_upload")

        # Create a simple dict for current_user to avoid session state issues
        user_context = None
        if user_id_value:
            user_context = type(
                "User",
                (),
                {"id": user_id_value, "display_name": user_display_name, "email": user_email},
            )()

        # Load subjects for error response - convert to dicts to avoid session state issues
        try:
            result = await db.execute(select(Subject).order_by(Subject.name))
            subject_rows = result.scalars().all()
            # Convert to simple dicts to avoid detached object issues
            subjects = [{"id": s.id, "name": s.name} for s in subject_rows]
        except Exception as subject_error:
            get_logger().error(f"Failed to load subjects in error handler: {subject_error}")
            subjects = []

        # Get CSRF token for error response
        from app.auth.csrf import get_csrf_token

        session_id = request.cookies.get("session_id")
        csrf_token = await get_csrf_token(session_id) if session_id else None

        # Return form partial with error (not full page)
        return templates.TemplateResponse(
            request,
            "partials/upload_form.html",
            {
                "current_user": user_context,
                "subjects": subjects,
                "error": error_message,
                "csrf_token": csrf_token,
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
                extra_data={"title": scroll.title, "doi_status": "pending"},
            )

            # Start background task for DOI minting
            asyncio.create_task(mint_doi_safe(str(scroll.id)))

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

        # Convert to string and validate size
        content_str = content_bytes.decode("utf-8")
        max_size = int(os.getenv("HTML_UPLOAD_MAX_SIZE", 52428800))  # 50MB default
        if len(content_bytes) > max_size:
            max_mb = max_size / 1024 / 1024
            raise HTTPException(status_code=422, detail=f"File size cannot exceed {max_mb:.0f}MB")

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
