"""Test suite for file upload validation."""

import os
import tempfile

from app.upload.validators import FileValidator


class TestFileValidator:
    """Test file validation functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.validator = FileValidator()
        self.temp_dir = tempfile.mkdtemp()

    def teardown_method(self):
        """Clean up test fixtures."""
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def create_test_file(self, filename, content, binary=False):
        """Helper to create test files."""
        filepath = os.path.join(self.temp_dir, filename)
        mode = "wb" if binary else "w"
        encoding = None if binary else "utf-8"
        with open(filepath, mode, encoding=encoding) as f:
            f.write(content)
        return filepath

    def test_valid_html_file(self):
        """Test validation of valid HTML file."""
        html_content = """
        <!DOCTYPE html>
        <html>
            <head><title>Test</title></head>
            <body><p>Content</p></body>
        </html>
        """
        filepath = self.create_test_file("test.html", html_content)

        is_valid, error = self.validator.validate_file(filepath, "test.html")
        assert is_valid
        assert error is None

    def test_file_not_found(self):
        """Test validation of non-existent file."""
        is_valid, error = self.validator.validate_file("/non/existent/file.html", "file.html")
        assert not is_valid
        assert error["type"] == "file_not_found"

    def test_file_too_large(self):
        """Test validation of oversized file."""
        # Create a file larger than 50MB
        large_content = "x" * (51 * 1024 * 1024)
        filepath = self.create_test_file("large.html", large_content)

        is_valid, error = self.validator.validate_file(filepath, "large.html")
        assert not is_valid
        assert error["type"] == "file_too_large"
        assert "50MB" in error["message"]

    def test_invalid_mime_type(self):
        """Test validation of invalid MIME type."""
        # Create an executable file
        binary_content = b"\x4d\x5a\x90\x00"  # PE executable header
        filepath = self.create_test_file("test.exe", binary_content, binary=True)

        is_valid, error = self.validator.validate_file(filepath, "test.exe")
        assert not is_valid
        assert error["type"] == "invalid_mime_type" or error["type"] == "dangerous_extension"

    def test_dangerous_extensions(self):
        """Test detection of dangerous file extensions."""
        dangerous_files = [
            "script.exe",
            "virus.com",
            "batch.bat",
            "command.cmd",
            "installer.msi",
            "visual.vbs",
            "javascript.js",
            "java.jar",
            "screen.scr",
            "library.dll",
            "shared.so",
        ]

        for filename in dangerous_files:
            # Create a dummy file
            filepath = self.create_test_file(filename, "content")
            is_valid, error = self.validator.validate_file(filepath, filename)
            assert not is_valid
            assert error["type"] == "dangerous_extension"
            assert "not allowed for security reasons" in error["message"]

    def test_invalid_html_detection(self):
        """Test detection of files pretending to be HTML."""
        # File without HTML content
        filepath = self.create_test_file("fake.html", "This is not HTML content")

        is_valid, error = self.validator.validate_file(filepath, "fake.html")
        assert not is_valid
        assert error["type"] == "invalid_html"
        assert "not appear to be valid HTML" in error["message"]

    def test_encoding_validation(self):
        """Test validation of file encoding."""
        # Create file with invalid UTF-8
        binary_content = b"Invalid UTF-8: \xff\xfe"
        filepath = self.create_test_file("bad_encoding.html", binary_content, binary=True)

        is_valid, error = self.validator.validate_file(filepath, "bad_encoding.html")
        assert not is_valid
        assert error["type"] == "encoding_error" or error["type"] == "invalid_html"

    def test_content_type_validation(self):
        """Test content type validation using magic numbers."""
        # Test HTML content
        html_content = b"<!DOCTYPE html><html><body>Test</body></html>"
        assert self.validator.validate_content_type(html_content, "text/html")

        # Test PNG content (simplified header)
        png_content = b"\x89PNG\r\n\x1a\n"
        assert not self.validator.validate_content_type(png_content, "text/html")
