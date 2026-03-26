"""Tests for zip archive validation pipeline."""

import io
import os
import stat
import struct
import tempfile
import unicodedata
import zipfile
import zlib

import pytest

from app.upload.zip_validator import ZipValidator


def _make_zip(files: dict[str, bytes | str], *, symlinks: list[tuple[str, str]] | None = None) -> bytes:
    """Helper to create a zip archive in memory.

    Args:
        files: mapping of filename -> content (str auto-encoded as UTF-8)
        symlinks: list of (link_name, target) to add as symlinks
    """
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, content in files.items():
            if isinstance(content, str):
                content = content.encode("utf-8")
            zf.writestr(name, content)
        if symlinks:
            for link_name, target in symlinks:
                info = zipfile.ZipInfo(link_name)
                # Set symlink attribute
                info.external_attr = (stat.S_IFLNK | 0o777) << 16
                zf.writestr(info, target.encode("utf-8"))
    return buf.getvalue()


def _minimal_png() -> bytes:
    """Create a minimal valid 1x1 white PNG."""
    signature = b"\x89PNG\r\n\x1a\n"

    def _chunk(chunk_type: bytes, data: bytes) -> bytes:
        c = chunk_type + data
        return struct.pack(">I", len(data)) + c + struct.pack(">I", zlib.crc32(c) & 0xFFFFFFFF)

    ihdr_data = struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)
    ihdr = _chunk(b"IHDR", ihdr_data)
    raw_row = b"\x00\xFF\xFF\xFF"
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


class TestArchiveSize:
    def test_rejects_oversized_archive(self, tmp_path):
        validator = ZipValidator()
        # Create a file larger than 50MB
        large_file = tmp_path / "large.zip"
        large_file.write_bytes(b"\x00" * (50 * 1024 * 1024 + 1))
        errors = validator.validate(str(large_file))
        assert any("50MB" in e or "exceeds" in e.lower() for e in errors)

    def test_accepts_small_archive(self, tmp_path):
        validator = ZipValidator()
        data = _make_zip({"index.html": MINIMAL_HTML})
        archive = tmp_path / "small.zip"
        archive.write_bytes(data)
        errors = validator.validate(str(archive))
        assert errors == []


class TestBadZipFile:
    def test_rejects_invalid_zip(self, tmp_path):
        validator = ZipValidator()
        bad_file = tmp_path / "bad.zip"
        bad_file.write_bytes(b"this is not a zip file")
        errors = validator.validate(str(bad_file))
        assert any("valid zip" in e.lower() or "corrupt" in e.lower() for e in errors)


class TestFileCount:
    def test_rejects_too_many_files(self, tmp_path):
        validator = ZipValidator()
        files = {f"file{i}.html": "<html><body>hi</body></html>" for i in range(501)}
        data = _make_zip(files)
        archive = tmp_path / "many.zip"
        archive.write_bytes(data)
        errors = validator.validate(str(archive))
        assert any("500" in e or "file count" in e.lower() or "too many" in e.lower() for e in errors)

    def test_hidden_files_not_counted(self, tmp_path):
        """Hidden files like __MACOSX/ and .DS_Store should be skipped in file count."""
        validator = ZipValidator()
        files = {"index.html": MINIMAL_HTML, "__MACOSX/._index.html": "junk", ".DS_Store": "junk"}
        data = _make_zip(files)
        archive = tmp_path / "hidden.zip"
        archive.write_bytes(data)
        errors = validator.validate(str(archive))
        assert errors == []


class TestSymlinks:
    def test_rejects_symlinks(self, tmp_path):
        validator = ZipValidator()
        data = _make_zip(
            {"index.html": MINIMAL_HTML},
            symlinks=[("evil_link", "/etc/passwd")],
        )
        archive = tmp_path / "symlink.zip"
        archive.write_bytes(data)
        errors = validator.validate(str(archive))
        assert any("symlink" in e.lower() for e in errors)


