"""Integration tests for the zip upload flow through the upload-form endpoint."""

import io
from unittest.mock import patch
import zipfile

import pytest

from app.storage.memory import InMemoryStorage

VALID_HTML = (
    "<html><head><title>Test Document</title></head><body>"
    "<h1>Research Paper Title</h1>"
    "<p>This is a comprehensive test document designed to pass the content validator "
    "minimum word count requirement of one hundred words. The document contains "
    "structured content with headings and paragraphs as required by the validation "
    "pipeline. Academic research papers typically contain many more words than this "
    "minimum threshold but for testing purposes we need to ensure that the validator "
    "accepts our test content without raising errors about insufficient word count "
    "or missing document structure elements that are expected in scholarly work.</p>"
    "<p>Additional paragraph providing more content to ensure we comfortably exceed "
    "the minimum word count threshold required by the content quality validator.</p>"
    "</body></html>"
)


def make_zip_bytes(files: dict[str, str | bytes]) -> bytes:
    """Create a zip file in memory and return the bytes."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, content in files.items():
            if isinstance(content, str):
                zf.writestr(name, content)
            else:
                zf.writestr(name, content)
    return buf.getvalue()


@pytest.fixture
def mock_storage():
    """Patch get_storage to return InMemoryStorage."""
    storage = InMemoryStorage()
    with patch("app.storage.get_storage", return_value=storage):
        yield storage


class TestZipUploadShowsPicker:
    @pytest.mark.asyncio
    async def test_zip_upload_returns_picker_page(self, authenticated_client, test_subject):
        """Uploading a zip file should return the entry point picker page."""
        zip_bytes = make_zip_bytes({"index.html": VALID_HTML, "style.css": "body{}"})

        response = await authenticated_client.post(
            "/upload-form",
            data={
                "title": "Test Scroll",
                "authors": "Test Author",
                "subject_id": str(test_subject.id),
                "abstract": "Test abstract content",
                "keywords": "test,keywords",
                "license": "cc-by-4.0",
                "confirm_rights": "true",
                "action": "publish",
            },
            files={"file": ("test.zip", zip_bytes, "application/zip")},
        )

        assert response.status_code == 200
        body = response.text
        assert "Select Entry Point" in body
        assert "index.html" in body
        assert "auto-detected" in body

    @pytest.mark.asyncio
    async def test_zip_with_multiple_html_files_shows_all(
        self, authenticated_client, test_subject
    ):
        """Picker should list all HTML files in the archive."""
        zip_bytes = make_zip_bytes(
            {
                "index.html": VALID_HTML,
                "appendix.html": VALID_HTML,
                "style.css": "body{}",
            }
        )

        response = await authenticated_client.post(
            "/upload-form",
            data={
                "title": "Multi HTML",
                "authors": "Author",
                "subject_id": str(test_subject.id),
                "abstract": "Test abstract",
                "license": "cc-by-4.0",
                "confirm_rights": "true",
                "action": "publish",
            },
            files={"file": ("multi.zip", zip_bytes, "application/zip")},
        )

        assert response.status_code == 200
        body = response.text
        assert "index.html" in body
        assert "appendix.html" in body

    @pytest.mark.asyncio
    async def test_invalid_zip_shows_error(self, authenticated_client, test_subject):
        """Invalid zip should return an error on the upload form."""
        response = await authenticated_client.post(
            "/upload-form",
            data={
                "title": "Bad Zip",
                "authors": "Author",
                "subject_id": str(test_subject.id),
                "abstract": "Test abstract",
                "license": "cc-by-4.0",
                "confirm_rights": "true",
                "action": "publish",
            },
            files={"file": ("bad.zip", b"not a zip file", "application/zip")},
        )

        assert response.status_code == 422
        assert (
            "not a valid zip" in response.text.lower()
            or "validation failed" in response.text.lower()
        )


class TestConfirmEntryPoint:
    @pytest.mark.asyncio
    async def test_confirm_creates_archive_scroll(
        self, authenticated_client, test_subject, mock_storage
    ):
        """Confirming entry point should create a scroll with storage_type='archive'."""
        zip_bytes = make_zip_bytes({"index.html": VALID_HTML, "style.css": "body{}"})

        # Step 1: Upload zip to get picker
        response = await authenticated_client.post(
            "/upload-form",
            data={
                "title": "Archive Scroll",
                "authors": "Test Author",
                "subject_id": str(test_subject.id),
                "abstract": "A test abstract for archive",
                "keywords": "archive,test",
                "license": "cc-by-4.0",
                "confirm_rights": "true",
                "action": "publish",
            },
            files={"file": ("test.zip", zip_bytes, "application/zip")},
        )
        assert response.status_code == 200
        assert "Select Entry Point" in response.text

        # Step 2: Confirm entry point
        response = await authenticated_client.post(
            "/upload/confirm-entry-point",
            data={"entry_point": "index.html"},
        )

        # Should redirect to preview
        assert response.status_code in (302, 303, 307, 200)
        if response.status_code in (302, 303, 307):
            assert "/preview/" in response.headers.get("location", "")

    @pytest.mark.asyncio
    async def test_confirm_stores_files_in_storage(
        self, authenticated_client, test_subject, mock_storage
    ):
        """Files should be uploaded to storage after confirmation."""
        zip_bytes = make_zip_bytes({"index.html": VALID_HTML, "style.css": "body{}"})

        # Upload zip
        await authenticated_client.post(
            "/upload-form",
            data={
                "title": "Storage Test",
                "authors": "Author",
                "subject_id": str(test_subject.id),
                "abstract": "Testing storage",
                "license": "cc-by-4.0",
                "confirm_rights": "true",
                "action": "publish",
            },
            files={"file": ("test.zip", zip_bytes, "application/zip")},
        )

        # Confirm
        await authenticated_client.post(
            "/upload/confirm-entry-point",
            data={"entry_point": "index.html"},
        )

        # Verify files were stored
        keys = await mock_storage.list_prefix("scrolls/")
        html_keys = [k for k in keys if k.endswith(".html")]
        css_keys = [k for k in keys if k.endswith(".css")]
        assert len(html_keys) >= 1
        assert len(css_keys) >= 1

    @pytest.mark.asyncio
    async def test_confirm_without_pending_upload_fails(self, authenticated_client):
        """Confirming without a pending upload should fail gracefully."""
        response = await authenticated_client.post(
            "/upload/confirm-entry-point",
            data={"entry_point": "index.html"},
        )

        assert response.status_code == 400


class TestHtmlUploadStillWorks:
    @pytest.mark.asyncio
    async def test_html_upload_unchanged(self, authenticated_client, test_subject):
        """Single HTML file upload should still work as before."""
        response = await authenticated_client.post(
            "/upload-form",
            data={
                "title": "HTML Scroll",
                "authors": "Author",
                "subject_id": str(test_subject.id),
                "abstract": "Test abstract",
                "license": "cc-by-4.0",
                "confirm_rights": "true",
                "action": "publish",
            },
            files={"file": ("paper.html", VALID_HTML.encode(), "text/html")},
        )

        # HTML upload should redirect to preview (not show picker)
        assert response.status_code in (200, 302, 303)
        if response.status_code in (302, 303):
            assert "/preview/" in response.headers.get("location", "")
        # Should NOT show picker
        if response.status_code == 200:
            assert "Select Entry Point" not in response.text
