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


class TestConfirmEntryPointErrorHandling:
    @pytest.mark.asyncio
    async def test_storage_failure_preserves_session_for_retry(
        self, authenticated_client, test_subject
    ):
        """If storage fails, session data should be preserved so the user can retry."""
        zip_bytes = make_zip_bytes({"index.html": VALID_HTML, "style.css": "body{}"})

        # Step 1: Upload zip to get picker
        await authenticated_client.post(
            "/upload-form",
            data={
                "title": "Retry Test",
                "authors": "Author",
                "subject_id": str(test_subject.id),
                "abstract": "Test abstract for retry",
                "license": "cc-by-4.0",
                "confirm_rights": "true",
                "action": "publish",
            },
            files={"file": ("test.zip", zip_bytes, "application/zip")},
        )

        # Step 2: Confirm with a storage that fails
        from app.storage.memory import InMemoryStorage

        class FailingStorage(InMemoryStorage):
            async def put(self, key, data, content_type="application/octet-stream"):
                raise RuntimeError("Simulated storage failure")

        with patch("app.storage.get_storage", return_value=FailingStorage()):
            response = await authenticated_client.post(
                "/upload/confirm-entry-point",
                data={"entry_point": "index.html"},
            )

        assert response.status_code == 422
        assert "Select Entry Point" in response.text
        assert "index.html" in response.text

        # Step 3: Retry with working storage should succeed
        working_storage = InMemoryStorage()
        with patch("app.storage.get_storage", return_value=working_storage):
            response = await authenticated_client.post(
                "/upload/confirm-entry-point",
                data={"entry_point": "index.html"},
            )

        assert response.status_code in (302, 303, 307, 200)
        if response.status_code in (302, 303, 307):
            assert "/preview/" in response.headers.get("location", "")

    @pytest.mark.asyncio
    async def test_storage_failure_shows_error_message(
        self, authenticated_client, test_subject
    ):
        """Storage failure should show error in the picker UI, not bare HTML."""
        zip_bytes = make_zip_bytes({"index.html": VALID_HTML})

        await authenticated_client.post(
            "/upload-form",
            data={
                "title": "Error Display Test",
                "authors": "Author",
                "subject_id": str(test_subject.id),
                "abstract": "Test abstract",
                "license": "cc-by-4.0",
                "confirm_rights": "true",
                "action": "publish",
            },
            files={"file": ("test.zip", zip_bytes, "application/zip")},
        )

        class FailingStorage:
            async def put(self, key, data, content_type="application/octet-stream"):
                raise RuntimeError("Storage is down")

        with patch("app.storage.get_storage", return_value=FailingStorage()):
            response = await authenticated_client.post(
                "/upload/confirm-entry-point",
                data={"entry_point": "index.html"},
            )

        assert response.status_code == 422
        body = response.text
        assert "Storage is down" in body
        assert "form-errors" in body

    @pytest.mark.asyncio
    async def test_confirm_clears_session_on_success(
        self, authenticated_client, test_subject, mock_storage
    ):
        """Session pending data should be cleared only after successful confirmation."""
        zip_bytes = make_zip_bytes({"index.html": VALID_HTML})

        await authenticated_client.post(
            "/upload-form",
            data={
                "title": "Session Cleanup Test",
                "authors": "Author",
                "subject_id": str(test_subject.id),
                "abstract": "Test abstract",
                "license": "cc-by-4.0",
                "confirm_rights": "true",
                "action": "publish",
            },
            files={"file": ("test.zip", zip_bytes, "application/zip")},
        )

        response = await authenticated_client.post(
            "/upload/confirm-entry-point",
            data={"entry_point": "index.html"},
        )
        assert response.status_code in (302, 303, 307, 200)

        # Retrying should fail because session was cleaned up
        response = await authenticated_client.post(
            "/upload/confirm-entry-point",
            data={"entry_point": "index.html"},
        )
        assert response.status_code == 400