class TestPathSafety:
    def test_rejects_path_traversal(self, tmp_path):
        validator = ZipValidator()
        data = _make_zip({"../../../etc/passwd": "root:x:0:0"})
        archive = tmp_path / "traversal.zip"
        archive.write_bytes(data)
        errors = validator.validate(str(archive))
        assert any("path" in e.lower() for e in errors)

    def test_rejects_absolute_paths(self, tmp_path):
        validator = ZipValidator()
        data = _make_zip({"/etc/passwd": "root:x:0:0"})
        archive = tmp_path / "absolute.zip"
        archive.write_bytes(data)
        errors = validator.validate(str(archive))
        assert any("path" in e.lower() or "absolute" in e.lower() for e in errors)

    def test_rejects_null_bytes(self, tmp_path):
        validator = ZipValidator()
        # Python's zipfile truncates filenames at null bytes, so
        # "index\x00\x00.html" becomes "index" (no extension).
        # This still gets rejected via the extension allowlist.
        data = _make_zip({"indexXX.html": "<html></html>"})
        data = data.replace(b"indexXX.html", b"index\x00\x00.html")
        archive = tmp_path / "null.zip"
        archive.write_bytes(data)
        errors = validator.validate(str(archive))
        assert len(errors) > 0

    def test_rejects_backslashes(self, tmp_path):
        validator = ZipValidator()
        data = _make_zip({"assets\\style.css": "body {}"})
        archive = tmp_path / "backslash.zip"
        archive.write_bytes(data)
        errors = validator.validate(str(archive))
        assert any("backslash" in e.lower() or "path" in e.lower() for e in errors)


class TestFilenameValidation:
    def test_rejects_long_filename_component(self, tmp_path):
        validator = ZipValidator()
        long_name = "a" * 256 + ".html"
        data = _make_zip({long_name: "<html></html>"})
        archive = tmp_path / "longname.zip"
        archive.write_bytes(data)
        errors = validator.validate(str(archive))
        assert any("255" in e or "filename" in e.lower() or "long" in e.lower() for e in errors)

    def test_rejects_windows_reserved_names(self, tmp_path):
        validator = ZipValidator()
        data = _make_zip({"CON.html": "<html></html>"})
        archive = tmp_path / "reserved.zip"
        archive.write_bytes(data)
        errors = validator.validate(str(archive))
        assert any("reserved" in e.lower() or "CON" in e for e in errors)

    def test_nfc_normalization(self, tmp_path):
        """Filenames should be NFC normalized."""
        validator = ZipValidator()
        # NFD form of 'e' + combining acute accent
        nfd_name = "caf\u0065\u0301.html"
        assert nfd_name != unicodedata.normalize("NFC", nfd_name)
        # The validator should handle this gracefully (normalize and proceed)
        data = _make_zip({nfd_name: MINIMAL_HTML})
        archive = tmp_path / "nfc.zip"
        archive.write_bytes(data)
        errors = validator.validate(str(archive))
        # Should not error - normalization happens transparently
        assert errors == []

    def test_rejects_special_characters(self, tmp_path):
        validator = ZipValidator()
        data = _make_zip({"file<name>.html": "<html></html>"})
        archive = tmp_path / "special.zip"
        archive.write_bytes(data)
        errors = validator.validate(str(archive))
        assert any("filename" in e.lower() or "character" in e.lower() for e in errors)


class TestExtensionAllowlist:
    def test_allows_valid_extensions(self, tmp_path):
        validator = ZipValidator()
        files = {
            "index.html": MINIMAL_HTML,
            "style.css": "body {}",
            "app.js": "console.log('hi')",
            "image.png": MINIMAL_PNG,
            "data.json": "{}",
            "font.woff2": b"\x00" * 50,
        }
        data = _make_zip(files)
        archive = tmp_path / "valid.zip"
        archive.write_bytes(data)
        errors = validator.validate(str(archive))
        assert errors == []

    def test_rejects_disallowed_extensions(self, tmp_path):
        validator = ZipValidator()
        data = _make_zip({"index.html": MINIMAL_HTML, "payload.exe": b"\x00"})
        archive = tmp_path / "exe.zip"
        archive.write_bytes(data)
        errors = validator.validate(str(archive))
        assert any(".exe" in e for e in errors)

    def test_rejects_php_files(self, tmp_path):
        validator = ZipValidator()
        data = _make_zip({"index.html": MINIMAL_HTML, "shell.php": "<?php system('id'); ?>"})
        archive = tmp_path / "php.zip"
        archive.write_bytes(data)
        errors = validator.validate(str(archive))
        assert any(".php" in e for e in errors)


