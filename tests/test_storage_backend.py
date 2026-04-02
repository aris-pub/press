"""Tests for StorageBackend protocol and InMemoryStorage implementation."""

import os
from unittest.mock import patch

import pytest

from app.storage.backend import StorageBackend
from app.storage.memory import InMemoryStorage


class TestInMemoryStorageProtocol:
    def test_implements_protocol(self):
        assert isinstance(InMemoryStorage(), StorageBackend)


class TestInMemoryStorage:
    @pytest.fixture
    def storage(self):
        return InMemoryStorage()

    async def test_put_and_get(self, storage):
        await storage.put("key", b"data")
        assert await storage.get("key") == b"data"

    async def test_get_missing_key_raises(self, storage):
        with pytest.raises(KeyError):
            await storage.get("nonexistent")

    async def test_exists_true(self, storage):
        await storage.put("key", b"data")
        assert await storage.exists("key") is True

    async def test_exists_false(self, storage):
        assert await storage.exists("key") is False

    async def test_delete(self, storage):
        await storage.put("key", b"data")
        await storage.delete("key")
        assert await storage.exists("key") is False

    async def test_delete_missing_key_no_error(self, storage):
        await storage.delete("nonexistent")

    async def test_list_prefix(self, storage):
        await storage.put("scrolls/abc/index.html", b"<html>")
        await storage.put("scrolls/abc/style.css", b"body{}")
        await storage.put("scrolls/def/index.html", b"<html>")

        keys = await storage.list_prefix("scrolls/abc/")
        assert keys == ["scrolls/abc/index.html", "scrolls/abc/style.css"]

    async def test_list_prefix_empty(self, storage):
        assert await storage.list_prefix("nothing/") == []

    async def test_put_overwrites(self, storage):
        await storage.put("key", b"v1")
        await storage.put("key", b"v2")
        assert await storage.get("key") == b"v2"

    async def test_content_type_ignored_but_accepted(self, storage):
        await storage.put("key", b"data", content_type="text/html")
        assert await storage.get("key") == b"data"

    async def test_large_binary_data(self, storage):
        data = b"\x00" * 1024 * 1024
        await storage.put("big", data)
        assert await storage.get("big") == data


class TestGetStorageFallback:
    """Test that get_storage() falls back to InMemoryStorage in test environments."""

    def setup_method(self):
        import app.storage

        app.storage._storage_instance = None

    def teardown_method(self):
        import app.storage

        app.storage._storage_instance = None

    def test_returns_inmemory_when_testing_without_bucket(self):
        with patch.dict(os.environ, {"TESTING": "1"}, clear=False):
            os.environ.pop("BUCKET_NAME", None)
            os.environ.pop("AWS_ENDPOINT_URL_S3", None)
            from app.storage import get_storage

            storage = get_storage()
            assert isinstance(storage, InMemoryStorage)

    def test_returns_inmemory_when_no_tigris_credentials(self):
        with patch.dict(os.environ, {"ENVIRONMENT": "preview"}, clear=False):
            os.environ.pop("BUCKET_NAME", None)
            os.environ.pop("AWS_ENDPOINT_URL_S3", None)
            os.environ.pop("TESTING", None)
            from app.storage import get_storage

            storage = get_storage()
            assert isinstance(storage, InMemoryStorage)

    def test_returns_tigris_when_bucket_configured(self):
        env = {
            "TESTING": "1",
            "BUCKET_NAME": "test-bucket",
            "AWS_ENDPOINT_URL_S3": "https://fly.storage.tigris.dev",
        }
        with patch.dict(os.environ, env, clear=False):
            from app.storage import get_storage
            from app.storage.tigris import TigrisStorage

            storage = get_storage()
            assert isinstance(storage, TigrisStorage)
