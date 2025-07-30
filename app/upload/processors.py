"""HTML upload processing module."""

from datetime import datetime
import hashlib
import logging
from typing import Any, Dict, List, Tuple

from ..security.sanitizer import HTMLSanitizer
from ..security.validation import ContentValidator
from .validators import FileValidator

logger = logging.getLogger(__name__)


class HTMLProcessor:
    """Processes HTML uploads for storage and display."""

    def __init__(self, max_external_links: int = 10):
        self.sanitizer = HTMLSanitizer()
        self.content_validator = ContentValidator(max_external_links=max_external_links)
        self.file_validator = FileValidator()

    async def process_html_upload(
        self, file_path: str, filename: str, user_id: str
    ) -> Tuple[bool, Dict[str, Any], List[Dict[str, str]]]:
        """
        Process an uploaded HTML file.

        Args:
            file_path: Path to uploaded file
            filename: Original filename
            user_id: ID of uploading user

        Returns:
            Tuple of (success, processed_data, errors)
        """
        errors = []
        processed_data = {
            "original_filename": filename,
            "upload_date": datetime.utcnow().isoformat(),
            "user_id": user_id,
            "validation_status": "pending",
        }

        # Step 1: Validate file
        is_valid, error = self.file_validator.validate_file(file_path, filename)
        if not is_valid:
            errors.append(error)
            processed_data["validation_status"] = "rejected"
            return False, processed_data, errors

        # Step 2: Read file content
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                html_content = f.read()
            processed_data["file_size"] = len(html_content.encode("utf-8"))
        except Exception as e:
            logger.error(f"Error reading file: {e}")
            errors.append({"type": "read_error", "message": "Failed to read file content"})
            return False, processed_data, errors

        # Step 3: Validate content
        is_valid, validation_errors = self.content_validator.validate(html_content)
        if not is_valid:
            errors.extend(validation_errors)
            # Check if any errors are severity 'error' (not just warnings)
            has_blocking_errors = any(e.get("severity") == "error" for e in validation_errors)
            if has_blocking_errors:
                processed_data["validation_status"] = "rejected"
                return False, processed_data, errors

        # Step 4: Sanitize HTML
        sanitized_html, sanitization_log = self.sanitizer.sanitize(html_content)
        processed_data["sanitization_log"] = sanitization_log
        processed_data["html_content"] = sanitized_html

        # Step 5: Extract metadata
        metadata = self._extract_metadata(sanitized_html)
        processed_data.update(metadata)

        # Step 6: Extract external resources
        external_resources = self.sanitizer.extract_external_resources(sanitized_html)
        processed_data["external_resources"] = external_resources

        # Step 7: Calculate content metrics
        metrics = self.content_validator.calculate_content_metrics(sanitized_html)
        processed_data["content_metrics"] = metrics

        # Step 8: Generate content hash for duplicate detection
        content_hash = hashlib.sha256(sanitized_html.encode("utf-8")).hexdigest()
        processed_data["content_hash"] = content_hash

        # Set final status
        processed_data["validation_status"] = "approved"
        processed_data["content_type"] = "html"

        return True, processed_data, errors

    def _extract_metadata(self, html_content: str) -> Dict[str, str]:
        """Extract metadata from HTML content."""
        import re

        metadata = {}

        # Extract title
        title_match = re.search(
            r"<title[^>]*>(.*?)</title>", html_content, re.IGNORECASE | re.DOTALL
        )
        if title_match:
            metadata["title"] = title_match.group(1).strip()
        else:
            # Try to get from first h1
            h1_match = re.search(r"<h1[^>]*>(.*?)</h1>", html_content, re.IGNORECASE | re.DOTALL)
            if h1_match:
                # Remove any nested tags
                title_text = re.sub(r"<[^>]+>", "", h1_match.group(1))
                metadata["title"] = title_text.strip()

        # Extract meta description
        desc_match = re.search(
            r'<meta\s+name=["\']description["\']\s+content=["\']([^"\']+)["\']',
            html_content,
            re.IGNORECASE,
        )
        if desc_match:
            metadata["description"] = desc_match.group(1).strip()

        # Extract meta keywords
        keywords_match = re.search(
            r'<meta\s+name=["\']keywords["\']\s+content=["\']([^"\']+)["\']',
            html_content,
            re.IGNORECASE,
        )
        if keywords_match:
            metadata["keywords"] = keywords_match.group(1).strip()

        # Extract author from meta tag
        author_match = re.search(
            r'<meta\s+name=["\']author["\']\s+content=["\']([^"\']+)["\']',
            html_content,
            re.IGNORECASE,
        )
        if author_match:
            metadata["author"] = author_match.group(1).strip()

        return metadata
