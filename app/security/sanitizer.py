"""HTML sanitization module for XSS prevention."""

import logging
import re

import bleach

logger = logging.getLogger(__name__)

ALLOWED_TAGS = [
    # Document structure
    "html",
    "head",
    "body",
    "title",
    "meta",
    "link",
    "style",
    "script",  # Allow scripts - will be secured with nonces
    # Typography
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "p",
    "br",
    "hr",
    "strong",
    "em",
    "u",
    "sub",
    "sup",
    "small",
    "mark",
    # lists
    "ul",
    "ol",
    "li",
    "dl",
    "dt",
    "dd",
    # Tables
    "table",
    "thead",
    "tbody",
    "tfoot",
    "tr",
    "th",
    "td",
    "caption",
    "colgroup",
    "col",
    # Semantic elements
    "article",
    "section",
    "aside",
    "header",
    "footer",
    "main",
    "nav",
    "div",
    "span",
    # Media
    "img",
    "figure",
    "figcaption",
    "svg",
    # Links
    "a",
    # Code
    "pre",
    "code",
    "kbd",
    "samp",
    # Quotes
    "blockquote",
    "cite",
    "q",
    # Scientific
    "abbr",
    "dfn",
    "time",
    "data",
]

ALLOWED_ATTRIBUTES = {
    "*": ["id", "class", "title", "lang", "dir", "style"],
    "a": ["href", "target", "rel"],
    "img": ["src", "alt", "width", "height"],
    "meta": ["name", "content", "charset", "http-equiv"],
    "link": ["rel", "href", "type"],
    "style": ["type"],
    "script": [
        "src",
        "type",
        "async",
        "defer",
    ],  # Script attributes - nonce will be added separately
    "svg": ["width", "height", "viewBox", "xmlns"],
    "th": ["scope", "colspan", "rowspan"],
    "td": ["colspan", "rowspan"],
    "time": ["datetime"],
    "data": ["value"],
}

ALLOWED_CSS_PROPERTIES = [
    # Typography
    "font-family",
    "font-size",
    "font-weight",
    "font-style",
    "color",
    "text-align",
    "line-height",
    "text-decoration",
    # Layout
    "margin",
    "margin-top",
    "margin-right",
    "margin-bottom",
    "margin-left",
    "padding",
    "padding-top",
    "padding-right",
    "padding-bottom",
    "padding-left",
    "width",
    "height",
    "max-width",
    "max-height",
    "display",
    "vertical-align",
    # Visual
    "background-color",
    "background-image",
    "border",
    "border-radius",
    "box-shadow",
    # Tables
    "border-collapse",
    "border-spacing",
    "table-layout",
]

ALLOWED_PROTOCOLS = ["http", "https", "mailto", "tel"]


class CustomCSSSanitizer:
    """Custom CSS sanitizer for Bleach."""

    def __init__(self, sanitizer_instance):
        self.sanitizer = sanitizer_instance

    def sanitize_css(self, style: str) -> str:
        """Sanitize CSS properties in style attributes."""
        return self.sanitizer._css_sanitizer(style)


