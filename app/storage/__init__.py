"""Content-addressable storage functionality."""

from app.storage.backend import StorageBackend

_storage_instance: StorageBackend | None = None


def get_storage() -> StorageBackend:
    """Return the singleton StorageBackend instance.

    In production this returns TigrisStorage; tests patch this function.
    """
    global _storage_instance
    if _storage_instance is None:
        from app.storage.tigris import TigrisStorage

        _storage_instance = TigrisStorage()
    return _storage_instance
