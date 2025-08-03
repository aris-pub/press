"""Unit tests for drag and drop file upload frontend validation."""

from httpx import AsyncClient
import pytest

from app.models.scroll import Subject


class TestFileUploadValidation:
    """Test frontend file upload validation logic."""

    @pytest.fixture
    def valid_html_content(self):
        """Valid HTML content for testing."""
        return """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Test Research Paper</title>
    <style>
        body { font-family: Arial; margin: 2rem; }
        h1 { color: #333; }
    </style>
</head>
<body>
    <h1>Interactive Research Paper</h1>
    <p>This is a test HTML document with valid structure.</p>
    <script>
        console.log('Interactive content loaded');
    </script>
</body>
</html>"""

    @pytest.fixture
    def invalid_html_content(self):
        """Invalid content that's not HTML."""
        return "This is just plain text, not HTML content."

    @pytest.fixture
    def test_subject(self, test_db):
        """Create a test subject for form submissions."""

        async def _create_subject():
            subject = Subject(name="Test Subject", description="Test description")
            test_db.add(subject)
            await test_db.commit()
            await test_db.refresh(subject)
            return subject

        return _create_subject


class TestFileUploadFormSubmission:
    """Test file upload form submission with validation."""

    async def test_upload_form_with_valid_html_file(
        self, authenticated_client: AsyncClient, test_db, test_user
    ):
        """Test successful form submission with valid HTML file content."""
        # Create a subject for the test
        subject = Subject(name="Test Subject", description="Test description")
        test_db.add(subject)
        await test_db.commit()
        await test_db.refresh(subject)

        valid_html = """<!DOCTYPE html>
<html>
<head>
    <title>Valid Test Document</title>
    <style>body { margin: 2rem; }</style>
</head>
<body>
    <h1>Test Content</h1>
    <p>This is valid HTML content from a file upload.</p>
</body>
</html>"""

        upload_data = {
            "title": "File Upload Test",
            "authors": "Test Author",
            "subject_id": str(subject.id),
            "abstract": "Testing file upload functionality",
            "keywords": "test, file, upload",
            "html_content": valid_html,  # Simulates populated hidden field
            "license": "cc-by-4.0",
            "confirm_rights": "true",
            "action": "publish",
        }

        response = await authenticated_client.post("/upload-form", data=upload_data)
        assert response.status_code == 200
        assert "Your scroll has been published successfully!" in response.text

    async def test_upload_form_rejects_empty_html_content(
        self, authenticated_client: AsyncClient, test_db
    ):
        """Test form rejection when HTML content is empty (file not uploaded)."""
        # Create a subject for the test
        subject = Subject(name="Test Subject", description="Test description")
        test_db.add(subject)
        await test_db.commit()
        await test_db.refresh(subject)

        upload_data = {
            "title": "Empty Content Test",
            "authors": "Test Author",
            "subject_id": str(subject.id),
            "abstract": "Testing empty content validation",
            "keywords": "test, empty",
            "html_content": "",  # Empty content (no file uploaded)
            "license": "cc-by-4.0",
            "confirm_rights": "true",
            "action": "publish",
        }

        response = await authenticated_client.post("/upload-form", data=upload_data)
        assert response.status_code == 422
        assert "HTML content is required" in response.text

    async def test_upload_form_with_minimal_html_structure(
        self, authenticated_client: AsyncClient, test_db
    ):
        """Test form accepts minimal but valid HTML structure."""
        # Create a subject for the test
        subject = Subject(name="Test Subject", description="Test description")
        test_db.add(subject)
        await test_db.commit()
        await test_db.refresh(subject)

        minimal_html = "<html><body><h1>Minimal HTML</h1><p>Content</p></body></html>"

        upload_data = {
            "title": "Minimal HTML Test",
            "authors": "Test Author",
            "subject_id": str(subject.id),
            "abstract": "Testing minimal HTML structure",
            "keywords": "minimal, html",
            "html_content": minimal_html,
            "license": "cc-by-4.0",
            "confirm_rights": "true",
            "action": "publish",
        }

        response = await authenticated_client.post("/upload-form", data=upload_data)
        assert response.status_code == 200
        assert "Your scroll has been published successfully!" in response.text

    async def test_upload_form_handles_large_html_content(
        self, authenticated_client: AsyncClient, test_db
    ):
        """Test form handles reasonably large HTML content."""
        # Create a subject for the test
        subject = Subject(name="Test Subject", description="Test description")
        test_db.add(subject)
        await test_db.commit()
        await test_db.refresh(subject)

        # Create large but reasonable HTML content (under 5MB)
        large_content_parts = [
            "<!DOCTYPE html><html><head><title>Large Document</title></head><body>",
            "<h1>Large HTML Document</h1>",
        ]

        # Add many paragraphs to make it large but not excessive
        for i in range(1000):
            large_content_parts.append(f"<p>This is paragraph {i} with some content.</p>")

        large_content_parts.append("</body></html>")
        large_html = "".join(large_content_parts)

        upload_data = {
            "title": "Large HTML Test",
            "authors": "Test Author",
            "subject_id": str(subject.id),
            "abstract": "Testing large HTML content handling",
            "keywords": "large, html",
            "html_content": large_html,
            "license": "cc-by-4.0",
            "confirm_rights": "true",
            "action": "publish",
        }

        response = await authenticated_client.post("/upload-form", data=upload_data)
        assert response.status_code == 200
        assert "Your scroll has been published successfully!" in response.text

    async def test_upload_form_with_interactive_elements(
        self, authenticated_client: AsyncClient, test_db
    ):
        """Test form accepts HTML with interactive JavaScript elements."""
        # Create a subject for the test
        subject = Subject(name="Test Subject", description="Test description")
        test_db.add(subject)
        await test_db.commit()
        await test_db.refresh(subject)

        interactive_html = """<!DOCTYPE html>
<html>
<head>
    <title>Interactive Research</title>
    <style>
        .interactive { padding: 1rem; border: 1px solid #ccc; }
        button { padding: 0.5rem; background: #007bff; color: white; }
    </style>
</head>
<body>
    <h1>Interactive Research Document</h1>
    <div class="interactive">
        <button onclick="showResult()">Run Experiment</button>
        <div id="result"></div>
    </div>
    <script>
        function showResult() {
            document.getElementById('result').innerHTML = 'Experiment completed!';
        }
    </script>
</body>
</html>"""

        upload_data = {
            "title": "Interactive HTML Test",
            "authors": "Test Author",
            "subject_id": str(subject.id),
            "abstract": "Testing interactive HTML elements",
            "keywords": "interactive, javascript",
            "html_content": interactive_html,
            "license": "cc-by-4.0",
            "confirm_rights": "true",
            "action": "publish",
        }

        response = await authenticated_client.post("/upload-form", data=upload_data)
        assert response.status_code == 200
        assert "Your scroll has been published successfully!" in response.text


