"""Researcher-friendly error messages for zip upload validation failures.

Translates technical ZipValidator errors into plain-language messages that
researchers (who may not be web developers) can understand and act on.
"""

from dataclasses import dataclass, field
import html
import re

# Threshold for "many files" warning
HIGH_FILE_COUNT_THRESHOLD = 200

# Threshold for "large image" warning (10MB)
LARGE_IMAGE_THRESHOLD = 10 * 1024 * 1024


@dataclass
class ZipUploadResult:
    """Structured result of zip upload validation with friendly messages."""

    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    skipped_files: list[str] = field(default_factory=list)

    @property
    def has_errors(self) -> bool:
        return len(self.errors) > 0

    @property
    def has_warnings(self) -> bool:
        return len(self.warnings) > 0

    def format_errors_html(self) -> str:
        if not self.errors:
            return ""
        escaped = [html.escape(e) for e in self.errors]
        items = "".join(f"<li>{e}</li>" for e in escaped)
        return (
            f"<strong>We found some problems with your archive:</strong>"
            f'<ul style="margin-top: 0.5rem; margin-bottom: 0;">{items}</ul>'
        )

    def format_warnings_html(self) -> str:
        if not self.warnings:
            return ""
        escaped = [html.escape(w) for w in self.warnings]
        items = "".join(f"<li>{w}</li>" for w in escaped)
        return f'<ul style="margin-top: 0.5rem; margin-bottom: 0;">{items}</ul>'


# --- Pattern matchers for raw error classification ---

_ARCHIVE_SIZE_RE = re.compile(r"Archive size \((.+?)\) exceeds the (\d+)MB limit")
_UNCOMPRESSED_SIZE_RE = re.compile(r"Total uncompressed size \((.+?)\) exceeds the (\d+)MB limit")
_FILE_COUNT_RE = re.compile(r"Archive contains (\d+) files, maximum is (\d+)")
_DISALLOWED_EXT_RE = re.compile(r"File '(.+?)' has disallowed extension '(.+?)'")
_NESTED_ARCHIVE_RE = re.compile(r"File '(.+?)' is a nested archive")
_COMPRESSION_RATIO_RE = re.compile(r"File '(.+?)' has suspicious compression ratio")
_SVG_FORBIDDEN_TAG_RE = re.compile(r"SVG '(.+?)' contains forbidden <(.+?)> element")
_SVG_EVENT_HANDLER_RE = re.compile(
    r"SVG '(.+?)' contains forbidden event handler attribute '(.+?)'"
)
_SVG_DANGEROUS_HREF_RE = re.compile(r"SVG '(.+?)' contains dangerous href")
_HTML_VALIDATION_RE = re.compile(r"HTML validation error in '(.+?)': (.+)")
_CONTENT_VALIDATION_RE = re.compile(r"Content validation error in '(.+?)': (.+)")
_MIME_SPOOFING_RE = re.compile(r"File '(.+?)' has extension '.+?' but MIME type is '.+?'")
_FILE_SIZE_LIMIT_RE = re.compile(r"File '(.+?)' \((.+?)\) exceeds the (\d+)MB size limit")
_PATH_TRAVERSAL_RE = re.compile(r"Path traversal detected")
_ABSOLUTE_PATH_RE = re.compile(r"Absolute path detected")
_NULL_BYTE_RE = re.compile(r"Null byte detected")
_BACKSLASH_RE = re.compile(r"Backslash detected in path")
_PATH_RESOLVES_RE = re.compile(r"resolves outside extraction directory")
_SYMLINK_RE = re.compile(r"Symlink detected")
_FILENAME_CHARS_RE = re.compile(r"Filename '.+?' contains invalid characters")
_FILENAME_LENGTH_RE = re.compile(r"Filename component '.+?' exceeds")
_RESERVED_NAME_RE = re.compile(r"uses reserved name")
_UTF8_RE = re.compile(r"File '(.+?)' is not valid UTF-8")
_HTML_UTF8_RE = re.compile(r"HTML file '(.+?)' is not valid UTF-8")
_NO_HTML_RE = re.compile(r"Archive must contain at least one .html file")
_CORRUPT_RE = re.compile(r"not a valid zip archive|Could not open archive")
_NOT_FOUND_RE = re.compile(r"Archive file not found")
_SVG_PARSE_RE = re.compile(r"SVG file '(.+?)' could not be parsed")


