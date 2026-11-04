"""DOI minting service with async job processing."""

import copy
from datetime import datetime, timezone
from typing import Optional

import sentry_sdk
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_base_url
from app.integrations.zenodo import ZenodoClient, ZenodoError, get_zenodo_client
from app.logging_config import get_logger
from app.models.scroll import Scroll
from app.models.user import ORCID_PATTERN, User

# Must match the upload_type and publication_type that create_deposit sends.
RELATED_RESOURCE_TYPE = "publication-preprint"


def scroll_landing_url(scroll: Scroll, base_url: Optional[str] = None) -> str:
    """Permanent Press URL for a scroll. Uses the hash, since slugs can change."""
    return f"{(base_url or get_base_url()).rstrip('/')}/scroll/{scroll.url_hash}"


def press_related_identifier(scroll: Scroll, base_url: Optional[str] = None) -> dict:
    """The related_identifiers entry that links a Zenodo record back to Press."""
    return {
        "identifier": scroll_landing_url(scroll, base_url),
        "relation": "isIdenticalTo",
        "resource_type": RELATED_RESOURCE_TYPE,
    }


def _name_key(name: str) -> str:
    """Normalize a person's name so 'Last, First' and 'first  last' compare equal."""
    if "," in name:
        family, given = name.split(",", 1)
        name = f"{given} {family}"
    return " ".join(name.split()).casefold()


def is_valid_orcid(orcid: Optional[str]) -> bool:
    """Check ORCID format and its ISO 7064 11,2 check digit.

    Zenodo rejects a deposit with a bad checksum, which would fail the whole DOI
    mint, so a bad iD is dropped instead of sent.
    """
    if not orcid or not ORCID_PATTERN.match(orcid):
        return False
    digits = orcid.replace("-", "")
    total = 0
    for ch in digits[:-1]:
        total = (total + int(ch)) * 2
    check = (12 - total % 11) % 11
    expected = "X" if check == 10 else str(check)
    return digits[-1] == expected


def attach_uploader_orcid(creators: list, uploader: Optional[User]) -> list:
    """Return a copy of creators with the uploader's ORCID on the uploader's own entry.

    The ORCID is attached only when exactly one creator name matches the uploader's
    display name, so it can never land on a co-author. A creator that already has a
    different ORCID is left alone.
    """
    result = copy.deepcopy(creators)
    if uploader is None or not is_valid_orcid(uploader.orcid_id) or not uploader.display_name:
        return result
    key = _name_key(uploader.display_name)
    matches = [c for c in result if _name_key(c.get("name", "")) == key]
    if len(matches) != 1:
        return result
    if not matches[0].get("orcid"):
        matches[0]["orcid"] = uploader.orcid_id
    return result


def merge_backfill_metadata(
    metadata: dict, scroll: Scroll, uploader: Optional[User], base_url: Optional[str] = None
) -> Optional[dict]:
    """Add the Press link and uploader ORCID to existing Zenodo metadata.

    Returns the full merged metadata, keeping every existing field, or None when
    nothing needs to change.
    """
    merged = copy.deepcopy(metadata)
    changed = False

    link = press_related_identifier(scroll, base_url)
    related = merged.get("related_identifiers") or []
    if not any(r.get("identifier") == link["identifier"] for r in related):
        merged["related_identifiers"] = related + [link]
        changed = True

    creators = merged.get("creators") or []
    new_creators = attach_uploader_orcid(creators, uploader)
    if new_creators != creators:
        merged["creators"] = new_creators
        changed = True

    return merged if changed else None


class DOIService:
    """Service for minting DOIs via Zenodo API.

    Handles the full lifecycle: deposit creation, file upload, and publishing.
    """

    def __init__(self, zenodo_client: ZenodoClient):
        self.zenodo = zenodo_client
        self.logger = get_logger()

    async def mint_doi_for_scroll(
        self, scroll: Scroll, db: AsyncSession, uploader: Optional[User] = None
    ) -> bool:
        """Mint a DOI for a published scroll.

        This is the main entry point called when a scroll is published.
        Runs as a background task to avoid blocking the publish request.

        Args:
            scroll: Published scroll to mint DOI for
            db: Database session
            uploader: User who published the scroll, whose ORCID goes on their own
                creator entry

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
                creators=attach_uploader_orcid(self._parse_creators(scroll.authors), uploader),
                description=scroll.abstract,
                publication_date=scroll.published_at.strftime("%Y-%m-%d"),
                keywords=scroll.keywords or [],
                license_id=self._map_license(scroll.license),
                related_identifiers=[press_related_identifier(scroll)],
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
    from sqlalchemy.orm import selectinload

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
        result = await db.execute(
            select(Scroll).options(selectinload(Scroll.user)).where(Scroll.id == UUID(scroll_id))
        )
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
        success = await service.mint_doi_for_scroll(scroll, db, uploader=scroll.user)

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