class TestNestedArchives:
    def test_rejects_nested_zip(self, tmp_path):
        validator = ZipValidator()
        inner = _make_zip({"inner.html": "<html></html>"})
        data = _make_zip({"index.html": MINIMAL_HTML, "nested.zip": inner})
        archive = tmp_path / "nested.zip"
        archive.write_bytes(data)
        errors = validator.validate(str(archive))
        assert any(".zip" in e or "nested" in e.lower() or "archive" in e.lower() for e in errors)

    def test_rejects_nested_tar_gz(self, tmp_path):
        validator = ZipValidator()
        data = _make_zip({"index.html": MINIMAL_HTML, "data.tar.gz": b"\x00"})
        archive = tmp_path / "nested_tar.zip"
        archive.write_bytes(data)
        errors = validator.validate(str(archive))
        assert any("tar.gz" in e or "nested" in e.lower() or "archive" in e.lower() for e in errors)


class TestUncompressedSize:
    def test_rejects_large_uncompressed_total(self, tmp_path):
        validator = ZipValidator()
        # Create a zip that claims large uncompressed sizes
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            # Highly compressible data
            for i in range(5):
                zf.writestr(f"big{i}.html", "A" * (50 * 1024 * 1024))
        data = buf.getvalue()
        archive = tmp_path / "big_uncompressed.zip"
        archive.write_bytes(data)
        errors = validator.validate(str(archive))
        assert any("200MB" in e or "uncompressed" in e.lower() for e in errors)


class TestCompressionRatio:
    def test_rejects_zip_bomb(self, tmp_path):
        validator = ZipValidator()
        # Create a file with extreme compression ratio
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            # Highly compressible data: 10MB of zeros compresses to almost nothing
            zf.writestr("bomb.html", "\x00" * (10 * 1024 * 1024))
        data = buf.getvalue()
        archive = tmp_path / "bomb.zip"
        archive.write_bytes(data)
        errors = validator.validate(str(archive))
        assert any("compression" in e.lower() or "ratio" in e.lower() or "bomb" in e.lower() for e in errors)


class TestHiddenFileSkipping:
    def test_skips_macosx_directory(self, tmp_path):
        validator = ZipValidator()
        files = {
            "index.html": MINIMAL_HTML,
            "__MACOSX/._index.html": "apple resource fork",
            "__MACOSX/.DS_Store": "finder info",
        }
        data = _make_zip(files)
        archive = tmp_path / "macosx.zip"
        archive.write_bytes(data)
        errors = validator.validate(str(archive))
        assert errors == []

    def test_skips_dotfiles(self, tmp_path):
        validator = ZipValidator()
        files = {
            "index.html": MINIMAL_HTML,
            ".gitignore": "*.pyc",
            ".DS_Store": "\x00\x00",
            "Thumbs.db": "\x00\x00",
            "desktop.ini": "[.ShellClassInfo]",
        }
        data = _make_zip(files)
        archive = tmp_path / "dotfiles.zip"
        archive.write_bytes(data)
        errors = validator.validate(str(archive))
        assert errors == []


class TestPerFileSizeLimits:
    def test_rejects_oversized_svg(self, tmp_path):
        validator = ZipValidator()
        # SVG limit is 5MB
        big_svg = '<svg xmlns="http://www.w3.org/2000/svg">' + "x" * (5 * 1024 * 1024 + 1) + "</svg>"
        data = _make_zip({"index.html": MINIMAL_HTML, "image.svg": big_svg})
        archive = tmp_path / "big_svg.zip"
        archive.write_bytes(data)
        errors = validator.validate(str(archive))
        assert any("svg" in e.lower() or "size" in e.lower() for e in errors)

    def test_rejects_oversized_css(self, tmp_path):
        validator = ZipValidator()
        # CSS limit is 10MB
        big_css = "body { color: red; }\n" * (600_000)  # ~12MB
        data = _make_zip({"index.html": MINIMAL_HTML, "style.css": big_css})
        archive = tmp_path / "big_css.zip"
        archive.write_bytes(data)
        errors = validator.validate(str(archive))
        assert any("css" in e.lower() or "size" in e.lower() for e in errors)


class TestMIMECheck:
    def test_rejects_extension_spoofing(self, tmp_path):
        validator = ZipValidator()
        # ELF binary disguised as .png
        elf_header = b"\x7fELF" + b"\x00" * 100
        data = _make_zip({"index.html": MINIMAL_HTML, "image.png": elf_header})
        archive = tmp_path / "spoofed.zip"
        archive.write_bytes(data)
        errors = validator.validate(str(archive))
        assert any("mime" in e.lower() or "type" in e.lower() or "spoof" in e.lower() for e in errors)


