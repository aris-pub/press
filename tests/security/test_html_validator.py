"""Test suite for HTML validation that rejects dangerous content."""

from app.security.html_validator import HTMLValidator


class TestHTMLValidator:
    """Test HTML validation functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.validator = HTMLValidator()

    def test_safe_html_passes(self):
        """Test that safe HTML passes validation."""
        safe_html = """
        <!DOCTYPE html>
        <html>
            <head><title>Safe Document</title></head>
            <body>
                <h1>Research Paper</h1>
                <p>This is safe content with <strong>formatting</strong>.</p>
                <div class="container">
                    <img src="chart.png" alt="Results">
                    <a href="https://example.com">Reference</a>
                </div>
                <table>
                    <tr><th>Variable</th><td>Value</td></tr>
                </table>
            </body>
        </html>
        """
        is_valid, errors = self.validator.validate(safe_html)
        assert is_valid
        assert len(errors) == 0

    def test_script_tags_allowed(self):
        """Test that script tags are now allowed (controlled by nonce system)."""
        html_with_script = """
        <html>
            <body>
                <h1>Title</h1>
                <script>console.log('Safe user script');</script>
                <p>Content</p>
            </body>
        </html>
        """
        is_valid, errors = self.validator.validate(html_with_script)
        assert is_valid, f"Script tags should be allowed now. Errors: {errors}"
        assert len(errors) == 0

    def test_event_handlers_rejected(self):
        """Test that event handlers are rejected."""
        test_cases = [
            "<div onclick=\"alert('xss')\">Click me</div>",
            '<img src="x" onerror="alert(\'xss\')">',
            '<body onload="malicious()">',
            '<input onfocus="evil()">',
            '<a href="#" onmouseover="hack()">Link</a>',
        ]

        for html in test_cases:
            is_valid, errors = self.validator.validate(html)
            assert not is_valid, f"Should reject: {html}"
            assert any(error["type"] == "forbidden_attribute" for error in errors)

    def test_javascript_urls_rejected(self):
        """Test that javascript: URLs are rejected."""
        test_cases = [
            "<a href=\"javascript:alert('xss')\">Click</a>",
            "<a href=\"JAVASCRIPT:alert('xss')\">Click</a>",
            "<img src=\"javascript:alert('xss')\">",
            '<form action="javascript:evil()">',
        ]

        for html in test_cases:
            is_valid, errors = self.validator.validate(html)
            assert not is_valid, f"Should reject: {html}"
            assert any(error["type"] == "javascript_url" for error in errors)

    def test_dangerous_css_rejected(self):
        """Test that dangerous CSS is rejected."""
        test_cases = [
            '<div style="behavior: url(evil.htc);">IE hack</div>',
            "<div style=\"expression(alert('xss'));\">Expression</div>",
            "<style>body { -moz-binding: url(evil.xml); }</style>",
            '<style>@import url("evil.css");</style>',
        ]

        for html in test_cases:
            is_valid, errors = self.validator.validate(html)
            assert not is_valid, f"Should reject: {html}"
            assert any(
                error["type"] in ["dangerous_css", "css_expression", "css_import"]
                for error in errors
            )

    def test_forbidden_tags_rejected(self):
        """Test that all forbidden tags are rejected."""
        forbidden_tags = [
            "iframe",
            "frame",
            "frameset",
            "object",
            "embed",
            "applet",
            "form",
            "base",
        ]

        for tag in forbidden_tags:
            html = f"<{tag}>content</{tag}>"
            is_valid, errors = self.validator.validate(html)
            assert not is_valid, f"Should reject tag: {tag}"
            assert any(error["type"] == "forbidden_tag" for error in errors)

    def test_interactive_elements_allowed(self):
        """Test that interactive elements (button, input, select, textarea) are allowed for research papers."""
        interactive_html = """
        <html>
            <body>
                <button onclick="runSimulation()">Run Simulation</button>
                <input type="range" min="0" max="100" value="50">
                <select><option>Option 1</option></select>
                <textarea>Notes</textarea>
            </body>
        </html>
        """
        is_valid, errors = self.validator.validate(interactive_html)
        # Should only fail on onclick, not on the tags themselves
        assert not is_valid, "Should reject onclick attribute"
        assert any(error["type"] == "forbidden_attribute" for error in errors)
        # But should not complain about button/input/select/textarea tags
        forbidden_tag_errors = [e for e in errors if e["type"] == "forbidden_tag"]
        assert len(forbidden_tag_errors) == 0, (
            "Should not reject button/input/select/textarea tags"
        )

    def test_dangerous_protocols_rejected(self):
        """Test that dangerous protocols are rejected."""
        test_cases = [
            "<a href=\"vbscript:msgbox('xss')\">Link</a>",
            "<a href=\"livescript:alert('xss')\">Link</a>",
            "<a href=\"data:text/html,<script>alert('xss')</script>\">Link</a>",
        ]

        for html in test_cases:
            is_valid, errors = self.validator.validate(html)
            assert not is_valid, f"Should reject: {html}"
            assert any(error["type"] == "dangerous_protocol" for error in errors)

    def test_line_number_reporting(self):
        """Test that line numbers are correctly reported."""
        html = """<html>
