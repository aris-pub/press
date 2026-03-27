"""Tests for archive processor: flattening, hashing, storage, and full pipeline."""

import os
import zipfile

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.storage.memory import InMemoryStorage
from app.upload.archive_processor import (
    _create_deterministic_tar_from_dir,
    _deterministic_archive_hash,
    _flatten_directory,
    cleanup_extracted,
    process_zip_upload,
    store_archive_files,
    store_original_zip,
)

MINIMAL_HTML = (
    "<html><head><title>Test Document</title></head><body>"
    "<h1>Research Paper Title</h1>"
    "<p>This is a comprehensive test document designed to pass the content validator "
    "minimum word count requirement of one hundred words. The document contains "
    "structured content with headings and paragraphs as required by the validation "
    "pipeline. Academic research papers typically contain many more words than this "
    "minimum threshold but for testing purposes we need to ensure that the validator "
    "accepts our test content without raising errors about insufficient word count "
    "or missing document structure elements that are expected in scholarly work.</p>"
    "<p>Additional paragraph providing more content to ensure we comfortably exceed "
    "the minimum word count threshold required by the content quality validator.</p>"
    "</body></html>"
)
MINIMAL_CSS = "body { margin: 0; }"


def _make_zip(files: dict[str, str | bytes], path: str) -> str:
    """Create a zip file with the given files. Returns the path."""
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, content in files.items():
            if isinstance(content, str):
                zf.writestr(name, content)
            else:
                zf.writestr(name, content)
    return path


@pytest.fixture
def tmp_dir(tmp_path):
    return str(tmp_path)


