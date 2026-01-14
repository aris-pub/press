"""Zenodo REST API client for DOI minting.

This module implements a simple HTTP client for the Zenodo REST API,
following the same pattern as app/emails/service.py.
"""

import asyncio
import os
from typing import Dict, List, Optional

import httpx
from pydantic import BaseModel
import sentry_sdk

from app.logging_config import get_logger


class ZenodoConfig(BaseModel):
    """Configuration for Zenodo API client."""

    api_token: str
    base_url: str = "https://zenodo.org"
    timeout: int = 30
    max_retries: int = 3


class ZenodoDeposit(BaseModel):
    """Zenodo deposit representation."""

    deposit_id: int
    doi: str
    doi_url: str
    bucket_url: str
    status: str  # 'draft', 'published'


class ZenodoError(Exception):
    """Base exception for Zenodo API errors."""

    def __init__(self, message: str, status_code: Optional[int] = None, retryable: bool = False):
        super().__init__(message)
        self.status_code = status_code
        self.retryable = retryable


class ZenodoClient:
    """Async HTTP client for Zenodo REST API.

    Implements the publisher model: Press has ONE organizational account
    and mints DOIs on behalf of all users.
    """

    def __init__(self, config: ZenodoConfig):
        self.config = config
        self.logger = get_logger()
        self.client = httpx.AsyncClient(
            base_url=config.base_url,
            headers={
                "Authorization": f"Bearer {config.api_token}",
                "Content-Type": "application/json",
            },
            timeout=config.timeout,
        )

    async def close(self):
        """Close HTTP client."""
        await self.client.aclose()

    async def create_deposit(
        self,
        title: str,
        creators: List[Dict[str, str]],
        description: str,
        publication_date: str,
        keywords: List[str],
        license_id: str = "cc-by-4.0",
    ) -> ZenodoDeposit:
        """Create a new Zenodo deposit.

        Args:
            title: Scroll title
            creators: List of author dicts with 'name', 'affiliation', 'orcid' (optional)
            description: Abstract text
            publication_date: ISO date string (YYYY-MM-DD)
            keywords: List of keyword strings
            license_id: License identifier (cc-by-4.0, cc0-1.0, etc.)

        Returns:
            ZenodoDeposit with deposit_id, doi, and bucket_url

        Raises:
            ZenodoError: If deposit creation fails
        """
        metadata = {
            "metadata": {
                "title": title,
                "upload_type": "publication",
                "publication_type": "preprint",
                "description": description,
                "creators": creators,
                "publication_date": publication_date,
                "keywords": keywords,
                "access_right": "open",
                "license": license_id,
                "communities": [{"identifier": "scrollpress"}],
                "prereserve_doi": True,
            }
        }

        try:
            response = await self._request_with_retry(
                "POST", "/api/deposit/depositions", json=metadata
            )

            deposit_data = response.json()

            # Extract DOI from metadata
            doi = deposit_data["metadata"]["prereserve_doi"]["doi"]
            doi_url = f"https://doi.org/{doi}"

            deposit = ZenodoDeposit(
                deposit_id=deposit_data["id"],
                doi=doi,
                doi_url=doi_url,
                bucket_url=deposit_data["links"]["bucket"],
                status="draft",
            )

            self.logger.info(f"Created Zenodo deposit {deposit.deposit_id} with DOI {deposit.doi}")

            return deposit

        except httpx.HTTPStatusError as e:
            self._handle_http_error(e, "create deposit")
        except Exception as e:
            self.logger.error(f"Unexpected error creating Zenodo deposit: {e}")
            sentry_sdk.capture_exception(e)
            raise ZenodoError(f"Failed to create deposit: {e}", retryable=True)

    async def upload_file(self, bucket_url: str, filename: str, content: bytes) -> bool:
        """Upload a file to Zenodo deposit bucket.

        Args:
            bucket_url: Bucket URL from deposit creation
            filename: Name of file to upload
            content: File content as bytes

        Returns:
            True if upload successful

        Raises:
            ZenodoError: If upload fails
        """
        try:
            # Use new bucket API (PUT to bucket URL)
            file_url = f"{bucket_url}/{filename}"

            await self._request_with_retry(
                "PUT",
                file_url,
                content=content,
                headers={"Content-Type": "text/html"},
            )

            self.logger.info(f"Uploaded file {filename} to Zenodo deposit")
            return True

        except httpx.HTTPStatusError as e:
            self._handle_http_error(e, "upload file")
        except Exception as e:
            self.logger.error(f"Unexpected error uploading file to Zenodo: {e}")
            sentry_sdk.capture_exception(e)
            raise ZenodoError(f"Failed to upload file: {e}", retryable=True)

    async def publish_deposit(self, deposit_id: int) -> ZenodoDeposit:
        """Publish a Zenodo deposit and register DOI with DataCite.

        Args:
            deposit_id: Zenodo deposit ID

        Returns:
            Updated ZenodoDeposit with published status

        Raises:
            ZenodoError: If publish fails
        """
        try:
            response = await self._request_with_retry(
                "POST", f"/api/deposit/depositions/{deposit_id}/actions/publish"
            )

            deposit_data = response.json()

            deposit = ZenodoDeposit(
                deposit_id=deposit_data["id"],
                doi=deposit_data["doi"],
                doi_url=deposit_data["doi_url"],
                bucket_url=deposit_data["links"]["bucket"],
                status="published",
            )

            self.logger.info(
                f"Published Zenodo deposit {deposit_id}, DOI registered: {deposit.doi}"
            )

            return deposit

        except httpx.HTTPStatusError as e:
            self._handle_http_error(e, "publish deposit")
        except Exception as e:
            self.logger.error(f"Unexpected error publishing Zenodo deposit: {e}")
            sentry_sdk.capture_exception(e)
            raise ZenodoError(f"Failed to publish deposit: {e}", retryable=True)

    async def _request_with_retry(self, method: str, url: str, **kwargs) -> httpx.Response:
        """Make HTTP request with exponential backoff retry logic.

        Args:
            method: HTTP method
            url: Request URL (can be relative to base_url or absolute)
            **kwargs: Additional httpx request parameters

        Returns:
            HTTP response

        Raises:
            httpx.HTTPStatusError: On final failure after retries
        """
        for attempt in range(self.config.max_retries):
            try:
                # Handle absolute URLs (for bucket operations)
                if url.startswith("http"):
                    response = await httpx.AsyncClient().request(
                        method,
                        url,
                        headers=self.client.headers,
                        timeout=self.config.timeout,
                        **kwargs,
                    )
                else:
                    response = await self.client.request(method, url, **kwargs)

                response.raise_for_status()

                # Check rate limits
                if "X-RateLimit-Remaining" in response.headers:
                    remaining = int(response.headers["X-RateLimit-Remaining"])
                    if remaining < 10:
                        self.logger.warning(
                            f"Zenodo rate limit low: {remaining} requests remaining"
                        )

                return response

            except httpx.HTTPStatusError as e:
                # Don't retry client errors (4xx) except 429 (rate limit)
                if 400 <= e.response.status_code < 500 and e.response.status_code != 429:
                    raise

                # Retry server errors (5xx) and rate limits (429)
                if attempt < self.config.max_retries - 1:
                    wait_time = 2**attempt  # Exponential backoff: 1s, 2s, 4s
                    self.logger.warning(
                        f"Zenodo API error {e.response.status_code}, "
                        f"retrying in {wait_time}s (attempt {attempt + 1}/{self.config.max_retries})"
                    )
                    await asyncio.sleep(wait_time)
                else:
                    raise

    def _handle_http_error(self, error: httpx.HTTPStatusError, operation: str):
        """Convert HTTP errors to ZenodoError with proper classification.

        Args:
            error: HTTP status error
            operation: Operation description for logging

        Raises:
            ZenodoError: Classified error with retryable flag
        """
        status_code = error.response.status_code

        # Try to extract error message from response
        try:
            error_data = error.response.json()
            message = error_data.get("message", str(error))
        except Exception:
            message = str(error)

        # Sanitize error message to prevent token leakage
        if self.config.api_token and self.config.api_token in message:
            message = message.replace(self.config.api_token, "[REDACTED]")

        # Classify error
        if status_code == 429:
            retryable = True
            error_msg = f"Rate limit exceeded while {operation}: {message}"
        elif 500 <= status_code < 600:
            retryable = True
            error_msg = f"Zenodo server error while {operation}: {message}"
        else:
            retryable = False
            error_msg = f"Zenodo API error while {operation}: {message}"

        self.logger.error(f"{error_msg} (status {status_code})")
        sentry_sdk.capture_exception(error)

        raise ZenodoError(error_msg, status_code=status_code, retryable=retryable)


def get_zenodo_client() -> Optional[ZenodoClient]:
    """Get configured Zenodo client instance.

    Returns:
        ZenodoClient if properly configured, None otherwise
    """
    api_token = os.getenv("ZENODO_API_TOKEN")
    base_url = os.getenv("ZENODO_BASE_URL", "https://zenodo.org")

    # Don't initialize client if API token is missing or placeholder
    if not api_token or api_token == "your_zenodo_personal_access_token_here":
        return None

    config = ZenodoConfig(api_token=api_token, base_url=base_url)
    return ZenodoClient(config)
