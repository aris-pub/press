"""Zip archive validation pipeline for secure multi-file uploads."""

import logging
import os
import re
import shutil
import stat
import tempfile
import unicodedata
import zipfile

from defusedxml import ElementTree as DefusedET
import magic

from app.security.html_validator import HTMLValidator
from app.security.validation import ContentValidator

logger = logging.getLogger(__name__)

MAX_ARCHIVE_SIZE = 50 * 1024 * 1024  # 50MB compressed
MAX_TOTAL_UNCOMPRESSED = 200 * 1024 * 1024  # 200MB uncompressed
MAX_FILE_COUNT = 500
MAX_COMPRESSION_RATIO = 100
MAX_FILENAME_LENGTH = 255
CHUNK_SIZE = 8192

ALLOWED_EXTENSIONS = frozenset(
    {
        ".html",
        ".htm",
        ".css",
        ".js",
        ".mjs",
        ".png",
        ".jpg",
        ".jpeg",
        ".gif",
        ".webp",
        ".svg",
        ".woff",
        ".woff2",
        ".ttf",
        ".otf",
        ".eot",
        ".json",
        ".csv",
        ".tsv",
        ".txt",
        ".map",
    }
)

NESTED_ARCHIVE_EXTENSIONS = frozenset(
    {
        ".zip",
        ".tar",
        ".gz",
        ".tgz",
        ".bz2",
        ".xz",
        ".rar",
        ".7z",
        ".jar",
        ".war",
        ".ear",
    }
)

WINDOWS_RESERVED = frozenset(
    {
        "CON",
        "PRN",
        "AUX",
        "NUL",
        "COM1",
        "COM2",
        "COM3",
        "COM4",
        "COM5",
        "COM6",
        "COM7",
        "COM8",
        "COM9",
        "LPT1",
        "LPT2",
        "LPT3",
        "LPT4",
        "LPT5",
        "LPT6",
        "LPT7",
        "LPT8",
        "LPT9",
    }
)

HIDDEN_PREFIXES = ("__MACOSX/", "__MACOSX")
HIDDEN_BASENAMES = frozenset({".DS_Store", "Thumbs.db", "desktop.ini"})

# Filename component pattern: word chars, hyphens, dots, spaces
SAFE_COMPONENT_RE = re.compile(r"^[\w\-. ]+$", re.UNICODE)

# Per-file size limits by category
FILE_SIZE_LIMITS: dict[str, int] = {
    "html": 50 * 1024 * 1024,
    "css": 10 * 1024 * 1024,
    "js": 20 * 1024 * 1024,
    "image": 20 * 1024 * 1024,
    "svg": 5 * 1024 * 1024,
    "font": 10 * 1024 * 1024,
    "data": 50 * 1024 * 1024,
}

# Extension to category mapping
EXTENSION_CATEGORY: dict[str, str] = {
    ".html": "html",
    ".htm": "html",
    ".css": "css",
    ".js": "js",
    ".mjs": "js",
    ".map": "js",
    ".png": "image",
    ".jpg": "image",
    ".jpeg": "image",
    ".gif": "image",
    ".webp": "image",
    ".svg": "svg",
    ".woff": "font",
    ".woff2": "font",
    ".ttf": "font",
    ".otf": "font",
    ".eot": "font",
    ".json": "data",
    ".csv": "data",
    ".tsv": "data",
    ".txt": "data",
}

TEXT_EXTENSIONS = frozenset(
    {".html", ".htm", ".css", ".js", ".mjs", ".json", ".csv", ".tsv", ".txt", ".map"}
)

# Expected MIME patterns per extension (prefix matching)
MIME_EXPECTATIONS: dict[str, list[str]] = {
    ".html": ["text/"],
    ".htm": ["text/"],
    ".css": ["text/"],
    ".js": ["text/", "application/javascript", "application/x-javascript"],
    ".mjs": ["text/", "application/javascript"],
    ".json": ["text/", "application/json"],
    ".csv": ["text/"],
    ".tsv": ["text/"],
    ".txt": ["text/"],
    ".map": ["text/", "application/json"],
    ".png": ["image/png"],
    ".jpg": ["image/jpeg"],
    ".jpeg": ["image/jpeg"],
    ".gif": ["image/gif"],
    ".webp": ["image/webp"],
    ".svg": ["image/svg", "text/xml", "application/xml", "text/html", "text/plain"],
    ".woff": [
        "font/",
        "application/font-woff",
        "application/x-font-woff",
        "application/octet-stream",
    ],
    ".woff2": [
        "font/",
        "application/font-woff2",
        "application/x-font-woff2",
        "application/octet-stream",
    ],
    ".ttf": [
        "font/",
        "application/x-font-ttf",
        "application/font-sfnt",
        "application/octet-stream",
    ],
    ".otf": [
        "font/",
        "application/x-font-opentype",
        "application/font-sfnt",
        "font/otf",
        "application/octet-stream",
        "application/vnd.ms-opentype",
    ],
    ".eot": ["application/vnd.ms-fontobject", "application/octet-stream"],
}

