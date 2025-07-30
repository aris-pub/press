"""Test suite for content validation and spam detection."""

from app.security.validation import ContentValidator


class TestContentValidator:
    """Test content validation functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.validator = ContentValidator(max_external_links=10, min_word_count=100)

    def test_valid_academic_content(self):
        """Test validation of valid academic content."""
        html = """
        <html>
            <head><title>Research Paper</title></head>
            <body>
                <h1>A Study on Machine Learning</h1>
                <p>This paper presents a comprehensive study on machine learning algorithms
                and their applications in various domains. We analyze different approaches
                and compare their effectiveness. Our research contributes to the understanding
                of algorithmic performance in real-world scenarios. The methodology involves
                extensive experimentation with diverse datasets. Results show significant
                improvements in accuracy and efficiency. This work has implications for
                future research in artificial intelligence and data science applications.
                We conducted thorough evaluation of multiple algorithms including neural
                networks, decision trees, and ensemble methods. The experimental design
                incorporated cross-validation techniques to ensure robust performance
                assessment. Statistical analysis revealed significant differences between
                methods. Future work will explore additional optimization strategies and
                applications in emerging domains such as natural language processing.</p>
            </body>
        </html>
        """
        is_valid, errors = self.validator.validate(html)
        assert is_valid
        assert len(errors) == 0

    def test_excessive_external_links(self):
        """Test detection of excessive external links."""
        html = "<body>"
        for i in range(15):
            html += f'<a href="https://example{i}.com">Link {i}</a>'
        html += "</body>"

        is_valid, errors = self.validator.validate(html)
        assert not is_valid
        assert any(e["type"] == "excessive_links" for e in errors)
        assert any("15 external links" in e["message"] for e in errors)

    def test_keyword_stuffing_detection(self):
        """Test detection of keyword stuffing."""
        # Create content with excessive repetition
        repeated_word = "algorithm"
        content = f"<p>{repeated_word} " * 100 + "and some other words.</p>"
        html = f"<body>{content}</body>"

        is_valid, errors = self.validator.validate(html)
        assert not is_valid
        assert any(e["type"] == "keyword_stuffing" for e in errors)
        assert any(repeated_word in e["message"] for e in errors)

    def test_missing_title(self):
        """Test detection of missing title."""
        html = """
        <body>
            <p>Content without title or h1.</p>
        </body>
        """
        is_valid, errors = self.validator.validate(html)
        assert not is_valid
        assert any(e["type"] == "missing_title" for e in errors)

    def test_title_in_h1_accepted(self):
        """Test that h1 is accepted as title."""
        html = """
        <body>
            <h1>Research Title</h1>
            <p>This is the content of the research paper with sufficient words
            to meet the minimum word count requirement. The paper discusses
            various topics in detail with comprehensive analysis and results.</p>
        </body>
        """
        is_valid, errors = self.validator.validate(html)
        # Should only fail on word count, not title
        assert not any(e["type"] == "missing_title" for e in errors)

    def test_missing_content_structure(self):
        """Test detection of missing content structure."""
        html = """
        <html>
            <head><title>Title</title></head>
            <body>
                Just plain text without any structure.
            </body>
        </html>
        """
        is_valid, errors = self.validator.validate(html)
        assert not is_valid
        assert any(e["type"] == "missing_content_structure" for e in errors)

    def test_spam_keywords_detection(self):
        """Test detection of spam keywords."""
        html = """
        <body>
            <h1>Buy Now!</h1>
            <p>Limited offer! Click here for guaranteed weight loss results.
            Act now and win a prize! This risk free opportunity won't last.
            Visit our casino for more chances to win the lottery!</p>
        </body>
        """
        is_valid, errors = self.validator.validate(html)
        assert not is_valid
        assert any(e["type"] == "spam_keywords" for e in errors)
        assert any("spam keywords" in e["message"] for e in errors)

    def test_insufficient_word_count(self):
        """Test detection of insufficient content."""
        html = """
        <body>
            <h1>Title</h1>
            <p>Very short content.</p>
        </body>
        """
        is_valid, errors = self.validator.validate(html)
        assert not is_valid
        assert any(e["type"] == "insufficient_content" for e in errors)
        assert any("minimum required is 100" in e["message"] for e in errors)

    def test_content_metrics_calculation(self):
        """Test calculation of content metrics."""
        html = """
        <article>
            <h1>Main Title</h1>
            <h2>Subtitle</h2>
            <p>First paragraph with substantial content about research methodology
            and experimental design. This section describes the approach used
            in our comprehensive study of machine learning algorithms and their
            performance characteristics across different domains and datasets.</p>
            <p>Second paragraph with detailed analysis of results and findings.
            We present statistical evidence supporting our hypotheses and discuss
            the implications of our research for future developments in artificial
            intelligence and automated systems. The results demonstrate significant
            improvements over existing methods and provide valuable insights for
            practitioners and researchers working in related fields.</p>
            <ul>
                <li>Item 1</li>
                <li>Item 2</li>
            </ul>
            <table>
                <tr><td>Data</td></tr>
            </table>
            <a href="https://example.com">Link</a>
            <img src="image.jpg" alt="Image">
            <pre>Code block</pre>
        </article>
        """
        metrics = self.validator.calculate_content_metrics(html)

        assert metrics["paragraph_count"] == 2
        assert metrics["heading_count"] == 2
        assert metrics["link_count"] == 1
        assert metrics["image_count"] == 1
        assert metrics["table_count"] == 1
        assert metrics["list_count"] == 1
        assert metrics["code_block_count"] == 1
        assert metrics["word_count"] > 0
        assert metrics["char_count"] > 0

    def test_valid_content_with_warnings(self):
        """Test content that has warnings but is still valid."""
        html = """
        <html>
            <head><title>Research Paper</title></head>
            <body>
                <h1>A Study on Online Marketing</h1>
                <p>This academic paper examines online marketing strategies.
                While some might guarantee results, our research shows that
                success depends on multiple factors. We analyze various approaches
                including social media, email campaigns, and content marketing.
                The methodology involves surveying businesses and analyzing their
                performance metrics over time. Results indicate that integrated
                strategies perform better than single-channel approaches.
                This research contributes to understanding digital marketing
                effectiveness in modern business environments. Our comprehensive
                analysis covers both traditional and digital marketing channels,
                examining their effectiveness across different industries and
                target demographics. We conducted extensive surveys with marketing
                professionals and analyzed performance data from multiple campaigns
                over a two-year period. The findings provide valuable insights
                for practitioners seeking to optimize their marketing strategies.</p>
                <a href="https://example1.com">Reference 1</a>
                <a href="https://example2.com">Reference 2</a>
            </body>
        </html>
        """
        is_valid, errors = self.validator.validate(html)

        # Should have warning for spam keyword "guarantee" but still be valid
        warnings = [e for e in errors if e.get("severity") == "warning"]
        assert len(warnings) > 0

        # But should still be valid if only warnings
        blocking_errors = [e for e in errors if e.get("severity") == "error"]
        assert len(blocking_errors) == 0

    def test_edge_cases(self):
        """Test various edge cases."""
        # Empty content
        is_valid, errors = self.validator.validate("")
        assert not is_valid

        # Only whitespace
        is_valid, errors = self.validator.validate("   \n\t   ")
        assert not is_valid

        # Minimal valid content with diverse vocabulary (100 unique words)
        words = [
            "research",
            "study",
            "analysis",
            "method",
            "result",
            "finding",
            "data",
            "experiment",
            "conclusion",
            "hypothesis",
            "investigation",
            "approach",
            "technique",
            "procedure",
            "outcome",
            "discovery",
            "evidence",
            "theory",
            "model",
            "framework",
            "evaluation",
            "assessment",
            "examination",
            "observation",
            "measurement",
            "calculation",
            "comparison",
            "correlation",
            "significance",
            "interpretation",
            "discussion",
            "implications",
            "applications",
            "methodology",
            "systematic",
            "comprehensive",
            "detailed",
            "extensive",
            "thorough",
            "rigorous",
            "innovative",
            "novel",
            "significant",
            "important",
            "crucial",
            "fundamental",
            "essential",
            "primary",
            "secondary",
            "tertiary",
            "initial",
            "final",
            "preliminary",
            "advanced",
            "sophisticated",
            "complex",
            "simple",
            "accurate",
            "precise",
            "effective",
            "efficient",
            "reliable",
            "valid",
            "statistical",
            "mathematical",
            "computational",
            "algorithmic",
            "empirical",
            "theoretical",
            "practical",
            "applied",
            "basic",
            "experimental",
            "observational",
            "longitudinal",
            "cross",
            "sectional",
            "quantitative",
            "qualitative",
            "mixed",
            "methods",
            "design",
            "sample",
            "population",
            "variables",
            "control",
            "treatment",
            "intervention",
            "baseline",
            "followup",
            "outcome",
            "measure",
            "instrument",
            "protocol",
            "standard",
            "guideline",
            "criteria",
            "threshold",
            "benchmark",
            "indicator",
            "metric",
            "parameter",
            "coefficient",
            "regression",
            "correlation",
            "association",
            "relationship",
        ]
        minimal_html = f"""
        <html>
            <head><title>Research</title></head>
            <body><p>{" ".join(words)}</p></body>
        </html>
        """
        is_valid, errors = self.validator.validate(minimal_html)
        assert is_valid

    def test_custom_thresholds(self):
        """Test validator with custom thresholds."""
        # Create validator with strict settings
        strict_validator = ContentValidator(max_external_links=2, min_word_count=500)

        html = """
        <body>
            <h1>Title</h1>
            <p>Short content with only a few words.</p>
            <a href="https://example1.com">Link 1</a>
            <a href="https://example2.com">Link 2</a>
            <a href="https://example3.com">Link 3</a>
        </body>
        """

        is_valid, errors = strict_validator.validate(html)
        assert not is_valid

        # Should have errors for both links and word count
        assert any(e["type"] == "excessive_links" for e in errors)
        assert any(e["type"] == "insufficient_content" for e in errors)
