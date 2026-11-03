"""HTML validation module that rejects dangerous content instead of sanitizing."""

import posixpath
import re
from typing import Dict, List, Optional, Set, Tuple
from urllib.parse import unquote, urlparse

from bs4 import BeautifulSoup
import tinycss2


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

    # Allowed iframe embed domains (src must start with one of these)
    ALLOWED_IFRAME_DOMAINS = [
        "https://www.youtube.com/embed/",
        "https://youtube.com/embed/",
        "https://player.vimeo.com/video/",
    ]

    # Tags that are completely forbidden
    FORBIDDEN_TAGS = [
        # "script" removed - now allowed, controlled by nonce system
        # "iframe" removed - now allowed for whitelisted embed domains (YouTube, Vimeo)
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

    # CSS is checked as tokens (tinycss2), never as substrings, so words in comments,
    # strings, class names and font names do not trip the checks, and CSS escapes
    # (\65 xpression) and comments (expression/**/() cannot hide the real thing.
    FORBIDDEN_CSS_FUNCTIONS = {"expression"}  # IE-specific CSS expressions (XSS vector)
    FORBIDDEN_CSS_DECLARATIONS = {"-moz-binding", "behavior"}  # old Firefox/IE code loading
    FORBIDDEN_CSS_URL_SCHEMES = (
        "javascript:",
        "vbscript:",
        "livescript:",
        "mocha:",
        "data:text/html",
    )

    def __init__(self):
        self.errors: List[HTMLValidationError] = []
        self._archive_files: Optional[Set[str]] = None
        self._html_path: str = ""

    def validate(
        self,
        html_content: str,
        archive_files: Optional[Set[str]] = None,
        html_path: str = "",
    ) -> Tuple[bool, List[Dict]]:
        """
        Validate HTML content and return validation results.

        Args:
            html_content: The HTML content to validate
            archive_files: For zip uploads, the relative paths of every file in the
                archive. None for single-file uploads, where a local CSS @import has
                nothing to point at and stays rejected.
            html_path: Path of this HTML file inside the archive, used to resolve
                relative @import URLs the way the browser will.

        Returns:
            Tuple of (is_valid, list_of_error_dicts)
        """
        self.errors = []
        self._archive_files = archive_files
        self._html_path = html_path

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
        self._check_iframes(soup, html_content)
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

    def _check_iframes(self, soup, content: str):
        """Check iframes — allow only whitelisted embed domains."""
        for tag in soup.find_all("iframe"):
            src = tag.get("src", "")
            if tag.get("srcdoc"):
                tag_str = str(tag)[:100]
                pos = content.find(tag_str[:50])
                line_num = self._get_line_number(content, pos) if pos != -1 else None
                self.errors.append(
                    HTMLValidationError(
                        error_type="forbidden_iframe",
                        message="Iframe with srcdoc attribute is not allowed",
                        line_number=line_num,
                        element=tag_str,
                    )
                )
                continue
            if not any(src.startswith(domain) for domain in self.ALLOWED_IFRAME_DOMAINS):
                tag_str = str(tag)[:100]
                pos = content.find(tag_str[:50])
                line_num = self._get_line_number(content, pos) if pos != -1 else None
                self.errors.append(
                    HTMLValidationError(
                        error_type="forbidden_iframe",
                        message=f"Iframe source '{src}' not allowed. Only YouTube and Vimeo embeds are permitted.",
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
        """Validate CSS content for dangerous constructs, using a real CSS tokenizer."""
        # Rule and block contents are walked as raw tokens, not parsed declarations:
        # tinycss2 turns anything that is not a valid declaration into an opaque
        # parse error, which would hide its tokens from these checks.
        if context == "inline style":
            nodes = tinycss2.parse_component_value_list(css_content, skip_comments=True)
        else:
            nodes = tinycss2.parse_stylesheet(
                css_content, skip_comments=True, skip_whitespace=False
            )
        element = css_content[:100] + "..." if len(css_content) > 100 else css_content
        self._walk_css(nodes, line_num, context, element)

    def _walk_css(self, nodes, line_num: int, context: str, element: str):
        """Recursively check a list of tinycss2 nodes."""
        meaningful = [n for n in nodes if n.type not in ("whitespace", "comment")]
        for i, node in enumerate(meaningful):
            following = meaningful[i + 1] if i + 1 < len(meaningful) else None
            kind = node.type

            if kind == "at-rule":
                if node.lower_at_keyword == "import":
                    self._check_css_import(node, line_num, context, element)
                self._walk_css(node.prelude, line_num, context, element)
                if node.content is not None:
                    self._walk_css(self._raw(node.content), line_num, context, element)
            elif kind == "qualified-rule":
                self._walk_css(node.prelude, line_num, context, element)
                self._walk_css(self._raw(node.content), line_num, context, element)
            elif kind == "function":
                if node.lower_name in self.FORBIDDEN_CSS_FUNCTIONS:
                    self._css_expression_error(context, line_num, element)
                elif node.lower_name in ("url", "src"):
                    for arg in node.arguments:
                        if arg.type == "string":
                            self._check_css_url_value(arg.value, line_num, context, element)
                self._walk_css(node.arguments, line_num, context, element)
            elif kind == "url":
                self._check_css_url_value(node.value, line_num, context, element)
            elif kind == "ident":
                # "expression/**/(" tokenizes as an ident then a () block, not a function.
                if (
                    node.lower_value in self.FORBIDDEN_CSS_FUNCTIONS
                    and following is not None
                    and following.type == "() block"
                ):
                    self._css_expression_error(context, line_num, element)
                # Declarations are seen as raw tokens: a forbidden name followed by ":".
                if (
                    node.lower_value in self.FORBIDDEN_CSS_DECLARATIONS
                    and following is not None
                    and following.type == "literal"
                    and following.value == ":"
                ):
                    self._css_error(
                        "dangerous_css",
                        f"Dangerous CSS property '{node.lower_value}' found in {context}",
                        line_num,
                        element,
                    )
            elif kind in ("() block", "[] block", "{} block"):
                self._walk_css(node.content, line_num, context, element)
            elif kind == "error":
                # A malformed unquoted url(), e.g. url(javascript:alert(1)). Browsers do
                # not load it, but its contents are hidden from the scheme check, so
                # fail closed. Other parse errors are junk browsers drop.
                if node.kind == "bad-url":
                    self._css_error(
                        "dangerous_css",
                        f"Malformed CSS url() found in {context} - quote the URL",
                        line_num,
                        element,
                    )

    @staticmethod
    def _raw(tokens):
        """Component values with comments removed, as the browser sees them."""
        return [t for t in tokens if t.type != "comment"]

    def _check_css_url_value(self, value: str, line_num: int, context: str, element: str):
        """Reject url() values that use a script scheme."""
        # Fail closed on anything a browser might normalise into a script scheme:
        # comment markers, whitespace and control characters are removed first.
        normalized = re.sub(r"/\*.*?\*/", "", value, flags=re.S)
        normalized = re.sub(r"[\s\x00-\x1f]", "", normalized).lower()
        if normalized.startswith(self.FORBIDDEN_CSS_URL_SCHEMES):
            self._css_error(
                "dangerous_css",
                f"Script URL in CSS url() found in {context} - not allowed",
                line_num,
                element,
            )

    def _check_css_import(self, rule, line_num: int, context: str, element: str):
        """Check one @import rule. Every @import is checked, not just the first."""
        target = None
        for token in rule.prelude:
            if token.type in ("whitespace", "comment"):
                continue
            if token.type == "url":
                target = token.value
            elif token.type == "string":
                target = token.value
            elif token.type == "function" and token.lower_name == "url":
                strings = [a.value for a in token.arguments if a.type == "string"]
                target = strings[0] if strings else None
            break  # only the first token names the file; layer()/media follow it

        if target is None:
            self._css_error(
                "css_import",
                f"CSS @import without a readable URL found in {context} - not allowed",
                line_num,
                element,
            )
            return

        stripped = target.strip()
        if stripped.lower().startswith(("http://", "https://")):
            if not self._is_allowed_cdn(stripped):
                self._css_error(
                    "css_import_external",
                    f"CSS @import with external URL found in {context} - not allowed. Papers must be self-contained (MathJax/KaTeX CDNs are allowed).",
                    line_num,
                    element,
                )
            return

        if self._archive_files is None:
            self._css_error(
                "css_import",
                f"CSS @import of a local file found in {context} - not allowed in a single HTML file. Upload a zip that contains the imported stylesheet.",
                line_num,
                element,
            )
            return

        problem = self._local_import_problem(stripped)
        if problem:
            self._css_error(
                "css_import_invalid",
                f"CSS @import of '{target}' in {context} - {problem}",
                line_num,
                element,
            )

    def _local_import_problem(self, target: str) -> Optional[str]:
        """Return why a relative @import target is not allowed, or None if it is."""
        # Cache-busting suffixes are common and do not change which file loads.
        path = re.split(r"[?#]", target, maxsplit=1)[0]
        decoded = unquote(path)
        if not decoded:
            return "empty path"
        if any(ord(c) < 0x20 for c in decoded) or "\\" in decoded:
            return "path contains control characters or backslashes"
        if decoded.startswith("/"):
            return "absolute and protocol-relative paths are not allowed"
        if ":" in decoded.split("/", 1)[0]:
            return "URL schemes are not allowed"
        if ".." in decoded.split("/"):
            return "paths containing '..' are not allowed"
        base = posixpath.dirname(self._html_path)
        resolved = posixpath.normpath(posixpath.join(base, decoded))
        if resolved.startswith("..") or resolved.startswith("/"):
            return "path points outside the archive"
        if not resolved.lower().endswith(".css"):
            return "only .css files can be imported"
        if resolved not in self._archive_files:
            return "file not found in the archive"
        return None

    def _css_expression_error(self, context: str, line_num: int, element: str):
        self._css_error(
            "css_expression",
            f"CSS expression() function found in {context} - not allowed",
            line_num,
            element,
        )

    def _css_error(self, error_type: str, message: str, line_num: int, element: str):
        self.errors.append(
            HTMLValidationError(
                error_type=error_type,
                message=message,
                line_number=line_num,
                element=element,
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

    # Allowed CDN origins: (hostname, path_prefix_or_None)
    # hostname is matched exactly; path_prefix constrains the URL path if set
    ALLOWED_CDN_RULES = [
        # Major CDN platforms
        ("cdn.jsdelivr.net", None),
        ("cdnjs.cloudflare.com", "/ajax/libs/"),
        ("unpkg.com", None),
        # Fonts
        ("fonts.googleapis.com", None),
        ("fonts.gstatic.com", None),
        # Visualization-specific CDNs
        ("cdn.plot.ly", None),
        ("cdn.bokeh.org", None),
        # UI frameworks
        ("code.getmdl.io", None),
    ]

    @classmethod
    def _is_allowed_cdn(cls, url: str) -> bool:
        """Check if a URL is from an allowed CDN using proper URL parsing."""
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https"):
            return False
        hostname = parsed.hostname
        if hostname is None:
            return False
        for allowed_host, path_prefix in cls.ALLOWED_CDN_RULES:
            if hostname == allowed_host:
                if path_prefix is None:
                    return True
                if parsed.path.startswith(path_prefix):
                    return True
        return False

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
                if self._is_allowed_cdn(src):
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
        # Only flag <link> tags that actually load a stylesheet — skip canonical,
        # icon, alternate, dns-prefetch, preconnect, manifest, etc.
        links = soup.find_all("link", attrs={"href": True})
        for link in links:
            rel = link.get("rel") or []
            if isinstance(rel, str):
                rel_tokens = {rel.lower()}
            else:
                rel_tokens = {r.lower() for r in rel}

            as_attr = (link.get("as") or "").lower()
            is_stylesheet = "stylesheet" in rel_tokens or (
                "preload" in rel_tokens and as_attr == "style"
            )
            if not is_stylesheet:
                continue

            href = link.get("href", "")

            # Skip data: URIs (self-contained)
            if href.startswith("data:"):
                continue

            # Only check external URLs
            if href.startswith(("http://", "https://")):
                # Check if URL is from allowed CDN
                if self._is_allowed_cdn(href):
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