SVG_FORBIDDEN_TAGS = frozenset({"script", "foreignObject", "foreignobject"})
SVG_FORBIDDEN_ATTRS_RE = re.compile(r"^on", re.IGNORECASE)
SVG_DANGEROUS_HREF_RE = re.compile(r"^\s*(javascript|data:text/html):", re.IGNORECASE)


def _is_hidden(name: str) -> bool:
    if any(name.startswith(p) for p in HIDDEN_PREFIXES):
        return True
    basename = os.path.basename(name)
    if basename in HIDDEN_BASENAMES:
        return True
    if basename.startswith("."):
        return True
    return False


def _check_nested_archive(name: str) -> bool:
    """Check if filename looks like a nested archive (handles compound extensions like .tar.gz)."""
    lower = name.lower()
    for ext in NESTED_ARCHIVE_EXTENSIONS:
        if lower.endswith(ext):
            return True
    return False


class ZipValidator:
    """Validates zip archives for secure multi-file upload."""

    def __init__(self):
        self._mime = magic.Magic(mime=True)

    def validate(self, archive_path: str) -> list[str]:
        """Validate a zip archive. Returns list of human-readable error strings (empty = valid)."""
        errors, _ = self._run_validation(archive_path, keep_extracted=False)
        return errors

    def validate_and_extract(self, archive_path: str) -> tuple[list[str], str | None]:
        """Validate and extract. Returns (errors, extract_dir_or_None)."""
        return self._run_validation(archive_path, keep_extracted=True)

    def _run_validation(
        self, archive_path: str, keep_extracted: bool
    ) -> tuple[list[str], str | None]:
        errors: list[str] = []

        # Step 1: Archive size
        try:
            archive_size = os.path.getsize(archive_path)
        except OSError:
            return ["Archive file not found."], None
        if archive_size > MAX_ARCHIVE_SIZE:
            return [
                f"Archive size ({archive_size / 1024 / 1024:.1f}MB) exceeds the 50MB limit."
            ], None

        # Step 2: Open safely
        try:
            zf = zipfile.ZipFile(archive_path, "r")
        except zipfile.BadZipFile:
            return ["File is not a valid zip archive (corrupt or wrong format)."], None
        except Exception as e:
            return [f"Could not open archive: {e}"], None

        temp_dir = None
        try:
            # Step 3: Pre-extraction checks on infolist
            infos = zf.infolist()
            non_hidden = [i for i in infos if not i.is_dir() and not _is_hidden(i.filename)]

            # 3a: File count
            if len(non_hidden) > MAX_FILE_COUNT:
                errors.append(
                    f"Archive contains {len(non_hidden)} files, maximum is {MAX_FILE_COUNT}."
                )

            total_uncompressed = 0
            for info in infos:
                if info.is_dir():
                    continue
                if _is_hidden(info.filename):
                    continue

                name = info.filename

                # 3b: Symlinks
                unix_attrs = info.external_attr >> 16
                if unix_attrs and stat.S_ISLNK(unix_attrs):
                    errors.append(f"Symlink detected: '{name}'. Symlinks are not allowed.")
                    continue

                # 3c: Path safety
                path_errors = self._check_path_safety(name)
                errors.extend(path_errors)
                if path_errors:
                    continue

                # 3d: Filename validation
                name_errors = self._check_filename(name)
                errors.extend(name_errors)

                # 3e: Extension allowlist
                ext = os.path.splitext(name)[1].lower()
                if ext not in ALLOWED_EXTENSIONS:
                    errors.append(
                        f"File '{name}' has disallowed extension '{ext}'. Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}"
                    )

                # 3f: Nested archives
                if _check_nested_archive(name):
                    errors.append(
                        f"File '{name}' is a nested archive. Nested archives are not allowed."
                    )

                # 3g: Accumulate uncompressed size
                total_uncompressed += info.file_size

                # 3h: Compression ratio
                if (
                    info.compress_size > 0
                    and info.file_size / info.compress_size > MAX_COMPRESSION_RATIO
                ):
                    errors.append(
                        f"File '{name}' has suspicious compression ratio "
                        f"({info.file_size / info.compress_size:.0f}:1). "
                        f"Maximum allowed is {MAX_COMPRESSION_RATIO}:1."
                    )

            # 3g: Total uncompressed size
            if total_uncompressed > MAX_TOTAL_UNCOMPRESSED:
                errors.append(
                    f"Total uncompressed size ({total_uncompressed / 1024 / 1024:.0f}MB) "
                    f"exceeds the 200MB limit."
                )

            # If pre-extraction checks found errors, stop here
            if errors:
                return errors, None

            # Step 4: Extract file-by-file
            temp_dir = tempfile.mkdtemp(prefix="press_zip_")
            os.chmod(temp_dir, 0o700)
            extracted_files: list[tuple[str, str]] = []  # (relative_name, full_path)

            for info in infos:
                if info.is_dir():
                    continue
                name = info.filename
                if _is_hidden(name):
                    logger.debug("Skipping hidden file: %s", name)
                    continue

                # NFC normalize the filename
                normalized = unicodedata.normalize("NFC", name)
                target = os.path.join(temp_dir, normalized)

                # Verify resolved path stays under temp_dir
                real_target = os.path.realpath(target)
                real_temp = os.path.realpath(temp_dir)
                if not real_target.startswith(real_temp + os.sep) and real_target != real_temp:
                    errors.append(f"Path '{name}' resolves outside extraction directory.")
                    continue

                # Create parent directories
                os.makedirs(os.path.dirname(target), exist_ok=True)

                # Determine per-file size limit
                ext = os.path.splitext(normalized)[1].lower()
                category = EXTENSION_CATEGORY.get(ext, "data")
                size_limit = FILE_SIZE_LIMITS.get(category, FILE_SIZE_LIMITS["data"])

                # Extract in chunks, tracking actual bytes
                bytes_written = 0
                oversized = False
                with zf.open(info) as src, open(target, "wb") as dst:
                    while True:
                        chunk = src.read(CHUNK_SIZE)
                        if not chunk:
                            break
                        bytes_written += len(chunk)
                        if bytes_written > size_limit:
                            oversized = True
                            break
                        dst.write(chunk)

                if oversized:
                    os.unlink(target)
                    errors.append(
                        f"File '{normalized}' ({category}) exceeds the "
                        f"{size_limit / 1024 / 1024:.0f}MB size limit for its type."
                    )
                    continue

                extracted_files.append((normalized, target))

            if errors:
                shutil.rmtree(temp_dir, ignore_errors=True)
                return errors, None

            # Step 5: Post-extraction validation
            # 5a: Verify no symlinks in extracted tree
            for dirpath, dirnames, filenames in os.walk(temp_dir):
                for name in filenames + dirnames:
                    full = os.path.join(dirpath, name)
                    if os.path.islink(full):
                        errors.append(f"Symlink detected in extracted files: '{name}'.")

            if errors:
                shutil.rmtree(temp_dir, ignore_errors=True)
                return errors, None

            has_html = False
            html_validator = HTMLValidator()
            content_validator = ContentValidator()

            for rel_name, full_path in extracted_files:
                ext = os.path.splitext(rel_name)[1].lower()

                # 5b: MIME check
                mime_errors = self._check_mime(rel_name, full_path, ext)
                errors.extend(mime_errors)

                # 5c: HTML validation
                if ext in (".html", ".htm"):
                    has_html = True
                    html_errors = self._validate_html_file(
                        rel_name, full_path, html_validator, content_validator
                    )
                    errors.extend(html_errors)

                # 5d: SVG validation
                if ext == ".svg":
                    svg_errors = self._validate_svg(rel_name, full_path)
                    errors.extend(svg_errors)

                # 5e: UTF-8 check for text files
                if ext in TEXT_EXTENSIONS:
                    try:
                        with open(full_path, "r", encoding="utf-8") as f:
                            f.read()
                    except UnicodeDecodeError:
                        errors.append(f"File '{rel_name}' is not valid UTF-8.")

            # 5f: Must have at least one HTML file
            if not has_html:
                errors.append("Archive must contain at least one .html file.")

            # Step 6: Cleanup on failure
            if errors:
                shutil.rmtree(temp_dir, ignore_errors=True)
                return errors, None

            if keep_extracted:
                return [], temp_dir
            else:
                shutil.rmtree(temp_dir, ignore_errors=True)
                return [], None

        except Exception as e:
            logger.error("Unexpected error during zip validation: %s", e)
            if temp_dir:
                shutil.rmtree(temp_dir, ignore_errors=True)
            return [f"Unexpected error during validation: {e}"], None
        finally:
            zf.close()

    def _check_path_safety(self, name: str) -> list[str]:
        errors = []
        if ".." in name.split("/"):
            errors.append(
                f"Path traversal detected in '{name}'. Paths containing '..' are not allowed."
            )
        if name.startswith("/"):
            errors.append(f"Absolute path detected: '{name}'. Only relative paths are allowed.")
        if "\x00" in name:
            errors.append(f"Null byte detected in filename '{name!r}'.")
        if "\\" in name:
            errors.append(f"Backslash detected in path '{name}'. Use forward slashes only.")
        return errors

    def _check_filename(self, name: str) -> list[str]:
        errors = []
        # NFC normalize for checking
        normalized = unicodedata.normalize("NFC", name)
        components = normalized.split("/")
        for component in components:
            if not component:
                continue
            if len(component) > MAX_FILENAME_LENGTH:
                errors.append(
                    f"Filename component '{component[:50]}...' exceeds {MAX_FILENAME_LENGTH} characters."
                )
            stem = os.path.splitext(component)[0].upper()
            if stem in WINDOWS_RESERVED:
                errors.append(f"'{component}' uses reserved name '{stem}'.")
            if not SAFE_COMPONENT_RE.match(component):
                errors.append(
                    f"Filename '{component}' contains invalid characters. Only letters, numbers, hyphens, dots, and spaces are allowed."
                )
        return errors

    def _check_mime(self, rel_name: str, full_path: str, ext: str) -> list[str]:
        expected = MIME_EXPECTATIONS.get(ext)
        if not expected:
            return []
        try:
            detected = self._mime.from_file(full_path)
        except Exception:
            return []
        for pattern in expected:
            if detected.startswith(pattern):
                return []
        return [
            f"File '{rel_name}' has extension '{ext}' but MIME type is '{detected}' (possible type spoofing)."
        ]

    def _validate_html_file(
        self,
        rel_name: str,
        full_path: str,
        html_validator: HTMLValidator,
        content_validator: ContentValidator,
    ) -> list[str]:
        errors = []
        try:
            with open(full_path, "r", encoding="utf-8") as f:
                content = f.read()
        except UnicodeDecodeError:
            return [f"HTML file '{rel_name}' is not valid UTF-8."]

        is_valid, html_errors = html_validator.validate(content)
        if not is_valid:
            for err in html_errors:
                msg = err.get("message", str(err))
                errors.append(f"HTML validation error in '{rel_name}': {msg}")

        is_valid, content_errors = content_validator.validate(content)
        if not is_valid:
            for err in content_errors:
                if err.get("severity") == "error":
                    msg = err.get("message", str(err))
                    errors.append(f"Content validation error in '{rel_name}': {msg}")

        return errors

    def _validate_svg(self, rel_name: str, full_path: str) -> list[str]:
        errors = []
        try:
            tree = DefusedET.parse(full_path)
        except Exception as e:
            return [f"SVG file '{rel_name}' could not be parsed: {e}"]

        root = tree.getroot()
        for elem in root.iter():
            # Strip namespace from tag name
            tag = elem.tag.split("}")[-1] if "}" in elem.tag else elem.tag

            if tag in SVG_FORBIDDEN_TAGS:
                errors.append(f"SVG '{rel_name}' contains forbidden <{tag}> element.")

            for attr_name, attr_value in elem.attrib.items():
                # Strip namespace from attribute name
                clean_attr = attr_name.split("}")[-1] if "}" in attr_name else attr_name

                if SVG_FORBIDDEN_ATTRS_RE.match(clean_attr):
                    errors.append(
                        f"SVG '{rel_name}' contains forbidden event handler attribute '{clean_attr}'."
                    )

                if clean_attr.lower() in ("href", "xlink:href") or attr_name.endswith("}href"):
                    if SVG_DANGEROUS_HREF_RE.match(attr_value):
                        errors.append(
                            f"SVG '{rel_name}' contains dangerous href: '{attr_value[:50]}'."
                        )

        return errors
