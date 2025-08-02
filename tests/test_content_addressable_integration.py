"""Integration tests for content-addressable storage pipeline."""

from pathlib import Path
import tempfile

from httpx import AsyncClient
import pytest

from app.storage.content_processing import generate_permanent_url


@pytest.mark.asyncio
class TestContentAddressableIntegration:
    """Integration tests for complete upload-to-URL pipeline."""

    async def test_complete_upload_pipeline(self, client: AsyncClient, test_db, test_subject):
        """Test complete pipeline from upload to URL access."""
        # Create test HTML content
        html_content = """<!DOCTYPE html>
<html>
<head>
    <title>Test Research Paper</title>
</head>
<body>
    <h1>A Test Research Paper</h1>
    <p>This is a test paper for content-addressable storage.</p>
    <p>It contains some research content.</p>
</body>
</html>"""

        # Create test file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".html", delete=False) as f:
            f.write(html_content)
            temp_file_path = f.name

        try:
            # Upload the file
            with open(temp_file_path, "rb") as f:
                files = {"file": ("test.html", f, "text/html")}
                response = await client.post("/upload", files=files)

            assert response.status_code == 200
            data = response.json()

            # Verify response structure
            assert data["success"] is True
            assert "permanent_url" in data
            assert "url_hash" in data
            assert "content_hash" in data
            assert data["exists"] is False

            url_hash = data["url_hash"]
            content_hash = data["content_hash"]

            # Verify URL format (12+ characters from hash)
            assert len(url_hash) >= 12
            assert url_hash == content_hash[: len(url_hash)]

            # Test accessing the content via permanent URL
            scroll_response = await client.get(f"/scroll/{url_hash}")
            assert scroll_response.status_code == 200

            # Verify content is served correctly
            content = scroll_response.content.decode("utf-8")
            assert "A Test Research Paper" in content
            assert "test paper for content-addressable storage" in content

        finally:
            Path(temp_file_path).unlink()

    async def test_duplicate_content_returns_existing_url(self, client: AsyncClient, test_subject):
        """Test that uploading identical content returns existing URL."""
        html_content = """<!DOCTYPE html>
<html><body><h1>Duplicate Test</h1></body></html>"""

        # Upload first time
        with tempfile.NamedTemporaryFile(mode="w", suffix=".html", delete=False) as f:
            f.write(html_content)
            temp_file_path = f.name

        try:
            with open(temp_file_path, "rb") as f:
                files = {"file": ("test1.html", f, "text/html")}
                response1 = await client.post("/upload", files=files)

            assert response1.status_code == 200
            data1 = response1.json()
            assert data1["exists"] is False

            # Upload identical content again
            with open(temp_file_path, "rb") as f:
                files = {"file": ("test2.html", f, "text/html")}
                response2 = await client.post("/upload", files=files)

            assert response2.status_code == 200
            data2 = response2.json()

            # Should return existing URL
            assert data2["exists"] is True
            assert data2["url_hash"] == data1["url_hash"]
            assert data2["content_hash"] == data1["content_hash"]
            assert data2["permanent_url"] == data1["permanent_url"]

        finally:
            Path(temp_file_path).unlink()

    async def test_different_content_different_urls(self, client: AsyncClient, test_subject):
        """Test that different content produces different URLs."""
        html_content1 = """<!DOCTYPE html>
<html><body><h1>Content 1</h1></body></html>"""

        html_content2 = """<!DOCTYPE html>
<html><body><h1>Content 2</h1></body></html>"""

        # Upload first content
        with tempfile.NamedTemporaryFile(mode="w", suffix=".html", delete=False) as f1:
            f1.write(html_content1)
            temp_file_path1 = f1.name

        with tempfile.NamedTemporaryFile(mode="w", suffix=".html", delete=False) as f2:
            f2.write(html_content2)
            temp_file_path2 = f2.name

        try:
            # Upload first file
            with open(temp_file_path1, "rb") as f:
                files = {"file": ("test1.html", f, "text/html")}
                response1 = await client.post("/upload", files=files)

            # Upload second file
            with open(temp_file_path2, "rb") as f:
                files = {"file": ("test2.html", f, "text/html")}
                response2 = await client.post("/upload", files=files)

            assert response1.status_code == 200
            assert response2.status_code == 200

            data1 = response1.json()
            data2 = response2.json()

            # Should have different URLs and hashes
            assert data1["url_hash"] != data2["url_hash"]
            assert data1["content_hash"] != data2["content_hash"]
            assert data1["permanent_url"] != data2["permanent_url"]

        finally:
            Path(temp_file_path1).unlink()
            Path(temp_file_path2).unlink()

    async def test_line_ending_normalization(self, client: AsyncClient, test_subject):
        """Test that different line endings produce identical URLs."""
        # Same content with different line endings
        base_content = "<!DOCTYPE html>\n<html>\n<body>\n<h1>Test</h1>\n</body>\n</html>"
        content_lf = base_content  # Unix (LF)
        content_crlf = base_content.replace("\n", "\r\n")  # Windows (CRLF)
        content_cr = base_content.replace("\n", "\r")  # Classic Mac (CR)

        results = []

        for i, content in enumerate([content_lf, content_crlf, content_cr]):
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".html", delete=False, newline=""
            ) as f:
                f.write(content)
                temp_file_path = f.name

            try:
                with open(temp_file_path, "rb") as f:
                    files = {"file": (f"test{i}.html", f, "text/html")}
                    response = await client.post("/upload", files=files)

                assert response.status_code == 200
                results.append(response.json())

            finally:
                Path(temp_file_path).unlink()

        # All should produce the same URL (after normalization)
        assert results[0]["url_hash"] == results[1]["url_hash"] == results[2]["url_hash"]
        assert (
            results[0]["content_hash"] == results[1]["content_hash"] == results[2]["content_hash"]
        )

    async def test_raw_content_endpoint(self, client: AsyncClient, test_subject):
        """Test raw content endpoint returns tar archive."""
        html_content = """<!DOCTYPE html>
<html>
<body>
    <h1>Raw Content Test</h1>
    <p>Testing raw tar output.</p>
</body>
</html>"""

        # Upload content
        with tempfile.NamedTemporaryFile(mode="w", suffix=".html", delete=False) as f:
            f.write(html_content)
            temp_file_path = f.name

        try:
            with open(temp_file_path, "rb") as f:
                files = {"file": ("test.html", f, "text/html")}
                upload_response = await client.post("/upload", files=files)

            assert upload_response.status_code == 200
            url_hash = upload_response.json()["url_hash"]

            # Request raw content
            raw_response = await client.get(f"/scroll/{url_hash}/raw")
            assert raw_response.status_code == 200
            assert raw_response.headers["content-type"] == "application/x-tar"
            assert "attachment" in raw_response.headers["content-disposition"]

            # Verify it's valid tar data
            tar_data = raw_response.content
            assert len(tar_data) > 0

            # Basic tar header check (tar files start with filename)
            assert b"content.html" in tar_data[:100]  # Filename should be early in header

        finally:
            Path(temp_file_path).unlink()

    async def test_invalid_file_types_rejected(self, client: AsyncClient, test_subject):
        """Test that non-HTML files are rejected."""
        # Test with text file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("This is not HTML")
            temp_file_path = f.name

        try:
            with open(temp_file_path, "rb") as f:
                files = {"file": ("test.txt", f, "text/plain")}
                response = await client.post("/upload", files=files)

            assert response.status_code == 422
            assert "Only HTML files are accepted" in response.json()["detail"]

        finally:
            Path(temp_file_path).unlink()

    async def test_non_utf8_content_rejected(self, client: AsyncClient, test_subject):
        """Test that non-UTF-8 content is rejected."""
        # Create file with Latin-1 encoding
        content = "<!DOCTYPE html><html><body><h1>Café</h1></body></html>"

        with tempfile.NamedTemporaryFile(mode="wb", suffix=".html", delete=False) as f:
            f.write(content.encode("latin-1"))  # Non-UTF-8 encoding
            temp_file_path = f.name

        try:
            with open(temp_file_path, "rb") as f:
                files = {"file": ("test.html", f, "text/html")}
                response = await client.post("/upload", files=files)

            assert response.status_code == 422
            assert "UTF-8 encoded" in response.json()["detail"]

        finally:
            Path(temp_file_path).unlink()

    async def test_empty_content_rejected(self, client: AsyncClient, test_subject):
        """Test that empty content is rejected."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".html", delete=False) as f:
            f.write("")  # Empty file
            temp_file_path = f.name

        try:
            with open(temp_file_path, "rb") as f:
                files = {"file": ("empty.html", f, "text/html")}
                response = await client.post("/upload", files=files)

            assert response.status_code == 422
            assert "cannot be empty" in response.json()["detail"]

        finally:
            Path(temp_file_path).unlink()

    async def test_oversized_content_rejected(self, client: AsyncClient, test_subject):
        """Test that oversized content is rejected."""
        # Create content larger than 5MB
        large_content = "<!DOCTYPE html><html><body>" + "x" * (6 * 1024 * 1024) + "</body></html>"

        with tempfile.NamedTemporaryFile(mode="w", suffix=".html", delete=False) as f:
            f.write(large_content)
            temp_file_path = f.name

        try:
            with open(temp_file_path, "rb") as f:
                files = {"file": ("large.html", f, "text/html")}
                response = await client.post("/upload", files=files)

            assert response.status_code == 422
            assert "cannot exceed 5MB" in response.json()["detail"]

        finally:
            Path(temp_file_path).unlink()


@pytest.mark.asyncio
class TestContentDeterminism:
    """Test deterministic content processing."""

    async def test_deterministic_hash_generation(self):
        """Test that identical content always produces identical hashes."""
        content = """<!DOCTYPE html>
<html>
<body>
    <h1>Determinism Test</h1>
    <p>This content should always produce the same hash.</p>
</body>
</html>"""

        # Generate hash multiple times
        results = []
        for _ in range(5):
            url_hash, content_hash, tar_data = await generate_permanent_url(content)
            results.append((url_hash, content_hash, tar_data))

        # All results should be identical
        first_result = results[0]
        for result in results[1:]:
            assert result[0] == first_result[0]  # url_hash
            assert result[1] == first_result[1]  # content_hash
            assert result[2] == first_result[2]  # tar_data

    async def test_content_with_whitespace_variations(self):
        """Test that content with different whitespace produces different hashes."""
        base_content = "<html><body><h1>Test</h1></body></html>"
        content_with_spaces = "<html><body><h1>Test</h1>   </body></html>"
        content_with_tabs = "<html><body><h1>Test</h1>\t</body></html>"

        hash1 = (await generate_permanent_url(base_content))[1]
        hash2 = (await generate_permanent_url(content_with_spaces))[1]
        hash3 = (await generate_permanent_url(content_with_tabs))[1]

        # Different whitespace should produce different hashes
        assert hash1 != hash2
        assert hash1 != hash3
        assert hash2 != hash3
