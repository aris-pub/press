"""DOI minting service with async job processing."""

from datetime import datetime, timezone

import sentry_sdk
from sqlalchemy.ext.asyncio import AsyncSession

from app.integrations.zenodo import ZenodoClient, ZenodoError, get_zenodo_client
from app.logging_config import get_logger
from app.models.scroll import Scroll


class DOIService:
    """Service for minting DOIs via Zenodo API.

    Handles the full lifecycle: deposit creation, file upload, and publishing.
    """

    def __init__(self, zenodo_client: ZenodoClient):
        self.zenodo = zenodo_client
        self.logger = get_logger()

    async def mint_doi_for_scroll(self, scroll: Scroll, db: AsyncSession) -> bool:
        """Mint a DOI for a published scroll.

        This is the main entry point called when a scroll is published.
        Runs as a background task to avoid blocking the publish request.

        Args:
            scroll: Published scroll to mint DOI for
            db: Database session

        Returns:
            True if DOI minted successfully, False otherwise
        """
        try:
            # Set status to pending
            scroll.doi_status = "pending"
            await db.commit()

            self.logger.info(f"Starting DOI minting for scroll {scroll.id}")

            # Create Zenodo deposit with scroll metadata
            deposit = await self.zenodo.create_deposit(
                title=scroll.title,
                creators=self._parse_creators(scroll.authors),
                description=scroll.abstract,
                publication_date=scroll.published_at.strftime("%Y-%m-%d"),
                keywords=scroll.keywords or [],
                license_id=self._map_license(scroll.license),
            )

            # Update scroll with Zenodo deposit ID and reserved DOI
            scroll.zenodo_deposit_id = deposit.deposit_id
            scroll.doi = deposit.doi
            await db.commit()

            # Upload HTML content to Zenodo
            html_bytes = scroll.html_content.encode("utf-8")
            await self.zenodo.upload_file(
                bucket_url=deposit.bucket_url,
                filename=f"{scroll.url_hash}.html",
                content=html_bytes,
            )

            # Publish deposit (registers DOI with DataCite)
            published_deposit = await self.zenodo.publish_deposit(deposit.deposit_id)

            # Update scroll with final DOI and minted status
            scroll.doi = published_deposit.doi
            scroll.doi_status = "minted"
            scroll.doi_minted_at = datetime.now(timezone.utc)
            await db.commit()

            self.logger.info(f"Successfully minted DOI {scroll.doi} for scroll {scroll.id}")

            return True

        except ZenodoError as e:
            # Handle Zenodo-specific errors
            scroll.doi_status = "failed"
            await db.commit()

            self.logger.error(
                f"DOI minting failed for scroll {scroll.id}: {e} (retryable: {e.retryable})"
            )

            sentry_sdk.capture_exception(e)
            return False

        except Exception as e:
            # Handle unexpected errors
            scroll.doi_status = "failed"
            await db.commit()

            self.logger.error(f"Unexpected error minting DOI for scroll {scroll.id}: {e}")

            sentry_sdk.capture_exception(e)
            return False

    def _parse_creators(self, authors_str: str) -> list:
        """Parse comma-separated author string into Zenodo creators list.

        Args:
            authors_str: Comma-separated author names

        Returns:
            List of creator dicts with 'name' field
        """
        authors = [name.strip() for name in authors_str.split(",")]
        return [{"name": author} for author in authors if author]

    def _map_license(self, license_code: str) -> str:
        """Map scroll license to Zenodo license identifier.

        Args:
            license_code: Scroll license code ('cc-by-4.0' or 'arr')

        Returns:
            Zenodo license identifier
        """
        license_map = {
            "cc-by-4.0": "cc-by-4.0",
            "arr": "other-open",
        }
        return license_map.get(license_code, "other-open")


async def mint_doi_async(scroll_id: str):
    """Background task to mint DOI for a scroll.

    CRITICAL: Creates its own database session to avoid session lifecycle issues.
    The route handler should NOT pass its database session to this function.

    This function is called asynchronously after scroll publication.

    Args:
        scroll_id: UUID of scroll to mint DOI for
    """
    from uuid import UUID

    from sqlalchemy import select

    from app.database import AsyncSessionLocal

    logger = get_logger()
    zenodo_client = None
    db = None

    try:
        # Create new database session
        db = AsyncSessionLocal()

        # Get Zenodo client
        zenodo_client = get_zenodo_client()
        if not zenodo_client:
            logger.warning("Zenodo client not configured, skipping DOI minting")
            return

        # Load scroll
        result = await db.execute(select(Scroll).where(Scroll.id == UUID(scroll_id)))
        scroll = result.scalar_one_or_none()

        if not scroll:
            logger.error(f"Scroll {scroll_id} not found for DOI minting")
            return

        # Check if DOI already minted
        if scroll.doi_status == "minted":
            logger.info(f"Scroll {scroll_id} already has minted DOI, skipping")
            return

        # Mint DOI
        service = DOIService(zenodo_client)
        success = await service.mint_doi_for_scroll(scroll, db)

        if success:
            logger.info(f"DOI minted successfully for scroll {scroll_id}")
        else:
            logger.warning(f"DOI minting failed for scroll {scroll_id}")

    except Exception as e:
        logger.error(f"Error in background DOI minting task: {e}")
        sentry_sdk.capture_exception(e)

    finally:
        # Close Zenodo client
        if zenodo_client:
            await zenodo_client.close()

        # Close database session
        if db:
            await db.close()


async def mint_doi_safe(scroll_id: str):
    """Safe wrapper for mint_doi_async that ensures exceptions don't crash the background task.

    CRITICAL: All exceptions are caught and logged. This prevents silent failures.

    Args:
        scroll_id: UUID of scroll to mint DOI for
    """
    try:
        await mint_doi_async(scroll_id)
    except Exception as e:
        logger = get_logger()
        logger.error(f"Critical error in DOI minting for scroll {scroll_id}: {e}")
        sentry_sdk.capture_exception(e, extra={"scroll_id": scroll_id})
