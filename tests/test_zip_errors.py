"""Tests for researcher-friendly zip upload error messages."""

import io
import stat
import struct
import zipfile
import zlib

from app.upload.zip_errors import (
    ZipUploadResult,
    translate_zip_errors,
)
from app.upload.zip_validator import ZipValidator


def _make_zip(
    files: dict[str, bytes | str], *, symlinks: list[tuple[str, str]] | None = None
) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, content in files.items():
            if isinstance(content, str):
                content = content.encode("utf-8")
            zf.writestr(name, content)
        if symlinks:
            for link_name, target in symlinks:
                info = zipfile.ZipInfo(link_name)
                info.external_attr = (stat.S_IFLNK | 0o777) << 16
                zf.writestr(info, target.encode("utf-8"))
    return buf.getvalue()


def _minimal_png() -> bytes:
    signature = b"\x89PNG\r\n\x1a\n"

    def _chunk(chunk_type: bytes, data: bytes) -> bytes:
        c = chunk_type + data
        return struct.pack(">I", len(data)) + c + struct.pack(">I", zlib.crc32(c) & 0xFFFFFFFF)

    ihdr_data = struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)
    ihdr = _chunk(b"IHDR", ihdr_data)
    raw_row = b"\x00\xff\xff\xff"
    idat = _chunk(b"IDAT", zlib.compress(raw_row))
    iend = _chunk(b"IEND", b"")
    return signature + ihdr + idat + iend


MINIMAL_PNG = _minimal_png()

MINIMAL_HTML = """<!DOCTYPE html>
<html><head><title>Test</title></head>
<body><p>This is a test academic paper with enough words to pass content validation.
We need at least one hundred words so let us keep writing some more filler text here.
The quick brown fox jumps over the lazy dog multiple times in this paragraph.
Research shows that academic papers need structure and content to be meaningful.
This document serves as a minimal valid HTML file for testing the zip validator.
Additional sentences help us reach the word count threshold for validation.
More text follows to ensure we have sufficient content for the validator.
The final sentence in this paragraph completes our minimal test document.</p></body></html>"""


