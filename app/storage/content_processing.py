"""Content processing utilities for content-addressable storage."""

import hashlib
import os
import tempfile

from sqlalchemy.ext.asyncio import AsyncSession


def normalize_line_endings(content: str) -> str:
    """
    Normalize all line endings to Unix format (LF only).

    Converts CRLF (\r\n) and CR (\r) to LF (\n).

    Args:
        content: String content with potentially mixed line endings

    Returns:
        String with normalized Unix line endings
    """
    # First replace CRLF with LF, then replace any remaining CR with LF
    return content.replace("\r\n", "\n").replace("\r", "\n")


def validate_utf8_content(content: bytes) -> bool:
    """
    Validate that content is valid UTF-8 encoded.

    Args:
        content: Byte content to validate

    Returns:
        True if content is valid UTF-8, False otherwise
    """
    try:
        content.decode("utf-8")
        return True
    except UnicodeDecodeError:
        return False


def create_deterministic_tar(file_path: str) -> bytes:
    """
    Create deterministic tar archive using available tar with compatibility flags.

    Uses these flags for determinism (compatible with both GNU and BSD tar):
    - Fixed timestamp via Python tarfile module for better compatibility
    - Zero ownership
    - Consistent file ordering

    Args:
        file_path: Path to file to include in tar archive

    Returns:
        Tar archive data as bytes
    """
    import tarfile

    with tempfile.NamedTemporaryFile() as tar_file:
        # Use fixed filename for determinism regardless of source file name
        filename = "content.html"

        # Use Python tarfile for better cross-platform compatibility
        with tarfile.open(tar_file.name, "w") as tar:
            # Read the file content
            with open(file_path, "rb") as f:
                file_data = f.read()

            # Create tarinfo with deterministic metadata
            tarinfo = tarfile.TarInfo(name=filename)
            tarinfo.size = len(file_data)
            tarinfo.mtime = 0  # Unix epoch for determinism
            tarinfo.uid = 0
            tarinfo.gid = 0
            tarinfo.uname = ""
            tarinfo.gname = ""
            tarinfo.mode = 0o644

            # Add file to tar with deterministic metadata
            from io import BytesIO

            tar.addfile(tarinfo, fileobj=BytesIO(file_data))

        # Read the tar data
        tar_file.seek(0)
        return tar_file.read()


def generate_content_hash(tar_data: bytes) -> str:
    """
    Generate SHA-256 hash of tar archive data.

    Args:
        tar_data: Tar archive data as bytes

    Returns:
        SHA-256 hash as lowercase hex string
    """
    return hashlib.sha256(tar_data).hexdigest()


def generate_url_from_hash(hash_value: str, length: int = 12) -> str:
    """
    Generate URL path from hash using specified number of characters.

    Args:
        hash_value: SHA-256 hash as hex string
        length: Number of characters to use from hash (default 12)

    Returns:
        URL path string (hash prefix)
    """
    return hash_value[:length]


async def check_hash_collision(session: AsyncSession, hash_prefix: str) -> bool:
    """
    Check if a hash prefix already exists in the database (for different content).

    Args:
        session: Database session
        hash_prefix: Hash prefix to check for collision

    Returns:
        True if collision exists, False otherwise
    """
    # Import here to avoid circular imports
    from sqlalchemy import select

    from app.models.scroll import Scroll

    result = await session.execute(select(Scroll).where(Scroll.url_hash == hash_prefix).limit(1))
    return result.scalar_one_or_none() is not None


async def resolve_hash_collision(
    session: AsyncSession, hash_value: str, start_length: int = 12
) -> str:
    """
    Resolve hash collision by extending hash length until unique or matching content found.

    Args:
        session: Database session
        hash_value: Full SHA-256 hash
        start_length: Starting length to try

    Returns:
        Unique hash prefix
    """
    # Import here to avoid circular imports
    from sqlalchemy import select

    from app.models.scroll import Scroll

    for length in range(start_length, len(hash_value) + 1):
        hash_prefix = generate_url_from_hash(hash_value, length)

        # Check if this prefix is already used
        result = await session.execute(
            select(Scroll).where(Scroll.url_hash == hash_prefix).limit(1)
        )
        existing_scroll = result.scalar_one_or_none()

        if not existing_scroll:
            # No conflict, use this prefix
            return hash_prefix
        elif existing_scroll.content_hash == hash_value:
            # Same content, can reuse the same prefix
            return hash_prefix
        # else: different content with same prefix, try longer

    # This should never happen with SHA-256, but just in case
    raise ValueError("Unable to resolve hash collision - this should not occur with SHA-256")


def process_html_content(content: str) -> tuple[str, bytes]:
    """
    Process HTML content for content-addressable storage.

    Args:
        content: Raw HTML content string

    Returns:
        Tuple of (normalized_content, tar_data)
    """
    # Normalize line endings
    normalized_content = normalize_line_endings(content)

    # Create temporary file with normalized content
    with tempfile.NamedTemporaryFile(mode="w", suffix=".html", delete=False) as temp_file:
        temp_file.write(normalized_content)
        temp_file_path = temp_file.name

    try:
        # Create deterministic tar
        tar_data = create_deterministic_tar(temp_file_path)
        return normalized_content, tar_data
    finally:
        # Clean up temporary file
        os.unlink(temp_file_path)


async def generate_permanent_url(session: AsyncSession, content: str) -> tuple[str, str, bytes]:
    """
    Generate permanent URL for HTML content.

    Args:
        session: Database session
        content: HTML content string

    Returns:
        Tuple of (permanent_url, content_hash, tar_data)
    """
    # Process content
    normalized_content, tar_data = process_html_content(content)

    # Generate hash
    content_hash = generate_content_hash(tar_data)

    # Generate initial 12-character URL hash
    url_hash = generate_url_from_hash(content_hash, 12)

    # Only resolve collisions if there's actually a collision
    if await check_hash_collision(session, url_hash):
        url_hash = await resolve_hash_collision(session, content_hash)

    return url_hash, content_hash, tar_data
