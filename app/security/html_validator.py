"""HTML validation module that rejects dangerous content instead of sanitizing."""

import re
from typing import Dict, List, Tuple

from bs4 import BeautifulSoup


class HTMLValidationError:
    """Represents a validation error with detailed information."""

    def __init__(
        self, error_type: str, message: str, line_number: int = None, element: str = None
    ):
        self.error_type = error_type
        self.message = message
        self.line_number = line_number
        self.element = element

    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "type": self.error_type,
            "message": self.message,
            "line_number": self.line_number,
            "element": self.element,
        }


class HTMLValidator:
    """Validates HTML content and rejects uploads with dangerous content."""

    # Tags that are completely forbidden
    FORBIDDEN_TAGS = [
        # "script" removed - now allowed, controlled by nonce system
        "iframe",
        "frame",
        "frameset",
        "object",
        "embed",
        "applet",
        # Note: form, button, input, textarea, select are allowed for interactive research papers
        # Forms with external actions are validated separately in _check_form_actions()
        "base",  # Base tag can redirect all relative URLs
    ]

    # Meta tags that are allowed (others will be rejected)
    ALLOWED_META_NAMES = [
        "author",
        "description",
        "keywords",
        "title",
        "subject",
        "language",
        "date",
        "revised",
        "generator",
        "viewport",
        "charset",
        "content-type",
    ]

    # Attributes that are never allowed
    FORBIDDEN_ATTRIBUTES = [
        # Event handlers
        "onclick",
        "onmouseover",
        "onmouseout",
        "onload",
        "onerror",
        "onfocus",
        "onblur",
        "onchange",
        "onsubmit",
        "onreset",
        "onkeydown",
        "onkeyup",
        "onkeypress",
        "ondblclick",
        "onmousedown",
        "onmouseup",
        "onmousemove",
        "onmouseenter",
        "onmouseleave",
        # Other dangerous attributes
        "srcdoc",
        "sandbox",
    ]

    # CSS properties that are forbidden
    FORBIDDEN_CSS_PROPERTIES = [
        "behavior",  # IE-specific, can execute code
        "-moz-binding",  # Firefox-specific, can execute code
        "expression",  # IE-specific CSS expressions (XSS vector)
        "javascript",  # Direct JavaScript in CSS
        "vbscript",  # VBScript in CSS
        "livescript",  # LiveScript in CSS
        "mocha",  # Mocha script in CSS
    ]

    def __init__(self):
        self.errors: List[HTMLValidationError] = []

    def validate(self, html_content: str) -> Tuple[bool, List[Dict]]:
        """
        Validate HTML content and return validation results.

        Args:
            html_content: The HTML content to validate

        Returns:
            Tuple of (is_valid, list_of_error_dicts)
        """
        self.errors = []
        lines = html_content.split("\n")

        # Check for forbidden tags
        self._check_forbidden_tags(html_content, lines)

        # Check meta tags specifically (some allowed, some not)
        self._check_meta_tags(html_content, lines)

        # Check for forbidden attributes
        self._check_forbidden_attributes(html_content, lines)

        # Check for dangerous CSS
        self._check_dangerous_css(html_content, lines)

        # Check for JavaScript URLs
        self._check_javascript_urls(html_content, lines)

        # Check for dangerous protocols
        self._check_dangerous_protocols(html_content, lines)

        # Check for external resources (CDN links)
        self._check_external_resources(html_content, lines)

        # Check for forms with external actions
        self._check_form_actions(html_content, lines)

        is_valid = len(self.errors) == 0
        error_dicts = [error.to_dict() for error in self.errors]

        return is_valid, error_dicts

    def _check_forbidden_tags(self, content: str, lines: List[str]):
        """Check for forbidden HTML tags using BeautifulSoup."""
        soup = BeautifulSoup(content, "html.parser")

        for tag_name in self.FORBIDDEN_TAGS:
            # Find all instances of this tag
            tags = soup.find_all(tag_name)

            for tag in tags:
                # Get the string representation of the tag
                tag_str = str(tag)[:100]  # Truncate to 100 chars

                # Find position in original content to get line number
                # Use the opening tag as search string
                search_str = f"<{tag.name}"
                pos = content.find(search_str, 0)

                # If we can't find it simply, try to find by matching the tag string
                if pos == -1:
                    pos = content.find(tag_str[:50])

                if pos != -1:
                    line_num = self._get_line_number(content, pos, lines)
                else:
                    line_num = None

                self.errors.append(
                    HTMLValidationError(
                        error_type="forbidden_tag",
                        message=f"Forbidden tag <{tag_name}> is not allowed",
                        line_number=line_num,
                        element=tag_str,
                    )
                )

    def _check_meta_tags(self, content: str, lines: List[str]):
        """Check meta tags - allow safe ones, reject dangerous ones."""
        soup = BeautifulSoup(content, "html.parser")
        meta_tags = soup.find_all("meta")

        for tag in meta_tags:
            tag_str = str(tag)[:100]

            # Find position in original content
            pos = content.find(tag_str[:50])
            line_num = self._get_line_number(content, pos, lines) if pos != -1 else None

            # Check for http-equiv refresh which can be dangerous
            http_equiv = tag.get("http-equiv", "").lower()
            if http_equiv == "refresh":
                self.errors.append(
                    HTMLValidationError(
                        error_type="dangerous_meta",
                        message="Meta refresh tags are not allowed (security risk)",
                        line_number=line_num,
                        element=tag_str,
                    )
                )
                continue

            # Check name attribute for allowed values
            name_value = tag.get("name", "").lower()
            if name_value and name_value not in [name.lower() for name in self.ALLOWED_META_NAMES]:
                self.errors.append(
                    HTMLValidationError(
                        error_type="forbidden_meta",
                        message=f"Meta tag with name '{name_value}' is not allowed",
                        line_number=line_num,
                        element=tag_str,
                    )
                )

    def _check_forbidden_attributes(self, content: str, lines: List[str]):
        """Check for forbidden attributes like event handlers."""
        soup = BeautifulSoup(content, "html.parser")

        for attr in self.FORBIDDEN_ATTRIBUTES:
            # Find all tags that have this attribute
            tags = soup.find_all(attrs={attr: True})

            for tag in tags:
                tag_str = str(tag)[:100]

                # Find position in original content
                pos = content.find(tag_str[:50])
                line_num = self._get_line_number(content, pos, lines) if pos != -1 else None

                # Get the attribute value for display
                attr_value = tag.get(attr, "")
                element_display = f'{attr}="{attr_value}"'

                self.errors.append(
                    HTMLValidationError(
                        error_type="forbidden_attribute",
                        message=f"Forbidden attribute '{attr}' is not allowed",
                        line_number=line_num,
                        element=element_display,
                    )
                )

    def _check_dangerous_css(self, content: str, lines: List[str]):
        """Check for dangerous CSS properties and values."""
        # Check style attributes
        style_pattern = r'style\s*=\s*["\']([^"\']*)["\']'
        style_matches = re.finditer(style_pattern, content, re.IGNORECASE)

        for match in style_matches:
            style_content = match.group(1)
            line_num = self._get_line_number(content, match.start(), lines)
            self._validate_css_content(style_content, line_num, "inline style")

        # Check <style> tags
        style_tag_pattern = r"<style[^>]*>(.*?)</style>"
        style_tag_matches = re.finditer(style_tag_pattern, content, re.IGNORECASE | re.DOTALL)

        for match in style_tag_matches:
            style_content = match.group(1)
            line_num = self._get_line_number(content, match.start(), lines)
            self._validate_css_content(style_content, line_num, "style tag")

    def _validate_css_content(self, css_content: str, line_num: int, context: str):
        """Validate CSS content for dangerous properties."""
        # Check for dangerous CSS properties (excluding 'expression' which is handled separately)
        dangerous_props = [prop for prop in self.FORBIDDEN_CSS_PROPERTIES if prop != "expression"]
        for prop in dangerous_props:
            if prop.lower() in css_content.lower():
                self.errors.append(
                    HTMLValidationError(
                        error_type="dangerous_css",
                        message=f"Dangerous CSS property '{prop}' found in {context}",
                        line_number=line_num,
                        element=css_content[:100] + "..."
                        if len(css_content) > 100
                        else css_content,
                    )
                )

        # Check for CSS expression() function calls specifically (not just the word "expression")
        if re.search(r"expression\s*\(", css_content, re.IGNORECASE):
            self.errors.append(
                HTMLValidationError(
                    error_type="css_expression",
                    message=f"CSS expression() function found in {context} - not allowed",
                    line_number=line_num,
                    element=css_content[:100] + "..." if len(css_content) > 100 else css_content,
                )
            )

        # Check for @import statements (including external URLs)
        # Allow MathJax/KaTeX CDNs
        import_matches = re.finditer(
            r"@import\s+(?:url\(['\"](https?://[^'\"]+)['\"]\)|['\"](https?://[^'\"]+)['\"])",
            css_content,
            re.IGNORECASE,
        )
        for import_match in import_matches:
            url = import_match.group(1) or import_match.group(2)

            # Check if URL is from allowed CDN
            if any(allowed in url for allowed in self.ALLOWED_CDN_DOMAINS):
                continue

            self.errors.append(
                HTMLValidationError(
                    error_type="css_import_external",
                    message=f"CSS @import with external URL '{url}' found in {context} - not allowed. Papers must be self-contained (MathJax/KaTeX CDNs are allowed).",
                    line_number=line_num,
                    element=import_match.group(0),
                )
            )

        # Check for any other @import statements (local files)
        if re.search(
            r"@import\s+(?:url\()?['\"]?(?!https?://)[^'\"]+", css_content, re.IGNORECASE
        ):
            self.errors.append(
                HTMLValidationError(
                    error_type="css_import",
                    message=f"CSS @import statement found in {context} - not allowed",
                    line_number=line_num,
                    element=css_content[:100] + "..." if len(css_content) > 100 else css_content,
                )
            )

    def _check_javascript_urls(self, content: str, lines: List[str]):
        """Check for javascript: URLs."""
        js_url_pattern = r'(?:href|src|action)\s*=\s*["\']?\s*javascript:'
        matches = re.finditer(js_url_pattern, content, re.IGNORECASE)

        for match in matches:
            line_num = self._get_line_number(content, match.start(), lines)
            self.errors.append(
                HTMLValidationError(
                    error_type="javascript_url",
                    message="JavaScript URLs (javascript:) are not allowed",
                    line_number=line_num,
                    element=match.group(0),
                )
            )

    def _check_dangerous_protocols(self, content: str, lines: List[str]):
        """Check for other dangerous protocols."""
        dangerous_protocols = ["vbscript:", "livescript:", "mocha:", "data:text/html"]

        for protocol in dangerous_protocols:
            if protocol.lower() in content.lower():
                # Find the specific location
                pattern = rf'(?:href|src|action)\s*=\s*["\']?\s*{re.escape(protocol)}'
                matches = re.finditer(pattern, content, re.IGNORECASE)

                for match in matches:
                    line_num = self._get_line_number(content, match.start(), lines)
                    self.errors.append(
                        HTMLValidationError(
                            error_type="dangerous_protocol",
                            message=f"Dangerous protocol '{protocol}' is not allowed",
                            line_number=line_num,
                            element=match.group(0),
                        )
                    )

    def _check_form_actions(self, content: str, lines: List[str]):
        """Check for forms with external action URLs."""
        # Find all form tags with action attributes using regex
        form_pattern = r'<form[^>]+action\s*=\s*["\']([^"\']+)["\'][^>]*>'
        matches = re.finditer(form_pattern, content, re.IGNORECASE)

        for match in matches:
            action_url = match.group(1).strip()
            line_num = self._get_line_number(content, match.start(), lines)

            # Allow empty actions, "#", or javascript: URLs (client-side handling)
            if not action_url or action_url == "#" or action_url.lower().startswith("javascript:"):
                continue

            # Block forms with external URLs (http://, https://, or protocol-relative //)
            if action_url.startswith(("http://", "https://", "//")):
                self.errors.append(
                    HTMLValidationError(
                        error_type="external_form_action",
                        message=f"Form with external action '{action_url}' is not allowed. Forms must not submit to external URLs.",
                        line_number=line_num,
                        element=match.group(0)[:100],
                    )
                )

    # Allowed CDN domains for essential rendering libraries
    ALLOWED_CDN_DOMAINS = [
        # Math rendering
        "cdn.jsdelivr.net/npm/mathjax",
        "cdnjs.cloudflare.com/ajax/libs/mathjax",
        "cdn.jsdelivr.net/npm/katex",
        "cdnjs.cloudflare.com/ajax/libs/KaTeX",
        # Fonts
        "fonts.googleapis.com",
        "fonts.gstatic.com",
        # Data visualization libraries
        "cdn.jsdelivr.net/npm/d3@",
        "cdn.jsdelivr.net/npm/plotly.js@",
        "cdn.jsdelivr.net/npm/chart.js@",
        "cdn.jsdelivr.net/npm/vega@",
        "cdn.jsdelivr.net/npm/vega-lite@",
        "cdn.jsdelivr.net/npm/vega-embed@",
        "unpkg.com/d3@",
        "unpkg.com/plotly.js@",
    ]

    def _check_external_resources(self, content: str, lines: List[str]):
        """Check for external script and stylesheet resources (reject non-self-contained HTML except for allowed CDNs)."""
        # Check for external script tags (http:// or https://)
        # Allow data: URIs since those are self-contained
        # Allow MathJax/KaTeX CDNs since they're essential for math rendering
        script_pattern = r'<script[^>]+src\s*=\s*["\'](?!data:)(https?://[^"\']+)["\'][^>]*>'
        script_matches = re.finditer(script_pattern, content, re.IGNORECASE)

        for match in script_matches:
            url = match.group(1)

            # Check if URL is from allowed CDN
            if any(allowed in url for allowed in self.ALLOWED_CDN_DOMAINS):
                continue

            line_num = self._get_line_number(content, match.start(), lines)
            self.errors.append(
                HTMLValidationError(
                    error_type="external_script",
                    message=f"External script '{url}' not allowed. Papers must be self-contained with all resources embedded (MathJax/KaTeX CDNs are allowed).",
                    line_number=line_num,
                    element=match.group(0),
                )
            )

        # Check for external stylesheet links (http:// or https://)
        # Allow data: URIs since those are self-contained
        # Allow MathJax/KaTeX CDNs since they're essential for math rendering
        link_pattern = r'<link[^>]+href\s*=\s*["\'](?!data:)(https?://[^"\']+)["\'][^>]*>'
        link_matches = re.finditer(link_pattern, content, re.IGNORECASE)

        for match in link_matches:
            url = match.group(1)

            # Check if URL is from allowed CDN
            if any(allowed in url for allowed in self.ALLOWED_CDN_DOMAINS):
                continue

            line_num = self._get_line_number(content, match.start(), lines)
            self.errors.append(
                HTMLValidationError(
                    error_type="external_stylesheet",
                    message=f"External stylesheet '{url}' not allowed. Papers must be self-contained with all resources embedded (MathJax/KaTeX CDNs are allowed).",
                    line_number=line_num,
                    element=match.group(0),
                )
            )

    def _get_line_number(self, content: str, position: int, lines: List[str]) -> int:
        """Get line number for a character position in the content."""
        chars_seen = 0
        for i, line in enumerate(lines, 1):
            chars_seen += len(line) + 1  # +1 for newline
            if chars_seen > position:
                return i
        return len(lines)
