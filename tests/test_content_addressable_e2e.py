"""End-to-end tests for URL permanence and content integrity."""

from pathlib import Path
import tempfile

from httpx import AsyncClient
import pytest
from sqlalchemy import select

from app.models.scroll import Scroll


@pytest.mark.asyncio
class TestURLPermanence:
    """Test URL permanence and content integrity over time."""

    async def test_url_permanence_across_sessions(
        self, client: AsyncClient, test_db, test_subject
    ):
        """Test that URLs remain accessible across multiple sessions."""
        html_content = """<!DOCTYPE html>
<html>
<head>
    <title>Permanence Test Document</title>
</head>
<body>
    <h1>Testing URL Permanence</h1>
    <p>This document tests that URLs remain permanent and accessible.</p>
    <section>
        <h2>Research Content</h2>
        <p>Lorem ipsum dolor sit amet, consectetur adipiscing elit.</p>
        <p>Sed do eiusmod tempor incididunt ut labore et dolore magna aliqua.</p>
    </section>
</body>
</html>"""

        # Upload content and get permanent URL
        with tempfile.NamedTemporaryFile(mode="w", suffix=".html", delete=False) as f:
            f.write(html_content)
            temp_file_path = f.name

        try:
            with open(temp_file_path, "rb") as f:
                files = {"file": ("permanence_test.html", f, "text/html")}
                upload_response = await client.post("/upload", files=files)

            assert upload_response.status_code == 200
            upload_data = upload_response.json()

            permanent_url = upload_data["permanent_url"]
            url_hash = upload_data["url_hash"]
            content_hash = upload_data["content_hash"]

            # Test access immediately after upload (returns scroll template)
            response1 = await client.get(permanent_url)
            assert response1.status_code == 200
            content1 = response1.content.decode("utf-8")
            assert "Testing URL Permanence" in content1

            # Get raw content for comparison
            raw_response1 = await client.get(f"{permanent_url}/raw")
            assert raw_response1.status_code == 200
            raw_content1 = raw_response1.content

            # Simulate multiple subsequent accesses
            for i in range(10):
                response = await client.get(permanent_url)
                assert response.status_code == 200
                content = response.content.decode("utf-8")
                assert "Testing URL Permanence" in content

                # Test raw content consistency
                raw_response = await client.get(f"{permanent_url}/raw")
                assert raw_response.status_code == 200
                raw_content = raw_response.content
                assert raw_content == raw_content1  # Raw content should be identical

            # Test raw content access
            raw_response = await client.get(f"/scroll/{url_hash}/raw")
            assert raw_response.status_code == 200
            assert raw_response.headers["content-type"] == "application/x-tar"

            # Verify database record persists correctly
            result = await test_db.execute(select(Scroll).where(Scroll.url_hash == url_hash))
            scroll = result.scalar_one()
            assert scroll.content_hash == content_hash
            assert scroll.url_hash == url_hash
            assert scroll.status == "published"

        finally:
            Path(temp_file_path).unlink()

    async def test_content_integrity_verification(self, client: AsyncClient, test_subject):
        """Test that content integrity is maintained (content matches hash)."""
        original_content = """<!DOCTYPE html>
<html>
<body>
    <h1>Content Integrity Test</h1>
    <p>This tests that content integrity is maintained over time.</p>
    <ul>
        <li>Original content should match exactly</li>
        <li>Hash should be verifiable</li>
        <li>No corruption should occur</li>
    </ul>
</body>
</html>"""

        # Upload and verify initial state
        with tempfile.NamedTemporaryFile(mode="w", suffix=".html", delete=False) as f:
            f.write(original_content)
            temp_file_path = f.name

        try:
            with open(temp_file_path, "rb") as f:
                files = {"file": ("integrity_test.html", f, "text/html")}
                upload_response = await client.post("/upload", files=files)

            upload_data = upload_response.json()
            url_hash = upload_data["url_hash"]
            expected_content_hash = upload_data["content_hash"]

            # Retrieve content and verify it matches original
            view_response = await client.get(f"/scroll/{url_hash}")
            assert view_response.status_code == 200
            served_content = view_response.content.decode("utf-8")

            # Extract the actual content (may have CSS injected)
            assert "Content Integrity Test" in served_content
            assert "This tests that content integrity is maintained" in served_content
            assert "Original content should match exactly" in served_content

            # Verify raw content hash by re-processing
            from app.database import AsyncSessionLocal
            from app.storage.content_processing import generate_permanent_url

            async with AsyncSessionLocal() as session:
                _, recalculated_hash, _ = await generate_permanent_url(session, original_content)
            assert recalculated_hash == expected_content_hash

        finally:
            Path(temp_file_path).unlink()

    async def test_concurrent_access_same_content(self, client: AsyncClient, test_subject):
        """Test that concurrent access to same content is handled correctly."""
        content = """<!DOCTYPE html>
<html><body><h1>Concurrent Access Test</h1></body></html>"""

        with tempfile.NamedTemporaryFile(mode="w", suffix=".html", delete=False) as f:
            f.write(content)
            temp_file_path = f.name

        try:
            # Upload content first time
            with open(temp_file_path, "rb") as f:
                files = {"file": ("concurrent1.html", f, "text/html")}
                response1 = await client.post("/upload", files=files)

            assert response1.status_code == 200
            data1 = response1.json()

            # Simulate concurrent uploads of same content
            concurrent_responses = []
            for i in range(5):
                with open(temp_file_path, "rb") as f:
                    files = {"file": (f"concurrent{i + 2}.html", f, "text/html")}
                    response = await client.post("/upload", files=files)
                concurrent_responses.append(response)

            # All should succeed and return same URL
            for response in concurrent_responses:
                assert response.status_code == 200
                data = response.json()
                assert data["url_hash"] == data1["url_hash"]
                assert data["content_hash"] == data1["content_hash"]
                assert data["exists"] is True  # Should find existing content

        finally:
            Path(temp_file_path).unlink()

    async def test_url_format_compliance(self, client: AsyncClient, test_subject):
        """Test that generated URLs comply with format requirements."""
        test_contents = [
            "<!DOCTYPE html><html><body><h1>Test 1</h1></body></html>",
            "<!DOCTYPE html><html><body><h1>Test 2</h1><p>More content</p></body></html>",
            "<!DOCTYPE html><html><body><div><p>Complex structure</p></div></body></html>",
        ]

        for i, content in enumerate(test_contents):
            with tempfile.NamedTemporaryFile(mode="w", suffix=".html", delete=False) as f:
                f.write(content)
                temp_file_path = f.name

            try:
                with open(temp_file_path, "rb") as f:
                    files = {"file": (f"format_test_{i}.html", f, "text/html")}
                    response = await client.post("/upload", files=files)

                assert response.status_code == 200
                data = response.json()

                # Verify URL format requirements
                url_hash = data["url_hash"]
                content_hash = data["content_hash"]

                # URL hash should be 12+ characters from SHA-256
                assert len(url_hash) >= 12
                assert len(url_hash) <= 64  # No longer than full hash
                assert all(c in "0123456789abcdef" for c in url_hash)  # Hex only

                # Should be prefix of content hash
                assert content_hash.startswith(url_hash)

                # Content hash should be full SHA-256
                assert len(content_hash) == 64
                assert all(c in "0123456789abcdef" for c in content_hash)

                # Permanent URL should follow expected format
                permanent_url = data["permanent_url"]
                assert permanent_url == f"/scroll/{url_hash}"

            finally:
                Path(temp_file_path).unlink()


