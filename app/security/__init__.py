"""Security module for HTML validation and XSS prevention."""

from .validation import ContentValidator

__all__ = ["ContentValidator"]
