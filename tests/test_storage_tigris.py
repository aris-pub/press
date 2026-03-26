"""Integration tests for TigrisStorage using moto standalone server."""

import boto3
from moto.server import ThreadedMotoServer
import pytest

from app.storage.tigris import TigrisStorage

BUCKET = "test-bucket"


@pytest.fixture(scope="module")
def moto_server():
    """Run moto as a real HTTP server so aioboto3 works against it."""
    server = ThreadedMotoServer(port=0, verbose=False)
    server.start()
    host, port = server.get_host_and_port()
    endpoint = f"http://{host}:{port}"
    yield endpoint
    server.stop()


@pytest.fixture
def storage(moto_server):
    """Create a TigrisStorage backed by moto HTTP server."""
    # Create bucket via sync boto3
    s3 = boto3.client(
        "s3",
        endpoint_url=moto_server,
        aws_access_key_id="testing",
        aws_secret_access_key="testing",
        region_name="us-east-1",
    )
    s3.create_bucket(Bucket=BUCKET)

    ts = TigrisStorage(
        bucket_name=BUCKET,
        endpoint_url=moto_server,
        aws_access_key_id="testing",
        aws_secret_access_key="testing",
        region_name="us-east-1",
    )
    yield ts

    # Clean up all objects
    response = s3.list_objects_v2(Bucket=BUCKET)
    for obj in response.get("Contents", []):
        s3.delete_object(Bucket=BUCKET, Key=obj["Key"])
    s3.delete_bucket(Bucket=BUCKET)


class TestTigrisStorage:
    async def test_put_and_get(self, storage):
        await storage.put("test/file.txt", b"hello world", content_type="text/plain")
        data = await storage.get("test/file.txt")
        assert data == b"hello world"

    async def test_get_missing_raises_key_error(self, storage):
        with pytest.raises(KeyError):
            await storage.get("does/not/exist")

    async def test_exists(self, storage):
        assert await storage.exists("nope") is False
        await storage.put("yep", b"data")
        assert await storage.exists("yep") is True

    async def test_delete(self, storage):
        await storage.put("to-delete", b"data")
        await storage.delete("to-delete")
        assert await storage.exists("to-delete") is False

    async def test_list_prefix(self, storage):
        await storage.put("scrolls/abc/index.html", b"<html>")
        await storage.put("scrolls/abc/style.css", b"body{}")
        await storage.put("scrolls/def/index.html", b"<html>")

        keys = await storage.list_prefix("scrolls/abc/")
        assert keys == ["scrolls/abc/index.html", "scrolls/abc/style.css"]
