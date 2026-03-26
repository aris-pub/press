"""Archive processing pipeline for zip uploads.

Handles validation, entry point detection, directory flattening,
deterministic hashing, and Tigris storage for multi-file archives.
"""

import hashlib
import io
import logging
import mimetypes
import os
import shutil
import tarfile
import tempfile

from sqlalchemy.ext.asyncio import AsyncSession

from app.storage.backend import StorageBackend
from app.storage.content_processing import (
    check_hash_collision,
    generate_url_from_hash,
    resolve_hash_collision,
)
from app.upload.entry_point import detect_entry_point_with_sizes
from app.upload.zip_validator import ZipValidator

logger = logging.getLogger(__name__)


class ArchiveResult:
    """Result of processing a zip archive."""

    __slots__ = (
        "entry_point",
        "html_files",
        "all_files",
        "manifest",
        "total_size",
        "file_count",
        "url_hash",
        "content_hash",
        "extracted_dir",
    )

    def __init__(
        self,
        *,
        entry_point: str,
        html_files: list[str],
        all_files: list[str],
        manifest: dict[str, dict],
        total_size: int,
        file_count: int,
        url_hash: str,
        content_hash: str,
        extracted_dir: str,
    ):
        self.entry_point = entry_point
        self.html_files = html_files
        self.all_files = all_files
        self.manifest = manifest
        self.total_size = total_size
        self.file_count = file_count
        self.url_hash = url_hash
        self.content_hash = content_hash
        self.extracted_dir = extracted_dir


async def process_zip_upload(
    archive_path: str,
    db: AsyncSession,
) -> tuple[list[str], ArchiveResult | None]:
    """Validate and process a zip archive for upload.

    Returns:
        (errors, result) - errors is empty on success, result is None on failure.
    """
    validator = ZipValidator()
    errors, extracted_dir = validator.validate_and_extract(archive_path)
    if errors:
        return errors, None

    try:
        return await _process_extracted(extracted_dir, archive_path, db)
    except Exception as e:
        logger.error("Archive processing failed: %s", e)
        if extracted_dir:
            shutil.rmtree(extracted_dir, ignore_errors=True)
        return [f"Archive processing failed: {e}"], None


async def _process_extracted(
    extracted_dir: str,
    archive_path: str,
    db: AsyncSession,
) -> tuple[list[str], ArchiveResult | None]:
    """Process already-validated extracted files."""
    # Build file inventory
    all_files: list[str] = []
    html_files: list[str] = []
    file_sizes: dict[str, int] = {}

    for dirpath, _, filenames in os.walk(extracted_dir):
        for fname in filenames:
            full = os.path.join(dirpath, fname)
            rel = os.path.relpath(full, extracted_dir)
            all_files.append(rel)
            size = os.path.getsize(full)
            file_sizes[rel] = size
            if rel.lower().endswith((".html", ".htm")):
                html_files.append(rel)

    html_file_sizes = {f: file_sizes[f] for f in html_files}
    entry_point = detect_entry_point_with_sizes(html_file_sizes)

    # Flatten directory structure so entry point is at root
    flattened_dir = _flatten_directory(extracted_dir, entry_point)

    # Rebuild inventory after flattening
    all_files_flat: list[str] = []
    html_files_flat: list[str] = []
    manifest: dict[str, dict] = {}
    total_size = 0

    for dirpath, _, filenames in os.walk(flattened_dir):
        for fname in filenames:
            full = os.path.join(dirpath, fname)
            rel = os.path.relpath(full, flattened_dir)
            size = os.path.getsize(full)
            ct = mimetypes.guess_type(fname)[0] or "application/octet-stream"
            all_files_flat.append(rel)
            manifest[rel] = {"size": size, "content_type": ct}
            total_size += size
            if rel.lower().endswith((".html", ".htm")):
                html_files_flat.append(rel)

    # Compute entry point path after flattening (should be at root now)
    entry_point_flat = os.path.basename(entry_point)
    if entry_point_flat not in all_files_flat:
        entry_point_flat = entry_point  # fallback if flattening didn't apply

    # Generate content hash from deterministic zip
    content_hash = _deterministic_archive_hash(flattened_dir)
    url_hash = generate_url_from_hash(content_hash, 12)
    if await check_hash_collision(db, url_hash):
        url_hash = await resolve_hash_collision(db, content_hash)

    return [], ArchiveResult(
        entry_point=entry_point_flat,
        html_files=sorted(html_files_flat),
        all_files=sorted(all_files_flat),
        manifest=manifest,
        total_size=total_size,
        file_count=len(all_files_flat),
        url_hash=url_hash,
        content_hash=content_hash,
        extracted_dir=flattened_dir,
    )


