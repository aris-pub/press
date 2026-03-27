"""Content-addressable storage functionality."""

import os

from app.storage.backend import StorageBackend

_storage_instance: StorageBackend | None = None


def get_storage() -> StorageBackend:
    """Return the singleton StorageBackend instance.

    In production this returns TigrisStorage; in test environments (TESTING=1)
    without Tigris credentials, falls back to InMemoryStorage.
    """
    global _storage_instance
    if _storage_instance is None:
        if os.getenv("TESTING") == "1" and not os.getenv("BUCKET_NAME"):
            from app.storage.memory import InMemoryStorage

            _storage_instance = InMemoryStorage()
        else:
            from app.storage.tigris import TigrisStorage

            _storage_instance = TigrisStorage()
    return _storage_instance
