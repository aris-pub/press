"""Content-addressable storage functionality."""

import os

from app.storage.backend import StorageBackend

_storage_instance: StorageBackend | None = None


def get_storage() -> StorageBackend:
    """Return the singleton StorageBackend instance.

    Returns TigrisStorage when credentials are configured, otherwise
    falls back to InMemoryStorage (tests, preview deploys without Tigris).
    """
    global _storage_instance
    if _storage_instance is None:
        has_tigris = bool(os.getenv("BUCKET_NAME") and os.getenv("AWS_ENDPOINT_URL_S3"))
        if has_tigris:
            from app.storage.tigris import TigrisStorage

            _storage_instance = TigrisStorage()
        else:
            from app.storage.memory import InMemoryStorage

            _storage_instance = InMemoryStorage()
    return _storage_instance