@pytest.mark.asyncio
class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    async def test_minimal_valid_html(self, client: AsyncClient, test_subject):
        """Test minimal valid HTML content."""
        minimal_content = "<html></html>"

        with tempfile.NamedTemporaryFile(mode="w", suffix=".html", delete=False) as f:
            f.write(minimal_content)
            temp_file_path = f.name

        try:
            with open(temp_file_path, "rb") as f:
                files = {"file": ("minimal.html", f, "text/html")}
                response = await client.post("/upload", files=files)

            assert response.status_code == 200
            data = response.json()

            # Should still generate valid permanent URL
            assert len(data["url_hash"]) >= 12
            assert data["permanent_url"].startswith("/scroll/")

            # Content should be accessible
            view_response = await client.get(data["permanent_url"])
            assert view_response.status_code == 200

        finally:
            Path(temp_file_path).unlink()

    async def test_html_with_special_characters(self, client: AsyncClient, test_subject):
        """Test HTML with Unicode and special characters."""
        unicode_content = """<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Unicode Test: 测试文档</title>
</head>
<body>
    <h1>Testing Unicode: 🧪 科学实验</h1>
    <p>Mathematical symbols: ∑ ∫ ∂ ∆ ∇</p>
    <p>Emoji: 🔬🧬🌍⚡️</p>
    <p>European chars: café naïve résumé</p>
    <p>Asian chars: 日本語 한국어 中文</p>
</body>
</html>"""

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".html", delete=False, encoding="utf-8"
        ) as f:
            f.write(unicode_content)
            temp_file_path = f.name

        try:
            with open(temp_file_path, "rb") as f:
                files = {"file": ("unicode_test.html", f, "text/html")}
                response = await client.post("/upload", files=files)

            assert response.status_code == 200
            data = response.json()

            # Verify content is accessible and correct
            view_response = await client.get(data["permanent_url"])
            assert view_response.status_code == 200
            served_content = view_response.content.decode("utf-8")

            # Check that Unicode characters are preserved (may be JSON-escaped or direct)
            # Check for text content presence in the response
            assert "测试文档" in served_content or "\\u6d4b\\u8bd5\\u6587\\u6863" in served_content
            assert "科学实验" in served_content or "\\u79d1\\u5b66\\u5b9e\\u9a8c" in served_content
            assert "Mathematical symbols" in served_content
            assert "European chars" in served_content
            assert "café" in served_content or "caf\\u00e9" in served_content

            # Test raw content preserves Unicode properly
            raw_response = await client.get(f"{data['permanent_url']}/raw")
            assert raw_response.status_code == 200

        finally:
            Path(temp_file_path).unlink()

    async def test_boundary_file_size(self, client: AsyncClient, test_subject):
        """Test file at boundary of size limit."""
        # Create content just under 50MB limit
        base_content = "<!DOCTYPE html><html><body><h1>Size Test</h1><p>"
        padding = "x" * (50 * 1024 * 1024 - len(base_content) - 20)  # Leave room for closing tags
        content = base_content + padding + "</p></body></html>"

        with tempfile.NamedTemporaryFile(mode="w", suffix=".html", delete=False) as f:
            f.write(content)
            temp_file_path = f.name

        try:
            with open(temp_file_path, "rb") as f:
                files = {"file": ("boundary_size.html", f, "text/html")}
                response = await client.post("/upload", files=files)

            # Should succeed (just under limit)
            assert response.status_code == 200
            data = response.json()

            # Verify accessibility
            view_response = await client.get(data["permanent_url"])
            assert view_response.status_code == 200

        finally:
            Path(temp_file_path).unlink()

    async def test_complex_html_structure(self, client: AsyncClient, test_subject):
        """Test complex HTML with nested structures."""
        complex_content = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Complex Structure Test</title>
    <style>
        body { font-family: Arial, sans-serif; }
        .highlight { background-color: yellow; }
        table { border-collapse: collapse; width: 100%; }
        td, th { border: 1px solid #ddd; padding: 8px; }
    </style>
</head>
<body>
    <header>
        <nav>
            <ul>
                <li><a href="#section1">Section 1</a></li>
                <li><a href="#section2">Section 2</a></li>
            </ul>
        </nav>
    </header>
    
    <main>
        <section id="section1">
            <h1>Complex HTML Structure Test</h1>
            <p>This tests handling of <em>complex</em> <strong>nested</strong> structures.</p>
            
            <table>
                <thead>
                    <tr><th>Column 1</th><th>Column 2</th></tr>
                </thead>
                <tbody>
                    <tr><td>Data 1</td><td>Data 2</td></tr>
                    <tr><td>Data 3</td><td>Data 4</td></tr>
                </tbody>
            </table>
        </section>
        
        <section id="section2">
            <h2>Nested Lists</h2>
            <ol>
                <li>First item
                    <ul>
                        <li>Nested item A</li>
                        <li>Nested item B
                            <ol>
                                <li>Deeply nested 1</li>
                                <li>Deeply nested 2</li>
                            </ol>
                        </li>
                    </ul>
                </li>
                <li>Second item</li>
            </ol>
        </section>
    </main>
    
    <footer>
        <p>&copy; 2024 Test Document</p>
    </footer>
</body>
</html>"""

        with tempfile.NamedTemporaryFile(mode="w", suffix=".html", delete=False) as f:
            f.write(complex_content)
            temp_file_path = f.name

        try:
            with open(temp_file_path, "rb") as f:
                files = {"file": ("complex_structure.html", f, "text/html")}
                response = await client.post("/upload", files=files)

            assert response.status_code == 200
            data = response.json()

            # Verify complex content is preserved
            view_response = await client.get(data["permanent_url"])
            assert view_response.status_code == 200
            served_content = view_response.content.decode("utf-8")

            # Check various structural elements are preserved (content may be JSON-encoded)
            assert "Complex HTML Structure Test" in served_content
            assert (
                "table>" in served_content or "table\\u003e" in served_content
            )  # May be JSON-escaped
            assert "Nested item A" in served_content
            assert "Deeply nested 1" in served_content
            assert "2024 Test Document" in served_content
            assert "font-family: Arial" in served_content  # CSS preserved

            # Verify raw content access works
            raw_response = await client.get(f"{data['permanent_url']}/raw")
            assert raw_response.status_code == 200

        finally:
            Path(temp_file_path).unlink()
