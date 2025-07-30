"""Integration tests for HTML upload processing."""

import os
import tempfile

import pytest

from app.upload.processors import HTMLProcessor


class TestHTMLProcessorIntegration:
    """Test HTML upload processing integration."""

    def setup_method(self):
        """Set up test fixtures."""
        self.processor = HTMLProcessor()
        self.temp_dir = tempfile.mkdtemp()
        self.user_id = "test-user-123"

    def teardown_method(self):
        """Clean up test fixtures."""
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def create_test_file(self, filename, content):
        """Helper to create test files."""
        filepath = os.path.join(self.temp_dir, filename)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)
        return filepath

    @pytest.mark.asyncio
    async def test_process_valid_html_upload(self):
        """Test processing of valid HTML upload."""
        html_content = """
        <!DOCTYPE html>
        <html>
            <head>
                <title>Research Paper on Machine Learning</title>
                <meta name="author" content="Dr. Jane Smith">
                <meta name="description" content="A comprehensive study on ML algorithms">
            </head>
            <body>
                <article>
                    <h1>Machine Learning in Healthcare</h1>
                    <p>This research paper explores the application of machine learning
                    algorithms in healthcare diagnostics. We present a novel approach
                    to disease prediction using deep learning models. Our methodology
                    involves training neural networks on large medical datasets.
                    The results demonstrate significant improvements in diagnostic
                    accuracy compared to traditional methods. This work has important
                    implications for the future of personalized medicine and automated
                    healthcare systems. We conclude with recommendations for clinical
                    implementation and future research directions.</p>
                    
                    <h2>Methodology</h2>
                    <p>We employed a combination of supervised and unsupervised learning
                    techniques to analyze patient data. The dataset included over 10,000
                    patient records with various health indicators.</p>
                    
                    <table>
                        <caption>Table 1: Model Performance Metrics</caption>
                        <tr><th>Model</th><th>Accuracy</th><th>Precision</th></tr>
                        <tr><td>Neural Network</td><td>94.5%</td><td>92.3%</td></tr>
                        <tr><td>Random Forest</td><td>89.2%</td><td>87.1%</td></tr>
                    </table>
                </article>
            </body>
        </html>
        """

        filepath = self.create_test_file("research.html", html_content)
        success, data, errors = await self.processor.process_html_upload(
            filepath, "research.html", self.user_id
        )

        assert success
        assert data["validation_status"] == "approved"
        assert data["content_type"] == "html"
        assert data["title"] == "Research Paper on Machine Learning"
        assert data["author"] == "Dr. Jane Smith"
        assert len(errors) == 0

        # Check sanitization preserved content
        assert "Machine Learning in Healthcare" in data["html_content"]
        assert "<table>" in data["html_content"]
        assert "<caption>Table 1: Model Performance Metrics</caption>" in data["html_content"]

        # Check metrics
        metrics = data["content_metrics"]
        assert metrics["paragraph_count"] == 2
        assert metrics["heading_count"] == 2
        assert metrics["table_count"] == 1
        assert metrics["word_count"] > 100

    @pytest.mark.asyncio
    async def test_process_html_with_xss_attempts(self):
        """Test processing of HTML with XSS attempts."""
        html_content = """
        <!DOCTYPE html>
        <html>
            <head><title>Paper with XSS</title></head>
            <body>
                <h1>Research Title</h1>
                <script>alert('XSS')</script>
                <p onclick="alert('XSS')">This is a paragraph with sufficient content
                to meet the minimum word count requirement. The research explores
                various aspects of web security and demonstrates common vulnerabilities.
                We analyze different attack vectors and propose mitigation strategies.
                The methodology involves testing various security measures against
                known exploits. Results show that proper input validation and output
                encoding are essential for preventing cross-site scripting attacks.
                Our comprehensive analysis covers multiple layers of defense including
                sanitization, validation, and secure coding practices. We examined
                both client-side and server-side vulnerabilities in modern web applications.
                The findings reveal critical security gaps that can be exploited by
                malicious actors to compromise user data and system integrity. This
                research contributes to the broader understanding of web application
                security and provides actionable recommendations for developers and
                security professionals working in the field.</p>
                <img src="x" onerror="alert('XSS')">
                <a href="javascript:alert('XSS')">Malicious Link</a>
            </body>
        </html>
        """

        filepath = self.create_test_file("xss_attempt.html", html_content)
        success, data, errors = await self.processor.process_html_upload(
            filepath, "xss_attempt.html", self.user_id
        )

        if not success:
            print(f"Errors: {errors}")
        assert success
        assert data["validation_status"] == "approved"

        # Check XSS was handled - scripts preserved, but event handlers and js URLs removed
        assert "<script>" in data["html_content"]  # Scripts should be preserved
        assert "onclick=" not in data["html_content"]
        assert "onerror=" not in data["html_content"]
        assert "javascript:" not in data["html_content"]

        # Check sanitization log
        assert len(data["sanitization_log"]) > 0
        log_types = [entry["type"] for entry in data["sanitization_log"]]
        # Scripts should NOT be removed anymore
        assert "script_removed" not in log_types
        assert "event_handler_removed" in log_types
        assert "javascript_url_removed" in log_types

    @pytest.mark.asyncio
    async def test_process_html_with_spam_content(self):
        """Test processing of HTML with spam content."""
        html_content = """
        <!DOCTYPE html>
        <html>
            <head><title>Spammy Content</title></head>
            <body>
                <h1>Buy Now! Limited Offer!</h1>
                <p>Click here for guaranteed results! This amazing product will
                help you lose weight fast. Act now and get a special discount.
                Win prizes and bonuses. Visit our casino for more opportunities.</p>
                <a href="https://spam1.com">Link 1</a>
                <a href="https://spam2.com">Link 2</a>
            </body>
        </html>
        """

        filepath = self.create_test_file("spam.html", html_content)
        success, data, errors = await self.processor.process_html_upload(
            filepath, "spam.html", self.user_id
        )

        assert not success
        assert data["validation_status"] == "rejected"

        # Check for spam detection errors
        error_types = [e["type"] for e in errors]
        assert "spam_keywords" in error_types
        assert "insufficient_content" in error_types

    @pytest.mark.asyncio
    async def test_process_html_with_excessive_links(self):
        """Test processing of HTML with too many external links."""
        html_content = """
        <!DOCTYPE html>
        <html>
            <head><title>Link Farm</title></head>
            <body>
                <h1>Research with Many Links</h1>
                <p>This paper contains numerous references to external sources.
                While academic papers often have many citations, excessive linking
                can be a sign of spam or low-quality content. We include sufficient
                text to meet word count requirements and demonstrate the validation
                of external link limits in our security system.</p>
        """

        # Add 15 external links
        for i in range(15):
            html_content += f'<a href="https://example{i}.com">Reference {i}</a>\n'

        html_content += "</body></html>"

        filepath = self.create_test_file("many_links.html", html_content)
        success, data, errors = await self.processor.process_html_upload(
            filepath, "many_links.html", self.user_id
        )

        assert not success
        assert data["validation_status"] == "rejected"

        # Check for excessive links error
        assert any(e["type"] == "excessive_links" for e in errors)

    @pytest.mark.asyncio
    async def test_metadata_extraction(self):
        """Test metadata extraction from HTML."""
        html_content = """
        <!DOCTYPE html>
        <html>
            <head>
                <title>Full Metadata Test</title>
                <meta name="author" content="Dr. John Doe">
                <meta name="description" content="Testing metadata extraction">
                <meta name="keywords" content="testing, metadata, extraction">
            </head>
            <body>
                <h1>Alternative Title in H1</h1>
                <p>Content with sufficient words to pass validation. This test ensures
                that all metadata is properly extracted from the HTML document.
                We verify that title, author, description, and keywords are all
                captured correctly during the processing phase. The extraction
                process involves parsing HTML content and identifying relevant
                meta tags that contain crucial information about the document.
                This comprehensive approach ensures that research papers maintain
                their scholarly integrity and proper attribution throughout the
                system. We implement robust parsing mechanisms to handle various
                HTML structures and formats commonly used in academic publishing.
                The metadata extraction functionality serves as a foundation for
                proper indexing and categorization of uploaded research documents.</p>
            </body>
        </html>
        """

        filepath = self.create_test_file("metadata.html", html_content)
        success, data, errors = await self.processor.process_html_upload(
            filepath, "metadata.html", self.user_id
        )

        assert success
        assert data["title"] == "Full Metadata Test"
        assert data["author"] == "Dr. John Doe"
        assert data["description"] == "Testing metadata extraction"
        assert data["keywords"] == "testing, metadata, extraction"

    @pytest.mark.asyncio
    async def test_content_hash_generation(self):
        """Test that content hash is generated for duplicate detection."""
        html_content = """
        <!DOCTYPE html>
        <html>
            <head><title>Test</title></head>
            <body>
                <p>This content will be used to generate a hash for duplicate
                detection. The hash should be consistent for the same content
                and different for different content. This helps prevent duplicate
                submissions of the same research paper. Our hashing algorithm
                utilizes cryptographic functions to create unique fingerprints
                for each document submitted to the platform. This approach ensures
                data integrity and prevents unauthorized duplication of research
                content. The system maintains a comprehensive database of content
                hashes to enable efficient duplicate detection across large volumes
                of academic papers. We implement robust comparison mechanisms that
                account for minor formatting differences while identifying substantial
                content similarities. This functionality is essential for maintaining
                the quality and originality of research publications in our repository.</p>
            </body>
        </html>
        """

        filepath1 = self.create_test_file("hash1.html", html_content)
        filepath2 = self.create_test_file("hash2.html", html_content)

        success1, data1, _ = await self.processor.process_html_upload(
            filepath1, "hash1.html", self.user_id
        )
        success2, data2, _ = await self.processor.process_html_upload(
            filepath2, "hash2.html", self.user_id
        )

        assert success1 and success2
        assert "content_hash" in data1 and "content_hash" in data2
        assert data1["content_hash"] == data2["content_hash"]  # Same content = same hash
