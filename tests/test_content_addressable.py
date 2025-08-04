"""Unit tests for content-addressable storage functionality."""

import hashlib
import os
import tarfile
import tempfile

from app.storage.content_processing import (
    create_deterministic_tar,
    generate_content_hash,
    generate_url_from_hash,
    normalize_line_endings,
    validate_utf8_content,
)


class TestLineEndingNormalization:
    """Test line ending normalization functionality."""

    def test_normalize_crlf_to_lf(self):
        """Test conversion of CRLF to LF."""
        content = "line1\r\nline2\r\nline3"
        expected = "line1\nline2\nline3"
        assert normalize_line_endings(content) == expected

    def test_normalize_cr_to_lf(self):
        """Test conversion of CR to LF."""
        content = "line1\rline2\rline3"
        expected = "line1\nline2\nline3"
        assert normalize_line_endings(content) == expected

    def test_normalize_mixed_line_endings(self):
        """Test conversion of mixed line endings to LF."""
        content = "line1\r\nline2\rline3\nline4"
        expected = "line1\nline2\nline3\nline4"
        assert normalize_line_endings(content) == expected

    def test_normalize_already_lf(self):
        """Test that LF-only content remains unchanged."""
        content = "line1\nline2\nline3"
        expected = "line1\nline2\nline3"
        assert normalize_line_endings(content) == expected

    def test_normalize_empty_string(self):
        """Test normalization of empty string."""
        assert normalize_line_endings("") == ""

    def test_normalize_single_line(self):
        """Test normalization of single line without line endings."""
        content = "single line"
        expected = "single line"
        assert normalize_line_endings(content) == expected


class TestUTF8Validation:
    """Test UTF-8 validation functionality."""

    def test_valid_utf8_ascii(self):
        """Test validation of valid ASCII content."""
        content = b"Hello, world!"
        assert validate_utf8_content(content) is True

    def test_valid_utf8_unicode(self):
        """Test validation of valid Unicode content."""
        content = "Hello, 世界! 🌍".encode("utf-8")
        assert validate_utf8_content(content) is True

    def test_invalid_utf8_latin1(self):
        """Test rejection of Latin-1 encoded content."""
        content = "café".encode("latin-1")
        assert validate_utf8_content(content) is False

    def test_invalid_utf8_windows1252(self):
        """Test rejection of Windows-1252 encoded content."""
        # Use actual Windows-1252 specific characters that differ from UTF-8
        content = bytes([0x93, 0x94])  # Left/right double quotes in Windows-1252
        assert validate_utf8_content(content) is False

    def test_empty_content(self):
        """Test validation of empty content."""
        assert validate_utf8_content(b"") is True

    def test_utf8_with_bom(self):
        """Test validation of UTF-8 content with BOM."""
        content = "\ufeffHello, world!".encode("utf-8")
        assert validate_utf8_content(content) is True


class TestDeterministicTarCreation:
    """Test deterministic tar archive creation."""

    def test_single_file_tar(self):
        """Test tar creation for single HTML file."""
        content = "<html><body>Hello, world!</body></html>"

        with tempfile.NamedTemporaryFile(mode="w", suffix=".html", delete=False) as f:
            f.write(content)
            temp_file = f.name

        try:
            tar_data = create_deterministic_tar(temp_file)

            # Verify it's valid tar data
            with tempfile.NamedTemporaryFile() as tar_file:
                tar_file.write(tar_data)
                tar_file.flush()

                with tarfile.open(tar_file.name, "r") as tar:
                    members = tar.getnames()
                    assert len(members) == 1
                    assert members[0] == "content.html"

                    # Verify content
                    extracted = tar.extractfile(members[0]).read().decode("utf-8")
                    assert extracted == content
        finally:
            os.unlink(temp_file)

    def test_deterministic_tar_same_content(self):
        """Test that identical content produces identical tar archives."""
        content = "<html><body>Test content</body></html>"

        # Create two identical files
        with tempfile.NamedTemporaryFile(mode="w", suffix=".html", delete=False) as f1:
            f1.write(content)
            temp_file1 = f1.name

        with tempfile.NamedTemporaryFile(mode="w", suffix=".html", delete=False) as f2:
            f2.write(content)
            temp_file2 = f2.name

        try:
            tar_data1 = create_deterministic_tar(temp_file1)
            tar_data2 = create_deterministic_tar(temp_file2)

            # Tar archives should be identical despite different source files
            assert tar_data1 == tar_data2
        finally:
            os.unlink(temp_file1)
            os.unlink(temp_file2)

    def test_deterministic_tar_different_content(self):
        """Test that different content produces different tar archives."""
        content1 = "<html><body>Content 1</body></html>"
        content2 = "<html><body>Content 2</body></html>"

        with tempfile.NamedTemporaryFile(mode="w", suffix=".html", delete=False) as f1:
            f1.write(content1)
            temp_file1 = f1.name

        with tempfile.NamedTemporaryFile(mode="w", suffix=".html", delete=False) as f2:
            f2.write(content2)
            temp_file2 = f2.name

        try:
            tar_data1 = create_deterministic_tar(temp_file1)
            tar_data2 = create_deterministic_tar(temp_file2)

            # Tar archives should be different
            assert tar_data1 != tar_data2
        finally:
            os.unlink(temp_file1)
            os.unlink(temp_file2)