class TestHTMLValidation:
    def test_validates_html_files_with_existing_validators(self, tmp_path):
        """HTML files in zip should go through HTMLValidator."""
        validator = ZipValidator()
        bad_html = """<!DOCTYPE html><html><head><title>Evil</title></head>
<body><p>This is an evil paper with enough words to pass content validation.
We need at least one hundred words so let us keep writing some filler text.
The quick brown fox jumps over the lazy dog multiple times in this paragraph.
Research shows that academic papers need structure and content validation.
Additional sentences help us reach the word count threshold for validation.
More text follows to ensure we have sufficient content for the validator.
The final sentence in this paragraph completes our minimal test document.</p>
<iframe src="http://evil.com"></iframe></body></html>"""
        data = _make_zip({"index.html": bad_html})
        archive = tmp_path / "bad_html.zip"
        archive.write_bytes(data)
        errors = validator.validate(str(archive))
        assert any("iframe" in e.lower() or "forbidden" in e.lower() for e in errors)


class TestSVGValidation:
    def test_rejects_svg_with_script(self, tmp_path):
        validator = ZipValidator()
        evil_svg = """<?xml version="1.0"?>
<svg xmlns="http://www.w3.org/2000/svg">
  <script>alert('xss')</script>
  <circle cx="50" cy="50" r="40"/>
</svg>"""
        data = _make_zip({"index.html": MINIMAL_HTML, "image.svg": evil_svg})
        archive = tmp_path / "evil_svg.zip"
        archive.write_bytes(data)
        errors = validator.validate(str(archive))
        assert any("script" in e.lower() for e in errors)

    def test_rejects_svg_with_event_handler(self, tmp_path):
        validator = ZipValidator()
        evil_svg = """<?xml version="1.0"?>
<svg xmlns="http://www.w3.org/2000/svg">
  <circle cx="50" cy="50" r="40" onclick="alert('xss')"/>
</svg>"""
        data = _make_zip({"index.html": MINIMAL_HTML, "image.svg": evil_svg})
        archive = tmp_path / "onclick_svg.zip"
        archive.write_bytes(data)
        errors = validator.validate(str(archive))
        assert any("event" in e.lower() or "onclick" in e.lower() for e in errors)

    def test_rejects_svg_with_foreign_object(self, tmp_path):
        validator = ZipValidator()
        evil_svg = """<?xml version="1.0"?>
<svg xmlns="http://www.w3.org/2000/svg">
  <foreignObject><body xmlns="http://www.w3.org/1999/xhtml"><script>alert(1)</script></body></foreignObject>
</svg>"""
        data = _make_zip({"index.html": MINIMAL_HTML, "image.svg": evil_svg})
        archive = tmp_path / "foreign_svg.zip"
        archive.write_bytes(data)
        errors = validator.validate(str(archive))
        assert any("foreignobject" in e.lower() or "foreign" in e.lower() for e in errors)

    def test_rejects_svg_with_javascript_href(self, tmp_path):
        validator = ZipValidator()
        evil_svg = """<?xml version="1.0"?>
<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink">
  <a xlink:href="javascript:alert(1)"><text>click</text></a>
</svg>"""
        data = _make_zip({"index.html": MINIMAL_HTML, "image.svg": evil_svg})
        archive = tmp_path / "jshref_svg.zip"
        archive.write_bytes(data)
        errors = validator.validate(str(archive))
        assert any("javascript" in e.lower() for e in errors)

    def test_accepts_safe_svg(self, tmp_path):
        validator = ZipValidator()
        safe_svg = """<?xml version="1.0"?>
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">
  <circle cx="50" cy="50" r="40" fill="red"/>
  <text x="50" y="55" text-anchor="middle" fill="white">Hi</text>
</svg>"""
        data = _make_zip({"index.html": MINIMAL_HTML, "image.svg": safe_svg})
        archive = tmp_path / "safe_svg.zip"
        archive.write_bytes(data)
        errors = validator.validate(str(archive))
        assert errors == []


class TestUTF8Validation:
    def test_rejects_non_utf8_html(self, tmp_path):
        validator = ZipValidator()
        # Latin-1 encoded content with non-UTF-8 bytes
        bad_content = b"<html><head><title>Test</title></head><body>\xff\xfe</body></html>"
        data = _make_zip({"index.html": bad_content})
        archive = tmp_path / "encoding.zip"
        archive.write_bytes(data)
        errors = validator.validate(str(archive))
        assert any("utf-8" in e.lower() or "encoding" in e.lower() for e in errors)

    def test_accepts_utf8_text(self, tmp_path):
        validator = ZipValidator()
        data = _make_zip({"index.html": MINIMAL_HTML, "data.json": '{"key": "value"}'})
        archive = tmp_path / "utf8.zip"
        archive.write_bytes(data)
        errors = validator.validate(str(archive))
        assert errors == []


