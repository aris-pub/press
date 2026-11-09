"""Jinja2 template configuration with global context.

This module provides centralized template configuration with access to
request-scoped variables like CSP nonces.
"""

import os

from dotenv import load_dotenv
from fastapi import Request
from fastapi.templating import Jinja2Templates

from app.security.nonce import get_nonce_from_request

load_dotenv()

TURNSTILE_SITE_KEY = os.getenv("TURNSTILE_SITE_KEY", "")
ORCID_ENABLED = bool(os.getenv("ORCID_CLIENT_ID", ""))


class TemplatesWithGlobals(Jinja2Templates):
    """Extended Jinja2Templates with automatic global context injection."""

    def TemplateResponse(self, request: Request, name: str, context: dict = None, **kwargs):
        """Create template response with automatic global context.

        Automatically injects request-scoped variables like nonce into
        the template context so they're available to all templates.

        Args:
            request: FastAPI request object
            name: Template name
            context: Template context dict
            **kwargs: Additional arguments for TemplateResponse

        Returns:
            TemplateResponse with enhanced context
        """
        if context is None:
            context = {}

        # Add request-scoped globals
        context["request"] = request

        # Add nonce to template context
        nonce = get_nonce_from_request(request)
        if nonce:
            context["nonce"] = nonce

        # Inject turnstile_site_key per-render so test patches and env changes
        # are seen live; Jinja's template.globals are frozen at load time, so
        # using env.globals alone makes the value un-overridable from tests.
        context["turnstile_site_key"] = templates.env.globals.get("turnstile_site_key", "")

        return super().TemplateResponse(request, name, context, **kwargs)


# Shared templates instance for all routes
templates = TemplatesWithGlobals(directory="app/templates")
templates.env.globals["turnstile_site_key"] = TURNSTILE_SITE_KEY


def paper_frame_src(scroll) -> str:
    """Address the scroll page's iframe loads. Published papers come from the content
    domain when it is set. Previews stay on Press until signed preview links exist."""
    from app.content_domain import paper_url

    if scroll.status != "preview" and (url := paper_url(scroll.url_hash)):
        return url
    suffix = "/" if scroll.storage_type == "archive" else ""
    return f"/scroll/{scroll.url_hash}/paper{suffix}"


templates.env.globals["paper_frame_src"] = paper_frame_src


def _abstract_html_filter(text, terms=()):
    """Escaped abstract with its math marked for MathJax (app/abstract_math.py)."""
    from markupsafe import Markup

    from app.abstract_math import abstract_html

    return Markup(abstract_html(text, terms))


templates.env.filters["abstract_html"] = _abstract_html_filter


def preview_frame_src(scroll) -> str:
    """Address the preview page's iframe loads: a signed content domain link that works
    for an hour, or Press itself when there is no content domain or no signing key."""
    from app.content_domain import signed_preview_url

    if url := signed_preview_url(scroll.url_hash):
        return url
    suffix = "/" if scroll.storage_type == "archive" else ""
    return f"/scroll/{scroll.url_hash}/paper{suffix}"


templates.env.globals["preview_frame_src"] = preview_frame_src
