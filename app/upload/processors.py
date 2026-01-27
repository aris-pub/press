"""HTML upload processing module."""

from datetime import datetime, timezone
import hashlib
import logging
from typing import Any, Dict, List, Tuple

from ..security.html_validator import HTMLValidator
from ..security.validation import ContentValidator
from .validators import FileValidator

logger = logging.getLogger(__name__)


class HTMLProcessor:
    """Processes HTML uploads for storage and display."""

    def __init__(self, max_external_links: int = 25):
        self.html_validator = HTMLValidator()
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
            "upload_date": datetime.now(timezone.utc).isoformat(),
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

        # Step 3: Validate HTML security - REJECT if dangerous content found
        is_html_safe, html_errors = self.html_validator.validate(html_content)
        if not is_html_safe:
            errors.extend(html_errors)
            processed_data["validation_status"] = "rejected"
            processed_data["rejection_reason"] = "dangerous_content"
            return False, processed_data, errors

        # Step 4: Validate content quality (spam, external links, etc.)
        is_valid, validation_errors = self.content_validator.validate(html_content)
        if not is_valid:
            errors.extend(validation_errors)
            # Check if any errors are severity 'error' (not just warnings)
            has_blocking_errors = any(e.get("severity") == "error" for e in validation_errors)
            if has_blocking_errors:
                processed_data["validation_status"] = "rejected"
                processed_data["rejection_reason"] = "content_quality"
                return False, processed_data, errors

        # Step 5: Store original HTML (no sanitization needed - validation passed)
        processed_data["html_content"] = html_content

        # Step 6: Extract metadata from clean HTML
        metadata = self._extract_metadata(html_content)
        processed_data.update(metadata)

        # Step 7: Extract external resources (for transparency)
        external_resources = self._extract_external_resources(html_content)
        processed_data["external_resources"] = external_resources

        # Step 8: Calculate content metrics
        metrics = self.content_validator.calculate_content_metrics(html_content)
        processed_data["content_metrics"] = metrics

        # Step 9: Generate content hash for duplicate detection
        content_hash = hashlib.sha256(html_content.encode("utf-8")).hexdigest()
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

    def _extract_external_resources(self, html_content: str) -> List[Dict[str, str]]:
        """Extract list of external resources referenced in HTML."""
        import re

        resources = []

        # Extract images
        img_pattern = re.compile(r'<img[^>]+src=["\']([^"\']+)["\']', re.IGNORECASE)
        for match in img_pattern.finditer(html_content):
            src = match.group(1)
            if src.startswith(("http://", "https://")):
                resources.append({"type": "image", "url": src})

        # Extract stylesheets
        link_pattern = re.compile(
            r'<link[^>]*rel=["\']stylesheet["\'][^>]*href=["\']([^"\']+)["\']', re.IGNORECASE
        )
        for match in link_pattern.finditer(html_content):
            href = match.group(1)
            if href.startswith(("http://", "https://")):
                resources.append({"type": "stylesheet", "url": href})

        # Extract links
        a_pattern = re.compile(r'<a[^>]+href=["\']([^"\']+)["\']', re.IGNORECASE)
        for match in a_pattern.finditer(html_content):
            href = match.group(1)
            if href.startswith(("http://", "https://")):
                resources.append({"type": "link", "url": href})

        return resources