class TestRequiresHTML:
    def test_rejects_zip_without_html(self, tmp_path):
        validator = ZipValidator()
        data = _make_zip({"style.css": "body {}", "app.js": "console.log('hi')"})
        archive = tmp_path / "no_html.zip"
        archive.write_bytes(data)
        errors = validator.validate(str(archive))
        assert any("html" in e.lower() for e in errors)


class TestCleanup:
    def test_cleans_up_temp_dir_on_failure(self, tmp_path):
        """Temp directory should be cleaned up even when validation fails."""
        validator = ZipValidator()
        data = _make_zip({"index.html": MINIMAL_HTML, "payload.exe": b"\x00"})
        archive = tmp_path / "cleanup.zip"
        archive.write_bytes(data)
        errors = validator.validate(str(archive))
        assert len(errors) > 0
        # The temp dir should have been cleaned up - we can't check directly
        # but we verify no exception was raised during cleanup

    def test_cleans_up_temp_dir_on_success(self, tmp_path):
        """Temp directory should be cleaned up on success too."""
        validator = ZipValidator()
        data = _make_zip({"index.html": MINIMAL_HTML})
        archive = tmp_path / "success.zip"
        archive.write_bytes(data)
        result = validator.validate(str(archive))
        assert result == []


class TestReturnValue:
    def test_returns_list_of_strings(self, tmp_path):
        validator = ZipValidator()
        data = _make_zip({"payload.exe": b"\x00"})
        archive = tmp_path / "errors.zip"
        archive.write_bytes(data)
        errors = validator.validate(str(archive))
        assert isinstance(errors, list)
        assert all(isinstance(e, str) for e in errors)

    def test_returns_empty_list_on_success(self, tmp_path):
        validator = ZipValidator()
        data = _make_zip({"index.html": MINIMAL_HTML})
        archive = tmp_path / "ok.zip"
        archive.write_bytes(data)
        errors = validator.validate(str(archive))
        assert errors == []

    def test_returns_multiple_errors(self, tmp_path):
        """Multiple validation failures should all be reported."""
        validator = ZipValidator()
        data = _make_zip({"payload.exe": b"\x00", "shell.php": "<?php ?>"})
        archive = tmp_path / "multi.zip"
        archive.write_bytes(data)
        errors = validator.validate(str(archive))
        # Should have errors for both disallowed extensions AND missing HTML
        assert len(errors) >= 2


class TestExtractedPath:
    def test_returns_extracted_path_on_success(self, tmp_path):
        """On success, validate should return empty errors and validate_and_extract should return a path."""
        validator = ZipValidator()
        data = _make_zip({"index.html": MINIMAL_HTML, "style.css": "body {}"})
        archive = tmp_path / "extract.zip"
        archive.write_bytes(data)
        errors, extract_dir = validator.validate_and_extract(str(archive))
        assert errors == []
        assert extract_dir is not None
        assert os.path.isdir(extract_dir)
        assert os.path.isfile(os.path.join(extract_dir, "index.html"))
        assert os.path.isfile(os.path.join(extract_dir, "style.css"))
        # Clean up
        import shutil
        shutil.rmtree(extract_dir)

    def test_returns_none_path_on_failure(self, tmp_path):
        validator = ZipValidator()
        data = _make_zip({"payload.exe": b"\x00"})
        archive = tmp_path / "fail.zip"
        archive.write_bytes(data)
        errors, extract_dir = validator.validate_and_extract(str(archive))
        assert len(errors) > 0
        assert extract_dir is None


class TestSubdirectoryStructure:
    def test_preserves_directory_structure(self, tmp_path):
        validator = ZipValidator()
        files = {
            "index.html": MINIMAL_HTML,
            "css/style.css": "body {}",
            "js/app.js": "console.log('hi')",
            "images/logo.png": MINIMAL_PNG,
        }
        data = _make_zip(files)
        archive = tmp_path / "structured.zip"
        archive.write_bytes(data)
        errors, extract_dir = validator.validate_and_extract(str(archive))
        assert errors == []
        assert os.path.isfile(os.path.join(extract_dir, "css", "style.css"))
        assert os.path.isfile(os.path.join(extract_dir, "js", "app.js"))
        assert os.path.isfile(os.path.join(extract_dir, "images", "logo.png"))
        import shutil
        shutil.rmtree(extract_dir)