class TestFullUploadToServingRoundTrip:
    """Verify that zip-uploaded assets are stored with keys that the serving endpoints can find."""

    @pytest.mark.asyncio
    async def test_uploaded_assets_are_servable(
        self, authenticated_client, test_subject, mock_storage
    ):
        """Upload zip → confirm → serve entry point + assets. The key round-trip test."""
        html_with_assets = VALID_HTML.replace(
            "</head>", '<link href="styles/main.css"></head>'
        )
        zip_bytes = make_zip_bytes(
            {
                "index.html": html_with_assets,
                "styles/main.css": "h1 { color: navy; }",
            }
        )

        # Step 1: Upload zip
        response = await authenticated_client.post(
            "/upload-form",
            data={
                "title": "Round Trip Test",
                "authors": "Author",
                "subject_id": str(test_subject.id),
                "abstract": "Test abstract for round trip",
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
            follow_redirects=False,
        )
        assert response.status_code in (302, 303)
        preview_url = response.headers["location"]
        assert "/preview/" in preview_url

        # Extract url_hash from preview URL
        url_hash = preview_url.split("/preview/")[1].rstrip("/")

        # Step 3: Verify entry point is servable
        response = await authenticated_client.get(f"/scroll/{url_hash}/paper/")
        assert response.status_code == 200
        assert b"Research Paper Title" in response.content

        # Step 4: Verify CSS asset is servable
        response = await authenticated_client.get(
            f"/scroll/{url_hash}/paper/styles/main.css"
        )
        assert response.status_code == 200
        assert b"color: navy" in response.content

    @pytest.mark.asyncio
    async def test_nested_zip_assets_servable_after_flattening(
        self, authenticated_client, test_subject, mock_storage
    ):
        """Nested zip (my-paper/index.html) should serve assets after flattening."""
        nested_html = VALID_HTML.replace(
            "</head>", '<link href="css/style.css"></head>'
        )
        zip_bytes = make_zip_bytes(
            {
                "my-paper/index.html": nested_html,
                "my-paper/css/style.css": "body { margin: 0; }",
                "my-paper/data/results.json": '{"x": [1,2,3]}',
            }
        )

        # Upload + confirm
        response = await authenticated_client.post(
            "/upload-form",
            data={
                "title": "Nested Zip Test",
                "authors": "Author",
                "subject_id": str(test_subject.id),
                "abstract": "Nested archive test abstract",
                "license": "cc-by-4.0",
                "confirm_rights": "true",
                "action": "publish",
            },
            files={"file": ("nested.zip", zip_bytes, "application/zip")},
        )
        assert response.status_code == 200

        response = await authenticated_client.post(
            "/upload/confirm-entry-point",
            data={"entry_point": "index.html"},
            follow_redirects=False,
        )
        assert response.status_code in (302, 303)
        url_hash = response.headers["location"].split("/preview/")[1].rstrip("/")

        # Verify entry point (should be at root after flattening)
        response = await authenticated_client.get(f"/scroll/{url_hash}/paper/")
        assert response.status_code == 200
        assert b"Research Paper Title" in response.content

        # Verify CSS (should be at css/style.css after stripping my-paper/ prefix)
        response = await authenticated_client.get(
            f"/scroll/{url_hash}/paper/css/style.css"
        )
        assert response.status_code == 200
        assert b"margin: 0" in response.content

        # Verify JSON data
        response = await authenticated_client.get(
            f"/scroll/{url_hash}/paper/data/results.json"
        )
        assert response.status_code == 200
        assert b'"x"' in response.content


    @pytest.mark.asyncio
    async def test_sibling_dir_assets_servable_via_parent_path(
        self, authenticated_client, test_subject, mock_storage
    ):
        """Assets in sibling dirs (referenced via ../) are servable at /scroll/{hash}/{path}.

        When an archive has paper/index.html referencing ../styles/paper.css, the browser
        resolves the ../ relative to /scroll/{hash}/paper/, producing /scroll/{hash}/styles/paper.css.
        The fallback route must serve these.
        """
        html_with_parent_refs = VALID_HTML.replace(
            "</head>",
            '<link href="../styles/paper.css"></head>',
        )
        zip_bytes = make_zip_bytes(
            {
                "paper/index.html": html_with_parent_refs,
                "styles/paper.css": "h1 { color: red; }",
                "images/figure1.svg": "<svg></svg>",
                "scripts/plot.js": "console.log('ok');",
            }
        )

        response = await authenticated_client.post(
            "/upload-form",
            data={
                "title": "Sibling Dir Test",
                "authors": "Author",
                "subject_id": str(test_subject.id),
                "abstract": "Test abstract for sibling directory references",
                "license": "cc-by-4.0",
                "confirm_rights": "true",
                "action": "publish",
            },
            files={"file": ("sibling.zip", zip_bytes, "application/zip")},
        )
        assert response.status_code == 200

        response = await authenticated_client.post(
            "/upload/confirm-entry-point",
            data={"entry_point": "index.html"},
            follow_redirects=False,
        )
        assert response.status_code in (302, 303)
        url_hash = response.headers["location"].split("/preview/")[1].rstrip("/")

        # Assets in sibling directories are accessible via the parent-level route
        # (simulating what ../styles/paper.css resolves to from /scroll/{hash}/paper/)
        response = await authenticated_client.get(
            f"/scroll/{url_hash}/styles/paper.css"
        )
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/css")
        assert b"color: red" in response.content

        response = await authenticated_client.get(
            f"/scroll/{url_hash}/images/figure1.svg"
        )
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("image/svg+xml")

        response = await authenticated_client.get(
            f"/scroll/{url_hash}/scripts/plot.js"
        )
        assert response.status_code == 200
        assert b"console.log" in response.content

    @pytest.mark.asyncio
    async def test_parent_path_route_rejects_non_archive_scrolls(
        self, authenticated_client, test_subject
    ):
        """The fallback route should 404 for non-archive scrolls."""
        response = await authenticated_client.post(
            "/upload-form",
            data={
                "title": "Inline Scroll",
                "authors": "Author",
                "subject_id": str(test_subject.id),
                "abstract": "Test abstract for inline scroll asset rejection",
                "license": "cc-by-4.0",
                "confirm_rights": "true",
                "action": "publish",
            },
            files={"file": ("paper.html", VALID_HTML.encode(), "text/html")},
            follow_redirects=False,
        )
        url_hash = response.headers["location"].split("/preview/")[1].rstrip("/")

        response = await authenticated_client.get(
            f"/scroll/{url_hash}/styles/paper.css"
        )
        assert response.status_code == 404


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
