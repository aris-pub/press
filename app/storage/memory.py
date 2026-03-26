"""In-memory storage backend for testing."""

from app.storage.backend import StorageBackend


class InMemoryStorage:
    """Dict-backed StorageBackend for tests. Not for production use."""

    def __init__(self) -> None:
        self._store: dict[str, bytes] = {}

    async def put(
        self, key: str, data: bytes, content_type: str = "application/octet-stream"
    ) -> None:
        self._store[key] = data

    async def get(self, key: str) -> bytes:
        if key not in self._store:
            raise KeyError(key)
        return self._store[key]

    async def delete(self, key: str) -> None:
        self._store.pop(key, None)

    async def exists(self, key: str) -> bool:
        return key in self._store

    async def list_prefix(self, prefix: str) -> list[str]:
        return sorted(k for k in self._store if k.startswith(prefix))


assert isinstance(InMemoryStorage(), StorageBackend)