def _flatten_directory(extracted_dir: str, entry_point: str) -> str:
    """Flatten directory so the entry point's parent becomes the root.

    If entry_point is "my-paper/index.html", strip "my-paper/" prefix from
    all paths so that index.html ends up at root level.
    """
    entry_dir = os.path.dirname(entry_point)
    if not entry_dir:
        return extracted_dir  # Already at root

    source_root = os.path.join(extracted_dir, entry_dir)
    if not os.path.isdir(source_root):
        return extracted_dir  # Safety fallback

    flat_dir = tempfile.mkdtemp(prefix="press_flat_")
    os.chmod(flat_dir, 0o700)

    for dirpath, _, filenames in os.walk(source_root):
        for fname in filenames:
            src = os.path.join(dirpath, fname)
            rel = os.path.relpath(src, source_root)
            dst = os.path.join(flat_dir, rel)
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copy2(src, dst)

    # Also copy files outside the entry point directory (e.g. shared assets)
    for dirpath, _, filenames in os.walk(extracted_dir):
        rel_dir = os.path.relpath(dirpath, extracted_dir)
        # Skip the entry point directory itself (already copied)
        if rel_dir == entry_dir or rel_dir.startswith(entry_dir + os.sep):
            continue
        for fname in filenames:
            src = os.path.join(dirpath, fname)
            rel = os.path.relpath(src, extracted_dir)
            dst = os.path.join(flat_dir, rel)
            if not os.path.exists(dst):
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                shutil.copy2(src, dst)

    shutil.rmtree(extracted_dir, ignore_errors=True)
    return flat_dir


def _deterministic_archive_hash(directory: str) -> str:
    """Create a deterministic hash of directory contents.

    Sorts entries alphabetically, normalizes line endings on text files,
    uses fixed timestamps, then hashes the resulting tar.
    """
    tar_data = _create_deterministic_tar_from_dir(directory)
    return hashlib.sha256(tar_data).hexdigest()


def _create_deterministic_tar_from_dir(directory: str) -> bytes:
    """Create a deterministic tar archive from a directory."""
    buf = io.BytesIO()
    entries: list[str] = []
    for dirpath, _, filenames in os.walk(directory):
        for fname in sorted(filenames):
            full = os.path.join(dirpath, fname)
            rel = os.path.relpath(full, directory)
            entries.append(rel)
    entries.sort()

    text_exts = {
        ".html",
        ".htm",
        ".css",
        ".js",
        ".mjs",
        ".json",
        ".csv",
        ".tsv",
        ".txt",
        ".map",
        ".svg",
    }

    with tarfile.open(fileobj=buf, mode="w") as tar:
        for rel in entries:
            full = os.path.join(directory, rel)
            with open(full, "rb") as f:
                data = f.read()

            ext = os.path.splitext(rel)[1].lower()
            if ext in text_exts:
                # Normalize line endings for text files
                text = data.decode("utf-8", errors="replace")
                text = text.replace("\r\n", "\n").replace("\r", "\n")
                data = text.encode("utf-8")

            info = tarfile.TarInfo(name=rel.replace("\\", "/"))
            info.size = len(data)
            info.mtime = 0
            info.uid = 0
            info.gid = 0
            info.uname = ""
            info.gname = ""
            info.mode = 0o644
            tar.addfile(info, fileobj=io.BytesIO(data))

    return buf.getvalue()


async def store_archive_files(
    storage: StorageBackend,
    extracted_dir: str,
    url_hash: str,
) -> None:
    """Upload all extracted files to Tigris under scrolls/{url_hash}/."""
    for dirpath, _, filenames in os.walk(extracted_dir):
        for fname in filenames:
            full = os.path.join(dirpath, fname)
            rel = os.path.relpath(full, extracted_dir)
            key = f"scrolls/{url_hash}/{rel}"
            ct = mimetypes.guess_type(fname)[0] or "application/octet-stream"
            with open(full, "rb") as f:
                data = f.read()
            await storage.put(key, data, content_type=ct)


async def store_original_zip(
    storage: StorageBackend,
    archive_path: str,
    url_hash: str,
) -> None:
    """Store the original zip file in Tigris for immutable archival."""
    key = f"scrolls/{url_hash}/_original.zip"
    with open(archive_path, "rb") as f:
        data = f.read()
    await storage.put(key, data, content_type="application/zip")


def cleanup_extracted(extracted_dir: str | None) -> None:
    """Clean up extracted directory if it exists."""
    if extracted_dir and os.path.isdir(extracted_dir):
        shutil.rmtree(extracted_dir, ignore_errors=True)