def translate_zip_errors(
    raw_errors: list[str],
    *,
    skipped_files: list[str] | None = None,
    large_files: list[tuple[str, int]] | None = None,
    file_count: int | None = None,
) -> ZipUploadResult:
    """Translate raw ZipValidator errors into researcher-friendly messages.

    Groups related errors (e.g. multiple forbidden file types) into single messages
    so the researcher gets a clear, actionable summary.

    Args:
        raw_errors: Error strings from ZipValidator.validate()
        skipped_files: Hidden/metadata files that were skipped (for warning)
        large_files: List of (filename, size_bytes) for large image files (for warning)
        file_count: Total file count in archive (for warning if high)
    """
    result = ZipUploadResult()

    # Buckets for grouping related errors
    forbidden_files: list[str] = []
    nested_archives: list[str] = []
    path_issues: list[str] = []
    svg_issues: list[tuple[str, str]] = []  # (filename, description)
    html_issues: list[tuple[str, str]] = []  # (filename, detail)
    content_issues: list[tuple[str, str]] = []
    file_size_issues: list[tuple[str, str]] = []  # (filename, category)
    mime_issues: list[str] = []  # filenames
    utf8_issues: list[str] = []  # filenames

    for err in raw_errors:
        # Archive-level: corrupt
        if _CORRUPT_RE.search(err):
            result.errors.append(
                "We couldn't read your archive. Please try creating a new zip file "
                "from your project folder."
            )
            continue

        # Archive-level: not found
        if _NOT_FOUND_RE.search(err):
            result.errors.append("We couldn't find the uploaded file. Please try uploading again.")
            continue

        # Archive size
        m = _ARCHIVE_SIZE_RE.search(err)
        if m:
            size, limit = m.group(1), m.group(2)
            result.errors.append(
                f"Your archive is {size}, which exceeds our {limit} MB limit. "
                "Large files are usually images or data -- try compressing images "
                "or hosting large datasets externally."
            )
            continue

        # Uncompressed size
        m = _UNCOMPRESSED_SIZE_RE.search(err)
        if m:
            size, limit = m.group(1), m.group(2)
            result.errors.append(
                f"Your archive is too large when extracted ({size}, limit {limit} MB). "
                "Try compressing images or removing unnecessary files."
            )
            continue

        # File count
        m = _FILE_COUNT_RE.search(err)
        if m:
            count, maximum = m.group(1), m.group(2)
            result.errors.append(
                f"Your archive contains {count} files, which is more than our limit "
                f"of {maximum}. Please reduce the number of files or remove "
                "unnecessary ones."
            )
            continue

        # No HTML
        if _NO_HTML_RE.search(err):
            result.errors.append(
                "Your archive doesn't contain an HTML file. Press publishes "
                "HTML research papers -- please include your paper as an .html file."
            )
            continue

        # Disallowed extension -> group
        m = _DISALLOWED_EXT_RE.search(err)
        if m:
            forbidden_files.append(m.group(1))
            continue

        # Nested archive -> group
        m = _NESTED_ARCHIVE_RE.search(err)
        if m:
            nested_archives.append(m.group(1))
            continue

        # Compression ratio (zip bomb)
        if _COMPRESSION_RATIO_RE.search(err):
            result.errors.append(
                "Your archive has an unusual compression pattern. "
                "Please create a standard zip file from your project folder."
            )
            continue

        # SVG forbidden tag
        m = _SVG_FORBIDDEN_TAG_RE.search(err)
        if m:
            svg_issues.append((m.group(1), f"contains a <{m.group(2)}> element"))
            continue

        # SVG event handler
        m = _SVG_EVENT_HANDLER_RE.search(err)
        if m:
            svg_issues.append((m.group(1), "contains interactive code"))
            continue

        # SVG dangerous href
        m = _SVG_DANGEROUS_HREF_RE.search(err)
        if m:
            svg_issues.append((m.group(1), "contains interactive code"))
            continue

        # SVG parse error
        m = _SVG_PARSE_RE.search(err)
        if m:
            svg_issues.append((m.group(1), "could not be read"))
            continue

        # HTML validation error
        m = _HTML_VALIDATION_RE.search(err)
        if m:
            html_issues.append((m.group(1), m.group(2)))
            continue

        # Content validation error
        m = _CONTENT_VALIDATION_RE.search(err)
        if m:
            content_issues.append((m.group(1), m.group(2)))
            continue

        # MIME type spoofing
        m = _MIME_SPOOFING_RE.search(err)
        if m:
            mime_issues.append(m.group(1))
            continue

        # Per-file size limit
        m = _FILE_SIZE_LIMIT_RE.search(err)
        if m:
            file_size_issues.append((m.group(1), m.group(2)))
            continue

        # Path safety issues -> group
        if any(
            p.search(err)
            for p in [
                _PATH_TRAVERSAL_RE,
                _ABSOLUTE_PATH_RE,
                _NULL_BYTE_RE,
                _BACKSLASH_RE,
                _PATH_RESOLVES_RE,
            ]
        ):
            path_issues.append(err)
            continue

        # Symlinks -> path issue
        if _SYMLINK_RE.search(err):
            path_issues.append(err)
            continue

        # Filename issues -> path issue
        if any(
            p.search(err) for p in [_FILENAME_CHARS_RE, _FILENAME_LENGTH_RE, _RESERVED_NAME_RE]
        ):
            path_issues.append(err)
            continue

        # UTF-8 issues
        m = _UTF8_RE.search(err) or _HTML_UTF8_RE.search(err)
        if m:
            utf8_issues.append(m.group(1))
            continue

        # Fallback: pass through unknown errors
        result.errors.append(err)

    # Emit grouped messages

    if forbidden_files:
        file_list = ", ".join(forbidden_files[:5])
        extra = f" (and {len(forbidden_files) - 5} more)" if len(forbidden_files) > 5 else ""
        result.errors.append(
            f"Your archive contains files we can't host: {file_list}{extra}. "
            "Please remove executable or archive files and re-upload. "
            "HTML, CSS, JavaScript, images, fonts, and data files are all fine."
        )

    if nested_archives:
        file_list = ", ".join(nested_archives[:5])
        extra = f" (and {len(nested_archives) - 5} more)" if len(nested_archives) > 5 else ""
        result.errors.append(
            f"Your archive contains other archives: {file_list}{extra}. "
            "Please zip your project folder directly -- don't zip a zip."
        )

    if path_issues:
        result.errors.append(
            "Some files in your archive have unusual paths. "
            "Please re-create the zip from your project folder directly."
        )

    if svg_issues:
        # Group by filename
        seen = {}
        for filename, desc in svg_issues:
            if filename not in seen:
                seen[filename] = desc
        for filename, desc in seen.items():
            result.errors.append(
                f"One of your SVG images ({filename}) {desc}, which we can't "
                "allow for security reasons. Please use a static SVG or convert to PNG."
            )

    if html_issues:
        # Group by file
        by_file: dict[str, list[str]] = {}
        for filename, detail in html_issues:
            by_file.setdefault(filename, []).append(detail)
        for filename, details in by_file.items():
            if len(details) == 1:
                result.errors.append(
                    f"Your HTML file ({filename}) has content we can't accept: {details[0]}"
                )
            else:
                summary = "; ".join(details[:3])
                extra = f" (and {len(details) - 3} more issues)" if len(details) > 3 else ""
                result.errors.append(
                    f"Your HTML file ({filename}) has content we can't accept: {summary}{extra}"
                )

    if content_issues:
        for filename, detail in content_issues:
            result.errors.append(f"Your HTML file ({filename}) has a content issue: {detail}")

    if mime_issues:
        file_list = ", ".join(mime_issues[:3])
        result.errors.append(
            f"Some files don't match their extension ({file_list}). "
            "Please make sure files have the correct extension for their type."
        )

    if file_size_issues:
        for filename, category in file_size_issues:
            result.errors.append(
                f"The file '{filename}' is too large for its type ({category}). "
                "Please reduce the file size or remove it."
            )

    if utf8_issues:
        file_list = ", ".join(utf8_issues[:3])
        result.errors.append(
            f"Some text files are not UTF-8 encoded ({file_list}). "
            "Please save them with UTF-8 encoding."
        )

    # --- Warnings ---

    if skipped_files:
        count = len(skipped_files)
        result.skipped_files = skipped_files
        result.warnings.append(
            f"{count} file{'s were' if count != 1 else ' was'} skipped "
            "(macOS metadata, hidden files) -- this is normal."
        )

    if large_files:
        names = ", ".join(name for name, _ in large_files[:3])
        extra = f" (and {len(large_files) - 3} more)" if len(large_files) > 3 else ""
        result.warnings.append(
            f"Some image files are large (over 10 MB): {names}{extra}. "
            "This may affect loading times for readers."
        )

    if file_count is not None and file_count >= HIGH_FILE_COUNT_THRESHOLD:
        result.warnings.append(
            f"Your archive has {file_count} files. Large archives may take longer to load."
        )

    return result