class HTMLSanitizer:
    """Sanitizes HTML content to prevent XSS attacks while preserving scientific formatting."""

    def __init__(self):
        self.sanitization_log = []

    def sanitize(self, html_content: str) -> tuple[str, list[dict]]:
        """
        Sanitize HTML content and return sanitized HTML with sanitization log.

        Args:
            html_content: Raw HTML content to sanitize

        Returns:
            tuple of (sanitized_html, sanitization_log)
        """
        self.sanitization_log = []

        # Pre-process: remove dangerous content (but not scripts)
        html_content = self._remove_event_handlers(html_content)
        html_content = self._remove_javascript_urls(html_content)
        html_content = self._remove_dangerous_css(html_content)

        # Sanitize with bleach
        sanitized = bleach.clean(
            html_content,
            tags=ALLOWED_TAGS,
            attributes=ALLOWED_ATTRIBUTES,
            protocols=ALLOWED_PROTOCOLS,
            strip=True,
            strip_comments=True,
            css_sanitizer=CustomCSSSanitizer(self),
        )

        # Post-process: validate remaining content
        sanitized = self._validate_links(sanitized)
        sanitized = self._process_style_tags(sanitized)

        return sanitized, self.sanitization_log

    def _remove_event_handlers(self, content: str) -> str:
        """Remove event handlers from HTML."""
        # Remove event handlers - use word boundaries to be specific
        event_pattern = re.compile(r'\s*\bon[a-z]+\s*=\s*["\'][^"\']*["\']', re.IGNORECASE)
        matches = event_pattern.findall(content)
        if matches:
            self.sanitization_log.append(
                {
                    "type": "event_handler_removed",
                    "count": len(matches),
                    "message": f"Removed {len(matches)} event handler(s)",
                }
            )
        content = event_pattern.sub("", content)
        return content

    def _remove_javascript_urls(self, content: str) -> str:
        """Remove javascript: URLs."""
        # Remove entire attribute values that contain javascript: URLs
        js_url_pattern = re.compile(
            r'(href|src)\s*=\s*["\'][^"\']*javascript\s*:[^"\']*["\']', re.IGNORECASE
        )
        matches = js_url_pattern.findall(content)
        if matches:
            self.sanitization_log.append(
                {
                    "type": "javascript_url_removed",
                    "count": len(matches),
                    "message": f"Removed {len(matches)} javascript: URL(s)",
                }
            )
        content = js_url_pattern.sub("", content)
        return content

    def _remove_dangerous_css(self, content: str) -> str:
        """Remove dangerous CSS properties and values."""
        # Remove expression() in CSS
        expression_pattern = re.compile(r"expression\s*\([^)]*\)", re.IGNORECASE)
        matches = expression_pattern.findall(content)
        if matches:
            self.sanitization_log.append(
                {
                    "type": "css_expression_removed",
                    "count": len(matches),
                    "message": f"Removed {len(matches)} CSS expression(s)",
                }
            )
        content = expression_pattern.sub("", content)

        # Remove javascript: in CSS url()
        css_js_pattern = re.compile(r'url\s*\(\s*["\']?\s*javascript:', re.IGNORECASE)
        matches = css_js_pattern.findall(content)
        if matches:
            self.sanitization_log.append(
                {
                    "type": "css_javascript_url_removed",
                    "count": len(matches),
                    "message": f"Removed {len(matches)} javascript: URL(s) in CSS",
                }
            )
        content = css_js_pattern.sub("url(", content)

        return content

    def _css_sanitizer(self, style: str) -> str:
        """Sanitize CSS properties in style attributes."""
        if not style:
            return ""

        # Parse CSS properties
        properties = []
        for prop in style.split(";"):
            prop = prop.strip()
            if ":" not in prop:
                continue

            name, value = prop.split(":", 1)
            name = name.strip().lower()
            value = value.strip()

            # Check if property is allowed
            if name in ALLOWED_CSS_PROPERTIES:
                # Additional validation for specific properties
                if "url(" in value.lower():
                    # Only allow data: URLs for images
                    if "data:image/" not in value.lower():
                        self.sanitization_log.append(
                            {
                                "type": "css_url_blocked",
                                "property": name,
                                "message": f"Blocked non-image URL in CSS property: {name}",
                            }
                        )
                        continue
                properties.append(f"{name}: {value}")
            else:
                self.sanitization_log.append(
                    {
                        "type": "css_property_blocked",
                        "property": name,
                        "message": f"Blocked disallowed CSS property: {name}",
                    }
                )

        result = "; ".join(properties)
        return result if result else ""

    def _validate_links(self, content: str) -> str:
        """Validate and sanitize link attributes."""
        # Ensure all external links have rel="noopener noreferrer"
        link_pattern = re.compile(
            r'<a\s+([^>]*href=["\']https?://[^"\']*["\'][^>]*)>', re.IGNORECASE
        )

        def add_rel_attribute(match):
            tag_content = match.group(1)
            if "rel=" not in tag_content:
                return f'<a {tag_content} rel="noopener noreferrer">'
            else:
                # Ensure existing rel includes noopener noreferrer
                tag_content = re.sub(
                    r'rel=["\'][^"\']*["\']', 'rel="noopener noreferrer"', tag_content
                )
                return f"<a {tag_content}>"

        content = link_pattern.sub(add_rel_attribute, content)
        return content

    def _process_style_tags(self, content: str) -> str:
        """Process and validate style tags."""
        style_pattern = re.compile(r"<style[^>]*>(.*?)</style>", re.IGNORECASE | re.DOTALL)

        def validate_style_content(match):
            style_content = match.group(1)
            # Remove @import statements
            if "@import" in style_content:
                self.sanitization_log.append(
                    {
                        "type": "css_import_removed",
                        "message": "Removed @import statement from style tag",
                    }
                )
                style_content = re.sub(r"@import[^;]+;", "", style_content)

            # Validate all CSS properties in the style block
            validated_content = self._validate_css_block(style_content)
            return f"<style>{validated_content}</style>"

        content = style_pattern.sub(validate_style_content, content)
        return content

    def _validate_css_block(self, css_content: str) -> str:
        """Validate CSS block content."""
        # This is a simplified CSS validator
        # In production, consider using a proper CSS parser
        lines = []
        for line in css_content.split("\n"):
            line = line.strip()
            if line and not line.startswith("/*") and not line.endswith("*/"):
                # Check for dangerous patterns
                if "expression(" in line.lower() or "javascript:" in line.lower():
                    continue
                lines.append(line)
        return "\n".join(lines)

    def extract_external_resources(self, html_content: str) -> list[dict[str, str]]:
        """Extract list of external resources referenced in HTML."""
        resources = []

        # Extract images
        img_pattern = re.compile(r'<img[^>]+src=["\']([^"\']+)["\']', re.IGNORECASE)
        for match in img_pattern.finditer(html_content):
            src = match.group(1)
            if src.startswith(("http://", "https://")):
                resources.append({"type": "image", "url": src})

        # Extract stylesheets
        link_pattern = re.compile(
            r'<link[^>]*rel=["\']stylesheet["\'][^>]*href=["\']([^"\']+)["\']', re.IGNORECASE
        )
        for match in link_pattern.finditer(html_content):
            href = match.group(1)
            if href.startswith(("http://", "https://")):
                resources.append({"type": "stylesheet", "url": href})

        # Extract links
        a_pattern = re.compile(r'<a[^>]+href=["\']([^"\']+)["\']', re.IGNORECASE)
        for match in a_pattern.finditer(html_content):
            href = match.group(1)
            if href.startswith(("http://", "https://")):
                resources.append({"type": "link", "url": href})

        return resources
