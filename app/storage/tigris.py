"""Tigris (S3-compatible) storage backend using aioboto3."""

import os

import aioboto3
from botocore.config import Config
from botocore.exceptions import ClientError


class TigrisStorage:
    """StorageBackend backed by Tigris (Fly.io S3-compatible object storage)."""

    def __init__(
        self,
        bucket_name: str | None = None,
        endpoint_url: str | None = None,
        aws_access_key_id: str | None = None,
        aws_secret_access_key: str | None = None,
        region_name: str = "auto",
    ) -> None:
        self._bucket = bucket_name or os.environ["BUCKET_NAME"]
        self._endpoint_url = endpoint_url or os.environ["AWS_ENDPOINT_URL_S3"]
        self._access_key = aws_access_key_id or os.environ.get("AWS_ACCESS_KEY_ID")
        self._secret_key = aws_secret_access_key or os.environ.get("AWS_SECRET_ACCESS_KEY")
        self._region = region_name
        self._session = aioboto3.Session()

    def _client_kwargs(self) -> dict:
        return {
            "service_name": "s3",
            "endpoint_url": self._endpoint_url,
            "aws_access_key_id": self._access_key,
            "aws_secret_access_key": self._secret_key,
            "region_name": self._region,
            "config": Config(s3={"addressing_style": "virtual"}),
        }

    async def put(
        self, key: str, data: bytes, content_type: str = "application/octet-stream"
    ) -> None:
        async with self._session.client(**self._client_kwargs()) as s3:
            await s3.put_object(Bucket=self._bucket, Key=key, Body=data, ContentType=content_type)

    async def get(self, key: str) -> bytes:
        async with self._session.client(**self._client_kwargs()) as s3:
            try:
                response = await s3.get_object(Bucket=self._bucket, Key=key)
                return await response["Body"].read()
            except ClientError as e:
                if e.response["Error"]["Code"] == "NoSuchKey":
                    raise KeyError(key) from e
                raise

    async def delete(self, key: str) -> None:
        async with self._session.client(**self._client_kwargs()) as s3:
            await s3.delete_object(Bucket=self._bucket, Key=key)

    async def exists(self, key: str) -> bool:
        async with self._session.client(**self._client_kwargs()) as s3:
            try:
                await s3.head_object(Bucket=self._bucket, Key=key)
                return True
            except ClientError:
                return False

    async def list_prefix(self, prefix: str) -> list[str]:
        keys: list[str] = []
        async with self._session.client(**self._client_kwargs()) as s3:
            paginator = s3.get_paginator("list_objects_v2")
            async for page in paginator.paginate(Bucket=self._bucket, Prefix=prefix):
                for obj in page.get("Contents", []):
                    keys.append(obj["Key"])
        return sorted(keys)
