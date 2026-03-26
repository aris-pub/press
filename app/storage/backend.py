"""StorageBackend protocol for abstracting file storage operations."""

from typing import Protocol, runtime_checkable


@runtime_checkable
class StorageBackend(Protocol):
    async def put(
        self, key: str, data: bytes, content_type: str = "application/octet-stream"
    ) -> None:
        """Store data at key."""
        ...

    async def get(self, key: str) -> bytes:
        """Retrieve data at key. Raises KeyError if not found."""
        ...

    async def delete(self, key: str) -> None:
        """Delete data at key."""
        ...

    async def exists(self, key: str) -> bool:
        """Check if key exists."""
        ...

    async def list_prefix(self, prefix: str) -> list[str]:
        """List all keys under prefix."""
        ...
