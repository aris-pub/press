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

        return super().TemplateResponse(request, name, context, **kwargs)


# Shared templates instance for all routes
templates = TemplatesWithGlobals(directory="app/templates")
templates.env.globals["turnstile_site_key"] = TURNSTILE_SITE_KEY
