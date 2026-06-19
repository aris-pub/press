"""Publish Press scrolls as pub.aris.scroll records on the configured PDS.

Usage:
    # Publish every published scroll on the configured DB.
    uv run --frozen --no-dev python scripts/publish_atproto.py publish-all

    # Publish a single scroll by its url_hash.
    uv run --frozen --no-dev python scripts/publish_atproto.py publish <url_hash>

Environment variables required (set as Fly secrets in production):
    ATPROTO_HANDLE        e.g. aris-pub.bsky.social
    ATPROTO_APP_PASSWORD  the 19-char Bluesky app password
    ATPROTO_DID           the account's did:plc:... identifier
    ATPROTO_PDS_URL       per-user PDS endpoint from the DID document
    BASE_URL              public Press URL (e.g. https://scroll.press)

Failure posture: per-scroll failures are logged and written as
atproto_status='failed' on the scroll row. The batch continues. Re-run for
failures by invoking publish-all again (put_record is upsert).
"""

import asyncio
import logging
import sys

from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.integrations.atproto.publisher import build_publisher_from_env
from app.models.scroll import Scroll

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("publish_atproto")


async def publish_all() -> int:
    publisher = build_publisher_from_env()
    async with AsyncSessionLocal() as db:
        count = await publisher.publish_all(db)
    print(f"published {count} scrolls")
    return 0


async def publish_one(url_hash: str) -> int:
    publisher = build_publisher_from_env()
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Scroll).where(Scroll.url_hash == url_hash))
        scroll = result.scalar_one_or_none()
        if scroll is None:
            print(f"no scroll with url_hash={url_hash!r}", file=sys.stderr)
            return 1
        ok = await publisher.publish_scroll(scroll, db)
        if ok:
            print(f"published: {scroll.atproto_uri}")
            return 0
        print(f"failed; status={scroll.atproto_status}", file=sys.stderr)
        return 2


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print(__doc__)
        return 64

    cmd = argv[1]
    if cmd == "publish-all":
        return asyncio.run(publish_all())
    if cmd == "publish":
        if len(argv) < 3:
            print("usage: publish <url_hash>", file=sys.stderr)
            return 64
        return asyncio.run(publish_one(argv[2]))

    print(f"unknown command: {cmd!r}", file=sys.stderr)
    return 64


if __name__ == "__main__":
    sys.exit(main(sys.argv))
