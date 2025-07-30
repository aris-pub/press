"""Test suite for HTML sanitization and XSS prevention."""

from app.security.sanitizer import HTMLSanitizer


class TestHTMLSanitizer:
    """Test HTML sanitization functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.sanitizer = HTMLSanitizer()

    def test_basic_html_preservation(self):
        """Test that basic HTML structure is preserved."""
        html = """
        <html>
            <head><title>Test Document</title></head>
            <body>
                <h1>Hello World</h1>
                <p>This is a test paragraph.</p>
            </body>
        </html>
        """
        sanitized, log = self.sanitizer.sanitize(html)
        assert "<h1>Hello World</h1>" in sanitized
        assert "<p>This is a test paragraph.</p>" in sanitized
        assert "<title>Test Document</title>" in sanitized

    def test_script_preservation(self):
        """Test that script tags are preserved (will be secured with nonces later)."""
        test_cases = [
            # Inline scripts
            '<script>console.log("Hello World")</script>',
            '<SCRIPT>alert("Test")</SCRIPT>',
            '<script type="text/javascript">var x = 1;</script>',
            # Script with attributes
            '<script src="app.js"></script>',
            '<script async defer>console.log("Test")</script>',
        ]

        for html in test_cases:
            sanitized, log = self.sanitizer.sanitize(html)
            assert "<script" in sanitized.lower()
            # Should not have script removal in log
            assert not any(entry["type"] == "script_removed" for entry in log)

    def test_event_handler_removal(self):
        """Test removal of event handlers."""
        test_cases = [
            "<div onclick=\"alert('XSS')\">Click me</div>",
            '<img src="x" onerror="alert(\'XSS\')">',
            "<body onload=\"alert('XSS')\">",
            "<input onfocus=\"alert('XSS')\">",
            '<a href="#" onmouseover="alert(\'XSS\')">Link</a>',
            "<form onsubmit=\"alert('XSS')\">",
        ]

        for html in test_cases:
            sanitized, log = self.sanitizer.sanitize(html)
            assert "onclick" not in sanitized
            assert "onerror" not in sanitized
            assert "onload" not in sanitized
            assert "onfocus" not in sanitized
            assert "onmouseover" not in sanitized
            assert "onsubmit" not in sanitized
            assert any(entry["type"] == "event_handler_removed" for entry in log)

    def test_javascript_url_removal(self):
        """Test removal of javascript: URLs."""
        test_cases = [
            "<a href=\"javascript:alert('XSS')\">Click</a>",
            "<a href=\"JAVASCRIPT:alert('XSS')\">Click</a>",
            "<a href=\" javascript:alert('XSS')\">Click</a>",
            "<img src=\"javascript:alert('XSS')\">",
            "<iframe src=\"javascript:alert('XSS')\"></iframe>",
        ]

        for html in test_cases:
            sanitized, log = self.sanitizer.sanitize(html)
            assert "javascript:" not in sanitized.lower()
            assert any(entry["type"] == "javascript_url_removed" for entry in log)

    def test_css_expression_removal(self):
        """Test removal of CSS expressions."""
        test_cases = [
            "<div style=\"width: expression(alert('XSS'))\">Test</div>",
            "<style>body { background: expression(alert('XSS')); }</style>",
            '<p style="height: expression(document.body.clientHeight)">Test</p>',
        ]

        for html in test_cases:
            sanitized, log = self.sanitizer.sanitize(html)
            assert "expression(" not in sanitized.lower()
            assert any(entry["type"] == "css_expression_removed" for entry in log)

    def test_css_javascript_url_removal(self):
        """Test removal of javascript: in CSS."""
        test_cases = [
            "<div style=\"background: url(javascript:alert('XSS'))\">Test</div>",
            "<style>body { background-image: url(\"javascript:alert('XSS')\"); }</style>",
        ]

        for html in test_cases:
            sanitized, log = self.sanitizer.sanitize(html)
            assert "javascript:" not in sanitized.lower()

    def test_allowed_tags_preservation(self):
        """Test that allowed tags are preserved."""
        html = """
        <article>
            <header><h1>Title</h1></header>
            <main>
                <p>Paragraph with <strong>bold</strong> and <em>italic</em>.</p>
                <ul>
                    <li>Item 1</li>
                    <li>Item 2</li>
                </ul>
                <table>
                    <tr><th>Header</th><td>Data</td></tr>
                </table>
                <blockquote>Quote</blockquote>
                <pre><code>Code block</code></pre>
            </main>
            <footer>Footer content</footer>
        </article>
        """
        sanitized, log = self.sanitizer.sanitize(html)

        # Check all tags are preserved
        for tag in [
            "article",
            "header",
            "h1",
            "main",
            "p",
            "strong",
            "em",
            "ul",
            "li",
            "table",
            "tr",
            "th",
            "td",
            "blockquote",
            "pre",
            "code",
            "footer",
        ]:
            assert f"<{tag}" in sanitized or f"</{tag}>" in sanitized

    def test_allowed_attributes_preservation(self):
        """Test that allowed attributes are preserved."""
        html = """
        <div id="main" class="container" title="Main content">
            <a href="https://example.com" target="_blank" rel="noopener">Link</a>
            <img src="image.jpg" alt="Description" width="100" height="100">
            <time datetime="2024-01-01">January 1, 2024</time>
        </div>
        """
        sanitized, log = self.sanitizer.sanitize(html)

        # Check attributes are preserved
        assert 'id="main"' in sanitized
        assert 'class="container"' in sanitized
        assert 'href="https://example.com"' in sanitized
        assert 'alt="Description"' in sanitized
        assert 'datetime="2024-01-01"' in sanitized

    def test_dangerous_tags_removal(self):
        """Test removal of dangerous tags."""
        test_cases = [
            '<iframe src="evil.html"></iframe>',
            '<object data="evil.swf"></object>',
            '<embed src="evil.swf">',
            '<applet code="Evil.class"></applet>',
            '<form action="evil.php"><input name="data"></form>',
            '<meta http-equiv="refresh" content="0;url=evil.html">',
            '<base href="https://evil.com/">',
        ]

        for html in test_cases:
            sanitized, log = self.sanitizer.sanitize(html)
            for tag in ["iframe", "object", "embed", "applet", "form", "base"]:
                assert f"<{tag}" not in sanitized.lower()

    def test_css_property_filtering(self):
        """Test CSS property filtering in style attributes."""
        html = """
        <div style="color: red; position: fixed; behavior: url(evil.htc); 
                    margin: 10px; -moz-binding: url(evil.xml);">
            Test
        </div>
        """
        sanitized, log = self.sanitizer.sanitize(html)

        # Allowed properties should be preserved
        assert "color:" in sanitized or "color :" in sanitized
        assert "margin:" in sanitized or "margin :" in sanitized

        # Dangerous properties should be removed
        assert "position: fixed" not in sanitized
        assert "behavior:" not in sanitized
        assert "-moz-binding:" not in sanitized

    def test_external_link_rel_attribute(self):
        """Test that external links get rel="noopener noreferrer"."""
        html = """
        <a href="https://example.com">External link</a>
        <a href="https://example.com" rel="author">Author link</a>
        <a href="/internal">Internal link</a>
        """
        sanitized, log = self.sanitizer.sanitize(html)

        # External links should have security attributes
        assert 'rel="noopener noreferrer"' in sanitized

    def test_data_url_images_allowed(self):
        """Test that data: URLs for images are allowed in CSS."""
        html = """
        <div style="background-image: url(data:image/png;base64,iVBORw0KG);">
            Test
        </div>
        """
        sanitized, log = self.sanitizer.sanitize(html)
        assert "data:image/png" in sanitized

    def test_complex_xss_attempts(self):
        """Test complex XSS attempts."""
        test_cases = [
            # SVG-based XSS
            "<svg onload=\"alert('XSS')\"></svg>",
            '<svg><script>alert("XSS")</script></svg>',
            # IMG-based XSS
            '<img src=x onerror=alert("XSS")>',
            '<img src="x" onerror="alert(\'XSS\')">',
            # Style-based XSS
            '<style>@import "http://evil.com/xss.css";</style>',
            '<link rel="stylesheet" href="javascript:alert(\'XSS\')">',
            # Encoded XSS attempts
            "<a href=\"java&#115;cript:alert('XSS')\">Click</a>",
            '<img src="&#106;&#97;&#118;&#97;&#115;&#99;&#114;&#105;&#112;&#116;&#58;">',
        ]

        for html in test_cases:
            sanitized, log = self.sanitizer.sanitize(html)
            # Scripts are preserved but event handlers and js URLs are removed
            if "<script>" in html:
                assert "<script>" in sanitized  # Scripts should be preserved
            else:
                assert "alert(" not in sanitized  # Non-script alerts should be removed
            assert "javascript:" not in sanitized.lower()

    def test_extract_external_resources(self):
        """Test extraction of external resources."""
        html = """
        <html>
            <head>
                <link rel="stylesheet" href="https://example.com/style.css">
            </head>
            <body>
                <img src="https://example.com/image.jpg" alt="Image">
                <a href="https://example.com/page">Link</a>
                <img src="/local/image.png" alt="Local">
            </body>
        </html>
        """
        resources = self.sanitizer.extract_external_resources(html)

        assert len(resources) == 3
        assert any(r["type"] == "stylesheet" and "style.css" in r["url"] for r in resources)
        assert any(r["type"] == "image" and "image.jpg" in r["url"] for r in resources)
        assert any(r["type"] == "link" and "/page" in r["url"] for r in resources)

    def test_scientific_content_preservation(self):
        """Test that scientific HTML elements are preserved."""
        html = """
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
        </article>
        """
        sanitized, log = self.sanitizer.sanitize(html)

        # Check scientific elements are preserved
        for tag in [
            "sup",
            "sub",
            "figure",
            "figcaption",
            "caption",
            "thead",
            "tbody",
            "abbr",
            "dfn",
            "cite",
        ]:
            assert f"<{tag}" in sanitized or f"</{tag}>" in sanitized