class TestFileUploadUIElements:
    """Test file upload UI elements are present and functional."""

    async def test_upload_page_contains_file_upload_zone(self, authenticated_client: AsyncClient):
        """Test upload page contains drag and drop file upload zone."""
        response = await authenticated_client.get("/upload")
        assert response.status_code == 200

        # Check for file upload zone elements
        assert 'id="file-upload-zone"' in response.text
        assert 'class="file-upload-zone"' in response.text
        assert 'id="html_file"' in response.text
        assert 'accept=".html,text/html"' in response.text
        assert 'type="hidden"' in response.text  # Hidden html_content field

    async def test_upload_page_contains_validation_messages(
        self, authenticated_client: AsyncClient
    ):
        """Test upload page contains validation message containers."""
        response = await authenticated_client.get("/upload")
        assert response.status_code == 200

        # Check for validation message containers
        assert 'id="file-info"' in response.text
        assert 'id="file-error"' in response.text
        assert 'id="file-success"' in response.text

        # Check for validation text
        assert "Only .html files are accepted" in response.text
        assert "max 5MB" in response.text
        assert "UTF-8 encoded" in response.text

    async def test_upload_page_contains_file_handling_javascript(
        self, authenticated_client: AsyncClient
    ):
        """Test upload page contains JavaScript for file handling."""
        response = await authenticated_client.get("/upload")
        assert response.status_code == 200

        # Check for key JavaScript functions and event handlers
        assert "handleFileSelection" in response.text
        assert "dragover" in response.text
        assert "dragleave" in response.text
        assert "FileReader" in response.text
        assert "readAsText" in response.text
        assert "UTF-8" in response.text
