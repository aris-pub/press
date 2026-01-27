"""HTML validation module that rejects dangerous content instead of sanitizing."""

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

        # MEMORY OPTIMIZATION: Strip out script contents before parsing
        # We validate HTML structure and attributes, not JavaScript code
        # This prevents BeautifulSoup from building huge DOM trees for minified libs (Plotly, etc)
        # Keep style contents because we need to validate CSS
        content_for_parsing = html_content
        script_start = 0
        while True:
            script_start = content_for_parsing.find("<script", script_start)
            if script_start == -1:
                break
            script_tag_end = content_for_parsing.find(">", script_start)
            if script_tag_end == -1:
                break
            script_close = content_for_parsing.find("</script>", script_tag_end)
            if script_close == -1:
                break
            # Replace script contents with empty string, keep opening/closing tags
            content_for_parsing = (
                content_for_parsing[: script_tag_end + 1] + content_for_parsing[script_close:]
            )
            script_start = script_tag_end + 1

        # Parse HTML once and reuse for all checks (memory optimization)
        # Use lxml parser if available (faster, more memory efficient)
        try:
            soup = BeautifulSoup(content_for_parsing, "lxml")
        except Exception:
            # Fall back to html.parser if lxml not available
            soup = BeautifulSoup(content_for_parsing, "html.parser")

        # Run all validation checks with the same parsed soup
        # Don't pass lines - we'll compute line numbers on demand to save memory
        self._check_forbidden_tags(soup, html_content)
        self._check_meta_tags(soup, html_content)
        self._check_forbidden_attributes(soup, html_content)
        self._check_dangerous_css(soup, html_content)
        self._check_javascript_urls(soup, html_content)
        self._check_dangerous_protocols(soup, html_content)
        self._check_external_resources(soup, html_content)
        self._check_form_actions(soup, html_content)

        is_valid = len(self.errors) == 0
        error_dicts = [error.to_dict() for error in self.errors]

        # Explicitly delete soup to free memory immediately
        del soup

        return is_valid, error_dicts

    def _check_forbidden_tags(self, soup, content: str):
        """Check for forbidden HTML tags using BeautifulSoup."""

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
                    line_num = self._get_line_number(content, pos)
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

    def _check_meta_tags(self, soup, content: str):
        """Check meta tags - allow safe ones, reject dangerous ones."""
        meta_tags = soup.find_all("meta")

        for tag in meta_tags:
            tag_str = str(tag)[:100]

            # Find position in original content
            pos = content.find(tag_str[:50])
            line_num = self._get_line_number(content, pos) if pos != -1 else None

            # Check for dangerous http-equiv values
            http_equiv = tag.get("http-equiv", "").lower()

            DANGEROUS_HTTP_EQUIV = ["refresh", "set-cookie", "content-security-policy"]

            if http_equiv in DANGEROUS_HTTP_EQUIV:
                self.errors.append(
                    HTMLValidationError(
                        error_type="dangerous_meta",
                        message=f"Meta tag with http-equiv='{http_equiv}' is not allowed (security risk)",
                        line_number=line_num,
                        element=tag_str,
                    )
                )
                continue

            # All meta tags with name, property, or charset attributes are allowed
            # These are metadata only and pose no XSS risk

    def _check_forbidden_attributes(self, soup, content: str):
        """Check for forbidden attributes like event handlers."""

        for attr in self.FORBIDDEN_ATTRIBUTES:
            # Find all tags that have this attribute
            tags = soup.find_all(attrs={attr: True})

            for tag in tags:
                tag_str = str(tag)[:100]

                # Find position in original content
                pos = content.find(tag_str[:50])
                line_num = self._get_line_number(content, pos) if pos != -1 else None

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

    def _check_dangerous_css(self, soup, content: str):
        """Check for dangerous CSS properties and values using BeautifulSoup."""

        # Check style attributes on all tags
        tags_with_style = soup.find_all(attrs={"style": True})
        for tag in tags_with_style:
            style_content = tag.get("style", "")
            tag_str = str(tag)[:50]
            pos = content.find(tag_str)
            line_num = self._get_line_number(content, pos) if pos != -1 else None
            self._validate_css_content(style_content, line_num, "inline style")

        # Check <style> tags
        style_tags = soup.find_all("style")
        for tag in style_tags:
            style_content = tag.string or ""
            tag_str = str(tag)[:50]
            pos = content.find(tag_str)
            line_num = self._get_line_number(content, pos) if pos != -1 else None
            self._validate_css_content(style_content, line_num, "style tag")

    def _validate_css_content(self, css_content: str, line_num: int, context: str):
        """Validate CSS content for dangerous properties."""
        css_lower = css_content.lower()

        # Check for dangerous CSS properties
        for prop in self.FORBIDDEN_CSS_PROPERTIES:
            if prop.lower() in css_lower:
                # Special handling for "expression" - only flag if it's expression()
                if prop == "expression":
                    # Check if "expression" is followed by "(" (with optional whitespace)
                    if "expression" in css_lower:
                        idx = css_lower.find("expression")
                        rest = css_lower[idx + len("expression") :].lstrip()
                        if rest.startswith("("):
                            self.errors.append(
                                HTMLValidationError(
                                    error_type="css_expression",
                                    message=f"CSS expression() function found in {context} - not allowed",
                                    line_number=line_num,
                                    element=css_content[:100] + "..."
                                    if len(css_content) > 100
                                    else css_content,
                                )
                            )
                else:
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

        # Check for @import statements
        if "@import" in css_lower:
            # Check for external URLs in @import
            if "http://" in css_lower or "https://" in css_lower:
                # Extract URL - simple string search for http(s):// after @import
                import_idx = css_lower.find("@import")
                rest = css_content[import_idx:]
                http_idx = rest.lower().find("http")
                if http_idx != -1:
                    # Find the URL by looking for the next quote or paren
                    url_start = import_idx + http_idx
                    url_rest = css_content[url_start:]
                    # Find end of URL (quote, paren, semicolon, or whitespace)
                    url_end = url_start
                    for char in ["'", '"', ")", ";", " ", "\n"]:
                        idx = url_rest.find(char)
                        if idx != -1:
                            url_end = url_start + idx
                            break
                    url = css_content[url_start:url_end] if url_end > url_start else ""

                    # Check if URL is from allowed CDN
                    if not any(allowed in url for allowed in self.ALLOWED_CDN_DOMAINS):
                        self.errors.append(
                            HTMLValidationError(
                                error_type="css_import_external",
                                message=f"CSS @import with external URL found in {context} - not allowed. Papers must be self-contained (MathJax/KaTeX CDNs are allowed).",
                                line_number=line_num,
                                element=css_content[:100] + "..."
                                if len(css_content) > 100
                                else css_content,
                            )
                        )
            else:
                # Local @import
                self.errors.append(
                    HTMLValidationError(
                        error_type="css_import",
                        message=f"CSS @import statement found in {context} - not allowed",
                        line_number=line_num,
                        element=css_content[:100] + "..."
                        if len(css_content) > 100
                        else css_content,
                    )
                )

    def _check_javascript_urls(self, soup, content: str):
        """Check for javascript: URLs using BeautifulSoup."""

        # Check all tags for href, src, or action attributes with javascript:
        url_attributes = ["href", "src", "action"]
        for attr in url_attributes:
            tags = soup.find_all(attrs={attr: True})
            for tag in tags:
                attr_value = tag.get(attr, "").strip().lower()
                if attr_value.startswith("javascript:"):
                    tag_str = str(tag)[:100]
                    pos = content.find(tag_str[:50])
                    line_num = self._get_line_number(content, pos) if pos != -1 else None

                    self.errors.append(
                        HTMLValidationError(
                            error_type="javascript_url",
                            message="JavaScript URLs (javascript:) are not allowed",
                            line_number=line_num,
                            element=f'{attr}="{tag.get(attr)}"',
                        )
                    )

    def _check_dangerous_protocols(self, soup, content: str):
        """Check for other dangerous protocols using BeautifulSoup."""
        dangerous_protocols = ["vbscript:", "livescript:", "mocha:", "data:text/html"]

        # Check all tags for href, src, or action attributes with dangerous protocols
        url_attributes = ["href", "src", "action"]
        for attr in url_attributes:
            tags = soup.find_all(attrs={attr: True})
            for tag in tags:
                attr_value = tag.get(attr, "").strip().lower()
                for protocol in dangerous_protocols:
                    if attr_value.startswith(protocol):
                        tag_str = str(tag)[:100]
                        pos = content.find(tag_str[:50])
                        line_num = self._get_line_number(content, pos) if pos != -1 else None

                        self.errors.append(
                            HTMLValidationError(
                                error_type="dangerous_protocol",
                                message=f"Dangerous protocol '{protocol}' is not allowed",
                                line_number=line_num,
                                element=f'{attr}="{tag.get(attr)}"',
                            )
                        )

    def _check_form_actions(self, soup, content: str):
        """Check for forms with external action URLs using BeautifulSoup."""
        forms = soup.find_all("form", attrs={"action": True})

        for form in forms:
            action_url = form.get("action", "").strip()

            # Allow empty actions, "#", or javascript: URLs (client-side handling)
            if not action_url or action_url == "#" or action_url.lower().startswith("javascript:"):
                continue

            # Block forms with external URLs (http://, https://, or protocol-relative //)
            if action_url.startswith(("http://", "https://", "//")):
                form_str = str(form)[:100]
                pos = content.find(form_str[:50])
                line_num = self._get_line_number(content, pos) if pos != -1 else None

                self.errors.append(
                    HTMLValidationError(
                        error_type="external_form_action",
                        message=f"Form with external action '{action_url}' is not allowed. Forms must not submit to external URLs.",
                        line_number=line_num,
                        element=form_str,
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
        "cdn.bokeh.org/bokeh/release/",
        "cdn.jsdelivr.net/npm/three@",
        "cdn.jsdelivr.net/npm/leaflet@",
        "cdn.jsdelivr.net/npm/cytoscape@",
        # Core UI libraries
        "cdn.jsdelivr.net/npm/jquery@",
        "cdnjs.cloudflare.com/ajax/libs/jquery/",
        "cdn.jsdelivr.net/npm/bootstrap@",
        "cdnjs.cloudflare.com/ajax/libs/bootstrap/",
        # Academic-specific libraries
        "cdn.jsdelivr.net/npm/tooltipster@",
        "cdn.jsdelivr.net/npm/pseudocode@",
        "cdn.jsdelivr.net/npm/popper.js@",
        # Aris ecosystem
        "cdn.jsdelivr.net/gh/aris-pub/rsm@",
    ]

    def _check_external_resources(self, soup, content: str):
        """Check for external script and stylesheet resources using BeautifulSoup."""

        # Check for external script tags (http:// or https://)
        # Allow data: URIs since those are self-contained
        # Allow MathJax/KaTeX CDNs since they're essential for math rendering
        scripts = soup.find_all("script", attrs={"src": True})
        for script in scripts:
            src = script.get("src", "")

            # Skip data: URIs (self-contained)
            if src.startswith("data:"):
                continue

            # Only check external URLs
            if src.startswith(("http://", "https://")):
                # Check if URL is from allowed CDN
                if any(allowed in src for allowed in self.ALLOWED_CDN_DOMAINS):
                    continue

                script_str = str(script)[:100]
                pos = content.find(script_str[:50])
                line_num = self._get_line_number(content, pos) if pos != -1 else None

                self.errors.append(
                    HTMLValidationError(
                        error_type="external_script",
                        message=f"External script '{src}' not allowed. Only whitelisted CDNs are permitted (jQuery, D3, Plotly, MathJax, etc. from jsdelivr/cdnjs). Download and inline this resource.",
                        line_number=line_num,
                        element=script_str,
                    )
                )

        # Check for external stylesheet links (http:// or https://)
        # Allow data: URIs since those are self-contained
        # Allow MathJax/KaTeX CDNs since they're essential for math rendering
        links = soup.find_all("link", attrs={"href": True})
        for link in links:
            href = link.get("href", "")

            # Skip data: URIs (self-contained)
            if href.startswith("data:"):
                continue

            # Only check external URLs
            if href.startswith(("http://", "https://")):
                # Check if URL is from allowed CDN
                if any(allowed in href for allowed in self.ALLOWED_CDN_DOMAINS):
                    continue

                link_str = str(link)[:100]
                pos = content.find(link_str[:50])
                line_num = self._get_line_number(content, pos) if pos != -1 else None

                self.errors.append(
                    HTMLValidationError(
                        error_type="external_stylesheet",
                        message=f"External stylesheet '{href}' not allowed. Only whitelisted CDNs are permitted (Google Fonts, Bootstrap, etc. from jsdelivr/cdnjs). Download and inline this resource.",
                        line_number=line_num,
                        element=link_str,
                    )
                )

    def _get_line_number(self, content: str, position: int) -> int:
        """Get line number for a character position in the content (computed on demand)."""
        # For large files (>1MB), skip line number calculation to save memory
        if len(content) > 1024 * 1024:
            return None

        # Only compute line number for errors in smaller files
        return content[:position].count("\n") + 1