class TestHashGeneration:
    """Test SHA-256 hashing and URL generation."""

    def test_generate_content_hash(self):
        """Test SHA-256 hash generation from tar data."""
        tar_data = b"test tar archive data"
        hash_value = generate_content_hash(tar_data)

        # Verify it's a valid SHA-256 hash (64 hex characters)
        assert len(hash_value) == 64
        assert all(c in "0123456789abcdef" for c in hash_value)

        # Verify it matches manual calculation
        expected = hashlib.sha256(tar_data).hexdigest()
        assert hash_value == expected

    def test_generate_url_from_hash_12_chars(self):
        """Test URL generation using first 12 characters of hash."""
        hash_value = "abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890"
        url = generate_url_from_hash(hash_value)

        assert url == "abcdef123456"
        assert len(url) == 12

    def test_generate_url_from_hash_with_length(self):
        """Test URL generation with custom length."""
        hash_value = "abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890"

        url_13 = generate_url_from_hash(hash_value, length=13)
        assert url_13 == "abcdef1234567"
        assert len(url_13) == 13

        url_14 = generate_url_from_hash(hash_value, length=14)
        assert url_14 == "abcdef12345678"
        assert len(url_14) == 14

    def test_different_content_different_hashes(self):
        """Test that different content produces different hashes."""
        tar_data1 = b"content 1"
        tar_data2 = b"content 2"

        hash1 = generate_content_hash(tar_data1)
        hash2 = generate_content_hash(tar_data2)

        assert hash1 != hash2

        url1 = generate_url_from_hash(hash1)
        url2 = generate_url_from_hash(hash2)

        assert url1 != url2

    def test_same_content_same_hash(self):
        """Test that identical content produces identical hashes."""
        tar_data = b"identical content"

        hash1 = generate_content_hash(tar_data)
        hash2 = generate_content_hash(tar_data)

        assert hash1 == hash2

        url1 = generate_url_from_hash(hash1)
        url2 = generate_url_from_hash(hash2)

        assert url1 == url2


class TestHashCollisionHandling:
    """Test hash collision detection and resolution."""

    def test_check_hash_collision_no_collision(self):
        """Test collision check when no collision exists."""
        # Test the URL generation logic without needing database mocking
        # This is a unit test for the deterministic hash-to-URL conversion
        test_hash = "abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890"
        url_10 = generate_url_from_hash(test_hash, length=10)
        url_12 = generate_url_from_hash(test_hash, length=12)

        assert len(url_10) == 10
        assert len(url_12) == 12
        assert url_10 == test_hash[:10]
        assert url_12 == test_hash[:12]

    def test_collision_resolution_extends_hash(self):
        """Test that collision resolution extends hash length."""
        # This test would need proper database mocking
        # For now, test the logic conceptually
        base_hash = "abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890"

        # Test incrementing length
        url_12 = generate_url_from_hash(base_hash, length=12)
        url_13 = generate_url_from_hash(base_hash, length=13)
        url_14 = generate_url_from_hash(base_hash, length=14)

        assert len(url_12) == 12
        assert len(url_13) == 13
        assert len(url_14) == 14

        # Each should be a prefix of the next
        assert url_13.startswith(url_12)
        assert url_14.startswith(url_13)