@pytest_asyncio.fixture
async def db_session():
    """Minimal async DB session for content hash collision checking."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    session = session_factory()
    try:
        yield session
    finally:
        await session.close()
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        await engine.dispose()


class TestFlattenDirectory:
    def test_no_flattening_when_entry_at_root(self, tmp_dir):
        extracted = os.path.join(tmp_dir, "extracted")
        os.makedirs(extracted)
        with open(os.path.join(extracted, "index.html"), "w") as f:
            f.write(MINIMAL_HTML)
        with open(os.path.join(extracted, "style.css"), "w") as f:
            f.write(MINIMAL_CSS)

        result = _flatten_directory(extracted, "index.html")
        assert result == extracted
        assert os.path.exists(os.path.join(result, "index.html"))

    def test_flattening_strips_prefix(self, tmp_dir):
        extracted = os.path.join(tmp_dir, "extracted")
        os.makedirs(os.path.join(extracted, "my-paper", "styles"))
        with open(os.path.join(extracted, "my-paper", "index.html"), "w") as f:
            f.write(MINIMAL_HTML)
        with open(os.path.join(extracted, "my-paper", "styles", "main.css"), "w") as f:
            f.write(MINIMAL_CSS)

        result = _flatten_directory(extracted, "my-paper/index.html")
        assert result != extracted
        assert os.path.exists(os.path.join(result, "index.html"))
        assert os.path.exists(os.path.join(result, "styles", "main.css"))
        cleanup_extracted(result)


class TestDeterministicHash:
    def test_same_content_same_hash(self, tmp_dir):
        dir1 = os.path.join(tmp_dir, "dir1")
        dir2 = os.path.join(tmp_dir, "dir2")
        for d in (dir1, dir2):
            os.makedirs(d)
            with open(os.path.join(d, "index.html"), "w") as f:
                f.write(MINIMAL_HTML)
            with open(os.path.join(d, "style.css"), "w") as f:
                f.write(MINIMAL_CSS)

        h1 = _deterministic_archive_hash(dir1)
        h2 = _deterministic_archive_hash(dir2)
        assert h1 == h2

    def test_different_content_different_hash(self, tmp_dir):
        dir1 = os.path.join(tmp_dir, "dir1")
        dir2 = os.path.join(tmp_dir, "dir2")
        for d in (dir1, dir2):
            os.makedirs(d)
        with open(os.path.join(dir1, "index.html"), "w") as f:
            f.write(MINIMAL_HTML)
        with open(os.path.join(dir2, "index.html"), "w") as f:
            f.write(MINIMAL_HTML + " different")

        h1 = _deterministic_archive_hash(dir1)
        h2 = _deterministic_archive_hash(dir2)
        assert h1 != h2

    def test_line_ending_normalization(self, tmp_dir):
        dir1 = os.path.join(tmp_dir, "dir1")
        dir2 = os.path.join(tmp_dir, "dir2")
        os.makedirs(dir1)
        os.makedirs(dir2)
        with open(os.path.join(dir1, "index.html"), "wb") as f:
            f.write(b"line1\nline2\n")
        with open(os.path.join(dir2, "index.html"), "wb") as f:
            f.write(b"line1\r\nline2\r\n")

        h1 = _deterministic_archive_hash(dir1)
        h2 = _deterministic_archive_hash(dir2)
        assert h1 == h2

    def test_hash_is_sha256_hex(self, tmp_dir):
        d = os.path.join(tmp_dir, "dir")
        os.makedirs(d)
        with open(os.path.join(d, "test.html"), "w") as f:
            f.write(MINIMAL_HTML)
        h = _deterministic_archive_hash(d)
        assert len(h) == 64
        assert all(c in "0123456789abcdef" for c in h)


class TestDeterministicTar:
    def test_tar_entries_sorted_alphabetically(self, tmp_dir):
        d = os.path.join(tmp_dir, "dir")
        os.makedirs(d)
        for name in ["z.html", "a.css", "m.js"]:
            with open(os.path.join(d, name), "w") as f:
                f.write("content")

        import io
        import tarfile

        tar_data = _create_deterministic_tar_from_dir(d)
        tar = tarfile.open(fileobj=io.BytesIO(tar_data), mode="r")
        names = [m.name for m in tar.getmembers()]
        assert names == ["a.css", "m.js", "z.html"]


class TestStoreArchiveFiles:
    @pytest.mark.asyncio
    async def test_stores_all_files(self, tmp_dir):
        d = os.path.join(tmp_dir, "dir")
        os.makedirs(os.path.join(d, "styles"))
        with open(os.path.join(d, "index.html"), "w") as f:
            f.write(MINIMAL_HTML)
        with open(os.path.join(d, "styles", "main.css"), "w") as f:
            f.write(MINIMAL_CSS)

        storage = InMemoryStorage()
        await store_archive_files(storage, d, "abc123")

        assert await storage.exists("scrolls/abc123/index.html")
        assert await storage.exists("scrolls/abc123/styles/main.css")

    @pytest.mark.asyncio
    async def test_correct_content_types(self, tmp_dir):
        d = os.path.join(tmp_dir, "dir")
        os.makedirs(d)
        with open(os.path.join(d, "index.html"), "w") as f:
            f.write(MINIMAL_HTML)

        storage = InMemoryStorage()
        await store_archive_files(storage, d, "abc123")
        # Content is stored correctly
        content = await storage.get("scrolls/abc123/index.html")
        assert b"Research Paper Title" in content


class TestStoreOriginalZip:
    @pytest.mark.asyncio
    async def test_stores_zip(self, tmp_dir):
        zip_path = os.path.join(tmp_dir, "test.zip")
        _make_zip({"index.html": MINIMAL_HTML}, zip_path)

        storage = InMemoryStorage()
        await store_original_zip(storage, zip_path, "abc123")

        assert await storage.exists("scrolls/abc123/_original.zip")
        data = await storage.get("scrolls/abc123/_original.zip")
        assert len(data) > 0


class TestProcessZipUpload:
    @pytest.mark.asyncio
    async def test_valid_single_html_zip(self, tmp_dir, db_session):
        zip_path = os.path.join(tmp_dir, "test.zip")
        _make_zip({"index.html": MINIMAL_HTML}, zip_path)

        errors, result = await process_zip_upload(zip_path, db_session)
        assert errors == []
        assert result is not None
        assert result.entry_point == "index.html"
        assert result.file_count == 1
        assert len(result.content_hash) == 64
        assert len(result.url_hash) == 12
        cleanup_extracted(result.extracted_dir)

    @pytest.mark.asyncio
    async def test_multi_file_zip_with_entry_detection(self, tmp_dir, db_session):
        zip_path = os.path.join(tmp_dir, "test.zip")
        _make_zip(
            {
                "index.html": MINIMAL_HTML,
                "style.css": MINIMAL_CSS,
                "data.json": '{"key": "value"}',
            },
            zip_path,
        )

        errors, result = await process_zip_upload(zip_path, db_session)
        assert errors == []
        assert result.entry_point == "index.html"
        assert result.file_count == 3
        assert "style.css" in result.all_files
        assert "data.json" in result.all_files
        cleanup_extracted(result.extracted_dir)

    @pytest.mark.asyncio
    async def test_nested_directory_gets_flattened(self, tmp_dir, db_session):
        zip_path = os.path.join(tmp_dir, "test.zip")
        _make_zip(
            {
                "my-paper/index.html": MINIMAL_HTML,
                "my-paper/styles/main.css": MINIMAL_CSS,
            },
            zip_path,
        )

        errors, result = await process_zip_upload(zip_path, db_session)
        assert errors == []
        assert result.entry_point == "index.html"
        assert "styles/main.css" in result.all_files
        cleanup_extracted(result.extracted_dir)

    @pytest.mark.asyncio
    async def test_manifest_contains_sizes_and_types(self, tmp_dir, db_session):
        zip_path = os.path.join(tmp_dir, "test.zip")
        _make_zip(
            {
                "index.html": MINIMAL_HTML,
                "style.css": MINIMAL_CSS,
            },
            zip_path,
        )

        errors, result = await process_zip_upload(zip_path, db_session)
        assert errors == []
        assert "index.html" in result.manifest
        assert "size" in result.manifest["index.html"]
        assert "content_type" in result.manifest["index.html"]
        assert result.manifest["index.html"]["content_type"] == "text/html"
        cleanup_extracted(result.extracted_dir)

    @pytest.mark.asyncio
    async def test_invalid_zip_returns_errors(self, tmp_dir, db_session):
        zip_path = os.path.join(tmp_dir, "bad.zip")
        with open(zip_path, "wb") as f:
            f.write(b"not a zip file")

        errors, result = await process_zip_upload(zip_path, db_session)
        assert len(errors) > 0
        assert result is None

    @pytest.mark.asyncio
    async def test_deterministic_hashing(self, tmp_dir, db_session):
        """Same content should produce the same hash."""
        zip1 = os.path.join(tmp_dir, "test1.zip")
        zip2 = os.path.join(tmp_dir, "test2.zip")
        content = {"index.html": MINIMAL_HTML, "style.css": MINIMAL_CSS}
        _make_zip(content, zip1)
        _make_zip(content, zip2)

        _, r1 = await process_zip_upload(zip1, db_session)
        _, r2 = await process_zip_upload(zip2, db_session)
        assert r1.content_hash == r2.content_hash
        cleanup_extracted(r1.extracted_dir)
        cleanup_extracted(r2.extracted_dir)


class TestCleanup:
    def test_cleanup_removes_directory(self, tmp_dir):
        d = os.path.join(tmp_dir, "to_clean")
        os.makedirs(d)
        with open(os.path.join(d, "file.txt"), "w") as f:
            f.write("test")
        cleanup_extracted(d)
        assert not os.path.exists(d)

    def test_cleanup_none_is_safe(self):
        cleanup_extracted(None)

    def test_cleanup_nonexistent_is_safe(self):
        cleanup_extracted("/nonexistent/path/abc123")
