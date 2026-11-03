"""Content-addressable storage: hashing rules, and no anonymous publish endpoint."""

from httpx import AsyncClient
import pytest

from app.storage.content_processing import generate_permanent_url

DETERMINISM_HTML = """<!DOCTYPE html>
<html>
<body>
    <h1>Determinism Test</h1>
    <p>This content should always produce the same hash.</p>
</body>
</html>"""


@pytest.mark.asyncio
class TestContentDeterminism:
    async def test_deterministic_hash_generation(self, test_db):
        """Identical content always produces identical hashes and tar data."""
        results = [await generate_permanent_url(test_db, DETERMINISM_HTML) for _ in range(5)]
        assert all(r == results[0] for r in results[1:])

    async def test_url_hash_is_prefix_of_content_hash(self, test_db):
        url_hash, content_hash, _ = await generate_permanent_url(test_db, DETERMINISM_HTML)
        assert len(url_hash) >= 12
        assert content_hash.startswith(url_hash)

    async def test_different_content_different_hashes(self, test_db):
        a = await generate_permanent_url(test_db, "<html><body><h1>Content 1</h1></body></html>")
        b = await generate_permanent_url(test_db, "<html><body><h1>Content 2</h1></body></html>")
        assert a[0] != b[0] and a[1] != b[1]

    async def test_line_ending_normalization(self, test_db):
        """LF, CRLF and CR versions of the same file get the same hash."""
        base = "<!DOCTYPE html>\n<html>\n<body>\n<h1>Test</h1>\n</body>\n</html>"
        variants = [base, base.replace("\n", "\r\n"), base.replace("\n", "\r")]
        hashes = [(await generate_permanent_url(test_db, v))[1] for v in variants]
        assert len(set(hashes)) == 1

    async def test_content_with_whitespace_variations(self, test_db):
        """Whitespace other than line endings is content and changes the hash."""
        base = "<html><body><h1>Test</h1></body></html>"
        spaces = "<html><body><h1>Test</h1>   </body></html>"
        tabs = "<html><body><h1>Test</h1>\t</body></html>"
        hashes = {(await generate_permanent_url(test_db, c))[1] for c in (base, spaces, tabs)}
        assert len(hashes) == 3


@pytest.mark.asyncio
class TestNoAnonymousPublishEndpoint:
    """POST /upload once published unvalidated HTML with no login (prs-yo3). Publishing
    goes through /upload-form only."""

    async def test_anonymous_post_upload_refused(self, client: AsyncClient, test_subject):
        files = {"file": ("x.html", b"<html><body><h1>x</h1></body></html>", "text/html")}
        response = await client.post("/upload", files=files)
        assert response.status_code == 405

    async def test_authenticated_post_upload_refused(
        self, authenticated_client: AsyncClient, test_subject
    ):
        files = {"file": ("x.html", b"<html><body><h1>x</h1></body></html>", "text/html")}
        response = await authenticated_client.post("/upload", files=files)
        assert response.status_code == 405