class TestTranslateZipErrors:
    """Test that technical errors become researcher-friendly messages."""

    def test_no_html_found(self):
        raw_errors = ["Archive must contain at least one .html file."]
        result = translate_zip_errors(raw_errors)
        assert len(result.errors) == 1
        assert "HTML" in result.errors[0]
        assert "include" in result.errors[0].lower() or ".html" in result.errors[0]

    def test_archive_too_large(self):
        raw_errors = ["Archive size (55.3MB) exceeds the 50MB limit."]
        result = translate_zip_errors(raw_errors)
        assert len(result.errors) == 1
        assert "55.3 MB" in result.errors[0] or "55.3MB" in result.errors[0]
        assert "50 MB" in result.errors[0] or "50MB" in result.errors[0]

    def test_uncompressed_too_large(self):
        raw_errors = ["Total uncompressed size (250MB) exceeds the 200MB limit."]
        result = translate_zip_errors(raw_errors)
        assert len(result.errors) == 1
        assert (
            "extracted" in result.errors[0].lower() or "uncompressed" in result.errors[0].lower()
        )

    def test_corrupt_archive(self):
        raw_errors = ["File is not a valid zip archive (corrupt or wrong format)."]
        result = translate_zip_errors(raw_errors)
        assert len(result.errors) == 1
        assert "read" in result.errors[0].lower() or "new zip" in result.errors[0].lower()

    def test_forbidden_files_grouped(self):
        raw_errors = [
            "File 'payload.exe' has disallowed extension '.exe'. Allowed: ...",
            "File 'script.bat' has disallowed extension '.bat'. Allowed: ...",
            "File 'run.sh' has disallowed extension '.sh'. Allowed: ...",
        ]
        result = translate_zip_errors(raw_errors)
        assert len(result.errors) == 1
        assert "payload.exe" in result.errors[0]
        assert "script.bat" in result.errors[0]
        assert "run.sh" in result.errors[0]

    def test_nested_archives_grouped(self):
        raw_errors = [
            "File 'inner.zip' is a nested archive. Nested archives are not allowed.",
            "File 'data.tar.gz' is a nested archive. Nested archives are not allowed.",
        ]
        result = translate_zip_errors(raw_errors)
        assert len(result.errors) == 1
        assert "inner.zip" in result.errors[0]
        assert "data.tar.gz" in result.errors[0]

    def test_path_issues(self):
        raw_errors = [
            "Path traversal detected in '../../../etc/passwd'. Paths containing '..' are not allowed."
        ]
        result = translate_zip_errors(raw_errors)
        assert len(result.errors) == 1
        # Should not expose the path traversal attempt detail
        assert (
            "unusual paths" in result.errors[0].lower() or "re-create" in result.errors[0].lower()
        )

    def test_too_many_files(self):
        raw_errors = ["Archive contains 501 files, maximum is 500."]
        result = translate_zip_errors(raw_errors)
        assert len(result.errors) == 1
        assert "500" in result.errors[0]

    def test_zip_bomb_detected(self):
        raw_errors = [
            "File 'bomb.html' has suspicious compression ratio (150:1). Maximum allowed is 100:1."
        ]
        result = translate_zip_errors(raw_errors)
        assert len(result.errors) == 1
        assert (
            "compression" in result.errors[0].lower() or "standard zip" in result.errors[0].lower()
        )

    def test_svg_security(self):
        raw_errors = ["SVG 'image.svg' contains forbidden <script> element."]
        result = translate_zip_errors(raw_errors)
        assert len(result.errors) == 1
        assert "image.svg" in result.errors[0]
        assert "SVG" in result.errors[0]

    def test_svg_event_handler(self):
        raw_errors = ["SVG 'chart.svg' contains forbidden event handler attribute 'onclick'."]
        result = translate_zip_errors(raw_errors)
        assert len(result.errors) == 1
        assert "chart.svg" in result.errors[0]

    def test_svg_dangerous_href(self):
        raw_errors = ["SVG 'link.svg' contains dangerous href: 'javascript:alert(1)'."]
        result = translate_zip_errors(raw_errors)
        assert len(result.errors) == 1
        assert "link.svg" in result.errors[0]

    def test_html_validation_error(self):
        raw_errors = [
            "HTML validation error in 'index.html': Forbidden tag <iframe> is not allowed"
        ]
        result = translate_zip_errors(raw_errors)
        assert len(result.errors) == 1
        assert "index.html" in result.errors[0]

    def test_multiple_error_categories(self):
        """Multiple different categories should produce multiple user messages."""
        raw_errors = [
            "Archive contains 501 files, maximum is 500.",
            "File 'payload.exe' has disallowed extension '.exe'. Allowed: ...",
        ]
        result = translate_zip_errors(raw_errors)
        assert len(result.errors) == 2

    def test_unknown_error_passes_through(self):
        raw_errors = ["Some completely unexpected error message."]
        result = translate_zip_errors(raw_errors)
        assert len(result.errors) == 1

    def test_mime_spoofing(self):
        raw_errors = [
            "File 'image.png' has extension '.png' but MIME type is 'application/x-executable' (possible type spoofing)."
        ]
        result = translate_zip_errors(raw_errors)
        assert len(result.errors) == 1
        assert "image.png" in result.errors[0]

    def test_file_size_limit(self):
        raw_errors = ["File 'huge.svg' (svg) exceeds the 5MB size limit for its type."]
        result = translate_zip_errors(raw_errors)
        assert len(result.errors) == 1
        assert "huge.svg" in result.errors[0]

    def test_symlink_detected(self):
        raw_errors = ["Symlink detected: 'evil_link'. Symlinks are not allowed."]
        result = translate_zip_errors(raw_errors)
        assert len(result.errors) == 1
        assert "re-create" in result.errors[0].lower() or "unusual" in result.errors[0].lower()


class TestZipUploadResult:
    def test_has_errors(self):
        result = ZipUploadResult(errors=["something wrong"], warnings=[])
        assert result.has_errors is True

    def test_no_errors(self):
        result = ZipUploadResult(errors=[], warnings=[])
        assert result.has_errors is False

    def test_has_warnings(self):
        result = ZipUploadResult(errors=[], warnings=["heads up"])
        assert result.has_warnings is True

    def test_format_errors_html(self):
        result = ZipUploadResult(
            errors=["Error one", "Error two"],
            warnings=["Warning one"],
        )
        html = result.format_errors_html()
        assert "<li>" in html
        assert "Error one" in html
        assert "Error two" in html

    def test_format_warnings_html(self):
        result = ZipUploadResult(
            errors=[],
            warnings=["Some files were skipped"],
            skipped_files=["__MACOSX/._foo", ".DS_Store"],
        )
        html = result.format_warnings_html()
        assert "skipped" in html.lower() or "Some files were skipped" in html

    def test_format_errors_html_escapes_html(self):
        result = ZipUploadResult(
            errors=["Contains <script>alert('xss')</script>"],
            warnings=[],
        )
        html = result.format_errors_html()
        assert "<script>" not in html
        assert "&lt;script&gt;" in html


