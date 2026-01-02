"""File validation module for upload security."""

import logging
import os
from pathlib import Path
from typing import Dict, Optional, Tuple

import magic

logger = logging.getLogger(__name__)

# Allowed MIME types
ALLOWED_MIME_TYPES = [
    "text/html",
]

# Dangerous file extensions to block
DANGEROUS_EXTENSIONS = [
    ".exe",
    ".com",
    ".bat",
    ".cmd",
    ".msi",
    ".vbs",
    ".js",
    ".jar",
    ".scr",
    ".app",
    ".deb",
    ".rpm",
    ".dmg",
    ".pkg",
    ".run",
    ".sh",
    ".bash",
    ".ps1",
    ".psm1",
    ".psd1",
    ".ps1xml",
    ".psc1",
    ".reg",
    ".dll",
    ".so",
    ".dylib",
    ".sys",
    ".drv",
    ".lnk",
    ".url",
    ".website",
    ".webloc",
]

# Maximum file size from environment variable (defaults to 50MB)
MAX_SINGLE_FILE_SIZE = int(os.getenv("HTML_UPLOAD_MAX_SIZE", 52428800))


class FileValidator:
    """Validates uploaded files for security and compliance."""

    def __init__(self):
        self.mime = magic.Magic(mime=True)
        self.file_magic = magic.Magic()

    def validate_file(
        self, file_path: str, filename: str
    ) -> Tuple[bool, Optional[Dict[str, str]]]:
        """
        Validate a single uploaded file.

        Args:
            file_path: Path to the uploaded file
            filename: Original filename

        Returns:
            Tuple of (is_valid, error_info)
        """
        # Check file exists
        if not os.path.exists(file_path):
            return False, {"type": "file_not_found", "message": "File not found"}

        # Check file size
        file_size = os.path.getsize(file_path)
        if file_size > MAX_SINGLE_FILE_SIZE:
            return False, {
                "type": "file_too_large",
                "message": f"File size {file_size / 1024 / 1024:.1f}MB exceeds maximum {int(MAX_SINGLE_FILE_SIZE / 1024 / 1024)}MB",
            }

        # Check file extension first (security check)
        file_ext = Path(filename).suffix.lower()
        if file_ext in DANGEROUS_EXTENSIONS:
            return False, {
                "type": "dangerous_extension",
                "message": f"File extension {file_ext} is not allowed for security reasons",
            }

        # Check MIME type
        mime_type = self.mime.from_file(file_path)

        # Special handling for .html files - allow text/plain to proceed to HTML validation
        if file_ext == ".html" and mime_type in ["text/html", "text/plain"]:
            return self._validate_html_file(file_path)

        if mime_type not in ALLOWED_MIME_TYPES:
            return False, {
                "type": "invalid_mime_type",
                "message": f"File type {mime_type} is not allowed. Allowed types: {', '.join(ALLOWED_MIME_TYPES)}",
            }

        # Additional validation based on MIME type
        if mime_type == "text/html":
            return self._validate_html_file(file_path)

        return True, None

    def _validate_html_file(self, file_path: str) -> Tuple[bool, Optional[Dict[str, str]]]:
        """Validate HTML file specifically."""
        try:
            # Check if file is actually HTML by reading content
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read(1024)  # Read first 1KB

            # Basic HTML validation - check for HTML-like content
            if not any(tag in content.lower() for tag in ["<html", "<head", "<body", "<!doctype"]):
                return False, {
                    "type": "invalid_html",
                    "message": "File does not appear to be valid HTML",
                }

            return True, None

        except UnicodeDecodeError:
            return False, {
                "type": "encoding_error",
                "message": "File is not valid UTF-8 encoded text",
            }
        except Exception as e:
            logger.error(f"Error validating HTML file: {e}")
            return False, {"type": "validation_error", "message": "Error validating HTML file"}

    def validate_content_type(self, content: bytes, expected_type: str) -> bool:
        """
        Validate content matches expected type using magic numbers.

        Args:
            content: File content bytes
            expected_type: Expected MIME type

        Returns:
            True if content matches expected type
        """
        try:
            detected_type = magic.from_buffer(content, mime=True)
            return detected_type == expected_type
        except Exception as e:
            logger.error(f"Error detecting content type: {e}")
            return False
