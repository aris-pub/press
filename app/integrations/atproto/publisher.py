"""AtprotoPublisher: orchestrates Scroll -> pub.aris.scroll record publication.

Mirrors the DOIService pattern in app/integrations/zenodo.py: a single class
that owns the workflow (convert + call SDK + write back to DB) and lets the
caller (CLI, future on-publish hook) stay one-line-simple.

Failure posture matches the DOI integration: on SDK error, write
atproto_status='failed' and return False. The CLI can re-run for failed rows.
No retry queue; admin-driven retry is enough for the scope.
"""

from datetime import datetime, timezone
import logging
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.integrations.atproto.client import AtprotoClient
from app.integrations.atproto.lexicon import scroll_to_lexicon_record
from app.models.scroll import Scroll

logger = logging.getLogger(__name__)


LEXICON_NSID = "pub.aris.scroll"


class AtprotoPublisher:
    """Publish Press scrolls as pub.aris.scroll records on the configured PDS.

    `client` is injected so tests can use a fake; production callers build it
    via AtprotoClient.from_env() and pass it in.
    """

    def __init__(self, client: AtprotoClient, base_url: str):
        self.client = client
        self.base_url = base_url

    async def publish_scroll(self, scroll: Scroll, db: AsyncSession) -> bool:
        """Publish a single scroll. Idempotent via rkey = scroll.url_hash.

        Returns True on success, False on caught failure. Raises only on
        programmer errors (e.g. scroll missing url_hash).
        """
        if not scroll.url_hash:
            raise ValueError(
                f"cannot publish scroll {scroll.id} without url_hash; "
                "Scroll.publish enforces this, so this should not happen"
            )

        record = scroll_to_lexicon_record(scroll, base_url=self.base_url)

        try:
            response = self.client.put_record(
                collection=LEXICON_NSID,
                rkey=scroll.url_hash,
                record=record,
            )
        except Exception as exc:
            logger.exception(
                "atproto publish failed for scroll %s (url_hash=%s): %r",
                scroll.id,
                scroll.url_hash,
                exc,
            )
            scroll.atproto_status = "failed"
            await db.commit()
            return False

        scroll.atproto_uri = response.uri
        scroll.atproto_cid = response.cid
        scroll.atproto_status = "published"
        scroll.atproto_published_at = datetime.now(timezone.utc)
        await db.commit()

        logger.info(
            "atproto published scroll %s as %s (cid=%s)",
            scroll.url_hash,
            response.uri,
            response.cid,
        )
        return True

    async def publish_all(self, db: AsyncSession) -> int:
        """Walk every published scroll and publish_scroll each one.

        Returns the count of successful publishes. Per-scroll failures are
        logged and counted as failures; the batch continues.
        """
        result = await db.execute(
            select(Scroll).where(Scroll.status == "published").order_by(Scroll.published_at)
        )
        scrolls = result.scalars().all()

        successes = 0
        for scroll in scrolls:
            ok = await self.publish_scroll(scroll, db)
            if ok:
                successes += 1

        logger.info(
            "publish_all: %d/%d scrolls published", successes, len(scrolls)
        )
        return successes


def build_publisher_from_env(base_url: Optional[str] = None) -> AtprotoPublisher:
    """Construct a production-shaped publisher from env vars.

    BASE_URL is the public Press URL records will point at (e.g.
    https://scroll.press). Falls back to the BASE_URL env var Press already
    reads for other purposes.
    """
    import os

    if base_url is None:
        base_url = os.getenv("BASE_URL", "https://scroll.press")

    return AtprotoPublisher(
        client=AtprotoClient.from_env(),
        base_url=base_url,
    )