class TestSkippedFilesWarning:
    """Hidden/skipped files should produce an informational warning."""

    def test_skipped_files_produce_warning(self, tmp_path):
        validator = ZipValidator()
        files = {
            "index.html": MINIMAL_HTML,
            "__MACOSX/._index.html": "apple resource fork",
            ".DS_Store": "\x00\x00",
        }
        data = _make_zip(files)
        archive = tmp_path / "skipped.zip"
        archive.write_bytes(data)

        raw_errors = validator.validate(archive_path=str(archive))
        assert raw_errors == []

        result = translate_zip_errors(
            raw_errors, skipped_files=["__MACOSX/._index.html", ".DS_Store"]
        )
        assert result.has_warnings
        assert any("skipped" in w.lower() for w in result.warnings)

    def test_no_skipped_files_no_warning(self):
        result = translate_zip_errors([], skipped_files=[])
        assert not result.has_warnings


class TestLargeImageWarning:
    def test_large_images_produce_warning(self):
        result = translate_zip_errors(
            [],
            large_files=[("figures/plot.png", 12_000_000)],
        )
        assert result.has_warnings
        assert any("image" in w.lower() or "loading" in w.lower() for w in result.warnings)


class TestHighFileCountWarning:
    def test_many_files_produce_warning(self):
        result = translate_zip_errors(
            [],
            file_count=350,
        )
        assert result.has_warnings
        assert any("350" in w for w in result.warnings)

    def test_few_files_no_warning(self):
        result = translate_zip_errors([], file_count=10)
        assert not result.has_warnings


class TestEndToEndErrorMessages:
    """Integration tests: run validator then translate, check final messages."""

    def test_exe_file_gives_friendly_message(self, tmp_path):
        validator = ZipValidator()
        data = _make_zip({"index.html": MINIMAL_HTML, "payload.exe": b"\x00"})
        archive = tmp_path / "exe.zip"
        archive.write_bytes(data)
        raw_errors = validator.validate(str(archive))
        result = translate_zip_errors(raw_errors)
        assert result.has_errors
        # The message should mention the filename and be understandable
        assert "payload.exe" in result.errors[0]
        assert "can't host" in result.errors[0].lower() or "remove" in result.errors[0].lower()

    def test_no_html_gives_friendly_message(self, tmp_path):
        validator = ZipValidator()
        data = _make_zip({"style.css": "body {}", "app.js": "console.log('hi')"})
        archive = tmp_path / "no_html.zip"
        archive.write_bytes(data)
        raw_errors = validator.validate(str(archive))
        result = translate_zip_errors(raw_errors)
        assert result.has_errors
        assert "html" in result.errors[0].lower()
        assert "include" in result.errors[0].lower() or ".html" in result.errors[0]

    def test_corrupt_zip_gives_friendly_message(self, tmp_path):
        validator = ZipValidator()
        bad_file = tmp_path / "bad.zip"
        bad_file.write_bytes(b"this is not a zip file")
        raw_errors = validator.validate(str(bad_file))
        result = translate_zip_errors(raw_errors)
        assert result.has_errors
        assert "new zip" in result.errors[0].lower() or "read" in result.errors[0].lower()

    def test_researcher_can_understand_all_messages(self, tmp_path):
        """No error message should contain technical jargon."""
        jargon_terms = [
            "null byte",
            "symlink",
            "path traversal",
            "MIME type",
            "compression ratio",
            "external_attr",
            "NFC",
            "unicode",
        ]

        test_cases = [
            (["Archive file not found."], "not found"),
            (["File is not a valid zip archive (corrupt or wrong format)."], "corrupt"),
            (["Symlink detected: 'evil_link'. Symlinks are not allowed."], "symlink"),
            (
                ["Path traversal detected in '../etc'. Paths containing '..' are not allowed."],
                "traversal",
            ),
            (["Null byte detected in filename 'index\\x00.html'."], "null byte"),
            (
                [
                    "File 'image.png' has extension '.png' but MIME type is 'text/plain' (possible type spoofing)."
                ],
                "mime",
            ),
        ]

        for raw_errors, _label in test_cases:
            result = translate_zip_errors(raw_errors)
            for msg in result.errors:
                msg_lower = msg.lower()
                for term in jargon_terms:
                    assert term.lower() not in msg_lower, (
                        f"Jargon '{term}' found in message for {_label}: {msg}"
                    )
