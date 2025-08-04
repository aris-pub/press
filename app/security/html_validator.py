"""HTML validation module that rejects dangerous content instead of sanitizing."""

import re
from typing import Dict, List, Tuple


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
        "script",  # No JavaScript allowed
        "iframe",
        "frame",
        "frameset",
        "object",
        "embed",
        "applet",
        "form",
        "input",
        "textarea",
        "select",
        "button",
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
        "position",
        "behavior",
        "-moz-binding",
        "expression",
        "javascript",
        "vbscript",
        "livescript",
        "mocha",
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

        is_valid = len(self.errors) == 0
        error_dicts = [error.to_dict() for error in self.errors]

        return is_valid, error_dicts

    def _check_forbidden_tags(self, content: str, lines: List[str]):
        """Check for forbidden HTML tags."""
        for tag in self.FORBIDDEN_TAGS:
            # Match both opening and self-closing tags
            pattern = rf"<\s*{re.escape(tag)}(?:\s[^>]*)?/?>"
            matches = list(re.finditer(pattern, content, re.IGNORECASE))

            for match in matches:
                line_num = self._get_line_number(content, match.start(), lines)
                self.errors.append(
                    HTMLValidationError(
                        error_type="forbidden_tag",
                        message=f"Forbidden tag <{tag}> is not allowed",
                        line_number=line_num,
                        element=match.group(0),
                    )
                )

    def _check_meta_tags(self, content: str, lines: List[str]):
        """Check meta tags - allow safe ones, reject dangerous ones."""
        # Find all meta tags
        meta_pattern = r"<meta\s+([^>]+)/?>"
        matches = list(re.finditer(meta_pattern, content, re.IGNORECASE))

        for match in matches:
            attrs = match.group(1)
            line_num = self._get_line_number(content, match.start(), lines)

            # Check for http-equiv which can be dangerous
            if re.search(r'http-equiv\s*=\s*["\']?refresh["\']?', attrs, re.IGNORECASE):
                self.errors.append(
                    HTMLValidationError(
                        error_type="dangerous_meta",
                        message="Meta refresh tags are not allowed (security risk)",
                        line_number=line_num,
                        element=match.group(0),
                    )
                )
                continue

            # Check name attribute for allowed values
            name_match = re.search(r'name\s*=\s*["\']([^"\']+)["\']', attrs, re.IGNORECASE)
            if name_match:
                name_value = name_match.group(1).lower()
                if name_value not in [name.lower() for name in self.ALLOWED_META_NAMES]:
                    self.errors.append(
                        HTMLValidationError(
                            error_type="forbidden_meta",
                            message=f"Meta tag with name '{name_value}' is not allowed",
                            line_number=line_num,
                            element=match.group(0),
                        )
                    )

    def _check_forbidden_attributes(self, content: str, lines: List[str]):
        """Check for forbidden attributes like event handlers."""
        for attr in self.FORBIDDEN_ATTRIBUTES:
            # Match attribute="value" or attribute='value' or attribute=value
            pattern = rf'\s{re.escape(attr)}\s*=\s*["\'][^"\']*["\']'
            matches = list(re.finditer(pattern, content, re.IGNORECASE))

            for match in matches:
                line_num = self._get_line_number(content, match.start(), lines)
                self.errors.append(
                    HTMLValidationError(
                        error_type="forbidden_attribute",
                        message=f"Forbidden attribute '{attr}' is not allowed",
                        line_number=line_num,
                        element=match.group(0).strip(),
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
        for prop in self.FORBIDDEN_CSS_PROPERTIES:
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

        # Check for CSS expressions
        if re.search(r"expression\s*\(", css_content, re.IGNORECASE):
            self.errors.append(
                HTMLValidationError(
                    error_type="css_expression",
                    message=f"CSS expression() found in {context} - not allowed",
                    line_number=line_num,
                    element=css_content[:100] + "..." if len(css_content) > 100 else css_content,
                )
            )

        # Check for @import statements
        if re.search(r"@import\s+", css_content, re.IGNORECASE):
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

    def _get_line_number(self, content: str, position: int, lines: List[str]) -> int:
        """Get line number for a character position in the content."""
        chars_seen = 0
        for i, line in enumerate(lines, 1):
            chars_seen += len(line) + 1  # +1 for newline
            if chars_seen > position:
                return i
        return len(lines)
