"""Content validation module for spam prevention and basic checks."""

from collections import Counter
import logging
import re
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class ContentValidator:
    """Validates HTML content for spam and basic academic structure."""

    def __init__(self, max_external_links: int = 10, min_word_count: int = 100):
        self.max_external_links = max_external_links
        self.min_word_count = min_word_count
        self.spam_keywords = [
            "buy now",
            "click here",
            "limited offer",
            "act now",
            "guarantee",
            "risk free",
            "winner",
            "prize",
            "congratulations",
            "urgent",
            "viagra",
            "cialis",
            "casino",
            "lottery",
            "weight loss",
        ]

    def validate(self, html_content: str) -> Tuple[bool, List[Dict[str, str]]]:
        """
        Validate HTML content for spam and basic requirements.

        Args:
            html_content: HTML content to validate

        Returns:
            Tuple of (is_valid, validation_errors)
        """
        errors = []

        # Check for excessive external links
        link_validation = self._validate_external_links(html_content)
        if link_validation:
            errors.append(link_validation)

        # Check for keyword stuffing
        keyword_validation = self._check_keyword_stuffing(html_content)
        if keyword_validation:
            errors.append(keyword_validation)

        # Check for basic academic structure
        structure_validation = self._validate_academic_structure(html_content)
        if structure_validation:
            errors.extend(structure_validation)

        # Check for spam keywords
        spam_validation = self._check_spam_keywords(html_content)
        if spam_validation:
            errors.append(spam_validation)

        # Check minimum word count
        word_count_validation = self._validate_word_count(html_content)
        if word_count_validation:
            errors.append(word_count_validation)

        is_valid = len(errors) == 0
        return is_valid, errors

    def _validate_external_links(self, content: str) -> Optional[Dict[str, str]]:
        """Check for excessive external links."""
        # Extract all external links
        link_pattern = re.compile(r'<a[^>]+href=["\']https?://[^"\']+["\']', re.IGNORECASE)
        external_links = link_pattern.findall(content)

        if len(external_links) > self.max_external_links:
            return {
                "type": "excessive_links",
                "message": f"Content contains {len(external_links)} external links, maximum allowed is {self.max_external_links}",
                "severity": "error",
            }
        return None

    def _check_keyword_stuffing(self, content: str) -> Optional[Dict[str, str]]:
        """Detect keyword stuffing patterns."""
        # Remove HTML tags for text analysis
        text = re.sub(r"<[^>]+>", " ", content)
        text = re.sub(r"\s+", " ", text).lower()

        # Split into words
        words = text.split()
        if len(words) < 10:
            return None

        # Check for repetitive patterns
        word_freq = Counter(words)
        total_words = len(words)

        # Check if any word appears too frequently (more than 5% of content)
        for word, count in word_freq.most_common(10):
            if len(word) > 3 and count / total_words > 0.05:
                return {
                    "type": "keyword_stuffing",
                    "message": f'Potential keyword stuffing detected: "{word}" appears {count} times ({count / total_words * 100:.1f}% of content)',
                    "severity": "warning",
                }

        return None

    def _validate_academic_structure(self, content: str) -> List[Dict[str, str]]:
        """Check for basic academic document structure."""
        errors = []

        # Check for title
        if not re.search(r"<title[^>]*>.*?</title>", content, re.IGNORECASE):
            if not re.search(r"<h1[^>]*>.*?</h1>", content, re.IGNORECASE):
                errors.append(
                    {
                        "type": "missing_title",
                        "message": "Document must have a title (either <title> or <h1> tag)",
                        "severity": "error",
                    }
                )

        # Check for some content structure (paragraphs or sections)
        has_paragraphs = bool(re.search(r"<p[^>]*>.*?</p>", content, re.IGNORECASE | re.DOTALL))
        has_sections = bool(
            re.search(r"<section[^>]*>.*?</section>", content, re.IGNORECASE | re.DOTALL)
        )
        has_articles = bool(
            re.search(r"<article[^>]*>.*?</article>", content, re.IGNORECASE | re.DOTALL)
        )

        if not (has_paragraphs or has_sections or has_articles):
            errors.append(
                {
                    "type": "missing_content_structure",
                    "message": "Document must contain structured content (paragraphs, sections, or articles)",
                    "severity": "error",
                }
            )

        return errors

    def _check_spam_keywords(self, content: str) -> Optional[Dict[str, str]]:
        """Check for common spam keywords."""
        # Remove HTML tags for text analysis
        text = re.sub(r"<[^>]+>", " ", content)
        text = text.lower()

        found_keywords = []
        for keyword in self.spam_keywords:
            if keyword in text:
                found_keywords.append(keyword)

        if found_keywords:
            return {
                "type": "spam_keywords",
                "message": f"Content contains potential spam keywords: {', '.join(found_keywords)}",
                "severity": "warning",
            }

        return None

    def _validate_word_count(self, content: str) -> Optional[Dict[str, str]]:
        """Validate minimum word count."""
        # Remove HTML tags
        text = re.sub(r"<[^>]+>", " ", content)
        text = re.sub(r"\s+", " ", text).strip()

        # Count words
        words = text.split()
        word_count = len(words)

        if word_count < self.min_word_count:
            return {
                "type": "insufficient_content",
                "message": f"Document contains only {word_count} words, minimum required is {self.min_word_count}",
                "severity": "error",
            }

        return None

    def calculate_content_metrics(self, html_content: str) -> Dict[str, any]:
        """Calculate various content metrics for logging and analysis."""
        # Remove HTML tags for text analysis
        text = re.sub(r"<[^>]+>", " ", html_content)
        text = re.sub(r"\s+", " ", text).strip()

        # Basic metrics
        word_count = len(text.split())
        char_count = len(text)

        # Count specific elements
        metrics = {
            "word_count": word_count,
            "char_count": char_count,
            "paragraph_count": len(re.findall(r"<p\b[^>]*>", html_content, re.IGNORECASE)),
            "heading_count": len(re.findall(r"<h[1-6]\b[^>]*>", html_content, re.IGNORECASE)),
            "link_count": len(re.findall(r"<a\b[^>]*>", html_content, re.IGNORECASE)),
            "image_count": len(re.findall(r"<img\b[^>]*>", html_content, re.IGNORECASE)),
            "table_count": len(re.findall(r"<table\b[^>]*>", html_content, re.IGNORECASE)),
            "list_count": len(re.findall(r"<[uo]l\b[^>]*>", html_content, re.IGNORECASE)),
            "code_block_count": len(re.findall(r"<pre\b[^>]*>", html_content, re.IGNORECASE)),
        }

        # Calculate readability metrics (simplified)
        sentences = re.split(r"[.!?]+", text)
        sentence_count = len([s for s in sentences if s.strip()])
        avg_words_per_sentence = word_count / sentence_count if sentence_count > 0 else 0

        metrics["sentence_count"] = sentence_count
        metrics["avg_words_per_sentence"] = round(avg_words_per_sentence, 2)

        return metrics