<body>
<h1>Title</h1>
<iframe src="evil.html"></iframe>
<p>More content</p>
</body>
</html>"""
        is_valid, errors = self.validator.validate(html)
        assert not is_valid
        assert len(errors) == 1
        assert errors[0]["line_number"] == 4  # iframe is on line 4

    def test_multiple_errors_reported(self):
        """Test that multiple errors are all reported."""
        html = """
        <div onclick="evil()">Click</div>
        <a href="javascript:alert('xss2')">Link</a>
        <iframe src="evil.html"></iframe>
        """
        is_valid, errors = self.validator.validate(html)
        assert not is_valid
        assert len(errors) == 3  # Should find all 3 issues (script tags are now allowed)

        error_types = [error["type"] for error in errors]
        assert "forbidden_tag" in error_types  # iframe only
        assert "forbidden_attribute" in error_types  # onclick
        assert "javascript_url" in error_types  # javascript: URL

    def test_safe_css_allowed(self):
        """Test that safe CSS properties are allowed."""
        safe_html = """
        <div style="color: red; margin: 10px; font-size: 14px; position: relative;">
            Safe styling including position
        </div>
        <style>
            .safe { 
                background-color: blue; 
                padding: 5px;
                border-radius: 3px;
                position: absolute;
                top: 10px;
            }
        </style>
        """
        is_valid, errors = self.validator.validate(safe_html)
        assert is_valid, f"Safe CSS should be allowed. Errors: {errors}"

    def test_data_image_urls_allowed(self):
        """Test that data: image URLs are allowed."""
        html = '<img src="data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8/5+hHgAHggJ/PchI7wAAAABJRU5ErkJggg==" alt="test">'
        is_valid, errors = self.validator.validate(html)
        assert is_valid, "Data image URLs should be allowed"

    def test_https_links_allowed(self):
        """Test that HTTPS links are allowed."""
        html = '<a href="https://example.com/research">Safe external link</a>'
        is_valid, errors = self.validator.validate(html)
        assert is_valid, "HTTPS links should be allowed"

    def test_scientific_content_allowed(self):
        """Test that scientific HTML elements are allowed."""
        scientific_html = """
        <article>
            <h1>Research Title</h1>
            <p>Abstract with <sup>superscript</sup> and <sub>subscript</sub>.</p>
            <figure>
                <img src="graph.png" alt="Results">
                <figcaption>Figure 1: Experimental results</figcaption>
            </figure>
            <table>
                <caption>Table 1: Data</caption>
                <thead>
                    <tr><th>Variable</th><th>Value</th></tr>
                </thead>
                <tbody>
                    <tr><td>x</td><td>42</td></tr>
                </tbody>
            </table>
            <abbr title="Artificial Intelligence">AI</abbr>
            <dfn>Definition</dfn>
            <cite>Reference</cite>
            <pre><code>code_example()</code></pre>
        </article>
        """
        is_valid, errors = self.validator.validate(scientific_html)
        assert is_valid, f"Scientific content should be allowed. Errors: {errors}"

    def test_meta_tags_validation(self):
        """Test that meta tags are properly validated."""
        # Safe meta tags should be allowed
        safe_html = """
        <html>
            <head>
                <meta name="author" content="Dr. Smith">
                <meta name="description" content="Research paper">
                <meta name="keywords" content="science, research">
                <meta charset="utf-8">
            </head>
            <body><p>Content</p></body>
        </html>
        """
        is_valid, errors = self.validator.validate(safe_html)
        assert is_valid, f"Safe meta tags should be allowed. Errors: {errors}"

        # Dangerous meta tags should be rejected
        dangerous_html = '<meta http-equiv="refresh" content="0;url=evil.com">'
        is_valid, errors = self.validator.validate(dangerous_html)
        assert not is_valid
        assert any(error["type"] == "dangerous_meta" for error in errors)

        # Unknown meta names should be rejected
        unknown_html = '<meta name="evil-tracker" content="malicious">'
        is_valid, errors = self.validator.validate(unknown_html)
        assert not is_valid
        assert any(error["type"] == "forbidden_meta" for error in errors)

    def test_error_details_complete(self):
        """Test that error objects contain all expected details."""
        html = '<iframe src="evil.html"></iframe>'
        is_valid, errors = self.validator.validate(html)

        assert not is_valid
        assert len(errors) == 1

        error = errors[0]
        assert "type" in error
        assert "message" in error
        assert "line_number" in error
        assert "element" in error

        assert error["type"] == "forbidden_tag"
        assert "iframe" in error["message"]
        assert isinstance(error["line_number"], int)
        assert error["element"] is not None
